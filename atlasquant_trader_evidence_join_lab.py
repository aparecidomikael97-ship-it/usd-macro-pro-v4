"""Offline, fail-closed join of the FX macro, price and rare-bias LAB gates.

This is a missing-evidence diagnostic, NOT a new direction model. In particular,
no matching self-declared report can authenticate original sources, point-in-
time market outcomes, the event calendar, or a tradable signal.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from atlasquant_fx_universe import OFFICIAL_PAIRS
from atlasquant_mt5_backtest_gap_guard_lab import GapGuardError, window_decision
from atlasquant_mt5_calendar_gap_audit_lab import BAR_SECONDS
from atlasquant_trader_g8_macro_matrix_pit_lab import inspect_g8_macro_matrix_pit_lab
from atlasquant_trader_policy_join_veto_lab import inspect_policy_veto_for_fx_join_lab
from atlasquant_trader_economic_surprise_veto_lab import inspect_economic_surprise_veto_lab
from atlasquant_trader_market_regime_veto_lab import inspect_market_regime_veto_lab
from atlasquant_trader_selective_bias_gate_lab import (
    BiasObservation, assess_selective_bias_lab,
)

SCHEMA = "ATLASQUANT_TRADER_FX_EVIDENCE_JOIN_READONLY_LAB_V1"
TF_HORIZONS = ("D1", "W1")
PAIR_MACRO_CLAIM_ONLY = "LAB_PAIR_MACRO_METADATA_COMPLETE_UNATTESTED"


def _clock(value: Any) -> datetime | None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        return None
    return value.astimezone(timezone.utc)


def _result(reason: str, *, asset: str | None = None) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "LAB_JOIN_BLOCKED",
        "reason": reason,
        "asset": asset,
        "macro_metadata_claims": {"D1": False, "W1": False},
        "price_calendar_contiguous_claims": {"D1": False, "W1": False},
        "selective_research_state": None,
        "selective_research_reason": None,
        "rate_path_research_state": None,
        "rate_path_research_veto": True,
        "rate_path_W1_comparison": None,
        "rate_path_D1_comparison": None,
        "rate_path_source_independently_authenticated": False,
        "news_surprise_research_state": None,
        "news_surprise_research_veto": True,
        "news_surprise_W1_events": [],
        "news_surprise_D1_events": [],
        "news_surprise_originals_independently_authenticated": False,
        "regime_research_state": None,
        "regime_research_veto": True,
        "regime_W1": None,
        "regime_D1": None,
        "regime_source_independently_authenticated": False,
        "blockers": [],
        "economic_originals_authenticated": False,
        "macro_bilateral_values_comparable": False,
        "event_forecast_validated": False,
        "event_actuals_independently_verified": False,
        "market_data_historical_pit_verified": False,
        "broker_calendar_verified": False,
        "validated_directional_accuracy": None,
        "calibrated_direction_probability": None,
        "candidate_direction_for_publication": None,
        "operational_bias": "AGUARDAR",
        "publishable": False,
        "live_alert_allowed": False,
        "trade_authorized": False,
        "worker_enabled": False,
        "scheduler_enabled": False,
        "http_requests": 0,
        "new_cost_brl": 0,
        "research_only": True,
    }


def inspect_fx_evidence_join_lab(
    *, candidate: Any, previous_confirmations: Any, holdout_windows: Any,
    audit_claims: Any, receipts_by_currency: Any,
    macro_decision_at: Any, price_windows: Any, now: Any,
    high_impact_events: Any = (), unverified_event_actual_pending: bool = False,
    last_alert: Any = None, reversal_catalyst_claimed: bool = False,
    rate_expectations_snapshots_by_horizon: Any = None,
    news_events_by_horizon: Any = None,
    news_macro_captured_at_by_horizon: Any = None,
    regime_bars_by_horizon: Any = None,
) -> dict[str, Any]:
    """Join independently prepared LAB observations without issuing a bias.

    `price_windows` is {'D1': {'times': [UTC open epochs], 'first': int,
    'last': int}, 'W1': {...}}. Only closed bars at the candidate cutoff are
    admissible. Contiguous bars remain unverified, not backtest-approved.
    `macro_decision_at` contains the historically plausible D1/W1 cutoffs.
    """
    current = _clock(now)
    if current is None or not isinstance(candidate, BiasObservation):
        return _result("INVALID_CANDIDATE_OR_CLOCK")
    asset = candidate.asset if isinstance(candidate.asset, str) else None
    out = _result("REQUIRED_INDEPENDENT_PROOFS_STILL_ABSENT", asset=asset)
    candidate_at = _clock(candidate.evaluated_at)
    if candidate_at is None or candidate_at > current:
        return _result("FUTURE_OR_INVALID_CANDIDATE", asset=asset)
    if asset not in OFFICIAL_PAIRS:
        out["reason"] = ("INDEX_REQUIRES_SEPARATE_MACRO_AND_PRICE_MODEL"
                         if asset in {"WIN", "WDO", "US500", "NAS100", "US30"}
                         else "OUTSIDE_CANONICAL_28_FX_PAIRS")
        return out
    if (candidate.horizon not in TF_HORIZONS
            or not isinstance(macro_decision_at, dict)
            or set(macro_decision_at) != set(TF_HORIZONS)
            or not isinstance(price_windows, dict)
            or set(price_windows) != set(TF_HORIZONS)):
        out["reason"] = "INVALID_HORIZON_OR_LAYER_INPUTS"
        return out

    decisions = {tf: _clock(macro_decision_at[tf]) for tf in TF_HORIZONS}
    if (any(value is None or value > candidate_at for value in decisions.values())
            or decisions["W1"] > decisions["D1"]):
        out["reason"] = "MACRO_DECISIONS_AFTER_PRICE_OR_WRONG_ORDER"
        return out

    # New P0 research-only veto: always use W1 and D1 vintages at their
    # *own* decision cutoffs. Missing snapshots are an explicit blocker.
    policy = inspect_policy_veto_for_fx_join_lab(
        candidate=candidate,
        snapshots_by_horizon=rate_expectations_snapshots_by_horizon,
        decision_at_by_horizon=decisions,
        as_of_utc=current,
    )
    out["rate_path_research_state"] = policy["state"]
    out["rate_path_research_veto"] = policy["research_veto"]
    out["rate_path_W1_comparison"] = policy["W1_comparison"]
    out["rate_path_D1_comparison"] = policy["D1_comparison"]
    out["blockers"].extend("POLICY_" + reason for reason in policy["blockers"])

    # P0: no interpretation of CPI/NFP arithmetic as an automatic currency
    # direction. W1 and D1 use separate as-of event and macro snapshots.
    surprise = inspect_economic_surprise_veto_lab(
        candidate=candidate,
        events_by_horizon=news_events_by_horizon,
        decision_at_by_horizon=decisions,
        macro_captured_at_by_horizon=news_macro_captured_at_by_horizon,
        as_of_utc=current,
    )
    out["news_surprise_research_state"] = surprise["state"]
    out["news_surprise_research_veto"] = surprise["research_veto"]
    out["news_surprise_W1_events"] = surprise["W1_events"]
    out["news_surprise_D1_events"] = surprise["D1_events"]
    out["blockers"].extend("NEWS_" + reason for reason in surprise["blockers"])

    # Research-only, close-bar D1/W1 regime veto. Even complete, aligned
    # synthetic candles cannot authenticate price vintages or permit trades.
    regime = inspect_market_regime_veto_lab(
        candidate=candidate,
        bars_by_horizon=regime_bars_by_horizon,
        decision_at_by_horizon=decisions,
        as_of_utc=current,
    )
    out["regime_research_state"] = regime["state"]
    out["regime_research_veto"] = regime["research_veto"]
    out["regime_W1"] = regime["W1"]
    out["regime_D1"] = regime["D1"]
    out["blockers"].extend("REGIME_" + reason for reason in regime["blockers"])

    selective = assess_selective_bias_lab(
        candidate, previous_confirmations, holdout_windows, audit_claims,
        now=current, high_impact_events=high_impact_events,
        unverified_event_actual_pending=unverified_event_actual_pending,
        last_alert=last_alert, reversal_catalyst_claimed=reversal_catalyst_claimed,
    )
    out["selective_research_state"] = selective["state"]
    out["selective_research_reason"] = selective["reason"]
    if selective["state"] != "LAB_INTERNAL_RESEARCH_CANDIDATE_NOT_LIVE":
        out["blockers"].append("SELECTIVE_GATE_" + selective["reason"])

    for tf in TF_HORIZONS:
        # The same eight currency receipts are assessed at each real decision
        # cutoff, so a later release cannot be retroactively inserted into D1.
        macro = inspect_g8_macro_matrix_pit_lab(
            receipts_by_currency, horizon=tf, decision_at_utc=decisions[tf],
            evaluated_at_utc=current,
        )
        pair = macro.get("pairs", {}).get(asset)
        metadata_claim = bool(
            pair and pair.get("metadata_claim_state") == PAIR_MACRO_CLAIM_ONLY
        )
        out["macro_metadata_claims"][tf] = metadata_claim
        if not metadata_claim:
            out["blockers"].append(f"{tf}_PAIR_MACRO_MISSING_STALE_OR_REJECTED")

        price = price_windows[tf]
        if (not isinstance(price, dict)
                or set(price) != {"times", "first", "last"}
                or not isinstance(price["times"], list)
                or len(price["times"]) > 10_000):
            out["blockers"].append(f"{tf}_PRICE_WINDOW_INVALID")
            continue
        try:
            report = window_decision(
                asset.replace("/", ""), tf, price["times"],
                price["first"], price["last"],
            )
        except (GapGuardError, TypeError, ValueError, OverflowError):
            out["blockers"].append(f"{tf}_PRICE_WINDOW_INVALID")
            continue
        last_open = price["times"][price["last"]]
        try:
            close_at = datetime.fromtimestamp(last_open, tz=timezone.utc) + timedelta(
                seconds=BAR_SECONDS[tf])
        except (OverflowError, OSError, ValueError):
            out["blockers"].append(f"{tf}_PRICE_TIMESTAMP_INVALID")
            continue
        if close_at > candidate_at:
            out["blockers"].append(f"{tf}_PRICE_BAR_NOT_YET_CLOSED_ASOF")
        elif not report["calendar_contiguous"]:
            out["blockers"].append(f"{tf}_PRICE_GAP_REQUIRES_CALENDAR_REVIEW")
        else:
            out["price_calendar_contiguous_claims"][tf] = True

    # Deliberate hard stop: even all synthetic layers agreeing is not evidence
    # of independent source authenticity, causal edge or calibration.
    out["blockers"].extend((
        "ORIGINAL_ECONOMIC_SOURCES_AND_BILATERAL_VALUES_UNATTESTED",
        "PRICE_SOURCE_BROKER_CALENDAR_AND_PIT_UNATTESTED",
        "HIGH_IMPACT_EVENT_COVERAGE_AND_ACTUALS_UNATTESTED",
        "FORWARD_LABELS_AND_CALIBRATION_NOT_INDEPENDENTLY_VERIFIED",
    ))
    out["state"] = "LAB_CROSS_LAYER_EVIDENCE_DIAGNOSTIC_NO_GO"
    return out


__all__ = ["SCHEMA", "inspect_fx_evidence_join_lab"]
