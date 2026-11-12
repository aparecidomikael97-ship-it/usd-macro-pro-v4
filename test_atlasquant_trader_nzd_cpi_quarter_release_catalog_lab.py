"""NZ quarterly CPI dates and stage must not leak into historical decisions."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from decimal import Decimal
import unittest
from unittest.mock import patch
from zoneinfo import ZoneInfo

from atlasquant_trader_nzd_cpi_quarter_release_catalog_lab import (
    RELEASES, inspect_nzd_cpi_quarter_release_catalog_lab,
)
from atlasquant_trader_gbp_nzd_official_pilot_lab import PILOT


def at(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


class NZDQuarterlyCPIReleaseResearchTests(unittest.TestCase):
    def inspect(self, stamp: str = "2026-11-08T12:00:00Z", tf: str = "D1") -> dict:
        return inspect_nzd_cpi_quarter_release_catalog_lab(
            decision_at_utc=at(stamp), horizon=tf)

    def test_four_distinct_quarters_and_two_distinct_years(self) -> None:
        r = self.inspect()
        self.assertEqual(set(r["records"]), {"2025-Q4", "2026-Q1", "2026-Q2", "2026-Q3"})
        self.assertEqual(r["research_available_count"], 4)

    def test_annual_values_remain_strings_research_only(self) -> None:
        self.assertEqual([x["cpi_yoy_pct_on_current_release_pages"] for x in RELEASES],
                         ["3.1", "3.1", "4.1", "3.7"])
        self.assertTrue(all(Decimal(x["cpi_yoy_pct_on_current_release_pages"]) > 0
                            for x in RELEASES))

    def test_each_quarter_pre_release_has_no_value(self) -> None:
        for release in RELEASES:
            floor = at(release["availability_floor_utc"])
            with self.subTest(period=release["period"]):
                before = inspect_nzd_cpi_quarter_release_catalog_lab(
                    decision_at_utc=floor-timedelta(seconds=1), horizon="D1")
                after = inspect_nzd_cpi_quarter_release_catalog_lab(
                    decision_at_utc=floor, horizon="D1")
                key = release["period"]
                self.assertIsNone(before["records"][key]["research_cpi_yoy_pct"])
                self.assertEqual(after["records"][key]["research_cpi_yoy_pct"],
                                 release["cpi_yoy_pct_on_current_release_pages"])
                self.assertFalse(after["records"][key]["backtest_approved"])

    def test_july_publisher_clock_nzst_converts_to_utc(self) -> None:
        local = datetime(2026, 7, 21, 10, 45, tzinfo=ZoneInfo("Pacific/Auckland"))
        self.assertEqual(local.astimezone(timezone.utc), at("2026-07-20T22:45:00Z"))

    def test_october_publisher_clock_nzdt_converts_to_utc(self) -> None:
        local = datetime(2026, 10, 22, 10, 45, tzinfo=ZoneInfo("Pacific/Auckland"))
        self.assertEqual(local.astimezone(timezone.utc), at("2026-10-21T21:45:00Z"))

    def test_october_floor_matches_existing_nzd_cpi_pilot(self) -> None:
        existing = PILOT["NZD_CPI_2026_Q3"]
        self.assertEqual(RELEASES[-1]["availability_floor_utc"], existing["availability_floor_utc"])
        self.assertEqual(RELEASES[-1]["cpi_yoy_pct_on_current_release_pages"], existing["value_percent"])

    def test_january_and_april_date_only_not_invented_release_clocks(self) -> None:
        for release in RELEASES[:2]:
            self.assertEqual(release["release_local_time"], "NOT_ESTABLISHED_FOR_THIS_RELEASE")
            self.assertEqual(release["time_evidence"], "DATE_ONLY_NEXT_UTC_DAY_RESEARCH_CUTOFF")

    def test_monthly_selected_index_not_headline_quarterly(self) -> None:
        r = self.inspect()
        self.assertFalse(r["monthly_cpi_in_2026"])
        self.assertEqual(r["metric"], "ALL_GROUPS_CPI_ANNUAL_PCT_QUARTERLY")
        self.assertTrue(r["monthly_selected_price_indexes_not_headline_cpi"])
        self.assertEqual(r["monthly_headline_cpi_announced_from_year"], 2027)

    def test_original_assets_and_vintages_not_attested(self) -> None:
        r = self.inspect()
        self.assertFalse(r["original_issue_vintage_attested"])
        self.assertFalse(r["historical_backtest_approved"])
        for row in r["records"].values():
            self.assertFalse(row["historical_original_issue_vintage_attested"])
            self.assertFalse(row["downloaded_original_release_assets_attested"])

    def test_wrong_horizon_or_naive_clock_blocks(self) -> None:
        for clock, tf in (
            (datetime(2026, 11, 8), "D1"),
            (at("2026-11-08T12:00:00Z"), "M15"),
            (at("2026-11-08T12:00:00Z").replace(microsecond=1), "D1"),
        ):
            with self.subTest(clock=clock, tf=tf):
                r = inspect_nzd_cpi_quarter_release_catalog_lab(
                    decision_at_utc=clock, horizon=tf)
                self.assertEqual(r["state"], "LAB_NZD_CPI_QUARTER_RESEARCH_BLOCKED")

    def test_timezoneless_source_floor_blocks_without_host_inference(self) -> None:
        with patch.dict(RELEASES[2], {"availability_floor_utc": "2026-07-20T22:45:00"}):
            self.assertEqual(self.inspect()["state"], "LAB_NZD_CPI_QUARTER_RESEARCH_BLOCKED")

    def test_duplicate_quarter_blocks_instead_of_overwriting(self) -> None:
        with patch.dict(RELEASES[2], {"period": "2026-Q1"}):
            self.assertEqual(self.inspect()["state"], "LAB_NZD_CPI_QUARTER_RESEARCH_BLOCKED")

    def test_aware_offset_normalized(self) -> None:
        a = self.inspect()
        b = inspect_nzd_cpi_quarter_release_catalog_lab(
            decision_at_utc=datetime(2026, 11, 8, 8, tzinfo=timezone(timedelta(hours=-4))),
            horizon="D1")
        self.assertEqual(a, b)

    def test_d1_w1_same_research_no_predictions(self) -> None:
        d = self.inspect(tf="D1")
        w = self.inspect(tf="W1")
        self.assertEqual(d["records"], w["records"])
        self.assertIsNone(d["forecast_probability"])
        self.assertIsNone(w["forecast_probability"])
        self.assertEqual(d["operational_bias"], "AGUARDAR")

    def test_no_worker_network_trades_or_cost(self) -> None:
        r = self.inspect()
        self.assertEqual(r["http_requests"], 0)
        self.assertEqual(r["new_cost_brl"], 0)
        self.assertFalse(r["trade_authorized"] or r["worker_enabled"] or r["scheduler_enabled"])


if __name__ == "__main__":
    unittest.main()
