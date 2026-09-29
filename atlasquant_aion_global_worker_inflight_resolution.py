"""Explicit staging ceremony for safely resolved Global Worker inflight ticks.

This module only prepares an updated checkpoint in memory. It never writes the
runtime, changes the feature flag, runs/retries work, deploys, publishes, pays,
or trades. Persistence remains a separate conditional write using expected_sha.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from atlasquant_aion_core_intelligence.context import Domain
from atlasquant_aion_core_intelligence.evidence import digest, utc
from atlasquant_aion_core_runtime_bridge import authenticated_context
from atlasquant_aion_global_worker import (
    _delegated_access,
    _empty_lease,
    _mutated,
    attach_global_worker_state,
    load_global_worker_state,
)
from atlasquant_aion_global_worker_inflight_reconciliation import (
    assess_global_inflight_reconciliation,
)


SCHEMA = "ATLASQUANT_AION_GLOBAL_INFLIGHT_RESOLUTION_CEREMONY_V1"
CONFIRMATION_PHRASE = "CONFIRMAR LIMPEZA INFLIGHT RECONCILIADO"
CLEARABLE_STATUSES = frozenset({
    "EMPTY_BATCH_READY_FOR_HUMAN_CLEAR",
    "TERMINAL_EVIDENCE_READY_FOR_HUMAN_CLEAR",
})


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_iso(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            return None
        return utc(parsed)
    except Exception:
        return None


def stage_resolved_inflight_clear(
    access: Mapping[str, Any] | None,
    runtime_result: Mapping[str, Any] | None,
    *,
    confirmation: bool,
    confirmation_phrase: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Stage a clear only when recomputed evidence proves a clearable state."""
    current = utc(now or _now())
    runtime = dict(runtime_result or {})
    checkpoint = runtime.get("checkpoint")
    expected_sha = str(runtime.get("sha") or "").strip()

    if confirmation is not True:
        return {
            "schema": SCHEMA,
            "status": "BLOCKED",
            "reason": "EXPLICIT_ADMIN_CONFIRMATION_REQUIRED",
            "checkpoint": checkpoint if isinstance(checkpoint, Mapping) else {},
            "requires_checkpoint_save": False,
            "external_persisted": False,
            "executes_action": False,
        }
    if confirmation_phrase != CONFIRMATION_PHRASE:
        return {
            "schema": SCHEMA,
            "status": "BLOCKED",
            "reason": "EXACT_CONFIRMATION_PHRASE_REQUIRED",
            "checkpoint": checkpoint if isinstance(checkpoint, Mapping) else {},
            "requires_checkpoint_save": False,
            "external_persisted": False,
            "executes_action": False,
        }
    if (
        str(runtime.get("status") or "").upper() != "CONFIRMED"
        or not isinstance(checkpoint, Mapping)
        or not expected_sha
    ):
        return {
            "schema": SCHEMA,
            "status": "BLOCKED",
            "reason": "CONFIRMED_RUNTIME_WITH_SHA_REQUIRED",
            "checkpoint": checkpoint if isinstance(checkpoint, Mapping) else {},
            "requires_checkpoint_save": False,
            "external_persisted": False,
            "executes_action": False,
        }

    context = authenticated_context(access, Domain.ADMIN)
    if context.role != "ADMIN":
        raise ValueError("ADMIN_REQUIRED")

    assessment = assess_global_inflight_reconciliation(runtime, now=current)
    assessment_status = str(assessment.get("status") or "")
    if assessment_status not in CLEARABLE_STATUSES:
        return {
            "schema": SCHEMA,
            "status": "BLOCKED",
            "reason": "INFLIGHT_RECONCILIATION_NOT_CLEARABLE",
            "assessment_status": assessment_status,
            "assessment": assessment,
            "checkpoint": dict(checkpoint),
            "requires_checkpoint_save": False,
            "external_persisted": False,
            "automatic_retry_allowed": False,
            "executes_action": False,
        }

    state, state_status = load_global_worker_state(checkpoint)
    if state_status.get("state") != "CONNECTED":
        return {
            "schema": SCHEMA,
            "status": "BLOCKED",
            "reason": "GLOBAL_WORKER_STATE_NOT_CONNECTED",
            "checkpoint": dict(checkpoint),
            "requires_checkpoint_save": False,
            "external_persisted": False,
            "executes_action": False,
        }
    inflight = state.get("inflight_tick")
    if not isinstance(inflight, Mapping) or not inflight:
        return {
            "schema": SCHEMA,
            "status": "BLOCKED",
            "reason": "INFLIGHT_STATE_REQUIRED",
            "checkpoint": dict(checkpoint),
            "requires_checkpoint_save": False,
            "external_persisted": False,
            "executes_action": False,
        }

    delegated = _delegated_access(state.get("delegation") or {})
    delegated_context = authenticated_context(delegated, Domain.ADMIN)
    if delegated_context.key != context.key:
        return {
            "schema": SCHEMA,
            "status": "BLOCKED",
            "reason": "GLOBAL_WORKER_CONTEXT_MISMATCH",
            "checkpoint": dict(checkpoint),
            "requires_checkpoint_save": False,
            "external_persisted": False,
            "executes_action": False,
        }

    lease = state.get("lease") if isinstance(state.get("lease"), Mapping) else {}
    lease_owner = str(lease.get("owner") or "")
    lease_expires_at = _parse_iso(lease.get("expires_at"))
    if (
        not lease_owner
        or lease_expires_at is None
        or lease_expires_at > current
    ):
        return {
            "schema": SCHEMA,
            "status": "BLOCKED",
            "reason": "EXPIRED_OWNED_LEASE_REQUIRED",
            "checkpoint": dict(checkpoint),
            "requires_checkpoint_save": False,
            "external_persisted": False,
            "automatic_retry_allowed": False,
            "executes_action": False,
        }

    resolution_payload = {
        "runtime_sha": expected_sha,
        "assessment_digest": str(assessment.get("reconciliation_digest") or ""),
        "assessment_status": assessment_status,
        "inflight_intent_id": str(inflight.get("intent_id") or ""),
        "work_intent_digest": str(inflight.get("work_intent_digest") or ""),
        "resolved_at": current.isoformat(),
        "resolution": "CLEAR_RECONCILED_INFLIGHT",
        "actor_id": context.actor_id,
    }
    resolution_digest = digest(resolution_payload)

    next_state = _mutated(
        state,
        lease=_empty_lease(),
        inflight_tick={},
    )
    staged_checkpoint = attach_global_worker_state(
        checkpoint,
        next_state,
    )
    return {
        "schema": SCHEMA,
        "status": "STAGED_CLEAR_READY",
        "reason": "",
        "checkpoint": staged_checkpoint,
        "expected_sha": expected_sha,
        "assessment_status": assessment_status,
        "assessment_digest": str(assessment.get("reconciliation_digest") or ""),
        "resolution_digest": resolution_digest,
        "resolved_work_intent_digest": str(inflight.get("work_intent_digest") or ""),
        "resolved_work_intent_count": int(inflight.get("work_intent_count") or 0),
        "resolution": "CLEAR_RECONCILED_INFLIGHT",
        "requires_checkpoint_save": True,
        "conditional_write_required": True,
        "external_persisted": False,
        "automatic_retry_allowed": False,
        "automatic_clear_executed": False,
        "global_worker_tick_executed": False,
        "feature_flag_modified": False,
        "runtime_modified": False,
        "external_business_action_executed": False,
        "real_trading_enabled": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "CONFIRMATION_PHRASE",
    "CLEARABLE_STATUSES",
    "stage_resolved_inflight_clear",
]
