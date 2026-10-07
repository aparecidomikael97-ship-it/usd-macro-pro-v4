from __future__ import annotations

import inspect
import os
import unittest
from concurrent.futures import ThreadPoolExecutor

import psycopg

from aion_chat.models import (
    Attachment,
    ContextSummary,
    ConversationCheckpoint,
    Message,
    Scope,
)
from aion_chat.store import AionChatStore, StorageUnavailableError
from atlasquant_aion_chat_postgres_store_adapter_fake_v1 import (
    CommitOutcomeUnknownError,
)
import atlasquant_aion_chat_ephemeral_postgres_v1 as ephemeral
import atlasquant_aion_chat_postgres_migration_rls_restore_ci_v1 as migration
import atlasquant_aion_chat_production_schema_binding_ci_v1 as binding


class ProductionSchemaBindingCiV1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        dsn = str(os.environ.get("AION_CHAT_PRODUCTION_SCHEMA_CI_PG_DSN") or "").strip()
        if not dsn:
            raise RuntimeError("AION_CHAT_PRODUCTION_SCHEMA_CI_PG_DSN required")
        if "localhost" not in dsn and "127.0.0.1" not in dsn:
            raise RuntimeError("production-schema CI PostgreSQL must be loopback-only")
        cls._dsn = dsn

        def connect():
            return psycopg.connect(
                cls._dsn,
                autocommit=False,
                connect_timeout=5,
                application_name="atlasquant-aion-production-schema-binding-ci",
            )

        cls.connect = staticmethod(connect)
        cls._reset_all()
        applied = migration.apply_migration(cls.connect, environment="CI")
        if applied["state"] != migration.APPLIED:
            raise RuntimeError(applied)
        cls._create_app_role()

    @classmethod
    def tearDownClass(cls):
        cls._reset_all()

    @classmethod
    def _reset_all(cls):
        conn = cls.connect()
        try:
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute(f"DROP SCHEMA IF EXISTS {migration.SCHEMA} CASCADE")
                cur.execute(
                    "SELECT 1 FROM pg_roles WHERE rolname=%s",
                    (binding.CI_APP_ROLE,),
                )
                if cur.fetchone():
                    cur.execute(f"DROP OWNED BY {binding.CI_APP_ROLE}")
                    cur.execute(f"DROP ROLE {binding.CI_APP_ROLE}")
        finally:
            conn.close()

    @classmethod
    def _create_app_role(cls):
        conn = cls.connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"CREATE ROLE {binding.CI_APP_ROLE} "
                    "NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE "
                    "NOINHERIT NOREPLICATION NOBYPASSRLS"
                )
                cur.execute(
                    f"GRANT USAGE ON SCHEMA {migration.SCHEMA} "
                    f"TO {binding.CI_APP_ROLE}"
                )
                cur.execute(
                    f"GRANT SELECT ON {migration.SCHEMA}.schema_meta "
                    f"TO {binding.CI_APP_ROLE}"
                )
                cur.execute(
                    f"GRANT SELECT,INSERT,UPDATE "
                    f"ON {migration.SCHEMA}.conversations "
                    f"TO {binding.CI_APP_ROLE}"
                )
                for table in binding.APPEND_ONLY_TABLES:
                    cur.execute(
                        f"GRANT SELECT,INSERT "
                        f"ON {migration.SCHEMA}.{table} "
                        f"TO {binding.CI_APP_ROLE}"
                    )
            conn.commit()
        finally:
            conn.close()

    def setUp(self):
        conn = self.connect()
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

        self.backend = binding.ProductionSchemaBoundPostgresBackendCiV1(
            self.connect,
            environment="CI",
        )
        self.store = binding.ProductionSchemaBoundPostgresChatStoreCiV1(
            self.backend,
            cursor_signing_key=b"atlasquant-production-schema-ci-cursor-key-v1",
        )
        self.scope = Scope("mikael", "atlasquant-owner", "central")
        self.other_owner = Scope("other", "atlasquant-owner", "central")
        self.other_tenant = Scope("mikael", "other-tenant", "central")
        self.other_workspace = Scope(
            "mikael",
            "atlasquant-owner",
            "other-workspace",
        )
        self.conversation = self.store.create_conversation(
            self.scope,
            title="Owner conversation",
            metadata={"tags": ["owner", "ci"]},
        )

    def message(self, content="hello", key="turn-1"):
        return Message(
            conversation_id=self.conversation.id,
            role="user",
            content=content,
            metadata={"idempotency_key": key},
        )

    def test_protocol_surface_matches_aion_chat_store(self):
        required = {
            name
            for name, value in inspect.getmembers(AionChatStore)
            if callable(value) and not name.startswith("_")
        }
        missing = sorted(
            name for name in required if not callable(getattr(self.store, name, None))
        )
        self.assertEqual(missing, [])

    def test_health_proves_production_schema_rls_and_least_privilege(self):
        report = self.store.storage_health()
        self.assertEqual(report["state"], binding.HEALTHY)
        self.assertEqual(report["production_schema"], migration.SCHEMA)
        self.assertTrue(report["rls_enabled_and_forced"])
        self.assertEqual(
            report["rls_tables_present"],
            report["rls_tables_expected"],
        )
        self.assertEqual(
            report["policies_present"],
            report["policies_expected"],
        )
        self.assertTrue(report["least_privilege_role_healthy"])
        self.assertTrue(report["append_only_privileges_healthy"])
        self.assertTrue(report["schema_create_denied"])
        self.assertTrue(report["migration_history_denied"])
        self.assertTrue(report["transaction_local_scope_required"])

    def test_production_like_schema_accepts_real_conversation_model(self):
        loaded = self.store.get_conversation(
            self.scope,
            self.conversation.id,
        )
        self.assertEqual(loaded.id, self.conversation.id)
        self.assertEqual(loaded.created_at, self.conversation.created_at)
        conn = self.connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT created_at,updated_at FROM "
                    f"{migration.SCHEMA}.conversations "
                    "WHERE owner_id=%s AND tenant_id=%s "
                    "AND workspace_id=%s AND id=%s",
                    (
                        self.scope.owner_id,
                        self.scope.tenant_id,
                        self.scope.workspace_id,
                        self.conversation.id,
                    ),
                )
                row = cur.fetchone()
            conn.rollback()
        finally:
            conn.close()
        self.assertIsNotNone(row)
        self.assertEqual(row[0], self.conversation.created_at)

    def test_scope_is_enforced_by_app_predicates_and_rls(self):
        for foreign in (
            self.other_owner,
            self.other_tenant,
            self.other_workspace,
        ):
            with self.subTest(foreign=foreign):
                with self.assertRaises(LookupError):
                    self.store.get_conversation(
                        foreign,
                        self.conversation.id,
                    )

        conn = self.connect()
        try:
            with conn.cursor() as cur:
                cur.execute(f"SET ROLE {binding.CI_APP_ROLE}")
                cur.execute(
                    "SELECT set_config('app.owner_id',%s,true)",
                    (self.other_owner.owner_id,),
                )
                cur.execute(
                    "SELECT set_config('app.tenant_id',%s,true)",
                    (self.other_owner.tenant_id,),
                )
                cur.execute(
                    "SELECT set_config('app.workspace_id',%s,true)",
                    (self.other_owner.workspace_id,),
                )
                cur.execute(
                    f"SELECT count(*) FROM {migration.SCHEMA}.conversations "
                    "WHERE id=%s",
                    (self.conversation.id,),
                )
                self.assertEqual(cur.fetchone()[0], 0)
            conn.rollback()
        finally:
            conn.close()

    def test_atomic_append_concurrency_and_idempotency_on_rls_schema(self):
        first = self.store.append_message(
            self.scope,
            self.message("first", "same-key"),
        )
        duplicate = self.store.append_message(
            self.scope,
            self.message("different", "same-key"),
        )
        self.assertEqual(duplicate.id, first.id)
        self.assertEqual(duplicate.content, "first")
        self.assertEqual(duplicate.sequence, 1)

        def append(index):
            return self.store.append_message(
                self.scope,
                Message(
                    conversation_id=self.conversation.id,
                    role="user",
                    content=f"concurrent-{index}",
                    metadata={"idempotency_key": f"concurrent-{index}"},
                ),
            )

        with ThreadPoolExecutor(max_workers=6) as pool:
            stored = list(pool.map(append, range(6)))

        self.assertEqual(
            sorted(item.sequence for item in stored),
            list(range(2, 8)),
        )
        conversation = self.store.get_conversation(
            self.scope,
            self.conversation.id,
        )
        self.assertEqual(conversation.message_count, 7)

    def test_unknown_commit_reconciles_through_scope_bound_idempotency(self):
        self.backend.commit_outcome_unknown_once = True
        with self.assertRaises(CommitOutcomeUnknownError):
            self.store.append_message(
                self.scope,
                self.message("unknown", "unknown-key"),
            )
        reconciled = self.store.reconcile_message_idempotency(
            self.scope,
            self.conversation.id,
            "unknown-key",
        )
        self.assertIsNotNone(reconciled)
        self.assertEqual(reconciled.content, "unknown")
        with self.assertRaises(LookupError):
            self.store.get_conversation(
                self.other_tenant,
                self.conversation.id,
            )

    def test_bound_cursor_pagination_survives_production_schema_rls(self):
        for index in range(5):
            self.store.append_message(
                self.scope,
                self.message(f"page-{index}", f"page-{index}"),
            )
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

        with self.assertRaisesRegex(ValueError, "cursor invalid or not bound"):
            self.store.list_messages(
                self.other_owner,
                self.conversation.id,
                cursor=first.next_cursor,
                page_size=2,
            )

    def test_search_filters_and_retrieval_run_through_rls_schema(self):
        alpha = self.store.create_conversation(
            self.scope,
            title="alpha owner",
            metadata={"tags": ["alpha"]},
        )
        self.store.append_message(
            self.scope,
            Message(
                conversation_id=alpha.id,
                role="user",
                content="needle in durable postgres",
                metadata={"idempotency_key": "search-1"},
            ),
        )
        page = self.store.list_conversations(
            self.scope,
            query="needle",
            tag="alpha",
            page_size=10,
        )
        self.assertEqual([item.id for item in page.items], [alpha.id])

        hits = self.store.retrieve_messages(
            self.scope,
            alpha.id,
            "durable",
            before_sequence=999,
            limit=10,
        )
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].content, "needle in durable postgres")

    def test_attachment_checkpoint_and_summary_preserve_scope(self):
        message = self.store.append_message(
            self.scope,
            self.message("evidence", "evidence-1"),
        )
        attachment = Attachment(
            conversation_id=self.conversation.id,
            name="evidence.txt",
            mime_type="text/plain",
            size=1,
            digest="a" * 64,
            storage_reference=("a" * 64) + ".blob",
        )
        saved_attachment = self.store.add_attachment_metadata(
            self.scope,
            attachment,
        )
        self.assertEqual(
            self.store.get_attachment(
                self.scope,
                self.conversation.id,
                saved_attachment.id,
            ).id,
            saved_attachment.id,
        )

        checkpoint = ConversationCheckpoint(
            conversation_id=self.conversation.id,
            through_sequence=message.sequence,
        )
        self.store.save_checkpoint(self.scope, checkpoint)
        self.assertEqual(
            self.store.get_latest_checkpoint(
                self.scope,
                self.conversation.id,
            ).id,
            checkpoint.id,
        )

        summary = ContextSummary(
            conversation_id=self.conversation.id,
            through_sequence=message.sequence,
            content="durable summary",
            source_message_ids=[message.id],
        )
        self.store.save_context_summary(self.scope, summary)
        self.assertEqual(
            self.store.get_latest_summary(
                self.scope,
                self.conversation.id,
            ).id,
            summary.id,
        )

        with self.assertRaises(LookupError):
            self.store.get_attachment(
                self.other_workspace,
                self.conversation.id,
                saved_attachment.id,
            )

    def test_scope_context_is_transaction_local_at_real_adapter_boundary(self):
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

    def test_health_fails_closed_if_rls_or_role_privileges_drift(self):
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

        try:
            report = self.store.storage_health()
            self.assertEqual(report["state"], binding.FAILED)
            self.assertFalse(report["rls_enabled_and_forced"])
            with self.assertRaises(StorageUnavailableError):
                self.store.require_healthy()
        finally:
            conn = self.connect()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        f"ALTER TABLE {migration.SCHEMA}.attachments "
                        "FORCE ROW LEVEL SECURITY"
                    )
                conn.commit()
            finally:
                conn.close()

        conn = self.connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"GRANT DELETE ON {migration.SCHEMA}.messages "
                    f"TO {binding.CI_APP_ROLE}"
                )
            conn.commit()
        finally:
            conn.close()

        try:
            report = self.store.storage_health()
            self.assertEqual(report["state"], binding.FAILED)
            self.assertFalse(report["append_only_privileges_healthy"])
        finally:
            conn = self.connect()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        f"REVOKE DELETE ON {migration.SCHEMA}.messages "
                        f"FROM {binding.CI_APP_ROLE}"
                    )
                conn.commit()
            finally:
                conn.close()

    def test_configuration_policy_has_zero_production_authority(self):
        source = inspect.getsource(binding)
        self.assertNotIn("DATABASE_URL", source)
        self.assertNotIn("os.getenv", source)
        self.assertNotIn("os.environ", source)
        self.assertNotIn("streamlit.secrets", source)

        policy = binding.production_schema_binding_policy()
        self.assertFalse(policy["production_allowed"])
        self.assertFalse(policy["production_connection_allowed"])
        self.assertTrue(policy["scope_context_transaction_local"])
        self.assertTrue(policy["forced_rls_required"])
        self.assertTrue(policy["least_privilege_role_required"])
        self.assertTrue(policy["append_only_privilege_profile_required"])
        for key in (
            "provider_called",
            "billing_executed",
            "deploy_executed",
            "worker_armed",
            "external_action_executed",
            "core_checkpoint_write",
        ):
            self.assertIs(policy[key], False, key)

    def test_connection_failure_is_fail_closed(self):
        def broken():
            raise OSError("synthetic CI-only connection failure")

        backend = binding.ProductionSchemaBoundPostgresBackendCiV1(
            broken,
            environment="TEST",
        )
        report = backend.health_report()
        self.assertEqual(report["state"], binding.FAILED)
        with self.assertRaises(StorageUnavailableError):
            backend.require_healthy()


if __name__ == "__main__":
    unittest.main()
