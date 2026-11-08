"""Retrospective RBNZ table is never misclassified as a release-time feed."""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
import unittest

from atlasquant_trader_nzd_ocr_decision_index_lab import (
    INDEX_RESEARCH_ROWS, INDEX_URL, inspect_nzd_ocr_decision_index_lab,
)
from atlasquant_trader_gbp_nzd_official_pilot_lab import (
    PILOT, inspect_gbp_nzd_publisher_pilot_lab,
)


class NZDOCRHistoryIndexResearchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.r = inspect_nzd_ocr_decision_index_lab()

    def test_history_is_an_official_publisher_index(self) -> None:
        self.assertEqual(self.r["currency"], "NZD")
        self.assertEqual(self.r["source_url"], INDEX_URL)
        self.assertEqual(self.r["history_page_lists_decisions_since_year"], 1999)
        self.assertEqual(self.r["reviewed_on_utc_date"], "2026-11-08")

    def test_thirteen_transcribed_rows_from_2025_and_2026(self) -> None:
        self.assertEqual(len(INDEX_RESEARCH_ROWS), 13)
        self.assertEqual(self.r["index_rows_count"], 13)
        self.assertEqual(INDEX_RESEARCH_ROWS[0], ("2025-02-19", "3.75"))
        self.assertEqual(INDEX_RESEARCH_ROWS[-1], ("2026-10-28", "2.75"))

    def test_decision_dates_are_strictly_increasing_and_unique(self) -> None:
        dates = [date.fromisoformat(x[0]) for x in INDEX_RESEARCH_ROWS]
        self.assertEqual(dates, sorted(set(dates)))

    def test_october_index_matches_release_headline_level(self) -> None:
        self.assertEqual(INDEX_RESEARCH_ROWS[-1], ("2026-10-28", "2.75"))
        self.assertIn("ocr-held-at-2-75-percent", self.r["2026_october_media_release_url"])

    def test_gbp_nzd_pilot_links_the_same_index_without_extra_authority(self) -> None:
        row = PILOT["NZD_OCR_2026_10"]
        self.assertEqual(row["decision_history_index_url"], INDEX_URL)
        self.assertEqual(row["decision_history_index_delay_hours"], 24)
        pilot = inspect_gbp_nzd_publisher_pilot_lab(
            decision_at_utc=datetime(2026, 11, 8, tzinfo=timezone.utc))
        entry = pilot["observations"]["NZD_OCR_2026_10"]
        self.assertEqual(entry["decision_history_index_url"], INDEX_URL)
        self.assertFalse(entry["eligible_for_exante_backtest"])
        self.assertFalse(entry["independent_historical_capture_attested"])

    def test_index_explicitly_warns_about_a_day_of_update_delay(self) -> None:
        self.assertEqual(self.r["index_update_delay_notice_hours"], 24)
        self.assertTrue(self.r["index_updated_later_than_original_announcements"])

    def test_policy_values_are_decimal_text_not_auto_strengths(self) -> None:
        for _, rate in INDEX_RESEARCH_ROWS:
            self.assertIsInstance(rate, str)
            self.assertLessEqual(Decimal("0"), Decimal(rate))
            self.assertLessEqual(Decimal(rate), Decimal("10"))

    def test_october_hold_not_mistaken_for_a_rate_hike(self) -> None:
        self.assertEqual(INDEX_RESEARCH_ROWS[-2][1], INDEX_RESEARCH_ROWS[-1][1])

    def test_research_has_no_as_of_decision_replay_api(self) -> None:
        self.assertNotIn("availability_floor_utc", self.r)
        self.assertNotIn("historical_as_of", self.r)
        self.assertFalse(self.r["issuer_original_release_second_proved"])

    def test_no_row_claims_original_bytes_or_backtest_eligibility(self) -> None:
        for row in self.r["index_rows_research_only"]:
            self.assertFalse(row["original_decision_issue_time_attested"])
            self.assertFalse(row["issuer_document_bytes_as_of_decision_archived"])
            self.assertFalse(row["eligible_for_historical_backtest"])

    def test_no_backtest_bias_or_probability(self) -> None:
        self.assertFalse(self.r["historical_backtest_approved"])
        self.assertFalse(self.r["original_point_in_time_vintage_attested"])
        self.assertFalse(self.r["cross_currency_strength_comparison_approved"])
        self.assertIsNone(self.r["forecast_probability"])
        self.assertEqual(self.r["operational_bias"], "AGUARDAR")
        self.assertFalse(self.r["trade_authorized"])

    def test_no_network_paid_api_or_worker(self) -> None:
        self.assertEqual(self.r["http_requests_at_runtime"], 0)
        self.assertEqual(self.r["new_cost_brl"], 0)
        self.assertFalse(self.r["worker_enabled"] or self.r["scheduler_enabled"])


if __name__ == "__main__":
    unittest.main()
