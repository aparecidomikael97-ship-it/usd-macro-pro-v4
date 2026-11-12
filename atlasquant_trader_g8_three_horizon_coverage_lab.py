"""Independent MN1/W1/D1 G8 source coverage audit for all 28 FX pairs.

This is metadata-only and uses only caller-supplied receipts. It never
generates directional hypotheses, probabilities, entries or trade alerts.
The three time horizons are not independent statistical trials, and their
decision cutoffs need not be chronologically ordered around month boundaries.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from atlasquant_fx_universe import OFFICIAL_PAIRS
from atlasquant_trader_g8_macro_matrix_pit_lab import (
    inspect_g8_macro_matrix_pit_lab,
)

SCHEMA = "ATLASQUANT_TRADER_G8_THREE_HORIZON_COVERAGE_LAB_V1"
HORIZONS = ("MN1", "W1", "D1")
COMPLETE = "LAB_PAIR_MACRO_METADATA_COMPLETE_UNATTESTED"
ACCEPTED = frozenset({
    "LAB_G8_MACRO_MATRIX_CLAIMS_ONLY",
    "LAB_G8_MACRO_MATRIX_HAS_REJECTIONS",
})


def _utc(value: Any) -> datetime | None:
    if (not isinstance(value, datetime) or value.tzinfo is None
            or value.utcoffset() is None or value.microsecond != 0):
        return None
    return value.astimezone(timezone.utc)


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "LAB_THREE_HORIZON_COVERAGE_BLOCKED",
        "reason": reason,
        "decision_cutoffs_utc": {},
        "horizon_audits": {},
        "pair_count": 0,
        "pairs": {},
        "claim_only_complete_all_horizons": 0,
        "pairs_with_any_missing_or_rejected_horizon": 0,
        "three_horizon_evidence_is_independent_trials": False,
        "source_independently_authenticated": False,
        "historical_point_in_time_independently_verified": False,
        "economic_metric_comparability_validated": False,
        "monthly_directional_bias": None,
        "weekly_directional_bias": None,
        "daily_directional_bias": None,
        "calibrated_direction_probability": None,
        "validated_accuracy": None,
        "operational_bias": "AGUARDAR",
        "publishable": False,
        "live_alert_allowed": False,
        "trade_authorized": False,
        "worker_enabled": False,
        "scheduler_enabled": False,
        "http_requests": 0,
        "file_writes": 0,
        "new_cost_brl": 0,
    }


def inspect_g8_three_horizon_coverage_lab(
    *, receipts_by_horizon: Any, decision_at_by_horizon: Any,
    evaluated_at_utc: Any,
) -> dict[str, Any]:
    """Inspect three separate as-of snapshots without merging future data.

    Caller must supply snapshots filtered to the cutoff for EACH horizon.
    Receipts reused across horizons are not counted as independent observations.
    MN1 is one MONTH; M1 is a one-minute chart and is not accepted here.
    """
    evaluated = _utc(evaluated_at_utc)
    if (evaluated is None or not isinstance(receipts_by_horizon, dict)
            or not isinstance(decision_at_by_horizon, dict)
            or set(receipts_by_horizon) != set(HORIZONS)
            or set(decision_at_by_horizon) != set(HORIZONS)):
        return _blocked("INVALID_HORIZON_MAPS_OR_EVALUATION_CLOCK")

    cutoffs = {h: _utc(decision_at_by_horizon[h]) for h in HORIZONS}
    if any(cutoffs[h] is None or cutoffs[h] > evaluated for h in HORIZONS):
        return _blocked("INVALID_OR_FUTURE_HORIZON_DECISION_CUTOFF")

    # Do not impose MN1 <= W1 <= D1: month rollover can place the monthly
    # cutoff after a prior week's cutoff even when both are genuine.
    matrices: dict[str, dict[str, Any]] = {}
    for horizon in HORIZONS:
        result = inspect_g8_macro_matrix_pit_lab(
            receipts_by_horizon[horizon],
            horizon=horizon,
            decision_at_utc=cutoffs[horizon],
            evaluated_at_utc=evaluated,
        )
        if (result["state"] not in ACCEPTED
                or result["pair_count"] != len(OFFICIAL_PAIRS)
                or set(result["pairs"]) != set(OFFICIAL_PAIRS)):
            return _blocked(horizon + "_INVALID_OR_REJECTED_MATRIX_INPUT")
        matrices[horizon] = result

    audits = {
        h: {
            "decision_at_utc": cutoffs[h].isoformat(),
            "matrix_state": matrices[h]["state"],
            "complete_claim_pairs": matrices[h]["claim_only_complete_pairs"],
            "incomplete_pairs": matrices[h]["incomplete_pairs"],
            "rejected_pairs": matrices[h]["rejected_pairs"],
            "source_authenticated": False,
            "predictive_validation_completed": False,
        }
        for h in HORIZONS
    }
    pair_rows: dict[str, dict[str, Any]] = {}
    complete_count = 0
    for pair in OFFICIAL_PAIRS:
        per_horizon = {}
        for h in HORIZONS:
            row = matrices[h]["pairs"][pair]
            per_horizon[h] = {
                "metadata_claim_state": row["metadata_claim_state"],
                "missing_or_stale": list(row["missing_or_stale"]),
                "rejection_reason": row["rejection_reason"],
                "claim_only_complete": row["metadata_claim_state"] == COMPLETE,
            }
        all_complete = all(per_horizon[h]["claim_only_complete"] for h in HORIZONS)
        complete_count += int(all_complete)
        pair_rows[pair] = {
            "horizons": per_horizon,
            "all_three_claim_only_complete_not_attested": all_complete,
            "directional_agreement_checked": False,
            "directional_signal": None,
            "operational_bias": "AGUARDAR",
        }

    out = _blocked("THREE_DISTINCT_CUTOFFS_AUDITED_CLAIM_ONLY_NO_BIAS")
    out.update(
        state="LAB_THREE_HORIZON_CLAIM_COVERAGE_NO_GO",
        decision_cutoffs_utc={h: cutoffs[h].isoformat() for h in HORIZONS},
        horizon_audits=audits,
        pair_count=len(pair_rows),
        pairs=pair_rows,
        claim_only_complete_all_horizons=complete_count,
        pairs_with_any_missing_or_rejected_horizon=len(pair_rows) - complete_count,
    )
    return out


__all__ = ("SCHEMA", "HORIZONS", "inspect_g8_three_horizon_coverage_lab")
