"""AION A.41: deterministic Saga sequence selection, with NO effect authority.

This module accepts only *already projected* step states and chooses a candidate.
It does NOT authenticate a producer, validate a receipt, authorize an action,
approve compensation, record an effect, or turn a simulated outcome into proof.
The productive coordinator must apply its independent trust gates before enqueue.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence


def select_forward_step(saga_state: str, steps: Sequence[Mapping[str, Any]]) -> int:
    """Return zero-based forward candidate, or fail without side effects."""
    if saga_state not in {"PLANNED", "RUNNING"}:
        raise ValueError("saga state does not allow forward enqueue")
    if any(s["state"] in {"ENQUEUED", "RETRY", "UNCERTAIN"} for s in steps):
        raise ValueError("previous saga step is not settled")
    if any(s["state"] in {"FAILED", "REVOKED", "BLOCKED_REAPPROVAL"} for s in steps):
        raise ValueError("failed saga cannot enqueue forward work")
    pending = next((i for i, s in enumerate(steps) if s["state"] == "PENDING"), None)
    if pending is None:
        raise ValueError("no pending saga step")
    earlier = [s for s in steps if s["ordinal"] < steps[pending]["ordinal"]]
    if any(s["state"] != "CONFIRMED" for s in earlier):
        raise ValueError("saga order requires earlier confirmation")
    return pending


def select_compensation_step(saga_state: str, steps: Sequence[Mapping[str, Any]]) -> int:
    """Return highest-ordinal pending compensation; never approve its effect."""
    if saga_state != "COMPENSATING":
        raise ValueError("saga is not in compensation mode")
    if any(s["state"] in {"COMPENSATION_ENQUEUED", "UNCERTAIN", "COMPENSATION_FAILED"}
           for s in steps):
        raise ValueError("previous compensation is not settled")
    pending = [i for i, s in enumerate(steps) if s["state"] == "COMPENSATION_PENDING"]
    if not pending:
        raise ValueError("no pending compensation")
    return max(pending, key=lambda i: steps[i]["ordinal"])


__all__ = ["select_forward_step", "select_compensation_step"]
