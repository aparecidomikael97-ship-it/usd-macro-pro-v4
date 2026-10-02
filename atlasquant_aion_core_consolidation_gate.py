"""Read-only consolidation gate for Night Shift knowledge.

It ties runtime evidence, provenance, trust assessment and memory access policy
without persisting, promoting memory, authorizing execution, or saving a checkpoint.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping
import hashlib
import json

from aion_core.memory_architecture import create_record, read_allowed
from atlasquant_aion_core_nightshift_bridge import validate_runtime_rows

SCHEMA = "ATLASQUANT_AION_CORE_CONSOLIDATION_GATE_V1"

_RECOMMENDED_STATE = {
    "SUPPORTED": "VALIDATED",
    "WEAKLY_SUPPORTED": "CANDIDATE",
    "CONFLICTING": "CONFLICTING",
    "STALE_EVIDENCE": "STALE",
    "INSUFFICIENT_EVIDENCE": "QUARANTINED",
    "UNTRUSTED": "QUARANTINED",
}
_BLOCKING_TRUST = frozenset({
    "CONFLICTING",
    "STALE_EVIDENCE",
    "INSUFFICIENT_EVIDENCE",
    "UNTRUSTED",
})


def _stable_digest(value: Any) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _manifest_by_claim(rows: list[Mapping[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        claim_id = str(row.get("claim_id") or "").strip()
        if claim_id:
            grouped.setdefault(claim_id, []).append(dict(row))
    return grouped


def consolidate_runtime_knowledge(
    *,
    tenant_id: str,
    runtime_domain: Any,
    rows: list[Mapping[str, Any]],
    now: datetime | None = None,
) -> dict[str, Any]:
    """Build review candidates from runtime evidence without mutating any store."""
    validation = validate_runtime_rows(
        tenant_id=tenant_id,
        runtime_domain=runtime_domain,
        rows=rows,
        now=now,
    )
    domain_id = str(validation.get("domain_id") or "")
    manifests = _manifest_by_claim(validation.get("evidence_manifest") or [])
    candidates: list[dict[str, Any]] = []
    blockers: list[str] = []

    if validation.get("status") != "VALIDATED":
        blockers.append("NIGHTSHIFT_VALIDATION_BLOCKED")

    for assessment in validation.get("assessments") or []:
        claim_id = str(assessment.get("claim_id") or "").strip()
        trust_status = str(assessment.get("status") or "").strip().upper()
        recommended_state = _RECOMMENDED_STATE.get(
            trust_status,
            "QUARANTINED",
        )
        evidence_rows = manifests.get(claim_id, [])
        provenance_ids = sorted({
            str(item.get("provenance_id") or "")
            for item in evidence_rows
            if str(item.get("provenance_id") or "")
        })
        evidence_ids = sorted({
            str(item.get("evidence_id") or "")
            for item in evidence_rows
            if str(item.get("evidence_id") or "")
        })
        candidate = create_record(
            layer="DOMAIN",
            content=claim_id or "unidentified-claim",
            tenant_id=tenant_id,
            domain_id=domain_id,
            source_ref="trust:" + str(assessment.get("assessment_digest") or ""),
            confidence=assessment.get("confidence") or 0.0,
            created_at=(now.isoformat() if isinstance(now, datetime) and now.tzinfo else ""),
            state="CANDIDATE",
            metadata={
                "trust_status": trust_status,
                "recommended_state": recommended_state,
                "evidence_count": len(evidence_ids),
                "provenance_count": len(provenance_ids),
            },
        )

        access = read_allowed(
            candidate,
            requesting_tenant_id=tenant_id,
            requesting_domain_id=domain_id,
            is_admin=(domain_id == "ADMIN"),
        )
        if access.get("allowed") is not True:
            blockers.append(f"MEMORY_POLICY_BLOCKED:{claim_id}")
        if trust_status in _BLOCKING_TRUST:
            blockers.append(f"TRUST_{trust_status}:{claim_id}")
        candidates.append({
            "claim_id": claim_id,
            "trust_status": trust_status,
            "confidence": assessment.get("confidence"),
            "recommended_state": recommended_state,
            "memory_candidate": candidate.as_dict(),
            "memory_access": access,
            "evidence_ids": evidence_ids,
            "provenance_ids": provenance_ids,
            "promotion_requires_explicit_review": True,
            "memory_written": False,
        })

    stable_view = {
        "tenant_id": tenant_id,
        "domain_id": domain_id,
        "validation_status": validation.get("status"),
        "candidates": [
            {
                "claim_id": row["claim_id"],
                "trust_status": row["trust_status"],
                "confidence": row["confidence"],
                "recommended_state": row["recommended_state"],
                "evidence_ids": row["evidence_ids"],
                "provenance_ids": row["provenance_ids"],
            }
            for row in candidates
        ],
        "blockers": sorted(set(blockers)),
    }
    digest = _stable_digest(stable_view)
    return {
        "schema": SCHEMA,
        "status": "BLOCKED" if blockers else "CONSOLIDATED",
        "tenant_id": tenant_id,
        "domain_id": domain_id,
        "nightshift_validation": validation,
        "memory_candidates": candidates,
        "blockers": list(dict.fromkeys(blockers)),
        "consolidation_digest": digest,
        "checkpoint_review_ready": not blockers,
        "checkpoint_auto_stage": False,
        "memory_auto_write": False,
        "memory_auto_promotion": False,
        "external_persisted": False,
        "execution_authorized": False,
        "external_action_executed": False,
    }


def consolidation_policy() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "runtime_validation_required": True,
        "provenance_required": True,
        "trust_assessment_required": True,
        "memory_access_policy_required": True,
        "conflict_blocks_review_readiness": True,
        "stale_evidence_blocks_review_readiness": True,
        "unknown_or_insufficient_blocks_review_readiness": True,
        "automatic_memory_write": False,
        "automatic_memory_promotion": False,
        "automatic_checkpoint_stage": False,
        "execution_authority": False,
    }


__all__ = [
    "SCHEMA",
    "consolidate_runtime_knowledge",
    "consolidation_policy",
]
