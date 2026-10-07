from __future__ import annotations

import inspect
import os
import unittest

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo

from aion_chat.models import Message, Scope
import atlasquant_aion_chat_migration_identity_lifecycle_ci_v1 as lifecycle
import atlasquant_aion_chat_postgres_migration_rls_restore_ci_v1 as migration
import atlasquant_aion_chat_postgres_schema_candidate_freeze_v1 as freeze
import atlasquant_aion_chat_tls_direct_app_role_ci_v1 as tls_binding
from atlasquant_aion_chat_direct_app_role_connection_ci_v1 import (
    CI_DIRECT_APP_ROLE,
)
from atlasquant_aion_chat_production_schema_binding_ci_v1 import (
    APPEND_ONLY_TABLES,
)


MIGRATOR_PASSWORD = "atlasquant-ci-migrator-only-v1"
APP_PASSWORD = "atlasquant-ci-app-after-migration-v1"


class MigrationIdentityLifecycleCiV1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        dsn = str(
            os.environ.get("AION_CHAT_MIGRATION_IDENTITY_CI_ADMIN_DSN") or ""
        ).strip()
        if not dsn:
            raise RuntimeError(
                "AION_CHAT_MIGRATION_IDENTITY_CI_ADMIN_DSN required"
            )
        params = conninfo_to_dict(dsn)
        if str(params.get("sslmode") or "").lower() != "verify-full":
            raise RuntimeError("CI admin connection must use sslmode=verify-full")
        if not str(params.get("sslrootcert") or "").strip():
            raise RuntimeError("CI admin connection must pin a CA root")
        cls._admin_dsn = dsn

        def admin_connect():
            return psycopg.connect(
                cls._admin_dsn,
                autocommit=False,
                connect_timeout=5,
                application_name="atlasquant-aion-migration-lifecycle-admin-ci",
            )

        cls.admin_connect = staticmethod(admin_connect)
        cls._reset_all()
        cls._create_migration_login()

        migrator_params = conninfo_to_dict(cls._admin_dsn)
        migrator_params.update(
            user=lifecycle.CI_MIGRATION_ROLE,
            password=MIGRATOR_PASSWORD,
            application_name="atlasquant-aion-migrator-ci",
        )
        cls._migrator_dsn = make_conninfo(**migrator_params)

        def migrator_connect():
            return psycopg.connect(
                cls._migrator_dsn,
                autocommit=False,
                connect_timeout=5,
            )

        cls.migrator_connect = staticmethod(migrator_connect)
        cls.attested_migrator = lifecycle.AttestedMigrationConnectionFactoryCiV1(
            cls.migrator_connect,
            environment="CI",
        )

        cls.active_report = lifecycle.active_migration_identity_report(
            cls.migrator_connect,
            environment="CI",
        )
        cls.apply_result = migration.apply_migration(
            cls.attested_migrator,
            environment="CI",
        )
        cls.migration_health = migration.migration_health_report(
            cls.attested_migrator,
            environment="CI",
        )

        cls._seal_migration_login()
        cls.sealed_report = lifecycle.sealed_migration_identity_report(
            cls.admin_connect,
            environment="CI",
        )

        cls._create_application_login()
        app_params = conninfo_to_dict(cls._admin_dsn)
        app_params.update(
            user=CI_DIRECT_APP_ROLE,
            password=APP_PASSWORD,
            application_name="atlasquant-aion-app-after-migration-ci",
        )
        cls._app_dsn = make_conninfo(**app_params)

        def app_connect():
            return psycopg.connect(
                cls._app_dsn,
                autocommit=False,
                connect_timeout=5,
            )

        cls.app_connect = staticmethod(app_connect)

    @classmethod
    def tearDownClass(cls):
        cls._reset_all()

    @classmethod
    def _reset_all(cls):
        conn = cls.admin_connect()
        try:
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute(f"DROP SCHEMA IF EXISTS {migration.SCHEMA} CASCADE")
                for role in (
                    CI_DIRECT_APP_ROLE,
                    lifecycle.CI_MIGRATION_ROLE,
                ):
                    cur.execute(
                        "SELECT 1 FROM pg_roles WHERE rolname=%s",
                        (role,),
                    )
                    if cur.fetchone():
                        cur.execute(
                            sql.SQL("DROP OWNED BY {}").format(
                                sql.Identifier(role)
                            )
                        )
                        cur.execute(
                            sql.SQL("DROP ROLE {}").format(
                                sql.Identifier(role)
                            )
                        )
        finally:
            conn.close()

    @classmethod
    def _create_migration_login(cls):
        conn = cls.admin_connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    sql.SQL(
                        "CREATE ROLE {} WITH LOGIN PASSWORD {} "
                        "NOSUPERUSER NOCREATEDB NOCREATEROLE "
                        "NOINHERIT NOREPLICATION NOBYPASSRLS"
                    ).format(
                        sql.Identifier(lifecycle.CI_MIGRATION_ROLE),
                        sql.Literal(MIGRATOR_PASSWORD),
                    )
                )
                cur.execute(
                    sql.SQL(
                        "GRANT CREATE ON DATABASE {} TO {}"
                    ).format(
                        sql.Identifier(conn.info.dbname),
                        sql.Identifier(lifecycle.CI_MIGRATION_ROLE),
                    )
                )
            conn.commit()
        finally:
            conn.close()

    @classmethod
    def _seal_migration_login(cls):
        conn = cls.admin_connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    sql.SQL(
                        "REVOKE CREATE ON DATABASE {} FROM {}"
                    ).format(
                        sql.Identifier(conn.info.dbname),
                        sql.Identifier(lifecycle.CI_MIGRATION_ROLE),
                    )
                )
                cur.execute(
                    sql.SQL("ALTER ROLE {} NOLOGIN").format(
                        sql.Identifier(lifecycle.CI_MIGRATION_ROLE)
                    )
                )
            conn.commit()
        finally:
            conn.close()

    @classmethod
    def _create_application_login(cls):
        conn = cls.admin_connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    sql.SQL(
                        "CREATE ROLE {} WITH LOGIN PASSWORD {} "
                        "NOSUPERUSER NOCREATEDB NOCREATEROLE "
                        "NOINHERIT NOREPLICATION NOBYPASSRLS"
                    ).format(
                        sql.Identifier(CI_DIRECT_APP_ROLE),
                        sql.Literal(APP_PASSWORD),
                    )
                )
                cur.execute(
                    sql.SQL("GRANT USAGE ON SCHEMA {} TO {}").format(
                        sql.Identifier(migration.SCHEMA),
                        sql.Identifier(CI_DIRECT_APP_ROLE),
                    )
                )
                cur.execute(
                    sql.SQL("GRANT SELECT ON {}.{} TO {}").format(
                        sql.Identifier(migration.SCHEMA),
                        sql.Identifier("schema_meta"),
                        sql.Identifier(CI_DIRECT_APP_ROLE),
                    )
                )
                cur.execute(
                    sql.SQL(
                        "GRANT SELECT,INSERT,UPDATE ON {}.{} TO {}"
                    ).format(
                        sql.Identifier(migration.SCHEMA),
                        sql.Identifier("conversations"),
                        sql.Identifier(CI_DIRECT_APP_ROLE),
                    )
                )
                for table in APPEND_ONLY_TABLES:
                    cur.execute(
                        sql.SQL("GRANT SELECT,INSERT ON {}.{} TO {}").format(
                            sql.Identifier(migration.SCHEMA),
                            sql.Identifier(table),
                            sql.Identifier(CI_DIRECT_APP_ROLE),
                        )
                    )
            conn.commit()
        finally:
            conn.close()

    def setUp(self):
        conn = self.admin_connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"TRUNCATE TABLE "
                    f"{migration.SCHEMA}.access_audit,"
                    f"{migration.SCHEMA}.summaries,"
                    f"{migration.SCHEMA}.checkpoints,"
                    f"{migration.SCHEMA}.attachments,"
                    f"{migration.SCHEMA}.message_idempotency,"
                    f"{migration.SCHEMA}.messages,"
                    f"{migration.SCHEMA}.conversations CASCADE"
                )
            conn.commit()
        finally:
            conn.close()

        self.backend = tls_binding.TlsDirectLoginAuditedPostgresBackendCiV1(
            self.app_connect,
            environment="CI",
        )
        self.store = tls_binding.TlsDirectLoginAuditedPostgresChatStoreCiV1(
            self.backend,
            cursor_signing_key=b"atlasquant-migration-lifecycle-ci-cursor-key",
        )
        self.scope = Scope("mikael", "atlasquant-owner", "central")

    def test_short_lived_migration_identity_was_direct_tls_and_least_privilege(self):
        self.assertEqual(
            self.active_report["state"],
            lifecycle.MIGRATION_IDENTITY_ACTIVE,
        )
        self.assertTrue(self.active_report["direct_identity"])
        self.assertTrue(self.active_report["verify_full_tls"])
        self.assertTrue(
            self.active_report["database_create_temporarily_allowed"]
        )
        self.assertFalse(self.active_report["superuser"])
        self.assertFalse(self.active_report["createdb"])
        self.assertFalse(self.active_report["createrole"])
        self.assertFalse(self.active_report["replication"])
        self.assertFalse(self.active_report["bypassrls"])
        self.assertTrue(self.active_report["can_login"])

    def test_frozen_migration_applied_and_health_was_proven_before_seal(self):
        self.assertEqual(self.apply_result["state"], migration.APPLIED)
        self.assertEqual(
            self.migration_health["state"],
            migration.HEALTHY,
        )
        self.assertTrue(
            self.migration_health["migration_checksum_verified"]
        )

    def test_post_migration_identity_is_sealed_but_retains_schema_ownership(self):
        self.assertEqual(
            self.sealed_report["state"],
            lifecycle.MIGRATION_IDENTITY_SEALED,
        )
        self.assertFalse(self.sealed_report["can_login"])
        self.assertTrue(self.sealed_report["database_create_revoked"])
        self.assertTrue(self.sealed_report["schema_owned_by_migrator"])
        self.assertTrue(
            self.sealed_report["all_application_tables_owned_by_migrator"]
        )
        self.assertGreater(
            self.sealed_report["application_table_count"],
            0,
        )

    def test_sealed_migration_credential_cannot_open_new_session(self):
        with self.assertRaises(psycopg.OperationalError):
            psycopg.connect(
                self._migrator_dsn,
                autocommit=False,
                connect_timeout=3,
            )

    def test_application_identity_operates_after_migrator_is_sealed(self):
        report = self.store.storage_health()
        self.assertEqual(report["state"], tls_binding.HEALTHY)
        conversation = self.store.create_conversation(
            self.scope,
            title="runtime after sealed migration identity",
            metadata={"tags": ["runtime", "sealed-migrator"]},
        )
        message = self.store.append_message(
            self.scope,
            Message(
                conversation_id=conversation.id,
                role="user",
                content="runtime remains independent from migrator",
                metadata={"idempotency_key": "sealed-migrator-runtime"},
            ),
        )
        self.assertEqual(message.sequence, 1)
        receipts = self.backend.list_audit_receipts(self.scope)
        self.assertEqual(
            [item["operation"] for item in receipts],
            ["CONVERSATION_CREATE", "MESSAGE_APPEND"],
        )

    def test_application_identity_cannot_use_migration_authority(self):
        conn = self.app_connect()
        try:
            with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                with conn.cursor() as cur:
                    cur.execute(
                        f"CREATE TABLE {migration.SCHEMA}.forbidden_after_seal"
                        "(id integer)"
                    )
            conn.rollback()

            with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                with conn.cursor() as cur:
                    cur.execute(
                        f"SELECT * FROM {migration.SCHEMA}.schema_migrations"
                    )
            conn.rollback()
        finally:
            conn.close()

    def test_schema_candidate_remains_frozen_after_identity_lifecycle(self):
        report = freeze.schema_candidate_report(
            self.admin_connect,
            environment="CI",
        )
        self.assertEqual(report["state"], freeze.CANDIDATE_STATE)
        self.assertTrue(report["migration_sha256_verified"])
        self.assertTrue(report["tables_exact"])
        self.assertTrue(report["access_audit_columns_exact"])
        self.assertTrue(report["required_indexes_present"])

    def test_module_has_zero_secret_resolution_or_production_authority(self):
        source = inspect.getsource(lifecycle)
        for banned in (
            "DATABASE_URL",
            "os.getenv",
            "os.environ",
            "streamlit.secrets",
            "render.com",
            "api.openai.com",
        ):
            self.assertNotIn(banned, source)

        policy = lifecycle.migration_identity_lifecycle_policy()
        self.assertTrue(policy["direct_login_required"])
        self.assertTrue(policy["verify_full_tls_required"])
        self.assertTrue(policy["post_migration_database_create_revoked"])
        self.assertTrue(policy["post_migration_login_disabled"])
        self.assertFalse(policy["migration_role_is_application_role"])
        self.assertFalse(policy["superuser_allowed"])
        self.assertFalse(policy["production_connection_allowed"])
        for key in (
            "provider_called",
            "billing_executed",
            "deploy_executed",
            "worker_armed",
            "external_action_executed",
            "core_checkpoint_write",
        ):
            self.assertIs(policy[key], False, key)


if __name__ == "__main__":
    unittest.main()
