"""Offline unit tests for AUD/CAD research-only publication chronology."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import unittest

from atlasquant_trader_aud_cad_official_pilot_lab import (
    OFFICIAL_OBSERVATIONS, inspect_aud_cad_official_pilot_lab,
)


def at(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


class AudCadOfficialPilotTests(unittest.TestCase):
    def audit(self, text: str) -> dict:
        return inspect_aud_cad_official_pilot_lab(decision_at_utc=at(text))

    def test_four_research_documents_two_currency_two_families(self) -> None:
        self.assertEqual(len(OFFICIAL_OBSERVATIONS), 4)
        self.assertEqual({(row["currency"], row["family"]) for row in OFFICIAL_OBSERVATIONS.values()}, {
            ("AUD", "INFLATION"), ("CAD", "INFLATION"), ("AUD", "POLICY"), ("CAD", "POLICY")})

    def test_only_official_https_document_hosts(self) -> None:
        expected = ("www.abs.gov.au", "www150.statcan.gc.ca", "www.rba.gov.au", "www.bankofcanada.ca")
        for row in OFFICIAL_OBSERVATIONS.values():
            self.assertTrue(any(row["document_url"].startswith("https://" + h + "/") for h in expected))

    def test_abs_1130_aedt_is_0030_utc(self) -> None:
        row = OFFICIAL_OBSERVATIONS["AUD_CPI_2026_09"]
        self.assertEqual(row["availability_floor_utc"], "2026-10-28T00:30:00Z")
        self.assertEqual(row["time_evidence"], "EXACT_ON_ABS_RELEASE_PAGE")

    def test_canadian_cpi_date_only_next_day(self) -> None:
        row = OFFICIAL_OBSERVATIONS["CAD_CPI_2026_09"]
        self.assertEqual(row["availability_floor_utc"], "2026-10-20T00:00:00Z")
        self.assertIn("DATE_ONLY", row["time_evidence"])

    def test_cad_boc_rate_is_overnight_target_not_bank_rate(self) -> None:
        row = OFFICIAL_OBSERVATIONS["CAD_BOC_OVERNIGHT_TARGET_2026_10"]
        self.assertEqual((row["metric"], row["value_percent"]), ("BOC_OVERNIGHT_RATE_TARGET_PCT", "2.50"))

    def test_aud_rate_announcement_and_effective_date_separate(self) -> None:
        row = OFFICIAL_OBSERVATIONS["AUD_RBA_CASH_TARGET_2026_11"]
        self.assertEqual(row["published_date"], "2026-11-03")
        self.assertEqual(row["effective_date"], "2026-11-04")
        self.assertEqual(row["availability_floor_utc"], "2026-11-04T00:00:00Z")
        self.assertIn("GENERAL_14_30_AEDT_POLICY_NOT_RELEASE_PROOF", row["time_evidence"])

    def test_one_second_before_every_boundary_values_hidden(self) -> None:
        for key, row in OFFICIAL_OBSERVATIONS.items():
            with self.subTest(key=key):
                stamp = at(row["availability_floor_utc"]) - timedelta(seconds=1)
                r = inspect_aud_cad_official_pilot_lab(decision_at_utc=stamp)["observations"][key]
                self.assertIsNone(r["research_value_percent"])
                self.assertEqual(r["publisher_timing_status"], "NOT_YET_PUBLIC_BY_BOUNDARY")

    def test_at_boundary_research_only_no_backtest(self) -> None:
        for key, row in OFFICIAL_OBSERVATIONS.items():
            with self.subTest(key=key):
                r = inspect_aud_cad_official_pilot_lab(
                    decision_at_utc=at(row["availability_floor_utc"]))["observations"][key]
                self.assertEqual(r["research_value_percent"], row["value_percent"])
                self.assertFalse(r["independent_historical_capture_attested"])
                self.assertFalse(r["eligible_for_exante_backtest"])

    def test_no_premature_rba_target_on_announcement_day(self) -> None:
        r = self.audit("2026-11-03T23:59:59Z")
        self.assertIsNone(r["observations"]["AUD_RBA_CASH_TARGET_2026_11"]["research_value_percent"])

    def test_old_research_day_hides_all_data(self) -> None:
        r = self.audit("2026-10-01T00:00:00Z")
        self.assertEqual(r["publisher_boundary_passed_count"], 0)

    def test_after_all_still_abstain(self) -> None:
        r = self.audit("2026-11-08T08:00:00Z")
        self.assertEqual(r["publisher_boundary_passed_count"], 4)
        self.assertFalse(r["historical_capture_attested"])
        self.assertFalse(r["point_in_time_backtest_approved"])
        self.assertFalse(r["macro_cross_currency_comparison_approved"])
        self.assertEqual(r["operational_bias"], "AGUARDAR")
        self.assertIsNone(r["forecast_probability"])
        self.assertFalse(r["trade_authorized"])

    def test_timezone_offset_normalized(self) -> None:
        a = self.audit("2026-11-04T00:00:00Z")
        b = inspect_aud_cad_official_pilot_lab(decision_at_utc=datetime(
            2026, 11, 3, 20, tzinfo=timezone(timedelta(hours=-4))))
        self.assertEqual(a, b)

    def test_naive_time_refused(self) -> None:
        with self.assertRaises(ValueError):
            inspect_aud_cad_official_pilot_lab(decision_at_utc=datetime(2026, 11, 8))

    def test_microseconds_refused(self) -> None:
        with self.assertRaises(ValueError):
            inspect_aud_cad_official_pilot_lab(decision_at_utc=at("2026-11-08T08:00:00Z").replace(microsecond=1))


if __name__ == "__main__":
    unittest.main()
