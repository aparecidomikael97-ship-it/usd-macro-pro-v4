from __future__ import annotations

import inspect
import os
import unittest

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo

from aion_chat.models import Message, Scope
from aion_chat.store import StorageUnavailableError
import atlasquant_aion_chat_direct_app_role_connection_ci_v1 as direct
import atlasquant_aion_chat_postgres_migration_rls_restore_ci_v1 as migration
import atlasquant_aion_chat_postgres_schema_candidate_freeze_v1 as freeze
from atlasquant_aion_chat_production_schema_binding_ci_v1 import (
    APPEND_ONLY_TABLES,
)


CI_PASSWORD = "atlasquant-ci-direct-role-only-v1"


class DirectAppRoleConnectionCiV1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        dsn = str(
            os.environ.get("AION_CHAT_DIRECT_ROLE_CI_ADMIN_DSN") or ""
        ).strip()
        if not dsn:
            raise RuntimeError("AION_CHAT_DIRECT_ROLE_CI_ADMIN_DSN required")
        if "localhost" not in dsn and "127.0.0.1" not in dsn:
            raise RuntimeError("direct-role CI PostgreSQL must be loopback-only")
        cls._admin_dsn = dsn

        def admin_connect():
            return psycopg.connect(
                cls._admin_dsn,
                autocommit=False,
                connect_timeout=5,
                application_name="atlasquant-aion-direct-role-admin-ci",
            )

        cls.admin_connect = staticmethod(admin_connect)
        cls._reset_all()

        applied = migration.apply_migration(cls.admin_connect, environment="CI")
        if applied["state"] != migration.APPLIED:
            raise RuntimeError(applied)

        cls._create_direct_login_role()

        params = conninfo_to_dict(cls._admin_dsn)
        params.update(
            user=direct.CI_DIRECT_APP_ROLE,
            password=CI_PASSWORD,
            application_name="atlasquant-aion-direct-role-app-ci",
        )
        cls._app_dsn = make_conninfo(**params)

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
                    (direct.CI_DIRECT_APP_ROLE,),
                )
                if cur.fetchone():
                    cur.execute(
                        sql.SQL("DROP OWNED BY {}").format(
                            sql.Identifier(direct.CI_DIRECT_APP_ROLE)
                        )
                    )
                    cur.execute(
                        sql.SQL("DROP ROLE {}").format(
                            sql.Identifier(direct.CI_DIRECT_APP_ROLE)
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
                        sql.Identifier(direct.CI_DIRECT_APP_ROLE),
                        sql.Literal(CI_PASSWORD),
                    )
                )
                cur.execute(
                    sql.SQL("GRANT USAGE ON SCHEMA {} TO {}").format(
                        sql.Identifier(migration.SCHEMA),
                        sql.Identifier(direct.CI_DIRECT_APP_ROLE),
                    )
                )
                cur.execute(
                    sql.SQL("GRANT SELECT ON {}.{} TO {}").format(
                        sql.Identifier(migration.SCHEMA),
                        sql.Identifier("schema_meta"),
                        sql.Identifier(direct.CI_DIRECT_APP_ROLE),
                    )
                )
                cur.execute(
                    sql.SQL(
                        "GRANT SELECT,INSERT,UPDATE ON {}.{} TO {}"
                    ).format(
                        sql.Identifier(migration.SCHEMA),
                        sql.Identifier("conversations"),
                        sql.Identifier(direct.CI_DIRECT_APP_ROLE),
                    )
                )
                for table in APPEND_ONLY_TABLES:
                    cur.execute(
                        sql.SQL("GRANT SELECT,INSERT ON {}.{} TO {}").format(
                            sql.Identifier(migration.SCHEMA),
                            sql.Identifier(table),
                            sql.Identifier(direct.CI_DIRECT_APP_ROLE),
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

        self.backend = direct.DirectLoginAuditedPostgresBackendCiV1(
            self.app_connect,
            environment="CI",
        )
        self.store = direct.DirectLoginAuditedPostgresChatStoreCiV1(
            self.backend,
            cursor_signing_key=b"atlasquant-direct-role-ci-cursor-key-v1",
        )
        self.scope = Scope("mikael", "atlasquant-owner", "central")
        self.other_scope = Scope("other", "atlasquant-owner", "central")
        self.conversation = self.store.create_conversation(
            self.scope,
            title="direct role owner conversation",
            metadata={"tags": ["direct-role", "ci"]},
        )

    def _message(self, index: int) -> Message:
        return Message(
            conversation_id=self.conversation.id,
            role="user",
            content=f"direct-role-message-{index}",
            metadata={"idempotency_key": f"direct-role-{index}"},
        )

    def test_health_proves_direct_login_and_least_privilege(self):
        report = self.store.storage_health()
        self.assertEqual(report["state"], direct.HEALTHY)
        self.assertTrue(report["direct_identity_healthy"])
        self.assertTrue(report["role_can_login"])
        self.assertTrue(report["least_privilege_role_healthy"])
        self.assertTrue(report["rls_enabled_and_forced"])
        self.assertTrue(report["append_only_privileges_healthy"])
        self.assertTrue(report["conversations_privileges_healthy"])
        self.assertTrue(report["schema_meta_read_only"])
        self.assertTrue(report["schema_create_denied"])
        self.assertTrue(report["migration_history_denied"])
        self.assertFalse(report["set_role_required"])

        conn = self.app_connect()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT session_user,current_user")
                self.assertEqual(
                    cur.fetchone(),
                    (
                        direct.CI_DIRECT_APP_ROLE,
                        direct.CI_DIRECT_APP_ROLE,
                    ),
                )
            conn.rollback()
        finally:
            conn.close()

    def test_admin_identity_miswire_fails_closed(self):
        backend = direct.DirectLoginAuditedPostgresBackendCiV1(
            self.admin_connect,
            environment="TEST",
        )
        self.assertEqual(backend.health_report()["state"], direct.FAILED)
        with self.assertRaises(StorageUnavailableError):
            backend.require_healthy()

    def test_wrong_password_fails_closed(self):
        params = conninfo_to_dict(self._app_dsn)
        params["password"] = "wrong-password"
        wrong_dsn = make_conninfo(**params)

        def broken_login():
            return psycopg.connect(
                wrong_dsn,
                autocommit=False,
                connect_timeout=2,
            )

        backend = direct.DirectLoginAuditedPostgresBackendCiV1(
            broken_login,
            environment="TEST",
        )
        self.assertEqual(backend.health_report()["state"], direct.FAILED)
        with self.assertRaises(StorageUnavailableError):
            backend.require_healthy()

    def test_direct_role_cannot_escalate_migrate_delete_or_create_schema_objects(self):
        conn = self.app_connect()
        try:
            with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                with conn.cursor() as cur:
                    cur.execute("SET ROLE postgres")
            conn.rollback()

            with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                with conn.cursor() as cur:
                    cur.execute(
                        f"SELECT version FROM "
                        f"{migration.SCHEMA}.schema_migrations"
                    )
            conn.rollback()

            with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                with conn.cursor() as cur:
                    cur.execute(
                        f"DELETE FROM {migration.SCHEMA}.conversations "
                        "WHERE id=%s",
                        (self.conversation.id,),
                    )
            conn.rollback()

            with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                with conn.cursor() as cur:
                    cur.execute(
                        f"CREATE TABLE {migration.SCHEMA}.forbidden_ci_table"
                        "(id integer)"
                    )
            conn.rollback()
        finally:
            conn.close()

    def test_real_store_mutations_and_audit_run_as_direct_role(self):
        first = self.store.append_message(self.scope, self._message(1))
        second = self.store.append_message(self.scope, self._message(2))
        self.assertEqual((first.sequence, second.sequence), (1, 2))

        receipts = self.backend.list_audit_receipts(self.scope)
        operations = [item["operation"] for item in receipts]
        self.assertEqual(
            operations,
            [
                "CONVERSATION_CREATE",
                "MESSAGE_APPEND",
                "MESSAGE_APPEND",
            ],
        )
        for receipt in receipts:
            self.assertEqual(receipt["actor_id"], self.scope.owner_id)
            self.assertTrue(receipt["evidence_digest"].startswith("sha256:"))

        with self.assertRaises(LookupError):
            self.store.get_conversation(
                self.other_scope,
                self.conversation.id,
            )

    def test_bound_cursor_pagination_runs_under_direct_login_rls(self):
        for index in range(1, 6):
            self.store.append_message(self.scope, self._message(index))
        first = self.store.list_messages(
            self.scope,
            self.conversation.id,
            page_size=2,
        )
        second = self.store.list_messages(
            self.scope,
            self.conversation.id,
            cursor=first.next_cursor,
            page_size=2,
        )
        third = self.store.list_messages(
            self.scope,
            self.conversation.id,
            cursor=second.next_cursor,
            page_size=2,
        )
        combined = first.items + second.items + third.items
        self.assertEqual([item.sequence for item in combined], [1, 2, 3, 4, 5])
        self.assertIsNone(third.next_cursor)

    def test_scope_context_is_transaction_local_for_direct_login(self):
        conn = self.backend._connection()
        try:
            self.backend._bind_scope(conn, self.scope)
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT current_setting('app.owner_id',true),"
                    "current_setting('app.tenant_id',true),"
                    "current_setting('app.workspace_id',true)"
                )
                self.assertEqual(
                    cur.fetchone(),
                    (
                        self.scope.owner_id,
                        self.scope.tenant_id,
                        self.scope.workspace_id,
                    ),
                )
            conn.commit()
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT current_setting('app.owner_id',true),"
                    "current_setting('app.tenant_id',true),"
                    "current_setting('app.workspace_id',true)"
                )
                cleared = cur.fetchone()
                self.assertTrue(
                    all(value in (None, "") for value in cleared),
                    cleared,
                )
        finally:
            conn.close()

    def test_role_or_privilege_drift_fails_health_closed(self):
        conn = self.admin_connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    sql.SQL("ALTER ROLE {} BYPASSRLS").format(
                        sql.Identifier(direct.CI_DIRECT_APP_ROLE)
                    )
                )
            conn.commit()
        finally:
            conn.close()
        try:
            report = self.backend.health_report()
            self.assertEqual(report["state"], direct.FAILED)
            self.assertFalse(report["least_privilege_role_healthy"])
        finally:
            conn = self.admin_connect()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        sql.SQL("ALTER ROLE {} NOBYPASSRLS").format(
                            sql.Identifier(direct.CI_DIRECT_APP_ROLE)
                        )
                    )
                conn.commit()
            finally:
                conn.close()

        conn = self.admin_connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    sql.SQL("GRANT DELETE ON {}.messages TO {}").format(
                        sql.Identifier(migration.SCHEMA),
                        sql.Identifier(direct.CI_DIRECT_APP_ROLE),
                    )
                )
            conn.commit()
        finally:
            conn.close()
        try:
            report = self.backend.health_report()
            self.assertEqual(report["state"], direct.FAILED)
            self.assertFalse(report["append_only_privileges_healthy"])
        finally:
            conn = self.admin_connect()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        sql.SQL("REVOKE DELETE ON {}.messages FROM {}").format(
                            sql.Identifier(migration.SCHEMA),
                            sql.Identifier(direct.CI_DIRECT_APP_ROLE),
                        )
                    )
                conn.commit()
            finally:
                conn.close()

    def test_schema_candidate_remains_frozen_after_role_binding(self):
        report = freeze.schema_candidate_report(
            self.admin_connect,
            environment="CI",
        )
        self.assertEqual(report["state"], freeze.CANDIDATE_STATE)
        self.assertTrue(report["migration_sha256_verified"])
        self.assertTrue(report["tables_exact"])
        self.assertTrue(report["access_audit_columns_exact"])
        self.assertTrue(report["required_indexes_present"])

    def test_module_has_no_secret_lookup_or_role_switch_authority(self):
        source = inspect.getsource(direct)
        for banned in (
            "DATABASE_URL",
            "os.getenv",
            "os.environ",
            "streamlit.secrets",
            "render.com",
            'execute("SET ROLE',
            'execute(f"SET ROLE',
        ):
            self.assertNotIn(banned, source)

        policy = direct.direct_app_role_connection_policy()
        self.assertFalse(policy["production_allowed"])
        self.assertFalse(policy["production_connection_allowed"])
        self.assertFalse(policy["set_role_used"])
        self.assertTrue(policy["direct_login_identity_required"])
        self.assertTrue(policy["forced_rls_required"])
        self.assertTrue(policy["audit_receipts_preserved"])
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
