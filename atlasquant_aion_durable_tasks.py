"""AION Durable Tasks contracts.

Structured resumable work state. Durable tasks preserve the exact cursor,
artifacts, evidence, blockers and next step across sessions/checkpoints.
They never turn resumption into authorization: resuming restores state only.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Mapping, Sequence
import json

from atlasquant_aion_core import guardian_decision
from atlasquant_aion_observability import append_event, new_event, normalize_events, redact_text

SCHEMA="ATLASQUANT_AION_DURABLE_TASKS_V1"
MAX_TASKS=300
MAX_STEPS=80
MAX_IDEMPOTENCY_KEYS=32
MAX_IDEMPOTENCY_KEY_LENGTH=128
TASK_STATES=(
    "PLANNED","RUNNING","PAUSED","WAITING_APPROVAL","BLOCKED","DONE","CANCELED",
)
STEP_STATES=(
    "PENDING","READY","RUNNING","WAITING_APPROVAL","BLOCKED","DONE","SKIPPED","FAILED",
)
TERMINAL_STEP_STATES=frozenset({"DONE","SKIPPED"})
TERMINAL_TASK_STATES=frozenset({"DONE","CANCELED"})
# PLANNED may be paused/blocked while preparing work; resumption never runs it.
TASK_TRANSITIONS={
    "PLANNED": {"RUNNING","PAUSED","WAITING_APPROVAL","BLOCKED","CANCELED"},
    "RUNNING": {"PAUSED","WAITING_APPROVAL","BLOCKED","DONE","CANCELED"},
    "PAUSED": {"RUNNING","WAITING_APPROVAL","BLOCKED","CANCELED"},
    "WAITING_APPROVAL": {"RUNNING","BLOCKED","CANCELED"},
    "BLOCKED": {"PAUSED","RUNNING","CANCELED"},
    "DONE": set(), "CANCELED": set(),
}
STEP_TRANSITIONS={
    "PENDING": {"READY","RUNNING","WAITING_APPROVAL","BLOCKED","SKIPPED"},
    "READY": {"RUNNING","WAITING_APPROVAL","BLOCKED","SKIPPED"},
    "RUNNING": {"WAITING_APPROVAL","BLOCKED","DONE","FAILED"},
    "WAITING_APPROVAL": {"READY","RUNNING","BLOCKED"},
    "BLOCKED": {"READY","RUNNING"},
    "FAILED": {"RUNNING"},
    "DONE": set(), "SKIPPED": set(),
}


def _exact_true(value:Any)->bool:
    return value is True


class DurableTaskError(ValueError):
    """Compatible ValueError carrying a structured, non-secret failure result."""
    def __init__(self, code:str, task:Mapping[str,Any]|None=None):
        super().__init__(code)
        item=dict(task or {})
        self.result={"status":"CONFLICT" if code.startswith("REVISION") else "BLOCKED",
                     "error_code":code,"task_id":item.get("durable_task_id",""),
                     "correlation_id":item.get("correlation_id",""),"executes_action":False}


def validate_transition(previous:str, target:str, *, step:bool=False,
                        unblock_reason:Any="", approved:bool=False, retry:bool=False)->None:
    policy=STEP_TRANSITIONS if step else TASK_TRANSITIONS
    if previous not in policy or target not in policy:
        raise DurableTaskError("INVALID_STATE")
    if previous==target:
        return
    if target not in policy[previous]:
        raise DurableTaskError("INVALID_TRANSITION")
    if previous=="BLOCKED" and target!="CANCELED" and not _clean(unblock_reason):
        raise DurableTaskError("UNBLOCK_REQUIRED")
    if previous=="WAITING_APPROVAL" and target in {"READY","RUNNING"} and not _exact_true(approved):
        raise DurableTaskError("APPROVAL_REQUIRED")
    if previous=="FAILED" and not retry:
        raise DurableTaskError("RETRY_REQUIRED")


def _check_revision(item:Mapping[str,Any], expected_revision:Any)->None:
    if expected_revision is None:
        return  # Legacy callers retain their pure/offline API.
    if isinstance(expected_revision,bool) or not str(expected_revision).isdigit():
        raise DurableTaskError("REVISION_INVALID",item)
    if int(expected_revision)!=item["revision"]:
        raise DurableTaskError("REVISION_CONFLICT",item)


def _audit(item:dict[str,Any], event_type:str, previous:str, changed:str, **metadata:Any)->None:
    correlation=item.setdefault("correlation_id",item["mission_id"] or item["durable_task_id"])
    event=new_event(event_type,event_type,created_at=changed,source="AION_DURABLE_TASK",
                    evidence={"task_id":item["durable_task_id"],"mission_id":item["mission_id"],
                              "correlation_id":correlation,"previous_state":previous,
                              "new_state":item["state"],"action":event_type,"result":"RECORDED",
                              "revision":item["revision"],"metadata":metadata})
    item["audit_events"]=append_event(item.get("audit_events",[]),event)


def _guard_step(step:Mapping[str,Any], access:Mapping[str,Any]|None, approved:bool)->None:
    approved_exact=_exact_true(approved)
    decision=guardian_decision(step["guardian_action"],access,approved=approved_exact)
    if not decision["allowed"]:
        raise DurableTaskError("GUARDIAN_DENIED")
    if (step["requires_approval"] or step["external_side_effects"]) and not approved_exact:
        raise DurableTaskError("APPROVAL_REQUIRED")


def _now()->str:
    return datetime.now(timezone.utc).isoformat()


def _clean(value:Any,limit:int=1400)->str:
    return " ".join(redact_text(value).replace("\x00","").split())[:limit]


def _refs(values:Sequence[Any]|None,limit:int=50)->list[str]:
    out=[]
    for raw in list(values or [])[:limit*2]:
        text=_clean(raw,240)
        if text and text not in out:
            out.append(text)
        if len(out)>=limit:
            break
    return out


def _int(value:Any,default:int=0,minimum:int=0,maximum:int=1_000_000)->int:
    try:
        parsed=int(value)
    except Exception:
        parsed=int(default)
    return max(minimum,min(maximum,parsed))


def _digest(value:Any)->str:
    raw=json.dumps(value,ensure_ascii=False,sort_keys=True,default=str)
    return sha256(raw.encode("utf-8")).hexdigest()[:24]


def _task_id(title:str,created_at:str)->str:
    return "DUR-"+_digest({"title":title,"created_at":created_at})[:14].upper()


def _retry_key(value:Any)->str:
    text=" ".join(str(value or "").replace("\x00","").split())
    if not text:
        return ""
    if len(text)>MAX_IDEMPOTENCY_KEY_LENGTH:
        raise DurableTaskError("IDEMPOTENCY_KEY_INVALID")
    return text


def _consumed_keys(raw:Mapping[str,Any])->list[str]:
    rows=raw.get("consumed_idempotency_keys")
    out=[]
    if isinstance(rows,(list,tuple)):
        source=list(rows)[:MAX_IDEMPOTENCY_KEYS]
    else:
        source=[]
    for item in source:
        text=" ".join(str(item or "").replace("\x00","").split())
        if text and len(text)<=MAX_IDEMPOTENCY_KEY_LENGTH and text not in out:
            out.append(text)
    legacy=" ".join(str(raw.get("idempotency_key") or "").replace("\x00","").split())
    if legacy and len(legacy)<=MAX_IDEMPOTENCY_KEY_LENGTH and legacy not in out and len(out)<MAX_IDEMPOTENCY_KEYS:
        out.append(legacy)
    return out


def normalize_step(raw:Mapping[str,Any],index:int)->dict[str,Any]:
    item=dict(raw or {})
    sid=_clean(item.get("step_id"),80) or f"S{index+1:03d}"
    state=_clean(item.get("state"),40).upper()
    if state not in STEP_STATES:
        state="PENDING"
    result={
        "step_id":sid,
        "title":_clean(item.get("title"),300) or f"Passo {index+1}",
        "state":state,
        "tool_id":_clean(item.get("tool_id"),120).lower(),
        "guardian_action":_clean(item.get("guardian_action"),80).lower() or "read",
        "requires_approval":bool(item.get("requires_approval",False)),
        "external_side_effects":bool(item.get("external_side_effects",False)),
        "input_refs":_refs(
            item.get("input_refs") if isinstance(item.get("input_refs"),(list,tuple)) else []
        ),
        "artifact_refs":_refs(
            item.get("artifact_refs") if isinstance(item.get("artifact_refs"),(list,tuple)) else []
        ),
        "evidence_refs":_refs(
            item.get("evidence_refs") if isinstance(item.get("evidence_refs"),(list,tuple)) else []
        ),
        "result_note":_clean(item.get("result_note")),
        "blocker":_clean(item.get("blocker")),
        "attempts":_int(item.get("attempts"),0,0,1000),
        "started_at":_clean(item.get("started_at"),80),
        "completed_at":_clean(item.get("completed_at"),80),
        "executes_action":False,
        "consumed_idempotency_keys":_consumed_keys(item),
    }
    result["idempotency_key"]=result["consumed_idempotency_keys"][-1] if result["consumed_idempotency_keys"] else ""
    for key in ("correlation_id","last_error"):
        if key in item:
            result[key]=_clean(item[key])
    if "max_attempts" in item:
        result["max_attempts"]=_int(item["max_attempts"],3,1,1000)
    return result


def normalize_steps(rows:Sequence[Mapping[str,Any]]|None)->list[dict[str,Any]]:
    out=[]
    seen=set()
    for index,raw in enumerate(list(rows or [])[:MAX_STEPS]):
        if not isinstance(raw,Mapping):
            continue
        item=normalize_step(raw,index)
        if item["step_id"] in seen:
            continue
        seen.add(item["step_id"])
        out.append(item)
    return out


def new_durable_task(
    title:Any,
    *,
    objective:Any="",
    domain:Any="development",
    mission_id:Any="",
    steps:Sequence[Mapping[str,Any]]|None=None,
    checkpoint_digest:Any="",
    created_at:str|None=None,
    source:Any="ADMIN",
)->dict[str,Any]:
    title_clean=_clean(title,300)
    if not title_clean:
        raise ValueError("durable task title required")
    created=str(created_at or _now())
    step_rows=normalize_steps(steps)
    item={
        "schema":SCHEMA,
        "durable_task_id":_task_id(title_clean,created),
        "title":title_clean,
        "objective":_clean(objective),
        "domain":_clean(domain,80).lower() or "development",
        "mission_id":_clean(mission_id,80),
        "state":"PLANNED",
        "steps":step_rows,
        "cursor":0,
        "revision":1,
        "resume_generation":0,
        "checkpoint_digest":_clean(checkpoint_digest,100),
        "artifacts":[],
        "evidence_refs":[],
        "blocker":"",
        "next_action":step_rows[0]["title"] if step_rows else "",
        "created_at":created,
        "updated_at":created,
        "source":_clean(source,100) or "ADMIN",
        "automatic_resume_executes":False,
        "real_trading_enabled":False,
    }
    _audit(item,"TASK_CREATED","",created)
    for step in item["steps"]:
        step["correlation_id"]=item["correlation_id"]
    return item


def normalize_durable_task(raw:Mapping[str,Any])->dict[str,Any]:
    item=dict(raw or {})
    title=_clean(item.get("title"),300)
    if not title:
        raise ValueError("durable task title required")
    created=_clean(item.get("created_at"),80) or _now()
    base=new_durable_task(
        title,
        objective=item.get("objective"),
        domain=item.get("domain"),
        mission_id=item.get("mission_id"),
        steps=item.get("steps") if isinstance(item.get("steps"),(list,tuple)) else [],
        checkpoint_digest=item.get("checkpoint_digest"),
        created_at=created,
        source=item.get("source") or "ADMIN",
    )
    supplied=_clean(item.get("durable_task_id"),80)
    if supplied:
        base["durable_task_id"]=supplied
    # Do not invent fields when reading legacy V17 records: keep their digests.
    base["steps"]=normalize_steps(item.get("steps",[]))
    for key in ("correlation_id","canceled_at"):
        if key in item:
            base[key]=_clean(item[key])
        else:
            base.pop(key,None)
    if "audit_events" in item:
        base["audit_events"]=normalize_events(item["audit_events"])
    else:
        base.pop("audit_events",None)
    state=_clean(item.get("state"),40).upper()
    base["state"]=state if state in TASK_STATES else "PLANNED"
    steps=base["steps"]
    cursor=_int(item.get("cursor"),0,0,len(steps))
    base["cursor"]=cursor
    base["revision"]=_int(item.get("revision"),1,1,1_000_000)
    base["resume_generation"]=_int(item.get("resume_generation"),0,0,1_000_000)
    base["artifacts"]=_refs(
        item.get("artifacts") if isinstance(item.get("artifacts"),(list,tuple)) else []
    )
    base["evidence_refs"]=_refs(
        item.get("evidence_refs") if isinstance(item.get("evidence_refs"),(list,tuple)) else []
    )
    base["blocker"]=_clean(item.get("blocker"))
    base["next_action"]=_clean(item.get("next_action"),500)
    base["updated_at"]=_clean(item.get("updated_at"),80) or created
    return base


def normalize_durable_tasks(rows:Sequence[Mapping[str,Any]]|None)->list[dict[str,Any]]:
    out=[]
    seen=set()
    for raw in list(rows or [])[-MAX_TASKS*2:]:
        if not isinstance(raw,Mapping):
            continue
        try:
            item=normalize_durable_task(raw)
        except Exception:
            continue
        did=item["durable_task_id"]
        if did in seen:
            continue
        seen.add(did)
        out.append(item)
    return out[-MAX_TASKS:]


def upsert_durable_task(
    rows:Sequence[Mapping[str,Any]]|None,
    task:Mapping[str,Any],
    *, expected_revision:Any=None,
)->list[dict[str,Any]]:
    current=normalize_durable_tasks(rows)
    item=normalize_durable_task(task)
    for idx,row in enumerate(current):
        if row["durable_task_id"]==item["durable_task_id"]:
            _check_revision(row,expected_revision)
            if item==row:
                return current
            if item["revision"]<=row["revision"]:
                raise DurableTaskError("REVISION_CONFLICT",row)
            if row["state"] in TERMINAL_TASK_STATES and item["state"]!=row["state"]:
                raise DurableTaskError("TASK_TERMINAL",row)
            current[idx]=item
            return current
    if len(current)>=MAX_TASKS:
        raise ValueError("durable task capacity reached")
    current.append(item)
    return current


def update_step(
    task:Mapping[str,Any],
    step_id:Any,
    state:Any,
    *,
    result_note:Any=None,
    blocker:Any=None,
    artifact_refs:Sequence[Any]|None=None,
    evidence_refs:Sequence[Any]|None=None,
    changed_at:str|None=None,
    expected_revision:Any=None,
    access:Mapping[str,Any]|None=None,
    approved:bool=False,
    unblock_reason:Any="",
    retry:bool=False,
    idempotency_key:Any="",
)->dict[str,Any]:
    """Update recorded state only. It does not perform the step."""
    item=normalize_durable_task(task)
    _check_revision(item,expected_revision)
    if item["state"] in TERMINAL_TASK_STATES:
        raise DurableTaskError("TASK_TERMINAL",item)
    previous_task_state=item["state"]
    original_cursor=item["cursor"]
    target=_clean(step_id,80)
    next_state=_clean(state,40).upper()
    if next_state not in STEP_STATES:
        raise ValueError("invalid durable step state")
    changed=str(changed_at or _now())
    found=False
    for step in item["steps"]:
        if step["step_id"]!=target:
            continue
        found=True
        previous=step["state"]
        validate_transition(previous,next_state,step=True,unblock_reason=unblock_reason,
                            approved=approved,retry=retry)
        if retry:
            key=_retry_key(idempotency_key)
            consumed=list(step.get("consumed_idempotency_keys") or [])
            if not key:
                raise DurableTaskError("IDEMPOTENCY_KEY_REQUIRED",item)
            if key in consumed:
                return item
            if previous==next_state:
                raise DurableTaskError("IDEMPOTENCY_CONFLICT",item)
            if previous!="FAILED" or next_state!="RUNNING":
                raise DurableTaskError("RETRY_INVALID",item)
            if step["external_side_effects"] or step["guardian_action"] not in {"read","search","summarize","draft"}:
                raise DurableTaskError("RETRY_UNSAFE",item)
            if step["attempts"]>=step.get("max_attempts",3):
                raise DurableTaskError("RETRY_LIMIT",item)
            if len(consumed)>=MAX_IDEMPOTENCY_KEYS:
                raise DurableTaskError("IDEMPOTENCY_HISTORY_FULL",item)
            step["consumed_idempotency_keys"]=consumed+[key]
            step["idempotency_key"]=key
        elif previous==next_state:
            return item
        if next_state in {"RUNNING","DONE","SKIPPED"}:
            if item["cursor"]>=len(item["steps"]) or step is not item["steps"][item["cursor"]]:
                raise DurableTaskError("STEP_OUT_OF_ORDER",item)
            if item["state"]=="BLOCKED" and not _clean(unblock_reason):
                raise DurableTaskError("UNBLOCK_REQUIRED",item)
            if item["state"]=="WAITING_APPROVAL" and not _exact_true(approved):
                raise DurableTaskError("APPROVAL_REQUIRED",item)
            if next_state in {"RUNNING","DONE"}:
                _guard_step(step,access,approved)
        step["state"]=next_state
        step["correlation_id"]=item.get("correlation_id") or item["mission_id"] or item["durable_task_id"]
        if next_state=="FAILED":
            step["last_error"]=_clean(blocker or result_note or "STEP_FAILED")
        if next_state=="RUNNING":
            step["attempts"]+=1
            if not step["started_at"]:
                step["started_at"]=changed
        if next_state in TERMINAL_STEP_STATES:
            step["completed_at"]=changed
        elif next_state not in TERMINAL_STEP_STATES:
            step["completed_at"]=""
        if result_note is not None:
            step["result_note"]=_clean(result_note)
        if blocker is not None:
            step["blocker"]=_clean(blocker)
        if artifact_refs is not None:
            step["artifact_refs"]=_refs(artifact_refs)
        if evidence_refs is not None:
            step["evidence_refs"]=_refs(evidence_refs)
        if next_state not in {"BLOCKED","FAILED"} and blocker is None:
            step["blocker"]=""
        if previous!=next_state:
            item["revision"]+=1
        _audit(item,"STEP_RETRIED" if retry else "STEP_STATE_CHANGED",previous_task_state,
               changed,step_id=step["step_id"],previous_state=previous,new_state=next_state,
               attempts=step["attempts"],error_code=step.get("last_error", ""))
    if not found:
        raise ValueError("durable step not found")

    # Annotating a future step cannot release the current task's suspension.
    if original_cursor<len(item["steps"]) and item["steps"][original_cursor]["step_id"]!=target:
        item["updated_at"]=changed
        return item

    cursor=0
    while cursor<len(item["steps"]) and item["steps"][cursor]["state"] in TERMINAL_STEP_STATES:
        cursor+=1
    item["cursor"]=cursor
    if cursor>=len(item["steps"]):
        item["state"]="DONE"
        item["next_action"]=""
        item["blocker"]=""
    else:
        current=item["steps"][cursor]
        if current["state"]=="WAITING_APPROVAL":
            item["state"]="WAITING_APPROVAL"
            item["blocker"]=current["blocker"]
        elif current["state"] in {"BLOCKED","FAILED"}:
            item["state"]="BLOCKED"
            item["blocker"]=current["blocker"]
        elif current["state"]=="RUNNING":
            item["state"]="RUNNING"
            item["blocker"]=""
        else:
            item["state"]="PAUSED"
            item["blocker"]=""
        item["next_action"]=current["title"]
    if previous_task_state in {"WAITING_APPROVAL","BLOCKED"} and next_state not in {"RUNNING","DONE"}:
        item["state"]=previous_task_state
        item["blocker"]=_clean(task.get("blocker"))
    item["updated_at"]=changed
    event_type={"RUNNING":"TASK_STARTED","DONE":"TASK_COMPLETED",
                "WAITING_APPROVAL":"TASK_WAITING_APPROVAL","BLOCKED":"TASK_BLOCKED",
                "PAUSED":"TASK_PAUSED"}.get(item["state"],"TASK_UPDATED")
    if next_state=="FAILED":
        event_type="TASK_FAILED"
    _audit(item,event_type,previous_task_state,changed,step_id=target)
    return item


def transition_durable_task(task:Mapping[str,Any], state:Any, *,
                            expected_revision:Any=None, access:Mapping[str,Any]|None=None,
                            approved:bool=False, unblock_reason:Any="",
                            changed_at:str|None=None)->dict[str,Any]:
    item=normalize_durable_task(task)
    _check_revision(item,expected_revision)
    previous=item["state"]
    target=_clean(state,40).upper()
    validate_transition(previous,target,unblock_reason=unblock_reason,approved=approved)
    if previous==target:
        return item
    current=item["steps"][item["cursor"]] if item["cursor"]<len(item["steps"]) else None
    if target=="RUNNING":
        if current and current["state"] in {"BLOCKED","FAILED","WAITING_APPROVAL"}:
            raise DurableTaskError("STEP_REQUIRES_TRANSITION",item)
        _guard_step(current or {"guardian_action":"read","requires_approval":False,
                               "external_side_effects":False},access,approved)
    if target=="DONE" and any(s["state"] not in TERMINAL_STEP_STATES for s in item["steps"]):
        raise DurableTaskError("STEPS_INCOMPLETE",item)
    changed=str(changed_at or _now())
    item["state"]=target
    item["revision"]+=1
    item["updated_at"]=changed
    if previous=="BLOCKED" and target in {"RUNNING","PAUSED"}:
        item["blocker"]=""
    if target in TERMINAL_TASK_STATES:
        item["next_action"]=""
    if target=="CANCELED":
        item["canceled_at"]=changed
    event_type={"RUNNING":"TASK_STARTED","PAUSED":"TASK_PAUSED",
                "WAITING_APPROVAL":"TASK_WAITING_APPROVAL","BLOCKED":"TASK_BLOCKED",
                "DONE":"TASK_COMPLETED","CANCELED":"TASK_CANCELED"}[target]
    _audit(item,event_type,previous,changed,unblock_reason=_clean(unblock_reason))
    return item


def cancel_durable_task(task:Mapping[str,Any], *, expected_revision:Any=None,
                        changed_at:str|None=None)->dict[str,Any]:
    """Cancel the record, preserving steps, artifacts, evidence and history."""
    return transition_durable_task(task,"CANCELED",expected_revision=expected_revision,
                                   changed_at=changed_at)


def retry_step(task:Mapping[str,Any], step_id:Any, *, expected_revision:Any=None,
               access:Mapping[str,Any]|None=None, approved:bool=False,
               idempotency_key:Any="", changed_at:str|None=None)->dict[str,Any]:
    return update_step(task,step_id,"RUNNING",expected_revision=expected_revision,
                       access=access,approved=approved,retry=True,
                       unblock_reason="Explicit retry of failed local step",
                       idempotency_key=idempotency_key,changed_at=changed_at)


def pause_durable_task(
    task:Mapping[str,Any],
    *,
    next_action:Any=None,
    blocker:Any=None,
    checkpoint_digest:Any=None,
    changed_at:str|None=None,
    expected_revision:Any=None,
)->dict[str,Any]:
    item=normalize_durable_task(task)
    _check_revision(item,expected_revision)
    previous=item["state"]
    if previous in TERMINAL_TASK_STATES:
        raise DurableTaskError("TASK_TERMINAL",item)
    # Pause does not release either an approval or an unresolved blocker.
    target=previous if previous in {"WAITING_APPROVAL","BLOCKED"} else "BLOCKED" if blocker else "PAUSED"
    validate_transition(previous,target)
    item["state"]=target
    if next_action is not None:
        item["next_action"]=_clean(next_action,500)
    if blocker is not None and (blocker or previous not in {"WAITING_APPROVAL","BLOCKED"}):
        item["blocker"]=_clean(blocker)
    if checkpoint_digest is not None:
        item["checkpoint_digest"]=_clean(checkpoint_digest,100)
    item["revision"]+=1
    item["updated_at"]=str(changed_at or _now())
    _audit(item,"TASK_PAUSED" if target=="PAUSED" else "TASK_"+target,previous,item["updated_at"])
    return item


def prepare_resume(
    task:Mapping[str,Any],
    *,
    expected_revision:Any=None,
    checkpoint_digest:Any="",
)->dict[str,Any]:
    """Restore cursor/context only. Resume never performs the next step."""
    item=normalize_durable_task(task)
    blockers=[]
    if item["state"] in {"DONE","CANCELED"}:
        blockers.append("TASK_TERMINAL")
    try:
        _check_revision(item,expected_revision)
    except DurableTaskError as exc:
        blockers.append(exc.result["error_code"])
    expected_digest=_clean(item.get("checkpoint_digest"),100)
    observed_digest=_clean(checkpoint_digest,100)
    if expected_digest and not observed_digest:
        blockers.append("CHECKPOINT_REQUIRED")
    elif expected_digest and expected_digest!=observed_digest:
        blockers.append("CHECKPOINT_CHANGED")
    step=(
        deepcopy(item["steps"][item["cursor"]])
        if item["cursor"]<len(item["steps"])
        else None
    )
    return {
        "schema":SCHEMA,
        "durable_task_id":item["durable_task_id"],
        "mission_id":item["mission_id"],
        "correlation_id":item.get("correlation_id") or item["mission_id"] or item["durable_task_id"],
        "checkpoint_digest":item["checkpoint_digest"],
        "resume_generation":item["resume_generation"],
        "task_blocker":item["blocker"],
        "approval_pending":item["state"]=="WAITING_APPROVAL" or bool(step and step["requires_approval"]),
        "state":"BLOCK" if blockers else "RESUME_READY",
        "task_state":item["state"],
        "revision":item["revision"],
        "cursor":item["cursor"],
        "next_step":step,
        "next_action":item["next_action"],
        "artifacts":deepcopy(item["artifacts"]),
        "evidence_refs":deepcopy(item["evidence_refs"]),
        "blockers":blockers,
        "restores_state_only":True,
        "executes_action":False,
        "real_trading_enabled":False,
    }


def record_resume(
    task:Mapping[str,Any],
    *,
    checkpoint_digest:Any="",
    changed_at:str|None=None,
    expected_revision:Any=None,
)->dict[str,Any]:
    item=normalize_durable_task(task)
    view=prepare_resume(item,expected_revision=expected_revision,checkpoint_digest=checkpoint_digest)
    if view["state"]=="BLOCK":
        raise DurableTaskError(view["blockers"][0],item)
    previous=item["state"]
    item["resume_generation"]+=1
    item["revision"]+=1
    item["checkpoint_digest"]=_clean(checkpoint_digest,100) or item["checkpoint_digest"]
    # Resumption records continuity only. It must not clear an approval/blocker.
    if item["state"] not in {"WAITING_APPROVAL","BLOCKED"}:
        item["state"]="PAUSED"
    item["updated_at"]=str(changed_at or _now())
    _audit(item,"TASK_RESUMED",previous,item["updated_at"],resume_generation=item["resume_generation"])
    return item


def durable_tasks_digest(rows:Sequence[Mapping[str,Any]]|None)->str:
    return _digest(normalize_durable_tasks(rows))


def durable_tasks_summary(rows:Sequence[Mapping[str,Any]]|None)->dict[str,Any]:
    tasks=normalize_durable_tasks(rows)
    by_state={state:0 for state in TASK_STATES}
    for item in tasks:
        by_state[item["state"]]+=1
    resumable=[
        x for x in tasks
        if x["state"] not in {"DONE","CANCELED"}
    ]
    resumable.sort(key=lambda x:str(x.get("updated_at") or ""),reverse=True)
    return {
        "schema":SCHEMA,
        "tasks":len(tasks),
        "resumable":len(resumable),
        "waiting_approval":by_state["WAITING_APPROVAL"],
        "blocked":by_state["BLOCKED"],
        "done":by_state["DONE"],
        "by_state":by_state,
        "next_resumable":deepcopy(resumable[0]) if resumable else None,
        "automatic_resume_executes":False,
        "real_trading_enabled":False,
        "digest":durable_tasks_digest(tasks),
    }


__all__=[
    "SCHEMA","TASK_STATES","STEP_STATES",
    "new_durable_task","normalize_durable_task","normalize_durable_tasks",
    "upsert_durable_task","update_step","pause_durable_task","prepare_resume",
    "record_resume","durable_tasks_digest","durable_tasks_summary",
    "transition_durable_task","cancel_durable_task","retry_step","DurableTaskError",
    "validate_transition",
]
