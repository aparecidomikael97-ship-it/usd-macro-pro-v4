"""Manual ONLY BLS October 2026 PPI source-byte capture and local replay.

One explicit --capture-official enables at most one GET, exact allowlisted
BLS archive HTTPS URL, no redirects/retries/cookies/keys/alternate sources.
Source HTML bytes are validated by EXISTING strict BLS Table-1 parser before
being stored in a dedicated LAB-only local directory with SHA256 receipt.
An independent read-only replay verifies bytes and JSON receipt later.

Capturing the post-event original today does NOT establish Nov-13 08:30 ET
first availability, historical point-in-time access, or a forecast. Neither
this module nor its output allows a USD direction or FX28 signal.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import stat
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from atlasquant_trader_us_ppi_oct2026_actual_table_guard_lab import (
    ClaimedPostReleaseHTTP, MAX_BYTES, OFFICIAL_URL, RELEASE_UTC,
    inspect_ppi_oct2026_first_print_lab,
)
from atlasquant_trader_us_ppi_oct2026_macro_context_lab import (
    _extract_ex_trade_actual_from_same_table1,
)

SCHEMA = "ATLASQUANT_TRADER_US_PPI_OCT2026_BLS_ORIGINAL_CAPTURE_LAB_V2"
RECEIPT_SCHEMA = "ATLASQUANT_US_PPI_OCT2026_BLS_LOCAL_RECEIPT_V1"
_ACCEPTED = "LAB_PPI_OCT2026_BLS_TABLE1_BODY_VALUES_UNATTESTED"
_ARCHIVE = re.compile(r"US_BLS_PPI_OCT2026_(20[0-9]{6}T[0-9]{6}Z)_([0-9a-f]{12})\Z")
_TS = re.compile(r"20[0-9]{2}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z\Z")
_SHA = re.compile(r"[a-f0-9]{64}\Z")
_FIELDS = frozenset((
    "schema", "source_url", "final_url", "status_code", "content_type",
    "started_at_utc", "finished_at_utc", "raw_sha256", "body_bytes",
))
_FOLDER = "official_macro_receipts"


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _clock(value: Any) -> datetime | None:
    if not isinstance(value, datetime) or value.tzinfo is None:
        return None
    try:
        if value.utcoffset() is None or value.microsecond:
            return None
        return value.astimezone(timezone.utc)
    except (ValueError, TypeError, OverflowError):
        return None


def _stamp(value: datetime) -> str:
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_stamp(value: Any) -> datetime | None:
    if type(value) is not str or _TS.fullmatch(value) is None:
        return None
    try:
        at = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc)
        return at if _stamp(at) == value else None
    except (ValueError, OverflowError):
        return None


def _base(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "LAB_US_PPI_OCT2026_ORIGINAL_CAPTURE_BLOCKED",
        "reason": reason,
        "source_url": OFFICIAL_URL,
        "capture_get_attempts": 0,
        "archive_directory_basename": None,
        "raw_document_bytes": 0,
        "raw_document_sha256": None,
        "documentary_series": [],
        "documentary_series_count": 0,
        "actuals_reconstructed_from_exact_local_bytes": False,
        "ppi_monthly_core_and_ex_trade_are_distinct_series": True,
        "consensus_pretended_from_bls_actual": False,
        "raw_bytes_and_receipt_replayed": False,
        "source_original_locally_retained_claim_only": False,
        "directory_created_once": False,
        "source_file_writes_attempted": 0,
        "release_first_seen_independently_verified": False,
        "bls_issuer_independently_authenticated": False,
        "release_pit_vintage_authenticated": False,
        "independent_pre_event_consensus_attested": False,
        "original_source_licensed_for_redistribution": False,
        "post_event_retrieval_not_pre_event_forecast": True,
        "ppi_can_feed_research_only": False,
        "ppi_can_feed_fx28_directional_model": False,
        "economic_impact_points": None,
        "usd_directional_bias": None,
        "calibrated_probability": None,
        "operational_bias": "AGUARDAR",
        "trade_authorized": False,
        "publishable": False,
        "live_alert_allowed": False,
        "worker_enabled": False,
        "scheduler_enabled": False,
        "new_cost_brl": 0,
        "research_only": True,
    }


def _lab_folder(local_appdata: Any) -> Path | None:
    if type(local_appdata) is not str or not local_appdata:
        return None
    try:
        base = Path(local_appdata)
        if not base.is_absolute() or not base.is_dir():
            return None
        if any(p.is_symlink() for p in (base, *base.parents)):
            return None
        atlas, lab = base / "AtlasQuant", base / "AtlasQuant" / "LAB"
        folder = lab / _FOLDER
        for part in (atlas, lab, folder):
            if part.is_symlink() or (part.exists() and not part.is_dir()):
                return None
        if not folder.resolve(strict=False).is_relative_to(base.resolve(strict=True)):
            return None
        return folder
    except (OSError, RuntimeError, TypeError, ValueError):
        return None


def _no_redirect():
    class NoRedirect(HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None
    return build_opener(NoRedirect())


def _strict_json_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for key, val in pairs:
        if key in values:
            raise ValueError("DUPLICATE_RECEIPT_FIELD")
        values[key] = val
    return values


def _no_constants(value: str) -> None:
    raise ValueError("NON_FINITE_RECEIPT_NUMBER")


def _check_bytes(body: Any, receipt: Any, asof: Any) -> dict[str, Any] | None:
    """Only existing byte/semantic guard; no independent issuer signature."""
    if (type(body) is not bytes or type(receipt) is not dict
            or set(receipt) != _FIELDS
            or receipt.get("schema") != RECEIPT_SCHEMA
            or receipt.get("source_url") != OFFICIAL_URL
            or receipt.get("final_url") != OFFICIAL_URL
            or type(receipt.get("status_code")) is not int
            or receipt["status_code"] != 200
            or type(receipt.get("content_type")) is not str
            or receipt["content_type"].split(";")[0].strip().lower() != "text/html"
            or type(receipt.get("raw_sha256")) is not str
            or _SHA.fullmatch(receipt["raw_sha256"]) is None
            or type(receipt.get("body_bytes")) is not int
            or receipt["body_bytes"] != len(body)
            or sha256(body).hexdigest() != receipt["raw_sha256"]):
        return None
    start = _parse_stamp(receipt.get("started_at_utc"))
    finish = _parse_stamp(receipt.get("finished_at_utc"))
    now = _clock(asof)
    if (start is None or finish is None or now is None
            or start < RELEASE_UTC or not start <= finish <= now
            or (finish-start).total_seconds() > 180):
        return None
    report = inspect_ppi_oct2026_first_print_lab(
        raw_html=body,
        receipt=ClaimedPostReleaseHTTP(
            source_url=OFFICIAL_URL,
            status_code=200,
            content_type=receipt["content_type"],
            started_utc=start, finished_utc=finish,
            raw_sha256=receipt["raw_sha256"]),
        as_of_utc=now,
    )
    if (type(report) is not dict or report.get("state") != _ACCEPTED
            or report.get("operational_bias") != "AGUARDAR"
            or report.get("trade_authorized") is not False
            or report.get("publishable") is not False):
        return None
    # FD/49116 is a SEPARATE ex-trade-services core, NOT FD/49104.
    # Require the unique original Table-1 row before any disk write.
    ex_trade = _extract_ex_trade_actual_from_same_table1(body)
    if ex_trade is None or not ex_trade.is_finite():
        return None
    return {**report, "_ex_trade_only_for_local_replay": str(ex_trade)}


def replay_oct2026_bls_original_capture_lab(
    *, local_appdata: Any, archive_basename: Any, observed_at_utc: Any,
) -> dict[str, Any]:
    """Read exactly named directory and SHA-check raw original; no fallback."""
    out = _base("LOCAL_PPI_ORIGINAL_NOT_FOUND_OR_UNVERIFIABLE")
    folder = _lab_folder(local_appdata)
    if (folder is None or type(archive_basename) is not str
            or _ARCHIVE.fullmatch(archive_basename) is None
            or _clock(observed_at_utc) is None):
        return out
    try:
        root = folder / archive_basename
        if root.is_symlink() or not root.is_dir():
            return out
        source = root / "original.html"
        metadata = root / "receipt.json"
        if (source.is_symlink() or metadata.is_symlink()
                or not source.is_file() or not metadata.is_file()
                or not stat.S_ISREG(source.stat(follow_symlinks=False).st_mode)
                or not stat.S_ISREG(metadata.stat(follow_symlinks=False).st_mode)
                or source.stat(follow_symlinks=False).st_nlink != 1
                or metadata.stat(follow_symlinks=False).st_nlink != 1
                or not 150 <= source.stat().st_size <= MAX_BYTES
                or not 40 <= metadata.stat().st_size <= 4096):
            return out
        body = source.read_bytes()
        meta = json.loads(metadata.read_bytes().decode("utf-8"),
                          object_pairs_hook=_strict_json_pairs,
                          parse_constant=_no_constants)
        if type(meta) is not dict or set(meta) != _FIELDS:
            return out
        match = _ARCHIVE.fullmatch(archive_basename)
        finish = _parse_stamp(meta.get("finished_at_utc"))
        if (match is None or finish is None
                or match[1] != finish.strftime("%Y%m%dT%H%M%SZ")
                or match[2] != sha256(body).hexdigest()[:12]):
            return out
        report = _check_bytes(body, meta, observed_at_utc)
        if report is None:
            return out
        # Source-bound values are read from the VERIFIED local original,
        # never from a caller-supplied dict or the journalist consensus.
        # This is documentary post-release data, not an impact score.
        parsed = (
            ("4", "Final demand",
             report["headline_final_demand_sa_mom_pct_body_claim"]),
            ("49104", "Final demand less foods and energy",
             report["core_ex_food_energy_sa_mom_pct_body_claim"]),
            ("49116", "Final demand less foods, energy, and trade services",
             report["_ex_trade_only_for_local_replay"]),
        )
        series = [{
            "issuer": "BLS", "country": "US",
            "series_label": label, "fd_commodity_code": code,
            "reference_period": "2026-10",
            "comparison_period": "2026-09",
            "change_type": "MONTH_OVER_MONTH",
            "seasonal_adjustment": "SA",
            "unit": "PERCENT_CHANGE",
            "actual_pct_local_documentary_claim": value,
            "actual_body_sha256": sha256(body).hexdigest(),
            "pre_event_consensus_pct": None,
            "surprise_percentage_points": None,
            "economic_impact_points": None,
            "issuer_first_seen_independently_attested": False,
            "pre_event_consensus_independently_attested": False,
        } for code, label, value in parsed]
        out.update({
            "state": "LAB_US_PPI_OCT2026_BLS_RAW_BYTES_REPLAYED_LOCAL_ONLY_NO_GO",
            "reason": "RAW_BLS_CANDIDATE_DOCUMENT_WITH_LOCAL_SHA_NOT_FIRST_SEEN",
            "archive_directory_basename": archive_basename,
            "raw_document_bytes": len(body),
            "raw_document_sha256": sha256(body).hexdigest(),
            "documentary_series": series,
            "documentary_series_count": len(series),
            "actuals_reconstructed_from_exact_local_bytes": True,
            "raw_bytes_and_receipt_replayed": True,
            "source_original_locally_retained_claim_only": True,
            "ppi_can_feed_research_only": True,
        })
    except (OSError, ValueError, TypeError, RuntimeError, OverflowError,
            UnicodeError, RecursionError):
        return _base("LOCAL_PPI_ORIGINAL_NOT_FOUND_OR_UNVERIFIABLE")
    return out


def capture_oct2026_bls_original_once_lab(
    *, allow_one_get: Any, local_appdata: Any,
    open_url: Callable[..., Any] | None = None,
    clock: Callable[[], datetime] = _now,
) -> dict[str, Any]:
    """One controlled post-release GET + durable-ish local save + readback.

    An existing archive directory is NEVER overwritten (including failed
    partial attempts). Not atomic or tamper-proof on Windows; strictly LAB.
    """
    out = _base("EXPLICIT_ALLOW_ONE_GET_REQUIRED")
    if allow_one_get is not True:
        return out
    out["reason"] = "LOCAL_LAB_ROOT_OR_TIME_INVALID"
    if _lab_folder(local_appdata) is None or not callable(clock):
        return out
    try:
        before = _clock(clock())
        if before is None or before < RELEASE_UTC:
            return out
    except (ValueError, TypeError, OverflowError, RuntimeError):
        return out
    request = Request(
        OFFICIAL_URL,
        headers={
            "Accept": "text/html",
            "Accept-Encoding": "identity",
            "User-Agent": "AtlasQuantTrader-LAB-Research/1.0",
        }, method="GET")
    out["capture_get_attempts"] = 1
    out["reason"] = "SOURCE_HTTPS_GET_OR_CONTENT_REJECTED_NO_FALLBACK"
    try:
        opener = open_url if open_url is not None else _no_redirect().open
        with opener(request, timeout=15) as response:
            content = response.headers.get("Content-Type", "")
            encoding = response.headers.get("Content-Encoding", "identity")
            if (type(response.status) is not int or response.status != 200
                    or response.geturl() != OFFICIAL_URL
                    or type(content) is not str
                    or content.split(";")[0].strip().lower() != "text/html"
                    or encoding.lower() != "identity"):
                return out
            body = response.read(MAX_BYTES+1)
            if not 150 <= len(body) <= MAX_BYTES:
                return out
            after = _clock(clock())
            if (after is None or not before <= after
                    or (after-before).total_seconds() > 180):
                return out
        receipt = {
            "schema": RECEIPT_SCHEMA,
            "source_url": OFFICIAL_URL,
            "final_url": OFFICIAL_URL,
            "status_code": 200,
            "content_type": content,
            "started_at_utc": _stamp(before),
            "finished_at_utc": _stamp(after),
            "raw_sha256": sha256(body).hexdigest(),
            "body_bytes": len(body),
        }
        parsed = _check_bytes(body, receipt, after)
        if parsed is None:
            out["reason"] = "OFFICIAL_BLS_BYTES_TABLE1_OR_TIME_NOT_ACCEPTED"
            return out
        folder = _lab_folder(local_appdata)
        if folder is None:
            out["reason"] = "LAB_ROOT_CHANGED_DURING_HTTPS_GET"
            return out
        # No directory is created until the original bytes pass the
        # strict issuer-specific PPI body parser.
        path = Path(local_appdata)
        for segment in ("AtlasQuant", "LAB", _FOLDER):
            path = path / segment
            if path.is_symlink() or (path.exists() and not path.is_dir()):
                out["reason"] = "LOCAL_LAB_PATH_CHANGED_OR_UNSAFE"
                return out
            if not path.exists():
                os.mkdir(path, 0o700)
        archive_name = (
            "US_BLS_PPI_OCT2026_"+after.strftime("%Y%m%dT%H%M%SZ")+
            "_"+receipt["raw_sha256"][:12])
        target = folder / archive_name
        os.mkdir(target, 0o700)  # O_EXCL-like directory creation; no overwrite
        out["directory_created_once"] = True
        out["archive_directory_basename"] = archive_name
        for filename, data in (
            ("original.html", body),
            ("receipt.json", (json.dumps(
                receipt, sort_keys=True, separators=(",", ":")
            )+"\n").encode("utf-8")),
        ):
            fd = os.open(
                target / filename,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                getattr(os, "O_NOFOLLOW", 0),
                0o600)
            out["source_file_writes_attempted"] += 1
            with os.fdopen(fd, "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
        checked = replay_oct2026_bls_original_capture_lab(
            local_appdata=local_appdata,
            archive_basename=archive_name,
            observed_at_utc=after)
        if not checked["raw_bytes_and_receipt_replayed"]:
            out["reason"] = "SAVED_BUT_READBACK_FAILED_MANUAL_REVIEW_REQUIRED"
            return out
        out.update(checked)
        out["capture_get_attempts"] = 1
        out["directory_created_once"] = True
        out["source_file_writes_attempted"] = 2
        return out
    except (OSError, ValueError, TypeError, UnicodeError, OverflowError,
            RuntimeError, RecursionError, HTTPError, URLError):
        out["reason"] = "CAPTURE_VALIDATE_OR_FILE_WRITE_FAILED_NO_RETRY"
        return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Manual BLS PPI October 2026 original-byte capture, NO-GO")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--capture-official", action="store_true",
                       help="One official HTTPS GET and local SHA receipt")
    group.add_argument("--replay", metavar="ARCHIVE_NAME",
                       help="Read-only verify explicitly named local archive")
    flags = parser.parse_args(argv)
    appdata = os.environ.get("LOCALAPPDATA", "")
    if flags.capture_official:
        report = capture_oct2026_bls_original_once_lab(
            allow_one_get=True, local_appdata=appdata)
    elif flags.replay is not None:
        report = replay_oct2026_bls_original_capture_lab(
            local_appdata=appdata, archive_basename=flags.replay,
            observed_at_utc=_now())
    else:
        report = _base("EXPLICIT_CAPTURE_OR_REPLAY_REQUIRED")
    print(json.dumps(report, sort_keys=True, indent=2, ensure_ascii=False))
    return 0 if report["raw_bytes_and_receipt_replayed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
