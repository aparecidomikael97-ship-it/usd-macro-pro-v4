"""Fail-closed retention and controlled conversation deletion for disposable CI.

Deletion is deliberately separate from the normal application role. The
retention role can inspect one scoped archived conversation, produce a
content-free plan digest, and execute a single approved deletion only when the
caller supplies the exact plan digest plus external approval evidence.

The deletion audit receipt is inserted in the same PostgreSQL transaction and
uses the request_id as the durable audit event id. This supports explicit
reconciliation if COMMIT acknowledgement is lost.

No automatic TTL, batch purge, production credentials, provider calls, deploy,
Worker activation, external action, or Core mutation is permitted here.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Callable

import psycopg

from aion_chat.models import Scope
from aion_chat.store import StorageUnavailableError
from atlasquant_aion_chat_postgres_migration_rls_restore_ci_v1 import SCHEMA
from atlasquant_aion_chat_storage_audit_receipts_ci_v1 import _evidence_digest


RETENTION_ROLE = "aion_chat_retention_ci"
APPROVE_DELETE = "APPROVE_CONVERSATION_DELETE"
PLAN_VERSION = 1
DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9_-]{16,128}$")
CHILD_TABLES = (
    "messages",
    "message_idempotency",
    "attachments",
    "checkpoints",
    "summaries",
)

READY = "READY"
BLOCKED = "BLOCKED"
COMMITTED = "COMMITTED"
ALREADY_COMMITTED = "ALREADY_COMMITTED"


class RetentionBlockedError(RuntimeError):
    pass


class StaleRetentionPlanError(RetentionBlockedError):
    pass


class RetentionCommitOutcomeUnknownError(RuntimeError):
    def __init__(self, request_id: str, conversation_id: str):
        super().__init__("retention commit outcome unknown")
        self.request_id = request_id
        self.conversation_id = conversation_id


@dataclass(frozen=True)
class RetentionDeleteRequestV1:
    request_id: str
    conversation_id: str
    authorized_by: str
    decision: str
    approval_evidence_digest: str
    expected_plan_digest: str

    def __post_init__(self):
        if not REQUEST_ID_RE.fullmatch(str(self.request_id or "")):
            raise ValueError("bounded retention request_id required")
        if not isinstance(self.conversation_id, str) or not self.conversation_id.strip():
            raise ValueError("conversation_id required")
        if not isinstance(self.authorized_by, str) or not self.authorized_by.strip():
            raise ValueError("authorized_by required")
        if self.decision != APPROVE_DELETE:
            raise ValueError("explicit APPROVE_CONVERSATION_DELETE required")
        if not DIGEST_RE.fullmatch(str(self.approval_evidence_digest or "")):
            raise ValueError("approval evidence digest required")
        if not DIGEST_RE.fullmatch(str(self.expected_plan_digest or "")):
            raise ValueError("expected plan digest required")


ConnectionFactory = Callable[[], psycopg.Connection]


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _sha256(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical(value)).hexdigest()


class ControlledRetentionExecutorCiV1:
    def __init__(
        self,
        connection_factory: ConnectionFactory,
        *,
        environment: str = "CI",
        role_name: str = RETENTION_ROLE,
    ):
        if not callable(connection_factory):
            raise TypeError("connection factory required")
        normalized = str(environment or "").strip().upper()
        if normalized not in {"CI", "TEST"}:
            raise ValueError("CI/TEST retention environment required")
        if str(role_name or "").strip() != RETENTION_ROLE:
            raise ValueError("fixed CI retention role required")
        self._connect = connection_factory
        self.environment = normalized
        self.role_name = RETENTION_ROLE
        self.commit_outcome_unknown_once = False

    def _connection(self) -> psycopg.Connection:
        try:
            conn = self._connect()
            conn.autocommit = False
            with conn.cursor() as cur:
                cur.execute(f"SET ROLE {RETENTION_ROLE}")
            return conn
        except Exception as exc:
            try:
                conn.close()
            except Exception:
                pass
            raise StorageUnavailableError(
                "retention database connection unavailable"
            ) from exc

    @staticmethod
    def _bind_scope(conn: psycopg.Connection, scope: Scope) -> None:
        if not isinstance(scope, Scope):
            raise TypeError("trusted Scope required")
        with conn.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.owner_id',%s,true)",
                (scope.owner_id,),
            )
            cur.execute(
                "SELECT set_config('app.tenant_id',%s,true)",
                (scope.tenant_id,),
            )
            cur.execute(
                "SELECT set_config('app.workspace_id',%s,true)",
                (scope.workspace_id,),
            )

    def health_report(self) -> dict[str, Any]:
        report = {
            "state": BLOCKED,
            "environment": self.environment,
            "role": RETENTION_ROLE,
            "least_privilege_role_healthy": False,
            "conversation_delete_only": False,
            "child_delete_denied": False,
            "audit_append_only": False,
            "schema_create_denied": False,
            "migration_history_denied": False,
            "automatic_deletion_enabled": False,
            "production_allowed": False,
            "provider_called": False,
            "billing_executed": False,
            "deploy_executed": False,
            "worker_armed": False,
            "external_action_executed": False,
            "core_checkpoint_write": False,
        }
        conn = None
        try:
            conn = self._connection()
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT rolsuper,rolcreatedb,rolcreaterole,"
                    "rolreplication,rolbypassrls "
                    "FROM pg_roles WHERE rolname=current_user"
                )
                role = cur.fetchone()
                role_ok = role == (False, False, False, False, False)

                cur.execute(
                    "SELECT "
                    "has_table_privilege(current_user,%s,'SELECT'),"
                    "has_table_privilege(current_user,%s,'DELETE'),"
                    "has_table_privilege(current_user,%s,'INSERT'),"
                    "has_table_privilege(current_user,%s,'UPDATE')",
                    (
                        f"{SCHEMA}.conversations",
                        f"{SCHEMA}.conversations",
                        f"{SCHEMA}.conversations",
                        f"{SCHEMA}.conversations",
                    ),
                )
                conversation_privileges = cur.fetchone()
                conversation_ok = conversation_privileges == (
                    True,
                    True,
                    False,
                    False,
                )

                child_ok = True
                for table in CHILD_TABLES:
                    cur.execute(
                        "SELECT "
                        "has_table_privilege(current_user,%s,'SELECT'),"
                        "has_table_privilege(current_user,%s,'INSERT'),"
                        "has_table_privilege(current_user,%s,'UPDATE'),"
                        "has_table_privilege(current_user,%s,'DELETE')",
                        (
                            f"{SCHEMA}.{table}",
                            f"{SCHEMA}.{table}",
                            f"{SCHEMA}.{table}",
                            f"{SCHEMA}.{table}",
                        ),
                    )
                    if cur.fetchone() != (True, False, False, False):
                        child_ok = False

                cur.execute(
                    "SELECT "
                    "has_table_privilege(current_user,%s,'SELECT'),"
                    "has_table_privilege(current_user,%s,'INSERT'),"
                    "has_table_privilege(current_user,%s,'UPDATE'),"
                    "has_table_privilege(current_user,%s,'DELETE')",
                    (
                        f"{SCHEMA}.access_audit",
                        f"{SCHEMA}.access_audit",
                        f"{SCHEMA}.access_audit",
                        f"{SCHEMA}.access_audit",
                    ),
                )
                audit_ok = cur.fetchone() == (True, True, False, False)

                cur.execute(
                    "SELECT has_schema_privilege(current_user,%s,'CREATE')",
                    (SCHEMA,),
                )
                schema_create_denied = cur.fetchone() == (False,)

                cur.execute(
                    "SELECT has_table_privilege(current_user,%s,'SELECT')",
                    (f"{SCHEMA}.schema_migrations",),
                )
                migration_history_denied = cur.fetchone() == (False,)
            conn.rollback()

            healthy = (
                role_ok
                and conversation_ok
                and child_ok
                and audit_ok
                and schema_create_denied
                and migration_history_denied
            )
            report.update(
                state=READY if healthy else BLOCKED,
                least_privilege_role_healthy=role_ok,
                conversation_delete_only=conversation_ok,
                child_delete_denied=child_ok,
                audit_append_only=audit_ok,
                schema_create_denied=schema_create_denied,
                migration_history_denied=migration_history_denied,
            )
            return report
        except Exception:
            return report
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass

    def require_healthy(self) -> dict[str, Any]:
        report = self.health_report()
        if report["state"] != READY:
            raise StorageUnavailableError("retention role health is not proven")
        return report

    @staticmethod
    def _counts(cur, scope: Scope, conversation_id: str) -> dict[str, int]:
        counts: dict[str, int] = {}
        for table in CHILD_TABLES:
            cur.execute(
                f"SELECT count(*) FROM {SCHEMA}.{table} "
                "WHERE owner_id=%s AND tenant_id=%s AND workspace_id=%s "
                "AND conversation_id=%s",
                (
                    scope.owner_id,
                    scope.tenant_id,
                    scope.workspace_id,
                    conversation_id,
                ),
            )
            counts[table] = int(cur.fetchone()[0])
        return counts

    @staticmethod
    def _plan_payload(
        scope: Scope,
        conversation_id: str,
        counts: dict[str, int],
    ) -> dict[str, Any]:
        return {
            "v": PLAN_VERSION,
            "owner_id": scope.owner_id,
            "tenant_id": scope.tenant_id,
            "workspace_id": scope.workspace_id,
            "conversation_id": conversation_id,
            "requires_archived": True,
            "counts": counts,
        }

    def plan_delete(
        self,
        scope: Scope,
        conversation_id: str,
    ) -> dict[str, Any]:
        self.require_healthy()
        conversation_id = str(conversation_id or "").strip()
        if not conversation_id:
            raise ValueError("conversation_id required")
        conn = self._connection()
        try:
            self._bind_scope(conn, scope)
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT archived FROM {SCHEMA}.conversations "
                    "WHERE owner_id=%s AND tenant_id=%s AND workspace_id=%s "
                    "AND id=%s",
                    (
                        scope.owner_id,
                        scope.tenant_id,
                        scope.workspace_id,
                        conversation_id,
                    ),
                )
                row = cur.fetchone()
                if row is None:
                    raise LookupError("conversation unavailable")
                if not bool(row[0]):
                    raise RetentionBlockedError(
                        "conversation must be archived before deletion planning"
                    )
                counts = self._counts(cur, scope, conversation_id)
            conn.rollback()
            payload = self._plan_payload(scope, conversation_id, counts)
            return {
                "state": READY,
                "conversation_id": conversation_id,
                "counts": counts,
                "plan_digest": _sha256(payload),
                "automatic": False,
                "delete_executed": False,
            }
        except (LookupError, ValueError, TypeError, RetentionBlockedError):
            try:
                conn.rollback()
            except Exception:
                pass
            raise
        except Exception as exc:
            try:
                conn.rollback()
            except Exception:
                pass
            raise StorageUnavailableError("retention plan unavailable") from exc
        finally:
            conn.close()

    @staticmethod
    def _find_receipt(cur, scope: Scope, request_id: str):
        cur.execute(
            f"SELECT operation,resource_type,resource_id,result,evidence_digest "
            f"FROM {SCHEMA}.access_audit "
            "WHERE owner_id=%s AND tenant_id=%s AND workspace_id=%s AND id=%s",
            (
                scope.owner_id,
                scope.tenant_id,
                scope.workspace_id,
                request_id,
            ),
        )
        return cur.fetchone()

    def execute_delete(
        self,
        scope: Scope,
        request: RetentionDeleteRequestV1,
    ) -> dict[str, Any]:
        self.require_healthy()
        if not isinstance(scope, Scope):
            raise TypeError("trusted Scope required")
        if not isinstance(request, RetentionDeleteRequestV1):
            raise TypeError("RetentionDeleteRequestV1 required")
        if request.authorized_by != scope.owner_id:
            raise RetentionBlockedError(
                "delete approval actor must match trusted owner scope"
            )

        conn = self._connection()
        try:
            self._bind_scope(conn, scope)
            with conn.cursor() as cur:
                prior = self._find_receipt(cur, scope, request.request_id)
                if prior is not None:
                    operation, resource_type, resource_id, result, evidence_digest = prior
                    if (
                        operation != "CONVERSATION_DELETE"
                        or resource_type != "conversation"
                        or resource_id != request.conversation_id
                        or result != COMMITTED
                        or not DIGEST_RE.fullmatch(str(evidence_digest or ""))
                    ):
                        raise RetentionBlockedError(
                            "retention request_id conflicts with prior audit receipt"
                        )
                    cur.execute(
                        f"SELECT 1 FROM {SCHEMA}.conversations "
                        "WHERE owner_id=%s AND tenant_id=%s AND workspace_id=%s "
                        "AND id=%s",
                        (
                            scope.owner_id,
                            scope.tenant_id,
                            scope.workspace_id,
                            request.conversation_id,
                        ),
                    )
                    if cur.fetchone() is not None:
                        raise RetentionBlockedError(
                            "prior committed delete receipt conflicts with live conversation"
                        )
                    conn.rollback()
                    return {
                        "state": ALREADY_COMMITTED,
                        "request_id": request.request_id,
                        "conversation_id": request.conversation_id,
                        "audit_receipt_id": request.request_id,
                    }

                cur.execute(
                    f"SELECT archived FROM {SCHEMA}.conversations "
                    "WHERE owner_id=%s AND tenant_id=%s AND workspace_id=%s "
                    "AND id=%s FOR UPDATE",
                    (
                        scope.owner_id,
                        scope.tenant_id,
                        scope.workspace_id,
                        request.conversation_id,
                    ),
                )
                row = cur.fetchone()
                if row is None:
                    raise LookupError("conversation unavailable")
                if not bool(row[0]):
                    raise RetentionBlockedError(
                        "conversation must remain archived at execution"
                    )

                counts = self._counts(cur, scope, request.conversation_id)
                payload = self._plan_payload(
                    scope,
                    request.conversation_id,
                    counts,
                )
                actual_plan_digest = _sha256(payload)
                if actual_plan_digest != request.expected_plan_digest:
                    raise StaleRetentionPlanError(
                        "retention plan changed; new explicit approval required"
                    )

                evidence = {
                    "conversation_id": request.conversation_id,
                    "request_id": request.request_id,
                    "plan_digest": actual_plan_digest,
                    "approval_evidence_digest": request.approval_evidence_digest,
                    "messages": counts["messages"],
                    "idempotency_records": counts["message_idempotency"],
                    "attachments": counts["attachments"],
                    "checkpoints": counts["checkpoints"],
                    "summaries": counts["summaries"],
                }
                digest = _evidence_digest(
                    operation="CONVERSATION_DELETE",
                    resource_type="conversation",
                    resource_id=request.conversation_id,
                    result=COMMITTED,
                    evidence=evidence,
                )

                cur.execute(
                    f"INSERT INTO {SCHEMA}.access_audit"
                    "(owner_id,tenant_id,workspace_id,id,operation,actor_id,"
                    "resource_type,resource_id,result,evidence_digest) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (
                        scope.owner_id,
                        scope.tenant_id,
                        scope.workspace_id,
                        request.request_id,
                        "CONVERSATION_DELETE",
                        scope.owner_id,
                        "conversation",
                        request.conversation_id,
                        COMMITTED,
                        digest,
                    ),
                )
                cur.execute(
                    f"DELETE FROM {SCHEMA}.conversations "
                    "WHERE owner_id=%s AND tenant_id=%s AND workspace_id=%s "
                    "AND id=%s",
                    (
                        scope.owner_id,
                        scope.tenant_id,
                        scope.workspace_id,
                        request.conversation_id,
                    ),
                )
                if cur.rowcount != 1:
                    raise StorageUnavailableError(
                        "conversation delete rowcount is not exactly one"
                    )

            try:
                conn.commit()
            except Exception as exc:
                raise RetentionCommitOutcomeUnknownError(
                    request.request_id,
                    request.conversation_id,
                ) from exc

            if self.commit_outcome_unknown_once:
                self.commit_outcome_unknown_once = False
                raise RetentionCommitOutcomeUnknownError(
                    request.request_id,
                    request.conversation_id,
                )

            return {
                "state": COMMITTED,
                "request_id": request.request_id,
                "conversation_id": request.conversation_id,
                "audit_receipt_id": request.request_id,
                "counts": counts,
                "plan_digest": actual_plan_digest,
            }
        except RetentionCommitOutcomeUnknownError:
            raise
        except (
            LookupError,
            ValueError,
            TypeError,
            RetentionBlockedError,
            StorageUnavailableError,
        ):
            try:
                conn.rollback()
            except Exception:
                pass
            raise
        except Exception as exc:
            try:
                conn.rollback()
            except Exception:
                pass
            raise StorageUnavailableError(
                "controlled retention delete failed"
            ) from exc
        finally:
            conn.close()

    def reconcile_delete(
        self,
        scope: Scope,
        *,
        request_id: str,
        conversation_id: str,
    ) -> dict[str, Any]:
        self.require_healthy()
        if not REQUEST_ID_RE.fullmatch(str(request_id or "")):
            raise ValueError("bounded retention request_id required")
        conn = self._connection()
        try:
            self._bind_scope(conn, scope)
            with conn.cursor() as cur:
                receipt = self._find_receipt(cur, scope, request_id)
                cur.execute(
                    f"SELECT 1 FROM {SCHEMA}.conversations "
                    "WHERE owner_id=%s AND tenant_id=%s AND workspace_id=%s "
                    "AND id=%s",
                    (
                        scope.owner_id,
                        scope.tenant_id,
                        scope.workspace_id,
                        conversation_id,
                    ),
                )
                live = cur.fetchone() is not None
            conn.rollback()

            if receipt is None:
                return {
                    "state": "NOT_PROVEN",
                    "request_id": request_id,
                    "conversation_id": conversation_id,
                    "receipt_found": False,
                    "conversation_live": live,
                }

            operation, resource_type, resource_id, result, evidence_digest = receipt
            proven = (
                operation == "CONVERSATION_DELETE"
                and resource_type == "conversation"
                and resource_id == conversation_id
                and result == COMMITTED
                and DIGEST_RE.fullmatch(str(evidence_digest or "")) is not None
                and not live
            )
            return {
                "state": COMMITTED if proven else "CONFLICT",
                "request_id": request_id,
                "conversation_id": conversation_id,
                "receipt_found": True,
                "conversation_live": live,
            }
        finally:
            conn.close()


def retention_policy() -> dict[str, Any]:
    return {
        "schema": "ATLASQUANT_AION_CHAT_RETENTION_CONTROLLED_DELETE_CI_V1",
        "environment_allowed": ["CI", "TEST"],
        "production_allowed": False,
        "automatic_ttl_enabled": False,
        "batch_delete_enabled": False,
        "single_conversation_only": True,
        "archive_required": True,
        "explicit_approval_required": True,
        "approval_evidence_digest_required": True,
        "plan_digest_required": True,
        "stale_plan_fails_closed": True,
        "separate_retention_role_required": True,
        "normal_application_delete_allowed": False,
        "audit_receipt_atomic_with_delete": True,
        "unknown_commit_requires_reconciliation": True,
        "provider_called": False,
        "billing_executed": False,
        "deploy_executed": False,
        "worker_armed": False,
        "external_action_executed": False,
        "core_checkpoint_write": False,
    }


__all__ = [
    "RETENTION_ROLE",
    "APPROVE_DELETE",
    "RetentionDeleteRequestV1",
    "RetentionBlockedError",
    "StaleRetentionPlanError",
    "RetentionCommitOutcomeUnknownError",
    "ControlledRetentionExecutorCiV1",
    "retention_policy",
    "READY",
    "BLOCKED",
    "COMMITTED",
    "ALREADY_COMMITTED",
]
