"""Manual-only forward D1/W1 research session plan and candidate precommit.

NO predictions are generated. No network, file writes, scheduled jobs or trade.
A 'candidate' is NOT an externally witnessed precommit: local/claimed time and
SHA hashes can be backdated, and macro data origin remains unverified.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from hashlib import sha256
import json
from typing import Any
from zoneinfo import ZoneInfo

from atlasquant_fx_universe import OFFICIAL_PAIRS
from atlasquant_trader_fx_d1w1_evidence_chain_lab import (
    inspect_fx_d1w1_evidence_chain_lab,
)
from atlasquant_trader_fx_ny_rollover_lab import (
    inspect_fx_ny_close_window_lab,
)
from atlasquant_trader_fx_premove_lab import (
    FORECAST, audit_fx_premove_lab,
)

SCHEMA = "ATLASQUANT_TRADER_FX_D1W1_MANUAL_FORWARD_TRIAL_LAB_V1"
NY = ZoneInfo("America/New_York")
MIN_LEAD_MINUTES = 60
MAX_FORECAST_AGE_MINUTES = 5
MAX_LOOKAHEAD_DAYS = 15
VALID_WINDOW = "LAB_FX_NY_ROLLOVER_WINDOW_STRUCTURALLY_VALID"
FORECAST_OK = "LAB_FORECAST_STRUCTURALLY_ACCEPTED_UNATTESTED"


def _clock(t: Any) -> datetime | None:
    if not isinstance(t, datetime) or t.tzinfo is None or t.utcoffset() is None:
        return None
    return t.astimezone(timezone.utc)


def _baseline(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_BLOCKED", "reason": reason,
        "checked_at_utc_claim": None,
        "horizon_windows": {},
        "pairs_covered": 0, "eligible_pairs": [], "planned_trial_slots": 0,
        "candidate_forecast_sha256": None,
        "candidate_macro_sha256": None,
        "candidate_pair": None, "candidate_horizon": None,
        "candidate_direction_claim": None,
        "candidate_is_abstention": None,
        "candidate_structurally_preparable": False,
        "candidate_external_precommit_url": None,
        "candidate_external_precommit_witnessed": False,
        "candidate_macroeconomic_data_original_source_authenticated": False,
        "candidate_macro_publication_times_verified": False,
        "candidate_immutable_algorithm_version_witnessed": False,
        "candidate_broker_timezone_verified": False,
        "future_outcome_already_known": False,
        "future_price_data_verified": False,
        "validated_prediction_count": 0,
        "validated_accuracy": None, "directional_bias": None,
        "operational_bias": "AGUARDAR",
        "trade_authorized": False, "can_feed_live_radar": False,
        "publishable": False, "worker_enabled": False,
        "scheduler_enabled": False, "external_http_requests": 0,
        "new_cost_brl": 0,
    }


def _next_window(now_utc: datetime, horizon: str) -> dict[str, Any] | None:
    local_date = now_utc.astimezone(NY).date()
    for offset in range(MAX_LOOKAHEAD_DAYS + 1):
        day: date = local_date + timedelta(days=offset)
        # Active daily windows: Sun->Mon, Mon->Tue, Tue->Wed,
        # Wed->Thu, Thu->Fri. Weekly: Sun->Fri.
        if horizon == "D1" and day.weekday() not in (6, 0, 1, 2, 3):
            continue
        if horizon == "W1" and day.weekday() != 6:
            continue
        start_ny = datetime.combine(day, time(17), tzinfo=NY)
        if horizon == "D1":
            end_day = day + timedelta(days=1)
        else:
            end_day = day + timedelta(days=5)
        end_ny = datetime.combine(end_day, time(17), tzinfo=NY)
        start = start_ny.astimezone(timezone.utc)
        end = end_ny.astimezone(timezone.utc)
        # A plan is useful only if the opportunity for a PRE-start
        # external commitment remains open with sufficient lead time.
        if start < now_utc + timedelta(minutes=MIN_LEAD_MINUTES):
            continue
        window = inspect_fx_ny_close_window_lab(
            horizon=horizon, start_at_utc=start, end_at_utc=end)
        if window["state"] != VALID_WINDOW:
            return None
        return {
            "horizon": horizon,
            "start_at_utc": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "end_at_utc": end.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "start_at_new_york": start_ny.isoformat(),
            "end_at_new_york": end_ny.isoformat(),
            "precommit_deadline_utc": (
                start - timedelta(minutes=MIN_LEAD_MINUTES)
            ).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "broker_session_calendar_verified": False,
            "prediction_supplied": False,
            "external_timestamp_witnessed": False,
        }
    return None


def plan_next_fx_forward_trial_lab(*, as_of_utc: Any) -> dict[str, Any]:
    """Return next research session windows for G8/28, NEVER a signal."""
    out = _baseline("AS_OF_MUST_BE_TIMEZONE_AWARE")
    now = _clock(as_of_utc)
    if now is None:
        return out
    windows = {h: _next_window(now, h) for h in ("D1", "W1")}
    if any(v is None for v in windows.values()) or len(OFFICIAL_PAIRS) != 28:
        out["reason"] = "FX_WINDOW_OR_UNIVERSE_INVALID"
        return out
    # 28 * (one D1 plus one W1) = 56 research slots, not predictions.
    out.update({
        "state": "LAB_FUTURE_SESSION_WINDOWS_PLANNED_NO_FORECAST",
        "reason": "NO_MACRO_VERIFICATION_OR_INDEPENDENT_FORECAST_PRECOMMIT",
        "checked_at_utc_claim": now.isoformat(),
        "horizon_windows": windows,
        "pairs_covered": len(OFFICIAL_PAIRS),
        "eligible_pairs": list(OFFICIAL_PAIRS),
        "planned_trial_slots": len(OFFICIAL_PAIRS) * len(windows),
    })
    return out


def inspect_fx_forward_candidate_lab(
    *, forecast_raw: Any, macro_raw: Any, as_of_utc: Any,
) -> dict[str, Any]:
    """Prepare a hash-linked manual candidate for EXTERNAL pre-registration.

    Caller must externally publish witness before the session. This method
    does not make that publication and cannot prove a historical timestamp.
    """
    out = plan_next_fx_forward_trial_lab(as_of_utc=as_of_utc)
    if out["state"] != "LAB_FUTURE_SESSION_WINDOWS_PLANNED_NO_FORECAST":
        return out
    now = _clock(as_of_utc)
    forecast_report = audit_fx_premove_lab(forecast_raw, as_of_utc=now)
    if forecast_report["state"] != FORECAST_OK:
        out.update(state="LAB_BLOCKED",
                   reason="FORECAST_INVALID_OR_NOT_BEFORE_NEW_YORK_SESSION")
        return out
    try:
        f = json.loads(forecast_raw)
        created = datetime.fromisoformat(f["created_at_utc"].replace("Z", "+00:00"))
    except (ValueError, TypeError, KeyError):
        out.update(state="LAB_BLOCKED", reason="FORECAST_TIMESTAMP_UNREADABLE")
        return out
    age = now - created
    if not timedelta(0) <= age <= timedelta(minutes=MAX_FORECAST_AGE_MINUTES):
        out.update(state="LAB_BLOCKED",
                   reason="FORECAST_CREATION_CLAIM_NOT_NEAR_MANUAL_AUDIT")
        return out
    planned = out["horizon_windows"][f["horizon"]]
    if (f["target_start_utc"] != planned["start_at_utc"]
            or f["target_end_utc"] != planned["end_at_utc"]):
        out.update(state="LAB_BLOCKED", reason="FORECAST_NOT_FOR_NEXT_PLANNED_SESSION")
        return out
    chain = inspect_fx_d1w1_evidence_chain_lab(
        forecast_raw=forecast_raw, macro_raw=macro_raw, as_of_utc=now,
        mt5_m15_csv_raw=None)
    required = (
        "forecast_receipt_structurally_valid",
        "macro_receipts_structurally_valid",
        "two_sided_pilot_indicators_present",
        "forecast_macro_pair_match",
        "macro_decision_time_equals_forecast_creation",
        "forecast_evidence_hash_binds_macro_bytes",
        "all_macro_captures_at_or_before_forecast_data_cutoff",
    )
    if not all(chain[k] is True for k in required):
        out.update(state="LAB_BLOCKED",
                   reason="FORECAST_MACRO_EVIDENCE_CHAIN_INCOMPLETE_OR_INCONSISTENT")
        return out
    # Never include unverifiable numeric indicators or publish a direction
    # as a real operational bias. Only reflect its untrusted claim.
    out.update({
        "state": "LAB_FORWARD_CANDIDATE_HASH_BOUND_AWAITING_EXTERNAL_WITNESS",
        "reason": "NOT_COMMITTED_OR_INDEPENDENTLY_VERIFIED",
        "candidate_forecast_sha256": sha256(forecast_raw).hexdigest(),
        "candidate_macro_sha256": sha256(macro_raw).hexdigest(),
        "candidate_pair": f["pair"],
        "candidate_horizon": f["horizon"],
        "candidate_direction_claim": f["direction"],
        "candidate_is_abstention": f["direction"] == "NEUTRO",
        "candidate_structurally_preparable": True,
    })
    return out


__all__ = ["SCHEMA", "MIN_LEAD_MINUTES",
           "plan_next_fx_forward_trial_lab", "inspect_fx_forward_candidate_lab"]
