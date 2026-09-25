"""AION Dev Fusion Pipeline.

Coordinates independent Builder, Reviewer and Breaker/Red-Team evidence around a
Digital Twin and Evaluation Lab run. It records workflow evidence only.

No stage calls tools, changes code, merges PRs, deploys, rolls back or enables
real trading. Human approval remains mandatory after all gates.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Mapping, Sequence
import json

SCHEMA="ATLASQUANT_AION_DEV_FUSION_V1"
MAX_PIPELINES=300
STAGES=("PLAN","BUILD","REVIEW","BREAK","EVALUATE","RELEASE_REVIEW")
STAGE_STATES=("PENDING","RUNNING","PASS","FAIL","BLOCKED","WAITING_HUMAN")
PIPELINE_STATES=("PLANNED","IN_PROGRESS","BLOCKED","HUMAN_REVIEW_CANDIDATE","DONE")


def _now()->str:
    return datetime.now(timezone.utc).isoformat()


def _clean(value:Any,limit:int=1600)->str:
    return " ".join(str(value or "").replace("\x00","").split())[:limit]


def _refs(values:Sequence[Any]|None,limit:int=100)->list[str]:
    out=[]
    for raw in list(values or [])[:limit*2]:
        text=_clean(raw,300)
        if text and text not in out:
            out.append(text)
        if len(out)>=limit:
            break
    return out


def _digest(value:Any,length:int=20)->str:
    raw=json.dumps(value,ensure_ascii=False,sort_keys=True,default=str)
    return sha256(raw.encode("utf-8")).hexdigest()[:length]


def _stage_rows()->list[dict[str,Any]]:
    return [{
        "stage":name,
        "state":"PENDING",
        "actor_ref":"",
        "evidence_refs":[],
        "summary":"",
        "critical_findings":0,
        "updated_at":"",
        "executes_action":False,
    } for name in STAGES]


def new_dev_fusion_pipeline(
    title:Any,
    *,
    twin_id:Any,
    baseline_ref:Any,
    candidate_ref:Any,
    created_by:Any="ADMIN",
    created_at:str|None=None,
)->dict[str,Any]:
    title_text=_clean(title,300)
    twin=_clean(twin_id,140)
    baseline=_clean(baseline_ref,180)
    candidate=_clean(candidate_ref,180)
    if not title_text or not twin or not baseline or not candidate or baseline==candidate:
        raise ValueError("invalid Dev Fusion pipeline")
    created=str(created_at or _now())
    pid="DEVF-"+_digest({"title":title_text,"twin":twin,"c":candidate,"at":created},16).upper()
    return {
        "schema":SCHEMA,
        "pipeline_id":pid,
        "title":title_text,
        "twin_id":twin,
        "baseline_ref":baseline,
        "candidate_ref":candidate,
        "evaluation_run_id":"",
        "stages":_stage_rows(),
        "state":"PLANNED",
        "created_by":_clean(created_by,120) or "ADMIN",
        "created_at":created,
        "updated_at":created,
        "automatic_merge":False,
        "automatic_deploy":False,
        "production_change_allowed":False,
        "real_trading_enabled":False,
    }


def normalize_pipeline(raw:Mapping[str,Any])->dict[str,Any]:
    item=dict(raw or {})
    created=_clean(item.get("created_at"),80) or _now()
    out=new_dev_fusion_pipeline(
        item.get("title"),
        twin_id=item.get("twin_id"),
        baseline_ref=item.get("baseline_ref"),
        candidate_ref=item.get("candidate_ref"),
        created_by=item.get("created_by") or "ADMIN",
        created_at=created,
    )
    supplied=_clean(item.get("pipeline_id"),120)
    if supplied:
        out["pipeline_id"]=supplied
    stage_map={x["stage"]:x for x in out["stages"]}
    for raw_stage in list(item.get("stages") or [])[:len(STAGES)*2]:
        if not isinstance(raw_stage,Mapping):
            continue
        name=_clean(raw_stage.get("stage"),40).upper()
        if name not in stage_map:
            continue
        state=_clean(raw_stage.get("state"),40).upper()
        if state not in STAGE_STATES:
            state="PENDING"
        stage_map[name]={
            "stage":name,
            "state":state,
            "actor_ref":_clean(raw_stage.get("actor_ref"),160),
            "evidence_refs":_refs(raw_stage.get("evidence_refs") if isinstance(raw_stage.get("evidence_refs"),(list,tuple)) else []),
            "summary":_clean(raw_stage.get("summary"),1200),
            "critical_findings":max(0,min(int(raw_stage.get("critical_findings") or 0),10000)),
            "updated_at":_clean(raw_stage.get("updated_at"),80),
            "executes_action":False,
        }
    out["stages"]=[stage_map[x] for x in STAGES]
    out["evaluation_run_id"]=_clean(item.get("evaluation_run_id"),140)
    out["updated_at"]=_clean(item.get("updated_at"),80) or created
    return evaluate_pipeline(out)


def _get_stage(item:Mapping[str,Any],name:str)->dict[str,Any]:
    return next(x for x in item["stages"] if x["stage"]==name)


def record_stage(
    pipeline:Mapping[str,Any],
    stage:Any,
    *,
    state:Any,
    actor_ref:Any,
    evidence_refs:Sequence[Any]|None=None,
    summary:Any="",
    critical_findings:Any=0,
    evaluation_run_id:Any="",
    changed_at:str|None=None,
)->dict[str,Any]:
    item=normalize_pipeline(pipeline)
    name=_clean(stage,40).upper()
    next_state=_clean(state,40).upper()
    if name not in STAGES or next_state not in STAGE_STATES:
        raise ValueError("invalid Dev Fusion stage update")
    actor=_clean(actor_ref,160)
    refs=_refs(evidence_refs)
    if next_state in {"PASS","FAIL","BLOCKED","WAITING_HUMAN"} and not refs:
        raise ValueError("terminal/review stage state requires evidence")
    if next_state in {"PASS","FAIL","BLOCKED","WAITING_HUMAN"} and not actor:
        raise ValueError("stage actor required")

    builder=_get_stage(item,"BUILD")
    reviewer=_get_stage(item,"REVIEW")
    if name=="REVIEW" and actor and builder.get("actor_ref") and actor==builder["actor_ref"]:
        raise ValueError("reviewer must be independent from builder")
    if name=="BREAK":
        prior={x for x in (builder.get("actor_ref"),reviewer.get("actor_ref")) if x}
        if actor in prior:
            raise ValueError("breaker must be independent from builder/reviewer")

    for row in item["stages"]:
        if row["stage"]==name:
            row.update({
                "state":next_state,
                "actor_ref":actor,
                "evidence_refs":refs,
                "summary":_clean(summary,1200),
                "critical_findings":max(0,min(int(critical_findings or 0),10000)),
                "updated_at":str(changed_at or _now()),
                "executes_action":False,
            })
            break
    if name=="EVALUATE" and evaluation_run_id:
        item["evaluation_run_id"]=_clean(evaluation_run_id,140)
    item["updated_at"]=str(changed_at or _now())
    return evaluate_pipeline(item)


def evaluate_pipeline(pipeline:Mapping[str,Any])->dict[str,Any]:
    item=dict(pipeline or {})
    stages=list(item.get("stages") or [])
    if not stages:
        return item
    blockers=[]
    builder=next((x for x in stages if x.get("stage")=="BUILD"),{})
    reviewer=next((x for x in stages if x.get("stage")=="REVIEW"),{})
    breaker=next((x for x in stages if x.get("stage")=="BREAK"),{})
    evaluator=next((x for x in stages if x.get("stage")=="EVALUATE"),{})
    release=next((x for x in stages if x.get("stage")=="RELEASE_REVIEW"),{})

    if builder.get("actor_ref") and reviewer.get("actor_ref") and builder["actor_ref"]==reviewer["actor_ref"]:
        blockers.append("REVIEWER_NOT_INDEPENDENT")
    if breaker.get("actor_ref") and breaker["actor_ref"] in {builder.get("actor_ref"),reviewer.get("actor_ref")}:
        blockers.append("BREAKER_NOT_INDEPENDENT")

    for row in stages:
        if row.get("state") in {"FAIL","BLOCKED"}:
            blockers.append(f"{row.get('stage')}_{row.get('state')}")
        if int(row.get("critical_findings") or 0)>0:
            blockers.append(f"{row.get('stage')}_CRITICAL_FINDINGS")

    review_ready=bool(
        builder.get("state")=="PASS"
        and reviewer.get("state")=="PASS"
        and breaker.get("state")=="PASS"
        and evaluator.get("state")=="PASS"
        and item.get("evaluation_run_id")
        and not blockers
    )
    if blockers:
        state="BLOCKED"
    elif release.get("state")=="PASS":
        state="DONE"
    elif review_ready and release.get("state") in {"PENDING","WAITING_HUMAN"}:
        state="HUMAN_REVIEW_CANDIDATE"
    elif any(x.get("state")!="PENDING" for x in stages):
        state="IN_PROGRESS"
    else:
        state="PLANNED"
    item["state"]=state
    item["blockers"]=list(dict.fromkeys(blockers))
    item["automatic_merge"]=False
    item["automatic_deploy"]=False
    item["production_change_allowed"]=False
    item["real_trading_enabled"]=False
    return item


def normalize_pipelines(rows:Sequence[Mapping[str,Any]]|None)->list[dict[str,Any]]:
    out=[]
    seen=set()
    for raw in list(rows or [])[-MAX_PIPELINES*2:]:
        if not isinstance(raw,Mapping):
            continue
        try:
            item=normalize_pipeline(raw)
        except Exception:
            continue
        pid=item["pipeline_id"]
        if pid in seen:
            continue
        seen.add(pid)
        out.append(item)
    return out[-MAX_PIPELINES:]


def upsert_pipeline(rows:Sequence[Mapping[str,Any]]|None,pipeline:Mapping[str,Any])->list[dict[str,Any]]:
    current=normalize_pipelines(rows)
    item=normalize_pipeline(pipeline)
    for idx,row in enumerate(current):
        if row["pipeline_id"]==item["pipeline_id"]:
            current[idx]=item
            return current
    current.append(item)
    return current[-MAX_PIPELINES:]


def dev_fusion_digest(rows:Sequence[Mapping[str,Any]]|None)->str:
    return _digest(normalize_pipelines(rows),24)


def dev_fusion_summary(rows:Sequence[Mapping[str,Any]]|None)->dict[str,Any]:
    pipelines=normalize_pipelines(rows)
    return {
        "schema":SCHEMA,
        "pipelines":len(pipelines),
        "human_review_candidates":sum(1 for x in pipelines if x["state"]=="HUMAN_REVIEW_CANDIDATE"),
        "blocked":sum(1 for x in pipelines if x["state"]=="BLOCKED"),
        "done":sum(1 for x in pipelines if x["state"]=="DONE"),
        "automatic_merge":False,
        "automatic_deploy":False,
        "real_trading_enabled":False,
        "digest":dev_fusion_digest(pipelines),
    }


__all__=[
    "SCHEMA","STAGES","STAGE_STATES","PIPELINE_STATES",
    "new_dev_fusion_pipeline","normalize_pipeline","record_stage","evaluate_pipeline",
    "normalize_pipelines","upsert_pipeline","dev_fusion_digest","dev_fusion_summary",
]
