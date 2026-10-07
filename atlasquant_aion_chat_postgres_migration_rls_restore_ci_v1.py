"""Production-like PostgreSQL migration/RLS validation for disposable CI only.

This module is intentionally restricted to CI/TEST. It reads a repository
migration artifact, verifies its pinned SHA-256 checksum, serializes migration
application with a PostgreSQL advisory transaction lock, and exposes non-secret
health evidence. It never resolves production credentials, calls a provider,
deploys AtlasQuant, arms a Worker, executes external actions, or writes Core V1.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Callable

import psycopg

from aion_chat.store import StorageUnavailableError


SCHEMA = "aion_chat_v1"
MIGRATION_VERSION = 1
MIGRATION_RELATIVE_PATH = Path(
    "migrations/aion_chat_postgres_v1/0001_initial.sql"
)
EXPECTED_MIGRATION_SHA256 = (
    "d57d5c225c86306afb79cb1d5dba2a6cd8e2838730ac27171243b4ec82664ab2"
)
MIGRATION_LOCK_KEY = 0x41514D4947524154  # "AQMIGRAT", within signed bigint.
APPLIED = "APPLIED"
ALREADY_APPLIED = "ALREADY_APPLIED"
HEALTHY = "healthy"
FAILED = "failed"

RLS_TABLES = frozenset({
    "conversations",
    "messages",
    "message_idempotency",
    "attachments",
    "checkpoints",
    "summaries",
    "access_audit",
})

REQUIRED_POLICIES = frozenset({
    "conversations_scope_policy_v1",
    "messages_scope_policy_v1",
    "idempotency_scope_policy_v1",
    "attachments_scope_policy_v1",
    "checkpoints_scope_policy_v1",
    "summaries_scope_policy_v1",
    "access_audit_scope_policy_v1",
})

REQUIRED_CONSTRAINTS = frozenset({
    "messages_scope_sequence_uq_v1",
    "messages_scope_conversation_message_uq_v1",
    "messages_scope_conversation_fk_v1",
    "idempotency_scope_conversation_fk_v1",
    "idempotency_scope_message_conversation_fk_v1",
    "attachments_scope_conversation_fk_v1",
    "checkpoints_scope_conversation_fk_v1",
    "summaries_scope_conversation_fk_v1",
})

ConnectionFactory = Callable[[], psycopg.Connection]


class MigrationChecksumError(StorageUnavailableError):
    """Migration artifact or applied migration checksum is not trusted."""


def _require_ci_environment(environment: str) -> str:
    normalized = str(environment or "").strip().upper()
    if normalized not in {"CI", "TEST"}:
        raise ValueError("CI/TEST migration environment required")
    return normalized


def _migration_path() -> Path:
    return Path(__file__).resolve().parent / MIGRATION_RELATIVE_PATH


def migration_artifact() -> dict[str, Any]:
    path = _migration_path()
    source = path.read_bytes()
    actual = hashlib.sha256(source).hexdigest()
    return {
        "version": MIGRATION_VERSION,
        "path": str(MIGRATION_RELATIVE_PATH).replace("\\", "/"),
        "expected_sha256": EXPECTED_MIGRATION_SHA256,
        "actual_sha256": actual,
        "checksum_valid": actual == EXPECTED_MIGRATION_SHA256,
        "size_bytes": len(source),
    }


def require_migration_artifact() -> tuple[str, dict[str, Any]]:
    evidence = migration_artifact()
    if not evidence["checksum_valid"]:
        raise MigrationChecksumError("migration artifact checksum mismatch")
    return _migration_path().read_text(encoding="utf-8"), evidence


def _connection(connection_factory: ConnectionFactory) -> psycopg.Connection:
    if not callable(connection_factory):
        raise TypeError("connection factory required")
    try:
        conn = connection_factory()
        conn.autocommit = False
        return conn
    except Exception as exc:
        raise StorageUnavailableError("migration database connection unavailable") from exc


def apply_migration(
    connection_factory: ConnectionFactory,
    *,
    environment: str = "CI",
) -> dict[str, Any]:
    """Apply V1 exactly once inside an explicit CI/TEST transaction."""
    normalized = _require_ci_environment(environment)
    sql, artifact = require_migration_artifact()
    conn = _connection(connection_factory)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT pg_advisory_xact_lock(%s)", (MIGRATION_LOCK_KEY,))
            cur.execute(
                "SELECT to_regclass(%s)",
                (f"{SCHEMA}.schema_migrations",),
            )
            history_exists = cur.fetchone()[0] is not None
            if history_exists:
                cur.execute(
                    f"SELECT checksum FROM {SCHEMA}.schema_migrations "
                    "WHERE version=%s",
                    (MIGRATION_VERSION,),
                )
                row = cur.fetchone()
                if row is None:
                    raise StorageUnavailableError(
                        "migration history exists without expected version"
                    )
                if str(row[0]) != EXPECTED_MIGRATION_SHA256:
                    raise MigrationChecksumError(
                        "applied migration checksum mismatch"
                    )
                conn.rollback()
                return {
                    "state": ALREADY_APPLIED,
                    "version": MIGRATION_VERSION,
                    "checksum": EXPECTED_MIGRATION_SHA256,
                    "environment": normalized,
                    "provider_called": False,
                    "deploy_executed": False,
                    "worker_armed": False,
                    "core_checkpoint_write": False,
                }

            cur.execute(sql)
            cur.execute(
                f"INSERT INTO {SCHEMA}.schema_migrations"
                "(version,checksum) VALUES (%s,%s)",
                (MIGRATION_VERSION, EXPECTED_MIGRATION_SHA256),
            )
        conn.commit()
        return {
            "state": APPLIED,
            "version": MIGRATION_VERSION,
            "checksum": artifact["actual_sha256"],
            "environment": normalized,
            "provider_called": False,
            "deploy_executed": False,
            "worker_armed": False,
            "core_checkpoint_write": False,
        }
    except (MigrationChecksumError, StorageUnavailableError):
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
        raise StorageUnavailableError("migration application failed") from exc
    finally:
        conn.close()


def migration_health_report(
    connection_factory: ConnectionFactory,
    *,
    environment: str = "CI",
) -> dict[str, Any]:
    normalized = _require_ci_environment(environment)
    report = {
        "state": FAILED,
        "environment": normalized,
        "schema": SCHEMA,
        "schema_version": None,
        "migration_version": None,
        "migration_checksum_verified": False,
        "rls_tables_present": 0,
        "rls_tables_expected": len(RLS_TABLES),
        "rls_enabled_and_forced": False,
        "policies_present": 0,
        "policies_expected": len(REQUIRED_POLICIES),
        "constraints_present": 0,
        "constraints_expected": len(REQUIRED_CONSTRAINTS),
        "transaction_healthy": False,
        "provider_called": False,
        "deploy_executed": False,
        "worker_armed": False,
        "core_checkpoint_write": False,
    }
    conn = None
    try:
        conn = _connection(connection_factory)
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT version FROM {SCHEMA}.schema_meta WHERE name=%s",
                ("aion_chat",),
            )
            row = cur.fetchone()
            schema_version = int(row[0]) if row else None

            cur.execute(
                f"SELECT version,checksum FROM {SCHEMA}.schema_migrations "
                "WHERE version=%s",
                (MIGRATION_VERSION,),
            )
            migration = cur.fetchone()
            migration_version = int(migration[0]) if migration else None
            migration_checksum = str(migration[1]) if migration else ""

            cur.execute(
                "SELECT c.relname,c.relrowsecurity,c.relforcerowsecurity "
                "FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
                "WHERE n.nspname=%s AND c.relname = ANY(%s)",
                (SCHEMA, list(RLS_TABLES)),
            )
            rls_rows = cur.fetchall()
            rls_by_table = {
                row[0]: bool(row[1]) and bool(row[2])
                for row in rls_rows
            }

            cur.execute(
                "SELECT policyname FROM pg_policies "
                "WHERE schemaname=%s AND policyname = ANY(%s)",
                (SCHEMA, list(REQUIRED_POLICIES)),
            )
            policies = {row[0] for row in cur.fetchall()}

            cur.execute(
                "SELECT conname FROM pg_constraint c "
                "JOIN pg_namespace n ON n.oid=c.connamespace "
                "WHERE n.nspname=%s AND conname = ANY(%s)",
                (SCHEMA, list(REQUIRED_CONSTRAINTS)),
            )
            constraints = {row[0] for row in cur.fetchall()}

            cur.execute("SAVEPOINT aion_migration_health_probe")
            cur.execute("SELECT 1")
            transaction_healthy = cur.fetchone() == (1,)
            cur.execute("ROLLBACK TO SAVEPOINT aion_migration_health_probe")
            cur.execute("RELEASE SAVEPOINT aion_migration_health_probe")
        conn.rollback()

        rls_ok = (
            set(rls_by_table) == RLS_TABLES
            and all(rls_by_table.values())
        )
        policies_ok = policies == REQUIRED_POLICIES
        constraints_ok = constraints == REQUIRED_CONSTRAINTS
        checksum_ok = (
            migration_version == MIGRATION_VERSION
            and migration_checksum == EXPECTED_MIGRATION_SHA256
        )
        healthy = (
            schema_version == MIGRATION_VERSION
            and checksum_ok
            and rls_ok
            and policies_ok
            and constraints_ok
            and transaction_healthy
        )
        report.update(
            state=HEALTHY if healthy else FAILED,
            schema_version=schema_version,
            migration_version=migration_version,
            migration_checksum_verified=checksum_ok,
            rls_tables_present=len(rls_by_table),
            rls_enabled_and_forced=rls_ok,
            policies_present=len(policies),
            constraints_present=len(constraints),
            transaction_healthy=transaction_healthy,
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


RESTORE_FIXTURE_SCOPE = ("restore-owner", "restore-tenant", "restore-workspace")
RESTORE_FIXTURE_CONVERSATION_ID = "restore-proof-conversation-v1"
RESTORE_FIXTURE_AUDIT_ID = "restore-proof-audit-v1"
RESTORE_FIXTURE_DIGEST = (
    "sha256:9d44fc01e5f5bd6b6d6b807067b9329d88cba9c70b11d28f9fd7d95ef39d60d8"
)


def seed_restore_fixture(
    connection_factory: ConnectionFactory,
    *,
    environment: str = "CI",
) -> dict[str, Any]:
    """Seed deterministic non-secret rows before a disposable CI backup drill."""
    _require_ci_environment(environment)
    owner, tenant, workspace = RESTORE_FIXTURE_SCOPE
    conn = _connection(connection_factory)
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"INSERT INTO {SCHEMA}.conversations"
                "(owner_id,tenant_id,workspace_id,id,created_at,updated_at,"
                "archived,title,data) "
                "VALUES (%s,%s,%s,%s,%s,%s,FALSE,%s,%s::jsonb) "
                "ON CONFLICT(owner_id,tenant_id,workspace_id,id) DO NOTHING",
                (
                    owner,
                    tenant,
                    workspace,
                    RESTORE_FIXTURE_CONVERSATION_ID,
                    "2026-10-07T00:00:00+00:00",
                    "2026-10-07T00:00:00+00:00",
                    "restore proof",
                    '{"fixture":"restore-v1"}',
                ),
            )
            cur.execute(
                f"INSERT INTO {SCHEMA}.access_audit"
                "(owner_id,tenant_id,workspace_id,id,operation,actor_id,"
                "result,evidence_digest) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s) "
                "ON CONFLICT(owner_id,tenant_id,workspace_id,id) DO NOTHING",
                (
                    owner,
                    tenant,
                    workspace,
                    RESTORE_FIXTURE_AUDIT_ID,
                    "RESTORE_DRILL_FIXTURE",
                    "ci",
                    "SEEDED",
                    RESTORE_FIXTURE_DIGEST,
                ),
            )
        conn.commit()
        return {
            "state": "RESTORE_FIXTURE_SEEDED",
            "conversation_id": RESTORE_FIXTURE_CONVERSATION_ID,
            "audit_id": RESTORE_FIXTURE_AUDIT_ID,
            "evidence_digest": RESTORE_FIXTURE_DIGEST,
        }
    except Exception as exc:
        try:
            conn.rollback()
        except Exception:
            pass
        raise StorageUnavailableError("restore fixture seed failed") from exc
    finally:
        conn.close()


def restore_fixture_report(
    connection_factory: ConnectionFactory,
    *,
    environment: str = "CI",
) -> dict[str, Any]:
    """Verify migration/RLS health and deterministic rows after CI restore."""
    normalized = _require_ci_environment(environment)
    health = migration_health_report(
        connection_factory,
        environment=normalized,
    )
    report = {
        "state": FAILED,
        "environment": normalized,
        "migration_health": health["state"],
        "conversation_restored": False,
        "audit_restored": False,
        "digest_verified": False,
        "provider_called": False,
        "deploy_executed": False,
        "worker_armed": False,
        "core_checkpoint_write": False,
    }
    if health["state"] != HEALTHY:
        return report

    owner, tenant, workspace = RESTORE_FIXTURE_SCOPE
    conn = None
    try:
        conn = _connection(connection_factory)
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT data FROM {SCHEMA}.conversations "
                "WHERE owner_id=%s AND tenant_id=%s AND workspace_id=%s AND id=%s",
                (
                    owner,
                    tenant,
                    workspace,
                    RESTORE_FIXTURE_CONVERSATION_ID,
                ),
            )
            conversation = cur.fetchone()
            cur.execute(
                f"SELECT evidence_digest FROM {SCHEMA}.access_audit "
                "WHERE owner_id=%s AND tenant_id=%s AND workspace_id=%s AND id=%s",
                (
                    owner,
                    tenant,
                    workspace,
                    RESTORE_FIXTURE_AUDIT_ID,
                ),
            )
            audit = cur.fetchone()
        conn.rollback()
        conversation_ok = bool(conversation)
        audit_ok = bool(audit)
        digest_ok = audit_ok and str(audit[0]) == RESTORE_FIXTURE_DIGEST
        report.update(
            state=(
                HEALTHY
                if conversation_ok and audit_ok and digest_ok
                else FAILED
            ),
            conversation_restored=conversation_ok,
            audit_restored=audit_ok,
            digest_verified=digest_ok,
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


def migration_policy() -> dict[str, Any]:
    return {
        "schema": "ATLASQUANT_AION_CHAT_POSTGRES_MIGRATION_RLS_RESTORE_CI_V1",
        "environment_allowed": ["CI", "TEST"],
        "migration_version": MIGRATION_VERSION,
        "migration_sha256": EXPECTED_MIGRATION_SHA256,
        "advisory_lock_required": True,
        "application_startup_auto_migration": False,
        "rls_required": True,
        "force_rls_required": True,
        "least_privilege_role_required": True,
        "transaction_local_scope_context_required": True,
        "application_delete_privilege_default": False,
        "message_update_privilege_default": False,
        "audit_append_only_role_profile": True,
        "backup_restore_drill_required": True,
        "production_connection_allowed": False,
        "provider_called": False,
        "billing_executed": False,
        "deploy_executed": False,
        "worker_armed": False,
        "external_action_executed": False,
        "core_checkpoint_write": False,
    }


__all__ = [
    "SCHEMA",
    "MIGRATION_VERSION",
    "EXPECTED_MIGRATION_SHA256",
    "MIGRATION_LOCK_KEY",
    "APPLIED",
    "ALREADY_APPLIED",
    "HEALTHY",
    "FAILED",
    "RLS_TABLES",
    "REQUIRED_POLICIES",
    "REQUIRED_CONSTRAINTS",
    "MigrationChecksumError",
    "migration_artifact",
    "require_migration_artifact",
    "apply_migration",
    "migration_health_report",
    "seed_restore_fixture",
    "restore_fixture_report",
    "RESTORE_FIXTURE_SCOPE",
    "RESTORE_FIXTURE_CONVERSATION_ID",
    "RESTORE_FIXTURE_AUDIT_ID",
    "RESTORE_FIXTURE_DIGEST",
    "migration_policy",
]
