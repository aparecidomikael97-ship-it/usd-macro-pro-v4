from __future__ import annotations

import inspect
import unittest

from aion_chat.models import Attachment, ContextSummary, ConversationCheckpoint, Message, Scope
from aion_chat.store import AionChatStore, StorageUnavailableError

import atlasquant_aion_chat_postgres_store_adapter_fake_v1 as fake


class PostgresStoreAdapterFakeV1Tests(unittest.TestCase):
    def setUp(self):
        self.backend = fake.FakePostgresBackend()
        self.store = fake.PostgresChatStoreAdapterSkeleton(self.backend)
        self.scope = Scope("mikael", "atlasquant-owner", "central")
        self.other = Scope("other", "atlasquant-owner", "central")
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

    def test_protocol_methods_are_present(self):
        required = {
            name for name, value in inspect.getmembers(AionChatStore)
            if callable(value) and not name.startswith("_")
        }
        for name in required:
            self.assertTrue(callable(getattr(self.store, name, None)), name)

    def test_policy_proves_zero_real_db_or_execution(self):
        policy = fake.skeleton_policy()
        self.assertTrue(policy["fake_backend_only"])
        for key in (
            "postgres_client_imported",
            "connection_opened",
            "sql_executed",
            "credentials_loaded",
            "secrets_loaded",
            "network_called",
            "provider_called",
            "billing_executed",
            "deploy_executed",
            "worker_armed",
            "external_action_executed",
            "core_checkpoint_write",
        ):
            self.assertIs(policy[key], False, key)

    def test_scope_is_fail_closed(self):
        with self.assertRaises(LookupError):
            self.store.get_conversation(self.other, self.conversation.id)
        with self.assertRaises(TypeError):
            self.store.get_conversation(None, self.conversation.id)

    def test_append_is_atomic_and_idempotent(self):
        first = self.store.append_message(self.scope, self.message())
        duplicate = self.store.append_message(self.scope, self.message(content="different"))
        self.assertEqual(duplicate.id, first.id)
        self.assertEqual(duplicate.content, first.content)
        self.assertEqual(duplicate.sequence, 1)
        conversation = self.store.get_conversation(self.scope, self.conversation.id)
        self.assertEqual(conversation.message_count, 1)
        self.assertEqual(len(self.store.list_messages(self.scope, self.conversation.id).items), 1)

    def test_idempotency_key_is_required(self):
        message = Message(
            conversation_id=self.conversation.id,
            role="user",
            content="x",
        )
        with self.assertRaisesRegex(ValueError, "idempotency_key required"):
            self.store.append_message(self.scope, message)

    def test_unknown_commit_requires_explicit_reconciliation(self):
        self.backend.commit_outcome_unknown_once = True
        with self.assertRaises(fake.CommitOutcomeUnknownError) as ctx:
            self.store.append_message(self.scope, self.message(key="unknown-1"))
        self.assertEqual(ctx.exception.idempotency_key, "unknown-1")

        reconciled = self.store.reconcile_message_idempotency(
            self.scope,
            self.conversation.id,
            "unknown-1",
        )
        self.assertIsNotNone(reconciled)
        self.assertEqual(reconciled.sequence, 1)
        self.assertEqual(
            len(self.store.list_messages(self.scope, self.conversation.id).items),
            1,
        )

    def test_unhealthy_backend_fails_closed(self):
        self.backend.healthy = False
        with self.assertRaises(StorageUnavailableError):
            self.store.get_conversation(self.scope, self.conversation.id)

    def test_schema_mismatch_fails_closed(self):
        self.backend.schema_version = fake.SCHEMA_VERSION + 1
        with self.assertRaises(StorageUnavailableError):
            self.store.list_conversations(self.scope)

    def test_attachment_scope_is_enforced(self):
        attachment = Attachment(
            conversation_id=self.conversation.id,
            name="a.txt",
            mime_type="text/plain",
            size=1,
            digest="sha256:" + "a" * 64,
            storage_reference="metadata-only",
        )
        stored = self.store.add_attachment_metadata(self.scope, attachment)
        self.assertEqual(
            self.store.get_attachment(self.scope, self.conversation.id, stored.id).id,
            stored.id,
        )
        with self.assertRaises(LookupError):
            self.store.get_attachment(self.other, self.conversation.id, stored.id)

    def test_checkpoint_must_advance(self):
        msg = self.store.append_message(self.scope, self.message())
        first = ConversationCheckpoint(
            conversation_id=self.conversation.id,
            through_sequence=msg.sequence,
        )
        self.store.save_checkpoint(self.scope, first)
        with self.assertRaisesRegex(ValueError, "coverage must advance"):
            self.store.save_checkpoint(
                self.scope,
                ConversationCheckpoint(
                    conversation_id=self.conversation.id,
                    through_sequence=msg.sequence,
                ),
            )

    def test_summary_sources_must_be_in_coverage(self):
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

    def test_retrieval_is_scoped_and_bounded(self):
        self.store.append_message(self.scope, self.message("alpha beta", "a"))
        second = self.store.append_message(self.scope, self.message("beta gamma", "b"))
        hits = self.store.retrieve_messages(
            self.scope,
            self.conversation.id,
            "beta",
            before_sequence=second.sequence + 1,
            limit=1,
        )
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].id, second.id)

    def test_store_has_no_provider_surface(self):
        names = set(dir(self.store))
        self.assertNotIn("provider", names)
        self.assertNotIn("execute_provider", names)
        self.assertNotIn("bill", names)


if __name__ == "__main__":
    unittest.main()
