"""Persistent AtlasQuant operational research evidence store.

Runtime-only persistence. Records are written to the dedicated runtime-data
branch, never to main/dev. The store is append/merge oriented and does not
change strategy parameters, gates, permissions or trading execution.
"""
from __future__ import annotations

import base64
from hashlib import sha256
import json
from typing import Any, Iterable, Mapping

import requests

from atlasquant_runtime_store import require_runtime_branch

SCHEMA="ATLASQUANT_RESEARCH_EVIDENCE_STORE_V1"
RESEARCH_EVIDENCE_PATH="dados/atlasquant_operational_evidence_v1.jsonl"
DEFAULT_MAX_RECORDS=5000


def _canonical_json(value:Any)->str:
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(",",":"),default=str)


def evidence_record(
    *,
    strategy:object,
    captured_at:object,
    source:object,
    passport:Mapping[str,Any]|None=None,
    evidence:Mapping[str,Any]|None=None,
    pair:object="",
)->dict[str,Any]:
    payload={
        "schema":SCHEMA,
        "strategy":str(strategy or "").strip(),
        "captured_at":str(captured_at or "").strip(),
        "source":str(source or "").strip().upper(),
        "pair":str(pair or "").strip().upper(),
        "passport":dict(passport or {}),
        "evidence":dict(evidence or {}),
        "automatic_promotion":False,
        "automatic_strategy_change":False,
        "real_orders_enabled":False,
    }
    identity={
        "strategy":payload["strategy"],
        "captured_at":payload["captured_at"],
        "source":payload["source"],
        "pair":payload["pair"],
        "passport":payload["passport"],
        "evidence":payload["evidence"],
    }
    payload["record_id"]=sha256(_canonical_json(identity).encode("utf-8")).hexdigest()
    return payload


def parse_evidence_records(text:str)->list[dict[str,Any]]:
    rows=[]
    for idx,line in enumerate(str(text or "").splitlines(),start=1):
        if not line.strip():
            continue
        try:
            obj=json.loads(line)
        except Exception as exc:
            raise ValueError(f"Invalid research evidence JSONL at line {idx}") from exc
        if not isinstance(obj,dict):
            raise ValueError(f"Invalid research evidence record at line {idx}")
        rid=str(obj.get("record_id") or "").strip()
        if not rid:
            raise ValueError(f"Missing research evidence record_id at line {idx}")
        rows.append(obj)
    return rows


def serialize_evidence_records(records:Iterable[Mapping[str,Any]])->str:
    rows=[dict(x) for x in records]
    return "\n".join(_canonical_json(x) for x in rows)+("\n" if rows else "")


def merge_evidence_records(
    existing:Iterable[Mapping[str,Any]]|None,
    incoming:Iterable[Mapping[str,Any]]|None,
    *,
    max_records:int=DEFAULT_MAX_RECORDS,
)->tuple[list[dict[str,Any]],int]:
    rows=[dict(x) for x in (existing or [])]
    seen={str(x.get("record_id") or "") for x in rows if str(x.get("record_id") or "")}
    added=0
    for raw in incoming or []:
        row=dict(raw)
        rid=str(row.get("record_id") or "")
        if not rid:
            continue
        if rid in seen:
            continue
        rows.append(row)
        seen.add(rid)
        added+=1
    limit=max(1,int(max_records))
    if len(rows)>limit:
        rows=rows[-limit:]
    return rows,added


def latest_evidence_by_strategy(
    records:Iterable[Mapping[str,Any]]|None,
)->dict[str,dict[str,Any]]:
    out={}
    for raw in records or []:
        row=dict(raw)
        strategy=str(row.get("strategy") or "").strip()
        if not strategy:
            continue
        current=out.get(strategy)
        if current is None or str(row.get("captured_at") or "")>=str(current.get("captured_at") or ""):
            out[strategy]=row
    return out


def _headers(token:str)->dict[str,str]:
    return {
        "Authorization":f"Bearer {token}",
        "Accept":"application/vnd.github+json",
        "X-GitHub-Api-Version":"2022-11-28",
    }


def _url(repo:str)->str:
    return f"https://api.github.com/repos/{repo}/contents/{RESEARCH_EVIDENCE_PATH}"


def _fetch(repo:str,branch:str,token:str,timeout:int)->tuple[list[dict[str,Any]],str]:
    response=requests.get(
        _url(repo),
        headers=_headers(token),
        params={"ref":branch},
        timeout=timeout,
    )
    if response.status_code==404:
        return [],""
    response.raise_for_status()
    payload=response.json()
    raw=base64.b64decode(payload.get("content","")).decode("utf-8")
    return parse_evidence_records(raw),str(payload.get("sha","") or "")


def load_research_evidence(
    *,
    repo:str,
    branch:str,
    token:str,
    timeout:int=15,
)->list[dict[str,Any]]:
    safe=require_runtime_branch(branch)
    if not str(repo or "").strip() or not str(token or "").strip():
        raise ValueError("Research evidence persistence requires repo and token")
    rows,_=_fetch(str(repo).strip(),safe,str(token).strip(),timeout)
    return rows


def persist_research_evidence(
    records:Iterable[Mapping[str,Any]],
    *,
    repo:str,
    branch:str,
    token:str,
    timeout:int=15,
    max_records:int=DEFAULT_MAX_RECORDS,
    retry_conflict_once:bool=True,
)->dict[str,Any]:
    try:
        safe=require_runtime_branch(branch)
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
            existing,remote_sha=_fetch(repo,safe,token,timeout)
            merged,added=merge_evidence_records(existing,incoming,max_records=max_records)
            if added==0:
                return {
                    "ok":True,"added":0,"records":len(merged),
                    "reason":"ALREADY_PRESENT","error":"","branch":safe,
                }
            payload={
                "message":"AtlasQuant: persist operational research evidence",
                "content":base64.b64encode(
                    serialize_evidence_records(merged).encode("utf-8")
                ).decode("ascii"),
                "branch":safe,
            }
            if remote_sha:
                payload["sha"]=remote_sha
            response=requests.put(
                _url(repo),
                headers=_headers(token),
                json=payload,
                timeout=timeout,
            )
            if response.status_code in (409,422) and attempt+1<attempts:
                continue
            response.raise_for_status()
            return {
                "ok":True,"added":added,"records":len(merged),
                "reason":"SAVED","error":"","branch":safe,
            }
        except ValueError as exc:
            return {
                "ok":False,"added":0,"records":0,
                "reason":"CORRUPT_REMOTE","error":str(exc),"branch":safe,
            }
        except Exception as exc:
            return {
                "ok":False,"added":0,"records":0,
                "reason":"IO_ERROR","error":f"{type(exc).__name__}: {exc}","branch":safe,
            }
    return {
        "ok":False,"added":0,"records":0,
        "reason":"CONFLICT","error":"Concurrent update conflict","branch":safe,
    }


__all__=[
    "SCHEMA",
    "RESEARCH_EVIDENCE_PATH",
    "DEFAULT_MAX_RECORDS",
    "evidence_record",
    "parse_evidence_records",
    "serialize_evidence_records",
    "merge_evidence_records",
    "latest_evidence_by_strategy",
    "load_research_evidence",
    "persist_research_evidence",
]
