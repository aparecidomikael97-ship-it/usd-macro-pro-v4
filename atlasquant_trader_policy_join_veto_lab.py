"""Fail-closed research integration of G8 policy-path contradictions with FX bias gate.

All supplied futures/OIS quotes, timestamps and fingerprints are caller claims.
A documentary alignment is never proof of edge, source provenance or a live bias.
No filesystem, network, scheduler, alert, broker or trade side effect.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from atlasquant_fx_universe import OFFICIAL_PAIRS
from atlasquant_trader_policy_expectations_conflict_lab import (
    inspect_policy_expectations_d1_w1_lab,
)

SCHEMA = "ATLASQUANT_TRADER_POLICY_TO_FX_EVIDENCE_JOIN_VETO_LAB_V1"
_GOOD = "LAB_D1_W1_POLICY_EXPECTATION_REVIEW_NO_GO"


def _utc(value: Any) -> datetime | None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        return None
    return value.astimezone(timezone.utc)


def _blocked(reason: str, *, asset: str | None = None) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "LAB_POLICY_JOIN_ABSTAIN",
        "reason": reason,
        "asset": asset,
        "research_veto": True,
        "blockers": [reason],
        "W1_comparison": None,
        "D1_comparison": None,
        "documentary_alignment_is_authorization": False,
        "rate_path_source_independently_authenticated": False,
        "rate_instruments_independently_comparable": False,
        "historical_rate_vintages_point_in_time_verified": False,
        "incremental_direction_accuracy_validated": None,
        "calibrated_direction_probability": None,
        "research_direction_for_publication": None,
        "operational_bias": "AGUARDAR",
        "publishable": False,
        "live_alert_allowed": False,
        "trade_authorized": False,
        "worker_enabled": False,
        "scheduler_enabled": False,
        "http_requests": 0,
        "file_writes": 0,
        "new_cost_brl": 0,
        "research_only": True,
    }


def inspect_policy_veto_for_fx_join_lab(
    *, candidate: Any, snapshots_by_horizon: Any,
    decision_at_by_horizon: Any, as_of_utc: Any,
) -> dict[str, Any]:
    """Link claimed D1/W1 policy shifts to a candidate, vetoing unsafe scenarios.

    The official 28-pair router still needs real, externally witnessed snapshots.
    Passing here ONLY means no documentary contradiction at the declared cutoffs.
    """
    asset = getattr(candidate, "asset", None)
    if not isinstance(asset, str):
        return _blocked("INVALID_RESEARCH_CANDIDATE")
    if asset not in OFFICIAL_PAIRS:
        return _blocked("OUTSIDE_FX_28_OR_INDEX_REQUIRES_OWN_MODEL", asset=asset)
    now = _utc(as_of_utc)
    evaluated_at = _utc(getattr(candidate, "evaluated_at", None))
    if now is None or evaluated_at is None or evaluated_at > now:
        return _blocked("INVALID_FUTURE_OR_NAIVE_CANDIDATE_CLOCK", asset=asset)
    if getattr(candidate, "horizon", None) not in ("D1", "W1"):
        return _blocked("INVALID_D1_W1_HORIZON", asset=asset)
    daily, weekly = getattr(candidate, "daily", None), getattr(candidate, "weekly", None)
    if daily not in ("ALTA", "BAIXA") or weekly not in ("ALTA", "BAIXA"):
        return _blocked("D1_OR_W1_DIRECTION_MISSING", asset=asset)
    if daily != weekly:
        return _blocked("D1_W1_DIRECTION_CONTRADICTION", asset=asset)
    if (not isinstance(decision_at_by_horizon, dict)
            or set(decision_at_by_horizon) != {"D1", "W1"}):
        return _blocked("INVALID_HORIZON_CUTOFF_MAP", asset=asset)
    d, w = (_utc(decision_at_by_horizon["D1"]),
            _utc(decision_at_by_horizon["W1"]))
    if d is None or w is None or not w <= d <= evaluated_at:
        return _blocked("RATE_HORIZON_CUTOFF_ORDER_OR_FUTURE", asset=asset)
    if snapshots_by_horizon is None:
        return _blocked("RATE_EXPECTATION_SNAPSHOTS_NOT_SUPPLIED", asset=asset)

    report = inspect_policy_expectations_d1_w1_lab(
        snapshots_by_horizon=snapshots_by_horizon,
        decision_at_by_horizon={"D1": d, "W1": w},
        candidate_directions_by_horizon={"D1": {asset: daily}, "W1": {asset: weekly}},
        as_of_utc=now,
    )
    if report["state"] != _GOOD:
        return _blocked("RATE_EXPECTATION_PIT_OR_SHAPE_REJECTED", asset=asset)
    pair_rows = [r for r in report["pair_rows"] if r["pair"] == asset]
    if len(pair_rows) != 1 or report["pair_count"] != 28:
        return _blocked("RATE_EXPECTATION_PAIR_JOIN_INCONSISTENT", asset=asset)
    pair = pair_rows[0]
    contradictions = bool(pair["research_contradiction_in_either_horizon"])
    unavailable = bool(pair["rate_data_unavailable_or_incomparable_in_either_horizon"])
    blockers = []
    if contradictions:
        blockers.append("RATE_EXPECTATIONS_CONTRADICT_RESEARCH_DIRECTION")
    if unavailable:
        blockers.append("RATE_EXPECTATIONS_MISSING_STALE_OR_INCOMPARABLE")
    out = _blocked("RATE_PATH_CONTEXT_CLAIM_ONLY_NOT_AUTHENTICATED", asset=asset)
    out.update({
        "state": ("LAB_POLICY_JOIN_RESEARCH_VETO" if blockers
                  else "LAB_POLICY_JOIN_NO_DOCUMENTARY_CONFLICT_NO_GO"),
        "reason": ("POLICY_CONTRADICTION_OR_MISSING_CONTEXT" if blockers
                   else "NO_POLICY_CONFLICT_IS_NOT_PROVEN_PREDICTIVE_EDGE"),
        "research_veto": bool(blockers),
        "blockers": blockers,
        "W1_comparison": pair["W1_comparison"],
        "D1_comparison": pair["D1_comparison"],
    })
    return out


__all__ = ["SCHEMA", "inspect_policy_veto_for_fx_join_lab"]
