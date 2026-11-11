"""Fail-closed LAB audit of selective FX/index opportunity denominators.

Seven FX pairs reacting to one CPI/PPI are seven *signal observations*, not
seven independent macro-event trials. An externally unwitnessed schedule and
caller-named event roots NEVER prove genuine forward testing or independence.
The illustrative Wilson bound below is NOT a calibrated market probability.
No account, price feed, HTTP, scheduler, alerts, orders or publication.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from math import sqrt
import re
from typing import Any

from atlasquant_fx_universe import OFFICIAL_PAIRS

SCHEMA = "ATLASQUANT_SELECTIVE_EVENT_ROOT_OOS_CENSUS_LAB_V1"
ASSETS = frozenset(OFFICIAL_PAIRS) | {
    "WIN", "WDO", "US500", "NAS100", "US30", "METAL:XAUUSD",
}
HORIZONS = frozenset({"D1", "W1"})
SIDES = frozenset({"ALTA", "BAIXA", "AGUARDAR"})
ID = re.compile(r"[A-Z0-9][A-Z0-9_:-]{3,79}\Z")
VERSION = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{1,63}\Z")
MAX_SLOTS = 10_000
MIN_CLAIMED_ROOTS = 100  # policy experiment, NOT scientifically sufficient by itself
RESEARCH_GOAL_LOWER = 0.80
LABEL = "CLOSED_BAR_DIRECTION_AFTER_PRECOMMITTED_DECISION"


@dataclass(frozen=True)
class FrozenOpportunityManifest:
    campaign_id: str
    rule_version: str
    frozen_at_utc: datetime
    expected_opportunity_ids: tuple[str, ...]


@dataclass(frozen=True)
class ObservedOpportunity:
    opportunity_id: str
    asset: str
    horizon: str
    event_root_id: str
    decided_at_utc: datetime
    issued_direction: str
    outcome_observed_at_utc: datetime | None
    correct_direction: bool | None
    outcome_label: str | None = None


def _utc(value: Any) -> datetime | None:
    if (not isinstance(value, datetime) or value.tzinfo is None
            or value.utcoffset() is None):
        return None
    return value.astimezone(timezone.utc)


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_EVENT_ROOT_OOS_ABSTAIN",
        "reason": reason,
        "expected_opportunities": 0, "accounted_opportunities": 0,
        "issued_count": 0, "abstained_count": 0,
        "issued_selection_rate_documentary": None,
        "claimed_event_root_count_all_opportunities": 0,
        "claimed_event_root_count_issued": 0,
        "signal_hit_rate_observed_unattested": None,
        "event_root_all_issued_correct_rate_unattested": None,
        "illustrative_event_root_wilson95_lower_if_iid": None,
        "event_root_hit_count_all_issued_correct": 0,
        "claimed_root_threshold_reached": False,
        "independent_event_trial_count_verified": None,
        "genuine_forward_precommitment_independently_attested": False,
        "individual_issued_decisions_first_seen_externally_attested": False,
        "original_market_data_vintage_independently_attested": False,
        "market_event_root_independence_verified": False,
        "selection_policy_unchanged_independently_attested": False,
        "execution_costs_and_net_profit_verified": False,
        "calibrated_direction_probability": None,
        "validated_accuracy": None,
        "operational_bias": "AGUARDAR", "live_alert_allowed": False,
        "publishable": False, "trade_authorized": False,
        "scheduler_enabled": False, "worker_enabled": False,
        "research_only": True, "http_requests": 0,
        "file_writes": 0, "new_cost_brl": 0,
    }


def _wilson_lower(success: int, count: int, z: float = 1.96) -> float:
    """Illustrative binomial lower bound ONLY IF trials were independent."""
    p = success / count
    denominator = 1 + z * z / count
    center = p + z * z / (2 * count)
    margin = z * sqrt(p * (1 - p) / count + z * z / (4 * count * count))
    return max(0.0, (center - margin) / denominator)


def audit_selective_event_roots_lab(
    *, frozen_manifest: Any, observations: Any, inspected_at_utc: Any,
) -> dict[str, Any]:
    """Reject missing opportunities before reporting any descriptive hit rate.

    One event root passes the *all-issued-correct* stress criterion only when
    EVERY issued prediction attached to that root was right. This strict
    event-level diagnostic is NOT a per-signal win rate or causal estimate.
    """
    now = _utc(inspected_at_utc)
    if (not isinstance(frozen_manifest, FrozenOpportunityManifest)
            or now is None or not isinstance(observations, (list, tuple))):
        return _blocked("INVALID_MANIFEST_OBSERVATIONS_OR_INSPECTION_CLOCK")
    plan = frozen_manifest
    frozen = _utc(plan.frozen_at_utc)
    expected = plan.expected_opportunity_ids
    if (not isinstance(plan.campaign_id, str) or ID.fullmatch(plan.campaign_id) is None
            or not isinstance(plan.rule_version, str)
            or VERSION.fullmatch(plan.rule_version) is None
            or frozen is None or frozen > now
            or not isinstance(expected, tuple)
            or not 1 <= len(expected) <= MAX_SLOTS
            or any(not isinstance(x, str) or ID.fullmatch(x) is None for x in expected)
            or len(set(expected)) != len(expected)):
        return _blocked("INVALID_OR_DUPLICATE_FROZEN_OPPORTUNITY_PLAN")
    if len(observations) != len(expected):
        return _blocked("MISSING_OR_EXTRA_PLANNED_OPPORTUNITIES")

    prior_decided: datetime | None = None
    event_roots: dict[str, list[bool]] = {}
    all_roots: set[str] = set()
    issued = won = 0
    for index, item in enumerate(observations):
        if not isinstance(item, ObservedOpportunity):
            return _blocked("INVALID_OPPORTUNITY_TYPE")
        decided = _utc(item.decided_at_utc)
        resolved = _utc(item.outcome_observed_at_utc)
        if (item.opportunity_id != expected[index]
                or not isinstance(item.asset, str) or item.asset not in ASSETS
                or not isinstance(item.horizon, str) or item.horizon not in HORIZONS
                or not isinstance(item.event_root_id, str)
                or ID.fullmatch(item.event_root_id) is None
                or not isinstance(item.issued_direction, str)
                or item.issued_direction not in SIDES
                or decided is None or not frozen < decided <= now
                or prior_decided is not None and decided < prior_decided):
            return _blocked("INVALID_OUT_OF_ORDER_OR_UNFROZEN_OPPORTUNITY")
        prior_decided = decided
        all_roots.add(item.event_root_id)
        if item.issued_direction == "AGUARDAR":
            if (item.correct_direction is not None
                    or item.outcome_observed_at_utc is not None
                    or item.outcome_label is not None):
                return _blocked("ABSTENTION_CANNOT_COUNT_AS_SCORED_SIGNAL")
            continue
        if (type(item.correct_direction) is not bool or resolved is None
                or not decided < resolved <= now or item.outcome_label != LABEL):
            return _blocked("ISSUED_SIGNAL_HAS_MISSING_FUTURE_OR_BAD_LABEL")
        issued += 1
        won += int(item.correct_direction)
        event_roots.setdefault(item.event_root_id, []).append(item.correct_direction)

    out = _blocked("NO_DIRECTIONAL_SIGNALS_OR_EVENT_ROOTS_TO_AUDIT")
    out.update({
        "expected_opportunities": len(expected),
        "accounted_opportunities": len(observations),
        "issued_count": issued, "abstained_count": len(expected) - issued,
        "issued_selection_rate_documentary": round(issued / len(expected), 6),
        "claimed_event_root_count_all_opportunities": len(all_roots),
        "claimed_event_root_count_issued": len(event_roots),
    })
    if not issued:
        return out

    root_hits = sum(all(outcomes) for outcomes in event_roots.values())
    root_count = len(event_roots)
    lower = _wilson_lower(root_hits, root_count)
    out.update({
        "signal_hit_rate_observed_unattested": round(won / issued, 6),
        "event_root_all_issued_correct_rate_unattested": round(root_hits / root_count, 6),
        "illustrative_event_root_wilson95_lower_if_iid": round(lower, 6),
        "event_root_hit_count_all_issued_correct": root_hits,
        "claimed_root_threshold_reached": root_count >= MIN_CLAIMED_ROOTS,
        "state": "LAB_EVENT_ROOT_DESCRIPTIVE_AUDIT_NO_GO",
        "reason": ("CLAIMED_ROOT_SAMPLE_TOO_SMALL_OR_BELOW_RESEARCH_GOAL"
                   if root_count < MIN_CLAIMED_ROOTS or lower < RESEARCH_GOAL_LOWER else
                   "ILLUSTRATIVE_ROOT_THRESHOLD_ONLY_INDEPENDENCE_UNVERIFIED"),
    })
    return out


__all__ = (
    "SCHEMA", "FrozenOpportunityManifest", "ObservedOpportunity",
    "audit_selective_event_roots_lab",
)
