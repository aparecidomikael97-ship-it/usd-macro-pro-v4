"""Synthetic only: hashing local CPI bytes does not authenticate issuer truth."""
from datetime import datetime, timezone
from hashlib import sha256
import unittest

from atlasquant_fx_universe import CURRENCIES
from atlasquant_trader_g8_macro_asof_lab import CPI_ISSUER_HOSTS
from atlasquant_trader_g8_cpi_capture_binding_lab import (
    MAX_BODY_BYTES,
    build_local_g8_cpi_capture_receipt_lab as build,
    inspect_local_g8_cpi_capture_binding_lab as inspect,
)

PUBLISHED = "2026-10-29T12:00:00Z"
CAPTURED = "2026-10-29T12:00:02Z"
DECISION = datetime(2026, 11, 5, 12, tzinfo=timezone.utc)
EVALUATED = datetime(2026, 11, 6, 12, tzinfo=timezone.utc)


def url_for(currency):
    host = sorted(CPI_ISSUER_HOSTS[currency])[0]
    return f"https://{host}/eurostat/web/hicp/research" if currency == "EUR" else f"https://{host}/cpi/research"


def fixture(currency="USD", *, stage="FINAL", published=PUBLISHED,
            captured=CAPTURED, period=None, body=None):
    if period is None:
        period = "2026-Q3" if currency == "NZD" else "2026-09"
    if body is None:
        body = ("SYNTHETIC NOT REAL SOURCE " + currency).encode("ascii")
    url = url_for(currency)
    row = {
        "currency": currency, "indicator": "CPI_YOY",
        "observation_period": period, "value": "2.0",
        "publication_stage": stage, "published_at_utc": published,
        "captured_at_utc": captured,
        "source_type": "OFFICIAL_STATISTICS_OFFICE",
        "source_sha256": sha256(body).hexdigest(), "source_url": url,
    }
    receipt = build(currency, period, stage, url, body, captured_at_utc=captured)
    return row, receipt


def run(row, receipt, *, decision=DECISION, now=EVALUATED):
    return inspect(row, receipt, decision_at_utc=decision, evaluated_at_utc=now)


class CPICaptureBindingTests(unittest.TestCase):
    def assert_no_go(self, result):
        self.assertEqual(result["operational_bias"], "AGUARDAR")
        self.assertIsNone(result["validated_accuracy"])
        for field in (
            "issuer_tls_connection_verified", "original_issuer_bytes_authenticated",
            "first_publication_time_independently_attested",
            "capture_clock_independently_attested",
            "cpi_value_extracted_and_verified_from_body",
            "historical_point_in_time_eligible", "can_feed_macro_bias",
            "publishable", "trade_authorized", "worker_enabled", "scheduler_enabled",
        ):
            self.assertFalse(result[field], field)
        self.assertEqual((result["network_requests"], result["file_writes"],
                          result["new_cost_brl"]), (0, 0, 0))

    def test_all_eight_g8_sources_can_link_synthetic_bytes_but_never_authenticate(self):
        self.assertEqual(len(CURRENCIES), 8)
        for currency in CURRENCIES:
            with self.subTest(currency=currency):
                row, receipt = fixture(currency)
                result = run(row, receipt)
                self.assertEqual(result["state"], "LAB_CPI_LOCAL_BYTE_HASH_BOUND_UNATTESTED")
                self.assertTrue(result["local_byte_hash_matches_macro_claim"])
                self.assertTrue(result["local_receipt_self_consistent"])
                self.assertTrue(result["issuer_host_claim_checked"])
                self.assertEqual(result["body_sha256_local"], row["source_sha256"])
                self.assert_no_go(result)

    def test_flash_reference_month_is_documentary_only(self):
        row, receipt = fixture("EUR", stage="FLASH", period="2026-10")
        result = run(row, receipt)
        self.assertEqual(result["state"], "LAB_CPI_LOCAL_BYTE_HASH_BOUND_UNATTESTED")
        self.assertEqual(result["publication_stage_claim"], "FLASH")
        self.assert_no_go(result)

    def test_claimed_macro_hash_must_match_the_supplied_source_bytes(self):
        row, receipt = fixture()
        result = run({**row, "source_sha256": "b" * 64}, receipt)
        self.assertEqual(result["reason"], "CPI_MACRO_SOURCE_HASH_NOT_BOUND_TO_CAPTURE_BYTES")
        self.assert_no_go(result)

    def test_tampering_with_receipt_body_or_clock_fails_closed(self):
        row, receipt = fixture()
        for altered in ({**receipt, "body_base64": "YQ=="},
                        {**receipt, "body_sha256": "0" * 64},
                        {**receipt, "captured_at_utc": "2026-10-29T12:00:03Z"}):
            with self.subTest(keys=altered):
                result = run(row, altered)
                self.assertEqual(result["state"], "LAB_CPI_LOCAL_BINDING_BLOCKED")
                self.assert_no_go(result)

    def test_other_country_page_cannot_be_bound_to_us_cpi(self):
        row, receipt = fixture("USD")
        bad = {**row, "source_url": url_for("GBP")}
        self.assertEqual(run(bad, receipt)["state"], "LAB_CPI_LOCAL_BINDING_BLOCKED")
        self.assert_no_go(run(bad, receipt))

    def test_non_cpi_revisions_bad_values_and_mismatched_stages_fail(self):
        row, receipt = fixture()
        for altered in ({**row, "indicator": "POLICY_RATE"},
                        {**row, "publication_stage": "REVISION"},
                        {**row, "publication_stage": "FLASH"},
                        {**row, "value": "NaN"},
                        {**row, "observation_period": "2026-10"}):
            result = run(altered, receipt)
            self.assertEqual(result["state"], "LAB_CPI_LOCAL_BINDING_BLOCKED")
            self.assert_no_go(result)

    def test_future_or_prepublication_capture_cannot_be_used_at_decision(self):
        row, receipt = fixture()
        for altered in ({**row, "published_at_utc": "2026-10-29T12:00:03Z"},
                        {**row, "captured_at_utc": "2026-11-05T12:00:01Z"}):
            result = run(altered, receipt)
            self.assertEqual(result["state"], "LAB_CPI_LOCAL_BINDING_BLOCKED")
            self.assert_no_go(result)
        result = run(row, receipt, now=datetime(2026, 11, 4, tzinfo=timezone.utc))
        self.assertEqual(result["state"], "LAB_CPI_LOCAL_BINDING_BLOCKED")

    def test_bool_status_extra_schema_field_and_oversize_are_rejected(self):
        row, receipt = fixture()
        for altered in ({**receipt, "http_status_claim": True},
                        {**receipt, "unknown_extra": "value"}):
            self.assertEqual(run(row, altered)["state"], "LAB_CPI_LOCAL_BINDING_BLOCKED")
        blocked = build("USD", "2026-09", "FINAL", url_for("USD"),
                        b"x" * (MAX_BODY_BYTES + 1), captured_at_utc=CAPTURED)
        self.assertEqual(blocked["state"], "LAB_CPI_LOCAL_BINDING_BLOCKED")
        self.assert_no_go(blocked)

    def test_recomputable_self_consistency_does_not_prove_official_publication(self):
        fake_body = b"completely invented synthetic CPI release text"
        row, receipt = fixture("GBP", body=fake_body)
        result = run(row, receipt)
        self.assertEqual(result["state"], "LAB_CPI_LOCAL_BYTE_HASH_BOUND_UNATTESTED")
        self.assertFalse(result["original_issuer_bytes_authenticated"])
        self.assertFalse(result["cpi_value_extracted_and_verified_from_body"])
        self.assert_no_go(result)


if __name__ == "__main__":
    unittest.main()
