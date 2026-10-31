"""A339 pure synthetic authority-budget reference. NO PRODUCTIVE AUTHORITY.

This model is a deterministic arithmetic reference for *hypothetical* entries.
It has no SQLite, adapter, filesystem, network, producer, owner, signer or
record_confirmed dependency. Its booleans are budget projections, NEVER grants.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Sequence


SCHEMA = "A339_PURE_SYNTHETIC_BUDGET_REFERENCE_V1"
CAPABILITIES = ("LOW_RISK", "MEDIUM_RISK", "HIGH_RISK", "CRITICAL")


def _instant(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError("timezone-aware synthetic timestamp required")
    return value.astimezone(timezone.utc)


@dataclass(frozen=True)
class SimulatedLimits:
    window_seconds: int = 900
    max_window_effects: int = 8
    max_window_risk_points: int = 16
    max_window_distinct_capabilities: int = 4
    max_transaction_effects: int = 5
    max_transaction_risk_points: int = 10

    def __post_init__(self):
        for name, value in vars(self).items():
            if type(value) is not int or value < 1:
                raise ValueError("invalid synthetic limit: " + name)


@dataclass(frozen=True)
class SimulatedCandidate:
    scope: tuple[str, str, str]
    transaction_id: str
    capability_class: str = "LOW_RISK"
    risk_points: int = 1
    action: str = "hypothetical-action"

    def __post_init__(self):
        if (
            type(self.scope) is not tuple or len(self.scope) != 3
            or any(type(item) is not str or not item for item in self.scope)
            or type(self.transaction_id) is not str or not self.transaction_id
            or self.capability_class not in CAPABILITIES
            or type(self.risk_points) is not int or not 1 <= self.risk_points <= 100
            or type(self.action) is not str or not self.action
        ):
            raise ValueError("invalid synthetic candidate")


@dataclass(frozen=True)
class SimulatedEvent:
    idempotency_key: str
    candidate: SimulatedCandidate
    local_effect_label: str
    scenario_at: datetime

    def __post_init__(self):
        if type(self.idempotency_key) is not str or not self.idempotency_key:
            raise ValueError("invalid synthetic idempotency key")
        if not isinstance(self.candidate, SimulatedCandidate):
            raise ValueError("invalid synthetic candidate")
        if type(self.local_effect_label) is not str or not self.local_effect_label:
            raise ValueError("invalid synthetic local label")
        _instant(self.scenario_at)


def simulate_append(
    previous: Sequence[SimulatedEvent],
    event: SimulatedEvent,
) -> tuple[tuple[SimulatedEvent, ...], str]:
    """Return a fresh immutable scenario and a SYNTHETIC label, not a receipt."""
    if not isinstance(event, SimulatedEvent):
        raise TypeError("SimulatedEvent required")
    rows = tuple(previous)
    if any(not isinstance(row, SimulatedEvent) for row in rows):
        raise TypeError("only SimulatedEvent rows supported")
    matches = [row for row in rows if row.idempotency_key == event.idempotency_key]
    if matches:
        old = matches[0]
        if (
            old.candidate == event.candidate
            and old.local_effect_label == event.local_effect_label
        ):
            return rows, "SYNTHETIC_IDEMPOTENT_ONLY"
        raise ValueError("SYNTHETIC_IDEMPOTENCY_COLLISION")
    return rows + (event,), "SYNTHETIC_ADDED_ONLY"


def simulate_projection(
    previous: Sequence[SimulatedEvent],
    candidate: SimulatedCandidate,
    *,
    now: datetime,
    limits: SimulatedLimits = SimulatedLimits(),
) -> dict:
    """Project synthetic capacity. A 'within limits' result grants NOTHING."""
    if not isinstance(candidate, SimulatedCandidate):
        raise TypeError("SimulatedCandidate required")
    if not isinstance(limits, SimulatedLimits):
        raise TypeError("SimulatedLimits required")
    current = _instant(now)
    rows = tuple(previous)
    if any(not isinstance(row, SimulatedEvent) for row in rows):
        raise TypeError("only SimulatedEvent rows supported")
    scope_rows = [row for row in rows if row.candidate.scope == candidate.scope]
    cutoff = current - timedelta(seconds=limits.window_seconds)
    window = [row for row in scope_rows if _instant(row.scenario_at) >= cutoff]
    transaction = [
        row for row in scope_rows
        if row.candidate.transaction_id == candidate.transaction_id
    ]
    caps = {row.candidate.capability_class for row in window}
    before = {
        "window_effects": len(window),
        "window_risk_points": sum(row.candidate.risk_points for row in window),
        "window_distinct_capabilities": len(caps),
        "transaction_effects": len(transaction),
        "transaction_risk_points": sum(row.candidate.risk_points for row in transaction),
        "transaction_distinct_capabilities": len(
            {row.candidate.capability_class for row in transaction}
        ),
    }
    after = {
        "window_effects": before["window_effects"] + 1,
        "window_risk_points": before["window_risk_points"] + candidate.risk_points,
        "window_distinct_capabilities": len(caps | {candidate.capability_class}),
        "transaction_effects": before["transaction_effects"] + 1,
        "transaction_risk_points": before["transaction_risk_points"] + candidate.risk_points,
    }
    blockers = []
    if candidate.capability_class == "CRITICAL":
        blockers.append("CRITICAL_CAPABILITY_REQUIRES_SEPARATE_HUMAN_GATE")
    if after["window_effects"] > limits.max_window_effects:
        blockers.append("WINDOW_EFFECT_LIMIT")
    if after["window_risk_points"] > limits.max_window_risk_points:
        blockers.append("WINDOW_RISK_LIMIT")
    if after["window_distinct_capabilities"] > limits.max_window_distinct_capabilities:
        blockers.append("WINDOW_CAPABILITY_DIVERSITY_LIMIT")
    if after["transaction_effects"] > limits.max_transaction_effects:
        blockers.append("TRANSACTION_EFFECT_LIMIT")
    if after["transaction_risk_points"] > limits.max_transaction_risk_points:
        blockers.append("TRANSACTION_RISK_LIMIT")
    return {
        "schema": SCHEMA,
        "candidate_within_simulated_limits": not blockers,
        "before": before,
        "projected_after": after,
        "blockers": blockers,
        "proof_scope": "PURE_SYNTHETIC_MODEL_ONLY",
        "independent_producer_receipt_verified": False,
        "grants_authority": False,
        "authorizes_execution": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA", "SimulatedLimits", "SimulatedCandidate", "SimulatedEvent",
    "simulate_append", "simulate_projection",
]
