"""Optional one-shot archival receipt for BLS CPI-U HTTPS capture (LAB).

This component does not fetch anything unless its CLI is explicitly called
with --allow-one-get. No cron, publish, portfolio, alerts, paid sources, or
main-branch changes. A ZIP freezes original response bytes + a canonical
manifest, with a source hash and observed timestamps, into a unique file.
It is NOT a trusted first-release attestation, a historical PIT archive,
a verified YoY inflation number, or a directional signal.

Usage after review:
python -m atlasquant_trader_bls_cpi_u_capture_receipt_lab \
  --allow-one-get --output-dir /path/to/your/controlled/lab-directory

The public API can fail, reject clients, or have delayed/revised data. In
those cases the command fails closed and never archives fabricated values.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
from io import BytesIO
import json
import os
from pathlib import Path
import re
import sys
from typing import Any
from zipfile import BadZipFile, ZipFile, ZIP_STORED

from atlasquant_trader_bls_cpi_u_official_bytes_readonly_lab import (
    SERIES, URL, inspect_bls_cpi_u_v1_bytes_lab,
    fetch_bls_cpi_u_v1_readonly_lab,
)

SCHEMA = "ATLASQUANT_TRADER_BLS_CPI_U_SOURCE_RECEIPT_ZIP_LAB_V1"
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
ZIP_MAX_BYTES = 1_100_000


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_BLS_CPI_U_RECEIPT_BLOCKED",
        "reason": reason, "filename": None, "capture_manifest_json": None,
        "capture_bundle_zip": None, "capture_manifest_sha256": None,
        "source_sha256": None, "artifact_written": False,
        "source_is_original_bls_issuer_attested": False,
        "original_release_time_proven": False,
        "point_in_time_vintage_proven": False,
        "cpi_yoy_validated": False,
        "fx28_forecast_supported": False,
        "operational_bias": "AGUARDAR", "trade_authorized": False,
        "publishable": False, "live_alert_allowed": False,
        "scheduler_enabled": False, "worker_enabled": False,
        "research_only": True, "new_cost_brl": 0,
    }


def _parsed_clock(value: Any) -> datetime | None:
    if not isinstance(value, str) or len(value) > 40:
        return None
    try:
        t = datetime.fromisoformat(value)
        if t.utcoffset() is None:
            return None
        return t.astimezone(timezone.utc)
    except (TypeError, ValueError, OverflowError):
        return None


def prepare_bls_cpi_u_source_receipt_lab(*, fetched: Any) -> dict[str, Any]:
    """Validate the full, original BLS byte sequence and make one ZIP in memory.

    A caller may spoof a fetch report. The archive allows a later auditor to
    compare exactly the bytes and declared capture metadata with external logs.
    """
    out = _blocked("INVALID_OR_UNATTESTED_HTTP_CAPTURE")
    if (not isinstance(fetched, dict)
            or fetched.get("state") != "LAB_BLS_CPI_U_INDEX_BYTES_INSPECTED_UNATTESTED"
            or fetched.get("http_get_completed") is not True
            or type(fetched.get("http_requests")) is not int
            or fetched["http_requests"] != 1
            or fetched.get("source_url") != URL
            or fetched.get("series_id") != SERIES
            or fetched.get("measure") != "USD_CPI_U_INDEX_LEVEL_NOT_YOY"
            or fetched.get("original_source_bytes_retained_in_result") is not True
            or fetched.get("can_feed_fx28_directional_forecast") is not False
            or fetched.get("original_release_at_independently_attested") is not False):
        return out
    raw = fetched.get("original_source_bytes_in_memory")
    captured = _parsed_clock(fetched.get("captured_at_utc"))
    server = _parsed_clock(fetched.get("server_date_utc_claim"))
    digest = fetched.get("source_sha256")
    if (not isinstance(raw, bytes) or captured is None or server is None
            or not isinstance(digest, str) or HEX64.fullmatch(digest) is None
            or sha256(raw).hexdigest() != digest):
        out["reason"] = "SOURCE_BYTES_OR_CLOCK_CHANGED_AFTER_CAPTURE"
        return out
    checked = inspect_bls_cpi_u_v1_bytes_lab(
        original_bytes=raw, captured_at_utc=captured, server_date_at_utc=server)
    if (checked["state"] != "LAB_BLS_CPI_U_INDEX_BYTES_INSPECTED_UNATTESTED"
            or checked.get("source_sha256") != digest
            or checked["last_monthly_period_documentary"] !=
                fetched.get("last_monthly_period_documentary")
            or checked["last_index_level_documentary"] !=
                fetched.get("last_index_level_documentary")
            or checked["monthly_observation_count"] !=
                fetched.get("monthly_observation_count")):
        out["reason"] = "SOURCE_REPARSE_OR_SUMMARY_MISMATCH"
        return out
    manifest = {
        "schema": SCHEMA,
        "capture_method_claim": "BLS_PUBLIC_API_V1_SINGLE_SERIES_GET",
        "source_url": URL, "series_id": SERIES,
        "measurement": "CPI_U_NSA_MONTHLY_INDEX_LEVEL_NOT_YOY",
        "observed_local_utc_claim": captured.isoformat(),
        "http_server_date_utc_claim": server.isoformat(),
        "raw_response_sha256": digest,
        "raw_response_length_bytes": len(raw),
        "last_monthly_period_documentary": checked["last_monthly_period_documentary"],
        "last_index_level_documentary": checked["last_index_level_documentary"],
        "months_returned": checked["monthly_observation_count"],
        "first_publication_proven": False,
        "historical_vintage_proven": False,
        "official_yoy_validated": False,
        "fx28_directional_forecast_authorized": False,
        "research_only": True,
    }
    manifest_bytes = json.dumps(
        manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
    ).encode("ascii")
    buffer = BytesIO()
    with ZipFile(buffer, "w", compression=ZIP_STORED) as archive:
        archive.writestr("bls_cpi_u_v1_original_response.json", raw)
        archive.writestr("capture_manifest.json", manifest_bytes)
    zipped = buffer.getvalue()
    if len(zipped) > ZIP_MAX_BYTES:
        out["reason"] = "CAPTURE_ARCHIVE_TOO_LARGE"
        return out
    iso = captured.strftime("%Y%m%dT%H%M%SZ")
    out.update({
        "state": "LAB_BLS_CPI_U_SOURCE_ZIP_PREPARED_LOCAL_ONLY",
        "reason": "ORIGINAL_BYTES_BOUND_LOCALLY_EXTERNAL_FIRST_RELEASE_NOT_PROVEN",
        "filename": f"atlasquant_bls_cpi_u_{iso}_{digest[:12]}.zip",
        "capture_manifest_json": manifest_bytes.decode("ascii"),
        "capture_bundle_zip": zipped,
        "capture_manifest_sha256": sha256(manifest_bytes).hexdigest(),
        "source_sha256": digest,
    })
    return out


def save_bls_cpi_u_source_receipt_once_lab(
    *, prepared: Any, directory: Any,
) -> dict[str, Any]:
    """One exclusive new archive in an EXISTING, caller-selected directory."""
    out = _blocked("INVALID_PREPARED_ZIP_OR_OUTPUT_DIRECTORY")
    if (not isinstance(prepared, dict)
            or prepared.get("state") != "LAB_BLS_CPI_U_SOURCE_ZIP_PREPARED_LOCAL_ONLY"
            or not isinstance(directory, (str, Path))
            or not isinstance(prepared.get("filename"), str)
            or not re.fullmatch(r"atlasquant_bls_cpi_u_20\d{6}T\d{6}Z_[a-f0-9]{12}\.zip",
                                prepared["filename"])
            or not isinstance(prepared.get("capture_bundle_zip"), bytes)):
        return out
    blob = prepared["capture_bundle_zip"]
    if not 0 < len(blob) <= ZIP_MAX_BYTES:
        return out
    try:
        with ZipFile(BytesIO(blob), "r") as archive:
            if set(archive.namelist()) != {
                    "bls_cpi_u_v1_original_response.json", "capture_manifest.json"}:
                return out
            raw = archive.read("bls_cpi_u_v1_original_response.json")
            manifest_bytes = archive.read("capture_manifest.json")
            manifest = json.loads(manifest_bytes.decode("ascii"))
        if (sha256(raw).hexdigest() != prepared.get("source_sha256")
                or sha256(manifest_bytes).hexdigest() !=
                    prepared.get("capture_manifest_sha256")
                or manifest_bytes.decode("ascii") !=
                    prepared.get("capture_manifest_json")
                or manifest.get("raw_response_sha256") != sha256(raw).hexdigest()
                or manifest.get("raw_response_length_bytes") != len(raw)
                or manifest.get("schema") != SCHEMA):
            out["reason"] = "ALTERED_ZIP_MANIFEST_OR_SOURCE_BYTES"
            return out
    except (OSError, UnicodeError, ValueError, TypeError, KeyError, BadZipFile):
        out["reason"] = "BROKEN_OR_UNREADABLE_ARCHIVE"
        return out

    root = Path(directory)
    if not root.is_dir():
        out["reason"] = "OUTPUT_DIRECTORY_NOT_PREEXISTING"
        return out
    target = root / prepared["filename"]
    try:
        # O_EXCL ensures no existing original can be overwritten.
        descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        out["reason"] = "CAPTURE_ARCHIVE_ALREADY_EXISTS_NO_OVERWRITE"
        return out
    except OSError:
        out["reason"] = "OUTPUT_DIRECTORY_OR_PERMISSION_ERROR"
        return out
    try:
        with os.fdopen(descriptor, "wb") as sink:
            sink.write(blob)
            sink.flush()
            os.fsync(sink.fileno())
    except OSError:
        try:
            target.unlink()
        except OSError:
            pass
        out["reason"] = "CAPTURE_ARCHIVE_WRITE_FAILED"
        return out
    out.update({
        "state": "LAB_BLS_CPI_U_ORIGINAL_BYTES_ARCHIVED_LOCALLY_NO_GO",
        "reason": "ARCHIVED_LOCALLY_NOT_EXTERNAL_PROVENANCE_OR_FIRST_RELEASE",
        "filename": str(target),
        "source_sha256": prepared["source_sha256"],
        "capture_manifest_sha256": prepared["capture_manifest_sha256"],
        "artifact_written": True,
    })
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="One-shot BLS original CPI-U receipt (LAB)")
    parser.add_argument("--output-dir", required=True,
                        help="Existing controlled local directory; one ZIP, no overwrite")
    parser.add_argument("--allow-one-get", action="store_true",
                        help="Explicitly authorize one BLS public API HTTPS GET")
    args = parser.parse_args(argv)
    if not args.allow_one_get:
        print("LAB_BLOCKED: --allow-one-get required; no HTTP request.", file=sys.stderr)
        return 2
    fetched = fetch_bls_cpi_u_v1_readonly_lab()
    prepared = prepare_bls_cpi_u_source_receipt_lab(fetched=fetched)
    if prepared["state"] != "LAB_BLS_CPI_U_SOURCE_ZIP_PREPARED_LOCAL_ONLY":
        print(f"LAB_BLOCKED: {fetched.get('reason')} / {prepared['reason']}",
              file=sys.stderr)
        return 2
    saved = save_bls_cpi_u_source_receipt_once_lab(
        prepared=prepared, directory=args.output_dir)
    if not saved["artifact_written"]:
        print(f"LAB_BLOCKED: {saved['reason']}", file=sys.stderr)
        return 2
    print(f"LAB_ONLY original bytes: {saved['filename']}")
    print(f"SHA256: {saved['source_sha256']}")
    print("NO-GO: no original-release/PIT verification or FX signal.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ("SCHEMA", "prepare_bls_cpi_u_source_receipt_lab",
           "save_bls_cpi_u_source_receipt_once_lab", "main")
