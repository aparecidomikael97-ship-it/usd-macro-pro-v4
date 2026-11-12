"""Explicit, one-document manual CPI evidence capture for the user's own PC.

NO fetch on import, timer, retry, account, MT5 or trading. This function has
not been run against the live BLS/Reuters endpoints in this LAB environment.
The caller must explicitly opt in and select an already existing LAB folder.

A default-CA-validated HTTPS exchange plus local hash is useful provenance,
but NOT independent publisher identity/time, exact Reuters poll methodology,
historical P-I-T proof or a reason to generate an FX/index bias.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import ssl
import sys
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, HTTPSHandler, Request, build_opener

from atlasquant_trader_us_cpi_source_custody_lab import (
    CONSENSUS_ID, MAX_BODY_BYTES, OFFICIAL_PREVIOUS_PUBLICATION_CLAIM,
    OFFICIAL_PREVIOUS_URL, PREVIOUS_ID, RELEASE, RESEARCH_VISIBLE_AFTER,
    build_us_cpi_source_receipt_lab, inspect_us_cpi_source_receipt_lab,
)
from atlasquant_trader_us_oct2026_cpi_metric_availability_consensus_lab import REUTERS_URL


SCHEMA = "ATLASQUANT_TRADER_US_CPI_MANUAL_ONCE_CAPTURE_LAB_V1"
TIMEOUT_SECONDS = 12
SOURCE_CONFIG = {
    PREVIOUS_ID: (OFFICIAL_PREVIOUS_URL, OFFICIAL_PREVIOUS_PUBLICATION_CLAIM),
    # Reuters reports a Reuters economist poll; its article is NOT the raw poll
    # participant sheet. Conservative *date-only* publication boundary.
    CONSENSUS_ID: (REUTERS_URL, "2026-11-06T23:59:59Z"),
}
_FILENAME = re.compile(
    r"US_CPI_2026_(?:09_BLS_PREVIOUS|10_EXACT_EVENT_ANALYST_POLL)_20\d{6}T\d{6}Z_[a-f0-9]{12}\.html\Z"
)


class _RejectRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _stamp(now: datetime) -> str:
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Timezone-aware clock required")
    return now.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _blocked(reason: str, *, request_count: int = 0, file_writes: int = 0) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_MANUAL_CAPTURE_BLOCKED", "reason": reason,
        "external_http_requests": request_count, "file_writes": file_writes,
        "body_sha256": None, "body_bytes": None,
        "local_snapshot_filename": None, "local_receipt_filename": None,
        "default_ca_tls_requested": False, "redirects_followed": False,
        "http_response_headers_independently_authenticated": False,
        "publisher_origin_independently_attested": False,
        "collector_clock_independently_attested": False,
        "analyst_poll_methodology_verified": False,
        "document_numeric_contents_verified": False,
        "historical_pit_eligible": False, "ready_for_news_nowcast": False,
        "can_feed_live_radar": False, "fx_bias": None, "index_bias": None,
        "operational_bias": "AGUARDAR", "trade_authorized": False,
        "publishable": False, "worker_enabled": False, "scheduler_enabled": False,
        "new_cost_brl": 0,
    }


def _safe_directory(directory: Any) -> Path | None:
    if not isinstance(directory, (str, Path)) or not str(directory).strip():
        return None
    raw = Path(directory)
    try:
        is_junction = getattr(raw, "is_junction", lambda: False)()
        if (raw.is_symlink() or is_junction or not raw.is_dir()
                or len(raw.resolve().parts) < 3
                or raw.resolve() in (Path.home().resolve(), Path.cwd().resolve())):
            return None
        return raw
    except (OSError, ValueError, RuntimeError):
        return None


def capture_us_cpi_document_once_lab(
    source_id: Any, *, output_dir: Any, manual_one_shot: bool = False,
    opener: Any = None, clock: Callable[[], datetime] | None = None,
) -> dict[str, Any]:
    """Opt-in one exact HTTPS GET and exclusive local snapshot+receipt writes.

    Injected opener/clock are for offline tests; never proof of live capture.
    Nothing is deleted or overwritten, including on a partial write failure.
    """
    if manual_one_shot is not True:
        return _blocked("EXPLICIT_MANUAL_ONE_SHOT_OPT_IN_REQUIRED")
    if not isinstance(source_id, str) or source_id not in SOURCE_CONFIG:
        return _blocked("UNKNOWN_SOURCE_ID")
    folder = _safe_directory(output_dir)
    if folder is None:
        return _blocked("EXISTING_ISOLATED_REAL_FOLDER_REQUIRED")
    real_transport = opener is None
    if real_transport:
        opener = build_opener(
            HTTPSHandler(context=ssl.create_default_context()), _RejectRedirect())
    local_clock = clock or _utc_now
    url, published_claim = SOURCE_CONFIG[source_id]
    req = Request(url, method="GET", headers={
        "User-Agent": "AtlasQuantTrader-LAB-Manual-CPI-Snapshot/1.0",
        "Accept": "text/html", "Accept-Encoding": "identity",
    })
    writes = 0
    try:
        started = _stamp(local_clock())
        if datetime.fromisoformat(started.replace("Z", "+00:00")) < RESEARCH_VISIBLE_AFTER:
            return _blocked("RESEARCH_WINDOW_NOT_OPEN_YET")
        with opener.open(req, timeout=TIMEOUT_SECONDS) as response:
            status = response.status
            final_url = response.geturl()
            media = str(response.headers.get("Content-Type", "")).split(";", 1)[0].strip().lower()
            encoding = str(response.headers.get("Content-Encoding", "identity")).strip().lower()
            declared = response.headers.get("Content-Length")
            if (type(status) is not int or status != 200 or final_url != url
                    or media != "text/html" or encoding != "identity"
                    or declared is not None and (re.fullmatch(r"\d+", str(declared)) is None
                                                or not 1 <= int(declared) <= MAX_BODY_BYTES)):
                return _blocked("HTTP_URL_STATUS_OR_HEADER_MISMATCH", request_count=1)
            body = response.read(MAX_BODY_BYTES + 1)
        finished = _stamp(local_clock())
        if (not isinstance(body, bytes) or not 1 <= len(body) <= MAX_BODY_BYTES
                or declared is not None and len(body) != int(declared)):
            return _blocked("HTTP_BODY_TOO_LARGE_EMPTY_OR_LENGTH_MISMATCH", request_count=1)
        receipt = build_us_cpi_source_receipt_lab(
            source_id, body, source_url=url,
            published_at_claim_utc=published_claim,
            started_at_claim_utc=started, finished_at_claim_utc=finished,
        )
        if receipt.get("schema") != "ATLASQUANT_TRADER_US_CPI_NEWS_SOURCE_CUSTODY_LAB_V1":
            return _blocked("SOURCE_CUSTODY_BUILDER_REJECTED", request_count=1)
        # A capture *after* the release can still be archived, but must never
        # be presented as a pre-event forecast observation.
        now = datetime.fromisoformat(finished.replace("Z", "+00:00"))
        if now < RELEASE:
            checked = inspect_us_cpi_source_receipt_lab(
                receipt, as_of_utc=now, forecast_cutoff_utc=now)
            if checked["state"] != "LAB_BYTES_CONSISTENT_CLAIMED_PRERELEASE_CAPTURE_UNATTESTED":
                return _blocked("LOCAL_RECEIPT_FAILED_INSPECTION", request_count=1)
        digest = sha256(body).hexdigest()
        instant = finished.replace("-", "").replace(":", "")
        filename = f"{source_id}_{instant}_{digest[:12]}.html"
        receipt_filename = filename + ".receipt.json"
        with (folder / filename).open("xb") as f:
            f.write(body)
            f.flush()
            os.fsync(f.fileno())
        writes = 1
        with (folder / receipt_filename).open("xb") as f:
            f.write((json.dumps(receipt, ensure_ascii=True, sort_keys=True, indent=2)
                     + "\n").encode("utf-8"))
            f.flush()
            os.fsync(f.fileno())
        writes = 2
        # A successful write syscall alone is not a disk-readback check.
        raw_readback = (folder / filename).read_bytes()
        receipt_readback = json.loads((folder / receipt_filename).read_text("utf-8"),
                                      object_pairs_hook=_unique)
        if (raw_readback != body or receipt_readback != receipt
                or sha256(raw_readback).hexdigest() != digest):
            return _blocked("LOCAL_FILE_READBACK_MISMATCH", request_count=1,
                            file_writes=writes)
        result = _blocked("LOCALLY_HASHED_ONLY_NOT_INDEPENDENT_SOURCE_PROOF",
                          request_count=1, file_writes=writes)
        result.update({
            "state": "LAB_MANUAL_CAPTURE_SAVED_UNATTESTED",
            "source_id": source_id, "source_url": url,
            "local_capture_started_at_claim_utc": started,
            "local_capture_finished_at_claim_utc": finished,
            "local_snapshot_filename": filename,
            "local_receipt_filename": receipt_filename,
            "body_sha256": digest, "body_bytes": len(body),
            "local_file_readback_matched": True,
            "default_ca_tls_requested": real_transport,
            "research_capture_after_release": now >= RELEASE,
        })
        return result
    except (HTTPError, URLError, OSError, TimeoutError, ValueError,
            TypeError, AttributeError, OverflowError) as exc:
        result = _blocked("CAPTURE_FAILED_" + type(exc).__name__,
                          request_count=1, file_writes=writes)
        result["partial_snapshot_may_remain_for_manual_review"] = writes > 0
        return result


def verify_us_cpi_local_pair_lab(
    *, output_dir: Any, snapshot_filename: Any, as_of_utc: Any,
    forecast_cutoff_utc: Any,
) -> dict[str, Any]:
    """Read back only an exact pair of local files, without any network call."""
    out = _blocked("INVALID_OR_TAMPERED_LOCAL_PAIR")
    folder = _safe_directory(output_dir)
    if (folder is None or not isinstance(snapshot_filename, str)
            or _FILENAME.fullmatch(snapshot_filename) is None):
        return out
    body_path = folder / snapshot_filename
    receipt_path = folder / (snapshot_filename + ".receipt.json")
    try:
        if (body_path.is_symlink() or receipt_path.is_symlink()
                or not body_path.is_file() or not receipt_path.is_file()
                or body_path.stat().st_size > MAX_BODY_BYTES
                or receipt_path.stat().st_size > 2 * MAX_BODY_BYTES):
            return out
        body = body_path.read_bytes()
        with receipt_path.open("r", encoding="utf-8") as f:
            data = json.load(f, object_pairs_hook=_unique)
        checked = inspect_us_cpi_source_receipt_lab(
            data, as_of_utc=as_of_utc, forecast_cutoff_utc=forecast_cutoff_utc)
        if (checked["state"] != "LAB_BYTES_CONSISTENT_CLAIMED_PRERELEASE_CAPTURE_UNATTESTED"
                or not snapshot_filename.startswith(data["source_id"] + "_")
                or sha256(body).hexdigest() != data["captured_body_sha256"]):
            return out
        out.update({
            "state": "LAB_LOCAL_RAW_AND_RECEIPT_HASH_MATCH_UNATTESTED",
            "reason": "NO_INDEPENDENT_PUBLICATION_OR_CLOCK_WITNESS",
            "source_id": data["source_id"],
            "body_sha256": data["captured_body_sha256"],
            "body_bytes": len(body), "local_snapshot_filename": snapshot_filename,
            "local_receipt_filename": receipt_path.name,
        })
        return out
    except (OSError, ValueError, TypeError, KeyError, OverflowError, UnicodeError):
        return out


def _unique(items: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in items:
        if key in result:
            raise ValueError("Duplicate JSON field")
        result[key] = value
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AtlasQuant LAB: one manual CPI document fetch")
    parser.add_argument("--source-id", required=True, choices=sorted(SOURCE_CONFIG))
    parser.add_argument("--output-dir", required=True, help="existing isolated LAB directory")
    parser.add_argument("--manual-one-shot", action="store_true",
                        help="explicitly permit exactly one HTTPS GET; no timer/retry")
    args = parser.parse_args(argv)
    result = capture_us_cpi_document_once_lab(
        args.source_id, output_dir=args.output_dir,
        manual_one_shot=args.manual_one_shot,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0 if result["state"] == "LAB_MANUAL_CAPTURE_SAVED_UNATTESTED" else 2


if __name__ == "__main__":
    sys.exit(main())
