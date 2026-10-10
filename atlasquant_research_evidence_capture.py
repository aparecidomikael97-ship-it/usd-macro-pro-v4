"""AtlasQuant session/runtime capture for operational research evidence."""
from __future__ import annotations

from datetime import datetime, timezone
import os
from typing import Any, Mapping, Sequence

import streamlit as st

from atlasquant_research_evidence_store import (
    evidence_record,
    latest_evidence_by_strategy,
    load_research_evidence,
    merge_evidence_records,
    persist_research_evidence,
)
from atlasquant_runtime_store import resolve_runtime_branch

SESSION_KEY="atlasquant_research_evidence_records"
HYDRATED_KEY="atlasquant_research_evidence_hydrated"
STATUS_KEY="atlasquant_research_evidence_status"
PENDING_KEY="atlasquant_research_evidence_reconciliation_pending"


def _pending_status()->dict[str,Any]|None:
    """Sticky session quarantine; reads/local captures cannot reconcile a PUT."""
    pending=st.session_state.get(PENDING_KEY)
    previous=st.session_state.get(STATUS_KEY,{}) or {}
    if pending is None and (previous.get("reason") in {"UNKNOWN_OUTCOME","CONFLICT","VALIDATION_REJECTED"}
                            or previous.get("reconciliation_required") is True):
        pending=previous
    if pending is None:
        return None
    status=dict(pending)
    if status.get("reason") not in {"UNKNOWN_OUTCOME","CONFLICT","VALIDATION_REJECTED"}:
        status["reason"]="UNKNOWN_OUTCOME"
    status.update(ok=False,reconciliation_required=True,safe_to_retry=False,
                  persistence_confirmed=False,verified=False,readback_matching_content=False,
                  confirmation_scope="NONE",source="session")
    st.session_state[PENDING_KEY]=dict(status)
    return status


def _remember_status(status:Mapping[str,Any])->dict[str,Any]:
    status=dict(status)
    status["persistence_confirmed"]=(status.get("reason")=="SAVED" and status.get("verified") is True
                                     and status.get("readback_matching_content") is True)
    status["confirmation_scope"]="CURRENT_WRITE_BATCH" if status["persistence_confirmed"] else "NONE"
    st.session_state[STATUS_KEY]=dict(status)
    pending=_pending_status()
    if pending is not None:
        for key in ("session_records","local_added"):
            if key in status:
                pending[key]=status[key]
        status=pending
        st.session_state[PENDING_KEY]=dict(status)
        st.session_state[STATUS_KEY]=dict(status)
    return status


def _secret_or_env(key:str,default:str="")->str:
    try:
        value=st.secrets.get(key,os.getenv(key,default))
    except Exception:
        value=os.getenv(key,default)
    return str(value or "").strip()


def research_evidence_config()->dict[str,str]:
    return {
        "repo":_secret_or_env(
            "GITHUB_REPO_HISTORICO",
            os.getenv("GITHUB_REPOSITORY","aparecidomikael97-ship-it/usd-macro-pro-v4"),
        ),
        "branch":resolve_runtime_branch(
            _secret_or_env("GITHUB_DATA_BRANCH",""),
            _secret_or_env("GITHUB_BRANCH_HISTORICO",""),
        ),
        "token":_secret_or_env("GITHUB_TOKEN_HISTORICO",os.getenv("GITHUB_TOKEN","")),
    }


def hydrate_research_evidence(
    session_records:Sequence[Mapping[str,Any]]|None,
    remote_records:Sequence[Mapping[str,Any]]|None,
)->list[dict[str,Any]]:
    merged,_=merge_evidence_records(remote_records,session_records)
    return merged


def ensure_research_evidence_hydrated()->tuple[list[dict[str,Any]],dict[str,Any]]:
    current=list(st.session_state.get(SESSION_KEY,[]) or [])
    pending=_pending_status()
    if pending is not None:
        pending["session_records"]=len(current)
        return current,_remember_status(pending)
    if bool(st.session_state.get(HYDRATED_KEY,False)):
        return current,dict(st.session_state.get(STATUS_KEY,{}) or {})

    cfg=research_evidence_config()
    if not cfg["repo"] or not cfg["token"]:
        status={
            "ok":False,"reason":"NOT_CONFIGURED","records":len(current),
            "source":"session","branch":cfg["branch"],"error":"",
        }
        st.session_state[HYDRATED_KEY]=True
        st.session_state[STATUS_KEY]=status
        return current,status

    try:
        remote=load_research_evidence(
            repo=cfg["repo"],branch=cfg["branch"],token=cfg["token"]
        )
        current=hydrate_research_evidence(current,remote)
        status={
            "ok":True,"reason":"LOADED","records":len(remote),
            "source":"runtime_persistent","branch":cfg["branch"],"error":"",
        }
    except Exception as exc:
        status={
            "ok":False,"reason":"LOAD_ERROR","records":len(current),
            "source":"session_fallback","branch":cfg["branch"],
            "error":f"{type(exc).__name__}: {exc}",
        }

    st.session_state[SESSION_KEY]=current
    st.session_state[HYDRATED_KEY]=True
    st.session_state[STATUS_KEY]=status
    return current,status


def capture_research_evidence(
    *,
    strategy:object,
    source:object,
    passport:Mapping[str,Any]|None,
    evidence:Mapping[str,Any]|None,
    pair:object="",
    captured_at:object|None=None,
    persist:bool=True,
)->dict[str,Any]:
    # Adopt a legacy pending status before a session-only capture can replace it.
    _pending_status()
    if persist:
        current,_=ensure_research_evidence_hydrated()
    else:
        # Backtest/session capture must stay fast and side-effect free: no remote
        # read is triggered merely to remember the evidence in this session.
        current=list(st.session_state.get(SESSION_KEY,[]) or [])
    timestamp=str(
        captured_at
        or datetime.now(timezone.utc).isoformat()
    )
    record=evidence_record(
        strategy=strategy,
        captured_at=timestamp,
        source=source,
        passport=passport,
        evidence=evidence,
        pair=pair,
    )
    merged,added=merge_evidence_records(current,[record])
    st.session_state[SESSION_KEY]=merged

    pending=_pending_status()
    if pending is not None:
        pending.update(session_records=len(merged),local_added=added)
        return _remember_status(pending)

    if not added:
        status={
            "ok":True,"reason":"LOCAL_ALREADY_PRESENT","added":0,
            "records":len(merged),"source":"session",
        }
        return _remember_status(status)

    if not persist:
        status={
            "ok":True,"reason":"SESSION_ONLY","added":added,
            "records":len(merged),"source":"session",
        }
        return _remember_status(status)

    cfg=research_evidence_config()
    status=persist_research_evidence(
        [record],
        repo=cfg["repo"],
        branch=cfg["branch"],
        token=cfg["token"],
    )
    status["session_records"]=len(merged)
    return _remember_status(status)


def persist_session_research_evidence()->dict[str,Any]:
    records,_=ensure_research_evidence_hydrated()
    pending=_pending_status()
    if pending is not None:
        pending["session_records"]=len(records)
        return _remember_status(pending)
    cfg=research_evidence_config()
    if not records:
        status={
            "ok":True,"reason":"NO_RECORDS","added":0,
            "records":0,"branch":cfg["branch"],"error":"",
        }
        return _remember_status(status)
    status=persist_research_evidence(
        records,
        repo=cfg["repo"],
        branch=cfg["branch"],
        token=cfg["token"],
    )
    status["session_records"]=len(records)
    return _remember_status(status)


def latest_research_evidence()->dict[str,dict[str,Any]]:
    records,_=ensure_research_evidence_hydrated()
    return latest_evidence_by_strategy(records)


__all__=[
    "SESSION_KEY",
    "HYDRATED_KEY",
    "STATUS_KEY",
    "PENDING_KEY",
    "research_evidence_config",
    "hydrate_research_evidence",
    "ensure_research_evidence_hydrated",
    "capture_research_evidence",
    "persist_session_research_evidence",
    "latest_research_evidence",
]
