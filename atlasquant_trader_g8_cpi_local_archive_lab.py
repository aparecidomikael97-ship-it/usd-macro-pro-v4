"""Archive one CURRENT CPI HTTP response in a user-selected LAB directory.

Records integrity of an observation NOW, not issuer publication at release or
an independently synchronized historical data vintage. No MT5 or trading IO.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import sys
from typing import Any, Callable

from atlasquant_trader_g8_cpi_http_probe_lab import (
    HTTPProbeLabResult, MAX_BODY_BYTES, probe_g8_cpi_official_page_once_lab,
)
from atlasquant_trader_g8_macro_asof_lab import (
    CPI_FREQUENCY_2026_LAB, _cpi_issuer_claim_host,
)

SCHEMA = "ATLASQUANT_TRADER_G8_CPI_CURRENT_HTTP_ARCHIVE_LAB_V1"
_MONTH = re.compile(r"20\d\d-(?:0[1-9]|1[0-2])\Z")
_QUARTER = re.compile(r"20\d\d-Q[1-4]\Z")
_HEX = re.compile(r"[0-9a-f]{64}\Z")


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_ARCHIVE_BLOCKED", "reason": reason,
        "manifest_path": None, "body_path": None,
        "body_sha256": None, "body_bytes": 0,
        "local_integrity_verified": False,
        "issuer_first_release_authenticated": False,
        "clock_independently_authenticated": False,
        "historical_point_in_time_eligible": False,
        "economic_value_extracted": False,
        "operational_bias": "AGUARDAR", "trade_authorized": False,
        "publishable": False, "scheduler_enabled": False,
        "worker_enabled": False, "new_cost_brl": 0,
        "file_writes": 0,
    }


def _period_ok(currency: str, period: Any) -> bool:
    if not isinstance(period, str):
        return False
    return ((_QUARTER.fullmatch(period) is not None) if currency == "NZD"
            else (_MONTH.fullmatch(period) is not None))


def _read_report(result: Any, *, url: str) -> tuple[dict[str, Any], bytes] | None:
    if not isinstance(result, HTTPProbeLabResult) or not isinstance(result.report, dict):
        return None
    report, body = result.report, result.body
    if (not isinstance(body, bytes) or not 1 <= len(body) <= MAX_BODY_BYTES
            or report.get("state") != "LAB_CURRENT_ISSUER_PAGE_HTTP_BYTES_CAPTURED_UNATTESTED"
            or report.get("source_url_claim") != url
            or report.get("final_url_observed") != url
            or report.get("response_status") != 200
            or report.get("body_bytes") != len(body)
            or report.get("body_sha256") != sha256(body).hexdigest()
            or report.get("content_type") not in ("text/html", "application/pdf")):
        return None
    return report, body


def archive_one_g8_cpi_current_page_lab(
    currency: str, source_url: str, period: str, stage: str, *,
    directory: str | Path,
    probe: Callable[..., HTTPProbeLabResult] = probe_g8_cpi_official_page_once_lab,
) -> dict[str, Any]:
    """Create exactly two new files; reject collisions instead of overwriting."""
    out = _blocked("INVALID_CURRENCY_STAGE_URL_PERIOD_OR_DIRECTORY")
    if (not isinstance(currency, str) or currency not in CPI_FREQUENCY_2026_LAB
            or stage not in ("FLASH", "FINAL") or not _period_ok(currency, period)
            or _cpi_issuer_claim_host(currency, source_url) is None):
        return out
    try:
        candidate = Path(directory)
        if candidate.is_symlink():
            return out
        root = candidate.resolve(strict=True)
        if not root.is_dir():
            return out
    except (OSError, TypeError, ValueError):
        return out
    result = probe(currency, source_url)
    data = _read_report(result, url=source_url)
    if data is None:
        out["reason"] = "HTTP_PROBE_DID_NOT_RETURN_ACCEPTABLE_BYTES"
        return out
    report, body = data
    writes = 0
    try:
        finished = datetime.fromisoformat(report["local_finished_utc_claim"])
        if finished.tzinfo is None or finished.utcoffset() is None:
            return _blocked("UNUSABLE_LOCAL_CAPTURE_CLOCK_CLAIM")
        # The clock is NOT independently attested. This is only a filename.
        stamp = finished.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        digest = sha256(body).hexdigest()
        suffix = ".pdf" if report["content_type"] == "application/pdf" else ".html"
        basename = f"{currency}_CPI_{stage}_{period}_{stamp}_{digest[:12]}"
        body_path = root / (basename + suffix)
        manifest_path = root / (basename + ".manifest.json")
        if body_path.exists() or manifest_path.exists():
            out["reason"] = "CAPTURE_NAME_COLLISION_NO_OVERWRITE"
            return out
        manifest = {
            "schema": SCHEMA, "state": "LAB_CURRENT_RESPONSE_ARCHIVED_UNATTESTED",
            "currency": currency, "indicator": "CPI_YOY",
            "reference_period_claim": period, "publication_stage_claim": stage,
            "source_url": source_url, "body_filename": body_path.name,
            "body_bytes": len(body), "body_sha256": digest,
            "http_status": report["response_status"],
            "content_type": report["content_type"],
            "http_date_header": report.get("response_date_header"),
            "http_last_modified_header": report.get("last_modified_header"),
            "local_started_utc_claim": report.get("local_started_utc_claim"),
            "local_finished_utc_claim": report.get("local_finished_utc_claim"),
            "default_tls_verification_requested": report.get(
                "default_tls_verification_requested", False),
            "issuer_first_release_authenticated": False,
            "clock_independently_authenticated": False,
            "historical_point_in_time_eligible": False,
            "economic_value_extracted": False,
            "operational_bias": "AGUARDAR", "trade_authorized": False,
        }
        # Exclusive creation: never truncate user files or overwrite an earlier
        # observation. A crash between writes leaves a clearly incomplete pair.
        with body_path.open("xb") as f:
            f.write(body)
            f.flush()
            os.fsync(f.fileno())
        writes += 1
        with manifest_path.open("x", encoding="utf-8") as f:
            json.dump(manifest, f, sort_keys=True, indent=2)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        writes += 1
    except (OSError, ValueError, TypeError):
        out["reason"] = "ARCHIVE_IO_OR_METADATA_FAILED_REVIEW_DIRECTORY"
        out["file_writes"] = writes
        return out
    out.update({
        "state": "LAB_CURRENT_CPI_ARCHIVE_CREATED_UNATTESTED",
        "reason": "CURRENT_LOCAL_ARCHIVE_NOT_FIRST_RELEASE_PROOF",
        "manifest_path": str(manifest_path), "body_path": str(body_path),
        "body_sha256": digest, "body_bytes": len(body), "file_writes": 2,
    })
    return out


def verify_g8_cpi_current_archive_lab(manifest_path: str | Path) -> dict[str, Any]:
    """Reopen manifest and body; verify only local bytes, never original issuer."""
    out = _blocked("LOCAL_ARCHIVE_INVALID_OR_TAMPERED")
    try:
        requested = Path(manifest_path)
        if requested.is_symlink():
            return out
        manifest_path = requested.resolve(strict=True)
        with manifest_path.open("r", encoding="utf-8") as f:
            manifest = json.load(f)
        if (not isinstance(manifest, dict) or manifest.get("schema") != SCHEMA
                or manifest.get("state") != "LAB_CURRENT_RESPONSE_ARCHIVED_UNATTESTED"
                or not isinstance(manifest.get("body_filename"), str)):
            return out
        name = manifest["body_filename"]
        if (Path(name).name != name or "\\" in name or "/" in name):
            return out
        currency = manifest.get("currency")
        if (not isinstance(currency, str) or currency not in CPI_FREQUENCY_2026_LAB
                or not _period_ok(currency, manifest.get("reference_period_claim"))
                or manifest.get("publication_stage_claim") not in ("FLASH", "FINAL")
                or _cpi_issuer_claim_host(currency, manifest.get("source_url")) is None
                or manifest.get("issuer_first_release_authenticated") is not False
                or manifest.get("historical_point_in_time_eligible") is not False
                or manifest.get("trade_authorized") is not False):
            return out
        body_path = manifest_path.parent / name
        if not body_path.is_file() or body_path.is_symlink():
            return out
        length = manifest.get("body_bytes")
        digest = manifest.get("body_sha256")
        if (type(length) is not int or not 1 <= length <= MAX_BODY_BYTES
                or not isinstance(digest, str) or _HEX.fullmatch(digest) is None):
            return out
        with body_path.open("rb") as f:
            body = f.read(MAX_BODY_BYTES + 1)
        if len(body) != length or sha256(body).hexdigest() != digest:
            return out
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return out
    out.update({
        "state": "LAB_LOCAL_ARCHIVE_BYTES_SELF_CONSISTENT_UNATTESTED",
        "reason": "LOCAL_INTEGRITY_ONLY_NOT_PUBLISHER_RELEASE_ATTESTATION",
        "manifest_path": str(manifest_path), "body_path": str(body_path),
        "body_sha256": digest, "body_bytes": length,
        "local_integrity_verified": True,
    })
    return out


def main(argv: list[str]) -> int:
    if len(argv) != 6:
        print("Usage: python ...archive_lab.py EUR FLASH 2026-10 https://official-url C:/AtlasQuant/LAB")
        return 2
    _, currency, stage, period, url, directory = argv
    result = archive_one_g8_cpi_current_page_lab(
        currency, url, period, stage, directory=directory)
    if result["state"] == "LAB_CURRENT_CPI_ARCHIVE_CREATED_UNATTESTED":
        result["verification"] = verify_g8_cpi_current_archive_lab(result["manifest_path"])["state"]
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result.get("verification") == "LAB_LOCAL_ARCHIVE_BYTES_SELF_CONSISTENT_UNATTESTED" else 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))


__all__ = ["SCHEMA", "archive_one_g8_cpi_current_page_lab",
           "verify_g8_cpi_current_archive_lab"]
