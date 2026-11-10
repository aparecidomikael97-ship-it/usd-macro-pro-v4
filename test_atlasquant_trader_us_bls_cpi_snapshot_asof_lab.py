"""Synthetic read-only receipt tests for US CPI lookahead gate."""
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import unittest

from atlasquant_trader_us_bls_cpi_snapshot_asof_lab import (
    RECEIPT_SCHEMA, inspect_bls_cpi_claimed_snapshot_asof_lab as inspect,
)
from atlasquant_trader_us_bls_cpi_yoy_snapshot_lab import SOURCE_URL_CLAIM
from test_atlasquant_trader_us_bls_cpi_yoy_snapshot_lab import payload

BEFORE = datetime(2026, 11, 9, 23, 59, tzinfo=timezone.utc)
AFTER = datetime(2026, 11, 10, 3, 0, tzinfo=timezone.utc)
LATER = datetime(2026, 11, 11, 3, 0, tzinfo=timezone.utc)


def receipt(raw):
    return {
        "schema": RECEIPT_SCHEMA,
        "source_url_claim": SOURCE_URL_CLAIM,
        "method_claim": "GET", "http_status_claim": 200,
        "content_type_claim": "application/json",
        "redirects_followed_claim": False, "body_bytes": len(raw),
        "body_sha256": sha256(raw).hexdigest(),
        "local_started_utc_claim": "2026-11-10T01:00:00Z",
        "local_finished_utc_claim": "2026-11-10T01:00:03Z",
        "caller_supplied_unattested": True,
        "original_issuer_release_authenticated": False,
        "collector_clock_independently_authenticated": False,
    }


def call(raw, rec=None, *, at=AFTER, evaluated=LATER, period="2026-09"):
    return inspect(raw, receipt(raw) if rec is None else rec,
                   reference_period=period, decision_at_utc=at,
                   evaluated_at_utc=evaluated)


class BLSAsOfLabTests(unittest.TestCase):
    def no_go(self, x):
        self.assertEqual(x["operational_bias"], "AGUARDAR")
        for name in ("source_origin_independently_authenticated",
                     "publisher_first_release_authenticated",
                     "collector_clock_independently_authenticated",
                     "historical_point_in_time_eligible",
                     "eligible_to_feed_macro_bias",
                     "revisions_independently_audited",
                     "derived_value_is_official_published_yoy",
                     "trade_authorized", "publishable", "scheduler_enabled",
                     "worker_enabled"):
            self.assertIs(x[name], False, name)
        self.assertEqual(x["http_requests"], 0)
        self.assertEqual(x["file_writes"], 0)
        self.assertEqual(x["new_cost_brl"], 0)

    def test_nonfuture_capture_allows_math_but_no_pit_or_bias(self):
        raw = payload()
        x = call(raw)
        self.assertEqual(x["state"], "LAB_BLS_CAPTURE_SELF_CONSISTENT_AND_NONFUTURE_UNATTESTED")
        self.assertEqual(x["derived_yoy_percent"], "5.000")
        self.assertTrue(x["local_body_hash_self_consistent"])
        self.assertEqual(x["body_sha256"], sha256(raw).hexdigest())
        self.no_go(x)

    def test_capture_after_historical_decision_hides_derived_number(self):
        x = call(payload(), at=BEFORE)
        self.assertEqual(x["state"], "LAB_BLS_CAPTURE_NOT_VISIBLE_AT_DECISION")
        self.assertIsNone(x["derived_yoy_percent"])
        self.assertFalse(x["local_body_hash_self_consistent"])
        self.no_go(x)

    def test_capture_end_equal_to_decision_is_not_future(self):
        cutoff = datetime(2026, 11, 10, 1, 0, 3, tzinfo=timezone.utc)
        self.assertEqual(call(payload(), at=cutoff)["derived_yoy_percent"], "5.000")

    def test_changed_body_or_wrong_checksum_rejects(self):
        raw = payload()
        rec = receipt(raw)
        rec["body_sha256"] = "0" * 64
        self.assertEqual(call(raw, rec)["state"], "LAB_BLS_ASOF_BLOCKED")
        rec = receipt(raw)
        self.assertEqual(call(raw + b" ", rec)["state"], "LAB_BLS_ASOF_BLOCKED")

    def test_wrong_url_method_status_content_type_or_redirect_rejects(self):
        raw = payload()
        variants = (("source_url_claim", "https://evil.example/data"),
                    ("method_claim", "POST"), ("http_status_claim", 403),
                    ("http_status_claim", True),
                    ("content_type_claim", "text/html"),
                    ("redirects_followed_claim", True),
                    ("body_bytes", len(raw) + 1),
                    ("caller_supplied_unattested", False),
                    ("original_issuer_release_authenticated", True),
                    ("collector_clock_independently_authenticated", True))
        for key, value in variants:
            with self.subTest(field=key):
                rec = receipt(raw)
                rec[key] = value
                x = call(raw, rec)
                self.assertEqual(x["state"], "LAB_BLS_ASOF_BLOCKED")
                self.no_go(x)

    def test_unsupported_receipt_field_rejected(self):
        raw = payload()
        rec = receipt(raw)
        rec["trade_authorized"] = True
        self.assertEqual(call(raw, rec)["state"], "LAB_BLS_ASOF_BLOCKED")

    def test_invalid_capture_window_rejected(self):
        raw = payload()
        cases = (("local_started_utc_claim", "2026-11-11T00:00:00Z"),
                 ("local_finished_utc_claim", "2026-11-10T01:03:00Z"),
                 ("local_finished_utc_claim", "2026-11-10T99:00:00Z"),
                 ("local_finished_utc_claim", "2026-11-10 01:00:03"))
        for key, value in cases:
            with self.subTest(field=key):
                rec = receipt(raw)
                rec[key] = value
                x = call(raw, rec)
                self.assertEqual(x["state"], "LAB_BLS_ASOF_BLOCKED")
                self.no_go(x)

    def test_invalid_or_reversed_decision_clocks_rejected(self):
        raw = payload()
        for at, evaluated in ((AFTER, BEFORE),
                              (datetime(2026, 11, 10, 3), LATER),
                              (AFTER.replace(microsecond=1), LATER),
                              (None, LATER)):
            with self.subTest(at=at):
                x = call(raw, at=at, evaluated=evaluated)
                self.assertEqual(x["state"], "LAB_BLS_ASOF_BLOCKED")
                self.no_go(x)

    def test_missing_t_minus_12_rejects_even_with_valid_hash(self):
        x = call(payload(), period="2026-10")
        self.assertEqual(x["reason"], "BLS_INDEX_RESPONSE_INVALID_OR_TARGET_MONTH_UNAVAILABLE")
        self.assertIsNone(x["derived_yoy_percent"])
        self.no_go(x)

    def test_original_input_and_receipt_not_mutated(self):
        raw = payload()
        rec = receipt(raw)
        before = deepcopy(rec)
        _ = call(raw, rec)
        self.assertEqual(rec, before)


if __name__ == "__main__":
    unittest.main()
