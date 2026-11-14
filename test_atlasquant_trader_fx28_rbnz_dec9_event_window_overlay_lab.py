"""Synthetic-only RBNZ schedule relevance, no live broker/HTTP calls."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from zoneinfo import ZoneInfoNotFoundError
import unittest

from atlasquant_fx_universe import OFFICIAL_PAIRS, split_pair
from atlasquant_trader_fx28_ny17_prospective_campaign_lab import (
    FROZEN_START_UTC, FROZEN_END_UTC, _nominal_windows,
)
from atlasquant_trader_fx28_rbnz_dec9_event_window_overlay_lab import (
    EVENT_ROOT_ID, SOURCE_URL,
    inspect_rbnz_dec9_event_ny17_relevance_lab as inspect,
)

UTC = timezone.utc
BEFORE = datetime(2026, 11, 14, 10, tzinfo=UTC)
EVENT = datetime(2026, 12, 9, 1, tzinfo=UTC)


class RbnzDec9Ny17OverlayTests(unittest.TestCase):
    def audit(self, now=BEFORE):
        return inspect(inspected_at_utc=now)

    def safe(self, r):
        self.assertEqual(r["operational_bias"], "AGUARDAR")
        self.assertFalse(r["publishable"])
        self.assertFalse(r["trade_authorized"])
        self.assertFalse(r["live_alert_allowed"])
        self.assertFalse(r["worker_enabled"])
        self.assertFalse(r["scheduler_enabled"])
        self.assertTrue(r["source_url_is_not_captured_original_html"])
        self.assertTrue(r["scheduled_event_is_not_realized_ocr_change"])
        self.assertFalse(r["source_schedule_first_seen_or_revision_independently_verified"])
        self.assertFalse(r["official_page_snapshot_locally_sha_verified"])
        self.assertFalse(r["pre_event_consensus_verified"])
        self.assertIsNone(r["official_ocr_actual_at_event"])
        self.assertFalse(r["other_currency_pairs_proved_unaffected"])
        self.assertIsNone(r["probability_estimated"])
        self.assertIsNone(r["accuracy_measured"])
        self.assertEqual((r["http_requests"], r["file_writes"],
                          r["new_cost_brl"]), (0, 0, 0))
        self.assertEqual(r["expected_pair_horizon_slots"], 672)

    def complete(self, r):
        self.safe(r)
        self.assertEqual(r["state"],
                         "LAB_RBNZ_EVENT_WINDOW_RELEVANCE_DOCUMENTARY_NO_GO")
        self.assertEqual(r["event_count"], 1)
        self.assertTrue(r["event_root_counted_as_one_shared_catalyst"])
        self.assertEqual(r["direct_nzd_pair_count"], 7)
        self.assertEqual(r["overlapping_nominal_window_count"], 2)
        self.assertEqual(r["direct_pair_horizon_slots_intersecting_event"], 14)
        self.assertTrue(r["all_672_slots_preserved"])
        self.assertEqual(len(r["direct_pair_horizon_slot_ids"]), 14)
        self.assertEqual(len(set(x["slot_id"] for x in
                                 r["direct_pair_horizon_slot_ids"])), 14)
        self.assertEqual(len({x["risk_event_root_id"] for x in
                              r["direct_pair_horizon_slot_ids"]}), 1)
        self.assertTrue(all(x["risk_event_root_id"] == EVENT_ROOT_ID
                            and x["event_impact_direction"] is None
                            and not x["event_is_confirmed_actual_release"]
                            and not x["event_first_seen_authenticated"]
                            and not x["signal_or_trade_authorized"]
                            for x in r["direct_pair_horizon_slot_ids"]))

    def test_01_dec9_nz1400_interpreted_dec8_2100_cuiaba(self):
        r = self.audit()
        self.complete(r)
        self.assertEqual(r["scheduled_event_utc_interpreted_from_nz_local"],
                         "2026-12-09T01:00:00+00:00")
        self.assertEqual(r["scheduled_event_at_cuiaba_interpreted"],
                         "2026-12-08T21:00:00-04:00")
        self.assertEqual(r["scheduled_event_status_at_inspection"],
                         "FUTURE_PUBLIC_SCHEDULE_CLAIM_UNATTESTED")
        self.assertEqual(r["source_reference_url"], SOURCE_URL)

    def test_02_event_inside_dec8_daily_and_dec6_weekly_nominal(self):
        r = self.audit()
        self.complete(r)
        by_h = {x["horizon"]:x for x in r["overlapping_window_details"]}
        self.assertEqual(by_h["D1"]["window_start_utc"],
                         "2026-12-08T22:00:00+00:00")
        self.assertEqual(by_h["D1"]["window_end_utc"],
                         "2026-12-09T22:00:00+00:00")
        self.assertEqual(by_h["W1"]["window_start_utc"],
                         "2026-12-06T22:00:00+00:00")
        self.assertEqual(by_h["W1"]["window_end_utc"],
                         "2026-12-11T22:00:00+00:00")
        self.assertTrue(all(x["overlapping_horizons_are_not_independent_trials"]
                            for x in by_h.values()))

    def test_03_seven_exact_nzd_pairs_each_horizon_no_spurious_usd_pairs(self):
        r = self.audit()
        self.complete(r)
        expected = {pair for pair in OFFICIAL_PAIRS
                    if "NZD" in split_pair(pair)}
        self.assertEqual(len(expected), 7)
        for h in ("D1","W1"):
            actual = {x["pair"] for x in r["direct_pair_horizon_slot_ids"]
                      if x["horizon"] == h}
            self.assertEqual(actual, expected)
            self.assertEqual(len(actual), 7)

    def test_04_frozen_672_opportunities_not_reduced_or_shifted(self):
        r = self.audit()
        self.complete(r)
        self.assertEqual((len(_nominal_windows("D1")),
                          len(_nominal_windows("W1"))), (20, 4))
        self.assertEqual((_nominal_windows("D1")[0][0],
                          _nominal_windows("W1")[0][0]), 
                         (FROZEN_START_UTC,FROZEN_START_UTC))
        self.assertEqual((_nominal_windows("D1")[-1][1],
                          _nominal_windows("W1")[-1][1]),
                         (FROZEN_END_UTC,FROZEN_END_UTC))
        self.assertEqual(20*28+4*28, 672)

    def test_05_one_second_before_event_still_only_scheduled(self):
        r = self.audit(EVENT-timedelta(seconds=1))
        self.complete(r)
        self.assertEqual(r["scheduled_event_status_at_inspection"],
                         "FUTURE_PUBLIC_SCHEDULE_CLAIM_UNATTESTED")

    def test_06_at_event_does_not_invent_actual_or_forecast(self):
        r = self.audit(EVENT)
        self.complete(r)
        self.assertEqual(r["scheduled_event_status_at_inspection"],
                         "ELAPSED_PUBLIC_SCHEDULE_NOT_HISTORICAL_FORECAST")
        self.assertFalse(r["pre_event_consensus_verified"])

    def test_07_after_end_cannot_claim_historical_first_seen(self):
        r = self.audit(FROZEN_END_UTC+timedelta(days=1))
        self.complete(r)
        self.assertEqual(r["scheduled_event_status_at_inspection"],
                         "ELAPSED_PUBLIC_SCHEDULE_NOT_HISTORICAL_FORECAST")

    def test_08_naive_string_missing_or_microsecond_clock_block(self):
        for value in (None, "2026-11-14T10:00:00Z",
                      BEFORE.replace(tzinfo=None),
                      BEFORE+timedelta(microseconds=1)):
            with self.subTest(value=value):
                r=self.audit(value)
                self.safe(r)
                self.assertEqual(
                    r["state"],"LAB_RBNZ_EVENT_WINDOW_OVERLAY_BLOCKED_NO_GO")
                self.assertEqual(r["direct_pair_horizon_slots_intersecting_event"],0)

    def test_09_no_iana_timezone_rules_fails_closed(self):
        with patch(
            "atlasquant_trader_fx28_rbnz_dec9_event_window_overlay_lab.ZoneInfo",
            side_effect=ZoneInfoNotFoundError("test-only")):
            r=self.audit()
        self.safe(r)
        self.assertEqual(r["state"],
                         "LAB_RBNZ_EVENT_WINDOW_OVERLAY_BLOCKED_NO_GO")
        self.assertEqual(
            r["reason"],"IANA_TIMEZONE_RULES_UNAVAILABLE_NO_FIXED_OFFSET_FALLBACK")

    def test_10_event_is_one_root_not_14_independent_surprises(self):
        r=self.audit()
        self.complete(r)
        roots={x["risk_event_root_id"] for x in
               r["direct_pair_horizon_slot_ids"]}
        self.assertEqual(roots,{EVENT_ROOT_ID})
        self.assertEqual(r["event_count"],1)
        self.assertTrue(r["event_root_counted_as_one_shared_catalyst"])

    def test_11_all_slots_have_canonical_ids_not_raw_market_prices(self):
        r=self.audit()
        self.complete(r)
        for slot in r["direct_pair_horizon_slot_ids"]:
            self.assertIn(slot["horizon"],("D1","W1"))
            self.assertIn(slot["pair"],OFFICIAL_PAIRS)
            self.assertTrue(slot["slot_id"].endswith(
                "_"+slot["horizon"]+"_"+slot["pair"]))
            self.assertNotIn("actual",slot)
            self.assertNotIn("price",slot)
            self.assertNotIn("probability",slot)


if __name__ == "__main__":
    unittest.main()
