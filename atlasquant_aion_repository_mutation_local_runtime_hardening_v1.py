"""AION Local Repository Mutation Runtime Hardening + Owner Key Enrollment V1.

Executable local/offline hardening stacked on the synthetic runtime V1.

This module hardens local runtime concerns that are required before any future
Windows installation:
- deterministic per-user Windows runtime layout;
- owner-only ACL attestation contract;
- single active HUMAN_OWNER public-key enrollment in the same SQLite truth;
- signed, nonce-protected, atomic kill-switch control;
- SQLite integrity/readback report;
- restart/crash recovery scan with no automatic retry;
- concurrency/CAS invariants inherited from the local mutation store.

It does not install a Windows service, modify real Windows ACLs, generate/store
the owner private key, bind GitHub credentials, call GitHub, open network
transport, or perform a live repository mutation.
"""
from __future__ import annotations

import base64
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import PureWindowsPath
import re
import sqlite3
from typing import Any, Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from atlasquant_aion_repository_mutation_offline_runtime_v1 import (
    PROVIDER_IDENTITY,
    LocalRepositoryMutationStore,
    OfflineRuntimeError,
    owner_public_key_fingerprint,
)


SCHEMA = "ATLASQUANT_AION_REPOSITORY_MUTATION_LOCAL_RUNTIME_HARDENING_V1"
WINDOWS_LAYOUT_SCHEMA = "ATLASQUANT_AION_WINDOWS_LOCAL_RUNTIME_LAYOUT_V1"
WINDOWS_ACL_SCHEMA = "ATLASQUANT_AION_WINDOWS_LOCAL_RUNTIME_ACL_ATTESTATION_V1"
OWNER_KEY_SCHEMA = "ATLASQUANT_AION_LOCAL_OWNER_PUBLIC_KEY_ENROLLMENT_V1"
KILL_SWITCH_CHALLENGE_SCHEMA = "ATLASQUANT_AION_LOCAL_KILL_SWITCH_CONTROL_CHALLENGE_V1"
KILL_SWITCH_APPLY_SCHEMA = "ATLASQUANT_AION_LOCAL_KILL_SWITCH_CONTROL_APPLY_V1"
INTEGRITY_SCHEMA = "ATLASQUANT_AION_LOCAL_RUNTIME_INTEGRITY_REPORT_V1"
RECOVERY_SCHEMA = "ATLASQUANT_AION_LOCAL_RUNTIME_RESTART_RECOVERY_SCAN_V1"
POLICY_SCHEMA = "ATLASQUANT_AION_LOCAL_RUNTIME_HARDENING_POLICY_V1"

HARDENING_SCHEMA_VERSION = 1
WINDOWS_RUNTIME_SUBDIR = ("AtlasQuant", "AION", "RepositoryMutationRuntime")
WINDOWS_DB_FILENAME = "repository_mutation_runtime.sqlite3"
WINDOWS_BACKUP_DIRNAME = "backups"
WINDOWS_LOCK_FILENAME = "runtime.lock"
WINDOWS_SERVICE_MODE = "CURRENT_USER_ONLY"
OWNER_KEY_STATUS = "ACTIVE"
KILL_SWITCH_CONTEXT = b"ATLASQUANT:AION:LOCAL_RUNTIME:KILL_SWITCH_CONTROL:"
MAX_KILL_SWITCH_AUTH_WINDOW_SECONDS = 120
RECOVERY_STATES = (
    "UNCONSUMED_AUTHORIZATION_ACTIVE",
    "UNCONSUMED_AUTHORIZATION_EXPIRED",
    "CONSUMED_WITHOUT_ATTEMPT_EVIDENCE",
    "OUTCOME_UNKNOWN_RECONCILIATION_REQUIRED",
    "OPEN_AMBIGUOUS_CERTIFIED_RECONCILIATION_REQUIRED",
    "RECONCILED_AUDIT_PENDING",
    "TERMINAL_AUDIT_PENDING",
    "CLOSED",
)
_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_DRIVE_RE = re.compile(r"^[A-Za-z]:\\")
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


def _b64decode(value: Any, code: str) -> bytes:
    text = _clean(value, 8192)
    if not text:
        raise OfflineRuntimeError(code)
    try:
        return base64.b64decode(text, validate=True)
    except Exception as exc:
        raise OfflineRuntimeError(code) from exc


def resolve_windows_runtime_layout(
    *,
    local_app_data: Any,
    owner_subject: Any,
) -> dict[str, Any]:
    """Resolve a per-user Windows runtime layout without touching the filesystem."""
    root_raw = str(local_app_data or "").strip()
    owner = _identity(owner_subject, 240)
    blockers: list[str] = []

    if not owner:
        blockers.append("OWNER_SUBJECT_REQUIRED")
    if not root_raw:
        blockers.append("LOCALAPPDATA_REQUIRED")
    if root_raw.startswith("\\"):
        blockers.append("UNC_RUNTIME_ROOT_FORBIDDEN")
    if root_raw and not _DRIVE_RE.match(root_raw):
        blockers.append("WINDOWS_DRIVE_ABSOLUTE_PATH_REQUIRED")

    path = PureWindowsPath(root_raw) if root_raw else PureWindowsPath("C:\\INVALID")
    if ".." in path.parts:
        blockers.append("PATH_TRAVERSAL_FORBIDDEN")

    runtime_root = path.joinpath(*WINDOWS_RUNTIME_SUBDIR)
    db_path = runtime_root / WINDOWS_DB_FILENAME
    backup_dir = runtime_root / WINDOWS_BACKUP_DIRNAME
    lock_path = runtime_root / WINDOWS_LOCK_FILENAME

    material = {
        "owner_subject": owner,
        "local_app_data_root": str(path),
        "runtime_root": str(runtime_root),
        "db_path": str(db_path),
        "backup_dir": str(backup_dir),
        "lock_path": str(lock_path),
        "service_mode": WINDOWS_SERVICE_MODE,
    }
    return {
        "schema": WINDOWS_LAYOUT_SCHEMA,
        "state": "WINDOWS_RUNTIME_LAYOUT_READY" if not blockers else "BLOCKED",
        "blockers": blockers,
        **material,
        "layout_digest": _digest(material) if not blockers else "",
        "per_user_location": True,
        "program_data_used": False,
        "system_account_required": False,
        "network_share_allowed": False,
        "filesystem_modified": False,
        "windows_service_installed": False,
    }


def build_windows_owner_acl_attestation(
    layout: Mapping[str, Any] | None,
    *,
    owner_sid_digest: Any,
    acl_evidence_digest: Any,
    current_user_owner_match: bool,
    owner_full_control_verified: bool,
    inheritance_disabled_verified: bool,
    broad_write_aces_absent: bool,
    service_account_is_current_user: bool,
) -> dict[str, Any]:
    """Validate externally observed Windows ACL facts.

    CI cannot modify/inspect a real Windows owner's ACL. This function binds the
    evidence that a future Windows installer must collect.
    """
    row = dict(layout or {})
    blockers: list[str] = []

    if row.get("schema") != WINDOWS_LAYOUT_SCHEMA:
        blockers.append("WINDOWS_LAYOUT_SCHEMA_MISMATCH")
    if row.get("state") != "WINDOWS_RUNTIME_LAYOUT_READY":
        blockers.append("READY_WINDOWS_LAYOUT_REQUIRED")

    owner_sid = _sha256(owner_sid_digest)
    acl_digest = _sha256(acl_evidence_digest)
    if not owner_sid:
        blockers.append("OWNER_SID_DIGEST_REQUIRED")
    if not acl_digest:
        blockers.append("ACL_EVIDENCE_DIGEST_REQUIRED")
    for label, flag in (
        ("CURRENT_USER_OWNER_MATCH_REQUIRED", current_user_owner_match),
        ("OWNER_FULL_CONTROL_REQUIRED", owner_full_control_verified),
        ("ACL_INHERITANCE_MUST_BE_DISABLED", inheritance_disabled_verified),
        ("BROAD_WRITE_ACES_MUST_BE_ABSENT", broad_write_aces_absent),
        ("SERVICE_ACCOUNT_MUST_BE_CURRENT_USER", service_account_is_current_user),
    ):
        if flag is not True:
            blockers.append(label)

    material = {
        "layout_digest": _sha256(row.get("layout_digest")),
        "owner_sid_digest": owner_sid,
        "acl_evidence_digest": acl_digest,
        "current_user_owner_match": current_user_owner_match is True,
        "owner_full_control_verified": owner_full_control_verified is True,
        "inheritance_disabled_verified": inheritance_disabled_verified is True,
        "broad_write_aces_absent": broad_write_aces_absent is True,
        "service_account_is_current_user": service_account_is_current_user is True,
    }
    return {
        "schema": WINDOWS_ACL_SCHEMA,
        "state": "WINDOWS_OWNER_ACL_ATTESTED" if not blockers else "BLOCKED",
        "blockers": blockers,
        **material,
        "acl_attestation_digest": _digest(material) if not blockers else "",
        "acl_modified_by_this_module": False,
        "filesystem_modified": False,
        "windows_service_installed": False,
    }


class HardenedLocalRepositoryMutationStore(LocalRepositoryMutationStore):
    """Extends the same SQLite runtime truth with hardening metadata."""

    def __init__(self, db_path: str | os.PathLike[str]):
        super().__init__(db_path)
        self._initialize_hardening()

    def _initialize_hardening(self) -> None:
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS runtime_hardening_meta (
                        key TEXT PRIMARY KEY,
                        value TEXT NOT NULL
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS owner_key_enrollment (
                        singleton INTEGER PRIMARY KEY CHECK(singleton = 1),
                        owner_subject TEXT NOT NULL,
                        owner_binding_digest TEXT NOT NULL,
                        device_binding_digest TEXT NOT NULL,
                        public_key_b64 TEXT NOT NULL,
                        public_key_fingerprint TEXT NOT NULL,
                        enrollment_nonce_digest TEXT NOT NULL UNIQUE,
                        enrolled_at TEXT NOT NULL,
                        physical_owner_presence_verified INTEGER NOT NULL
                            CHECK(physical_owner_presence_verified IN (0,1)),
                        owner_only_acl_verified INTEGER NOT NULL
                            CHECK(owner_only_acl_verified IN (0,1)),
                        status TEXT NOT NULL
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS kill_switch_control_audit (
                        action_id TEXT PRIMARY KEY,
                        challenge_digest TEXT NOT NULL UNIQUE,
                        nonce_digest TEXT NOT NULL UNIQUE,
                        owner_key_fingerprint TEXT NOT NULL,
                        previous_state_digest TEXT NOT NULL,
                        desired_enabled INTEGER NOT NULL CHECK(desired_enabled IN (0,1)),
                        reason_digest TEXT NOT NULL,
                        signature_digest TEXT NOT NULL,
                        issued_at TEXT NOT NULL,
                        expires_at TEXT NOT NULL,
                        applied_at TEXT NOT NULL
                    )
                    """
                )
                conn.execute(
                    """
                    INSERT INTO runtime_hardening_meta(key, value)
                    VALUES ('schema_version', ?)
                    ON CONFLICT(key) DO UPDATE SET value=excluded.value
                    """,
                    (str(HARDENING_SCHEMA_VERSION),),
                )
                conn.execute("COMMIT")
            except Exception:
                if conn.in_transaction:
                    conn.execute("ROLLBACK")
                raise

    def hardening_schema_version(self) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT value FROM runtime_hardening_meta WHERE key='schema_version'"
            ).fetchone()
        if row is None:
            raise OfflineRuntimeError("HARDENING_SCHEMA_VERSION_MISSING")
        return int(row["value"])

    def enroll_owner_public_key_once(
        self,
        *,
        owner_subject: Any,
        owner_binding_digest: Any,
        device_binding_digest: Any,
        public_key_b64: Any,
        enrollment_nonce_digest: Any,
        enrolled_at: Any,
        physical_owner_presence_verified: bool,
        owner_only_acl_verified: bool,
    ) -> dict[str, Any]:
        owner = _identity(owner_subject, 240)
        owner_binding = _sha256(owner_binding_digest)
        device_binding = _sha256(device_binding_digest)
        nonce = _sha256(enrollment_nonce_digest)
        at = _iso(enrolled_at, "OWNER_KEY_ENROLLED_AT")
        if not owner:
            raise OfflineRuntimeError("OWNER_SUBJECT_REQUIRED")
        if not owner_binding:
            raise OfflineRuntimeError("OWNER_BINDING_DIGEST_REQUIRED")
        if not device_binding:
            raise OfflineRuntimeError("DEVICE_BINDING_DIGEST_REQUIRED")
        if not nonce:
            raise OfflineRuntimeError("ENROLLMENT_NONCE_DIGEST_REQUIRED")
        if physical_owner_presence_verified is not True:
            raise OfflineRuntimeError("PHYSICAL_OWNER_PRESENCE_REQUIRED")
        if owner_only_acl_verified is not True:
            raise OfflineRuntimeError("OWNER_ONLY_ACL_VERIFICATION_REQUIRED")

        raw = _b64decode(public_key_b64, "OWNER_PUBLIC_KEY_INVALID")
        if len(raw) != 32:
            raise OfflineRuntimeError("OWNER_PUBLIC_KEY_LENGTH_INVALID")
        canonical_key = base64.b64encode(raw).decode("ascii")
        fingerprint = owner_public_key_fingerprint(canonical_key)

        expected = {
            "owner_subject": owner,
            "owner_binding_digest": owner_binding,
            "device_binding_digest": device_binding,
            "public_key_b64": canonical_key,
            "public_key_fingerprint": fingerprint,
            "enrollment_nonce_digest": nonce,
            "enrolled_at": at,
            "physical_owner_presence_verified": 1,
            "owner_only_acl_verified": 1,
            "status": OWNER_KEY_STATUS,
        }
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                existing = conn.execute(
                    "SELECT * FROM owner_key_enrollment WHERE singleton=1"
                ).fetchone()
                if existing is not None:
                    item = dict(existing)
                    comparable = tuple(expected.keys())
                    if any(item[key] != expected[key] for key in comparable):
                        raise OfflineRuntimeError("OWNER_KEY_ALREADY_ENROLLED_CONFLICT")
                    conn.execute("COMMIT")
                    material = {
                        key: item[key]
                        for key in (
                            "owner_subject",
                            "owner_binding_digest",
                            "device_binding_digest",
                            "public_key_fingerprint",
                            "enrollment_nonce_digest",
                            "enrolled_at",
                            "physical_owner_presence_verified",
                            "owner_only_acl_verified",
                            "status",
                        )
                    }
                    return {
                        "schema": OWNER_KEY_SCHEMA,
                        "state": "OWNER_PUBLIC_KEY_ENROLLED",
                        **item,
                        "enrollment_digest": _digest(material),
                        "replay": True,
                        "private_key_material_present": False,
                    }

                conn.execute(
                    """
                    INSERT INTO owner_key_enrollment(
                        singleton, owner_subject, owner_binding_digest,
                        device_binding_digest, public_key_b64,
                        public_key_fingerprint, enrollment_nonce_digest,
                        enrolled_at, physical_owner_presence_verified,
                        owner_only_acl_verified, status
                    ) VALUES (1, ?, ?, ?, ?, ?, ?, ?, 1, 1, ?)
                    """,
                    (
                        expected["owner_subject"],
                        expected["owner_binding_digest"],
                        expected["device_binding_digest"],
                        expected["public_key_b64"],
                        expected["public_key_fingerprint"],
                        expected["enrollment_nonce_digest"],
                        expected["enrolled_at"],
                        expected["status"],
                    ),
                )
                conn.execute("COMMIT")
            except Exception:
                if conn.in_transaction:
                    conn.execute("ROLLBACK")
                raise
        material = {
            key: expected[key]
            for key in (
                "owner_subject",
                "owner_binding_digest",
                "device_binding_digest",
                "public_key_fingerprint",
                "enrollment_nonce_digest",
                "enrolled_at",
                "physical_owner_presence_verified",
                "owner_only_acl_verified",
                "status",
            )
        }
        return {
            "schema": OWNER_KEY_SCHEMA,
            "state": "OWNER_PUBLIC_KEY_ENROLLED",
            **expected,
            "enrollment_digest": _digest(material),
            "replay": False,
            "private_key_material_present": False,
        }

    def get_active_owner_key(self) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM owner_key_enrollment WHERE singleton=1"
            ).fetchone()
        if row is None:
            raise OfflineRuntimeError("OWNER_KEY_NOT_ENROLLED")
        item = dict(row)
        if item["status"] != OWNER_KEY_STATUS:
            raise OfflineRuntimeError("OWNER_KEY_NOT_ACTIVE")
        item["private_key_material_present"] = False
        return item

    def integrity_report(self) -> dict[str, Any]:
        with self._connect() as conn:
            integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
            foreign = conn.execute("PRAGMA foreign_key_check").fetchall()
            journal = conn.execute("PRAGMA journal_mode").fetchone()[0]
            sync = conn.execute("PRAGMA synchronous").fetchone()[0]
        owner_enrolled = True
        try:
            owner = self.get_active_owner_key()
            fingerprint = owner["public_key_fingerprint"]
        except OfflineRuntimeError as exc:
            if exc.code != "OWNER_KEY_NOT_ENROLLED":
                raise
            owner_enrolled = False
            fingerprint = ""
        ok = (
            str(integrity).lower() == "ok"
            and not foreign
            and str(journal).lower() == "wal"
            and int(sync) >= 2
            and self.schema_version() >= 1
            and self.hardening_schema_version() == HARDENING_SCHEMA_VERSION
        )
        material = {
            "sqlite_integrity": str(integrity),
            "foreign_key_violations": len(foreign),
            "journal_mode": str(journal).lower(),
            "synchronous_level": int(sync),
            "runtime_schema_version": self.schema_version(),
            "hardening_schema_version": self.hardening_schema_version(),
            "owner_key_enrolled": owner_enrolled,
            "owner_key_fingerprint": fingerprint,
            "counts": self.counts(),
            "kill_switch": self.kill_switch_status(),
        }
        return {
            "schema": INTEGRITY_SCHEMA,
            "state": "LOCAL_RUNTIME_INTEGRITY_OK" if ok else "BLOCKED",
            "integrity_ok": ok,
            **material,
            "integrity_report_digest": _digest(material),
            "database_repaired": False,
            "data_mutated_by_report": False,
            "github_api_called": False,
            "network_called": False,
        }

    def recovery_scan(self, *, now: Any) -> dict[str, Any]:
        """Read-only crash/restart scan. Never releases consumed authorization."""
        current = _aware(now, "RECOVERY_NOW")
        findings: list[dict[str, Any]] = []

        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    a.receipt_digest,
                    a.pr_number,
                    a.requested_mutation,
                    a.expires_at,
                    a.consumed_at,
                    a.consumption_digest,
                    t.attempt_id,
                    t.primary_outcome,
                    r.reconciled_outcome,
                    x.terminal_outcome
                FROM authorizations a
                LEFT JOIN attempts t ON t.receipt_digest = a.receipt_digest
                LEFT JOIN reconciliations r ON r.attempt_id = t.attempt_id
                LEFT JOIN terminal_audits x ON x.attempt_id = t.attempt_id
                ORDER BY a.persisted_at, a.receipt_digest
                """
            ).fetchall()

        for raw in rows:
            row = dict(raw)
            if not row["consumed_at"]:
                state = (
                    "UNCONSUMED_AUTHORIZATION_EXPIRED"
                    if current > _aware(row["expires_at"], "AUTHORIZATION_EXPIRES_AT")
                    else "UNCONSUMED_AUTHORIZATION_ACTIVE"
                )
            elif not row["attempt_id"]:
                state = "CONSUMED_WITHOUT_ATTEMPT_EVIDENCE"
            elif row["terminal_outcome"]:
                if (
                    row["terminal_outcome"] == "CERTIFIED_OPEN_AMBIGUOUS"
                    and row["primary_outcome"] == "OUTCOME_UNKNOWN"
                    and not row["reconciled_outcome"]
                ):
                    state = "OPEN_AMBIGUOUS_CERTIFIED_RECONCILIATION_REQUIRED"
                else:
                    state = "CLOSED"
            elif row["primary_outcome"] == "OUTCOME_UNKNOWN":
                state = (
                    "RECONCILED_AUDIT_PENDING"
                    if row["reconciled_outcome"]
                    else "OUTCOME_UNKNOWN_RECONCILIATION_REQUIRED"
                )
            else:
                state = "TERMINAL_AUDIT_PENDING"

            findings.append(
                {
                    "receipt_digest": row["receipt_digest"],
                    "attempt_id": row["attempt_id"] or "",
                    "pr_number": row["pr_number"],
                    "requested_mutation": row["requested_mutation"],
                    "recovery_state": state,
                    "automatic_retry_allowed": False,
                    "authorization_release_allowed": False,
                    "repository_mutation_replay_allowed": False,
                }
            )

        manual_states = {
            "CONSUMED_WITHOUT_ATTEMPT_EVIDENCE",
            "OUTCOME_UNKNOWN_RECONCILIATION_REQUIRED",
            "OPEN_AMBIGUOUS_CERTIFIED_RECONCILIATION_REQUIRED",
        }
        material = {
            "observed_at": current.isoformat(),
            "findings": findings,
        }
        return {
            "schema": RECOVERY_SCHEMA,
            "state": "LOCAL_RUNTIME_RECOVERY_SCAN_COMPLETE",
            "findings": findings,
            "finding_count": len(findings),
            "manual_attention_required": any(
                item["recovery_state"] in manual_states for item in findings
            ),
            "recovery_scan_digest": _digest(material),
            "automatic_retry_allowed": False,
            "consumed_authorization_released": False,
            "repository_mutation_replayed": False,
            "database_mutated_by_scan": False,
            "github_api_called": False,
            "network_called": False,
        }


def build_kill_switch_control_challenge(
    store: HardenedLocalRepositoryMutationStore,
    *,
    action_id: Any,
    desired_enabled: bool,
    reason: Any,
    nonce_digest: Any,
    issued_at: Any,
    expires_at: Any,
) -> dict[str, Any]:
    """Build an exact challenge against current kill-switch state."""
    action = _identity(action_id, 180)
    reason_text = _clean(reason, 300)
    nonce = _sha256(nonce_digest)
    if not action:
        raise OfflineRuntimeError("KILL_SWITCH_ACTION_ID_REQUIRED")
    if type(desired_enabled) is not bool:
        raise OfflineRuntimeError("KILL_SWITCH_DESIRED_STATE_BOOLEAN_REQUIRED")
    if not reason_text:
        raise OfflineRuntimeError("KILL_SWITCH_REASON_REQUIRED")
    if not nonce:
        raise OfflineRuntimeError("KILL_SWITCH_NONCE_DIGEST_REQUIRED")

    issued = _aware(issued_at, "KILL_SWITCH_ISSUED_AT")
    expires = _aware(expires_at, "KILL_SWITCH_EXPIRES_AT")
    if expires <= issued:
        raise OfflineRuntimeError("KILL_SWITCH_AUTH_EXPIRY_INVALID")
    if (expires - issued).total_seconds() > MAX_KILL_SWITCH_AUTH_WINDOW_SECONDS:
        raise OfflineRuntimeError("KILL_SWITCH_AUTH_WINDOW_TOO_LONG")

    owner = store.get_active_owner_key()
    current = store.kill_switch_status()
    current_state_digest = _digest(current)
    material = {
        "action_id": action,
        "provider_identity": PROVIDER_IDENTITY,
        "desired_enabled": desired_enabled,
        "reason_digest": _digest({"reason": reason_text}),
        "nonce_digest": nonce,
        "owner_subject": owner["owner_subject"],
        "owner_key_fingerprint": owner["public_key_fingerprint"],
        "current_state_digest": current_state_digest,
        "issued_at": issued.isoformat(),
        "expires_at": expires.isoformat(),
    }
    challenge_digest = _digest(material)
    return {
        "schema": KILL_SWITCH_CHALLENGE_SCHEMA,
        "state": "KILL_SWITCH_CONTROL_CHALLENGE_READY",
        **material,
        "challenge_digest": challenge_digest,
        "reason": reason_text,
        "signature_message_b64": base64.b64encode(
            KILL_SWITCH_CONTEXT + challenge_digest.encode("ascii")
        ).decode("ascii"),
        "private_key_required_inside_runtime": False,
        "kill_switch_changed": False,
        "github_api_called": False,
        "network_called": False,
    }


def verify_and_apply_signed_kill_switch_change(
    store: HardenedLocalRepositoryMutationStore,
    challenge: Mapping[str, Any] | None,
    *,
    signature_b64: Any,
    now: Any,
) -> dict[str, Any]:
    """Atomically verify signature+nonce+state and apply local kill-switch change."""
    row = dict(challenge or {})
    if row.get("schema") != KILL_SWITCH_CHALLENGE_SCHEMA:
        raise OfflineRuntimeError("KILL_SWITCH_CHALLENGE_SCHEMA_MISMATCH")
    if row.get("state") != "KILL_SWITCH_CONTROL_CHALLENGE_READY":
        raise OfflineRuntimeError("READY_KILL_SWITCH_CHALLENGE_REQUIRED")

    current = _aware(now, "KILL_SWITCH_APPLY_NOW")
    issued = _aware(row.get("issued_at"), "KILL_SWITCH_ISSUED_AT")
    expires = _aware(row.get("expires_at"), "KILL_SWITCH_EXPIRES_AT")
    if current < issued:
        raise OfflineRuntimeError("KILL_SWITCH_CHALLENGE_FROM_FUTURE")
    if current > expires:
        raise OfflineRuntimeError("KILL_SWITCH_CHALLENGE_EXPIRED")

    owner = store.get_active_owner_key()
    if owner["public_key_fingerprint"] != row.get("owner_key_fingerprint"):
        raise OfflineRuntimeError("KILL_SWITCH_OWNER_KEY_FINGERPRINT_MISMATCH")

    raw_key = _b64decode(owner["public_key_b64"], "OWNER_PUBLIC_KEY_INVALID")
    raw_sig = _b64decode(signature_b64, "KILL_SWITCH_SIGNATURE_INVALID")
    if len(raw_key) != 32 or len(raw_sig) != 64:
        raise OfflineRuntimeError("KILL_SWITCH_SIGNATURE_MATERIAL_INVALID")
    try:
        Ed25519PublicKey.from_public_bytes(raw_key).verify(
            raw_sig,
            KILL_SWITCH_CONTEXT
            + _sha256(row.get("challenge_digest")).encode("ascii"),
        )
    except InvalidSignature as exc:
        raise OfflineRuntimeError("KILL_SWITCH_SIGNATURE_NOT_VERIFIED") from exc

    action = _identity(row.get("action_id"), 180)
    nonce = _sha256(row.get("nonce_digest"))
    challenge_digest = _sha256(row.get("challenge_digest"))
    reason_digest = _sha256(row.get("reason_digest"))
    if not all((action, nonce, challenge_digest, reason_digest)):
        raise OfflineRuntimeError("KILL_SWITCH_CHALLENGE_BINDING_INVALID")

    signature_digest = "sha256:" + hashlib.sha256(raw_sig).hexdigest()
    desired_enabled = row.get("desired_enabled")
    if type(desired_enabled) is not bool:
        raise OfflineRuntimeError("KILL_SWITCH_DESIRED_STATE_BOOLEAN_REQUIRED")
    reason_text = _clean(row.get("reason"), 300)

    with store._connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        try:
            active = conn.execute(
                "SELECT enabled, reason, updated_at FROM kill_switch WHERE singleton=1"
            ).fetchone()
            if active is None:
                raise OfflineRuntimeError("KILL_SWITCH_STATE_MISSING")
            active_dict = {
                "enabled": bool(active["enabled"]),
                "reason": active["reason"],
                "updated_at": active["updated_at"],
            }
            if _digest(active_dict) != row.get("current_state_digest"):
                raise OfflineRuntimeError("KILL_SWITCH_STATE_CHANGED_AFTER_CHALLENGE")

            nonce_seen = conn.execute(
                "SELECT 1 FROM nonce_registry WHERE scope=? AND nonce_digest=?",
                ("kill-switch-control", nonce),
            ).fetchone()
            if nonce_seen is not None:
                raise OfflineRuntimeError("KILL_SWITCH_NONCE_REPLAY_REJECTED")

            prior = conn.execute(
                "SELECT * FROM kill_switch_control_audit WHERE action_id=?",
                (action,),
            ).fetchone()
            if prior is not None:
                raise OfflineRuntimeError("KILL_SWITCH_ACTION_REPLAY_REJECTED")

            conn.execute(
                """
                INSERT INTO nonce_registry(scope, nonce_digest, reserved_at, expires_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    "kill-switch-control",
                    nonce,
                    current.isoformat(),
                    expires.isoformat(),
                ),
            )
            conn.execute(
                """
                UPDATE kill_switch
                SET enabled=?, reason=?, updated_at=?
                WHERE singleton=1
                """,
                (
                    1 if desired_enabled else 0,
                    reason_text,
                    current.isoformat(),
                ),
            )
            conn.execute(
                """
                INSERT INTO kill_switch_control_audit(
                    action_id, challenge_digest, nonce_digest,
                    owner_key_fingerprint, previous_state_digest,
                    desired_enabled, reason_digest, signature_digest,
                    issued_at, expires_at, applied_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    action,
                    challenge_digest,
                    nonce,
                    owner["public_key_fingerprint"],
                    row["current_state_digest"],
                    1 if desired_enabled else 0,
                    reason_digest,
                    signature_digest,
                    issued.isoformat(),
                    expires.isoformat(),
                    current.isoformat(),
                ),
            )
            conn.execute("COMMIT")
        except Exception:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise

    status = store.kill_switch_status()
    material = {
        "action_id": action,
        "challenge_digest": challenge_digest,
        "nonce_digest": nonce,
        "owner_key_fingerprint": owner["public_key_fingerprint"],
        "signature_digest": signature_digest,
        "desired_enabled": desired_enabled,
        "applied_at": current.isoformat(),
        "resulting_state_digest": _digest(status),
    }
    return {
        "schema": KILL_SWITCH_APPLY_SCHEMA,
        "state": "SIGNED_KILL_SWITCH_CHANGE_APPLIED",
        **material,
        "kill_switch_status": status,
        "control_receipt_digest": _digest(material),
        "owner_signature_verified": True,
        "nonce_consumed": True,
        "state_compare_and_set_verified": True,
        "private_key_loaded": False,
        "github_api_called": False,
        "network_called": False,
        "live_repository_mutation_authorized": False,
        "live_repository_mutation_performed": False,
    }


def local_runtime_hardening_policy() -> dict[str, Any]:
    return {
        "schema": POLICY_SCHEMA,
        "windows_service_mode": WINDOWS_SERVICE_MODE,
        "windows_runtime_is_per_user": True,
        "program_data_runtime_forbidden": True,
        "unc_runtime_root_forbidden": True,
        "owner_only_acl_required": True,
        "acl_inheritance_disabled_required": True,
        "broad_write_aces_absent_required": True,
        "current_user_service_account_required": True,
        "real_windows_acl_modified_by_this_module": False,
        "windows_service_installed": False,
        "single_sqlite_runtime_truth": True,
        "second_runtime_database_forbidden": True,
        "owner_public_key_enrollment_implemented": True,
        "single_active_owner_key_v1": True,
        "owner_key_rotation_implemented": False,
        "owner_private_key_generated": False,
        "owner_private_key_stored": False,
        "physical_owner_presence_required_for_enrollment": True,
        "owner_only_acl_attestation_required_for_enrollment": True,
        "signed_kill_switch_control_implemented": True,
        "kill_switch_change_requires_owner_signature": True,
        "kill_switch_change_requires_single_use_nonce": True,
        "kill_switch_change_binds_previous_state": True,
        "kill_switch_change_is_atomic_with_audit": True,
        "direct_raw_kill_switch_method_is_test_harness_only": True,
        "sqlite_integrity_check_implemented": True,
        "restart_recovery_scan_implemented": True,
        "restart_recovery_scan_is_read_only": True,
        "consumed_without_attempt_never_auto_released": True,
        "outcome_unknown_never_auto_retried": True,
        "automatic_retry_allowed": False,
        "repository_mutation_replay_allowed": False,
        "live_github_state_reader_implemented": False,
        "live_github_adapter_implemented": False,
        "runtime_credential_broker_implemented": False,
        "real_github_credentials_loaded": False,
        "real_github_network_path_enabled": False,
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
    "WINDOWS_LAYOUT_SCHEMA",
    "WINDOWS_ACL_SCHEMA",
    "OWNER_KEY_SCHEMA",
    "KILL_SWITCH_CHALLENGE_SCHEMA",
    "KILL_SWITCH_APPLY_SCHEMA",
    "INTEGRITY_SCHEMA",
    "RECOVERY_SCHEMA",
    "POLICY_SCHEMA",
    "HARDENING_SCHEMA_VERSION",
    "WINDOWS_RUNTIME_SUBDIR",
    "WINDOWS_DB_FILENAME",
    "WINDOWS_BACKUP_DIRNAME",
    "WINDOWS_LOCK_FILENAME",
    "WINDOWS_SERVICE_MODE",
    "OWNER_KEY_STATUS",
    "KILL_SWITCH_CONTEXT",
    "MAX_KILL_SWITCH_AUTH_WINDOW_SECONDS",
    "RECOVERY_STATES",
    "resolve_windows_runtime_layout",
    "build_windows_owner_acl_attestation",
    "HardenedLocalRepositoryMutationStore",
    "build_kill_switch_control_challenge",
    "verify_and_apply_signed_kill_switch_change",
    "local_runtime_hardening_policy",
]
