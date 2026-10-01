"""AION core provenance engine.

Every piece of knowledge used by AION must be able to answer: where did it
come from, when, which version, which authority, was it validated, is it
current, which tenant and domain does it belong to. Pure/offline: no network,
no providers, no side effects.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence
import hashlib
import json
import unicodedata

SCHEMA = "ATLASQUANT_AION_CORE_PROVENANCE_V1"
PROVENANCE_VERSION = 1

SOURCE_TYPES = (
    "PRIMARY_SOURCE",
    "OFFICIAL_SOURCE",
    "INTERNAL_DOCUMENT",
    "BOOK",
    "ACADEMIC",
    "NEWS",
    "WEB",
    "CLIENT_DATA",
    "MODEL_OUTPUT",
    "HUMAN_INPUT",
    "DERIVED_ANALYSIS",
    "UNKNOWN",
)

REVIEW_STATUSES = (
    "UNREVIEWED",
    "REVIEWED",
    "VALIDATED",
    "CONFLICTING",
    "STALE",
    "QUARANTINED",
    "REJECTED",
)

# Explicit state machine for review status. Fail closed on anything else.
STATUS_TRANSITIONS: dict[str, tuple[str, ...]] = {
    "UNREVIEWED": ("REVIEWED", "VALIDATED", "QUARANTINED", "REJECTED"),
    "REVIEWED": ("VALIDATED", "CONFLICTING", "STALE", "QUARANTINED", "REJECTED"),
    "VALIDATED": ("CONFLICTING", "STALE", "QUARANTINED", "REJECTED"),
    "CONFLICTING": ("VALIDATED", "STALE", "QUARANTINED", "REJECTED"),
    "STALE": ("REVIEWED", "VALIDATED", "QUARANTINED", "REJECTED"),
    "QUARANTINED": ("UNREVIEWED", "REJECTED"),
    "REJECTED": (),
}


class ProvenanceError(ValueError):
    """Fail-closed error for invalid provenance records or transitions."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(value: Any, limit: int = 240) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _digest(value: Any, length: int = 24) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:length]


@dataclass(frozen=True)
class ProvenanceRecord:
    provenance_id: str
    source_type: str
    source_reference: str
    source_title: str
    author: str
    publisher: str
    published_at: str
    retrieved_at: str
    document_version: str
    location_reference: str
    ingestion_id: str
    checksum: str
    tenant_id: str
    domain_id: str
    rights_status: str
    review_status: str
    confidence: float
    last_validation: str
    parent_provenance_ids: tuple[str, ...]
    metadata: Mapping[str, Any]

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["parent_provenance_ids"] = list(self.parent_provenance_ids)
        data["metadata"] = dict(self.metadata)
        return data


def create_provenance(
    *,
    source_type: Any,
    source_reference: Any = "",
    source_title: Any = "",
    author: Any = "",
    publisher: Any = "",
    published_at: Any = "",
    retrieved_at: Any = "",
    document_version: Any = "",
    location_reference: Any = "",
    ingestion_id: Any = "",
    checksum: Any = "",
    tenant_id: Any = "",
    domain_id: Any = "",
    rights_status: Any = "UNKNOWN",
    review_status: Any = "UNREVIEWED",
    confidence: Any = 0.0,
    last_validation: Any = "",
    parent_provenance_ids: Sequence[Any] | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> ProvenanceRecord:
    """Create a provenance record. UNKNOWN stays UNKNOWN; a missing
    source_reference is preserved as empty and flagged by validate_provenance,
    never masked."""
    key_type = _clean(source_type, 40).upper()
    if key_type not in SOURCE_TYPES:
        raise ProvenanceError(f"unknown source_type: {source_type!r}")
    key_status = _clean(review_status, 40).upper()
    if key_status not in REVIEW_STATUSES:
        raise ProvenanceError(f"unknown review_status: {review_status!r}")
    try:
        conf = max(0.0, min(1.0, float(confidence)))
    except Exception:
        conf = 0.0
    parents = tuple(_clean(p, 80) for p in list(parent_provenance_ids or []) if _clean(p, 80))
    if key_type == "DERIVED_ANALYSIS" and not parents:
        raise ProvenanceError("DERIVED_ANALYSIS requires parent_provenance_ids")
    stamp = _clean(retrieved_at, 80) or _now()
    payload = {
        "source_type": key_type,
        "source_reference": _clean(source_reference, 400),
        "source_title": _clean(source_title, 400),
        "author": _clean(author, 240),
        "publisher": _clean(publisher, 240),
        "published_at": _clean(published_at, 80),
        "document_version": _clean(document_version, 80),
        "location_reference": _clean(location_reference, 400),
        "ingestion_id": _clean(ingestion_id, 120),
        "checksum": _clean(checksum, 160),
        "tenant_id": _clean(tenant_id, 120),
        "domain_id": _clean(domain_id, 40).upper(),
        "rights_status": _clean(rights_status, 40).upper(),
        "parents": list(parents),
    }
    provenance_id = "PRV-" + _digest(payload).upper()
    meta = {k: _clean(v, 240) for k, v in dict(metadata or {}).items()}
    return ProvenanceRecord(
        provenance_id=provenance_id,
        source_type=key_type,
        source_reference=_clean(source_reference, 400),
        source_title=_clean(source_title, 400),
        author=_clean(author, 240),
        publisher=_clean(publisher, 240),
        published_at=_clean(published_at, 80),
        retrieved_at=stamp,
        document_version=_clean(document_version, 80),
        location_reference=_clean(location_reference, 400),
        ingestion_id=_clean(ingestion_id, 120),
        checksum=_clean(checksum, 160),
        tenant_id=_clean(tenant_id, 120),
        domain_id=_clean(domain_id, 40).upper(),
        rights_status=_clean(rights_status, 40).upper(),
        review_status=key_status,
        confidence=round(conf, 4),
        last_validation=_clean(last_validation, 80),
        parent_provenance_ids=parents,
        metadata=meta,
    )


def provenance_digest(record: ProvenanceRecord | Mapping[str, Any]) -> str:
    """Deterministic digest over material fields only. Volatile fields
    (retrieved_at, updated metadata timestamps) are excluded so that the same
    knowledge keeps the same digest across re-retrievals."""
    data = record.as_dict() if isinstance(record, ProvenanceRecord) else dict(record)
    material = {k: v for k, v in data.items() if k not in ("retrieved_at",)}
    raw = json.dumps(material, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def validate_provenance(record: ProvenanceRecord) -> dict[str, Any]:
    """Explicit validation UNREVIEWED/REVIEWED/STALE -> VALIDATED with reasons."""
    reasons: list[str] = []
    warnings: list[str] = []
    if record.source_type == "UNKNOWN":
        reasons.append("unknown_source_type")
    if not record.source_reference:
        reasons.append("source_reference_missing")
    if not record.checksum:
        warnings.append("checksum_missing")
    if not record.published_at:
        warnings.append("published_at_missing")
    allowed = STATUS_TRANSITIONS.get(record.review_status, ())
    if "VALIDATED" not in allowed:
        reasons.append(f"invalid_transition_{record.review_status}_to_VALIDATED")
    decision = {
        "schema": SCHEMA,
        "validatable": not reasons,
        "reasons": reasons,
        "warnings": warnings,
        "executes_action": False,
    }
    if reasons:
        return decision
    data = record.as_dict()
    data["review_status"] = "VALIDATED"
    data["last_validation"] = _now()
    return {**decision, "record": ProvenanceRecord(**data)}


def _transition(record: ProvenanceRecord, target: Any) -> ProvenanceRecord:
    key = _clean(target, 40).upper()
    if key not in REVIEW_STATUSES:
        raise ProvenanceError(f"unknown review_status: {target!r}")
    if key not in STATUS_TRANSITIONS.get(record.review_status, ()):
        raise ProvenanceError(
            f"invalid transition {record.review_status} -> {key} for {record.provenance_id}"
        )
    data = record.as_dict()
    data["review_status"] = key
    return ProvenanceRecord(**data)


def mark_provenance_stale(record: ProvenanceRecord, *, reason: Any = "") -> ProvenanceRecord:
    result = _transition(record, "STALE")
    data = result.as_dict()
    data["metadata"] = dict(record.metadata)
    data["metadata"]["stale_reason"] = _clean(reason, 240)
    return ProvenanceRecord(**data)


def mark_provenance_conflicting(record: ProvenanceRecord, *, conflict_ref: Any = "") -> ProvenanceRecord:
    result = _transition(record, "CONFLICTING")
    data = result.as_dict()
    data["metadata"] = dict(record.metadata)
    data["metadata"]["conflict_ref"] = _clean(conflict_ref, 240)
    return ProvenanceRecord(**data)


def derive_provenance(
    *,
    parents: Sequence[ProvenanceRecord],
    analysis_note: Any = "",
    tenant_id: Any = "",
    domain_id: Any = "",
    metadata: Mapping[str, Any] | None = None,
) -> ProvenanceRecord:
    """Derived analysis must preserve its parent references (lineage)."""
    parent_list = list(parents or [])
    if not parent_list:
        raise ProvenanceError("derive_provenance requires at least one parent")
    tenant = _clean(tenant_id, 120)
    if not tenant:
        tenants = {p.tenant_id for p in parent_list if p.tenant_id}
        if len(tenants) > 1:
            raise ProvenanceError("derived provenance cannot mix tenants")
        tenant = next(iter(tenants), "")
    return create_provenance(
        source_type="DERIVED_ANALYSIS",
        source_reference="derived:" + ",".join(p.provenance_id for p in parent_list),
        source_title=_clean(analysis_note, 400),
        tenant_id=tenant,
        domain_id=domain_id,
        parent_provenance_ids=[p.provenance_id for p in parent_list],
        metadata=metadata,
    )


def provenance_access_allowed(
    record: ProvenanceRecord,
    *,
    requesting_tenant_id: Any = "",
    requesting_domain_id: Any = "",
    is_admin: bool = False,
    explicit_cross_domain_permission: bool = False,
) -> dict[str, Any]:
    reasons: list[str] = []
    tenant = _clean(requesting_tenant_id, 120)
    domain = _clean(requesting_domain_id, 40).upper()
    if record.tenant_id and record.tenant_id != tenant:
        reasons.append("tenant_mismatch")
    if record.domain_id and domain and record.domain_id != domain:
        if explicit_cross_domain_permission is not True and is_admin is not True:
            reasons.append("cross_domain_requires_explicit_permission")
    if record.review_status == "QUARANTINED":
        reasons.append("quarantined_not_operational")
    return {
        "schema": SCHEMA,
        "allowed": not reasons,
        "reasons": reasons,
        "executes_action": False,
    }


def provenance_lineage(record: ProvenanceRecord, known: Mapping[str, ProvenanceRecord]) -> list[str]:
    """Walk parent ids through the known registry. Unknown parents stop the
    walk but are still reported (lineage gaps are visible, not hidden)."""
    chain: list[str] = []
    seen: set[str] = set()
    frontier = list(record.parent_provenance_ids)
    while frontier:
        current = frontier.pop(0)
        if not current or current in seen:
            continue
        seen.add(current)
        chain.append(current)
        parent = known.get(current)
        if parent is not None:
            frontier.extend(parent.parent_provenance_ids)
    return chain


__all__ = [
    "SCHEMA",
    "PROVENANCE_VERSION",
    "SOURCE_TYPES",
    "REVIEW_STATUSES",
    "STATUS_TRANSITIONS",
    "ProvenanceRecord",
    "ProvenanceError",
    "create_provenance",
    "provenance_digest",
    "validate_provenance",
    "mark_provenance_stale",
    "mark_provenance_conflicting",
    "derive_provenance",
    "provenance_access_allowed",
    "provenance_lineage",
]
