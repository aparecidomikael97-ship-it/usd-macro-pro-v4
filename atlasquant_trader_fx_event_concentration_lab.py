"""Audit shared economic roots across FX research candidates, offline only.

One US PPI event affecting seven USD crosses is NOT seven independent event
trials. This is a documentary portfolio-risk inventory, not a position sizing
tool, a correlation estimator, a broker exposure limit, or a live signal.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from atlasquant_fx_universe import OFFICIAL_PAIRS, split_pair
from atlasquant_trader_fx_evidence_dependency_gate_lab import (
    FactorClaim, inspect_fx_evidence_dependency_lab,
)

SCHEMA = "ATLASQUANT_FX_SHARED_EVENT_CONCENTRATION_LAB_V1"
MAX_CANDIDATES = 56  # 28 canonical FX pairs x D1/W1
HORIZONS = frozenset({"D1", "W1"})
SIDES = frozenset({"ALTA", "BAIXA"})


@dataclass(frozen=True)
class ResearchCandidate:
    asset: str
    horizon: str
    side: str
    decision_at_utc: datetime
    factors: tuple[FactorClaim, ...]


def _clock(value: Any) -> datetime | None:
    if (not isinstance(value, datetime) or value.tzinfo is None
            or value.utcoffset() is None or value.microsecond):
        return None
    return value.astimezone(timezone.utc)


def _base(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_EVENT_CONCENTRATION_BLOCKED",
        "reason": reason, "candidate_observations": 0,
        "distinct_assets": 0, "claimed_event_roots": 0,
        "shared_event_root_groups": [], "event_root_inventory": [],
        "currency_exposure_conflicts": [],
        "independent_event_trial_count": None,
        "event_causality_independently_verified": False,
        "cross_pair_correlation_statistically_estimated": False,
        "broker_notional_and_executable_liquidity_verified": False,
        "portfolio_risk_approved": False,
        "directional_probability": None, "validated_accuracy": None,
        "operational_bias": "AGUARDAR", "publishable": False,
        "live_alert_allowed": False, "trade_authorized": False,
        "worker_enabled": False, "scheduler_enabled": False,
        "http_requests": 0, "file_writes": 0, "new_cost_brl": 0,
    }


def audit_fx_shared_event_concentration_lab(
    *, candidates: Any, inspected_at_utc: Any,
) -> dict[str, Any]:
    """Group candidate hypotheses by caller-claimed root, never by signal count.

    Each factor is checked again with the existing per-pair dependency gate.
    Passing this inventory NEVER proves external timestamps, event independence,
    a causal driver of either currency, profitability, or portfolio safety.
    """
    now = _clock(inspected_at_utc)
    if (now is None or not isinstance(candidates, (list, tuple))
            or not 1 <= len(candidates) <= MAX_CANDIDATES):
        return _base("INVALID_INSPECTION_CLOCK_OR_CANDIDATE_COLLECTION")

    roots: dict[str, dict[str, Any]] = {}
    pair_horizons: set[tuple[str, str]] = set()
    asset_sides: dict[str, str] = {}
    out = _base("NOT_AUDITED")
    for candidate in candidates:
        if not isinstance(candidate, ResearchCandidate):
            return _base("INVALID_CANDIDATE_TYPE")
        decision = _clock(candidate.decision_at_utc)
        if (not isinstance(candidate.asset, str)
                or candidate.asset not in OFFICIAL_PAIRS
                or candidate.horizon not in HORIZONS
                or candidate.side not in SIDES
                or decision is None or decision > now
                or not isinstance(candidate.factors, (tuple, list))):
            return _base("INVALID_ASSET_DIRECTION_CUTOFF_OR_FACTOR_TYPE")
        key = (candidate.asset, candidate.horizon)
        if key in pair_horizons:
            return _base("DUPLICATED_PAIR_HORIZON_IS_NOT_A_NEW_TRIAL")
        pair_horizons.add(key)
        if candidate.asset in asset_sides and asset_sides[candidate.asset] != candidate.side:
            return _base("D1_W1_DIRECTION_CONFLICT_ABSTAIN")
        asset_sides[candidate.asset] = candidate.side

        evidence = inspect_fx_evidence_dependency_lab(
            asset=candidate.asset, horizon=candidate.horizon,
            factors=candidate.factors, decision_at_utc=decision, as_of_utc=now,
        )
        expected = "BASE_RELATIVE" if candidate.side == "ALTA" else "QUOTE_RELATIVE"
        non_neutral = {factor.relative_side for factor in candidate.factors
                       if isinstance(factor, FactorClaim) and
                       factor.relative_side != "NEUTRAL"}
        if (evidence["state"] not in {
                "LAB_DOCUMENTARY_ROOT_DIVERSITY_CANDIDATE_NO_GO",
                "LAB_INSUFFICIENT_DISTINCT_CATALYSTS_ABSTAIN"}
                or non_neutral != {expected}):
            return _base("FACTOR_PROVENANCE_OR_DIRECTION_DISAGREES_WITH_HYPOTHESIS")
        base, quote = split_pair(candidate.asset)
        exposure = {base: "LONG" if candidate.side == "ALTA" else "SHORT",
                    quote: "SHORT" if candidate.side == "ALTA" else "LONG"}
        for group in evidence["claimed_root_catalyst_groups"]:
            root = group["root_catalyst_id"]
            row = roots.setdefault(root, {"assets": set(), "horizons": set(),
                                          "observations": 0, "currency_sides": {}})
            row["assets"].add(candidate.asset)
            row["horizons"].add(candidate.horizon)
            row["observations"] += 1
            for currency, direction in exposure.items():
                row["currency_sides"].setdefault(currency, set()).add(direction)

    inventory = []
    conflicts = []
    for root, row in sorted(roots.items()):
        directions = {cur: sorted(sides) for cur, sides in
                      sorted(row["currency_sides"].items())}
        for currency, sides in directions.items():
            if len(sides) > 1:
                conflicts.append({"root_catalyst_id": root, "currency": currency,
                                  "opposing_candidate_exposures": sides})
        inventory.append({
            "root_catalyst_id": root,
            "candidate_observations": row["observations"],
            "distinct_assets": len(row["assets"]),
            "assets": sorted(row["assets"]),
            "horizons": sorted(row["horizons"]),
            "currency_exposure_claims_not_root_causality": directions,
        })
    shared = [row for row in inventory if row["distinct_assets"] > 1]
    out.update({
        "candidate_observations": len(candidates),
        "distinct_assets": len(asset_sides),
        "claimed_event_roots": len(inventory),
        "event_root_inventory": inventory,
        "shared_event_root_groups": shared,
        "currency_exposure_conflicts": conflicts,
    })
    if conflicts:
        out.update(state="LAB_EVENT_EXPOSURE_CONFLICT_ABSTAIN",
                   reason="SAME_CLAIMED_ROOT_OPPOSING_CURRENCY_EXPOSURES")
    elif shared:
        out.update(state="LAB_SHARED_ROOT_EXPOSURE_REVIEW_REQUIRED",
                   reason="CROSS_PAIR_CANDIDATES_ARE_NOT_INDEPENDENT_EVENT_TRIALS")
    else:
        out.update(state="LAB_ROOT_INVENTORY_UNATTESTED_NO_GO",
                   reason="NO_SHARED_ROOT_CLAIM_DOES_NOT_PROVE_INDEPENDENCE")
    return out


__all__ = ("SCHEMA", "ResearchCandidate", "audit_fx_shared_event_concentration_lab")
