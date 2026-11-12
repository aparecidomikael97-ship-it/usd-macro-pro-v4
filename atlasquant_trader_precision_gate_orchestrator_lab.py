"""Compose existing FX research vetoes without creating a trading signal.

A structurally concordant synthetic packet is *not* verified market evidence.
No network, broker access, orders, scheduler or side effects. The module calls
existing gates again rather than trusting caller-supplied "passed" reports.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone, timedelta
from typing import Any

from atlasquant_fx_universe import OFFICIAL_PAIRS, split_pair
from atlasquant_fx_d1_shared_calendar_gate_lab import inspect_d1_date_coverage_lab
from atlasquant_trader_fx28_d1w1_consensus_guard_lab import inspect_fx28_d1w1_agreement_lab
from atlasquant_trader_fx_evidence_dependency_gate_lab import inspect_fx_evidence_dependency_lab
from atlasquant_trader_market_regime_veto_lab import inspect_market_regime_veto_lab
from atlasquant_trader_fx_m15_price_cost_veto_lab import inspect_fx_m15_price_cost_veto_lab
from atlasquant_trader_selective_bias_gate_lab import (
    BiasObservation, SelectiveAuditClaims, assess_selective_bias_lab,
)

SCHEMA = "ATLASQUANT_TRADER_FX_PRECISION_ORCHESTRATOR_LAB_V1"
PAIR_OK = "LAB_D1W1_BILATERAL_CONSISTENCY_CLASSIFIED_NO_GO"
EVIDENCE_OK = "LAB_DOCUMENTARY_ROOT_DIVERSITY_CANDIDATE_NO_GO"
REGIME_OK = "LAB_REGIME_ALIGNMENT_DOCUMENTARY_NOT_LIVE"
PRICE_OK = "LAB_PRICE_COST_CONTEXT_NOT_VETOED_UNATTESTED"
SELECTIVE_OK = "LAB_INTERNAL_RESEARCH_CANDIDATE_NOT_LIVE"
MAX_REVIEW_AGE = timedelta(hours=12)  # research input freshness, not a calibrated edge
MAX_D1_COVERAGE_AGE_DAYS = 4  # allows weekend; not a broker session attestation
FX28_CANONICAL_SYMBOLS = tuple(p.replace("/", "") for p in OFFICIAL_PAIRS)
D1_COHORT_OK = "LAB_ALL_28_D1_BARS_PRESENT_DOCUMENTARY_UNATTESTED"


@dataclass(frozen=True)
class ResearchPacket:
    candidate: BiasObservation
    daily_currency_scores: Any
    daily_pair_claims: Any
    weekly_currency_scores: Any
    weekly_pair_claims: Any
    daily_decision_at_utc: datetime
    weekly_decision_at_utc: datetime
    factors_by_horizon: Any
    regime_bars_by_horizon: Any
    closed_m15_bars: Any
    indicative_quote: Any
    previous_confirmations: Any
    holdout_windows: Any
    audit_claims: SelectiveAuditClaims
    calendar_reviewed_at_utc: datetime
    high_impact_events: Any
    unverified_event_actual_pending: bool = False
    last_alert: Any = None
    reversal_catalyst_claimed: bool = False
    # Required for a candidate to pass the D1 completeness stage. Defaults
    # keep old packet construction possible but fail closed (not a live signal).
    d1_coverage_trading_date: date | None = None
    d1_coverage_present_symbols: Any = None
    d1_coverage_observed_at_utc: datetime | None = None


def _utc(value: Any) -> datetime | None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        return None
    return value.astimezone(timezone.utc)


def _result(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_PRECISION_ABSTAIN",
        "reason": reason, "asset": None, "horizon": None,
        "research_candidate_direction": None, "stage_reports": {},
        "blocking_stages": [reason], "blocking_reasons": [reason],
        "stages_tested": 0, "stages_structurally_passed": 0,
        "economic_event_roots_are_not_independent_trials": True,
        "market_data_and_macro_originals_independently_authenticated": False,
        "calendar_source_independently_authenticated": False,
        "calibration_prospectively_verified": False,
        "dependency_independence_statistically_proven": False,
        "broker_bid_ask_executable_verified": False,
        "net_profit_after_costs_verified": False,
        "historical_point_in_time_verified": False,
        "d1_28fx_coverage_independently_attested": False,
        "d1_28fx_coverage_claim_not_source_verified": True,
        "validated_accuracy": None, "calibrated_direction_probability": None,
        "operational_bias": "AGUARDAR", "publishable": False,
        "live_alert_allowed": False, "trade_authorized": False,
        "worker_enabled": False, "scheduler_enabled": False,
        "http_requests": 0, "file_writes": 0, "new_cost_brl": 0,
    }


def inspect_fx_precision_orchestrator_lab(*, packet: Any, inspected_at_utc: Any) -> dict[str, Any]:
    """Recalculate seven lab stages at one as-of cutoff; fail closed.

    The 'candidate' output is a research label that must NOT feed a live Radar.
    Each provider timestamp/hash and audit assertion can still be fabricated.
    """
    now = _utc(inspected_at_utc)
    if not isinstance(packet, ResearchPacket) or now is None:
        return _result("INVALID_PACKET_OR_INSPECTION_CLOCK")
    candidate = packet.candidate
    if not isinstance(candidate, BiasObservation):
        return _result("INVALID_BIAS_OBSERVATION")
    decided, daily, weekly, calendar = (
        _utc(candidate.evaluated_at), _utc(packet.daily_decision_at_utc),
        _utc(packet.weekly_decision_at_utc), _utc(packet.calendar_reviewed_at_utc),
    )
    if (not isinstance(candidate.asset, str) or candidate.asset not in OFFICIAL_PAIRS
            or candidate.horizon not in ("D1", "W1")
            or candidate.daily not in ("ALTA", "BAIXA")
            or candidate.weekly != candidate.daily or any(v is None for v in
                (decided, daily, weekly, calendar))
            or not weekly <= daily <= calendar <= decided <= now
            or decided - calendar > MAX_REVIEW_AGE
            or not isinstance(packet.factors_by_horizon, dict)
            or set(packet.factors_by_horizon) != {"D1", "W1"}
            or not isinstance(packet.high_impact_events, (tuple, list))
            or type(packet.unverified_event_actual_pending) is not bool
            or type(packet.reversal_catalyst_claimed) is not bool):
        return _result("INVALID_HORIZON_DIRECTION_CALENDAR_OR_DECISION_CUTOFF")
    if len(packet.high_impact_events) > 100 or any(_utc(v) is None for v in packet.high_impact_events):
        return _result("INVALID_HIGH_IMPACT_EVENT_WINDOW")
    out = _result("STAGES_NOT_YET_EVALUATED")
    out["asset"] = candidate.asset
    out["horizon"] = candidate.horizon
    stages: dict[str, dict[str, Any]] = {}
    blocking: list[str] = []
    reasons: list[str] = []

    def record(name: str, state: str, reason: str, okay: bool, **details: Any) -> None:
        stages[name] = {"state": state, "reason": reason,
                        "structurally_accepted": okay, **details}
        if not okay:
            blocking.append(name)
            reasons.append(f"{name}:{reason}")

    # The D1 pair matrix MUST be based on a complete declared 28-FX date
    # cohort, not on cherry-picked surviving pairs. This remains caller-
    # provided data until source/manifests and server sessions are attested.
    # Do not equate the D1 trading date to UTC midnight or a broker's NY close.
    coverage_at = _utc(packet.d1_coverage_observed_at_utc)
    trading_day = packet.d1_coverage_trading_date
    cutoff_ok = (
        type(trading_day) is date
        and coverage_at is not None
        and trading_day < daily.date()
        and 0 < (daily.date() - trading_day).days <= MAX_D1_COVERAGE_AGE_DAYS
        and datetime.combine(trading_day, datetime.min.time(), timezone.utc)
            < coverage_at <= daily
    )
    if not cutoff_ok:
        record("D1_28FX_DATE_COVERAGE", "LAB_D1_COVERAGE_CUTOFF_BLOCKED",
               "MISSING_STALE_FUTURE_OR_POST_DECISION_D1_COVERAGE", False)
    else:
        try:
            coverage = inspect_d1_date_coverage_lab(
                trading_date=trading_day,
                present_symbols=packet.d1_coverage_present_symbols,
                expected_symbols=FX28_CANONICAL_SYMBOLS,
            )
            okay = (
                coverage.get("status") == D1_COHORT_OK
                and coverage.get("rank_28fx_coverage_complete") is True
                and coverage.get("observed_count") == 28
                and coverage.get("missing_count") == 0
            )
            record(
                "D1_28FX_DATE_COVERAGE", str(coverage.get("status")),
                str(coverage.get("reason", "COVERAGE_REJECTED")), okay,
                observed_count=coverage.get("observed_count"),
                missing_symbols=coverage.get("missing_symbols"),
                d1_bar_date_claim=trading_day.isoformat(),
                independently_attested=False,
            )
        except (ValueError, TypeError, AttributeError, KeyError, OverflowError):
            record("D1_28FX_DATE_COVERAGE", "LAB_EXCEPTION_BLOCKED",
                   "INVALID_D1_DATE_COHORT", False)

    # Deliberately do not trust precomputed report dictionaries from a caller.
    # The pair matrix is checked in full (not a cherry-picked single pair).
    try:
        pair = inspect_fx28_d1w1_agreement_lab(
            daily_currency_scores=packet.daily_currency_scores,
            daily_pair_claims=packet.daily_pair_claims,
            weekly_currency_scores=packet.weekly_currency_scores,
            weekly_pair_claims=packet.weekly_pair_claims,
            daily_decision_at_utc=daily, weekly_decision_at_utc=weekly,
            inspected_at_utc=decided,
        )
        item = pair.get("pairs", {}).get(candidate.asset, {})
        expected_label = "BASE_RELATIVE" if candidate.daily == "ALTA" else "QUOTE_RELATIVE"
        accepted = (pair.get("state") == PAIR_OK
                    and item.get("state") == "CONCORDANTE_HIPOTESE"
                    and item.get("daily_label_synthetic") == expected_label
                    and item.get("weekly_label_synthetic") == expected_label)
        record("BILATERAL_D1W1", str(pair.get("state")),
               str(item.get("state", pair.get("reason", "PAIR_NOT_FOUND"))), accepted)
    except (ValueError, TypeError, AttributeError, KeyError, OverflowError):
        record("BILATERAL_D1W1", "LAB_EXCEPTION_BLOCKED", "INVALID_BILATERAL_INPUT", False)

    # The same economic root is NEVER counted as an independent sample again
    # simply because the hypothesis is reviewed on both daily and weekly.
    claimed_roots: set[str] = set()
    for horizon, cutoff in (("D1", daily), ("W1", weekly)):
        name = f"EVIDENCE_{horizon}"
        try:
            dep = inspect_fx_evidence_dependency_lab(
                asset=candidate.asset, horizon=horizon,
                factors=packet.factors_by_horizon[horizon],
                decision_at_utc=cutoff, as_of_utc=decided,
            )
            groups = dep.get("claimed_root_catalyst_groups", [])
            claimed_roots.update(g["root_catalyst_id"] for g in groups)
            direction = "BASE_RELATIVE" if candidate.daily == "ALTA" else "QUOTE_RELATIVE"
            factors = packet.factors_by_horizon[horizon]
            aligned = isinstance(factors, (list, tuple)) and all(
                f.relative_side in (direction, "NEUTRAL") for f in factors)
            okay = dep.get("state") == EVIDENCE_OK and aligned
            reason = (str(dep.get("reason")) if aligned else
                      "EVIDENCE_DIRECTION_MISMATCH_TO_PAIR_HYPOTHESIS")
            record(name, str(dep.get("state")), reason, okay,
                   factor_count=dep.get("factor_count", 0),
                   claimed_root_count=dep.get("claimed_root_catalyst_count", 0))
        except (ValueError, TypeError, AttributeError, KeyError, OverflowError):
            record(name, "LAB_EXCEPTION_BLOCKED", "INVALID_FACTOR_CLAIMS", False)

    try:
        regime = inspect_market_regime_veto_lab(
            candidate=candidate,
            bars_by_horizon=packet.regime_bars_by_horizon,
            decision_at_by_horizon={"D1": daily, "W1": weekly},
            as_of_utc=decided,
        )
        okay = regime.get("state") == REGIME_OK and regime.get("research_veto") is False
        record("MARKET_REGIME", str(regime.get("state")), str(regime.get("reason")), okay)
    except (ValueError, TypeError, AttributeError, KeyError, OverflowError):
        record("MARKET_REGIME", "LAB_EXCEPTION_BLOCKED", "INVALID_REGIME_INPUT", False)

    try:
        price = inspect_fx_m15_price_cost_veto_lab(
            asset=candidate.asset, research_side=candidate.daily,
            closed_bars=packet.closed_m15_bars,
            quote=packet.indicative_quote,
            decision_at_utc=decided, as_of_utc=decided,
        )
        okay = price.get("state") == PRICE_OK and price.get("research_veto") is False
        record("M15_PRICE_COST", str(price.get("state")), str(price.get("reason")), okay)
    except (ValueError, TypeError, AttributeError, KeyError, OverflowError):
        record("M15_PRICE_COST", "LAB_EXCEPTION_BLOCKED", "INVALID_M15_QUOTE_OR_BARS", False)

    try:
        selective = assess_selective_bias_lab(
            candidate, packet.previous_confirmations, packet.holdout_windows,
            packet.audit_claims, now=decided,
            high_impact_events=packet.high_impact_events,
            unverified_event_actual_pending=packet.unverified_event_actual_pending,
            last_alert=packet.last_alert,
            reversal_catalyst_claimed=packet.reversal_catalyst_claimed,
        )
        okay = (selective.get("state") == SELECTIVE_OK
                and selective.get("research_candidate_direction") == candidate.daily)
        record("SELECTIVE_NEWS_OOS", str(selective.get("state")), str(selective.get("reason")), okay)
    except (ValueError, TypeError, AttributeError, KeyError, OverflowError):
        record("SELECTIVE_NEWS_OOS", "LAB_EXCEPTION_BLOCKED", "INVALID_SELECTIVE_PROOF", False)

    out.update({
        "stage_reports": stages, "blocking_stages": blocking,
        "blocking_reasons": reasons, "stages_tested": len(stages),
        "stages_structurally_passed": sum(v["structurally_accepted"] for v in stages.values()),
        "claimed_unique_event_roots_across_d1w1_not_independent": len(claimed_roots),
    })
    if not blocking and len(stages) == 7:
        out.update({
            "state": "LAB_PRECISION_RESEARCH_CANDIDATE_UNATTESTED",
            "reason": "SYNTHETIC_OR_CALLER_CLAIMS_DO_NOT_PROVE_EDGE",
            "research_candidate_direction": candidate.daily,
        })
    else:
        out.update(state="LAB_PRECISION_ABSTAIN",
                   reason="ONE_OR_MORE_RESEARCH_GATES_BLOCKED")
    return out


__all__ = ("SCHEMA", "ResearchPacket", "inspect_fx_precision_orchestrator_lab")