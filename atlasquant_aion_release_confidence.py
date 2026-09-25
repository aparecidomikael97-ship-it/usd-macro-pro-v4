"""AION Release Confidence.

Evidence-coverage summary for a candidate release. It is deliberately NOT a
probability of success and never authorizes merge/deploy. The highest state is
HUMAN_REVIEW_READY.

Inputs are externally observed evidence snapshots (Digital Twin, Dev Fusion,
Evaluation Lab, CI/release gate/rollback). Missing or contradictory evidence
fails closed.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Any, Mapping, Sequence
import json

SCHEMA="ATLASQUANT_AION_RELEASE_CONFIDENCE_V1"
DIMENSIONS=("DIGITAL_TWIN","DEV_FUSION","EVALUATION","QUALITY","RELEASE_GATE","ROLLBACK")


def _clean(value:Any,limit:int=1000)->str:
    return " ".join(str(value or "").replace("\x00","").split())[:limit]


def _digest(value:Any,length:int=20)->str:
    raw=json.dumps(value,ensure_ascii=False,sort_keys=True,default=str)
    return sha256(raw.encode("utf-8")).hexdigest()[:length]


def evidence_dimension(
    name:Any,
    *,
    confirmed:bool,
    evidence_refs:Sequence[Any]|None=None,
    blocker:bool=False,
    detail:Any="",
)->dict[str,Any]:
    dim=_clean(name,40).upper()
    if dim not in DIMENSIONS:
        raise ValueError("invalid release confidence dimension")
    refs=[]
    for raw in list(evidence_refs or [])[:80]:
        text=_clean(raw,280)
        if text and text not in refs:
            refs.append(text)
    is_confirmed=bool(confirmed and refs and not blocker)
    return {
        "dimension":dim,
        "confirmed":is_confirmed,
        "blocker":bool(blocker),
        "evidence_refs":refs,
        "detail":_clean(detail,800),
    }


def release_confidence(
    *,
    candidate_ref:Any,
    dimensions:Sequence[Mapping[str,Any]]|None,
)->dict[str,Any]:
    candidate=_clean(candidate_ref,180)
    if not candidate:
        raise ValueError("candidate ref required")
    rows=[]
    seen=set()
    for raw in list(dimensions or [])[:20]:
        if not isinstance(raw,Mapping):
            continue
        try:
            row=evidence_dimension(
                raw.get("dimension"),
                confirmed=bool(raw.get("confirmed",False)),
                evidence_refs=raw.get("evidence_refs") if isinstance(raw.get("evidence_refs"),(list,tuple)) else [],
                blocker=bool(raw.get("blocker",False)),
                detail=raw.get("detail"),
            )
        except Exception:
            continue
        if row["dimension"] in seen:
            continue
        seen.add(row["dimension"])
        rows.append(row)

    by={x["dimension"]:x for x in rows}
    normalized=[
        by.get(name) or evidence_dimension(name,confirmed=False,evidence_refs=[],detail="Evidência ausente.")
        for name in DIMENSIONS
    ]
    blockers=[x["dimension"] for x in normalized if x["blocker"]]
    confirmed=sum(1 for x in normalized if x["confirmed"])
    total=len(DIMENSIONS)
    coverage_pct=round(100.0*confirmed/total,2) if total else 0.0

    if blockers:
        state="BLOCKED"
    elif confirmed<total:
        state="NEEDS_EVIDENCE"
    else:
        state="HUMAN_REVIEW_READY"

    return {
        "schema":SCHEMA,
        "candidate_ref":candidate,
        "state":state,
        "dimensions":normalized,
        "confirmed_dimensions":confirmed,
        "total_dimensions":total,
        "evidence_coverage_pct":coverage_pct,
        "blockers":blockers,
        "meaning":"Evidence coverage only; not probability and not authorization.",
        "merge_allowed":False,
        "deploy_allowed":False,
        "automatic_promotion":False,
        "requires_human_approval":True,
        "real_trading_enabled":False,
        "digest":_digest({"candidate":candidate,"dimensions":normalized},24),
    }


def release_confidence_summary(rows:Sequence[Mapping[str,Any]]|None)->dict[str,Any]:
    items=[dict(x) for x in list(rows or [])[-300:] if isinstance(x,Mapping)]
    return {
        "schema":SCHEMA,
        "records":len(items),
        "human_review_ready":sum(1 for x in items if x.get("state")=="HUMAN_REVIEW_READY"),
        "blocked":sum(1 for x in items if x.get("state")=="BLOCKED"),
        "needs_evidence":sum(1 for x in items if x.get("state")=="NEEDS_EVIDENCE"),
        "merge_allowed":False,
        "deploy_allowed":False,
        "real_trading_enabled":False,
        "digest":_digest(items,24),
    }


__all__=["SCHEMA","DIMENSIONS","evidence_dimension","release_confidence","release_confidence_summary"]
