"""Immutable candidate manifest for AION Chat PostgreSQL schema V1.

This freezes the reviewed V1 migration artifact in CI before any production
database exists. It does not apply a production migration or authorize deploy.
After this candidate freeze, a schema change must use a new numbered migration
rather than editing 0001 in place.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Callable

import psycopg

from aion_chat.store import StorageUnavailableError
from atlasquant_aion_chat_postgres_migration_rls_restore_ci_v1 import (
    EXPECTED_MIGRATION_SHA256,
    MIGRATION_VERSION,
    SCHEMA,
    HEALTHY,
    migration_health_report,
)

MIGRATION_PATH = Path("migrations/aion_chat_postgres_v1/0001_initial.sql")
CANDIDATE_SHA256 = (
    "7dd72d75365862f54c81110027430011f8ac8f81ce629f500cbbd9aa0c00c50c"
)
CANDIDATE_STATE = "POSTGRES_SCHEMA_CANDIDATE_FROZEN_IN_CI"
FAILED = "failed"

EXPECTED_TABLES = frozenset({
    "schema_migrations",
    "schema_meta",
    "conversations",
    "messages",
    "message_idempotency",
    "attachments",
    "checkpoints",
    "summaries",
    "access_audit",
})

EXPECTED_ACCESS_AUDIT_COLUMNS = (
    "owner_id",
    "tenant_id",
    "workspace_id",
    "id",
    "operation",
    "actor_id",
    "resource_type",
    "resource_id",
    "result",
    "evidence_digest",
    "created_at",
)

EXPECTED_INDEXES = frozenset({
    "conversations_pkey",
    "conversations_scope_recency_v1",
    "messages_pkey",
    "messages_scope_sequence_uq_v1",
    "messages_scope_conversation_message_uq_v1",
    "messages_scope_history_v1",
    "message_idempotency_pkey",
    "attachments_pkey",
    "checkpoints_pkey",
    "checkpoints_scope_latest_v1",
    "summaries_pkey",
    "summaries_scope_latest_v1",
    "access_audit_pkey",
    "access_audit_scope_time_v1",
    "access_audit_scope_resource_v1",
    "schema_migrations_pkey",
    "schema_meta_pkey",
})

ConnectionFactory = Callable[[], psycopg.Connection]


def _migration_file() -> Path:
    return Path(__file__).resolve().parent / MIGRATION_PATH


def candidate_artifact_report() -> dict[str, Any]:
    source = _migration_file().read_bytes()
    actual = hashlib.sha256(source).hexdigest()
    return {
        "state": CANDIDATE_STATE if actual == CANDIDATE_SHA256 else FAILED,
        "version": MIGRATION_VERSION,
        "path": str(MIGRATION_PATH).replace("\\", "/"),
        "expected_sha256": CANDIDATE_SHA256,
        "actual_sha256": actual,
        "runner_expected_sha256": EXPECTED_MIGRATION_SHA256,
        "runner_hash_matches_candidate": (
            EXPECTED_MIGRATION_SHA256 == CANDIDATE_SHA256
        ),
        "immutable_after_candidate_freeze": True,
        "future_schema_changes_require_new_numbered_migration": True,
    }


def schema_candidate_report(
    connection_factory: ConnectionFactory,
    *,
    environment: str = "CI",
) -> dict[str, Any]:
    normalized = str(environment or "").strip().upper()
    if normalized not in {"CI", "TEST"}:
        raise ValueError("CI/TEST schema candidate environment required")
    if not callable(connection_factory):
        raise TypeError("connection factory required")

    artifact = candidate_artifact_report()
    report = {
        "state": FAILED,
        "environment": normalized,
        "artifact_state": artifact["state"],
        "migration_sha256_verified": False,
        "migration_health": FAILED,
        "tables_exact": False,
        "access_audit_columns_exact": False,
        "required_indexes_present": False,
        "extra_tables": [],
        "missing_tables": [],
        "missing_indexes": [],
        "production_allowed": False,
        "provider_called": False,
        "billing_executed": False,
        "deploy_executed": False,
        "worker_armed": False,
        "external_action_executed": False,
        "core_checkpoint_write": False,
    }
    if (
        artifact["state"] != CANDIDATE_STATE
        or not artifact["runner_hash_matches_candidate"]
    ):
        return report

    health = migration_health_report(
        connection_factory,
        environment=normalized,
    )
    report["migration_health"] = health["state"]
    if health["state"] != HEALTHY:
        return report

    conn = None
    try:
        conn = connection_factory()
        conn.autocommit = False
        with conn.cursor() as cur:
            cur.execute(
                "SELECT tablename FROM pg_tables WHERE schemaname=%s",
                (SCHEMA,),
            )
            tables = {row[0] for row in cur.fetchall()}

            cur.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema=%s AND table_name='access_audit'
                ORDER BY ordinal_position
                """,
                (SCHEMA,),
            )
            audit_columns = tuple(row[0] for row in cur.fetchall())

            cur.execute(
                "SELECT indexname FROM pg_indexes WHERE schemaname=%s",
                (SCHEMA,),
            )
            indexes = {row[0] for row in cur.fetchall()}

            cur.execute(
                f"SELECT version,checksum FROM {SCHEMA}.schema_migrations "
                "WHERE version=%s",
                (MIGRATION_VERSION,),
            )
            migration_row = cur.fetchone()
        conn.rollback()

        missing_tables = sorted(EXPECTED_TABLES - tables)
        extra_tables = sorted(tables - EXPECTED_TABLES)
        missing_indexes = sorted(EXPECTED_INDEXES - indexes)
        migration_sha_ok = (
            migration_row is not None
            and int(migration_row[0]) == MIGRATION_VERSION
            and str(migration_row[1]) == CANDIDATE_SHA256
        )
        tables_exact = not missing_tables and not extra_tables
        audit_exact = audit_columns == EXPECTED_ACCESS_AUDIT_COLUMNS
        indexes_ok = not missing_indexes

        frozen = (
            migration_sha_ok
            and tables_exact
            and audit_exact
            and indexes_ok
        )
        report.update(
            state=CANDIDATE_STATE if frozen else FAILED,
            migration_sha256_verified=migration_sha_ok,
            tables_exact=tables_exact,
            access_audit_columns_exact=audit_exact,
            required_indexes_present=indexes_ok,
            extra_tables=extra_tables,
            missing_tables=missing_tables,
            missing_indexes=missing_indexes,
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


def schema_candidate_freeze_policy() -> dict[str, Any]:
    return {
        "schema": "ATLASQUANT_AION_CHAT_POSTGRES_SCHEMA_CANDIDATE_FREEZE_V1",
        "migration_version": MIGRATION_VERSION,
        "migration_sha256": CANDIDATE_SHA256,
        "candidate_state": CANDIDATE_STATE,
        "initial_migration_immutable_after_freeze": True,
        "future_changes_require_new_numbered_migration": True,
        "production_allowed": False,
        "production_migration_executed": False,
        "provider_called": False,
        "billing_executed": False,
        "deploy_executed": False,
        "worker_armed": False,
        "external_action_executed": False,
        "core_checkpoint_write": False,
    }


__all__ = [
    "MIGRATION_PATH",
    "CANDIDATE_SHA256",
    "CANDIDATE_STATE",
    "EXPECTED_TABLES",
    "EXPECTED_ACCESS_AUDIT_COLUMNS",
    "EXPECTED_INDEXES",
    "candidate_artifact_report",
    "schema_candidate_report",
    "schema_candidate_freeze_policy",
]
