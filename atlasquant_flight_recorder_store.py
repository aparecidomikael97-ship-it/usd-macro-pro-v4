"""Persistent AtlasQuant Flight Recorder storage.

Stores deduplicated decision snapshots on the dedicated runtime-data branch.
This module is fail-closed for code branches and never changes trading logic.
"""
from __future__ import annotations
from atlasquant_aion_v2_github_write_url_guard import guard_github_token_read_destination
from atlasquant_aion_v2_github_read_response_guard import reject_github_read_unexpected_status
from atlasquant_aion_v2_github_write_url_guard import guard_github_write_destination
from atlasquant_aion_v2_github_write_response_guard import reject_github_write_unexpected_status
from atlasquant_aion_v2_legacy_github_contents_readback import verify_legacy_jsonl_readback, decode_verified_github_contents

import base64
import json
from typing import Any, Iterable, Mapping
import requests

from atlasquant_runtime_store import require_runtime_branch


FLIGHT_RECORDER_PATH="dados/atlasquant_flight_recorder.jsonl"
DEFAULT_MAX_RECORDS=5000


def _record_key(row: Mapping[str, Any]) -> str:
    fp=str(row.get("_fingerprint","") or "").strip()
    if fp:
        return "fp:"+fp
    did=str(row.get("decision_id","") or "").strip()
    if did:
        return "id:"+did
    return "raw:"+json.dumps(dict(row),sort_keys=True,ensure_ascii=False,separators=(",",":"))


def parse_records(text: str) -> list[dict[str, Any]]:
    rows=[]
    for idx,line in enumerate(str(text or "").splitlines(),start=1):
        if not line.strip():
            continue
        try:
            obj=json.loads(line)
        except Exception as exc:
            raise ValueError(f"Invalid Flight Recorder JSONL at line {idx}") from exc
        if not isinstance(obj,dict):
            raise ValueError(f"Invalid Flight Recorder record at line {idx}")
        rows.append(obj)
    return rows


def serialize_records(records: Iterable[Mapping[str, Any]]) -> str:
    return "\n".join(
        json.dumps(dict(row),ensure_ascii=False,sort_keys=True,separators=(",",":"))
        for row in records
    ) + ("\n" if records else "")


def merge_unique_records(
    existing: Iterable[Mapping[str, Any]] | None,
    incoming: Iterable[Mapping[str, Any]] | None,
    *,
    max_records: int = DEFAULT_MAX_RECORDS,
) -> tuple[list[dict[str, Any]], int]:
    rows=[dict(x) for x in (existing or [])]
    seen={_record_key(x) for x in rows}
    added=0
    for raw in (incoming or []):
        row=dict(raw)
        key=_record_key(row)
        if key in seen:
            continue
        rows.append(row)
        seen.add(key)
        added+=1
    limit=max(1,int(max_records))
    if len(rows)>limit:
        rows=rows[-limit:]
    return rows,added


def _headers(token: str) -> dict[str,str]:
    return {
        "Authorization":f"Bearer {token}",
        "Accept":"application/vnd.github+json",
        "X-GitHub-Api-Version":"2022-11-28",
    }


def _contents_url(repo: str) -> str:
    return f"https://api.github.com/repos/{repo}/contents/{FLIGHT_RECORDER_PATH}"


def _fetch_remote(repo: str, branch: str, token: str, timeout: int) -> tuple[list[dict[str,Any]], str]:
    # A token/session cannot prove the legacy shared file belongs to a tenant.
    from atlasquant_private_read_gate_v1 import require_private_read
    from atlasquant_legacy_private_resource_gate_v1 import require_legacy_private_remote_resource
    require_private_read()
    require_legacy_private_remote_resource(FLIGHT_RECORDER_PATH)
    r=reject_github_read_unexpected_status(requests.get(
        guard_github_token_read_destination(_contents_url(repo)),
        headers=_headers(token),
        params={"ref":branch},
        timeout=timeout,
        allow_redirects=False,
    ))
    if r.status_code==404:
        return [],""
    r.raise_for_status()
    payload=r.json()
    raw,sha=decode_verified_github_contents(payload)
    return parse_records(raw),sha


def load_persistent_records(
    *,
    repo: str,
    branch: str,
    token: str,
    timeout: int = 15,
) -> list[dict[str,Any]]:
    from atlasquant_private_read_gate_v1 import require_private_read
    from atlasquant_legacy_private_resource_gate_v1 import require_legacy_private_remote_resource
    require_private_read()
    require_legacy_private_remote_resource(FLIGHT_RECORDER_PATH)
    safe_branch=require_runtime_branch(branch)
    if not str(token or "").strip() or not str(repo or "").strip():
        raise ValueError("Persistent Flight Recorder requires repo and token")
    rows,_=_fetch_remote(str(repo).strip(),safe_branch,str(token).strip(),timeout)
    return rows


def persist_records(
    records: Iterable[Mapping[str, Any]],
    *,
    repo: str,
    branch: str,
    token: str,
    timeout: int = 15,
    max_records: int = DEFAULT_MAX_RECORDS,
    retry_conflict_once: bool = True,
) -> dict[str,Any]:
    # Mandatory fail-closed until per-resource tenant provenance and an
    # independently witnessed CAS receipt exist. Historical protocol code
    # below is unreachable in production and only synthetic offline tests
    # can reconstruct it in a network-blocked reference harness.
    return {"ok":False,"reason":"HARD_DENIED","added":0,"records":0,
            "reconciliation_required":True,"safe_to_retry":False}
    try:
        safe_branch=require_runtime_branch(branch)
    except Exception as exc:
        return {"ok":False,"added":0,"records":0,"reason":"UNSAFE_BRANCH","error":str(exc)}

    repo=str(repo or "").strip()
    token=str(token or "").strip()
    if not repo or not token:
        return {"ok":False,"added":0,"records":0,"reason":"NOT_CONFIGURED","error":""}

    incoming=[dict(x) for x in records]
    # Legacy retry_conflict_once is accepted for caller compatibility, but
    # cannot grant another HTTP PUT without independently trusted CAS evidence.
    attempts=1

    for attempt in range(attempts):
        write_attempted = False
        try:
            existing,sha=_fetch_remote(repo,safe_branch,token,timeout)
            merged,added=merge_unique_records(existing,incoming,max_records=max_records)
            if added==0:
                return {"ok":True,"added":0,"records":len(merged),"reason":"ALREADY_PRESENT","error":""}

            serialized=serialize_records(merged)
            raw=serialized.encode("utf-8")
            payload={
                "message":"AtlasQuant: persist Flight Recorder snapshots",
                "content":base64.b64encode(raw).decode("ascii"),
                "branch":safe_branch,
            }
            if sha:
                payload["sha"]=sha

            # Conservative: from here a network failure can conceal a commit.
            write_attempted = True
            r=reject_github_write_unexpected_status(requests.put(
                guard_github_write_destination(_contents_url(repo)),
                headers=_headers(token),
                json=payload,
                timeout=timeout,
                allow_redirects=False,
            ),"contents_put")
            if r.status_code == 422:
                # 422 may be a validation error, not CAS conflict: never replay.
                return {
                    "ok":False,"added":0,"records":0,
                    "reason":"VALIDATION_REJECTED","error":"REPORTED_HTTP_422",
                    "write_outcome":"REPORTED_HTTP_422",
                    "reconciliation_required":True,"safe_to_retry":False,
                }
            if r.status_code == 409:
                # A reported conflict alone is not trusted permission to replay.
                return {
                    "ok":False,"added":0,"records":0,
                    "reason":"CONFLICT","error":"REPORTED_HTTP_409",
                    "write_outcome":"REPORTED_CAS_CONFLICT",
                    "reconciliation_required":True,"safe_to_retry":False,
                }
            r.raise_for_status()
            verification=verify_legacy_jsonl_readback(
                response=r,
                expected_text=serialized,
                readback=lambda: _fetch_remote(repo,safe_branch,token,timeout),
                serialize=serialize_records,
            )
            return {"ok":True,"added":added,"records":len(merged),"reason":"SAVED","error":"",**verification}
        except ValueError as exc:
            if write_attempted:
                return {
                    "ok":False,"added":0,"records":0,
                    "reason":"UNKNOWN_OUTCOME","error":type(exc).__name__,
                    "write_outcome":"UNKNOWN","write_attempted":True,
                    "reconciliation_required":True,"safe_to_retry":False,
                }
            return {"ok":False,"added":0,"records":0,"reason":"CORRUPT_REMOTE","error":str(exc)}
        except Exception as exc:
            if write_attempted:
                return {
                    "ok":False,"added":0,"records":0,
                    "reason":"UNKNOWN_OUTCOME","error":type(exc).__name__,
                    "write_outcome":"UNKNOWN","write_attempted":True,
                    "reconciliation_required":True,"safe_to_retry":False,
                }
            return {"ok":False,"added":0,"records":0,"reason":"IO_ERROR","error":f"{type(exc).__name__}: {exc}"}
    return {"ok":False,"added":0,"records":0,"reason":"CONFLICT","error":"Concurrent update conflict"}
