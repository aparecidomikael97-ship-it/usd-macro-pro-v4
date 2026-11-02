"""Contract checks for a real BLS-document review, NOT an ALFRED vintage test."""
import json
import unittest
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

MANIFEST = (Path(__file__).resolve().parent / "docs" / "continuidade" /
            "TRADER_CPI_BLS_ALFRED_CASO_REAL_LAB_20261102.json")


def sample():
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


class RealBlsCpiDocumentCaseLabTests(unittest.TestCase):
    def test_manifest_has_explicit_partial_status(self):
        s = sample()
        self.assertEqual(s["schema"], "ATLASQUANT_TRADER_BLS_CPI_ALFRED_CASE_LAB_V1")
        self.assertIn("ALFRED_VINTAGES_UNVERIFIED", s["state"])

    def test_original_bls_document_and_release_id(self):
        original = sample()["sources"][0]
        self.assertEqual(original["provider"], "BLS")
        self.assertEqual(original["id"], "USDL-26-0042")
        self.assertEqual(original["reference_month"], "2025-12")
        self.assertEqual(original["cpi_u_nsa_index"], 324.054)

    def test_original_yoy_unadjusted_is_not_monthly_seasonally_adjusted(self):
        original = sample()["sources"][0]
        self.assertEqual(original["yoy_nsa_pct"], 2.7)
        self.assertEqual(original["mom_sa_pct"], 0.3)
        self.assertNotEqual(original["yoy_nsa_pct"], original["mom_sa_pct"])

    def test_second_bls_document_agrees_for_december_nsa_level_only(self):
        s = sample()
        self.assertEqual(s["sources"][1]["id"], "USDL-26-0186")
        self.assertEqual(s["sources"][1]["table1_dec2025_nsa_index"], 324.054)
        self.assertTrue(s["cross_release"]["match"])
        self.assertEqual(s["cross_release"]["delta_index_points"], 0)
        self.assertEqual(s["sources"][0]["cpi_u_nsa_index"],
                         s["sources"][1]["table1_dec2025_nsa_index"])

    def test_alfred_series_is_nonseasonal_and_not_confused_with_adjusted(self):
        a = sample()["alfred"]
        self.assertEqual(a["series"], "CPIAUCNS")
        self.assertEqual(a["reject_as_equivalent_series"], "CPIAUCSL")
        self.assertIn("CPIAUCNS", a["series_url"])
        self.assertTrue(a["metadata_seen"])

    def test_alfred_vintage_numbers_are_not_faked_from_bls(self):
        a = sample()["alfred"]
        self.assertEqual(a["requested_vintages"], ["2026-01-13", "2026-02-13"])
        self.assertIsNone(a["jan13_dec2025_value"])
        self.assertIsNone(a["feb13_dec2025_value"])
        self.assertFalse(a["vintage_csv_downloaded"])
        self.assertFalse(a["alfred_vintage_agreement_verified"])

    def test_original_and_next_release_urls_are_different_and_official(self):
        s = sample()["sources"]
        self.assertNotEqual(s[0]["url"], s[1]["url"])
        for doc in s:
            parsed = urlsplit(doc["url"])
            self.assertEqual(parsed.scheme, "https")
            self.assertEqual(parsed.hostname, "www.bls.gov")
            self.assertTrue(doc["document_read"])
            self.assertFalse(doc["original_bytes_archived"])
            self.assertIsNone(doc["sha256"])

    def test_official_embargo_is_later_than_candidate_cuiaba_cutoff(self):
        s = sample()["point_in_time"]
        issue = datetime.fromisoformat(s["tentative_research_at"])
        release = datetime.fromisoformat(s["scheduled_release_cuiaba"])
        self.assertLess(issue, release)
        self.assertEqual(release.hour, 9)
        self.assertEqual(release.minute, 30)
        self.assertTrue(s["forecast_before_release"])
        self.assertFalse(s["actual_available_at_research_cutoff"])

    def test_eastern_and_cuiaba_clocks_represent_same_release_instant(self):
        s = sample()["point_in_time"]
        eastern = datetime.fromisoformat(s["official_release_new_york"])
        cuiaba = datetime.fromisoformat(s["scheduled_release_cuiaba"])
        self.assertEqual(eastern, cuiaba)
        self.assertEqual(eastern.astimezone(ZoneInfo("America/Cuiaba")), cuiaba)

    def test_no_attested_historical_capture_from_schedule(self):
        s = sample()
        self.assertTrue(s["point_in_time"]["official_release_is_not_historical_receipt"])
        self.assertFalse(s["alfred"]["intraday_timestamp_proven"])
        self.assertFalse(s["blockers"]["exact_historical_receipt_verified"])

    def test_expected_consensus_and_raw_archive_are_absent(self):
        s = sample()
        self.assertFalse(s["blockers"]["consensus_event_pre_release_verified"])
        self.assertFalse(s["blockers"]["original_bytes_custodied"])
        self.assertFalse(s["blockers"]["fred_vintages_matched"])

    def test_no_market_or_commercial_reuse_claims(self):
        s = sample()
        self.assertFalse(s["alfred"]["commercial_redistribution_reviewed"])
        self.assertFalse(s["blockers"]["commercial_reuse_rights_verified"])
        self.assertFalse(s["blockers"]["independent_28_fx_quote_history_verified"])
        self.assertFalse(s["blockers"]["real_oos_results_validated"])

    def test_never_issues_trading_or_operational_authority(self):
        s = sample()
        for key in ("can_feed_live_bias", "can_feed_real_oos",
                    "market_direction_inferred", "trade_authorized",
                    "worker_enabled", "scheduler_enabled", "paid_api_activated",
                    "merge_or_deploy_authorized"):
            self.assertFalse(s[key], key)


if __name__ == "__main__":
    unittest.main()
