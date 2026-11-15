"""Audit FX28 preflight execution ACTUAL start/end vs the frozen 12h window.

Pure offline, read-only quality-control of supplied run metadata. Does not
contact Automations, GitHub, AM12, or MetaTrader 5, and never writes a forecast.
The caller is responsible for retrieving run times. Their timestamps remain
provider claims, not independently signed trusted time.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

SCHEMA = "ATLASQUANT_FX28_PREFLIGHT_TEMPORAL_ATTESTATION_LAB_V1"
WINDOW_START = datetime(2026, 11, 15, 10, 0, tzinfo=timezone.utc)
FIRST_NOMINAL_OPEN = datetime(2026, 11, 15, 22, 0, tzinfo=timezone.utc)
FIRST_NOMINAL_M15_CLOSED = datetime(2026, 11, 15, 22, 15, tzinfo=timezone.utc)
EXPECTED_TOTAL = 672
EXPECTED_FIRST = 56


def _time(value: Any) -> datetime | None:
    if not isinstance(value, datetime) or value.tzinfo is None:
        return None
    try:
        if value.utcoffset() is None:
            return None
        return value.astimezone(timezone.utc)
    except (TypeError, OverflowError, ValueError):
        return None


def _base(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "LAB_FX28_PREFLIGHT_TEMPORAL_INPUT_INVALID_NO_GO",
        "reason": reason,
        "first_56_slots_due": None,
        "frozen_total_pair_horizon_slots": EXPECTED_TOTAL,
        "frozen_first_d1w1_pair_horizon_slots": EXPECTED_FIRST,
        "preflight_execution_fully_inside_12h": False,
        "preflight_early_completed_outside_window": False,
        "hourly_comment_review_inside_12h": False,
        "hourly_comment_review_substitutes_local_source_audit": False,
        "observed_comment_count": None,
        "canonical_comment_header_count": None,
        "authenticated_immutable_forecast_count": 0,
        "github_comments_absence_independently_attested": False,
        "local_source_state": "UNKNOWN",
        "local_source_audit_completed": False,
        "market_data_observed": False,
        "m15_data_collection_performed": False,
        "claim_is_not_third_party_timestamp_attestation": True,
        "first_m15_capture_not_automatically_authorized": True,
        "calibrated_directional_probability": None,
        "directional_bias": None,
        "validated_accuracy": None,
        "trade_authorized": False,
        "publishable": False,
        "operational_bias": "AGUARDAR",
        "http_requests": 0,
        "mt5_calls": 0,
        "file_writes": 0,
    }


def audit_fx28_preflight_actual_run_times_lab(
    *,
    preflight_started: Any,
    preflight_completed: Any,
    hourly_started: Any,
    hourly_completed: Any,
    inspected_at: Any,
    github_comments_checked: Any,
    canonical_header_count: Any,
    local_source_audit_completed: Any,
) -> dict[str, Any]:
    """Do not promote a scheduled 10:00 execution if actually run at 09:58."""
    r = _base("MISSING_NAIVE_OR_INCOHERENT_RUN_TIMES")
    times = [_time(v) for v in (
        preflight_started, preflight_completed, hourly_started,
        hourly_completed, inspected_at,
    )]
    if any(t is None for t in times):
        return r
    p0, p1, h0, h1, now = times
    if p0 > p1 or h0 > h1 or p1 > now or h1 > now:
        return r
    if type(github_comments_checked) is not int or github_comments_checked < 0:
        return _base("INVALID_COMMENT_COUNT")
    if (type(canonical_header_count) is not int or canonical_header_count < 0
            or canonical_header_count > github_comments_checked):
        return _base("INVALID_CANONICAL_HEADER_COUNT")
    if type(local_source_audit_completed) is not bool:
        return _base("INVALID_SOURCE_AUDIT_STATUS")

    p_inside = WINDOW_START <= p0 <= p1 < FIRST_NOMINAL_OPEN
    h_inside = WINDOW_START <= h0 <= h1 < FIRST_NOMINAL_OPEN
    p_early = p1 < WINDOW_START
    source = "LOCALLY_AUDITED_CLAIM_ONLY" if local_source_audit_completed else "UNKNOWN"
    if p_early and h_inside:
        state = "LAB_FX28_PREFLIGHT_EARLY_LATER_COMMENT_REVIEW_ONLY_NO_GO"
        reason = "EARLY_PREFLIGHT_NOT_REPLACED_BY_HOURLY_GITHUB_COMMENT_SCAN"
    elif p_inside:
        state = "LAB_FX28_PREFLIGHT_TEMPORALLY_IN_WINDOW_STILL_UNATTESTED_NO_GO"
        reason = "CLOCK_CLAIM_IN_WINDOW_NOT_SOURCE_OR_WITNESS_AUTHENTICATION"
    elif now >= FIRST_NOMINAL_OPEN:
        state = "LAB_FX28_FIRST_SLOTS_DUE_NO_RETROACTIVE_PREFLIGHT_NO_GO"
        reason = "NO_HINDSIGHT_PRECOMMITMENT_ALLOWED"
    else:
        state = "LAB_FX28_PREFLIGHT_NOT_FULLY_WITHIN_WINDOW_NO_GO"
        reason = "TEMPORAL_ADMISSION_REQUIREMENTS_NOT_SATISFIED"

    r.update({
        "state": state,
        "reason": reason,
        "first_56_slots_due": now >= FIRST_NOMINAL_OPEN,
        "preflight_execution_fully_inside_12h": p_inside,
        "preflight_early_completed_outside_window": p_early,
        "hourly_comment_review_inside_12h": h_inside,
        "observed_comment_count": github_comments_checked,
        "canonical_comment_header_count": canonical_header_count,
        "local_source_state": source,
        "local_source_audit_completed": local_source_audit_completed,
    })
    # A structurally correct GitHub header is still NOT an authenticated
    # pre-event market direction or proof that all other channels were empty.
    return r


__all__ = (
    "SCHEMA", "WINDOW_START", "FIRST_NOMINAL_OPEN",
    "FIRST_NOMINAL_M15_CLOSED", "audit_fx28_preflight_actual_run_times_lab",
)
