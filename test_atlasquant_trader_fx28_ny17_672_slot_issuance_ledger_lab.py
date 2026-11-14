"""Synthetic contracts only. No GitHub timestamp or broker authentication."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
import unittest

from atlasquant_fx_universe import OFFICIAL_PAIRS
from atlasquant_trader_fx28_ny17_prospective_campaign_lab import (
    FROZEN_START_UTC, FROZEN_END_UTC, _nominal_windows,
)
from atlasquant_trader_fx28_ny17_672_slot_issuance_ledger_lab import (
    FUTURE, FUTURE_CLAIM, MISSING, PAST_CLAIM,
    inspect_fx28_ny17_672_slot_issuance_ledger_lab as inspect,
)
from test_atlasquant_trader_fx28_ny17_forecast_witness_lab import make_claim


UTC = timezone.utc
PRE_FIRST = datetime(2026, 11, 14, 0, 15, tzinfo=UTC)


class SlotIssuanceLedgerTests(unittest.TestCase):
    def call(self, claims=(), *, now=PRE_FIRST):
        return inspect(window_claims=claims, inspected_at_utc=now)

    def safe(self, result):
        self.assertEqual(result["operational_bias"], "AGUARDAR")
        self.assertIsNone(result["validated_directional_accuracy"])
        self.assertIsNone(result["calibrated_probability"])
        self.assertEqual(result["independently_authenticated_forecasts"], 0)
        for key in (
            "independently_authenticated_comment_timestamps",
            "absence_of_github_witness_independently_verified",
            "github_comments_fetched", "forecast_direction_published",
            "trade_authorized", "publishable", "live_alert_allowed",
            "worker_enabled", "scheduler_enabled",
        ):
            self.assertFalse(result[key], key)
        self.assertTrue(result["no_witness_in_input_does_not_prove_absence_on_github"])
        self.assertEqual((result["http_requests"], result["file_writes"],
                          result["new_cost_brl"]), (0, 0, 0))

    def accepted(self, r):
        self.safe(r)
        self.assertEqual(r["state"], "LAB_FX28_672_SLOTS_ACCOUNTED_UNATTESTED_NO_GO")
        self.assertEqual(r["slots_accounted"], 672)
        self.assertEqual(len(r["slots"]), 672)
        self.assertEqual(len(set(x["slot_id"] for x in r["slots"])), 672)
        self.assertEqual(sum(x["horizon"] == "D1" for x in r["slots"]), 560)
        self.assertEqual(sum(x["horizon"] == "W1" for x in r["slots"]), 112)
        self.assertEqual(
            r["not_yet_due_slots"] + r["future_unattested_claim_slots"] +
            r["not_issued_before_window_slots"] + r["past_unattested_claim_slots"], 672)
        self.assertTrue(all(not x["forecast_issued_independently_verified"]
                            and not x["claim_is_external_witness"]
                            and not x["missing_status_proves_github_absence"]
                            and not x["broker_price_verified"]
                            and not x["trade_authorized"]
                            for x in r["slots"]))

    def test_01_pre_first_672_future_slots_not_issued_missing(self):
        r=self.call()
        self.accepted(r)
        self.assertEqual(r["not_yet_due_slots"], 672)
        self.assertEqual(r["not_issued_before_window_slots"], 0)
        self.assertEqual(r["future_unattested_claim_slots"], 0)
        self.assertTrue(all(x["issuance_accounting_status"] == FUTURE
                            for x in r["slots"]))

    def test_02_before_start_one_second_all_future(self):
        r=self.call(now=FROZEN_START_UTC-timedelta(seconds=1))
        self.accepted(r)
        self.assertEqual(r["not_yet_due_slots"], 672)
        self.assertEqual(r["not_issued_before_window_slots"], 0)

    def test_03_at_exact_start_56_missing_but_not_outcome(self):
        r=self.call(now=FROZEN_START_UTC)
        self.accepted(r)
        self.assertEqual(r["not_issued_before_window_slots"], 56)
        self.assertEqual(r["not_yet_due_slots"], 616)
        first=[x for x in r["slots"]
               if x["window_start_utc"] == FROZEN_START_UTC.isoformat()]
        self.assertEqual(len(first), 56)
        self.assertTrue(all(x["issuance_accounting_status"] == MISSING
                            for x in first))

    def test_04_all_672_due_without_supplied_witness_stay_visible(self):
        r=self.call(now=FROZEN_END_UTC)
        self.accepted(r)
        self.assertEqual(r["not_issued_before_window_slots"], 672)
        self.assertEqual(r["not_yet_due_slots"], 0)
        self.assertTrue(all(x["issuance_accounting_status"] == MISSING
                            for x in r["slots"]))

    def test_05_synthetic_d1_claim_does_not_hide_missing_w1(self):
        r=self.call((make_claim(),), now=FROZEN_START_UTC+timedelta(minutes=1))
        self.accepted(r)
        self.assertEqual(r["past_unattested_claim_slots"], 28)
        self.assertEqual(r["not_issued_before_window_slots"], 28)
        self.assertEqual(r["not_yet_due_slots"], 616)
        self.assertEqual(sum(x["issuance_accounting_status"] == PAST_CLAIM
                             for x in r["slots"]), 28)

    def test_06_two_synthetic_claims_remain_unattested(self):
        r=self.call((make_claim(),make_claim(horizon="W1",comment_id=2002)),
                    now=FROZEN_START_UTC+timedelta(minutes=1))
        self.accepted(r)
        self.assertEqual(r["past_unattested_claim_slots"], 56)
        self.assertEqual(r["not_issued_before_window_slots"], 0)
        self.assertFalse(r["absence_of_github_witness_independently_verified"])

    def test_07_future_claim_does_not_count_as_issued_or_hit(self):
        claim=make_claim()
        moment=claim.github_witness.retrieved_at+timedelta(minutes=1)
        r=self.call((claim,),now=moment)
        self.accepted(r)
        self.assertEqual(r["future_unattested_claim_slots"], 28)
        self.assertEqual(r["not_yet_due_slots"], 644)
        self.assertEqual(r["past_unattested_claim_slots"], 0)
        self.assertEqual(r["not_issued_before_window_slots"], 0)
        self.assertFalse(r["forecast_direction_published"])

    def test_08_invalid_claim_rejected_no_partial_672_ledger(self):
        claim=make_claim()
        late=replace(claim.github_witness,
                     retrieved_at=FROZEN_START_UTC+timedelta(seconds=1))
        bad=replace(claim,github_witness=late)
        r=self.call((bad,),now=FROZEN_START_UTC+timedelta(minutes=2))
        self.safe(r)
        self.assertEqual(r["state"],
                         "LAB_FX28_672_SLOT_ISSUANCE_LEDGER_BLOCKED_NO_GO")
        self.assertEqual(r["slots"], [])
        self.assertEqual(r["slots_accounted"],0)

    def test_09_duplicate_window_claim_no_pseudo_independent_slots(self):
        claim=make_claim()
        r=self.call((claim,claim),now=FROZEN_START_UTC+timedelta(minutes=1))
        self.safe(r)
        self.assertEqual(r["state"],
                         "LAB_FX28_672_SLOT_ISSUANCE_LEDGER_BLOCKED_NO_GO")

    def test_10_clock_wrong_type_naive_microseconds_and_pre_campaign(self):
        for moment in (None, "2026-11-14T00:15:00Z",
                       PRE_FIRST.replace(tzinfo=None),
                       PRE_FIRST+timedelta(microseconds=1),
                       datetime(2026,11,11,12,tzinfo=UTC)):
            with self.subTest(moment=moment):
                r=self.call(now=moment)
                self.safe(r)
                self.assertEqual(r["state"],
                                 "LAB_FX28_672_SLOT_ISSUANCE_LEDGER_BLOCKED_NO_GO")

    def test_11_slot_ids_unique_between_w1_and_d1_same_start(self):
        r=self.call()
        self.accepted(r)
        same=[x for x in r["slots"]
              if x["pair"] == OFFICIAL_PAIRS[0]
              and x["window_start_utc"] == FROZEN_START_UTC.isoformat()]
        self.assertEqual(len(same),2)
        self.assertEqual(set(x["horizon"] for x in same),{"D1","W1"})
        self.assertNotEqual(same[0]["slot_id"],same[1]["slot_id"])

    def test_12_weekly_and_daily_end_frozen_not_shifted_by_labels(self):
        r=self.call()
        self.accepted(r)
        last=[x for x in r["slots"]
              if x["window_end_utc"] == FROZEN_END_UTC.isoformat()]
        self.assertEqual(len(last), 56)
        self.assertEqual(r["per_horizon"]["D1"]["slots_expected"], 560)
        self.assertEqual(r["per_horizon"]["W1"]["slots_expected"], 112)

    def test_13_no_claims_as_input_not_external_github_coverage(self):
        r=self.call(now=FROZEN_START_UTC+timedelta(minutes=1))
        self.accepted(r)
        self.assertTrue(r["no_witness_in_input_does_not_prove_absence_on_github"])
        self.assertFalse(r["github_comments_fetched"])
        self.assertFalse(r["absence_of_github_witness_independently_verified"])


if __name__ == "__main__":
    unittest.main()
