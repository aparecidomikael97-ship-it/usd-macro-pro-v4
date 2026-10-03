"""Unified AION request -> Durable Tasks continuity bridge.

The bridge converts a completed unified preflight into durable state and later
prepares a recovery view. It records state only. Recovery restores cursor and
context, never performs the next step, bypasses approval, writes Checkpoint
Mestre, calls providers, or executes external actions.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from aion_chat.models import Scope
from atlasquant_aion_durable_tasks import (
    new_durable_task,
    normalize_durable_task,
    prepare_resume,
    update_step,
)
from atlasquant_aion_unified_journal import (
    append_request_event,
    verify_request_journal,
)
from atlasquant_aion_unified_runtime import AionRequest, AionResponse

SCHEMA = "ATLASQUANT_AION_UNIFIED_DURABLE_BRIDGE_V1"


def _block(reason: str, *, blockers: list[str] | None = None) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "status": "BLOCKED",
        "reason": reason,
        "blockers": list(blockers or [reason]),
        "restores_state_only": True,
        "automatic_resume_executes": False,
        "checkpoint_written": False,
        "external_action_executed": False,
    }


def prepare_durable_handoff(
    request: AionRequest,
    response: AionResponse,
    journal: Mapping[str, Any],
    *,
    checkpoint_digest: str = "",
) -> dict[str, Any]:
    if not isinstance(request, AionRequest) or not isinstance(response, AionResponse):
        raise TypeError("AionRequest and AionResponse required")
    if response.request_id != request.request_id or response.conversation_id != request.conversation_id:
        return _block("REQUEST_RESPONSE_MISMATCH")

    verified = verify_request_journal(journal, scope=request.scope, request_id=request.request_id)
    if verified["valid"] is not True:
        return _block("JOURNAL_INTEGRITY_MISMATCH", blockers=list(verified["reasons"]))

    needs_approval = bool(response.pending_approvals)
    task = new_durable_task(
        f"AION request {request.request_id}",
        objective=f"Retomar com segurança a solicitação {request.requested_action}.",
        domain=request.sector,
        mission_id=request.request_id,
        checkpoint_digest=checkpoint_digest,
        source="AION_UNIFIED_RUNTIME",
        steps=[
            {
                "step_id": "runtime-preflight",
                "title": "Preflight unificado registrado",
                "state": "PENDING",
                "guardian_action": "read",
                "requires_approval": False,
                "external_side_effects": False,
            },
            {
                "step_id": "guarded-continuation",
                "title": "Preparar continuação sob gates",
                "state": "PENDING",
                "guardian_action": "read",
                "requires_approval": needs_approval,
                "external_side_effects": False,
            },
        ],
    )
    task = update_step(
        task,
        "runtime-preflight",
        "RUNNING",
        result_note="Recording already completed unified preflight state only.",
        evidence_refs=[verified["head_digest"]],
        access={"role": "ADMIN"},
        approved=True,
    )
    task = update_step(
        task,
        "runtime-preflight",
        "DONE",
        result_note="Unified preflight already completed; state recorded only.",
        evidence_refs=[verified["head_digest"]],
        access={"role": "ADMIN"},
        approved=True,
    )

    if response.authorization_class == "BLOCKED":
        task = update_step(
            task,
            "guarded-continuation",
            "BLOCKED",
            blocker="Unified runtime classified the requested action as blocked.",
        )
    elif needs_approval:
        task = update_step(
            task,
            "guarded-continuation",
            "WAITING_APPROVAL",
            blocker="Explicit human approval remains pending.",
        )

    task["evidence_refs"] = list(dict.fromkeys([
        *list(task.get("evidence_refs") or []),
        verified["head_digest"],
    ]))
    task["artifacts"] = list(dict.fromkeys([
        *list(task.get("artifacts") or []),
        "aion-unified-journal:" + verified["head_digest"],
    ]))
    task = normalize_durable_task(task)

    updated_journal = append_request_event(
        journal,
        event_type="DURABLE_HANDOFF_PREPARED",
        selected_role=response.selected_role,
        authorization_class=response.authorization_class,
        truth_state=response.truth_state,
        state=task["state"],
        metadata={
            "durable_task_id": task["durable_task_id"],
            "task_revision": task["revision"],
            "approval_pending": needs_approval,
            "checkpoint_digest_present": bool(checkpoint_digest),
        },
    )
    return {
        "schema": SCHEMA,
        "status": "PREPARED",
        "durable_task": task,
        "journal": updated_journal,
        "journal_integrity": verify_request_journal(
            updated_journal, scope=request.scope, request_id=request.request_id
        ),
        "requires_explicit_approval": needs_approval,
        "restores_state_only": True,
        "automatic_resume_executes": False,
        "checkpoint_written": False,
        "external_action_executed": False,
    }


def prepare_durable_recovery(
    task: Mapping[str, Any],
    journal: Mapping[str, Any],
    *,
    scope: Scope,
    request_id: str,
    checkpoint_digest: str = "",
    expected_revision: Any = None,
) -> dict[str, Any]:
    if not isinstance(scope, Scope):
        raise TypeError("Scope required")
    verified = verify_request_journal(journal, scope=scope, request_id=request_id)
    if verified["valid"] is not True:
        return _block("JOURNAL_INTEGRITY_MISMATCH", blockers=list(verified["reasons"]))

    durable = normalize_durable_task(task)
    if durable.get("mission_id") != request_id:
        return _block("DURABLE_REQUEST_MISMATCH")

    view = prepare_resume(
        durable,
        expected_revision=expected_revision,
        checkpoint_digest=checkpoint_digest,
    )
    if view["state"] == "BLOCK":
        return _block("DURABLE_RECOVERY_BLOCKED", blockers=list(view["blockers"]))

    updated_journal = append_request_event(
        journal,
        event_type="RECOVERY_PREPARED",
        authorization_class="REQUIRES_APPROVAL" if view["approval_pending"] else "LOW_RISK",
        state=view["task_state"],
        metadata={
            "durable_task_id": view["durable_task_id"],
            "task_revision": view["revision"],
            "cursor": view["cursor"],
            "approval_pending": view["approval_pending"],
            "blockers": list(view["blockers"]),
        },
    )
    return {
        "schema": SCHEMA,
        "status": "RESUME_PREPARED",
        "resume": deepcopy(view),
        "journal": updated_journal,
        "journal_integrity": verify_request_journal(
            updated_journal, scope=scope, request_id=request_id
        ),
        "restores_state_only": True,
        "automatic_resume_executes": False,
        "checkpoint_written": False,
        "external_action_executed": False,
    }


__all__ = [
    "SCHEMA", "prepare_durable_handoff", "prepare_durable_recovery",
]
