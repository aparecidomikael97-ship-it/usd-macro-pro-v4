"""Synthetic read-only receipt tests for US CPI lookahead gate."""
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import unittest

from atlasquant_trader_us_bls_cpi_snapshot_asof_lab import (
    RECEIPT_SCHEMA, KNOWN_BLS_CPI_RELEASE_FLOORS_UTC,
    inspect_bls_cpi_claimed_snapshot_asof_lab as inspect,
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
        self.assertEqual(x["known_bls_release_floor_utc"],
                         "2026-10-14T12:30:00+00:00")
        self.no_go(x)

    def test_september_2026_fake_early_capture_not_rescued_by_later_decision(self):
        raw = payload()
        for claimed_time in ("2026-10-01T12:00:00Z",
                             "2026-10-14T12:29:59Z"):
            with self.subTest(claimed_time=claimed_time):
                rec = receipt(raw)
                rec["local_started_utc_claim"] = claimed_time
                rec["local_finished_utc_claim"] = claimed_time
                result = call(raw, rec, at=AFTER)
                self.assertEqual(result["state"],
                                 "LAB_BLS_CAPTURE_CLAIM_PRECEDES_OFFICIAL_RELEASE")
                self.assertEqual(result["reason"],
                                 "KNOWN_BLS_CPI_RELEASE_FLOOR_NOT_REACHED")
                self.assertIsNone(result["derived_yoy_percent"])
                self.no_go(result)

    def test_september_2026_release_at_0830_edt_is_1230_utc(self):
        release = KNOWN_BLS_CPI_RELEASE_FLOORS_UTC["2026-09"]
        self.assertEqual(release.isoformat(), "2026-10-14T12:30:00+00:00")
        raw = payload()
        rec = receipt(raw)
        rec["local_started_utc_claim"] = "2026-10-14T12:30:00Z"
        rec["local_finished_utc_claim"] = "2026-10-14T12:30:00Z"
        result = call(raw, rec, at=release)
        self.assertEqual(result["state"],
                         "LAB_BLS_CAPTURE_SELF_CONSISTENT_AND_NONFUTURE_UNATTESTED")
        self.no_go(result)

    def test_october_2026_release_at_0830_est_is_1330_utc(self):
        release = KNOWN_BLS_CPI_RELEASE_FLOORS_UTC["2026-10"]
        self.assertEqual(release.isoformat(), "2026-11-10T13:30:00+00:00")
        # The October 2025 CPI-U year-ago index is officially unavailable.
        # The publication fence is independent of that separate arithmetic veto.
        raw = payload()
        rec = receipt(raw)
        rec["local_started_utc_claim"] = "2026-11-10T13:29:59Z"
        rec["local_finished_utc_claim"] = "2026-11-10T13:29:59Z"
        result = call(raw, rec, at=release, period="2026-10")
        self.assertEqual(result["state"],
                         "LAB_BLS_CAPTURE_CLAIM_PRECEDES_OFFICIAL_RELEASE")
        self.no_go(result)

        rec["local_started_utc_claim"] = "2026-11-10T13:30:00Z"
        rec["local_finished_utc_claim"] = "2026-11-10T13:30:00Z"
        result = call(raw, rec, at=release, period="2026-10")
        self.assertEqual(result["reason"],
                         "BLS_INDEX_RESPONSE_INVALID_OR_TARGET_MONTH_UNAVAILABLE")
        self.no_go(result)

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
        raw = payload()
        rec = receipt(raw)
        rec["local_started_utc_claim"] = "2026-11-10T13:30:00Z"
        rec["local_finished_utc_claim"] = "2026-11-10T13:30:00Z"
        x = call(raw, rec, period="2026-10",
                 at=datetime(2026, 11, 10, 13, 31, tzinfo=timezone.utc))
        self.assertEqual(x["reason"], "BLS_INDEX_RESPONSE_INVALID_OR_TARGET_MONTH_UNAVAILABLE")
        self.assertIsNone(x["derived_yoy_percent"])
        self.no_go(x)

    def test_unhashable_reference_period_fails_closed_without_exception(self):
        result = call(payload(), period={"month": "2026-09"})
        self.assertEqual(result["state"], "LAB_BLS_ASOF_BLOCKED")
        self.no_go(result)

    def test_original_input_and_receipt_not_mutated(self):
        raw = payload()
        rec = receipt(raw)
        before = deepcopy(rec)
        _ = call(raw, rec)
        self.assertEqual(rec, before)


if __name__ == "__main__":
    unittest.main()
