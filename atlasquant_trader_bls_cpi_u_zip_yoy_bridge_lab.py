"""LAB: read-only same-response CPI-U YoY calculation from a custody ZIP.

This is only a local integrity/chronology contract. The claimed HTTP capture
time, issuer provenance, original first publication, revisions and historical
point-in-time availability remain UNATTESTED. Never feed this output directly
into a 28-FX bias, trade, alert, portfolio or accuracy metric.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from io import BytesIO
import json
import re
from typing import Any
from zipfile import BadZipFile, ZipFile, ZIP_STORED

from atlasquant_trader_bls_cpi_u_capture_receipt_lab import (
    SCHEMA as ZIP_SCHEMA, ZIP_MAX_BYTES, _canonical_manifest, _parsed_clock,
)
from atlasquant_trader_bls_cpi_u_official_bytes_readonly_lab import (
    MAX_BODY_BYTES, SERIES, URL, inspect_bls_cpi_u_v1_bytes_lab,
)
from atlasquant_trader_us_bls_cpi_yoy_snapshot_lab import (
    interpret_bls_cpi_u_snapshot_lab,
)

SCHEMA = "ATLASQUANT_TRADER_BLS_CPI_U_ARCHIVED_SAME_BYTES_YOY_LAB_V1"
MONTH = re.compile(r"20\d\d-(?:0[1-9]|1[0-2])\Z")
MEMBERS = {"bls_cpi_u_v1_original_response.json", "capture_manifest.json"}


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "LAB_ARCHIVED_BLS_CPI_U_YOY_BLOCKED",
        "reason": reason,
        "source_url_claim": URL,
        "series_id": SERIES,
        "reference_period": None,
        "previous_year_reference_period": None,
        "derived_yoy_percent_research_only": None,
        "original_response_sha256_local": None,
        "capture_utc_claim": None,
        "decision_cutoff_utc": None,
        "zip_original_bytes_and_manifest_locally_consistent": False,
        "derived_from_two_months_of_same_original_response": False,
        "original_bls_issuer_attested": False,
        "first_publication_utc_independently_attested": False,
        "point_in_time_vintage_independently_attested": False,
        "validated_for_fx28_macro": False,
        "operational_bias": "AGUARDAR",
        "calibrated_direction_probability": None,
        "trade_authorized": False,
        "publishable": False,
        "live_alert_allowed": False,
        "scheduler_enabled": False,
        "worker_enabled": False,
        "http_requests": 0,
        "file_writes": 0,
        "new_cost_brl": 0,
        "research_only": True,
    }


def inspect_bls_cpi_u_archive_same_bytes_yoy_lab(
    *, archive_zip: Any, reference_period: Any, decision_at_utc: Any,
) -> dict[str, Any]:
    """Inspect an in-memory ZIP, enforcing local response and cutoff integrity.

    The decision cutoff is a *caller supplied* time, not a trusted historical
    witness. A locally intact ZIP never proves when those values were released.
    """
    out = _blocked("INVALID_ARCHIVE_PERIOD_OR_DECISION")
    if (not isinstance(archive_zip, bytes)
            or not 1 <= len(archive_zip) <= ZIP_MAX_BYTES
            or not isinstance(reference_period, str)
            or MONTH.fullmatch(reference_period) is None
            or not isinstance(decision_at_utc, datetime)
            or decision_at_utc.tzinfo is None
            or decision_at_utc.utcoffset() is None
            or decision_at_utc.microsecond):
        return out
    try:
        cutoff = decision_at_utc.astimezone(timezone.utc)
        with ZipFile(BytesIO(archive_zip), "r") as archive:
            members = archive.infolist()
            if (len(members) != 2
                    or {m.filename for m in members} != MEMBERS
                    or any(m.is_dir() or m.compress_type != ZIP_STORED
                           or m.file_size > (
                               MAX_BODY_BYTES if m.filename.startswith("bls_")
                               else 8_192) for m in members)):
                out["reason"] = "DUPLICATE_OR_UNEXPECTED_ZIP_MEMBER"
                return out
            original = archive.read("bls_cpi_u_v1_original_response.json")
            manifest_raw = archive.read("capture_manifest.json")
        manifest = json.loads(manifest_raw.decode("ascii"))
        if not isinstance(manifest, dict):
            out["reason"] = "ZIP_MANIFEST_NOT_CANONICAL"
            return out
        captured = _parsed_clock(manifest.get("observed_local_utc_claim"))
        server = _parsed_clock(manifest.get("http_server_date_utc_claim"))
        if captured is None or server is None:
            out["reason"] = "ZIP_INVALID_CAPTURE_CLOCK"
            return out
        if captured > cutoff:
            out["reason"] = "CAPTURE_AFTER_FORECAST_CUTOFF_LOOKAHEAD"
            return out
        checked = inspect_bls_cpi_u_v1_bytes_lab(
            original_bytes=original, captured_at_utc=captured,
            server_date_at_utc=server)
        if checked["state"] != "LAB_BLS_CPI_U_INDEX_BYTES_INSPECTED_UNATTESTED":
            out["reason"] = "ARCHIVED_BLS_BYTES_REJECTED"
            return out
        digest = sha256(original).hexdigest()
        canonical = _canonical_manifest(
            checked=checked, captured=captured, server=server,
            digest=digest, raw=original)
        canonical_raw = json.dumps(
            canonical, sort_keys=True, separators=(",", ":"),
            ensure_ascii=True).encode("ascii")
        if (manifest.get("schema") != ZIP_SCHEMA
                or manifest_raw != canonical_raw):
            out["reason"] = "ZIP_MANIFEST_NOT_CANONICAL"
            return out
    except (BadZipFile, OSError, UnicodeError, ValueError, TypeError,
            KeyError, OverflowError, RecursionError):
        out["reason"] = "ZIP_OR_ORIGINAL_BYTES_UNREADABLE"
        return out

    # Never use a future or same-month observation without demonstrated
    # release chronology. Month ceiling alone is NOT independent proof.
    if reference_period > f"{captured.year:04d}-{captured.month:02d}":
        out["reason"] = "REFERENCE_MONTH_AFTER_CAPTURE_MONTH"
        return out
    parsed = interpret_bls_cpi_u_snapshot_lab(
        original, reference_period=reference_period)
    if parsed["state"] != "LAB_BLS_CPI_U_DERIVED_YOY_FROM_MUTABLE_API_BYTES_UNATTESTED":
        out["reason"] = "SAME_BYTES_YOY_UNAVAILABLE_" + parsed["reason"]
        return out
    out.update({
        "state": "LAB_ARCHIVED_BLS_CPI_U_TWO_LEVEL_YOY_UNATTESTED",
        "reason": "LOCAL_CUSTODY_AND_ARITHMETIC_ONLY_NOT_FIRST_RELEASE_OR_PIT",
        "reference_period": reference_period,
        "previous_year_reference_period": parsed["previous_year_reference_period"],
        "derived_yoy_percent_research_only": parsed["derived_yoy_percent"],
        "original_response_sha256_local": digest,
        "capture_utc_claim": captured.isoformat(),
        "decision_cutoff_utc": cutoff.isoformat(),
        "zip_original_bytes_and_manifest_locally_consistent": True,
        "derived_from_two_months_of_same_original_response": True,
    })
    return out


__all__ = ("SCHEMA", "inspect_bls_cpi_u_archive_same_bytes_yoy_lab")
