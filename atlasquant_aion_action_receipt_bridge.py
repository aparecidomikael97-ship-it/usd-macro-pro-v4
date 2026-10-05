"""Bridge existing executor/outbox receipts into AION Action Receipt envelopes.

The child execution record remains the source of truth. The Action Receipt is an
informational envelope that references a child id + canonical fingerprint. It
never grants permission, persists external state, or executes anything.

The ExecutionOutbox binding is intentionally stricter than the legacy generic
bridge: final receipts are emitted only from a real scoped outbox terminal
record. PENDING/CLAIMED/SENT/UNCERTAIN cannot be presented as completed work.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from atlasquant_aion_action_receipt import (
    canonical_fingerprint,
    seal_action_receipt,
)
from atlasquant_aion_execution_outbox import (
    SCHEMA as OUTBOX_SCHEMA,
    TERMINAL_STATES as OUTBOX_TERMINAL_STATES,
    ExecutionOutbox,
)


def _context_value(context: Any, name: str) -> str:
    return str(getattr(context, name, "") or "").strip()


def _issued_at(value: Any = None) -> str:
    if value is None:
        return datetime.now(timezone.utc).isoformat()
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise ValueError("timezone-aware issued_at required")
        return value.astimezone(timezone.utc).isoformat()
    text = str(value or "").strip()
    parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timezone-aware issued_at required")
    return parsed.astimezone(timezone.utc).isoformat()


def seal_executor_receipt_envelope(
    child_receipt: Mapping[str, Any],
    *,
    context: Any,
) -> dict[str, Any]:
    child = dict(child_receipt or {})
    receipt_id = str(child.get("receipt_id") or "").strip()
    if not receipt_id:
        raise ValueError("child receipt id required")
    child_fingerprint = canonical_fingerprint(child)
    authorization_digest = str(child.get("authorization_digest") or "").strip()
    result_digest = str(child.get("result_digest") or "").strip()
    guardian_allowed = child.get("guardian_allowed")
    guardian_state = "ALLOW" if guardian_allowed is True else "BLOCK"
    sealed = seal_action_receipt(
        {
            "task_id": str(getattr(context, "task_id", "") or child.get("schedule_id") or ""),
            "blast_radius": "LOW",
            "policy_ref": "guardian:" + str(child.get("guardian_action") or "unknown"),
            "guardian": {
                "state": guardian_state,
                "allowed": guardian_allowed if isinstance(guardian_allowed, bool) else None,
            },
            "evidence_refs": (
                ["result:" + result_digest] if result_digest else []
            ),
            "approval_refs": (
                ["authorization:" + authorization_digest] if authorization_digest else []
            ),
            "child_receipts": [{
                "receipt_id": receipt_id,
                "schema": str(child.get("schema") or ""),
                "fingerprint": child_fingerprint,
            }],
            "capability": str(child.get("capability") or ""),
            "tool_id": "",
            "state": str(child.get("state") or "UNKNOWN"),
            "result": str(child.get("reason") or ""),
            "issued_at": str(child.get("completed_at") or child.get("started_at") or ""),
            "rollback_ref": "",
            "correlation_id": str(child.get("occurrence_key") or receipt_id),
        },
        trusted_context={
            "requester_id": str(getattr(context, "actor_id", "") or ""),
            "tenant_id": str(getattr(context, "tenant_id", "") or ""),
            "workspace_id": str(getattr(context, "workspace_id", "") or ""),
        },
    )
    return {
        **sealed,
        "child_receipt_id": receipt_id,
        "child_fingerprint": child_fingerprint,
        "authorization": "NONE",
        "external_persisted": False,
    }


def seal_execution_outbox_receipt(
    outbox: ExecutionOutbox,
    idempotency_key: Any,
    *,
    context: Any,
    issued_at: Any = None,
) -> dict[str, Any]:
    """Seal a final informational receipt from a trusted scoped ExecutionOutbox.

    This function deliberately refuses non-terminal outbox states. In
    particular UNCERTAIN and SENT are not success and cannot produce a final
    action receipt. The child fingerprint excludes raw payload data and binds
    only execution metadata plus the already-computed payload digest.
    """
    if not isinstance(outbox, ExecutionOutbox):
        raise TypeError("ExecutionOutbox required")

    tenant = _context_value(context, "tenant_id")
    workspace = _context_value(context, "workspace_id")
    actor = _context_value(context, "actor_id")
    scope = outbox.scope
    if not tenant or tenant != scope.tenant_id:
        raise ValueError("outbox receipt tenant scope mismatch")
    if not workspace or workspace != scope.workspace_id:
        raise ValueError("outbox receipt workspace scope mismatch")
    if actor and actor != scope.owner_id:
        raise ValueError("outbox receipt owner scope mismatch")

    key = str(idempotency_key or "").strip()
    if not key:
        raise ValueError("outbox idempotency key required")
    item = outbox.get(key)
    state = str(item.get("state") or "").upper()
    if state not in OUTBOX_TERMINAL_STATES:
        raise ValueError("outbox action is not terminal; final receipt unavailable")

    decision = dict(item.get("decision") or {})
    if (
        decision.get("owner_id") != scope.owner_id
        or decision.get("tenant_id") != scope.tenant_id
        or decision.get("workspace_id") != scope.workspace_id
    ):
        raise ValueError("outbox decision scope mismatch")
    if decision.get("idempotency_key") != key:
        raise ValueError("outbox decision idempotency binding mismatch")

    effect_confirmed = state == "CONFIRMED"
    effect_ref = str(item.get("effect_ref") or "").strip()
    confirmed_at = str(item.get("confirmed_at") or "").strip()
    if effect_confirmed and (not effect_ref or not confirmed_at):
        raise ValueError("confirmed outbox effect binding incomplete")
    if not effect_confirmed and effect_ref:
        raise ValueError("unconfirmed terminal outbox record cannot carry effect_ref")

    child_snapshot = {
        "schema": OUTBOX_SCHEMA,
        "idempotency_key": key,
        "decision_id": str(item.get("decision_id") or ""),
        "state": state,
        "attempts": int(item.get("attempts") or 0),
        "effect_ref": effect_ref,
        "confirmed_at": confirmed_at,
        "aggregate_key": str(item.get("aggregate_key") or ""),
        "aggregate_seq": int(item.get("aggregate_seq") or 0),
        "payload_digest": str(decision.get("payload_digest") or ""),
        "policy_version": str(decision.get("policy_version") or ""),
        "authorization_ref": str(decision.get("authorization_ref") or ""),
        "transaction_id": str(decision.get("transaction_id") or ""),
        "authority_budget_ref": str(decision.get("authority_budget_ref") or ""),
        "risk_points": decision.get("risk_points"),
        "capability_class": str(decision.get("capability_class") or ""),
    }
    child_fingerprint = canonical_fingerprint(child_snapshot)
    child_receipt_id = "OUTBOX-" + key[:24].upper()

    evidence_refs = [
        "outbox:" + key,
        "decision:" + str(item.get("decision_id") or ""),
    ]
    if effect_confirmed:
        evidence_refs.append("effect:" + effect_ref)
    else:
        evidence_refs.append("terminal-state:" + state)

    approval_refs = []
    authorization_ref = str(decision.get("authorization_ref") or "").strip()
    if authorization_ref:
        approval_refs.append("authorization:" + authorization_ref)
    reauth_ref = str(decision.get("reauth_ref") or "").strip()
    if reauth_ref:
        approval_refs.append("reauth:" + reauth_ref)

    capability_class = str(decision.get("capability_class") or "").upper()
    blast_radius = capability_class if capability_class in {"LOW", "MEDIUM", "HIGH", "CRITICAL"} else "UNKNOWN"

    if state == "CONFIRMED":
        guardian = {"state": "OUTBOX_REVALIDATED", "allowed": True}
        result = "Execution outbox ledger confirms the external effect."
        truth_state = "CONFIRMED_EFFECT"
    elif state in {"REVOKED", "BLOCKED_REAPPROVAL"}:
        guardian = {"state": "OUTBOX_BLOCKED", "allowed": False}
        result = "Execution terminated without a confirmed external effect."
        truth_state = "NO_CONFIRMED_EFFECT"
    else:
        guardian = {"state": "UNKNOWN", "allowed": None}
        result = "Execution ended in a terminal failure without a confirmed external effect."
        truth_state = "NO_CONFIRMED_EFFECT"

    sealed = seal_action_receipt(
        {
            "task_id": str(decision.get("transaction_id") or item.get("decision_id") or ""),
            "blast_radius": blast_radius,
            "policy_ref": (
                "policy:" + str(decision.get("policy_version") or "")
                if decision.get("policy_version")
                else ""
            ),
            "guardian": guardian,
            "evidence_refs": evidence_refs,
            "approval_refs": approval_refs,
            "child_receipts": [{
                "receipt_id": child_receipt_id,
                "schema": OUTBOX_SCHEMA,
                "fingerprint": child_fingerprint,
            }],
            "capability": str(decision.get("capability_class") or decision.get("action") or ""),
            "tool_id": "execution_outbox",
            "state": state,
            "result": result,
            "issued_at": _issued_at(issued_at),
            "rollback_ref": "",
            "correlation_id": key,
        },
        trusted_context={
            "requester_id": scope.owner_id,
            "tenant_id": scope.tenant_id,
            "workspace_id": scope.workspace_id,
        },
    )
    return {
        **sealed,
        "source": "EXECUTION_OUTBOX",
        "source_schema": OUTBOX_SCHEMA,
        "source_state": state,
        "child_receipt_id": child_receipt_id,
        "child_fingerprint": child_fingerprint,
        "effect_confirmed": effect_confirmed,
        "effect_ref": effect_ref if effect_confirmed else "",
        "truth_state": truth_state,
        "authorization": "NONE",
        "external_persisted": False,
        "executes_action": False,
    }


__all__ = [
    "seal_executor_receipt_envelope",
    "seal_execution_outbox_receipt",
]
