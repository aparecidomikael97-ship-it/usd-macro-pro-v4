"""AION Digital Twin contracts.

A Digital Twin is a read-only simulation manifest for a proposed change. It
captures baseline/candidate identity, scope, dependencies, expected impacts,
evidence and rollback assumptions without touching production.

This module never edits code, calls tools, deploys, rolls back or enables real
trading.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Mapping, Sequence
import json
import math

SCHEMA="ATLASQUANT_AION_DIGITAL_TWIN_V1"
MAX_TWINS=300
TWIN_STATES=("PLANNED","EVIDENCE_INCOMPLETE","READY_FOR_EVALUATION","BLOCKED")
IMPACTS=("LOW","MEDIUM","HIGH","CRITICAL")


def _now()->str:
    return datetime.now(timezone.utc).isoformat()


def _clean(value:Any,limit:int=1200)->str:
    return " ".join(str(value or "").replace("\x00","").split())[:limit]


def _refs(values:Sequence[Any]|None,limit:int=80)->list[str]:
    out=[]
    for raw in list(values or [])[:limit*2]:
        text=_clean(raw,280)
        if text and text not in out:
            out.append(text)
        if len(out)>=limit:
            break
    return out


def _digest(value:Any,length:int=20)->str:
    raw=json.dumps(value,ensure_ascii=False,sort_keys=True,default=str)
    return sha256(raw.encode("utf-8")).hexdigest()[:length]


def _finite_pct(value:Any)->float|None:
    try:
        x=float(value)
        if math.isfinite(x) and 0.0<=x<=100.0:
            return round(x,2)
    except Exception:
        pass
    return None


def new_digital_twin(
    title:Any,
    *,
    baseline_ref:Any,
    candidate_ref:Any,
    scope:Sequence[Any]|None=None,
    dependencies:Sequence[Any]|None=None,
    expected_impacts:Sequence[Any]|None=None,
    rollback_plan:Any="",
    created_by:Any="ADMIN",
    created_at:str|None=None,
)->dict[str,Any]:
    title_text=_clean(title,300)
    baseline=_clean(baseline_ref,180)
    candidate=_clean(candidate_ref,180)
    if not title_text or not baseline or not candidate or baseline==candidate:
        raise ValueError("digital twin requires distinct baseline and candidate")
    created=str(created_at or _now())
    twin_id="TWIN-"+_digest({"title":title_text,"b":baseline,"c":candidate,"at":created},16).upper()
    return {
        "schema":SCHEMA,
        "twin_id":twin_id,
        "title":title_text,
        "baseline_ref":baseline,
        "candidate_ref":candidate,
        "scope":_refs(scope,60),
        "dependencies":_refs(dependencies,80),
        "expected_impacts":_refs(expected_impacts,80),
        "rollback_plan":_clean(rollback_plan,1800),
        "observations":[],
        "state":"PLANNED",
        "created_by":_clean(created_by,120) or "ADMIN",
        "created_at":created,
        "updated_at":created,
        "simulation_only":True,
        "production_touched":False,
        "automatic_action":False,
        "real_trading_enabled":False,
    }


def normalize_observation(raw:Mapping[str,Any])->dict[str,Any]:
    item=dict(raw or {})
    impact=_clean(item.get("impact"),30).upper()
    if impact not in IMPACTS:
        impact="MEDIUM"
    return {
        "observation_id":_clean(item.get("observation_id"),120) or "OBS-"+_digest(item,14).upper(),
        "area":_clean(item.get("area"),120).lower() or "general",
        "claim":_clean(item.get("claim"),900),
        "impact":impact,
        "baseline_value":_clean(item.get("baseline_value"),300),
        "candidate_value":_clean(item.get("candidate_value"),300),
        "uncertainty_pct":_finite_pct(item.get("uncertainty_pct")),
        "evidence_refs":_refs(item.get("evidence_refs") if isinstance(item.get("evidence_refs"),(list,tuple)) else []),
        "critical_blocker":bool(item.get("critical_blocker",False)),
        "executes_action":False,
    }


def record_twin_observation(
    twin:Mapping[str,Any],
    *,
    area:Any,
    claim:Any,
    impact:Any="MEDIUM",
    baseline_value:Any="",
    candidate_value:Any="",
    uncertainty_pct:Any=None,
    evidence_refs:Sequence[Any]|None=None,
    critical_blocker:bool=False,
    changed_at:str|None=None,
)->dict[str,Any]:
    item=normalize_digital_twin(twin)
    obs=normalize_observation({
        "area":area,
        "claim":claim,
        "impact":impact,
        "baseline_value":baseline_value,
        "candidate_value":candidate_value,
        "uncertainty_pct":uncertainty_pct,
        "evidence_refs":evidence_refs,
        "critical_blocker":critical_blocker,
    })
    if not obs["claim"]:
        raise ValueError("digital twin observation claim required")
    rows=[x for x in item["observations"] if x["observation_id"]!=obs["observation_id"]]
    rows.append(obs)
    item["observations"]=rows[:500]
    item["updated_at"]=str(changed_at or _now())
    return evaluate_digital_twin(item)


def evaluate_digital_twin(twin:Mapping[str,Any])->dict[str,Any]:
    item=normalize_digital_twin(twin, evaluate=False)
    observations=item["observations"]
    blockers=[]
    if not item["scope"]:
        blockers.append("SCOPE_MISSING")
    if not item["rollback_plan"]:
        blockers.append("ROLLBACK_PLAN_MISSING")
    if not observations:
        blockers.append("NO_OBSERVATIONS")
    for obs in observations:
        if not obs["evidence_refs"]:
            blockers.append(f"EVIDENCE_MISSING:{obs['observation_id']}")
        if obs["uncertainty_pct"] is None:
            blockers.append(f"UNCERTAINTY_MISSING:{obs['observation_id']}")
        if obs["critical_blocker"]:
            blockers.append(f"CRITICAL_BLOCKER:{obs['observation_id']}")
    blockers=list(dict.fromkeys(blockers))
    critical=any(x.startswith("CRITICAL_BLOCKER:") for x in blockers)
    if critical:
        state="BLOCKED"
    elif blockers:
        state="EVIDENCE_INCOMPLETE"
    else:
        state="READY_FOR_EVALUATION"
    item["state"]=state
    item["blockers"]=blockers
    item["simulation_only"]=True
    item["production_touched"]=False
    item["automatic_action"]=False
    item["real_trading_enabled"]=False
    return item


def normalize_digital_twin(raw:Mapping[str,Any],*,evaluate:bool=True)->dict[str,Any]:
    item=dict(raw or {})
    title=_clean(item.get("title"),300)
    baseline=_clean(item.get("baseline_ref"),180)
    candidate=_clean(item.get("candidate_ref"),180)
    if not title or not baseline or not candidate or baseline==candidate:
        raise ValueError("invalid digital twin")
    created=_clean(item.get("created_at"),80) or _now()
    out=new_digital_twin(
        title,
        baseline_ref=baseline,
        candidate_ref=candidate,
        scope=item.get("scope") if isinstance(item.get("scope"),(list,tuple)) else [],
        dependencies=item.get("dependencies") if isinstance(item.get("dependencies"),(list,tuple)) else [],
        expected_impacts=item.get("expected_impacts") if isinstance(item.get("expected_impacts"),(list,tuple)) else [],
        rollback_plan=item.get("rollback_plan"),
        created_by=item.get("created_by") or "ADMIN",
        created_at=created,
    )
    supplied=_clean(item.get("twin_id"),120)
    if supplied:
        out["twin_id"]=supplied
    out["observations"]=[
        normalize_observation(x)
        for x in list(item.get("observations") or [])[:500]
        if isinstance(x,Mapping)
    ]
    out["updated_at"]=_clean(item.get("updated_at"),80) or created
    if evaluate:
        return evaluate_digital_twin(out)
    return out


def normalize_digital_twins(rows:Sequence[Mapping[str,Any]]|None)->list[dict[str,Any]]:
    out=[]
    seen=set()
    for raw in list(rows or [])[-MAX_TWINS*2:]:
        if not isinstance(raw,Mapping):
            continue
        try:
            item=normalize_digital_twin(raw)
        except Exception:
            continue
        tid=item["twin_id"]
        if tid in seen:
            continue
        seen.add(tid)
        out.append(item)
    return out[-MAX_TWINS:]


def upsert_digital_twin(rows:Sequence[Mapping[str,Any]]|None,twin:Mapping[str,Any])->list[dict[str,Any]]:
    current=normalize_digital_twins(rows)
    item=normalize_digital_twin(twin)
    for idx,row in enumerate(current):
        if row["twin_id"]==item["twin_id"]:
            current[idx]=item
            return current
    current.append(item)
    return current[-MAX_TWINS:]


def digital_twins_digest(rows:Sequence[Mapping[str,Any]]|None)->str:
    return _digest(normalize_digital_twins(rows),24)


def digital_twin_summary(rows:Sequence[Mapping[str,Any]]|None)->dict[str,Any]:
    twins=normalize_digital_twins(rows)
    return {
        "schema":SCHEMA,
        "twins":len(twins),
        "ready_for_evaluation":sum(1 for x in twins if x["state"]=="READY_FOR_EVALUATION"),
        "blocked":sum(1 for x in twins if x["state"]=="BLOCKED"),
        "incomplete":sum(1 for x in twins if x["state"]=="EVIDENCE_INCOMPLETE"),
        "production_touched":False,
        "automatic_action":False,
        "real_trading_enabled":False,
        "digest":digital_twins_digest(twins),
    }


__all__=[
    "SCHEMA","TWIN_STATES","IMPACTS","new_digital_twin","normalize_observation",
    "record_twin_observation","evaluate_digital_twin","normalize_digital_twin",
    "normalize_digital_twins","upsert_digital_twin","digital_twins_digest",
    "digital_twin_summary",
]
