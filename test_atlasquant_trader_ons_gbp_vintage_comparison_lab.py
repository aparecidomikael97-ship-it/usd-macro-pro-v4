"""Synthetic-only ONS revision/date-cutoff tests. No HTTP or ONS originals."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
import unittest

from atlasquant_trader_ons_gbp_vintage_comparison_lab import (
    SCHEMA, compare_ons_gbp_d7g7_vintages_lab as compare,
)

CAPTURED = datetime(2026, 11, 5, 12, tzinfo=timezone.utc)


def snapshot(release, months):
    return {
        "cdid": "D7G7", "dataset": "MM23",
        "description": "CPI ANNUAL RATE 00: ALL ITEMS 2015=100",
        "unit": "%", "preUnit": "", "date": release,
        "months": [{"date": period, "value": value}
                   for period, value in months],
    }


def raw(obj):
    return json.dumps(obj).encode("utf-8")


EARLIER = snapshot("16 September 2026", [
    ("2026 JUN", "2.5"), ("2026 JUL", "2.9"), ("2026 AUG", "3.1"),
])
LATER = snapshot("21 October 2026", [
    ("2026 JUN", "2.5"), ("2026 JUL", "2.9"),
    ("2026 AUG", "3.2"), ("2026 SEP", "3.5"),
])


def cutoff(year=2026, month=10, day=1, hour=12):
    return datetime(year, month, day, hour, tzinfo=timezone.utc)


_UNSET = object()


def run(earlier=_UNSET, later=_UNSET, **kw):
    return compare(
        earlier_vintage_raw=raw(EARLIER) if earlier is _UNSET else earlier,
        later_vintage_raw=raw(LATER) if later is _UNSET else later,
        captured_at_utc=kw.get("captured", CAPTURED),
        historical_cutoff_utc=kw.get("asof", cutoff()),
    )


class OnsVintageComparisonTests(unittest.TestCase):
    def assert_hard_block(self, r):
        for key in (
            "source_origin_independently_verified",
            "historical_vintage_archive_verified", "publication_instant_verified",
            "point_in_time_available_verified", "usable_in_historical_backtest",
            "methodologically_comparable_to_other_cpi", "trade_authorized",
            "can_feed_live_radar", "worker_enabled", "scheduler_enabled",
            "publishable",
        ):
            self.assertIs(r[key], False, key)
        self.assertEqual(r["operational_bias"], "AGUARDAR")
        self.assertIsNone(r["fx_bias"])
        self.assertEqual((r["external_http_requests"], r["new_cost_brl"]), (0, 0))

    def test_detect_revised_same_month_and_new_month_without_signal(self):
        r = run()
        self.assertEqual(r["schema"], SCHEMA)
        self.assertEqual(r["state"], "LAB_UNATTESTED_VINTAGE_DIFFERENCES_QUARANTINED")
        self.assertEqual(r["revised_months"], [{
            "period": "2026-08",
            "earlier_annual_cpi_percent_claim": "3.1",
            "later_annual_cpi_percent_claim": "3.2",
        }])
        self.assertEqual(r["newly_observed_months"], ["2026-09"])
        self.assertEqual(r["unchanged_common_month_count"], 2)
        self.assertEqual(r["no_longer_observed_in_window"], [])
        self.assertEqual(r["earlier_claimed_release_date"], "2026-09-16")
        self.assertEqual(r["later_claimed_release_date"], "2026-10-21")
        self.assertEqual(len(r["earlier_raw_sha256"]), 64)
        self.assertNotEqual(r["earlier_raw_sha256"], r["later_raw_sha256"])
        self.assert_hard_block(r)

    def test_pre_later_vintage_cutoff_marks_possible_lookahead(self):
        r = run(asof=cutoff(2026, 10, 20))
        self.assertIs(r["later_release_after_asof_calendar"], True)
        self.assertEqual(r["later_cutoff_status"], "CALENDAR_RELEASE_AFTER_CUTOFF_BLOCKED")
        self.assert_hard_block(r)

    def test_pre_earlier_vintage_cutoff_blocks_both(self):
        r = run(asof=cutoff(2026, 9, 15))
        self.assertEqual(r["earlier_cutoff_status"], "CALENDAR_RELEASE_AFTER_CUTOFF_BLOCKED")
        self.assertEqual(r["later_cutoff_status"], "CALENDAR_RELEASE_AFTER_CUTOFF_BLOCKED")
        self.assert_hard_block(r)

    def test_release_day_intraday_unresolved_for_earlier(self):
        r = run(asof=cutoff(2026, 9, 16, 23))
        self.assertIs(r["same_day_release_instant_unknown"], True)
        self.assertIn("SAME_CALENDAR_DAY", r["earlier_cutoff_status"])
        self.assert_hard_block(r)

    def test_release_day_intraday_unresolved_for_later(self):
        r = run(asof=cutoff(2026, 10, 21, 23))
        self.assertIs(r["same_day_release_instant_unknown"], True)
        self.assertIn("SAME_CALENDAR_DAY", r["later_cutoff_status"])
        self.assert_hard_block(r)

    def test_date_prior_to_cutoff_is_still_not_pit_attestation(self):
        r = run(asof=cutoff(2026, 10, 22))
        self.assertIs(r["later_release_after_asof_calendar"], False)
        self.assertEqual(r["later_cutoff_status"],
                         "CALENDAR_EARLIER_BUT_HISTORICAL_AVAILABILITY_UNATTESTED")
        self.assert_hard_block(r)

    def test_equal_numeric_value_different_format_not_a_revision(self):
        new = deepcopy(LATER)
        new["months"][2]["value"] = "3.10"
        r = run(later=raw(new))
        self.assertEqual(r["revised_months"], [])
        self.assertEqual(r["unchanged_common_month_count"], 3)
        self.assert_hard_block(r)

    def test_missing_to_number_is_not_zero_and_is_flagged(self):
        older = deepcopy(EARLIER)
        older["months"][1]["value"] = ".."
        r = run(earlier=raw(older))
        self.assertEqual(r["revised_months"][0]["period"], "2026-07")
        self.assertIsNone(r["revised_months"][0]["earlier_annual_cpi_percent_claim"])
        self.assertEqual(len(r["revised_months"]), 2)
        self.assert_hard_block(r)

    def test_number_to_missing_is_flagged(self):
        newer = deepcopy(LATER)
        newer["months"][1]["value"] = ".."
        r = run(later=raw(newer))
        self.assertEqual(r["revised_months"][0]["period"], "2026-07")
        self.assertIsNone(r["revised_months"][0]["later_annual_cpi_percent_claim"])
        self.assert_hard_block(r)

    def test_both_missing_are_not_a_revision(self):
        older, newer = deepcopy(EARLIER), deepcopy(LATER)
        older["months"][0]["value"] = ".."
        newer["months"][0]["value"] = None
        r = run(earlier=raw(older), later=raw(newer))
        self.assertEqual([x["period"] for x in r["revised_months"]], ["2026-08"])
        self.assert_hard_block(r)

    def test_disappearing_month_only_absent_in_comparison_window(self):
        older = deepcopy(EARLIER)
        older["months"].insert(0, {"date": "2026 MAY", "value": "2.4"})
        r = run(earlier=raw(older))
        self.assertEqual(r["no_longer_observed_in_window"], ["2026-05"])
        self.assertEqual(r["comparison_window"], "LAST_15_MONTHLY_ROWS_PER_PROVIDED_SNAPSHOT")
        self.assert_hard_block(r)

    def test_same_release_dates_rejected(self):
        newer = deepcopy(LATER)
        newer["date"] = EARLIER["date"]
        self.assertEqual(run(later=raw(newer))["reason"],
                         "REPORTED_VINTAGE_DATES_NOT_STRICTLY_ORDERED")

    def test_reversed_release_dates_rejected(self):
        self.assertEqual(run(earlier=raw(LATER), later=raw(EARLIER))["reason"],
                         "REPORTED_VINTAGE_DATES_NOT_STRICTLY_ORDERED")

    def test_future_cutoff_relative_to_capture_rejected(self):
        self.assertEqual(run(asof=cutoff(2026, 11, 6))["reason"],
                         "INVALID_INPUT_OR_CLOCK")

    def test_naive_missing_or_invalid_clock_rejected(self):
        for wrong in (None, datetime(2026, 11, 5), "2026-11-05"):
            self.assertEqual(run(captured=wrong)["state"], "LAB_BLOCKED")
            self.assertEqual(run(asof=wrong)["state"], "LAB_BLOCKED")

    def test_invalid_or_spoofed_json_snapshots_rejected(self):
        for wrong in (b"x" * 125, b"", "fake-json", None):
            self.assertEqual(run(earlier=wrong)["reason"],
                             "INVALID_INPUT_OR_CLOCK" if not isinstance(wrong, bytes)
                             else "EARLIER_OR_LATER_SNAPSHOT_INVALID")
            self.assertEqual(run(later=wrong)["state"], "LAB_BLOCKED")

    def test_wrong_series_or_duplicate_json_key_rejected(self):
        bad = deepcopy(EARLIER)
        bad["cdid"] = "OTHER"
        self.assertEqual(run(earlier=raw(bad))["reason"],
                         "EARLIER_OR_LATER_SNAPSHOT_INVALID")
        dup = raw(LATER).replace(b'"cdid": "D7G7",',
                               b'"cdid": "D7G7", "cdid": "D7G7",')
        self.assertEqual(run(later=dup)["state"], "LAB_BLOCKED")

    def test_future_reported_release_date_rejected(self):
        newer = deepcopy(LATER)
        newer["date"] = "18 November 2026"
        self.assertEqual(run(later=raw(newer))["reason"],
                         "EARLIER_OR_LATER_SNAPSHOT_INVALID")

    def test_all_cutoffs_remain_hard_no_go(self):
        for asof in (cutoff(2026, 9, 15), cutoff(2026, 9, 16),
                     cutoff(2026, 10, 20), cutoff(2026, 10, 21),
                     cutoff(2026, 11, 4)):
            self.assert_hard_block(run(asof=asof))


if __name__ == "__main__":
    unittest.main()
