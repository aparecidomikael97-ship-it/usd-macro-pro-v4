"""RBNZ website automation permission policy: never treat public data as a license."""
from __future__ import annotations
import unittest
from atlasquant_trader_nzd_rbnz_access_terms_lab import (
    ALLOW_LIST_REQUEST_URL, B2_OCR_DATA_SOURCE_URL,
    DATA_FILE_INDEX_URL, RBNZ_AUTOMATED_ACCESS_WRITTEN_PERMISSION_VERIFIED,
    RBNZ_BLOCK_REASON, TERMS_LAST_UPDATED, TERMS_URL,
    inspect_rbnz_automated_access_policy_lab as inspect,
)


class RbnzTermsSafetyTests(unittest.TestCase):
    def test_01_genuine_permission_not_verified_no_auto_access(self):
        self.assertFalse(RBNZ_AUTOMATED_ACCESS_WRITTEN_PERMISSION_VERIFIED)
        r=inspect()
        self.assertEqual(
            r["state"],"LAB_RBNZ_AUTOMATED_ACCESS_TERMS_GATE_BLOCKED_NO_GO")
        self.assertEqual(r["reason"],RBNZ_BLOCK_REASON)
        self.assertFalse(r["automated_collection_permission_verified"])
        self.assertFalse(r["automatic_rbnz_collection_allowed"])
        self.assertTrue(r["bot_quota_does_not_grant_permission"])
        self.assertTrue(r["issuer_html_403_seen_in_prior_cloud_run"])
        self.assertFalse(r["current_nzd_ocr_raw_source_persisted_on_am12"])

    def test_02_issuer_urls_and_date_are_exact(self):
        self.assertEqual(TERMS_LAST_UPDATED,"2025-07-11")
        self.assertEqual(TERMS_URL,
                         "https://www.rbnz.govt.nz/about-our-site/terms-of-use")
        self.assertEqual(ALLOW_LIST_REQUEST_URL,TERMS_URL+"/allow-list-request")
        self.assertEqual(DATA_FILE_INDEX_URL,
                         "https://www.rbnz.govt.nz/statistics/series/data-file-index-page")
        self.assertEqual(
            B2_OCR_DATA_SOURCE_URL,
            "https://rbnz.govt.nz/-/media/project/sites/rbnz/files/"
            "statistics/series/b/b2/hb2-daily-close.xlsx")
        r=inspect()
        self.assertTrue(r["official_b2_contains_ocr_and_third_party_market_data"])
        self.assertTrue(r["public_web_search_value_is_not_reproducible_source_receipt"])

    def test_03_block_trade_accuracy_and_source_claims(self):
        r=inspect()
        self.assertEqual(r["operational_bias"],"AGUARDAR")
        self.assertFalse(r["pre_event_consensus_or_signed_effect_validated"])
        for k in ("trade_authorized","publishable","live_alert_allowed"):
            self.assertFalse(r[k])
        self.assertEqual((r["http_requests"],r["file_writes"],
                          r["new_cost_brl"]),(0,0,0))


if __name__=="__main__":
    unittest.main()
