"""Fail-closed persistence contract for future per-subscriber AION memory.

This module deliberately performs no network I/O. It prepares safe read/write
plans for a future runtime connector while enforcing:
- authenticated USER/SALES tenant identity;
- confirmed AION_PERSONAL entitlement;
- dedicated runtime-data branch only;
- tenant-specific path only;
- explicit approval before writes;
- optimistic-concurrency revision checks;
- size limits and tenant-id integrity;
- no fallback to ADMIN/project/other-tenant memory.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence
import hashlib
import json

from atlasquant_runtime_store import evaluate_runtime_branch, require_runtime_branch
from atlasquant_aion_tenant import (
    personal_aion_eligibility,
    sanitize_tenant_memory,
    tenant_namespace,
    tenant_runtime_path,
)

SCHEMA="ATLASQUANT_AION_TENANT_STORE_V1"
MAX_TENANT_MEMORY_BYTES=256_000


def _now()->str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class TenantStoreTarget:
    tenant_id:str
    branch:str
    path:str

    def as_dict(self)->dict[str,Any]:
        return asdict(self)


def tenant_store_target(
    access:Mapping[str,Any]|None,
    *,
    runtime_branch:Any="atlasquant-runtime",
)->dict[str,Any]:
    ns=tenant_namespace(access)
    if not ns["ready"]:
        return {
            "schema":SCHEMA,
            "ready":False,
            "reason":ns["reason"],
            "tenant_id":"",
            "branch":"",
            "path":"",
        }
    policy=evaluate_runtime_branch(str(runtime_branch or ""))
    if not policy.safe_for_runtime_writes:
        return {
            "schema":SCHEMA,
            "ready":False,
            "reason":"UNSAFE_RUNTIME_BRANCH",
            "tenant_id":ns["tenant_id"],
            "branch":policy.branch,
            "path":"",
        }
    branch=require_runtime_branch(policy.branch)
    path=tenant_runtime_path(access)
    if not path:
        return {
            "schema":SCHEMA,
            "ready":False,
            "reason":"TENANT_PATH_UNAVAILABLE",
            "tenant_id":ns["tenant_id"],
            "branch":branch,
            "path":"",
        }
    target=TenantStoreTarget(ns["tenant_id"],branch,path)
    return {
        "schema":SCHEMA,
        "ready":True,
        "reason":"OK",
        **target.as_dict(),
    }


def _foreign_tenant_memory(
    memory:Mapping[str,Any]|None,
    access:Mapping[str,Any]|None,
)->bool:
    ns=tenant_namespace(access)
    if not ns["ready"] or not isinstance(memory,Mapping):
        return False
    raw_tenant=str(memory.get("tenant_id") or "").strip()
    return bool(raw_tenant and raw_tenant!=str(ns["tenant_id"]))


def tenant_memory_source_digest(
    memory:Mapping[str,Any]|None,
    access:Mapping[str,Any]|None,
)->str:
    payload=sanitize_tenant_memory(memory,access)
    payload=deepcopy(payload)
    payload.pop("created_at",None)
    payload.pop("updated_at",None)
    raw=json.dumps(payload,ensure_ascii=False,sort_keys=True,default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:24]


def tenant_memory_payload(
    memory:Mapping[str,Any]|None,
    access:Mapping[str,Any]|None,
)->dict[str,Any]:
    payload=sanitize_tenant_memory(memory,access)
    payload["schema"]="ATLASQUANT_AION_TENANT_V1"
    payload["updated_at"]=_now()
    raw=json.dumps(payload,ensure_ascii=False,sort_keys=True,default=str).encode("utf-8")
    if len(raw)>MAX_TENANT_MEMORY_BYTES:
        raise ValueError("tenant memory exceeds size limit")
    return payload


def revision_matches(expected:Any,current:Any)->bool:
    expected_clean=str(expected or "").strip()
    current_clean=str(current or "").strip()
    if not expected_clean:
        return not current_clean
    return bool(current_clean and expected_clean==current_clean)


def prepare_tenant_load(
    access:Mapping[str,Any]|None,
    entitlements:Sequence[Mapping[str,Any]]|None,
    *,
    runtime_branch:Any="atlasquant-runtime",
    now:datetime|None=None,
)->dict[str,Any]:
    eligibility=personal_aion_eligibility(access,entitlements,now=now)
    target=tenant_store_target(access,runtime_branch=runtime_branch)
    allowed=bool(eligibility["eligible"] and target["ready"])
    reason=(
        "OK"
        if allowed
        else eligibility["reason"]
        if not eligibility["eligible"]
        else target["reason"]
    )
    return {
        "schema":SCHEMA,
        "allowed":allowed,
        "reason":reason,
        "target":target,
        "executes_network":False,
        "executes_read":False,
        "admin_memory_fallback":False,
        "other_tenant_fallback":False,
    }


def prepare_tenant_write(
    access:Mapping[str,Any]|None,
    entitlements:Sequence[Mapping[str,Any]]|None,
    memory:Mapping[str,Any]|None,
    *,
    runtime_branch:Any="atlasquant-runtime",
    approved:bool=False,
    expected_revision:Any="",
    now:datetime|None=None,
)->dict[str,Any]:
    eligibility=personal_aion_eligibility(access,entitlements,now=now)
    target=tenant_store_target(access,runtime_branch=runtime_branch)

    if not eligibility["eligible"]:
        return {
            "schema":SCHEMA,
            "allowed":False,
            "reason":eligibility["reason"],
            "target":target,
            "executes_network":False,
            "executes_write":False,
            "approved":bool(approved),
        }
    if not target["ready"]:
        return {
            "schema":SCHEMA,
            "allowed":False,
            "reason":target["reason"],
            "target":target,
            "executes_network":False,
            "executes_write":False,
            "approved":bool(approved),
        }
    if _foreign_tenant_memory(memory,access):
        return {
            "schema":SCHEMA,
            "allowed":False,
            "reason":"FOREIGN_TENANT_MEMORY_REJECTED",
            "target":target,
            "executes_network":False,
            "executes_write":False,
            "approved":bool(approved),
        }
    if not approved:
        return {
            "schema":SCHEMA,
            "allowed":False,
            "reason":"EXPLICIT_WRITE_APPROVAL_REQUIRED",
            "target":target,
            "executes_network":False,
            "executes_write":False,
            "approved":False,
        }

    payload=tenant_memory_payload(memory,access)
    return {
        "schema":SCHEMA,
        "allowed":True,
        "reason":"WRITE_PLAN_READY",
        "target":target,
        "payload":payload,
        "payload_digest":tenant_memory_source_digest(payload,access),
        "expected_revision":str(expected_revision or "").strip(),
        "executes_network":False,
        "executes_write":False,
        "approved":True,
        "account_registry_changed":False,
        "role_changed":False,
        "billing_changed":False,
        "real_trading_changed":False,
    }


def accept_loaded_memory(
    access:Mapping[str,Any]|None,
    entitlements:Sequence[Mapping[str,Any]]|None,
    raw_memory:Mapping[str,Any]|None,
    *,
    runtime_branch:Any="atlasquant-runtime",
    now:datetime|None=None,
)->dict[str,Any]:
    plan=prepare_tenant_load(
        access,
        entitlements,
        runtime_branch=runtime_branch,
        now=now,
    )
    if not plan["allowed"]:
        return {
            "schema":SCHEMA,
            "accepted":False,
            "reason":plan["reason"],
            "memory":None,
            "target":plan["target"],
        }
    ns=tenant_namespace(access)
    raw=dict(raw_memory or {})
    raw_tenant=str(raw.get("tenant_id") or "")
    if raw_tenant and raw_tenant!=ns["tenant_id"]:
        return {
            "schema":SCHEMA,
            "accepted":False,
            "reason":"FOREIGN_TENANT_MEMORY_REJECTED",
            "memory":None,
            "target":plan["target"],
        }
    memory=sanitize_tenant_memory(raw,access)
    return {
        "schema":SCHEMA,
        "accepted":True,
        "reason":"OK",
        "memory":memory,
        "source_digest":tenant_memory_source_digest(memory,access),
        "target":plan["target"],
    }


def resolve_write_conflict(
    *,
    expected_revision:Any,
    current_revision:Any,
)->dict[str,Any]:
    ok=revision_matches(expected_revision,current_revision)
    return {
        "schema":SCHEMA,
        "can_write":ok,
        "reason":"REVISION_MATCH" if ok else "REVISION_CONFLICT",
        "requires_reload":not ok,
        "automatic_overwrite":False,
    }


def tenant_memory_change_summary(
    before:Mapping[str,Any]|None,
    after:Mapping[str,Any]|None,
    access:Mapping[str,Any]|None,
)->dict[str,Any]:
    before_foreign=_foreign_tenant_memory(before,access)
    after_foreign=_foreign_tenant_memory(after,access)
    a=sanitize_tenant_memory(before,access)
    b=sanitize_tenant_memory(after,access)
    a_profile=a.get("profile") if isinstance(a.get("profile"),Mapping) else {}
    b_profile=b.get("profile") if isinstance(b.get("profile"),Mapping) else {}
    return {
        "schema":SCHEMA,
        "tenant_id":a["tenant_id"],
        "same_tenant":a["tenant_id"]==b["tenant_id"],
        "profile_changed":a_profile!=b_profile,
        "notes_before":len(a.get("conversation_notes") or []),
        "notes_after":len(b.get("conversation_notes") or []),
        "watchlist_before":len(a.get("watchlist") or []),
        "watchlist_after":len(b.get("watchlist") or []),
        "academy_items_before":len(a.get("academy_progress") or {}),
        "academy_items_after":len(b.get("academy_progress") or {}),
        "before_digest":tenant_memory_source_digest(a,access),
        "after_digest":tenant_memory_source_digest(b,access),
        "contains_admin_memory":False,
        "contains_other_tenant_memory":bool(before_foreign or after_foreign),
    }


def tenant_store_policy()->dict[str,Any]:
    return {
        "schema":SCHEMA,
        "network_io_implemented":False,
        "automatic_write":False,
        "automatic_overwrite":False,
        "explicit_write_approval_required":True,
        "confirmed_entitlement_required":True,
        "code_branch_write_allowed":False,
        "admin_memory_fallback":False,
        "other_tenant_fallback":False,
        "max_tenant_memory_bytes":MAX_TENANT_MEMORY_BYTES,
    }


__all__=[
    "SCHEMA","MAX_TENANT_MEMORY_BYTES","TenantStoreTarget",
    "tenant_store_target","tenant_memory_source_digest","tenant_memory_payload",
    "revision_matches","prepare_tenant_load","prepare_tenant_write",
    "accept_loaded_memory","resolve_write_conflict",
    "tenant_memory_change_summary","tenant_store_policy",
]
