"""Local durable tenant/workspace persistence for AION.

This module implements filesystem persistence only. It never performs network I/O,
never activates production persistence, and never bypasses entitlement or explicit
write approval. Every path is derived from the authenticated tenant namespace.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence
import hashlib
import json
import os
import re
import tempfile

from atlasquant_aion_tenant import tenant_namespace
from atlasquant_aion_tenant_store import (
    MAX_TENANT_MEMORY_BYTES,
    accept_loaded_memory,
    prepare_tenant_load,
    prepare_tenant_write,
    resolve_write_conflict,
)

SCHEMA = "ATLASQUANT_AION_TENANT_DURABLE_STORE_V1"
ENVELOPE_SCHEMA = "ATLASQUANT_AION_TENANT_DURABLE_ENVELOPE_V1"
ACL_SCHEMA = "ATLASQUANT_AION_TENANT_ACL_V1"
IDENTITY_SCHEMA = "ATLASQUANT_AION_TENANT_IDENTITY_V1"
MAX_ENVELOPE_BYTES = MAX_TENANT_MEMORY_BYTES + 64_000
_WORKSPACE_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")


def _sha256(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _principal_id(access: Mapping[str, Any] | None) -> str:
    ns = tenant_namespace(access)
    if not ns.get("ready"):
        return ""
    session = dict((access or {}).get("session") or access or {})
    username = str(session.get("username") or "").strip().casefold()
    fingerprint = str(session.get("credential_fingerprint") or "").strip().lower()
    if not username or not fingerprint:
        return ""
    raw = f"{username}|{fingerprint}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def normalize_workspace_id(value: Any = "default") -> str:
    workspace = str(value or "default").strip().casefold()
    if not _WORKSPACE_RE.fullmatch(workspace):
        raise ValueError("unsafe workspace id")
    return workspace


def _safe_root(root: str | os.PathLike[str]) -> Path:
    base = Path(root).expanduser().resolve()
    if base == Path(base.anchor):
        raise ValueError("store root cannot be filesystem root")
    return base


def tenant_workspace_paths(
    access: Mapping[str, Any] | None,
    root: str | os.PathLike[str],
    *,
    workspace_id: Any = "default",
) -> dict[str, Any]:
    ns = tenant_namespace(access)
    if not ns.get("ready"):
        return {"ready": False, "reason": ns.get("reason"), "tenant_id": ""}
    workspace = normalize_workspace_id(workspace_id)
    base = _safe_root(root)
    tenant_id = str(ns["tenant_id"])
    folder = (base / "tenants" / tenant_id / "workspaces" / workspace).resolve()
    expected_parent = (base / "tenants" / tenant_id / "workspaces").resolve()
    if folder.parent != expected_parent:
        raise ValueError("workspace path escaped tenant root")
    return {
        "ready": True,
        "reason": "OK",
        "tenant_id": tenant_id,
        "workspace_id": workspace,
        "folder": folder,
        "memory": folder / "memory.json",
        "identity": folder / "identity.json",
        "acl": folder / "acl.json",
        "audit": folder / "audit.jsonl",
        "backups": folder / "backups",
    }


def build_identity_record(
    access: Mapping[str, Any] | None,
    *,
    workspace_id: Any = "default",
) -> dict[str, Any]:
    ns = tenant_namespace(access)
    principal = _principal_id(access)
    if not ns.get("ready") or not principal:
        raise ValueError("authenticated tenant principal required")
    session = dict((access or {}).get("session") or access or {})
    return {
        "schema": IDENTITY_SCHEMA,
        "tenant_id": ns["tenant_id"],
        "workspace_id": normalize_workspace_id(workspace_id),
        "principal_id": principal,
        "role": str(session.get("role") or "").strip().upper(),
        "credential_bound": True,
    }


def build_acl_record(
    access: Mapping[str, Any] | None,
    *,
    workspace_id: Any = "default",
) -> dict[str, Any]:
    identity = build_identity_record(access, workspace_id=workspace_id)
    return {
        "schema": ACL_SCHEMA,
        "tenant_id": identity["tenant_id"],
        "workspace_id": identity["workspace_id"],
        "principal_id": identity["principal_id"],
        "allow": ["READ", "WRITE", "BACKUP", "RESTORE"],
        "deny": ["CROSS_TENANT", "ADMIN_MEMORY", "NETWORK_WRITE", "PRODUCTION"],
        "default": "DENY",
    }


def _atomic_json_write(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = _canonical_bytes(payload)
    if len(raw) > MAX_ENVELOPE_BYTES:
        raise ValueError("durable payload exceeds envelope size limit")
    fd, temp_name = tempfile.mkstemp(prefix=".aion-", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def _append_audit(path: Path, event: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = _canonical_bytes(event) + b"\n"
    with open(path, "ab") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(path)
    if path.stat().st_size > MAX_ENVELOPE_BYTES:
        raise ValueError("durable file exceeds size limit")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("durable file must contain an object")
    return data


def _acl_allows(
    access: Mapping[str, Any] | None,
    acl: Mapping[str, Any],
    *,
    tenant_id: str,
    workspace_id: str,
    action: str,
) -> bool:
    expected_principal = _principal_id(access)
    return bool(
        expected_principal
        and acl.get("schema") == ACL_SCHEMA
        and acl.get("tenant_id") == tenant_id
        and acl.get("workspace_id") == workspace_id
        and acl.get("principal_id") == expected_principal
        and str(action).upper() in set(acl.get("allow") or ())
        and acl.get("default") == "DENY"
    )


def _envelope(memory: Mapping[str, Any], *, tenant_id: str, workspace_id: str) -> dict[str, Any]:
    clean = deepcopy(dict(memory))
    payload_digest = _sha256(clean)
    revision = _sha256({
        "tenant_id": tenant_id,
        "workspace_id": workspace_id,
        "payload_digest": payload_digest,
    })
    return {
        "schema": ENVELOPE_SCHEMA,
        "tenant_id": tenant_id,
        "workspace_id": workspace_id,
        "payload_digest": payload_digest,
        "revision": revision,
        "memory": clean,
    }


def _verify_envelope(
    envelope: Mapping[str, Any],
    *,
    tenant_id: str,
    workspace_id: str,
) -> tuple[bool, str]:
    if envelope.get("schema") != ENVELOPE_SCHEMA:
        return False, "ENVELOPE_SCHEMA_INVALID"
    if envelope.get("tenant_id") != tenant_id:
        return False, "FOREIGN_TENANT_ENVELOPE_REJECTED"
    if envelope.get("workspace_id") != workspace_id:
        return False, "FOREIGN_WORKSPACE_ENVELOPE_REJECTED"
    memory = envelope.get("memory")
    if not isinstance(memory, Mapping):
        return False, "MEMORY_PAYLOAD_INVALID"
    expected = _envelope(memory, tenant_id=tenant_id, workspace_id=workspace_id)
    if envelope.get("payload_digest") != expected["payload_digest"]:
        return False, "PAYLOAD_DIGEST_MISMATCH"
    if envelope.get("revision") != expected["revision"]:
        return False, "REVISION_DIGEST_MISMATCH"
    return True, "OK"


class DurableTenantStore:
    def __init__(self, root: str | os.PathLike[str]):
        self.root = _safe_root(root)

    def _paths(self, access: Mapping[str, Any] | None, workspace_id: Any) -> dict[str, Any]:
        return tenant_workspace_paths(access, self.root, workspace_id=workspace_id)

    def _ensure_identity_acl(
        self,
        access: Mapping[str, Any] | None,
        paths: Mapping[str, Any],
    ) -> tuple[bool, str]:
        identity_expected = build_identity_record(access, workspace_id=paths["workspace_id"])
        acl_expected = build_acl_record(access, workspace_id=paths["workspace_id"])
        identity_path = Path(paths["identity"])
        acl_path = Path(paths["acl"])
        if identity_path.exists():
            if _load_json(identity_path) != identity_expected:
                return False, "IDENTITY_REGISTRY_MISMATCH"
        else:
            _atomic_json_write(identity_path, identity_expected)
        if acl_path.exists():
            acl = _load_json(acl_path)
            if not _acl_allows(
                access, acl,
                tenant_id=paths["tenant_id"],
                workspace_id=paths["workspace_id"],
                action="READ",
            ):
                return False, "ACL_MISMATCH"
        else:
            _atomic_json_write(acl_path, acl_expected)
        return True, "OK"

    def write(
        self,
        access: Mapping[str, Any] | None,
        entitlements: Sequence[Mapping[str, Any]] | None,
        memory: Mapping[str, Any] | None,
        *,
        workspace_id: Any = "default",
        approved: bool = False,
        expected_revision: Any = "",
        now: datetime | None = None,
    ) -> dict[str, Any]:
        bound_memory: Mapping[str, Any] | None = memory
        if isinstance(memory, Mapping) and not str(memory.get("tenant_id") or "").strip():
            ns = tenant_namespace(access)
            if not ns.get("ready"):
                return {"stored": False, "reason": ns.get("reason"), "revision": ""}
            bound = deepcopy(dict(memory))
            bound["tenant_id"] = ns["tenant_id"]
            bound_memory = bound
        plan = prepare_tenant_write(
            access, entitlements, bound_memory,
            approved=approved,
            expected_revision=expected_revision,
            now=now,
        )
        if not plan["allowed"]:
            return {"stored": False, "reason": plan["reason"], "revision": ""}
        paths = self._paths(access, workspace_id)
        ok, reason = self._ensure_identity_acl(access, paths)
        if not ok:
            return {"stored": False, "reason": reason, "revision": ""}
        acl = _load_json(Path(paths["acl"]))
        if not _acl_allows(
            access, acl,
            tenant_id=paths["tenant_id"],
            workspace_id=paths["workspace_id"],
            action="WRITE",
        ):
            return {"stored": False, "reason": "ACL_WRITE_DENIED", "revision": ""}

        memory_path = Path(paths["memory"])
        current_revision = ""
        if memory_path.exists():
            current = _load_json(memory_path)
            valid, verify_reason = _verify_envelope(
                current,
                tenant_id=paths["tenant_id"],
                workspace_id=paths["workspace_id"],
            )
            if not valid:
                return {"stored": False, "reason": verify_reason, "revision": ""}
            current_revision = str(current.get("revision") or "")

        conflict = resolve_write_conflict(
            expected_revision=expected_revision,
            current_revision=current_revision,
        )
        if not conflict["can_write"]:
            return {
                "stored": False,
                "reason": "REVISION_CONFLICT",
                "revision": current_revision,
                "requires_reload": True,
            }

        envelope = _envelope(
            plan["payload"],
            tenant_id=paths["tenant_id"],
            workspace_id=paths["workspace_id"],
        )
        _atomic_json_write(memory_path, envelope)
        _append_audit(Path(paths["audit"]), {
            "schema": SCHEMA,
            "event": "WRITE",
            "at": _now(),
            "tenant_id": paths["tenant_id"],
            "workspace_id": paths["workspace_id"],
            "principal_id": _principal_id(access),
            "revision": envelope["revision"],
            "payload_digest": envelope["payload_digest"],
        })
        return {
            "stored": True,
            "reason": "STORED",
            "revision": envelope["revision"],
            "payload_digest": envelope["payload_digest"],
            "tenant_id": paths["tenant_id"],
            "workspace_id": paths["workspace_id"],
            "network_io": False,
            "production_activated": False,
        }

    def read(
        self,
        access: Mapping[str, Any] | None,
        entitlements: Sequence[Mapping[str, Any]] | None,
        *,
        workspace_id: Any = "default",
        now: datetime | None = None,
    ) -> dict[str, Any]:
        plan = prepare_tenant_load(access, entitlements, now=now)
        if not plan["allowed"]:
            return {"loaded": False, "reason": plan["reason"], "memory": None}
        paths = self._paths(access, workspace_id)
        memory_path = Path(paths["memory"])
        if not memory_path.exists():
            return {"loaded": False, "reason": "NOT_FOUND", "memory": None}
        ok, reason = self._ensure_identity_acl(access, paths)
        if not ok:
            return {"loaded": False, "reason": reason, "memory": None}
        acl = _load_json(Path(paths["acl"]))
        if not _acl_allows(
            access, acl,
            tenant_id=paths["tenant_id"],
            workspace_id=paths["workspace_id"],
            action="READ",
        ):
            return {"loaded": False, "reason": "ACL_READ_DENIED", "memory": None}
        envelope = _load_json(memory_path)
        valid, verify_reason = _verify_envelope(
            envelope,
            tenant_id=paths["tenant_id"],
            workspace_id=paths["workspace_id"],
        )
        if not valid:
            return {"loaded": False, "reason": verify_reason, "memory": None}
        accepted = accept_loaded_memory(
            access,
            entitlements,
            envelope["memory"],
            now=now,
        )
        if not accepted["accepted"]:
            return {"loaded": False, "reason": accepted["reason"], "memory": None}
        return {
            "loaded": True,
            "reason": "OK",
            "memory": accepted["memory"],
            "revision": envelope["revision"],
            "payload_digest": envelope["payload_digest"],
            "tenant_id": paths["tenant_id"],
            "workspace_id": paths["workspace_id"],
            "network_io": False,
        }

    def backup(
        self,
        access: Mapping[str, Any] | None,
        entitlements: Sequence[Mapping[str, Any]] | None,
        *,
        workspace_id: Any = "default",
        approved: bool = False,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        if approved is not True:
            return {"backed_up": False, "reason": "EXPLICIT_BACKUP_APPROVAL_REQUIRED"}
        loaded = self.read(
            access,
            entitlements,
            workspace_id=workspace_id,
            now=now,
        )
        if not loaded["loaded"]:
            return {"backed_up": False, "reason": loaded["reason"]}
        paths = self._paths(access, workspace_id)
        acl = _load_json(Path(paths["acl"]))
        if not _acl_allows(
            access,
            acl,
            tenant_id=paths["tenant_id"],
            workspace_id=paths["workspace_id"],
            action="BACKUP",
        ):
            return {"backed_up": False, "reason": "ACL_BACKUP_DENIED"}
        envelope = _load_json(Path(paths["memory"]))
        backup_path = Path(paths["backups"]) / (
            loaded["revision"].replace("sha256:", "") + ".json"
        )
        _atomic_json_write(backup_path, envelope)
        _append_audit(Path(paths["audit"]), {
            "schema": SCHEMA,
            "event": "BACKUP",
            "at": _now(),
            "tenant_id": paths["tenant_id"],
            "workspace_id": paths["workspace_id"],
            "principal_id": _principal_id(access),
            "revision": loaded["revision"],
        })
        return {
            "backed_up": True,
            "reason": "BACKUP_CREATED",
            "revision": loaded["revision"],
            "backup_path": str(backup_path),
            "network_io": False,
        }

    def restore(
        self,
        access: Mapping[str, Any] | None,
        entitlements: Sequence[Mapping[str, Any]] | None,
        backup_revision: Any,
        *,
        workspace_id: Any = "default",
        approved: bool = False,
        expected_revision: Any = "",
        now: datetime | None = None,
    ) -> dict[str, Any]:
        if approved is not True:
            return {"restored": False, "reason": "EXPLICIT_RESTORE_APPROVAL_REQUIRED"}
        revision = str(backup_revision or "").strip()
        if not re.fullmatch(r"sha256:[a-f0-9]{64}", revision):
            return {"restored": False, "reason": "BACKUP_REVISION_INVALID"}
        paths = self._paths(access, workspace_id)
        ok, reason = self._ensure_identity_acl(access, paths)
        if not ok:
            return {"restored": False, "reason": reason}
        acl = _load_json(Path(paths["acl"]))
        if not _acl_allows(
            access,
            acl,
            tenant_id=paths["tenant_id"],
            workspace_id=paths["workspace_id"],
            action="RESTORE",
        ):
            return {"restored": False, "reason": "ACL_RESTORE_DENIED"}
        backup_path = Path(paths["backups"]) / (
            revision.replace("sha256:", "") + ".json"
        )
        if not backup_path.exists():
            return {"restored": False, "reason": "BACKUP_NOT_FOUND"}
        envelope = _load_json(backup_path)
        valid, verify_reason = _verify_envelope(
            envelope,
            tenant_id=paths["tenant_id"],
            workspace_id=paths["workspace_id"],
        )
        if not valid:
            return {"restored": False, "reason": verify_reason}
        if envelope.get("revision") != revision:
            return {"restored": False, "reason": "BACKUP_REVISION_MISMATCH"}
        result = self.write(
            access,
            entitlements,
            envelope["memory"],
            workspace_id=workspace_id,
            approved=True,
            expected_revision=expected_revision,
            now=now,
        )
        if not result["stored"]:
            return {
                "restored": False,
                "reason": result["reason"],
                "revision": result.get("revision", ""),
            }
        _append_audit(Path(paths["audit"]), {
            "schema": SCHEMA,
            "event": "RESTORE",
            "at": _now(),
            "tenant_id": paths["tenant_id"],
            "workspace_id": paths["workspace_id"],
            "principal_id": _principal_id(access),
            "revision": result["revision"],
            "source_backup_revision": revision,
        })
        return {
            "restored": True,
            "reason": "RESTORED",
            "revision": result["revision"],
            "source_backup_revision": revision,
            "network_io": False,
        }


def durable_store_policy() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "local_durable_io_implemented": True,
        "identity_registry_implemented": True,
        "acl_store_implemented": True,
        "atomic_replace": True,
        "integrity_digest": "SHA256",
        "optimistic_concurrency": True,
        "backup_restore_implemented": True,
        "audit_log_implemented": True,
        "cross_tenant_default": "DENY",
        "explicit_write_approval_required": True,
        "explicit_backup_restore_approval_required": True,
        "network_io_implemented": False,
        "production_persistence_activated": False,
        "automatic_write": False,
        "automatic_overwrite": False,
    }


__all__ = [
    "SCHEMA",
    "ENVELOPE_SCHEMA",
    "ACL_SCHEMA",
    "IDENTITY_SCHEMA",
    "DurableTenantStore",
    "normalize_workspace_id",
    "tenant_workspace_paths",
    "build_identity_record",
    "build_acl_record",
    "durable_store_policy",
]
