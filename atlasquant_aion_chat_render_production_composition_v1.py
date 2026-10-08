"""Fail-closed production PostgreSQL composition for AION Chat.

The storage/backend layer never resolves environment variables or provider
secrets itself. The trusted host must inject a mapping containing only the
approved AION Chat PostgreSQL configuration.

Production persistence is disabled unless the explicit activation flag is true.
This module does not deploy AtlasQuant, arm Workers, mutate Core V1, perform
migrations, or use migration/admin credentials.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping
from uuid import uuid4

import psycopg
from psycopg.conninfo import conninfo_to_dict

from aion_chat.models import Scope
from aion_chat.store import StorageUnavailableError
from atlasquant_aion_chat_ephemeral_postgres_v1 import (
    EphemeralPostgresBackendV1,
    EphemeralPostgresChatStoreV1,
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
    _evidence_digest,
)


SCHEMA_ID = "ATLASQUANT_AION_CHAT_RENDER_PRODUCTION_COMPOSITION_V1"
EXPECTED_DATABASE = "atlasquant_aion_chat_prod"
EXPECTED_USER = "aion_chat_app"
EXPECTED_PORT = 5432

ENABLED_KEY = "AION_CHAT_PRODUCTION_PERSISTENCE_ENABLED"
HOST_KEY = "AION_CHAT_PG_HOST"
PORT_KEY = "AION_CHAT_PG_PORT"
DATABASE_KEY = "AION_CHAT_PG_DATABASE"
USER_KEY = "AION_CHAT_PG_USER"
PASSWORD_KEY = "AION_CHAT_PG_PASSWORD"
SSLMODE_KEY = "AION_CHAT_PG_SSLMODE"
CURSOR_KEY = "AION_CHAT_CURSOR_SIGNING_KEY"

_ALLOWED_SSLMODES = frozenset({"require", "verify-ca", "verify-full"})
_TRUE = frozenset({"1", "true", "yes", "on", "sim"})


def _clean(value: Any, limit: int = 4096) -> str:
    return str(value or "").strip()[:limit]


def _enabled(value: Any) -> bool:
    return _clean(value, 20).lower() in _TRUE


def _safe_host(value: Any, *, environment: str) -> str:
    host = _clean(value, 255)
    if (
        not host
        or any(char.isspace() for char in host)
        or "://" in host
        or "/" in host
        or "@" in host
        or ":" in host
    ):
        raise ValueError("plain PostgreSQL host name required")
    if environment == "PRODUCTION" and host in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError("production PostgreSQL host cannot be loopback")
    return host


@dataclass(frozen=True)
class ProductionPostgresConfigV1:
    host: str
    port: int
    database: str
    user: str
    password: str
    sslmode: str
    cursor_signing_key: bytes
    enabled: bool
    environment: str

    def public_evidence(self) -> dict[str, Any]:
        return {
            "schema": SCHEMA_ID,
            "enabled": self.enabled,
            "environment": self.environment,
            "host_present": bool(self.host),
            "port": self.port,
            "database": self.database,
            "user": self.user,
            "sslmode": self.sslmode,
            "password_present": bool(self.password),
            "password_length_ok": len(self.password) >= 32,
            "cursor_signing_key_present": bool(self.cursor_signing_key),
            "cursor_signing_key_length_ok": len(self.cursor_signing_key) >= 32,
            "password_exposed": False,
            "cursor_key_exposed": False,
        }


def resolve_production_postgres_config(
    values: Mapping[str, Any] | None,
    *,
    environment: str = "PRODUCTION",
) -> ProductionPostgresConfigV1:
    """Validate host-injected configuration without reading process state."""
    if not isinstance(values, Mapping):
        raise TypeError("trusted configuration mapping required")

    env = _clean(environment, 32).upper()
    if env not in {"PRODUCTION", "TEST"}:
        raise ValueError("PRODUCTION/TEST environment required")

    enabled = _enabled(values.get(ENABLED_KEY))
    host = _safe_host(values.get(HOST_KEY), environment=env)

    raw_port = _clean(values.get(PORT_KEY), 16)
    try:
        port = int(raw_port)
    except (TypeError, ValueError) as exc:
        raise ValueError("valid PostgreSQL port required") from exc
    if port != EXPECTED_PORT:
        raise ValueError("unexpected PostgreSQL port")

    database = _clean(values.get(DATABASE_KEY), 120)
    if database != EXPECTED_DATABASE:
        raise ValueError("unexpected AION Chat production database")

    user = _clean(values.get(USER_KEY), 120)
    if user != EXPECTED_USER:
        raise ValueError("least-privilege AION Chat application user required")

    password = _clean(values.get(PASSWORD_KEY), 4096)
    if len(password) < 32:
        raise ValueError("strong injected PostgreSQL password required")

    sslmode = _clean(values.get(SSLMODE_KEY), 40).lower()
    if sslmode not in _ALLOWED_SSLMODES:
        raise ValueError("TLS PostgreSQL sslmode required")

    cursor_raw = _clean(values.get(CURSOR_KEY), 4096)
    cursor_key = cursor_raw.encode("utf-8")
    if len(cursor_key) < 32:
        raise ValueError("stable cursor signing key of at least 32 bytes required")

    return ProductionPostgresConfigV1(
        host=host,
        port=port,
        database=database,
        user=user,
        password=password,
        sslmode=sslmode,
        cursor_signing_key=cursor_key,
        enabled=enabled,
        environment=env,
    )


ConnectionFactory = Callable[[], psycopg.Connection]


def build_connection_factory(
    config: ProductionPostgresConfigV1,
) -> ConnectionFactory:
    if not isinstance(config, ProductionPostgresConfigV1):
        raise TypeError("ProductionPostgresConfigV1 required")

    def connect() -> psycopg.Connection:
        return psycopg.connect(
            host=config.host,
            port=config.port,
            dbname=config.database,
            user=config.user,
            password=config.password,
            sslmode=config.sslmode,
            connect_timeout=5,
            application_name="atlasquant-aion-chat-prod-v1",
            autocommit=False,
        )

    return connect


class RenderProductionPostgresBackendV1(EphemeralPostgresBackendV1):
    """Real production-schema backend authenticated directly as app role."""

    def __init__(
        self,
        connection_factory: ConnectionFactory,
        *,
        sslmode: str,
    ):
        if not callable(connection_factory):
            raise TypeError("connection factory required")
        normalized_sslmode = _clean(sslmode, 40).lower()
        if normalized_sslmode not in _ALLOWED_SSLMODES:
            raise ValueError("TLS sslmode required")

        # Deliberately bypass the CI-only parent constructor while reusing the
        # reviewed store SQL surface.
        self._connect = connection_factory
        self.environment = "PRODUCTION"
        self.schema = SCHEMA
        self.commit_outcome_unknown_once = False
        self.sslmode = normalized_sslmode

    def _connection(self) -> psycopg.Connection:
        conn = None
        try:
            conn = self._connect()
            conn.autocommit = False

            params = conninfo_to_dict(conn.info.dsn)
            effective_sslmode = _clean(params.get("sslmode"), 40).lower()
            if effective_sslmode not in _ALLOWED_SSLMODES:
                raise StorageUnavailableError(
                    "TLS PostgreSQL client policy is not proven"
                )

            with conn.cursor() as cur:
                cur.execute("SELECT session_user,current_user")
                identity = tuple(str(value) for value in cur.fetchone())
                cur.execute(
                    "SELECT s.ssl,s.version,s.cipher,"
                    "inet_client_addr() IS NOT NULL "
                    "FROM pg_stat_ssl s WHERE s.pid=pg_backend_pid()"
                )
                tls = cur.fetchone()

            if identity != (EXPECTED_USER, EXPECTED_USER):
                raise StorageUnavailableError(
                    "direct least-privilege application identity is not proven"
                )
            if (
                tls is None
                or tls[0] is not True
                or not str(tls[1] or "").strip()
                or not str(tls[2] or "").strip()
                or tls[3] is not True
            ):
                raise StorageUnavailableError(
                    "encrypted PostgreSQL TCP transport is not proven"
                )
            conn.rollback()
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
                "production PostgreSQL connection unavailable"
            ) from exc

    def _bind_scope(self, conn: psycopg.Connection, scope: Scope) -> None:
        if not isinstance(scope, Scope):
            raise TypeError("trusted Scope required")
        owner = _clean(scope.owner_id, 120)
        tenant = _clean(scope.tenant_id, 120)
        workspace = _clean(scope.workspace_id, 120)
        if not owner or not tenant or not workspace:
            raise ValueError("complete trusted Scope required")
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
                    "created_at": (
                        row[7].isoformat()
                        if hasattr(row[7], "isoformat")
                        else str(row[7])
                    ),
                }
                for row in rows
            ]
        except Exception as exc:
            try:
                conn.rollback()
            except Exception:
                pass
            if isinstance(exc, (LookupError, ValueError, TypeError)):
                raise
            raise StorageUnavailableError(
                "production audit receipt retrieval unavailable"
            ) from exc
        finally:
            conn.close()

    def health_report(self) -> dict[str, Any]:
        report = EphemeralPostgresBackendV1.health_report(self)
        report.update(
            backend="render_production_postgres_v1",
            environment="PRODUCTION",
            production_allowed=True,
            production_schema=SCHEMA,
            expected_migration_version=MIGRATION_VERSION,
            direct_login_user=EXPECTED_USER,
            direct_identity_healthy=False,
            tls_required=True,
            tls_verified=False,
            tls_version="",
            tls_cipher="",
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
            database_create_denied=False,
            migration_history_denied=False,
            transaction_local_scope_required=True,
            migration_authority_present=False,
            worker_armed=False,
            core_checkpoint_write=False,
        )
        if report["state"] != HEALTHY:
            return report

        conn = None
        try:
            conn = self._connection()
            params = conninfo_to_dict(conn.info.dsn)
            with conn.cursor() as cur:
                cur.execute("SELECT session_user,current_user")
                identity = tuple(str(value) for value in cur.fetchone())
                identity_ok = identity == (EXPECTED_USER, EXPECTED_USER)

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
                    "SELECT s.ssl,s.version,s.cipher "
                    "FROM pg_stat_ssl s WHERE s.pid=pg_backend_pid()"
                )
                tls = cur.fetchone()
                tls_ok = bool(
                    tls
                    and tls[0] is True
                    and str(tls[1] or "").strip()
                    and str(tls[2] or "").strip()
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
                    "SELECT "
                    "has_schema_privilege(current_user,%s,'CREATE'),"
                    "has_database_privilege(current_user,current_database(),'CREATE'),"
                    "has_table_privilege(current_user,%s,'SELECT')",
                    (SCHEMA, f"{SCHEMA}.schema_migrations"),
                )
                schema_create, database_create, migration_select = cur.fetchone()

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
                schema_meta_ok = cur.fetchone() == (
                    True,
                    False,
                    False,
                    False,
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
                and tls_ok
                and rls_ok
                and policies_ok
                and not bool(schema_create)
                and not bool(database_create)
                and not bool(migration_select)
                and schema_meta_ok
                and append_only_ok
                and conversations_ok
            )
            report.update(
                state=HEALTHY if hardened else FAILED,
                direct_identity_healthy=identity_ok,
                tls_verified=tls_ok,
                tls_version=str(tls[1]) if tls else "",
                tls_cipher=str(tls[2]) if tls else "",
                effective_sslmode=_clean(params.get("sslmode"), 40).lower(),
                least_privilege_role_healthy=role_ok,
                rls_tables_present=len(rls),
                rls_enabled_and_forced=rls_ok,
                policies_present=len(policies),
                append_only_privileges_healthy=append_only_ok,
                conversations_privileges_healthy=conversations_ok,
                schema_meta_read_only=schema_meta_ok,
                schema_create_denied=not bool(schema_create),
                database_create_denied=not bool(database_create),
                migration_history_denied=not bool(migration_select),
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


class RenderProductionPostgresChatStoreV1(EphemeralPostgresChatStoreV1):
    def __init__(
        self,
        backend: RenderProductionPostgresBackendV1,
        *,
        cursor_signing_key: bytes,
    ):
        if not isinstance(backend, RenderProductionPostgresBackendV1):
            raise TypeError("RenderProductionPostgresBackendV1 required")
        super().__init__(
            backend,
            cursor_signing_key=cursor_signing_key,
        )


def build_production_chat_store(
    values: Mapping[str, Any] | None,
    *,
    environment: str = "PRODUCTION",
) -> tuple[RenderProductionPostgresChatStoreV1, dict[str, Any]]:
    config = resolve_production_postgres_config(values, environment=environment)
    if not config.enabled:
        raise PermissionError("production chat persistence activation flag is off")

    backend = RenderProductionPostgresBackendV1(
        build_connection_factory(config),
        sslmode=config.sslmode,
    )
    store = RenderProductionPostgresChatStoreV1(
        backend,
        cursor_signing_key=config.cursor_signing_key,
    )
    health = store.require_healthy()
    return store, {
        "schema": SCHEMA_ID,
        "state": "PRODUCTION_STORE_BOUND",
        "config": config.public_evidence(),
        "health": health,
        "migration_execution": False,
        "migration_authority_used": False,
        "provider_called": False,
        "billing_executed": False,
        "deploy_executed": False,
        "worker_armed": False,
        "external_action_executed": False,
        "core_checkpoint_write": False,
    }


def production_composition_policy() -> dict[str, Any]:
    return {
        "schema": SCHEMA_ID,
        "activation_flag": ENABLED_KEY,
        "default_activation": False,
        "expected_database": EXPECTED_DATABASE,
        "expected_user": EXPECTED_USER,
        "expected_port": EXPECTED_PORT,
        "allowed_sslmodes": sorted(_ALLOWED_SSLMODES),
        "password_injected": True,
        "cursor_signing_key_injected": True,
        "environment_lookup_inside_store": False,
        "database_url_supported": False,
        "migration_execution": False,
        "migration_authority_used": False,
        "admin_credential_supported": False,
        "worker_armed": False,
        "external_action_executed": False,
        "core_checkpoint_write": False,
    }


__all__ = [
    "SCHEMA_ID",
    "EXPECTED_DATABASE",
    "EXPECTED_USER",
    "EXPECTED_PORT",
    "ENABLED_KEY",
    "HOST_KEY",
    "PORT_KEY",
    "DATABASE_KEY",
    "USER_KEY",
    "PASSWORD_KEY",
    "SSLMODE_KEY",
    "CURSOR_KEY",
    "ProductionPostgresConfigV1",
    "resolve_production_postgres_config",
    "build_connection_factory",
    "RenderProductionPostgresBackendV1",
    "RenderProductionPostgresChatStoreV1",
    "build_production_chat_store",
    "production_composition_policy",
]
