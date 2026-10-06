"""AION V2.14 durable execution safety kernel.

Persistent local state for task dispatch safety. This module does not execute
external actions. It coordinates idempotency, leases, retry scheduling,
dead-lettering and crash recovery around an executor.

Critical invariant:
Once an external dispatch is durably recorded, a crash or ambiguous result is
OUTCOME_UNKNOWN and automatic retry is forbidden until explicit reconciliation.
"""
from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping

SCHEMA = "ATLASQUANT_AION_DURABLE_EXECUTION_V1"
STATES = {
    "PREPARED",
    "LEASED",
    "DISPATCH_RECORDED",
    "RETRY_WAIT",
    "OUTCOME_UNKNOWN",
    "COMPLETED",
    "CANCELED",
    "DLQ",
}
TERMINAL = {"COMPLETED", "CANCELED", "DLQ"}
MODES = {"LOCAL_SAFE", "EXTERNAL_EFFECT"}
DEFAULT_BASE_BACKOFF_SECONDS = 5
DEFAULT_MAX_BACKOFF_SECONDS = 300
DEFAULT_LEASE_SECONDS = 120
MAX_LEASE_SECONDS = 1800
DEFAULT_POISON_THRESHOLD = 3
STORE_SCHEMA_VERSION = 2
TERMINAL_FINAL_STATES = {"FINALIZED_SUCCESS", "FINALIZED_TERMINAL_FAILURE"}
TERMINAL_EVIDENCE_DIGEST_ALGORITHM = "SHA256"
TERMINAL_EVIDENCE_CANONICAL_ENCODING = "UTF8_CANONICAL_JSON"


class DurableExecutionError(ValueError):
    def __init__(self, code: str, record: Mapping[str, Any] | None = None):
        super().__init__(code)
        row = dict(record or {})
        self.result = {
            "state": "BLOCKED",
            "error_code": code,
            "execution_id": row.get("execution_id", ""),
            "task_id": row.get("task_id", ""),
            "step_id": row.get("step_id", ""),
            "executes_action": False,
        }


def _parse_ts(value: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise DurableExecutionError("TIMESTAMP_INVALID")
    try:
        return datetime.fromisoformat(value[:-1] + "+00:00").astimezone(timezone.utc)
    except Exception as exc:
        raise DurableExecutionError("TIMESTAMP_INVALID") from exc


def _ts(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _clean(value: Any, limit: int = 256) -> str:
    text = " ".join(str(value or "").replace("\x00", "").split())
    return text[:limit]


def _digest(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _required_text(value: Any, code: str, limit: int = 256) -> str:
    text = _clean(value, limit)
    if not text:
        raise DurableExecutionError(code)
    return text


def _terminal_revision(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise DurableExecutionError("TERMINAL_REVISION_INVALID")
    return value


def _evidence_row(row, missing_code: str) -> dict[str, Any]:
    if row is None:
        raise DurableExecutionError(missing_code)
    item = dict(row)
    item["executes_action"] = False
    return item


def canonical_execution_id(task_id: str, step_id: str, idempotency_key: str, payload_digest: str) -> str:
    values = [task_id, step_id, idempotency_key, payload_digest]
    if any(not _clean(v) for v in values):
        raise DurableExecutionError("EXECUTION_ID_INPUT_INVALID")
    raw = "|".join(values).encode("utf-8")
    return "EXE-" + hashlib.sha256(raw).hexdigest()[:24].upper()


def deterministic_backoff_seconds(
    attempt: int,
    *,
    base_seconds: int = DEFAULT_BASE_BACKOFF_SECONDS,
    max_seconds: int = DEFAULT_MAX_BACKOFF_SECONDS,
) -> int:
    if isinstance(attempt, bool) or not isinstance(attempt, int) or attempt < 1:
        raise DurableExecutionError("ATTEMPT_INVALID")
    if base_seconds < 1 or max_seconds < base_seconds:
        raise DurableExecutionError("BACKOFF_POLICY_INVALID")
    return min(max_seconds, base_seconds * (2 ** (attempt - 1)))


@dataclass(frozen=True)
class PreparedExecution:
    record: dict[str, Any]
    replay: bool


class DurableExecutionStore:
    def __init__(self, db_path: str | Path):
        self.path = Path(db_path)
        if self.path.exists() and self.path.is_symlink():
            raise DurableExecutionError("STORE_SYMLINK_REJECTED")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self):
        conn = sqlite3.connect(str(self.path), timeout=10.0, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA synchronous=FULL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _initialize(self):
        with self._connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("BEGIN IMMEDIATE")
            try:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS executions (
                        execution_id TEXT PRIMARY KEY,
                        task_id TEXT NOT NULL,
                        step_id TEXT NOT NULL,
                        idempotency_key TEXT NOT NULL UNIQUE,
                        effect_key TEXT NOT NULL UNIQUE,
                        payload_digest TEXT NOT NULL,
                        mode TEXT NOT NULL,
                        state TEXT NOT NULL,
                        attempt INTEGER NOT NULL,
                        max_attempts INTEGER NOT NULL,
                        poison_threshold INTEGER NOT NULL,
                        same_error_count INTEGER NOT NULL,
                        last_error_fingerprint TEXT NOT NULL,
                        next_attempt_at TEXT NOT NULL,
                        deadline_at TEXT NOT NULL,
                        lease_owner TEXT NOT NULL,
                        lease_token TEXT NOT NULL,
                        lease_expires_at TEXT NOT NULL,
                        dispatch_recorded_at TEXT NOT NULL,
                        completed_at TEXT NOT NULL,
                        result_digest TEXT NOT NULL,
                        reconciliation_evidence_digest TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS execution_store_meta (
                        key TEXT PRIMARY KEY,
                        value TEXT NOT NULL
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS execution_scope_bindings (
                        execution_id TEXT PRIMARY KEY,
                        owner_id TEXT NOT NULL,
                        tenant_id TEXT NOT NULL,
                        workspace_id TEXT NOT NULL,
                        scope_digest TEXT NOT NULL,
                        scope_binding_source_digest TEXT NOT NULL,
                        bound_at TEXT NOT NULL,
                        FOREIGN KEY(execution_id)
                            REFERENCES executions(execution_id) ON DELETE RESTRICT
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS execution_terminal_finalizations (
                        execution_id TEXT PRIMARY KEY,
                        terminal_revision INTEGER NOT NULL CHECK (terminal_revision >= 1),
                        core_execution_state TEXT NOT NULL,
                        final_execution_state TEXT NOT NULL,
                        execution_finalization_contract_digest TEXT NOT NULL,
                        finalization_record_digest TEXT NOT NULL,
                        external_effect_outcome_receipt_digest TEXT NOT NULL,
                        outcome_reconciliation_record_digest TEXT NOT NULL,
                        rollback_or_compensation_settlement_digest TEXT NOT NULL,
                        finops_estimate_digest TEXT NOT NULL,
                        finops_observation_digest TEXT NOT NULL,
                        observability_trace_id TEXT NOT NULL,
                        pre_terminal_audit_chain_digest TEXT NOT NULL,
                        persisted_at TEXT NOT NULL,
                        FOREIGN KEY(execution_id)
                            REFERENCES executions(execution_id) ON DELETE RESTRICT
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS execution_audit_seals (
                        execution_id TEXT PRIMARY KEY,
                        terminal_revision INTEGER NOT NULL CHECK (terminal_revision >= 1),
                        finalization_record_digest TEXT NOT NULL,
                        audit_seal_manifest_digest TEXT NOT NULL,
                        audit_seal_record_digest TEXT NOT NULL,
                        audit_chain_digest TEXT NOT NULL,
                        finops_observation_digest TEXT NOT NULL,
                        observability_trace_id TEXT NOT NULL,
                        persisted_at TEXT NOT NULL,
                        FOREIGN KEY(execution_id)
                            REFERENCES execution_terminal_finalizations(execution_id)
                            ON DELETE RESTRICT
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS execution_terminal_certificates (
                        execution_id TEXT PRIMARY KEY,
                        terminal_revision INTEGER NOT NULL CHECK (terminal_revision >= 1),
                        final_execution_state TEXT NOT NULL,
                        scope_digest TEXT NOT NULL,
                        finalization_record_digest TEXT NOT NULL,
                        audit_seal_manifest_digest TEXT NOT NULL,
                        audit_seal_record_digest TEXT NOT NULL,
                        certificate_manifest_digest TEXT NOT NULL,
                        certificate_digest TEXT NOT NULL,
                        certificate_persistence_record_digest TEXT NOT NULL,
                        terminal_evidence_set_digest TEXT NOT NULL,
                        finops_observation_digest TEXT NOT NULL,
                        observability_trace_id TEXT NOT NULL,
                        pre_terminal_audit_chain_digest TEXT NOT NULL,
                        digest_algorithm TEXT NOT NULL,
                        canonical_encoding TEXT NOT NULL,
                        persisted_at TEXT NOT NULL,
                        FOREIGN KEY(execution_id)
                            REFERENCES execution_audit_seals(execution_id)
                            ON DELETE RESTRICT
                    )
                    """
                )
                conn.execute(
                    """
                    INSERT INTO execution_store_meta(key, value)
                    VALUES ('schema_version', ?)
                    ON CONFLICT(key) DO UPDATE SET value=excluded.value
                    """,
                    (str(STORE_SCHEMA_VERSION),),
                )
                conn.execute("COMMIT")
            except Exception:
                if conn.in_transaction:
                    conn.execute("ROLLBACK")
                raise

    def _row(self, row) -> dict[str, Any]:
        if row is None:
            raise DurableExecutionError("EXECUTION_NOT_FOUND")
        item = dict(row)
        item["automatic_retry_allowed"] = (
            item["state"] == "RETRY_WAIT"
            and item["mode"] == "LOCAL_SAFE"
        ) or (
            item["state"] == "RETRY_WAIT"
            and item["mode"] == "EXTERNAL_EFFECT"
            and not item["dispatch_recorded_at"]
        )
        item["executes_action"] = False
        item["external_effect_performed"] = False
        return item

    def get(self, execution_id: str) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM executions WHERE execution_id = ?",
                (_clean(execution_id, 96),),
            ).fetchone()
        return self._row(row)

    def _find_by_idempotency(self, key: str):
        with self._connect() as conn:
            return conn.execute(
                "SELECT * FROM executions WHERE idempotency_key = ?",
                (key,),
            ).fetchone()

    def prepare(
        self,
        *,
        task_id: str,
        step_id: str,
        idempotency_key: str,
        effect_key: str,
        payload_digest: str,
        mode: str,
        now_ts: str,
        deadline_at: str,
        max_attempts: int = 3,
        poison_threshold: int = DEFAULT_POISON_THRESHOLD,
    ) -> PreparedExecution:
        task_id = _clean(task_id, 128)
        step_id = _clean(step_id, 128)
        idem = _clean(idempotency_key, 256)
        effect = _clean(effect_key, 256)
        payload = _clean(payload_digest, 128)
        if not all((task_id, step_id, idem, effect, payload)):
            raise DurableExecutionError("PREPARE_INPUT_INVALID")
        if mode not in MODES:
            raise DurableExecutionError("MODE_INVALID")
        if isinstance(max_attempts, bool) or not isinstance(max_attempts, int) or not 1 <= max_attempts <= 100:
            raise DurableExecutionError("MAX_ATTEMPTS_INVALID")
        if isinstance(poison_threshold, bool) or not isinstance(poison_threshold, int) or not 1 <= poison_threshold <= max_attempts:
            raise DurableExecutionError("POISON_THRESHOLD_INVALID")
        now = _parse_ts(now_ts)
        deadline = _parse_ts(deadline_at)
        if deadline <= now:
            raise DurableExecutionError("DEADLINE_EXPIRED")
        execution_id = canonical_execution_id(task_id, step_id, idem, payload)

        existing = self._find_by_idempotency(idem)
        if existing is not None:
            row = self._row(existing)
            same = (
                row["execution_id"] == execution_id
                and row["task_id"] == task_id
                and row["step_id"] == step_id
                and row["effect_key"] == effect
                and row["payload_digest"] == payload
                and row["mode"] == mode
            )
            if not same:
                raise DurableExecutionError("IDEMPOTENCY_CONFLICT", row)
            return PreparedExecution(row, True)

        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                conflict = conn.execute(
                    "SELECT * FROM executions WHERE effect_key = ?",
                    (effect,),
                ).fetchone()
                if conflict is not None:
                    conn.execute("ROLLBACK")
                    raise DurableExecutionError("EFFECT_ALREADY_REGISTERED", self._row(conflict))
                conn.execute(
                    """
                    INSERT INTO executions (
                        execution_id, task_id, step_id, idempotency_key, effect_key,
                        payload_digest, mode, state, attempt, max_attempts,
                        poison_threshold, same_error_count, last_error_fingerprint,
                        next_attempt_at, deadline_at, lease_owner, lease_token,
                        lease_expires_at, dispatch_recorded_at, completed_at,
                        result_digest, reconciliation_evidence_digest, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, 'PREPARED', 0, ?, ?, 0, '',
                              '', ?, '', '', '', '', '', '', '', ?, ?)
                    """,
                    (
                        execution_id, task_id, step_id, idem, effect, payload, mode,
                        max_attempts, poison_threshold, deadline_at, now_ts, now_ts,
                    ),
                )
                conn.execute("COMMIT")
            except DurableExecutionError:
                raise
            except sqlite3.IntegrityError as exc:
                conn.execute("ROLLBACK")
                raise DurableExecutionError("PREPARE_CONFLICT") from exc
            except Exception:
                conn.execute("ROLLBACK")
                raise
        return PreparedExecution(self.get(execution_id), False)

    def _deadline_check(self, row: dict[str, Any], now_ts: str) -> None:
        if _parse_ts(now_ts) >= _parse_ts(row["deadline_at"]):
            with self._connect() as conn:
                conn.execute(
                    "UPDATE executions SET state='DLQ', updated_at=?, lease_owner='', lease_token='', lease_expires_at='' WHERE execution_id=?",
                    (now_ts, row["execution_id"]),
                )
            raise DurableExecutionError("DEADLINE_EXCEEDED", self.get(row["execution_id"]))

    def acquire_lease(
        self,
        execution_id: str,
        *,
        owner: str,
        now_ts: str,
        lease_seconds: int = DEFAULT_LEASE_SECONDS,
        lease_token: str | None = None,
    ) -> dict[str, Any]:
        owner = _clean(owner, 128)
        if not owner:
            raise DurableExecutionError("LEASE_OWNER_REQUIRED")
        if isinstance(lease_seconds, bool) or not isinstance(lease_seconds, int) or not 1 <= lease_seconds <= MAX_LEASE_SECONDS:
            raise DurableExecutionError("LEASE_SECONDS_INVALID")
        token = _clean(lease_token or secrets.token_urlsafe(24), 128)
        now = _parse_ts(now_ts)
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT * FROM executions WHERE execution_id=?", (execution_id,)).fetchone()
            if row is None:
                conn.execute("ROLLBACK")
                raise DurableExecutionError("EXECUTION_NOT_FOUND")
            item = self._row(row)
            if item["state"] in TERMINAL or item["state"] in {"OUTCOME_UNKNOWN", "DISPATCH_RECORDED"}:
                conn.execute("ROLLBACK")
                raise DurableExecutionError("LEASE_STATE_BLOCKED", item)
            if item["state"] == "RETRY_WAIT" and item["next_attempt_at"] and now < _parse_ts(item["next_attempt_at"]):
                conn.execute("ROLLBACK")
                raise DurableExecutionError("RETRY_NOT_DUE", item)
            if now >= _parse_ts(item["deadline_at"]):
                conn.execute(
                    "UPDATE executions SET state='DLQ', updated_at=? WHERE execution_id=?",
                    (now_ts, execution_id),
                )
                conn.execute("COMMIT")
                raise DurableExecutionError("DEADLINE_EXCEEDED", self.get(execution_id))
            if item["state"] == "LEASED" and item["lease_expires_at"] and now < _parse_ts(item["lease_expires_at"]):
                conn.execute("ROLLBACK")
                raise DurableExecutionError("LEASE_CONFLICT", item)
            expires = _ts(now + timedelta(seconds=lease_seconds))
            conn.execute(
                """
                UPDATE executions
                SET state='LEASED', attempt=attempt+1, lease_owner=?, lease_token=?,
                    lease_expires_at=?, next_attempt_at='', updated_at=?
                WHERE execution_id=?
                """,
                (owner, token, expires, now_ts, execution_id),
            )
            conn.execute("COMMIT")
        return self.get(execution_id)

    def heartbeat(
        self,
        execution_id: str,
        *,
        lease_token: str,
        now_ts: str,
        lease_seconds: int = DEFAULT_LEASE_SECONDS,
    ) -> dict[str, Any]:
        row = self.get(execution_id)
        if row["state"] != "LEASED":
            raise DurableExecutionError("HEARTBEAT_STATE_BLOCKED", row)
        if not lease_token or row["lease_token"] != lease_token:
            raise DurableExecutionError("LEASE_TOKEN_MISMATCH", row)
        self._deadline_check(row, now_ts)
        now = _parse_ts(now_ts)
        if row["lease_expires_at"] and now >= _parse_ts(row["lease_expires_at"]):
            raise DurableExecutionError("LEASE_EXPIRED", row)
        if isinstance(lease_seconds, bool) or not isinstance(lease_seconds, int) or not 1 <= lease_seconds <= MAX_LEASE_SECONDS:
            raise DurableExecutionError("LEASE_SECONDS_INVALID", row)
        expires = _ts(now + timedelta(seconds=lease_seconds))
        with self._connect() as conn:
            conn.execute(
                "UPDATE executions SET lease_expires_at=?, updated_at=? WHERE execution_id=? AND lease_token=?",
                (expires, now_ts, execution_id, lease_token),
            )
        return self.get(execution_id)

    def record_dispatch_started(
        self,
        execution_id: str,
        *,
        lease_token: str,
        now_ts: str,
    ) -> dict[str, Any]:
        row = self.get(execution_id)
        if row["mode"] != "EXTERNAL_EFFECT":
            raise DurableExecutionError("DISPATCH_MODE_BLOCKED", row)
        if row["state"] != "LEASED":
            raise DurableExecutionError("DISPATCH_STATE_BLOCKED", row)
        if row["lease_token"] != lease_token or not lease_token:
            raise DurableExecutionError("LEASE_TOKEN_MISMATCH", row)
        self._deadline_check(row, now_ts)
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE executions
                SET state='DISPATCH_RECORDED', dispatch_recorded_at=?, updated_at=?
                WHERE execution_id=? AND lease_token=?
                """,
                (now_ts, now_ts, execution_id, lease_token),
            )
        return self.get(execution_id)

    def complete(
        self,
        execution_id: str,
        *,
        lease_token: str,
        result_digest: str,
        now_ts: str,
    ) -> dict[str, Any]:
        row = self.get(execution_id)
        digest = _clean(result_digest, 128)
        if row["state"] == "COMPLETED":
            if row["result_digest"] == digest:
                return row
            raise DurableExecutionError("RESULT_REPLAY_CONFLICT", row)
        allowed = {"LEASED"} if row["mode"] == "LOCAL_SAFE" else {"DISPATCH_RECORDED"}
        if row["state"] not in allowed:
            raise DurableExecutionError("COMPLETE_STATE_BLOCKED", row)
        if row["lease_token"] != lease_token or not lease_token:
            raise DurableExecutionError("LEASE_TOKEN_MISMATCH", row)
        if not digest:
            raise DurableExecutionError("RESULT_DIGEST_REQUIRED", row)
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE executions
                SET state='COMPLETED', result_digest=?, completed_at=?, updated_at=?,
                    lease_owner='', lease_token='', lease_expires_at=''
                WHERE execution_id=?
                """,
                (digest, now_ts, now_ts, execution_id),
            )
        return self.get(execution_id)

    def fail_before_dispatch(
        self,
        execution_id: str,
        *,
        lease_token: str,
        error_fingerprint: str,
        now_ts: str,
        retryable: bool,
        base_backoff_seconds: int = DEFAULT_BASE_BACKOFF_SECONDS,
        max_backoff_seconds: int = DEFAULT_MAX_BACKOFF_SECONDS,
    ) -> dict[str, Any]:
        row = self.get(execution_id)
        if row["state"] != "LEASED" or row["dispatch_recorded_at"]:
            raise DurableExecutionError("FAIL_BEFORE_DISPATCH_STATE_BLOCKED", row)
        if row["lease_token"] != lease_token or not lease_token:
            raise DurableExecutionError("LEASE_TOKEN_MISMATCH", row)
        error = _clean(error_fingerprint, 128)
        if not error:
            raise DurableExecutionError("ERROR_FINGERPRINT_REQUIRED", row)
        same_count = row["same_error_count"] + 1 if row["last_error_fingerprint"] == error else 1
        dlq = (
            retryable is not True
            or row["attempt"] >= row["max_attempts"]
            or same_count >= row["poison_threshold"]
            or _parse_ts(now_ts) >= _parse_ts(row["deadline_at"])
        )
        if dlq:
            state = "DLQ"
            next_attempt = ""
        else:
            state = "RETRY_WAIT"
            delay = deterministic_backoff_seconds(
                row["attempt"],
                base_seconds=base_backoff_seconds,
                max_seconds=max_backoff_seconds,
            )
            next_attempt = _ts(_parse_ts(now_ts) + timedelta(seconds=delay))
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE executions
                SET state=?, same_error_count=?, last_error_fingerprint=?,
                    next_attempt_at=?, updated_at=?, lease_owner='', lease_token='',
                    lease_expires_at=''
                WHERE execution_id=?
                """,
                (state, same_count, error, next_attempt, now_ts, execution_id),
            )
        return self.get(execution_id)

    def mark_outcome_unknown(
        self,
        execution_id: str,
        *,
        lease_token: str,
        error_fingerprint: str,
        now_ts: str,
    ) -> dict[str, Any]:
        row = self.get(execution_id)
        if row["state"] != "DISPATCH_RECORDED":
            raise DurableExecutionError("OUTCOME_UNKNOWN_STATE_BLOCKED", row)
        if row["lease_token"] != lease_token or not lease_token:
            raise DurableExecutionError("LEASE_TOKEN_MISMATCH", row)
        error = _clean(error_fingerprint, 128) or "OUTCOME_UNKNOWN"
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE executions
                SET state='OUTCOME_UNKNOWN', last_error_fingerprint=?, updated_at=?,
                    lease_owner='', lease_token='', lease_expires_at=''
                WHERE execution_id=?
                """,
                (error, now_ts, execution_id),
            )
        return self.get(execution_id)

    def recover_expired_leases(self, *, now_ts: str) -> list[dict[str, Any]]:
        now = _parse_ts(now_ts)
        changed = []
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            rows = conn.execute(
                "SELECT * FROM executions WHERE state IN ('LEASED','DISPATCH_RECORDED')"
            ).fetchall()
            for raw in rows:
                row = self._row(raw)
                if not row["lease_expires_at"] or now < _parse_ts(row["lease_expires_at"]):
                    continue
                if row["state"] == "DISPATCH_RECORDED" or row["dispatch_recorded_at"]:
                    state = "OUTCOME_UNKNOWN"
                    next_attempt = ""
                elif row["attempt"] >= row["max_attempts"]:
                    state = "DLQ"
                    next_attempt = ""
                else:
                    state = "RETRY_WAIT"
                    next_attempt = now_ts
                conn.execute(
                    """
                    UPDATE executions
                    SET state=?, next_attempt_at=?, updated_at=?, lease_owner='',
                        lease_token='', lease_expires_at=''
                    WHERE execution_id=?
                    """,
                    (state, next_attempt, now_ts, row["execution_id"]),
                )
                changed.append(row["execution_id"])
            conn.execute("COMMIT")
        return [self.get(execution_id) for execution_id in changed]

    def cancel(self, execution_id: str, *, now_ts: str) -> dict[str, Any]:
        row = self.get(execution_id)
        if row["state"] == "LEASED":
            # A live lease means a worker may currently be executing local work
            # or preparing an external dispatch. Do not mutate ownership from a
            # tokenless cancellation path; recover/expire the lease first.
            raise DurableExecutionError("CANCEL_ACTIVE_LEASE_BLOCKED", row)
        if row["state"] in {"DISPATCH_RECORDED", "OUTCOME_UNKNOWN", "COMPLETED"}:
            raise DurableExecutionError("CANCEL_OUTCOME_UNCERTAIN_OR_TERMINAL", row)
        if row["state"] in {"CANCELED", "DLQ"}:
            return row
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE executions
                SET state='CANCELED', updated_at=?, lease_owner='', lease_token='',
                    lease_expires_at='', next_attempt_at=''
                WHERE execution_id=?
                """,
                (now_ts, execution_id),
            )
        return self.get(execution_id)

    def reconcile_unknown(
        self,
        execution_id: str,
        *,
        outcome: str,
        evidence_digest: str,
        reconciliation_authorized: bool,
        now_ts: str,
    ) -> dict[str, Any]:
        row = self.get(execution_id)
        if row["state"] != "OUTCOME_UNKNOWN":
            raise DurableExecutionError("RECONCILE_STATE_BLOCKED", row)
        if reconciliation_authorized is not True:
            raise DurableExecutionError("RECONCILIATION_AUTHORIZATION_REQUIRED", row)
        evidence = _clean(evidence_digest, 128)
        if not evidence:
            raise DurableExecutionError("RECONCILIATION_EVIDENCE_REQUIRED", row)
        if outcome not in {"CONFIRMED_EFFECT", "CONFIRMED_NO_EFFECT"}:
            raise DurableExecutionError("RECONCILIATION_OUTCOME_INVALID", row)
        if outcome == "CONFIRMED_EFFECT":
            state = "COMPLETED"
            result_digest = evidence
            completed_at = now_ts
            next_attempt = ""
            dispatch_recorded_at = row["dispatch_recorded_at"]
        else:
            if row["attempt"] >= row["max_attempts"]:
                state = "DLQ"
                next_attempt = ""
            else:
                state = "RETRY_WAIT"
                next_attempt = now_ts
            result_digest = ""
            completed_at = ""
            # Authoritative reconciliation proved the prior dispatch caused no
            # effect, so a future attempt starts a fresh dispatch lifecycle.
            dispatch_recorded_at = ""
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE executions
                SET state=?, result_digest=?, completed_at=?, next_attempt_at=?,
                    dispatch_recorded_at=?, reconciliation_evidence_digest=?, updated_at=?
                WHERE execution_id=?
                """,
                (state, result_digest, completed_at, next_attempt, dispatch_recorded_at,
                 evidence, now_ts, execution_id),
            )
        return self.get(execution_id)


    def store_schema_version(self) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT value FROM execution_store_meta WHERE key='schema_version'"
            ).fetchone()
        if row is None:
            raise DurableExecutionError("STORE_SCHEMA_VERSION_MISSING")
        try:
            return int(row["value"])
        except Exception as exc:
            raise DurableExecutionError("STORE_SCHEMA_VERSION_INVALID") from exc

    def get_execution_scope(self, execution_id: str) -> dict[str, Any]:
        execution_id = _required_text(execution_id, "EXECUTION_ID_REQUIRED", 96)
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM execution_scope_bindings WHERE execution_id=?",
                (execution_id,),
            ).fetchone()
        return _evidence_row(row, "EXECUTION_SCOPE_NOT_FOUND")

    def bind_execution_scope_once(
        self,
        execution_id: str,
        *,
        owner_id: str,
        tenant_id: str,
        workspace_id: str,
        scope_digest: str,
        scope_binding_source_digest: str,
        bound_at: str,
    ) -> dict[str, Any]:
        execution_id = _required_text(execution_id, "EXECUTION_ID_REQUIRED", 96)
        values = {
            "owner_id": _required_text(owner_id, "OWNER_ID_REQUIRED", 128),
            "tenant_id": _required_text(tenant_id, "TENANT_ID_REQUIRED", 128),
            "workspace_id": _required_text(workspace_id, "WORKSPACE_ID_REQUIRED", 128),
            "scope_digest": _required_text(scope_digest, "SCOPE_DIGEST_REQUIRED", 128),
            "scope_binding_source_digest": _required_text(
                scope_binding_source_digest,
                "SCOPE_BINDING_SOURCE_DIGEST_REQUIRED",
                128,
            ),
            "bound_at": _required_text(bound_at, "BOUND_AT_REQUIRED", 64),
        }
        _parse_ts(values["bound_at"])
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                parent = conn.execute(
                    "SELECT execution_id FROM executions WHERE execution_id=?",
                    (execution_id,),
                ).fetchone()
                if parent is None:
                    raise DurableExecutionError("EXECUTION_NOT_FOUND")
                existing = conn.execute(
                    "SELECT * FROM execution_scope_bindings WHERE execution_id=?",
                    (execution_id,),
                ).fetchone()
                if existing is not None:
                    item = dict(existing)
                    same = all(item[key] == value for key, value in values.items())
                    if not same:
                        raise DurableExecutionError("EXECUTION_SCOPE_CONFLICT", item)
                    conn.execute("COMMIT")
                    item["replay"] = True
                    item["executes_action"] = False
                    return item
                conn.execute(
                    """
                    INSERT INTO execution_scope_bindings (
                        execution_id, owner_id, tenant_id, workspace_id,
                        scope_digest, scope_binding_source_digest, bound_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        execution_id,
                        values["owner_id"],
                        values["tenant_id"],
                        values["workspace_id"],
                        values["scope_digest"],
                        values["scope_binding_source_digest"],
                        values["bound_at"],
                    ),
                )
                conn.execute("COMMIT")
            except Exception:
                if conn.in_transaction:
                    conn.execute("ROLLBACK")
                raise
        item = self.get_execution_scope(execution_id)
        item["replay"] = False
        return item

    def get_terminal_finalization(self, execution_id: str) -> dict[str, Any]:
        execution_id = _required_text(execution_id, "EXECUTION_ID_REQUIRED", 96)
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM execution_terminal_finalizations WHERE execution_id=?",
                (execution_id,),
            ).fetchone()
        return _evidence_row(row, "TERMINAL_FINALIZATION_NOT_FOUND")

    def persist_terminal_finalization_once(
        self,
        execution_id: str,
        *,
        terminal_revision: int,
        final_execution_state: str,
        execution_finalization_contract_digest: str,
        finalization_record_digest: str,
        external_effect_outcome_receipt_digest: str,
        outcome_reconciliation_record_digest: str = "",
        rollback_or_compensation_settlement_digest: str = "",
        finops_estimate_digest: str,
        finops_observation_digest: str,
        observability_trace_id: str,
        pre_terminal_audit_chain_digest: str,
        persisted_at: str,
    ) -> dict[str, Any]:
        execution_id = _required_text(execution_id, "EXECUTION_ID_REQUIRED", 96)
        revision = _terminal_revision(terminal_revision)
        final_state = _required_text(
            final_execution_state, "FINAL_EXECUTION_STATE_REQUIRED", 64
        )
        if final_state not in TERMINAL_FINAL_STATES:
            raise DurableExecutionError("FINAL_EXECUTION_STATE_INVALID")
        values = {
            "execution_finalization_contract_digest": _required_text(
                execution_finalization_contract_digest,
                "EXECUTION_FINALIZATION_CONTRACT_DIGEST_REQUIRED",
                128,
            ),
            "finalization_record_digest": _required_text(
                finalization_record_digest, "FINALIZATION_RECORD_DIGEST_REQUIRED", 128
            ),
            "external_effect_outcome_receipt_digest": _required_text(
                external_effect_outcome_receipt_digest,
                "OUTCOME_RECEIPT_DIGEST_REQUIRED",
                128,
            ),
            "outcome_reconciliation_record_digest": _clean(
                outcome_reconciliation_record_digest, 128
            ),
            "rollback_or_compensation_settlement_digest": _clean(
                rollback_or_compensation_settlement_digest, 128
            ),
            "finops_estimate_digest": _required_text(
                finops_estimate_digest, "FINOPS_ESTIMATE_DIGEST_REQUIRED", 128
            ),
            "finops_observation_digest": _required_text(
                finops_observation_digest, "FINOPS_OBSERVATION_DIGEST_REQUIRED", 128
            ),
            "observability_trace_id": _required_text(
                observability_trace_id, "OBSERVABILITY_TRACE_ID_REQUIRED", 128
            ),
            "pre_terminal_audit_chain_digest": _required_text(
                pre_terminal_audit_chain_digest,
                "PRE_TERMINAL_AUDIT_CHAIN_DIGEST_REQUIRED",
                128,
            ),
            "persisted_at": _required_text(persisted_at, "PERSISTED_AT_REQUIRED", 64),
        }
        _parse_ts(values["persisted_at"])

        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                execution = conn.execute(
                    "SELECT * FROM executions WHERE execution_id=?",
                    (execution_id,),
                ).fetchone()
                if execution is None:
                    raise DurableExecutionError("EXECUTION_NOT_FOUND")
                execution = dict(execution)
                if execution["state"] not in TERMINAL:
                    raise DurableExecutionError("EXECUTION_NOT_TERMINAL", execution)
                scope = conn.execute(
                    "SELECT execution_id FROM execution_scope_bindings WHERE execution_id=?",
                    (execution_id,),
                ).fetchone()
                if scope is None:
                    raise DurableExecutionError("EXECUTION_SCOPE_NOT_FOUND", execution)
                expected_final = (
                    "FINALIZED_SUCCESS"
                    if execution["state"] == "COMPLETED"
                    else "FINALIZED_TERMINAL_FAILURE"
                )
                if final_state != expected_final:
                    raise DurableExecutionError(
                        "FINAL_EXECUTION_STATE_CORE_MISMATCH", execution
                    )
                existing = conn.execute(
                    "SELECT * FROM execution_terminal_finalizations WHERE execution_id=?",
                    (execution_id,),
                ).fetchone()
                expected = {
                    "terminal_revision": revision,
                    "core_execution_state": execution["state"],
                    "final_execution_state": final_state,
                    **values,
                }
                if existing is not None:
                    item = dict(existing)
                    same = all(item[key] == value for key, value in expected.items())
                    if not same:
                        raise DurableExecutionError(
                            "TERMINAL_FINALIZATION_CONFLICT", item
                        )
                    conn.execute("COMMIT")
                    item["replay"] = True
                    item["executes_action"] = False
                    return item
                conn.execute(
                    """
                    INSERT INTO execution_terminal_finalizations (
                        execution_id, terminal_revision, core_execution_state,
                        final_execution_state,
                        execution_finalization_contract_digest,
                        finalization_record_digest,
                        external_effect_outcome_receipt_digest,
                        outcome_reconciliation_record_digest,
                        rollback_or_compensation_settlement_digest,
                        finops_estimate_digest, finops_observation_digest,
                        observability_trace_id, pre_terminal_audit_chain_digest,
                        persisted_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        execution_id,
                        revision,
                        execution["state"],
                        final_state,
                        values["execution_finalization_contract_digest"],
                        values["finalization_record_digest"],
                        values["external_effect_outcome_receipt_digest"],
                        values["outcome_reconciliation_record_digest"],
                        values["rollback_or_compensation_settlement_digest"],
                        values["finops_estimate_digest"],
                        values["finops_observation_digest"],
                        values["observability_trace_id"],
                        values["pre_terminal_audit_chain_digest"],
                        values["persisted_at"],
                    ),
                )
                conn.execute("COMMIT")
            except Exception:
                if conn.in_transaction:
                    conn.execute("ROLLBACK")
                raise
        item = self.get_terminal_finalization(execution_id)
        item["replay"] = False
        return item

    def get_audit_seal(self, execution_id: str) -> dict[str, Any]:
        execution_id = _required_text(execution_id, "EXECUTION_ID_REQUIRED", 96)
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM execution_audit_seals WHERE execution_id=?",
                (execution_id,),
            ).fetchone()
        return _evidence_row(row, "AUDIT_SEAL_NOT_FOUND")

    def persist_audit_seal_once(
        self,
        execution_id: str,
        *,
        terminal_revision: int,
        finalization_record_digest: str,
        audit_seal_manifest_digest: str,
        audit_seal_record_digest: str,
        audit_chain_digest: str,
        finops_observation_digest: str,
        observability_trace_id: str,
        persisted_at: str,
    ) -> dict[str, Any]:
        execution_id = _required_text(execution_id, "EXECUTION_ID_REQUIRED", 96)
        revision = _terminal_revision(terminal_revision)
        values = {
            "finalization_record_digest": _required_text(
                finalization_record_digest, "FINALIZATION_RECORD_DIGEST_REQUIRED", 128
            ),
            "audit_seal_manifest_digest": _required_text(
                audit_seal_manifest_digest, "AUDIT_SEAL_MANIFEST_DIGEST_REQUIRED", 128
            ),
            "audit_seal_record_digest": _required_text(
                audit_seal_record_digest, "AUDIT_SEAL_RECORD_DIGEST_REQUIRED", 128
            ),
            "audit_chain_digest": _required_text(
                audit_chain_digest, "AUDIT_CHAIN_DIGEST_REQUIRED", 128
            ),
            "finops_observation_digest": _required_text(
                finops_observation_digest, "FINOPS_OBSERVATION_DIGEST_REQUIRED", 128
            ),
            "observability_trace_id": _required_text(
                observability_trace_id, "OBSERVABILITY_TRACE_ID_REQUIRED", 128
            ),
            "persisted_at": _required_text(persisted_at, "PERSISTED_AT_REQUIRED", 64),
        }
        _parse_ts(values["persisted_at"])
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                finalization = conn.execute(
                    "SELECT * FROM execution_terminal_finalizations WHERE execution_id=?",
                    (execution_id,),
                ).fetchone()
                if finalization is None:
                    raise DurableExecutionError("TERMINAL_FINALIZATION_NOT_FOUND")
                finalization = dict(finalization)
                if finalization["terminal_revision"] != revision:
                    raise DurableExecutionError(
                        "AUDIT_SEAL_TERMINAL_REVISION_MISMATCH", finalization
                    )
                if (
                    finalization["finalization_record_digest"]
                    != values["finalization_record_digest"]
                ):
                    raise DurableExecutionError(
                        "AUDIT_SEAL_FINALIZATION_DIGEST_MISMATCH", finalization
                    )
                if (
                    finalization["finops_observation_digest"]
                    != values["finops_observation_digest"]
                ):
                    raise DurableExecutionError(
                        "AUDIT_SEAL_FINOPS_DIGEST_MISMATCH", finalization
                    )
                if (
                    finalization["observability_trace_id"]
                    != values["observability_trace_id"]
                ):
                    raise DurableExecutionError(
                        "AUDIT_SEAL_TRACE_MISMATCH", finalization
                    )
                existing = conn.execute(
                    "SELECT * FROM execution_audit_seals WHERE execution_id=?",
                    (execution_id,),
                ).fetchone()
                expected = {"terminal_revision": revision, **values}
                if existing is not None:
                    item = dict(existing)
                    same = all(item[key] == value for key, value in expected.items())
                    if not same:
                        raise DurableExecutionError("AUDIT_SEAL_CONFLICT", item)
                    conn.execute("COMMIT")
                    item["replay"] = True
                    item["executes_action"] = False
                    return item
                conn.execute(
                    """
                    INSERT INTO execution_audit_seals (
                        execution_id, terminal_revision, finalization_record_digest,
                        audit_seal_manifest_digest, audit_seal_record_digest,
                        audit_chain_digest, finops_observation_digest,
                        observability_trace_id, persisted_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        execution_id,
                        revision,
                        values["finalization_record_digest"],
                        values["audit_seal_manifest_digest"],
                        values["audit_seal_record_digest"],
                        values["audit_chain_digest"],
                        values["finops_observation_digest"],
                        values["observability_trace_id"],
                        values["persisted_at"],
                    ),
                )
                conn.execute("COMMIT")
            except Exception:
                if conn.in_transaction:
                    conn.execute("ROLLBACK")
                raise
        item = self.get_audit_seal(execution_id)
        item["replay"] = False
        return item

    def get_terminal_certificate(self, execution_id: str) -> dict[str, Any]:
        execution_id = _required_text(execution_id, "EXECUTION_ID_REQUIRED", 96)
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM execution_terminal_certificates WHERE execution_id=?",
                (execution_id,),
            ).fetchone()
        return _evidence_row(row, "TERMINAL_CERTIFICATE_NOT_FOUND")

    def persist_terminal_certificate_once(
        self,
        execution_id: str,
        *,
        terminal_revision: int,
        final_execution_state: str,
        scope_digest: str,
        finalization_record_digest: str,
        audit_seal_manifest_digest: str,
        audit_seal_record_digest: str,
        certificate_manifest_digest: str,
        certificate_digest: str,
        certificate_persistence_record_digest: str,
        terminal_evidence_set_digest: str,
        finops_observation_digest: str,
        observability_trace_id: str,
        pre_terminal_audit_chain_digest: str,
        digest_algorithm: str = TERMINAL_EVIDENCE_DIGEST_ALGORITHM,
        canonical_encoding: str = TERMINAL_EVIDENCE_CANONICAL_ENCODING,
        persisted_at: str,
    ) -> dict[str, Any]:
        execution_id = _required_text(execution_id, "EXECUTION_ID_REQUIRED", 96)
        revision = _terminal_revision(terminal_revision)
        final_state = _required_text(
            final_execution_state, "FINAL_EXECUTION_STATE_REQUIRED", 64
        )
        if digest_algorithm != TERMINAL_EVIDENCE_DIGEST_ALGORITHM:
            raise DurableExecutionError("CERTIFICATE_DIGEST_ALGORITHM_INVALID")
        if canonical_encoding != TERMINAL_EVIDENCE_CANONICAL_ENCODING:
            raise DurableExecutionError("CERTIFICATE_CANONICAL_ENCODING_INVALID")
        values = {
            "scope_digest": _required_text(scope_digest, "SCOPE_DIGEST_REQUIRED", 128),
            "finalization_record_digest": _required_text(
                finalization_record_digest, "FINALIZATION_RECORD_DIGEST_REQUIRED", 128
            ),
            "audit_seal_manifest_digest": _required_text(
                audit_seal_manifest_digest, "AUDIT_SEAL_MANIFEST_DIGEST_REQUIRED", 128
            ),
            "audit_seal_record_digest": _required_text(
                audit_seal_record_digest, "AUDIT_SEAL_RECORD_DIGEST_REQUIRED", 128
            ),
            "certificate_manifest_digest": _required_text(
                certificate_manifest_digest,
                "CERTIFICATE_MANIFEST_DIGEST_REQUIRED",
                128,
            ),
            "certificate_digest": _required_text(
                certificate_digest, "CERTIFICATE_DIGEST_REQUIRED", 128
            ),
            "certificate_persistence_record_digest": _required_text(
                certificate_persistence_record_digest,
                "CERTIFICATE_PERSISTENCE_RECORD_DIGEST_REQUIRED",
                128,
            ),
            "terminal_evidence_set_digest": _required_text(
                terminal_evidence_set_digest,
                "TERMINAL_EVIDENCE_SET_DIGEST_REQUIRED",
                128,
            ),
            "finops_observation_digest": _required_text(
                finops_observation_digest, "FINOPS_OBSERVATION_DIGEST_REQUIRED", 128
            ),
            "observability_trace_id": _required_text(
                observability_trace_id, "OBSERVABILITY_TRACE_ID_REQUIRED", 128
            ),
            "pre_terminal_audit_chain_digest": _required_text(
                pre_terminal_audit_chain_digest,
                "PRE_TERMINAL_AUDIT_CHAIN_DIGEST_REQUIRED",
                128,
            ),
            "persisted_at": _required_text(persisted_at, "PERSISTED_AT_REQUIRED", 64),
        }
        _parse_ts(values["persisted_at"])

        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                scope = conn.execute(
                    "SELECT * FROM execution_scope_bindings WHERE execution_id=?",
                    (execution_id,),
                ).fetchone()
                finalization = conn.execute(
                    "SELECT * FROM execution_terminal_finalizations WHERE execution_id=?",
                    (execution_id,),
                ).fetchone()
                seal = conn.execute(
                    "SELECT * FROM execution_audit_seals WHERE execution_id=?",
                    (execution_id,),
                ).fetchone()
                if scope is None:
                    raise DurableExecutionError("EXECUTION_SCOPE_NOT_FOUND")
                if finalization is None:
                    raise DurableExecutionError("TERMINAL_FINALIZATION_NOT_FOUND")
                if seal is None:
                    raise DurableExecutionError("AUDIT_SEAL_NOT_FOUND")
                scope = dict(scope)
                finalization = dict(finalization)
                seal = dict(seal)
                if scope["scope_digest"] != values["scope_digest"]:
                    raise DurableExecutionError("CERTIFICATE_SCOPE_DIGEST_MISMATCH")
                if finalization["terminal_revision"] != revision:
                    raise DurableExecutionError("CERTIFICATE_TERMINAL_REVISION_MISMATCH")
                if finalization["final_execution_state"] != final_state:
                    raise DurableExecutionError("CERTIFICATE_FINAL_STATE_MISMATCH")
                if (
                    finalization["finalization_record_digest"]
                    != values["finalization_record_digest"]
                ):
                    raise DurableExecutionError("CERTIFICATE_FINALIZATION_DIGEST_MISMATCH")
                if (
                    finalization["finops_observation_digest"]
                    != values["finops_observation_digest"]
                ):
                    raise DurableExecutionError("CERTIFICATE_FINOPS_DIGEST_MISMATCH")
                if (
                    finalization["observability_trace_id"]
                    != values["observability_trace_id"]
                ):
                    raise DurableExecutionError("CERTIFICATE_TRACE_MISMATCH")
                if (
                    finalization["pre_terminal_audit_chain_digest"]
                    != values["pre_terminal_audit_chain_digest"]
                ):
                    raise DurableExecutionError("CERTIFICATE_AUDIT_CHAIN_MISMATCH")
                if (
                    seal["audit_seal_manifest_digest"]
                    != values["audit_seal_manifest_digest"]
                    or seal["audit_seal_record_digest"]
                    != values["audit_seal_record_digest"]
                ):
                    raise DurableExecutionError("CERTIFICATE_AUDIT_SEAL_DIGEST_MISMATCH")
                existing = conn.execute(
                    "SELECT * FROM execution_terminal_certificates WHERE execution_id=?",
                    (execution_id,),
                ).fetchone()
                expected = {
                    "terminal_revision": revision,
                    "final_execution_state": final_state,
                    **values,
                    "digest_algorithm": digest_algorithm,
                    "canonical_encoding": canonical_encoding,
                }
                if existing is not None:
                    item = dict(existing)
                    same = all(item[key] == value for key, value in expected.items())
                    if not same:
                        raise DurableExecutionError("TERMINAL_CERTIFICATE_CONFLICT", item)
                    conn.execute("COMMIT")
                    item["replay"] = True
                    item["executes_action"] = False
                    return item
                conn.execute(
                    """
                    INSERT INTO execution_terminal_certificates (
                        execution_id, terminal_revision, final_execution_state,
                        scope_digest, finalization_record_digest,
                        audit_seal_manifest_digest, audit_seal_record_digest,
                        certificate_manifest_digest, certificate_digest,
                        certificate_persistence_record_digest,
                        terminal_evidence_set_digest, finops_observation_digest,
                        observability_trace_id, pre_terminal_audit_chain_digest,
                        digest_algorithm, canonical_encoding, persisted_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        execution_id,
                        revision,
                        final_state,
                        values["scope_digest"],
                        values["finalization_record_digest"],
                        values["audit_seal_manifest_digest"],
                        values["audit_seal_record_digest"],
                        values["certificate_manifest_digest"],
                        values["certificate_digest"],
                        values["certificate_persistence_record_digest"],
                        values["terminal_evidence_set_digest"],
                        values["finops_observation_digest"],
                        values["observability_trace_id"],
                        values["pre_terminal_audit_chain_digest"],
                        digest_algorithm,
                        canonical_encoding,
                        values["persisted_at"],
                    ),
                )
                conn.execute("COMMIT")
            except Exception:
                if conn.in_transaction:
                    conn.execute("ROLLBACK")
                raise
        item = self.get_terminal_certificate(execution_id)
        item["replay"] = False
        return item

    def read_terminal_certificate_snapshot(
        self,
        execution_id: str,
        *,
        owner_id: str,
        tenant_id: str,
        workspace_id: str,
    ) -> dict[str, Any]:
        execution_id = _required_text(execution_id, "EXECUTION_ID_REQUIRED", 96)
        owner = _required_text(owner_id, "OWNER_ID_REQUIRED", 128)
        tenant = _required_text(tenant_id, "TENANT_ID_REQUIRED", 128)
        workspace = _required_text(workspace_id, "WORKSPACE_ID_REQUIRED", 128)
        with self._connect() as conn:
            conn.execute("BEGIN")
            try:
                scope = conn.execute(
                    "SELECT * FROM execution_scope_bindings WHERE execution_id=?",
                    (execution_id,),
                ).fetchone()
                finalization = conn.execute(
                    "SELECT * FROM execution_terminal_finalizations WHERE execution_id=?",
                    (execution_id,),
                ).fetchone()
                seal = conn.execute(
                    "SELECT * FROM execution_audit_seals WHERE execution_id=?",
                    (execution_id,),
                ).fetchone()
                certificate = conn.execute(
                    "SELECT * FROM execution_terminal_certificates WHERE execution_id=?",
                    (execution_id,),
                ).fetchone()
                conn.execute("COMMIT")
            except Exception:
                if conn.in_transaction:
                    conn.execute("ROLLBACK")
                raise

        if scope is None:
            return {
                "state": "UNAVAILABLE",
                "error_code": "EXECUTION_SCOPE_NOT_FOUND",
                "execution_id": execution_id,
                "executes_action": False,
            }
        scope = dict(scope)
        if (
            scope["owner_id"] != owner
            or scope["tenant_id"] != tenant
            or scope["workspace_id"] != workspace
        ):
            return {
                "state": "MISMATCH",
                "error_code": "EXECUTION_SCOPE_MISMATCH",
                "execution_id": execution_id,
                "executes_action": False,
            }
        if finalization is None or seal is None or certificate is None:
            return {
                "state": "UNAVAILABLE",
                "error_code": "TERMINAL_EVIDENCE_CHAIN_INCOMPLETE",
                "execution_id": execution_id,
                "executes_action": False,
            }
        finalization = dict(finalization)
        seal = dict(seal)
        certificate = dict(certificate)
        consistent = (
            finalization["terminal_revision"] == seal["terminal_revision"]
            == certificate["terminal_revision"]
            and finalization["final_execution_state"]
            == certificate["final_execution_state"]
            and scope["scope_digest"] == certificate["scope_digest"]
            and finalization["finalization_record_digest"]
            == seal["finalization_record_digest"]
            == certificate["finalization_record_digest"]
            and seal["audit_seal_manifest_digest"]
            == certificate["audit_seal_manifest_digest"]
            and seal["audit_seal_record_digest"]
            == certificate["audit_seal_record_digest"]
            and finalization["finops_observation_digest"]
            == seal["finops_observation_digest"]
            == certificate["finops_observation_digest"]
            and finalization["observability_trace_id"]
            == seal["observability_trace_id"]
            == certificate["observability_trace_id"]
            and finalization["pre_terminal_audit_chain_digest"]
            == certificate["pre_terminal_audit_chain_digest"]
            and certificate["digest_algorithm"]
            == TERMINAL_EVIDENCE_DIGEST_ALGORITHM
            and certificate["canonical_encoding"]
            == TERMINAL_EVIDENCE_CANONICAL_ENCODING
        )
        if not consistent:
            return {
                "state": "MISMATCH",
                "error_code": "TERMINAL_EVIDENCE_CHAIN_MISMATCH",
                "execution_id": execution_id,
                "executes_action": False,
            }
        return {
            "state": "VERIFIED",
            "execution_id": execution_id,
            "scope": {**scope, "executes_action": False},
            "finalization": {**finalization, "executes_action": False},
            "audit_seal": {**seal, "executes_action": False},
            "certificate": {**certificate, "executes_action": False},
            "executes_action": False,
        }

    def list_dlq(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM executions WHERE state='DLQ' ORDER BY updated_at, execution_id"
            ).fetchall()
        return [self._row(row) for row in rows]

    def count(self) -> int:
        with self._connect() as conn:
            return int(conn.execute("SELECT COUNT(*) FROM executions").fetchone()[0])
