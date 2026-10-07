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
    "0bb91049a51177bc8fbe42654c82497fae95714042028ff831cf2c87a9cfca50"
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
    "migration_policy",
]
