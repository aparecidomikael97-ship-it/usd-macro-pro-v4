"""Two Fed Cleveland CPI forecasts must never cross dates or masquerade as FX signals."""
from datetime import datetime, timezone, timedelta
from pathlib import Path
import json
import unittest

from atlasquant_trader_us_octnov2026_clevelandfed_two_horizons_lab import (
    PINNED_NOV_RECEIPT_SHA256,
    inspect_us_octnov2026_clevelandfed_two_horizons_lab as inspect,
)

DOCS = Path(__file__).resolve().parent / "docs" / "continuidade"
OCT = (DOCS / "TRADER_US_OCT2026_CLEVELANDFED_FORWARD_NOWCAST_RECEIPT_20261106.json").read_bytes()
NOV = (DOCS / "TRADER_US_NOV2026_CLEVELANDFED_EARLY_NOWCAST_RECEIPT_20261106.json").read_bytes()


def at(month, day, hour=0, minute=0):
    return datetime(2026, month, day, hour, minute, tzinfo=timezone.utc)


class ClevelandFedOctNovDistinctHorizonTests(unittest.TestCase):
    def case(self, when=at(11, 8), oct_raw=OCT, nov_raw=NOV):
        return inspect(oct_raw, nov_raw, as_of_utc=when)

    def assert_never_market_fx_signal(self, r):
        self.assertEqual(r["operational_bias"], "AGUARDAR")
        self.assertIsNone(r["fx_bias"])
        self.assertIsNone(r["usd_strength_score"])
        self.assertIsNone(r["oct_vs_nov_inflation_level_delta"])
        self.assertEqual(r["official_first_release_actual_by_month"], {})
        self.assertEqual(r["model_error_by_month"], {})
        self.assertEqual(r["market_consensus_by_month"], {})
        self.assertEqual(r["market_surprise_by_month"], {})
        self.assertFalse(r["source_page_original_html_archived"])
        self.assertFalse(r["exact_source_capture_instant_independently_attested"])
        self.assertEqual(r["validated_forward_prediction_count"], 0)
        self.assertIsNone(r["validated_accuracy"])
        self.assertEqual((r["http_requests"], r["new_cost_brl"]), (0, 0))
        for key in ("can_feed_live_radar", "trade_authorized", "publishable",
                    "worker_enabled", "scheduler_enabled"):
            self.assertFalse(r[key], key)

    def test_two_distinct_forecast_months_before_october_release(self):
        r = self.case()
        self.assertEqual(r["state"], "LAB_TWO_SEPARATE_PRE_RELEASE_WINDOWS")
        self.assertEqual(r["nov_receipt_sha256"], PINNED_NOV_RECEIPT_SHA256)
        self.assertTrue(r["source_is_two_separate_forecast_horizons"])
        self.assertEqual(r["forecast_months_visible"], ["2026-10", "2026-11"])
        rows = r["forecast_rows_documentary_only"]
        self.assertEqual([row["model_forecast_yoy_percent"] for row in rows], [3.74, 3.88])
        self.assertEqual([row["scheduled_first_release_utc"] for row in rows],
                         ["2026-11-10T13:30:00Z", "2026-12-10T13:30:00Z"])
        self.assertEqual([row["release_window"] for row in rows],
                         ["BEFORE_SCHEDULED_RELEASE", "BEFORE_SCHEDULED_RELEASE"])
        self.assert_never_market_fx_signal(r)

    def test_no_november_research_data_visible_in_october_simulation(self):
        for when in (at(10, 30), at(11, 6), at(11, 6, 23, 59)):
            r = self.case(when)
            self.assertEqual(r["state"], "LAB_TWO_FORECAST_MONTHS_UNAVAILABLE_ASOF")
            self.assertEqual(r["forecast_rows_documentary_only"], [])
            self.assertEqual(r["forecast_months_visible"], [])
            self.assert_never_market_fx_signal(r)

    def test_october_release_window_does_not_end_november_forecast(self):
        r = self.case(at(11, 10, 13, 30))
        self.assertEqual(r["state"], "LAB_OCT_AFTER_SCHEDULE_NOV_BEFORE_SCHEDULE")
        rows = r["forecast_rows_documentary_only"]
        self.assertEqual(rows[0]["release_window"],
                         "AFTER_SCHEDULED_RELEASE_NO_AUTHENTICATED_ACTUAL")
        self.assertEqual(rows[1]["release_window"], "BEFORE_SCHEDULED_RELEASE")
        self.assert_never_market_fx_signal(r)

    def test_december_release_window_no_fabricated_actual(self):
        r = self.case(at(12, 10, 13, 30))
        self.assertEqual(r["state"],
                         "LAB_BOTH_RELEASE_SCHEDULES_PASSED_NO_OFFICIAL_ACTUAL")
        for row in r["forecast_rows_documentary_only"]:
            self.assertEqual(row["release_window"],
                             "AFTER_SCHEDULED_RELEASE_NO_AUTHENTICATED_ACTUAL")
        self.assert_never_market_fx_signal(r)

    def test_separate_month_yoy_forecasts_not_used_as_strength_spread(self):
        r = self.case(at(12, 11))
        self.assertEqual(r["forecast_rows_documentary_only"][0]["model_forecast_yoy_percent"],
                         3.74)
        self.assertEqual(r["forecast_rows_documentary_only"][1]["model_forecast_yoy_percent"],
                         3.88)
        self.assertIsNone(r["oct_vs_nov_inflation_level_delta"])
        self.assertIsNone(r["usd_strength_score"])
        self.assert_never_market_fx_signal(r)

    def test_fake_early_november_result_or_source_change_rejected(self):
        changes = (("source_transcribed_forecast_percent", 5.0),
                   ("target_reference_month", "2026-10"),
                   ("source_page_row", "INFLATION_YEAR_OVER_YEAR_OCTOBER_2026_CPI_HEADLINE"),
                   ("source_page_updated_calendar_date", "2026-12-10"),
                   ("first_release_calendar_schedule_url", "https://example.com"),
                   ("first_release_scheduled_utc", "2026-11-10T13:30:00Z"),
                   ("first_release_actual_observed", True),
                   ("first_release_actual_headline_cpi_yoy_percent", 3.8),
                   ("may_infer_fx_direction", True),
                   ("source_original_html_bytes_archived", True))
        for key, value in changes:
            modified = json.loads(NOV)
            modified[key] = value
            r = self.case(nov_raw=json.dumps(modified).encode())
            self.assertEqual(r["state"], "LAB_BLOCKED", key)
            self.assert_never_market_fx_signal(r)

    def test_parent_receipt_change_duplicate_json_and_bad_clock_block(self):
        self.assertEqual(self.case(oct_raw=OCT + b" ")["state"], "LAB_BLOCKED")
        for bad in (None, "string", {}, b"", NOV + b" "):
            self.assertEqual(self.case(nov_raw=bad)["state"], "LAB_BLOCKED")
        duplicate = NOV.replace(b'"schema":', b'"schema":"x","schema":', 1)
        self.assertEqual(self.case(nov_raw=duplicate)["state"], "LAB_BLOCKED")
        for bad_clock in (None, "2026-11-08", datetime(2026, 11, 8)):
            self.assertEqual(self.case(bad_clock)["state"], "LAB_BLOCKED")

    def test_timezone_equivalence(self):
        local = datetime(2026, 11, 7, 20, tzinfo=timezone(timedelta(hours=-4)))
        self.assertEqual(self.case(local), self.case(at(11, 8)))


if __name__ == "__main__":
    unittest.main()
