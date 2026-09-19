"""Persistent AtlasQuant Flight Recorder storage.

Stores deduplicated decision snapshots on the dedicated runtime-data branch.
This module is fail-closed for code branches and never changes trading logic.
"""
from __future__ import annotations

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
    r=requests.get(
        _contents_url(repo),
        headers=_headers(token),
        params={"ref":branch},
        timeout=timeout,
    )
    if r.status_code==404:
        return [],""
    r.raise_for_status()
    payload=r.json()
    raw=base64.b64decode(payload.get("content","")).decode("utf-8")
    return parse_records(raw),str(payload.get("sha","") or "")


def load_persistent_records(
    *,
    repo: str,
    branch: str,
    token: str,
    timeout: int = 15,
) -> list[dict[str,Any]]:
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
    try:
        safe_branch=require_runtime_branch(branch)
    except Exception as exc:
        return {"ok":False,"added":0,"records":0,"reason":"UNSAFE_BRANCH","error":str(exc)}

    repo=str(repo or "").strip()
    token=str(token or "").strip()
    if not repo or not token:
        return {"ok":False,"added":0,"records":0,"reason":"NOT_CONFIGURED","error":""}

    incoming=[dict(x) for x in records]
    attempts=2 if retry_conflict_once else 1

    for attempt in range(attempts):
        try:
            existing,sha=_fetch_remote(repo,safe_branch,token,timeout)
            merged,added=merge_unique_records(existing,incoming,max_records=max_records)
            if added==0:
                return {"ok":True,"added":0,"records":len(merged),"reason":"ALREADY_PRESENT","error":""}

            raw=serialize_records(merged).encode("utf-8")
            payload={
                "message":"AtlasQuant: persist Flight Recorder snapshots",
                "content":base64.b64encode(raw).decode("ascii"),
                "branch":safe_branch,
            }
            if sha:
                payload["sha"]=sha

            r=requests.put(
                _contents_url(repo),
                headers=_headers(token),
                json=payload,
                timeout=timeout,
            )
            if r.status_code in (409,422) and attempt+1<attempts:
                continue
            r.raise_for_status()
            return {"ok":True,"added":added,"records":len(merged),"reason":"SAVED","error":""}
        except ValueError as exc:
            # Corrupt remote JSONL: never overwrite it.
            return {"ok":False,"added":0,"records":0,"reason":"CORRUPT_REMOTE","error":str(exc)}
        except Exception as exc:
            return {"ok":False,"added":0,"records":0,"reason":"IO_ERROR","error":f"{type(exc).__name__}: {exc}"}

    return {"ok":False,"added":0,"records":0,"reason":"CONFLICT","error":"Concurrent update conflict"}
