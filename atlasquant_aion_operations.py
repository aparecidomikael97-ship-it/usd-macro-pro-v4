"""AION operating queue, approvals and secretary contracts.

Pure/offline helpers. No network calls. The queue stores work requested by the
administrator and keeps approval state separate from execution state.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence
import hashlib
import json

from atlasquant_aion_core import (
    DOMAINS,
    cost_guard,
    guardian_decision,
)

SCHEMA="ATLASQUANT_AION_OPERATIONS_V1"
MAX_TASKS=300
MAX_TITLE=240
MAX_NOTE=1200

PRIORITIES=("P0","P1","P2","P3")
STATUSES=("TODO","IN_PROGRESS","WAITING_APPROVAL","BLOCKED","DONE","CANCELED")
ACTIONS=(
    "read","summarize","search","draft","save_checkpoint","write_runtime",
    "publish_social","publish_marketplace","activate_promotion","charge_customer",
    "deploy_production","merge_main","read_secret","write_secret","real_trade",
)
_PRIORITY_RANK={"P0":0,"P1":1,"P2":2,"P3":3}
_ACTIVE={"TODO","IN_PROGRESS","WAITING_APPROVAL","BLOCKED"}


def _now()->str:
    return datetime.now(timezone.utc).isoformat()


def _clean_text(value:Any, limit:int)->str:
    text=" ".join(str(value or "").replace("\x00","").split())
    return text[:limit]


def _normalize_priority(value:Any)->str:
    p=str(value or "P2").strip().upper()
    return p if p in PRIORITIES else "P2"


def _normalize_status(value:Any)->str:
    s=str(value or "TODO").strip().upper()
    return s if s in STATUSES else "TODO"


def _normalize_domain(value:Any)->str:
    d=str(value or "central").strip().lower()
    return d if d in DOMAINS else "central"


def _normalize_action(value:Any)->str:
    a=str(value or "read").strip().lower()
    return a if a in ACTIONS else "read"


def _task_id(title:str, domain:str, created_at:str)->str:
    raw=f"{domain}|{title}|{created_at}".encode("utf-8")
    return "AION-"+hashlib.sha256(raw).hexdigest()[:12].upper()


def new_task(
    title:Any,
    *,
    domain:Any="central",
    priority:Any="P2",
    action:Any="read",
    note:Any="",
    estimated_monthly_cost_usd:Any=0.0,
    created_at:str|None=None,
    source:str="ADMIN",
)->dict[str,Any]:
    title_clean=_clean_text(title,MAX_TITLE)
    if not title_clean:
        raise ValueError("task title required")
    try:
        cost=max(0.0,float(estimated_monthly_cost_usd or 0))
    except Exception as exc:
        raise ValueError("invalid task cost") from exc
    created=str(created_at or _now())
    domain_norm=_normalize_domain(domain)
    return {
        "schema":SCHEMA,
        "task_id":_task_id(title_clean,domain_norm,created),
        "title":title_clean,
        "domain":domain_norm,
        "priority":_normalize_priority(priority),
        "status":"TODO",
        "action":_normalize_action(action),
        "note":_clean_text(note,MAX_NOTE),
        "estimated_monthly_cost_usd":round(cost,4),
        "approval":{
            "required":False,
            "attempted":False,
            "approved":False,
            "approved_at":"",
            "approved_by":"",
            "guardian_allowed":False,
            "cost_allowed":False,
            "feature_flag":"",
        },
        "created_at":created,
        "updated_at":created,
        "source":_clean_text(source,80) or "ADMIN",
    }


def normalize_task(task:Mapping[str,Any])->dict[str,Any]:
    if not isinstance(task,Mapping):
        raise ValueError("invalid task")
    title=_clean_text(task.get("title"),MAX_TITLE)
    if not title:
        raise ValueError("task title required")
    created=str(task.get("created_at") or _now())
    normalized=new_task(
        title,
        domain=task.get("domain"),
        priority=task.get("priority"),
        action=task.get("action"),
        note=task.get("note"),
        estimated_monthly_cost_usd=task.get("estimated_monthly_cost_usd",0),
        created_at=created,
        source=str(task.get("source") or "ADMIN"),
    )
    supplied_id=_clean_text(task.get("task_id"),64)
    if supplied_id:
        normalized["task_id"]=supplied_id
    normalized["status"]=_normalize_status(task.get("status"))
    normalized["updated_at"]=str(task.get("updated_at") or created)
    approval=task.get("approval")
    if isinstance(approval,Mapping):
        normalized["approval"]={
            "required":bool(approval.get("required",False)),
            "attempted":bool(approval.get("attempted",False)),
            "approved":bool(approval.get("approved",False)),
            "approved_at":_clean_text(approval.get("approved_at"),80),
            "approved_by":_clean_text(approval.get("approved_by"),80),
            "guardian_allowed":bool(approval.get("guardian_allowed",False)),
            "cost_allowed":bool(approval.get("cost_allowed",False)),
            "feature_flag":_clean_text(approval.get("feature_flag"),80),
        }
    return normalized


def normalize_queue(tasks:Sequence[Mapping[str,Any]]|None)->list[dict[str,Any]]:
    out=[]
    seen=set()
    for raw in list(tasks or [])[:MAX_TASKS*2]:
        try:
            task=normalize_task(raw)
        except Exception:
            continue
        tid=task["task_id"]
        if tid in seen:
            continue
        seen.add(tid)
        out.append(task)
        if len(out)>=MAX_TASKS:
            break
    return out


def upsert_task(
    tasks:Sequence[Mapping[str,Any]]|None,
    task:Mapping[str,Any],
)->list[dict[str,Any]]:
    queue=normalize_queue(tasks)
    item=normalize_task(task)
    replaced=False
    for idx,current in enumerate(queue):
        if current["task_id"]==item["task_id"]:
            queue[idx]=item
            replaced=True
            break
    if not replaced:
        if len(queue)>=MAX_TASKS:
            raise ValueError("task queue capacity reached")
        queue.append(item)
    return queue


def transition_task(
    tasks:Sequence[Mapping[str,Any]]|None,
    task_id:Any,
    status:Any,
)->list[dict[str,Any]]:
    queue=normalize_queue(tasks)
    target=_clean_text(task_id,64)
    next_status=_normalize_status(status)
    found=False
    for task in queue:
        if task["task_id"]!=target:
            continue
        found=True
        task["status"]=next_status
        task["updated_at"]=_now()
    if not found:
        raise ValueError("task not found")
    return queue


def approval_requirement(
    task:Mapping[str,Any],
    access:Mapping[str,Any]|None,
    *,
    feature_flags:Mapping[str,Any]|None=None,
)->dict[str,Any]:
    item=normalize_task(task)
    cost=cost_guard(item["estimated_monthly_cost_usd"],approved=False)
    guardian=guardian_decision(
        item["action"],
        access,
        approved=False,
        feature_flags=feature_flags,
    )
    required=bool(
        cost["requires_explicit_approval"]
        or guardian["requires_explicit_approval"]
        or not guardian["allowed"]
    )
    return {
        "schema":SCHEMA,
        "required":required,
        "cost":cost,
        "guardian":guardian,
    }


def approve_task(
    tasks:Sequence[Mapping[str,Any]]|None,
    task_id:Any,
    access:Mapping[str,Any]|None,
    *,
    feature_flags:Mapping[str,Any]|None=None,
)->list[dict[str,Any]]:
    queue=normalize_queue(tasks)
    target=_clean_text(task_id,64)
    username=_clean_text((access or {}).get("username"),80) or "ADMIN"
    found=False
    for task in queue:
        if task["task_id"]!=target:
            continue
        found=True
        # Approval records intent only. It does not bypass a feature flag and
        # does not execute any action.
        cost=cost_guard(task["estimated_monthly_cost_usd"],approved=True)
        guardian=guardian_decision(
            task["action"],
            access,
            approved=True,
            feature_flags=feature_flags,
        )
        approval_valid=bool(guardian["allowed"] and cost["allowed"])
        task["approval"]={
            "required":True,
            "attempted":True,
            "approved":approval_valid,
            "approved_at":_now() if approval_valid else "",
            "approved_by":username if approval_valid else "",
            "guardian_allowed":bool(guardian["allowed"]),
            "cost_allowed":bool(cost["allowed"]),
            "feature_flag":str(guardian.get("feature_flag") or ""),
        }
        task["updated_at"]=_now()
        task["status"]="TODO" if approval_valid else "BLOCKED"
        task["approval_decision"]={
            "guardian_allowed":bool(guardian["allowed"]),
            "guardian_reason":str(guardian["reason"]),
            "cost_allowed":bool(cost["allowed"]),
            "feature_flag":str(guardian.get("feature_flag") or ""),
            "approval_valid":approval_valid,
        }
    if not found:
        raise ValueError("task not found")
    return queue


def executable_decision(
    task:Mapping[str,Any],
    access:Mapping[str,Any]|None,
    *,
    feature_flags:Mapping[str,Any]|None=None,
)->dict[str,Any]:
    item=normalize_task(task)
    approved=bool((item.get("approval") or {}).get("approved",False))
    guardian=guardian_decision(
        item["action"],
        access,
        approved=approved,
        feature_flags=feature_flags,
    )
    cost=cost_guard(item["estimated_monthly_cost_usd"],approved=approved)
    allowed=bool(guardian["allowed"] and cost["allowed"])
    return {
        "schema":SCHEMA,
        "allowed":allowed,
        "task_id":item["task_id"],
        "guardian":guardian,
        "cost":cost,
        "executes_action":False,
    }


def queue_summary(tasks:Sequence[Mapping[str,Any]]|None)->dict[str,Any]:
    queue=normalize_queue(tasks)
    by_status={status:0 for status in STATUSES}
    by_priority={priority:0 for priority in PRIORITIES}
    for task in queue:
        by_status[task["status"]]+=1
        by_priority[task["priority"]]+=1
    active=[x for x in queue if x["status"] in _ACTIVE]
    active.sort(key=lambda x:(
        _PRIORITY_RANK.get(x["priority"],99),
        0 if x["status"]=="WAITING_APPROVAL" else 1,
        str(x["created_at"]),
    ))
    return {
        "schema":SCHEMA,
        "total":len(queue),
        "active":len(active),
        "waiting_approval":by_status["WAITING_APPROVAL"],
        "blocked":by_status["BLOCKED"],
        "done":by_status["DONE"],
        "by_status":by_status,
        "by_priority":by_priority,
        "next_actions":deepcopy(active[:8]),
    }


def queue_digest(tasks:Sequence[Mapping[str,Any]]|None)->str:
    raw=json.dumps(normalize_queue(tasks),ensure_ascii=False,sort_keys=True,default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
