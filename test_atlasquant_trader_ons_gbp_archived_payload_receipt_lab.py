"""Synthetic opaque byte receipts; no ONS download and no CSV parsing."""
from datetime import datetime, timezone
from hashlib import sha256
import unittest

from atlasquant_trader_ons_gbp_archived_payload_receipt_lab import (
    MAX_ARCHIVE_BYTES, SCHEMA, inspect_ons_gbp_archive_payload_receipt_lab as inspect,
)
from atlasquant_trader_ons_gbp_archived_link_catalog_lab import (
    plan_ons_gbp_archived_source_leads_lab,
)

NOW = datetime(2026, 11, 5, 16, tzinfo=timezone.utc)
CUTOFF = datetime(2026, 10, 20, 12, tzinfo=timezone.utc)
FAKE = b"synthetic-archive-byte-receipt-fixture-ONLY-DO-NOT-TRADE\n" * 3


def real_looking_url(version="v131"):
    r = plan_ons_gbp_archived_source_leads_lab(
        historical_as_of_utc=CUTOFF, evaluated_at_utc=NOW,
        version_id=version,
    )
    return r["catalog_entries"][0]["official_archive_download_url_candidate"]


def run(data=FAKE, **override):
    options = {
        "version_id": "v131",
        "claimed_source_url": real_looking_url(),
        "claimed_http_status": 200,
        "claimed_content_type": "application/octet-stream",
        "claimed_content_length": len(data) if isinstance(data, bytes) else None,
        "independently_recorded_sha256": (
            sha256(data).hexdigest() if isinstance(data, bytes) else None),
        "claimed_observed_at_utc": NOW,
        "historical_as_of_utc": CUTOFF,
        "evaluated_at_utc": NOW,
    }
    options.update(override)
    return inspect(data, **options)


class OnsArchiveReceiptTests(unittest.TestCase):
    def assert_no_go(self, x):
        for key in (
            "http_response_independently_observed",
            "external_sha256_independently_attested",
            "publisher_tls_origin_verified",
            "original_historical_snapshot_independently_verified",
            "release_instant_independently_verified",
            "point_in_time_historically_available_verified",
            "commercial_redistribution_rights_verified",
            "payload_csv_structure_verified",
            "usable_for_backtest", "trade_authorized",
            "can_feed_live_radar", "worker_enabled", "scheduler_enabled",
            "publishable",
        ):
            self.assertIs(x[key], False, key)
        self.assertEqual(x["operational_bias"], "AGUARDAR")
        self.assertIsNone(x["fx_bias"])
        self.assertEqual((x["external_http_requests"], x["new_cost_brl"]), (0, 0))

    def test_matching_synthetic_bytes_only_internal_integrity(self):
        x = run()
        self.assertEqual(x["schema"], SCHEMA)
        self.assertEqual(x["state"],
                         "LAB_ONS_ARCHIVE_BYTES_INTERNALLY_MATCHED_QUARANTINED")
        self.assertTrue(x["expected_source_url_allowlisted"])
        self.assertTrue(x["declared_response_status_checked"])
        self.assertTrue(x["declared_content_length_matched"])
        self.assertTrue(x["provided_sha256_matched"])
        self.assertEqual(x["source_raw_sha256"], sha256(FAKE).hexdigest())
        self.assertEqual(x["source_bytes"], len(FAKE))
        self.assertEqual(x["declared_observed_at_utc"], NOW.isoformat())
        self.assertEqual(x["version_id"], "v131")
        self.assert_no_go(x)

    def test_future_version_not_assumed_published_asof(self):
        x = run(historical_as_of_utc=datetime(2026, 7, 1, tzinfo=timezone.utc))
        self.assertEqual(x["reported_supersession_calendar_state"],
                         "BEFORE_SUPERSESSION_UPPER_BOUND_ONLY_NO_PROOF")
        self.assert_no_go(x)

    def test_same_day_supersession_is_unknown(self):
        x = run(historical_as_of_utc=datetime(2026, 10, 21, 23,
                                            tzinfo=timezone.utc))
        self.assertEqual(x["reported_supersession_calendar_state"],
                         "SUPERSESSION_DAY_INTRADAY_AMBIGUOUS_BLOCKED")
        self.assert_no_go(x)

    def test_after_supersession_not_a_current_vintage(self):
        x = run(historical_as_of_utc=datetime(2026, 10, 22,
                                            tzinfo=timezone.utc))
        self.assertEqual(x["reported_supersession_calendar_state"],
                         "AFTER_SUPERSESSION_NOT_CURRENT_VINTAGE")
        self.assert_no_go(x)

    def test_correct_second_version_still_quarantined(self):
        x = run(version_id="v130", claimed_source_url=real_looking_url("v130"))
        self.assertEqual(x["version_id"], "v130")
        self.assert_no_go(x)

    def test_same_url_with_wrong_version_id_rejected(self):
        x = run(version_id="v130")
        self.assertEqual(x["reason"], "SOURCE_URL_NOT_PINNED_OLD_ONS_VERSION")

    def test_unregistered_version_rejected(self):
        x = run(version_id="v132")
        self.assertEqual(x["reason"], "UNKNOWN_VERSION_ID")

    def test_wrong_host_or_query_rejected(self):
        for url in ("https://ons.gov.uk/generator?format=csv",
                    real_looking_url() + "&redirect=1",
                    real_looking_url().replace("www.ons.gov.uk", "ons.evil.test")):
            self.assertEqual(run(claimed_source_url=url)["reason"],
                             "SOURCE_URL_NOT_PINNED_OLD_ONS_VERSION")

    def test_tampered_bytes_rejected_with_separately_recorded_hash(self):
        x = run(data=FAKE + b"!", independently_recorded_sha256=sha256(FAKE).hexdigest())
        self.assertEqual(x["reason"], "PROVIDED_SHA256_MISMATCH_OR_INVALID")

    def test_uppercase_hash_and_invalid_hash_rejected(self):
        for bad in ("X" * 64, "0" * 63, "a" * 65, 0, None):
            self.assertEqual(run(independently_recorded_sha256=bad)["reason"],
                             "PROVIDED_SHA256_MISMATCH_OR_INVALID")

    def test_wrong_declared_size_and_bool_rejected(self):
        for size in (len(FAKE) + 1, -1, True, str(len(FAKE))):
            self.assertEqual(run(claimed_content_length=size)["reason"],
                             "DECLARED_BYTE_COUNT_MISMATCH")

    def test_http_status_not_200_or_bool_rejected(self):
        for status in (201, 304, 404, 302, 500, True, "200"):
            self.assertEqual(run(claimed_http_status=status)["reason"],
                             "DECLARED_HTTP_STATUS_NOT_SUCCESS")

    def test_accepted_media_claims_are_conservative(self):
        for mime in ("application/octet-stream", "text/csv",
                     "application/csv", "text/csv; charset=utf-8",
                     "text/csv; charset=us-ascii"):
            self.assertEqual(run(claimed_content_type=mime)["state"],
                             "LAB_ONS_ARCHIVE_BYTES_INTERNALLY_MATCHED_QUARANTINED")

    def test_unknown_or_injected_media_claim_rejected(self):
        for mime in ("text/html", "application/pdf", "text/csv;foo=bar",
                     "text/csv\r\nX-Foo: injected", "", None):
            self.assertEqual(run(claimed_content_type=mime)["reason"],
                             "UNRECOGNIZED_CLAIMED_CONTENT_TYPE")

    def test_empty_small_or_non_bytes_rejected(self):
        for bad in (b"", b"x" * 15, None, "opaque", []):
            self.assertEqual(run(data=bad)["reason"], "INVALID_BYTES_OR_CLOCKS")

    def test_oversized_bytes_rejected_before_hashing(self):
        self.assertEqual(run(data=b"x" * (MAX_ARCHIVE_BYTES + 1))["state"],
                         "LAB_BLOCKED")

    def test_future_capture_after_evaluation_rejected(self):
        later = datetime(2026, 11, 6, tzinfo=timezone.utc)
        self.assertEqual(run(claimed_observed_at_utc=later)["reason"],
                         "INVALID_BYTES_OR_CLOCKS")

    def test_historical_cutoff_after_evaluation_rejected(self):
        later = datetime(2026, 11, 6, tzinfo=timezone.utc)
        self.assertEqual(run(historical_as_of_utc=later)["reason"],
                         "INVALID_BYTES_OR_CLOCKS")

    def test_naive_time_rejected(self):
        naive = datetime(2026, 11, 5)
        for name in ("claimed_observed_at_utc", "historical_as_of_utc",
                     "evaluated_at_utc"):
            self.assertEqual(run(**{name: naive})["state"], "LAB_BLOCKED")

    def test_no_receipt_can_become_operational_without_independent_proof(self):
        for version in ("v131", "v130", "v129", "v128"):
            r = run(version_id=version, claimed_source_url=real_looking_url(version))
            self.assert_no_go(r)


if __name__ == "__main__":
    unittest.main()
