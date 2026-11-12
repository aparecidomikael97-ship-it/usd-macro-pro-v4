"""Pure LAB reconciliation: full frozen 56-slot FX census -> paired trial inputs.

The paired MT5 historical benchmark must NEVER choose its own denominator.
Only baseline-eligible directional records are projected; every AGUARDAR,
noneligible direction and regime veto remains accounted for. This checks
self-asserted records only and cannot authenticate first-publication timestamps,
source vintages, broker calendars or forecast accuracy. NO live use.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import re
from typing import Any

from atlasquant_trader_fx_trial_census_lab import (
    FrozenBlob, _verified_roster, verify_frozen_fx_census_lab,
)
from atlasquant_trader_mt5_paired_outcome_bridge_lab import RecordedFxHypothesis

SCHEMA = "ATLASQUANT_FX_FULL_CENSUS_TO_PAIRED_BRIDGE_GUARD_LAB_V1"
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")


def _utc(value: Any) -> datetime | None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        return None
    if value.microsecond != 0:
        return None
    return value.astimezone(timezone.utc)


def _when(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return _utc(datetime.fromisoformat(value.replace("Z", "+00:00")))
    except (ValueError, OverflowError):
        return None


def _fail(reason: str, *, total: int = 0) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "LAB_CENSUS_PAIRED_COVERAGE_BLOCKED",
        "reason": reason,
        "roster_slots_expected": 56,
        "roster_slots_verified": total,
        "census_slots_verified": 0,
        "awaiting_count": None,
        "directional_baseline_ineligible_count": None,
        "baseline_eligible_count": None,
        "regime_vetoed_count": None,
        "regime_retained_count": None,
        "hypotheses_count_matched": 0,
        "expected_paired_ids": None,
        "matched_paired_ids": None,
        "per_horizon_documentary": None,
        "roster_sha256": None,
        "census_sha256": None,
        "complete_declared_denominator_reconciled": False,
        "historical_outcomes_loaded": False,
        "externally_anchored_forecasts_verified": False,
        "independent_broker_or_macro_evidence_verified": False,
        "direction_and_regime_sources_independently_verified": False,
        "holdout_accuracy_verified": False,
        "validated_directional_accuracy": None,
        "calibrated_direction_probability": None,
        "benchmark_sufficient_sample": False,
        "operational_bias": "AGUARDAR",
        "publishable": False,
        "trade_authorized": False,
        "live_alert_allowed": False,
        "scheduler_enabled": False,
        "worker_enabled": False,
        "http_requests": 0,
        "file_writes": 0,
        "new_cost_brl": 0,
        "research_only": True,
    }


def reconcile_full_fx_census_paired_lab(
    roster: Any, census: Any, hypotheses: Any, *, as_of_utc: Any,
) -> dict[str, Any]:
    """Require EVERY baseline-eligible slot even if the regime vetoes it.

    This is only the ledger/coverage gate for a SINGLE 56-slot cohort.
    A backtest's statistical denominator must be accumulated by pair/horizon
    over prospectively locked cohorts, with broker data, external anchors and
    out-of-sample windows separately verified. No outcome scoring here.
    """
    out = _fail("INVALID_FROZEN_ROSTER_CENSUS_OR_NOW")
    now = _utc(as_of_utc)
    plan = _verified_roster(roster)
    checked = verify_frozen_fx_census_lab(roster, census) if plan is not None else None
    if (now is None or plan is None or not isinstance(census, FrozenBlob)
            or not isinstance(hypotheses, (tuple, list))
            or checked is None or checked["state"] != "LAB_FULL_CENSUS_HASHED_UNATTESTED"):
        return out
    try:
        data = json.loads(census.canonical_json)
        frozen_at = _when(data["census_frozen_utc_claim"])
        if frozen_at is None or frozen_at > now:
            out["reason"] = "CENSUS_NOT_FROZEN_BY_AS_OF"
            return out
        slots = plan["slots"]
        decisions = data["decisions"]
        if len(slots) != 56 or len(decisions) != 56:
            return out
    except (TypeError, ValueError, KeyError, IndexError):
        return out

    planned_at = _when(plan["plan_frozen_utc_claim"])
    if planned_at is None or planned_at > frozen_at:
        return out
    out["roster_slots_verified"] = 56
    out["census_slots_verified"] = 56
    out["roster_sha256"] = roster.sha256
    out["census_sha256"] = census.sha256
    expected: dict[str, tuple[dict, dict]] = {}
    per_horizon = {tf: {"total": 0, "AGUARDAR": 0,
                         "directional_noneligible": 0,
                         "baseline_eligible": 0, "regime_vetoed": 0}
                   for tf in ("D1", "W1")}
    for slot, decision in zip(slots, decisions):
        if slot["id"] != decision["id"]:
            out["reason"] = "FROZEN_SLOT_ORDER_OR_ID_MISMATCH"
            return out
        tf = slot["horizon"]
        per_horizon[tf]["total"] += 1
        if decision["side"] == "AGUARDAR":
            per_horizon[tf]["AGUARDAR"] += 1
        elif decision["baseline_eligible"]:
            per_horizon[tf]["baseline_eligible"] += 1
            per_horizon[tf]["regime_vetoed"] += int(decision["regime_veto"] is True)
            expected[slot["id"]] = (slot, decision)
        else:
            per_horizon[tf]["directional_noneligible"] += 1

    out["per_horizon_documentary"] = per_horizon
    out["awaiting_count"] = sum(t["AGUARDAR"] for t in per_horizon.values())
    out["directional_baseline_ineligible_count"] = sum(
        t["directional_noneligible"] for t in per_horizon.values())
    out["baseline_eligible_count"] = len(expected)
    out["regime_vetoed_count"] = sum(t["regime_vetoed"] for t in per_horizon.values())
    out["regime_retained_count"] = len(expected) - out["regime_vetoed_count"]
    out["expected_paired_ids"] = list(expected)
    if (out["awaiting_count"] + out["directional_baseline_ineligible_count"]
            + len(expected) != 56):
        out["reason"] = "CENSUS_ACCOUNTING_NONCONSERVATIVE"
        return out

    if len(hypotheses) != len(expected):
        out["reason"] = "BASELINE_ELIGIBLE_DENOMINATOR_MISMATCH_NO_SUBSETTING"
        return out
    seen: set[str] = set()
    for hyp in hypotheses:
        if not isinstance(hyp, RecordedFxHypothesis):
            out["reason"] = "INVALID_PAIRED_HYPOTHESIS_TYPE"
            return out
        if not isinstance(hyp.opportunity_id, str) or hyp.opportunity_id in seen:
            out["reason"] = "DUPLICATE_PAIRED_OPPORTUNITY_ID"
            return out
        seen.add(hyp.opportunity_id)
        if hyp.opportunity_id not in expected:
            out["reason"] = "PAIRED_ID_NOT_BASELINE_ELIGIBLE_IN_CENSUS"
            return out
        slot, d = expected[hyp.opportunity_id]
        recorded, target = _when(d["recorded_utc_claim"]), _when(slot["target_open_utc"])
        locked, decided, regime = (
            _utc(hyp.prediction_locked_at), _utc(hyp.decided_at),
            _utc(hyp.regime_observed_at),
        )
        if (recorded is None or target is None or locked is None
                or decided is None or regime is None or not regime <= decided
                or not planned_at <= locked <= decided or decided != recorded
                or not decided < target or decided > now):
            out["reason"] = "PAIRED_FORECAST_CLOCK_DIFFERS_FROM_FROZEN_CENSUS"
            return out
        if (hyp.asset != slot["asset"] or hyp.horizon != slot["horizon"]
                or hyp.candidate_direction != d["side"]
                or type(hyp.target_open_epoch) is not int
                or hyp.target_open_epoch != int(target.timestamp())
                or hyp.baseline_eligible is not True
                or type(hyp.regime_veto) is not bool
                or hyp.regime_veto != d["regime_veto"]):
            out["reason"] = "PAIRED_SIDE_HORIZON_TARGET_OR_VETO_CHANGED"
            return out
        if (any(not isinstance(x, str) or _HEX64.fullmatch(x) is None for x in (
                hyp.decision_sha256_claim, hyp.regime_source_sha256_claim))):
            out["reason"] = "PAIRED_SOURCE_HASH_CLAIM_MALFORMED"
            return out
    if seen != set(expected):
        out["reason"] = "BASELINE_ELIGIBLE_DENOMINATOR_MISMATCH_NO_SUBSETTING"
        return out
    out["hypotheses_count_matched"] = len(seen)
    out["matched_paired_ids"] = sorted(seen)
    out["complete_declared_denominator_reconciled"] = True
    out["state"] = "LAB_FULL_56_CENSUS_TO_PAIRED_COVERAGE_DOCUMENTARY_NO_GO"
    out["reason"] = "CENSUS_AND_PAIR_LEDGER_RECONCILED_BUT_ORIGINS_UNATTESTED"
    return out


__all__ = ["SCHEMA", "reconcile_full_fx_census_paired_lab"]
