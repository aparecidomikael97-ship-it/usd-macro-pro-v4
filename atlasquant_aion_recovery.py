"""AION Checkpoint Mestre recovery helpers.

Recovery uses GitHub history of the dedicated runtime-data checkpoint file.
It never restores automatically. A candidate must be read, integrity-checked,
reviewed, approved by ADMIN/Guardian in the UI, and written conditionally
against the current runtime SHA.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping
import base64
import json
import re

import requests

from atlasquant_runtime_store import require_runtime_branch
from atlasquant_aion_memory import (
    MAX_RUNTIME_BYTES,
    RuntimeConfig,
    checkpoint_integrity_report,
    checkpoint_source_digest,
    ensure_operating_checkpoint,
    save_runtime_checkpoint,
    update_operating_checkpoint,
)
from atlasquant_aion_observability import append_event, new_event

SCHEMA="ATLASQUANT_AION_RECOVERY_V1"
_REVISION_RE=re.compile(r"^[0-9a-fA-F]{7,40}$")


def _history_url(cfg:RuntimeConfig)->str:
    return f"https://api.github.com/repos/{cfg.repo}/commits"


def _contents_url(cfg:RuntimeConfig)->str:
    return f"https://api.github.com/repos/{cfg.repo}/contents/{cfg.path}"


def _headers(token:str)->dict[str,str]:
    return {
        "Authorization":f"Bearer {token}",
        "Accept":"application/vnd.github+json",
        "X-GitHub-Api-Version":"2022-11-28",
    }


def _safe_revision(value:Any)->str:
    revision=str(value or "").strip()
    return revision if _REVISION_RE.fullmatch(revision) else ""


def list_checkpoint_revisions(
    config:RuntimeConfig,
    *,
    limit:int=12,
    timeout:float=12.0,
)->dict[str,Any]:
    """List versioned revisions for the Checkpoint file without changing state."""
    try:
        require_runtime_branch(config.branch)
    except Exception as exc:
        return {
            "schema":SCHEMA,"status":"BLOCKED","items":[],
            "reason":f"unsafe runtime branch: {type(exc).__name__}",
            "executes_action":False,
        }
    if not config.ready:
        return {
            "schema":SCHEMA,"status":"UNAVAILABLE","items":[],
            "reason":"GitHub runtime credentials not configured.",
            "executes_action":False,
        }
    per_page=max(1,min(int(limit or 12),30))
    try:
        response=requests.get(
            _history_url(config),
            headers=_headers(config.token),
            params={
                "sha":config.branch,
                "path":config.path,
                "per_page":per_page,
            },
            timeout=timeout,
        )
        response.raise_for_status()
        raw=response.json()
        if not isinstance(raw,list):
            raise ValueError("history response is not a list")
        items=[]
        for row in raw[:per_page]:
            if not isinstance(row,Mapping):
                continue
            sha=_safe_revision(row.get("sha"))
            if not sha:
                continue
            commit=row.get("commit") if isinstance(row.get("commit"),Mapping) else {}
            author=commit.get("author") if isinstance(commit.get("author"),Mapping) else {}
            message=" ".join(str(commit.get("message") or "").split())[:240]
            items.append({
                "revision":sha,
                "short_revision":sha[:10],
                "created_at":str(author.get("date") or "")[:40],
                "message":message,
            })
        return {
            "schema":SCHEMA,
            "status":"CONFIRMED",
            "source":f"GitHub:{config.branch}:{config.path}",
            "items":items,
            "count":len(items),
            "executes_action":False,
        }
    except Exception as exc:
        return {
            "schema":SCHEMA,"status":"ERROR","items":[],
            "reason":type(exc).__name__,
            "executes_action":False,
        }


def load_checkpoint_revision(
    revision:Any,
    config:RuntimeConfig,
    *,
    timeout:float=12.0,
)->dict[str,Any]:
    """Load one historical Checkpoint revision and verify its internal digests."""
    rev=_safe_revision(revision)
    if not rev:
        return {
            "schema":SCHEMA,"status":"BLOCKED","checkpoint":None,
            "reason":"Invalid checkpoint revision.",
            "executes_action":False,
        }
    try:
        require_runtime_branch(config.branch)
    except Exception as exc:
        return {
            "schema":SCHEMA,"status":"BLOCKED","checkpoint":None,
            "reason":f"unsafe runtime branch: {type(exc).__name__}",
            "executes_action":False,
        }
    if not config.ready:
        return {
            "schema":SCHEMA,"status":"UNAVAILABLE","checkpoint":None,
            "reason":"GitHub runtime credentials not configured.",
            "executes_action":False,
        }
    try:
        response=requests.get(
            _contents_url(config),
            headers=_headers(config.token),
            params={"ref":rev},
            timeout=timeout,
        )
        response.raise_for_status()
        obj=response.json()
        raw=base64.b64decode(str(obj.get("content") or "")).decode("utf-8")
        if len(raw.encode("utf-8"))>MAX_RUNTIME_BYTES:
            raise ValueError("runtime checkpoint too large")
        checkpoint=json.loads(raw)
        if not isinstance(checkpoint,dict):
            raise ValueError("checkpoint is not an object")
        integrity=checkpoint_integrity_report(checkpoint)
        return {
            "schema":SCHEMA,
            "status":"CONFIRMED",
            "source":f"GitHub:{config.branch}:{config.path}@{rev}",
            "revision":rev,
            "checkpoint":checkpoint,
            "integrity":integrity,
            "digest":checkpoint_source_digest(checkpoint),
            "executes_action":False,
        }
    except Exception as exc:
        return {
            "schema":SCHEMA,"status":"ERROR","checkpoint":None,
            "revision":rev,"reason":type(exc).__name__,
            "executes_action":False,
        }


def recovery_preflight(
    current_runtime:Mapping[str,Any]|None,
    candidate:Mapping[str,Any]|None,
)->dict[str,Any]:
    """Fail closed unless current SHA and historical candidate are safe enough.

    Recovery is intentionally allowed to repair a current MISMATCH because
    normal writes are blocked in that condition. The candidate itself must
    never be MISMATCH or UNKNOWN.
    """
    current=dict(current_runtime or {})
    selected=dict(candidate or {})
    if str(current.get("status") or "").upper()!="CONFIRMED":
        return {
            "schema":SCHEMA,"allowed":False,"reason":"Current runtime is not confirmed.",
            "executes_action":False,
        }
    current_sha=str(current.get("sha") or "").strip()
    if not current_sha:
        return {
            "schema":SCHEMA,"allowed":False,"reason":"Current runtime SHA is missing.",
            "executes_action":False,
        }
    if str(selected.get("status") or "").upper()!="CONFIRMED":
        return {
            "schema":SCHEMA,"allowed":False,"reason":"Recovery candidate is not confirmed.",
            "executes_action":False,
        }
    revision=_safe_revision(selected.get("revision"))
    checkpoint=selected.get("checkpoint")
    if not revision or not isinstance(checkpoint,Mapping):
        return {
            "schema":SCHEMA,"allowed":False,"reason":"Recovery candidate is incomplete.",
            "executes_action":False,
        }

    integrity=(
        selected.get("integrity")
        if isinstance(selected.get("integrity"),Mapping)
        else checkpoint_integrity_report(checkpoint)
    )
    integrity_state=str(integrity.get("state") or "UNKNOWN").upper()
    if integrity_state not in {"CONFIRMED","MIGRATION_REQUIRED"}:
        return {
            "schema":SCHEMA,
            "allowed":False,
            "reason":f"Recovery candidate integrity is {integrity_state}.",
            "candidate_integrity":integrity_state,
            "executes_action":False,
        }

    candidate_digest=checkpoint_source_digest(checkpoint)
    current_checkpoint=current.get("checkpoint")
    current_digest=(
        checkpoint_source_digest(current_checkpoint)
        if isinstance(current_checkpoint,Mapping)
        else ""
    )
    if current_digest and candidate_digest==current_digest:
        return {
            "schema":SCHEMA,"allowed":False,
            "reason":"Selected revision has the same effective checkpoint content.",
            "candidate_integrity":integrity_state,
            "candidate_digest":candidate_digest,
            "current_digest":current_digest,
            "executes_action":False,
        }

    return {
        "schema":SCHEMA,
        "allowed":True,
        "reason":"Historical checkpoint is eligible for explicit conditional recovery.",
        "expected_sha":current_sha,
        "candidate_revision":revision,
        "candidate_integrity":integrity_state,
        "candidate_digest":candidate_digest,
        "current_digest":current_digest,
        "executes_action":False,
    }


def restore_checkpoint_revision(
    candidate:Mapping[str,Any],
    current_runtime:Mapping[str,Any],
    config:RuntimeConfig,
    *,
    approved:bool=False,
    timeout:float=15.0,
)->dict[str,Any]:
    """Restore a verified historical revision after explicit administrator approval."""
    if not approved:
        return {
            "schema":SCHEMA,"status":"BLOCKED","saved":False,"verified":False,
            "reason":"Explicit administrator approval required for recovery.",
        }
    preflight=recovery_preflight(current_runtime,candidate)
    if not preflight.get("allowed"):
        return {
            "schema":SCHEMA,"status":"BLOCKED","saved":False,"verified":False,
            "reason":preflight.get("reason") or "Recovery preflight blocked.",
            "preflight":preflight,
        }

    checkpoint=ensure_operating_checkpoint(candidate.get("checkpoint"))
    checkpoint=deepcopy(checkpoint)
    operating=checkpoint.get("operating") if isinstance(checkpoint.get("operating"),Mapping) else {}
    events=append_event(
        operating.get("events",[]),
        new_event(
            "checkpoint_recovery_restored",
            "Checkpoint Mestre restaurado a partir de revisão histórica explicitamente aprovada.",
            severity="WARNING",
            source="AION_RECOVERY",
            truth_state="CONFIRMED",
            evidence={
                "candidate_revision":preflight.get("candidate_revision"),
                "candidate_digest":preflight.get("candidate_digest"),
                "previous_runtime_sha":preflight.get("expected_sha"),
                "automatic_restore":False,
            },
        ),
    )
    checkpoint=update_operating_checkpoint(
        checkpoint,
        events=events,
        dirty=True,
    )

    result=save_runtime_checkpoint(
        checkpoint,
        config,
        approved=True,
        expected_sha=str(preflight.get("expected_sha") or ""),
        timeout=timeout,
    )
    output=dict(result)
    output["schema"]=SCHEMA
    output["recovery_preflight"]=preflight
    output["restored_revision"]=preflight.get("candidate_revision")
    output["automatic_restore"]=False
    return output


__all__=[
    "SCHEMA",
    "list_checkpoint_revisions",
    "load_checkpoint_revision",
    "recovery_preflight",
    "restore_checkpoint_revision",
]
