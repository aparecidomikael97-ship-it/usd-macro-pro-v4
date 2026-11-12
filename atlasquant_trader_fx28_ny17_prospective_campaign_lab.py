"""Offline FX28 D1/W1 nominal-census boundary for the *prospective* Nov-Dec study.

The 2026-11-15 -> 2026-12-11 campaign dates and 28 pairs were published
in GitHub issue #1884 before the first nominal session. This pure function
does NOT fetch that issue, authenticate its revisions, fetch Pepperstone
prices, authenticate historical macro snapshots, or verify predictions.

Never confuse 672 pair-horizon slots with 672 independent Bernoulli trials.
Twenty D1 sessions overlap four W1 sessions; pairs share eight currencies.
The result is a documentary completeness check ONLY. No PnL or live biases.
"""
from __future__ import annotations

from datetime import datetime, timedelta, time, timezone
from typing import Any
from zoneinfo import ZoneInfo

from atlasquant_fx_universe import OFFICIAL_PAIRS

SCHEMA = "ATLASQUANT_TRADER_FX28_NY17_PROSPECTIVE_BOUNDARY_LAB_V1"
ROSTER_SCHEMA = "ATLASQUANT_TRADER_MT5_FULL_NY17_WINDOW_ROSTER_LAB_V1"
ROSTER_COMPLETE = "LAB_AM12_NY17_FULL_ROSTER_LOCAL_CLAIMS_ONLY_NO_GO"
ROSTER_GAPS = "LAB_AM12_NY17_FULL_ROSTER_HAS_GAPS_NO_GO"
WINDOW_COMPLETE = "LAB_AM12_LOCAL_M15_WINDOW_CHECKS_ONLY_NO_GO"
NY = ZoneInfo("America/New_York")
FROZEN_START_UTC = datetime(2026, 11, 15, 22, tzinfo=timezone.utc)
FROZEN_END_UTC = datetime(2026, 12, 11, 22, tzinfo=timezone.utc)
CAMPAIGN_ID = "FX28_NY17_20261115_20261211"
CALENDAR_ISSUE = "https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/issues/1884"
EXPECTED_SESSIONS = {"D1": 20, "W1": 4}
EXPECTED_PAIR_HORIZON_SLOTS = 672


def _utc(value: Any) -> datetime | None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        return None
    try:
        return value.astimezone(timezone.utc)
    except (OverflowError, ValueError):
        return None


def _iso(value: Any) -> datetime | None:
    if not isinstance(value, str) or len(value) > 40:
        return None
    try:
        return _utc(datetime.fromisoformat(value))
    except (OverflowError, ValueError, TypeError):
        return None


def _nominal_windows(horizon: str) -> list[tuple[datetime, datetime]]:
    """Derive dates strictly from the frozen range, never from price rows."""
    first = FROZEN_START_UTC.astimezone(NY)
    last = FROZEN_END_UTC.astimezone(NY)
    out: list[tuple[datetime, datetime]] = []
    current = first.date()
    while current <= last.date():
        weekday = current.weekday()
        relevant = (weekday == 6 if horizon == "W1"
                    else weekday in (6, 0, 1, 2, 3))
        if relevant:
            beginning = datetime.combine(current, time(17), tzinfo=NY).astimezone(timezone.utc)
            ending = datetime.combine(
                current + timedelta(days=5 if horizon == "W1" else 1),
                time(17), tzinfo=NY,
            ).astimezone(timezone.utc)
            if beginning >= FROZEN_START_UTC and ending <= FROZEN_END_UTC:
                out.append((beginning, ending))
        current += timedelta(days=1)
    return out


def _base(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "campaign_id": CAMPAIGN_ID,
        "calendar_issue_url": CALENDAR_ISSUE,
        "campaign_range_start_utc": FROZEN_START_UTC.isoformat(),
        "campaign_range_end_utc": FROZEN_END_UTC.isoformat(),
        "state": "LAB_NY17_PROSPECTIVE_BOUNDARY_BLOCKED",
        "reason": reason,
        "expected_nominal_sessions": {"D1": 20, "W1": 4},
        "expected_pair_horizon_slots": EXPECTED_PAIR_HORIZON_SLOTS,
        "reconciled_pair_horizon_slots": 0,
        "unverifiable_pair_horizon_slots": None,
        "per_horizon": {},
        "frozen_calendar_scope_matched_locally": False,
        "calendar_github_timestamp_independently_verified_here": False,
        "pre_event_forecasts_witnessed": False,
        "broker_price_provenance_authenticated": False,
        "broker_trading_calendar_authenticated": False,
        "point_in_time_macro_authenticated": False,
        "out_of_sample_accuracy_validated": False,
        "independent_trial_count_validated": False,
        "calibrated_direction_probability": None,
        "validated_directional_accuracy": None,
        "operational_bias": "AGUARDAR",
        "publishable": False, "live_alert_allowed": False,
        "trade_authorized": False, "scheduler_enabled": False,
        "worker_enabled": False, "http_requests": 0, "file_writes": 0,
        "new_cost_brl": 0, "research_only": True,
    }


def inspect_frozen_fx28_ny17_campaign_lab(
    *, daily_price_roster: Any, weekly_price_roster: Any,
    inspected_at_utc: Any,
) -> dict[str, Any]:
    """Require the ENTIRE externally *declared* study period in both horizons.

    Checks 20+4 nominal sessions and all 672 pair-horizon slots; allows an
    honest missing-data report, but labels it incomplete. Caller can fabricate
    records, so neither a structural PASS nor the issue URL proves outcomes.
    """
    out = _base("INVALID_CLOCK_OR_CAMPAIGN_NOT_FINISHED")
    now = _utc(inspected_at_utc)
    if now is None or now < FROZEN_END_UTC:
        return out
    if len(OFFICIAL_PAIRS) != 28 or len(set(OFFICIAL_PAIRS)) != 28:
        out["reason"] = "FX28_CANONICAL_UNIVERSE_CHANGED"
        return out

    reports = {"D1": daily_price_roster, "W1": weekly_price_roster}
    per_horizon = {}
    total_complete = 0
    any_gaps = False
    for horizon in ("D1", "W1"):
        r = reports[horizon]
        windows = _nominal_windows(horizon)
        if len(windows) != EXPECTED_SESSIONS[horizon]:
            out["reason"] = "FROZEN_CAMPAIGN_CALENDAR_CODE_INCONSISTENT"
            return out
        expected_checks = len(windows) * 28
        if not isinstance(r, dict) or r.get("schema") != ROSTER_SCHEMA:
            out["reason"] = horizon + "_PRICE_ROSTER_MISSING_OR_INVALID"
            return out
        if (_iso(r.get("range_start_utc")) != FROZEN_START_UTC
                or _iso(r.get("range_end_utc")) != FROZEN_END_UTC):
            out["reason"] = horizon + "_CAMP_AIGN_BOUNDS_MISMATCH".replace("CAMP_AIGN", "CAMPAIGN")
            return out
        rows = r.get("windows")
        if (r.get("horizon") != horizon
                or not isinstance(rows, list)
                or len(rows) != len(windows)
                or type(r.get("nominal_window_count")) is not int
                or r["nominal_window_count"] != len(windows)
                or type(r.get("total_expected_pair_window_checks")) is not int
                or r["total_expected_pair_window_checks"] != expected_checks):
            out["reason"] = horizon + "_NOMINAL_SESSION_OR_PAIR_SLOT_CENSUS_MISMATCH"
            return out

        complete_checks = 0
        complete_windows = 0
        blocked_by_pair = {pair: 0 for pair in OFFICIAL_PAIRS}
        complete_by_pair = {pair: 0 for pair in OFFICIAL_PAIRS}
        for ix, (record, (start, end)) in enumerate(zip(rows, windows), 1):
            if (not isinstance(record, dict)
                    or type(record.get("window_number")) is not int
                    or record["window_number"] != ix
                    or _iso(record.get("start_utc")) != start
                    or _iso(record.get("end_utc")) != end):
                out["reason"] = horizon + "_MISSING_SWAPPED_OR_NONCANONICAL_SESSION"
                return out
            blocked = record.get("blocked_pairs")
            reasons = record.get("unverifiable_pair_reasons")
            movements = record.get("price_movements_documentary_by_pair")
            if (not isinstance(blocked, list)
                    or len(blocked) != len(set(blocked))
                    or not isinstance(reasons, dict)
                    or not isinstance(movements, dict)
                    or not set(blocked) <= set(OFFICIAL_PAIRS)
                    or set(reasons) != set(blocked)
                    or set(movements) != set(OFFICIAL_PAIRS).difference(blocked)
                    or any(not isinstance(x, str) or not x for x in reasons.values())):
                out["reason"] = horizon + "_PER_PAIR_MISSING_PRICE_DIAGNOSTICS"
                return out
            complete = 28 - len(blocked)
            if (type(record.get("pair_checks_complete_claim_only")) is not int
                    or record["pair_checks_complete_claim_only"] != complete
                    or type(record.get("pair_checks_blocked_or_unverifiable")) is not int
                    or record["pair_checks_blocked_or_unverifiable"] != len(blocked)):
                out["reason"] = horizon + "_PER_SESSION_PAIR_COUNT_MISMATCH"
                return out
            is_full = complete == 28
            if (record.get("local_archive_check_state") == WINDOW_COMPLETE) != is_full:
                out["reason"] = horizon + "_PRICE_WINDOW_STATUS_INCONSISTENT"
                return out
            complete_windows += int(is_full)
            complete_checks += complete
            for pair in OFFICIAL_PAIRS:
                if pair in reasons:
                    blocked_by_pair[pair] += 1
                else:
                    complete_by_pair[pair] += 1

        if (type(r.get("local_pair_window_checks_complete")) is not int
                or r["local_pair_window_checks_complete"] != complete_checks
                or type(r.get("blocked_or_unverifiable_pair_window_checks")) is not int
                or r["blocked_or_unverifiable_pair_window_checks"] != expected_checks - complete_checks
                or type(r.get("complete_local_window_count")) is not int
                or r["complete_local_window_count"] != complete_windows
                or type(r.get("blocked_or_incomplete_window_count")) is not int
                or r["blocked_or_incomplete_window_count"] != len(windows) - complete_windows
                or r.get("unverifiable_window_counts_by_pair") != blocked_by_pair
                or r.get("complete_window_counts_by_pair") != complete_by_pair
                or r.get("all_nominal_windows_locally_checked_complete") is not (complete_windows == len(windows))):
            out["reason"] = horizon + "_AGGREGATE_PAIR_WINDOW_TOTALS_INCONSISTENT"
            return out
        is_roster_full = complete_windows == len(windows)
        if r.get("state") != (ROSTER_COMPLETE if is_roster_full else ROSTER_GAPS):
            out["reason"] = horizon + "_ROSTER_STATE_NOT_RECONCILED"
            return out

        total_complete += complete_checks
        any_gaps = any_gaps or not is_roster_full
        per_horizon[horizon] = {
            "nominal_sessions": len(windows),
            "expected_pair_horizon_slots": expected_checks,
            "documentary_complete_pair_slots": complete_checks,
            "documentary_unverifiable_pair_slots": expected_checks - complete_checks,
            "complete_nominal_sessions": complete_windows,
            "sessions_with_gaps": len(windows) - complete_windows,
        }

    out.update({
        "state": ("LAB_NY17_FROZEN_CAMPAIGN_HAS_GAPS_NO_GO" if any_gaps
                  else "LAB_NY17_FROZEN_CAMPAIGN_LOCAL_ROSTER_ONLY_NO_GO"),
        "reason": ("NOMINAL_SCOPE_RECONCILED_BUT_DATA_MISSING"
                   if any_gaps else "ALL_672_DOCUMENTARY_SLOTS_PRESENT_NO_EXTERNAL_ATTESTATION"),
        "reconciled_pair_horizon_slots": total_complete,
        "unverifiable_pair_horizon_slots": EXPECTED_PAIR_HORIZON_SLOTS - total_complete,
        "per_horizon": per_horizon,
        "frozen_calendar_scope_matched_locally": True,
    })
    return out


__all__ = (
    "CAMPAIGN_ID", "CALENDAR_ISSUE", "FROZEN_START_UTC", "FROZEN_END_UTC",
    "EXPECTED_PAIR_HORIZON_SLOTS", "SCHEMA",
    "inspect_frozen_fx28_ny17_campaign_lab",
)
