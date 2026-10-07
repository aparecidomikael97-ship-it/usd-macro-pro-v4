from __future__ import annotations

import os
import unittest
from concurrent.futures import ThreadPoolExecutor

import psycopg

from aion_chat.store import StorageUnavailableError
import atlasquant_aion_chat_postgres_migration_rls_restore_ci_v1 as migration


APP_ROLE = "aion_chat_app_ci"
CONVERSATION_TABLE = "conversations"
APPEND_ONLY_TABLES = (
    "messages",
    "message_idempotency",
    "attachments",
    "checkpoints",
    "summaries",
    "access_audit",
)


class PostgresMigrationRlsRestoreCiV1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        dsn = str(os.environ.get("AION_CHAT_MIGRATION_CI_PG_DSN") or "").strip()
        if not dsn:
            raise RuntimeError("AION_CHAT_MIGRATION_CI_PG_DSN required")
        if "localhost" not in dsn and "127.0.0.1" not in dsn:
            raise RuntimeError("migration CI PostgreSQL must be loopback-only")
        cls._dsn = dsn

        def connect():
            return psycopg.connect(
                cls._dsn,
                autocommit=False,
                connect_timeout=5,
                application_name="atlasquant-aion-chat-migration-rls-ci",
            )

        cls.connect = staticmethod(connect)

    def setUp(self):
        self._reset_database_objects()
        first = migration.apply_migration(self.connect, environment="CI")
        self.assertEqual(first["state"], migration.APPLIED)
        self._create_and_grant_app_role()

    def tearDown(self):
        self._reset_database_objects()

    def _reset_database_objects(self):
        conn = self.connect()
        try:
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute(f"DROP SCHEMA IF EXISTS {migration.SCHEMA} CASCADE")
                cur.execute(
                    "SELECT 1 FROM pg_roles WHERE rolname=%s",
                    (APP_ROLE,),
                )
                if cur.fetchone():
                    cur.execute(f"DROP OWNED BY {APP_ROLE}")
                    cur.execute(f"DROP ROLE {APP_ROLE}")
        finally:
            conn.close()

    def _create_and_grant_app_role(self):
        conn = self.connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"CREATE ROLE {APP_ROLE} "
                    "NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE "
                    "NOINHERIT NOREPLICATION NOBYPASSRLS"
                )
                cur.execute(
                    f"GRANT USAGE ON SCHEMA {migration.SCHEMA} TO {APP_ROLE}"
                )
                cur.execute(
                    f"GRANT SELECT ON {migration.SCHEMA}.schema_meta TO {APP_ROLE}"
                )
                cur.execute(
                    f"GRANT SELECT,INSERT,UPDATE "
                    f"ON {migration.SCHEMA}.{CONVERSATION_TABLE} TO {APP_ROLE}"
                )
                for table in APPEND_ONLY_TABLES:
                    cur.execute(
                        f"GRANT SELECT,INSERT "
                        f"ON {migration.SCHEMA}.{table} TO {APP_ROLE}"
                    )
            conn.commit()
        finally:
            conn.close()

    def _app_connection(self, scope=None):
        conn = self.connect()
        with conn.cursor() as cur:
            cur.execute(f"SET ROLE {APP_ROLE}")
            if scope is not None:
                owner, tenant, workspace = scope
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
        return conn

    def _insert_conversation(self, conn, scope, conversation_id):
        owner, tenant, workspace = scope
        with conn.cursor() as cur:
            cur.execute(
                f"INSERT INTO {migration.SCHEMA}.conversations"
                "(owner_id,tenant_id,workspace_id,id,created_at,updated_at,"
                "archived,title,data) "
                "VALUES (%s,%s,%s,%s,%s,%s,FALSE,%s,%s::jsonb)",
                (
                    owner,
                    tenant,
                    workspace,
                    conversation_id,
                    "2026-10-07T00:00:00+00:00",
                    "2026-10-07T00:00:00+00:00",
                    "rls proof",
                    '{"tags":["ci"]}',
                ),
            )
        conn.commit()

    def test_migration_artifact_is_sha256_bound(self):
        artifact = migration.migration_artifact()
        self.assertTrue(artifact["checksum_valid"])
        self.assertEqual(
            artifact["actual_sha256"],
            migration.EXPECTED_MIGRATION_SHA256,
        )
        self.assertEqual(artifact["version"], migration.MIGRATION_VERSION)

    def test_repeat_migration_is_idempotent_and_checksum_verified(self):
        second = migration.apply_migration(self.connect, environment="CI")
        self.assertEqual(second["state"], migration.ALREADY_APPLIED)
        self.assertEqual(
            second["checksum"],
            migration.EXPECTED_MIGRATION_SHA256,
        )

    def test_applied_checksum_tamper_fails_closed(self):
        conn = self.connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"UPDATE {migration.SCHEMA}.schema_migrations "
                    "SET checksum=%s WHERE version=%s",
                    ("0" * 64, migration.MIGRATION_VERSION),
                )
            conn.commit()
        finally:
            conn.close()

        with self.assertRaises(migration.MigrationChecksumError):
            migration.apply_migration(self.connect, environment="CI")

    def test_concurrent_migration_is_serialized_by_advisory_lock(self):
        self._reset_database_objects()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(
                pool.map(
                    lambda _: migration.apply_migration(
                        self.connect,
                        environment="CI",
                    )["state"],
                    range(2),
                )
            )

        self.assertCountEqual(
            results,
            [migration.APPLIED, migration.ALREADY_APPLIED],
        )

    def test_missing_expected_migration_history_fails_closed(self):
        conn = self.connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"DELETE FROM {migration.SCHEMA}.schema_migrations "
                    "WHERE version=%s",
                    (migration.MIGRATION_VERSION,),
                )
            conn.commit()
        finally:
            conn.close()

        with self.assertRaises(StorageUnavailableError):
            migration.apply_migration(self.connect, environment="CI")

    def test_failed_migration_rolls_back_partial_ddl_and_history(self):
        self._reset_database_objects()
        conn = self.connect()
        try:
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute(f"CREATE SCHEMA {migration.SCHEMA}")
                cur.execute(
                    f"CREATE TABLE {migration.SCHEMA}.messages("
                    "preexisting INTEGER NOT NULL)"
                )
        finally:
            conn.close()

        with self.assertRaises(StorageUnavailableError):
            migration.apply_migration(self.connect, environment="CI")

        conn = self.connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT to_regclass(%s),to_regclass(%s),to_regclass(%s)",
                    (
                        f"{migration.SCHEMA}.schema_migrations",
                        f"{migration.SCHEMA}.conversations",
                        f"{migration.SCHEMA}.messages",
                    ),
                )
                history, conversations, preexisting = cur.fetchone()
                self.assertIsNone(history)
                self.assertIsNone(conversations)
                self.assertIsNotNone(preexisting)
            conn.rollback()
        finally:
            conn.close()

    def test_migration_health_proves_rls_policies_constraints_and_transaction(self):
        report = migration.migration_health_report(
            self.connect,
            environment="CI",
        )
        self.assertEqual(report["state"], migration.HEALTHY)
        self.assertTrue(report["migration_checksum_verified"])
        self.assertTrue(report["rls_enabled_and_forced"])
        self.assertEqual(
            report["rls_tables_present"],
            report["rls_tables_expected"],
        )
        self.assertEqual(
            report["policies_present"],
            report["policies_expected"],
        )
        self.assertEqual(
            report["constraints_present"],
            report["constraints_expected"],
        )
        self.assertTrue(report["transaction_healthy"])

    def test_missing_rls_force_flag_fails_health_closed(self):
        conn = self.connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"ALTER TABLE {migration.SCHEMA}.attachments "
                    "NO FORCE ROW LEVEL SECURITY"
                )
            conn.commit()
        finally:
            conn.close()

        report = migration.migration_health_report(
            self.connect,
            environment="CI",
        )
        self.assertEqual(report["state"], migration.FAILED)
        self.assertFalse(report["rls_enabled_and_forced"])

    def test_app_role_is_least_privilege_and_cannot_read_migration_history(self):
        conn = self.connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT rolsuper,rolcreatedb,rolcreaterole,rolreplication,"
                    "rolbypassrls FROM pg_roles WHERE rolname=%s",
                    (APP_ROLE,),
                )
                row = cur.fetchone()
                self.assertEqual(row, (False, False, False, False, False))
                cur.execute(
                    "SELECT has_schema_privilege(%s,%s,'USAGE'),"
                    "has_schema_privilege(%s,%s,'CREATE')",
                    (APP_ROLE, migration.SCHEMA, APP_ROLE, migration.SCHEMA),
                )
                self.assertEqual(cur.fetchone(), (True, False))
                cur.execute(
                    "SELECT "
                    "has_table_privilege(%s,%s,'UPDATE'),"
                    "has_table_privilege(%s,%s,'DELETE'),"
                    "has_table_privilege(%s,%s,'UPDATE'),"
                    "has_table_privilege(%s,%s,'DELETE'),"
                    "has_table_privilege(%s,%s,'DELETE')",
                    (
                        APP_ROLE,
                        f"{migration.SCHEMA}.messages",
                        APP_ROLE,
                        f"{migration.SCHEMA}.messages",
                        APP_ROLE,
                        f"{migration.SCHEMA}.access_audit",
                        APP_ROLE,
                        f"{migration.SCHEMA}.access_audit",
                        APP_ROLE,
                        f"{migration.SCHEMA}.conversations",
                    ),
                )
                self.assertEqual(
                    cur.fetchone(),
                    (False, False, False, False, False),
                )
            conn.rollback()
        finally:
            conn.close()

        app = self._app_connection(("mikael", "atlasquant-owner", "central"))
        try:
            with app.cursor() as cur:
                with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                    cur.execute(
                        f"SELECT * FROM {migration.SCHEMA}.schema_migrations"
                    )
            app.rollback()
        finally:
            app.close()

    def test_scope_context_is_transaction_local_and_clears_after_commit(self):
        scope = ("mikael", "atlasquant-owner", "central")
        app = self._app_connection(scope)
        try:
            self._insert_conversation(app, scope, "transaction-local-proof")
            with app.cursor() as cur:
                cur.execute(
                    f"SELECT count(*) FROM {migration.SCHEMA}.conversations"
                )
                self.assertEqual(cur.fetchone()[0], 0)
        finally:
            app.rollback()
            app.close()

    def test_append_only_tables_reject_update_and_delete(self):
        scope = ("mikael", "atlasquant-owner", "central")
        app = self._app_connection(scope)
        try:
            self._insert_conversation(app, scope, "append-only-parent")
        finally:
            app.close()

        app = self._app_connection(scope)
        try:
            with app.cursor() as cur:
                cur.execute(
                    f"INSERT INTO {migration.SCHEMA}.access_audit"
                    "(owner_id,tenant_id,workspace_id,id,operation,actor_id,"
                    "result,evidence_digest) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                    (
                        scope[0],
                        scope[1],
                        scope[2],
                        "audit-append-only",
                        "TEST",
                        "ci",
                        "OK",
                        "sha256:append-only-proof",
                    ),
                )
            app.commit()
        finally:
            app.close()

        app = self._app_connection(scope)
        try:
            with app.cursor() as cur:
                with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                    cur.execute(
                        f"UPDATE {migration.SCHEMA}.access_audit "
                        "SET result='MUTATED' WHERE id='audit-append-only'"
                    )
            app.rollback()
        finally:
            app.close()

        app = self._app_connection(scope)
        try:
            with app.cursor() as cur:
                with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                    cur.execute(
                        f"DELETE FROM {migration.SCHEMA}.access_audit "
                        "WHERE id='audit-append-only'"
                    )
            app.rollback()
        finally:
            app.close()

    def test_rls_missing_context_is_default_deny(self):
        scoped = self._app_connection(
            ("mikael", "atlasquant-owner", "central")
        )
        try:
            self._insert_conversation(
                scoped,
                ("mikael", "atlasquant-owner", "central"),
                "conv-owner",
            )
        finally:
            scoped.close()

        unscoped = self._app_connection()
        try:
            with unscoped.cursor() as cur:
                cur.execute(
                    f"SELECT count(*) FROM {migration.SCHEMA}.conversations"
                )
                self.assertEqual(cur.fetchone()[0], 0)
        finally:
            unscoped.rollback()
            unscoped.close()

    def test_rls_cross_scope_select_and_insert_fail_closed(self):
        owner_scope = ("mikael", "atlasquant-owner", "central")
        other_scope = ("other", "atlasquant-owner", "central")

        owner = self._app_connection(owner_scope)
        try:
            self._insert_conversation(owner, owner_scope, "owner-conv")
        finally:
            owner.close()

        other = self._app_connection(other_scope)
        try:
            with other.cursor() as cur:
                cur.execute(
                    f"SELECT count(*) FROM {migration.SCHEMA}.conversations "
                    "WHERE id=%s",
                    ("owner-conv",),
                )
                self.assertEqual(cur.fetchone()[0], 0)

                with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                    cur.execute(
                        f"INSERT INTO {migration.SCHEMA}.conversations"
                        "(owner_id,tenant_id,workspace_id,id,created_at,"
                        "updated_at,archived,title,data) "
                        "VALUES (%s,%s,%s,%s,%s,%s,FALSE,%s,%s::jsonb)",
                        (
                            owner_scope[0],
                            owner_scope[1],
                            owner_scope[2],
                            "malicious-cross-scope",
                            "2026-10-07T00:00:00+00:00",
                            "2026-10-07T00:00:00+00:00",
                            "blocked",
                            '{}',
                        ),
                    )
            other.rollback()
        finally:
            other.close()

    def test_rls_allows_only_matching_scope_rows(self):
        scopes = (
            ("mikael", "atlasquant-owner", "central"),
            ("other", "other-tenant", "other-workspace"),
        )
        for index, scope in enumerate(scopes):
            conn = self._app_connection(scope)
            try:
                self._insert_conversation(conn, scope, f"conv-{index}")
            finally:
                conn.close()

        for index, scope in enumerate(scopes):
            conn = self._app_connection(scope)
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        f"SELECT id FROM {migration.SCHEMA}.conversations "
                        "ORDER BY id"
                    )
                    self.assertEqual(
                        [row[0] for row in cur.fetchall()],
                        [f"conv-{index}"],
                    )
            finally:
                conn.rollback()
                conn.close()

    def test_restore_fixture_seed_and_report_before_backup(self):
        seeded = migration.seed_restore_fixture(
            self.connect,
            environment="CI",
        )
        self.assertEqual(seeded["state"], "RESTORE_FIXTURE_SEEDED")
        report = migration.restore_fixture_report(
            self.connect,
            environment="CI",
        )
        self.assertEqual(report["state"], migration.HEALTHY)
        self.assertTrue(report["conversation_restored"])
        self.assertTrue(report["audit_restored"])
        self.assertTrue(report["digest_verified"])

    def test_policy_forbids_production_runtime_authority(self):
        policy = migration.migration_policy()
        self.assertFalse(policy["application_startup_auto_migration"])
        self.assertTrue(policy["transaction_local_scope_context_required"])
        self.assertFalse(policy["application_delete_privilege_default"])
        self.assertFalse(policy["message_update_privilege_default"])
        self.assertTrue(policy["audit_append_only_role_profile"])
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

    def test_non_ci_environment_is_rejected(self):
        with self.assertRaises(ValueError):
            migration.apply_migration(
                self.connect,
                environment="PRODUCTION",
            )


if __name__ == "__main__":
    unittest.main()
