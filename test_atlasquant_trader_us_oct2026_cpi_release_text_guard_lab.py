"""Synthetic HTML fragment fixtures; no actual BLS HTML bytes in tests."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import unittest

from atlasquant_trader_us_oct2026_cpi_release_text_guard_lab import (
    ClaimedBLSHtmlReceipt, URL, RELEASE_FLOOR_UTC,
    inspect_bls_oct2026_release_text_lab as inspect,
)

UTC = timezone.utc
AFTER = datetime(2026, 11, 10, 22, 0, tzinfo=UTC)
CAP = datetime(2026, 11, 10, 20, 0, tzinfo=UTC)


def raw(head="0.4", core="0.3", *, past="BLS did not collect survey data for October 2025", 
        missing="BLS cannot publish 12-month percent changes for October 2026"):
    return ("<html><body><h1>CONSUMER PRICE INDEX - OCTOBER 2026</h1>"
            "USDL-26-1685 8:30 a.m. (ET) Tuesday, November 10, 2026 "
            "The Consumer Price Index for All Urban Consumers (CPI-U) increased "
            + head + " percent on a seasonally adjusted basis in October "
            "The index for all items less food and energy rose " + core + 
            " percent in October, as it did in September and August. "
            + past + ". As a result, " + missing + ".</body></html>").encode()


def receipt(data):
    return ClaimedBLSHtmlReceipt(URL, 200, "text/html", CAP, sha256(data).hexdigest())


class OctBLSReleaseTextGateTests(unittest.TestCase):
    def case(self, data=None, rec=None, when=AFTER):
        body = raw() if data is None else data
        return inspect(raw_html=body, receipt=receipt(body) if rec is None else rec, as_of_utc=when)

    def safe(self, out):
        self.assertEqual(out["operational_bias"], "AGUARDAR")
        self.assertIsNone(out["fx_bias"])
        self.assertIsNone(out["score_0_to_10"])
        self.assertIsNone(out["headline_oct2026_nsa_yoy_pct"])
        self.assertIsNone(out["core_oct2026_nsa_yoy_pct"])
        self.assertIsNone(out["verified_surprise_percent"])
        for k in ("publisher_original_bytes_independently_attested",
                  "first_release_publication_timestamp_verified",
                  "capture_clock_independently_attested", "point_in_time_archive_eligible",
                  "pre_release_consensus_authenticated", "trade_authorized",
                  "publishable", "worker_enabled", "scheduler_enabled"):
            self.assertFalse(out[k], k)
        self.assertEqual((out["http_requests"], out["file_writes"], out["new_cost_brl"]), (0,0,0))

    def test_exact_monthly_headline_core_but_no_yoy_or_signal(self):
        x=self.case()
        self.assertEqual(x["state"], "LAB_BLS_HTML_MONTHLY_CONTEXT_UNATTESTED")
        self.assertEqual((x["headline_oct2026_sa_mom_pct_body_claim"], x["core_oct2026_sa_mom_pct_body_claim"]), ("0.4","0.3"))
        self.assertTrue(x["headline_yoy_reported_missing_oct2025_baseline"])
        self.assertEqual(x["usd_pair_count"], 7)
        self.assertIn("EUR/USD", x["usd_exposed_pairs"])
        self.assertNotIn("EUR/GBP", x["usd_exposed_pairs"])
        self.assertTrue(x["body_sha256_self_consistent"])
        self.safe(x)

    def test_before_nov10_first_release_blocks_even_perfect_fake_html(self):
        x=self.case(when=RELEASE_FLOOR_UTC-timedelta(seconds=1))
        self.assertEqual(x["state"], "LAB_NOT_YET_RELEASED")
        self.safe(x)

    def test_no_earlier_capture_or_future_capture(self):
        body=raw()
        for t in (RELEASE_FLOOR_UTC-timedelta(seconds=1),AFTER+timedelta(seconds=1)):
            with self.subTest(t=t):
                x=self.case(data=body,rec=replace(receipt(body),captured_at_utc=t))
                self.assertEqual(x["state"], "LAB_INVALID_INPUT")
                self.safe(x)

    def test_raw_body_sha_mismatch(self):
        d=raw()
        x=self.case(data=d+b" ",rec=receipt(d))
        self.assertEqual(x["state"], "LAB_INVALID_INPUT")
        self.safe(x)

    def test_wrong_url_type_mime_status(self):
        d=raw()
        for mutation in ({"source_url":"https://fake.example/cpi.htm"},
                         {"http_status":True}, {"http_status":404},
                         {"content_type":"application/json"}, {"content_type":None}):
            with self.subTest(mutation=mutation):
                x=self.case(data=d,rec=replace(receipt(d),**mutation))
                self.assertEqual(x["state"], "LAB_INVALID_INPUT")
                self.safe(x)

    def test_missing_official_no_yoy_text_is_not_overridden_by_good_monthly(self):
        for d in (raw(past="No old data"),raw(missing="YoY 4%")):
            x=self.case(data=d)
            self.assertEqual(x["state"], "LAB_SOURCE_TEXT_INSUFFICIENT")
            self.safe(x)

    def test_no_conflicting_two_headline_values(self):
        d=raw()
        d=d.replace(b"</body>", b" The Consumer Price Index for All Urban Consumers (CPI-U) increased 9.9 percent on a seasonally adjusted basis in October</body>")
        x=self.case(data=d)
        self.assertEqual(x["state"], "LAB_SOURCE_TEXT_INSUFFICIENT")
        self.safe(x)

    def test_no_false_monthly_metric_if_text_only_in_script(self):
        d=raw()
        d=d.replace(b"The index for all items less food and energy rose 0.3 percent in October", b"<script>The index for all items less food and energy rose 0.3 percent in October</script>")
        x=self.case(data=d)
        self.assertEqual(x["state"], "LAB_SOURCE_TEXT_INSUFFICIENT")
        self.safe(x)

    def test_wrong_release_id(self):
        x=self.case(data=raw().replace(b"USDL-26-1685",b"USDL-27-2222"))
        self.assertEqual(x["state"], "LAB_SOURCE_TEXT_INSUFFICIENT")
        self.safe(x)

    def test_data_claims_can_be_spoofed_and_are_not_authentication(self):
        x=self.case(data=raw(head="0.9",core="0.8"))
        self.assertEqual(x["state"], "LAB_BLS_HTML_MONTHLY_CONTEXT_UNATTESTED")
        self.assertEqual(x["headline_oct2026_sa_mom_pct_body_claim"], "0.9")
        self.assertFalse(x["publisher_original_bytes_independently_attested"])
        self.safe(x)

    def test_nonnumeric_or_outlier_claim(self):
        for head in ("nan", "16.9", "1,000"):
            with self.subTest(head=head):
                x=self.case(data=raw(head=head))
                self.assertEqual(x["state"], "LAB_SOURCE_TEXT_INSUFFICIENT")
                self.safe(x)

    def test_invalid_cutoff(self):
        for when in (None,"2026-11-10",AFTER.replace(tzinfo=None)):
            x=self.case(when=when)
            self.assertEqual(x["state"], "LAB_INVALID_INPUT")
            self.safe(x)

    def test_extra_html_has_no_fake_gap_or_label(self):
        d=raw().replace(b"BLS did not collect survey data for October 2025", b"BLS did not collect survey data for October 2024")
        x=self.case(data=d)
        self.assertEqual(x["state"],"LAB_SOURCE_TEXT_INSUFFICIENT")
        self.safe(x)


    def test_browser_saved_html_over_one_megabyte_and_six_bad_bytes(self):
        d = raw().replace(b"</body>", b"<div>" + b"x"*(1024*1024 + 100)
                          + b"\x9d"*6 + b"</div></body>")
        x = self.case(data=d)
        self.assertEqual(x["state"], "LAB_BLS_HTML_MONTHLY_CONTEXT_UNATTESTED")
        self.assertEqual(x["non_utf8_source_byte_count"], 6)
        self.assertEqual(x["headline_oct2026_sa_mom_pct_body_claim"], "0.4")
        self.assertEqual(x["core_oct2026_sa_mom_pct_body_claim"], "0.3")
        self.safe(x)

    def test_excess_bad_bytes_fails_closed(self):
        d = raw().replace(b"</body>", b"\x9d"*17 + b"</body>")
        x = self.case(data=d)
        self.assertEqual(x["reason"], "EXCESS_NON_UTF8_SOURCE_BYTES")
        self.safe(x)

    def test_more_than_two_megabytes_rejected(self):
        d = raw().replace(b"</body>", b"x"*(2*1024*1024) + b"</body>")
        x = self.case(data=d)
        self.assertEqual(x["reason"], "RAW_BODY_SIZE_OR_SHA256_CLAIM_MISMATCH")
        self.safe(x)

    def test_duplicate_core_equal_summary_and_details_allowed(self):
        d = raw().replace(b"</body>",
            b" The index for all items less food and energy rose 0.3 percent in October</body>")
        x = self.case(data=d)
        self.assertEqual(x["state"], "LAB_BLS_HTML_MONTHLY_CONTEXT_UNATTESTED")
        self.assertEqual(x["core_oct2026_sa_mom_pct_body_claim"], "0.3")
        self.safe(x)

    def test_duplicate_core_conflict_blocked(self):
        d = raw().replace(b"</body>",
            b" The index for all items less food and energy rose 0.8 percent in October</body>")
        x = self.case(data=d)
        self.assertEqual(x["reason"], "EXACT_HEADLINE_OR_CORE_MOM_CLAIM_NOT_EXTRACTED")
        self.safe(x)

if __name__ == "__main__":
    unittest.main()