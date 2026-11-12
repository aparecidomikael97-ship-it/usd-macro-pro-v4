"""Offline test suite for USD/EUR official-publication research, NOT backtests."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import unittest

from atlasquant_trader_usd_eur_official_pilot_lab import (
    OFFICIAL_OBSERVATIONS, inspect_usd_eur_official_pilot_lab,
)


def at(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


class OfficialUsdEurPilotTests(unittest.TestCase):
    def test_research_covers_two_currencies_and_two_families(self) -> None:
        self.assertEqual(len(OFFICIAL_OBSERVATIONS), 5)
        self.assertEqual({(o["currency"], o["family"]) for o in OFFICIAL_OBSERVATIONS.values()}, {
            ("USD", "INFLATION"), ("USD", "POLICY"), ("EUR", "INFLATION"), ("EUR", "POLICY")})

    def test_each_document_is_specific_official_https(self) -> None:
        permitted = ("www.bls.gov", "www.federalreserve.gov", "ec.europa.eu", "www.ecb.europa.eu")
        for o in OFFICIAL_OBSERVATIONS.values():
            with self.subTest(o=o["metric"]):
                self.assertTrue(any(o["document_url"].startswith("https://" + d + "/") for d in permitted))

    def test_cpi_and_hicp_are_distinct_definitions(self) -> None:
        self.assertNotEqual(OFFICIAL_OBSERVATIONS["USD_CPI_2026_09_FINAL"]["metric"],
                            OFFICIAL_OBSERVATIONS["EUR_HICP_2026_09_FINAL"]["metric"])

    def test_euro_final_and_flash_never_conflated(self) -> None:
        final = OFFICIAL_OBSERVATIONS["EUR_HICP_2026_09_FINAL"]
        flash = OFFICIAL_OBSERVATIONS["EUR_HICP_2026_10_FLASH"]
        self.assertEqual(final["stage"], "FINAL_RELEASE")
        self.assertEqual(flash["stage"], "FLASH_PRELIMINARY")
        self.assertNotEqual(final["observation_period"], flash["observation_period"])

    def test_fed_range_not_collapsed_or_equated_with_ecb_rate(self) -> None:
        us = OFFICIAL_OBSERVATIONS["USD_FED_TARGET_2026_10"]
        eu = OFFICIAL_OBSERVATIONS["EUR_ECB_DEPOSIT_RATE_2026_10"]
        self.assertEqual((us["rate_shape"], us["range_lower_percent"], us["range_upper_percent"]),
                         ("RANGE", "3.75", "4.00"))
        self.assertIsNone(us["value_percent"])
        self.assertEqual((eu["rate_shape"], eu["value_percent"]), ("POINT", "2.50"))
        self.assertNotEqual(us["metric"], eu["metric"])

    def test_no_future_number_even_one_second_before_each_release(self) -> None:
        for key, o in OFFICIAL_OBSERVATIONS.items():
            with self.subTest(key=key):
                result = inspect_usd_eur_official_pilot_lab(
                    decision_at_utc=at(o["availability_floor_utc"]) - timedelta(seconds=1))
                record = result["observations"][key]
                self.assertEqual(record["publisher_timing_status"], "NOT_YET_PUBLIC_BY_BOUNDARY")
                self.assertIsNone(record["research_value_percent"])
                self.assertIsNone(record["research_range_lower_percent"])
                self.assertIsNone(record["research_range_upper_percent"])

    def test_after_publisher_floor_still_not_backtest_authorized(self) -> None:
        for key, o in OFFICIAL_OBSERVATIONS.items():
            with self.subTest(key=key):
                result = inspect_usd_eur_official_pilot_lab(decision_at_utc=at(o["availability_floor_utc"]))
                record = result["observations"][key]
                self.assertEqual(record["publisher_timing_status"],
                                 "AFTER_CONSERVATIVE_PUBLISHER_BOUNDARY_ONLY")
                self.assertEqual(record["research_value_percent"], o["value_percent"])
                self.assertFalse(record["revisions_excluded"])
                self.assertFalse(record["eligible_for_exante_backtest"])

    def test_us_release_cutoffs_are_exact_ed_t(self) -> None:
        self.assertEqual(OFFICIAL_OBSERVATIONS["USD_CPI_2026_09_FINAL"]["availability_floor_utc"],
                         "2026-10-14T12:30:00Z")
        self.assertEqual(OFFICIAL_OBSERVATIONS["USD_FED_TARGET_2026_10"]["availability_floor_utc"],
                         "2026-10-28T18:00:00Z")

    def test_eu_research_date_only_uses_next_day_boundary(self) -> None:
        for key in ("EUR_HICP_2026_09_FINAL", "EUR_ECB_DEPOSIT_RATE_2026_10", "EUR_HICP_2026_10_FLASH"):
            o = OFFICIAL_OBSERVATIONS[key]
            self.assertIn("DATE_ONLY_CONSERVATIVE", o["time_evidence"])
            self.assertEqual(at(o["availability_floor_utc"]).date(),
                             datetime.fromisoformat(o["published_date"]).date() + timedelta(days=1))

    def test_flash_unavailable_on_its_publication_day_under_safe_floor(self) -> None:
        result = inspect_usd_eur_official_pilot_lab(decision_at_utc=at("2026-11-04T23:59:59Z"))
        self.assertIsNone(result["observations"]["EUR_HICP_2026_10_FLASH"]["research_value_percent"])
        self.assertEqual(result["publisher_boundary_passed_count"], 4)

    def test_pre_publication_all_hidden(self) -> None:
        result = inspect_usd_eur_official_pilot_lab(decision_at_utc=at("2026-10-01T00:00:00Z"))
        self.assertEqual(result["publisher_boundary_passed_count"], 0)
        self.assertTrue(all(row["research_value_percent"] is None for row in result["observations"].values()))

    def test_all_visible_is_still_abstention(self) -> None:
        result = inspect_usd_eur_official_pilot_lab(decision_at_utc=at("2026-11-08T10:00:00Z"))
        self.assertEqual(result["publisher_boundary_passed_count"], 5)
        self.assertFalse(result["historical_capture_attested"])
        self.assertFalse(result["point_in_time_backtest_approved"])
        self.assertFalse(result["macro_cross_currency_comparison_approved"])
        self.assertEqual(result["operational_bias"], "AGUARDAR")
        self.assertIsNone(result["forecast_probability"])
        self.assertFalse(result["trade_authorized"])

    def test_aware_timezone_offset_same_result(self) -> None:
        utc = inspect_usd_eur_official_pilot_lab(decision_at_utc=at("2026-11-05T00:00:00Z"))
        minus_four = inspect_usd_eur_official_pilot_lab(decision_at_utc=datetime(
            2026, 11, 4, 20, 0, tzinfo=timezone(timedelta(hours=-4))))
        self.assertEqual(utc, minus_four)

    def test_naive_datetime_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            inspect_usd_eur_official_pilot_lab(decision_at_utc=datetime(2026, 11, 8))

    def test_microseconds_are_refused(self) -> None:
        with self.assertRaises(ValueError):
            inspect_usd_eur_official_pilot_lab(decision_at_utc=at("2026-11-08T10:00:00Z").replace(microsecond=1))


if __name__ == "__main__":
    unittest.main()
