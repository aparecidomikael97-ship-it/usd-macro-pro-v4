"""Offline contract tests for public-source audit inventory (not source verification)."""
import json
import unittest
from pathlib import Path
from urllib.parse import urlsplit


AUDIT = (
    Path(__file__).resolve().parent
    / "docs" / "continuidade"
    / "TRADER_MACRO_SOURCE_AUDIT_LAB_20261102.json"
)


def catalog():
    return json.loads(AUDIT.read_text(encoding="utf-8"))


class MacroSourceAuditLabTests(unittest.TestCase):
    def test_manifest_is_present_and_valid_json(self):
        obj = catalog()
        self.assertEqual(obj["schema"], "ATLASQUANT_TRADER_MACRO_PRIMARY_SOURCES_AUDIT_LAB_V1")
        self.assertEqual(obj["state"], "PUBLIC_DOC_AUDIT_ONLY_NO_HISTORICAL_INGESTION")

    def test_all_eight_documentation_leads_present(self):
        obj = catalog()
        self.assertEqual(obj["count"], 8)
        self.assertEqual(len(obj["sources"]), 8)
        self.assertEqual(len({row["source_id"] for row in obj["sources"]}), 8)

    def test_only_usd_eur_audited_not_six_other_fx_economies(self):
        obj = catalog()
        self.assertEqual({row["currency"] for row in obj["sources"]}, {"USD", "EUR"})
        self.assertIn("NOT 28 FX quote coverage", obj["scope"])

    def test_official_http_urls_are_not_automatically_authorized(self):
        accepted_hosts = {"www.bls.gov", "alfred.stlouisfed.org",
                          "www.philadelphiafed.org", "www.bea.gov",
                          "ec.europa.eu", "www.ecb.europa.eu",
                          "www.newyorkfed.org"}
        for row in catalog()["sources"]:
            url = urlsplit(row["official_url"])
            self.assertEqual(url.scheme, "https")
            self.assertIn(url.hostname, accepted_hosts)
            self.assertTrue(row["public_documentation_located"])
            self.assertFalse(row["commercial_reuse_rights_verified"])
            self.assertFalse(row["can_feed_real_trader_bias"])
            self.assertFalse(row["can_feed_real_oos"])

    def test_no_actual_download_or_historical_receipt_claimed(self):
        obj = catalog()
        self.assertFalse(obj["data_downloaded"])
        self.assertFalse(obj["historical_release_consensus_available"])
        for row in obj["sources"]:
            self.assertFalse(row["historical_payload_downloaded"])
            self.assertFalse(row["intraday_captured_receipt_attested"])
            self.assertFalse(row["exact_release_prepublication_consensus_attested"])

    def test_alfred_date_level_not_intraday_utc_receipt(self):
        row = next(x for x in catalog()["sources"] if x["source_id"] == "US_ALFRED_VINTAGES")
        self.assertEqual(row["time_evidence_precision"], "DATE_LEVEL_VINTAGE")
        self.assertEqual(row["key_blocker"], "INTRADAY_AVAILABILITY_UNATTESTED")
        self.assertFalse(row["can_feed_real_oos"])

    def test_bls_schedule_not_actual_cpi_release(self):
        row = next(x for x in catalog()["sources"] if x["source_id"] == "US_BLS_RELEASE_SCHEDULE")
        self.assertEqual(row["research_role"], "RELEASE_SCHEDULE")
        self.assertEqual(row["key_blocker"], "NOT_ACTUAL_RESULT")

    def test_survey_forecasts_not_event_specific_cpi_consensus(self):
        ids = ("US_PHILLY_FED_SPF", "EUR_ECB_SPF")
        for row in catalog()["sources"]:
            if row["source_id"] in ids:
                self.assertEqual(row["key_blocker"], "NOT_EVENT_CONSENSUS")
                self.assertFalse(row["exact_release_prepublication_consensus_attested"])

    def test_ny_fed_meeting_survey_published_after_meeting(self):
        row = next(x for x in catalog()["sources"] if x["source_id"] == "US_NYFED_SME")
        self.assertEqual(row["key_blocker"], "RESULTS_NOT_AVAILABLE_BEFORE_MEETING")
        self.assertIn("3 semanas", row["verified_public_documentation_summary_pt"])

    def test_eurostat_flash_final_not_mislabeled_as_same_vintage(self):
        row = next(x for x in catalog()["sources"] if x["source_id"] == "EUR_EUROSTAT_HICP")
        self.assertEqual(row["research_role"], "FLASH_FINAL_AND_REVISIONS")
        self.assertFalse(row["real_historical_market_data_verified"])

    def test_bea_archive_not_marked_as_complete_fx_source(self):
        row = next(x for x in catalog()["sources"] if x["source_id"] == "US_BEAGDP_ARCHIVE")
        self.assertEqual(row["currency"], "USD")
        self.assertFalse(row["real_historical_market_data_verified"])

    def test_no_provider_has_been_promoted_from_document_review(self):
        for row in catalog()["sources"]:
            self.assertEqual(row["review_state"],
                             "OFFICIAL_DOCUMENTATION_REVIEWED_SOURCE_NOT_ADMITTED")

    def test_no_worker_scheduler_trade_or_real_backtest_authorized(self):
        obj = catalog()
        for flag in ("data_downloaded", "paid_api_activated",
                     "licensed_market_quotes_available",
                     "historical_release_consensus_available",
                     "real_oos_authorized", "worker_enabled",
                     "scheduler_enabled", "trade_authorized"):
            self.assertFalse(obj[flag], flag)


if __name__ == "__main__":
    unittest.main()
