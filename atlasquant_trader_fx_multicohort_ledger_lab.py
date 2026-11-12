"""P0 LAB: exhaustively reconcile many 56-slot FX cohorts, without scoring.

This is a *documentary ledger*, not authenticated pre-registration. Every
caller-declared cohort is checked against its frozen 56-slot plan and census;
no pair, rejection, or entire cohort can be silently dropped *relative to the
supplied expected manifest*. Prospective external anchors, broker provenance
and actual outcomes are unverified. Nothing grants execution or publishing.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import re
from typing import Any

from atlasquant_fx_universe import OFFICIAL_PAIRS
from atlasquant_trader_fx_trial_census_lab import FrozenBlob, _verified_roster
from atlasquant_trader_fx_census_bridge_guard_lab import reconcile_full_fx_census_paired_lab
from atlasquant_trader_mt5_paired_outcome_bridge_lab import RecordedFxHypothesis

SCHEMA = "ATLASQUANT_FX_FULL_MULTICOHORT_LEDGER_LAB_V1"
COHORT_ID = re.compile(r"[A-Z0-9][A-Z0-9_-]{3,31}\Z")
MAX_COHORTS = 240


@dataclass(frozen=True)
class FrozenFxCohort:
    roster: FrozenBlob
    census: FrozenBlob
    hypotheses: tuple[RecordedFxHypothesis, ...]


@dataclass(frozen=True)
class PreparedPairHorizon:
    asset: str
    horizon: str
    expected_opportunity_ids: tuple[str, ...]
    hypotheses: tuple[RecordedFxHypothesis, ...]
    regime_vetoed_count: int


def _utc(v: Any) -> datetime | None:
    if (not isinstance(v, datetime) or v.tzinfo is None
            or v.utcoffset() is None or v.microsecond != 0):
        return None
    return v.astimezone(timezone.utc)


def _parsed(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return _utc(datetime.fromisoformat(value.replace("Z", "+00:00")))
    except (ValueError, TypeError, OverflowError):
        return None


def _blocked(reason: str, declared: int = 0) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_MULTI_COHORT_LEDGER_BLOCKED",
        "reason": reason, "failed_cohort_id": None,
        "cohorts_expected": declared, "cohorts_verified": 0,
        "slots_expected": 56 * declared, "slots_verified": 0,
        "awaiting_count": 0, "directional_noneligible_count": 0,
        "baseline_eligible_count": 0, "regime_vetoed_count": 0,
        "regime_retained_count": 0, "groups": None,
        "all_56_pair_horizon_groups_preserved": False,
        "full_declared_cohort_manifest_reconciled": False,
        "external_cohort_manifest_precommitted": False,
        "external_roster_or_census_anchors_verified": False,
        "broker_calendar_authenticated": False,
        "macro_source_vintages_authenticated": False,
        "mt5_prices_loaded": False,
        "paired_outcomes_evaluated": False,
        "validated_directional_accuracy": None,
        "calibrated_direction_probability": None,
        "operational_bias": "AGUARDAR", "publishable": False,
        "live_alert_allowed": False, "trade_authorized": False,
        "worker_enabled": False, "scheduler_enabled": False,
        "http_requests": 0, "file_writes": 0,
        "new_cost_brl": 0, "research_only": True,
    }


def build_full_fx_multicohort_ledger_lab(
    cohorts: Any, *, expected_cohort_ids: Any, as_of_utc: Any,
) -> dict[str, Any]:
    """Require 100% of caller-declared cohorts and all 56 positions in each.

    Returns all 56 pair/horizon group packets (including empty ones) for later
    *separate* assessment. Never scores a selected subset here. The declared
    cohort list is NOT independently anchored, so retrospective completeness
    or genuine out-of-sample selection is not established by this check.
    """
    now = _utc(as_of_utc)
    if (now is None or not isinstance(cohorts, (tuple, list))
            or not isinstance(expected_cohort_ids, (tuple, list))
            or not 1 <= len(cohorts) <= MAX_COHORTS
            or len(cohorts) != len(expected_cohort_ids)
            or any(not isinstance(cid, str) or COHORT_ID.fullmatch(cid) is None
                   for cid in expected_cohort_ids)
            or len(set(expected_cohort_ids)) != len(expected_cohort_ids)):
        return _blocked("INVALID_OR_INCOMPLETE_DECLARED_COHORT_MANIFEST")
    out = _blocked("UNRECONCILED", len(expected_cohort_ids))
    expected = set(expected_cohort_ids)
    encountered: set[str] = set()
    prior_plan: datetime | None = None
    fixed_rule_version: str | None = None
    seen_targets: set[tuple[str, str, int]] = set()
    seen_opportunity_ids: set[str] = set()
    groups: dict[tuple[str, str], list[RecordedFxHypothesis]] = {
        (asset, horizon): [] for horizon in ("D1", "W1") for asset in OFFICIAL_PAIRS
    }
    veto_counts = {key: 0 for key in groups}
    for declared_position, packet in enumerate(cohorts):
        if (not isinstance(packet, FrozenFxCohort)
                or not isinstance(packet.hypotheses, tuple)):
            out["reason"] = "INVALID_COHORT_PACKET_TYPE"
            return out
        plan = _verified_roster(packet.roster)
        if plan is None:
            out["reason"] = "INVALID_FROZEN_ROSTER"
            return out
        cid = plan["cohort_id"]
        out["failed_cohort_id"] = cid
        if cid not in expected or cid in encountered:
            out["reason"] = "UNKNOWN_OR_DUPLICATE_COHORT"
            return out
        if cid != expected_cohort_ids[declared_position]:
            out["reason"] = "DECLARED_COHORT_SEQUENCE_MISMATCH"
            return out
        planned_at = _parsed(plan["plan_frozen_utc_claim"])
        if (planned_at is None or planned_at > now
                or prior_plan is not None and planned_at <= prior_plan):
            out["reason"] = "COHORTS_NOT_STRICTLY_ORDERED_BY_PLAN_TIME"
            return out
        if fixed_rule_version is not None and plan["rule_version"] != fixed_rule_version:
            out["reason"] = "RULE_VERSION_CHANGED_WITHIN_FIXED_COHORT_SET"
            return out
        fixed_rule_version = plan["rule_version"]
        prior_plan = planned_at
        # Anchor of the individual source packet is still a caller's claim.
        check = reconcile_full_fx_census_paired_lab(
            packet.roster, packet.census, packet.hypotheses, as_of_utc=now,
        )
        if check["state"] != "LAB_FULL_56_CENSUS_TO_PAIRED_COVERAGE_DOCUMENTARY_NO_GO":
            out["reason"] = "INDIVIDUAL_COHORT_CENSUS_OR_PAIRED_MISMATCH"
            return out
        for slot in plan["slots"]:
            key = (slot["asset"], slot["horizon"],
                   int(_parsed(slot["target_open_utc"]).timestamp()))
            if key in seen_targets:
                out["reason"] = "DUPLICATE_TARGET_CANDLE_ACROSS_COHORTS"
                return out
            seen_targets.add(key)
            if slot["id"] in seen_opportunity_ids:
                out["reason"] = "OPPORTUNITY_ID_REUSED_ACROSS_COHORTS"
                return out
            seen_opportunity_ids.add(slot["id"])
        for hyp in packet.hypotheses:
            key = (hyp.asset, hyp.horizon)
            groups[key].append(hyp)
            veto_counts[key] += int(hyp.regime_veto)
        out["cohorts_verified"] += 1
        out["slots_verified"] += 56
        out["awaiting_count"] += check["awaiting_count"]
        out["directional_noneligible_count"] += check["directional_baseline_ineligible_count"]
        out["baseline_eligible_count"] += check["baseline_eligible_count"]
        out["regime_vetoed_count"] += check["regime_vetoed_count"]
        out["regime_retained_count"] += check["regime_retained_count"]
        encountered.add(cid)
    if encountered != expected:
        return _blocked("MISSING_DECLARED_COHORT_NO_SUBSETTING", len(expected_cohort_ids))
    if (out["awaiting_count"] + out["directional_noneligible_count"]
            + out["baseline_eligible_count"] != out["slots_expected"]
            or out["regime_vetoed_count"] + out["regime_retained_count"]
            != out["baseline_eligible_count"]):
        return _blocked("AGGREGATED_ACCOUNTING_NONCONSERVATIVE", len(expected_cohort_ids))
    payload = []
    for key, seq in groups.items():
        ordered = tuple(sorted(seq, key=lambda h: (h.target_open_epoch, h.opportunity_id)))
        payload.append(PreparedPairHorizon(
            asset=key[0], horizon=key[1],
            expected_opportunity_ids=tuple(h.opportunity_id for h in ordered),
            hypotheses=ordered, regime_vetoed_count=veto_counts[key],
        ))
    out.update({
        "groups": tuple(payload),
        "all_56_pair_horizon_groups_preserved": True,
        "full_declared_cohort_manifest_reconciled": True,
        "failed_cohort_id": None,
        "state": "LAB_ALL_DECLARED_FX_COHORTS_RECONCILED_DOCUMENTARY_NO_GO",
        "reason": "DECLARED_COHORTS_PAIRED_BUT_EXTERNAL_EVIDENCE_UNATTESTED",
    })
    return out


__all__ = ["SCHEMA", "FrozenFxCohort", "PreparedPairHorizon",
           "build_full_fx_multicohort_ledger_lab"]
