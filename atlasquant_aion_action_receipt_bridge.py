"""Bridge existing executor receipts into AION Action Receipt envelopes.

The child receipt remains the execution record. The Action Receipt is an
informational envelope that references the child id + canonical fingerprint.
It grants no permission and does not persist or execute anything.
"""
from __future__ import annotations

from typing import Any, Mapping

from atlasquant_aion_action_receipt import (
    canonical_fingerprint,
    seal_action_receipt,
)


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


__all__ = ["seal_executor_receipt_envelope"]
