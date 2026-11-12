"""Offline synthetic tests of the archived-BLS same-response YoY bridge."""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from io import BytesIO
import json
import unittest
import warnings
from zipfile import ZipFile, ZIP_STORED

from atlasquant_trader_bls_cpi_u_official_bytes_readonly_lab import (
    inspect_bls_cpi_u_v1_bytes_lab,
)
from atlasquant_trader_bls_cpi_u_capture_receipt_lab import (
    prepare_bls_cpi_u_source_receipt_lab,
)
from atlasquant_trader_bls_cpi_u_zip_yoy_bridge_lab import (
    inspect_bls_cpi_u_archive_same_bytes_yoy_lab as inspect,
)

UTC = timezone.utc
CAPTURED = datetime(2026, 11, 12, 20, 0, tzinfo=UTC)
CUTOFF = datetime(2026, 11, 12, 20, 5, tzinfo=UTC)
MONTH_NAMES = ("January", "February", "March", "April", "May", "June",
               "July", "August", "September", "October", "November", "December")


def row(year, month, value):
    return {
        "year": str(year),
        "period": f"M{month:02d}",
        "periodName": MONTH_NAMES[month - 1],
        "value": str(value),
        "footnotes": [],
    }


def archive(rows=None):
    if rows is None:
        rows = [row(2026, 9, "330.000"), row(2025, 9, "300.000")]
    raw = json.dumps({
        "status": "REQUEST_SUCCEEDED", "message": [],
        "Results": [{"series": [{"seriesID": "CUUR0000SA0", "data": rows}]}],
    }, sort_keys=True, separators=(",", ":")).encode("ascii")
    report = inspect_bls_cpi_u_v1_bytes_lab(
        original_bytes=raw, captured_at_utc=CAPTURED, server_date_at_utc=CAPTURED)
    assert report["state"] == "LAB_BLS_CPI_U_INDEX_BYTES_INSPECTED_UNATTESTED"
    report["http_get_completed"] = True
    report["http_requests"] = 1
    prepared = prepare_bls_cpi_u_source_receipt_lab(fetched=report)
    assert prepared["state"] == "LAB_BLS_CPI_U_SOURCE_ZIP_PREPARED_LOCAL_ONLY"
    return prepared["capture_bundle_zip"]


class ArchivedBlsCpiYoYBridgeTests(unittest.TestCase):
    def no_go(self, result):
        self.assertEqual(result["operational_bias"], "AGUARDAR")
        self.assertIsNone(result["calibrated_direction_probability"])
        for flag in (
            "original_bls_issuer_attested",
            "first_publication_utc_independently_attested",
            "point_in_time_vintage_independently_attested",
            "validated_for_fx28_macro", "trade_authorized",
            "publishable", "live_alert_allowed", "scheduler_enabled",
            "worker_enabled",
        ):
            self.assertIs(result[flag], False, flag)
        self.assertEqual(
            (result["http_requests"], result["file_writes"], result["new_cost_brl"]),
            (0, 0, 0))

    def test_same_original_archive_bytes_yield_research_only_rate(self):
        zipped = archive()
        out = inspect(
            archive_zip=zipped, reference_period="2026-09",
            decision_at_utc=CUTOFF)
        self.assertEqual(out["state"], "LAB_ARCHIVED_BLS_CPI_U_TWO_LEVEL_YOY_UNATTESTED")
        self.assertEqual(out["derived_yoy_percent_research_only"], "10.000")
        self.assertEqual(out["previous_year_reference_period"], "2025-09")
        self.assertTrue(out["zip_original_bytes_and_manifest_locally_consistent"])
        self.assertTrue(out["derived_from_two_months_of_same_original_response"])
        with ZipFile(BytesIO(zipped)) as z:
            raw = z.read("bls_cpi_u_v1_original_response.json")
        self.assertEqual(out["original_response_sha256_local"], sha256(raw).hexdigest())
        self.no_go(out)

    def test_missing_year_ago_must_block_not_replace_with_previous_month(self):
        zipped = archive([row(2026, 9, "330"), row(2026, 8, "300")])
        out = inspect(
            archive_zip=zipped, reference_period="2026-09",
            decision_at_utc=CUTOFF)
        self.assertEqual(out["state"], "LAB_ARCHIVED_BLS_CPI_U_YOY_BLOCKED")
        self.assertIn("TARGET_OR_PRIOR_YEAR_SAME_MONTH_INDEX_MISSING", out["reason"])
        self.assertIsNone(out["derived_yoy_percent_research_only"])
        self.no_go(out)

    def test_october_2025_missing_index_must_not_be_fabricated(self):
        zipped = archive([row(2026, 10, "335"), row(2025, 10, "320")])
        out = inspect(
            archive_zip=zipped, reference_period="2026-10",
            decision_at_utc=CUTOFF)
        self.assertEqual(out["state"], "LAB_ARCHIVED_BLS_CPI_U_YOY_BLOCKED")
        self.assertIn("OFFICIAL_2025_10_CPI_U_YEAR_AGO_INDEX_UNAVAILABLE", out["reason"])
        self.no_go(out)

    def test_capture_after_decision_is_strictly_blocked(self):
        out = inspect(
            archive_zip=archive(), reference_period="2026-09",
            decision_at_utc=CAPTURED - timedelta(seconds=1))
        self.assertEqual(out["reason"], "CAPTURE_AFTER_FORECAST_CUTOFF_LOOKAHEAD")
        self.no_go(out)

    def test_future_reference_month_is_not_extrapolated(self):
        out = inspect(
            archive_zip=archive(), reference_period="2026-12",
            decision_at_utc=CUTOFF)
        self.assertEqual(out["reason"], "REFERENCE_MONTH_AFTER_CAPTURE_MONTH")
        self.no_go(out)

    def test_forged_manifest_positive_provenance_is_rejected(self):
        original = archive()
        with ZipFile(BytesIO(original)) as z:
            raw = z.read("bls_cpi_u_v1_original_response.json")
            manifest = json.loads(z.read("capture_manifest.json"))
        manifest["first_publication_proven"] = True
        buf = BytesIO()
        with ZipFile(buf, "w", compression=ZIP_STORED) as z:
            z.writestr("bls_cpi_u_v1_original_response.json", raw)
            z.writestr("capture_manifest.json", json.dumps(
                manifest, sort_keys=True, separators=(",", ":")).encode("ascii"))
        out = inspect(
            archive_zip=buf.getvalue(), reference_period="2026-09",
            decision_at_utc=CUTOFF)
        self.assertEqual(out["reason"], "ZIP_MANIFEST_NOT_CANONICAL")
        self.no_go(out)

    def test_modified_original_with_unchanged_receipt_is_rejected(self):
        original = archive()
        with ZipFile(BytesIO(original)) as z:
            raw = z.read("bls_cpi_u_v1_original_response.json")
            manifest = z.read("capture_manifest.json")
        changed = raw.replace(b"330.000", b"399.000")
        self.assertNotEqual(changed, raw)
        buf = BytesIO()
        with ZipFile(buf, "w", compression=ZIP_STORED) as z:
            z.writestr("bls_cpi_u_v1_original_response.json", changed)
            z.writestr("capture_manifest.json", manifest)
        out = inspect(
            archive_zip=buf.getvalue(), reference_period="2026-09",
            decision_at_utc=CUTOFF)
        self.assertEqual(out["reason"], "ZIP_MANIFEST_NOT_CANONICAL")
        self.no_go(out)

    def test_duplicate_zip_member_blocked_even_if_identical(self):
        original = archive()
        with ZipFile(BytesIO(original)) as z:
            raw = z.read("bls_cpi_u_v1_original_response.json")
            manifest = z.read("capture_manifest.json")
        buf = BytesIO()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            with ZipFile(buf, "w", compression=ZIP_STORED) as z:
                z.writestr("bls_cpi_u_v1_original_response.json", raw)
                z.writestr("capture_manifest.json", manifest)
                z.writestr("capture_manifest.json", manifest)
        out = inspect(
            archive_zip=buf.getvalue(), reference_period="2026-09",
            decision_at_utc=CUTOFF)
        self.assertEqual(out["reason"], "DUPLICATE_OR_UNEXPECTED_ZIP_MEMBER")
        self.no_go(out)

    def test_incorrect_or_naive_dates_are_blocked(self):
        for when in (None, "2026-11-12T20:05:00Z",
                     datetime(2026, 11, 12, 20, 5),
                     datetime(2026, 11, 12, 20, 5, 0, 10, tzinfo=UTC)):
            with self.subTest(when=when):
                out = inspect(
                    archive_zip=archive(), reference_period="2026-09",
                    decision_at_utc=when)
                self.assertEqual(out["reason"], "INVALID_ARCHIVE_PERIOD_OR_DECISION")
                self.no_go(out)

    def test_wrong_series_and_non_zip_have_no_fallback(self):
        out = inspect(
            archive_zip=b"not an archive", reference_period="2026-09",
            decision_at_utc=CUTOFF)
        self.assertEqual(out["state"], "LAB_ARCHIVED_BLS_CPI_U_YOY_BLOCKED")
        self.assertIsNone(out["derived_yoy_percent_research_only"])
        self.no_go(out)


if __name__ == "__main__":
    unittest.main()
