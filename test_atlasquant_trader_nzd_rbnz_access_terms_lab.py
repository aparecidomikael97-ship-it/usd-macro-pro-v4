"""Current 12-Nov-2026 RBNZ terms and the prior 403 route restriction."""
from __future__ import annotations
import unittest
from atlasquant_trader_nzd_rbnz_access_terms_lab import (
    HIGHER_RATE_ACCESS_REQUEST_URL, B2_OCR_DATA_SOURCE_URL,
    DATA_FILE_INDEX_URL, OCR_MEDIA_RELEASE_XML_FEED_URL,
    MAX_REQUESTS_PER_HOUR, REQUIRED_USER_AGENT_PATTERN,
    RBNZ_BLOCK_REASON, TERMS_LAST_UPDATED, TERMS_URL,
    inspect_rbnz_automated_access_policy_lab as inspect,
)


class RbnzTermsSafetyTests(unittest.TestCase):
    def test_01_terms_now_permit_conditioned_ordinary_automation(self):
        r=inspect()
        self.assertEqual(
            r["state"],"LAB_RBNZ_PREVIOUS_403_ROUTE_ACCESS_SUSPENDED_NO_GO")
        self.assertEqual(r["reason"],RBNZ_BLOCK_REASON)
        self.assertTrue(r["issuer_ordinary_automation_permitted_under_conditions"])
        self.assertEqual(r["issuer_automation_hourly_request_limit"],120)
        self.assertEqual(r["issuer_required_user_agent_format"],
                         "RBNZ-Automated-Agent/<organisation>/<application>")
        self.assertFalse(r["issuer_written_approval_needed_for_ordinary_rate"])
        self.assertTrue(r["issuer_approval_required_for_higher_rate"])
        self.assertTrue(r["higher_rate_static_egress_ip_required"])

    def test_02_403_route_suspended_without_misquoting_terms(self):
        r=inspect()
        self.assertTrue(r["issuer_403_may_prohibit_this_route_even_below_quota"])
        self.assertTrue(r["prior_403_route_suspended_here"])
        self.assertFalse(r["automated_access_granted_to_specific_prior_403_route"])
        self.assertFalse(r["current_atlasquant_endpoint_access_allowed"])
        self.assertFalse(r["current_nzd_ocr_raw_source_persisted_on_am12"])

    def test_03_issuer_urls_and_latest_terms_date_exact(self):
        self.assertEqual(TERMS_LAST_UPDATED,"2026-11-12")
        self.assertEqual(TERMS_URL,
                         "https://www.rbnz.govt.nz/about-our-site/terms-of-use")
        self.assertEqual(HIGHER_RATE_ACCESS_REQUEST_URL,
                         TERMS_URL+"/allow-list-request")
        self.assertEqual(DATA_FILE_INDEX_URL,
                         "https://www.rbnz.govt.nz/statistics/series/data-file-index-page")
        self.assertEqual(B2_OCR_DATA_SOURCE_URL,
                         "https://rbnz.govt.nz/-/media/project/sites/rbnz/files/"
                         "statistics/series/b/b2/hb2-daily-close.xlsx")
        self.assertEqual(OCR_MEDIA_RELEASE_XML_FEED_URL,
                         "https://www.rbnz.govt.nz/feeds/news")
        self.assertEqual(MAX_REQUESTS_PER_HOUR,120)
        self.assertEqual(REQUIRED_USER_AGENT_PATTERN,
                         "RBNZ-Automated-Agent/<organisation>/<application>")

    def test_04_no_public_api_but_xml_feed_is_documented(self):
        r=inspect()
        self.assertTrue(r["issuer_xml_feed_for_ocr_releases_documented"])
        self.assertFalse(r["issuer_public_api_for_ocr_supported"])
        self.assertTrue(r["official_b2_contains_ocr_and_third_party_market_data"])
        self.assertTrue(r["public_web_search_value_is_not_reproducible_source_receipt"])

    def test_05_block_trading_accuracy_and_source_claims(self):
        r=inspect()
        self.assertEqual(r["operational_bias"],"AGUARDAR")
        self.assertFalse(r["pre_event_consensus_or_signed_effect_validated"])
        for k in ("trade_authorized","publishable","live_alert_allowed"):
            self.assertFalse(r[k])
        self.assertEqual((r["http_requests"],r["file_writes"],
                          r["new_cost_brl"]),(0,0,0))


if __name__=="__main__":
    unittest.main()
