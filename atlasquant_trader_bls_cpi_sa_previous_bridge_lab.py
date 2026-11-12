"""Offline BLS CPI-U seasonally adjusted INDEX -> previous monthly context.

This is deliberately separate from CUUR0000SA0 (unadjusted index / YoY).
The API supplies mutable index levels without initial publication timestamps.
Computed percent change is NOT a verified first-print release, consensus,
event prediction, or directional FX/index bias. No HTTP is performed.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from hashlib import sha256
import json
import re
from typing import Any

SCHEMA = "ATLASQUANT_TRADER_BLS_CPI_U_SA_PREVIOUS_MOM_BRIDGE_LAB_V1"
API_URL = "https://api.bls.gov/publicAPI/v1/timeseries/data/CUSR0000SA0"
SERIES_ID = "CUSR0000SA0"
MAX_BYTES = 128 * 1024
_MONTH = re.compile(r"20[0-9]{2}-(0[1-9]|1[0-2])\Z")
_INDEX = re.compile(r"[0-9]{1,4}(?:\.[0-9]{1,4})?\Z")


def _utc(v: Any) -> datetime | None:
    if (not isinstance(v, datetime) or v.tzinfo is None
            or v.utcoffset() is None or v.microsecond != 0):
        return None
    return v.astimezone(timezone.utc)


def _previous_month(month: str) -> str:
    y, m = int(month[:4]), int(month[5:])
    return f"{y - 1:04d}-12" if m == 1 else f"{y:04d}-{m - 1:02d}"


def _base(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_BLS_CPI_SA_BLOCKED", "reason": reason,
        "source": "US_BLS", "api_url_documentary": API_URL,
        "series_id": SERIES_ID,
        "series_semantics": "CPI_U_ALL_ITEMS_SA_INDEX_1982_84_100",
        "unit": "INDEX_LEVEL_NOT_MOM_PERCENT",
        "observed_at_utc_claim": None, "raw_response_sha256": None,
        "index_months": [], "missing_months": [],
        "latest_available_index_month": None,
        "latest_available_mom_sa_percent_derived": None,
        "target_period": None, "previous_period": None,
        "previous_mom_percent_documentary": None,
        "previous_mom_source_index_pair": None,
        "claimed_api_bytes_publisher_authenticated": False,
        "index_vintage_independently_verified": False,
        "actual_first_print_independently_verified": False,
        "observed_clock_independently_attested": False,
        "prior_month_bls_reported_change_verified": False,
        "consensus_before_release_verified": False,
        "valid_pre_event_forecast": False,
        "calibrated_direction_probability": None,
        "fx_bias": None, "index_bias": None, "operational_bias": "AGUARDAR",
        "publishable": False, "live_alert_allowed": False,
        "trade_authorized": False, "worker_enabled": False,
        "scheduler_enabled": False, "http_requests": 0,
        "file_writes": 0, "new_cost_brl": 0, "research_only": True,
    }


def parse_current_bls_cpi_sa_index_lab(
    raw: Any, *, observed_at_utc: Any,
) -> dict[str, Any]:
    """Parse untrusted BLS-API-shaped response; reject any data time travel."""
    out = _base("INVALID_CLOCK_OR_BYTES")
    observed = _utc(observed_at_utc)
    if observed is None or not isinstance(raw, bytes) or not 1 <= len(raw) <= MAX_BYTES:
        return out
    try:
        response = json.loads(raw)
    except (ValueError, UnicodeDecodeError, TypeError, RecursionError):
        return _base("INVALID_BLS_JSON")
    if (not isinstance(response, dict)
            or response.get("status") != "REQUEST_SUCCEEDED"
            or response.get("message") != []
            or not isinstance(response.get("Results"), dict)):
        return _base("BLS_STATUS_OR_MESSAGES_INVALID")
    series = response["Results"].get("series")
    if (not isinstance(series, list) or len(series) != 1
            or not isinstance(series[0], dict)
            or series[0].get("seriesID") != SERIES_ID):
        return _base("WRONG_BLS_SERIES_OR_CARDINALITY")
    data = series[0].get("data")
    if not isinstance(data, list) or not 1 <= len(data) <= 48:
        return _base("INVALID_BLS_DATA_ROWS")

    months: dict[str, Decimal] = {}
    missing: list[str] = []
    all_months: list[str] = []
    annual_average_years: set[str] = set()
    latest_flags = 0
    for row in data:
        if not isinstance(row, dict):
            return _base("INVALID_BLS_ROW")
        year, period, value = row.get("year"), row.get("period"), row.get("value")
        if (not isinstance(year, str) or re.fullmatch(r"20[0-9]{2}", year) is None
                or not isinstance(period, str)
                or re.fullmatch(r"M(0[1-9]|1[0-2]|13)", period) is None
                or not isinstance(value, str)):
            return _base("INVALID_BLS_PERIOD_OR_VALUE")
        is_annual = period == "M13"
        month = f"{year}-{period[1:]}"
        if (int(year) > observed.year
                or (not is_annual and month > observed.strftime("%Y-%m"))):
            return _base("BLS_MONTH_IN_FUTURE")
        if value != "-" and _INDEX.fullmatch(value) is None:
            return _base("INVALID_BLS_INDEX_DECIMAL")
        val = None
        if value != "-":
            try:
                val = Decimal(value)
            except InvalidOperation:
                return _base("INVALID_BLS_INDEX_DECIMAL")
            if not Decimal(0) < val < Decimal(10000):
                return _base("INVALID_BLS_INDEX_BOUNDS")
        footnotes = row.get("footnotes", [])
        if (not isinstance(footnotes, list) or len(footnotes) > 10
                or any(not isinstance(note, dict) for note in footnotes)):
            return _base("INVALID_BLS_FOOTNOTES")
        for note in footnotes:
            code = note.get("code", "")
            if not isinstance(code, str) or len(code) > 12:
                return _base("INVALID_BLS_FOOTNOTES")
        latest = row.get("latest")
        if latest is not None and latest != "true":
            return _base("INVALID_BLS_LATEST_MARKER")
        if is_annual:
            if year in annual_average_years or val is None or latest is not None:
                return _base("INVALID_ANNUAL_AVERAGE")
            annual_average_years.add(year)
            continue
        if month in all_months:
            return _base("DUPLICATED_BLS_MONTH")
        all_months.append(month)
        if val is None:
            if latest is not None:
                return _base("MISSING_BLS_INDEX_MUST_NOT_BE_LATEST")
            missing.append(month)
            continue
        months[month] = val
        if latest == "true":
            latest_flags += 1

    if (not months or all_months != sorted(all_months, reverse=True)
            or latest_flags > 1):
        return _base("BLS_MONTH_ORDER_OR_LATEST_INVALID")
    latest_month = max(months)
    if latest_flags and not any(
        isinstance(row, dict)
        and row.get("year") == latest_month[:4]
        and row.get("period") == "M" + latest_month[5:]
        and row.get("latest") == "true" for row in data
    ):
        return _base("BLS_LATEST_NOT_NEWEST_NONMISSING_MONTH")

    rows = []
    for month in sorted(months, reverse=True):
        prior = _previous_month(month)
        calculated = None
        if prior in months:
            calculated = str(((months[month] / months[prior] - 1) * 100).quantize(
                Decimal("0.1"), rounding=ROUND_HALF_UP))
        rows.append({
            "month": month, "index_level": str(months[month]),
            "month_before": prior,
            "derived_mom_sa_percent_rounded_documentary": calculated,
            "not_official_first_published_change": True,
        })
    out.update({
        "state": "LAB_BLS_SA_INDEX_CURRENT_RESPONSE_UNVERIFIED",
        "reason": "SA_INDEX_MUTABLE_NO_RELEASE_INSTANT_IN_API",
        "observed_at_utc_claim": observed.isoformat(),
        "raw_response_sha256": sha256(raw).hexdigest(),
        "index_months": rows, "missing_months": sorted(missing),
        "latest_available_index_month": latest_month,
        "latest_available_mom_sa_percent_derived": rows[0][
            "derived_mom_sa_percent_rounded_documentary"],
    })
    return out


def bridge_previous_cpi_sa_mom_before_event_lab(
    raw: Any, *, observed_at_utc: Any, forecast_captured_at_utc: Any,
    scheduled_release_at_utc: Any, as_of_utc: Any, target_period: Any,
) -> dict[str, Any]:
    """Use the latest *preceding* index month as documentary prior context."""
    out = _base("INVALID_PRERELEASE_CONTEXT_OR_SOURCE")
    observed, captured, release, now = (_utc(observed_at_utc),
                                       _utc(forecast_captured_at_utc),
                                       _utc(scheduled_release_at_utc),
                                       _utc(as_of_utc))
    if (observed is None or captured is None or release is None or now is None
            or not observed <= captured < release or captured > now
            or not isinstance(target_period, str)
            or _MONTH.fullmatch(target_period) is None):
        return out
    parsed = parse_current_bls_cpi_sa_index_lab(raw, observed_at_utc=observed)
    if parsed["state"] != "LAB_BLS_SA_INDEX_CURRENT_RESPONSE_UNVERIFIED":
        return out
    previous = _previous_month(target_period)
    if parsed["latest_available_index_month"] != previous:
        out.update({
            "state": "LAB_BLS_SA_PREVIOUS_MONTH_UNAVAILABLE",
            "reason": "LATEST_CAPTURED_MONTH_IS_NOT_TARGET_PREVIOUS_MONTH",
            "target_period": target_period, "previous_period": previous,
            "raw_response_sha256": parsed["raw_response_sha256"],
        })
        return out
    month = parsed["index_months"][0]
    if month["derived_mom_sa_percent_rounded_documentary"] is None:
        out.update({
            "state": "LAB_BLS_SA_PREVIOUS_MONTH_UNAVAILABLE",
            "reason": "MONTH_BEFORE_PREVIOUS_REQUIRED_FOR_MOM",
            "target_period": target_period, "previous_period": previous,
            "raw_response_sha256": parsed["raw_response_sha256"],
        })
        return out
    out.update({
        "state": "LAB_BLS_SA_PREVIOUS_MOM_DOCUMENTARY_ONLY",
        "reason": "DERIVED_FROM_MUTABLE_SA_INDEX_NOT_ATTESTED_FIRST_PRINT",
        "observed_at_utc_claim": observed.isoformat(),
        "raw_response_sha256": parsed["raw_response_sha256"],
        "target_period": target_period, "previous_period": previous,
        "previous_mom_percent_documentary": month[
            "derived_mom_sa_percent_rounded_documentary"],
        "previous_mom_source_index_pair": [
            {"month": previous, "index_level": month["index_level"]},
            {"month": month["month_before"], "index_level": next(
                v["index_level"] for v in parsed["index_months"]
                if v["month"] == month["month_before"]
            )},
        ],
    })
    return out


__all__ = [
    "SCHEMA", "SERIES_ID", "API_URL", "parse_current_bls_cpi_sa_index_lab",
    "bridge_previous_cpi_sa_mom_before_event_lab",
]
