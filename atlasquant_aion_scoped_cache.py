"""Scoped local retrieval cache for AION.

Cache is an optimization only. Keys bind tenant/workspace + policy version +
data version. Dynamic/sensitive classes are structurally non-cacheable.
No provider prompt-cache assumptions are made here.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from typing import Any, Mapping, Sequence

from atlasquant_aion_observability import redact_text

SCHEMA = "ATLASQUANT_AION_SCOPED_RETRIEVAL_CACHE_V1"
MAX_ENTRIES = 5000
MAX_TTL_SECONDS = 3600
NON_CACHEABLE_CLASSES = frozenset({
    "LIVE_MARKET",
    "AUTHORITY",
    "CREDENTIAL",
    "SECRET",
    "PAYMENT",
    "TRADING_EXECUTION",
    "PERSONAL_DATA_SENSITIVE",
})


def _clean(value: Any, limit: int = 4000) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _aware(value: Any = None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if isinstance(value, datetime):
        out = value
    else:
        out = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if out.tzinfo is None:
        raise ValueError("timezone-aware timestamp required")
    return out.astimezone(timezone.utc)


def _scope(context: Mapping[str, Any] | None) -> tuple[str, str]:
    raw = dict(context or {})
    tenant = _clean(raw.get("tenant_id"), 120)
    workspace = _clean(raw.get("workspace_id"), 120)
    if not tenant or not workspace:
        raise ValueError("trusted tenant/workspace required")
    return tenant, workspace


def _refs(values: Sequence[Any] | None, limit: int = 80) -> list[str]:
    out: list[str] = []
    for raw in list(values or [])[:limit * 2]:
        value = _clean(raw, 300)
        if value and value not in out:
            out.append(value)
        if len(out) >= limit:
            break
    return out


def _key(
    tenant: str,
    workspace: str,
    *,
    policy_version: str,
    data_version: str,
    cache_class: str,
    query: str,
) -> str:
    raw = json.dumps(
        [tenant, workspace, policy_version, data_version, cache_class, query],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return sha256(raw.encode("utf-8")).hexdigest()


def empty_cache() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "entries": {},
        "provider_prompt_cache_trusted": False,
        "cross_tenant_sharing": False,
        "canonical_source": False,
        "executes_action": False,
    }


def cache_put(
    cache: Mapping[str, Any] | None,
    *,
    query: Any,
    value: Any,
    cache_class: Any,
    policy_version: Any,
    data_version: Any,
    source_refs: Sequence[Any] | None,
    requested_ttl_seconds: int,
    trusted_context: Mapping[str, Any] | None,
    source_valid_until: Any = None,
    now: Any = None,
) -> dict[str, Any]:
    state = dict(cache or empty_cache())
    tenant, workspace = _scope(trusted_context)
    cls = _clean(cache_class, 80).upper()
    if cls in NON_CACHEABLE_CLASSES:
        return {
            "schema": SCHEMA,
            "state": "NOT_CACHEABLE",
            "reason": "CACHE_CLASS_FORBIDDEN",
            "cache": state,
            "cached": False,
            "executes_action": False,
        }
    query_text = _clean(query, 1000)
    policy = _clean(policy_version, 160)
    data = _clean(data_version, 160)
    refs = _refs(source_refs)
    if not query_text or not policy or not data or not refs:
        raise ValueError("query/policy/data/source refs required")
    if isinstance(requested_ttl_seconds, bool):
        raise ValueError("invalid cache TTL")
    ttl = int(requested_ttl_seconds)
    if ttl <= 0:
        raise ValueError("cache TTL must be positive")
    ttl = min(ttl, MAX_TTL_SECONDS)
    current = _aware(now)
    if source_valid_until is not None:
        expiry = _aware(source_valid_until)
        remaining = int((expiry - current).total_seconds())
        if remaining <= 0:
            return {
                "schema": SCHEMA,
                "state": "NOT_CACHEABLE",
                "reason": "SOURCE_ALREADY_EXPIRED",
                "cache": state,
                "cached": False,
                "executes_action": False,
            }
        ttl = min(ttl, remaining)
    safe_value = redact_text(value)
    if "[REDACTED]" in safe_value:
        return {
            "schema": SCHEMA,
            "state": "NOT_CACHEABLE",
            "reason": "SECRET_LIKE_VALUE",
            "cache": state,
            "cached": False,
            "executes_action": False,
        }
    key = _key(
        tenant,
        workspace,
        policy_version=policy,
        data_version=data,
        cache_class=cls,
        query=query_text,
    )
    entries = {
        str(k): dict(v)
        for k, v in dict(state.get("entries") or {}).items()
        if isinstance(v, Mapping)
    }
    entries[key] = {
        "key": key,
        "tenant_id": tenant,
        "workspace_id": workspace,
        "policy_version": policy,
        "data_version": data,
        "cache_class": cls,
        "query_digest": "sha256:" + sha256(query_text.encode("utf-8")).hexdigest(),
        "value": safe_value[:12000],
        "source_refs": refs,
        "created_at": current.isoformat(),
        "expires_at": (current + timedelta(seconds=ttl)).isoformat(),
        "ttl_seconds": ttl,
        "canonical_source": False,
        "authority": "NONE",
    }
    if len(entries) > MAX_ENTRIES:
        ordered = sorted(
            entries.items(),
            key=lambda pair: pair[1].get("created_at", ""),
        )
        entries = dict(ordered[-MAX_ENTRIES:])
    updated = {
        "schema": SCHEMA,
        "entries": entries,
        "provider_prompt_cache_trusted": False,
        "cross_tenant_sharing": False,
        "canonical_source": False,
        "executes_action": False,
    }
    return {
        "schema": SCHEMA,
        "state": "CACHED",
        "key": key,
        "cache": updated,
        "cached": True,
        "ttl_seconds": ttl,
        "executes_action": False,
    }


def cache_get(
    cache: Mapping[str, Any] | None,
    *,
    query: Any,
    cache_class: Any,
    policy_version: Any,
    data_version: Any,
    trusted_context: Mapping[str, Any] | None,
    now: Any = None,
) -> dict[str, Any]:
    state = dict(cache or empty_cache())
    tenant, workspace = _scope(trusted_context)
    cls = _clean(cache_class, 80).upper()
    if cls in NON_CACHEABLE_CLASSES:
        return {
            "schema": SCHEMA,
            "state": "MISS",
            "reason": "CACHE_CLASS_FORBIDDEN",
            "hit": False,
            "cache": state,
            "executes_action": False,
        }
    query_text = _clean(query, 1000)
    policy = _clean(policy_version, 160)
    data = _clean(data_version, 160)
    key = _key(
        tenant,
        workspace,
        policy_version=policy,
        data_version=data,
        cache_class=cls,
        query=query_text,
    )
    entries = {
        str(k): dict(v)
        for k, v in dict(state.get("entries") or {}).items()
        if isinstance(v, Mapping)
    }
    row = entries.get(key)
    if not row:
        return {
            "schema": SCHEMA,
            "state": "MISS",
            "reason": "NOT_FOUND",
            "hit": False,
            "cache": state,
            "executes_action": False,
        }
    # Defense in depth: a keyed hit still re-checks stored scope and versions.
    if (
        row.get("tenant_id") != tenant
        or row.get("workspace_id") != workspace
        or row.get("policy_version") != policy
        or row.get("data_version") != data
        or row.get("cache_class") != cls
    ):
        return {
            "schema": SCHEMA,
            "state": "MISS",
            "reason": "CACHE_BINDING_MISMATCH",
            "hit": False,
            "cache": state,
            "executes_action": False,
        }
    current = _aware(now)
    expires = _aware(row.get("expires_at"))
    if expires <= current:
        entries.pop(key, None)
        updated = {**state, "entries": entries}
        return {
            "schema": SCHEMA,
            "state": "MISS",
            "reason": "EXPIRED",
            "hit": False,
            "cache": updated,
            "executes_action": False,
        }
    return {
        "schema": SCHEMA,
        "state": "HIT",
        "reason": "VALID_SCOPED_CACHE",
        "hit": True,
        "value": row.get("value"),
        "source_refs": list(row.get("source_refs") or []),
        "expires_at": row.get("expires_at"),
        "cache": state,
        "canonical_source": False,
        "authority": "NONE",
        "executes_action": False,
    }


def invalidate_sources(
    cache: Mapping[str, Any] | None,
    source_refs: Sequence[Any] | None,
    *,
    trusted_context: Mapping[str, Any] | None,
) -> dict[str, Any]:
    state = dict(cache or empty_cache())
    tenant, workspace = _scope(trusted_context)
    targets = set(_refs(source_refs))
    entries = {
        str(k): dict(v)
        for k, v in dict(state.get("entries") or {}).items()
        if isinstance(v, Mapping)
    }
    removed = 0
    for key, row in list(entries.items()):
        if row.get("tenant_id") != tenant or row.get("workspace_id") != workspace:
            continue
        if targets.intersection(set(row.get("source_refs") or [])):
            entries.pop(key, None)
            removed += 1
    return {
        "schema": SCHEMA,
        "state": "INVALIDATED",
        "removed": removed,
        "cache": {
            **state,
            "entries": entries,
            "provider_prompt_cache_trusted": False,
            "cross_tenant_sharing": False,
            "canonical_source": False,
            "executes_action": False,
        },
        "executes_action": False,
    }


def invalidate_scope(
    cache: Mapping[str, Any] | None,
    *,
    trusted_context: Mapping[str, Any] | None,
) -> dict[str, Any]:
    state = dict(cache or empty_cache())
    tenant, workspace = _scope(trusted_context)
    entries = {
        str(k): dict(v)
        for k, v in dict(state.get("entries") or {}).items()
        if isinstance(v, Mapping)
    }
    kept = {
        key: row
        for key, row in entries.items()
        if not (
            row.get("tenant_id") == tenant
            and row.get("workspace_id") == workspace
        )
    }
    return {
        "schema": SCHEMA,
        "state": "INVALIDATED",
        "removed": len(entries) - len(kept),
        "cache": {
            **state,
            "entries": kept,
            "provider_prompt_cache_trusted": False,
            "cross_tenant_sharing": False,
            "canonical_source": False,
            "executes_action": False,
        },
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "MAX_ENTRIES",
    "MAX_TTL_SECONDS",
    "NON_CACHEABLE_CLASSES",
    "empty_cache",
    "cache_put",
    "cache_get",
    "invalidate_sources",
    "invalidate_scope",
]
