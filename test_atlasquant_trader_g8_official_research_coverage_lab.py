"""Deterministic offline tests for the G8 source-research inventory."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import unittest

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS
from atlasquant_trader_g8_official_research_coverage_lab import (
    inspect_g8_official_research_coverage_lab,
)


def at(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


class G8OfficialResearchCoverageTests(unittest.TestCase):
    def audit(self, time: str = "2026-11-08T10:00:00Z", tf: str = "D1") -> dict:
        return inspect_g8_official_research_coverage_lab(decision_at_utc=at(time), horizon=tf)

    def test_canonical_28_pairs_and_8_currencies(self) -> None:
        report = self.audit()
        self.assertEqual(report["currency_count"], 8)
        self.assertEqual(report["pair_count"], 28)
        self.assertEqual(set(report["pairs"]), set(OFFICIAL_PAIRS))
        self.assertEqual(set(report["currencies"]), set(CURRENCIES))

    def test_six_currencies_have_two_family_research_today(self) -> None:
        report = self.audit()
        documented = {c for c, x in report["currencies"].items() if x["two_family_publisher_research"]}
        self.assertEqual(documented, {"USD", "EUR", "GBP", "NZD", "AUD", "CAD"})

    def test_bilateral_research_counts_fifteen_twelve_one(self) -> None:
        report = self.audit()
        self.assertEqual((report["two_sided_research_pairs"], report["one_sided_research_pairs"],
                          report["zero_sided_research_pairs"]), (15, 12, 1))

    def test_every_pair_is_only_inventory_never_a_trade(self) -> None:
        report = self.audit()
        for key, row in report["pairs"].items():
            with self.subTest(pair=key):
                self.assertFalse(row["historical_pit_verified"])
                self.assertFalse(row["backtest_approved"])
                self.assertEqual(row["operational_bias"], "AGUARDAR")

    def test_usd_eur_pair_is_bilateral_research_only(self) -> None:
        report = self.audit()
        found = [r for r in report["pairs"].values() if {r["base"], r["quote"]} == {"USD", "EUR"}]
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["coverage"], "TWO_SIDED_RESEARCH_ONLY")

    def test_missing_currencies_are_explicit(self) -> None:
        report = self.audit()
        for c in ("CHF", "JPY"):
            self.assertEqual(report["currencies"][c]["missing_families"], ["INFLATION", "POLICY"])

    def test_both_inflation_vintages_stay_individually_named(self) -> None:
        report = self.audit()
        keys = report["currencies"]["EUR"]["family_research_keys"]["INFLATION"]
        self.assertEqual(keys, ["EUR_HICP_2026_09_FINAL", "EUR_HICP_2026_10_FLASH"])

    def test_us_fed_range_is_counted_without_synthesizing_single_rate(self) -> None:
        report = self.audit()
        self.assertIn("USD_FED_TARGET_2026_10",
                      report["currencies"]["USD"]["family_research_keys"]["POLICY"])
        self.assertNotIn("value_percent", report["currencies"]["USD"])

    def test_empty_research_before_first_release(self) -> None:
        report = self.audit("2026-10-01T00:00:00Z")
        self.assertEqual((report["two_sided_research_pairs"], report["one_sided_research_pairs"],
                          report["zero_sided_research_pairs"]), (0, 0, 28))

    def test_one_second_before_last_eur_flash_keeps_final(self) -> None:
        before = self.audit("2026-11-04T23:59:59Z")
        after = self.audit("2026-11-05T00:00:00Z")
        self.assertEqual(before["currencies"]["EUR"]["family_research_keys"]["INFLATION"],
                         ["EUR_HICP_2026_09_FINAL"])
        self.assertEqual(len(after["currencies"]["EUR"]["family_research_keys"]["INFLATION"]), 2)

    def test_research_output_never_claims_pit_or_probability(self) -> None:
        report = self.audit()
        self.assertFalse(report["original_point_in_time_vintage_attested"])
        self.assertFalse(report["issuer_values_independently_authenticated"])
        self.assertFalse(report["historical_backtest_approved"])
        self.assertFalse(report["cross_currency_strength_comparison_approved"])
        self.assertIsNone(report["validated_directional_accuracy"])
        self.assertIsNone(report["forecast_probability"])

    def test_d1_and_w1_same_research_not_same_bias(self) -> None:
        d = self.audit(tf="D1")
        w = self.audit(tf="W1")
        self.assertEqual(d["pairs"], w["pairs"])
        self.assertEqual({d["horizon"], w["horizon"]}, {"D1", "W1"})
        self.assertFalse(d["historical_backtest_approved"] or w["historical_backtest_approved"])

    def test_bad_horizon_is_fail_closed(self) -> None:
        report = self.audit(tf="M15")
        self.assertEqual(report["state"], "LAB_RESEARCH_COVERAGE_BLOCKED")
        self.assertFalse(report["trade_authorized"])

    def test_naive_datetime_is_fail_closed(self) -> None:
        result = inspect_g8_official_research_coverage_lab(
            decision_at_utc=datetime(2026, 11, 8), horizon="D1")
        self.assertEqual(result["state"], "LAB_RESEARCH_COVERAGE_BLOCKED")

    def test_non_utc_timezone_is_normalized(self) -> None:
        a = self.audit("2026-11-08T10:00:00Z")
        b = inspect_g8_official_research_coverage_lab(
            decision_at_utc=datetime(2026, 11, 8, 6, tzinfo=timezone(timedelta(hours=-4))), horizon="D1")
        self.assertEqual(a, b)

    def test_microseconds_are_fail_closed(self) -> None:
        result = inspect_g8_official_research_coverage_lab(
            decision_at_utc=at("2026-11-08T10:00:00Z").replace(microsecond=1), horizon="D1")
        self.assertEqual(result["state"], "LAB_RESEARCH_COVERAGE_BLOCKED")

    def test_no_network_or_scheduler_actions(self) -> None:
        report = self.audit()
        self.assertEqual(report["http_requests"], 0)
        self.assertEqual(report["new_cost_brl"], 0)
        self.assertFalse(report["worker_enabled"] or report["scheduler_enabled"])


if __name__ == "__main__":
    unittest.main()
