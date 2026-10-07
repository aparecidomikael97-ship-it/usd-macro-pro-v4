"""AION Business Academy V1 educational mode contract.

Pure/offline. Defines lesson progression and preserves a hard boundary between
learning and live operations.
"""
from __future__ import annotations

from typing import Any

SCHEMA = "ATLASQUANT_AION_BUSINESS_ACADEMY_V1"
MODES = ("PROFESSOR", "GUIDED_PRACTICE", "OPERATOR")
LESSON_STATES = (
    "NOT_STARTED",
    "IN_PROGRESS",
    "PRACTICE_READY",
    "UNDERSTOOD",
    "REVIEW_RECOMMENDED",
)

LIVE_ACTIONS = frozenset({
    "OUTREACH_SEND",
    "CRM_WRITE",
    "SPEND_MONEY",
    "SIGN_CONTRACT",
    "CHANGE_PERMISSION",
    "PUBLISH",
    "LIVE_INTEGRATION",
    "TRADING_ACTION",
    "FINANCIAL_ACTION",
})


def _clean(value: Any, limit: int = 80) -> str:
    return " ".join(str(value or "").split())[:limit]


def academy_action_policy(*, mode: Any, action: Any) -> dict[str, Any]:
    normalized_mode = _clean(mode).upper()
    normalized_action = _clean(action).upper()
    blockers: list[str] = []

    if normalized_mode not in MODES:
        blockers.append("ACADEMY_MODE_INVALID")

    if normalized_mode in {"PROFESSOR", "GUIDED_PRACTICE"} and normalized_action in LIVE_ACTIONS:
        blockers.append("LIVE_ACTION_BLOCKED_IN_LEARNING_MODE")

    return {
        "schema": SCHEMA,
        "mode": normalized_mode,
        "action": normalized_action,
        "state": "BLOCKED" if blockers else "ALLOWED_BY_EDUCATIONAL_POLICY",
        "blockers": blockers,
        "executes_action": False,
        "grants_authority": False,
        "production_mutation": False,
    }


def lesson_progress(*, prior_state: Any, demonstrated_understanding: bool, practice_passed: bool) -> dict[str, Any]:
    state = _clean(prior_state).upper()
    if state not in LESSON_STATES:
        state = "NOT_STARTED"

    if demonstrated_understanding and practice_passed:
        next_state = "UNDERSTOOD"
    elif demonstrated_understanding:
        next_state = "PRACTICE_READY"
    elif state == "NOT_STARTED":
        next_state = "IN_PROGRESS"
    else:
        next_state = "REVIEW_RECOMMENDED"

    return {
        "schema": SCHEMA,
        "prior_state": state,
        "state": next_state,
        "demonstrated_understanding": bool(demonstrated_understanding),
        "practice_passed": bool(practice_passed),
        "clicks_only_do_not_complete": True,
    }


__all__ = [
    "SCHEMA",
    "MODES",
    "LESSON_STATES",
    "LIVE_ACTIONS",
    "academy_action_policy",
    "lesson_progress",
]
