"""Bounded, public HTTPS capture of four GBP/NZD official 2026 releases.

LAB-only. Stores raw HTTP response bodies and an integrity manifest on the
collector's local machine. A real fetch-time hash is NOT a historical
publication-time archive, a trusted timestamp, or authorization for backtests.
Never touches MetaTrader, accounts, logins, trading, or financial orders.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from hashlib import sha256
import json
import os
from pathlib import Path
import re
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

SCHEMA = "ATLASQUANT_TRADER_GBP_NZD_OFFICIAL_HTTP_CAPTURE_LAB_V1"
MAX_BYTES = 2 * 1024 * 1024
TIMEOUT_SECONDS = 20
TARGETS = {
    "GBP_CPI_2026_09": "https://www.ons.gov.uk/economy/inflationandpriceindices/bulletins/consumerpriceinflation/september2026",
    "NZD_CPI_2026_Q3": "https://www.stats.govt.nz/information-releases/consumers-price-index-september-2026-quarter/",
    "GBP_BANK_RATE_2026_11": "https://www.bankofengland.co.uk/monetary-policy-summary-and-minutes/2026/november-2026",
    "NZD_OCR_2026_10": "https://www.rbnz.govt.nz/news-and-events/news/2026/10/ocr-held-at-2-75-percent",
}
SAFE_NAME = re.compile(r"[A-Z0-9_]+_20\d{6}T\d{6}Z_[0-9a-f]{12}\.html\Z")
HEX64 = re.compile(r"[0-9a-f]{64}\Z")


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _clock(value: datetime) -> str:
    return value.isoformat(timespec="seconds").replace("+00:00", "Z")


class SameHostHttpsRedirect(HTTPRedirectHandler):
    """Do not follow redirects to unrelated hosts or insecure HTTP."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        start, dest = urlsplit(req.full_url), urlsplit(newurl)
        if (dest.scheme != "https" or dest.hostname != start.hostname
                or dest.username or dest.password or dest.port not in (None, 443)):
            raise HTTPError(newurl, code, "Cross-host or insecure redirect refused", headers, fp)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def capture_one_lab(key: str, output_dir: Path, *, opener: Any = None) -> dict[str, Any]:
    """Write a unique body+receipt pair without overwriting earlier captures."""
    if key not in TARGETS:
        raise ValueError("Document must be in the four-item official allowlist")
    url = TARGETS[key]
    output_dir = Path(output_dir)
    if not output_dir.is_dir():
        raise ValueError("Output directory must exist before capture")
    opener = opener if opener is not None else build_opener(SameHostHttpsRedirect())
    request = Request(url, headers={
        "User-Agent": "AtlasQuant-LAB-public-research/1.0",
        "Accept-Encoding": "identity", "Accept": "text/html",
    })
    started = _now_utc()
    with opener.open(request, timeout=TIMEOUT_SECONDS) as response:
        code = response.status
        final = response.geturl()
        media = response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
        if (code != 200 or media != "text/html" or urlsplit(final).hostname != urlsplit(url).hostname
                or urlsplit(final).scheme != "https"):
            raise ValueError("Unexpected HTTP response, content type or final host")
        raw = response.read(MAX_BYTES + 1)
        date_header = response.headers.get("Date")
        last_modified = response.headers.get("Last-Modified")
    finished = _now_utc()
    if not 128 <= len(raw) <= MAX_BYTES:
        raise ValueError("Original response body absent or above size limit")
    digest = sha256(raw).hexdigest()
    filename = f"{key}_{finished:%Y%m%dT%H%M%SZ}_{digest[:12]}.html"
    body_path = output_dir / filename
    # Exclusive create: never replace earlier captures or revisions.
    with body_path.open("xb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    with body_path.open("rb") as handle:
        disk_raw = handle.read(MAX_BYTES + 1)
    if sha256(disk_raw).hexdigest() != digest:
        raise RuntimeError("Local readback SHA-256 failed")
    server_clock_delta_seconds = None
    if date_header:
        try:
            header_clock = parsedate_to_datetime(date_header).astimezone(timezone.utc)
            server_clock_delta_seconds = int((finished - header_clock).total_seconds())
        except (ValueError, TypeError, OverflowError):
            pass
    record = {
        "schema": SCHEMA, "document_id": key, "source_url": url,
        "final_url": final, "http_method": "GET", "http_status": code,
        "http_content_type": media, "http_date_header": date_header,
        "http_last_modified_header": last_modified,
        "local_capture_started_at_utc": _clock(started),
        "local_capture_finished_at_utc": _clock(finished),
        "local_clock_minus_server_date_seconds": server_clock_delta_seconds,
        "snapshot_filename": filename, "snapshot_bytes": len(raw),
        "snapshot_sha256": digest, "local_readback_hash_matched": True,
        "source_http_body_captured_now": True,
        "issuer_document_semantics_verified": False,
        "historical_vintage_at_original_release_verified": False,
        "independent_timestamp_authority_verified": False,
        "public_redistribution_rights_verified": False,
        "historical_backtest_authorized": False,
        "operational_bias": "AGUARDAR", "trade_authorized": False,
    }
    receipt_path = output_dir / (filename + ".receipt.json")
    with receipt_path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(record, handle, ensure_ascii=True, sort_keys=True, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    return record


def verify_capture_directory_lab(output_dir: Path) -> dict[str, Any]:
    """Verify original bytes still match each saved receipt, without network."""
    output_dir = Path(output_dir)
    if not output_dir.is_dir():
        raise ValueError("Capture directory not found")
    valid = 0
    failures = []
    recorded_names = set()
    for receipt_path in sorted(output_dir.glob("*.receipt.json")):
        try:
            with receipt_path.open("r", encoding="utf-8") as handle:
                record = json.load(handle)
            name = record["snapshot_filename"]
            if (record["schema"] != SCHEMA or record["document_id"] not in TARGETS
                    or record["source_url"] != TARGETS[record["document_id"]]
                    or not isinstance(name, str) or SAFE_NAME.fullmatch(name) is None
                    or receipt_path.name != name + ".receipt.json"
                    or not isinstance(record["snapshot_sha256"], str)
                    or HEX64.fullmatch(record["snapshot_sha256"]) is None):
                raise ValueError("Unexpected manifest metadata")
            path = output_dir / name
            recorded_names.add(name)
            if path.is_symlink() or not path.is_file():
                raise ValueError("Snapshot missing or unsafe link")
            with path.open("rb") as handle:
                raw = handle.read(MAX_BYTES + 1)
            if (len(raw) != record["snapshot_bytes"]
                    or sha256(raw).hexdigest() != record["snapshot_sha256"]):
                raise ValueError("Snapshot hash or size changed")
            valid += 1
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            failures.append({"receipt_file": receipt_path.name, "error": type(exc).__name__})
    for path in sorted(output_dir.glob("*.html")):
        if SAFE_NAME.fullmatch(path.name) is not None and path.name not in recorded_names:
            failures.append({"receipt_file": path.name, "error": "ORPHAN_SNAPSHOT_NO_RECEIPT"})
    status = ("LOCAL_INTEGRITY_FAIL" if failures else
              "LOCAL_INTEGRITY_PASS" if valid else "LOCAL_NO_RECEIPTS")
    return {"schema": SCHEMA, "status": status,
            "receipts_checked": valid + len(failures), "matched": valid,
            "failed": len(failures), "failures": failures,
            "independent_timestamp_authority_verified": False,
            "historical_backtest_authorized": False, "operational_bias": "AGUARDAR"}


def main() -> int:
    parser = argparse.ArgumentParser(description="AtlasQuant official public macro HTTP capture LAB")
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    if not args.output_dir.is_dir():
        parser.error("Create an explicit isolated LAB output folder first")
    if args.verify_only:
        result = verify_capture_directory_lab(args.output_dir)
        print(json.dumps(result, sort_keys=True))
        return 0 if result["status"] == "LOCAL_INTEGRITY_PASS" else 2
    count = 0
    for key in TARGETS:
        try:
            r = capture_one_lab(key, args.output_dir)
            print(json.dumps({"document_id": key, "result": "CAPTURED_RESEARCH_ONLY",
                              "bytes": r["snapshot_bytes"], "sha256": r["snapshot_sha256"],
                              "file": r["snapshot_filename"],
                              "utc": r["local_capture_finished_at_utc"]}, sort_keys=True))
            count += 1
        except (OSError, ValueError, RuntimeError, HTTPError) as exc:
            print(json.dumps({"document_id": key, "result": "CAPTURE_FAILED",
                              "error_type": type(exc).__name__}))
    result = verify_capture_directory_lab(args.output_dir)
    print(json.dumps(result, sort_keys=True))
    return 0 if count == len(TARGETS) and result["status"] == "LOCAL_INTEGRITY_PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
