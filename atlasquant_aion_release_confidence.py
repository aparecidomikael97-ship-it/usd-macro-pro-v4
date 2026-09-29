"""AION Release Confidence.

Evidence-coverage summary for a candidate release. It is deliberately NOT a
probability of success and never authorizes merge/deploy. The highest state is
HUMAN_REVIEW_READY.

Inputs are externally observed evidence snapshots (Digital Twin, Dev Fusion,
Evaluation Lab, CI/release gate/rollback). Missing or contradictory evidence
fails closed.
"""
from __future__ import annotations

from collections import deque
from hashlib import sha256
from typing import Any, Mapping, Sequence
from itertools import islice
import json

SCHEMA="ATLASQUANT_AION_RELEASE_CONFIDENCE_V1"
DIMENSIONS=("DIGITAL_TWIN","DEV_FUSION","EVALUATION","QUALITY","RELEASE_GATE","ROLLBACK")


def _clean(value:Any,limit:int=1000)->str:
    return " ".join(str(value or "").replace("\x00","").split())[:limit]


def _digest(value:Any,length:int=20)->str:
    raw=json.dumps(value,ensure_ascii=False,sort_keys=True,default=str)
    return sha256(raw.encode("utf-8")).hexdigest()[:length]


def _verified_refs(dimension:str, refs:list[str], evidence_verifier:Any)->bool:
    """A ref list is evidence only when a caller verifier binds those exact refs.

    Without a verifier, invented refs stay unvalidated.
    """
    if not callable(evidence_verifier) or not refs:
        return False
    try:
        verdict=evidence_verifier(dimension, list(refs))
    except Exception:
        return False
    if not isinstance(verdict, Mapping):
        return False
    bound=verdict.get("bound_refs")
    return (
        verdict.get("state")=="VERIFIED"
        and isinstance(bound,(list,tuple))
        and list(bound)==list(refs)
    )


def evidence_dimension(
    name:Any,
    *,
    confirmed:bool,
    evidence_refs:Sequence[Any]|None=None,
    blocker:bool=False,
    detail:Any="",
    evidence_verifier:Any=None,
)->dict[str,Any]:
    dim=_clean(name,40).upper()
    if dim not in DIMENSIONS:
        raise ValueError("invalid release confidence dimension")
    refs=[]
    for raw in islice(evidence_refs or (),80):
        text=_clean(raw,280)
        if text and text not in refs:
            refs.append(text)
    is_blocker=blocker is not False
    is_confirmed=(
        confirmed is True
        and not is_blocker
        and _verified_refs(dim, refs, evidence_verifier)
    )
    return {
        "dimension":dim,
        "confirmed":is_confirmed,
        "blocker":is_blocker,
        "evidence_refs":refs,
        "detail":_clean(detail,800),
    }


def release_confidence(
    *,
    candidate_ref:Any,
    dimensions:Sequence[Mapping[str,Any]]|None,
    evidence_verifier:Any=None,
)->dict[str,Any]:
    candidate=_clean(candidate_ref,180)
    if not candidate:
        raise ValueError("candidate ref required")
    rows=[]
    seen=set()
    for raw in islice(dimensions or (),20):
        if not isinstance(raw,Mapping):
            continue
        try:
            row=evidence_dimension(
                raw.get("dimension"),
                confirmed=raw.get("confirmed",False),
                evidence_refs=raw.get("evidence_refs") if isinstance(raw.get("evidence_refs"),(list,tuple)) else [],
                blocker=raw.get("blocker",False),
                detail=raw.get("detail"),
                evidence_verifier=evidence_verifier,
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


def normalize_release_confidence(
    raw:Mapping[str,Any],
    *,
    evidence_verifier:Any=None,
)->dict[str,Any]:
    """Recompute state from evidence; never trust a persisted readiness label."""
    item=dict(raw or {})
    return release_confidence(
        candidate_ref=item.get("candidate_ref"),
        dimensions=item.get("dimensions")
        if isinstance(item.get("dimensions"),(list,tuple))
        else [],
        evidence_verifier=evidence_verifier,
    )


def normalize_release_confidence_records(
    rows:Sequence[Mapping[str,Any]]|None,
)->list[dict[str,Any]]:
    out=[]
    seen=set()
    source=(
        rows[-300:]
        if isinstance(rows,(list,tuple))
        else deque(rows or (),maxlen=300)
    )
    for raw in source:
        if not isinstance(raw,Mapping):
            continue
        try:
            item=normalize_release_confidence(raw)
        except Exception:
            continue
        key=(item["candidate_ref"],item["digest"])
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def release_confidence_digest(rows:Sequence[Mapping[str,Any]]|None)->str:
    return _digest(normalize_release_confidence_records(rows),24)


def release_confidence_summary(rows:Sequence[Mapping[str,Any]]|None)->dict[str,Any]:
    items=normalize_release_confidence_records(rows)
    return {
        "schema":SCHEMA,
        "records":len(items),
        "human_review_ready":sum(1 for x in items if x.get("state")=="HUMAN_REVIEW_READY"),
        "blocked":sum(1 for x in items if x.get("state")=="BLOCKED"),
        "needs_evidence":sum(1 for x in items if x.get("state")=="NEEDS_EVIDENCE"),
        "merge_allowed":False,
        "deploy_allowed":False,
        "real_trading_enabled":False,
        "digest":release_confidence_digest(items),
    }


__all__=["SCHEMA","DIMENSIONS","evidence_dimension","release_confidence","normalize_release_confidence","normalize_release_confidence_records","release_confidence_digest","release_confidence_summary"]
