"""Short-lived PostgreSQL migration identity lifecycle for disposable CI.

The migration identity is directly authenticated, least-privilege at cluster
level, TLS verify-full attested, allowed to create the reviewed application
schema, and then sealed by revoking database CREATE and disabling LOGIN.

This module never resolves passwords, environment variables, provider secrets,
or production connection details.
"""
from __future__ import annotations

from typing import Any, Callable

import psycopg
from psycopg.conninfo import conninfo_to_dict

from aion_chat.store import StorageUnavailableError
from atlasquant_aion_chat_postgres_migration_rls_restore_ci_v1 import SCHEMA


CI_MIGRATION_ROLE = "aion_chat_migrator_ci_login"
MIGRATION_IDENTITY_ACTIVE = "MIGRATION_IDENTITY_ACTIVE_IN_CI"
MIGRATION_IDENTITY_SEALED = "MIGRATION_IDENTITY_SEALED_IN_CI"
FAILED = "failed"

ConnectionFactory = Callable[[], psycopg.Connection]


class AttestedMigrationConnectionFactoryCiV1:
    """Return only a direct, verified-TLS, least-privilege migrator session."""

    def __init__(
        self,
        connection_factory: ConnectionFactory,
        *,
        environment: str = "CI",
    ):
        if not callable(connection_factory):
            raise TypeError("connection factory required")
        normalized = str(environment or "").strip().upper()
        if normalized not in {"CI", "TEST"}:
            raise ValueError("CI/TEST migration identity environment required")
        self._connect = connection_factory
        self.environment = normalized

    def __call__(self) -> psycopg.Connection:
        conn = None
        try:
            conn = self._connect()
            conn.autocommit = False

            params = conninfo_to_dict(conn.info.dsn)
            if (
                str(params.get("sslmode") or "").strip().lower()
                != "verify-full"
                or not str(params.get("sslrootcert") or "").strip()
            ):
                raise StorageUnavailableError(
                    "verify-full migration TLS policy is not proven"
                )

            with conn.cursor() as cur:
                cur.execute("SELECT session_user,current_user")
                identity = tuple(str(value) for value in cur.fetchone())
                cur.execute(
                    "SELECT rolsuper,rolcreatedb,rolcreaterole,"
                    "rolinherit,rolreplication,rolbypassrls,rolcanlogin "
                    "FROM pg_roles WHERE rolname=current_user"
                )
                role = cur.fetchone()
                cur.execute(
                    "SELECT s.ssl,s.version,s.cipher,"
                    "inet_client_addr() IS NOT NULL "
                    "FROM pg_stat_ssl s WHERE s.pid=pg_backend_pid()"
                )
                tls = cur.fetchone()

            if identity != (CI_MIGRATION_ROLE, CI_MIGRATION_ROLE):
                raise StorageUnavailableError(
                    "direct migration PostgreSQL identity is not proven"
                )
            if role != (
                False,
                False,
                False,
                False,
                False,
                False,
                True,
            ):
                raise StorageUnavailableError(
                    "least-privilege migration role flags are not proven"
                )
            if (
                tls is None
                or tls[0] is not True
                or not str(tls[1] or "").strip()
                or not str(tls[2] or "").strip()
                or tls[3] is not True
            ):
                raise StorageUnavailableError(
                    "verified migration TLS transport is not proven"
                )
            return conn
        except Exception as exc:
            if conn is not None:
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
                "migration identity attestation unavailable"
            ) from exc


def active_migration_identity_report(
    connection_factory: ConnectionFactory,
    *,
    environment: str = "CI",
) -> dict[str, Any]:
    """Attest the short-lived identity before the reviewed migration."""
    normalized = str(environment or "").strip().upper()
    if normalized not in {"CI", "TEST"}:
        raise ValueError("CI/TEST migration identity environment required")

    report = {
        "state": FAILED,
        "environment": normalized,
        "role": CI_MIGRATION_ROLE,
        "direct_identity": False,
        "verify_full_tls": False,
        "database_create_temporarily_allowed": False,
        "superuser": None,
        "createdb": None,
        "createrole": None,
        "replication": None,
        "bypassrls": None,
        "can_login": None,
        "provider_called": False,
        "production_connection_allowed": False,
        "deploy_executed": False,
        "worker_armed": False,
        "core_checkpoint_write": False,
    }

    conn = None
    try:
        attested = AttestedMigrationConnectionFactoryCiV1(
            connection_factory,
            environment=normalized,
        )
        conn = attested()
        with conn.cursor() as cur:
            cur.execute("SELECT session_user,current_user")
            identity = tuple(str(value) for value in cur.fetchone())
            cur.execute(
                "SELECT rolsuper,rolcreatedb,rolcreaterole,"
                "rolreplication,rolbypassrls,rolcanlogin "
                "FROM pg_roles WHERE rolname=current_user"
            )
            flags = cur.fetchone()
            cur.execute(
                "SELECT has_database_privilege(current_user,"
                "current_database(),'CREATE')"
            )
            can_create_schema = cur.fetchone() == (True,)
        conn.rollback()

        direct_ok = identity == (CI_MIGRATION_ROLE, CI_MIGRATION_ROLE)
        role_ok = flags == (False, False, False, False, False, True)
        healthy = direct_ok and role_ok and can_create_schema
        report.update(
            state=MIGRATION_IDENTITY_ACTIVE if healthy else FAILED,
            direct_identity=direct_ok,
            verify_full_tls=healthy,
            database_create_temporarily_allowed=can_create_schema,
            superuser=flags[0] if flags else None,
            createdb=flags[1] if flags else None,
            createrole=flags[2] if flags else None,
            replication=flags[3] if flags else None,
            bypassrls=flags[4] if flags else None,
            can_login=flags[5] if flags else None,
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


def sealed_migration_identity_report(
    admin_connection_factory: ConnectionFactory,
    *,
    environment: str = "CI",
) -> dict[str, Any]:
    """Attest post-migration ownership while standing login/CREATE are removed."""
    normalized = str(environment or "").strip().upper()
    if normalized not in {"CI", "TEST"}:
        raise ValueError("CI/TEST migration identity environment required")
    if not callable(admin_connection_factory):
        raise TypeError("admin connection factory required")

    report = {
        "state": FAILED,
        "environment": normalized,
        "role": CI_MIGRATION_ROLE,
        "can_login": None,
        "database_create_revoked": False,
        "schema_owned_by_migrator": False,
        "all_application_tables_owned_by_migrator": False,
        "application_table_count": 0,
        "provider_called": False,
        "production_connection_allowed": False,
        "deploy_executed": False,
        "worker_armed": False,
        "core_checkpoint_write": False,
    }

    conn = None
    try:
        conn = admin_connection_factory()
        conn.autocommit = False
        with conn.cursor() as cur:
            cur.execute(
                "SELECT rolcanlogin,rolsuper,rolcreatedb,rolcreaterole,"
                "rolreplication,rolbypassrls "
                "FROM pg_roles WHERE rolname=%s",
                (CI_MIGRATION_ROLE,),
            )
            flags = cur.fetchone()
            cur.execute(
                "SELECT has_database_privilege(%s,current_database(),'CREATE')",
                (CI_MIGRATION_ROLE,),
            )
            can_create_schema = cur.fetchone() == (True,)
            cur.execute(
                "SELECT pg_get_userbyid(nspowner) "
                "FROM pg_namespace WHERE nspname=%s",
                (SCHEMA,),
            )
            schema_owner_row = cur.fetchone()
            schema_owner = (
                str(schema_owner_row[0]) if schema_owner_row else ""
            )
            cur.execute(
                "SELECT tableowner,count(*) "
                "FROM pg_tables WHERE schemaname=%s "
                "GROUP BY tableowner ORDER BY tableowner",
                (SCHEMA,),
            )
            ownership_rows = cur.fetchall()
        conn.rollback()

        can_login = flags[0] if flags else None
        cluster_flags_ok = bool(
            flags
            and flags == (False, False, False, False, False, False)
        )
        table_count = sum(int(row[1]) for row in ownership_rows)
        all_tables_owned = bool(
            table_count
            and len(ownership_rows) == 1
            and str(ownership_rows[0][0]) == CI_MIGRATION_ROLE
        )
        schema_owned = schema_owner == CI_MIGRATION_ROLE
        sealed = (
            cluster_flags_ok
            and not can_create_schema
            and schema_owned
            and all_tables_owned
        )
        report.update(
            state=MIGRATION_IDENTITY_SEALED if sealed else FAILED,
            can_login=can_login,
            database_create_revoked=not can_create_schema,
            schema_owned_by_migrator=schema_owned,
            all_application_tables_owned_by_migrator=all_tables_owned,
            application_table_count=table_count,
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


def migration_identity_lifecycle_policy() -> dict[str, Any]:
    return {
        "schema": "ATLASQUANT_AION_CHAT_MIGRATION_IDENTITY_LIFECYCLE_CI_V1",
        "role": CI_MIGRATION_ROLE,
        "environment_allowed": ["CI", "TEST"],
        "direct_login_required": True,
        "verify_full_tls_required": True,
        "temporary_database_create_required": True,
        "post_migration_database_create_revoked": True,
        "post_migration_login_disabled": True,
        "migration_role_is_application_role": False,
        "superuser_allowed": False,
        "createdb_allowed": False,
        "createrole_allowed": False,
        "replication_allowed": False,
        "bypassrls_allowed": False,
        "password_read_by_module": False,
        "environment_read_by_module": False,
        "provider_secret_read_by_module": False,
        "production_connection_allowed": False,
        "provider_called": False,
        "billing_executed": False,
        "deploy_executed": False,
        "worker_armed": False,
        "external_action_executed": False,
        "core_checkpoint_write": False,
    }


__all__ = [
    "CI_MIGRATION_ROLE",
    "MIGRATION_IDENTITY_ACTIVE",
    "MIGRATION_IDENTITY_SEALED",
    "AttestedMigrationConnectionFactoryCiV1",
    "active_migration_identity_report",
    "sealed_migration_identity_report",
    "migration_identity_lifecycle_policy",
]
