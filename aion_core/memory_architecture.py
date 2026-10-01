"""AION core memory architecture.

Facade/contract over the existing AION memory infrastructure
(atlasquant_aion_memory_layers and atlasquant_aion_memory_quarantine).
It adds the seven architectural layers, the seven knowledge states and an
explicit fail-closed state machine. It does not recreate the layered memory
store, does not persist externally, does not call the network, and never
promotes memory by repetition alone.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence
import hashlib
import json
import unicodedata

SCHEMA = "ATLASQUANT_AION_CORE_MEMORY_ARCHITECTURE_V1"
ARCHITECTURE_VERSION = 1

LAYERS = ("WORKING", "EPISODIC", "SEMANTIC", "PROCEDURAL", "TENANT", "ADMIN", "DOMAIN")
STATES = (
    "CANDIDATE",
    "VALIDATED",
    "CONFLICTING",
    "STALE",
    "QUARANTINED",
    "REJECTED",
    "SUPERSEDED",
)

# Explicit state machine. Anything not listed here fails closed.
TRANSITIONS: dict[str, tuple[str, ...]] = {
    "CANDIDATE": ("VALIDATED", "QUARANTINED", "REJECTED", "SUPERSEDED"),
    "VALIDATED": ("CONFLICTING", "STALE", "SUPERSEDED"),
    "CONFLICTING": ("VALIDATED", "REJECTED", "SUPERSEDED"),
    "STALE": ("VALIDATED", "SUPERSEDED", "REJECTED"),
    "QUARANTINED": ("CANDIDATE", "REJECTED"),
    "REJECTED": (),
    "SUPERSEDED": (),
}

# States visible in normal operational reads. QUARANTINED and REJECTED are
# history/audit only; CONFLICTING and STALE are visible but never "valid".
OPERATIONAL_STATES = ("CANDIDATE", "VALIDATED", "CONFLICTING", "STALE")
VALID_STATES = ("VALIDATED",)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(value: Any, limit: int = 240) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _fold(value: Any) -> str:
    raw = unicodedata.normalize("NFKD", str(value or ""))
    return "".join(ch for ch in raw if not unicodedata.combining(ch)).casefold()


def _digest(value: Any, length: int = 24) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:length]


@dataclass(frozen=True)
class MemoryRecord:
    memory_id: str
    layer: str
    state: str
    content: str
    tenant_id: str
    domain_id: str
    source_ref: str
    confidence: float
    created_at: str
    updated_at: str
    version: str
    supersedes: str
    metadata: Mapping[str, Any]

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["metadata"] = dict(self.metadata)
        return data


class MemoryArchitectureError(ValueError):
    """Fail-closed error for invalid records or transitions."""


def _require_layer(layer: Any) -> str:
    key = _clean(layer, 40).upper()
    if key not in LAYERS:
        raise MemoryArchitectureError(f"unknown memory layer: {layer!r}")
    return key


def _require_state(state: Any) -> str:
    key = _clean(state, 40).upper()
    if key not in STATES:
        raise MemoryArchitectureError(f"unknown memory state: {state!r}")
    return key


def create_record(
    *,
    layer: Any,
    content: Any,
    tenant_id: Any = "",
    domain_id: Any = "",
    source_ref: Any = "",
    confidence: Any = 0.0,
    created_at: Any = "",
    version: Any = "1",
    metadata: Mapping[str, Any] | None = None,
    state: Any = "CANDIDATE",
) -> MemoryRecord:
    """Create a record. New content always starts as CANDIDATE unless the
    caller explicitly passes another state (used by tests/admin tooling)."""
    key_layer = _require_layer(layer)
    key_state = _require_state(state)
    text = _clean(content, 4000)
    if not text:
        raise MemoryArchitectureError("content is required")
    tenant = _clean(tenant_id, 120)
    domain = _clean(domain_id, 40).upper()
    if key_layer == "TENANT" and not tenant:
        raise MemoryArchitectureError("TENANT memory requires tenant_id")
    if key_layer == "DOMAIN" and not domain:
        raise MemoryArchitectureError("DOMAIN memory requires domain_id")
    if domain and domain not in {
        "CORE", "NEGOCIOS", "TRADER", "INVESTIMENTOS", "BIBLIOTECA",
        "ADMIN", "SEGURANCA", "MEMORIA", "ORQUESTRACAO",
    }:
        raise MemoryArchitectureError(f"unknown domain_id: {domain_id!r}")
    try:
        conf = max(0.0, min(1.0, float(confidence)))
    except Exception:
        conf = 0.0
    stamp = _clean(created_at, 80) or _now()
    payload = {"layer": key_layer, "content": text, "tenant": tenant, "domain": domain, "version": _clean(version, 40)}
    memory_id = "MAM-" + _digest(payload).upper()
    meta = {k: _clean(v, 200) for k, v in dict(metadata or {}).items()}
    return MemoryRecord(
        memory_id=memory_id,
        layer=key_layer,
        state=key_state,
        content=text,
        tenant_id=tenant,
        domain_id=domain,
        source_ref=_clean(source_ref, 240),
        confidence=round(conf, 4),
        created_at=stamp,
        updated_at=stamp,
        version=_clean(version, 40) or "1",
        supersedes="",
        metadata=meta,
    )


def _transition(record: MemoryRecord, target: Any, *, supersedes_by: str = "") -> MemoryRecord:
    target_state = _require_state(target)
    allowed = TRANSITIONS.get(record.state, ())
    if target_state not in allowed:
        raise MemoryArchitectureError(
            f"invalid transition {record.state} -> {target_state} for {record.memory_id}"
        )
    data = record.as_dict()
    data["state"] = target_state
    data["updated_at"] = _now()
    if target_state == "SUPERSEDED":
        if not supersedes_by:
            raise MemoryArchitectureError("supersede requires the successor id")
        # keep predecessor link on successor; mark this one superseded
    return MemoryRecord(**data)


def validate_record(record: MemoryRecord, *, reviewer: Any = "") -> MemoryRecord:
    """Explicit promotion CANDIDATE/CONFLICTING/STALE -> VALIDATED."""
    result = _transition(record, "VALIDATED")
    data = result.as_dict()
    data["metadata"] = dict(record.metadata)
    if _clean(reviewer, 80):
        data["metadata"]["reviewer"] = _clean(reviewer, 80)
    return MemoryRecord(**data)


def mark_conflicting(record: MemoryRecord, *, conflict_ref: Any = "") -> MemoryRecord:
    result = _transition(record, "CONFLICTING")
    data = result.as_dict()
    data["metadata"] = dict(record.metadata)
    data["metadata"]["conflict_ref"] = _clean(conflict_ref, 240)
    return MemoryRecord(**data)


def mark_stale(record: MemoryRecord, *, reason: Any = "") -> MemoryRecord:
    result = _transition(record, "STALE")
    data = result.as_dict()
    data["metadata"] = dict(record.metadata)
    data["metadata"]["stale_reason"] = _clean(reason, 240)
    return MemoryRecord(**data)


def quarantine(record: MemoryRecord, *, reason: Any = "") -> MemoryRecord:
    result = _transition(record, "QUARANTINED")
    data = result.as_dict()
    data["metadata"] = dict(record.metadata)
    data["metadata"]["quarantine_reason"] = _clean(reason, 240)
    return MemoryRecord(**data)


def reject(record: MemoryRecord, *, reason: Any = "") -> MemoryRecord:
    """REJECTED is terminal for operational use but the record stays readable
    through list_history. It is never deleted."""
    result = _transition(record, "REJECTED")
    data = result.as_dict()
    data["metadata"] = dict(record.metadata)
    data["metadata"]["reject_reason"] = _clean(reason, 240)
    return MemoryRecord(**data)


def supersede(record: MemoryRecord, *, successor_id: Any) -> MemoryRecord:
    result = _transition(record, "SUPERSEDED", supersedes_by=_clean(successor_id, 80))
    data = result.as_dict()
    data["metadata"] = dict(record.metadata)
    data["metadata"]["superseded_by"] = _clean(successor_id, 80)
    return MemoryRecord(**data)


def read_allowed(
    record: MemoryRecord,
    *,
    requesting_tenant_id: Any = "",
    requesting_domain_id: Any = "",
    is_admin: bool = False,
    explicit_cross_domain_permission: bool = False,
) -> dict[str, Any]:
    """Access decision. Unknown/missing context denies (fail closed)."""
    reasons: list[str] = []
    if record.state == "QUARANTINED":
        reasons.append("quarantined_not_operational")
    elif record.state == "REJECTED":
        reasons.append("rejected_history_only")
    tenant = _clean(requesting_tenant_id, 120)
    domain = _clean(requesting_domain_id, 40).upper()
    if record.layer == "TENANT":
        if not tenant:
            reasons.append("requesting_tenant_missing")
        elif tenant != record.tenant_id:
            reasons.append("tenant_mismatch")
    if record.layer == "ADMIN":
        if is_admin is not True:
            reasons.append("admin_layer_requires_admin")
    if record.layer == "DOMAIN":
        if not domain:
            reasons.append("requesting_domain_missing")
        elif domain != record.domain_id:
            if explicit_cross_domain_permission is not True:
                reasons.append("cross_domain_requires_explicit_permission")
    allowed = not reasons
    return {
        "schema": SCHEMA,
        "allowed": allowed,
        "reasons": reasons,
        "state_visible_as_valid": record.state in VALID_STATES,
        "executes_action": False,
    }


def read_record(
    store: Mapping[str, Any] | None,
    memory_id: Any,
    *,
    requesting_tenant_id: Any = "",
    requesting_domain_id: Any = "",
    is_admin: bool = False,
    explicit_cross_domain_permission: bool = False,
) -> dict[str, Any]:
    """Operational read: only OPERATIONAL_STATES are returned; QUARANTINED and
    REJECTED records exist but are not served here (use list_history)."""
    records = _records_of(store)
    target = next((r for r in records if r.memory_id == _clean(memory_id, 80)), None)
    if target is None:
        return {"schema": SCHEMA, "found": False, "reasons": ["record_missing"], "record": None}
    decision = read_allowed(
        target,
        requesting_tenant_id=requesting_tenant_id,
        requesting_domain_id=requesting_domain_id,
        is_admin=is_admin,
        explicit_cross_domain_permission=explicit_cross_domain_permission,
    )
    if not decision["allowed"]:
        return {"schema": SCHEMA, "found": True, "allowed": False, "reasons": decision["reasons"], "record": None}
    if target.state not in OPERATIONAL_STATES:
        return {"schema": SCHEMA, "found": True, "allowed": False, "reasons": ["state_not_operational"], "record": None}
    return {"schema": SCHEMA, "found": True, "allowed": True, "reasons": [], "record": target.as_dict()}


def list_history(
    store: Mapping[str, Any] | None,
    *,
    memory_id: Any = "",
    tenant_id: Any = "",
    include_non_operational: bool = True,
) -> list[dict[str, Any]]:
    """Audit view. REJECTED and SUPERSEDED records remain visible here; the
    chain (supersedes / superseded_by) is preserved."""
    records = _records_of(store)
    rows = []
    for record in records:
        if memory_id and record.memory_id != _clean(memory_id, 80):
            continue
        if tenant_id and record.tenant_id != _clean(tenant_id, 120):
            continue
        if not include_non_operational and record.state not in OPERATIONAL_STATES:
            continue
        rows.append(record.as_dict())
    return rows


def _records_of(store: Mapping[str, Any] | None) -> list[MemoryRecord]:
    raw = (store or {}).get("records") if isinstance(store, Mapping) else None
    out: list[MemoryRecord] = []
    for item in list(raw or []):
        if not isinstance(item, Mapping):
            continue
        try:
            out.append(MemoryRecord(
                memory_id=str(item.get("memory_id") or ""),
                layer=str(item.get("layer") or ""),
                state=str(item.get("state") or ""),
                content=str(item.get("content") or ""),
                tenant_id=str(item.get("tenant_id") or ""),
                domain_id=str(item.get("domain_id") or ""),
                source_ref=str(item.get("source_ref") or ""),
                confidence=float(item.get("confidence") or 0.0),
                created_at=str(item.get("created_at") or ""),
                updated_at=str(item.get("updated_at") or ""),
                version=str(item.get("version") or "1"),
                supersedes=str(item.get("supersedes") or ""),
                metadata=dict(item.get("metadata") or {}),
            ))
        except Exception:
            continue
    return out


def new_store() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "version": ARCHITECTURE_VERSION,
        "records": [],
        "executes_action": False,
        "persists_externally": False,
    }


def put_record(store: Mapping[str, Any] | None, record: MemoryRecord) -> dict[str, Any]:
    """Insert or replace by memory_id. Repeating the same content never changes
    state: repetition is not promotion."""
    base = new_store() if not isinstance(store, Mapping) else dict(store)
    records = [dict(r) for r in list(base.get("records") or []) if isinstance(r, Mapping)]
    payload = record.as_dict()
    replaced = False
    for index, row in enumerate(records):
        if row.get("memory_id") == record.memory_id:
            if row.get("state") == record.state:
                # identical repetition: keep stored row, no promotion
                records[index] = dict(row)
            else:
                # explicit transition supplied by caller
                records[index] = record.as_dict()
            replaced = True
            break
    if not replaced:
        records.append(payload)
    base["records"] = records
    return base


__all__ = [
    "SCHEMA",
    "ARCHITECTURE_VERSION",
    "LAYERS",
    "STATES",
    "TRANSITIONS",
    "OPERATIONAL_STATES",
    "VALID_STATES",
    "MemoryRecord",
    "MemoryArchitectureError",
    "create_record",
    "validate_record",
    "mark_conflicting",
    "mark_stale",
    "quarantine",
    "reject",
    "supersede",
    "read_allowed",
    "read_record",
    "list_history",
    "new_store",
    "put_record",
]
