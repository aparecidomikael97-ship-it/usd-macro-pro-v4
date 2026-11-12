"""Join two audited synthetic FX28 bilateral matrices at historical D1/W1 cutoffs.

All labels are comparative hypotheses, never directional market predictions.
This module cannot authenticate score sources, prove point-in-time facts,
calibrate probabilities, send alerts or authorize trading. LAB only.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from atlasquant_fx_universe import OFFICIAL_PAIRS
from atlasquant_trader_fx28_bilateral_symmetry_guard_lab import (
    inspect_fx28_bilateral_symmetry_lab,
)

SCHEMA = "ATLASQUANT_TRADER_FX28_D1W1_BILATERAL_AGREEMENT_LAB_V1"
ACCEPTED = "LAB_FX28_BILATERAL_COHERENT_CLAIMS_NO_GO"


def _utc(value: Any) -> datetime | None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        return None
    return value.astimezone(timezone.utc)


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "LAB_D1W1_BILATERAL_JOIN_BLOCKED",
        "reason": reason,
        "pair_count": 0,
        "pairs": {},
        "daily_ready_pair_count": 0,
        "weekly_ready_pair_count": 0,
        "concordant_hypothesis_count": 0,
        "opposing_hypothesis_count": 0,
        "neutral_hypothesis_count": 0,
        "abstained_pair_count": 0,
        "per_currency_missing_may_affect_seven_crosses": True,
        "D1_matrix_claim_consistency_verified_locally": False,
        "W1_matrix_claim_consistency_verified_locally": False,
        "source_authenticity_verified": False,
        "independent_historical_pit_verified": False,
        "weights_and_accuracy_empirically_validated": False,
        "calibrated_direction_probability": None,
        "market_bias": None,
        "operational_bias": "AGUARDAR",
        "trade_authorized": False,
        "live_alert_allowed": False,
        "publishable": False,
        "worker_enabled": False,
        "scheduler_enabled": False,
        "new_cost_brl": 0,
        "http_requests": 0,
    }


def inspect_fx28_d1w1_agreement_lab(
    *, daily_currency_scores: Any, daily_pair_claims: Any,
    weekly_currency_scores: Any, weekly_pair_claims: Any,
    daily_decision_at_utc: Any, weekly_decision_at_utc: Any,
    inspected_at_utc: Any,
) -> dict[str, Any]:
    """Classify 28 research pairs into abstain/neutral/opposition/agreement.

    Comparing daily and weekly relative hypotheses is NOT a signal; even
    fully consistent artificial scores give no authenticated market edge.
    Partial matrices and invalid time order fail closed without subset ranking.
    """
    d = _utc(daily_decision_at_utc)
    w = _utc(weekly_decision_at_utc)
    at = _utc(inspected_at_utc)
    if d is None or w is None or at is None or not w <= d <= at:
        return _blocked("D1_W1_CUTOFF_ORDER_OR_CLOCK_INVALID")
    daily = inspect_fx28_bilateral_symmetry_lab(
        currency_scores=daily_currency_scores, pair_claims=daily_pair_claims,
        horizon="D1", decision_at_utc=d, inspected_at_utc=at,
    )
    weekly = inspect_fx28_bilateral_symmetry_lab(
        currency_scores=weekly_currency_scores, pair_claims=weekly_pair_claims,
        horizon="W1", decision_at_utc=w, inspected_at_utc=at,
    )
    if daily["state"] != ACCEPTED:
        return _blocked("DAILY_MATRIX_INCOHERENT_OR_INCOMPLETE_" + daily["reason"])
    if weekly["state"] != ACCEPTED:
        return _blocked("WEEKLY_MATRIX_INCOHERENT_OR_INCOMPLETE_" + weekly["reason"])
    # The underlying audit guarantees exactly the 28 unique canonical pairs.
    drows = {r.pair: r for r in daily_pair_claims}
    wrows = {r.pair: r for r in weekly_pair_claims}
    if set(drows) != set(OFFICIAL_PAIRS) or set(wrows) != set(OFFICIAL_PAIRS):
        return _blocked("CANONICAL_PAIR_MATRIX_MISMATCH")
    pairs: dict[str, dict[str, Any]] = {}
    categories = {"CONCORDANTE_HIPOTESE": 0, "CONFLITO_D1_W1": 0,
                  "NEUTRO_EM_UM_HORIZONTE": 0, "AGUARDAR_DADOS": 0}
    for pair in OFFICIAL_PAIRS:
        dx, wx = drows[pair], wrows[pair]
        if "AGUARDAR" in (dx.relative_label, wx.relative_label):
            status = "AGUARDAR_DADOS"
        elif "NEUTRAL" in (dx.relative_label, wx.relative_label):
            status = "NEUTRO_EM_UM_HORIZONTE"
        elif dx.relative_label != wx.relative_label:
            status = "CONFLITO_D1_W1"
        else:
            status = "CONCORDANTE_HIPOTESE"
        categories[status] += 1
        pairs[pair] = {
            "state": status,
            "daily_label_synthetic": dx.relative_label,
            "weekly_label_synthetic": wx.relative_label,
            "daily_points_synthetic": dx.relative_points,
            "weekly_points_synthetic": wx.relative_points,
            "operational_bias": "AGUARDAR",
            "calibrated_probability": None,
        }
    if sum(categories.values()) != 28:
        return _blocked("CENSUS_NOT_RECONCILED")
    out = _blocked("TWO_COHERENT_SYNTHETIC_MATRICES_NO_REAL_PREDICTION")
    out.update({
        "state": "LAB_D1W1_BILATERAL_CONSISTENCY_CLASSIFIED_NO_GO",
        "pair_count": len(pairs),
        "pairs": pairs,
        "daily_ready_pair_count": daily["ready_pair_count"],
        "weekly_ready_pair_count": weekly["ready_pair_count"],
        "concordant_hypothesis_count": categories["CONCORDANTE_HIPOTESE"],
        "opposing_hypothesis_count": categories["CONFLITO_D1_W1"],
        "neutral_hypothesis_count": categories["NEUTRO_EM_UM_HORIZONTE"],
        "abstained_pair_count": categories["AGUARDAR_DADOS"],
        "D1_matrix_claim_consistency_verified_locally": True,
        "W1_matrix_claim_consistency_verified_locally": True,
    })
    return out


__all__ = ("SCHEMA", "inspect_fx28_d1w1_agreement_lab")