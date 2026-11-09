"""Strictly retrospective D1/W1 economic surprise review for FX evidence joining.

Consumes the existing G8 event relevance router; never converts an economic
surprise into bullish/bearish FX direction. Caller-provided sources and timing
are documentary claims, not independently authenticated. No IO or trading.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from atlasquant_fx_universe import OFFICIAL_PAIRS, split_pair
from atlasquant_trader_g8_event_relevance_lab import (
    EventSnapshot, inspect_g8_event_relevance_lab,
)

SCHEMA = "ATLASQUANT_TRADER_G8_SURPRISE_D1_W1_VETO_LAB_V1"
EXPECTED_ROUTE_STATE = "LAB_G8_EVENT_RELEVANCE_DOCUMENTARY_ONLY_NO_BIAS"
BLACKOUT_BEFORE = timedelta(minutes=30)
# Initial research windows, not tuned or validated against market outcomes.
ACTIVE_RELEASE_MAX_AGE = {"D1": timedelta(days=2), "W1": timedelta(days=8)}


def _utc(value: Any) -> datetime | None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        return None
    return value.astimezone(timezone.utc)


def _blocked(reason: str, *, asset: str | None = None) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_SURPRISE_REVIEW_ABSTAIN", "reason": reason,
        "asset": asset, "research_veto": True, "blockers": [reason],
        "W1_events": [], "D1_events": [], "W1_event_count": 0, "D1_event_count": 0,
        "W1_context_status": "UNASSESSED", "D1_context_status": "UNASSESSED",
        "event_calendar_coverage_independently_verified": False,
        "pre_event_consensus_independently_authenticated": False,
        "actual_first_release_independently_authenticated": False,
        "surprise_direction_to_currency_independently_validated": False,
        "economic_surprise_predictive_increment_validated": None,
        "calibrated_direction_probability": None, "research_direction_for_publication": None,
        "operational_bias": "AGUARDAR", "publishable": False,
        "live_alert_allowed": False, "trade_authorized": False,
        "worker_enabled": False, "scheduler_enabled": False,
        "http_requests": 0, "file_writes": 0, "new_cost_brl": 0,
        "research_only": True,
    }


def inspect_economic_surprise_veto_lab(
    *, candidate: Any, events_by_horizon: Any,
    decision_at_by_horizon: Any, macro_captured_at_by_horizon: Any,
    as_of_utc: Any,
) -> dict[str, Any]:
    """Assess event chronology at distinct W1/D1 cutoffs, only for one FX pair.

    A high-impact release without an independently interpreted, current
    surprise *vetoes* the documentary candidate. Agreement is not approval.
    The caller MUST supply historical event snapshots as they existed at each
    cutoff; this module cannot authenticate the original news calendar.
    """
    asset = getattr(candidate, "asset", None)
    if not isinstance(asset, str) or asset not in OFFICIAL_PAIRS:
        return _blocked("INVALID_OR_OUT_OF_SCOPE_FX_28_ASSET", asset=asset if isinstance(asset, str) else None)
    now, evaluated = _utc(as_of_utc), _utc(getattr(candidate, "evaluated_at", None))
    if now is None or evaluated is None or evaluated > now:
        return _blocked("INVALID_CANDIDATE_OR_ASOF_CLOCK", asset=asset)
    if getattr(candidate, "horizon", None) not in ("D1", "W1"):
        return _blocked("INVALID_CANDIDATE_HORIZON", asset=asset)
    if getattr(candidate, "daily", None) not in ("ALTA", "BAIXA") or getattr(candidate, "weekly", None) not in ("ALTA", "BAIXA"):
        return _blocked("MISSING_D1_OR_W1_CANDIDATE_DIRECTION", asset=asset)
    if candidate.daily != candidate.weekly:
        return _blocked("D1_W1_DIRECTION_CONFLICT", asset=asset)
    if events_by_horizon is None:
        return _blocked("ECONOMIC_EVENT_SNAPSHOTS_NOT_SUPPLIED", asset=asset)
    if macro_captured_at_by_horizon is None:
        return _blocked("ECONOMIC_MACRO_SNAPSHOT_CLOCKS_NOT_SUPPLIED", asset=asset)
    if any(not isinstance(value, dict) or set(value) != {"D1", "W1"} for value in (
        events_by_horizon, decision_at_by_horizon, macro_captured_at_by_horizon
    )):
        return _blocked("INVALID_D1_W1_EVENT_OR_TIME_MAP", asset=asset)
    cuts = {h: _utc(decision_at_by_horizon[h]) for h in ("W1", "D1")}
    macros = {h: _utc(macro_captured_at_by_horizon[h]) for h in ("W1", "D1")}
    if (any(cuts[h] is None or macros[h] is None or macros[h] > cuts[h] for h in ("W1", "D1"))
            or not cuts["W1"] <= cuts["D1"] <= evaluated):
        return _blocked("MACRO_CLOCK_AFTER_HORIZON_OR_INVALID_ORDER", asset=asset)

    base, quote = split_pair(asset)
    out = _blocked("ECONOMIC_EVENT_DOCUMENTARY_REVIEW_ONLY_NOT_AUTHENTICATED", asset=asset)
    all_blockers: list[str] = []
    seen_release_times: dict[tuple[str, str, str], datetime] = {}
    for horizon in ("W1", "D1"):
        events, cutoff, macro_at = events_by_horizon[horizon], cuts[horizon], macros[horizon]
        if not isinstance(events, (list, tuple)) or len(events) > 32 or any(
            not isinstance(v, EventSnapshot) for v in events
        ):
            return _blocked(horizon + "_INVALID_EVENT_SNAPSHOT_COLLECTION", asset=asset)
        # The event router validates units, source-claim timeline, event IDs,
        # missing actuals and surprise arithmetic. No post-cutoff values may pass.
        routed = inspect_g8_event_relevance_lab(events, as_of_utc=cutoff)
        if routed["state"] != EXPECTED_ROUTE_STATE or routed["pair_count"] != 28:
            return _blocked(horizon + "_EVENT_ROUTE_REJECTED_FUTURE_OR_INVALID", asset=asset)
        unique_identities = set()
        for event in events:
            identity = (event.currency, event.metric, event.target_period)
            schedule_time = _utc(event.scheduled_release_at)
            if identity in unique_identities:
                return _blocked(horizon + "_DUPLICATE_ECONOMIC_RELEASE", asset=asset)
            unique_identities.add(identity)
            # Event calendar revisions must never silently change identity
            # between weekly and daily cutoffs; they require manual review.
            if identity in seen_release_times and seen_release_times[identity] != schedule_time:
                return _blocked("EVENT_RELEASE_SCHEDULE_REVISED_NEEDS_REVIEW", asset=asset)
            seen_release_times[identity] = schedule_time
        relevant = [e for e in routed["events"] if e["currency"] in (base, quote)]
        if not events:
            all_blockers.append(horizon + "_CALENDAR_EMPTY_COVERAGE_NOT_PROVEN")
        observed = []
        for event in relevant:
            if event["importance"] != "HIGH":
                continue  # Medium/low metadata retained but not a high-impact veto
            scheduled = datetime.fromisoformat(event["scheduled_release_utc"])
            phase = event["phase"]
            reasons = []
            if scheduled <= cutoff and cutoff - scheduled > ACTIVE_RELEASE_MAX_AGE[horizon]:
                observed.append({
                    "event_id": event["event_id"], "currency": event["currency"],
                    "metric": event["metric"], "target_period": event["target_period"],
                    "phase": phase, "surprise_documentary": event["actual_minus_consensus_documentary"],
                    "review_reasons": [], "event_outside_research_relevance_window": True,
                    "directional_fx_impact": None, "is_first_print_authenticated": False,
                })
                continue
            if scheduled > cutoff:
                if scheduled - cutoff <= BLACKOUT_BEFORE:
                    reasons.append("HIGH_IMPACT_EVENT_IMMINENT")
            elif phase == "RELEASE_PASSED_ACTUAL_NOT_AVAILABLE":
                reasons.append("POST_RELEASE_ACTUAL_UNAVAILABLE")
            elif phase == "POST_RELEASE_ACTUAL_WITHOUT_CONSENSUS":
                reasons.append("PRE_RELEASE_CONSENSUS_MISSING")
            elif phase == "POST_RELEASE_DIFFERENCE_DOCUMENTARY_UNATTESTED":
                # Only documentary timestamps. New data must already have been
                # incorporated into the macro context at this horizon cutoff.
                actual_claimed = event["actual_claimed_captured_utc"]
                actual_at = datetime.fromisoformat(actual_claimed) if actual_claimed else None
                if actual_at is None or macro_at < actual_at:
                    reasons.append("MACRO_CONTEXT_PREDATES_ACTUAL_CAPTURE")
                try:
                    surprise = Decimal(event["actual_minus_consensus_documentary"])
                except (InvalidOperation, TypeError, ValueError):
                    return _blocked(horizon + "_SURPRISE_ARITHMETIC_MISSING", asset=asset)
                if not surprise.is_finite():
                    return _blocked(horizon + "_NONFINITE_SURPRISE", asset=asset)
                if surprise != 0:
                    reasons.append("SURPRISE_DIRECTION_NOT_INTERPRETED_OR_VALIDATED")
            else:
                return _blocked(horizon + "_UNEXPECTED_EVENT_PHASE", asset=asset)
            all_blockers.extend(horizon + "_" + x for x in reasons)
            observed.append({
                "event_id": event["event_id"], "currency": event["currency"],
                "metric": event["metric"], "target_period": event["target_period"],
                "phase": phase, "surprise_documentary": event["actual_minus_consensus_documentary"],
                "review_reasons": reasons, "event_outside_research_relevance_window": False,
                "directional_fx_impact": None,
                "is_first_print_authenticated": False,
            })
        out[horizon + "_events"] = observed
        out[horizon + "_event_count"] = len(observed)
        out[horizon + "_context_status"] = "DOCUMENTARY_NO_SOURCE_ATTESTATION"

    out.update({
        "state": ("LAB_SURPRISE_DOCUMENTARY_VETO" if all_blockers
                  else "LAB_SURPRISE_NO_DOCUMENTARY_VETO_NO_GO"),
        "reason": ("NEWS_UNVERIFIED_OR_CONTEXT_STALE" if all_blockers
                   else "NO_NEWS_CONFLICT_IS_NOT_PREDICTIVE_EVIDENCE"),
        "research_veto": bool(all_blockers), "blockers": list(dict.fromkeys(all_blockers)),
    })
    return out


__all__ = ["SCHEMA", "inspect_economic_surprise_veto_lab"]
