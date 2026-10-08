"""Direct least-privilege PostgreSQL login binding for AION Chat in disposable CI.

This stage proves the AION Chat store can connect as the application identity
itself instead of opening an administrator connection and switching roles.

Only an injected connection factory is accepted. The module never reads a DSN,
password, environment variable, provider secret, or Render configuration.
Production access remains forbidden.
"""
from __future__ import annotations

from typing import Any

import psycopg

from aion_chat.store import StorageUnavailableError
from atlasquant_aion_chat_ephemeral_postgres_v1 import (
    EphemeralPostgresBackendV1,
    HEALTHY,
    FAILED,
)
from atlasquant_aion_chat_postgres_migration_rls_restore_ci_v1 import (
    MIGRATION_VERSION,
    REQUIRED_CONSTRAINTS,
    REQUIRED_POLICIES,
    RLS_TABLES,
    SCHEMA,
)
from atlasquant_aion_chat_production_schema_binding_ci_v1 import (
    APPEND_ONLY_TABLES,
)
from atlasquant_aion_chat_storage_audit_receipts_ci_v1 import (
    AuditedProductionSchemaPostgresBackendCiV1,
    AuditedProductionSchemaPostgresChatStoreCiV1,
)


CI_DIRECT_APP_ROLE = "aion_chat_app_ci_login"


class DirectLoginAuditedPostgresBackendCiV1(
    AuditedProductionSchemaPostgresBackendCiV1
):
    """Audited production-schema backend authenticated directly as app role."""

    def __init__(
        self,
        connection_factory,
        *,
        environment: str = "CI",
    ):
        self.role_name = CI_DIRECT_APP_ROLE
        # Deliberately bypass ProductionSchemaBoundPostgresBackendCiV1.__init__:
        # that earlier CI stage models least privilege through SET ROLE. This
        # stage proves the stronger direct-login boundary instead.
        EphemeralPostgresBackendV1.__init__(
            self,
            connection_factory,
            environment=environment,
            schema=SCHEMA,
        )

    def _connection(self) -> psycopg.Connection:
        conn = EphemeralPostgresBackendV1._connection(self)
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT session_user,current_user")
                identity = tuple(str(value) for value in cur.fetchone())
            if identity != (CI_DIRECT_APP_ROLE, CI_DIRECT_APP_ROLE):
                raise StorageUnavailableError(
                    "direct PostgreSQL application identity is not proven"
                )
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
            if isinstance(exc, StorageUnavailableError):
                raise
            raise StorageUnavailableError(
                "direct PostgreSQL application identity unavailable"
            ) from exc

    def health_report(self) -> dict[str, Any]:
        report = EphemeralPostgresBackendV1.health_report(self)
        report.update(
            backend="direct_login_audited_postgres_ci",
            production_schema=SCHEMA,
            expected_migration_version=MIGRATION_VERSION,
            direct_login_role=CI_DIRECT_APP_ROLE,
            direct_identity_healthy=False,
            role_can_login=False,
            least_privilege_role_healthy=False,
            rls_tables_expected=len(RLS_TABLES),
            rls_tables_present=0,
            rls_enabled_and_forced=False,
            policies_expected=len(REQUIRED_POLICIES),
            policies_present=0,
            append_only_privileges_healthy=False,
            conversations_privileges_healthy=False,
            schema_meta_read_only=False,
            schema_create_denied=False,
            migration_history_denied=False,
            transaction_local_scope_required=True,
            set_role_required=False,
        )
        if report["state"] != HEALTHY:
            return report

        conn = None
        try:
            conn = self._connection()
            with conn.cursor() as cur:
                cur.execute("SELECT session_user,current_user")
                identity = tuple(str(value) for value in cur.fetchone())
                identity_ok = identity == (
                    CI_DIRECT_APP_ROLE,
                    CI_DIRECT_APP_ROLE,
                )

                cur.execute(
                    "SELECT rolsuper,rolcreatedb,rolcreaterole,"
                    "rolinherit,rolreplication,rolbypassrls,rolcanlogin "
                    "FROM pg_roles WHERE rolname=current_user"
                )
                role = cur.fetchone()
                role_ok = role == (
                    False,
                    False,
                    False,
                    False,
                    False,
                    False,
                    True,
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

                cur.execute(
                    "SELECT "
                    "has_table_privilege(current_user,%s,'SELECT'),"
                    "has_table_privilege(current_user,%s,'INSERT'),"
                    "has_table_privilege(current_user,%s,'UPDATE'),"
                    "has_table_privilege(current_user,%s,'DELETE')",
                    (
                        f"{SCHEMA}.schema_meta",
                        f"{SCHEMA}.schema_meta",
                        f"{SCHEMA}.schema_meta",
                        f"{SCHEMA}.schema_meta",
                    ),
                )
                schema_meta_read_only = (
                    cur.fetchone() == (True, False, False, False)
                )

                append_only_ok = True
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
                        append_only_ok = False

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
                conversations_ok = cur.fetchone() == (
                    True,
                    True,
                    True,
                    False,
                )
            conn.rollback()

            hardened = (
                identity_ok
                and role_ok
                and rls_ok
                and policies_ok
                and schema_create_denied
                and migration_history_denied
                and schema_meta_read_only
                and append_only_ok
                and conversations_ok
            )
            report.update(
                state=HEALTHY if hardened else FAILED,
                direct_identity_healthy=identity_ok,
                role_can_login=bool(role and role[-1]),
                least_privilege_role_healthy=role_ok,
                rls_tables_present=len(rls),
                rls_enabled_and_forced=rls_ok,
                policies_present=len(policies),
                append_only_privileges_healthy=append_only_ok,
                conversations_privileges_healthy=conversations_ok,
                schema_meta_read_only=schema_meta_read_only,
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


class DirectLoginAuditedPostgresChatStoreCiV1(
    AuditedProductionSchemaPostgresChatStoreCiV1
):
    """AionChatStore over a direct-login least-privilege CI identity."""

    def __init__(
        self,
        backend: DirectLoginAuditedPostgresBackendCiV1,
        *,
        cursor_signing_key: bytes,
    ):
        if not isinstance(backend, DirectLoginAuditedPostgresBackendCiV1):
            raise TypeError("DirectLoginAuditedPostgresBackendCiV1 required")
        super().__init__(
            backend,
            cursor_signing_key=cursor_signing_key,
        )


def direct_app_role_connection_policy() -> dict[str, Any]:
    return {
        "schema": "ATLASQUANT_AION_CHAT_DIRECT_APP_ROLE_CONNECTION_CI_V1",
        "postgres_schema": SCHEMA,
        "direct_login_role": CI_DIRECT_APP_ROLE,
        "environment_allowed": ["CI", "TEST"],
        "production_allowed": False,
        "production_connection_allowed": False,
        "connection_factory_injected": True,
        "dsn_read_by_store": False,
        "password_read_by_store": False,
        "environment_read_by_store": False,
        "provider_secret_read_by_store": False,
        "set_role_used": False,
        "direct_login_identity_required": True,
        "transaction_local_scope_required": True,
        "forced_rls_required": True,
        "least_privilege_required": True,
        "audit_receipts_preserved": True,
        "normal_app_delete_allowed": False,
        "migration_history_access_allowed": False,
        "schema_create_allowed": False,
        "provider_called": False,
        "billing_executed": False,
        "deploy_executed": False,
        "worker_armed": False,
        "external_action_executed": False,
        "core_checkpoint_write": False,
    }


__all__ = [
    "CI_DIRECT_APP_ROLE",
    "DirectLoginAuditedPostgresBackendCiV1",
    "DirectLoginAuditedPostgresChatStoreCiV1",
    "direct_app_role_connection_policy",
]
