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

from aion_chat.store import HEALTHY, SQLiteChatStore, StorageUnavailableError

SCHEMA = "ATLASQUANT_AION_CHAT_STORAGE_RESILIENCE_V1"
STAGING_RPO_SECONDS = 300
STAGING_RTO_SECONDS = 900


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp-" + uuid4().hex)
    try:
        temp.write_text(
            json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2),
            encoding="utf-8",
        )
        os.replace(temp, path)
    finally:
        try:
            temp.unlink(missing_ok=True)
        except Exception:
            pass


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
    sidecar = Path(manifest_path) if manifest_path else Path(str(backup_path) + ".manifest.json")
    _atomic_json(sidecar, manifest)
    return {**manifest, "manifest_path": str(sidecar)}


def restore_verified_staging_backup(
    backup_path: str | Path,
    target_path: str | Path,
) -> dict[str, Any]:
    """Atomically restore a verified snapshot and prove the restored DB is healthy."""
    report = SQLiteChatStore.restore_from_backup(backup_path, target_path)
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
    }


__all__ = [
    "SCHEMA",
    "STAGING_RPO_SECONDS",
    "STAGING_RTO_SECONDS",
    "create_verified_staging_backup",
    "restore_verified_staging_backup",
]
