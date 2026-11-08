"""Offline chronological and abstention tests for official-page research."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
import unittest

from atlasquant_trader_gbp_nzd_official_pilot_lab import (
    PILOT, inspect_gbp_nzd_publisher_pilot_lab,
)


def at(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


class OfficialResearchPilotTests(unittest.TestCase):
    def test_four_independent_release_documents(self) -> None:
        self.assertEqual(len(PILOT), 4)
        self.assertEqual({(x["currency"], x["family"]) for x in PILOT.values()}, {
            ("GBP", "INFLATION"), ("GBP", "POLICY"),
            ("NZD", "INFLATION"), ("NZD", "POLICY"),
        })

    def test_inflation_periods_are_not_assumed_same_frequency(self) -> None:
        self.assertEqual(PILOT["GBP_CPI_2026_09"]["observation_period"], "2026-09")
        self.assertEqual(PILOT["NZD_CPI_2026_Q3"]["observation_period"], "2026-Q3")

    def test_official_research_urls_use_https(self) -> None:
        for row in PILOT.values():
            with self.subTest(row=row["metric"]):
                self.assertTrue(row["document_url"].startswith("https://"))
                self.assertTrue(row["timing_url"].startswith("https://"))

    def test_before_each_release_never_shows_future_number(self) -> None:
        for key, row in PILOT.items():
            with self.subTest(key=key):
                cutoff = at(row["availability_floor_utc"]) - timedelta(seconds=1)
                result = inspect_gbp_nzd_publisher_pilot_lab(decision_at_utc=cutoff)
                record = result["observations"][key]
                self.assertEqual(record["publisher_timing_status"], "NOT_YET_PUBLIC_BY_BOUNDARY")
                self.assertIsNone(record["research_value_percent"])
                self.assertFalse(record["eligible_for_exante_backtest"])

    def test_at_each_boundary_research_value_visible_only_as_research(self) -> None:
        for key, row in PILOT.items():
            with self.subTest(key=key):
                result = inspect_gbp_nzd_publisher_pilot_lab(
                    decision_at_utc=at(row["availability_floor_utc"]))
                record = result["observations"][key]
                self.assertEqual(record["research_value_percent"], row["value_percent"])
                self.assertFalse(record["original_document_bytes_archived"])
                self.assertFalse(record["independent_historical_capture_attested"])
                self.assertFalse(record["eligible_for_exante_backtest"])

    def test_uk_inflation_not_usable_before_ons_7am_bst(self) -> None:
        a = inspect_gbp_nzd_publisher_pilot_lab(decision_at_utc=at("2026-10-21T05:59:59Z"))
        b = inspect_gbp_nzd_publisher_pilot_lab(decision_at_utc=at("2026-10-21T06:00:00Z"))
        self.assertIsNone(a["observations"]["GBP_CPI_2026_09"]["research_value_percent"])
        self.assertEqual(b["observations"]["GBP_CPI_2026_09"]["research_value_percent"], "3.5")

    def test_nz_inflation_is_evening_of_previous_utc_day(self) -> None:
        a = inspect_gbp_nzd_publisher_pilot_lab(decision_at_utc=at("2026-10-21T21:44:59Z"))
        b = inspect_gbp_nzd_publisher_pilot_lab(decision_at_utc=at("2026-10-21T21:45:00Z"))
        self.assertIsNone(a["observations"]["NZD_CPI_2026_Q3"]["research_value_percent"])
        self.assertEqual(b["observations"]["NZD_CPI_2026_Q3"]["research_value_percent"], "3.7")

    def test_boe_release_date_only_is_deferred_to_next_day(self) -> None:
        same_day = inspect_gbp_nzd_publisher_pilot_lab(decision_at_utc=at("2026-11-05T23:59:59Z"))
        next_day = inspect_gbp_nzd_publisher_pilot_lab(decision_at_utc=at("2026-11-06T00:00:00Z"))
        self.assertIsNone(same_day["observations"]["GBP_BANK_RATE_2026_11"]["research_value_percent"])
        self.assertEqual(next_day["observations"]["GBP_BANK_RATE_2026_11"]["research_value_percent"], "4.0")

    def test_nz_ocr_update_not_original_archive(self) -> None:
        result = inspect_gbp_nzd_publisher_pilot_lab(decision_at_utc=at("2026-10-28T01:00:00Z"))
        row = result["observations"]["NZD_OCR_2026_10"]
        self.assertEqual(row["research_value_percent"], "2.75")
        self.assertIn("NOT_ORIGINAL_ARCHIVE", row["time_evidence"])
        self.assertFalse(row["eligible_for_exante_backtest"])

    def test_pre_release_decision_yields_no_values(self) -> None:
        result = inspect_gbp_nzd_publisher_pilot_lab(decision_at_utc=at("2026-10-01T00:00:00Z"))
        self.assertEqual(result["publisher_boundary_passed_count"], 0)
        self.assertTrue(all(x["research_value_percent"] is None for x in result["observations"].values()))

    def test_after_all_releases_still_abstain(self) -> None:
        result = inspect_gbp_nzd_publisher_pilot_lab(decision_at_utc=at("2026-11-07T20:00:00Z"))
        self.assertEqual(result["publisher_boundary_passed_count"], 4)
        self.assertFalse(result["historical_capture_attested"])
        self.assertFalse(result["point_in_time_backtest_approved"])
        self.assertEqual(result["operational_bias"], "AGUARDAR")
        self.assertIsNone(result["forecast_probability"])
        self.assertFalse(result["trade_authorized"])

    def test_timezone_aware_cutoff_required(self) -> None:
        with self.assertRaises(ValueError):
            inspect_gbp_nzd_publisher_pilot_lab(decision_at_utc=datetime(2026, 11, 7))

    def test_cutoff_with_offset_normalized(self) -> None:
        utc = inspect_gbp_nzd_publisher_pilot_lab(decision_at_utc=at("2026-10-21T21:45:00Z"))
        minus_four = inspect_gbp_nzd_publisher_pilot_lab(decision_at_utc=datetime(
            2026, 10, 21, 17, 45, 0, tzinfo=timezone(timedelta(hours=-4))))
        self.assertEqual(utc, minus_four)

    def test_microsecond_cutoff_refused(self) -> None:
        with self.assertRaises(ValueError):
            inspect_gbp_nzd_publisher_pilot_lab(decision_at_utc=at("2026-11-07T00:00:00Z").replace(microsecond=1))


if __name__ == "__main__":
    unittest.main()
