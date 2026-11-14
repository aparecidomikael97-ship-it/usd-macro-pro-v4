"""Synthetic BoJ site structure triage, no external requests."""
from __future__ import annotations

from datetime import datetime, timezone
from urllib.error import HTTPError
import unittest
from unittest.mock import patch

from test_atlasquant_trader_jpy_boj_guideline_source_receipt_lab import (
    homepage, receipt,
)
from atlasquant_trader_jpy_boj_home_structure_probe_lab import (
    SCHEMA, inspect_boj_home_structure_lab as inspect,
    collect_boj_structure_once_lab as collect, main,
)
from atlasquant_trader_jpy_boj_guideline_source_receipt_lab import (
    inspect_boj_home_guideline_receipt_lab as strict,
)

NOW=datetime(2026,11,13,10,11,tzinfo=timezone.utc)


class BoJHtmlTriageTests(unittest.TestCase):
    def safe(self,r):
        self.assertEqual(r["schema"],SCHEMA)
        self.assertEqual(r["operational_bias"],"AGUARDAR")
        for k in ("trade_authorized","publishable","worker_enabled",
                  "scheduler_enabled","validated_policy_original_retained",
                  "issuer_first_seen_authenticated"):
            self.assertFalse(r[k],k)
        self.assertIsNone(r["economic_policy_expected_rate_or_macro_bias"])
        self.assertIsNone(r["calibrated_probability"])
        self.assertEqual(r["file_writes"],0)
        self.assertEqual(r["new_cost_brl"],0)

    def test_01_no_flag_no_collector_called(self):
        calls=[]
        def never():
            calls.append(1)
            raise AssertionError("must not GET")
        r=collect(explicit_probe=False,collector=never,clock=lambda:NOW)
        self.safe(r)
        self.assertEqual(r["official_https_get_attempts"],0)
        self.assertEqual(calls,[])

    def test_02_valid_one_section_has_three_real_measures(self):
        raw=homepage()
        r=inspect(original_html=raw,receipt=receipt(raw),decision_at_utc=NOW)
        self.safe(r)
        self.assertEqual(r["state"],"LAB_BOJ_HTML_STRUCTURE_COUNTED_NO_GO")
        self.assertEqual(r["market_heading_occurrences"],1)
        self.assertEqual(r["last_market_section_policy_occurrences"],1)
        self.assertEqual(r["last_market_section_deposit_occurrences"],1)
        self.assertEqual(r["last_market_section_loan_occurrences"],1)
        self.assertEqual(r["earlier_market_sections_with_three_distinct_measures"],1)
        self.assertEqual(r["strict_validator_state"],
                         "LAB_JPY_BOJ_CURRENT_GUIDELINE_HTML_LOCALLY_CHECKED_NO_GO")

    def test_03_second_navigation_heading_can_break_rfind(self):
        raw=homepage().replace(
            b"</body>",b"<footer>The Bank's Market Operations</footer></body>")
        r=inspect(original_html=raw,receipt=receipt(raw),decision_at_utc=NOW)
        self.safe(r)
        self.assertEqual(r["market_heading_occurrences"],2)
        self.assertEqual(r["earlier_market_sections_with_three_distinct_measures"],1)
        self.assertFalse(r["last_market_section_guideline_found"])
        self.assertEqual(r["strict_validator_reason_code"],
                         "BOJ_POLICY_GUIDELINE_INSTRUMENT_OR_HTML_STRUCTURE_INVALID")

    def test_04_js_fake_policy_does_not_increase_visible_counts(self):
        raw=homepage()
        r=inspect(original_html=raw,receipt=receipt(raw),decision_at_utc=NOW)
        self.safe(r)
        self.assertEqual(r["whole_page_exact_policy_guideline_occurrences"],1)

    def test_05_body_decode_error_rejected_without_excerpts(self):
        bad=homepage()+b"\xff"
        r=inspect(original_html=bad,receipt=receipt(bad),decision_at_utc=NOW)
        self.safe(r)
        self.assertEqual(r["state"],"LAB_BOJ_STRUCTURE_DIAGNOSTIC_NO_REQUEST")
        self.assertFalse(r["html_utf8_parsed"])

    def test_06_collector_runs_once_only_and_no_raw_body_in_report(self):
        body=homepage()
        calls=[]
        def collector():
            calls.append(1)
            return body,receipt(body)
        r=collect(explicit_probe=True,collector=collector,clock=lambda:NOW)
        self.safe(r)
        self.assertEqual(calls,[1])
        self.assertEqual(r["official_https_get_attempts"],1)
        self.assertNotIn("Bank of Japan",str(r))
        self.assertTrue(r["html_utf8_parsed"])

    def test_07_http403_is_not_automatically_retried(self):
        calls=[]
        def deny():
            calls.append(1)
            raise HTTPError("https://www.boj.or.jp/en/",403,"Forbidden",None,None)
        r=collect(explicit_probe=True,collector=deny,clock=lambda:NOW)
        self.safe(r)
        self.assertEqual(calls,[1])
        self.assertEqual(r["state"],"LAB_BOJ_HTTP_DENIED_NO_GO")
        self.assertEqual(r["reason"],"OFFICIAL_HTTPS_HTTP_403")

    def test_08_cli_default_does_not_touch_network(self):
        with patch("atlasquant_trader_jpy_boj_home_structure_probe_lab."
                   "collect_boj_home_once_lab") as patched:
            self.assertEqual(main([]),2)
            patched.assert_not_called()


if __name__=="__main__":
    unittest.main()
