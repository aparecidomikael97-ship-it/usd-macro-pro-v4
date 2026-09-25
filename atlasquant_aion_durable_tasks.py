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

SCHEMA="ATLASQUANT_AION_DURABLE_TASKS_V1"
MAX_TASKS=300
MAX_STEPS=80
TASK_STATES=(
    "PLANNED","RUNNING","PAUSED","WAITING_APPROVAL","BLOCKED","DONE","CANCELED",
)
STEP_STATES=(
    "PENDING","READY","RUNNING","WAITING_APPROVAL","BLOCKED","DONE","SKIPPED","FAILED",
)
TERMINAL_STEP_STATES=frozenset({"DONE","SKIPPED"})


def _now()->str:
    return datetime.now(timezone.utc).isoformat()


def _clean(value:Any,limit:int=1400)->str:
    return " ".join(str(value or "").replace("\x00","").split())[:limit]


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


def normalize_step(raw:Mapping[str,Any],index:int)->dict[str,Any]:
    item=dict(raw or {})
    sid=_clean(item.get("step_id"),80) or f"S{index+1:03d}"
    state=_clean(item.get("state"),40).upper()
    if state not in STEP_STATES:
        state="PENDING"
    return {
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
    }


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
    return {
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
)->list[dict[str,Any]]:
    current=normalize_durable_tasks(rows)
    item=normalize_durable_task(task)
    for idx,row in enumerate(current):
        if row["durable_task_id"]==item["durable_task_id"]:
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
)->dict[str,Any]:
    """Update recorded state only. It does not perform the step."""
    item=normalize_durable_task(task)
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
        step["state"]=next_state
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
    if not found:
        raise ValueError("durable step not found")

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
    item["updated_at"]=changed
    return item


def pause_durable_task(
    task:Mapping[str,Any],
    *,
    next_action:Any=None,
    blocker:Any=None,
    checkpoint_digest:Any=None,
    changed_at:str|None=None,
)->dict[str,Any]:
    item=normalize_durable_task(task)
    if item["state"] not in {"DONE","CANCELED"}:
        item["state"]="BLOCKED" if blocker else "PAUSED"
    if next_action is not None:
        item["next_action"]=_clean(next_action,500)
    if blocker is not None:
        item["blocker"]=_clean(blocker)
    if checkpoint_digest is not None:
        item["checkpoint_digest"]=_clean(checkpoint_digest,100)
    item["revision"]+=1
    item["updated_at"]=str(changed_at or _now())
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
    if expected_revision is not None:
        try:
            if int(expected_revision)!=int(item["revision"]):
                blockers.append("REVISION_CONFLICT")
        except Exception:
            blockers.append("REVISION_INVALID")
    expected_digest=_clean(item.get("checkpoint_digest"),100)
    observed_digest=_clean(checkpoint_digest,100)
    if expected_digest and observed_digest and expected_digest!=observed_digest:
        blockers.append("CHECKPOINT_CHANGED")
    step=(
        deepcopy(item["steps"][item["cursor"]])
        if item["cursor"]<len(item["steps"])
        else None
    )
    return {
        "schema":SCHEMA,
        "durable_task_id":item["durable_task_id"],
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
)->dict[str,Any]:
    item=normalize_durable_task(task)
    if item["state"] in {"DONE","CANCELED"}:
        raise ValueError("terminal durable task cannot resume")
    item["resume_generation"]+=1
    item["revision"]+=1
    item["checkpoint_digest"]=_clean(checkpoint_digest,100) or item["checkpoint_digest"]
    # Resumption records continuity only. It must not clear an approval/blocker.
    if item["state"] not in {"WAITING_APPROVAL","BLOCKED"}:
        item["state"]="PAUSED"
    item["updated_at"]=str(changed_at or _now())
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
]
