"""Research-only FX D1/W1 time windows at 17:00 America/New_York.

D1: five active sessions, Sunday->Monday through Thursday->Friday.
W1: Sunday 17:00 through Friday 17:00 New York time.
This is a convention, NOT proof of broker sessions or holiday trading hours.
NY DST must be applied by IANA zoneinfo, not by a fixed EST/EDT offset.
"""
from __future__ import annotations
from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from typing import Any

SCHEMA = "ATLASQUANT_TRADER_FX_NY_CLOSE_WINDOW_LAB_V1"
NY = ZoneInfo("America/New_York")
CONVENTION = "FX_NY_1700_ROLLOVER_RESEARCH_NOT_BROKER_ATTESTED"


def _utc(value: Any) -> datetime | None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        return None
    return value.astimezone(timezone.utc)


def inspect_fx_ny_close_window_lab(
    *, horizon: Any, start_at_utc: Any, end_at_utc: Any,
) -> dict[str, Any]:
    """Fail-closed calendar check, not independent proof of trading or pricing."""
    out = {
        "schema": SCHEMA, "state": "LAB_BLOCKED", "reason": "INVALID_WINDOW",
        "market_calendar_convention": CONVENTION,
        "horizon": horizon if horizon in ("D1", "W1") else None,
        "start_utc": None, "end_utc": None, "start_new_york": None,
        "end_new_york": None, "session_days": None,
        "new_york_iana_timezone_applied": False,
        "broker_session_schedule_verified": False,
        "weekend_holiday_early_close_verified": False,
        "broker_m15_execution_price_verified": False,
        "point_in_time_evidence_verified": False,
        "fx_bias": None, "trade_authorized": False,
        "worker_enabled": False, "scheduler_enabled": False,
        "new_cost_brl": 0,
    }
    if not isinstance(horizon, str) or horizon not in ("D1", "W1"):
        return out
    start, end = _utc(start_at_utc), _utc(end_at_utc)
    if start is None or end is None or start >= end:
        return out
    local_start = start.astimezone(NY)
    local_end = end.astimezone(NY)
    # Only standard daily FX close, no UTC-midnight pseudo-market windows.
    if any(t.hour != 17 or t.minute or t.second or t.microsecond
           for t in (local_start, local_end)):
        out["reason"] = "NOT_NEW_YORK_1700_CLOSE_BOUNDARY"
        return out
    start_weekday, end_weekday = local_start.weekday(), local_end.weekday()
    local_day_gap = (local_end.date() - local_start.date()).days
    if horizon == "D1":
        # A completed active FX day starts Sunday 17:00 through Thursday 17:00.
        good = (start_weekday in (6, 0, 1, 2, 3)
                and end_weekday == (start_weekday + 1) % 7
                and local_day_gap == 1)
        count = 1
    else:
        good = (start_weekday == 6 and end_weekday == 4 and local_day_gap == 5)
        count = 5
    if not good:
        out["reason"] = "FOREX_WEEKEND_OR_NONCANONICAL_SESSION"
        return out
    out.update({
        "state": "LAB_FX_NY_ROLLOVER_WINDOW_STRUCTURALLY_VALID",
        "reason": "TIMEZONE_CONVENTION_NOT_BROKER_ATTESTATION",
        "start_utc": start.isoformat(),
        "end_utc": end.isoformat(),
        "start_new_york": local_start.isoformat(),
        "end_new_york": local_end.isoformat(),
        "session_days": count,
        "new_york_iana_timezone_applied": True,
    })
    return out


__all__ = ["SCHEMA", "CONVENTION", "inspect_fx_ny_close_window_lab"]
