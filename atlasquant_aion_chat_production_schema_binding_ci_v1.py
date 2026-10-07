"""Bind the real AION Chat store to the production-like PostgreSQL schema in CI.

This is not a production connector. It uses only an injected disposable CI
connection factory, SET ROLE to a fixed least-privilege test role, transaction-
local owner/tenant/workspace scope context, and the reviewed aion_chat_v1 schema.

No provider discovery, environment secret lookup, production DSN resolution,
billing, deploy, Worker activation, external action, or Core mutation occurs.
"""
from __future__ import annotations

from typing import Any

import psycopg

from aion_chat.models import Scope
from aion_chat.store import StorageUnavailableError
from atlasquant_aion_chat_ephemeral_postgres_v1 import (
    HEALTHY,
    FAILED,
    BoundCursorCodecV1,
    EphemeralPostgresBackendV1,
    EphemeralPostgresChatStoreV1,
)
from atlasquant_aion_chat_postgres_migration_rls_restore_ci_v1 import (
    MIGRATION_VERSION,
    REQUIRED_CONSTRAINTS,
    REQUIRED_POLICIES,
    RLS_TABLES,
    SCHEMA,
)


CI_APP_ROLE = "aion_chat_app_ci"
APPEND_ONLY_TABLES = frozenset({
    "messages",
    "message_idempotency",
    "attachments",
    "checkpoints",
    "summaries",
    "access_audit",
})


class ProductionSchemaBoundPostgresBackendCiV1(EphemeralPostgresBackendV1):
    """Production-schema/RLS binding restricted to disposable CI/TEST."""

    def __init__(
        self,
        connection_factory,
        *,
        environment: str = "CI",
        role_name: str = CI_APP_ROLE,
    ):
        role = str(role_name or "").strip()
        if role != CI_APP_ROLE:
            raise ValueError("fixed CI least-privilege role required")
        self.role_name = role
        super().__init__(
            connection_factory,
            environment=environment,
            schema=SCHEMA,
        )

    def _connection(self) -> psycopg.Connection:
        conn = super()._connection()
        try:
            with conn.cursor() as cur:
                cur.execute(f"SET ROLE {CI_APP_ROLE}")
            return conn
        except Exception as exc:
            try:
                conn.rollback()
            except Exception:
                pass
            try:
                conn.close()
            except Exception:
                pass
            raise StorageUnavailableError(
                "least-privilege PostgreSQL role binding unavailable"
            ) from exc

    def _bind_scope(self, conn: psycopg.Connection, scope: Scope) -> None:
        if not isinstance(scope, Scope):
            raise TypeError("trusted Scope required")
        owner = str(scope.owner_id or "").strip()
        tenant = str(scope.tenant_id or "").strip()
        workspace = str(scope.workspace_id or "").strip()
        if not owner or not tenant or not workspace:
            raise ValueError("complete trusted scope required")
        with conn.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.owner_id',%s,true)",
                (owner,),
            )
            cur.execute(
                "SELECT set_config('app.tenant_id',%s,true)",
                (tenant,),
            )
            cur.execute(
                "SELECT set_config('app.workspace_id',%s,true)",
                (workspace,),
            )

    def health_report(self) -> dict[str, Any]:
        report = super().health_report()
        report.update(
            backend="production_schema_binding_ci",
            production_schema=SCHEMA,
            expected_migration_version=MIGRATION_VERSION,
            rls_tables_expected=len(RLS_TABLES),
            rls_tables_present=0,
            rls_enabled_and_forced=False,
            policies_expected=len(REQUIRED_POLICIES),
            policies_present=0,
            least_privilege_role_healthy=False,
            append_only_privileges_healthy=False,
            schema_create_denied=False,
            migration_history_denied=False,
            transaction_local_scope_required=True,
        )
        if report["state"] != HEALTHY:
            return report

        conn = None
        try:
            conn = self._connection()
            with conn.cursor() as cur:
                cur.execute("SELECT current_user")
                current_user = str(cur.fetchone()[0])

                cur.execute(
                    "SELECT rolsuper,rolcreatedb,rolcreaterole,"
                    "rolreplication,rolbypassrls "
                    "FROM pg_roles WHERE rolname=current_user"
                )
                role = cur.fetchone()
                role_ok = (
                    current_user == CI_APP_ROLE
                    and role == (False, False, False, False, False)
                )

                cur.execute(
                    "SELECT c.relname,c.relrowsecurity,c.relforcerowsecurity "
                    "FROM pg_class c "
                    "JOIN pg_namespace n ON n.oid=c.relnamespace "
                    "WHERE n.nspname=%s AND c.relname = ANY(%s)",
                    (SCHEMA, list(RLS_TABLES)),
                )
                rls_rows = cur.fetchall()
                rls = {
                    row[0]: bool(row[1]) and bool(row[2])
                    for row in rls_rows
                }
                rls_ok = set(rls) == RLS_TABLES and all(rls.values())

                cur.execute(
                    "SELECT policyname FROM pg_policies "
                    "WHERE schemaname=%s AND policyname = ANY(%s)",
                    (SCHEMA, list(REQUIRED_POLICIES)),
                )
                policies = {row[0] for row in cur.fetchall()}
                policies_ok = policies == REQUIRED_POLICIES

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

                privilege_ok = True
                for table in APPEND_ONLY_TABLES:
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
                    if cur.fetchone() != (True, True, False, False):
                        privilege_ok = False

                cur.execute(
                    "SELECT "
                    "has_table_privilege(current_user,%s,'SELECT'),"
                    "has_table_privilege(current_user,%s,'INSERT'),"
                    "has_table_privilege(current_user,%s,'UPDATE'),"
                    "has_table_privilege(current_user,%s,'DELETE')",
                    (
                        f"{SCHEMA}.conversations",
                        f"{SCHEMA}.conversations",
                        f"{SCHEMA}.conversations",
                        f"{SCHEMA}.conversations",
                    ),
                )
                conversations_privileges_ok = (
                    cur.fetchone() == (True, True, True, False)
                )
            conn.rollback()

            hardened = (
                role_ok
                and rls_ok
                and policies_ok
                and schema_create_denied
                and migration_history_denied
                and privilege_ok
                and conversations_privileges_ok
            )
            report.update(
                state=HEALTHY if hardened else FAILED,
                rls_tables_present=len(rls),
                rls_enabled_and_forced=rls_ok,
                policies_present=len(policies),
                least_privilege_role_healthy=role_ok,
                append_only_privileges_healthy=(
                    privilege_ok and conversations_privileges_ok
                ),
                schema_create_denied=schema_create_denied,
                migration_history_denied=migration_history_denied,
                required_constraints_expected=len(REQUIRED_CONSTRAINTS),
            )
            return report
        except Exception:
            report["state"] = FAILED
            return report
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass


class ProductionSchemaBoundPostgresChatStoreCiV1(EphemeralPostgresChatStoreV1):
    """AionChatStore surface over the production-like schema, still CI-only."""

    def __init__(
        self,
        backend: ProductionSchemaBoundPostgresBackendCiV1,
        *,
        cursor_signing_key: bytes,
    ):
        if not isinstance(backend, ProductionSchemaBoundPostgresBackendCiV1):
            raise TypeError("ProductionSchemaBoundPostgresBackendCiV1 required")
        super().__init__(
            backend,
            cursor_signing_key=cursor_signing_key,
        )


def production_schema_binding_policy() -> dict[str, Any]:
    return {
        "schema": "ATLASQUANT_AION_CHAT_PRODUCTION_SCHEMA_BINDING_CI_V1",
        "postgres_schema": SCHEMA,
        "role": CI_APP_ROLE,
        "environment_allowed": ["CI", "TEST"],
        "production_allowed": False,
        "production_connection_allowed": False,
        "connection_factory_injected": True,
        "environment_read_by_store": False,
        "database_url_read_by_store": False,
        "secret_lookup_by_store": False,
        "set_role_ci_only": True,
        "scope_context_transaction_local": True,
        "application_scope_predicates_preserved": True,
        "forced_rls_required": True,
        "least_privilege_role_required": True,
        "append_only_privilege_profile_required": True,
        "migration_history_access_denied_to_app": True,
        "schema_create_denied_to_app": True,
        "provider_called": False,
        "billing_executed": False,
        "deploy_executed": False,
        "worker_armed": False,
        "external_action_executed": False,
        "core_checkpoint_write": False,
    }


__all__ = [
    "CI_APP_ROLE",
    "APPEND_ONLY_TABLES",
    "ProductionSchemaBoundPostgresBackendCiV1",
    "ProductionSchemaBoundPostgresChatStoreCiV1",
    "production_schema_binding_policy",
    "BoundCursorCodecV1",
]
