"""AION Core V2.3 Checkpoint Mestre contract.

Pure/offline snapshot + append-only journal envelope. The existing
atlasquant_aion_memory module remains authoritative for runtime persistence and
atlasquant_aion_recovery remains authoritative for reviewed runtime recovery.
This module only provides deterministic state reconstruction and conflict-safe
contract semantics; it performs no I/O and no external execution.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Mapping, Sequence
import json

SCHEMA="ATLASQUANT_AION_CHECKPOINT_MASTER_V23"
EVENT_SCHEMA="ATLASQUANT_AION_CHECKPOINT_EVENT_V23"
GENESIS="GENESIS"

MAX_BASE_BYTES=1_500_000
MAX_EVENT_BYTES=96_000
MAX_EVENTS=256
MAX_MASTER_BYTES=2_000_000
MAX_DEPTH=24

_FORBIDDEN_TRUE_KEYS=frozenset({
    "external_action_executed",
    "execution_allowed",
    "executes_provider_call",
    "executes_billing",
    "real_orders_enabled",
    "automatic_external_actions",
})


class CheckpointMasterError(ValueError):
    """Fail-closed base error."""


class CheckpointConflict(CheckpointMasterError):
    """Logical compare-and-swap or idempotency conflict."""


class CheckpointIntegrityError(CheckpointMasterError):
    """Digest, chain or schema mismatch."""


def _now()->str:
    return datetime.now(timezone.utc).isoformat()


def _canonical(value:Any)->str:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",",":"),
            allow_nan=False,
            default=str,
        )
    except Exception as exc:
        raise CheckpointMasterError("checkpoint payload is not canonically serializable") from exc


def _bytes(value:Any)->int:
    return len(_canonical(value).encode("utf-8"))


def _digest(value:Any)->str:
    return "sha256:"+sha256(_canonical(value).encode("utf-8")).hexdigest()


def _clean(value:Any,limit:int=240)->str:
    return " ".join(str(value or "").replace("\x00","").split())[:limit]


def _positive_int(value:Any,label:str,minimum:int=0)->int:
    if isinstance(value,bool):
        raise CheckpointMasterError(f"{label} must be an integer")
    try:
        parsed=int(value)
    except Exception as exc:
        raise CheckpointMasterError(f"{label} must be an integer") from exc
    if parsed<minimum:
        raise CheckpointMasterError(f"{label} below minimum")
    return parsed


def _safe_structure(value:Any, *, depth:int=0)->Any:
    if depth>MAX_DEPTH:
        raise CheckpointMasterError("checkpoint nesting too deep")
    if value is None or isinstance(value,(bool,int,str)):
        return value
    if isinstance(value,float):
        if value!=value or value in (float("inf"),float("-inf")):
            raise CheckpointMasterError("non-finite number rejected")
        return value
    if isinstance(value,Mapping):
        out={}
        for raw_key,raw_value in value.items():
            key=_clean(raw_key,160)
            if not key:
                raise CheckpointMasterError("empty checkpoint key")
            checked=_safe_structure(raw_value,depth=depth+1)
            if key in _FORBIDDEN_TRUE_KEYS and checked is True:
                raise CheckpointMasterError(f"unsafe execution flag rejected: {key}")
            out[key]=checked
        return out
    if isinstance(value,(list,tuple)):
        return [_safe_structure(item,depth=depth+1) for item in value]
    raise CheckpointMasterError(f"unsupported checkpoint type: {type(value).__name__}")


def _merge_patch(target:Mapping[str,Any],patch:Mapping[str,Any])->dict[str,Any]:
    out=deepcopy(dict(target))
    for key,value in patch.items():
        if value is None:
            out.pop(key,None)
        elif isinstance(value,Mapping):
            existing=out.get(key)
            base=existing if isinstance(existing,Mapping) else {}
            out[key]=_merge_patch(base,value)
        else:
            out[key]=deepcopy(value)
    return out


def _event_material(event:Mapping[str,Any])->dict[str,Any]:
    return {
        "schema":event.get("schema"),
        "event_id":event.get("event_id"),
        "sequence":event.get("sequence"),
        "base_revision":event.get("base_revision"),
        "revision":event.get("revision"),
        "event_type":event.get("event_type"),
        "created_at":event.get("created_at"),
        "patch":event.get("patch"),
        "patch_digest":event.get("patch_digest"),
        "prev_digest":event.get("prev_digest"),
        "evidence_refs":event.get("evidence_refs"),
    }


def new_checkpoint_master(
    snapshot:Mapping[str,Any],
    *,
    base_revision:Any=0,
    created_at:Any="",
    source_refs:Sequence[Any]|None=None,
    compaction_generation:Any=0,
)->dict[str,Any]:
    if not isinstance(snapshot,Mapping):
        raise CheckpointMasterError("snapshot mapping required")
    checked=_safe_structure(snapshot)
    if _bytes(checked)>MAX_BASE_BYTES:
        raise CheckpointMasterError("base snapshot exceeds limit")
    revision=_positive_int(base_revision,"base_revision",0)
    generation=_positive_int(compaction_generation,"compaction_generation",0)
    refs=[]
    for raw in list(source_refs or [])[:64]:
        text=_clean(raw,300)
        if text and text not in refs:
            refs.append(text)
    state_digest=_digest(checked)
    master={
        "schema":SCHEMA,
        "created_at":_clean(created_at,80) or _now(),
        "base_revision":revision,
        "revision":revision,
        "base_snapshot":checked,
        "base_digest":state_digest,
        "journal":[],
        "head_digest":GENESIS,
        "state_digest":state_digest,
        "compaction_generation":generation,
        "source_refs":refs,
        "compacted_from_head":"",
        "external_action_executed":False,
        "execution_allowed":False,
        "executes_provider_call":False,
        "executes_billing":False,
        "real_orders_enabled":False,
    }
    if _bytes(master)>MAX_MASTER_BYTES:
        raise CheckpointMasterError("checkpoint master exceeds limit")
    return master


def reconstruct_checkpoint(master:Mapping[str,Any], *, target_revision:Any=None)->dict[str,Any]:
    row=dict(master or {})
    if row.get("schema")!=SCHEMA:
        raise CheckpointIntegrityError("checkpoint master schema mismatch")
    base=row.get("base_snapshot")
    journal=row.get("journal")
    if not isinstance(base,Mapping) or not isinstance(journal,list):
        raise CheckpointIntegrityError("checkpoint master shape invalid")
    checked_base=_safe_structure(base)
    if _bytes(checked_base)>MAX_BASE_BYTES:
        raise CheckpointIntegrityError("base snapshot exceeds limit")
    if row.get("base_digest")!=_digest(checked_base):
        raise CheckpointIntegrityError("base digest mismatch")
    if len(journal)>MAX_EVENTS:
        raise CheckpointIntegrityError("journal event limit exceeded")
    base_revision=_positive_int(row.get("base_revision"),"base_revision",0)
    final_revision=_positive_int(row.get("revision"),"revision",base_revision)
    target=final_revision if target_revision is None else _positive_int(target_revision,"target_revision",base_revision)
    if target>final_revision:
        raise CheckpointConflict("target revision beyond current revision")

    state=deepcopy(dict(checked_base))
    previous_digest=GENESIS
    current_revision=base_revision
    seen_ids={}
    applied=0

    for index,event_raw in enumerate(journal,1):
        if not isinstance(event_raw,Mapping):
            raise CheckpointIntegrityError("journal event must be mapping")
        event=dict(event_raw)
        if event.get("schema")!=EVENT_SCHEMA:
            raise CheckpointIntegrityError("event schema mismatch")
        sequence=_positive_int(event.get("sequence"),"sequence",1)
        if sequence!=index:
            raise CheckpointIntegrityError("event sequence mismatch")
        event_id=_clean(event.get("event_id"),160)
        if not event_id:
            raise CheckpointIntegrityError("event_id missing")
        material=_event_material(event)
        patch=material.get("patch")
        if not isinstance(patch,Mapping):
            raise CheckpointIntegrityError("event patch invalid")
        safe_patch=_safe_structure(patch)
        if _bytes(safe_patch)>MAX_EVENT_BYTES:
            raise CheckpointIntegrityError("event patch exceeds limit")
        patch_digest=_digest(safe_patch)
        if material.get("patch_digest")!=patch_digest:
            raise CheckpointIntegrityError("patch digest mismatch")
        if material.get("prev_digest")!=previous_digest:
            raise CheckpointIntegrityError("journal previous digest mismatch")
        expected_base=current_revision
        event_base=_positive_int(event.get("base_revision"),"event base_revision",0)
        event_revision=_positive_int(event.get("revision"),"event revision",1)
        if event_base!=expected_base or event_revision!=expected_base+1:
            raise CheckpointIntegrityError("journal revision chain mismatch")
        calculated_event_digest=_digest(material)
        if event.get("event_digest")!=calculated_event_digest:
            raise CheckpointIntegrityError("event digest mismatch")

        duplicate=seen_ids.get(event_id)
        if duplicate is not None and duplicate!=patch_digest:
            raise CheckpointIntegrityError("duplicate event id with different payload")
        seen_ids[event_id]=patch_digest

        if event_revision<=target:
            state=_merge_patch(state,safe_patch)
            state=_safe_structure(state)
            if _bytes(state)>MAX_BASE_BYTES:
                raise CheckpointIntegrityError("reconstructed snapshot exceeds limit")
            applied+=1
        previous_digest=calculated_event_digest
        current_revision=event_revision

    if current_revision!=final_revision:
        raise CheckpointIntegrityError("master revision mismatch")
    if row.get("head_digest")!=(previous_digest if journal else GENESIS):
        raise CheckpointIntegrityError("head digest mismatch")

    if target==final_revision:
        expected_state_digest=_digest(state)
        if row.get("state_digest")!=expected_state_digest:
            raise CheckpointIntegrityError("state digest mismatch")
    else:
        expected_state_digest=_digest(state)

    return {
        "schema":SCHEMA,
        "snapshot":state,
        "revision":target,
        "state_digest":expected_state_digest,
        "events_applied":applied,
        "external_action_executed":False,
        "execution_allowed":False,
        "real_orders_enabled":False,
    }


def append_checkpoint_patch(
    master:Mapping[str,Any],
    *,
    event_id:Any,
    patch:Mapping[str,Any],
    expected_revision:Any,
    created_at:Any="",
    evidence_refs:Sequence[Any]|None=None,
)->dict[str,Any]:
    current=reconstruct_checkpoint(master)
    expected=_positive_int(expected_revision,"expected_revision",0)
    if expected!=current["revision"]:
        raise CheckpointConflict("REVISION_CONFLICT")
    eid=_clean(event_id,160)
    if not eid:
        raise CheckpointMasterError("event_id required")
    if not isinstance(patch,Mapping):
        raise CheckpointMasterError("patch mapping required")
    checked_patch=_safe_structure(patch)
    if _bytes(checked_patch)>MAX_EVENT_BYTES:
        raise CheckpointMasterError("event patch exceeds limit")
    patch_digest=_digest(checked_patch)

    row=deepcopy(dict(master))
    existing=[
        event for event in row.get("journal",[])
        if isinstance(event,Mapping) and _clean(event.get("event_id"),160)==eid
    ]
    if existing:
        if all(event.get("patch_digest")==patch_digest for event in existing):
            return row
        raise CheckpointConflict("IDEMPOTENCY_CONFLICT")
    if len(row.get("journal",[]))>=MAX_EVENTS:
        raise CheckpointMasterError("journal capacity reached")

    refs=[]
    for raw in list(evidence_refs or [])[:64]:
        text=_clean(raw,300)
        if text and text not in refs:
            refs.append(text)
    revision=current["revision"]+1
    event={
        "schema":EVENT_SCHEMA,
        "event_id":eid,
        "sequence":len(row.get("journal",[]))+1,
        "base_revision":current["revision"],
        "revision":revision,
        "event_type":"MERGE_PATCH",
        "created_at":_clean(created_at,80) or _now(),
        "patch":checked_patch,
        "patch_digest":patch_digest,
        "prev_digest":row.get("head_digest") or GENESIS,
        "evidence_refs":refs,
    }
    event["event_digest"]=_digest(_event_material(event))
    next_state=_merge_patch(current["snapshot"],checked_patch)
    next_state=_safe_structure(next_state)
    if _bytes(next_state)>MAX_BASE_BYTES:
        raise CheckpointMasterError("resulting snapshot exceeds limit")

    row.setdefault("journal",[]).append(event)
    row["revision"]=revision
    row["head_digest"]=event["event_digest"]
    row["state_digest"]=_digest(next_state)
    row["external_action_executed"]=False
    row["execution_allowed"]=False
    row["executes_provider_call"]=False
    row["executes_billing"]=False
    row["real_orders_enabled"]=False
    if _bytes(row)>MAX_MASTER_BYTES:
        raise CheckpointMasterError("checkpoint master exceeds limit")
    return row


def compact_checkpoint(master:Mapping[str,Any], *, expected_revision:Any)->dict[str,Any]:
    current=reconstruct_checkpoint(master)
    expected=_positive_int(expected_revision,"expected_revision",0)
    if expected!=current["revision"]:
        raise CheckpointConflict("REVISION_CONFLICT")
    generation=_positive_int(dict(master).get("compaction_generation",0),"compaction_generation",0)+1
    compacted=new_checkpoint_master(
        current["snapshot"],
        base_revision=current["revision"],
        created_at=dict(master).get("created_at") or _now(),
        source_refs=dict(master).get("source_refs") if isinstance(dict(master).get("source_refs"),list) else [],
        compaction_generation=generation,
    )
    compacted["compacted_from_head"]=_clean(dict(master).get("head_digest"),160)
    return compacted


def rollback_candidate(master:Mapping[str,Any], *, target_revision:Any)->dict[str,Any]:
    candidate=reconstruct_checkpoint(master,target_revision=target_revision)
    return {
        "schema":"ATLASQUANT_AION_CHECKPOINT_ROLLBACK_CANDIDATE_V23",
        "target_revision":candidate["revision"],
        "snapshot":candidate["snapshot"],
        "state_digest":candidate["state_digest"],
        "requires_explicit_approval":True,
        "automatic_rollback":False,
        "external_action_executed":False,
        "execution_allowed":False,
    }


def future_signature_hook(master:Mapping[str,Any])->dict[str,Any]:
    verified=reconstruct_checkpoint(master)
    return {
        "schema":"ATLASQUANT_AION_FUTURE_SIGNATURE_HOOK_V23",
        "digest_to_sign":checkpoint_master_digest(master),
        "state_digest":verified["state_digest"],
        "mechanism":"FIDO2_OR_PLATFORM_SIGNATURE_FUTURE",
        "active":False,
        "biometric_capture_performed":False,
        "signature_performed":False,
        "execution_allowed":False,
    }


def checkpoint_master_digest(master:Mapping[str,Any])->str:
    row=dict(master or {})
    material={
        "schema":row.get("schema"),
        "base_revision":row.get("base_revision"),
        "revision":row.get("revision"),
        "base_digest":row.get("base_digest"),
        "head_digest":row.get("head_digest"),
        "state_digest":row.get("state_digest"),
        "compaction_generation":row.get("compaction_generation"),
        "source_refs":row.get("source_refs"),
        "journal_event_digests":[
            event.get("event_digest")
            for event in row.get("journal",[])
            if isinstance(event,Mapping)
        ],
    }
    return _digest(material)


__all__=[
    "SCHEMA","EVENT_SCHEMA","GENESIS","MAX_BASE_BYTES","MAX_EVENT_BYTES",
    "MAX_EVENTS","MAX_MASTER_BYTES","CheckpointMasterError","CheckpointConflict",
    "CheckpointIntegrityError","new_checkpoint_master","reconstruct_checkpoint",
    "append_checkpoint_patch","compact_checkpoint","rollback_candidate",
    "future_signature_hook","checkpoint_master_digest",
]
