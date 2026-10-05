"""Bridge independent verification and governance state into the unified journal.

The existing unified journal remains the one tamper-evident request lifecycle
journal. This bridge adds governance audit events without creating a second
journal or authority system.
"""
from __future__ import annotations

from typing import Any, Mapping

from aion_chat.models import Scope
from atlasquant_aion_independent_verifier import (
    validate_verification_receipt,
)
from atlasquant_aion_unified_journal import append_request_event


SCHEMA = "ATLASQUANT_AION_GOVERNANCE_AUDIT_BRIDGE_V1"


def _clean(value: Any, limit: int = 240) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def append_verification_audit(
    journal: Mapping[str, Any],
    *,
    receipt: Mapping[str, Any],
    request: Mapping[str, Any],
    scope: Scope,
    observed_at: str,
) -> dict[str, Any]:
    checked = validate_verification_receipt(
        receipt,
        request=request,
        scope=scope,
        now=observed_at,
    )
    if checked["valid"] is not True:
        raise ValueError("verification receipt invalid for audit")
    return append_request_event(
        journal,
        event_type="VERIFICATION_RECORDED",
        truth_state="CONFIRMED",
        state="VERIFIED",
        metadata={
            "verification_schema": receipt.get("schema"),
            "verification_kind": receipt.get("verification_kind"),
            "verifier_id": receipt.get("verifier_id"),
            "claim_ref": receipt.get("claim_ref"),
            "request_digest": receipt.get("request_digest"),
            "receipt_digest": receipt.get("receipt_digest"),
            "content_digest": receipt.get("content_digest"),
            "bound_refs": list(receipt.get("bound_refs") or []),
            "independent": True,
            "authorization": "NONE",
        },
        observed_at=observed_at,
    )


def append_memory_promotion_audit(
    journal: Mapping[str, Any],
    *,
    promotion: Mapping[str, Any],
    observed_at: str,
) -> dict[str, Any]:
    if promotion.get("state") != "PROMOTED":
        raise ValueError("PROMOTED memory result required")
    proposal = (
        dict(promotion.get("proposal"))
        if isinstance(promotion.get("proposal"), Mapping)
        else {}
    )
    row = (
        dict(promotion.get("promoted_memory"))
        if isinstance(promotion.get("promoted_memory"), Mapping)
        else {}
    )
    if (
        row.get("promotion_state") != "PROMOTED"
        or not row.get("promotion_proof_digest")
        or proposal.get("verification_receipt_validated") is not True
        or not proposal.get("verification_receipt_digest")
    ):
        raise ValueError("governed promotion proof required")
    return append_request_event(
        journal,
        event_type="MEMORY_PROMOTION_RECORDED",
        truth_state="CONFIRMED",
        state="PROMOTED",
        metadata={
            "proposal_id": proposal.get("proposal_id"),
            "memory_id": row.get("memory_id"),
            "promotion_proof_digest": row.get("promotion_proof_digest"),
            "verification_receipt_digest": proposal.get("verification_receipt_digest"),
            "content_digest": proposal.get("content_digest"),
            "authority": "NONE",
        },
        observed_at=observed_at,
    )


def append_authority_revalidation_audit(
    journal: Mapping[str, Any],
    *,
    outbox_result: Mapping[str, Any],
    observed_at: str,
) -> dict[str, Any]:
    state = _clean(outbox_result.get("state"), 40).upper()
    if state not in {"REVOKED", "BLOCKED_REAPPROVAL", "CLAIMED", "SENT", "CONFIRMED"}:
        raise ValueError("unsupported authority revalidation state")
    return append_request_event(
        journal,
        event_type="AUTHORITY_REVALIDATED",
        state=state,
        metadata={
            "idempotency_key": outbox_result.get("idempotency_key"),
            "decision_id": outbox_result.get("decision_id"),
            "last_error": outbox_result.get("last_error"),
            "authorization_revalidated": True,
            "external_action_executed": False,
        },
        observed_at=observed_at,
    )


def append_outbox_reconciliation_audit(
    journal: Mapping[str, Any],
    *,
    outbox_result: Mapping[str, Any],
    observed_at: str,
) -> dict[str, Any]:
    reconciliation = _clean(outbox_result.get("reconcile_state"), 60).upper()
    if reconciliation not in {
        "CONFIRMED",
        "RETRY",
        "REVOKED",
        "BLOCKED_REAPPROVAL",
        "STILL_UNCERTAIN",
    }:
        raise ValueError("reconcile_state required")
    return append_request_event(
        journal,
        event_type="OUTBOX_RECONCILED",
        state=reconciliation,
        metadata={
            "idempotency_key": outbox_result.get("idempotency_key"),
            "decision_id": outbox_result.get("decision_id"),
            "effect_ref": outbox_result.get("effect_ref"),
            "reconcile_state": reconciliation,
            "blind_resend": False,
        },
        observed_at=observed_at,
    )


__all__ = [
    "SCHEMA",
    "append_verification_audit",
    "append_memory_promotion_audit",
    "append_authority_revalidation_audit",
    "append_outbox_reconciliation_audit",
]
