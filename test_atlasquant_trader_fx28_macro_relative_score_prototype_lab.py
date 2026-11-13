"""Experimental 28-pair arithmetic tested ONLY with fabricated impact points."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from copy import deepcopy
import unittest

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS
from atlasquant_trader_fx28_macro_relative_score_prototype_lab import (
    HypotheticalMacroFactorClaim as F,
    evaluate_experimental_fx28_macro_relative_score_lab as evaluate,
    WEIGHTS, SCHEMA,
)

START = datetime(2026, 11, 15, 22, tzinfo=timezone.utc)
BEFORE = START - timedelta(hours=2)


def samples(*, values=None, conflict=None):
    values = values or {}
    claims = []
    for currency in sorted(CURRENCIES):
        for factor in WEIGHTS:
            points = values.get(currency, 0)
            if conflict is not None and currency == conflict:
                points = 80 if factor != "inflation_impact" else -80
            claims.append(F(
                currency=currency, category=factor,
                signed_impact_points=points,
                event_published_at_utc=BEFORE-timedelta(hours=1),
                source_locally_captured_at_utc=BEFORE-timedelta(minutes=10),
                event_root_id=f"EVENT.{currency}.{factor.upper()}",
                source_sha256_claim="a"*64,
            ))
    return claims


class Fx28ExperimentalAggregationTests(unittest.TestCase):
    def execute(self, *, inputs=None, horizon="D1", start=START, now=BEFORE):
        return evaluate(
            horizon=horizon, window_start_utc=start,
            calculated_at_utc=now,
            claimed_factors=samples() if inputs is None else inputs,
        )

    def safe(self, result):
        self.assertEqual(result["schema"], SCHEMA)
        self.assertEqual(result["operational_bias"], "AGUARDAR")
        self.assertIsNone(result["directional_bias"])
        self.assertIsNone(result["calibrated_probability"])
        self.assertIsNone(result["percentage_accuracy"])
        self.assertFalse(result["inputs_are_authenticated_macro_sources"])
        self.assertFalse(result["macro_surprises_were_calculated_from_official_values"])
        self.assertFalse(result["first_seen_independently_attested"])
        self.assertFalse(result["prospective_forecast_witnessed"])
        self.assertFalse(result["out_of_sample_accuracy_measured"])
        for flag in ("trade_authorized", "publishable", "live_alert_allowed",
                     "scheduler_enabled", "worker_enabled"):
            self.assertFalse(result[flag], flag)
        self.assertTrue(result["research_only"])
        self.assertEqual(result["new_cost_brl"], 0)
        self.assertEqual(result["file_writes"], 0)
        self.assertEqual(result["http_requests"], 0)
        self.assertEqual([r["pair"] for r in result["pairs"]], list(OFFICIAL_PAIRS))
        self.assertEqual(len(result["pairs"]), 28)
        for pair in result["pairs"]:
            self.assertFalse(pair["trade_authorized"])
            self.assertFalse(pair["real_market_direction_authenticated"])
            self.assertIn(pair["research_relative_label"],
                          ("BASE_RELATIVE","QUOTE_RELATIVE","NEUTRAL","AGUARDAR"))

    def blocked(self, **kwargs):
        r=self.execute(**kwargs)
        self.safe(r)
        self.assertEqual(r["state"],"LAB_FX28_HYPOTHETICAL_MACRO_SCORE_BLOCKED")
        self.assertEqual(r["currency_score_claims_reconciled"],0)
        self.assertEqual(r["hypothetical_labeled_pair_count"],0)
        self.assertTrue(all(x["research_relative_label"]=="AGUARDAR"
                            for x in r["pairs"]))
        return r

    def test_01_all_neutral_reconciles_28_no_macro_signal(self):
        r=self.execute()
        self.safe(r)
        self.assertEqual(r["state"],"LAB_FX28_HYPOTHETICAL_MACRO_SCORE_COHERENT_NO_GO")
        self.assertTrue(r["bilateral_consistency_rechecked"])
        self.assertEqual(r["currency_score_claims_reconciled"],8)
        self.assertEqual(r["hypothetical_labeled_pair_count"],0)
        self.assertTrue(all(x["research_relative_label"]=="NEUTRAL"
                            for x in r["pairs"]))
        self.assertEqual(r["abstained_pair_count"],0)
        self.assertEqual(r["currency_scores_research_only"]["USD"],0)

    def test_02_hypothetical_usd_eur_diff_oriented_correctly(self):
        r=self.execute(inputs=samples(values={"USD":80,"EUR":-50}))
        self.safe(r)
        eurusd=next(x for x in r["pairs"] if x["pair"]=="EUR/USD")
        usdjpy=next(x for x in r["pairs"] if x["pair"]=="USD/JPY")
        self.assertEqual(eurusd["research_relative_label"],"QUOTE_RELATIVE")
        self.assertEqual(eurusd["hypothetical_points"],-130)
        self.assertEqual(usdjpy["research_relative_label"],"BASE_RELATIVE")
        self.assertEqual(usdjpy["hypothetical_points"],80)
        self.assertIsNone(r["calibrated_probability"])

    def test_03_root_factor_duplicate_blocks_no_double_count(self):
        factors=samples()
        factors[1]=replace(factors[1],event_root_id=factors[0].event_root_id)
        self.assertEqual(self.blocked(inputs=factors)["reason"],
                         "INVALID_OR_DUPLICATE_FACTOR_CLAIMS")

    def test_04_missing_eighth_currency_factor_blocks_without_filling_zero(self):
        factors=samples()
        factors.pop()
        self.assertEqual(self.blocked(inputs=factors)["reason"],
                         "INVALID_WINDOW_OR_CUTOFF")

    def test_05_duplicate_currency_category_blocked(self):
        factors=samples()
        factors[1]=replace(factors[1],category=factors[0].category)
        self.assertEqual(self.blocked(inputs=factors)["reason"],
                         "INVALID_OR_DUPLICATE_FACTOR_CLAIMS")

    def test_06_future_capture_or_release_blocks(self):
        for field,value in (
            ("source_locally_captured_at_utc",BEFORE+timedelta(seconds=1)),
            ("event_published_at_utc",BEFORE+timedelta(seconds=1)),
            ("event_published_at_utc",BEFORE-timedelta(days=80)),
            ("source_locally_captured_at_utc",BEFORE-timedelta(days=1)),
        ):
            with self.subTest(field=field):
                factors=samples()
                factors[0]=replace(factors[0],**{field:value})
                self.blocked(inputs=factors)

    def test_07_invalid_number_type_limits_and_nan_not_admitted(self):
        for num in (True,1.2,None,"40",101,-101,float("nan")):
            with self.subTest(num=num):
                factors=samples()
                factors[0]=replace(factors[0],signed_impact_points=num)
                self.blocked(inputs=factors)

    def test_08_invalid_sha_and_root_id_not_authenticated(self):
        for field,bad in (
            ("source_sha256_claim","not a sha"),
            ("source_sha256_claim","A"*64),
            ("event_root_id","DROP TABLE"),
            ("event_root_id","x"),
        ):
            with self.subTest(field=field):
                factors=samples()
                factors[0]=replace(factors[0],**{field:bad})
                self.blocked(inputs=factors)

    def test_09_bad_window_start_horizon_and_stale_calculation(self):
        for horizon,start,now in (
            ("MONTHLY",START,BEFORE),
            ("D1",START-timedelta(days=2),BEFORE),
            ("W1",START+timedelta(days=1),BEFORE),
            ("D1",START,START),
            ("D1",START,START+timedelta(seconds=1)),
            ("D1",START,START-timedelta(hours=13)),
            ("D1",START,BEFORE.replace(tzinfo=None)),
            ("D1",START,BEFORE.replace(microsecond=1)),
        ):
            with self.subTest(horizon=horizon,start=start,now=now):
                self.blocked(horizon=horizon,start=start,now=now)

    def test_10_conflicting_usd_factors_abstain_exactly_seven_pairs(self):
        r=self.execute(inputs=samples(conflict="USD"))
        self.safe(r)
        self.assertEqual(r["conflicting_currency_codes"],["USD"])
        abstained={x["pair"] for x in r["pairs"]
                   if x["research_relative_label"]=="AGUARDAR"}
        self.assertEqual(len(abstained),7)
        self.assertTrue(all("USD" in x for x in abstained))
        self.assertEqual(r["abstained_pair_count"],7)
        self.assertEqual(next(x for x in r["pairs"] if x["pair"]=="EUR/USD")["reason"],
                         "CONFLICTING_STRONG_MACRO_COMPONENTS")

    def test_11_weekly_extra_abstention_40_to_55_reduces_hypotheses(self):
        factors=samples(values={"EUR":50})
        daily=self.execute(inputs=factors,horizon="D1")
        weekly=self.execute(inputs=factors,horizon="W1")
        self.safe(daily)
        self.safe(weekly)
        day=next(x for x in daily["pairs"] if x["pair"]=="EUR/USD")
        week=next(x for x in weekly["pairs"] if x["pair"]=="EUR/USD")
        self.assertEqual(day["research_relative_label"],"BASE_RELATIVE")
        self.assertEqual(day["hypothetical_points"],50)
        self.assertEqual(week["research_relative_label"],"AGUARDAR")
        self.assertIsNone(week["hypothetical_points"])
        self.assertLess(weekly["hypothetical_labeled_pair_count"],
                        daily["hypothetical_labeled_pair_count"])

    def test_12_fixed_config_digest_independent_of_input_order(self):
        factors=samples(values={"EUR":60,"USD":-15,"AUD":30})
        r1=self.execute(inputs=factors)
        r2=self.execute(inputs=list(reversed(factors)))
        self.safe(r1); self.safe(r2)
        self.assertEqual(r1,r2)
        self.assertEqual(len(r1["model_contract_sha256"]),64)
        self.assertEqual(sum(r1["weights"].values()),100)

    def test_13_no_market_result_accuracy_or_real_probability_in_scores(self):
        out=self.execute(inputs=samples(values={"EUR":100,"USD":-100}))
        self.safe(out)
        self.assertGreater(out["hypothetical_labeled_pair_count"],0)
        self.assertIsNone(out["calibrated_probability"])
        self.assertFalse(out["prospective_forecast_witnessed"])
        self.assertFalse(out["out_of_sample_accuracy_measured"])
        self.assertTrue(out["score_is_synthetic_relative_points_not_economic_measure"])

    def test_14_timezone_equivalent_snapshot_reproduces_scores(self):
        utc=self.execute(inputs=samples(values={"EUR":45}))
        offset=timezone(timedelta(hours=-4))
        mt=BEFORE.astimezone(offset)
        converted=[replace(f,
            event_published_at_utc=f.event_published_at_utc.astimezone(offset),
            source_locally_captured_at_utc=f.source_locally_captured_at_utc.astimezone(offset)
        ) for f in samples(values={"EUR":45})]
        other=self.execute(inputs=converted,now=mt,
                           start=START.astimezone(offset))
        self.safe(other)
        self.assertEqual(utc,other)

    def test_15_caller_records_not_mutated(self):
        original=samples(values={"EUR":70})
        copy=deepcopy(original)
        self.execute(inputs=original)
        self.assertEqual(original,copy)

    def test_16_signs_conflict_that_cannot_be_offset_by_high_weight(self):
        factor=samples(values={"GBP":95})
        ix=next(i for i,f in enumerate(factor)
                if f.currency=="GBP" and f.category=="inflation_impact")
        factor[ix]=replace(factor[ix],signed_impact_points=-95)
        r=self.execute(inputs=factor)
        self.safe(r)
        self.assertIn("GBP",r["conflicting_currency_codes"])
        self.assertEqual(
            next(x for x in r["pairs"] if x["pair"]=="GBP/USD")["research_relative_label"],
            "AGUARDAR")

    def test_17_prestart_only_no_hindsight_fake_past_forecast(self):
        for asof in (START,START+timedelta(days=1)):
            with self.subTest(asof=asof):
                r=self.blocked(now=asof)
                self.assertFalse(r["prospective_forecast_witnessed"])


if __name__=="__main__":
    unittest.main()
