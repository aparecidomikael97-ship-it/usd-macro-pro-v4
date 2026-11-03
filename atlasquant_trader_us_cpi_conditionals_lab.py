"""Pre-event US CPI conditional playbook for FX and indices, LAB only.

All branches are mutually exclusive hypothetical *IF* stories, not weighted
probabilities or selected directional forecasts. A CPI nowcast is not the
market's consensus, and interest-rate or equity effects are regime-dependent.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from atlasquant_fx_universe import OFFICIAL_PAIRS, split_pair
from atlasquant_trader_exante_macro_scenarios_lab import HORIZONS, INDICES
from atlasquant_trader_cpi_prospective_freeze_lab import (
    inspect_cpi_prospective_freeze_lab,
)

SCHEMA = "ATLASQUANT_TRADER_US_CPI_CONDITIONAL_IMPACT_LAB_V1"
BRANCHES = (
    "INFLATION_UPSIDE_AND_HAWKISH_REPRICING",
    "INFLATION_DOWNSIDE_AND_DOVISH_REPRICING",
    "MIXED_CORE_OR_GEOPOLITICAL_RISK",
)
US_INDICES = frozenset(("SPX500", "NAS100", "US30"))
INDEX_CONDITIONS = {
    "INFLATION_UPSIDE_AND_HAWKISH_REPRICING": (
        "CPI_ACTUAL_ABOVE_VERIFIED_PRE_RELEASE_CONSENSUS",
        "US_REAL_YIELDS_RISE", "US_EARNINGS_DO_NOT_OFFSET_HIGHER_DISCOUNT_RATE",
        "NO_GROWTH_OR_GEOPOLITICAL_OVERRIDE",
    ),
    "INFLATION_DOWNSIDE_AND_DOVISH_REPRICING": (
        "CPI_ACTUAL_BELOW_VERIFIED_PRE_RELEASE_CONSENSUS",
        "US_REAL_YIELDS_FALL", "US_GROWTH_NOT_REPRICED_AS_RECESSION",
        "NO_GEOPOLITICAL_RISK_OFF_OVERRIDE",
    ),
}
SCENARIO_CONDITIONS = {
    BRANCHES[0]: (
        "CPI_ACTUAL_ABOVE_VERIFIED_PRE_RELEASE_CONSENSUS",
        "CORE_CPI_CORROBORATES",
        "USD_EXPECTED_RATE_PATH_MORE_HAWKISH_THAN_PEER",
        "RELATIVE_YIELDS_REPRICE_IN_USD_FAVOR",
        "GEOPOLITICS_AND_RISK_DO_NOT_OVERRIDE",
    ),
    BRANCHES[1]: (
        "CPI_ACTUAL_BELOW_VERIFIED_PRE_RELEASE_CONSENSUS",
        "CORE_CPI_CORROBORATES",
        "USD_EXPECTED_RATE_PATH_MORE_DOVISH_THAN_PEER",
        "RELATIVE_YIELDS_REPRICE_AGAINST_USD",
        "NO_RECESSION_OR_RISK_OFF_OVERRIDE",
    ),
    BRANCHES[2]: (
        "CPI_CORE_OR_RISK_CHANNELS_CONFLICT",
        "DO_NOT_FORCE_DIRECTION_FROM_HEADLINE",
    ),
}


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_CPI_CONDITIONAL_FANOUT_BLOCKED",
        "reason": reason, "branches": list(BRANCHES), "pair_scenarios": [],
        "index_scenarios": [], "selected_branch": None,
        "actual_cpi": None, "consensus": None,
        "conditional_hypotheses_are_real_forecasts": False,
        "market_probability_calibrated": None, "accuracy_90_proven": False,
        "historical_oos_verified": False, "can_feed_live_radar": False,
        "trade_authorized": False, "worker_enabled": False,
        "scheduler_enabled": False,
    }


def build_us_cpi_conditional_impact_lab(
    prospective_snapshot: Any, *, evaluated_at: datetime,
) -> dict[str, Any]:
    """Fan out three if-then branches without selecting/activating any."""
    freeze = inspect_cpi_prospective_freeze_lab(
        prospective_snapshot, evaluated_at=evaluated_at,
    )
    if freeze["state"] != "LAB_PROSPECTIVE_DOCUMENTARY_NOWCAST_PRE_EVENT":
        return _blocked("Pre-event observed-nowcast freeze unavailable or event passed")
    pair_rows, index_rows = [], []
    for branch in BRANCHES:
        common = SCENARIO_CONDITIONS[branch]
        for horizon in HORIZONS:
            persistent = ("POLICY_REPRICING_PERSISTS_THROUGH_WEEK",) if horizon == "W1" else ()
            for pair in OFFICIAL_PAIRS:
                base, quote = split_pair(pair)
                # USD is the affected leg. Foreign rate paths and safe havens
                # are not automatically inferred from this US event.
                if (horizon == "MN1" or branch == BRANCHES[2]
                        or "USD" not in (base, quote)):
                    hypothesis = "AGUARDAR"
                    explanation = "No month-long or non-USD relative macro conclusion"
                    conditions = []
                else:
                    usd_base = base == "USD"
                    usd_support = branch == BRANCHES[0]
                    hypothesis = ("ALTA_CONDICIONAL" if usd_base == usd_support
                                  else "BAIXA_CONDICIONAL")
                    explanation = "USD relative to peer IF all monetary/risk assumptions hold"
                    conditions = list(common + persistent)
                pair_rows.append({
                    "branch": branch, "horizon": horizon, "pair": pair,
                    "bias_if_conditions": hypothesis,
                    "condition_chain": conditions, "why": explanation,
                    "branch_selected": False, "entry_signal": False,
                    "trade_authorized": False, "probability_calibrated": None,
                })
            for symbol in INDICES:
                if (horizon == "MN1" or branch == BRANCHES[2]
                        or symbol not in US_INDICES):
                    hypothesis = "AGUARDAR"
                    conditions = []
                    explanation = "Index requires its own rate, growth and risk model"
                else:
                    # This is a conditional discount-rate branch, not an
                    # equity forecast. Earnings/growth can overpower yields.
                    upside = branch == BRANCHES[0]
                    hypothesis = ("BAIXA_CONDICIONAL" if upside
                                  else "ALTA_CONDICIONAL")
                    index_persistence = (
                        ("US_REAL_YIELD_MOVE_PERSISTS_THROUGH_WEEK",)
                        if horizon == "W1" else ()
                    )
                    conditions = list(INDEX_CONDITIONS[branch] + index_persistence)
                    explanation = "US equity IF yields, earnings and risk transmit as posited"
                index_rows.append({
                    "branch": branch, "horizon": horizon, "symbol": symbol,
                    "bias_if_conditions": hypothesis,
                    "condition_chain": conditions, "why": explanation,
                    "branch_selected": False, "entry_signal": False,
                    "trade_authorized": False, "probability_calibrated": None,
                })
    return {
        **_blocked(""),
        "state": "LAB_HYPOTHETICAL_UNSELECTED_CPI_BRANCHES_ONLY",
        "reason": "All branches are hypothetical; not an issued market prediction",
        "context_model_nowcast": freeze["forecast"],
        "prospective_snapshot_sha256": freeze["snapshot_sha256"],
        "branches": [{"branch": b, "must_all_hold": list(SCENARIO_CONDITIONS[b]),
                      "selected": False} for b in BRANCHES],
        "pair_scenarios": pair_rows, "index_scenarios": index_rows,
        "bias_primary": "AGUARDAR",
        "market_consensus_available": False,
        "relative_policy_paths_verified": False,
        "geopolitics_alignment_verified": False,
        "can_feed_live_radar": False,
    }


__all__ = ["SCHEMA", "BRANCHES", "build_us_cpi_conditional_impact_lab"]
