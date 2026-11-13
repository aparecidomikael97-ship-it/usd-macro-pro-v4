"""Experimental 28-pair arithmetic tested ONLY with fabricated impact points."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from copy import deepcopy
from hashlib import sha256
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
                source_sha256_claim=sha256(f"{currency}:{factor}".encode("ascii")).hexdigest(),
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
        self.assertFalse(result["pair_claims_are_independent_economic_events"])
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
                         "REUSED_CATALYST_NOT_AN_INDEPENDENT_MACRO_FACTOR")

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



    def test_18_same_news_root_usable_for_usd_and_eur_without_double_count(self):
        factors=samples(values={"USD":70,"EUR":-20})
        usd=next(x for x in factors
                 if x.currency=="USD" and x.category=="inflation_impact")
        index=next(i for i,x in enumerate(factors)
                   if x.currency=="EUR" and x.category=="inflation_impact")
        factors[index]=replace(factors[index], event_root_id=usd.event_root_id, source_sha256_claim=usd.source_sha256_claim)
        out=self.execute(inputs=factors)
        self.safe(out)
        self.assertEqual(out["state"],"LAB_FX28_HYPOTHETICAL_MACRO_SCORE_COHERENT_NO_GO")
        self.assertEqual(out["distinct_root_catalyst_claim_count"],31)
        self.assertEqual(out["shared_event_root_ids"],[usd.event_root_id])
        self.assertEqual(out["currency_score_claims_reconciled"],8)
        self.assertIsNone(out["calibrated_probability"])

    def test_19_shared_root_conflicting_sha_is_not_same_document(self):
        factors=samples()
        usd=next(x for x in factors
                 if x.currency=="USD" and x.category=="inflation_impact")
        index=next(i for i,x in enumerate(factors)
                   if x.currency=="EUR" and x.category=="inflation_impact")
        factors[index]=replace(factors[index], event_root_id=usd.event_root_id,
                               source_sha256_claim="b"*64)
        out=self.blocked(inputs=factors)
        self.assertEqual(out["reason"],"REUSED_CATALYST_NOT_AN_INDEPENDENT_MACRO_FACTOR")

    def test_20_same_root_cross_category_rejected_not_independent(self):
        factors=samples()
        usd=next(x for x in factors
                 if x.currency=="USD" and x.category=="inflation_impact")
        index=next(i for i,x in enumerate(factors)
                   if x.currency=="EUR" and x.category=="activity_impact")
        factors[index]=replace(factors[index],event_root_id=usd.event_root_id, source_sha256_claim=usd.source_sha256_claim)
        out=self.blocked(inputs=factors)
        self.assertEqual(out["reason"],"REUSED_CATALYST_NOT_AN_INDEPENDENT_MACRO_FACTOR")

    def test_21_shared_root_wrong_publication_or_capture_is_blocked(self):
        for field in ("event_published_at_utc","source_locally_captured_at_utc"):
            with self.subTest(field=field):
                factors=samples()
                usd=next(x for x in factors
                         if x.currency=="USD" and x.category=="inflation_impact")
                index=next(i for i,x in enumerate(factors)
                           if x.currency=="EUR" and x.category=="inflation_impact")
                factors[index]=replace(
                    factors[index],event_root_id=usd.event_root_id,
                    source_sha256_claim=usd.source_sha256_claim,
                    **{field:getattr(usd,field)-timedelta(seconds=1)})
                out=self.blocked(inputs=factors)
                self.assertEqual(out["reason"],"REUSED_CATALYST_NOT_AN_INDEPENDENT_MACRO_FACTOR")

    def test_22_shared_root_order_independent_without_false_accuracy(self):
        factors=samples(values={"USD":55,"EUR":-40})
        usd=next(x for x in factors
                 if x.currency=="USD" and x.category=="inflation_impact")
        index=next(i for i,x in enumerate(factors)
                   if x.currency=="EUR" and x.category=="inflation_impact")
        factors[index]=replace(factors[index],event_root_id=usd.event_root_id, source_sha256_claim=usd.source_sha256_claim)
        x=self.execute(inputs=factors)
        y=self.execute(inputs=list(reversed(factors)))
        self.safe(x);self.safe(y)
        self.assertEqual(x,y)
        self.assertEqual(x["distinct_root_catalyst_claim_count"],31)
        self.assertFalse(x["pair_claims_are_independent_economic_events"])



    def test_23_shared_source_root_on_two_pair_legs_blocks_only_that_pair(self):
        factors=samples(values={"USD":90,"EUR":-90})
        shared=next(f for f in factors if f.currency=="USD"
                    and f.category=="inflation_impact")
        i=next(i for i,f in enumerate(factors)
               if f.currency=="EUR" and f.category=="inflation_impact")
        factors[i]=replace(factors[i],event_root_id=shared.event_root_id, source_sha256_claim=shared.source_sha256_claim)
        result=self.execute(inputs=factors)
        self.safe(result)
        self.assertEqual(result["state"],
                         "LAB_FX28_HYPOTHETICAL_MACRO_SCORE_COHERENT_NO_GO")
        self.assertEqual(result["pair_shared_root_overlap_veto_count"],1)
        blocked=[r for r in result["pairs"]
                 if r["shared_event_root_overlap_veto"]]
        self.assertEqual([r["pair"] for r in blocked],["EUR/USD"])
        self.assertEqual(blocked[0]["research_relative_label"],"AGUARDAR")
        self.assertIsNone(blocked[0]["hypothetical_points"])
        self.assertEqual(blocked[0]["reason"],
            "SHARED_EVENT_ROOT_BOTH_CURRENCY_LEGS_NO_RELATIVE_CALIBRATION")
        self.assertEqual(blocked[0]["shared_event_root_ids_for_both_legs"],
                         [shared.event_root_id])
        usd_jpy=next(r for r in result["pairs"] if r["pair"]=="USD/JPY")
        self.assertFalse(usd_jpy["shared_event_root_overlap_veto"])
        self.assertEqual(usd_jpy["research_relative_label"],"BASE_RELATIVE")
        self.assertEqual(usd_jpy["hypothetical_points"],90)
        self.assertIsNone(result["calibrated_probability"])

    def test_24_three_currencies_with_one_root_block_three_pair_combinations(self):
        factors=samples(values={"USD":85,"EUR":-45,"JPY":30})
        usd=next(f for f in factors if f.currency=="USD"
                 and f.category=="policy_expectations")
        for currency in ("EUR","JPY"):
            i=next(i for i,f in enumerate(factors)
                   if f.currency==currency
                   and f.category=="policy_expectations")
            factors[i]=replace(factors[i],event_root_id=usd.event_root_id, source_sha256_claim=usd.source_sha256_claim)
        result=self.execute(inputs=factors)
        self.safe(result)
        self.assertEqual(result["distinct_root_catalyst_claim_count"],30)
        self.assertEqual(result["shared_event_root_ids"],[usd.event_root_id])
        self.assertEqual(result["pair_shared_root_overlap_veto_count"],3)
        abstains={r["pair"] for r in result["pairs"]
                  if r["shared_event_root_overlap_veto"]}
        self.assertEqual(abstains,{"EUR/USD","USD/JPY","EUR/JPY"})
        self.assertTrue(all(r["research_relative_label"]=="AGUARDAR"
                            for r in result["pairs"] if r["pair"] in abstains))
        self.assertEqual(result["currency_score_claims_reconciled"],8)
        self.assertFalse(result["trade_authorized"])

    def test_25_same_news_root_either_horizon_and_timezone_never_directional(self):
        factors=samples(values={"USD":70,"EUR":-20})
        usd=next(f for f in factors if f.currency=="USD"
                 and f.category=="inflation_impact")
        i=next(i for i,f in enumerate(factors)
               if f.currency=="EUR" and f.category=="inflation_impact")
        factors[i]=replace(factors[i],event_root_id=usd.event_root_id, source_sha256_claim=usd.source_sha256_claim)
        mt=timezone(timedelta(hours=-4))
        shifted=[replace(f,
            event_published_at_utc=f.event_published_at_utc.astimezone(mt),
            source_locally_captured_at_utc=f.source_locally_captured_at_utc.astimezone(mt))
            for f in factors]
        for horizon in ("D1","W1"):
            with self.subTest(horizon=horizon):
                a=self.execute(inputs=factors,horizon=horizon)
                b=self.execute(inputs=shifted,horizon=horizon,
                               now=BEFORE.astimezone(mt),
                               start=START.astimezone(mt))
                self.safe(a)
                self.assertEqual(a,b)
                self.assertEqual(a["pair_shared_root_overlap_veto_count"],1)
                eurusd=next(r for r in a["pairs"] if r["pair"]=="EUR/USD")
                self.assertEqual(eurusd["research_relative_label"],"AGUARDAR")

    def test_26_synthetic_shared_root_must_not_turn_into_provenance_or_score(self):
        factors=samples(values={"USD":95,"EUR":-95})
        usd=next(f for f in factors if f.currency=="USD"
                 and f.category=="inflation_impact")
        i=next(i for i,f in enumerate(factors)
               if f.currency=="EUR" and f.category=="inflation_impact")
        factors[i]=replace(factors[i],event_root_id=usd.event_root_id, source_sha256_claim=usd.source_sha256_claim)
        result=self.execute(inputs=factors)
        self.safe(result)
        self.assertFalse(result["inputs_are_authenticated_macro_sources"])
        self.assertFalse(result["first_seen_independently_attested"])
        self.assertFalse(result["prospective_forecast_witnessed"])
        self.assertFalse(result["out_of_sample_accuracy_measured"])
        self.assertIsNone(result["calibrated_probability"])
        self.assertIsNone(result["directional_bias"])
        self.assertEqual(result["operational_bias"],"AGUARDAR")
        self.assertFalse(result["trade_authorized"])

    def test_27_without_shared_root_normal_math_stays_unchanged(self):
        result=self.execute(inputs=samples(values={"USD":80,"EUR":-50}))
        self.safe(result)
        self.assertEqual(result["pair_shared_root_overlap_veto_count"],0)
        self.assertTrue(all(not r["shared_event_root_overlap_veto"]
                            for r in result["pairs"]))
        eurusd=next(r for r in result["pairs"] if r["pair"]=="EUR/USD")
        self.assertEqual(eurusd["research_relative_label"],"QUOTE_RELATIVE")
        self.assertEqual(eurusd["hypothetical_points"],-130)
        self.assertEqual(eurusd["shared_event_root_ids_for_both_legs"],[])

    def test_28_strong_opposite_macro_components_still_reject_direction(self):
        factors=samples(values={"USD":90,"EUR":-70},conflict="USD")
        usd=next(f for f in factors if f.currency=="USD"
                 and f.category=="inflation_impact")
        i=next(i for i,f in enumerate(factors)
               if f.currency=="EUR" and f.category=="inflation_impact")
        factors[i]=replace(factors[i],event_root_id=usd.event_root_id, source_sha256_claim=usd.source_sha256_claim)
        result=self.execute(inputs=factors)
        self.safe(result)
        self.assertEqual(result["pair_shared_root_overlap_veto_count"],1)
        self.assertIn("USD",result["conflicting_currency_codes"])
        eurusd=next(r for r in result["pairs"] if r["pair"]=="EUR/USD")
        self.assertEqual(eurusd["research_relative_label"],"AGUARDAR")
        self.assertIsNone(eurusd["hypothetical_points"])



    def test_29_alias_root_same_source_category_and_clock_must_block(self):
        factors=samples(values={"USD":90,"EUR":-90})
        usd=next(f for f in factors if f.currency=="USD"
                 and f.category=="inflation_impact")
        i=next(i for i,f in enumerate(factors)
               if f.currency=="EUR" and f.category=="inflation_impact")
        # Keep DIFFERENT event_root_id but counterfeit one shared document.
        factors[i]=replace(
            factors[i],source_sha256_claim=usd.source_sha256_claim)
        blocked=self.blocked(inputs=factors)
        self.assertEqual(blocked["reason"],
                         "SAME_SOURCE_BYTES_TWO_ROOT_ALIASES_NOT_INDEPENDENT")
        self.assertEqual(blocked["currency_score_claims_reconciled"],0)
        self.assertFalse(blocked["prospective_forecast_witnessed"])

    def test_30_same_original_document_eight_aliases_are_not_eight_events(self):
        factors=samples(values={"USD":80})
        shared=next(x for x in factors if x.currency=="USD"
                    and x.category=="policy_expectations")
        for i,f in enumerate(factors):
            if f.category=="policy_expectations" and f.currency!="USD":
                factors[i]=replace(f,
                    source_sha256_claim=shared.source_sha256_claim)
        blocked=self.blocked(inputs=factors)
        self.assertEqual(blocked["reason"],
                         "SAME_SOURCE_BYTES_TWO_ROOT_ALIASES_NOT_INDEPENDENT")
        self.assertEqual(blocked["hypothetical_labeled_pair_count"],0)
        self.assertTrue(all(row["research_relative_label"]=="AGUARDAR"
                            for row in blocked["pairs"]))

    def test_31_shared_root_must_have_identical_document_sha_and_utc(self):
        factors=samples(values={"USD":90,"EUR":-60})
        usd=next(f for f in factors if f.currency=="USD"
                 and f.category=="inflation_impact")
        i=next(i for i,f in enumerate(factors)
               if f.currency=="EUR" and f.category=="inflation_impact")
        factors[i]=replace(
            factors[i],event_root_id=usd.event_root_id,
            source_sha256_claim=usd.source_sha256_claim)
        coherent=self.execute(inputs=factors)
        self.safe(coherent)
        self.assertEqual(coherent["pair_shared_root_overlap_veto_count"],1)
        pair=next(x for x in coherent["pairs"] if x["pair"]=="EUR/USD")
        self.assertEqual(pair["research_relative_label"],"AGUARDAR")
        self.assertIsNone(pair["hypothetical_points"])
        self.assertEqual(coherent["distinct_root_catalyst_claim_count"],31)
        self.assertIsNone(coherent["calibrated_probability"])

    def test_32_alias_rejection_invariant_to_factor_input_order(self):
        factors=samples(values={"USD":80,"EUR":-70})
        usd=next(f for f in factors if f.currency=="USD"
                 and f.category=="activity_impact")
        i=next(i for i,f in enumerate(factors)
               if f.currency=="EUR" and f.category=="activity_impact")
        factors[i]=replace(factors[i],
                           source_sha256_claim=usd.source_sha256_claim)
        first=self.blocked(inputs=factors)
        second=self.blocked(inputs=list(reversed(factors)))
        self.assertEqual(first,second)
        self.assertEqual(first["reason"],
                         "SAME_SOURCE_BYTES_TWO_ROOT_ALIASES_NOT_INDEPENDENT")
        self.assertFalse(first["trade_authorized"])


if __name__=="__main__":
    unittest.main()
