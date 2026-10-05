"""Tenant/workspace isolation contract for AION derived data.

Derived data (cache, index, backup, logs and traces) must never become a second
canonical source of truth. This module is metadata/control-plane only: it does
not persist tenant payloads, delete files, call providers, or claim production
encryption.

The contract binds every artifact to one trusted tenant/workspace boundary,
versions cache keys by policy/data/producer state, treats search indexes as
rebuildable projections, and requires derived-artifact reconciliation before a
deletion request can be described as complete.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Any, Mapping, Sequence

SCHEMA = "ATLASQUANT_AION_TENANT_DERIVED_DATA_V1"
REGISTRY_VERSION = 1
ARTIFACT_KINDS = ("CACHE", "INDEX", "BACKUP", "LOG", "TRACE")
ARTIFACT_STATES = (
    "ACTIVE",
    "STALE",
    "PURGE_REQUIRED",
    "PURGED",
    "ERASURE_PENDING_RETENTION",
)
TOMBSTONE_STATES = (
    "PENDING_DERIVED_PURGE",
    "DERIVED_PURGE_CONFIRMED",
    "BLOCKED",
)
MAX_ARTIFACTS = 4000
MAX_TOMBSTONES = 500


def _clean(value: Any, limit: int = 600) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _upper(value: Any, limit: int = 80) -> str:
    return _clean(value, limit).upper()


def _canonical(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def _digest(value: Any) -> str:
    return sha256(_canonical(value).encode("utf-8")).hexdigest()


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


def _scope(context: Mapping[str, Any] | None) -> dict[str, str]:
    raw = dict(context or {})
    tenant = _clean(raw.get("tenant_id"), 120)
    workspace = _clean(raw.get("workspace_id"), 120)
    owner = _clean(raw.get("owner_id") or raw.get("actor_id"), 120)
    if not tenant or not workspace:
        raise ValueError("trusted tenant_id/workspace_id required")
    material = "|".join((tenant, workspace)).encode("utf-8")
    scope_digest = sha256(material).hexdigest()[:24]
    return {
        "owner_id": owner,
        "tenant_id": tenant,
        "workspace_id": workspace,
        "scope_digest": scope_digest,
    }


def scope_binding(context: Mapping[str, Any] | None) -> dict[str, str]:
    """Return a non-secret storage boundary identifier."""
    bound = _scope(context)
    return {
        **bound,
        "namespace_root": "aqd/" + bound["scope_digest"],
    }


def derived_namespace(
    kind: Any,
    trusted_context: Mapping[str, Any] | None,
) -> str:
    token = _upper(kind, 40)
    if token not in ARTIFACT_KINDS:
        raise ValueError("unsupported derived artifact kind")
    scope = _scope(trusted_context)
    return f"aqd/{scope['scope_digest']}/{token.lower()}"


def derived_cache_key(
    *,
    trusted_context: Mapping[str, Any] | None,
    purpose: Any,
    source_digest: Any,
    policy_version: Any,
    data_version: Any,
    producer_version: Any,
    query_digest: Any = "",
) -> str:
    """Produce a scope/version-bound cache key.

    Omitting policy/data/producer version is forbidden because that can silently
    reuse a result after authority, data or tool/model behavior changed.
    """
    scope = _scope(trusted_context)
    fields = {
        "purpose": _clean(purpose, 160),
        "source_digest": _clean(source_digest, 180),
        "policy_version": _clean(policy_version, 120),
        "data_version": _clean(data_version, 120),
        "producer_version": _clean(producer_version, 160),
        "query_digest": _clean(query_digest, 180),
    }
    if any(not fields[name] for name in (
        "purpose",
        "source_digest",
        "policy_version",
        "data_version",
        "producer_version",
    )):
        raise ValueError("cache key requires source/policy/data/producer version")
    body = {
        "scope_digest": scope["scope_digest"],
        **fields,
    }
    return "aq-cache-v1:" + scope["scope_digest"] + ":" + _digest(body)


def default_derived_registry(
    trusted_context: Mapping[str, Any] | None,
) -> dict[str, Any]:
    scope = _scope(trusted_context)
    artifacts: list[dict[str, Any]] = []
    tombstones: list[dict[str, Any]] = []
    state = {
        "schema": SCHEMA,
        "version": REGISTRY_VERSION,
        **scope,
        "namespace_root": "aqd/" + scope["scope_digest"],
        "artifacts": artifacts,
        "tombstones": tombstones,
        "canonical_source": False,
        "index_is_rebuildable_projection": True,
        "automatic_deletion": False,
        "production_encryption_claimed": False,
        "tenant_key_management_implemented": False,
        "executes_action": False,
    }
    state["digest"] = _digest({
        "scope_digest": scope["scope_digest"],
        "artifacts": artifacts,
        "tombstones": tombstones,
    })
    return state


def _registry_digest(state: Mapping[str, Any]) -> str:
    return _digest({
        "scope_digest": state.get("scope_digest"),
        "artifacts": state.get("artifacts") or [],
        "tombstones": state.get("tombstones") or [],
    })


def validate_derived_registry(
    registry: Mapping[str, Any] | None,
    *,
    trusted_context: Mapping[str, Any] | None,
) -> dict[str, Any]:
    expected = _scope(trusted_context)
    if not isinstance(registry, Mapping):
        return {
            "schema": SCHEMA,
            "state": "BLOCK",
            "blockers": ["REGISTRY_MAPPING_REQUIRED"],
            "valid": False,
        }
    raw = dict(registry)
    blockers: list[str] = []
    if raw.get("schema") != SCHEMA or raw.get("version") != REGISTRY_VERSION:
        blockers.append("REGISTRY_SCHEMA_OR_VERSION_MISMATCH")
    if raw.get("scope_digest") != expected["scope_digest"]:
        blockers.append("REGISTRY_SCOPE_MISMATCH")
    if raw.get("tenant_id") != expected["tenant_id"]:
        blockers.append("REGISTRY_TENANT_MISMATCH")
    if raw.get("workspace_id") != expected["workspace_id"]:
        blockers.append("REGISTRY_WORKSPACE_MISMATCH")
    expected_root = "aqd/" + expected["scope_digest"]
    if raw.get("namespace_root") != expected_root:
        blockers.append("REGISTRY_NAMESPACE_MISMATCH")

    artifacts = list(raw.get("artifacts") or [])
    if len(artifacts) > MAX_ARTIFACTS:
        blockers.append("ARTIFACT_CAPACITY_EXCEEDED")
    ids: set[str] = set()
    for item in artifacts[: MAX_ARTIFACTS + 1]:
        if not isinstance(item, Mapping):
            blockers.append("ARTIFACT_NOT_MAPPING")
            continue
        row = dict(item)
        artifact_id = _clean(row.get("artifact_id"), 120)
        kind = _upper(row.get("kind"), 40)
        if not artifact_id or artifact_id in ids:
            blockers.append("ARTIFACT_ID_INVALID_OR_DUPLICATE")
        ids.add(artifact_id)
        if kind not in ARTIFACT_KINDS:
            blockers.append("ARTIFACT_KIND_INVALID")
        if row.get("scope_digest") != expected["scope_digest"]:
            blockers.append("ARTIFACT_SCOPE_MISMATCH")
        if row.get("tenant_id") != expected["tenant_id"]:
            blockers.append("ARTIFACT_TENANT_MISMATCH")
        if row.get("workspace_id") != expected["workspace_id"]:
            blockers.append("ARTIFACT_WORKSPACE_MISMATCH")
        namespace = _clean(row.get("namespace"), 300)
        if kind in ARTIFACT_KINDS and namespace != derived_namespace(kind, expected):
            blockers.append("ARTIFACT_NAMESPACE_MISMATCH")
        if row.get("canonical_source") is not False:
            blockers.append("DERIVED_ARTIFACT_CANNOT_BE_CANONICAL")
        if kind == "INDEX":
            if row.get("rebuildable_projection") is not True:
                blockers.append("INDEX_MUST_BE_REBUILDABLE_PROJECTION")
        if kind == "CACHE":
            cache_key = _clean(row.get("cache_key"), 300)
            if not cache_key.startswith(
                "aq-cache-v1:" + expected["scope_digest"] + ":"
            ):
                blockers.append("CACHE_KEY_SCOPE_MISMATCH")
            for field in ("policy_version", "data_version", "producer_version"):
                if not _clean(row.get(field), 160):
                    blockers.append("CACHE_VERSION_BINDING_MISSING:" + field)

    tombstones = list(raw.get("tombstones") or [])
    if len(tombstones) > MAX_TOMBSTONES:
        blockers.append("TOMBSTONE_CAPACITY_EXCEEDED")
    for row in tombstones[: MAX_TOMBSTONES + 1]:
        if not isinstance(row, Mapping):
            blockers.append("TOMBSTONE_NOT_MAPPING")
            continue
        if row.get("scope_digest") != expected["scope_digest"]:
            blockers.append("TOMBSTONE_SCOPE_MISMATCH")
        if _upper(row.get("state"), 40) not in TOMBSTONE_STATES:
            blockers.append("TOMBSTONE_STATE_INVALID")

    stored_digest = _clean(raw.get("digest"), 64)
    expected_digest = _registry_digest(raw)
    if stored_digest != expected_digest:
        blockers.append("REGISTRY_DIGEST_MISMATCH")

    return {
        "schema": SCHEMA,
        "state": "CONFIRMED" if not blockers else "BLOCK",
        "blockers": sorted(set(blockers)),
        "valid": not blockers,
        "expected_digest": expected_digest,
        "stored_digest": stored_digest,
        "scope_digest": expected["scope_digest"],
        "canonical_source": False,
        "executes_action": False,
    }


def register_derived_artifact(
    registry: Mapping[str, Any] | None,
    *,
    kind: Any,
    artifact_ref: Any,
    trusted_context: Mapping[str, Any] | None,
    source_digest: Any,
    policy_version: Any,
    data_version: Any,
    producer_version: Any,
    purpose: Any = "",
    query_digest: Any = "",
    retention_until: Any = "",
    created_at: Any = None,
) -> dict[str, Any]:
    current = (
        deepcopy(dict(registry))
        if isinstance(registry, Mapping)
        else default_derived_registry(trusted_context)
    )
    audit = validate_derived_registry(current, trusted_context=trusted_context)
    if audit["valid"] is not True:
        raise ValueError("derived registry integrity/scope mismatch")

    scope = _scope(trusted_context)
    token = _upper(kind, 40)
    if token not in ARTIFACT_KINDS:
        raise ValueError("unsupported derived artifact kind")
    ref = _clean(artifact_ref, 500)
    source = _clean(source_digest, 180)
    policy = _clean(policy_version, 120)
    data_ver = _clean(data_version, 120)
    producer = _clean(producer_version, 160)
    if not ref or not source or not policy or not data_ver or not producer:
        raise ValueError("artifact binding fields required")
    created = _aware(created_at)
    retention = ""
    if retention_until:
        retention = _aware(retention_until).isoformat()

    cache_key = ""
    if token == "CACHE":
        cache_key = derived_cache_key(
            trusted_context=scope,
            purpose=purpose or ref,
            source_digest=source,
            policy_version=policy,
            data_version=data_ver,
            producer_version=producer,
            query_digest=query_digest,
        )

    seed = {
        "scope_digest": scope["scope_digest"],
        "kind": token,
        "artifact_ref": ref,
        "source_digest": source,
        "policy_version": policy,
        "data_version": data_ver,
        "producer_version": producer,
        "cache_key": cache_key,
    }
    artifact_id = "DRV-" + _digest(seed)[:24].upper()
    existing = next(
        (
            row
            for row in list(current.get("artifacts") or [])
            if isinstance(row, Mapping) and row.get("artifact_id") == artifact_id
        ),
        None,
    )
    if existing is not None:
        return {
            "schema": SCHEMA,
            "state": "IDEMPOTENT",
            "artifact": deepcopy(dict(existing)),
            "registry": current,
            "executes_action": False,
        }
    if len(list(current.get("artifacts") or [])) >= MAX_ARTIFACTS:
        raise OverflowError("derived registry capacity reached")

    artifact = {
        "artifact_id": artifact_id,
        "kind": token,
        **scope,
        "namespace": derived_namespace(token, scope),
        "artifact_ref": ref,
        "source_digest": source,
        "policy_version": policy,
        "data_version": data_ver,
        "producer_version": producer,
        "purpose": _clean(purpose, 160),
        "query_digest": _clean(query_digest, 180),
        "cache_key": cache_key,
        "created_at": created.isoformat(),
        "retention_until": retention,
        "state": "ACTIVE",
        "canonical_source": False,
        "rebuildable_projection": token in {"CACHE", "INDEX"},
        "payload_content_stored_in_registry": False,
        "external_action_executed": False,
        "executes_action": False,
    }
    current["artifacts"] = [*list(current.get("artifacts") or []), artifact]
    current["digest"] = _registry_digest(current)
    return {
        "schema": SCHEMA,
        "state": "REGISTERED",
        "artifact": deepcopy(artifact),
        "registry": current,
        "executes_action": False,
    }


def resolve_derived_artifact(
    registry: Mapping[str, Any] | None,
    artifact_id: Any,
    *,
    trusted_context: Mapping[str, Any] | None,
    policy_version: Any = "",
    data_version: Any = "",
    producer_version: Any = "",
) -> dict[str, Any]:
    audit = validate_derived_registry(registry, trusted_context=trusted_context)
    if audit["valid"] is not True:
        return {
            "schema": SCHEMA,
            "state": "BLOCK",
            "reason": "REGISTRY_SCOPE_OR_INTEGRITY_MISMATCH",
            "artifact": None,
            "executes_action": False,
        }
    target = _clean(artifact_id, 120)
    row = next(
        (
            dict(item)
            for item in list((registry or {}).get("artifacts") or [])
            if isinstance(item, Mapping) and item.get("artifact_id") == target
        ),
        None,
    )
    if row is None:
        return {
            "schema": SCHEMA,
            "state": "NOT_FOUND",
            "artifact": None,
            "executes_action": False,
        }
    if row.get("state") not in {"ACTIVE", "STALE"}:
        return {
            "schema": SCHEMA,
            "state": "BLOCK",
            "reason": "ARTIFACT_NOT_ACTIVE",
            "artifact": None,
            "executes_action": False,
        }
    expected_versions = {
        "policy_version": _clean(policy_version, 120),
        "data_version": _clean(data_version, 120),
        "producer_version": _clean(producer_version, 160),
    }
    mismatches = [
        field
        for field, expected in expected_versions.items()
        if expected and expected != row.get(field)
    ]
    if mismatches:
        return {
            "schema": SCHEMA,
            "state": "STALE",
            "reason": "VERSION_BINDING_CHANGED",
            "mismatches": mismatches,
            "artifact": None,
            "executes_action": False,
        }
    return {
        "schema": SCHEMA,
        "state": "READY",
        "artifact": row,
        "canonical_source": False,
        "executes_action": False,
    }


def create_deletion_tombstone(
    registry: Mapping[str, Any] | None,
    *,
    request_id: Any,
    trusted_context: Mapping[str, Any] | None,
    requested_classes: Sequence[Any] | None = None,
    created_at: Any = None,
) -> dict[str, Any]:
    current = deepcopy(dict(registry or {}))
    audit = validate_derived_registry(current, trusted_context=trusted_context)
    if audit["valid"] is not True:
        raise ValueError("derived registry integrity/scope mismatch")
    scope = _scope(trusted_context)
    rid = _clean(request_id, 160)
    if not rid:
        raise ValueError("deletion request_id required")
    classes = []
    for raw in list(requested_classes or ARTIFACT_KINDS):
        token = _upper(raw, 40)
        if token in ARTIFACT_KINDS and token not in classes:
            classes.append(token)
    if not classes:
        raise ValueError("at least one derived class required")

    existing = next(
        (
            row
            for row in list(current.get("tombstones") or [])
            if isinstance(row, Mapping) and row.get("request_id") == rid
        ),
        None,
    )
    if existing is not None:
        return {
            "schema": SCHEMA,
            "state": "IDEMPOTENT",
            "tombstone": deepcopy(dict(existing)),
            "registry": current,
            "executes_action": False,
        }
    if len(list(current.get("tombstones") or [])) >= MAX_TOMBSTONES:
        raise OverflowError("deletion tombstone capacity reached")

    targets = [
        str(row.get("artifact_id"))
        for row in list(current.get("artifacts") or [])
        if isinstance(row, Mapping)
        and row.get("kind") in classes
        and row.get("state") not in {"PURGED"}
    ]
    tombstone_id = "DEL-" + _digest({
        "scope_digest": scope["scope_digest"],
        "request_id": rid,
        "classes": classes,
    })[:24].upper()
    tombstone = {
        "tombstone_id": tombstone_id,
        "request_id": rid,
        **scope,
        "requested_classes": classes,
        "target_artifact_ids": targets,
        "purged_artifact_ids": [],
        "pending_artifact_ids": list(targets),
        "state": "PENDING_DERIVED_PURGE",
        "created_at": _aware(created_at).isoformat(),
        "updated_at": _aware(created_at).isoformat(),
        "canonical_delete_executed": False,
        "deletion_complete_claimed": False,
        "backup_retention_reconciliation_required": any(
            row.get("artifact_id") in targets and row.get("kind") == "BACKUP"
            for row in list(current.get("artifacts") or [])
            if isinstance(row, Mapping)
        ),
        "executes_action": False,
    }
    current["tombstones"] = [*list(current.get("tombstones") or []), tombstone]
    for row in list(current.get("artifacts") or []):
        if isinstance(row, dict) and row.get("artifact_id") in targets:
            row["state"] = "PURGE_REQUIRED"
    current["digest"] = _registry_digest(current)
    return {
        "schema": SCHEMA,
        "state": tombstone["state"],
        "tombstone": deepcopy(tombstone),
        "registry": current,
        "executes_action": False,
    }


def acknowledge_derived_purge(
    registry: Mapping[str, Any] | None,
    tombstone_id: Any,
    artifact_id: Any,
    *,
    trusted_context: Mapping[str, Any] | None,
    purge_evidence_ref: Any,
    now: Any = None,
) -> dict[str, Any]:
    current = deepcopy(dict(registry or {}))
    audit = validate_derived_registry(current, trusted_context=trusted_context)
    if audit["valid"] is not True:
        raise ValueError("derived registry integrity/scope mismatch")
    tid = _clean(tombstone_id, 120)
    aid = _clean(artifact_id, 120)
    evidence = _clean(purge_evidence_ref, 300)
    if not evidence:
        raise ValueError("purge evidence ref required")
    current_time = _aware(now)

    tombstone = next(
        (
            row for row in list(current.get("tombstones") or [])
            if isinstance(row, dict) and row.get("tombstone_id") == tid
        ),
        None,
    )
    artifact = next(
        (
            row for row in list(current.get("artifacts") or [])
            if isinstance(row, dict) and row.get("artifact_id") == aid
        ),
        None,
    )
    if tombstone is None or artifact is None:
        raise LookupError("tombstone/artifact unavailable")
    if aid not in list(tombstone.get("target_artifact_ids") or []):
        raise ValueError("artifact not targeted by deletion request")

    if artifact.get("kind") == "BACKUP" and artifact.get("retention_until"):
        retention = _aware(artifact["retention_until"])
        if current_time < retention:
            artifact["state"] = "ERASURE_PENDING_RETENTION"
            artifact["purge_evidence_ref"] = evidence
            artifact["purge_blocked_until"] = retention.isoformat()
            tombstone["state"] = "PENDING_DERIVED_PURGE"
            tombstone["updated_at"] = current_time.isoformat()
            current["digest"] = _registry_digest(current)
            return {
                "schema": SCHEMA,
                "state": "ERASURE_PENDING_RETENTION",
                "reason": "BACKUP_RETENTION_NOT_EXPIRED",
                "artifact": deepcopy(artifact),
                "tombstone": deepcopy(tombstone),
                "registry": current,
                "deletion_complete_claimed": False,
                "executes_action": False,
            }

    artifact["state"] = "PURGED"
    artifact["purge_evidence_ref"] = evidence
    artifact["purged_at"] = current_time.isoformat()
    purged = list(tombstone.get("purged_artifact_ids") or [])
    if aid not in purged:
        purged.append(aid)
    targets = list(tombstone.get("target_artifact_ids") or [])
    pending = [target for target in targets if target not in purged]
    tombstone["purged_artifact_ids"] = purged
    tombstone["pending_artifact_ids"] = pending
    tombstone["updated_at"] = current_time.isoformat()
    tombstone["state"] = (
        "DERIVED_PURGE_CONFIRMED" if not pending else "PENDING_DERIVED_PURGE"
    )
    # Even after derived purge, canonical deletion is a separate authenticated
    # runtime operation and is not claimed by this metadata contract.
    tombstone["canonical_delete_executed"] = False
    tombstone["deletion_complete_claimed"] = False
    current["digest"] = _registry_digest(current)
    return {
        "schema": SCHEMA,
        "state": tombstone["state"],
        "artifact": deepcopy(artifact),
        "tombstone": deepcopy(tombstone),
        "registry": current,
        "deletion_complete_claimed": False,
        "executes_action": False,
    }


def derived_data_summary(
    registry: Mapping[str, Any] | None,
    *,
    trusted_context: Mapping[str, Any] | None,
) -> dict[str, Any]:
    audit = validate_derived_registry(registry, trusted_context=trusted_context)
    rows = list((registry or {}).get("artifacts") or []) if isinstance(registry, Mapping) else []
    tombstones = list((registry or {}).get("tombstones") or []) if isinstance(registry, Mapping) else []
    return {
        "schema": SCHEMA,
        "state": audit["state"],
        "blockers": audit.get("blockers", []),
        "artifacts": len(rows),
        "by_kind": {
            kind: sum(
                isinstance(row, Mapping) and row.get("kind") == kind
                for row in rows
            )
            for kind in ARTIFACT_KINDS
        },
        "pending_deletion_requests": sum(
            isinstance(row, Mapping)
            and row.get("state") == "PENDING_DERIVED_PURGE"
            for row in tombstones
        ),
        "canonical_source": False,
        "index_is_rebuildable_projection": True,
        "tenant_key_management_implemented": False,
        "production_encryption_claimed": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "REGISTRY_VERSION",
    "ARTIFACT_KINDS",
    "ARTIFACT_STATES",
    "TOMBSTONE_STATES",
    "scope_binding",
    "derived_namespace",
    "derived_cache_key",
    "default_derived_registry",
    "validate_derived_registry",
    "register_derived_artifact",
    "resolve_derived_artifact",
    "create_deletion_tombstone",
    "acknowledge_derived_purge",
    "derived_data_summary",
]
