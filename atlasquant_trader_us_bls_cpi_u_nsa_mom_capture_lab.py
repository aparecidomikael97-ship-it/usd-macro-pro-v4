"""Optional manual official BLS API v1 CPI-U NSA MONTH-OVER-MONTH capture.

CUUR0000SA0 = US city average, all items, CPI-U, NOT seasonally adjusted.
Two levels (Oct 2026 and Sep 2026) permit a DOCUMENTARY NSA MoM:
100 * (index_oct2026/index_sep2026 - 1). October 2025 CPI-U index was
NOT collected due to a federal funding lapse, according to the official
Nov 10 2026 release; Oct 2026 annual YoY is unavailable. NEVER invent it.
This is NOT a signed US Dollar
impact, release surprise, CPI consensus, authenticated first-release vintage,
or prediction before the November 2026 CPI publication.

No flag -> no network/files. With --capture-official: EXACTLY one GET to
the BLS public API v1 fixed series URL, no key/redirect/retry/fallback;
store actual HTTP body and strict receipt in an exclusive local LAB folder,
then read back raw bytes independently. --replay does read-only verification.
Official public endpoint may reject requests (403); DO NOT bypass it.
No MT5, FX prices, trades, background jobs, forecasts, or publication.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import stat
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

SCHEMA = "ATLASQUANT_TRADER_US_BLS_CPI_U_NSA_MOM_ORIGINAL_LAB_V2"
RECEIPT_SCHEMA = "ATLASQUANT_BLS_CPI_U_NSA_LOCAL_HTTP_RECEIPT_V1"
SERIES = "CUUR0000SA0"
URL = "https://api.bls.gov/publicAPI/v1/timeseries/data/CUUR0000SA0"
TARGET = "2026-10"
PREVIOUS = "2026-09"
MISSING_ANNUAL_BASE = "2025-10"
RELEASE_UTC = datetime(2026, 11, 10, 13, 30, tzinfo=timezone.utc)
OFFICIAL_MISSING_BASE_EXPLANATION = (
    "OCT2025_CPIU_INDEX_UNAVAILABLE_DUE_TO_2025_APPROPRIATIONS_LAPSE"
)
# Independently researched from BLS archived Oct 2026 first release,
# Table 1 "All items" (unadjusted index), Nov 10 2026.
# An index comparison proves numerical CONSISTENCY with this page only.
# It cannot prove the HTTP bytes' origin, receipt first-seen, or vintage.
ARCHIVED_RELEASE_URL = "https://www.bls.gov/news.release/archives/cpi_11102026.htm"
ARCHIVED_SEP2026_CPI_U_NSA_INDEX = Decimal("336.940")
ARCHIVED_OCT2026_CPI_U_NSA_INDEX = Decimal("337.511")
MAX_BYTES = 200_000
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_VAL = re.compile(r"(?:0|[1-9][0-9]{0,3})(?:\.[0-9]{1,3})?\Z")
_PERIOD = re.compile(r"M(?:0[1-9]|1[0-2])\Z")
_STAMP = re.compile(r"20[0-9]{2}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z\Z")
_ARCHIVE = re.compile(r"US_BLS_CPIU_NSA_(20[0-9]{6}T[0-9]{6}Z)_([0-9a-f]{12})\Z")
_RECEIPT_FIELDS = frozenset((
    "schema", "url", "final_url", "http_status", "content_type",
    "started_at_utc", "finished_at_utc", "raw_sha256", "body_bytes",
))


def _time(value: Any) -> datetime | None:
    if not isinstance(value, datetime) or value.tzinfo is None:
        return None
    try:
        if value.utcoffset() is None or value.microsecond:
            return None
        return value.astimezone(timezone.utc)
    except (TypeError, ValueError, OverflowError):
        return None


def _stamp(value: datetime) -> str:
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_stamp(value: Any) -> datetime | None:
    if type(value) is not str or _STAMP.fullmatch(value) is None:
        return None
    try:
        dt = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        return dt if _stamp(dt) == value else None
    except (ValueError, OverflowError):
        return None


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _base(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "LAB_US_BLS_CPI_U_NSA_DOCUMENT_NOT_VERIFIED_NO_GO",
        "reason": reason,
        "url": URL,
        "series_id": SERIES,
        "seasonal_adjustment": "NSA",
        "index_unit": "INDEX_LEVEL",
        "comparison": "MONTH_OVER_MONTH_NSA_FROM_TWO_MONTHLY_INDEX_LEVELS",
        "cpi_oct2026_yoy_unavailable_due_to_missing_oct2025": True,
        "oct2025_annual_base_missing_reason": OFFICIAL_MISSING_BASE_EXPLANATION,
        "earliest_official_release_utc": RELEASE_UTC.isoformat(),
        "target_month": TARGET,
        "base_month": PREVIOUS,
        "index_target_level_documentary": None,
        "index_base_level_documentary": None,
        "calculated_mom_nsa_pct_documentary": None,
        "calculated_yoy_pct_documentary": None,
        "calculation_is_not_official_bls_published_mom": True,
        "bls_archived_first_print_reference_url": ARCHIVED_RELEASE_URL,
        "bls_archived_sep2026_cpi_u_nsa_index": str(
            ARCHIVED_SEP2026_CPI_U_NSA_INDEX),
        "bls_archived_oct2026_cpi_u_nsa_index": str(
            ARCHIVED_OCT2026_CPI_U_NSA_INDEX),
        "local_api_index_levels_match_bls_archived_first_print": False,
        "release_index_crosscheck_not_issuer_or_first_seen_authentication": True,
        "raw_body_sha256": None,
        "archive_directory_basename": None,
        "raw_original_bytes_retained_and_replayed_local_only": False,
        "source_first_seen_independently_attested": False,
        "published_release_timestamp_independently_attested": False,
        "asof_historical_vintage_authenticated": False,
        "independent_pre_release_consensus_authenticated": False,
        "cpi_surprise_percentage_points": None,
        "usd_directional_impact": None,
        "fx28_direction_authorized": False,
        "calibrated_probability": None,
        "operational_bias": "AGUARDAR",
        "trade_authorized": False,
        "publishable": False,
        "live_alert_allowed": False,
        "worker_enabled": False,
        "scheduler_enabled": False,
        "http_get_attempts": 0,
        "file_writes_attempted": 0,
        "research_only": True,
        "new_cost_brl": 0,
    }


def _pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
    obj: dict[str, Any] = {}
    for name, value in items:
        if name in obj:
            raise ValueError("DUPLICATE_JSON_KEY")
        obj[name] = value
    return obj


def _no_nonfinite(s: str) -> None:
    raise ValueError("NONFINITE_NUMBER")


def _parse_original(body: Any, now: Any) -> dict[str, Any] | None:
    at = _time(now)
    if (type(body) is not bytes or not 100 <= len(body) <= MAX_BYTES
            or at is None or at < RELEASE_UTC):
        return None
    try:
        packet = json.loads(body.decode("utf-8"), object_pairs_hook=_pairs,
                            parse_constant=_no_nonfinite)
        if (type(packet) is not dict or packet.get("status") != "REQUEST_SUCCEEDED"
                or packet.get("message") != []
                or type(packet.get("Results")) is not list
                or len(packet["Results"]) != 1
                or type(packet["Results"][0]) is not dict):
            return None
        series = packet["Results"][0].get("series")
        if (type(series) is not list or len(series) != 1
                or type(series[0]) is not dict
                or series[0].get("seriesID") != SERIES
                or type(series[0].get("data")) is not list
                or not 2 <= len(series[0]["data"]) <= 48):
            return None
        values: dict[str, Decimal] = {}
        for item in series[0]["data"]:
            if (type(item) is not dict or type(item.get("year")) is not str
                    or type(item.get("period")) is not str):
                return None
            year, period = item["year"], item["period"]
            if not (len(year) == 4 and year.isascii() and year.isdigit()
                    and 2023 <= int(year) <= 2026):
                return None
            if period == "M13":  # annual average is not a month level
                continue
            if _PERIOD.fullmatch(period) is None:
                return None
            key = f"{year}-{period[1:]}"
            if key in values or key > f"{at.year:04d}-{at.month:02d}":
                return None
            val = item.get("value")
            if type(val) is not str or _VAL.fullmatch(val) is None:
                return None
            level = Decimal(val)
            if not level.is_finite() or not Decimal("0") < level < Decimal("1000"):
                return None
            flags = item.get("footnotes", [])
            if type(flags) is not list:
                return None
            # A preliminary or revised value cannot silently be a first-print.
            if any(type(flag) is not dict or flag.get("code")
                   not in (None, "",) for flag in flags):
                return None
            values[key] = level
        if TARGET not in values or PREVIOUS not in values:
            return None
        # 2025-10 is officially missing. A synthetic 2025-10 row (or a
        # revised later source) CANNOT restore the 2026 first-release YoY.
        if MISSING_ANNUAL_BASE in values:
            return None
        mom = ((values[TARGET] / values[PREVIOUS] - Decimal(1))
               * Decimal(100)).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
        if not mom.is_finite() or not -100 < mom < 100:
            return None
        matches_first_print_archive = (
            values[TARGET] == ARCHIVED_OCT2026_CPI_U_NSA_INDEX
            and values[PREVIOUS] == ARCHIVED_SEP2026_CPI_U_NSA_INDEX
        )
        return {
            "index_target_level_documentary": format(values[TARGET], "f"),
            "index_base_level_documentary": format(values[PREVIOUS], "f"),
            "calculated_mom_nsa_pct_documentary": format(mom, "f"),
            "calculated_yoy_pct_documentary": None,
            "local_api_index_levels_match_bls_archived_first_print":
                matches_first_print_archive,
        }
    except (ValueError, UnicodeError, OverflowError, TypeError,
            InvalidOperation, RecursionError, ZeroDivisionError):
        return None


def _lab_root(local_appdata: Any) -> Path | None:
    if type(local_appdata) is not str or not local_appdata:
        return None
    try:
        base = Path(local_appdata)
        if not base.is_absolute() or not base.is_dir():
            return None
        if any(p.is_symlink() for p in (base, *base.parents)):
            return None
        root = base
        for part in ("AtlasQuant", "LAB", "official_macro_receipts"):
            root = root / part
            if root.is_symlink() or (root.exists() and not root.is_dir()):
                return None
        if not root.resolve(strict=False).is_relative_to(base.resolve(strict=True)):
            return None
        return root
    except (ValueError, TypeError, OSError, RuntimeError):
        return None


def _validated(body: Any, meta: Any, observed: Any) -> dict[str, Any] | None:
    at = _time(observed)
    if (at is None or type(meta) is not dict or set(meta) != _RECEIPT_FIELDS
            or meta.get("schema") != RECEIPT_SCHEMA
            or meta.get("url") != URL or meta.get("final_url") != URL
            or type(meta.get("http_status")) is not int
            or meta["http_status"] != 200
            or type(meta.get("content_type")) is not str
            or meta["content_type"].split(";")[0].strip().lower()
               != "application/json"
            or type(meta.get("raw_sha256")) is not str
            or _SHA.fullmatch(meta["raw_sha256"]) is None
            or type(meta.get("body_bytes")) is not int
            or type(body) is not bytes
            or meta["body_bytes"] != len(body)
            or sha256(body).hexdigest() != meta["raw_sha256"]):
        return None
    start = _parse_stamp(meta.get("started_at_utc"))
    end = _parse_stamp(meta.get("finished_at_utc"))
    if (start is None or end is None or start > end or end > at
            or (end - start).total_seconds() > 180):
        return None
    return _parse_original(body, end)


def replay_bls_cpi_u_nsa_original_lab(
    *, local_appdata: Any, archive_basename: Any,
    observed_at_utc: Any,
) -> dict[str, Any]:
    out = _base("ORIGINAL_BLS_CPI_BYTES_OR_RECEIPT_NOT_AVAILABLE")
    root = _lab_root(local_appdata)
    if (root is None or type(archive_basename) is not str
            or _ARCHIVE.fullmatch(archive_basename) is None
            or _time(observed_at_utc) is None):
        return out
    try:
        folder = root / archive_basename
        if folder.is_symlink() or not folder.is_dir():
            return out
        source, receipt = folder/"original.json", folder/"receipt.json"
        if any(p.is_symlink() or not p.is_file()
               or not stat.S_ISREG(p.stat(follow_symlinks=False).st_mode)
               or p.stat(follow_symlinks=False).st_nlink != 1
               for p in (source, receipt)):
            return out
        if (not 100 <= source.stat().st_size <= MAX_BYTES
                or not 50 <= receipt.stat().st_size <= 4096):
            return out
        body = source.read_bytes()
        meta = json.loads(receipt.read_bytes().decode("utf-8"),
                          object_pairs_hook=_pairs, parse_constant=_no_nonfinite)
        match = _ARCHIVE.fullmatch(archive_basename)
        stamp = _parse_stamp(meta.get("finished_at_utc")) if type(meta) is dict else None
        if (match is None or stamp is None
                or match[1] != stamp.strftime("%Y%m%dT%H%M%SZ")
                or match[2] != sha256(body).hexdigest()[:12]):
            return out
        parsed = _validated(body, meta, observed_at_utc)
        if parsed is None:
            return out
        out.update({
            "state": "LAB_US_BLS_CPI_U_NSA_MOM_LOCAL_DOCUMENT_REPLAY_NO_GO",
            "reason": "TWO_NSA_MONTH_INDEX_LEVELS_RECONSTRUCTED_NOT_ISSUER_VINTAGE_PROOF",
            **parsed,
            "raw_body_sha256": sha256(body).hexdigest(),
            "archive_directory_basename": archive_basename,
            "raw_original_bytes_retained_and_replayed_local_only": True,
        })
    except (OSError, ValueError, TypeError, RuntimeError,
            UnicodeError, OverflowError, RecursionError):
        return _base("ORIGINAL_BLS_CPI_BYTES_OR_RECEIPT_NOT_AVAILABLE")
    return out


def _no_redirect():
    class NoRedirect(HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None
    return build_opener(NoRedirect())


def capture_bls_cpi_u_nsa_original_once_lab(
    *, allow_one_get: Any, local_appdata: Any,
    open_url: Callable[..., Any] | None = None,
    clock: Callable[[], datetime] = _now,
) -> dict[str, Any]:
    out = _base("EXPLICIT_ONE_GET_PERMISSION_REQUIRED")
    if allow_one_get is not True:
        return out
    out["reason"] = "NO_SAFE_LOCAL_ROOT_OR_CLOCK"
    if _lab_root(local_appdata) is None or not callable(clock):
        return out
    try:
        before = _time(clock())
        if before is None or before < RELEASE_UTC:
            return out
        request = Request(URL, headers={
            "Accept": "application/json",
            "Accept-Encoding": "identity",
            "User-Agent": "AtlasQuantTrader-LAB-Research/1.0",
        }, method="GET")
        out["http_get_attempts"] = 1
        out["reason"] = "BLS_API_ONE_GET_FAILED_OR_RESPONSE_REJECTED"
        opener = open_url if open_url is not None else _no_redirect().open
        with opener(request, timeout=15) as response:
            ctype = response.headers.get("Content-Type", "")
            encoding = response.headers.get("Content-Encoding", "identity")
            if (type(response.status) is not int or response.status != 200
                    or response.geturl() != URL
                    or type(ctype) is not str
                    or ctype.split(";")[0].strip().lower() != "application/json"
                    or type(encoding) is not str
                    or encoding.lower() != "identity"):
                return out
            original = response.read(MAX_BYTES+1)
            after = _time(clock())
            if (after is None or after < before
                    or (after-before).total_seconds() > 180
                    or _parse_original(original, after) is None):
                return out
        meta = {
            "schema": RECEIPT_SCHEMA,
            "url": URL,
            "final_url": URL,
            "http_status": 200,
            "content_type": ctype,
            "started_at_utc": _stamp(before),
            "finished_at_utc": _stamp(after),
            "raw_sha256": sha256(original).hexdigest(),
            "body_bytes": len(original),
        }
        if _validated(original, meta, after) is None:
            return out
        root = _lab_root(local_appdata)
        if root is None:
            out["reason"] = "LOCAL_ROOT_CHANGED_DURING_GET"
            return out
        folder = Path(local_appdata)
        for segment in ("AtlasQuant", "LAB", "official_macro_receipts"):
            folder = folder / segment
            if folder.is_symlink() or (folder.exists() and not folder.is_dir()):
                out["reason"] = "LAB_FOLDER_UNSAFE"
                return out
            if not folder.exists():
                os.mkdir(folder,0o700)
        name = ("US_BLS_CPIU_NSA_"
                + after.strftime("%Y%m%dT%H%M%SZ") + "_"
                + meta["raw_sha256"][:12])
        destination = root / name
        os.mkdir(destination,0o700)  # refuses existing archive, no overwrite
        out["archive_directory_basename"] = name
        for filename, content in (
            ("original.json", original),
            ("receipt.json", (
                json.dumps(meta,sort_keys=True,separators=(",",":"))+"\n"
            ).encode("utf-8")),
        ):
            fd = os.open(
                destination / filename,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                getattr(os,"O_NOFOLLOW",0), 0o600)
            out["file_writes_attempted"] += 1
            with os.fdopen(fd,"wb") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
        checked = replay_bls_cpi_u_nsa_original_lab(
            local_appdata=local_appdata,archive_basename=name,
            observed_at_utc=after)
        if not checked["raw_original_bytes_retained_and_replayed_local_only"]:
            out["reason"] = "SAVED_BUT_READBACK_FAILED_NO_REWRITE"
            return out
        out.update(checked)
        out["http_get_attempts"]=1
        out["file_writes_attempted"]=2
    except (OSError, HTTPError, URLError, ValueError, TypeError,
            RuntimeError, UnicodeError, OverflowError, RecursionError):
        out["reason"] = "API_GET_OR_LOCAL_STORAGE_FAILED_NO_RETRY"
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Manual official BLS CPI-U NSA MoM LAB")
    group = ap.add_mutually_exclusive_group()
    group.add_argument("--capture-official",action="store_true")
    group.add_argument("--replay",metavar="ARCHIVE_BASENAME")
    args=ap.parse_args(argv)
    if args.capture_official:
        report=capture_bls_cpi_u_nsa_original_once_lab(
            allow_one_get=True,local_appdata=os.environ.get("LOCALAPPDATA",""))
    elif args.replay:
        report=replay_bls_cpi_u_nsa_original_lab(
            local_appdata=os.environ.get("LOCALAPPDATA",""),
            archive_basename=args.replay,observed_at_utc=_now())
    else:
        report=_base("EXPLICIT_CAPTURE_OR_REPLAY_REQUIRED")
    print(json.dumps(report,indent=2,sort_keys=True,ensure_ascii=False))
    return 0 if report["raw_original_bytes_retained_and_replayed_local_only"] else 2


if __name__=="__main__":
    raise SystemExit(main())

__all__=("SCHEMA","SERIES","URL","capture_bls_cpi_u_nsa_original_once_lab",
         "replay_bls_cpi_u_nsa_original_lab")
