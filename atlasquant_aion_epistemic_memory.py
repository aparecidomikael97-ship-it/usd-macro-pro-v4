"""AION Epistemic Memory & Reliability Core.

A reliability layer over AION memory. It does not attempt to duplicate every
stored document. Instead, it records provenance/version/evidence metadata for
decision-relevant memories, detects stale/conflicting/superseded knowledge and
builds auditable decision-replay manifests.

"Confidence" here means evidence/knowledge quality, never trading-profit
probability. This module never changes strategy rules, executes tools, deploys,
publishes, pays, or trades.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Mapping, Sequence
import json
import math

SCHEMA="ATLASQUANT_AION_EPISTEMIC_MEMORY_V1"
MAX_RECORDS=5000
MAX_REPLAYS=2000

MEMORY_LAYERS=("WORKING","EPISODIC","SEMANTIC","PROCEDURAL","DECISION_LEDGER")
TRUTH_STATES=("CONFIRMED","INFERENCE","HYPOTHESIS","UNKNOWN")
RELIABILITY_STATES=(
    "TRUSTED","USABLE_WITH_CAUTION","STALE","CONFLICTED",
    "SUPERSEDED","INSUFFICIENT_EVIDENCE","UNKNOWN",
)
EPISTEMIC_STATES=("KNOWN","PARTIALLY_KNOWN","UNKNOWN","CONFLICTED","STALE")
GATE_STATES=("SAFE_TO_USE","VERIFY_FIRST","RESEARCH_REQUIRED","BLOCK_SENSITIVE")


def _now()->str:
    return datetime.now(timezone.utc).isoformat()


def _clean(value:Any,limit:int=1600)->str:
    return " ".join(str(value or "").replace("\x00","").split())[:limit]


def _upper(value:Any,limit:int=80)->str:
    return _clean(value,limit).upper()


def _refs(values:Sequence[Any]|None,limit:int=100)->list[str]:
    out=[]
    for raw in list(values or [])[:limit*2]:
        text=_clean(raw,300)
        if text and text not in out:
            out.append(text)
        if len(out)>=limit:
            break
    return out


def _digest(value:Any,length:int=24)->str:
    raw=json.dumps(value,ensure_ascii=False,sort_keys=True,default=str)
    return sha256(raw.encode("utf-8")).hexdigest()[:length]


def _parse_time(value:Any)->datetime|None:
    raw=_clean(value,100)
    if not raw:
        return None
    try:
        dt=datetime.fromisoformat(raw.replace("Z","+00:00"))
        if dt.tzinfo is None:
            dt=dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def _truth(value:Any)->str:
    state=_upper(value,40)
    return state if state in TRUTH_STATES else "UNKNOWN"


def _layer(value:Any)->str:
    layer=_upper(value,40)
    return layer if layer in MEMORY_LAYERS else "SEMANTIC"


def memory_layer_catalog()->list[dict[str,Any]]:
    return [
        {"layer":"WORKING","purpose":"Estado ativo, tarefas e contexto de execução.","automatic_authority":False},
        {"layer":"EPISODIC","purpose":"Eventos, experiências e resultados observados.","automatic_authority":False},
        {"layer":"SEMANTIC","purpose":"Conhecimento revisado, Wisdom e relações explícitas.","automatic_authority":False},
        {"layer":"PROCEDURAL","purpose":"Procedimentos e regras aprovadas/versionadas.","automatic_authority":False},
        {"layer":"DECISION_LEDGER","purpose":"Replay auditável de decisões e evidências usadas.","automatic_authority":False},
    ]


def new_memory_record(
    subject:Any,
    claim:Any,
    *,
    layer:Any="SEMANTIC",
    truth_state:Any="UNKNOWN",
    source_ref:Any="",
    source_version:Any="",
    evidence_refs:Sequence[Any]|None=None,
    observed_at:Any="",
    valid_until:Any="",
    review_due_at:Any="",
    supersedes:Sequence[Any]|None=None,
    created_at:str|None=None,
)->dict[str,Any]:
    subject_text=_clean(subject,300)
    claim_text=_clean(claim,1600)
    if not subject_text or not claim_text:
        raise ValueError("memory subject and claim required")
    truth=_truth(truth_state)
    refs=_refs(evidence_refs)
    source=_clean(source_ref,300)
    version=_clean(source_version,180)
    if truth=="CONFIRMED" and (not refs or not source or not version):
        raise ValueError("confirmed memory requires evidence, source and source version")
    for raw_time in (observed_at,valid_until,review_due_at):
        if _clean(raw_time,100) and _parse_time(raw_time) is None:
            raise ValueError("invalid memory timestamp")
    created=str(created_at or _now())
    payload={
        "subject":subject_text,
        "claim":claim_text,
        "layer":_layer(layer),
        "source_ref":source,
        "source_version":version,
        "created_at":created,
    }
    return {
        "schema":SCHEMA,
        "memory_id":"MEM-"+_digest(payload,16).upper(),
        "layer":_layer(layer),
        "subject":subject_text,
        "claim":claim_text,
        "claim_digest":_digest(claim_text,20),
        "truth_state":truth,
        "source_ref":source,
        "source_version":version,
        "evidence_refs":refs,
        "observed_at":_clean(observed_at,100),
        "valid_until":_clean(valid_until,100),
        "review_due_at":_clean(review_due_at,100),
        "supersedes":_refs(supersedes,50),
        "created_at":created,
        "automatic_authority":False,
        "automatic_rule_change":False,
        "real_trading_enabled":False,
    }


def normalize_memory_record(raw:Mapping[str,Any])->dict[str,Any]:
    item=dict(raw or {})
    subject=_clean(item.get("subject"),300)
    claim=_clean(item.get("claim"),1600)
    if not subject or not claim:
        raise ValueError("memory subject and claim required")
    truth=_truth(item.get("truth_state"))
    refs=_refs(item.get("evidence_refs") if isinstance(item.get("evidence_refs"),(list,tuple)) else [])
    source=_clean(item.get("source_ref"),300)
    version=_clean(item.get("source_version"),180)
    # A persisted CONFIRMED label without evidence/version is downgraded,
    # never trusted as confirmed merely because the JSON says so.
    if truth=="CONFIRMED" and (not refs or not source or not version):
        truth="UNKNOWN"
    created=_clean(item.get("created_at"),100)
    base=new_memory_record(
        subject,claim,
        layer=item.get("layer"),
        truth_state=truth,
        source_ref=source,
        source_version=version,
        evidence_refs=refs,
        observed_at=item.get("observed_at") if _parse_time(item.get("observed_at")) else "",
        valid_until=item.get("valid_until") if _parse_time(item.get("valid_until")) else "",
        review_due_at=item.get("review_due_at") if _parse_time(item.get("review_due_at")) else "",
        supersedes=item.get("supersedes") if isinstance(item.get("supersedes"),(list,tuple)) else [],
        created_at=created or "UNKNOWN",
    )
    supplied=_clean(item.get("memory_id"),120)
    if supplied:
        base["memory_id"]=supplied
    return base


def normalize_memory_records(rows:Sequence[Mapping[str,Any]]|None)->list[dict[str,Any]]:
    out=[]
    seen=set()
    for raw in list(rows or [])[-MAX_RECORDS*2:]:
        if not isinstance(raw,Mapping):
            continue
        try:
            item=normalize_memory_record(raw)
        except Exception:
            continue
        mid=item["memory_id"]
        if mid in seen:
            continue
        seen.add(mid)
        out.append(item)
    return out[-MAX_RECORDS:]


def assess_memory_record(
    record:Mapping[str,Any],
    *,
    now:Any=None,
    superseded_by:Sequence[Any]|None=None,
    conflicted:bool=False,
)->dict[str,Any]:
    item=normalize_memory_record(record)
    now_dt=_parse_time(now) if now else datetime.now(timezone.utc)
    if now_dt is None:
        now_dt=datetime.now(timezone.utc)
    blockers=[]
    cautions=[]
    superseders=_refs(superseded_by,50)

    valid_until=_parse_time(item.get("valid_until"))
    review_due=_parse_time(item.get("review_due_at"))
    stale=bool(
        (valid_until is not None and now_dt>valid_until)
        or (review_due is not None and now_dt>review_due)
    )

    if superseders:
        state="SUPERSEDED"
        blockers.append("SUPERSEDED_BY_NEWER_MEMORY")
    elif conflicted:
        state="CONFLICTED"
        blockers.append("CONFIRMED_CONFLICT")
    elif stale:
        state="STALE"
        blockers.append("FRESHNESS_REVIEW_REQUIRED")
    elif item["truth_state"]=="CONFIRMED":
        if item["evidence_refs"] and item["source_ref"] and item["source_version"]:
            state="TRUSTED"
        else:
            state="INSUFFICIENT_EVIDENCE"
            blockers.append("CONFIRMED_METADATA_INCOMPLETE")
    elif item["truth_state"] in {"INFERENCE","HYPOTHESIS"}:
        state="USABLE_WITH_CAUTION"
        cautions.append(f"TRUTH_STATE_{item['truth_state']}")
    else:
        state="UNKNOWN"
        blockers.append("TRUTH_UNKNOWN")

    return {
        "schema":SCHEMA,
        "memory_id":item["memory_id"],
        "subject":item["subject"],
        "reliability_state":state,
        "truth_state":item["truth_state"],
        "source_ref":item["source_ref"],
        "source_version":item["source_version"],
        "evidence_count":len(item["evidence_refs"]),
        "stale":stale,
        "superseded_by":superseders,
        "conflicted":bool(conflicted),
        "blockers":blockers,
        "cautions":cautions,
        "knowledge_confidence_meaning":"EVIDENCE_QUALITY_NOT_PROFIT_PROBABILITY",
        "safe_for_sensitive_decision":state=="TRUSTED",
        "executes_action":False,
    }


def reconcile_memory_subject(
    records:Sequence[Mapping[str,Any]]|None,
    subject:Any,
    *,
    now:Any=None,
)->dict[str,Any]:
    target=_clean(subject,300).casefold()
    rows=[x for x in normalize_memory_records(records) if x["subject"].casefold()==target]
    ids={x["memory_id"] for x in rows}
    superseded_by={mid:[] for mid in ids}
    for item in rows:
        for prior in item["supersedes"]:
            if prior in superseded_by and item["memory_id"]!=prior:
                superseded_by[prior].append(item["memory_id"])

    current=[x for x in rows if not superseded_by.get(x["memory_id"])]
    confirmed_current=[x for x in current if x["truth_state"]=="CONFIRMED"]
    distinct_claims={x["claim_digest"] for x in confirmed_current}
    conflict=len(distinct_claims)>1

    assessments=[]
    for item in rows:
        assessments.append(assess_memory_record(
            item,
            now=now,
            superseded_by=superseded_by.get(item["memory_id"],[]),
            conflicted=bool(conflict and item in confirmed_current),
        ))

    if conflict:
        state="CONFLICTED"
    elif not rows:
        state="UNKNOWN"
    elif any(x["reliability_state"]=="TRUSTED" for x in assessments):
        state="KNOWN"
    elif any(x["reliability_state"]=="USABLE_WITH_CAUTION" for x in assessments):
        state="PARTIALLY_KNOWN"
    elif any(x["reliability_state"]=="STALE" for x in assessments):
        state="STALE"
    else:
        state="UNKNOWN"

    return {
        "schema":SCHEMA,
        "subject":_clean(subject,300),
        "epistemic_state":state,
        "records":len(rows),
        "current_records":len(current),
        "conflict":conflict,
        "assessments":assessments,
        "automatic_conflict_resolution":False,
        "executes_action":False,
    }


def epistemic_gate(
    subject_states:Sequence[Mapping[str,Any]]|None,
    *,
    sensitive:bool=False,
)->dict[str,Any]:
    rows=[dict(x) for x in list(subject_states or []) if isinstance(x,Mapping)]
    states=[_upper(x.get("epistemic_state"),40) for x in rows]
    blockers=[]
    actions=[]

    if not rows or any(x=="UNKNOWN" for x in states):
        actions.append("RESEARCH_OR_VERIFY")
    if any(x=="CONFLICTED" for x in states):
        blockers.append("MEMORY_CONFLICT")
        actions.append("RESOLVE_CONFLICT_WITH_EVIDENCE")
    if any(x=="STALE" for x in states):
        blockers.append("STALE_MEMORY")
        actions.append("REFRESH_EVIDENCE")
    if any(x=="PARTIALLY_KNOWN" for x in states):
        actions.append("VERIFY_INFERENCE_BEFORE_SENSITIVE_USE")

    all_known=bool(rows) and all(x=="KNOWN" for x in states)
    if sensitive and (blockers or not all_known):
        gate="BLOCK_SENSITIVE"
    elif blockers:
        gate="VERIFY_FIRST"
    elif all_known:
        gate="SAFE_TO_USE"
    elif rows:
        gate="VERIFY_FIRST"
    else:
        gate="RESEARCH_REQUIRED"

    return {
        "schema":SCHEMA,
        "state":gate,
        "sensitive":bool(sensitive),
        "subjects":len(rows),
        "epistemic_states":states,
        "blockers":list(dict.fromkeys(blockers)),
        "required_actions":list(dict.fromkeys(actions)),
        "grants_permission":False,
        "executes_action":False,
        "real_trading_enabled":False,
    }


def new_decision_replay(
    decision_id:Any,
    *,
    decided_at:Any,
    domain:Any,
    decision_summary:Any,
    model_version:Any,
    rule_version:Any="",
    memory_record_ids:Sequence[Any]|None=None,
    evidence_refs:Sequence[Any]|None=None,
    data_snapshot_refs:Sequence[Any]|None=None,
    context_digest:Any="",
    created_at:str|None=None,
)->dict[str,Any]:
    did=_clean(decision_id,160)
    summary=_clean(decision_summary,1600)
    decided=_clean(decided_at,100)
    if not did or not summary or _parse_time(decided) is None:
        raise ValueError("decision replay requires id, summary and valid decided_at")
    memories=_refs(memory_record_ids,200)
    evidence=_refs(evidence_refs,200)
    snapshots=_refs(data_snapshot_refs,200)
    blockers=[]
    if not memories:
        blockers.append("MEMORY_REFS_MISSING")
    if not evidence:
        blockers.append("EVIDENCE_REFS_MISSING")
    if not snapshots:
        blockers.append("DATA_SNAPSHOT_REFS_MISSING")
    if not _clean(model_version,160):
        blockers.append("MODEL_VERSION_MISSING")

    payload={
        "decision_id":did,
        "decided_at":decided,
        "memory_record_ids":memories,
        "evidence_refs":evidence,
        "data_snapshot_refs":snapshots,
        "model_version":_clean(model_version,160),
        "rule_version":_clean(rule_version,160),
        "context_digest":_clean(context_digest,160),
    }
    return {
        "schema":SCHEMA,
        "replay_id":"REPLAY-"+_digest(payload,16).upper(),
        "decision_id":did,
        "decided_at":decided,
        "domain":_clean(domain,100).lower() or "general",
        "decision_summary":summary,
        "model_version":_clean(model_version,160),
        "rule_version":_clean(rule_version,160),
        "memory_record_ids":memories,
        "evidence_refs":evidence,
        "data_snapshot_refs":snapshots,
        "context_digest":_clean(context_digest,160),
        "state":"COMPLETE_REFERENCE_SET" if not blockers else "INCOMPLETE_REFERENCE_SET",
        "blockers":blockers,
        "created_at":str(created_at or _now()),
        "reconstructs_only_recorded_state":True,
        "invent_missing_context":False,
        "executes_action":False,
        "real_trading_enabled":False,
    }


def normalize_decision_replay(raw:Mapping[str,Any])->dict[str,Any]:
    item=dict(raw or {})
    replay=new_decision_replay(
        item.get("decision_id"),
        decided_at=item.get("decided_at"),
        domain=item.get("domain"),
        decision_summary=item.get("decision_summary"),
        model_version=item.get("model_version"),
        rule_version=item.get("rule_version"),
        memory_record_ids=item.get("memory_record_ids") if isinstance(item.get("memory_record_ids"),(list,tuple)) else [],
        evidence_refs=item.get("evidence_refs") if isinstance(item.get("evidence_refs"),(list,tuple)) else [],
        data_snapshot_refs=item.get("data_snapshot_refs") if isinstance(item.get("data_snapshot_refs"),(list,tuple)) else [],
        context_digest=item.get("context_digest"),
        created_at=_clean(item.get("created_at"),100) or "UNKNOWN",
    )
    supplied=_clean(item.get("replay_id"),120)
    if supplied:
        replay["replay_id"]=supplied
    return replay


def normalize_decision_replays(rows:Sequence[Mapping[str,Any]]|None)->list[dict[str,Any]]:
    out=[]
    seen=set()
    for raw in list(rows or [])[-MAX_REPLAYS*2:]:
        if not isinstance(raw,Mapping):
            continue
        try:
            item=normalize_decision_replay(raw)
        except Exception:
            continue
        rid=item["replay_id"]
        if rid in seen:
            continue
        seen.add(rid)
        out.append(item)
    return out[-MAX_REPLAYS:]


def epistemic_memory_digest(
    records:Sequence[Mapping[str,Any]]|None,
    replays:Sequence[Mapping[str,Any]]|None,
)->str:
    return _digest({
        "records":normalize_memory_records(records),
        "decision_replays":normalize_decision_replays(replays),
    })


def default_epistemic_memory()->dict[str,Any]:
    records=[]
    replays=[]
    return {
        "schema":SCHEMA,
        "layers":memory_layer_catalog(),
        "records":records,
        "decision_replays":replays,
        "digest":epistemic_memory_digest(records,replays),
        "automatic_truth_promotion":False,
        "automatic_conflict_resolution":False,
        "photographic_memory_claimed":False,
        "real_trading_enabled":False,
    }


def normalize_epistemic_memory(raw:Mapping[str,Any]|None)->dict[str,Any]:
    item=dict(raw or {})
    records=normalize_memory_records(item.get("records") if isinstance(item.get("records"),(list,tuple)) else [])
    replays=normalize_decision_replays(item.get("decision_replays") if isinstance(item.get("decision_replays"),(list,tuple)) else [])
    return {
        "schema":SCHEMA,
        "layers":memory_layer_catalog(),
        "records":records,
        "decision_replays":replays,
        "digest":epistemic_memory_digest(records,replays),
        "automatic_truth_promotion":False,
        "automatic_conflict_resolution":False,
        "photographic_memory_claimed":False,
        "real_trading_enabled":False,
    }


def epistemic_memory_summary(raw:Mapping[str,Any]|None,*,now:Any=None)->dict[str,Any]:
    state=normalize_epistemic_memory(raw)
    records=state["records"]
    replays=state["decision_replays"]
    assessments=[assess_memory_record(x,now=now) for x in records]
    return {
        "schema":SCHEMA,
        "records":len(records),
        "trusted":sum(1 for x in assessments if x["reliability_state"]=="TRUSTED"),
        "stale":sum(1 for x in assessments if x["reliability_state"]=="STALE"),
        "insufficient_or_unknown":sum(1 for x in assessments if x["reliability_state"] in {"INSUFFICIENT_EVIDENCE","UNKNOWN"}),
        "decision_replays":len(replays),
        "complete_replays":sum(1 for x in replays if x["state"]=="COMPLETE_REFERENCE_SET"),
        "automatic_conflict_resolution":False,
        "photographic_memory_claimed":False,
        "real_trading_enabled":False,
        "digest":state["digest"],
    }


__all__=[
    "SCHEMA","MEMORY_LAYERS","TRUTH_STATES","RELIABILITY_STATES",
    "EPISTEMIC_STATES","GATE_STATES","memory_layer_catalog","new_memory_record",
    "normalize_memory_record","normalize_memory_records","assess_memory_record",
    "reconcile_memory_subject","epistemic_gate","new_decision_replay",
    "normalize_decision_replay","normalize_decision_replays",
    "epistemic_memory_digest","default_epistemic_memory",
    "normalize_epistemic_memory","epistemic_memory_summary",
]
