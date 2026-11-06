"""Frozen prospective G8/28 FX D1+W1 study universe, LAB only.

This generates an EMPTY research cohort before its target session. A cohort
registers the universe and denominators, NOT forecasts or correctness.
Git SHA and self-declared reference time are not an independently witnessed
pre-event prediction. Never trade, schedule, fetch or publish automatically.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Any

from atlasquant_fx_universe import OFFICIAL_PAIRS
from atlasquant_trader_fx_manual_forward_trial_lab import (
    plan_next_fx_forward_trial_lab,
)

SCHEMA = "ATLASQUANT_TRADER_FX_G8_FROZEN_COHORT_LAB_V1"
MAX_BYTES = 40000
HORIZONS = ("D1", "W1")
EXPECTED_COUNT = 56
NO_FORECAST = "SLOT_UNFILLED_NO_FORECAST"
EXTERNAL_WITNESS = "NOT_WITNESSED"


def _utc_clock(value: Any) -> datetime | None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        return None
    return value.astimezone(timezone.utc)


def _clock_claim(value: Any) -> datetime | None:
    if not isinstance(value, str) or len(value) != 20 or not value.endswith("Z"):
        return None
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return None
    if parsed.year < 2026:
        return None
    return parsed.replace(tzinfo=timezone.utc)


def build_g8_forward_cohort_lab(*, planning_reference_utc: Any) -> dict[str, Any]:
    """Deterministic 56-slot trial plan. Reference time is NOT capture proof."""
    at = _utc_clock(planning_reference_utc)
    if at is None or len(OFFICIAL_PAIRS) != 28 or len(set(OFFICIAL_PAIRS)) != 28:
        raise ValueError("INVALID_CLOCK_OR_FOREX_UNIVERSE")
    base = plan_next_fx_forward_trial_lab(as_of_utc=at)
    if base["state"] != "LAB_FUTURE_SESSION_WINDOWS_PLANNED_NO_FORECAST":
        raise ValueError("NO_VALID_FORWARD_SESSIONS")
    windows = base["horizon_windows"]
    if any(windows.get(h) is None for h in HORIZONS):
        raise ValueError("INCOMPLETE_D1_W1")
    day = windows["D1"]["start_at_new_york"][:10].replace("-", "")
    slots = []
    for horizon in HORIZONS:
        target = windows[horizon]
        for pair in OFFICIAL_PAIRS:
            code = pair.replace("/", "")
            slots.append({
                "slot_id": f"G8_{day}_{code}_{horizon}",
                "pair": pair,
                "horizon": horizon,
                "target_start_utc": target["start_at_utc"],
                "target_end_utc": target["end_at_utc"],
                "precommit_deadline_utc": target["precommit_deadline_utc"],
                "state": NO_FORECAST,
                "direction": None,
                "forecast_receipt_sha256": None,
                "independent_precommit_witness": None,
            })
    assert len(slots) == EXPECTED_COUNT
    # The cohort has no predictions. Subsequent, separately committed
    # forecasts MUST NOT edit or replace this pre-registered universe.
    return {
        "schema": SCHEMA,
        "cohort_id": f"LAB_G8_{day}_D1W1_V1",
        "planning_reference_utc_claim": at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "time_reference_independently_attested": False,
        "market_clock_convention": "AMERICA_NEW_YORK_1700_RESEARCH_NOT_BROKER_ATTESTED",
        "daily_window": {
            "start_at_utc": windows["D1"]["start_at_utc"],
            "end_at_utc": windows["D1"]["end_at_utc"],
            "precommit_deadline_utc": windows["D1"]["precommit_deadline_utc"],
        },
        "weekly_window": {
            "start_at_utc": windows["W1"]["start_at_utc"],
            "end_at_utc": windows["W1"]["end_at_utc"],
            "precommit_deadline_utc": windows["W1"]["precommit_deadline_utc"],
        },
        "coverage_policy": {
            "universe": "G8_28_CANONICAL_FX_PAIRS",
            "selection_after_outcome_prohibited": True,
            "all_slots_required_in_future_coverage_report": True,
            "abstentions_must_be_counted_separately": True,
            "missing_outcomes_cannot_be_treated_as_wins": True,
            "neutral_is_not_a_directional_hit": True,
            "precommit_witness_required_for_proven_predictions": True,
        },
        "declared_pair_count": 28,
        "declared_horizons": list(HORIZONS),
        "declared_slot_count": EXPECTED_COUNT,
        "committed_predictions": 0,
        "committed_abstentions": 0,
        "unfilled_slots": EXPECTED_COUNT,
        "slots": slots,
        "external_witness_status": EXTERNAL_WITNESS,
        "algorithm_version_frozen_and_attested": False,
        "source_publication_times_independently_verified": False,
        "broker_m15_timezone_verified": False,
        "real_market_price_outcome_verified": False,
        "historical_accuracy_verified": False,
        "validated_prediction_count": 0,
        "validated_accuracy": None,
        "fx_bias": None,
        "operational_bias": "AGUARDAR",
        "trade_authorized": False,
        "can_feed_live_radar": False,
        "worker_enabled": False,
        "scheduler_enabled": False,
        "publishable": False,
        "new_cost_brl": 0,
    }


def serialize_g8_forward_cohort_lab(*, planning_reference_utc: Any) -> bytes:
    """Canonical bytes to freeze; outputs never contain generated forecasts."""
    obj = build_g8_forward_cohort_lab(planning_reference_utc=planning_reference_utc)
    return (json.dumps(obj, sort_keys=True, ensure_ascii=True,
                       separators=(",", ":")) + "\n").encode("utf-8")


def inspect_g8_forward_cohort_lab(
    raw: Any, *, inspected_at_utc: Any,
) -> dict[str, Any]:
    """Check exact deterministic 56-slot manifest, not independent time proof.

    If the current clock is after the planned deadline, the cohort remains
    structurally readable but can no longer enroll a prospective precommit.
    """
    out = {
        "schema": SCHEMA, "state": "LAB_BLOCKED",
        "reason": "INVALID_COHORT_BYTES_OR_INSPECTION_CLOCK",
        "cohort_id": None, "manifest_sha256": None,
        "pair_count": 0, "required_slots": 0, "unfilled_slots": 0,
        "forecast_directions_recorded": 0, "evaluable_predictions": 0,
        "all_56_slots_unmodified": False,
        "still_before_60_minute_precommit_deadline": False,
        "commit_recorded_externally_before_market": False,
        "external_commit_timestamp_verified": False,
        "algorithm_version_independently_frozen": False,
        "point_in_time_macro_sources_verified": False,
        "broker_m15_prices_verified": False,
        "validated_accuracy": None, "operational_bias": "AGUARDAR",
        "trade_authorized": False, "worker_enabled": False,
        "scheduler_enabled": False, "new_cost_brl": 0,
    }
    inspected = _utc_clock(inspected_at_utc)
    if (inspected is None or not isinstance(raw, bytes)
            or not 1000 <= len(raw) <= MAX_BYTES):
        return out
    try:
        obj = json.loads(raw.decode("utf-8", "strict"))
        if not isinstance(obj, dict) or obj.get("schema") != SCHEMA:
            return out
        claimed = _clock_claim(obj.get("planning_reference_utc_claim"))
        if claimed is None or claimed > inspected:
            out["reason"] = "INVALID_OR_FUTURE_PLANNING_REFERENCE_CLAIM"
            return out
        expected = serialize_g8_forward_cohort_lab(planning_reference_utc=claimed)
        if raw != expected:
            out["reason"] = "FROZEN_56_SLOT_UNIVERSE_OR_CANONICAL_BYTES_CHANGED"
            return out
        first_deadline = _clock_claim(obj["daily_window"]["precommit_deadline_utc"])
        weekly_deadline = _clock_claim(obj["weekly_window"]["precommit_deadline_utc"])
        if first_deadline is None or weekly_deadline is None:
            return out
        early = inspected <= min(first_deadline, weekly_deadline)
        out.update({
            "state": ("LAB_COHORT_STRUCTURE_VALID_BEFORE_DEADLINE_NO_FORECAST"
                      if early else "LAB_COHORT_STRUCTURE_VALID_BUT_DEADLINE_PASSED"),
            "reason": ("UNIVERSE_FROZEN_CLAIM_NO_EXTERNAL_WITNESS_NO_PREDICTIONS"
                       if early else "CANNOT_RETROACTIVELY_CREATE_FORECAST"),
            "cohort_id": obj["cohort_id"],
            "manifest_sha256": sha256(raw).hexdigest(),
            "pair_count": 28, "required_slots": EXPECTED_COUNT,
            "unfilled_slots": EXPECTED_COUNT,
            "all_56_slots_unmodified": True,
            "still_before_60_minute_precommit_deadline": early,
        })
        return out
    except (ValueError, TypeError, KeyError, UnicodeDecodeError, RecursionError):
        return out


__all__ = [
    "SCHEMA", "EXPECTED_COUNT", "build_g8_forward_cohort_lab",
    "serialize_g8_forward_cohort_lab", "inspect_g8_forward_cohort_lab",
]
