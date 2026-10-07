"""Atomic, content-free storage audit receipts for AION Chat in disposable CI.

The audit hook is executed inside the same PostgreSQL transaction as each
durable mutation. Receipts contain only scope, operation class, actor, result,
timestamp and a SHA-256 evidence digest over an allow-listed set of operational
identifiers. Message bodies, titles, attachment names and secrets are forbidden.

This module remains CI/TEST-only and does not connect to any production
provider, resolve credentials, deploy, arm Workers, execute external actions,
or mutate Core V1.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any
from uuid import uuid4

from aion_chat.models import Scope
from aion_chat.store import StorageUnavailableError
from atlasquant_aion_chat_postgres_migration_rls_restore_ci_v1 import SCHEMA
from atlasquant_aion_chat_production_schema_binding_ci_v1 import (
    HEALTHY,
    ProductionSchemaBoundPostgresBackendCiV1,
    ProductionSchemaBoundPostgresChatStoreCiV1,
)


ALLOWED_AUDIT_EVIDENCE = {
    "CONVERSATION_CREATE": frozenset({
        "conversation_id",
        "created_at",
    }),
    "CONVERSATION_UPDATE": frozenset({
        "conversation_id",
        "archived",
        "updated_at",
    }),
    "MESSAGE_APPEND": frozenset({
        "conversation_id",
        "message_id",
        "sequence",
        "idempotency_key",
    }),
    "MESSAGE_APPEND_IDEMPOTENT": frozenset({
        "conversation_id",
        "message_id",
        "sequence",
        "idempotency_key",
    }),
    "ATTACHMENT_METADATA_ADD": frozenset({
        "conversation_id",
        "attachment_id",
        "digest",
        "size",
    }),
    "CHECKPOINT_SAVE": frozenset({
        "conversation_id",
        "checkpoint_id",
        "through_sequence",
    }),
    "SUMMARY_SAVE": frozenset({
        "conversation_id",
        "summary_id",
        "through_sequence",
        "source_message_ids",
    }),
    "CONVERSATION_DELETE": frozenset({
        "conversation_id",
        "request_id",
        "plan_digest",
        "approval_evidence_digest",
        "messages",
        "idempotency_records",
        "attachments",
        "checkpoints",
        "summaries",
    }),
}

FORBIDDEN_EVIDENCE_TERMS = (
    "content",
    "title",
    "body",
    "prompt",
    "password",
    "secret",
    "token",
    "dsn",
    "api_key",
    "filename",
    "name",
)


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _evidence_digest(
    *,
    operation: str,
    resource_type: str,
    resource_id: str,
    result: str,
    evidence: dict[str, Any],
) -> str:
    allowed = ALLOWED_AUDIT_EVIDENCE.get(operation)
    if allowed is None:
        raise ValueError("audit operation is not allow-listed")
    keys = frozenset(str(key) for key in evidence)
    if keys != allowed:
        raise ValueError("audit evidence keys do not match operation contract")
    for key in keys:
        lowered = key.lower()
        if any(term in lowered for term in FORBIDDEN_EVIDENCE_TERMS):
            raise ValueError("content-bearing audit evidence key forbidden")

    safe = {
        "operation": operation,
        "resource_type": str(resource_type),
        "resource_id": str(resource_id),
        "result": str(result),
        "evidence": evidence,
    }
    return "sha256:" + hashlib.sha256(_canonical_json(safe)).hexdigest()


class AuditedProductionSchemaPostgresBackendCiV1(
    ProductionSchemaBoundPostgresBackendCiV1
):
    """Production-like RLS backend with atomic content-free mutation receipts."""

    def _audit_mutation(
        self,
        cur,
        scope: Scope,
        *,
        operation: str,
        resource_type: str,
        resource_id: str,
        result: str,
        evidence: dict[str, Any],
    ) -> None:
        if not isinstance(scope, Scope):
            raise TypeError("trusted Scope required")
        digest = _evidence_digest(
            operation=operation,
            resource_type=resource_type,
            resource_id=resource_id,
            result=result,
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
                uuid4().hex,
                operation,
                scope.owner_id,
                str(resource_type),
                str(resource_id),
                str(result),
                digest,
            ),
        )

    def list_audit_receipts(
        self,
        scope: Scope,
        *,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        if not isinstance(limit, int) or limit < 1 or limit > 200:
            raise ValueError("audit receipt limit must be within 1..200")
        self.require_healthy()
        conn = self._connection()
        try:
            self._bind_scope(conn, scope)
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT id,operation,actor_id,resource_type,resource_id,"
                    "result,evidence_digest,created_at "
                    f"FROM {SCHEMA}.access_audit "
                    "WHERE owner_id=%s AND tenant_id=%s AND workspace_id=%s "
                    "ORDER BY created_at ASC,id ASC LIMIT %s",
                    (
                        scope.owner_id,
                        scope.tenant_id,
                        scope.workspace_id,
                        limit,
                    ),
                )
                rows = cur.fetchall()
            conn.rollback()
            return [
                {
                    "id": row[0],
                    "operation": row[1],
                    "actor_id": row[2],
                    "resource_type": row[3],
                    "resource_id": row[4],
                    "result": row[5],
                    "evidence_digest": row[6],
                    "created_at": row[7].isoformat()
                    if hasattr(row[7], "isoformat")
                    else str(row[7]),
                }
                for row in rows
            ]
        except (LookupError, ValueError, TypeError):
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
                "audit receipt retrieval unavailable"
            ) from exc
        finally:
            conn.close()


class AuditedProductionSchemaPostgresChatStoreCiV1(
    ProductionSchemaBoundPostgresChatStoreCiV1
):
    def __init__(
        self,
        backend: AuditedProductionSchemaPostgresBackendCiV1,
        *,
        cursor_signing_key: bytes,
    ):
        if not isinstance(backend, AuditedProductionSchemaPostgresBackendCiV1):
            raise TypeError("AuditedProductionSchemaPostgresBackendCiV1 required")
        super().__init__(
            backend,
            cursor_signing_key=cursor_signing_key,
        )


def storage_audit_policy() -> dict[str, Any]:
    return {
        "schema": "ATLASQUANT_AION_CHAT_STORAGE_AUDIT_RECEIPTS_CI_V1",
        "environment_allowed": ["CI", "TEST"],
        "production_allowed": False,
        "atomic_with_mutation": True,
        "content_free": True,
        "message_body_forbidden": True,
        "conversation_title_forbidden": True,
        "attachment_name_forbidden": True,
        "secrets_forbidden": True,
        "audit_update_allowed": False,
        "audit_delete_allowed": False,
        "scope_rls_required": True,
        "actor_bound_to_trusted_scope_owner_v1": True,
        "provider_called": False,
        "billing_executed": False,
        "deploy_executed": False,
        "worker_armed": False,
        "external_action_executed": False,
        "core_checkpoint_write": False,
    }


__all__ = [
    "ALLOWED_AUDIT_EVIDENCE",
    "FORBIDDEN_EVIDENCE_TERMS",
    "AuditedProductionSchemaPostgresBackendCiV1",
    "AuditedProductionSchemaPostgresChatStoreCiV1",
    "storage_audit_policy",
    "_evidence_digest",
    "HEALTHY",
]
