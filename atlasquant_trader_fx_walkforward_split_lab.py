"""Chronological, embargoed train/validation/test split for FX bias trials.

This is an OFFLINE structure auditor. All prices, model SHA claims, source
clocks and trial creation times are caller-supplied; no real backtest,
out-of-sample result, trained model, broker costs or accuracy is certified.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import re
from typing import Any

from atlasquant_fx_universe import OFFICIAL_PAIRS
from atlasquant_trader_fx_bias_quality_lab import (
    BiasTrial, HORIZONS, inspect_fx_bias_quality_claims_lab,
)

SCHEMA = "ATLASQUANT_TRADER_FX_WALK_FORWARD_SPLIT_LAB_V1"
_HEX = re.compile(r"[0-9a-f]{64}\Z")
MIN_EMBARGO_DAYS = {"D1": 1, "W1": 7, "M1": 31}
HORIZON_LABEL_DURATION_DAYS = {"D1": (1, 4), "W1": (7, 10), "M1": (28, 35)}


@dataclass(frozen=True)
class WalkForwardPlan:
    train_start_at: datetime
    train_end_at: datetime
    validation_start_at: datetime
    validation_end_at: datetime
    test_start_at: datetime
    test_end_at: datetime
    candidate_model_frozen_at: datetime
    final_model_frozen_at: datetime
    candidate_model_sha256_claim: str
    final_model_sha256_claim: str
    embargo_days: int


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_WALK_FORWARD_BLOCKED", "reason": reason,
        "pair": None, "horizon": None,
        "training_trial_count": 0, "validation_trial_count": 0,
        "test_trial_count": 0, "embargo_days": None,
        "caller_supplied_model_hashes_only": False,
        "timestamps_independently_authenticated": False,
        "features_point_in_time_verified": False,
        "price_outcomes_independently_verified": False,
        "cross_pair_correlation_audited": False,
        "out_of_sample_accuracy_validated": False,
        "training_or_model_fit_performed": False,
        "validated_accuracy": None, "calibrated_probability": None,
        "bias_direction": None, "operational_bias": "AGUARDAR",
        "trade_authorized": False, "publishable": False,
        "worker_enabled": False, "scheduler_enabled": False,
        "http_requests": 0, "file_writes": 0, "new_cost_brl": 0,
    }


def _t(v: Any) -> datetime | None:
    if (not isinstance(v, datetime) or v.tzinfo is None
            or v.utcoffset() is None or v.microsecond != 0):
        return None
    return v.astimezone(timezone.utc)


def inspect_fx_walkforward_split_lab(
    trials: Any, plan: Any, *, pair: str, horizon: str,
    evaluated_at_utc: datetime,
) -> dict[str, Any]:
    """Reject overlapping folds, model refits, and future/out-of-window labels.

    No accuracy is returned: this checks only structural chronology and the
    caller's claimed model-freeze times, NOT real independent OOS quality.
    """
    out = _blocked("INVALID_PLAN_TRIALS_OR_EVALUATION_TIME")
    evaluation = _t(evaluated_at_utc)
    if (pair not in OFFICIAL_PAIRS or horizon not in HORIZONS
            or not isinstance(plan, WalkForwardPlan)
            or not isinstance(trials, (list, tuple))
            or not 3 <= len(trials) <= 10_000 or evaluation is None
            or type(plan.embargo_days) is not int
            or not MIN_EMBARGO_DAYS[horizon] <= plan.embargo_days <= 180
            or not isinstance(plan.candidate_model_sha256_claim, str)
            or _HEX.fullmatch(plan.candidate_model_sha256_claim) is None
            or not isinstance(plan.final_model_sha256_claim, str)
            or _HEX.fullmatch(plan.final_model_sha256_claim) is None):
        return out
    stamps = [_t(getattr(plan, key)) for key in (
        "train_start_at", "train_end_at", "validation_start_at",
        "validation_end_at", "test_start_at", "test_end_at",
        "candidate_model_frozen_at", "final_model_frozen_at")]
    if any(s is None for s in stamps):
        return out
    train_start, train_end, val_start, val_end, test_start, test_end, candidate, final = stamps
    embargo = timedelta(days=plan.embargo_days)
    if (not train_start < train_end < val_start < val_end < test_start < test_end <= evaluation
            or val_start - train_end < embargo
            or test_start - val_end < embargo
            or not train_end <= candidate <= val_start
            or not val_end <= final <= test_start):
        out["reason"] = "SPLIT_EMBARGO_OR_MODEL_FREEZE_CHRONOLOGY_INVALID"
        return out

    partitions: dict[str, list[BiasTrial]] = {"train": [], "validation": [], "test": []}
    windows = (
        ("train", train_start, train_end),
        ("validation", val_start, val_end),
        ("test", test_start, test_end),
    )
    ids = set()
    for trial in trials:
        if (not isinstance(trial, BiasTrial) or trial.pair != pair
                or trial.horizon != horizon or trial.trial_id in ids):
            out["reason"] = "TRIAL_OWNER_HORIZON_OR_ID_INVALID"
            return out
        ids.add(trial.trial_id)
        issued, started, ended, captured = (_t(trial.prediction_issued_at),
                                           _t(trial.outcome_start_at),
                                           _t(trial.outcome_end_at),
                                           _t(trial.outcome_captured_at))
        if any(t is None for t in (issued, started, ended, captured)):
            out["reason"] = "TRIAL_CLOCK_INVALID"
            return out
        matches = [name for name, start, end in windows
                   if start <= issued < start + (end - start)]
        if len(matches) != 1:
            out["reason"] = "TRIAL_ISSUED_IN_EMBARGO_GAP_OR_OUTSIDE_PLAN"
            return out
        shortest, longest = HORIZON_LABEL_DURATION_DAYS[horizon]
        if not (timedelta(days=shortest) <= ended - started <=
                timedelta(days=longest)):
            out["reason"] = "FORWARD_LABEL_DURATION_NOT_MATCHING_HORIZON"
            return out
        fold = matches[0]
        cutoff = next(end for name, _, end in windows if name == fold)
        if (not issued < started < ended <= captured <= cutoff
                or (fold == "validation" and issued < candidate)
                or (fold == "test" and issued < final)):
            out["reason"] = "FORWARD_LABEL_LEAKS_ACROSS_FOLD_OR_UNAVAILABLE"
            return out
        partitions[fold].append(trial)

    if any(not rows for rows in partitions.values()):
        out["reason"] = "EMPTY_FOLD_CANNOT_CLAIM_WALK_FORWARD"
        return out
    for name, rows in partitions.items():
        cutoff = next(end for fold, _, end in windows if fold == name)
        audit = inspect_fx_bias_quality_claims_lab(
            rows, pair=pair, horizon=horizon, evaluated_at_utc=cutoff)
        if audit["state"] != "LAB_BIAS_QUALITY_SYNTHETIC_OR_CALLER_CLAIM_ACCOUNTED_NO_GO":
            out["reason"] = "TRIAL_QUALITY_GATE_FAILED_" + name.upper()
            return out
    out.update({
        "state": "LAB_WALK_FORWARD_FOLDS_STRUCTURALLY_ISOLATED_UNATTESTED",
        "reason": "STRUCTURAL_SPLIT_ONLY_NO_SOURCE_OR_OOS_MODEL_AUTHENTICATION",
        "pair": pair, "horizon": horizon, "embargo_days": plan.embargo_days,
        "training_trial_count": len(partitions["train"]),
        "validation_trial_count": len(partitions["validation"]),
        "test_trial_count": len(partitions["test"]),
        "caller_supplied_model_hashes_only": True,
    })
    return out


__all__ = ["SCHEMA", "WalkForwardPlan", "MIN_EMBARGO_DAYS",
           "inspect_fx_walkforward_split_lab"]
