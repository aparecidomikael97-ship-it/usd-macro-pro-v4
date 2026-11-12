"""Offline-only tests of BLS source-byte custody. No live HTTP calls."""
from datetime import datetime, timezone
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile, ZIP_STORED

from atlasquant_trader_bls_cpi_u_official_bytes_readonly_lab import (
    inspect_bls_cpi_u_v1_bytes_lab as inspect,
)
from atlasquant_trader_bls_cpi_u_capture_receipt_lab import (
    prepare_bls_cpi_u_source_receipt_lab as prepare,
    save_bls_cpi_u_source_receipt_once_lab as save,
    main,
)

UTC = timezone.utc
AT = datetime(2026, 11, 12, 19, 31, tzinfo=UTC)


def fetched():
    original = json.dumps({
        "status": "REQUEST_SUCCEEDED",
        "Results": [{"series": [{"seriesID": "CUUR0000SA0", "data": [
            {"year": "2026", "period": "M09", "value": "325.000"},
            {"year": "2026", "period": "M08", "value": "324.125"},
        ]}]}],
    }, sort_keys=True, separators=(",", ":")).encode("ascii")
    report = inspect(original_bytes=original,
                     captured_at_utc=AT,
                     server_date_at_utc=AT)
    assert report["state"] == "LAB_BLS_CPI_U_INDEX_BYTES_INSPECTED_UNATTESTED"
    report["http_get_completed"] = True
    report["http_requests"] = 1
    return report


class BlsSourceReceiptZipTests(unittest.TestCase):
    def safe(self, result):
        for key in ("source_is_original_bls_issuer_attested",
                    "original_release_time_proven",
                    "point_in_time_vintage_proven", "cpi_yoy_validated",
                    "fx28_forecast_supported", "publishable",
                    "trade_authorized", "live_alert_allowed",
                    "scheduler_enabled", "worker_enabled"):
            self.assertFalse(result[key], key)
        self.assertEqual(result["operational_bias"], "AGUARDAR")
        self.assertEqual(result["new_cost_brl"], 0)

    def test_receipt_contains_original_bytes_and_matching_canonical_manifest(self):
        report = fetched()
        out = prepare(fetched=report)
        self.assertEqual(out["state"],
                         "LAB_BLS_CPI_U_SOURCE_ZIP_PREPARED_LOCAL_ONLY")
        with ZipFile(BytesIO(out["capture_bundle_zip"])) as archive:
            names = set(archive.namelist())
            self.assertEqual(names, {
                "capture_manifest.json", "bls_cpi_u_v1_original_response.json"})
            original = archive.read("bls_cpi_u_v1_original_response.json")
            manifest_raw = archive.read("capture_manifest.json")
        manifest = json.loads(manifest_raw)
        self.assertEqual(original, report["original_source_bytes_in_memory"])
        self.assertEqual(sha256(original).hexdigest(), manifest["raw_response_sha256"])
        self.assertEqual(manifest["source_url"], report["source_url"])
        self.assertEqual(manifest["series_id"], "CUUR0000SA0")
        self.assertEqual(manifest["measurement"],
                         "CPI_U_NSA_MONTHLY_INDEX_LEVEL_NOT_YOY")
        self.assertFalse(manifest["historical_vintage_proven"])
        self.assertFalse(manifest["official_yoy_validated"])
        self.assertFalse(out["artifact_written"])
        self.safe(out)

    def test_missing_live_get_claim_is_blocked(self):
        report = fetched()
        for field, value in (("http_get_completed", False),
                             ("http_requests", 0),
                             ("series_id", "CUSR0000SA0"),
                             ("can_feed_fx28_directional_forecast", True)):
            with self.subTest(field=field):
                changed = dict(report, **{field: value})
                out = prepare(fetched=changed)
                self.assertEqual(out["state"], "LAB_BLS_CPI_U_RECEIPT_BLOCKED")
                self.safe(out)

    def test_original_bytes_or_hash_tampered_after_receipt_fails(self):
        report = fetched()
        for field, value in (
            ("original_source_bytes_in_memory", b'{"status":"REQUEST_SUCCEEDED"}'),
            ("source_sha256", "f" * 64),
            ("last_index_level_documentary", "999.000"),
            ("monthly_observation_count", 3),
        ):
            with self.subTest(field=field):
                out = prepare(fetched=dict(report, **{field: value}))
                self.assertEqual(out["state"], "LAB_BLS_CPI_U_RECEIPT_BLOCKED")
                self.safe(out)

    def test_fake_or_naive_capture_time_fails(self):
        report = fetched()
        for value in ("2026-11-12T19:31:00", "bogus", "2026-11-12T19:42:00+00:00"):
            with self.subTest(value=value):
                out = prepare(fetched=dict(report, captured_at_utc=value))
                self.assertEqual(out["state"], "LAB_BLS_CPI_U_RECEIPT_BLOCKED")
                self.safe(out)

    def test_save_one_zip_exclusively_and_never_overwrite(self):
        out = prepare(fetched=fetched())
        with tempfile.TemporaryDirectory() as tmp:
            first = save(prepared=out, directory=tmp)
            self.assertTrue(first["artifact_written"])
            path = Path(first["filename"])
            self.assertTrue(path.is_file())
            self.assertEqual(path.read_bytes(), out["capture_bundle_zip"])
            first_bytes = path.read_bytes()
            second = save(prepared=out, directory=tmp)
            self.assertEqual(second["reason"],
                             "CAPTURE_ARCHIVE_ALREADY_EXISTS_NO_OVERWRITE")
            self.assertFalse(second["artifact_written"])
            self.assertEqual(path.read_bytes(), first_bytes)
            self.safe(first)
            self.safe(second)

    def test_no_directory_created_implicitly(self):
        prepared = prepare(fetched=fetched())
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "missing-folder"
            report = save(prepared=prepared, directory=path)
            self.assertEqual(report["reason"], "OUTPUT_DIRECTORY_NOT_PREEXISTING")
            self.assertFalse(path.exists())
            self.safe(report)

    def test_bad_zip_and_tampered_manifest_rejected_before_file_creation(self):
        out = prepare(fetched=fetched())
        for mutation in (
            dict(out, capture_bundle_zip=b"not-a-zip"),
            dict(out, capture_manifest_sha256="a" * 64),
            dict(out, source_sha256="b" * 64),
        ):
            with self.subTest(mutation=list(mutation)):
                with tempfile.TemporaryDirectory() as tmp:
                    report = save(prepared=mutation, directory=tmp)
                    self.assertFalse(report["artifact_written"])
                    self.assertEqual(list(Path(tmp).iterdir()), [])
                    self.safe(report)

    def test_forged_provenance_flag_with_rehashed_manifest_cannot_be_saved(self):
        receipt = prepare(fetched=fetched())
        with ZipFile(BytesIO(receipt["capture_bundle_zip"])) as archive:
            original = archive.read("bls_cpi_u_v1_original_response.json")
            manifest = json.loads(archive.read("capture_manifest.json"))
        # An attacker can re-hash their modified metadata; hashes alone are
        # never proof that "first publication verified" is an honest claim.
        for key in ("first_publication_proven", "historical_vintage_proven",
                    "official_yoy_validated", "fx28_directional_forecast_authorized"):
            with self.subTest(key=key):
                forged = dict(manifest, **{key: True})
                manifest_raw = json.dumps(
                    forged, sort_keys=True, separators=(",", ":"),
                    ensure_ascii=True).encode("ascii")
                buf = BytesIO()
                with ZipFile(buf, "w", compression=ZIP_STORED) as out:
                    out.writestr("bls_cpi_u_v1_original_response.json", original)
                    out.writestr("capture_manifest.json", manifest_raw)
                modified = dict(
                    receipt,
                    capture_bundle_zip=buf.getvalue(),
                    capture_manifest_json=manifest_raw.decode("ascii"),
                    capture_manifest_sha256=sha256(manifest_raw).hexdigest(),
                )
                with tempfile.TemporaryDirectory() as tmp:
                    result = save(prepared=modified, directory=tmp)
                    self.assertFalse(result["artifact_written"])
                    self.assertEqual(result["reason"],
                                     "ALTERED_ZIP_MANIFEST_OR_SOURCE_BYTES")
                    self.assertEqual(list(Path(tmp).iterdir()), [])
                    self.safe(result)

    def test_zip_duplicate_member_cannot_hide_under_a_set_of_names(self):
        receipt = prepare(fetched=fetched())
        with ZipFile(BytesIO(receipt["capture_bundle_zip"])) as archive:
            original = archive.read("bls_cpi_u_v1_original_response.json")
            manifest_raw = archive.read("capture_manifest.json")
        import warnings
        buf = BytesIO()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            with ZipFile(buf, "w", compression=ZIP_STORED) as out:
                out.writestr("bls_cpi_u_v1_original_response.json", original)
                out.writestr("capture_manifest.json", manifest_raw)
                out.writestr("capture_manifest.json", manifest_raw)
        modified = dict(receipt, capture_bundle_zip=buf.getvalue())
        with tempfile.TemporaryDirectory() as tmp:
            result = save(prepared=modified, directory=tmp)
            self.assertFalse(result["artifact_written"])
            self.assertEqual(result["reason"], "UNEXPECTED_OR_DUPLICATE_ARCHIVE_MEMBER")
            self.assertEqual(list(Path(tmp).iterdir()), [])
            self.safe(result)

    def test_valid_zip_under_false_receipt_filename_is_blocked(self):
        receipt = prepare(fetched=fetched())
        # Still looks like a permitted name but falsely claims a different UTC time.
        forged = dict(
            receipt,
            filename="atlasquant_bls_cpi_u_20261112T193200Z_" +
                     receipt["source_sha256"][:12] + ".zip",
        )
        with tempfile.TemporaryDirectory() as tmp:
            result = save(prepared=forged, directory=tmp)
            self.assertFalse(result["artifact_written"])
            self.assertEqual(result["reason"], "ALTERED_ZIP_MANIFEST_OR_SOURCE_BYTES")
            self.assertEqual(list(Path(tmp).iterdir()), [])
            self.safe(result)

    def test_path_traversal_not_permitted(self):
        out = prepare(fetched=fetched())
        out["filename"] = "../outside.zip"
        with tempfile.TemporaryDirectory() as tmp:
            report = save(prepared=out, directory=tmp)
            self.assertEqual(report["state"], "LAB_BLS_CPI_U_RECEIPT_BLOCKED")
            self.assertEqual(list(Path(tmp).iterdir()), [])
            self.safe(report)

    def test_cli_without_explicit_get_flag_never_fetches(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch(
                "atlasquant_trader_bls_cpi_u_capture_receipt_lab."
                "fetch_bls_cpi_u_v1_readonly_lab"
            ) as client:
                result = main(["--output-dir", tmp])
                client.assert_not_called()
            self.assertEqual(result, 2)
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_cli_on_provider_error_never_writes_or_fabricates_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch(
                "atlasquant_trader_bls_cpi_u_capture_receipt_lab."
                "fetch_bls_cpi_u_v1_readonly_lab",
                return_value={"state": "LAB_BLS_CPI_U_CAPTURE_BLOCKED",
                              "reason": "BLS_API_HTTPS_FETCH_FAILED_NO_FALLBACK"}
            ):
                code = main(["--output-dir", tmp, "--allow-one-get"])
            self.assertEqual(code, 2)
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_cli_mock_one_successful_provider_get_writes_only_one_zip(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch(
                "atlasquant_trader_bls_cpi_u_capture_receipt_lab."
                "fetch_bls_cpi_u_v1_readonly_lab", return_value=fetched()
            ) as client:
                code = main(["--output-dir", tmp, "--allow-one-get"])
                client.assert_called_once()
            self.assertEqual(code, 0)
            self.assertEqual(len(list(Path(tmp).iterdir())), 1)


if __name__ == "__main__":
    unittest.main()
