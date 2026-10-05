"""Atomic physical repository for AION durable-task snapshots.

The pure atlasquant_aion_durable_tasks module remains the transition engine.
This repository is only the authoritative physical CAS boundary required for
multi-process persistence.

It performs no external action and never resumes/executes a task automatically.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from typing import Any, Callable, Mapping

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_durable_tasks import (
    MAX_TASKS,
    TERMINAL_TASK_STATES,
    durable_tasks_digest,
    normalize_durable_task,
    normalize_durable_tasks,
)

SCHEMA = "ATLASQUANT_AION_DURABLE_TASK_REPOSITORY_V1"


class DurableTaskRepositoryError(ValueError):
    def __init__(self, code: str, *, task_id: str = "", revision: int | None = None):
        super().__init__(code)
        self.code = code
        self.result = {
            "schema": SCHEMA,
            "status": "CONFLICT" if "REVISION" in code or "CAS" in code else "BLOCKED",
            "error_code": code,
            "task_id": task_id,
            "revision": revision,
            "executes_action": False,
            "automatic_resume_executes": False,
        }


class DurableTaskRepositoryIntegrityError(DurableTaskRepositoryError):
    pass


class SimulatedTaskStoreCrash(RuntimeError):
    pass


def _canonical(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def _digest_text(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def _scope(scope: Scope) -> tuple[str, str, str]:
    if not isinstance(scope, Scope):
        raise TypeError("trusted Scope required")
    return scope.owner_id, scope.tenant_id, scope.workspace_id


def _exact_revision(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise DurableTaskRepositoryError("REVISION_INVALID")
    return value


class DurableTaskRepository:
    def __init__(
        self,
        store: SQLiteChatStore,
        scope: Scope,
        *,
        fault_injector: Callable[[str, Mapping[str, Any]], None] | None = None,
    ):
        if not isinstance(store, SQLiteChatStore):
            raise TypeError("SQLiteChatStore required")
        store.require_healthy()
        _scope(scope)
        self.store = store
        self.db = store.db
        self.scope = scope
        self.fault_injector = fault_injector
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        with self.db:
            self.db.executescript("""
            CREATE TABLE IF NOT EXISTS aion_durable_task_repository(
                owner TEXT NOT NULL,
                tenant TEXT NOT NULL,
                workspace TEXT NOT NULL,
                task_id TEXT NOT NULL,
                revision INTEGER NOT NULL,
                task_digest TEXT NOT NULL,
                task_state TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                payload TEXT NOT NULL,
                PRIMARY KEY(owner,tenant,workspace,task_id)
            );
            CREATE INDEX IF NOT EXISTS aion_durable_task_repo_scope_revision
              ON aion_durable_task_repository(owner,tenant,workspace,revision,task_id);
            """)

    def _scope_args(self) -> tuple[str, str, str]:
        return _scope(self.scope)

    def _fault(self, stage: str, context: Mapping[str, Any]) -> None:
        if callable(self.fault_injector):
            self.fault_injector(stage, deepcopy(dict(context)))

    @staticmethod
    def _encoded(task: Mapping[str, Any]) -> tuple[dict[str, Any], str, str]:
        item = normalize_durable_task(task)
        encoded = _canonical(item)
        return item, encoded, _digest_text(encoded)

    def _row(self, task_id: str):
        return self.db.execute(
            """SELECT * FROM aion_durable_task_repository
               WHERE owner=? AND tenant=? AND workspace=? AND task_id=?""",
            (*self._scope_args(), str(task_id)),
        ).fetchone()

    def _verify_row(self, row) -> dict[str, Any]:
        if row is None:
            raise LookupError("durable task unavailable")
        task_id = str(row["task_id"])
        try:
            raw = json.loads(row["payload"])
        except Exception as exc:
            raise DurableTaskRepositoryIntegrityError(
                "TASK_PAYLOAD_JSON_INVALID",
                task_id=task_id,
                revision=int(row["revision"]),
            ) from exc
        if not isinstance(raw, Mapping):
            raise DurableTaskRepositoryIntegrityError(
                "TASK_PAYLOAD_NOT_MAPPING",
                task_id=task_id,
                revision=int(row["revision"]),
            )
        canonical_raw = _canonical(dict(raw))
        stored_digest = str(row["task_digest"] or "")
        if _digest_text(canonical_raw) != stored_digest:
            raise DurableTaskRepositoryIntegrityError(
                "TASK_DIGEST_MISMATCH",
                task_id=task_id,
                revision=int(row["revision"]),
            )
        item = normalize_durable_task(raw)
        normalized_encoded = _canonical(item)
        if normalized_encoded != canonical_raw:
            raise DurableTaskRepositoryIntegrityError(
                "TASK_PAYLOAD_NOT_CANONICAL",
                task_id=task_id,
                revision=int(row["revision"]),
            )
        if item["durable_task_id"] != task_id:
            raise DurableTaskRepositoryIntegrityError(
                "TASK_ID_BINDING_MISMATCH",
                task_id=task_id,
                revision=int(row["revision"]),
            )
        if item["revision"] != int(row["revision"]):
            raise DurableTaskRepositoryIntegrityError(
                "TASK_REVISION_BINDING_MISMATCH",
                task_id=task_id,
                revision=int(row["revision"]),
            )
        if item["state"] != row["task_state"]:
            raise DurableTaskRepositoryIntegrityError(
                "TASK_STATE_BINDING_MISMATCH",
                task_id=task_id,
                revision=int(row["revision"]),
            )
        if str(item["updated_at"]) != str(row["updated_at"]):
            raise DurableTaskRepositoryIntegrityError(
                "TASK_UPDATED_AT_BINDING_MISMATCH",
                task_id=task_id,
                revision=int(row["revision"]),
            )
        return item

    def create(self, task: Mapping[str, Any]) -> dict[str, Any]:
        item, encoded, digest = self._encoded(task)
        task_id = item["durable_task_id"]
        if item["revision"] != 1:
            raise DurableTaskRepositoryError(
                "CREATE_REVISION_MUST_BE_ONE",
                task_id=task_id,
                revision=item["revision"],
            )
        self.db.execute("BEGIN IMMEDIATE")
        try:
            existing = self._row(task_id)
            if existing is not None:
                current = self._verify_row(existing)
                if existing["task_digest"] == digest and _canonical(current) == encoded:
                    self.db.commit()
                    return {
                        "schema": SCHEMA,
                        "status": "IDEMPOTENT",
                        "task": current,
                        "revision": current["revision"],
                        "task_digest": digest,
                        "executes_action": False,
                        "automatic_resume_executes": False,
                    }
                raise DurableTaskRepositoryError(
                    "TASK_ID_COLLISION",
                    task_id=task_id,
                    revision=int(existing["revision"]),
                )
            count = int(
                self.db.execute(
                    """SELECT count(*) FROM aion_durable_task_repository
                       WHERE owner=? AND tenant=? AND workspace=?""",
                    self._scope_args(),
                ).fetchone()[0]
            )
            if count >= MAX_TASKS:
                raise DurableTaskRepositoryError("TASK_CAPACITY_REACHED")
            self.db.execute(
                """INSERT INTO aion_durable_task_repository(
                    owner,tenant,workspace,task_id,revision,task_digest,
                    task_state,updated_at,payload
                ) VALUES (?,?,?,?,?,?,?,?,?)""",
                (
                    *self._scope_args(),
                    task_id,
                    item["revision"],
                    digest,
                    item["state"],
                    item["updated_at"],
                    encoded,
                ),
            )
            self._fault("BEFORE_CREATE_COMMIT", {
                "task_id": task_id,
                "revision": item["revision"],
                "task_digest": digest,
            })
            self.db.commit()
        except Exception:
            if self.db.in_transaction:
                self.db.rollback()
            raise
        self._fault("AFTER_CREATE_COMMIT", {
            "task_id": task_id,
            "revision": item["revision"],
            "task_digest": digest,
        })
        return {
            "schema": SCHEMA,
            "status": "CREATED",
            "task": deepcopy(item),
            "revision": item["revision"],
            "task_digest": digest,
            "executes_action": False,
            "automatic_resume_executes": False,
        }

    def load(self, task_id: Any) -> dict[str, Any]:
        task_key = str(task_id or "").strip()
        if not task_key:
            raise ValueError("task_id required")
        return deepcopy(self._verify_row(self._row(task_key)))

    def list(self) -> list[dict[str, Any]]:
        rows = self.db.execute(
            """SELECT * FROM aion_durable_task_repository
               WHERE owner=? AND tenant=? AND workspace=?
               ORDER BY updated_at,task_id""",
            self._scope_args(),
        ).fetchall()
        return [deepcopy(self._verify_row(row)) for row in rows]

    def compare_and_swap(
        self,
        candidate: Mapping[str, Any],
        *,
        expected_revision: Any,
    ) -> dict[str, Any]:
        expected = _exact_revision(expected_revision)
        item, encoded, digest = self._encoded(candidate)
        task_id = item["durable_task_id"]
        self.db.execute("BEGIN IMMEDIATE")
        try:
            row = self._row(task_id)
            if row is None:
                raise LookupError("durable task unavailable")
            current = self._verify_row(row)
            current_revision = int(row["revision"])

            # Lost response / retry after a successful commit.
            if (
                item["revision"] == current_revision
                and digest == row["task_digest"]
                and encoded == row["payload"]
            ):
                self.db.commit()
                return {
                    "schema": SCHEMA,
                    "status": "IDEMPOTENT",
                    "task": deepcopy(current),
                    "revision": current_revision,
                    "task_digest": digest,
                    "executes_action": False,
                    "automatic_resume_executes": False,
                }

            if current_revision != expected:
                raise DurableTaskRepositoryError(
                    "REVISION_CONFLICT",
                    task_id=task_id,
                    revision=current_revision,
                )
            if item["revision"] != expected + 1:
                raise DurableTaskRepositoryError(
                    "CAS_REVISION_MUST_INCREMENT_ONCE",
                    task_id=task_id,
                    revision=item["revision"],
                )
            if current["state"] in TERMINAL_TASK_STATES and item["state"] != current["state"]:
                raise DurableTaskRepositoryError(
                    "TASK_TERMINAL",
                    task_id=task_id,
                    revision=current_revision,
                )

            cursor = self.db.execute(
                """UPDATE aion_durable_task_repository
                   SET revision=?,task_digest=?,task_state=?,updated_at=?,payload=?
                   WHERE owner=? AND tenant=? AND workspace=? AND task_id=? AND revision=?""",
                (
                    item["revision"],
                    digest,
                    item["state"],
                    item["updated_at"],
                    encoded,
                    *self._scope_args(),
                    task_id,
                    expected,
                ),
            )
            if cursor.rowcount != 1:
                raise DurableTaskRepositoryError(
                    "CAS_LOST_RACE",
                    task_id=task_id,
                    revision=current_revision,
                )
            self._fault("BEFORE_CAS_COMMIT", {
                "task_id": task_id,
                "expected_revision": expected,
                "new_revision": item["revision"],
                "task_digest": digest,
            })
            self.db.commit()
        except Exception:
            if self.db.in_transaction:
                self.db.rollback()
            raise
        self._fault("AFTER_CAS_COMMIT", {
            "task_id": task_id,
            "expected_revision": expected,
            "new_revision": item["revision"],
            "task_digest": digest,
        })
        return {
            "schema": SCHEMA,
            "status": "UPDATED",
            "task": deepcopy(item),
            "revision": item["revision"],
            "task_digest": digest,
            "executes_action": False,
            "automatic_resume_executes": False,
        }

    def checkpoint_projection(self) -> dict[str, Any]:
        """Build a read-only Checkpoint Mestre projection from physical truth."""
        tasks = self.list()
        integrity = self.integrity_report()
        if integrity["state"] != "MATCH":
            raise DurableTaskRepositoryIntegrityError("REPOSITORY_INTEGRITY_MISMATCH")
        return {
            "records": tasks,
            "digest": durable_tasks_digest(tasks),
            "repository_digest": integrity["repository_digest"],
            "source": "ATOMIC_DURABLE_TASK_REPOSITORY",
            "authoritative_store": "SQLITE_CAS",
            "projection_only": True,
            "executes_action": False,
            "automatic_resume_executes": False,
        }

    def verify_checkpoint_projection(
        self,
        projection: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        expected = self.checkpoint_projection()
        raw = dict(projection or {})
        records = normalize_durable_tasks(
            raw.get("records") if isinstance(raw.get("records"), (list, tuple)) else []
        )
        observed_digest = str(raw.get("digest") or "")
        observed_repo = str(raw.get("repository_digest") or "")
        blockers = []
        if durable_tasks_digest(records) != observed_digest:
            blockers.append("CHECKPOINT_TASK_DIGEST_INVALID")
        if observed_digest != expected["digest"]:
            blockers.append("CHECKPOINT_TASK_DIGEST_STALE")
        if observed_repo != expected["repository_digest"]:
            blockers.append("CHECKPOINT_REPOSITORY_DIGEST_STALE")
        if records != expected["records"]:
            blockers.append("CHECKPOINT_TASK_PAYLOAD_STALE")
        return {
            "schema": SCHEMA,
            "state": "MATCH" if not blockers else "MISMATCH",
            "blockers": sorted(set(blockers)),
            "expected_digest": expected["digest"],
            "observed_digest": observed_digest,
            "expected_repository_digest": expected["repository_digest"],
            "observed_repository_digest": observed_repo,
            "physical_repository_authoritative": True,
            "checkpoint_is_projection": True,
            "executes_action": False,
            "automatic_resume_executes": False,
        }

    def integrity_report(self) -> dict[str, Any]:
        blockers: list[str] = []
        checked = 0
        rows = self.db.execute(
            """SELECT * FROM aion_durable_task_repository
               WHERE owner=? AND tenant=? AND workspace=?
               ORDER BY task_id""",
            self._scope_args(),
        ).fetchall()
        for row in rows:
            checked += 1
            try:
                self._verify_row(row)
            except DurableTaskRepositoryIntegrityError as exc:
                blockers.append(exc.code + ":" + str(row["task_id"]))
        fingerprint = _digest_text(_canonical([
            {
                "task_id": row["task_id"],
                "revision": int(row["revision"]),
                "task_digest": row["task_digest"],
            }
            for row in rows
        ]))
        return {
            "schema": SCHEMA,
            "state": "MATCH" if not blockers else "MISMATCH",
            "blockers": blockers,
            "tasks": checked,
            "repository_digest": fingerprint,
            "scope": {
                "owner_id": self.scope.owner_id,
                "tenant_id": self.scope.tenant_id,
                "workspace_id": self.scope.workspace_id,
            },
            "atomic_cas": True,
            "multi_process_boundary": "SQLITE_TRANSACTION",
            "restores_state_only": True,
            "executes_action": False,
            "automatic_resume_executes": False,
        }


__all__ = [
    "SCHEMA",
    "DurableTaskRepository",
    "DurableTaskRepositoryError",
    "DurableTaskRepositoryIntegrityError",
    "SimulatedTaskStoreCrash",
]
