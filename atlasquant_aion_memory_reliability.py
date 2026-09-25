"""AION Memory Reliability + Epistemic Core.

Deterministic memory-quality contracts. This layer decides whether a memory may
be used as current evidence, caveated context, or must be reverified. It never
executes tools, expands permissions, deploys, publishes or enables real trading.

The Epistemic Core answers a narrower question than the model: "what is actually
supported by the evidence available right now?" It can reduce confidence or
require research, but it never grants action authority.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Mapping, Sequence
import json
import math

SCHEMA="ATLASQUANT_AION_MEMORY_RELIABILITY_V1"
MAX_REVIEWS=1000
MAX_SNAPSHOTS=500

MEMORY_KINDS=(
    "WORKING","EPISODIC","SEMANTIC","PROCEDURAL","DECISION","EVIDENCE",
)
TRUTH_STATES=("CONFIRMED","INFERENCE","HYPOTHESIS","UNKNOWN")
REVIEW_STATES=("CURRENT","EXPIRED","CONFLICT","SUPERSEDED","VERIFY_REQUIRED")
GATE_STATES=("ELIGIBLE","CONTEXT_ONLY","STALE_CONTEXT_ONLY","VERIFY_REQUIRED","BLOCKED")
EPISTEMIC_STATES=("SUPPORTED","PARTIAL","RESEARCH_REQUIRED","VERIFY_REQUIRED","CONFLICT","INSUFFICIENT_EVIDENCE")


def _now()->str:
    return datetime.now(timezone.utc).isoformat()


def _clean(value:Any,limit:int=1400)->str:
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


def _pct(value:Any)->float|None:
    try:
        x=float(value)
        if math.isfinite(x) and 0.0<=x<=100.0:
            return round(x,2)
    except Exception:
        pass
    return None


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


def _stable(value:Any,length:int=24)->str:
    raw=json.dumps(value,ensure_ascii=False,sort_keys=True,default=str)
    return sha256(raw.encode("utf-8")).hexdigest()[:length]


def memory_reliability_policy()->dict[str,Any]:
    return {
        "schema":SCHEMA,
        "confirmed_requires_provenance":True,
        "confirmed_requires_content_digest":True,
        "contradiction_fails_closed":True,
        "superseded_memory_blocked":True,
        "expired_confirmed_downgrades_to":"INFERENCE",
        "sensitive_action_requires_current_confirmed":True,
        "memory_never_authorizes_action":True,
        "memory_never_expands_permissions":True,
        "historical_memory_never_confirms_live_market":True,
        "automatic_rule_change":False,
        "real_trading_enabled":False,
    }


def _review_base(raw:Mapping[str,Any])->dict[str,Any]:
    item=dict(raw or {})
    ref=_clean(item.get("memory_ref"),220)
    if not ref:
        raise ValueError("memory_ref required")
    kind=_upper(item.get("memory_kind") or "SEMANTIC")
    if kind not in MEMORY_KINDS:
        kind="SEMANTIC"
    truth=_upper(item.get("truth_state") or "UNKNOWN")
    if truth not in TRUTH_STATES:
        truth="UNKNOWN"
    return {
        "memory_ref":ref,
        "memory_kind":kind,
        "version":_clean(item.get("version"),120),
        "truth_state":truth,
        "source_refs":_refs(item.get("source_refs") if isinstance(item.get("source_refs"),(list,tuple)) else []),
        "evidence_refs":_refs(item.get("evidence_refs") if isinstance(item.get("evidence_refs"),(list,tuple)) else []),
        "content_digest":_clean(item.get("content_digest"),160),
        "observed_at":_clean(item.get("observed_at"),100),
        "reviewed_at":_clean(item.get("reviewed_at"),100),
        "valid_until":_clean(item.get("valid_until"),100),
        "contradiction_refs":_refs(item.get("contradiction_refs") if isinstance(item.get("contradiction_refs"),(list,tuple)) else []),
        "superseded_by":_clean(item.get("superseded_by"),220),
        "knowledge_confidence_pct":_pct(item.get("knowledge_confidence_pct")),
        "reviewer":_clean(item.get("reviewer"),160),
        "note":_clean(item.get("note"),900),
        "knowledge_confidence_is_profit_probability":False,
        "executes_action":False,
        "real_trading_enabled":False,
    }


def evaluate_memory_review(
    raw:Mapping[str,Any],
    *,
    now:Any=None,
)->dict[str,Any]:
    item=_review_base(raw)
    now_dt=_dt(now) if now is not None else datetime.now(timezone.utc)
    if now_dt is None:
        now_dt=datetime.now(timezone.utc)

    provenance_ok=bool(item["source_refs"] or item["evidence_refs"])
    digest_ok=bool(item["content_digest"])
    expiry=_dt(item["valid_until"])
    expired=bool(expiry is not None and now_dt>expiry)

    if item["contradiction_refs"]:
        state="CONFLICT"
        effective_truth="UNKNOWN"
        reason="CONTRADICTION_PRESENT"
    elif item["superseded_by"]:
        state="SUPERSEDED"
        effective_truth="UNKNOWN"
        reason="SUPERSEDED_MEMORY"
    elif item["truth_state"]=="CONFIRMED" and (not provenance_ok or not digest_ok):
        state="VERIFY_REQUIRED"
        effective_truth="UNKNOWN"
        reason="CONFIRMED_WITHOUT_PROVENANCE_OR_DIGEST"
    elif item["truth_state"]=="UNKNOWN":
        state="VERIFY_REQUIRED"
        effective_truth="UNKNOWN"
        reason="TRUTH_UNKNOWN"
    elif expired:
        state="EXPIRED"
        effective_truth="INFERENCE" if item["truth_state"]=="CONFIRMED" else item["truth_state"]
        reason="VALIDITY_EXPIRED"
    else:
        state="CURRENT"
        effective_truth=item["truth_state"]
        reason="CURRENT_WITH_PROVENANCE" if provenance_ok and digest_ok else "CURRENT_NONCONFIRMED_CONTEXT"

    item.update({
        "review_state":state,
        "effective_truth_state":effective_truth,
        "provenance_ok":provenance_ok,
        "content_integrity_ref_present":digest_ok,
        "expired":expired,
        "reason":reason,
        "review_evaluated_at":now_dt.isoformat(),
        "action_authorized":False,
        "may_expand_permissions":False,
    })
    return item


def new_memory_review(
    memory_ref:Any,
    *,
    memory_kind:Any="SEMANTIC",
    version:Any="",
    truth_state:Any="UNKNOWN",
    source_refs:Sequence[Any]|None=None,
    evidence_refs:Sequence[Any]|None=None,
    content_digest:Any="",
    observed_at:Any="",
    reviewed_at:Any="",
    valid_until:Any="",
    contradiction_refs:Sequence[Any]|None=None,
    superseded_by:Any="",
    knowledge_confidence_pct:Any=None,
    reviewer:Any="",
    note:Any="",
    now:Any=None,
)->dict[str,Any]:
    return evaluate_memory_review({
        "memory_ref":memory_ref,
        "memory_kind":memory_kind,
        "version":version,
        "truth_state":truth_state,
        "source_refs":source_refs or [],
        "evidence_refs":evidence_refs or [],
        "content_digest":content_digest,
        "observed_at":observed_at,
        "reviewed_at":reviewed_at,
        "valid_until":valid_until,
        "contradiction_refs":contradiction_refs or [],
        "superseded_by":superseded_by,
        "knowledge_confidence_pct":knowledge_confidence_pct,
        "reviewer":reviewer,
        "note":note,
    },now=now)


def normalize_memory_reviews(rows:Sequence[Mapping[str,Any]]|None)->list[dict[str,Any]]:
    out=[]
    seen=set()
    for raw in list(rows or [])[-MAX_REVIEWS*2:]:
        if not isinstance(raw,Mapping):
            continue
        try:
            item=evaluate_memory_review(raw)
        except Exception:
            continue
        ref=item["memory_ref"]
        if ref in seen:
            # Keep the most recent occurrence supplied by caller.
            out=[x for x in out if x["memory_ref"]!=ref]
        seen.add(ref)
        out.append(item)
    return out[-MAX_REVIEWS:]


def memory_retrieval_gate(
    raw:Mapping[str,Any],
    *,
    sensitive_action:bool=False,
    now:Any=None,
)->dict[str,Any]:
    review=evaluate_memory_review(raw,now=now)
    state=review["review_state"]
    truth=review["effective_truth_state"]

    if state in {"CONFLICT","SUPERSEDED"}:
        gate="BLOCKED"
        context_eligible=False
    elif state=="VERIFY_REQUIRED":
        gate="VERIFY_REQUIRED"
        context_eligible=False
    elif state=="EXPIRED":
        gate="VERIFY_REQUIRED" if sensitive_action else "STALE_CONTEXT_ONLY"
        context_eligible=not sensitive_action
    elif truth=="CONFIRMED":
        gate="ELIGIBLE"
        context_eligible=True
    else:
        gate="VERIFY_REQUIRED" if sensitive_action else "CONTEXT_ONLY"
        context_eligible=not sensitive_action

    sensitive_support=bool(
        gate=="ELIGIBLE"
        and state=="CURRENT"
        and truth=="CONFIRMED"
        and review["provenance_ok"]
        and review["content_integrity_ref_present"]
    )
    return {
        "schema":SCHEMA,
        "memory_ref":review["memory_ref"],
        "gate_state":gate,
        "review_state":state,
        "effective_truth_state":truth,
        "context_eligible":context_eligible,
        "can_support_sensitive_action":sensitive_support,
        "requires_reverification":gate in {"VERIFY_REQUIRED","STALE_CONTEXT_ONLY"},
        "reason":review["reason"],
        "action_authorized":False,
        "may_expand_permissions":False,
        "real_trading_enabled":False,
    }


def new_decision_snapshot(
    decision_ref:Any,
    *,
    domain:Any,
    conclusion:Any,
    context_refs:Sequence[Any]|None=None,
    evidence_refs:Sequence[Any]|None=None,
    checklist:Sequence[Any]|None=None,
    regime:Any="",
    thesis:Any="",
    stop:Any="",
    target:Any="",
    model_version:Any="",
    truth_state:Any="UNKNOWN",
    data_as_of:Any="",
    created_at:Any="",
)->dict[str,Any]:
    ref=_clean(decision_ref,220)
    if not ref:
        raise ValueError("decision_ref required")
    truth=_upper(truth_state)
    if truth not in TRUTH_STATES:
        truth="UNKNOWN"
    created=_clean(created_at,100) or _now()
    payload={
        "decision_ref":ref,
        "domain":_clean(domain,100).lower() or "central",
        "conclusion":_clean(conclusion,1800),
        "context_refs":_refs(context_refs,120),
        "evidence_refs":_refs(evidence_refs,120),
        "checklist":_refs(checklist,120),
        "regime":_clean(regime,500),
        "thesis":_clean(thesis,1800),
        "stop":_clean(stop,500),
        "target":_clean(target,500),
        "model_version":_clean(model_version,160),
        "truth_state":truth,
        "data_as_of":_clean(data_as_of,100),
        "created_at":created,
        "memory_replay":True,
        "executes_action":False,
        "real_trading_enabled":False,
    }
    payload["context_digest"]=_stable({
        k:v for k,v in payload.items()
        if k not in {"context_digest"}
    })
    payload["evidence_complete"]=bool(payload["evidence_refs"] and payload["conclusion"])
    return payload


def normalize_decision_snapshot(raw:Mapping[str,Any])->dict[str,Any]:
    item=dict(raw or {})
    return new_decision_snapshot(
        item.get("decision_ref"),
        domain=item.get("domain"),
        conclusion=item.get("conclusion"),
        context_refs=item.get("context_refs") if isinstance(item.get("context_refs"),(list,tuple)) else [],
        evidence_refs=item.get("evidence_refs") if isinstance(item.get("evidence_refs"),(list,tuple)) else [],
        checklist=item.get("checklist") if isinstance(item.get("checklist"),(list,tuple)) else [],
        regime=item.get("regime"),
        thesis=item.get("thesis"),
        stop=item.get("stop"),
        target=item.get("target"),
        model_version=item.get("model_version"),
        truth_state=item.get("truth_state"),
        data_as_of=item.get("data_as_of"),
        created_at=item.get("created_at"),
    )


def normalize_decision_snapshots(rows:Sequence[Mapping[str,Any]]|None)->list[dict[str,Any]]:
    out=[]
    seen=set()
    for raw in list(rows or [])[-MAX_SNAPSHOTS*2:]:
        if not isinstance(raw,Mapping):
            continue
        try:
            item=normalize_decision_snapshot(raw)
        except Exception:
            continue
        ref=item["decision_ref"]
        if ref in seen:
            out=[x for x in out if x["decision_ref"]!=ref]
        seen.add(ref)
        out.append(item)
    return out[-MAX_SNAPSHOTS:]


def epistemic_assessment(
    subject:Any,
    reviews:Sequence[Mapping[str,Any]]|None,
    *,
    sensitive_action:bool=False,
    freshness_required:bool=False,
    required_memory_refs:Sequence[Any]|None=None,
    now:Any=None,
)->dict[str,Any]:
    subject_text=_clean(subject,1200)
    evaluated=[]
    gates=[]
    for raw in list(reviews or [])[:200]:
        if not isinstance(raw,Mapping):
            continue
        try:
            review=evaluate_memory_review(raw,now=now)
            gate=memory_retrieval_gate(review,sensitive_action=sensitive_action,now=now)
        except Exception:
            continue
        evaluated.append(review)
        gates.append(gate)

    required=set(_refs(required_memory_refs,200))
    present={x["memory_ref"] for x in evaluated}
    missing=sorted(required-present)
    conflicts=[x["memory_ref"] for x in evaluated if x["review_state"]=="CONFLICT"]
    expired=[x["memory_ref"] for x in evaluated if x["review_state"]=="EXPIRED"]
    verify=[x["memory_ref"] for x in evaluated if x["review_state"]=="VERIFY_REQUIRED"]
    current_confirmed=[
        x["memory_ref"] for x in evaluated
        if x["review_state"]=="CURRENT" and x["effective_truth_state"]=="CONFIRMED"
    ]
    contextual=[
        x["memory_ref"] for x in evaluated
        if x["effective_truth_state"] in {"INFERENCE","HYPOTHESIS"}
    ]

    blockers=[]
    if conflicts:
        blockers.append("MEMORY_CONFLICT")
    if missing:
        blockers.append("REQUIRED_MEMORY_MISSING")
    if freshness_required and not current_confirmed:
        blockers.append("CURRENT_CONFIRMED_EVIDENCE_MISSING")
    if sensitive_action and any(not x["can_support_sensitive_action"] for x in gates):
        blockers.append("SENSITIVE_ACTION_EVIDENCE_NOT_CURRENT_CONFIRMED")
    if verify:
        blockers.append("MEMORY_REVERIFICATION_REQUIRED")
    blockers=list(dict.fromkeys(blockers))

    if conflicts:
        state="CONFLICT"
        answer_mode="STOP_AND_REVIEW"
    elif not evaluated:
        state="INSUFFICIENT_EVIDENCE"
        answer_mode="RESEARCH_FIRST"
    elif missing or verify:
        state="VERIFY_REQUIRED"
        answer_mode="RESEARCH_FIRST"
    elif freshness_required and not current_confirmed:
        state="RESEARCH_REQUIRED"
        answer_mode="RESEARCH_FIRST"
    elif sensitive_action and blockers:
        state="VERIFY_REQUIRED"
        answer_mode="STOP_AND_REVIEW"
    elif current_confirmed:
        state="SUPPORTED"
        answer_mode="EVIDENCE_SUPPORTED"
    elif contextual:
        state="PARTIAL"
        answer_mode="CAVEATED"
    else:
        state="RESEARCH_REQUIRED"
        answer_mode="RESEARCH_FIRST"

    return {
        "schema":SCHEMA,
        "subject":subject_text,
        "state":state,
        "answer_mode":answer_mode,
        "reviewed_memory_count":len(evaluated),
        "current_confirmed_refs":current_confirmed,
        "contextual_refs":contextual,
        "expired_refs":expired,
        "conflict_refs":conflicts,
        "verify_refs":verify,
        "missing_required_refs":missing,
        "blockers":blockers,
        "sensitive_action":bool(sensitive_action),
        "freshness_required":bool(freshness_required),
        "can_support_sensitive_action":bool(
            sensitive_action
            and evaluated
            and not blockers
            and all(x["can_support_sensitive_action"] for x in gates)
        ),
        "action_authorized":False,
        "may_expand_permissions":False,
        "real_trading_enabled":False,
    }


def assess_canonical_memory_hits(
    subject:Any,
    memory_hits:Sequence[Mapping[str,Any]]|None,
)->dict[str,Any]:
    reviews=[]
    for hit in list(memory_hits or [])[:20]:
        if not isinstance(hit,Mapping):
            continue
        path=_clean(hit.get("path"),220)
        digest=_clean(hit.get("sha256"),160)
        if not path:
            continue
        reviews.append(new_memory_review(
            path,
            memory_kind="SEMANTIC",
            version=digest[:16],
            truth_state="CONFIRMED" if digest else "UNKNOWN",
            source_refs=[path],
            evidence_refs=[f"sha256:{digest}"] if digest else [],
            content_digest=digest,
            reviewer="CANONICAL_MEMORY_INDEX",
            note="Project canonical memory hit; does not confirm live external state.",
        ))
    return epistemic_assessment(subject,reviews,sensitive_action=False,freshness_required=False)


def default_memory_reliability()->dict[str,Any]:
    reviews=[]
    snapshots=[]
    return {
        "schema":SCHEMA,
        "policy":memory_reliability_policy(),
        "reviews":reviews,
        "decision_snapshots":snapshots,
        "digest":memory_reliability_digest(reviews,snapshots),
        "action_authorized":False,
        "real_trading_enabled":False,
    }


def normalize_memory_reliability(raw:Mapping[str,Any]|None)->dict[str,Any]:
    item=dict(raw or {})
    reviews=normalize_memory_reviews(
        item.get("reviews") if isinstance(item.get("reviews"),(list,tuple)) else []
    )
    snapshots=normalize_decision_snapshots(
        item.get("decision_snapshots")
        if isinstance(item.get("decision_snapshots"),(list,tuple))
        else []
    )
    return {
        "schema":SCHEMA,
        "policy":memory_reliability_policy(),
        "reviews":reviews,
        "decision_snapshots":snapshots,
        "digest":memory_reliability_digest(reviews,snapshots),
        "action_authorized":False,
        "real_trading_enabled":False,
    }


def memory_reliability_digest(
    reviews:Sequence[Mapping[str,Any]]|None,
    snapshots:Sequence[Mapping[str,Any]]|None,
)->str:
    # Evaluated-at timestamps are volatile; strip them before hashing.
    normalized_reviews=normalize_memory_reviews(reviews)
    stable_reviews=[]
    for row in normalized_reviews:
        item=dict(row)
        item.pop("review_evaluated_at",None)
        stable_reviews.append(item)
    return _stable({
        "reviews":stable_reviews,
        "decision_snapshots":normalize_decision_snapshots(snapshots),
        "policy":memory_reliability_policy(),
    })


def upsert_memory_review(
    rows:Sequence[Mapping[str,Any]]|None,
    review:Mapping[str,Any],
)->list[dict[str,Any]]:
    current=normalize_memory_reviews(rows)
    item=evaluate_memory_review(review)
    current=[x for x in current if x["memory_ref"]!=item["memory_ref"]]
    current.append(item)
    return current[-MAX_REVIEWS:]


def upsert_decision_snapshot(
    rows:Sequence[Mapping[str,Any]]|None,
    snapshot:Mapping[str,Any],
)->list[dict[str,Any]]:
    current=normalize_decision_snapshots(rows)
    item=normalize_decision_snapshot(snapshot)
    current=[x for x in current if x["decision_ref"]!=item["decision_ref"]]
    current.append(item)
    return current[-MAX_SNAPSHOTS:]


def memory_reliability_summary(raw:Mapping[str,Any]|None)->dict[str,Any]:
    state=normalize_memory_reliability(raw)
    reviews=state["reviews"]
    return {
        "schema":SCHEMA,
        "reviews":len(reviews),
        "current_confirmed":sum(1 for x in reviews if x["review_state"]=="CURRENT" and x["effective_truth_state"]=="CONFIRMED"),
        "verify_required":sum(1 for x in reviews if x["review_state"]=="VERIFY_REQUIRED"),
        "expired":sum(1 for x in reviews if x["review_state"]=="EXPIRED"),
        "conflicts":sum(1 for x in reviews if x["review_state"]=="CONFLICT"),
        "superseded":sum(1 for x in reviews if x["review_state"]=="SUPERSEDED"),
        "decision_snapshots":len(state["decision_snapshots"]),
        "action_authorized":False,
        "real_trading_enabled":False,
        "digest":state["digest"],
    }


__all__=[
    "SCHEMA","MEMORY_KINDS","TRUTH_STATES","REVIEW_STATES","GATE_STATES",
    "EPISTEMIC_STATES","memory_reliability_policy","new_memory_review",
    "evaluate_memory_review","normalize_memory_reviews","memory_retrieval_gate",
    "new_decision_snapshot","normalize_decision_snapshot",
    "normalize_decision_snapshots","epistemic_assessment",
    "assess_canonical_memory_hits","default_memory_reliability",
    "normalize_memory_reliability","memory_reliability_digest",
    "upsert_memory_review","upsert_decision_snapshot","memory_reliability_summary",
]
