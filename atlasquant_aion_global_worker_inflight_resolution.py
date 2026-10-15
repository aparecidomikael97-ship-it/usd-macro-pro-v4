"""Explicit staging ceremony for safely resolved Global Worker inflight ticks.

This module only prepares an updated checkpoint in memory. It never writes the
runtime, changes the feature flag, runs/retries work, deploys, publishes, pays,
or trades. Persistence remains a separate conditional write using expected_sha.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from atlasquant_aion_core_intelligence.context import Domain
from atlasquant_aion_core_intelligence.evidence import utc
from atlasquant_aion_core_runtime_bridge import authenticated_context
from atlasquant_aion_global_worker import (
    _delegated_access,
    load_global_worker_state,
)
from atlasquant_aion_global_worker_inflight_reconciliation import (
    assess_global_inflight_reconciliation,
)


SCHEMA = "ATLASQUANT_AION_GLOBAL_INFLIGHT_RESOLUTION_CEREMONY_V1"
CONFIRMATION_PHRASE = "CONFIRMAR LIMPEZA INFLIGHT RECONCILIADO"
# A66: a local EMPTY_BATCH is never proof of no effect, even when the
# checkpoint's self-contained checksums are internally consistent. Do not
# stage a conditional clear while independent F1/T1 custody is unenrolled.
# Historical terminal label remains a recognized diagnosis, not an
# authorization to clear. No independently enrolled proof can presently
# certify terminal no-effect for a Global Worker inflight occurrence.
CLEARABLE_STATUSES = frozenset({
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
    """Deny unsafe clear staging until external producer/source custody exists."""
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
    # A66: keep the current "empty work" diagnosis non-clearable, but
    # continue evaluating caller scope and active lease first. This preserves
    # the more precise security denial for wrong-context or live-lease calls.
    # No branch here authorizes an unproven empty batch for staging.
    if (assessment_status not in CLEARABLE_STATUSES
            and assessment_status != "UNVERIFIED_EMPTY_BATCH_REVIEW_REQUIRED"):
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

    # A84: no trusted producer terminal fence or F1/T1 external source
    # witness is enrolled. A locally recomputed terminal-ready label can
    # never authorize erasing in-flight state, even after human confirmation,
    # expiry and matching delegation. These checks are necessary, not a
    # substitute for independently authenticated causal absence evidence.
    #
    # In particular do NOT preserve a dormant positive checkpoint builder
    # that could be revived by a future assessor-refactor or forged return.
    return {
        "schema": SCHEMA,
        "status": "BLOCKED",
        "reason": (
            "INDEPENDENT_INFLIGHT_CLEAR_PROOF_NOT_ENROLLED"
            if assessment_status in CLEARABLE_STATUSES
            else "INFLIGHT_RECONCILIATION_NOT_CLEARABLE"
        ),
        "assessment_status": assessment_status,
        "assessment": assessment,
        "checkpoint": dict(checkpoint),
        "requires_checkpoint_save": False,
        "external_persisted": False,
        "runtime_modified": False,
        "feature_flag_modified": False,
        "automatic_retry_allowed": False,
        "executes_action": False,
    }

__all__ = [
    "SCHEMA",
    "CONFIRMATION_PHRASE",
    "CLEARABLE_STATUSES",
    "stage_resolved_inflight_clear",
]
