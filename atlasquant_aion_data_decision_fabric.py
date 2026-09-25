"""AION Data & Decision Fabric.

Provider-neutral, deterministic contracts for sharing evidence and decision
state across Trading, Investments, Studio, Business and Development.

The fabric stores compact evidence envelopes and decision-review records. It is
not an execution bus: it never calls tools, spends money, publishes, deploys or
enables real trading. Memory/evidence can support a decision, but never grants
authority.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Mapping, Sequence
import json
import math

SCHEMA="ATLASQUANT_AION_DATA_DECISION_FABRIC_V1"
MAX_EVENTS=2000
MAX_DECISIONS=600

DOMAINS=(
    "central","trading","investments","studio","business","laboratory",
    "secretary","development","subscriptions","promotions",
)
EVENT_TYPES=(
    "EVIDENCE","OBSERVATION","HYPOTHESIS","TEST","DECISION",
    "OUTCOME","LEARNING","SYSTEM",
)
TRUTH_STATES=("CONFIRMED","INFERENCE","HYPOTHESIS","UNKNOWN")
RISK_LEVELS=("LOW","MEDIUM","HIGH","CRITICAL")
DECISION_STATES=(
    "DRAFT","RESEARCH_REQUIRED","TEST_REQUIRED","RISK_REVIEW",
    "HUMAN_REVIEW_CANDIDATE","BLOCKED","CLOSED",
)
PRIVACY_CLASSES=("PUBLIC","INTERNAL","SENSITIVE","SECRET")


def _now()->str:
    return datetime.now(timezone.utc).isoformat()


def _clean(value:Any,limit:int=1600)->str:
    return " ".join(str(value or "").replace("\x00","").split())[:limit]


def _upper(value:Any,limit:int=80)->str:
    return _clean(value,limit).upper()


def _lower(value:Any,limit:int=80)->str:
    return _clean(value,limit).lower()


def _refs(values:Sequence[Any]|None,limit:int=120)->list[str]:
    out=[]
    for raw in list(values or [])[:limit*2]:
        value=_clean(raw,320)
        if value and value not in out:
            out.append(value)
        if len(out)>=limit:
            break
    return out


def _stable(value:Any,length:int=24)->str:
    raw=json.dumps(value,ensure_ascii=False,sort_keys=True,default=str)
    return sha256(raw.encode("utf-8")).hexdigest()[:length]


def _dt(value:Any)->datetime|None:
    text=_clean(value,100)
    if not text:
        return None
    try:
        out=datetime.fromisoformat(text.replace("Z","+00:00"))
        if out.tzinfo is None:
            out=out.replace(tzinfo=timezone.utc)
        return out.astimezone(timezone.utc)
    except Exception:
        return None


def _finite(value:Any)->float|None:
    try:
        out=float(value)
        return out if math.isfinite(out) else None
    except Exception:
        return None


def fabric_policy()->dict[str,Any]:
    return {
        "schema":SCHEMA,
        "evidence_is_not_authority":True,
        "confirmed_requires_provenance":True,
        "conflicts_preserved":True,
        "silent_conflict_resolution":False,
        "incremental_deduplication":True,
        "cache_is_advisory":True,
        "automatic_action":False,
        "automatic_rule_change":False,
        "automatic_spend":False,
        "automatic_publish":False,
        "automatic_deploy":False,
        "real_trading_enabled":False,
    }


def new_fabric_event(
    label:Any,
    *,
    domain:Any="central",
    event_type:Any="EVIDENCE",
    truth_state:Any="UNKNOWN",
    source_ref:Any="",
    claim_key:Any="",
    value:Any="",
    value_summary:Any="",
    evidence_refs:Sequence[Any]|None=None,
    observed_at:Any="",
    valid_until:Any="",
    severity:Any="MEDIUM",
    privacy_class:Any="INTERNAL",
    supersedes:Any="",
    event_id:Any="",
)->dict[str,Any]:
    title=_clean(label,320)
    if not title:
        raise ValueError("event label required")
    dom=_lower(domain) or "central"
    if dom not in DOMAINS:
        dom="central"
    etype=_upper(event_type)
    if etype not in EVENT_TYPES:
        etype="EVIDENCE"
    truth=_upper(truth_state)
    if truth not in TRUTH_STATES:
        truth="UNKNOWN"
    risk=_upper(severity)
    if risk not in RISK_LEVELS:
        risk="MEDIUM"
    privacy=_upper(privacy_class)
    if privacy not in PRIVACY_CLASSES:
        privacy="INTERNAL"

    source=_clean(source_ref,320)
    refs=_refs(evidence_refs)
    if truth=="CONFIRMED" and not (source or refs):
        truth="UNKNOWN"

    observed=_clean(observed_at,100) or _now()
    expiry=_clean(valid_until,100)
    claim=_clean(claim_key,260)
    raw_value=value
    digest=_stable({"claim_key":claim,"value":raw_value})
    summary=_clean(value_summary if value_summary not in (None,"") else raw_value,700)
    if privacy in {"SENSITIVE","SECRET"}:
        summary="[REDACTED]"

    identity={
        "label":title,"domain":dom,"event_type":etype,"source_ref":source,
        "claim_key":claim,"observed_at":observed,"value_digest":digest,
    }
    eid=_clean(event_id,100) or ("FAB-"+_stable(identity,20).upper())
    return {
        "schema":SCHEMA,
        "event_id":eid,
        "label":title,
        "domain":dom,
        "event_type":etype,
        "truth_state":truth,
        "source_ref":source,
        "claim_key":claim,
        "value_digest":digest,
        "value_summary":summary,
        "evidence_refs":refs,
        "observed_at":observed,
        "valid_until":expiry,
        "severity":risk,
        "privacy_class":privacy,
        "supersedes":_clean(supersedes,100),
        "content_digest":_stable(identity|{"evidence_refs":refs,"truth_state":truth,"valid_until":expiry}),
        "action_authorized":False,
        "may_expand_permissions":False,
        "real_trading_enabled":False,
    }


def normalize_fabric_event(raw:Mapping[str,Any])->dict[str,Any]:
    item=dict(raw or {})
    return new_fabric_event(
        item.get("label") or item.get("claim_key") or item.get("event_id"),
        domain=item.get("domain"),
        event_type=item.get("event_type"),
        truth_state=item.get("truth_state"),
        source_ref=item.get("source_ref"),
        claim_key=item.get("claim_key"),
        value=item.get("value_summary") or item.get("value_digest"),
        value_summary=item.get("value_summary"),
        evidence_refs=item.get("evidence_refs") if isinstance(item.get("evidence_refs"),(list,tuple)) else [],
        observed_at=item.get("observed_at"),
        valid_until=item.get("valid_until"),
        severity=item.get("severity"),
        privacy_class=item.get("privacy_class"),
        supersedes=item.get("supersedes"),
        event_id=item.get("event_id"),
    ) | {
        # Persist supplied digests when present; normalization must not invent a
        # different fact identity simply because only compact data is stored.
        "value_digest":_clean(item.get("value_digest"),80) or _stable({
            "claim_key":_clean(item.get("claim_key"),260),
            "value":item.get("value_summary"),
        }),
        "content_digest":_clean(item.get("content_digest"),80) or _stable(item),
    }


def normalize_fabric_events(rows:Sequence[Mapping[str,Any]]|None)->list[dict[str,Any]]:
    out=[]
    by_id={}
    for raw in list(rows or [])[-MAX_EVENTS*2:]:
        if not isinstance(raw,Mapping):
            continue
        try:
            item=normalize_fabric_event(raw)
        except Exception:
            continue
        eid=item["event_id"]
        prior=by_id.get(eid)
        if prior and prior.get("content_digest")!=item.get("content_digest"):
            # Same immutable event id with different content is unsafe.
            raise ValueError("fabric event id collision")
        by_id[eid]=item
    for raw in list(rows or [])[-MAX_EVENTS*2:]:
        if not isinstance(raw,Mapping):
            continue
        eid=_clean(raw.get("event_id"),100)
        if eid and eid in by_id and all(x["event_id"]!=eid for x in out):
            out.append(by_id[eid])
    # Include generated ids for legacy rows that did not have one.
    for eid,item in by_id.items():
        if all(x["event_id"]!=eid for x in out):
            out.append(item)
    return out[-MAX_EVENTS:]


def merge_fabric_events(
    existing:Sequence[Mapping[str,Any]]|None,
    incoming:Sequence[Mapping[str,Any]]|None,
)->list[dict[str,Any]]:
    current={x["event_id"]:x for x in normalize_fabric_events(existing)}
    order=[x["event_id"] for x in normalize_fabric_events(existing)]
    for raw in list(incoming or []):
        if not isinstance(raw,Mapping):
            continue
        item=normalize_fabric_event(raw)
        eid=item["event_id"]
        prior=current.get(eid)
        if prior and prior["content_digest"]!=item["content_digest"]:
            raise ValueError("fabric event id collision")
        if not prior:
            order.append(eid)
        current[eid]=item
    return [current[eid] for eid in order if eid in current][-MAX_EVENTS:]


def event_is_expired(event:Mapping[str,Any],*,now:Any=None)->bool:
    item=normalize_fabric_event(event)
    expiry=_dt(item.get("valid_until"))
    if expiry is None:
        return False
    current=_dt(now) if now is not None else datetime.now(timezone.utc)
    if current is None:
        current=datetime.now(timezone.utc)
    return current>expiry


def active_fabric_events(
    rows:Sequence[Mapping[str,Any]]|None,
    *,
    now:Any=None,
)->list[dict[str,Any]]:
    events=normalize_fabric_events(rows)
    superseded={x["supersedes"] for x in events if x.get("supersedes")}
    return [
        x for x in events
        if x["event_id"] not in superseded and not event_is_expired(x,now=now)
    ]


def detect_fabric_conflicts(
    rows:Sequence[Mapping[str,Any]]|None,
    *,
    claim_keys:Sequence[Any]|None=None,
    now:Any=None,
)->list[dict[str,Any]]:
    allowed=set(_refs(claim_keys,300))
    groups:dict[str,list[dict[str,Any]]]={}
    for item in active_fabric_events(rows,now=now):
        claim=item.get("claim_key") or ""
        if not claim or (allowed and claim not in allowed):
            continue
        if item.get("truth_state")!="CONFIRMED":
            continue
        groups.setdefault(claim,[]).append(item)
    conflicts=[]
    for claim,items in groups.items():
        values={x.get("value_digest") for x in items if x.get("value_digest")}
        sources={x.get("source_ref") for x in items if x.get("source_ref")}
        if len(values)>1 and len(sources)>1:
            conflicts.append({
                "claim_key":claim,
                "event_ids":[x["event_id"] for x in items],
                "source_refs":sorted(sources),
                "value_digests":sorted(values),
                "state":"CONFLICT",
                "automatic_resolution":False,
            })
    return conflicts


def _decision_id(objective:str,domain:str,created_at:str)->str:
    return "DEC-"+_stable({"objective":objective,"domain":domain,"created_at":created_at},20).upper()


def new_decision_case(
    objective:Any,
    *,
    domain:Any="central",
    hypothesis:Any="",
    required_claim_keys:Sequence[Any]|None=None,
    evidence_event_ids:Sequence[Any]|None=None,
    test_refs:Sequence[Any]|None=None,
    risk_level:Any="MEDIUM",
    impact:Any="MEDIUM",
    reversible:bool=True,
    rollback_plan:Any="",
    requires_test:bool=True,
    sensitive_action:bool=False,
    created_by:Any="AION",
    created_at:Any="",
    decision_id:Any="",
)->dict[str,Any]:
    obj=_clean(objective,1200)
    if not obj:
        raise ValueError("decision objective required")
    dom=_lower(domain) or "central"
    if dom not in DOMAINS:
        dom="central"
    risk=_upper(risk_level)
    if risk not in RISK_LEVELS:
        risk="MEDIUM"
    imp=_upper(impact)
    if imp not in RISK_LEVELS:
        imp="MEDIUM"
    created=_clean(created_at,100) or _now()
    did=_clean(decision_id,100) or _decision_id(obj,dom,created)
    return {
        "schema":SCHEMA,
        "decision_id":did,
        "domain":dom,
        "objective":obj,
        "hypothesis":_clean(hypothesis,1800),
        "required_claim_keys":_refs(required_claim_keys,120),
        "evidence_event_ids":_refs(evidence_event_ids,200),
        "test_refs":_refs(test_refs,120),
        "risk_level":risk,
        "impact":imp,
        "reversible":bool(reversible),
        "rollback_plan":_clean(rollback_plan,1800),
        "requires_test":bool(requires_test),
        "sensitive_action":bool(sensitive_action),
        "state":"DRAFT",
        "blockers":[],
        "evidence_coverage_pct":0.0,
        "created_by":_clean(created_by,160) or "AION",
        "created_at":created,
        "updated_at":created,
        "outcome":{},
        "action_authorized":False,
        "automatic_execution":False,
        "real_trading_enabled":False,
    }


def normalize_decision_case(raw:Mapping[str,Any])->dict[str,Any]:
    item=dict(raw or {})
    case=new_decision_case(
        item.get("objective"),
        domain=item.get("domain"),
        hypothesis=item.get("hypothesis"),
        required_claim_keys=item.get("required_claim_keys") if isinstance(item.get("required_claim_keys"),(list,tuple)) else [],
        evidence_event_ids=item.get("evidence_event_ids") if isinstance(item.get("evidence_event_ids"),(list,tuple)) else [],
        test_refs=item.get("test_refs") if isinstance(item.get("test_refs"),(list,tuple)) else [],
        risk_level=item.get("risk_level"),
        impact=item.get("impact"),
        reversible=bool(item.get("reversible",True)),
        rollback_plan=item.get("rollback_plan"),
        requires_test=bool(item.get("requires_test",True)),
        sensitive_action=bool(item.get("sensitive_action",False)),
        created_by=item.get("created_by"),
        created_at=item.get("created_at"),
        decision_id=item.get("decision_id"),
    )
    state=_upper(item.get("state") or "DRAFT")
    if state in DECISION_STATES:
        case["state"]=state
    case["blockers"]=_refs(item.get("blockers") if isinstance(item.get("blockers"),(list,tuple)) else [],80)
    cov=_finite(item.get("evidence_coverage_pct"))
    case["evidence_coverage_pct"]=round(max(0.0,min(100.0,cov or 0.0)),2)
    case["updated_at"]=_clean(item.get("updated_at"),100) or case["created_at"]
    outcome=item.get("outcome")
    case["outcome"]=dict(outcome) if isinstance(outcome,Mapping) else {}
    return case


def normalize_decision_cases(rows:Sequence[Mapping[str,Any]]|None)->list[dict[str,Any]]:
    out=[]
    seen=set()
    for raw in list(rows or [])[-MAX_DECISIONS*2:]:
        if not isinstance(raw,Mapping):
            continue
        try:
            item=normalize_decision_case(raw)
        except Exception:
            continue
        did=item["decision_id"]
        if did in seen:
            out=[x for x in out if x["decision_id"]!=did]
        seen.add(did)
        out.append(item)
    return out[-MAX_DECISIONS:]


def evaluate_decision_case(
    raw:Mapping[str,Any],
    events:Sequence[Mapping[str,Any]]|None,
    *,
    now:Any=None,
)->dict[str,Any]:
    case=normalize_decision_case(raw)
    current=active_fabric_events(events,now=now)
    by_id={x["event_id"]:x for x in current}
    selected=[
        by_id[eid] for eid in case["evidence_event_ids"]
        if eid in by_id
    ]

    required=set(case["required_claim_keys"])
    confirmed_claims={
        x["claim_key"] for x in selected
        if x.get("claim_key") and x.get("truth_state")=="CONFIRMED"
    }
    contextual_claims={
        x["claim_key"] for x in selected
        if x.get("claim_key") and x.get("truth_state") in {"INFERENCE","HYPOTHESIS"}
    }
    covered=confirmed_claims|contextual_claims
    missing=sorted(required-covered)
    conflicts=detect_fabric_conflicts(
        selected,
        claim_keys=case["required_claim_keys"],
        now=now,
    )

    blockers=[]
    if conflicts:
        blockers.append("EVIDENCE_CONFLICT")
    if missing:
        blockers.append("REQUIRED_EVIDENCE_MISSING")
    high_stakes=case["risk_level"] in {"HIGH","CRITICAL"} or case["impact"] in {"HIGH","CRITICAL"} or case["sensitive_action"]
    if high_stakes:
        not_confirmed=sorted(required-confirmed_claims)
        if not_confirmed:
            blockers.append("HIGH_STAKES_REQUIRES_CURRENT_CONFIRMED_EVIDENCE")
    if case["requires_test"] and not case["test_refs"]:
        blockers.append("TEST_EVIDENCE_MISSING")
    if high_stakes and case["reversible"] and not case["rollback_plan"]:
        blockers.append("ROLLBACK_PLAN_MISSING")
    blockers=list(dict.fromkeys(blockers))

    if conflicts:
        state="BLOCKED"
    elif missing or "HIGH_STAKES_REQUIRES_CURRENT_CONFIRMED_EVIDENCE" in blockers:
        state="RESEARCH_REQUIRED"
    elif "TEST_EVIDENCE_MISSING" in blockers:
        state="TEST_REQUIRED"
    elif "ROLLBACK_PLAN_MISSING" in blockers:
        state="RISK_REVIEW"
    else:
        state="HUMAN_REVIEW_CANDIDATE"

    coverage=100.0 if not required else (len(covered & required)/len(required))*100.0
    case.update({
        "state":state,
        "blockers":blockers,
        "evidence_coverage_pct":round(coverage,2),
        "evidence_summary":{
            "selected_events":len(selected),
            "confirmed_claims":sorted(confirmed_claims),
            "contextual_claims":sorted(contextual_claims),
            "missing_claims":missing,
            "conflicts":conflicts,
        },
        "updated_at":_now(),
        "action_authorized":False,
        "automatic_execution":False,
        "real_trading_enabled":False,
    })
    return case


def record_decision_outcome(
    raw:Mapping[str,Any],
    *,
    outcome_summary:Any,
    truth_state:Any="UNKNOWN",
    evidence_refs:Sequence[Any]|None=None,
    metrics:Mapping[str,Any]|None=None,
    root_cause:Any="",
    root_cause_truth_state:Any="UNKNOWN",
    root_cause_refs:Sequence[Any]|None=None,
    recorded_at:Any="",
)->dict[str,Any]:
    case=normalize_decision_case(raw)
    summary=_clean(outcome_summary,1600)
    if not summary:
        raise ValueError("outcome summary required")
    truth=_upper(truth_state)
    if truth not in TRUTH_STATES:
        truth="UNKNOWN"
    refs=_refs(evidence_refs)
    if truth=="CONFIRMED" and not refs:
        raise ValueError("confirmed outcome requires evidence")

    cause=_clean(root_cause,1000)
    cause_truth=_upper(root_cause_truth_state)
    if cause_truth not in TRUTH_STATES:
        cause_truth="UNKNOWN"
    cause_refs=_refs(root_cause_refs)
    if cause and cause_truth=="CONFIRMED" and not cause_refs:
        raise ValueError("confirmed root cause requires evidence")
    if not cause:
        cause_truth="UNKNOWN"

    case["outcome"]={
        "summary":summary,
        "truth_state":truth,
        "evidence_refs":refs,
        "metrics":dict(metrics or {}),
        "root_cause":cause,
        "root_cause_truth_state":cause_truth,
        "root_cause_refs":cause_refs,
        "recorded_at":_clean(recorded_at,100) or _now(),
        "learning_candidate":bool(truth=="CONFIRMED" and refs),
        "automatic_rule_change":False,
    }
    case["state"]="CLOSED"
    case["updated_at"]=_now()
    case["action_authorized"]=False
    case["automatic_execution"]=False
    case["real_trading_enabled"]=False
    return case


def upsert_decision_case(
    rows:Sequence[Mapping[str,Any]]|None,
    case:Mapping[str,Any],
)->list[dict[str,Any]]:
    current=normalize_decision_cases(rows)
    item=normalize_decision_case(case)
    current=[x for x in current if x["decision_id"]!=item["decision_id"]]
    current.append(item)
    return current[-MAX_DECISIONS:]


def _checkpoint_event(
    label:Any,
    *,
    domain:Any,
    event_type:Any,
    truth_state:Any,
    source_ref:Any,
    claim_key:Any,
    value_summary:Any,
    evidence_refs:Sequence[Any]|None=None,
    observed_at:Any="",
)->dict[str,Any]:
    return new_fabric_event(
        label,
        domain=domain,
        event_type=event_type,
        truth_state=truth_state,
        source_ref=source_ref,
        claim_key=claim_key,
        value=value_summary,
        value_summary=value_summary,
        evidence_refs=evidence_refs or [],
        observed_at=observed_at or _now(),
        privacy_class="INTERNAL",
    )


def derive_checkpoint_fabric_events(
    checkpoint:Mapping[str,Any]|None,
)->list[dict[str,Any]]:
    """Build read-only cross-domain envelopes from already persisted state.

    These derived events are not automatically written back to the checkpoint.
    Their purpose is to give the decision engine one common evidence vocabulary.
    """
    cp=dict(checkpoint or {})
    out=[]

    operating=cp.get("operating") if isinstance(cp.get("operating"),Mapping) else {}
    op_digest=_clean(operating.get("task_digest"),120)
    for task in list(operating.get("tasks",[]) or [])[-200:]:
        if not isinstance(task,Mapping):
            continue
        tid=_clean(task.get("task_id"),100)
        if not tid:
            continue
        out.append(_checkpoint_event(
            f"Tarefa {task.get('title') or tid}",
            domain=task.get("domain") or "central",
            event_type="SYSTEM",
            truth_state="CONFIRMED",
            source_ref=f"checkpoint:operating:{tid}",
            claim_key=f"task.{tid}.status",
            value_summary=str(task.get("status") or "UNKNOWN"),
            evidence_refs=[f"task_digest:{op_digest}"] if op_digest else [],
            observed_at=task.get("updated_at") or task.get("created_at"),
        ))

    studio=cp.get("studio") if isinstance(cp.get("studio"),Mapping) else {}
    studio_digest=_clean(studio.get("digest"),120)
    for project in list(studio.get("projects",[]) or [])[-200:]:
        if not isinstance(project,Mapping):
            continue
        pid=_clean(project.get("content_id"),100)
        if not pid:
            continue
        out.append(_checkpoint_event(
            f"Studio {project.get('title') or pid}",
            domain="studio",
            event_type="SYSTEM",
            truth_state="CONFIRMED",
            source_ref=f"checkpoint:studio:{pid}",
            claim_key=f"studio.{pid}.status",
            value_summary=str(project.get("status") or "UNKNOWN"),
            evidence_refs=[f"studio_digest:{studio_digest}"] if studio_digest else [],
            observed_at=project.get("updated_at") or project.get("created_at"),
        ))

    business=cp.get("business") if isinstance(cp.get("business"),Mapping) else {}
    business_digest=_clean(business.get("digest"),120)
    for product in list(business.get("products",[]) or [])[-200:]:
        if not isinstance(product,Mapping):
            continue
        pid=_clean(product.get("product_id"),100)
        if not pid:
            continue
        out.append(_checkpoint_event(
            f"Produto {product.get('name') or pid}",
            domain="business",
            event_type="HYPOTHESIS",
            truth_state="INFERENCE" if product.get("evidence_refs") else "UNKNOWN",
            source_ref=f"checkpoint:business:{pid}",
            claim_key=f"business.{pid}.candidate",
            value_summary=str(product.get("status") or "CANDIDATE"),
            evidence_refs=(
                list(product.get("evidence_refs") or [])
                + ([f"business_digest:{business_digest}"] if business_digest else [])
            ),
            observed_at=product.get("updated_at") or product.get("created_at"),
        ))

    learning=cp.get("learning") if isinstance(cp.get("learning"),Mapping) else {}
    learning_digest=_clean(learning.get("digest"),120)
    for episode in list(learning.get("episodes",[]) or [])[-300:]:
        if not isinstance(episode,Mapping) or str(episode.get("state") or "").upper()!="SETTLED":
            continue
        eid=_clean(episode.get("episode_id"),100)
        if not eid:
            continue
        refs=list(episode.get("evidence_refs") or [])
        out.append(_checkpoint_event(
            f"Resultado {episode.get('subject') or eid}",
            domain=episode.get("domain") or "trading",
            event_type="OUTCOME",
            truth_state="INFERENCE" if refs else "UNKNOWN",
            source_ref=f"checkpoint:learning:{eid}",
            claim_key=f"learning.{eid}.outcome",
            value_summary=str(episode.get("actual_outcome") or episode.get("evaluation") or "UNKNOWN"),
            evidence_refs=refs+([f"learning_digest:{learning_digest}"] if learning_digest else []),
            observed_at=episode.get("settled_at") or episode.get("created_at"),
        ))

    journal=cp.get("live_event_journal") if isinstance(cp.get("live_event_journal"),Mapping) else {}
    journal_digest=_clean(journal.get("digest"),120)
    for event in list(journal.get("events",[]) or [])[-300:]:
        if not isinstance(event,Mapping):
            continue
        eid=_clean(event.get("event_id"),100)
        if not eid:
            continue
        out.append(_checkpoint_event(
            event.get("headline") or eid,
            domain="trading",
            event_type="OBSERVATION",
            truth_state=event.get("truth_state") or "UNKNOWN",
            source_ref=f"checkpoint:live_event:{eid}",
            claim_key=f"live_event.{eid}",
            value_summary=str(event.get("category") or event.get("kind") or "EVENT"),
            evidence_refs=list(event.get("sources") or [])+([f"journal_digest:{journal_digest}"] if journal_digest else []),
            observed_at=event.get("last_seen_at") or event.get("reported_at"),
        ))

    twins=cp.get("digital_twins") if isinstance(cp.get("digital_twins"),Mapping) else {}
    twins_digest=_clean(twins.get("digest"),120)
    for twin in list(twins.get("records",[]) or [])[-120:]:
        if not isinstance(twin,Mapping):
            continue
        tid=_clean(twin.get("twin_id"),100)
        if not tid:
            continue
        out.append(_checkpoint_event(
            f"Digital Twin {twin.get('title') or tid}",
            domain="development",
            event_type="TEST",
            truth_state="CONFIRMED",
            source_ref=f"checkpoint:digital_twin:{tid}",
            claim_key=f"development.{tid}.state",
            value_summary=str(twin.get("state") or "UNKNOWN"),
            evidence_refs=[f"digital_twins_digest:{twins_digest}"] if twins_digest else [],
            observed_at=twin.get("updated_at") or twin.get("created_at"),
        ))

    return normalize_fabric_events(out)


def default_data_decision_fabric()->dict[str,Any]:
    events=[]
    decisions=[]
    return {
        "schema":SCHEMA,
        "policy":fabric_policy(),
        "events":events,
        "decisions":decisions,
        "cursor":{"revision":0,"last_event_id":"","updated_at":""},
        "digest":data_decision_fabric_digest(events,decisions),
        "automatic_execution":False,
        "real_trading_enabled":False,
    }


def normalize_data_decision_fabric(raw:Mapping[str,Any]|None)->dict[str,Any]:
    item=dict(raw or {})
    events=normalize_fabric_events(
        item.get("events") if isinstance(item.get("events"),(list,tuple)) else []
    )
    decisions=normalize_decision_cases(
        item.get("decisions") if isinstance(item.get("decisions"),(list,tuple)) else []
    )
    cursor=item.get("cursor") if isinstance(item.get("cursor"),Mapping) else {}
    revision=max(0,int(_finite(cursor.get("revision")) or 0))
    return {
        "schema":SCHEMA,
        "policy":fabric_policy(),
        "events":events,
        "decisions":decisions,
        "cursor":{
            "revision":revision,
            "last_event_id":_clean(cursor.get("last_event_id"),100),
            "updated_at":_clean(cursor.get("updated_at"),100),
        },
        "digest":data_decision_fabric_digest(events,decisions),
        "automatic_execution":False,
        "real_trading_enabled":False,
    }


def data_decision_fabric_digest(
    events:Sequence[Mapping[str,Any]]|None,
    decisions:Sequence[Mapping[str,Any]]|None,
)->str:
    return _stable({
        "events":normalize_fabric_events(events),
        "decisions":normalize_decision_cases(decisions),
        "policy":fabric_policy(),
    })


def data_decision_fabric_summary(
    raw:Mapping[str,Any]|None,
    *,
    derived_events:Sequence[Mapping[str,Any]]|None=None,
)->dict[str,Any]:
    state=normalize_data_decision_fabric(raw)
    events=merge_fabric_events(state["events"],derived_events or [])
    active=active_fabric_events(events)
    conflicts=detect_fabric_conflicts(active)
    decisions=state["decisions"]
    by_domain={domain:0 for domain in DOMAINS}
    by_truth={truth:0 for truth in TRUTH_STATES}
    for event in active:
        by_domain[event["domain"]]=by_domain.get(event["domain"],0)+1
        by_truth[event["truth_state"]]=by_truth.get(event["truth_state"],0)+1
    return {
        "schema":SCHEMA,
        "persisted_events":len(state["events"]),
        "derived_events":len(list(derived_events or [])),
        "active_events":len(active),
        "conflicts":len(conflicts),
        "decisions":len(decisions),
        "human_review_candidates":sum(1 for x in decisions if x["state"]=="HUMAN_REVIEW_CANDIDATE"),
        "blocked_decisions":sum(1 for x in decisions if x["state"]=="BLOCKED"),
        "research_required":sum(1 for x in decisions if x["state"]=="RESEARCH_REQUIRED"),
        "by_domain":by_domain,
        "by_truth_state":by_truth,
        "automatic_execution":False,
        "real_trading_enabled":False,
        "digest":state["digest"],
    }


__all__=[
    "SCHEMA","DOMAINS","EVENT_TYPES","TRUTH_STATES","RISK_LEVELS",
    "DECISION_STATES","PRIVACY_CLASSES","fabric_policy","new_fabric_event",
    "normalize_fabric_event","normalize_fabric_events","merge_fabric_events",
    "event_is_expired","active_fabric_events","detect_fabric_conflicts",
    "new_decision_case","normalize_decision_case","normalize_decision_cases",
    "evaluate_decision_case","record_decision_outcome","upsert_decision_case",
    "derive_checkpoint_fabric_events","default_data_decision_fabric",
    "normalize_data_decision_fabric","data_decision_fabric_digest",
    "data_decision_fabric_summary",
]
