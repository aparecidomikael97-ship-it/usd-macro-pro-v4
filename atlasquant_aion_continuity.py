"""AION persistent mission continuity and session handoff contracts.

Pure/offline. This module stores structured mission history and handoff snapshots
inside the Checkpoint Mestre. It never executes the mission itself, never calls
external services, and never turns a recorded next step into authorization.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence
import hashlib
import json

SCHEMA="ATLASQUANT_AION_CONTINUITY_V1"
MAX_MISSIONS=240
MAX_HANDOFFS=120
MAX_TEXT=1600
MISSION_STATUSES=(
    "PLANNED","IN_PROGRESS","WAITING_APPROVAL","BLOCKED","DONE","CANCELED",
)
ACTIVE_STATUSES=frozenset({"PLANNED","IN_PROGRESS","WAITING_APPROVAL","BLOCKED"})


def _now()->str:
    return datetime.now(timezone.utc).isoformat()


def _clean(value:Any,limit:int=MAX_TEXT)->str:
    return " ".join(str(value or "").replace("\x00","").split())[:limit]


def _status(value:Any)->str:
    raw=str(value or "PLANNED").strip().upper()
    return raw if raw in MISSION_STATUSES else "PLANNED"


def _domain(value:Any)->str:
    raw=_clean(value,80).casefold()
    return raw or "central"


def _mission_id(title:str,domain:str,created_at:str)->str:
    seed=f"{domain}|{title}|{created_at}".encode("utf-8")
    return "MIS-"+hashlib.sha256(seed).hexdigest()[:12].upper()


def _handoff_id(created_at:str,digest:str)->str:
    seed=f"{created_at}|{digest}".encode("utf-8")
    return "HOF-"+hashlib.sha256(seed).hexdigest()[:12].upper()


def _refs(values:Sequence[Any]|None,*,limit:int=24)->list[str]:
    out=[]
    for value in list(values or [])[:limit*2]:
        item=_clean(value,180)
        if item and item not in out:
            out.append(item)
        if len(out)>=limit:
            break
    return out


def new_mission(
    title:Any,
    *,
    domain:Any="development",
    objective:Any="",
    next_action:Any="",
    created_at:str|None=None,
    source:Any="ADMIN",
)->dict[str,Any]:
    title_clean=_clean(title,240)
    if not title_clean:
        raise ValueError("mission title required")
    created=str(created_at or _now())
    domain_clean=_domain(domain)
    return {
        "schema":SCHEMA,
        "mission_id":_mission_id(title_clean,domain_clean,created),
        "title":title_clean,
        "domain":domain_clean,
        "status":"PLANNED",
        "objective":_clean(objective),
        "outcome":"",
        "blocker":"",
        "next_action":_clean(next_action),
        "evidence_refs":[],
        "created_at":created,
        "updated_at":created,
        "started_at":"",
        "completed_at":"",
        "source":_clean(source,80) or "ADMIN",
        "executes_action":False,
    }


def normalize_mission(raw:Mapping[str,Any])->dict[str,Any]:
    if not isinstance(raw,Mapping):
        raise ValueError("invalid mission")
    title=_clean(raw.get("title"),240)
    if not title:
        raise ValueError("mission title required")
    created=str(raw.get("created_at") or _now())
    item=new_mission(
        title,
        domain=raw.get("domain"),
        objective=raw.get("objective"),
        next_action=raw.get("next_action"),
        created_at=created,
        source=raw.get("source") or "ADMIN",
    )
    supplied=_clean(raw.get("mission_id"),64)
    if supplied:
        item["mission_id"]=supplied
    item["status"]=_status(raw.get("status"))
    item["outcome"]=_clean(raw.get("outcome"))
    item["blocker"]=_clean(raw.get("blocker"))
    item["evidence_refs"]=_refs(raw.get("evidence_refs") if isinstance(raw.get("evidence_refs"),(list,tuple)) else [])
    item["updated_at"]=str(raw.get("updated_at") or created)
    item["started_at"]=str(raw.get("started_at") or "")[:80]
    item["completed_at"]=str(raw.get("completed_at") or "")[:80]
    return item


def normalize_missions(rows:Sequence[Mapping[str,Any]]|None)->list[dict[str,Any]]:
    out=[]
    seen=set()
    for raw in list(rows or [])[-MAX_MISSIONS*2:]:
        try:
            item=normalize_mission(raw)
        except Exception:
            continue
        mid=item["mission_id"]
        if mid in seen:
            continue
        seen.add(mid)
        out.append(item)
    return out[-MAX_MISSIONS:]


def upsert_mission(
    missions:Sequence[Mapping[str,Any]]|None,
    mission:Mapping[str,Any],
)->list[dict[str,Any]]:
    rows=normalize_missions(missions)
    item=normalize_mission(mission)
    for idx,current in enumerate(rows):
        if current["mission_id"]==item["mission_id"]:
            rows[idx]=item
            return rows
    if len(rows)>=MAX_MISSIONS:
        raise ValueError("mission capacity reached")
    rows.append(item)
    return rows


def transition_mission(
    missions:Sequence[Mapping[str,Any]]|None,
    mission_id:Any,
    status:Any,
    *,
    outcome:Any=None,
    blocker:Any=None,
    next_action:Any=None,
    evidence_refs:Sequence[Any]|None=None,
    changed_at:str|None=None,
)->list[dict[str,Any]]:
    rows=normalize_missions(missions)
    target=_clean(mission_id,64)
    next_status=_status(status)
    changed=str(changed_at or _now())
    found=False
    for item in rows:
        if item["mission_id"]!=target:
            continue
        found=True
        previous=item["status"]
        item["status"]=next_status
        if previous=="PLANNED" and next_status=="IN_PROGRESS" and not item["started_at"]:
            item["started_at"]=changed
        if next_status=="DONE":
            item["completed_at"]=changed
            if not item["started_at"]:
                item["started_at"]=changed
        elif next_status not in {"DONE","CANCELED"}:
            item["completed_at"]=""
        if outcome is not None:
            item["outcome"]=_clean(outcome)
        if blocker is not None:
            item["blocker"]=_clean(blocker)
        if next_action is not None:
            item["next_action"]=_clean(next_action)
        if evidence_refs is not None:
            item["evidence_refs"]=_refs(evidence_refs)
        if next_status!="BLOCKED" and blocker is None:
            # Do not preserve a stale blocker after a deliberate non-blocked transition.
            item["blocker"]=""
        item["updated_at"]=changed
    if not found:
        raise ValueError("mission not found")
    return rows


def _handoff_list(values:Sequence[Any]|None,limit:int=12)->list[str]:
    return _refs(values,limit=limit)


def normalize_handoff(raw:Mapping[str,Any])->dict[str,Any]:
    if not isinstance(raw,Mapping):
        raise ValueError("invalid handoff")
    created=str(raw.get("created_at") or _now())
    focus=_clean(raw.get("current_focus"),400)
    completed=_handoff_list(raw.get("completed") if isinstance(raw.get("completed"),(list,tuple)) else [])
    blockers=_handoff_list(raw.get("blockers") if isinstance(raw.get("blockers"),(list,tuple)) else [])
    next_steps=_handoff_list(raw.get("next_steps") if isinstance(raw.get("next_steps"),(list,tuple)) else [])
    evidence=_handoff_list(raw.get("evidence_refs") if isinstance(raw.get("evidence_refs"),(list,tuple)) else [],20)
    digest=_clean(raw.get("checkpoint_digest"),80)
    hid=_clean(raw.get("handoff_id"),64) or _handoff_id(created,digest)
    return {
        "schema":SCHEMA,
        "handoff_id":hid,
        "created_at":created,
        "current_focus":focus,
        "completed":completed,
        "blockers":blockers,
        "next_steps":next_steps,
        "evidence_refs":evidence,
        "checkpoint_digest":digest,
        "source":_clean(raw.get("source"),80) or "AION",
        "executes_action":False,
    }


def normalize_handoffs(rows:Sequence[Mapping[str,Any]]|None)->list[dict[str,Any]]:
    out=[]
    seen=set()
    for raw in list(rows or [])[-MAX_HANDOFFS*2:]:
        try:
            item=normalize_handoff(raw)
        except Exception:
            continue
        hid=item["handoff_id"]
        if hid in seen:
            continue
        seen.add(hid)
        out.append(item)
    return out[-MAX_HANDOFFS:]


def build_session_handoff(
    missions:Sequence[Mapping[str,Any]]|None,
    *,
    tasks:Sequence[Mapping[str,Any]]|None=None,
    events:Sequence[Mapping[str,Any]]|None=None,
    checkpoint_digest:Any="",
    created_at:str|None=None,
    source:Any="AION",
)->dict[str,Any]:
    """Synthesize a truthful handoff from already recorded Checkpoint state."""
    rows=normalize_missions(missions)
    active=[x for x in rows if x["status"] in ACTIVE_STATUSES]
    active.sort(key=lambda x:(
        0 if x["status"]=="IN_PROGRESS" else
        1 if x["status"]=="WAITING_APPROVAL" else
        2 if x["status"]=="BLOCKED" else 3,
        str(x["updated_at"]),
    ))
    done=[x for x in rows if x["status"]=="DONE"]
    done.sort(key=lambda x:str(x.get("completed_at") or x.get("updated_at") or ""),reverse=True)
    blocked=[x for x in rows if x["status"]=="BLOCKED"]

    focus=active[0]["title"] if active else ""
    completed=[x["title"] for x in done[:8]]
    blockers=[
        f"{x['title']}: {x['blocker']}" if x.get("blocker") else x["title"]
        for x in blocked[:8]
    ]
    next_steps=[]
    for item in active:
        step=_clean(item.get("next_action"),300)
        if step and step not in next_steps:
            next_steps.append(step)
        if len(next_steps)>=8:
            break

    # Fall back to active task titles only when no mission next step exists.
    if not next_steps:
        for task in list(tasks or [])[:50]:
            if not isinstance(task,Mapping):
                continue
            if str(task.get("status") or "").upper() not in {"TODO","IN_PROGRESS","WAITING_APPROVAL","BLOCKED"}:
                continue
            title=_clean(task.get("title"),300)
            if title and title not in next_steps:
                next_steps.append(title)
            if len(next_steps)>=8:
                break

    evidence=[]
    for event in list(events or [])[-30:]:
        if not isinstance(event,Mapping):
            continue
        eid=_clean(event.get("event_id"),80)
        if eid and eid not in evidence:
            evidence.append(eid)
        if len(evidence)>=12:
            break

    created=str(created_at or _now())
    digest=_clean(checkpoint_digest,80)
    payload={
        "schema":SCHEMA,
        "handoff_id":_handoff_id(created,digest),
        "created_at":created,
        "current_focus":focus,
        "completed":completed,
        "blockers":blockers,
        "next_steps":next_steps,
        "evidence_refs":evidence,
        "checkpoint_digest":digest,
        "source":_clean(source,80) or "AION",
        "executes_action":False,
    }
    return normalize_handoff(payload)


def append_handoff(
    handoffs:Sequence[Mapping[str,Any]]|None,
    handoff:Mapping[str,Any],
)->list[dict[str,Any]]:
    rows=normalize_handoffs(handoffs)
    item=normalize_handoff(handoff)
    if all(x["handoff_id"]!=item["handoff_id"] for x in rows):
        rows.append(item)
    return rows[-MAX_HANDOFFS:]


def continuity_summary(
    missions:Sequence[Mapping[str,Any]]|None,
    handoffs:Sequence[Mapping[str,Any]]|None,
)->dict[str,Any]:
    rows=normalize_missions(missions)
    history=normalize_handoffs(handoffs)
    by_status={status:0 for status in MISSION_STATUSES}
    for item in rows:
        by_status[item["status"]]+=1
    active=[x for x in rows if x["status"] in ACTIVE_STATUSES]
    active.sort(key=lambda x:(
        0 if x["status"]=="IN_PROGRESS" else
        1 if x["status"]=="WAITING_APPROVAL" else
        2 if x["status"]=="BLOCKED" else 3,
        str(x["updated_at"]),
    ))
    completed=[x for x in rows if x["status"]=="DONE"]
    completed.sort(key=lambda x:str(x.get("completed_at") or x.get("updated_at") or ""),reverse=True)
    return {
        "schema":SCHEMA,
        "total_missions":len(rows),
        "active_missions":len(active),
        "blocked_missions":by_status["BLOCKED"],
        "done_missions":by_status["DONE"],
        "by_status":by_status,
        "current_mission":deepcopy(active[0]) if active else None,
        "recent_completed":deepcopy(completed[:8]),
        "latest_handoff":deepcopy(history[-1]) if history else None,
        "handoff_count":len(history),
        "executes_action":False,
    }


def continuity_briefing(
    missions:Sequence[Mapping[str,Any]]|None,
    handoffs:Sequence[Mapping[str,Any]]|None,
    *,
    tasks:Sequence[Mapping[str,Any]]|None=None,
    events:Sequence[Mapping[str,Any]]|None=None,
    checkpoint_digest:Any="",
)->dict[str,Any]:
    """Return the best available continuity view without inventing progress."""
    summary=continuity_summary(missions,handoffs)
    latest=summary.get("latest_handoff")
    if isinstance(latest,Mapping):
        handoff=deepcopy(dict(latest))
        source="PERSISTED_HANDOFF"
    else:
        handoff=build_session_handoff(
            missions,
            tasks=tasks,
            events=events,
            checkpoint_digest=checkpoint_digest,
            source="AION_SYNTHESIS",
        )
        source="SYNTHESIZED_FROM_CHECKPOINT"

    current=summary.get("current_mission") if isinstance(summary.get("current_mission"),Mapping) else None
    focus=str(handoff.get("current_focus") or (current or {}).get("title") or "")
    next_steps=[str(x) for x in list(handoff.get("next_steps") or [])[:8]]
    blockers=[str(x) for x in list(handoff.get("blockers") or [])[:8]]
    completed=[str(x) for x in list(handoff.get("completed") or [])[:8]]
    return {
        "schema":SCHEMA,
        "source":source,
        "current_focus":focus,
        "next_steps":next_steps,
        "blockers":blockers,
        "recent_completed":completed,
        "latest_handoff_id":str(handoff.get("handoff_id") or ""),
        "latest_handoff_at":str(handoff.get("created_at") or ""),
        "mission_summary":summary,
        "truth_state":"CONFIRMED_CHECKPOINT_STATE",
        "executes_action":False,
    }


def continuity_digest(
    missions:Sequence[Mapping[str,Any]]|None,
    handoffs:Sequence[Mapping[str,Any]]|None,
)->str:
    payload={
        "missions":normalize_missions(missions),
        "handoffs":normalize_handoffs(handoffs),
    }
    raw=json.dumps(payload,ensure_ascii=False,sort_keys=True,default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


__all__=[
    "SCHEMA","MISSION_STATUSES","ACTIVE_STATUSES",
    "new_mission","normalize_mission","normalize_missions","upsert_mission",
    "transition_mission","normalize_handoff","normalize_handoffs",
    "build_session_handoff","append_handoff","continuity_summary","continuity_briefing","continuity_digest",
]
