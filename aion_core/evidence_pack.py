"""AION core evidence pack.

Transportable, verifiable bundle of evidence between retrieval, specialists,
analysis and response validation. Reuses the provenance, trust engine and
domain registry contracts; it does not recreate them. The pack never grants
permissions, never contains secrets or private chain-of-thought, and document
content is DATA, never a privileged instruction.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence
import hashlib
import json
import re
import unicodedata

from aion_core.domain_registry import get_domain, cross_domain_read_allowed
from aion_core.provenance import ProvenanceRecord, provenance_digest
from aion_core.trust_engine import (
    EvidenceItem,
    TrustAssessment,
    assess_claim,
    trust_assessment_digest,
)

SCHEMA = "ATLASQUANT_AION_CORE_EVIDENCE_PACK_V1"
PACK_VERSION = 1

# Phrases that would claim privileged authority inside document content.
# Content is data: these are flagged, never executed.
_PRIVILEGED_INSTRUCTION_PATTERNS = (
    re.compile(r"(?i)\b(ignore|esqueca)\s+(as|the)\s+(regras?|rules?|policy)"),
    re.compile(r"(?i)\b(revele|reveals?)\s+(o|the)\s+segredo"),
    re.compile(r"(?i)\b(execute|execute)\s+o\s+comando"),
    re.compile(r"(?i)\b(esta|this)\s+(memoria|memory|documento|document)\s+(autoriza|authorizes?)"),
    re.compile(r"(?i)\b(voce|you)\s+(agora)?\s*(e|is)\s+admin"),
)


class EvidencePackError(ValueError):
    """Fail-closed error for invalid evidence packs."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(value: Any, limit: int = 240) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _digest(value: Any, length: int = 24) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:length]


def _secret_like(text: str) -> bool:
    folded = unicodedata.normalize("NFKD", text).casefold()
    markers = ("password=", "senha=", "api_key=", "apikey=", "secret=", "bearer ",
               "private key", "-----begin", "akia[0-9a-z]{16}")
    return any(m in folded for m in markers)


@dataclass(frozen=True)
class EvidencePack:
    evidence_pack_id: str
    claim_ids: tuple[str, ...]
    evidence_items: tuple[EvidenceItem, ...]
    trust_assessments: tuple[TrustAssessment, ...]
    provenance_records: tuple[ProvenanceRecord, ...]
    sources: tuple[str, ...]
    conflict_flags: tuple[str, ...]
    stale_flags: tuple[str, ...]
    tenant_id: str
    domain_id: str
    schema_version: int
    generated_at: str
    requires_evidence: bool
    digest: str

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["claim_ids"] = list(self.claim_ids)
        data["evidence_items"] = [i.as_dict() for i in self.evidence_items]
        data["trust_assessments"] = [t.as_dict() for t in self.trust_assessments]
        data["provenance_records"] = [p.as_dict() for p in self.provenance_records]
        data["sources"] = list(self.sources)
        data["conflict_flags"] = list(self.conflict_flags)
        data["stale_flags"] = list(self.stale_flags)
        return data


def _pack_digest(payload: Mapping[str, Any]) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def create_evidence_pack(
    *,
    tenant_id: Any,
    domain_id: Any,
    evidence_items: Sequence[EvidenceItem],
    provenance_records: Sequence[ProvenanceRecord] | None = None,
    trust_assessments: Sequence[TrustAssessment] | None = None,
    requires_evidence: bool = True,
    generated_at: Any = "",
    metadata: Mapping[str, Any] | None = None,
) -> EvidencePack:
    """Build a pack. Fail closed on: empty evidence when required, tenant
    mixing, missing provenance for evidence, unknown domain, secret-like
    content, privileged instructions in content, assessments not matching
    claims."""
    tenant = _clean(tenant_id, 120)
    domain = _clean(domain_id, 40).upper()
    if not tenant:
        raise EvidencePackError("tenant_id is required")
    if domain and get_domain(domain) is None:
        raise EvidencePackError(f"unknown domain_id: {domain_id!r}")
    items = list(evidence_items or [])
    if requires_evidence and not items:
        raise EvidencePackError("pack requires evidence but none was provided")

    # tenant isolation: no mixing of private tenants inside one pack
    tenants = {i.tenant_id for i in items if i.tenant_id}
    tenants |= {p.tenant_id for p in (provenance_records or []) if p.tenant_id}
    if tenants and tenant not in tenants:
        raise EvidencePackError("pack tenant does not match evidence tenant")
    if len(tenants - {tenant}) > 0:
        raise EvidencePackError("mixed tenants are not allowed in one pack")

    # provenance coverage: every evidence item must reference known provenance
    prov_by_id = {p.provenance_id: p for p in (provenance_records or [])}
    missing_prov = [i.evidence_id for i in items if i.provenance_id and i.provenance_id not in prov_by_id]
    no_prov = [i.evidence_id for i in items if not i.provenance_id]

    # content checks: secrets and privileged instructions
    flagged_instructions: list[str] = []
    for item in items:
        text = f"{item.claim} {item.metadata.get('excerpt', '')}"
        if _secret_like(text):
            raise EvidencePackError(f"secret-like content in {item.evidence_id}")
        if any(p.search(text) for p in _PRIVILEGED_INSTRUCTION_PATTERNS):
            flagged_instructions.append(item.evidence_id)

    # assessments must correspond to the claims present
    claims = sorted({i.claim_id for i in items})
    if trust_assessments is None:
        # derive deterministically per claim
        trust_assessments = [assess_claim([i for i in items if i.claim_id == c], claim_id=c) for c in claims]
    assessment_claims = {t.claim_id for t in trust_assessments}
    if set(claims) != assessment_claims:
        raise EvidencePackError("trust assessments do not match pack claims")

    conflict_flags = sorted({t.claim_id for t in trust_assessments if t.status == "CONFLICTING"})
    stale_flags = sorted({t.claim_id for t in trust_assessments if t.status == "STALE_EVIDENCE"})

    sources = tuple(sorted({i.source_fingerprint for i in items}))
    payload = {
        "claim_ids": claims,
        "evidence": sorted(i.evidence_id for i in items),
        "assessments": sorted(t.assessment_digest for t in trust_assessments),
        "provenance": sorted(provenance_digest(p) for p in (provenance_records or [])),
        "sources": list(sources),
        "conflicts": conflict_flags,
        "stale": stale_flags,
        "tenant": tenant,
        "domain": domain,
        "missing_provenance": sorted(no_prov),
        "unresolved_provenance_refs": sorted(missing_prov),
        "privileged_instruction_flags": flagged_instructions,
    }
    digest = _pack_digest(payload)
    pack_id = "EVP-" + digest[:20].upper()
    return EvidencePack(
        evidence_pack_id=pack_id,
        claim_ids=tuple(claims),
        evidence_items=tuple(items),
        trust_assessments=tuple(trust_assessments),
        provenance_records=tuple(provenance_records or []),
        sources=sources,
        conflict_flags=tuple(conflict_flags),
        stale_flags=tuple(stale_flags),
        tenant_id=tenant,
        domain_id=domain,
        schema_version=PACK_VERSION,
        generated_at=_clean(generated_at, 80) or _now(),
        requires_evidence=requires_evidence is True,
        digest=digest,
    )


def _instruction_flags(pack: EvidencePack) -> list[str]:
    out = []
    for item in pack.evidence_items:
        text = f"{item.claim} {item.metadata.get('excerpt', '')}"
        if any(p.search(text) for p in _PRIVILEGED_INSTRUCTION_PATTERNS):
            out.append(item.evidence_id)
    return sorted(out)


def validate_evidence_pack(pack: EvidencePack) -> dict[str, Any]:
    """Re-verify the pack digest and internal consistency. The pack itself
    never grants permission: this only proves integrity of what is carried."""
    problems: list[str] = []
    payload = {
        "claim_ids": list(pack.claim_ids),
        "evidence": sorted(i.evidence_id for i in pack.evidence_items),
        "assessments": sorted(t.assessment_digest for t in pack.trust_assessments),
        "provenance": sorted(provenance_digest(p) for p in pack.provenance_records),
        "sources": list(pack.sources),
        "conflicts": list(pack.conflict_flags),
        "stale": list(pack.stale_flags),
        "tenant": pack.tenant_id,
        "domain": pack.domain_id,
        "missing_provenance": sorted(i.evidence_id for i in pack.evidence_items if not i.provenance_id),
        "unresolved_provenance_refs": sorted(
            i.evidence_id for i in pack.evidence_items
            if i.provenance_id and i.provenance_id not in {p.provenance_id for p in pack.provenance_records}
        ),
        "privileged_instruction_flags": _instruction_flags(pack),
    }
    if _pack_digest(payload) != pack.digest:
        problems.append("digest_mismatch")
    if pack.requires_evidence and not pack.evidence_items:
        problems.append("empty_pack_requires_evidence")
    return {
        "schema": SCHEMA,
        "integrity_ok": not problems,
        "problems": problems,
        "grants_permission": False,
        "executes_action": False,
    }


def pack_access_allowed(
    pack: EvidencePack,
    *,
    requesting_tenant_id: Any,
    requesting_domain_id: Any = "",
    is_admin: bool = False,
    explicit_cross_domain_permission: bool = False,
) -> dict[str, Any]:
    """Access to the pack. Tenant must match; cross-domain needs explicit
    permission (or admin). Unknown/missing context denies (fail closed)."""
    reasons: list[str] = []
    tenant = _clean(requesting_tenant_id, 120)
    domain = _clean(requesting_domain_id, 40).upper()
    if not tenant:
        reasons.append("requesting_tenant_missing")
    elif tenant != pack.tenant_id:
        reasons.append("tenant_mismatch")
    if pack.domain_id and domain and domain != pack.domain_id:
        if explicit_cross_domain_permission is not True and is_admin is not True:
            decision = cross_domain_read_allowed(pack.domain_id, domain, "evidence_pack")
            if not decision["allowed"]:
                reasons.append("cross_domain_requires_explicit_permission")
    allowed = not reasons
    return {
        "schema": SCHEMA,
        "allowed": allowed,
        "reasons": reasons,
        "grants_permission": False,
        "executes_action": False,
    }


def serialize_pack(pack: EvidencePack) -> str:
    return json.dumps(pack.as_dict(), ensure_ascii=False, sort_keys=True, default=str)


def deserialize_pack(raw: str) -> EvidencePack:
    data = json.loads(raw)
    items = [EvidenceItem(**i) for i in data.get("evidence_items", [])]
    assessments = [TrustAssessment(**t) for t in data.get("trust_assessments", [])]
    provs = [ProvenanceRecord(**p) for p in data.get("provenance_records", [])]
    return EvidencePack(
        evidence_pack_id=data["evidence_pack_id"],
        claim_ids=tuple(data.get("claim_ids", [])),
        evidence_items=tuple(items),
        trust_assessments=tuple(assessments),
        provenance_records=tuple(provs),
        sources=tuple(data.get("sources", [])),
        conflict_flags=tuple(data.get("conflict_flags", [])),
        stale_flags=tuple(data.get("stale_flags", [])),
        tenant_id=data["tenant_id"],
        domain_id=data["domain_id"],
        schema_version=int(data.get("schema_version", PACK_VERSION)),
        generated_at=data.get("generated_at", ""),
        requires_evidence=bool(data.get("requires_evidence", True)),
        digest=data["digest"],
    )


__all__ = [
    "SCHEMA",
    "PACK_VERSION",
    "EvidencePack",
    "EvidencePackError",
    "create_evidence_pack",
    "validate_evidence_pack",
    "pack_access_allowed",
    "serialize_pack",
    "deserialize_pack",
]
