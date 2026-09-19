"""Persistent AtlasQuant Shadow Mode sample store."""
from __future__ import annotations

import base64
import json
from typing import Any, Iterable, Mapping
import requests

from atlasquant_runtime_store import require_runtime_branch


SHADOW_PATH="dados/atlasquant_shadow_samples.jsonl"
DEFAULT_MAX_SAMPLES=10000


def parse_samples(text: str) -> list[dict[str,Any]]:
    rows=[]
    for idx,line in enumerate(str(text or "").splitlines(),start=1):
        if not line.strip():
            continue
        try:
            obj=json.loads(line)
        except Exception as exc:
            raise ValueError(f"Invalid Shadow JSONL at line {idx}") from exc
        if not isinstance(obj,dict):
            raise ValueError(f"Invalid Shadow sample at line {idx}")
        rows.append(obj)
    return rows


def serialize_samples(samples: Iterable[Mapping[str,Any]]) -> str:
    rows=[dict(x) for x in samples]
    return "\n".join(
        json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(",",":"))
        for x in rows
    ) + ("\n" if rows else "")


def merge_unique_samples(
    existing: Iterable[Mapping[str,Any]] | None,
    incoming: Iterable[Mapping[str,Any]] | None,
    *,
    max_samples: int = DEFAULT_MAX_SAMPLES,
) -> tuple[list[dict[str,Any]],int]:
    rows=[dict(x) for x in (existing or [])]
    seen={str(x.get("sample_id","")) for x in rows if str(x.get("sample_id",""))}
    added=0
    for raw in (incoming or []):
        row=dict(raw)
        sid=str(row.get("sample_id",""))
        if sid and sid in seen:
            continue
        rows.append(row)
        if sid: seen.add(sid)
        added+=1
    limit=max(1,int(max_samples))
    if len(rows)>limit:
        rows=rows[-limit:]
    return rows,added


def _headers(token: str) -> dict[str,str]:
    return {
        "Authorization":f"Bearer {token}",
        "Accept":"application/vnd.github+json",
        "X-GitHub-Api-Version":"2022-11-28",
    }


def _url(repo: str) -> str:
    return f"https://api.github.com/repos/{repo}/contents/{SHADOW_PATH}"


def _fetch(repo: str, branch: str, token: str, timeout: int):
    r=requests.get(_url(repo),headers=_headers(token),params={"ref":branch},timeout=timeout)
    if r.status_code==404:
        return [],""
    r.raise_for_status()
    payload=r.json()
    raw=base64.b64decode(payload.get("content","")).decode("utf-8")
    return parse_samples(raw),str(payload.get("sha","") or "")


def load_shadow_samples(*,repo: str,branch: str,token: str,timeout: int=15):
    safe=require_runtime_branch(branch)
    if not str(repo or "").strip() or not str(token or "").strip():
        raise ValueError("Shadow persistence requires repo and token")
    rows,_=_fetch(str(repo).strip(),safe,str(token).strip(),timeout)
    return rows


def persist_shadow_samples(
    samples: Iterable[Mapping[str,Any]],
    *,
    repo: str,
    branch: str,
    token: str,
    timeout: int=15,
    max_samples: int=DEFAULT_MAX_SAMPLES,
    retry_conflict_once: bool=True,
) -> dict[str,Any]:
    try:
        safe=require_runtime_branch(branch)
    except Exception as exc:
        return {"ok":False,"added":0,"samples":0,"reason":"UNSAFE_BRANCH","error":str(exc)}

    repo=str(repo or "").strip(); token=str(token or "").strip()
    if not repo or not token:
        return {"ok":False,"added":0,"samples":0,"reason":"NOT_CONFIGURED","error":""}

    incoming=[dict(x) for x in samples]
    attempts=2 if retry_conflict_once else 1
    for attempt in range(attempts):
        try:
            existing,sha=_fetch(repo,safe,token,timeout)
            merged,added=merge_unique_samples(existing,incoming,max_samples=max_samples)
            if added==0:
                return {"ok":True,"added":0,"samples":len(merged),"reason":"ALREADY_PRESENT","error":""}
            payload={
                "message":"AtlasQuant: persist Shadow Mode samples",
                "content":base64.b64encode(serialize_samples(merged).encode("utf-8")).decode("ascii"),
                "branch":safe,
            }
            if sha: payload["sha"]=sha
            r=requests.put(_url(repo),headers=_headers(token),json=payload,timeout=timeout)
            if r.status_code in (409,422) and attempt+1<attempts:
                continue
            r.raise_for_status()
            return {"ok":True,"added":added,"samples":len(merged),"reason":"SAVED","error":""}
        except ValueError as exc:
            return {"ok":False,"added":0,"samples":0,"reason":"CORRUPT_REMOTE","error":str(exc)}
        except Exception as exc:
            return {"ok":False,"added":0,"samples":0,"reason":"IO_ERROR","error":f"{type(exc).__name__}: {exc}"}
    return {"ok":False,"added":0,"samples":0,"reason":"CONFLICT","error":"Concurrent update conflict"}
