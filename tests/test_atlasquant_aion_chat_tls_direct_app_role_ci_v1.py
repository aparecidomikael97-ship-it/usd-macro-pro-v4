from __future__ import annotations

import inspect
import os
import unittest

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo

from aion_chat.models import Message, Scope
from aion_chat.store import StorageUnavailableError
import atlasquant_aion_chat_postgres_migration_rls_restore_ci_v1 as migration
import atlasquant_aion_chat_postgres_schema_candidate_freeze_v1 as freeze
import atlasquant_aion_chat_tls_direct_app_role_ci_v1 as tls_binding
from atlasquant_aion_chat_direct_app_role_connection_ci_v1 import (
    CI_DIRECT_APP_ROLE,
)
from atlasquant_aion_chat_production_schema_binding_ci_v1 import (
    APPEND_ONLY_TABLES,
)


CI_PASSWORD = "atlasquant-ci-tls-role-only-v1"


class TlsDirectAppRoleCiV1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        dsn = str(os.environ.get("AION_CHAT_TLS_CI_ADMIN_DSN") or "").strip()
        if not dsn:
            raise RuntimeError("AION_CHAT_TLS_CI_ADMIN_DSN required")
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
                application_name="atlasquant-aion-tls-admin-ci",
            )

        cls.admin_connect = staticmethod(admin_connect)
        cls._reset_all()
        applied = migration.apply_migration(cls.admin_connect, environment="CI")
        if applied["state"] != migration.APPLIED:
            raise RuntimeError(applied)
        cls._create_direct_login_role()

        app_params = conninfo_to_dict(cls._admin_dsn)
        app_params.update(
            user=CI_DIRECT_APP_ROLE,
            password=CI_PASSWORD,
            application_name="atlasquant-aion-tls-app-ci",
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
                cur.execute(
                    "SELECT 1 FROM pg_roles WHERE rolname=%s",
                    (CI_DIRECT_APP_ROLE,),
                )
                if cur.fetchone():
                    cur.execute(
                        sql.SQL("DROP OWNED BY {}").format(
                            sql.Identifier(CI_DIRECT_APP_ROLE)
                        )
                    )
                    cur.execute(
                        sql.SQL("DROP ROLE {}").format(
                            sql.Identifier(CI_DIRECT_APP_ROLE)
                        )
                    )
        finally:
            conn.close()

    @classmethod
    def _create_direct_login_role(cls):
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
                        sql.Literal(CI_PASSWORD),
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
            cursor_signing_key=b"atlasquant-tls-direct-role-ci-cursor-key-v1",
        )
        self.scope = Scope("mikael", "atlasquant-owner", "central")
        self.other_scope = Scope("other", "atlasquant-owner", "central")
        self.conversation = self.store.create_conversation(
            self.scope,
            title="verified TLS direct login",
            metadata={"tags": ["tls", "ci"]},
        )

    def test_health_proves_verify_full_tls_and_direct_identity(self):
        report = self.store.storage_health()
        self.assertEqual(report["state"], tls_binding.HEALTHY)
        self.assertTrue(report["tls_required"])
        self.assertTrue(report["tls_verified"])
        self.assertTrue(report["tcp_transport"])
        self.assertTrue(report["direct_identity_healthy"])
        self.assertTrue(report["least_privilege_role_healthy"])
        self.assertTrue(report["rls_enabled_and_forced"])
        self.assertEqual(report["client_sslmode_required"], "verify-full")
        self.assertTrue(report["sslrootcert_required"])
        self.assertTrue(report["tls_version"])
        self.assertTrue(report["tls_cipher"])

    def test_weak_tls_client_policy_fails_closed_even_if_transport_encrypts(self):
        params = conninfo_to_dict(self._app_dsn)
        params["sslmode"] = "require"
        params.pop("sslrootcert", None)
        weak_dsn = make_conninfo(**params)

        def weak_connect():
            return psycopg.connect(
                weak_dsn,
                autocommit=False,
                connect_timeout=5,
            )

        backend = tls_binding.TlsDirectLoginAuditedPostgresBackendCiV1(
            weak_connect,
            environment="TEST",
        )
        self.assertEqual(backend.health_report()["state"], tls_binding.FAILED)
        with self.assertRaises(StorageUnavailableError):
            backend.require_healthy()

    def test_plaintext_connection_is_rejected(self):
        params = conninfo_to_dict(self._app_dsn)
        params["sslmode"] = "disable"
        params.pop("sslrootcert", None)
        plaintext_dsn = make_conninfo(**params)
        with self.assertRaises(psycopg.OperationalError):
            psycopg.connect(
                plaintext_dsn,
                autocommit=False,
                connect_timeout=5,
            )

    def test_verify_full_rejects_hostname_mismatch(self):
        params = conninfo_to_dict(self._app_dsn)
        params["host"] = "127.0.0.1"
        mismatch_dsn = make_conninfo(**params)
        with self.assertRaises(psycopg.OperationalError):
            psycopg.connect(
                mismatch_dsn,
                autocommit=False,
                connect_timeout=5,
            )

    def test_real_store_and_audit_operate_over_verified_tls(self):
        first = self.store.append_message(
            self.scope,
            Message(
                conversation_id=self.conversation.id,
                role="user",
                content="tls durable one",
                metadata={"idempotency_key": "tls-1"},
            ),
        )
        second = self.store.append_message(
            self.scope,
            Message(
                conversation_id=self.conversation.id,
                role="assistant",
                content="tls durable two",
                metadata={"idempotency_key": "tls-2"},
            ),
        )
        self.assertEqual((first.sequence, second.sequence), (1, 2))
        receipts = self.backend.list_audit_receipts(self.scope)
        self.assertEqual(
            [item["operation"] for item in receipts],
            ["CONVERSATION_CREATE", "MESSAGE_APPEND", "MESSAGE_APPEND"],
        )
        with self.assertRaises(LookupError):
            self.store.get_conversation(
                self.other_scope,
                self.conversation.id,
            )

    def test_frozen_schema_candidate_remains_exact(self):
        report = freeze.schema_candidate_report(
            self.admin_connect,
            environment="CI",
        )
        self.assertEqual(report["state"], freeze.CANDIDATE_STATE)
        self.assertTrue(report["migration_sha256_verified"])
        self.assertTrue(report["tables_exact"])
        self.assertTrue(report["required_indexes_present"])

    def test_runtime_module_has_zero_secret_or_provider_lookup(self):
        source = inspect.getsource(tls_binding)
        for banned in (
            "DATABASE_URL",
            "os.getenv",
            "os.environ",
            "streamlit.secrets",
            "render.com",
            "api.openai.com",
        ):
            self.assertNotIn(banned, source)

        policy = tls_binding.tls_direct_connection_policy()
        self.assertFalse(policy["production_allowed"])
        self.assertFalse(policy["production_connection_allowed"])
        self.assertTrue(policy["tls_required"])
        self.assertTrue(policy["certificate_verification_required"])
        self.assertTrue(policy["hostname_verification_required"])
        self.assertFalse(policy["plaintext_allowed"])
        self.assertFalse(policy["set_role_used"])
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
