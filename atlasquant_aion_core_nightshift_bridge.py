"""Read-only Nightshift V1 validator for the authenticated AION runtime.

This adapter may veto untrusted runtime evidence. It never grants execution,
persists memory, calls providers, performs I/O, or changes production state.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from aion_core.domain_registry import require_domain
from aion_core.memory_architecture import create_record, read_allowed
from aion_core.provenance import create_provenance, validate_provenance
from aion_core.trust_engine import create_evidence_item, assess_claim

SCHEMA = "ATLASQUANT_AION_NIGHTSHIFT_RUNTIME_VALIDATOR_V1"

_DOMAIN_MAP = {
    "ADMIN": "ADMIN",
    "DEVELOPER": "ORQUESTRACAO",
    "CONTENT": "BIBLIOTECA",
    "RESEARCH": "BIBLIOTECA",
    "BUSINESS": "NEGOCIOS",
    "TRADER": "TRADER",
    "INVESTMENTS": "INVESTIMENTOS",
}

def _clean(value: Any, limit: int = 500) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]
def _domain_id(runtime_domain: Any) -> str:
    key = _clean(getattr(runtime_domain, "value", runtime_domain), 40).upper()
    mapped = _DOMAIN_MAP.get(key, "")
    if not mapped:
        raise ValueError("NIGHTSHIFT_DOMAIN_UNMAPPED")
    require_domain(mapped)
    return mapped

def _now_iso(now: datetime | None) -> str:
    current = now if isinstance(now, datetime) and now.tzinfo else datetime.now(timezone.utc)
    return current.astimezone(timezone.utc).isoformat()

def validate_runtime_rows(
    *,
    tenant_id: str,
    runtime_domain: Any,
    rows: list[Mapping[str, Any]],
    now: datetime | None = None,
) -> dict[str, Any]:
    """Validate runtime observations without creating durable state."""
    domain_id = _domain_id(runtime_domain)
    current = _now_iso(now)
    evidence = []
    provenance_failures = 0
    rejected_rows = 0

    for row in rows:
        claim = _clean(row.get("claim") or row.get("id"), 400)
        source = _clean(row.get("source"), 240)
        source_ref = _clean(row.get("source_ref") or row.get("reference") or row.get("url"), 500)
        if not claim or not source or not source_ref:
            rejected_rows += 1
            continue
        prov = create_provenance(
            source_type="INTERNAL_DOCUMENT",
            source_reference=source_ref,
            source_title=source,
            retrieved_at=current,
            tenant_id=tenant_id,
            domain_id=domain_id,
            confidence=1.0 if str(row.get("truth_state") or "").upper() == "CONFIRMED" else 0.5,
        )
        checked = validate_provenance(prov)
        if checked.get("validatable") is not True:
            provenance_failures += 1
            continue
        validated = checked["record"]
        truth = str(row.get("truth_state") or "").upper()
        evidence.append(create_evidence_item(
            claim_id=claim,
            claim=claim,
            source_fingerprint=source_ref,
            source_type="INTERNAL_DOCUMENT",
            authority=1.0 if truth == "CONFIRMED" else 0.5,
            primary_source=False,
            independence_group=source_ref,
            freshness_class="STATIC" if row.get("time_sensitive") is False else "REALTIME",
            published_at=_clean(row.get("observed_at") or row.get("timestamp") or current, 80),
            confidence=1.0 if truth == "CONFIRMED" else 0.5,
            supports_claim=row.get("supports_claim") is not False,
            contradicts_claim=row.get("contradicts_claim") is True,
            human_validated=row.get("human_validated") is True,
            provenance_id=validated.provenance_id,
            tenant_id=tenant_id,
            domain_id=domain_id,
        ))
    grouped: dict[str, list[Any]] = {}
    for item in evidence:
        grouped.setdefault(item.claim_id, []).append(item)
    assessments = [assess_claim(items, claim_id=claim, now=now) for claim, items in grouped.items()]

    # Exercise Nightshift memory access policy only on an ephemeral candidate.
    # Nothing is inserted into a store or persisted.
    probe = create_record(
        layer="WORKING",
        content="runtime-validation-probe",
        tenant_id=tenant_id,
        domain_id=domain_id,
        source_ref="runtime-validator",
        confidence=1.0,
    )
    memory_access = read_allowed(
        probe,
        requesting_tenant_id=tenant_id,
        requesting_domain_id=domain_id,
        is_admin=(domain_id == "ADMIN"),
    )

    blocked = bool(rejected_rows or provenance_failures)
    return {
        "schema": SCHEMA,
        "status": "BLOCKED" if blocked else "VALIDATED",
        "domain_id": domain_id,
        "accepted_evidence": len(evidence),
        "rejected_rows": rejected_rows,
        "provenance_failures": provenance_failures,
        "assessments": [a.as_dict() for a in assessments],
        "evidence_manifest": [
            {
                "evidence_id": item.evidence_id,
                "claim_id": item.claim_id,
                "provenance_id": item.provenance_id,
                "source_fingerprint": item.source_fingerprint,
                "supports_claim": item.supports_claim,
                "contradicts_claim": item.contradicts_claim,
                "tenant_id": item.tenant_id,
                "domain_id": item.domain_id,
            }
            for item in evidence
        ],
        "memory_policy_probe": memory_access,
        "memory_auto_write": False,
        "external_persisted": False,
        "execution_authorized": False,
        "external_action_executed": False,
    }

__all__ = ["SCHEMA", "validate_runtime_rows"]
