"""Staging-only resilience policy for AION Chat durable SQLite.

These objectives are test targets for the staged local store. They are not a
production activation promise. Production remains explicitly disabled.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any
from uuid import uuid4

from aion_chat.store import (
    HEALTHY, SQLiteChatStore, StorageUnavailableError,
    _file_sha256, _sync_staging_restore_directory,
)

SCHEMA = "ATLASQUANT_AION_CHAT_STORAGE_RESILIENCE_V1"
STAGING_RPO_SECONDS = 300
STAGING_RTO_SECONDS = 900


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    """Create a fresh local sidecar; never replace a prior manifest."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp-" + uuid4().hex)
    published = False
    try:
        with temp.open("x", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, sort_keys=True, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temp, path)
            published = True
        except FileExistsError as exc:
            raise StorageUnavailableError("manifest destination already exists") from exc
        try:
            _sync_staging_restore_directory(path.parent)
        except OSError as exc:
            raise StorageUnavailableError(
                "MANIFEST_PUBLICATION_UNCERTAIN_ZERO_AUTO_RETRY"
            ) from exc
    finally:
        try:
            temp.unlink(missing_ok=True)
        except OSError:
            if not published:
                raise StorageUnavailableError("failed to remove unpublished manifest temp")


def _unique_json_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("ambiguous duplicate JSON key")
        value[key] = item
    return value


def _verify_local_backup_manifest(backup_path: Path, manifest_path: Path) -> str:
    """Local consistency only; neither signature nor independent origin."""
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise StorageUnavailableError("restore denied: local manifest missing or unsafe")
    try:
        value = json.loads(
            manifest_path.read_text(encoding="utf-8"),
            object_pairs_hook=_unique_json_object,
        )
    except (OSError, UnicodeError, ValueError, TypeError) as exc:
        raise StorageUnavailableError("restore denied: invalid local manifest") from exc
    if not isinstance(value, dict) or (
        value.get("schema") != SCHEMA
        or value.get("state") != "BACKUP_VERIFIED"
        or value.get("staging_only") is not True
        or value.get("production_ready") is not False
    ):
        raise StorageUnavailableError("restore denied: local manifest contract invalid")
    report = value.get("backup")
    if not isinstance(report, dict):
        raise StorageUnavailableError("restore denied: backup report missing")
    expected_hash = report.get("sha256")
    expected_size = report.get("size_bytes")
    stored_path = report.get("backup_path")
    if not isinstance(expected_hash, str) or len(expected_hash) != 64 or any(
        ch not in "0123456789abcdef" for ch in expected_hash
    ):
        raise StorageUnavailableError("restore denied: invalid expected SHA-256")
    if type(expected_size) is not int or expected_size <= 0:
        raise StorageUnavailableError("restore denied: invalid backup byte count")
    if not isinstance(stored_path, str) or not stored_path:
        raise StorageUnavailableError("restore denied: backup pathname absent")
    try:
        if Path(stored_path).resolve(strict=True) != backup_path.resolve(strict=True):
            raise StorageUnavailableError("restore denied: manifest pathname mismatch")
        if not backup_path.is_file() or backup_path.is_symlink():
            raise StorageUnavailableError("restore denied: backup file unsafe")
        if backup_path.stat().st_size != expected_size:
            raise StorageUnavailableError("restore denied: backup size mismatch")
        if _file_sha256(backup_path) != expected_hash:
            raise StorageUnavailableError("restore denied: backup SHA-256 mismatch")
    except (OSError, ValueError) as exc:
        raise StorageUnavailableError("restore denied: backup cannot be inspected") from exc
    return expected_hash


def create_verified_staging_backup(
    store: SQLiteChatStore,
    backup_path: str | Path,
    *,
    manifest_path: str | Path | None = None,
) -> dict[str, Any]:
    """Checkpoint, backup via SQLite API, verify, and persist a sidecar manifest."""
    if not isinstance(store, SQLiteChatStore):
        raise TypeError("SQLiteChatStore required")
    health = store.require_healthy()
    sidecar = Path(manifest_path) if manifest_path else Path(str(backup_path) + ".manifest.json")
    if os.path.lexists(str(sidecar)):
        raise StorageUnavailableError("backup denied: manifest pathname already exists")
    report = store.backup_to(backup_path)
    manifest = {
        "schema": SCHEMA,
        "state": "BACKUP_VERIFIED",
        "created_at": _utc_now(),
        "staging_only": True,
        "production_ready": False,
        "rpo_seconds": STAGING_RPO_SECONDS,
        "rto_seconds": STAGING_RTO_SECONDS,
        "source_health": health,
        "backup": report,
        "restore_test_required": True,
    }
    _atomic_json(sidecar, manifest)
    return {**manifest, "manifest_path": str(sidecar)}


def restore_verified_staging_backup(
    backup_path: str | Path,
    target_path: str | Path,
    *,
    manifest_path: str | Path | None = None,
) -> dict[str, Any]:
    """Require a matching local manifest BEFORE publishing a restored SQLite DB."""
    backup = Path(backup_path)
    sidecar = Path(manifest_path) if manifest_path else Path(str(backup) + ".manifest.json")
    expected_hash = _verify_local_backup_manifest(backup, sidecar)
    report = SQLiteChatStore.restore_from_backup(
        backup, target_path, expected_sha256=expected_hash
    )
    restored = SQLiteChatStore(target_path)
    try:
        health = restored.require_healthy()
    finally:
        restored.close()
    if health["state"] != HEALTHY:
        raise StorageUnavailableError("restored staging database is not healthy")
    return {
        "schema": SCHEMA,
        "state": "RESTORE_VERIFIED",
        "staging_only": True,
        "production_ready": False,
        "rpo_seconds": STAGING_RPO_SECONDS,
        "rto_seconds": STAGING_RTO_SECONDS,
        "restore": report,
        "restored_health": health,
        "local_manifest_sha256_match": True,
        "independent_provenance_verified": False,
    }


__all__ = [
    "SCHEMA",
    "STAGING_RPO_SECONDS",
    "STAGING_RTO_SECONDS",
    "create_verified_staging_backup",
    "restore_verified_staging_backup",
]
