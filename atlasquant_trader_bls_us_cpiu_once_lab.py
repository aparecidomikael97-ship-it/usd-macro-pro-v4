"""One-shot BLS CPI-U all-items NSA US city average INDEX (LAB).

No API key, no import-time network. Index levels CUUR0000SA0 are NOT CPI
inflation percentages. YoY is only calculated if the SAME month one year
earlier occurs in this response. This is a CURRENT mutable API response:
NO publication instants, consensus or point-in-time history are proved.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from hashlib import sha256
import json
from pathlib import Path
import re
import ssl
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, HTTPSHandler, build_opener
from zipfile import ZipFile, ZIP_STORED

from atlasquant_trader_g8_single_https_probe_lab import _RejectRedirect

SCHEMA = "ATLASQUANT_TRADER_US_BLS_CPIU_MONTHLY_INDEX_LAB_V1"
API_URL = "https://api.bls.gov/publicAPI/v1/timeseries/data/CUUR0000SA0"
SERIES_ID = "CUUR0000SA0"
MAX_BYTES = 128 * 1024
_MONTH = re.compile(r"M(0[1-9]|1[0-2])$")
_YEAR = re.compile(r"20[0-9]{2}$")
_INDEX = re.compile(r"[0-9]{1,4}(?:\.[0-9]{1,4})?$")


def _blocked(reason: str, *, attempted: bool = False) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_BLOCKED", "reason": reason,
        "currency": "USD", "source": "US_BLS", "series_id": SERIES_ID,
        "series_unit": "CPI_U_INDEX_1982_84_EQUALS_100",
        "seasonal_adjustment": "NOT_SEASONALLY_ADJUSTED",
        "external_http_requests": int(attempted), "current_http_response_observed": False,
        "individual_release_instant_verified": False,
        "prior_forecast_vintage_verified": False,
        "consensus_before_release_verified": False,
        "methodologically_comparable_to_EUROSTAT_HICP": False,
        "macro_causation_verified": False, "trade_authorized": False,
        "can_feed_live_radar": False, "publishable": False,
        "worker_enabled": False, "scheduler_enabled": False,
        "new_cost_brl": 0, "operational_bias": "AGUARDAR",
    }


def parse_current_bls_cpiu_lab(raw: Any, *, observed_at_utc: datetime) -> dict[str, Any]:
    """Pure parser; caller-supplied text is never publisher-authenticated."""
    if (not isinstance(observed_at_utc, datetime)
            or observed_at_utc.tzinfo is None
            or observed_at_utc.utcoffset() is None):
        raise ValueError("Timezone-aware collection clock required")
    if not isinstance(raw, bytes) or not 1 <= len(raw) <= MAX_BYTES:
        return _blocked("INVALID_RESPONSE_BYTES")
    try:
        obj = json.loads(raw)
    except (ValueError, UnicodeDecodeError, TypeError, OverflowError):
        return _blocked("INVALID_JSON")
    if not isinstance(obj, dict) or obj.get("status") != "REQUEST_SUCCEEDED":
        return _blocked("BLS_API_DID_NOT_SUCCEED")
    if obj.get("message") != []:
        return _blocked("BLS_API_MESSAGES_REQUIRE_REVIEW")
    results = obj.get("Results")
    if not isinstance(results, dict) or not isinstance(results.get("series"), list):
        return _blocked("BLS_SERIES_STRUCTURE_INVALID")
    series = results["series"]
    if len(series) != 1 or not isinstance(series[0], dict):
        return _blocked("BLS_EXPECTED_ONE_SERIES")
    one = series[0]
    if one.get("seriesID") != SERIES_ID or not isinstance(one.get("data"), list):
        return _blocked("BLS_WRONG_SERIES_OR_DATA")
    data = one["data"]
    if not 1 <= len(data) <= 48:
        return _blocked("BLS_ROW_COUNT_INVALID")
    months: dict[str, dict[str, Any]] = {}
    ordered = []
    annual_average_years: set[str] = set()
    seen_months: set[str] = set()
    missing_months: list[str] = []
    latest_claims = 0
    now = observed_at_utc.astimezone(timezone.utc)
    for row in data:
        if not isinstance(row, dict):
            return _blocked("BLS_ROW_NOT_OBJECT")
        year = row.get("year")
        period = row.get("period")
        value = row.get("value")
        if (not isinstance(year, str) or not _YEAR.fullmatch(year)
                or not isinstance(period, str)
                or (period != "M13" and not _MONTH.fullmatch(period))):
            return _blocked("BLS_YEAR_OR_MONTH_INVALID")
        is_annual_average = period == "M13"
        month = f"{year}-{period[1:]}"
        if (int(year) > now.year or (not is_annual_average and month > now.strftime("%Y-%m"))
                or month in seen_months):
            return _blocked("BLS_FUTURE_OR_DUPLICATED_MONTH")
        if not is_annual_average:
            seen_months.add(month)
        if not isinstance(value, str) or (value != "-" and not _INDEX.fullmatch(value)):
            return _blocked("BLS_INDEX_NOT_STRICT_DECIMAL_STRING")
        val = None
        if value != "-":
            try:
                val = Decimal(value)
            except (InvalidOperation, ValueError):
                return _blocked("BLS_INDEX_NOT_STRICT_DECIMAL_STRING")
            if not Decimal("0") < val < Decimal("10000"):
                return _blocked("BLS_INDEX_OUT_OF_BOUNDS")
        flags = row.get("footnotes", [])
        if (not isinstance(flags, list) or len(flags) > 10
                or any(not isinstance(flag, dict) for flag in flags)):
            return _blocked("BLS_FOOTNOTE_INVALID")
        notes = []
        for flag in flags:
            if not flag:
                continue
            code = flag.get("code", "")
            if not isinstance(code, str) or len(code) > 12:
                return _blocked("BLS_FOOTNOTE_INVALID")
            if code:
                notes.append(code)
        latest = row.get("latest")
        if latest is not None and latest != "true":
            return _blocked("BLS_LATEST_FLAG_INVALID")
        if val is None:
            # BLS can return "-" for missing data (e.g., Oct 2025).
            # Never convert missing into CPI=0 or a valid monthly index.
            if is_annual_average or latest is not None:
                return _blocked("BLS_MISSING_AVERAGE_OR_LATEST_VALUE")
            missing_months.append(month)
            continue
        if is_annual_average:
            # BLS documents M13 as an ANNUAL AVERAGE, not month 13.
            # Never use it as an inflation month or YoY denominator.
            if year in annual_average_years or latest is not None:
                return _blocked("BLS_ANNUAL_AVERAGE_INVALID")
            annual_average_years.add(year)
            continue
        if latest == "true":
            latest_claims += 1
        months[month] = {
            "month": month, "cpiu_index": str(val),
            "footnote_codes": notes,
            "latest_claimed_by_api": latest == "true",
            "not_proven_final": True,
        }
        ordered.append(month)
    if not ordered:
        return _blocked("BLS_NO_MONTHLY_OBSERVATIONS")
    if ordered != sorted(ordered, reverse=True) or latest_claims > 1:
        return _blocked("BLS_ORDER_OR_LATEST_FLAG_INVALID")
    if latest_claims and not months[ordered[0]]["latest_claimed_by_api"]:
        return _blocked("BLS_LATEST_FLAG_NOT_NEWEST_MONTH")
    recent = ordered[0]
    previous = f"{int(recent[:4])-1:04d}-{recent[5:]}"
    comparable = previous in months
    pct = None
    if comparable:
        latest_index = Decimal(months[recent]["cpiu_index"])
        older_index = Decimal(months[previous]["cpiu_index"])
        pct = str(((latest_index / older_index - 1) * 100).quantize(
            Decimal("0.0001"), rounding=ROUND_HALF_UP))
    out = _blocked("LATEST_MUTABLE_CPI_INDEX_NO_RELEASE_VINTAGE")
    out.update({
        "state": "LAB_CURRENT_US_BLS_CPIU_INDEX_QUARANTINED",
        "raw_response_sha256": sha256(raw).hexdigest(),
        "raw_response_bytes": len(raw),
        "observed_at_local_system_utc": now.isoformat(),
        "exact_series_id_checked": True,
        "observations": [months[key] for key in ordered],
        "observations_count": len(ordered),
        "bls_m13_annual_averages_ignored": len(annual_average_years),
        "explicit_missing_months_from_api_sentinel": sorted(missing_months),
        "missing_index_never_replaced_with_zero_or_interpolated": True,
        "annual_average_m13_is_not_monthly_observation": True,
        "latest_period": recent,
        "latest_index_value": months[recent]["cpiu_index"],
        "prior_year_same_month": previous,
        "prior_year_month_observed": comparable,
        "derived_yoy_percent_from_same_month_indices": pct,
        "derived_yoy_not_direct_official_bls_release_claim": True,
        "missing_comparable_month_yields_no_yoy": not comparable,
        "no_api_release_timestamps_available": True,
        "raw_snapshot_archive_path": None,
    })
    return out


def fetch_current_bls_cpiu_once_lab(
    *, manually_authorized: bool = False, timeout_seconds: int = 8,
    archive_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Exactly one opted-in GET; preserve raw bytes only with explicit folder."""
    if manually_authorized is not True:
        return _blocked("MANUAL_HTTP_OPT_IN_REQUIRED")
    if type(timeout_seconds) is not int or not 1 <= timeout_seconds <= 15:
        return _blocked("HTTP_TIMEOUT_OUT_OF_BOUNDS")
    req = Request(API_URL, method="GET", headers={
        "Accept": "application/json", "Accept-Encoding": "identity",
        "User-Agent": "AtlasQuant-Trader-LAB-one-shot-US-CPIU/1.0",
    })
    try:
        opener = build_opener(
            HTTPSHandler(context=ssl.create_default_context()), _RejectRedirect())
        with opener.open(req, timeout=timeout_seconds) as response:
            if response.status != 200 or response.geturl() != API_URL:
                return _blocked("HTTP_STATUS_OR_URL_INVALID", attempted=True)
            content_type = str(response.headers.get("Content-Type", "")).split(";")[0].strip().lower()
            if content_type != "application/json" or str(response.headers.get(
                    "Content-Encoding", "identity")).lower() != "identity":
                return _blocked("HTTP_RESPONSE_NOT_JSON_PLAIN", attempted=True)
            raw = response.read(MAX_BYTES + 1)
    except (HTTPError, URLError, OSError, ssl.SSLError, TimeoutError,
            ValueError, TypeError) as exc:
        return _blocked("HTTPS_FAILED_" + type(exc).__name__, attempted=True)

    captured = datetime.now(timezone.utc)
    parsed = parse_current_bls_cpiu_lab(raw, observed_at_utc=captured)
    parsed["external_http_requests"] = 1
    parsed["current_http_response_observed"] = True
    parsed["exact_url_requested"] = API_URL
    parsed["tls_default_ca_validation_requested"] = True
    parsed["http_redirects_followed"] = False
    if parsed["state"] != "LAB_CURRENT_US_BLS_CPIU_INDEX_QUARANTINED":
        return parsed
    if archive_dir is not None:
        try:
            directory = Path(archive_dir)
            if not directory.is_dir():
                return _blocked("SNAPSHOT_DIRECTORY_MISSING", attempted=True)
            stamp = captured.strftime("%Y%m%dT%H%M%S%fZ")
            filename = "bls_us_cpiu_" + stamp + "_" + sha256(raw).hexdigest()[:12] + ".zip"
            destination = directory / filename
            metadata = {k: v for k, v in parsed.items() if k != "raw_snapshot_archive_path"}
            with ZipFile(destination, mode="x", compression=ZIP_STORED) as archive:
                archive.writestr("response.json", raw)
                archive.writestr("observation_receipt.json", json.dumps(
                    metadata, ensure_ascii=False, sort_keys=True, indent=2))
            parsed["raw_snapshot_archive_path"] = str(destination)
            parsed["raw_snapshot_archive_sha256"] = sha256(destination.read_bytes()).hexdigest()
        except (OSError, ValueError, TypeError, RuntimeError):
            return _blocked("SNAPSHOT_ARCHIVE_FAILED", attempted=True)
    return parsed


__all__ = [
    "API_URL", "SERIES_ID", "parse_current_bls_cpiu_lab",
    "fetch_current_bls_cpiu_once_lab",
]
