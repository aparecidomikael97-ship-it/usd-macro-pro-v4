"""AION Windows Local Service Installation Blueprint + Crash/Process Isolation V1.

Executable local process-isolation primitives plus a non-installing Windows
service blueprint.

This layer prepares a future per-user Windows background agent without actually
installing or spawning a Windows service.

Implemented/testable on CI:
- atomic singleton lock-file acquisition;
- immutable lock ownership metadata with tamper-evident digest;
- service-instance/heartbeat state in the existing hardened SQLite truth;
- fail-closed startup that re-enables the local kill switch;
- clean shutdown bookkeeping and lock release;
- read-only health/readiness snapshot;
- explicit crash/stale-lock recovery ceremony;
- concurrency stress for singleton acquisition;
- owner-only logical named-pipe health IPC contract.

Explicitly absent:
- Windows SCM/Task Scheduler installation;
- process spawning;
- SYSTEM/LocalSystem execution;
- TCP/HTTP listener;
- remote/LAN control;
- real Windows ACL mutation;
- owner private-key handling;
- GitHub credentials/network/API;
- live repository mutation;
- deploy/Worker/provider activation.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import hashlib
import os
from pathlib import Path
import re
import sqlite3
from typing import Any, Mapping

from atlasquant_aion_repository_mutation_offline_runtime_v1 import (
    OfflineRuntimeError,
)
from atlasquant_aion_repository_mutation_local_runtime_hardening_v1 import (
    HardenedLocalRepositoryMutationStore,
    WINDOWS_ACL_SCHEMA,
    WINDOWS_LAYOUT_SCHEMA,
)


SCHEMA = "ATLASQUANT_AION_WINDOWS_LOCAL_SERVICE_CRASH_ISOLATION_V1"
BLUEPRINT_SCHEMA = "ATLASQUANT_AION_WINDOWS_LOCAL_SERVICE_INSTALLATION_BLUEPRINT_V1"
LOCK_SCHEMA = "ATLASQUANT_AION_WINDOWS_LOCAL_SERVICE_PROCESS_LOCK_V1"
STARTUP_SCHEMA = "ATLASQUANT_AION_WINDOWS_LOCAL_SERVICE_STARTUP_V1"
HEALTH_SCHEMA = "ATLASQUANT_AION_WINDOWS_LOCAL_SERVICE_HEALTH_V1"
RECOVERY_SCHEMA = "ATLASQUANT_AION_WINDOWS_LOCAL_SERVICE_STALE_LOCK_RECOVERY_V1"
IPC_SCHEMA = "ATLASQUANT_AION_WINDOWS_LOCAL_SERVICE_IPC_V1"
POLICY_SCHEMA = "ATLASQUANT_AION_WINDOWS_LOCAL_SERVICE_POLICY_V1"

SERVICE_MODE = "CURRENT_USER_LOGON_AGENT"
SERVICE_ID = "AtlasQuant.AION.RepositoryMutationRuntime"
HEALTH_PIPE_NAME = r"\\.\pipe\AtlasQuant.AION.RepositoryMutationRuntime.Health.v1"
MAX_HEARTBEAT_AGE_SECONDS = 30
LOCK_FILE_MODE_POSIX = 0o600
FAIL_CLOSED_STARTUP_REASON = "SERVICE_STARTUP_FAIL_CLOSED"
FAIL_CLOSED_SHUTDOWN_REASON = "SERVICE_SHUTDOWN_FAIL_CLOSED"
FAIL_CLOSED_CRASH_REASON = "SERVICE_CRASH_RECOVERY_FAIL_CLOSED"

_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{2,239}$")


def _clean(value: Any, limit: int = 1000) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _canonical(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
        default=str,
    )


def _digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(
        _canonical(value).encode("utf-8")
    ).hexdigest()


def _sha256(value: Any) -> str:
    token = _clean(value, 90)
    return token if _DIGEST_RE.fullmatch(token) else ""


def _identity(value: Any, limit: int = 240) -> str:
    if type(value) is not str:
        return ""
    text = _clean(value, limit)
    if text != value or not _ID_RE.fullmatch(text):
        return ""
    return text


def _aware(value: Any, label: str) -> datetime:
    try:
        if isinstance(value, datetime):
            dt = value
        else:
            dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception as exc:
        raise OfflineRuntimeError(label + "_INVALID") from exc
    if dt.tzinfo is None:
        raise OfflineRuntimeError(label + "_TIMEZONE_REQUIRED")
    return dt.astimezone(timezone.utc)


def _iso(value: Any, label: str) -> str:
    return _aware(value, label).isoformat()


def build_windows_service_installation_blueprint(
    layout: Mapping[str, Any] | None,
    acl_attestation: Mapping[str, Any] | None,
    *,
    package_digest: Any,
    code_signing_evidence_digest: Any,
    uninstall_plan_digest: Any,
    owner_key_enrollment_digest: Any,
) -> dict[str, Any]:
    """Plan a future per-user agent installation; never install it."""
    layout_row = dict(layout or {})
    acl = dict(acl_attestation or {})
    blockers: list[str] = []

    if layout_row.get("schema") != WINDOWS_LAYOUT_SCHEMA:
        blockers.append("WINDOWS_LAYOUT_SCHEMA_MISMATCH")
    if layout_row.get("state") != "WINDOWS_RUNTIME_LAYOUT_READY":
        blockers.append("READY_WINDOWS_LAYOUT_REQUIRED")
    if acl.get("schema") != WINDOWS_ACL_SCHEMA:
        blockers.append("WINDOWS_ACL_ATTESTATION_SCHEMA_MISMATCH")
    if acl.get("state") != "WINDOWS_OWNER_ACL_ATTESTED":
        blockers.append("WINDOWS_OWNER_ACL_ATTESTATION_REQUIRED")
    if _sha256(acl.get("layout_digest")) != _sha256(layout_row.get("layout_digest")):
        blockers.append("ACL_LAYOUT_BINDING_MISMATCH")

    package = _sha256(package_digest)
    signing = _sha256(code_signing_evidence_digest)
    uninstall = _sha256(uninstall_plan_digest)
    enrollment = _sha256(owner_key_enrollment_digest)
    if not package:
        blockers.append("PACKAGE_DIGEST_REQUIRED")
    if not signing:
        blockers.append("CODE_SIGNING_EVIDENCE_DIGEST_REQUIRED")
    if not uninstall:
        blockers.append("UNINSTALL_PLAN_DIGEST_REQUIRED")
    if not enrollment:
        blockers.append("OWNER_KEY_ENROLLMENT_DIGEST_REQUIRED")

    material = {
        "service_id": SERVICE_ID,
        "service_mode": SERVICE_MODE,
        "runtime_root": layout_row.get("runtime_root"),
        "db_path": layout_row.get("db_path"),
        "lock_path": layout_row.get("lock_path"),
        "health_pipe_name": HEALTH_PIPE_NAME,
        "layout_digest": _sha256(layout_row.get("layout_digest")),
        "acl_attestation_digest": _sha256(acl.get("acl_attestation_digest")),
        "package_digest": package,
        "code_signing_evidence_digest": signing,
        "uninstall_plan_digest": uninstall,
        "owner_key_enrollment_digest": enrollment,
        "startup_trigger": "CURRENT_USER_LOGON",
        "restart_policy": "FAIL_CLOSED_RESTART_WITH_OWNER_REOPEN_REQUIRED",
        "process_identity": "CURRENT_WINDOWS_USER",
        "health_transport": "OWNER_ONLY_NAMED_PIPE",
    }
    blockers = list(dict.fromkeys(blockers))
    return {
        "schema": BLUEPRINT_SCHEMA,
        "state": "WINDOWS_LOCAL_SERVICE_BLUEPRINT_READY" if not blockers else "BLOCKED",
        "blockers": blockers,
        **material,
        "blueprint_digest": _digest(material) if not blockers else "",
        "windows_service_installed": False,
        "scheduled_task_installed": False,
        "process_spawned": False,
        "system_account_used": False,
        "local_system_used": False,
        "admin_elevation_required_at_runtime": False,
        "tcp_listener_enabled": False,
        "http_listener_enabled": False,
        "remote_control_enabled": False,
        "lan_control_enabled": False,
        "firewall_rule_created": False,
        "filesystem_modified_by_blueprint": False,
        "github_api_called": False,
        "network_called": False,
        "live_repository_mutation_performed": False,
    }


def local_health_ipc_contract() -> dict[str, Any]:
    """Expose the logical owner-only health IPC contract; opens nothing."""
    return {
        "schema": IPC_SCHEMA,
        "state": "OWNER_ONLY_LOCAL_HEALTH_IPC_DEFINED",
        "service_id": SERVICE_ID,
        "transport": "WINDOWS_NAMED_PIPE",
        "pipe_name": HEALTH_PIPE_NAME,
        "allowed_operations": ["GET_HEALTH", "GET_READINESS"],
        "owner_sid_acl_required": True,
        "current_user_only": True,
        "local_machine_only": True,
        "anonymous_access_allowed": False,
        "remote_pipe_access_allowed": False,
        "command_dispatch_allowed": False,
        "mutation_dispatch_allowed": False,
        "credential_exchange_allowed": False,
        "tcp_listener_enabled": False,
        "http_listener_enabled": False,
        "socket_opened_by_this_module": False,
        "pipe_opened_by_this_module": False,
        "network_called": False,
    }


class WindowsServiceRuntimeStore(HardenedLocalRepositoryMutationStore):
    """Adds service/process metadata to the same SQLite runtime truth."""

    def __init__(self, db_path: str | os.PathLike[str]):
        super().__init__(db_path)
        self._initialize_service_runtime()

    def _initialize_service_runtime(self) -> None:
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS local_service_instances (
                        instance_id TEXT PRIMARY KEY,
                        process_id INTEGER NOT NULL,
                        process_start_digest TEXT NOT NULL,
                        lock_digest TEXT NOT NULL,
                        owner_subject TEXT NOT NULL,
                        state TEXT NOT NULL,
                        started_at TEXT NOT NULL,
                        last_heartbeat_at TEXT NOT NULL,
                        clean_shutdown_at TEXT NOT NULL,
                        crash_detected_at TEXT NOT NULL
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS local_service_stale_lock_recoveries (
                        recovery_id TEXT PRIMARY KEY,
                        stale_lock_digest TEXT NOT NULL UNIQUE,
                        instance_id TEXT NOT NULL,
                        process_not_running_evidence_digest TEXT NOT NULL,
                        owner_session_evidence_digest TEXT NOT NULL,
                        recovered_at TEXT NOT NULL
                    )
                    """
                )
                conn.execute("COMMIT")
            except Exception:
                if conn.in_transaction:
                    conn.execute("ROLLBACK")
                raise

    def register_instance(
        self,
        *,
        instance_id: Any,
        process_id: int,
        process_start_digest: Any,
        lock_digest: Any,
        owner_subject: Any,
        started_at: Any,
    ) -> dict[str, Any]:
        instance = _identity(instance_id, 180)
        process_digest = _sha256(process_start_digest)
        lock = _sha256(lock_digest)
        owner = _identity(owner_subject, 240)
        at = _iso(started_at, "SERVICE_STARTED_AT")
        if not instance:
            raise OfflineRuntimeError("SERVICE_INSTANCE_ID_REQUIRED")
        if int(process_id) <= 0:
            raise OfflineRuntimeError("SERVICE_PROCESS_ID_INVALID")
        if not process_digest:
            raise OfflineRuntimeError("PROCESS_START_DIGEST_REQUIRED")
        if not lock:
            raise OfflineRuntimeError("PROCESS_LOCK_DIGEST_REQUIRED")
        if not owner:
            raise OfflineRuntimeError("OWNER_SUBJECT_REQUIRED")

        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                active = conn.execute(
                    """
                    SELECT instance_id FROM local_service_instances
                    WHERE state IN ('STARTING','RUNNING','CRASH_RECOVERY_REQUIRED')
                    """
                ).fetchall()
                if active:
                    raise OfflineRuntimeError("ACTIVE_SERVICE_INSTANCE_ALREADY_REGISTERED")
                conn.execute(
                    """
                    INSERT INTO local_service_instances(
                        instance_id, process_id, process_start_digest,
                        lock_digest, owner_subject, state, started_at,
                        last_heartbeat_at, clean_shutdown_at, crash_detected_at
                    ) VALUES (?, ?, ?, ?, ?, 'RUNNING', ?, ?, '', '')
                    """,
                    (
                        instance,
                        int(process_id),
                        process_digest,
                        lock,
                        owner,
                        at,
                        at,
                    ),
                )
                conn.execute("COMMIT")
            except Exception:
                if conn.in_transaction:
                    conn.execute("ROLLBACK")
                raise
        return self.get_instance(instance)

    def get_instance(self, instance_id: Any) -> dict[str, Any]:
        instance = _identity(instance_id, 180)
        if not instance:
            raise OfflineRuntimeError("SERVICE_INSTANCE_ID_REQUIRED")
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM local_service_instances WHERE instance_id=?",
                (instance,),
            ).fetchone()
        if row is None:
            raise OfflineRuntimeError("SERVICE_INSTANCE_NOT_FOUND")
        return dict(row)

    def active_instances(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM local_service_instances
                WHERE state IN ('STARTING','RUNNING','CRASH_RECOVERY_REQUIRED')
                ORDER BY started_at, instance_id
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def heartbeat(
        self,
        *,
        instance_id: Any,
        lock_digest: Any,
        heartbeat_at: Any,
    ) -> dict[str, Any]:
        instance = _identity(instance_id, 180)
        lock = _sha256(lock_digest)
        at = _iso(heartbeat_at, "SERVICE_HEARTBEAT_AT")
        if not instance or not lock:
            raise OfflineRuntimeError("SERVICE_HEARTBEAT_BINDING_INVALID")
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                row = conn.execute(
                    "SELECT * FROM local_service_instances WHERE instance_id=?",
                    (instance,),
                ).fetchone()
                if row is None:
                    raise OfflineRuntimeError("SERVICE_INSTANCE_NOT_FOUND")
                item = dict(row)
                if item["state"] != "RUNNING":
                    raise OfflineRuntimeError("SERVICE_INSTANCE_NOT_RUNNING")
                if item["lock_digest"] != lock:
                    raise OfflineRuntimeError("SERVICE_HEARTBEAT_LOCK_MISMATCH")
                conn.execute(
                    """
                    UPDATE local_service_instances
                    SET last_heartbeat_at=?
                    WHERE instance_id=? AND state='RUNNING'
                    """,
                    (at, instance),
                )
                conn.execute("COMMIT")
            except Exception:
                if conn.in_transaction:
                    conn.execute("ROLLBACK")
                raise
        return self.get_instance(instance)

    def mark_clean_shutdown(
        self,
        *,
        instance_id: Any,
        lock_digest: Any,
        shutdown_at: Any,
    ) -> dict[str, Any]:
        instance = _identity(instance_id, 180)
        lock = _sha256(lock_digest)
        at = _iso(shutdown_at, "SERVICE_SHUTDOWN_AT")
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                row = conn.execute(
                    "SELECT * FROM local_service_instances WHERE instance_id=?",
                    (instance,),
                ).fetchone()
                if row is None:
                    raise OfflineRuntimeError("SERVICE_INSTANCE_NOT_FOUND")
                item = dict(row)
                if item["lock_digest"] != lock:
                    raise OfflineRuntimeError("SERVICE_SHUTDOWN_LOCK_MISMATCH")
                if item["state"] != "RUNNING":
                    raise OfflineRuntimeError("SERVICE_INSTANCE_NOT_RUNNING")
                conn.execute(
                    """
                    UPDATE local_service_instances
                    SET state='STOPPED', clean_shutdown_at=?
                    WHERE instance_id=?
                    """,
                    (at, instance),
                )
                conn.execute("COMMIT")
            except Exception:
                if conn.in_transaction:
                    conn.execute("ROLLBACK")
                raise
        return self.get_instance(instance)

    def mark_crash_recovery_required(
        self,
        *,
        instance_id: Any,
        detected_at: Any,
    ) -> dict[str, Any]:
        instance = _identity(instance_id, 180)
        at = _iso(detected_at, "CRASH_DETECTED_AT")
        # Restrictive transition is safe to perform automatically.
        self.set_kill_switch(
            enabled=True,
            reason=FAIL_CLOSED_CRASH_REASON,
            updated_at=at,
        )
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                row = conn.execute(
                    "SELECT * FROM local_service_instances WHERE instance_id=?",
                    (instance,),
                ).fetchone()
                if row is None:
                    raise OfflineRuntimeError("SERVICE_INSTANCE_NOT_FOUND")
                if row["state"] not in ("RUNNING", "CRASH_RECOVERY_REQUIRED"):
                    raise OfflineRuntimeError("SERVICE_INSTANCE_NOT_CRASH_RECOVERABLE")
                conn.execute(
                    """
                    UPDATE local_service_instances
                    SET state='CRASH_RECOVERY_REQUIRED', crash_detected_at=?
                    WHERE instance_id=?
                    """,
                    (at, instance),
                )
                conn.execute("COMMIT")
            except Exception:
                if conn.in_transaction:
                    conn.execute("ROLLBACK")
                raise
        return self.get_instance(instance)

    def record_stale_lock_recovery(
        self,
        *,
        recovery_id: Any,
        stale_lock_digest: Any,
        instance_id: Any,
        process_not_running_evidence_digest: Any,
        owner_session_evidence_digest: Any,
        recovered_at: Any,
    ) -> dict[str, Any]:
        recovery = _identity(recovery_id, 180)
        stale = _sha256(stale_lock_digest)
        instance = _identity(instance_id, 180)
        dead_evidence = _sha256(process_not_running_evidence_digest)
        owner_evidence = _sha256(owner_session_evidence_digest)
        at = _iso(recovered_at, "STALE_LOCK_RECOVERED_AT")
        if not all((recovery, stale, instance, dead_evidence, owner_evidence)):
            raise OfflineRuntimeError("STALE_LOCK_RECOVERY_BINDING_INVALID")
        if self.kill_switch_status()["enabled"] is not True:
            raise OfflineRuntimeError("KILL_SWITCH_MUST_BE_ENABLED_FOR_STALE_LOCK_RECOVERY")

        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                row = conn.execute(
                    "SELECT * FROM local_service_instances WHERE instance_id=?",
                    (instance,),
                ).fetchone()
                if row is None:
                    raise OfflineRuntimeError("SERVICE_INSTANCE_NOT_FOUND")
                if row["lock_digest"] != stale:
                    raise OfflineRuntimeError("STALE_LOCK_INSTANCE_BINDING_MISMATCH")
                if row["state"] != "CRASH_RECOVERY_REQUIRED":
                    raise OfflineRuntimeError("CRASH_RECOVERY_STATE_REQUIRED")
                existing = conn.execute(
                    """
                    SELECT * FROM local_service_stale_lock_recoveries
                    WHERE stale_lock_digest=?
                    """,
                    (stale,),
                ).fetchone()
                if existing is not None:
                    item = dict(existing)
                    if item["recovery_id"] != recovery:
                        raise OfflineRuntimeError("STALE_LOCK_ALREADY_RECOVERED")
                    conn.execute("COMMIT")
                    item["replay"] = True
                    return item

                conn.execute(
                    """
                    INSERT INTO local_service_stale_lock_recoveries(
                        recovery_id, stale_lock_digest, instance_id,
                        process_not_running_evidence_digest,
                        owner_session_evidence_digest, recovered_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        recovery,
                        stale,
                        instance,
                        dead_evidence,
                        owner_evidence,
                        at,
                    ),
                )
                conn.execute(
                    """
                    UPDATE local_service_instances
                    SET state='CRASHED_RECOVERED'
                    WHERE instance_id=?
                    """,
                    (instance,),
                )
                conn.execute("COMMIT")
            except Exception:
                if conn.in_transaction:
                    conn.execute("ROLLBACK")
                raise
        return {
            "recovery_id": recovery,
            "stale_lock_digest": stale,
            "instance_id": instance,
            "process_not_running_evidence_digest": dead_evidence,
            "owner_session_evidence_digest": owner_evidence,
            "recovered_at": at,
            "replay": False,
        }


class AtomicProcessLock:
    """Atomic local singleton lock. Never auto-deletes a stale lock."""

    def __init__(self, lock_path: str | os.PathLike[str]):
        self.path = Path(lock_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _validate_path(self) -> None:
        if self.path.exists() and self.path.is_symlink():
            raise OfflineRuntimeError("PROCESS_LOCK_SYMLINK_REJECTED")

    def acquire(
        self,
        *,
        instance_id: Any,
        process_id: int,
        process_start_digest: Any,
        owner_subject: Any,
        acquired_at: Any,
    ) -> dict[str, Any]:
        self._validate_path()
        instance = _identity(instance_id, 180)
        process_digest = _sha256(process_start_digest)
        owner = _identity(owner_subject, 240)
        at = _iso(acquired_at, "PROCESS_LOCK_ACQUIRED_AT")
        if not instance:
            raise OfflineRuntimeError("SERVICE_INSTANCE_ID_REQUIRED")
        if int(process_id) <= 0:
            raise OfflineRuntimeError("SERVICE_PROCESS_ID_INVALID")
        if not process_digest:
            raise OfflineRuntimeError("PROCESS_START_DIGEST_REQUIRED")
        if not owner:
            raise OfflineRuntimeError("OWNER_SUBJECT_REQUIRED")

        material = {
            "schema": LOCK_SCHEMA,
            "service_id": SERVICE_ID,
            "instance_id": instance,
            "process_id": int(process_id),
            "process_start_digest": process_digest,
            "owner_subject": owner,
            "acquired_at": at,
        }
        payload = {**material, "lock_digest": _digest(material)}
        encoded = (_canonical(payload) + "\n").encode("utf-8")

        flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
        try:
            fd = os.open(str(self.path), flags, LOCK_FILE_MODE_POSIX)
        except FileExistsError as exc:
            raise OfflineRuntimeError("PROCESS_SINGLETON_LOCK_ALREADY_HELD") from exc
        try:
            os.write(fd, encoded)
            os.fsync(fd)
        finally:
            os.close(fd)
        if os.name != "nt":
            try:
                os.chmod(self.path, LOCK_FILE_MODE_POSIX)
            except OSError:
                pass
        return payload

    def read(self) -> dict[str, Any]:
        self._validate_path()
        if not self.path.exists():
            raise OfflineRuntimeError("PROCESS_LOCK_NOT_FOUND")
        try:
            raw = self.path.read_text(encoding="utf-8")
            value = json.loads(raw)
        except Exception as exc:
            raise OfflineRuntimeError("PROCESS_LOCK_CONTENT_INVALID") from exc
        if not isinstance(value, Mapping):
            raise OfflineRuntimeError("PROCESS_LOCK_CONTENT_INVALID")
        row = dict(value)
        if row.get("schema") != LOCK_SCHEMA:
            raise OfflineRuntimeError("PROCESS_LOCK_SCHEMA_MISMATCH")
        supplied = _sha256(row.get("lock_digest"))
        material = {
            key: row.get(key)
            for key in (
                "schema",
                "service_id",
                "instance_id",
                "process_id",
                "process_start_digest",
                "owner_subject",
                "acquired_at",
            )
        }
        if not supplied or supplied != _digest(material):
            raise OfflineRuntimeError("PROCESS_LOCK_DIGEST_MISMATCH")
        return row

    def release_clean(
        self,
        *,
        instance_id: Any,
        lock_digest: Any,
    ) -> None:
        row = self.read()
        if row["instance_id"] != _identity(instance_id, 180):
            raise OfflineRuntimeError("PROCESS_LOCK_INSTANCE_MISMATCH")
        if row["lock_digest"] != _sha256(lock_digest):
            raise OfflineRuntimeError("PROCESS_LOCK_DIGEST_MISMATCH")
        self.path.unlink()

    def remove_after_verified_stale_recovery(
        self,
        *,
        instance_id: Any,
        lock_digest: Any,
        recovery_record: Mapping[str, Any] | None,
    ) -> None:
        row = self.read()
        recovery = dict(recovery_record or {})
        if row["instance_id"] != _identity(instance_id, 180):
            raise OfflineRuntimeError("PROCESS_LOCK_INSTANCE_MISMATCH")
        if row["lock_digest"] != _sha256(lock_digest):
            raise OfflineRuntimeError("PROCESS_LOCK_DIGEST_MISMATCH")
        if recovery.get("instance_id") != row["instance_id"]:
            raise OfflineRuntimeError("STALE_RECOVERY_INSTANCE_MISMATCH")
        if _sha256(recovery.get("stale_lock_digest")) != row["lock_digest"]:
            raise OfflineRuntimeError("STALE_RECOVERY_LOCK_DIGEST_MISMATCH")
        if not _sha256(recovery.get("process_not_running_evidence_digest")):
            raise OfflineRuntimeError("PROCESS_NOT_RUNNING_EVIDENCE_REQUIRED")
        self.path.unlink()


class WindowsLocalServiceController:
    """Lifecycle controller for the current process; never spawns/installs it."""

    def __init__(
        self,
        *,
        store: WindowsServiceRuntimeStore,
        lock: AtomicProcessLock,
    ):
        self.store = store
        self.lock = lock

    def start_current_process(
        self,
        *,
        instance_id: Any,
        process_id: int,
        process_start_digest: Any,
        owner_subject: Any,
        started_at: Any,
    ) -> dict[str, Any]:
        integrity = self.store.integrity_report()
        if integrity.get("integrity_ok") is not True:
            raise OfflineRuntimeError("LOCAL_RUNTIME_INTEGRITY_REQUIRED")
        owner = self.store.get_active_owner_key()
        if owner.get("owner_subject") != owner_subject:
            raise OfflineRuntimeError("SERVICE_OWNER_SUBJECT_MISMATCH")

        # Every restart closes the mutation gate. Reopening requires the
        # separate signed owner kill-switch ceremony from #1043.
        self.store.set_kill_switch(
            enabled=True,
            reason=FAIL_CLOSED_STARTUP_REASON,
            updated_at=started_at,
        )
        lock_record = self.lock.acquire(
            instance_id=instance_id,
            process_id=process_id,
            process_start_digest=process_start_digest,
            owner_subject=owner_subject,
            acquired_at=started_at,
        )
        try:
            instance = self.store.register_instance(
                instance_id=instance_id,
                process_id=process_id,
                process_start_digest=process_start_digest,
                lock_digest=lock_record["lock_digest"],
                owner_subject=owner_subject,
                started_at=started_at,
            )
        except Exception:
            # Safe rollback of a lock we just created; no runtime authority was
            # opened because the kill switch remains enabled.
            try:
                self.lock.release_clean(
                    instance_id=instance_id,
                    lock_digest=lock_record["lock_digest"],
                )
            except Exception:
                pass
            raise

        return {
            "schema": STARTUP_SCHEMA,
            "state": "LOCAL_SERVICE_PROCESS_RUNNING_FAIL_CLOSED",
            "service_id": SERVICE_ID,
            "service_mode": SERVICE_MODE,
            "instance": instance,
            "lock": lock_record,
            "kill_switch": self.store.kill_switch_status(),
            "owner_key_enrolled": True,
            "process_spawned_by_this_module": False,
            "windows_service_installed": False,
            "scheduled_task_installed": False,
            "mutation_gate_open": False,
            "github_api_called": False,
            "network_called": False,
            "live_repository_mutation_authorized": False,
            "live_repository_mutation_performed": False,
        }

    def heartbeat(
        self,
        *,
        instance_id: Any,
        heartbeat_at: Any,
    ) -> dict[str, Any]:
        lock = self.lock.read()
        if lock["instance_id"] != _identity(instance_id, 180):
            raise OfflineRuntimeError("PROCESS_LOCK_INSTANCE_MISMATCH")
        return self.store.heartbeat(
            instance_id=instance_id,
            lock_digest=lock["lock_digest"],
            heartbeat_at=heartbeat_at,
        )

    def clean_shutdown(
        self,
        *,
        instance_id: Any,
        shutdown_at: Any,
    ) -> dict[str, Any]:
        lock = self.lock.read()
        self.store.set_kill_switch(
            enabled=True,
            reason=FAIL_CLOSED_SHUTDOWN_REASON,
            updated_at=shutdown_at,
        )
        instance = self.store.mark_clean_shutdown(
            instance_id=instance_id,
            lock_digest=lock["lock_digest"],
            shutdown_at=shutdown_at,
        )
        self.lock.release_clean(
            instance_id=instance_id,
            lock_digest=lock["lock_digest"],
        )
        return {
            "schema": STARTUP_SCHEMA,
            "state": "LOCAL_SERVICE_PROCESS_STOPPED_CLEANLY",
            "instance": instance,
            "kill_switch": self.store.kill_switch_status(),
            "lock_released": True,
            "automatic_restart_authorized": False,
            "live_repository_mutation_authorized": False,
            "live_repository_mutation_performed": False,
        }

    def health_snapshot(
        self,
        *,
        instance_id: Any,
        now: Any,
    ) -> dict[str, Any]:
        current = _aware(now, "HEALTH_NOW")
        blockers: list[str] = []
        integrity = self.store.integrity_report()
        if integrity.get("integrity_ok") is not True:
            blockers.append("LOCAL_RUNTIME_INTEGRITY_FAILED")

        try:
            lock = self.lock.read()
        except OfflineRuntimeError as exc:
            lock = {}
            blockers.append(exc.code)

        try:
            instance = self.store.get_instance(instance_id)
        except OfflineRuntimeError as exc:
            instance = {}
            blockers.append(exc.code)

        if instance:
            if instance.get("state") != "RUNNING":
                blockers.append("SERVICE_INSTANCE_NOT_RUNNING")
            try:
                heartbeat = _aware(
                    instance.get("last_heartbeat_at"),
                    "LAST_HEARTBEAT_AT",
                )
                age = (current - heartbeat).total_seconds()
                if age < 0:
                    blockers.append("HEARTBEAT_FROM_FUTURE")
                if age > MAX_HEARTBEAT_AGE_SECONDS:
                    blockers.append("HEARTBEAT_STALE")
            except OfflineRuntimeError:
                age = None
                blockers.append("HEARTBEAT_TIME_INVALID")
        else:
            age = None

        if lock and instance:
            if lock.get("instance_id") != instance.get("instance_id"):
                blockers.append("LOCK_INSTANCE_BINDING_MISMATCH")
            if lock.get("lock_digest") != instance.get("lock_digest"):
                blockers.append("LOCK_DIGEST_BINDING_MISMATCH")

        kill = self.store.kill_switch_status()
        process_healthy = not blockers
        mutation_runtime_ready = process_healthy and kill["enabled"] is False
        material = {
            "service_id": SERVICE_ID,
            "instance_id": _identity(instance_id, 180),
            "process_healthy": process_healthy,
            "mutation_runtime_ready": mutation_runtime_ready,
            "kill_switch_enabled": kill["enabled"],
            "heartbeat_age_seconds": age,
            "lock_digest": lock.get("lock_digest", ""),
            "integrity_report_digest": integrity.get("integrity_report_digest", ""),
            "observed_at": current.isoformat(),
        }
        return {
            "schema": HEALTH_SCHEMA,
            "state": "HEALTHY" if process_healthy else "DEGRADED",
            "blockers": list(dict.fromkeys(blockers)),
            **material,
            "health_digest": _digest(material),
            "health_transport": "OWNER_ONLY_NAMED_PIPE_CONTRACT",
            "tcp_listener_enabled": False,
            "http_listener_enabled": False,
            "network_called": False,
            "github_api_called": False,
            "live_repository_mutation_performed": False,
        }

    def inspect_crash_candidate(
        self,
        *,
        instance_id: Any,
        now: Any,
    ) -> dict[str, Any]:
        current = _aware(now, "CRASH_INSPECTION_NOW")
        lock = self.lock.read()
        instance = self.store.get_instance(instance_id)
        if lock["instance_id"] != instance["instance_id"]:
            raise OfflineRuntimeError("LOCK_INSTANCE_BINDING_MISMATCH")
        if lock["lock_digest"] != instance["lock_digest"]:
            raise OfflineRuntimeError("LOCK_DIGEST_BINDING_MISMATCH")

        heartbeat = _aware(instance["last_heartbeat_at"], "LAST_HEARTBEAT_AT")
        age = (current - heartbeat).total_seconds()
        stale = age > MAX_HEARTBEAT_AGE_SECONDS
        if stale:
            self.store.mark_crash_recovery_required(
                instance_id=instance_id,
                detected_at=current.isoformat(),
            )
        return {
            "schema": RECOVERY_SCHEMA,
            "state": (
                "PROCESS_LIVENESS_ATTESTATION_REQUIRED"
                if stale
                else "PROCESS_HEARTBEAT_CURRENT"
            ),
            "instance_id": instance["instance_id"],
            "process_id": instance["process_id"],
            "lock_digest": lock["lock_digest"],
            "heartbeat_age_seconds": age,
            "heartbeat_stale": stale,
            "process_not_running_verified": False,
            "stale_lock_removed": False,
            "automatic_restart_authorized": False,
            "automatic_lock_recovery_allowed": False,
            "kill_switch": self.store.kill_switch_status(),
            "network_called": False,
            "live_repository_mutation_performed": False,
        }

    def recover_verified_dead_process(
        self,
        *,
        candidate: Mapping[str, Any] | None,
        recovery_id: Any,
        process_not_running_evidence_digest: Any,
        owner_session_evidence_digest: Any,
        process_not_running_verified: bool,
        owner_session_match_verified: bool,
        recovered_at: Any,
    ) -> dict[str, Any]:
        row = dict(candidate or {})
        if row.get("schema") != RECOVERY_SCHEMA:
            raise OfflineRuntimeError("CRASH_CANDIDATE_SCHEMA_MISMATCH")
        if row.get("state") != "PROCESS_LIVENESS_ATTESTATION_REQUIRED":
            raise OfflineRuntimeError("STALE_PROCESS_CANDIDATE_REQUIRED")
        if process_not_running_verified is not True:
            raise OfflineRuntimeError("PROCESS_NOT_RUNNING_VERIFICATION_REQUIRED")
        if owner_session_match_verified is not True:
            raise OfflineRuntimeError("OWNER_SESSION_MATCH_REQUIRED")

        recovery = self.store.record_stale_lock_recovery(
            recovery_id=recovery_id,
            stale_lock_digest=row.get("lock_digest"),
            instance_id=row.get("instance_id"),
            process_not_running_evidence_digest=process_not_running_evidence_digest,
            owner_session_evidence_digest=owner_session_evidence_digest,
            recovered_at=recovered_at,
        )
        self.lock.remove_after_verified_stale_recovery(
            instance_id=row.get("instance_id"),
            lock_digest=row.get("lock_digest"),
            recovery_record=recovery,
        )
        return {
            "schema": RECOVERY_SCHEMA,
            "state": "VERIFIED_DEAD_PROCESS_LOCK_RECOVERED",
            "recovery": recovery,
            "stale_lock_removed": True,
            "kill_switch": self.store.kill_switch_status(),
            "automatic_restart_authorized": False,
            "mutation_gate_open": False,
            "github_api_called": False,
            "network_called": False,
            "live_repository_mutation_authorized": False,
            "live_repository_mutation_performed": False,
        }


def windows_local_service_policy() -> dict[str, Any]:
    return {
        "schema": POLICY_SCHEMA,
        "service_id": SERVICE_ID,
        "service_mode": SERVICE_MODE,
        "current_user_only": True,
        "system_account_allowed": False,
        "local_system_allowed": False,
        "runtime_admin_elevation_required": False,
        "startup_trigger": "CURRENT_USER_LOGON",
        "singleton_process_required": True,
        "atomic_lock_file_implemented": True,
        "lock_file_auto_deleted_when_stale": False,
        "stale_lock_requires_process_liveness_attestation": True,
        "stale_lock_requires_owner_session_match": True,
        "kill_switch_forced_enabled_on_startup": True,
        "kill_switch_forced_enabled_on_shutdown": True,
        "kill_switch_forced_enabled_on_crash_recovery": True,
        "signed_owner_reopen_required_after_restart": True,
        "heartbeat_implemented": True,
        "max_heartbeat_age_seconds": MAX_HEARTBEAT_AGE_SECONDS,
        "health_is_read_only": True,
        "health_transport": "OWNER_ONLY_WINDOWS_NAMED_PIPE",
        "tcp_listener_enabled": False,
        "http_listener_enabled": False,
        "remote_control_enabled": False,
        "lan_control_enabled": False,
        "anonymous_ipc_access_allowed": False,
        "command_dispatch_over_health_ipc_allowed": False,
        "repository_mutation_dispatch_over_health_ipc_allowed": False,
        "credential_exchange_over_health_ipc_allowed": False,
        "windows_service_installed": False,
        "scheduled_task_installed": False,
        "process_spawned_by_this_module": False,
        "real_windows_acl_modified_by_this_module": False,
        "crash_recovery_is_automatic_retry": False,
        "automatic_restart_authorized": False,
        "automatic_retry_allowed": False,
        "repository_mutation_replay_allowed": False,
        "consumed_authorization_auto_released": False,
        "owner_private_key_loaded": False,
        "real_github_credentials_loaded": False,
        "github_api_called": False,
        "network_called": False,
        "live_repository_mutation_authorized": False,
        "live_repository_mutation_performed": False,
        "production_repository_mutation_performed": False,
        "deploy_executed": False,
        "worker_activated": False,
        "provider_activated": False,
        "production_persistence_activated": False,
    }


__all__ = [
    "SCHEMA",
    "BLUEPRINT_SCHEMA",
    "LOCK_SCHEMA",
    "STARTUP_SCHEMA",
    "HEALTH_SCHEMA",
    "RECOVERY_SCHEMA",
    "IPC_SCHEMA",
    "POLICY_SCHEMA",
    "SERVICE_MODE",
    "SERVICE_ID",
    "HEALTH_PIPE_NAME",
    "MAX_HEARTBEAT_AGE_SECONDS",
    "build_windows_service_installation_blueprint",
    "local_health_ipc_contract",
    "WindowsServiceRuntimeStore",
    "AtomicProcessLock",
    "WindowsLocalServiceController",
    "windows_local_service_policy",
]
