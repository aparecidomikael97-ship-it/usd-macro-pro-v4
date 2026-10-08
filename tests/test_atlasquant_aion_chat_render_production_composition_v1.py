from __future__ import annotations

import os
import unittest

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo

from aion_chat.models import Message, Scope
from aion_chat.store import StorageUnavailableError
import atlasquant_aion_chat_postgres_migration_rls_restore_ci_v1 as migration
import atlasquant_aion_chat_render_production_composition_v1 as production
from atlasquant_aion_chat_production_schema_binding_ci_v1 import (
    APPEND_ONLY_TABLES,
)


APP_PASSWORD = "atlasquant-production-composition-ci-password-v1-strong"


class RenderProductionCompositionV1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        dsn = str(os.environ.get("AION_CHAT_RENDER_COMPOSITION_CI_ADMIN_DSN") or "").strip()
        if not dsn:
            raise RuntimeError("AION_CHAT_RENDER_COMPOSITION_CI_ADMIN_DSN required")
        cls._admin_dsn = dsn

        def admin_connect():
            return psycopg.connect(
                cls._admin_dsn,
                autocommit=False,
                connect_timeout=5,
                application_name="atlasquant-production-composition-admin-ci",
            )

        cls.admin_connect = staticmethod(admin_connect)
        cls._reset_all()

        applied = migration.apply_migration(cls.admin_connect, environment="CI")
        if applied["state"] != migration.APPLIED:
            raise RuntimeError(applied)

        cls._create_app_role()

        admin_params = conninfo_to_dict(cls._admin_dsn)
        cls._app_config = {
            production.ENABLED_KEY: "true",
            production.HOST_KEY: str(admin_params["host"]),
            production.PORT_KEY: str(admin_params["port"]),
            production.DATABASE_KEY: production.EXPECTED_DATABASE,
            production.USER_KEY: production.EXPECTED_USER,
            production.PASSWORD_KEY: APP_PASSWORD,
            production.SSLMODE_KEY: "verify-full",
            production.CURSOR_KEY: (
                "atlasquant-render-production-composition-ci-cursor-key-v1"
            ),
        }
        # The service database name is normalized to the production name so the
        # tested composition cannot silently accept another database.
        conn = cls.admin_connect()
        try:
            conn.autocommit = True
            with conn.cursor() as cur:
                current = conn.info.dbname
                if current != production.EXPECTED_DATABASE:
                    cur.execute(
                        sql.SQL("ALTER DATABASE {} RENAME TO {}").format(
                            sql.Identifier(current),
                            sql.Identifier(production.EXPECTED_DATABASE),
                        )
                    )
        finally:
            conn.close()

        # Rebuild admin DSN against renamed database.
        admin_params["dbname"] = production.EXPECTED_DATABASE
        cls._admin_dsn = make_conninfo(**admin_params)

        def renamed_admin_connect():
            return psycopg.connect(
                cls._admin_dsn,
                autocommit=False,
                connect_timeout=5,
                application_name="atlasquant-production-composition-admin-ci",
            )

        cls.admin_connect = staticmethod(renamed_admin_connect)

    @classmethod
    def tearDownClass(cls):
        cls._reset_all()

    @classmethod
    def _reset_all(cls):
        try:
            conn = cls.admin_connect()
        except Exception:
            return
        try:
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute(f"DROP SCHEMA IF EXISTS {migration.SCHEMA} CASCADE")
                cur.execute(
                    "SELECT 1 FROM pg_roles WHERE rolname=%s",
                    (production.EXPECTED_USER,),
                )
                if cur.fetchone():
                    cur.execute(
                        sql.SQL("DROP OWNED BY {}").format(
                            sql.Identifier(production.EXPECTED_USER)
                        )
                    )
                    cur.execute(
                        sql.SQL("DROP ROLE {}").format(
                            sql.Identifier(production.EXPECTED_USER)
                        )
                    )
        finally:
            conn.close()

    @classmethod
    def _create_app_role(cls):
        conn = cls.admin_connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    sql.SQL(
                        "CREATE ROLE {} WITH LOGIN PASSWORD {} "
                        "NOSUPERUSER NOCREATEDB NOCREATEROLE "
                        "NOINHERIT NOREPLICATION NOBYPASSRLS"
                    ).format(
                        sql.Identifier(production.EXPECTED_USER),
                        sql.Literal(APP_PASSWORD),
                    )
                )
                cur.execute(
                    sql.SQL("GRANT USAGE ON SCHEMA {} TO {}").format(
                        sql.Identifier(migration.SCHEMA),
                        sql.Identifier(production.EXPECTED_USER),
                    )
                )
                cur.execute(
                    sql.SQL("GRANT SELECT ON {}.{} TO {}").format(
                        sql.Identifier(migration.SCHEMA),
                        sql.Identifier("schema_meta"),
                        sql.Identifier(production.EXPECTED_USER),
                    )
                )
                cur.execute(
                    sql.SQL("GRANT SELECT,INSERT,UPDATE ON {}.{} TO {}").format(
                        sql.Identifier(migration.SCHEMA),
                        sql.Identifier("conversations"),
                        sql.Identifier(production.EXPECTED_USER),
                    )
                )
                for table in APPEND_ONLY_TABLES:
                    cur.execute(
                        sql.SQL("GRANT SELECT,INSERT ON {}.{} TO {}").format(
                            sql.Identifier(migration.SCHEMA),
                            sql.Identifier(table),
                            sql.Identifier(production.EXPECTED_USER),
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

    def config(self, **updates):
        values = dict(self._app_config)
        values.update(updates)
        return values

    def test_configuration_is_fail_closed_and_secret_free(self):
        cfg = production.resolve_production_postgres_config(
            self.config(),
            environment="TEST",
        )
        evidence = cfg.public_evidence()
        self.assertTrue(evidence["enabled"])
        self.assertEqual(evidence["database"], production.EXPECTED_DATABASE)
        self.assertEqual(evidence["user"], production.EXPECTED_USER)
        self.assertTrue(evidence["password_present"])
        self.assertTrue(evidence["cursor_signing_key_present"])
        self.assertNotIn(APP_PASSWORD, repr(evidence))
        self.assertNotIn(self.config()[production.CURSOR_KEY], repr(evidence))

        for key, value in (
            (production.USER_KEY, "postgres"),
            (production.DATABASE_KEY, "postgres"),
            (production.PORT_KEY, "5433"),
            (production.SSLMODE_KEY, "disable"),
            (production.PASSWORD_KEY, "short"),
            (production.CURSOR_KEY, "short"),
        ):
            with self.subTest(key=key):
                with self.assertRaises(ValueError):
                    production.resolve_production_postgres_config(
                        self.config(**{key: value}),
                        environment="TEST",
                    )

    def test_activation_flag_blocks_store_construction(self):
        with self.assertRaises(PermissionError):
            production.build_production_chat_store(
                self.config(**{production.ENABLED_KEY: "false"}),
                environment="TEST",
            )

    def test_real_store_health_is_production_hardened(self):
        store, binding = production.build_production_chat_store(
            self.config(),
            environment="TEST",
        )
        report = binding["health"]
        self.assertEqual(report["state"], production.HEALTHY)
        self.assertTrue(report["direct_identity_healthy"])
        self.assertTrue(report["tls_verified"])
        self.assertTrue(report["least_privilege_role_healthy"])
        self.assertTrue(report["rls_enabled_and_forced"])
        self.assertTrue(report["append_only_privileges_healthy"])
        self.assertTrue(report["conversations_privileges_healthy"])
        self.assertTrue(report["schema_meta_read_only"])
        self.assertTrue(report["schema_create_denied"])
        self.assertTrue(report["database_create_denied"])
        self.assertTrue(report["migration_history_denied"])
        self.assertFalse(binding["migration_execution"])
        self.assertFalse(binding["worker_armed"])

    def test_real_store_writes_scope_and_atomic_audit(self):
        store, _ = production.build_production_chat_store(
            self.config(),
            environment="TEST",
        )
        scope = Scope("mikael", "atlasquant-owner", "central")
        conversation = store.create_conversation(
            scope,
            title="production composition CI",
            metadata={"tags": ["ci"]},
        )
        message = store.append_message(
            scope,
            Message(
                conversation_id=conversation.id,
                role="user",
                content="durable production composition proof",
                metadata={"idempotency_key": "prod-composition-ci-1"},
            ),
        )
        self.assertEqual(message.sequence, 1)

        receipts = store.backend.list_audit_receipts(scope)
        self.assertEqual(
            [row["operation"] for row in receipts],
            ["CONVERSATION_CREATE", "MESSAGE_APPEND"],
        )
        other = Scope("other", "atlasquant-owner", "central")
        with self.assertRaises(LookupError):
            store.get_conversation(other, conversation.id)

    def test_privilege_drift_fails_health_closed(self):
        store, _ = production.build_production_chat_store(
            self.config(),
            environment="TEST",
        )
        conn = self.admin_connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    sql.SQL("GRANT DELETE ON {}.messages TO {}").format(
                        sql.Identifier(migration.SCHEMA),
                        sql.Identifier(production.EXPECTED_USER),
                    )
                )
            conn.commit()
        finally:
            conn.close()

        try:
            report = store.storage_health()
            self.assertEqual(report["state"], production.FAILED)
            self.assertFalse(report["append_only_privileges_healthy"])
            with self.assertRaises(StorageUnavailableError):
                store.require_healthy()
        finally:
            conn = self.admin_connect()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        sql.SQL("REVOKE DELETE ON {}.messages FROM {}").format(
                            sql.Identifier(migration.SCHEMA),
                            sql.Identifier(production.EXPECTED_USER),
                        )
                    )
                conn.commit()
            finally:
                conn.close()

    def test_admin_identity_miswire_fails_closed(self):
        backend = production.RenderProductionPostgresBackendV1(
            self.admin_connect,
            sslmode="verify-full",
        )
        self.assertEqual(backend.health_report()["state"], production.FAILED)
        with self.assertRaises(StorageUnavailableError):
            backend.require_healthy()

    def test_policy_contains_no_migration_or_worker_authority(self):
        policy = production.production_composition_policy()
        self.assertFalse(policy["default_activation"])
        self.assertFalse(policy["database_url_supported"])
        self.assertFalse(policy["migration_execution"])
        self.assertFalse(policy["migration_authority_used"])
        self.assertFalse(policy["admin_credential_supported"])
        self.assertFalse(policy["worker_armed"])
        self.assertFalse(policy["external_action_executed"])
        self.assertFalse(policy["core_checkpoint_write"])


if __name__ == "__main__":
    unittest.main()
