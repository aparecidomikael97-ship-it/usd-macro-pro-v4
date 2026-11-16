"""Protect event-relative macro-FX observation clocks against post-hoc shifts.

All price/consensus/actual values are synthetic. No real market return,
publisher-first-seen, broker bid/ask, OOS forecast or directional claim.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import timedelta, timezone
import unittest

import test_atlasquant_trader_fx28_macro_event_surprise_reaction_contract_lab as examples
from atlasquant_trader_fx28_macro_event_surprise_reaction_contract_lab import (
    inspect_macro_event_surprise_reaction_lab as inspect,
)
from atlasquant_trader_us_dec2026_frozen_evaluation_protocol_lab import FROZEN_PLAN

RELEASE=examples.RELEASE
NOW=examples.NOW
RANGE={"M15":15,"H1":60,"H4":240}
BLOCKED="LAB_FX28_MACRO_EVENT_STUDY_BLOCKED_NO_GO"
PASS="LAB_FX28_SINGLE_EVENT_AND_7FX_REACTIONS_DOCUMENTARY_ONLY_NO_GO"


def study(prices):
    return inspect(
        event_root_id=examples.ROOT,
        consensus=examples.CONSENSUS,
        actual=examples.ACTUAL,
        price_claims=prices,
        inspected_at_utc=NOW,
    )


def all_shift(horizon="M15", *, baseline=timedelta(0),
              endpoint=timedelta(0)):
    return [replace(p,
        baseline_at_utc=p.baseline_at_utc+baseline,
        endpoint_at_utc=p.endpoint_at_utc+endpoint,
    ) for p in examples.prices(horizon=horizon)]


class FixedMacroFxWindowTests(unittest.TestCase):
    def safe(self,r):
        self.assertEqual(r["operational_bias"],"AGUARDAR")
        self.assertFalse(r["trade_authorized"])
        self.assertFalse(r["publishable"])
        self.assertFalse(r["live_alert_allowed"])
        self.assertIsNone(r["predicted_currency_direction"])
        self.assertIsNone(r["calibrated_probability"])
        self.assertIsNone(r["historical_out_of_sample_accuracy"])
        self.assertFalse(r["issuer_first_seen_independently_authenticated"])
        self.assertFalse(r["broker_price_and_bid_ask_independently_authenticated"])
        self.assertTrue(r["seven_pair_outcomes_are_not_independent_events"])
        self.assertEqual((r["http_calls"],r["file_writes"],r["mt5_calls"]),(0,0,0))
        self.assertEqual(r["new_cost_brl"],0)

    def accepted(self,records):
        r=study(records)
        self.safe(r)
        self.assertEqual(r["state"],PASS)
        self.assertEqual(r["fx_pair_outcome_claim_count"],7)
        self.assertEqual(r["single_independent_economic_event_count"],1)
        self.assertTrue(r["price_window_matches_frozen_event_relative_clocks_claim_only"])
        self.assertTrue(r["all_seven_pairs_share_identical_baseline_and_endpoint_clocks"])
        return r

    def denied(self,records,reason="PRICE_BASELINE_ENDPOINT_NOT_FROZEN_EVENT_RELATIVE"):
        r=study(records)
        self.safe(r)
        self.assertEqual(r["state"],BLOCKED)
        self.assertEqual(r["reason"],reason)
        self.assertIsNone(r["actual_minus_consensus_metric_units"])
        self.assertEqual(r["fx_pair_outcome_claim_count"],0)
        self.assertIsNone(r["historical_out_of_sample_accuracy"])
        return r

    def test_01_canonical_m15_15minutes_pre_and_exact_15minute_close(self):
        r=self.accepted(examples.prices())
        self.assertEqual(r["shared_price_baseline_utc_claim"],
                         (RELEASE-timedelta(minutes=15)).isoformat())
        self.assertEqual(r["shared_price_endpoint_utc_claim"],
                         (RELEASE+timedelta(minutes=15)).isoformat())

    def test_02_canonical_h1_requires_exact_60m_endpoint(self):
        r=self.accepted(examples.prices(horizon="H1"))
        self.assertEqual(r["shared_price_endpoint_utc_claim"],
                         (RELEASE+timedelta(minutes=60)).isoformat())

    def test_03_canonical_h4_requires_exact_240m_endpoint(self):
        r=self.accepted(examples.prices(horizon="H4"))
        self.assertEqual(r["shared_price_endpoint_utc_claim"],
                         (RELEASE+timedelta(minutes=240)).isoformat())

    def test_04_all_seven_baselines_at_news_release_not_pre_news(self):
        self.denied(all_shift(baseline=timedelta(minutes=15)))

    def test_05_all_seven_baselines_one_minute_late_no_cherrypick(self):
        self.denied(all_shift(baseline=timedelta(minutes=1)))

    def test_06_all_seven_baselines_14min_after_preanchor_no_cherrypick(self):
        self.denied(all_shift(baseline=timedelta(minutes=14)))

    def test_07_all_seven_baselines_one_microsecond_late_refused(self):
        self.denied(all_shift(baseline=timedelta(microseconds=1)))

    def test_08_all_seven_m15_endpoints_one_second_late_refused(self):
        self.denied(all_shift(endpoint=timedelta(seconds=1)))

    def test_09_all_seven_m15_endpoints_one_microsecond_late_refused(self):
        self.denied(all_shift(endpoint=timedelta(microseconds=1)))

    def test_10_all_seven_m15_endpoints_fifteen_minutes_late_refused(self):
        self.denied(all_shift(endpoint=timedelta(minutes=15)))

    def test_11_all_seven_h1_endpoints_one_minute_late_refused(self):
        self.denied(all_shift("H1",endpoint=timedelta(minutes=1)))

    def test_12_all_seven_h4_endpoints_fifteen_minutes_late_refused(self):
        self.denied(all_shift("H4",endpoint=timedelta(minutes=15)))

    def test_13_all_seven_h1_baselines_news_release_refused(self):
        self.denied(all_shift("H1",baseline=timedelta(minutes=15)))

    def test_14_all_seven_h4_baselines_one_minute_late_refused(self):
        self.denied(all_shift("H4",baseline=timedelta(minutes=1)))

    def test_15_all_seven_shift_both_clocks_plus_minute_not_disguised(self):
        self.denied(all_shift(
            baseline=timedelta(minutes=1),endpoint=timedelta(minutes=1)))

    def test_16_one_pair_different_baseline_still_preserves_sync_error(self):
        pp=examples.prices()
        pp[0]=replace(pp[0],baseline_at_utc=RELEASE-timedelta(minutes=14))
        self.denied(pp,reason="SEVEN_FX_REACTIONS_HAVE_DIFFERENT_PRICE_WINDOWS")

    def test_17_one_pair_different_endpoint_still_preserves_sync_error(self):
        pp=examples.prices()
        pp[-1]=replace(pp[-1],endpoint_at_utc=RELEASE+timedelta(minutes=16))
        self.denied(pp,reason="SEVEN_FX_REACTIONS_HAVE_DIFFERENT_PRICE_WINDOWS")

    def test_18_timezone_cuiaba_exact_instant_allowed(self):
        tz=timezone(timedelta(hours=-4))
        pp=[replace(row,
            baseline_at_utc=row.baseline_at_utc.astimezone(tz),
            endpoint_at_utc=row.endpoint_at_utc.astimezone(tz))
            for row in examples.prices()]
        self.accepted(pp)

    def test_19_timezone_cuiaba_one_second_shift_still_refused(self):
        tz=timezone(timedelta(hours=-4))
        pp=[replace(row,
            baseline_at_utc=(row.baseline_at_utc+timedelta(seconds=1)).astimezone(tz),
            endpoint_at_utc=row.endpoint_at_utc.astimezone(tz))
            for row in examples.prices()]
        self.denied(pp)

    def test_20_precommitted_december_rule_is_same_fixed_baseline(self):
        self.assertEqual(FROZEN_PLAN["price_baseline_rule"],
                         "M15_CANDLE_OPEN_AT_RELEASE_MINUS_15_MINUTES")
        self.assertEqual(FROZEN_PLAN["analysis_windows_minutes"],RANGE)
        self.assertEqual(FROZEN_PLAN["price_endpoint_rule"],
                         "CLOSED_M15_CANDLE_AT_RELEASE_PLUS_WINDOW_MINUTES")

    def test_21_identity_of_all_seven_synthetic_prices_is_not_oos_skill(self):
        r=self.accepted(examples.prices())
        self.assertEqual(len(r["fx_reaction_claims"]),7)
        self.assertEqual(r["single_independent_economic_event_count"],1)
        self.assertIsNone(r["predicted_currency_direction"])

    def test_22_one_synchronized_shifted_study_does_not_leak_surprise(self):
        r=self.denied(all_shift(endpoint=timedelta(seconds=1)))
        self.assertIsNone(r["economic_surprise_label_documentary_only"])
        self.assertEqual(r["single_independent_economic_event_count"],0)

if __name__=="__main__":
    unittest.main()
