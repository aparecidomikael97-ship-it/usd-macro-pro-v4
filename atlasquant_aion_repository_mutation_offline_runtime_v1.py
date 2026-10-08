"""AION Physical Repository Mutation Runtime V1 — Offline/Local First.

This is the first executable runtime behind the non-executing repository
mutation contracts. It is deliberately restricted to a synthetic local
repository provider.

Implemented here:
- SQLite durability with synchronous=FULL + WAL;
- durable nonce/replay registry;
- durable authorization receipt persistence;
- atomic single-use authorization consumption via BEGIN IMMEDIATE/CAS;
- Ed25519 public-key verification of an external HUMAN_OWNER signature;
- fail-closed kill switch;
- synthetic local repository state;
- one-attempt mutation execution against the synthetic provider only;
- immutable attempt/outcome evidence;
- synthetic authoritative postcondition readback;
- append-only reconciliation for OUTCOME_UNKNOWN;
- append-only terminal audit persistence.

Explicitly NOT implemented:
- real HUMAN_OWNER private-key signing;
- GitHub network state reader;
- GitHub credentials/tokens;
- GitHub API endpoints or requests;
- live GitHub mutation adapter;
- production repository writes;
- deploy/Worker/provider/production-persistence activation.

This module performs real local SQLite writes and may mutate a synthetic in-memory
repository model. It never mutates GitHub or any production repository.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
from typing import Any, Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from atlasquant_aion_repository_mutation_authorization_receipt_v1 import (
    RECEIPT_SCHEMA,
    verify_repository_mutation_authorization_receipt,
)


SCHEMA = "ATLASQUANT_AION_REPOSITORY_MUTATION_OFFLINE_RUNTIME_V1"
STORE_SCHEMA = "ATLASQUANT_AION_REPOSITORY_MUTATION_LOCAL_STORE_V1"
SIGNATURE_SCHEMA = "ATLASQUANT_AION_REPOSITORY_MUTATION_LOCAL_OWNER_SIGNATURE_VERIFY_V1"
ATTEMPT_SCHEMA = "ATLASQUANT_AION_REPOSITORY_MUTATION_SYNTHETIC_ATTEMPT_V1"
RECONCILIATION_SCHEMA = "ATLASQUANT_AION_REPOSITORY_MUTATION_SYNTHETIC_RECONCILIATION_V1"
TERMINAL_AUDIT_SCHEMA = "ATLASQUANT_AION_REPOSITORY_MUTATION_LOCAL_TERMINAL_AUDIT_V1"
POLICY_SCHEMA = "ATLASQUANT_AION_REPOSITORY_MUTATION_OFFLINE_RUNTIME_POLICY_V1"

STORE_SCHEMA_VERSION = 1
PROVIDER_IDENTITY = "SYNTHETIC_LOCAL_REPOSITORY_V1"
PROVIDER_MODE = "OFFLINE_LOCAL_SYNTHETIC_ONLY"
SIGNATURE_CONTEXT = b"ATLASQUANT:AION:REPOSITORY_MUTATION:AUTH_RECEIPT:"
SUPPORTED_MUTATIONS = (
    "PR_DRAFT_TO_READY",
    "PR_RETARGET_TO_MAIN",
    "SQUASH_MERGE_TO_MAIN",
)
SYNTHETIC_BEHAVIORS = (
    "SUCCESS",
    "TERMINAL_FAILURE",
    "UNKNOWN_AFTER_APPLY",
    "UNKNOWN_NO_EFFECT",
)
PRIMARY_OUTCOMES = (
    "CONFIRMED_SUCCESS",
    "CONFIRMED_TERMINAL_FAILURE",
    "OUTCOME_UNKNOWN",
)
RECONCILED_OUTCOMES = (
    "RECONCILED_CONFIRMED_SUCCESS",
    "RECONCILED_CONFIRMED_TERMINAL_FAILURE",
)
DEFAULT_KILL_SWITCH_REASON = "BOOTSTRAP_FAIL_CLOSED"

_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{2,239}$")


class OfflineRuntimeError(ValueError):
    def __init__(self, code: str, **fields: Any):
        super().__init__(code)
        self.code = code
        self.result = {
            "schema": SCHEMA,
            "state": "BLOCKED",
            "error_code": code,
            **fields,
            "provider_identity": PROVIDER_IDENTITY,
            "github_api_called": False,
            "network_called": False,
            "live_repository_mutation_performed": False,
            "deploy_executed": False,
            "worker_activated": False,
            "production_persistence_activated": False,
        }


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


def _sha(value: Any) -> str:
    token = _clean(value, 60)
    return token if _SHA_RE.fullmatch(token) else ""


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


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def _b64decode(value: Any, code: str) -> bytes:
    text = _clean(value, 4096)
    if not text:
        raise OfflineRuntimeError(code)
    try:
        return base64.b64decode(text, validate=True)
    except Exception as exc:
        raise OfflineRuntimeError(code) from exc


def _receipt_message(receipt_digest: str) -> bytes:
    digest = _sha256(receipt_digest)
    if not digest:
        raise OfflineRuntimeError("AUTHORIZATION_RECEIPT_DIGEST_REQUIRED")
    return SIGNATURE_CONTEXT + digest.encode("ascii")


def owner_public_key_fingerprint(public_key_b64: Any) -> str:
    raw = _b64decode(public_key_b64, "OWNER_PUBLIC_KEY_INVALID")
    if len(raw) != 32:
        raise OfflineRuntimeError("OWNER_PUBLIC_KEY_LENGTH_INVALID")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def verify_external_owner_ed25519_signature(
    *,
    authorization_receipt: Mapping[str, Any] | None,
    owner_public_key_b64: Any,
    signature_b64: Any,
    expected_owner_key_fingerprint: Any = "",
) -> dict[str, Any]:
    """Verify an externally produced Ed25519 signature.

    This function has no private-key capability. It cannot sign for the owner.
    """
    receipt = dict(authorization_receipt or {})
    blockers: list[str] = []

    if receipt.get("schema") != RECEIPT_SCHEMA:
        blockers.append("AUTHORIZATION_RECEIPT_SCHEMA_MISMATCH")
    digest = _sha256(receipt.get("authorization_receipt_digest"))
    if not digest:
        blockers.append("AUTHORIZATION_RECEIPT_DIGEST_REQUIRED")

    try:
        raw_key = _b64decode(owner_public_key_b64, "OWNER_PUBLIC_KEY_INVALID")
        raw_sig = _b64decode(signature_b64, "OWNER_SIGNATURE_INVALID")
        if len(raw_key) != 32:
            blockers.append("OWNER_PUBLIC_KEY_LENGTH_INVALID")
        if len(raw_sig) != 64:
            blockers.append("OWNER_SIGNATURE_LENGTH_INVALID")
        fingerprint = "sha256:" + hashlib.sha256(raw_key).hexdigest()
    except OfflineRuntimeError as exc:
        raw_key = b""
        raw_sig = b""
        fingerprint = ""
        blockers.append(exc.code)

    expected = _sha256(expected_owner_key_fingerprint)
    if expected and fingerprint and expected != fingerprint:
        blockers.append("OWNER_KEY_FINGERPRINT_MISMATCH")

    signature_valid = False
    if not blockers and digest:
        try:
            Ed25519PublicKey.from_public_bytes(raw_key).verify(
                raw_sig,
                _receipt_message(digest),
            )
            signature_valid = True
        except InvalidSignature:
            blockers.append("OWNER_SIGNATURE_NOT_VERIFIED")
        except Exception:
            blockers.append("OWNER_SIGNATURE_VERIFICATION_FAILED")

    blockers = list(dict.fromkeys(blockers))
    material = {
        "authorization_receipt_digest": digest,
        "owner_key_fingerprint": fingerprint,
        "signature_context_digest": _digest(
            {"context": SIGNATURE_CONTEXT.decode("ascii"), "receipt": digest}
        ),
        "signature_verified": signature_valid,
        "private_key_loaded": False,
        "private_key_generated": False,
        "signature_generated_by_this_module": False,
    }
    return {
        "schema": SIGNATURE_SCHEMA,
        "state": "OWNER_SIGNATURE_VERIFIED" if not blockers else "BLOCKED",
        "blockers": blockers,
        **material,
        "signature_attestation_digest": _digest(material) if not blockers else "",
        "github_api_called": False,
        "network_called": False,
        "live_repository_mutation_performed": False,
    }


@dataclass
class SyntheticPullRequest:
    number: int
    head_sha: str
    base_branch: str
    draft: bool = True
    open: bool = True
    merged: bool = False
    merge_commit_sha: str = ""


@dataclass
class SyntheticRepositoryState:
    repository_id: str
    main_sha: str
    main_tree_sha: str
    pull_requests: dict[int, SyntheticPullRequest] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not _identity(self.repository_id, 240):
            raise OfflineRuntimeError("SYNTHETIC_REPOSITORY_ID_INVALID")
        if not _sha(self.main_sha):
            raise OfflineRuntimeError("SYNTHETIC_MAIN_SHA_INVALID")
        if not _sha(self.main_tree_sha):
            raise OfflineRuntimeError("SYNTHETIC_MAIN_TREE_SHA_INVALID")

    def snapshot(self) -> dict[str, Any]:
        return {
            "repository_id": self.repository_id,
            "main_sha": self.main_sha,
            "main_tree_sha": self.main_tree_sha,
            "pull_requests": {
                str(number): {
                    "number": pr.number,
                    "head_sha": pr.head_sha,
                    "base_branch": pr.base_branch,
                    "draft": pr.draft,
                    "open": pr.open,
                    "merged": pr.merged,
                    "merge_commit_sha": pr.merge_commit_sha,
                }
                for number, pr in sorted(self.pull_requests.items())
            },
        }

    def snapshot_digest(self) -> str:
        return _digest(self.snapshot())

    def get_pr(self, number: int) -> SyntheticPullRequest:
        try:
            return self.pull_requests[int(number)]
        except Exception as exc:
            raise OfflineRuntimeError("SYNTHETIC_PR_NOT_FOUND") from exc


class LocalRepositoryMutationStore:
    """One local SQLite truth for offline mutation-runtime evidence."""

    def __init__(self, db_path: str | Path):
        self.path = Path(db_path)
        if self.path.exists() and self.path.is_symlink():
            raise OfflineRuntimeError("LOCAL_STORE_SYMLINK_REJECTED")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()
        self._tighten_permissions_best_effort()

    def _tighten_permissions_best_effort(self) -> None:
        try:
            if self.path.exists() and os.name != "nt":
                os.chmod(self.path, 0o600)
        except OSError:
            pass

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.path), timeout=10.0, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA synchronous=FULL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _initialize(self) -> None:
        with self._connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("BEGIN IMMEDIATE")
            try:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS runtime_meta (
                        key TEXT PRIMARY KEY,
                        value TEXT NOT NULL
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS kill_switch (
                        singleton INTEGER PRIMARY KEY CHECK(singleton = 1),
                        enabled INTEGER NOT NULL CHECK(enabled IN (0,1)),
                        reason TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS nonce_registry (
                        scope TEXT NOT NULL,
                        nonce_digest TEXT NOT NULL,
                        reserved_at TEXT NOT NULL,
                        expires_at TEXT NOT NULL,
                        PRIMARY KEY(scope, nonce_digest)
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS authorizations (
                        receipt_digest TEXT PRIMARY KEY,
                        receipt_payload_digest TEXT NOT NULL,
                        signature_attestation_digest TEXT NOT NULL,
                        owner_key_fingerprint TEXT NOT NULL,
                        pr_number INTEGER NOT NULL,
                        requested_mutation TEXT NOT NULL,
                        main_sha TEXT NOT NULL,
                        head_sha TEXT NOT NULL,
                        base_branch TEXT NOT NULL,
                        expires_at TEXT NOT NULL,
                        persisted_at TEXT NOT NULL,
                        consumed_at TEXT NOT NULL,
                        consumption_digest TEXT NOT NULL
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS attempts (
                        attempt_id TEXT PRIMARY KEY,
                        receipt_digest TEXT NOT NULL,
                        pr_number INTEGER NOT NULL,
                        requested_mutation TEXT NOT NULL,
                        behavior TEXT NOT NULL,
                        before_state_digest TEXT NOT NULL,
                        after_state_digest TEXT NOT NULL,
                        primary_outcome TEXT NOT NULL,
                        evidence_digest TEXT NOT NULL,
                        attempted_at TEXT NOT NULL,
                        FOREIGN KEY(receipt_digest)
                            REFERENCES authorizations(receipt_digest)
                            ON DELETE RESTRICT
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS reconciliations (
                        attempt_id TEXT PRIMARY KEY,
                        original_outcome TEXT NOT NULL,
                        reconciled_outcome TEXT NOT NULL,
                        postcondition_evidence_digest TEXT NOT NULL,
                        reconciled_at TEXT NOT NULL,
                        FOREIGN KEY(attempt_id)
                            REFERENCES attempts(attempt_id)
                            ON DELETE RESTRICT
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS terminal_audits (
                        attempt_id TEXT PRIMARY KEY,
                        terminal_outcome TEXT NOT NULL,
                        manifest_digest TEXT NOT NULL,
                        certificate_digest TEXT NOT NULL,
                        persisted_at TEXT NOT NULL,
                        FOREIGN KEY(attempt_id)
                            REFERENCES attempts(attempt_id)
                            ON DELETE RESTRICT
                    )
                    """
                )
                conn.execute(
                    """
                    INSERT INTO runtime_meta(key, value)
                    VALUES ('schema_version', ?)
                    ON CONFLICT(key) DO UPDATE SET value=excluded.value
                    """,
                    (str(STORE_SCHEMA_VERSION),),
                )
                row = conn.execute(
                    "SELECT singleton FROM kill_switch WHERE singleton=1"
                ).fetchone()
                if row is None:
                    conn.execute(
                        """
                        INSERT INTO kill_switch(singleton, enabled, reason, updated_at)
                        VALUES (1, 1, ?, ?)
                        """,
                        (DEFAULT_KILL_SWITCH_REASON, "1970-01-01T00:00:00+00:00"),
                    )
                conn.execute("COMMIT")
            except Exception:
                if conn.in_transaction:
                    conn.execute("ROLLBACK")
                raise

    def schema_version(self) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT value FROM runtime_meta WHERE key='schema_version'"
            ).fetchone()
        if row is None:
            raise OfflineRuntimeError("LOCAL_STORE_SCHEMA_MISSING")
        return int(row["value"])

    def kill_switch_status(self) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT enabled, reason, updated_at FROM kill_switch WHERE singleton=1"
            ).fetchone()
        if row is None:
            raise OfflineRuntimeError("KILL_SWITCH_STATE_MISSING")
        return {
            "enabled": bool(row["enabled"]),
            "reason": row["reason"],
            "updated_at": row["updated_at"],
        }

    def set_kill_switch(
        self,
        *,
        enabled: bool,
        reason: Any,
        updated_at: Any,
    ) -> dict[str, Any]:
        if type(enabled) is not bool:
            raise OfflineRuntimeError("KILL_SWITCH_ENABLED_BOOLEAN_REQUIRED")
        reason_text = _clean(reason, 300)
        if not reason_text:
            raise OfflineRuntimeError("KILL_SWITCH_REASON_REQUIRED")
        updated = _iso(_aware(updated_at, "KILL_SWITCH_UPDATED_AT"))
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                """
                UPDATE kill_switch
                SET enabled=?, reason=?, updated_at=?
                WHERE singleton=1
                """,
                (1 if enabled else 0, reason_text, updated),
            )
            conn.execute("COMMIT")
        return self.kill_switch_status()

    def require_kill_switch_open(self) -> None:
        status = self.kill_switch_status()
        if status["enabled"]:
            raise OfflineRuntimeError(
                "KILL_SWITCH_ENABLED",
                kill_switch_reason=status["reason"],
            )

    def reserve_nonce_once(
        self,
        *,
        scope: Any,
        nonce_digest: Any,
        reserved_at: Any,
        expires_at: Any,
    ) -> dict[str, Any]:
        scope_text = _identity(scope, 160)
        nonce = _sha256(nonce_digest)
        if not scope_text:
            raise OfflineRuntimeError("NONCE_SCOPE_REQUIRED")
        if not nonce:
            raise OfflineRuntimeError("NONCE_DIGEST_REQUIRED")
        reserved = _aware(reserved_at, "NONCE_RESERVED_AT")
        expires = _aware(expires_at, "NONCE_EXPIRES_AT")
        if expires <= reserved:
            raise OfflineRuntimeError("NONCE_EXPIRY_INVALID")
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                conn.execute(
                    """
                    INSERT INTO nonce_registry(scope, nonce_digest, reserved_at, expires_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (scope_text, nonce, _iso(reserved), _iso(expires)),
                )
                conn.execute("COMMIT")
            except sqlite3.IntegrityError as exc:
                if conn.in_transaction:
                    conn.execute("ROLLBACK")
                raise OfflineRuntimeError("NONCE_REPLAY_REJECTED") from exc
        return {
            "scope": scope_text,
            "nonce_digest": nonce,
            "reserved_at": _iso(reserved),
            "expires_at": _iso(expires),
            "replay_rejected": False,
        }

    def persist_authorization_once(
        self,
        *,
        receipt: Mapping[str, Any],
        signature_attestation: Mapping[str, Any],
        persisted_at: Any,
    ) -> dict[str, Any]:
        row = dict(receipt)
        sig = dict(signature_attestation)
        digest = _sha256(row.get("authorization_receipt_digest"))
        if row.get("schema") != RECEIPT_SCHEMA:
            raise OfflineRuntimeError("AUTHORIZATION_RECEIPT_SCHEMA_MISMATCH")
        if row.get("state") != "REPOSITORY_MUTATION_AUTHORIZATION_VERIFIED":
            raise OfflineRuntimeError("VERIFIED_AUTHORIZATION_RECEIPT_REQUIRED")
        if row.get("repository_mutation_authorized") is not True:
            raise OfflineRuntimeError("AUTHORIZATION_FLAG_REQUIRED")
        if sig.get("schema") != SIGNATURE_SCHEMA:
            raise OfflineRuntimeError("OWNER_SIGNATURE_ATTESTATION_SCHEMA_MISMATCH")
        if sig.get("state") != "OWNER_SIGNATURE_VERIFIED":
            raise OfflineRuntimeError("OWNER_SIGNATURE_VERIFICATION_REQUIRED")
        if _sha256(sig.get("authorization_receipt_digest")) != digest:
            raise OfflineRuntimeError("SIGNATURE_RECEIPT_BINDING_MISMATCH")
        if not digest:
            raise OfflineRuntimeError("AUTHORIZATION_RECEIPT_DIGEST_REQUIRED")

        persisted = _iso(_aware(persisted_at, "AUTHORIZATION_PERSISTED_AT"))
        payload_digest = _digest(
            {
                "receipt_digest": digest,
                "pr_number": row.get("pr_number"),
                "requested_mutation": row.get("requested_mutation"),
                "main_sha": row.get("main_sha"),
                "head_sha": row.get("head_sha"),
                "base_branch": row.get("base_branch"),
                "expires_at": row.get("expires_at"),
            }
        )
        expected = {
            "receipt_digest": digest,
            "receipt_payload_digest": payload_digest,
            "signature_attestation_digest": _sha256(
                sig.get("signature_attestation_digest")
            ),
            "owner_key_fingerprint": _sha256(sig.get("owner_key_fingerprint")),
            "pr_number": int(row.get("pr_number")),
            "requested_mutation": _clean(row.get("requested_mutation"), 100),
            "main_sha": _sha(row.get("main_sha")),
            "head_sha": _sha(row.get("head_sha")),
            "base_branch": _clean(row.get("base_branch"), 300),
            "expires_at": _iso(_aware(row.get("expires_at"), "AUTHORIZATION_EXPIRES_AT")),
            "persisted_at": persisted,
            "consumed_at": "",
            "consumption_digest": "",
        }
        if expected["requested_mutation"] not in SUPPORTED_MUTATIONS:
            raise OfflineRuntimeError("SUPPORTED_MUTATION_REQUIRED")
        if not expected["main_sha"] or not expected["head_sha"]:
            raise OfflineRuntimeError("AUTHORIZATION_SHA_BINDING_REQUIRED")

        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                existing = conn.execute(
                    "SELECT * FROM authorizations WHERE receipt_digest=?",
                    (digest,),
                ).fetchone()
                if existing is not None:
                    item = dict(existing)
                    immutable_keys = (
                        "receipt_digest",
                        "receipt_payload_digest",
                        "signature_attestation_digest",
                        "owner_key_fingerprint",
                        "pr_number",
                        "requested_mutation",
                        "main_sha",
                        "head_sha",
                        "base_branch",
                        "expires_at",
                    )
                    if any(item[key] != expected[key] for key in immutable_keys):
                        raise OfflineRuntimeError("AUTHORIZATION_PERSISTENCE_CONFLICT")
                    conn.execute("COMMIT")
                    item["replay"] = True
                    return item

                conn.execute(
                    """
                    INSERT INTO authorizations (
                        receipt_digest, receipt_payload_digest,
                        signature_attestation_digest, owner_key_fingerprint,
                        pr_number, requested_mutation, main_sha, head_sha,
                        base_branch, expires_at, persisted_at, consumed_at,
                        consumption_digest
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '', '')
                    """,
                    (
                        expected["receipt_digest"],
                        expected["receipt_payload_digest"],
                        expected["signature_attestation_digest"],
                        expected["owner_key_fingerprint"],
                        expected["pr_number"],
                        expected["requested_mutation"],
                        expected["main_sha"],
                        expected["head_sha"],
                        expected["base_branch"],
                        expected["expires_at"],
                        expected["persisted_at"],
                    ),
                )
                conn.execute("COMMIT")
            except Exception:
                if conn.in_transaction:
                    conn.execute("ROLLBACK")
                raise
        expected["replay"] = False
        return expected

    def get_authorization(self, receipt_digest: Any) -> dict[str, Any]:
        digest = _sha256(receipt_digest)
        if not digest:
            raise OfflineRuntimeError("AUTHORIZATION_RECEIPT_DIGEST_REQUIRED")
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM authorizations WHERE receipt_digest=?",
                (digest,),
            ).fetchone()
        if row is None:
            raise OfflineRuntimeError("AUTHORIZATION_NOT_FOUND")
        return dict(row)

    def consume_authorization_once(
        self,
        *,
        receipt_digest: Any,
        consumption_digest: Any,
        consumed_at: Any,
    ) -> dict[str, Any]:
        digest = _sha256(receipt_digest)
        consumption = _sha256(consumption_digest)
        if not digest:
            raise OfflineRuntimeError("AUTHORIZATION_RECEIPT_DIGEST_REQUIRED")
        if not consumption:
            raise OfflineRuntimeError("CONSUMPTION_DIGEST_REQUIRED")
        consumed = _aware(consumed_at, "AUTHORIZATION_CONSUMED_AT")

        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                row = conn.execute(
                    "SELECT * FROM authorizations WHERE receipt_digest=?",
                    (digest,),
                ).fetchone()
                if row is None:
                    raise OfflineRuntimeError("AUTHORIZATION_NOT_FOUND")
                item = dict(row)
                if consumed > _aware(item["expires_at"], "AUTHORIZATION_EXPIRES_AT"):
                    raise OfflineRuntimeError("AUTHORIZATION_EXPIRED")
                if item["consumed_at"]:
                    if item["consumption_digest"] == consumption:
                        raise OfflineRuntimeError("AUTHORIZATION_ALREADY_CONSUMED")
                    raise OfflineRuntimeError("AUTHORIZATION_CONSUMPTION_CONFLICT")
                cursor = conn.execute(
                    """
                    UPDATE authorizations
                    SET consumed_at=?, consumption_digest=?
                    WHERE receipt_digest=? AND consumed_at=''
                    """,
                    (_iso(consumed), consumption, digest),
                )
                if cursor.rowcount != 1:
                    raise OfflineRuntimeError("AUTHORIZATION_CAS_FAILED")
                conn.execute("COMMIT")
            except Exception:
                if conn.in_transaction:
                    conn.execute("ROLLBACK")
                raise
        return self.get_authorization(digest)

    def record_attempt_once(
        self,
        *,
        attempt_id: Any,
        receipt_digest: Any,
        pr_number: int,
        requested_mutation: Any,
        behavior: Any,
        before_state_digest: Any,
        after_state_digest: Any,
        primary_outcome: Any,
        evidence_digest: Any,
        attempted_at: Any,
    ) -> dict[str, Any]:
        attempt = _identity(attempt_id, 180)
        receipt = _sha256(receipt_digest)
        mutation = _clean(requested_mutation, 100).upper()
        behavior_name = _clean(behavior, 100).upper()
        before = _sha256(before_state_digest)
        after = _sha256(after_state_digest)
        outcome = _clean(primary_outcome, 100).upper()
        evidence = _sha256(evidence_digest)
        attempted = _iso(_aware(attempted_at, "ATTEMPTED_AT"))
        if not attempt:
            raise OfflineRuntimeError("ATTEMPT_ID_REQUIRED")
        if not receipt:
            raise OfflineRuntimeError("AUTHORIZATION_RECEIPT_DIGEST_REQUIRED")
        if mutation not in SUPPORTED_MUTATIONS:
            raise OfflineRuntimeError("SUPPORTED_MUTATION_REQUIRED")
        if behavior_name not in SYNTHETIC_BEHAVIORS:
            raise OfflineRuntimeError("SYNTHETIC_BEHAVIOR_INVALID")
        if not before or not after or not evidence:
            raise OfflineRuntimeError("ATTEMPT_EVIDENCE_DIGEST_REQUIRED")
        if outcome not in PRIMARY_OUTCOMES:
            raise OfflineRuntimeError("PRIMARY_OUTCOME_INVALID")

        expected = {
            "attempt_id": attempt,
            "receipt_digest": receipt,
            "pr_number": int(pr_number),
            "requested_mutation": mutation,
            "behavior": behavior_name,
            "before_state_digest": before,
            "after_state_digest": after,
            "primary_outcome": outcome,
            "evidence_digest": evidence,
            "attempted_at": attempted,
        }
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                existing = conn.execute(
                    "SELECT * FROM attempts WHERE attempt_id=?",
                    (attempt,),
                ).fetchone()
                if existing is not None:
                    item = dict(existing)
                    if any(item[key] != value for key, value in expected.items()):
                        raise OfflineRuntimeError("ATTEMPT_RECORD_CONFLICT")
                    conn.execute("COMMIT")
                    item["replay"] = True
                    return item
                conn.execute(
                    """
                    INSERT INTO attempts (
                        attempt_id, receipt_digest, pr_number, requested_mutation,
                        behavior, before_state_digest, after_state_digest,
                        primary_outcome, evidence_digest, attempted_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    tuple(expected[key] for key in expected),
                )
                conn.execute("COMMIT")
            except Exception:
                if conn.in_transaction:
                    conn.execute("ROLLBACK")
                raise
        expected["replay"] = False
        return expected

    def get_attempt(self, attempt_id: Any) -> dict[str, Any]:
        attempt = _identity(attempt_id, 180)
        if not attempt:
            raise OfflineRuntimeError("ATTEMPT_ID_REQUIRED")
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM attempts WHERE attempt_id=?",
                (attempt,),
            ).fetchone()
        if row is None:
            raise OfflineRuntimeError("ATTEMPT_NOT_FOUND")
        return dict(row)

    def record_reconciliation_once(
        self,
        *,
        attempt_id: Any,
        reconciled_outcome: Any,
        postcondition_evidence_digest: Any,
        reconciled_at: Any,
    ) -> dict[str, Any]:
        attempt = self.get_attempt(attempt_id)
        if attempt["primary_outcome"] != "OUTCOME_UNKNOWN":
            raise OfflineRuntimeError("RECONCILIATION_ONLY_FOR_OUTCOME_UNKNOWN")
        outcome = _clean(reconciled_outcome, 120).upper()
        if outcome not in RECONCILED_OUTCOMES:
            raise OfflineRuntimeError("RECONCILED_OUTCOME_INVALID")
        evidence = _sha256(postcondition_evidence_digest)
        if not evidence:
            raise OfflineRuntimeError("POSTCONDITION_EVIDENCE_DIGEST_REQUIRED")
        at = _iso(_aware(reconciled_at, "RECONCILED_AT"))
        expected = {
            "attempt_id": attempt["attempt_id"],
            "original_outcome": attempt["primary_outcome"],
            "reconciled_outcome": outcome,
            "postcondition_evidence_digest": evidence,
            "reconciled_at": at,
        }
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                existing = conn.execute(
                    "SELECT * FROM reconciliations WHERE attempt_id=?",
                    (attempt["attempt_id"],),
                ).fetchone()
                if existing is not None:
                    item = dict(existing)
                    if any(item[key] != value for key, value in expected.items()):
                        raise OfflineRuntimeError("RECONCILIATION_RECORD_CONFLICT")
                    conn.execute("COMMIT")
                    item["replay"] = True
                    return item
                conn.execute(
                    """
                    INSERT INTO reconciliations(
                        attempt_id, original_outcome, reconciled_outcome,
                        postcondition_evidence_digest, reconciled_at
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    tuple(expected[key] for key in expected),
                )
                conn.execute("COMMIT")
            except Exception:
                if conn.in_transaction:
                    conn.execute("ROLLBACK")
                raise
        expected["replay"] = False
        return expected

    def get_reconciliation(self, attempt_id: Any) -> dict[str, Any]:
        attempt = _identity(attempt_id, 180)
        if not attempt:
            raise OfflineRuntimeError("ATTEMPT_ID_REQUIRED")
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM reconciliations WHERE attempt_id=?",
                (attempt,),
            ).fetchone()
        if row is None:
            raise OfflineRuntimeError("RECONCILIATION_NOT_FOUND")
        return dict(row)

    def persist_terminal_audit_once(
        self,
        *,
        attempt_id: Any,
        terminal_outcome: Any,
        manifest_digest: Any,
        certificate_digest: Any,
        persisted_at: Any,
    ) -> dict[str, Any]:
        attempt = self.get_attempt(attempt_id)
        terminal = _clean(terminal_outcome, 120).upper()
        if terminal not in (
            "CERTIFIED_FINAL_SUCCESS",
            "CERTIFIED_FINAL_TERMINAL_FAILURE",
            "CERTIFIED_OPEN_AMBIGUOUS",
        ):
            raise OfflineRuntimeError("TERMINAL_AUDIT_OUTCOME_INVALID")
        manifest = _sha256(manifest_digest)
        certificate = _sha256(certificate_digest)
        if not manifest or not certificate:
            raise OfflineRuntimeError("TERMINAL_AUDIT_DIGEST_REQUIRED")
        at = _iso(_aware(persisted_at, "TERMINAL_AUDIT_PERSISTED_AT"))
        expected = {
            "attempt_id": attempt["attempt_id"],
            "terminal_outcome": terminal,
            "manifest_digest": manifest,
            "certificate_digest": certificate,
            "persisted_at": at,
        }
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                existing = conn.execute(
                    "SELECT * FROM terminal_audits WHERE attempt_id=?",
                    (attempt["attempt_id"],),
                ).fetchone()
                if existing is not None:
                    item = dict(existing)
                    if any(item[key] != value for key, value in expected.items()):
                        raise OfflineRuntimeError("TERMINAL_AUDIT_CONFLICT")
                    conn.execute("COMMIT")
                    item["replay"] = True
                    return item
                conn.execute(
                    """
                    INSERT INTO terminal_audits(
                        attempt_id, terminal_outcome, manifest_digest,
                        certificate_digest, persisted_at
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    tuple(expected[key] for key in expected),
                )
                conn.execute("COMMIT")
            except Exception:
                if conn.in_transaction:
                    conn.execute("ROLLBACK")
                raise
        expected["replay"] = False
        return expected

    def counts(self) -> dict[str, int]:
        with self._connect() as conn:
            return {
                table: int(
                    conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()["n"]
                )
                for table in (
                    "nonce_registry",
                    "authorizations",
                    "attempts",
                    "reconciliations",
                    "terminal_audits",
                )
            }


class SyntheticRepositoryMutationAdapter:
    """Offline provider that can only mutate SyntheticRepositoryState."""

    provider_identity = PROVIDER_IDENTITY

    def __init__(self, repository: SyntheticRepositoryState):
        self.repository = repository

    def _validate_bindings(
        self,
        *,
        receipt: Mapping[str, Any],
    ) -> SyntheticPullRequest:
        if _clean(receipt.get("requested_mutation"), 100).upper() not in SUPPORTED_MUTATIONS:
            raise OfflineRuntimeError("SUPPORTED_MUTATION_REQUIRED")
        if _sha(receipt.get("main_sha")) != self.repository.main_sha:
            raise OfflineRuntimeError("SYNTHETIC_MAIN_SHA_MISMATCH")
        pr = self.repository.get_pr(int(receipt.get("pr_number")))
        if _sha(receipt.get("head_sha")) != pr.head_sha:
            raise OfflineRuntimeError("SYNTHETIC_HEAD_SHA_MISMATCH")
        if _clean(receipt.get("base_branch"), 300) != pr.base_branch:
            raise OfflineRuntimeError("SYNTHETIC_BASE_BRANCH_MISMATCH")
        return pr

    def _apply(self, mutation: str, pr: SyntheticPullRequest) -> dict[str, Any]:
        if mutation == "PR_DRAFT_TO_READY":
            if not pr.open or pr.merged:
                raise OfflineRuntimeError("SYNTHETIC_PR_NOT_OPEN")
            if not pr.draft:
                raise OfflineRuntimeError("SYNTHETIC_PR_ALREADY_READY")
            pr.draft = False
            return {"postcondition": "PR_IS_READY_FOR_REVIEW"}

        if mutation == "PR_RETARGET_TO_MAIN":
            if not pr.open or pr.merged:
                raise OfflineRuntimeError("SYNTHETIC_PR_NOT_OPEN")
            if pr.draft:
                raise OfflineRuntimeError("SYNTHETIC_PR_MUST_BE_READY_BEFORE_RETARGET")
            pr.base_branch = "main"
            return {"postcondition": "PR_BASE_IS_MAIN"}

        if mutation == "SQUASH_MERGE_TO_MAIN":
            if not pr.open or pr.merged:
                raise OfflineRuntimeError("SYNTHETIC_PR_NOT_OPEN")
            if pr.draft:
                raise OfflineRuntimeError("SYNTHETIC_PR_MUST_BE_READY_BEFORE_MERGE")
            if pr.base_branch != "main":
                raise OfflineRuntimeError("SYNTHETIC_PR_BASE_MUST_BE_MAIN")
            merge_material = {
                "previous_main_sha": self.repository.main_sha,
                "previous_main_tree_sha": self.repository.main_tree_sha,
                "pr_number": pr.number,
                "head_sha": pr.head_sha,
                "operation": "SQUASH_MERGE_TO_MAIN",
            }
            merge_commit = hashlib.sha1(
                _canonical(merge_material).encode("utf-8")
            ).hexdigest()
            next_tree = hashlib.sha1(
                ("tree|" + _canonical(merge_material)).encode("utf-8")
            ).hexdigest()
            self.repository.main_sha = merge_commit
            self.repository.main_tree_sha = next_tree
            pr.merge_commit_sha = merge_commit
            pr.merged = True
            pr.open = False
            return {
                "postcondition": "PR_MERGED_AND_MERGE_COMMIT_PRESENT_IN_MAIN",
                "merge_commit_sha": merge_commit,
            }

        raise OfflineRuntimeError("SYNTHETIC_MUTATION_UNSUPPORTED")

    def attempt(
        self,
        *,
        receipt: Mapping[str, Any],
        behavior: Any,
    ) -> dict[str, Any]:
        behavior_name = _clean(behavior, 100).upper()
        if behavior_name not in SYNTHETIC_BEHAVIORS:
            raise OfflineRuntimeError("SYNTHETIC_BEHAVIOR_INVALID")
        pr = self._validate_bindings(receipt=receipt)
        mutation = _clean(receipt.get("requested_mutation"), 100).upper()
        before = self.repository.snapshot()
        before_digest = _digest(before)

        effect_applied = False
        terminal_reason = ""
        postcondition = ""
        if behavior_name in ("SUCCESS", "UNKNOWN_AFTER_APPLY"):
            result = self._apply(mutation, pr)
            effect_applied = True
            postcondition = result["postcondition"]
        elif behavior_name == "TERMINAL_FAILURE":
            terminal_reason = "SYNTHETIC_PROVIDER_TERMINAL_REJECTION"
        elif behavior_name == "UNKNOWN_NO_EFFECT":
            pass

        after = self.repository.snapshot()
        after_digest = _digest(after)

        if behavior_name == "SUCCESS":
            outcome = "CONFIRMED_SUCCESS"
        elif behavior_name == "TERMINAL_FAILURE":
            outcome = "CONFIRMED_TERMINAL_FAILURE"
        else:
            outcome = "OUTCOME_UNKNOWN"

        evidence = {
            "provider_identity": PROVIDER_IDENTITY,
            "behavior": behavior_name,
            "mutation": mutation,
            "pr_number": int(receipt.get("pr_number")),
            "before_state_digest": before_digest,
            "after_state_digest": after_digest,
            "effect_applied": effect_applied,
            "terminal_reason": terminal_reason,
            "postcondition": postcondition,
        }
        return {
            "schema": ATTEMPT_SCHEMA,
            "state": "SYNTHETIC_ATTEMPT_COMPLETE",
            **evidence,
            "primary_outcome": outcome,
            "evidence_digest": _digest(evidence),
            "synthetic_local_mutation_performed": effect_applied,
            "github_api_called": False,
            "network_called": False,
            "live_repository_mutation_performed": False,
            "automatic_retry_allowed": False,
        }

    def authoritative_readback(
        self,
        *,
        attempt: Mapping[str, Any],
    ) -> dict[str, Any]:
        pr = self.repository.get_pr(int(attempt.get("pr_number")))
        mutation = _clean(attempt.get("requested_mutation"), 100).upper()
        if mutation == "PR_DRAFT_TO_READY":
            success = pr.open and not pr.draft and not pr.merged
        elif mutation == "PR_RETARGET_TO_MAIN":
            success = pr.open and pr.base_branch == "main" and not pr.merged
        elif mutation == "SQUASH_MERGE_TO_MAIN":
            success = (
                pr.merged
                and not pr.open
                and bool(pr.merge_commit_sha)
                and pr.merge_commit_sha == self.repository.main_sha
            )
        else:
            raise OfflineRuntimeError("SYNTHETIC_MUTATION_UNSUPPORTED")

        outcome = (
            "RECONCILED_CONFIRMED_SUCCESS"
            if success
            else "RECONCILED_CONFIRMED_TERMINAL_FAILURE"
        )
        evidence = {
            "provider_identity": PROVIDER_IDENTITY,
            "attempt_id": attempt.get("attempt_id"),
            "requested_mutation": mutation,
            "pr_number": pr.number,
            "repository_snapshot_digest": self.repository.snapshot_digest(),
            "postcondition_verified": success,
            "authoritative_no_effect_verified": not success,
            "reconciled_outcome": outcome,
        }
        return {
            "schema": RECONCILIATION_SCHEMA,
            "state": "SYNTHETIC_AUTHORITATIVE_READBACK_COMPLETE",
            **evidence,
            "postcondition_evidence_digest": _digest(evidence),
            "github_queried": False,
            "network_called": False,
            "repository_mutation_replayed": False,
            "automatic_retry_allowed": False,
            "new_attempt_authorized": False,
        }


class OfflineRepositoryMutationRuntime:
    """Orchestrates one synthetic local mutation attempt fail-closed."""

    def __init__(
        self,
        *,
        store: LocalRepositoryMutationStore,
        adapter: SyntheticRepositoryMutationAdapter,
    ):
        self.store = store
        self.adapter = adapter

    def execute_once(
        self,
        *,
        authorization_receipt: Mapping[str, Any] | None,
        owner_signature_attestation: Mapping[str, Any] | None,
        runtime_nonce_scope: Any,
        runtime_nonce_digest: Any,
        attempt_id: Any,
        behavior: Any,
        now: Any,
    ) -> dict[str, Any]:
        receipt = dict(authorization_receipt or {})
        signature = dict(owner_signature_attestation or {})
        current = _aware(now, "RUNTIME_NOW")

        self.store.require_kill_switch_open()

        auth_check = verify_repository_mutation_authorization_receipt(
            receipt,
            now=_iso(current),
        )
        if auth_check.get("valid") is not True:
            raise OfflineRuntimeError(
                "VALID_FRESH_AUTHORIZATION_RECEIPT_REQUIRED",
                blockers=auth_check.get("blockers", []),
            )
        if signature.get("state") != "OWNER_SIGNATURE_VERIFIED":
            raise OfflineRuntimeError("OWNER_SIGNATURE_VERIFICATION_REQUIRED")
        if _sha256(signature.get("authorization_receipt_digest")) != _sha256(
            receipt.get("authorization_receipt_digest")
        ):
            raise OfflineRuntimeError("OWNER_SIGNATURE_RECEIPT_BINDING_MISMATCH")

        nonce_expires = _aware(receipt.get("expires_at"), "AUTHORIZATION_EXPIRES_AT")
        self.store.reserve_nonce_once(
            scope=runtime_nonce_scope,
            nonce_digest=runtime_nonce_digest,
            reserved_at=_iso(current),
            expires_at=_iso(nonce_expires),
        )

        persisted = self.store.persist_authorization_once(
            receipt=receipt,
            signature_attestation=signature,
            persisted_at=_iso(current),
        )
        consumption_digest = _digest(
            {
                "receipt_digest": persisted["receipt_digest"],
                "attempt_id": _identity(attempt_id, 180),
                "runtime_nonce_digest": _sha256(runtime_nonce_digest),
                "consumed_at": _iso(current),
            }
        )
        consumed = self.store.consume_authorization_once(
            receipt_digest=persisted["receipt_digest"],
            consumption_digest=consumption_digest,
            consumed_at=_iso(current),
        )

        adapter_result = self.adapter.attempt(
            receipt=receipt,
            behavior=behavior,
        )
        attempt = self.store.record_attempt_once(
            attempt_id=attempt_id,
            receipt_digest=consumed["receipt_digest"],
            pr_number=int(receipt.get("pr_number")),
            requested_mutation=receipt.get("requested_mutation"),
            behavior=behavior,
            before_state_digest=adapter_result["before_state_digest"],
            after_state_digest=adapter_result["after_state_digest"],
            primary_outcome=adapter_result["primary_outcome"],
            evidence_digest=adapter_result["evidence_digest"],
            attempted_at=_iso(current),
        )
        return {
            "schema": SCHEMA,
            "state": "OFFLINE_SYNTHETIC_ATTEMPT_RECORDED",
            "provider_identity": PROVIDER_IDENTITY,
            "provider_mode": PROVIDER_MODE,
            "attempt": attempt,
            "adapter_result": adapter_result,
            "authorization_consumed": True,
            "automatic_retry_allowed": False,
            "new_attempt_authorized": False,
            "synthetic_local_mutation_performed": adapter_result[
                "synthetic_local_mutation_performed"
            ],
            "github_api_called": False,
            "network_called": False,
            "live_repository_mutation_performed": False,
            "deploy_executed": False,
            "worker_activated": False,
            "production_persistence_activated": False,
        }

    def reconcile_unknown(
        self,
        *,
        attempt_id: Any,
        reconciled_at: Any,
    ) -> dict[str, Any]:
        self.store.require_kill_switch_open()
        attempt = self.store.get_attempt(attempt_id)
        if attempt["primary_outcome"] != "OUTCOME_UNKNOWN":
            raise OfflineRuntimeError("RECONCILIATION_ONLY_FOR_OUTCOME_UNKNOWN")
        readback = self.adapter.authoritative_readback(attempt=attempt)
        persisted = self.store.record_reconciliation_once(
            attempt_id=attempt["attempt_id"],
            reconciled_outcome=readback["reconciled_outcome"],
            postcondition_evidence_digest=readback[
                "postcondition_evidence_digest"
            ],
            reconciled_at=reconciled_at,
        )
        return {
            "schema": RECONCILIATION_SCHEMA,
            "state": "OFFLINE_SYNTHETIC_RECONCILIATION_RECORDED",
            "attempt_id": attempt["attempt_id"],
            "reconciliation": persisted,
            "readback": readback,
            "repository_mutation_replayed": False,
            "automatic_retry_allowed": False,
            "new_attempt_authorized": False,
            "github_queried": False,
            "network_called": False,
            "live_repository_mutation_performed": False,
        }

    def persist_terminal_audit(
        self,
        *,
        attempt_id: Any,
        persisted_at: Any,
    ) -> dict[str, Any]:
        attempt = self.store.get_attempt(attempt_id)
        reconciliation: dict[str, Any] | None = None
        try:
            reconciliation = self.store.get_reconciliation(attempt_id)
        except OfflineRuntimeError as exc:
            if exc.code != "RECONCILIATION_NOT_FOUND":
                raise

        if attempt["primary_outcome"] == "CONFIRMED_SUCCESS":
            terminal = "CERTIFIED_FINAL_SUCCESS"
        elif attempt["primary_outcome"] == "CONFIRMED_TERMINAL_FAILURE":
            terminal = "CERTIFIED_FINAL_TERMINAL_FAILURE"
        elif reconciliation is None:
            terminal = "CERTIFIED_OPEN_AMBIGUOUS"
        elif (
            reconciliation["reconciled_outcome"]
            == "RECONCILED_CONFIRMED_SUCCESS"
        ):
            terminal = "CERTIFIED_FINAL_SUCCESS"
        elif (
            reconciliation["reconciled_outcome"]
            == "RECONCILED_CONFIRMED_TERMINAL_FAILURE"
        ):
            terminal = "CERTIFIED_FINAL_TERMINAL_FAILURE"
        else:
            terminal = "CERTIFIED_OPEN_AMBIGUOUS"

        manifest = {
            "provider_identity": PROVIDER_IDENTITY,
            "attempt_id": attempt["attempt_id"],
            "receipt_digest": attempt["receipt_digest"],
            "pr_number": attempt["pr_number"],
            "requested_mutation": attempt["requested_mutation"],
            "primary_outcome": attempt["primary_outcome"],
            "reconciled_outcome": (
                reconciliation["reconciled_outcome"]
                if reconciliation is not None
                else ""
            ),
            "terminal_outcome": terminal,
            "attempt_evidence_digest": attempt["evidence_digest"],
        }
        manifest_digest = _digest(manifest)
        certificate_digest = _digest(
            {"manifest_digest": manifest_digest, "manifest": manifest}
        )
        stored = self.store.persist_terminal_audit_once(
            attempt_id=attempt["attempt_id"],
            terminal_outcome=terminal,
            manifest_digest=manifest_digest,
            certificate_digest=certificate_digest,
            persisted_at=persisted_at,
        )
        return {
            "schema": TERMINAL_AUDIT_SCHEMA,
            "state": "OFFLINE_TERMINAL_AUDIT_PERSISTED",
            "terminal_audit": stored,
            "manifest": manifest,
            "terminal_closed": terminal != "CERTIFIED_OPEN_AMBIGUOUS",
            "reconciliation_required": terminal == "CERTIFIED_OPEN_AMBIGUOUS",
            "automatic_retry_allowed": False,
            "new_attempt_authorized": False,
            "github_api_called": False,
            "network_called": False,
            "live_repository_mutation_performed": False,
        }


def offline_runtime_policy() -> dict[str, Any]:
    return {
        "schema": POLICY_SCHEMA,
        "provider_identity": PROVIDER_IDENTITY,
        "provider_mode": PROVIDER_MODE,
        "supported_mutations": list(SUPPORTED_MUTATIONS),
        "synthetic_behaviors": list(SYNTHETIC_BEHAVIORS),
        "sqlite_local_store_implemented": True,
        "sqlite_wal_enabled": True,
        "sqlite_synchronous_full_required": True,
        "single_local_runtime_truth": True,
        "durable_nonce_replay_registry_implemented": True,
        "durable_authorization_store_implemented": True,
        "atomic_authorization_consumption_implemented": True,
        "external_ed25519_public_key_verification_implemented": True,
        "real_owner_private_signer_implemented": False,
        "kill_switch_implemented": True,
        "kill_switch_default_enabled": True,
        "synthetic_provider_implemented": True,
        "synthetic_attempt_observation_implemented": True,
        "synthetic_postcondition_readback_implemented": True,
        "synthetic_unknown_reconciliation_implemented": True,
        "local_terminal_audit_store_implemented": True,
        "live_github_state_reader_implemented": False,
        "live_github_adapter_implemented": False,
        "runtime_credential_broker_implemented": False,
        "live_github_transport_executor_implemented": False,
        "live_authoritative_postcondition_reader_implemented": False,
        "live_reconciliation_evidence_collector_implemented": False,
        "github_endpoint_material_included": False,
        "credential_material_included": False,
        "real_github_credentials_loaded": False,
        "real_github_network_path_enabled": False,
        "github_api_called": False,
        "network_called": False,
        "live_repository_mutation_authorized": False,
        "live_repository_mutation_performed": False,
        "production_repository_mutation_performed": False,
        "automatic_retry_allowed": False,
        "deploy_executed": False,
        "worker_activated": False,
        "provider_activated": False,
        "production_persistence_activated": False,
    }


__all__ = [
    "SCHEMA",
    "STORE_SCHEMA",
    "SIGNATURE_SCHEMA",
    "ATTEMPT_SCHEMA",
    "RECONCILIATION_SCHEMA",
    "TERMINAL_AUDIT_SCHEMA",
    "POLICY_SCHEMA",
    "STORE_SCHEMA_VERSION",
    "PROVIDER_IDENTITY",
    "PROVIDER_MODE",
    "SIGNATURE_CONTEXT",
    "SUPPORTED_MUTATIONS",
    "SYNTHETIC_BEHAVIORS",
    "PRIMARY_OUTCOMES",
    "RECONCILED_OUTCOMES",
    "OfflineRuntimeError",
    "owner_public_key_fingerprint",
    "verify_external_owner_ed25519_signature",
    "SyntheticPullRequest",
    "SyntheticRepositoryState",
    "LocalRepositoryMutationStore",
    "SyntheticRepositoryMutationAdapter",
    "OfflineRepositoryMutationRuntime",
    "offline_runtime_policy",
]
