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

    def list_dlq(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM executions WHERE state='DLQ' ORDER BY updated_at, execution_id"
            ).fetchall()
        return [self._row(row) for row in rows]

    def count(self) -> int:
        with self._connect() as conn:
            return int(conn.execute("SELECT COUNT(*) FROM executions").fetchone()[0])
