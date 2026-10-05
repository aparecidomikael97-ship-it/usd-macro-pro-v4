"""AION Core V2.3 memory governance contract.

Pure/offline facade over the existing memory architecture, provenance and truth
contracts. It does not persist state, call providers, promote knowledge
automatically, or authorize external execution.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Mapping, Sequence
import json

from aion_core.memory_architecture import create_record as create_architecture_record
from aion_core.provenance import ProvenanceRecord, provenance_digest
from atlasquant_aion_truth import TRUTH_STATES

SCHEMA = "ATLASQUANT_AION_MEMORY_CONTRACT_V23"
CONTRACT_VERSION = 23

MEMORY_NAMESPACES = (
    "ECOSYSTEM","SECTOR","PROJECT","TENANT","PERSONA","SUBJECT",
    "DECISION","TASK","EVIDENCE","RESULT","ERROR","LESSON",
)
MEMORY_CLASSES = (
    "WORKING","EPISODIC","SEMANTIC","PROCEDURAL","TENANT","ADMIN","DOMAIN",
)
VALIDATION_STATES = (
    "VALIDATED","CONFLICTING","OUTDATED","DOUBTFUL",
    "QUARANTINED","REJECTED","UNVERIFIED","PROPOSED",
)
SENSITIVITY_LEVELS = ("PUBLIC","INTERNAL","CONFIDENTIAL","RESTRICTED")
RETENTION_POLICIES = ("SESSION","PROJECT","LONG_TERM","UNTIL_SUPERSEDED","LEGAL_HOLD")
LESSON_STATES = ("PROPOSED","OBSERVED","VALIDATED","REJECTED","SUPERSEDED")

_VALIDATION_MAP = {
    "VALIDATED": ("VALIDATED","CONFIRMED"),
    "CONFLICTING": ("CONFLICTING","UNKNOWN"),
    "OUTDATED": ("STALE","UNKNOWN"),
    "DOUBTFUL": ("CANDIDATE","HYPOTHESIS"),
    "QUARANTINED": ("QUARANTINED","UNKNOWN"),
    "REJECTED": ("REJECTED","UNKNOWN"),
    "UNVERIFIED": ("CANDIDATE","UNKNOWN"),
    "PROPOSED": ("CANDIDATE","HYPOTHESIS"),
}


class MemoryContractError(ValueError):
    """Fail-closed validation error for V2.3 memory contracts."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(value: Any, limit: int = 4000) -> str:
    return " ".join(str(value or "").replace("\x00","").split())[:limit]


def _canonical(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",",":"),
        allow_nan=False,
        default=str,
    )


def _digest(value: Any) -> str:
    return "sha256:" + sha256(_canonical(value).encode("utf-8")).hexdigest()


def _enum(value: Any, allowed: Sequence[str], label: str) -> str:
    key=_clean(value,80).upper()
    if key not in allowed:
        raise MemoryContractError(f"invalid {label}: {value!r}")
    return key


def _refs(values: Sequence[Any] | None, *, limit: int = 64) -> tuple[str,...]:
    out=[]
    for raw in list(values or [])[:limit*2]:
        text=_clean(raw,300)
        if text and text not in out:
            out.append(text)
        if len(out)>=limit:
            break
    return tuple(out)


def _scope(raw: Mapping[str,Any] | None) -> dict[str,str]:
    item=dict(raw or {})
    keys=(
        "ecosystem_id","sector_id","project_id","tenant_id","persona_id",
        "subject_id","decision_id","task_id",
    )
    return {key:_clean(item.get(key),120) for key in keys}


@dataclass(frozen=True)
class MemoryContractRecord:
    memory_id: str
    namespace: str
    memory_class: str
    content: str
    scope: Mapping[str,str]
    provenance_ids: tuple[str,...]
    version: int
    previous_version: str
    evidence_refs: tuple[str,...]
    validation_state: str
    retention: str
    sensitivity: str
    rollback_pointer: str
    tombstone: bool
    created_at: str
    updated_at: str
    metadata: Mapping[str,Any]

    def as_dict(self) -> dict[str,Any]:
        row=asdict(self)
        row["scope"]=dict(self.scope)
        row["provenance_ids"]=list(self.provenance_ids)
        row["evidence_refs"]=list(self.evidence_refs)
        row["metadata"]=dict(self.metadata)
        return row


def validation_mapping(state: Any) -> dict[str,str]:
    key=_enum(state,VALIDATION_STATES,"validation_state")
    architecture_state,truth_state=_VALIDATION_MAP[key]
    if truth_state not in TRUTH_STATES:
        raise MemoryContractError("truth mapping drift")
    return {
        "validation_state":key,
        "architecture_state":architecture_state,
        "truth_state":truth_state,
    }


def create_memory_record(
    *,
    namespace: Any,
    memory_class: Any,
    content: Any,
    scope: Mapping[str,Any] | None = None,
    provenance_ids: Sequence[Any] | None = None,
    version: Any = 1,
    previous_version: Any = "",
    evidence_refs: Sequence[Any] | None = None,
    validation_state: Any = "PROPOSED",
    retention: Any = "PROJECT",
    sensitivity: Any = "INTERNAL",
    rollback_pointer: Any = "",
    tombstone: bool = False,
    created_at: Any = "",
    metadata: Mapping[str,Any] | None = None,
) -> MemoryContractRecord:
    namespace_key=_enum(namespace,MEMORY_NAMESPACES,"namespace")
    class_key=_enum(memory_class,MEMORY_CLASSES,"memory_class")
    validation_key=_enum(validation_state,VALIDATION_STATES,"validation_state")
    retention_key=_enum(retention,RETENTION_POLICIES,"retention")
    sensitivity_key=_enum(sensitivity,SENSITIVITY_LEVELS,"sensitivity")
    text=_clean(content,8000)
    if not text and tombstone is not True:
        raise MemoryContractError("content is required unless tombstone=True")
    try:
        version_value=int(version)
    except Exception as exc:
        raise MemoryContractError("version must be a positive integer") from exc
    if isinstance(version,bool) or version_value<1:
        raise MemoryContractError("version must be a positive integer")

    scoped=_scope(scope)
    prov=_refs(provenance_ids)
    evidence=_refs(evidence_refs)
    previous=_clean(previous_version,160)
    rollback=_clean(rollback_pointer,160)

    if namespace_key=="TENANT" and not scoped["tenant_id"]:
        raise MemoryContractError("TENANT namespace requires tenant_id")
    if namespace_key=="PERSONA" and not scoped["persona_id"]:
        raise MemoryContractError("PERSONA namespace requires persona_id")
    if namespace_key=="SECTOR" and not scoped["sector_id"]:
        raise MemoryContractError("SECTOR namespace requires sector_id")
    if namespace_key=="PROJECT" and not scoped["project_id"]:
        raise MemoryContractError("PROJECT namespace requires project_id")
    if version_value>1 and not previous:
        raise MemoryContractError("version > 1 requires previous_version")
    if validation_key=="VALIDATED" and not (prov or evidence):
        raise MemoryContractError("VALIDATED memory requires provenance or evidence")
    if validation_key=="CONFLICTING" and not (prov or evidence):
        raise MemoryContractError("CONFLICTING memory requires conflict evidence")
    if tombstone is True and validation_key=="VALIDATED":
        raise MemoryContractError("tombstone cannot be VALIDATED")
    if sensitivity_key=="RESTRICTED" and not scoped["tenant_id"] and class_key!="ADMIN":
        raise MemoryContractError("RESTRICTED memory requires tenant scope or ADMIN class")

    stamp=_clean(created_at,80) or _now()
    identity={
        "namespace":namespace_key,
        "memory_class":class_key,
        "scope":scoped,
        "version":version_value,
        "previous_version":previous,
        "content":text,
    }
    memory_id="MEM-"+_digest(identity).split(":",1)[1][:20].upper()
    safe_meta={
        _clean(k,80):_clean(v,400)
        for k,v in dict(metadata or {}).items()
        if _clean(k,80)
    }
    return MemoryContractRecord(
        memory_id=memory_id,
        namespace=namespace_key,
        memory_class=class_key,
        content=text,
        scope=scoped,
        provenance_ids=prov,
        version=version_value,
        previous_version=previous,
        evidence_refs=evidence,
        validation_state=validation_key,
        retention=retention_key,
        sensitivity=sensitivity_key,
        rollback_pointer=rollback,
        tombstone=tombstone is True,
        created_at=stamp,
        updated_at=stamp,
        metadata=safe_meta,
    )


def operational_decision(record: MemoryContractRecord) -> dict[str,Any]:
    blockers=[]
    if record.tombstone:
        blockers.append("TOMBSTONED")
    if record.validation_state=="CONFLICTING":
        blockers.append("CONFLICT_BLOCKER")
    elif record.validation_state=="OUTDATED":
        blockers.append("OUTDATED")
    elif record.validation_state=="DOUBTFUL":
        blockers.append("DOUBTFUL")
    elif record.validation_state=="QUARANTINED":
        blockers.append("QUARANTINED")
    elif record.validation_state=="REJECTED":
        blockers.append("REJECTED")
    elif record.validation_state in {"UNVERIFIED","PROPOSED"}:
        blockers.append("EVIDENCE_NOT_VALIDATED")
    if record.validation_state=="VALIDATED" and not (record.provenance_ids or record.evidence_refs):
        blockers.append("EVIDENCE_MISSING")
    return {
        "schema":SCHEMA,
        "memory_id":record.memory_id,
        "allowed_for_operational_use":not blockers and record.validation_state=="VALIDATED",
        "blockers":blockers,
        "truth_state":validation_mapping(record.validation_state)["truth_state"],
        "external_action_executed":False,
        "execution_allowed":False,
    }


def to_architecture_record(record: MemoryContractRecord):
    mapping=validation_mapping(record.validation_state)
    return create_architecture_record(
        layer=record.memory_class,
        content=record.content or "[TOMBSTONE]",
        tenant_id=record.scope.get("tenant_id",""),
        domain_id=record.scope.get("sector_id","") or record.scope.get("ecosystem_id",""),
        source_ref=(record.provenance_ids or record.evidence_refs or ("",))[0],
        confidence=1.0 if record.validation_state=="VALIDATED" else 0.0,
        created_at=record.created_at,
        version=str(record.version),
        metadata={
            "v23_memory_id":record.memory_id,
            "namespace":record.namespace,
            "sensitivity":record.sensitivity,
            "retention":record.retention,
        },
        state=mapping["architecture_state"],
    )


def provenance_refs(records: Sequence[ProvenanceRecord] | None) -> list[dict[str,str]]:
    out=[]
    for record in list(records or [])[:64]:
        if not isinstance(record,ProvenanceRecord):
            raise MemoryContractError("trusted ProvenanceRecord required")
        out.append({
            "provenance_id":record.provenance_id,
            "digest":provenance_digest(record),
        })
    return out


def normalize_lesson(
    raw: Mapping[str,Any] | None,
    *,
    state: Any = "PROPOSED",
) -> dict[str,Any]:
    item=dict(raw or {})
    lesson_state=_enum(state or item.get("state"),LESSON_STATES,"lesson_state")
    lesson=_clean(item.get("lesson") or item.get("content"),2000)
    if not lesson:
        raise MemoryContractError("lesson content required")
    evidence=_refs(item.get("evidence_refs") if isinstance(item.get("evidence_refs"),(list,tuple)) else [])
    if lesson_state=="VALIDATED" and not evidence:
        raise MemoryContractError("validated lesson requires evidence")
    return {
        "schema":"ATLASQUANT_AION_LESSON_CONTRACT_V23",
        "lesson":lesson,
        "state":lesson_state,
        "evidence_refs":list(evidence),
        "scope":_scope(item.get("scope") if isinstance(item.get("scope"),Mapping) else {}),
        "global_rule":False,
        "automatic_policy_change":False,
        "external_action_executed":False,
    }


LIBRARY_REQUIRED_FIELDS=(
    "document_id","hash","version","author","date","origin","subject",
    "evidence_refs","excerpts","quality","conflict","status",
    "superseded_by","provenance_chain",
)


def validate_library_document_contract(raw: Mapping[str,Any] | None) -> dict[str,Any]:
    item=dict(raw or {})
    missing=[key for key in LIBRARY_REQUIRED_FIELDS if key not in item]
    status=_clean(item.get("status"),40).upper() or "UNVERIFIED"
    if status not in {"VALIDATED","CONFLICTING","OUTDATED","DOUBTFUL","QUARANTINED","REJECTED","UNVERIFIED"}:
        missing.append("status:invalid")
    evidence=item.get("evidence_refs")
    provenance=item.get("provenance_chain")
    if status=="VALIDATED" and not (
        isinstance(evidence,(list,tuple)) and evidence
        and isinstance(provenance,(list,tuple)) and provenance
    ):
        missing.append("validated_without_evidence_or_provenance")
    return {
        "schema":"ATLASQUANT_AION_LIBRARY_DOCUMENT_CONTRACT_V23",
        "valid":not missing,
        "missing_or_invalid":missing,
        "status":status,
        "external_ingestion_executed":False,
        "embeddings_executed":False,
        "provider_call_executed":False,
    }


def memory_contract_digest(record: MemoryContractRecord | Mapping[str,Any]) -> str:
    row=record.as_dict() if isinstance(record,MemoryContractRecord) else dict(record or {})
    return _digest(row)


__all__=[
    "SCHEMA","CONTRACT_VERSION","MEMORY_NAMESPACES","MEMORY_CLASSES",
    "VALIDATION_STATES","SENSITIVITY_LEVELS","RETENTION_POLICIES","LESSON_STATES",
    "MemoryContractError","MemoryContractRecord","create_memory_record",
    "validation_mapping","operational_decision","to_architecture_record",
    "provenance_refs","normalize_lesson","validate_library_document_contract",
    "memory_contract_digest",
]
