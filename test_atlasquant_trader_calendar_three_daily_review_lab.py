"""3x daily calendar change queue is documentary, never a live alert."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import unittest

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS
from atlasquant_trader_calendar_three_daily_review_lab import (
    SCHEMA, build_three_daily_calendar_review_lab,
)
from test_atlasquant_trader_official_change_detection_lab import (
    event, snapshot,
)

NOW = datetime(2026, 11, 4, 21, tzinfo=timezone.utc)
STAMPS = ("2026-11-04T09:40:00Z", "2026-11-04T13:50:00Z",
          "2026-11-04T20:20:00Z")
SLOTS = ("PRE_MARKET", "MIDDAY", "CLOSE")


def cap(index=0, snapshots=None):
    return {"slot": SLOTS[index], "captured_at_utc": STAMPS[index],
            "snapshots": [] if snapshots is None else snapshots}


def nz_observed(index, *, events=None):
    observed = ("2026-11-04T09:39:00Z", "2026-11-04T13:49:00Z",
                "2026-11-04T20:19:00Z")
    return snapshot(observed=observed[index], events=events)


def usd_observed(index):
    row = nz_observed(index, events=[{
        **event(), "event_id": "US_CPI_TEST_NOV26",
        "event_kind": "INFLATION",
        "source_url": "https://www.bls.gov/schedule/news_release/cpi.htm",
    }])
    row["currency"] = "USD"
    row["source_id"] = "US_BLS_CPI"
    return row


def review(captures):
    return build_three_daily_calendar_review_lab(captures, at=NOW)


def pair(result, code):
    return next(item for item in result["pair_cards"] if item["pair"] == code)


class ThreeDailyCalendarReviewLabTests(unittest.TestCase):
    def test_no_documentary_captures_means_28_pair_waits(self):
        result = review([])
        self.assertEqual((result["schema"], result["state"]),
                         (SCHEMA, "LAB_THREE_DAILY_CALENDAR_REVIEW_ONLY"))
        self.assertEqual(result["claimed_capture_count"], 0)
        self.assertEqual(result["change_count"], 0)
        self.assertEqual({r["pair"] for r in result["pair_cards"]}, set(OFFICIAL_PAIRS))
        for item in result["pair_cards"]:
            self.assertEqual((item["D1"], item["W1"], item["MN1"]),
                             ("AGUARDAR", "AGUARDAR", "AGUARDAR"))
        self.assertEqual([p["missing_g8_currencies"] for p in result["planned_slots"]],
                         [list(CURRENCIES)] * 3)

    def test_two_snapshots_show_rescheduled_nzd_event_for_seven_pairs(self):
        old = cap(0, [nz_observed(0)])
        changed = event("2026-11-16T20:00:00Z", digest="b" * 64,
                        updated="2026-11-04T13:00:00Z")
        new = cap(1, [nz_observed(1, events=[changed])])
        before = deepcopy([old, new])
        result = review([old, new])
        self.assertEqual([old, new], before)
        self.assertEqual(result["change_count"], 1)
        self.assertEqual(result["source_comparison_count"], 1)
        record = result["review_queue"][0]
        self.assertEqual(record["source_id"], "RBNZ_OFFICIAL_NEWS")
        self.assertEqual(record["previous_slot"], "PRE_MARKET")
        self.assertEqual(record["detected_in_claimed_slot"], "MIDDAY")
        self.assertIn("DATE_RESCHEDULED", record["changed_fields"])
        self.assertEqual(record["priority"], "REVISAR_IMEDIATAMENTE")
        self.assertFalse(record["calendar_change_time_verified"])
        self.assertEqual(sum(x["documentary_changes_for_review"] for x in result["pair_cards"]), 7)
        self.assertEqual(pair(result, "EUR/NZD")["immediate_reviews"], 1)
        self.assertEqual(pair(result, "EUR/USD")["immediate_reviews"], 0)
        self.assertFalse(result["notifications_sent"])

    def test_three_claimed_snapshots_do_not_prove_three_real_daily_updates(self):
        result = review([cap(i, [nz_observed(i)]) for i in range(3)])
        self.assertTrue(result["three_claimed_slots_seen"])
        self.assertEqual(result["source_comparison_count"], 2)
        self.assertEqual(result["change_count"], 0)
        self.assertFalse(result["three_daily_updates_verified"])
        self.assertFalse(result["realtime_calendar_verified"])
        self.assertEqual([s["state"] for s in result["planned_slots"]],
                         ["UNATTESTED_DOCUMENTARY_CAPTURE"] * 3)
        self.assertFalse(result["source_authenticity_attested"])

    def test_partial_disappearance_never_means_cancellation(self):
        result = review([cap(0, [nz_observed(0)]),
                         cap(1, [nz_observed(1, events=[])])])
        self.assertEqual(result["change_count"], 0)
        self.assertEqual(result["omissions_not_cancellations"][0]["event_ids"],
                         ["RBNZ_NZ_FSR_NOV26"])
        self.assertFalse(result["omissions_not_cancellations"][0]
                         ["disappearance_is_cancellation"])

    def test_explicit_cancelled_status_requires_review_but_no_notification(self):
        cancelled = event(status="CANCELLED", digest="c" * 64,
                          updated="2026-11-04T12:00:00Z")
        result = review([cap(0, [nz_observed(0)]),
                         cap(1, [nz_observed(1, events=[cancelled])])])
        self.assertIn("STATUS_CHANGED", result["review_queue"][0]["changed_fields"])
        self.assertFalse(result["notifications_sent"])
        self.assertFalse(result["trade_authorized"])

    def test_source_missing_midday_does_not_erase_last_known_snapshot(self):
        changed = event("2026-11-16T20:00:00Z", digest="d" * 64,
                        updated="2026-11-04T19:00:00Z")
        result = review([cap(0, [nz_observed(0)]), cap(1),
                         cap(2, [nz_observed(2, events=[changed])])])
        self.assertEqual(result["source_comparison_count"], 1)
        self.assertEqual(result["review_queue"][0]["previous_slot"], "PRE_MARKET")
        self.assertEqual(result["review_queue"][0]["detected_in_claimed_slot"], "CLOSE")
        self.assertIn("NZD", result["planned_slots"][1]["missing_g8_currencies"])

    def test_usd_and_nzd_sources_only_affect_relevant_pairs(self):
        changed = event("2026-11-16T20:00:00Z", digest="b" * 64,
                        updated="2026-11-04T13:00:00Z")
        result = review([cap(0, [usd_observed(0), nz_observed(0)]),
                         cap(1, [usd_observed(1), nz_observed(1, events=[changed])])])
        self.assertEqual(result["source_comparison_count"], 2)
        self.assertEqual(result["change_count"], 1)
        self.assertEqual(pair(result, "EUR/USD")["documentary_changes_for_review"], 0)
        self.assertEqual(pair(result, "NZD/USD")["documentary_changes_for_review"], 1)

    def test_duplicate_sources_or_slots_and_nonmonotonic_time_block(self):
        cases = ([cap(0, [nz_observed(0), nz_observed(0)])],
                 [cap(0), cap(0)],
                 [cap(0, [nz_observed(0)]), cap(1, [nz_observed(0)])])
        for c in cases:
            with self.subTest(c=c):
                self.assertEqual(review(c)["state"], "LAB_BLOCKED")

    def test_unordered_input_list_is_normalized_by_named_daily_slot(self):
        out = review([cap(1), cap(0)])
        self.assertEqual(out["state"], "LAB_THREE_DAILY_CALENDAR_REVIEW_ONLY")
        self.assertEqual(out["claimed_capture_count"], 2)

    def test_forged_live_flags_future_snapshot_or_spoofed_url_block(self):
        bad_live = nz_observed(0)
        bad_live["original_source_bytes_attested"] = True
        future = nz_observed(2)
        forged = nz_observed(0)
        forged["events"][0]["source_url"] = (
            "https://www.rbnz.govt.nz.example.invalid/events"
        )
        for c in ([cap(0, [bad_live])], [cap(0, [future])],
                  [cap(0, [forged])]):
            with self.subTest(c=c):
                out = review(c)
                self.assertEqual(out["state"], "LAB_BLOCKED")
                self.assertEqual(out["review_queue"], [])

    def test_invalid_envelope_and_more_than_three_snapshots_block(self):
        for c in ("bad", [{}], [cap(0)] * 4,
                  [dict(cap(0), scheduled_live=True)],
                  [dict(cap(0), snapshots="malformed")]):
            with self.subTest(c=c):
                self.assertEqual(review(c)["state"], "LAB_BLOCKED")

    def test_stale_claim_is_flagged_without_automatic_refresh(self):
        old = nz_observed(0, events=[event(updated="2026-10-31T12:00:00Z")])
        old["observed_at_utc"] = "2026-11-01T08:00:00Z"
        out = review([cap(0, [old])])
        self.assertEqual(len(out["aged_claimed_source_observations"]), 1)
        self.assertFalse(out["three_daily_updates_verified"])

    def test_no_network_cost_worker_or_trading_and_naive_clock_refused(self):
        out = review([cap(0, [nz_observed(0)])])
        for field in ("trade_authorized", "can_feed_live_radar", "worker_enabled",
                      "scheduler_enabled", "notifications_sent",
                      "realtime_calendar_verified", "source_authenticity_attested"):
            self.assertFalse(out[field], field)
        self.assertEqual((out["external_http_requests"], out["new_cost_brl"]), (0, 0))
        with self.assertRaises(ValueError):
            build_three_daily_calendar_review_lab([], at=NOW.replace(tzinfo=None))


if __name__ == "__main__":
    unittest.main()
