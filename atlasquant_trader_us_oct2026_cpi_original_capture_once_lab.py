"""Opt-in, one-off capture and strict offline replay of October-2026 BLS CPI HTML.

This laboratory module only preserves original source bytes, HTTP metadata
claims and local SHA-256. It reuses the existing CPI October release text guard
instead of recognizing numbers with new regexes. Capture is POST-release and
cannot prove first-print availability or justify any Forex bias/trade.

No request without explicit --capture-official. At most ONE HTTPS GET without
redirect, retry, fallback, credentials or BLS API substitution. Retained bytes
are private LAB evidence; redistribution/publishing is not assumed licensed.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from atlasquant_trader_us_oct2026_cpi_release_text_guard_lab import (
    ClaimedBLSHtmlReceipt, URL, RELEASE_FLOOR_UTC,
    MAX_HTML_BYTES, inspect_bls_oct2026_release_text_lab,
)

SCHEMA = "ATLASQUANT_US_OCT2026_CPI_BLS_ORIGINAL_ONCE_LAB_V1"
RECEIPT_SCHEMA = "ATLASQUANT_US_OCT2026_CPI_BLS_ORIGINAL_RECEIPT_V1"
_ACCEPT = "LAB_BLS_HTML_MONTHLY_CONTEXT_UNATTESTED"
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_ARCHIVE = re.compile(r"US_BLS_CPI_OCT2026_(20[0-9]{6}T[0-9]{6}Z)_([0-9a-f]{12})\Z")
_CLOCK = re.compile(r"20[0-9]{2}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z\Z")
_KEYS = frozenset((
    "schema", "source_url", "final_url", "status_code", "content_type",
    "started_at_utc", "finished_at_utc", "body_bytes", "body_sha256",
    "method", "original_available_at_release_independently_attested",
))


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _utc(value: Any) -> datetime | None:
    if type(value) is not datetime or value.tzinfo is None or value.microsecond:
        return None
    try:
        return value.astimezone(timezone.utc) if value.utcoffset() is not None else None
    except (TypeError, ValueError, OverflowError):
        return None


def _stamp(value: datetime) -> str:
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_stamp(value: Any) -> datetime | None:
    if type(value) is not str or _CLOCK.fullmatch(value) is None:
        return None
    try:
        return _utc(datetime.fromisoformat(value.replace("Z", "+00:00")))
    except (ValueError, OverflowError, TypeError):
        return None


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_CPI_OCT2026_ORIGINAL_BLOCKED_NO_GO",
        "reason": reason, "source_url": URL, "capture_get_attempts": 0,
        "original_local_replayed": False, "documentary_headline_sa_mom_pct": None,
        "documentary_core_sa_mom_pct": None, "original_body_sha256": None,
        "original_body_bytes": None, "archive_directory_basename": None,
        "first_release_original_independently_attested": False,
        "publisher_first_seen_clock_independently_attested": False,
        "consensus_pre_release_authenticated": False,
        "month_oct2026_yoy_available": False,
        "macro_surprise_qualified": False, "fx_direction": None,
        "validated_fx_accuracy": None, "trade_authorized": False,
        "publishable": False, "scheduler_enabled": False,
        "worker_enabled": False, "operational_bias": "AGUARDAR",
        "original_672_campaign_slots_modified": False,
    }


def _reconcile(raw: Any, receipt: Any, *, as_of_utc: Any) -> dict[str, Any] | None:
    if (type(receipt) is not dict or set(receipt) != _KEYS
            or receipt.get("schema") != RECEIPT_SCHEMA
            or receipt.get("source_url") != URL or receipt.get("final_url") != URL
            or type(receipt.get("status_code")) is not int or receipt["status_code"] != 200
            or type(receipt.get("content_type")) is not str
            or receipt["content_type"].split(";")[0].strip().lower() != "text/html"
            or receipt.get("method") != "GET"
            or receipt.get("original_available_at_release_independently_attested") is not False
            or type(receipt.get("body_bytes")) is not int
            or type(receipt.get("body_sha256")) is not str
            or _SHA.fullmatch(receipt["body_sha256"]) is None
            or type(raw) is not bytes
            or not 100 <= len(raw) <= MAX_HTML_BYTES
            or len(raw) != receipt["body_bytes"]
            or sha256(raw).hexdigest() != receipt["body_sha256"]):
        return None
    start = _parse_stamp(receipt["started_at_utc"])
    end = _parse_stamp(receipt["finished_at_utc"])
    now = _utc(as_of_utc)
    if (start is None or end is None or now is None
            or not RELEASE_FLOOR_UTC <= start <= end <= now
            or (end-start).total_seconds() > 180):
        return None
    parsed = inspect_bls_oct2026_release_text_lab(
        raw_html=raw,
        receipt=ClaimedBLSHtmlReceipt(
            source_url=URL, http_status=200, content_type=receipt["content_type"],
            captured_at_utc=end, body_sha256_claim=receipt["body_sha256"]),
        as_of_utc=now,
    )
    if (type(parsed) is not dict or parsed.get("state") != _ACCEPT
            or parsed.get("operational_bias") != "AGUARDAR"
            or parsed.get("trade_authorized") is not False
            or parsed.get("publishable") is not False
            or parsed.get("headline_yoy_reported_missing_oct2025_baseline") is not True):
        return None
    return parsed


def replay_cpi_oct2026_original_lab(*, output_root: Any,
                                    archive_basename: Any,
                                    as_of_utc: Any) -> dict[str, Any]:
    out = _blocked("NO_VALID_LOCAL_BLS_CPI_ORIGINAL_REPLAY")
    now = _utc(as_of_utc)
    if (type(archive_basename) is not str
            or _ARCHIVE.fullmatch(archive_basename) is None
            or now is None):
        return out
    try:
        root = Path(output_root)
        if root.is_symlink() or not root.is_dir():
            return out
        folder = root / archive_basename
        body_path, receipt_path = folder / "original.html", folder / "receipt.json"
        if (folder.is_symlink() or not folder.is_dir()
                or body_path.is_symlink() or receipt_path.is_symlink()
                or not body_path.is_file() or not receipt_path.is_file()
                or not 100 <= body_path.stat().st_size <= MAX_HTML_BYTES
                or not 40 <= receipt_path.stat().st_size <= 4096):
            return out
        body = body_path.read_bytes()
        metadata = json.loads(receipt_path.read_text("utf-8"),
                              object_pairs_hook=_unique_pairs)
        parsed = _reconcile(body, metadata, as_of_utc=now)
        capture = _parse_stamp(metadata.get("finished_at_utc"))
        match = _ARCHIVE.fullmatch(archive_basename)
        if (parsed is None or capture is None or match is None
                or match.group(1) != capture.strftime("%Y%m%dT%H%M%SZ")
                or match.group(2) != sha256(body).hexdigest()[:12]):
            return out
        out.update({
            "state": "LAB_CPI_OCT2026_BLS_ORIGINAL_REPLAYED_POST_RELEASE_NO_GO",
            "reason": "SOURCE_BODY_PARSED_AND_LOCALLY_SHA_RECONCILED_NO_FIRST_SEEN",
            "original_local_replayed": True,
            "documentary_headline_sa_mom_pct":
                parsed["headline_oct2026_sa_mom_pct_body_claim"],
            "documentary_core_sa_mom_pct":
                parsed["core_oct2026_sa_mom_pct_body_claim"],
            "original_body_sha256": metadata["body_sha256"],
            "original_body_bytes": len(body),
            "archive_directory_basename": archive_basename,
            "source_capture_claim_utc": metadata["finished_at_utc"],
        })
    except (OSError, TypeError, ValueError, UnicodeError, OverflowError, RuntimeError):
        return _blocked("NO_VALID_LOCAL_BLS_CPI_ORIGINAL_REPLAY")
    return out


def _unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("DUPLICATE_RECEIPT_JSON_KEY")
        result[key] = value
    return result


def capture_cpi_oct2026_original_once_lab(
    *, allow_one_get: Any, output_root: Any,
    open_url: Callable[..., Any] | None = None,
    clock: Callable[[], datetime] = _now,
) -> dict[str, Any]:
    out = _blocked("MANUAL_OPT_IN_REQUIRED")
    if allow_one_get is not True:
        return out
    out["reason"] = "MISSING_OR_INVALID_EXISTING_OUTPUT_ROOT"
    try:
        root = Path(output_root)
        if root.is_symlink() or not root.is_dir():
            return out
    except (TypeError, OSError, ValueError):
        return out
    start = _utc(clock())
    if start is None or start < RELEASE_FLOOR_UTC:
        out["reason"] = "INVALID_OR_PRE_RELEASE_CAPTURE_CLOCK"
        return out
    opener = open_url or build_opener(_NoRedirect()).open
    request = Request(URL, headers={
        "User-Agent": "AtlasQuantTrader-LAB-Research/1.0",
        "Accept": "text/html",
        "Accept-Encoding": "identity",
        "Connection": "close",
    }, method="GET")
    # This is the ONLY outbound request: no retry, redirect, fallback.
    out["capture_get_attempts"] = 1
    try:
        with opener(request, timeout=15) as response:
            status = response.status
            final_url = response.geturl()
            mime = response.headers.get("Content-Type", "")
            encoding = response.headers.get("Content-Encoding", "identity")
            length_header = response.headers.get("Content-Length")
            raw = response.read(MAX_HTML_BYTES + 1)
        finish = _utc(clock())
        if (type(status) is not int or status != 200 or final_url != URL
                or type(mime) is not str
                or mime.split(";")[0].strip().lower() != "text/html"
                or encoding not in ("", "identity")
                or finish is None or not start <= finish
                or (finish-start).total_seconds() > 180
                or type(raw) is not bytes or not 100 <= len(raw) <= MAX_HTML_BYTES
                or (length_header is not None
                    and (not str(length_header).isdigit()
                         or int(length_header) != len(raw)))):
            out["reason"] = "BLS_HTTP_OR_BODY_SIZE_OR_CAPTURE_TIME_INVALID"
            return out
        digest = sha256(raw).hexdigest()
        metadata = {
            "schema": RECEIPT_SCHEMA, "source_url": URL, "final_url": final_url,
            "status_code": status, "content_type": mime,
            "started_at_utc": _stamp(start), "finished_at_utc": _stamp(finish),
            "body_bytes": len(raw), "body_sha256": digest, "method": "GET",
            "original_available_at_release_independently_attested": False,
        }
        if _reconcile(raw, metadata, as_of_utc=finish) is None:
            out["reason"] = "BLS_CPI_BODY_SEMANTIC_PARSER_REJECTED"
            return out
        basename = "US_BLS_CPI_OCT2026_" + finish.strftime("%Y%m%dT%H%M%SZ") + "_" + digest[:12]
        target = root / basename
        target.mkdir(mode=0o700, exist_ok=False)
        with (target / "original.html").open("xb") as f:
            f.write(raw)
        with (target / "receipt.json").open("xb") as f:
            f.write((json.dumps(metadata, sort_keys=True, separators=(",", ":"))+"\n").encode("utf-8"))
        check = replay_cpi_oct2026_original_lab(
            output_root=root, archive_basename=basename, as_of_utc=finish)
        if not check["original_local_replayed"]:
            out["reason"] = "POST_WRITE_REPLAY_NOT_ACCEPTED"
            return out
        check["capture_get_attempts"] = 1
        return check
    except (OSError, HTTPError, URLError, TimeoutError, UnicodeError,
            ValueError, TypeError, OverflowError, RuntimeError) as exc:
        out["reason"] = "BLS_GET_OR_LOCAL_CAPTURE_FAILED_NO_FALLBACK"
        # Never claim successful retrieval on an HTTP or I/O exception.
        return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Single real BLS CPI October 2026 HTML capture (LAB)")
    parser.add_argument("--capture-official", action="store_true")
    parser.add_argument("--output-root", required=True)
    args = parser.parse_args(argv)
    result = capture_cpi_oct2026_original_once_lab(
        allow_one_get=args.capture_official, output_root=args.output_root)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["original_local_replayed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
