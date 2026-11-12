"""Offline chronology and abstention tests for CHF/JPY official research."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import unittest

from atlasquant_trader_chf_jpy_official_pilot_lab import (
    OFFICIAL_OBSERVATIONS, inspect_chf_jpy_official_pilot_lab,
)


def at(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


class ChfJpyOfficialResearchTests(unittest.TestCase):
    def audit(self, text: str) -> dict:
        return inspect_chf_jpy_official_pilot_lab(decision_at_utc=at(text))

    def test_four_official_sources_both_families(self) -> None:
        self.assertEqual(len(OFFICIAL_OBSERVATIONS), 4)
        self.assertEqual({(r["currency"], r["family"]) for r in OFFICIAL_OBSERVATIONS.values()}, {
            ("CHF", "INFLATION"), ("CHF", "POLICY"), ("JPY", "INFLATION"), ("JPY", "POLICY")})

    def test_https_and_primary_domains(self) -> None:
        hosts = ("www.snb.ch", "www.stat.go.jp", "www.boj.or.jp", "www.bfs.admin.ch")
        for row in OFFICIAL_OBSERVATIONS.values():
            self.assertTrue(any(row["document_url"].startswith("https://" + h + "/") for h in hosts))

    def test_chf_national_cpi_value_is_year_on_year_not_monthly(self) -> None:
        r = OFFICIAL_OBSERVATIONS["CHF_CPI_2026_10"]
        self.assertEqual((r["observation_period"], r["value_percent"], r["value_qualifier"]),
                         ("2026-10", "1.5", "YOY_ALL_ITEMS"))

    def test_jpy_cpi_all_items_is_not_core_definition(self) -> None:
        r = OFFICIAL_OBSERVATIONS["JPY_NATIONAL_CPI_2026_09"]
        self.assertEqual((r["value_percent"], r["metric"]), ("2.1", "JP_NATIONAL_ALL_ITEMS_CPI_YOY_PCT"))
        self.assertTrue(r["source_page_mutable"])

    def test_boj_policy_is_around_125_not_exact_deposit_rate(self) -> None:
        r = OFFICIAL_OBSERVATIONS["JPY_BOJ_OVERNIGHT_GUIDELINE_2026_10"]
        self.assertEqual((r["value_percent"], r["value_qualifier"]),
                         ("1.25", "AROUND_TARGET_NOT_FIXED_POINT"))

    def test_boj_document_exact_release_1202_jst_0302_utc(self) -> None:
        r = OFFICIAL_OBSERVATIONS["JPY_BOJ_OVERNIGHT_GUIDELINE_2026_10"]
        self.assertEqual(r["availability_floor_utc"], "2026-10-30T03:02:00Z")
        self.assertIn("PDF_PAGE_3", r["time_evidence"])

    def test_missing_exact_time_uses_next_day_research_floor(self) -> None:
        for key in ("CHF_CPI_2026_10", "CHF_SNB_POLICY_2026_09", "JPY_NATIONAL_CPI_2026_09"):
            r = OFFICIAL_OBSERVATIONS[key]
            self.assertIn("DATE_ONLY_CONSERVATIVE", r["time_evidence"])
            self.assertEqual(at(r["availability_floor_utc"]).date(),
                             datetime.fromisoformat(r["published_date"]).date() + timedelta(days=1))

    def test_before_each_release_no_future_values(self) -> None:
        for key, record in OFFICIAL_OBSERVATIONS.items():
            with self.subTest(key=key):
                early = inspect_chf_jpy_official_pilot_lab(
                    decision_at_utc=at(record["availability_floor_utc"]) - timedelta(seconds=1))
                self.assertIsNone(early["observations"][key]["research_value_percent"])
                self.assertFalse(early["observations"][key]["eligible_for_exante_backtest"])

    def test_at_each_floor_research_value_visible_but_not_attested(self) -> None:
        for key, record in OFFICIAL_OBSERVATIONS.items():
            with self.subTest(key=key):
                result = inspect_chf_jpy_official_pilot_lab(
                    decision_at_utc=at(record["availability_floor_utc"]))
                self.assertEqual(result["observations"][key]["research_value_percent"], record["value_percent"])
                self.assertFalse(result["observations"][key]["independent_historical_capture_attested"])

    def test_jpy_policy_not_available_before_1202_jst(self) -> None:
        a = self.audit("2026-10-30T03:01:59Z")
        b = self.audit("2026-10-30T03:02:00Z")
        key = "JPY_BOJ_OVERNIGHT_GUIDELINE_2026_10"
        self.assertIsNone(a["observations"][key]["research_value_percent"])
        self.assertEqual(b["observations"][key]["research_value_percent"], "1.25")

    def test_pre_release_none_visible(self) -> None:
        r = self.audit("2026-09-01T00:00:00Z")
        self.assertEqual(r["publisher_boundary_passed_count"], 0)

    def test_research_never_authorizes_score_or_trade(self) -> None:
        r = self.audit("2026-11-08T10:00:00Z")
        self.assertEqual(r["publisher_boundary_passed_count"], 4)
        self.assertFalse(r["historical_capture_attested"])
        self.assertFalse(r["point_in_time_backtest_approved"])
        self.assertFalse(r["macro_cross_currency_comparison_approved"])
        self.assertIsNone(r["forecast_probability"])
        self.assertEqual(r["operational_bias"], "AGUARDAR")
        self.assertFalse(r["trade_authorized"])

    def test_timezone_aware_normalized(self) -> None:
        a = self.audit("2026-11-04T00:00:00Z")
        b = inspect_chf_jpy_official_pilot_lab(decision_at_utc=datetime(
            2026, 11, 3, 20, tzinfo=timezone(timedelta(hours=-4))))
        self.assertEqual(a, b)

    def test_naive_datetime_refused(self) -> None:
        with self.assertRaises(ValueError):
            inspect_chf_jpy_official_pilot_lab(decision_at_utc=datetime(2026, 11, 8))

    def test_microsecond_datetime_refused(self) -> None:
        with self.assertRaises(ValueError):
            inspect_chf_jpy_official_pilot_lab(decision_at_utc=at("2026-11-08T10:00:00Z").replace(microsecond=1))


if __name__ == "__main__":
    unittest.main()
