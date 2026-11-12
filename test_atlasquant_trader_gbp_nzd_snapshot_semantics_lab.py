"""Synthetic offline tests of conservative, SHA-pinned HTML context checks."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import unittest

from atlasquant_trader_gbp_nzd_official_capture_lab import SCHEMA as CAPTURE_SCHEMA, TARGETS
from atlasquant_trader_gbp_nzd_snapshot_semantics_lab import (
    PINS, RULES, audit_am12_directory_lab,
    inspect_pinned_html_semantics_lab as inspect,
)


EXAMPLES = {
    "GBP_CPI_2026_09": (
        "Consumer price inflation, UK - Office for National Statistics",
        "Consumer price inflation, UK: September 2026. "
        "The Consumer Prices Index (CPI) rose by 3.5% in the 12 months to September 2026. "
        "Released: 21 October 2026 7:00am."),
    "NZD_CPI_2026_Q3": (
        "Consumers price index: September 2026 quarter | Stats NZ",
        "Consumers price index: September 2026 quarter. "
        "22 October 2026, 10:45am. "
        "Within the 3.7 percent increase in the CPI in the 12 months to the September 2026 quarter, prices changed."),
    "GBP_BANK_RATE_2026_11": (
        "Bank rate increased to 4% - November 2026 Monetary Policy Summary and Minutes | Bank of England",
        "Published on 05 November 2026. "
        "At its meeting ending on 4 November 2026, the MPC voted by a majority "
        "to increase Bank Rate by 0.25 percentage points, to 4%."),
}


def synthetic_fixture(key, *, title=None, body=None, script=""):
    expected_title, expected_body = EXAMPLES[key]
    html = ("<html><head><title>" + (expected_title if title is None else title)
            + "</title><script>" + script + "</script></head><body><h1>"
            + (expected_body if body is None else body)
            + "</h1></body></html>").encode()
    pin = dict(PINS[key])
    receipt = {
        "schema": CAPTURE_SCHEMA, "document_id": key,
        "source_url": TARGETS[key], "snapshot_filename": pin["filename"],
        "snapshot_sha256": sha256(html).hexdigest(), "snapshot_bytes": len(html),
        "local_capture_finished_at_utc": pin["capture_finished_at_utc"],
        "http_status": 200, "http_content_type": "text/html",
    }
    receipt_raw = json.dumps(receipt, sort_keys=True).encode()
    pin.update(body_sha256=sha256(html).hexdigest(),
               receipt_sha256=sha256(receipt_raw).hexdigest())
    return html, receipt_raw, pin


class SnapshotSemanticAuditTests(unittest.TestCase):
    def assert_no_go(self, result):
        self.assertFalse(result["issuer_authenticity_at_original_release_verified"])
        self.assertFalse(result["independent_timestamp_authority_verified"])
        self.assertFalse(result["point_in_time_backtest_approved"])
        self.assertFalse(result["trade_authorized"])
        self.assertIsNone(result["directional_probability"])
        self.assertEqual(result["operational_bias"], "AGUARDAR")

    def test_three_known_real_pins_but_no_rbnz_pin(self):
        self.assertEqual(len(PINS), 3)
        self.assertEqual(set(PINS), set(RULES))
        self.assertNotIn("NZD_OCR_2026_10", PINS)

    def test_each_synthetic_official_phrase_visible_and_pinned(self):
        for key in EXAMPLES:
            with self.subTest(key=key):
                html, receipt, pin = synthetic_fixture(key)
                with patch.dict(PINS, {key: pin}):
                    result = inspect(key, raw_html=html, raw_receipt_json=receipt)
                self.assertEqual(result["state"], "LAB_VISIBLE_CONTEXT_MATCH_UNATTESTED")
                self.assertTrue(result["sha256_matches_checkpoint_pins"])
                self.assertEqual(result["checks"], {
                    "title": True, "period": True, "metric": True, "release": True,
                })
                self.assert_no_go(result)

    def test_wrong_period_is_not_accepted_as_correct_value(self):
        key = "GBP_CPI_2026_09"
        title, body = EXAMPLES[key]
        html, receipt, pin = synthetic_fixture(key, body=body.replace("September 2026", "August 2026"))
        with patch.dict(PINS, {key: pin}):
            result = inspect(key, raw_html=html, raw_receipt_json=receipt)
        self.assertEqual(result["state"], "LAB_SEMANTIC_REVIEW_REQUIRED")
        self.assertFalse(result["checks"]["metric"])
        self.assert_no_go(result)

    def test_future_value_in_script_is_not_official_visible_text(self):
        key = "GBP_BANK_RATE_2026_11"
        title, body = EXAMPLES[key]
        html, receipt, pin = synthetic_fixture(
            key, body="Published on 05 November 2026. At its meeting ending on 4 November 2026, no value appears.",
            script=body)
        with patch.dict(PINS, {key: pin}):
            result = inspect(key, raw_html=html, raw_receipt_json=receipt)
        self.assertEqual(result["state"], "LAB_SEMANTIC_REVIEW_REQUIRED")
        self.assertFalse(result["checks"]["metric"])

    def test_archived_html_tampered_one_byte_is_rejected(self):
        key = "NZD_CPI_2026_Q3"
        html, receipt, pin = synthetic_fixture(key)
        changed = bytearray(html)
        changed[-20] ^= 1
        with patch.dict(PINS, {key: pin}):
            result = inspect(key, raw_html=bytes(changed), raw_receipt_json=receipt)
        self.assertEqual(result["reason"], "CAPTURE_BYTES_OR_RECEIPT_DIFFER_FROM_GITHUB_CHECKPOINT")
        self.assert_no_go(result)

    def test_manifest_tampered_one_byte_is_rejected(self):
        key = "GBP_CPI_2026_09"
        html, receipt, pin = synthetic_fixture(key)
        changed = bytearray(receipt)
        changed[40] ^= 1
        with patch.dict(PINS, {key: pin}):
            result = inspect(key, raw_html=html, raw_receipt_json=bytes(changed))
        self.assertEqual(result["reason"], "CAPTURE_BYTES_OR_RECEIPT_DIFFER_FROM_GITHUB_CHECKPOINT")

    def test_reanchored_manifest_with_wrong_source_is_rejected(self):
        key = "GBP_CPI_2026_09"
        html, receipt, pin = synthetic_fixture(key)
        metadata = json.loads(receipt)
        metadata["source_url"] = TARGETS["NZD_CPI_2026_Q3"]
        forged_receipt = json.dumps(metadata, sort_keys=True).encode()
        pin["receipt_sha256"] = sha256(forged_receipt).hexdigest()
        with patch.dict(PINS, {key: pin}):
            result = inspect(key, raw_html=html, raw_receipt_json=forged_receipt)
        self.assertEqual(result["reason"], "CAPTURE_RECEIPT_METADATA_INCONSISTENT")

    def test_not_a_real_capture_cannot_match_default_pins(self):
        key = "GBP_CPI_2026_09"
        html, receipt, _ = synthetic_fixture(key)
        result = inspect(key, raw_html=html, raw_receipt_json=receipt)
        self.assertEqual(result["state"], "LAB_BLOCKED")
        self.assert_no_go(result)

    def test_missing_capture_directory_is_not_a_pass(self):
        with TemporaryDirectory() as tmp:
            result = audit_am12_directory_lab(Path(tmp))
            self.assertEqual(result["consistent_sha_pins"], 0)
            self.assertEqual(result["visible_context_matches"], 0)
            self.assertTrue(all(x["state"] == "LAB_BLOCKED" for x in result["results"].values()))

    def test_directory_audit_with_pinned_synthetic_fixtures(self):
        with TemporaryDirectory() as tmp:
            pins = {}
            for key in EXAMPLES:
                html, receipt, pin = synthetic_fixture(key)
                pins[key] = pin
                (Path(tmp) / pin["filename"]).write_bytes(html)
                (Path(tmp) / (pin["filename"] + ".receipt.json")).write_bytes(receipt)
            with patch.dict(PINS, pins):
                report = audit_am12_directory_lab(Path(tmp))
            self.assertEqual(report["consistent_sha_pins"], 3)
            self.assertEqual(report["visible_context_matches"], 3)
            self.assertFalse(report["historical_backtest_authorized"])

    def test_malformed_utf8_rejected_even_if_pinned(self):
        key = "GBP_BANK_RATE_2026_11"
        html, receipt, pin = synthetic_fixture(key)
        bad = b"\xff" + html
        pin["body_sha256"] = sha256(bad).hexdigest()
        metadata = json.loads(receipt)
        metadata["snapshot_sha256"] = pin["body_sha256"]
        metadata["snapshot_bytes"] = len(bad)
        receipt = json.dumps(metadata, sort_keys=True).encode()
        pin["receipt_sha256"] = sha256(receipt).hexdigest()
        with patch.dict(PINS, {key: pin}):
            result = inspect(key, raw_html=bad, raw_receipt_json=receipt)
        self.assertEqual(result["reason"], "INVALID_UTF8_JSON_OR_HTML")

    def test_unsupported_source_keeps_rbnz_blocked(self):
        result = inspect("NZD_OCR_2026_10", raw_html=b"x" * 1000, raw_receipt_json=b"y" * 1000)
        self.assertEqual(result["reason"], "UNKNOWN_DOCUMENT_OR_INVALID_BYTES")


if __name__ == "__main__":
    unittest.main()
