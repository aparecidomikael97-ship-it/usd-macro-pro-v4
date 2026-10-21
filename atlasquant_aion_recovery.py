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
import hashlib
import json
import re
from urllib.parse import quote


from atlasquant_runtime_store import require_runtime_branch
from atlasquant_aion_memory import (
    MAX_RUNTIME_BYTES,
    RuntimeConfig,
    checkpoint_integrity_report,
    checkpoint_source_digest,
    ensure_operating_checkpoint,
    load_runtime_checkpoint,
    save_runtime_checkpoint,
    update_operating_checkpoint,
)
from atlasquant_aion_observability import append_event, new_event

SCHEMA="ATLASQUANT_AION_RECOVERY_V1"
_REVISION_RE=re.compile(r"^[0-9a-fA-F]{40}$")


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


def _strict_json_object(pairs:list[tuple[str,Any]])->dict[str,Any]:
    out={}
    for key,value in pairs:
        if key in out:
            raise ValueError("duplicate JSON key")
        out[key]=value
    return out


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
        import requests
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
        seen_revisions=set()
        invalid_rows_dropped=0
        duplicates_dropped=0
        for row in raw[:per_page]:
            if not isinstance(row,Mapping):
                invalid_rows_dropped+=1
                continue
            sha=_safe_revision(row.get("sha"))
            if not sha:
                invalid_rows_dropped+=1
                continue
            if sha in seen_revisions:
                duplicates_dropped+=1
                continue
            seen_revisions.add(sha)
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
            "invalid_rows_dropped":invalid_rows_dropped,
            "duplicates_dropped":duplicates_dropped,
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
        import requests
        response=requests.get(
            _contents_url(config),
            headers=_headers(config.token),
            params={"ref":rev},
            timeout=timeout,
        )
        response.raise_for_status()
        obj=response.json()
        if not isinstance(obj,Mapping):
            raise ValueError("checkpoint response is not an object")
        raw_content=obj.get("content")
        if not isinstance(raw_content,str):
            raise ValueError("runtime checkpoint content must be a base64 string")
        encoding=str(obj.get("encoding") or "base64").strip().casefold()
        if encoding!="base64":
            raise ValueError("runtime checkpoint encoding must be base64")
        encoded="".join(raw_content.split())
        if not encoded:
            raise ValueError("runtime checkpoint content missing")
        max_encoded_chars=4*((MAX_RUNTIME_BYTES+2)//3)
        if len(encoded)>max_encoded_chars:
            raise ValueError("runtime checkpoint encoded content too large")
        raw_bytes=base64.b64decode(encoded,validate=True)
        if len(raw_bytes)>MAX_RUNTIME_BYTES:
            raise ValueError("runtime checkpoint too large")
        # A131 LAB: GitHub Contents exposes a Git blob SHA for these bytes.
        # A well-formed but inconsistent metadata SHA must never turn the
        # historical source into CONFIRMED or reach a restore candidate.
        # This is consistency only; it is NOT independent provenance.
        metadata_sha=obj.get("sha")
        if (
            type(metadata_sha) is not str
            or _REVISION_RE.fullmatch(metadata_sha) is None
        ):
            raise ValueError("historical Git blob SHA missing or malformed")
        calculated_sha=hashlib.sha1(
            b"blob "+str(len(raw_bytes)).encode("ascii")+b"\x00"+raw_bytes
        ).hexdigest()
        if metadata_sha.lower()!=calculated_sha:
            raise ValueError("historical Git blob SHA does not match decoded contents")
        raw=raw_bytes.decode("utf-8")
        checkpoint=json.loads(raw,object_pairs_hook=_strict_json_object)
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
    # A127: reject caller-supplied non-mapping recovery envelopes rather
    # than leaking TypeError through dict(value). A missing envelope may
    # still be represented by {} and must fail the ordinary status gate.
    if current_runtime is not None and not isinstance(current_runtime, Mapping):
        return {
            "schema": SCHEMA, "allowed": False,
            "reason": "Current runtime envelope is invalid.",
            "executes_action": False,
        }
    if candidate is not None and not isinstance(candidate, Mapping):
        return {
            "schema": SCHEMA, "allowed": False,
            "reason": "Recovery candidate envelope is invalid.",
            "executes_action": False,
        }
    current=dict(current_runtime or {})
    selected=dict(candidate or {})
    if str(current.get("status") or "").upper()!="CONFIRMED":
        return {
            "schema":SCHEMA,"allowed":False,"reason":"Current runtime is not confirmed.",
            "executes_action":False,
        }
    # GitHub Contents API conditional writes use a 40-character blob SHA.
    # A truthy but malformed value must never reach history readback or a
    # restore attempt as an expected_sha (boolean/int coercion is unsafe).
    raw_current_sha = current.get("sha")
    current_sha = raw_current_sha if type(raw_current_sha) is str else ""
    if not current_sha:
        return {
            "schema":SCHEMA,"allowed":False,"reason":"Current runtime SHA is missing or invalid.",
            "executes_action":False,
        }
    if re.fullmatch(r"[0-9a-fA-F]{40}", current_sha) is None:
        return {
            "schema":SCHEMA,"allowed":False,"reason":"Current runtime SHA is invalid.",
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

    integrity=checkpoint_integrity_report(checkpoint)
    claim=selected.get("integrity") if isinstance(selected.get("integrity"),Mapping) else None
    actual_state=str(integrity.get("state") or "UNKNOWN").upper()
    if claim is not None:
        claim_state=str(claim.get("state") or "").strip().upper()
        write_mismatch=(
            "write_safe" in claim
            and claim.get("write_safe") is not integrity.get("write_safe")
        )
        if claim_state!=actual_state or write_mismatch:
            return {
                "schema":SCHEMA,
                "allowed":False,
                "reason":"Recovery integrity claim does not match the recomputed checkpoint.",
                "candidate_integrity":actual_state,
                "executes_action":False,
            }
    claimed_digest=str(selected.get("digest") or "").strip()
    actual_digest=checkpoint_source_digest(checkpoint)
    if claimed_digest and claimed_digest!=actual_digest:
        return {
            "schema":SCHEMA,
            "allowed":False,
            "reason":"Recovery candidate digest does not match the checkpoint.",
            "candidate_integrity":actual_state,
            "candidate_digest":actual_digest,
            "executes_action":False,
        }
    integrity_state=actual_state
    if integrity_state not in {"CONFIRMED","MIGRATION_REQUIRED"}:
        return {
            "schema":SCHEMA,
            "allowed":False,
            "reason":f"Recovery candidate integrity is {integrity_state}.",
            "candidate_integrity":integrity_state,
            "executes_action":False,
        }

    candidate_digest=checkpoint_source_digest(checkpoint)
    # A128 LAB: a syntactically valid Git blob SHA is not proof that a
    # current checkpoint body was observed. Preserve the legacy candidate
    # integrity diagnosis above, then deny absent/empty current evidence
    # before computing digests or permitting a historical readback.
    current_checkpoint=current.get("checkpoint")
    if not isinstance(current_checkpoint, Mapping) or not current_checkpoint:
        return {
            "schema": SCHEMA, "allowed": False,
            "reason": "Current runtime checkpoint is missing or invalid.",
            "candidate_integrity": integrity_state,
            "candidate_digest": candidate_digest,
            "executes_action": False,
        }
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


def _recheck_live_restore_target(
    current_runtime:Mapping[str,Any],
    preflight:Mapping[str,Any],
    config:RuntimeConfig,
    *,
    timeout:float,
)->dict[str,Any]:
    """Verify the configured destination with a fresh read-only GET.

    A caller-supplied SHA/source is never its own trust evidence. The read
    is bound to RuntimeConfig's exact repo, branch and path. A conditional
    GitHub write remains mandatory later. This does not certify branch
    ancestry, independent monotonic heads, owner authority or effects.
    """
    expected_source=f"GitHub:{config.branch}:{config.path}"
    caller_source=current_runtime.get("source")
    if caller_source is not None and (
        type(caller_source) is not str or caller_source!=expected_source
    ):
        return {"allowed":False,"reason":"Current runtime source disagrees with the destination."}
    try:
        observed=load_runtime_checkpoint(config,timeout=min(float(timeout),12.0))
    except Exception:
        return {"allowed":False,"reason":"Current runtime readback failed."}
    if not isinstance(observed,Mapping):
        return {"allowed":False,"reason":"Current runtime readback envelope is invalid."}
    if str(observed.get("status") or "").upper()!="CONFIRMED":
        return {"allowed":False,"reason":"Current destination runtime could not be confirmed."}
    if (
        type(observed.get("source")) is not str
        or observed.get("source")!=expected_source
    ):
        return {"allowed":False,"reason":"Current destination source is inconsistent."}
    if (
        type(observed.get("sha")) is not str
        or observed.get("sha")!=preflight.get("expected_sha")
    ):
        return {"allowed":False,"reason":"Current destination SHA changed or is invalid."}
    seen_checkpoint=observed.get("checkpoint")
    expected_checkpoint=current_runtime.get("checkpoint")
    if (
        not isinstance(seen_checkpoint,Mapping)
        or not seen_checkpoint
        or not isinstance(expected_checkpoint,Mapping)
        or not expected_checkpoint
    ):
        return {"allowed":False,"reason":"Current destination checkpoint is incomplete."}
    try:
        # Compare the complete observed JSON object, not only the truncated
        # stable digest (which intentionally omits volatile fields).
        same_content=seen_checkpoint==expected_checkpoint
    except Exception:
        same_content=False
    if same_content is not True:
        return {"allowed":False,"reason":"Current destination checkpoint differs from the selected runtime."}
    return {"allowed":True,"expected_sha":preflight["expected_sha"]}


def _verify_runtime_revision_ancestry(
    revision:Any,
    config:RuntimeConfig,
    *,
    timeout:float,
)->dict[str,Any]:
    """Review-only GitHub compare gate for ancestor revision selection.

    This verifies branch ancestry under the configured GitHub repository
    snapshot. It does NOT provide independent, monotonic-head authority,
    identity enrollment, revocation, or external no-effect receipts.
    """
    rev=_safe_revision(revision)
    if not rev:
        return {"allowed":False,"reason":"Historical revision is malformed.","executes_action":False}
    try:
        require_runtime_branch(config.branch)
        if (
            type(config.repo) is not str
            or re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+",config.repo) is None
        ):
            raise ValueError("Invalid configured GitHub repository.")
        safe_branch=quote(config.branch,safe="")
        safe_rev=quote(rev,safe="")
        import requests
        response=requests.get(
            f"https://api.github.com/repos/{config.repo}/compare/{safe_rev}...{safe_branch}",
            headers=_headers(config.token),
            timeout=min(float(timeout),12.0),
        )
        response.raise_for_status()
        raw=response.json()
    except Exception:
        return {"allowed":False,"reason":"Historical revision ancestry could not be verified.","executes_action":False}
    if not isinstance(raw,Mapping):
        return {"allowed":False,"reason":"Historical ancestry response is invalid.","executes_action":False}
    status=raw.get("status")
    base=raw.get("base_commit")
    common=raw.get("merge_base_commit")
    head=raw.get("head_commit")
    base_sha=base.get("sha") if isinstance(base,Mapping) else None
    common_sha=common.get("sha") if isinstance(common,Mapping) else None
    head_sha=head.get("sha") if isinstance(head,Mapping) else None
    good=bool(
        status in ("ahead","identical")
        and type(base_sha) is str and base_sha.lower()==rev.lower()
        and type(common_sha) is str and common_sha.lower()==rev.lower()
        and type(head_sha) is str and _REVISION_RE.fullmatch(head_sha)
        and (status!="identical" or head_sha.lower()==rev.lower())
    )
    if not good:
        return {
            "allowed":False,
            "reason":"Historical revision is not proven to be an ancestor of the configured runtime branch.",
            "executes_action":False,
        }
    return {
        "allowed":True,"revision":rev,"runtime_branch_head":head_sha,
        "executes_action":False,
    }



def _recheck_runtime_branch_head_before_save(
    ancestry:Mapping[str,Any],
    config:RuntimeConfig,
    *,
    timeout:float,
)->dict[str,Any]:
    """Fail closed if configured Git branch moved since the ancestry compare.

    GitHub itself remains ONE trust domain. This is a TOCTOU consistency
    fence only, never an independent monotonic-head witness.
    """
    head=ancestry.get("runtime_branch_head") if isinstance(ancestry,Mapping) else None
    if type(head) is not str or _REVISION_RE.fullmatch(head) is None:
        return {"allowed":False,"reason":"Compared runtime branch head is missing or malformed."}
    try:
        require_runtime_branch(config.branch)
        if (
            type(config.repo) is not str
            or re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+",config.repo) is None
        ):
            raise ValueError("Invalid GitHub repository.")
        import requests
        response=requests.get(
            f"https://api.github.com/repos/{config.repo}/git/ref/heads/{quote(config.branch,safe='')}",
            headers=_headers(config.token),
            timeout=min(float(timeout),12.0),
        )
        response.raise_for_status()
        raw=response.json()
    except Exception:
        return {"allowed":False,"reason":"Runtime branch head readback unavailable."}
    if not isinstance(raw,Mapping):
        return {"allowed":False,"reason":"Runtime branch head response is invalid."}
    obj=raw.get("object")
    observed=obj.get("sha") if isinstance(obj,Mapping) else None
    if (
        raw.get("ref")!=f"refs/heads/{config.branch}"
        or not isinstance(obj,Mapping)
        or obj.get("type")!="commit"
        or type(observed) is not str
        or _REVISION_RE.fullmatch(observed) is None
        or observed.lower()!=head.lower()
    ):
        return {"allowed":False,"reason":"Runtime branch head moved or was not verified."}
    return {"allowed":True,"runtime_branch_head":observed,"executes_action":False}



def _require_independent_recovery_head_witness(
    config:RuntimeConfig,
    *,
    ancestry:Mapping[str,Any],
    current_blob_sha:Any,
    candidate_revision:Any,
)->dict[str,Any]:
    """A134 HARD NO-GO until an independently ENROLLED witness exists.

    There is currently no trusted off-GitHub enrollment, revocation, durable
    monotonic-head READ or authenticated provider-backed CAS in this runtime.
    Therefore no environmental boolean, caller-supplied certificate, GitHub
    response, or current blob SHA may authorize a historical restore.
    This deliberately refuses ALL real restore writes. Positive mock tests
    of downstream legacy CAS are NOT enrollment or an operational bypass.
    Implementing a real provider requires a separate reviewed trust ceremony.
    """
    return {
        "allowed":False,
        "status":"BLOCKED",
        "reason":"INDEPENDENT_MONOTONIC_HEAD_WITNESS_NOT_ENROLLED",
        "independent_witness_enrolled":False,
        "monotonic_head_proven":False,
        "human_owner_verified":False,
        "restoration_authorized":False,
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
    if approved is not True:
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

    # A129 LAB: before reading the historical candidate, re-observe the
    # exact configured runtime destination. A source label or blob SHA
    # supplied by the caller is insufficient, even with approved=True.
    target_check=_recheck_live_restore_target(
        current_runtime,preflight,config,timeout=timeout,
    )
    if target_check.get("allowed") is not True:
        return {
            "schema":SCHEMA,"status":"BLOCKED","saved":False,"verified":False,
            "reason":target_check.get("reason") or "Current destination is unverified.",
            "preflight":preflight,
            "restore_confirmed":False,
            "reconciliation_required":False,
            "automatic_retry_allowed":False,
            "automatic_restore":False,
        }

    revision=str(preflight.get("candidate_revision") or "")
    ancestry=_verify_runtime_revision_ancestry(
        revision,config,timeout=timeout,
    )
    if ancestry.get("allowed") is not True:
        return {
            "schema":SCHEMA,"status":"BLOCKED","saved":False,"verified":False,
            "reason":ancestry.get("reason") or "Historical ancestry is unverified.",
            "preflight":preflight,
            "restore_confirmed":False,
            "reconciliation_required":False,
            "automatic_retry_allowed":False,
            "automatic_restore":False,
        }
    rebound_candidate=load_checkpoint_revision(
        revision,
        config,
        timeout=min(float(timeout),12.0),
    )
    if str(rebound_candidate.get("status") or "").upper()!="CONFIRMED":
        return {
            "schema":SCHEMA,
            "status":"BLOCKED",
            "saved":False,
            "verified":False,
            "reason":"Historical recovery revision could not be revalidated.",
            "preflight":preflight,
            "revision_revalidation":{
                "status":str(rebound_candidate.get("status") or "UNKNOWN"),
                "reason":str(rebound_candidate.get("reason") or ""),
            },
            "requested_revision":revision,
            "restored_revision":"",
            "restore_confirmed":False,
            "reconciliation_required":False,
            "automatic_retry_allowed":False,
            "automatic_restore":False,
        }

    rebound_preflight=recovery_preflight(current_runtime,rebound_candidate)
    if not rebound_preflight.get("allowed"):
        return {
            "schema":SCHEMA,
            "status":"BLOCKED",
            "saved":False,
            "verified":False,
            "reason":"Revalidated historical revision failed recovery preflight.",
            "preflight":preflight,
            "revision_revalidation":rebound_preflight,
            "requested_revision":revision,
            "restored_revision":"",
            "restore_confirmed":False,
            "reconciliation_required":False,
            "automatic_retry_allowed":False,
            "automatic_restore":False,
        }

    selected_digest=str(preflight.get("candidate_digest") or "")
    rebound_digest=str(rebound_preflight.get("candidate_digest") or "")
    if not selected_digest or selected_digest!=rebound_digest:
        return {
            "schema":SCHEMA,
            "status":"BLOCKED",
            "saved":False,
            "verified":False,
            "reason":"Selected recovery candidate does not match the historical revision.",
            "preflight":preflight,
            "revision_revalidation":rebound_preflight,
            "requested_revision":revision,
            "restored_revision":"",
            "restore_confirmed":False,
            "reconciliation_required":False,
            "automatic_retry_allowed":False,
            "automatic_restore":False,
        }

    # A133 LAB: even a valid GitHub ancestry response may be stale when the
    # branch moves during historical readback. Recheck HEAD before any save.
    branch_head_check=_recheck_runtime_branch_head_before_save(
        ancestry,config,timeout=timeout,
    )
    if branch_head_check.get("allowed") is not True:
        return {
            "schema":SCHEMA,"status":"BLOCKED","saved":False,"verified":False,
            "reason":branch_head_check.get("reason") or "Runtime branch head changed.",
            "preflight":preflight,
            "requested_revision":revision,"restored_revision":"",
            "restore_confirmed":False,"reconciliation_required":False,
            "automatic_retry_allowed":False,"automatic_restore":False,
        }
    # A134: GitHub branch HEAD agreement is not an independently witnessed
    # last head. No real custodian/trust enrollment exists, so hard-deny the
    # recovery write even when approved=True and GitHub checks all agree.
    witness_admission=_require_independent_recovery_head_witness(
        config,
        ancestry=ancestry,
        current_blob_sha=preflight.get("expected_sha"),
        candidate_revision=revision,
    )
    if witness_admission.get("allowed") is not True:
        return {
            "schema":SCHEMA,"status":"BLOCKED","saved":False,"verified":False,
            "reason":witness_admission.get("reason")
                or "Independent recovery witness unavailable.",
            "preflight":preflight,
            "requested_revision":revision,"restored_revision":"",
            "restore_confirmed":False,"reconciliation_required":False,
            "automatic_retry_allowed":False,"automatic_restore":False,
            "independent_witness_enrolled":False,
            "monotonic_head_proven":False,
            "human_owner_verified":False,
        }
    preflight=rebound_preflight
    checkpoint=ensure_operating_checkpoint(rebound_candidate.get("checkpoint"))
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
    confirmed=bool(
        result.get("status")=="CONFIRMED"
        and result.get("saved") is True
        and result.get("verified") is True
    )
    requested_revision=preflight.get("candidate_revision")
    output["schema"]=SCHEMA
    output["recovery_preflight"]=preflight
    output["requested_revision"]=requested_revision
    output["restored_revision"]=requested_revision if confirmed else ""
    output["restore_confirmed"]=confirmed
    output["reconciliation_required"]=bool(result.get("reconciliation_required"))
    output["automatic_retry_allowed"]=False
    output["automatic_restore"]=False
    return output


__all__=[
    "SCHEMA",
    "list_checkpoint_revisions",
    "load_checkpoint_revision",
    "recovery_preflight",
    "restore_checkpoint_revision",
]
