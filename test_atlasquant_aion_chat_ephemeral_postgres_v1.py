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
from atlasquant_aion_chat_postgres_store_adapter_fake_v1 import CommitOutcomeUnknownError
import atlasquant_aion_chat_ephemeral_postgres_v1 as pg


class EphemeralPostgresV1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        dsn = str(os.environ.get("AION_CHAT_EPHEMERAL_PG_DSN") or "").strip()
        if not dsn:
            raise RuntimeError("AION_CHAT_EPHEMERAL_PG_DSN required for ephemeral integration test")
        if "localhost" not in dsn and "127.0.0.1" not in dsn:
            raise RuntimeError("ephemeral PostgreSQL must be loopback-only in this CI test")
        cls._dsn = dsn

        def connect():
            return psycopg.connect(
                cls._dsn,
                autocommit=False,
                connect_timeout=5,
                application_name="atlasquant-aion-chat-ephemeral-ci",
            )

        cls.connect = staticmethod(connect)
        pg.reset_ephemeral_schema(cls.connect)
        pg.install_ephemeral_schema(cls.connect)

    @classmethod
    def tearDownClass(cls):
        pg.reset_ephemeral_schema(cls.connect)

    def setUp(self):
        conn = self.connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"TRUNCATE TABLE "
                    f"{pg.DB_SCHEMA}.summaries,"
                    f"{pg.DB_SCHEMA}.checkpoints,"
                    f"{pg.DB_SCHEMA}.attachments,"
                    f"{pg.DB_SCHEMA}.message_idempotency,"
                    f"{pg.DB_SCHEMA}.messages,"
                    f"{pg.DB_SCHEMA}.conversations CASCADE"
                )
            conn.commit()
        finally:
            conn.close()
        self.backend = pg.EphemeralPostgresBackendV1(self.connect, environment="CI")
        self.store = pg.EphemeralPostgresChatStoreV1(self.backend)
        self.scope = Scope("mikael", "atlasquant-owner", "central")
        self.other_owner = Scope("other", "atlasquant-owner", "central")
        self.other_tenant = Scope("mikael", "other-tenant", "central")
        self.other_workspace = Scope("mikael", "atlasquant-owner", "other-workspace")
        self.conversation = self.store.create_conversation(
            self.scope,
            metadata={"tags": ["owner"]},
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

    def test_store_configuration_boundary_does_not_read_environment_or_database_url(self):
        source = inspect.getsource(pg)
        self.assertNotIn("os.getenv", source)
        self.assertNotIn("os.environ", source)
        self.assertNotIn("DATABASE_URL", source)
        policy = pg.ephemeral_policy()
        self.assertFalse(policy["production_allowed"])
        self.assertFalse(policy["environment_read_by_store"])
        self.assertFalse(policy["secret_lookup_by_store"])
        self.assertFalse(policy["database_url_read_by_store"])

    def test_health_proves_schema_and_fails_closed_for_wrong_schema_version(self):
        report = self.store.storage_health()
        self.assertEqual(report["state"], pg.HEALTHY)
        self.assertEqual(report["schema_version"], pg.SCHEMA_VERSION)
        self.assertTrue(report["scope_policy_healthy"])

        conn = self.connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"UPDATE {pg.DB_SCHEMA}.schema_meta SET version=%s WHERE name=%s",
                    (pg.SCHEMA_VERSION + 1, "aion_chat"),
                )
            conn.commit()
        finally:
            conn.close()
        with self.assertRaises(StorageUnavailableError):
            self.store.require_healthy()

        conn = self.connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"UPDATE {pg.DB_SCHEMA}.schema_meta SET version=%s WHERE name=%s",
                    (pg.SCHEMA_VERSION, "aion_chat"),
                )
            conn.commit()
        finally:
            conn.close()

    def test_connection_failure_is_fail_closed(self):
        def broken():
            raise OSError("synthetic CI connection failure")

        backend = pg.EphemeralPostgresBackendV1(broken, environment="TEST")
        report = backend.health_report()
        self.assertEqual(report["state"], pg.FAILED)
        with self.assertRaises(StorageUnavailableError):
            backend.require_healthy()

    def test_owner_tenant_workspace_scope_is_default_deny(self):
        for foreign in (self.other_owner, self.other_tenant, self.other_workspace):
            with self.subTest(foreign=foreign):
                with self.assertRaises(LookupError):
                    self.store.get_conversation(foreign, self.conversation.id)
        with self.assertRaises(TypeError):
            self.store.get_conversation(None, self.conversation.id)

    def test_atomic_append_and_duplicate_idempotency_return_original(self):
        first = self.store.append_message(
            self.scope, self.message("original", "same-key")
        )
        duplicate = self.store.append_message(
            self.scope, self.message("different", "same-key")
        )
        self.assertEqual(duplicate.id, first.id)
        self.assertEqual(duplicate.content, "original")
        self.assertEqual(duplicate.sequence, 1)
        persisted = self.store.get_conversation(self.scope, self.conversation.id)
        self.assertEqual(persisted.message_count, 1)
        self.assertEqual(
            len(self.store.list_messages(self.scope, self.conversation.id).items),
            1,
        )

    def test_concurrent_appends_have_unique_contiguous_sequences(self):
        def append(index):
            msg = Message(
                conversation_id=self.conversation.id,
                role="user",
                content=f"concurrent-{index}",
                metadata={"idempotency_key": f"concurrent-{index}"},
            )
            return self.store.append_message(self.scope, msg)

        with ThreadPoolExecutor(max_workers=8) as pool:
            stored = list(pool.map(append, range(8)))
        self.assertEqual(
            sorted(item.sequence for item in stored),
            list(range(1, 9)),
        )
        self.assertEqual(len({item.id for item in stored}), 8)
        conversation = self.store.get_conversation(
            self.scope, self.conversation.id
        )
        self.assertEqual(conversation.message_count, 8)

    def test_unknown_commit_requires_idempotency_reconciliation(self):
        self.backend.commit_outcome_unknown_once = True
        with self.assertRaises(CommitOutcomeUnknownError) as ctx:
            self.store.append_message(
                self.scope, self.message("unknown", "unknown-key")
            )
        self.assertEqual(ctx.exception.idempotency_key, "unknown-key")
        reconciled = self.store.reconcile_message_idempotency(
            self.scope,
            self.conversation.id,
            "unknown-key",
        )
        self.assertIsNotNone(reconciled)
        self.assertEqual(reconciled.content, "unknown")
        self.assertEqual(
            len(self.store.list_messages(self.scope, self.conversation.id).items),
            1,
        )

    def test_attachment_metadata_is_scoped(self):
        digest = "a" * 64
        attachment = Attachment(
            conversation_id=self.conversation.id,
            name="evidence.txt",
            mime_type="text/plain",
            size=1,
            digest=digest,
            storage_reference=digest + ".blob",
        )
        stored = self.store.add_attachment_metadata(self.scope, attachment)
        loaded = self.store.get_attachment(
            self.scope, self.conversation.id, stored.id
        )
        self.assertEqual(loaded.id, stored.id)
        with self.assertRaises(LookupError):
            self.store.get_attachment(
                self.other_owner, self.conversation.id, stored.id
            )

    def test_checkpoint_coverage_is_monotonic_and_bounded(self):
        message = self.store.append_message(self.scope, self.message())
        first = ConversationCheckpoint(
            conversation_id=self.conversation.id,
            through_sequence=message.sequence,
        )
        self.store.save_checkpoint(self.scope, first)
        with self.assertRaisesRegex(ValueError, "coverage must advance"):
            self.store.save_checkpoint(
                self.scope,
                ConversationCheckpoint(
                    conversation_id=self.conversation.id,
                    through_sequence=message.sequence,
                ),
            )
        with self.assertRaisesRegex(ValueError, "coverage beyond conversation"):
            self.store.save_checkpoint(
                self.scope,
                ConversationCheckpoint(
                    conversation_id=self.conversation.id,
                    through_sequence=message.sequence + 2,
                ),
            )

    def test_summary_sources_are_same_scope_and_within_coverage(self):
        one = self.store.append_message(self.scope, self.message("one", "one"))
        two = self.store.append_message(self.scope, self.message("two", "two"))
        with self.assertRaisesRegex(ValueError, "source beyond coverage"):
            self.store.save_context_summary(
                self.scope,
                ContextSummary(
                    conversation_id=self.conversation.id,
                    through_sequence=one.sequence,
                    content="bad",
                    source_message_ids=[two.id],
                ),
            )
        good = ContextSummary(
            conversation_id=self.conversation.id,
            through_sequence=two.sequence,
            content="good",
            source_message_ids=[one.id, two.id],
        )
        self.store.save_context_summary(self.scope, good)
        self.assertEqual(
            self.store.get_latest_summary(
                self.scope, self.conversation.id
            ).id,
            good.id,
        )

    def test_retrieval_is_scope_bound_and_limit_bounded(self):
        for index in range(5):
            self.store.append_message(
                self.scope,
                self.message(f"alpha beta {index}", f"r-{index}"),
            )
        hits = self.store.retrieve_messages(
            self.scope,
            self.conversation.id,
            "beta",
            before_sequence=999,
            limit=2,
        )
        self.assertEqual(len(hits), 2)
        with self.assertRaises(LookupError):
            self.store.retrieve_messages(
                self.other_tenant,
                self.conversation.id,
                "beta",
                before_sequence=999,
                limit=2,
            )
        with self.assertRaises(ValueError):
            self.store.retrieve_messages(
                self.scope,
                self.conversation.id,
                "beta",
                before_sequence=999,
                limit=201,
            )

    def test_nonempty_cursor_fails_closed_until_bound_cursor_stage(self):
        with self.assertRaisesRegex(
            ValueError, "cursor pagination is not implemented"
        ):
            self.store.list_messages(
                self.scope,
                self.conversation.id,
                cursor="foreign-or-untrusted-cursor",
            )
        with self.assertRaisesRegex(
            ValueError, "cursor pagination is not implemented"
        ):
            self.store.list_conversations(
                self.other_workspace,
                cursor="untrusted-cursor",
            )

    def test_explicit_schema_install_is_not_store_startup_migration(self):
        source = inspect.getsource(pg.EphemeralPostgresBackendV1.__init__)
        self.assertNotIn("install_ephemeral_schema", source)
        self.assertTrue(
            pg.ephemeral_policy()["explicit_schema_install_only"]
        )

    def test_zero_provider_billing_deploy_worker_external_or_core_execution(self):
        policy = pg.ephemeral_policy()
        for key in (
            "production_allowed",
            "provider_called",
            "billing_executed",
            "deploy_executed",
            "worker_armed",
            "external_action_executed",
            "core_checkpoint_write",
        ):
            self.assertIs(policy[key], False, key)
        names = set(dir(self.store))
        self.assertNotIn("execute_provider", names)
        self.assertNotIn("bill", names)


if __name__ == "__main__":
    unittest.main()
