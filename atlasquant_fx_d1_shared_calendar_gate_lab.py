"""AtlasQuant FX D1 cross-asset calendar completeness, offline LAB only.

Only the immutable FX_28 registry is accepted, in its exact canonical order.
Do not normalize misspelled symbols, whitespace or lowercase names.
The caller MUST supply a timezone-aware UTC as_of_utc; omitting it causes
an explicit BLOCKED report. No hidden system-clock, broker or network call.

A claimed server UTC offset (2 or 3 hours) is ONLY a calendar-boundary
hypothesis, never proof that a Pepperstone candle exists or is final.
Weekend server dates and Sunday-UTC/Monday-server boundary cases are
SUSPECT / CALENDAR UNAUTHENTICATED, not complete or automatically rejected.
The actual D1 candle roster and original server timestamps remain unverified.

Even on a complete weekday the report is only documentary: no broker
identity, live radar, trading permission, imputation or model probability.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

from atlasquant_instrument_registry import FX_28

SCHEMA = "ATLASQUANT_FX_D1_CROSS_ASSET_CALENDAR_GATE_LAB_V1"
SERVER_UTC_OFFSET_OPTIONS_HOURS = (2, 3)
SUSPECT_WEEKEND = "LAB_D1_WEEKEND_CALENDAR_SUSPECT_UNAUTHENTICATED"
SUSPECT_UTC_SERVER_BOUNDARY = (
    "LAB_D1_UTC_SUNDAY_SERVER_MONDAY_SUSPECT_UNAUTHENTICATED"
)


def _valid_utc(value: Any) -> datetime | None:
    """Require an explicitly supplied UTC-aware datetime, not local time."""
    if type(value) is not datetime or value.tzinfo is None:
        return None
    try:
        return value if value.utcoffset() == timedelta(0) else None
    except (TypeError, ValueError, OverflowError):
        return None


def inspect_d1_date_coverage_lab(
    *, trading_date: Any, present_symbols: Any, expected_symbols: tuple[str, ...],
    as_of_utc: Any = None, server_utc_offset_hours: Any = None,
) -> dict[str, Any]:
    """Pure read-only historical-coverage audit; always LAB / AGUARDAR.

    as_of_utc is a logically required KEYWORD-ONLY input: default None is
    only to produce a BLOCKED result for accidental omissions instead of
    throwing a TypeError. It must carry an explicit UTC timezone.

    trading_date is a claimed D1 calendar DATE, not a verified MT5 bar stamp.
    An optional explicit GMT+2/+3 server offset allows at most the server's
    CURRENT date; if it is one day ahead of UTC, flag SUSPECT and never
    mark documentary coverage complete. No DST inference or broker IO.
    """
    result = {
        "schema": SCHEMA, "date": None,
        "status": "LAB_D1_CALENDAR_BLOCKED",
        "observed_count": 0, "missing_count": None,
        "missing_symbols": None, "rank_28fx_coverage_complete": False,
        "as_of_utc": None,
        "server_utc_offset_hours_claim": None,
        "server_calendar_clock_independently_verified": False,
        "server_day_ahead_of_utc_calendar": False,
        "weekend_server_calendar_suspect": False,
        "weekend_d1_bars_independently_verified": False,
        "trading_calendar_independently_verified": False,
        "historical_broker_source_independently_verified": False,
        "out_of_sample_accuracy_verified": False,
        "single_pair_backtest_authorized": False,
        "unrestricted_backtest_authorized": False,
        "imputation_allowed": False,
        "direction_probability": None,
        "operational_bias": "AGUARDAR", "trade_authorized": False,
        "publishable": False, "research_only": True,
    }
    now = _valid_utc(as_of_utc)
    if now is None:
        result["reason"] = "MISSING_OR_INVALID_AS_OF_UTC"
        return result
    result["as_of_utc"] = now.astimezone(timezone.utc).isoformat()
    if (server_utc_offset_hours is not None
            and (type(server_utc_offset_hours) is not int
                 or server_utc_offset_hours not in SERVER_UTC_OFFSET_OPTIONS_HOURS)):
        result["reason"] = "INVALID_OR_UNSUPPORTED_SERVER_UTC_OFFSET"
        return result
    result["server_utc_offset_hours_claim"] = server_utc_offset_hours
    if (type(trading_date) is not date
            or type(expected_symbols) is not tuple
            or expected_symbols != FX_28
            or not isinstance(present_symbols, (tuple, list, set, frozenset))
            or any(type(s) is not str for s in present_symbols)):
        result["reason"] = "INVALID_CALENDAR_OR_COHORT"
        return result

    utc_date = now.date()
    if trading_date > utc_date:
        if server_utc_offset_hours is None:
            result["reason"] = "SERVER_OFFSET_REQUIRED_TO_CHECK_UTC_FUTURE_DATE"
            return result
        # Only the EXPLICIT +2/+3 server calendar may allow the server
        # to have entered Monday while the UTC clock still says Sunday.
        # That is an *unverified date label*, NOT an observed D1 candle.
        server_date = (now + timedelta(hours=server_utc_offset_hours)).date()
        if trading_date > server_date:
            result["reason"] = "D1_DATE_AFTER_CLAIMED_SERVER_CALENDAR_NOW"
            return result
    present = list(present_symbols)
    if len(set(present)) != len(present) or not set(present).issubset(FX_28):
        result["reason"] = "UNKNOWN_OR_DUPLICATE_D1_SYMBOL"
        return result
    missing = [s for s in FX_28 if s not in present]
    n = len(present)
    result.update({
        "date": trading_date.isoformat(),
        "observed_count": n,
        "missing_count": len(missing),
        "missing_symbols": missing,
    })
    if trading_date.weekday() >= 5:
        # Even 28/28 purported D1 bars on Sat/Sun are NOT a verified
        # broker trading day. No permanent veto: historical provenance
        # might later explain the label, but not in this LAB.
        result["status"] = SUSPECT_WEEKEND
        result["reason"] = "WEEKEND_D1_SOURCE_CALENDAR_NOT_AUTHENTICATED"
        result["weekend_server_calendar_suspect"] = True
        return result
    if trading_date > utc_date:
        # e.g., Sunday 22:01Z + GMT+2 = Monday 00:01 server; or
        # Sunday 21:01Z + GMT+3 = Monday 00:01 server.
        # 28 synthetic entries do NOT prove a D1 close at the opening.
        result["status"] = SUSPECT_UTC_SERVER_BOUNDARY
        result["reason"] = "SERVER_MONDAY_WHILE_UTC_SUNDAY_NOT_CLOSED_D1"
        result["server_day_ahead_of_utc_calendar"] = True
        return result
    if n == 28:
        status = "LAB_ALL_28_D1_BARS_PRESENT_DOCUMENTARY_UNATTESTED"
        result["rank_28fx_coverage_complete"] = True
    elif n == 27:
        status = "LAB_SINGLE_PAIR_D1_MISSING_DATE_QUARANTINE"
    elif n == 0:
        status = "LAB_SHARED_28FX_NO_D1_BARS_CALENDAR_UNVERIFIED"
    else:
        status = "LAB_PARTIAL_D1_COHORT_CALENDAR_UNVERIFIED"
    result["status"] = status
    result["reason"] = "LOCAL_DATE_COVERAGE_ONLY_NOT_BROKER_SCHEDULE"
    return result


__all__ = ["SCHEMA", "inspect_d1_date_coverage_lab"]
