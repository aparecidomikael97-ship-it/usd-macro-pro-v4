"""A193: REAL AION Chat SQLite fail-closed-after-close regression.

All content is synthetic, entirely local stdlib SQLite. This verifies local
handle state ONLY; it does NOT prove authorization, root-of-trust,
independent anti-rollback, native same-inode P0 or provider no-effect.
"""
from pathlib import Path
import tempfile
import unittest

from aion_chat.models import (
    Attachment, ConversationCheckpoint, ContextSummary, Message, Scope,
)
from aion_chat.store import (
    SQLiteChatStore, StorageUnavailableError, FAILED,
)
from atlasquant_aion_chat_product_bridge import validate_product_binding


class A193SQLiteClosedStoreFailClosedLab(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "chat.sqlite3"
        self.scope = Scope("synthetic-owner", "synthetic-tenant", "trader")
        self.store = SQLiteChatStore(self.path)
        self.addCleanup(self.store.close)
        self.conv = self.store.create_conversation(self.scope, "SYNTHETIC_PRIVATE")
        self.msg = self.store.append_message(
            self.scope, Message(self.conv.id, "user", "synthetic-only-data"),
        )
        self.store.close()

    def closed(self, callback):
        with self.assertRaises(StorageUnavailableError) as cm:
            callback()
        self.assertIn("closed", str(cm.exception))

    def test_get_conversation_denies(self):
        self.closed(lambda: self.store.get_conversation(self.scope, self.conv.id))

    def test_get_nonexistent_conversation_does_not_disclose_state(self):
        self.closed(lambda: self.store.get_conversation(self.scope, "unknown"))

    def test_list_conversations_denies(self):
        self.closed(lambda: self.store.list_conversations(self.scope))

    def test_search_conversations_denies(self):
        self.closed(lambda: self.store.search_conversations(self.scope, "SYNTHETIC"))

    def test_archive_denies(self):
        self.closed(lambda: self.store.archive_conversation(self.scope, self.conv.id))

    def test_create_denies(self):
        self.closed(lambda: self.store.create_conversation(self.scope, "blocked"))

    def test_get_message_denies(self):
        self.closed(lambda: self.store.get_message(self.scope, self.conv.id, self.msg.id))

    def test_list_messages_denies(self):
        self.closed(lambda: self.store.list_messages(self.scope, self.conv.id))

    def test_append_message_denies(self):
        self.closed(
            lambda: self.store.append_message(
                self.scope, Message(self.conv.id, "user", "should-never-append"),
            )
        )

    def test_add_attachment_metadata_denies_before_any_write(self):
        a = Attachment(
            self.conv.id, "local.txt", "text/plain", 4, "a" * 64, "a" * 64 + ".blob",
        )
        self.closed(lambda: self.store.add_attachment_metadata(self.scope, a))

    def test_get_attachment_denies(self):
        self.closed(lambda: self.store.get_attachment(self.scope, self.conv.id, "fake-id"))

    def test_save_checkpoint_denies(self):
        cp = ConversationCheckpoint(self.conv.id, 1)
        self.closed(lambda: self.store.save_checkpoint(self.scope, cp))

    def test_get_latest_checkpoint_denies(self):
        self.closed(lambda: self.store.get_latest_checkpoint(self.scope, self.conv.id))

    def test_save_context_summary_denies(self):
        summary = ContextSummary(self.conv.id, 1, "synthetic", [])
        self.closed(lambda: self.store.save_context_summary(self.scope, summary))

    def test_get_latest_context_summary_denies(self):
        self.closed(lambda: self.store.get_latest_summary(self.scope, self.conv.id))

    def test_retrieve_messages_denies(self):
        self.closed(lambda: self.store.retrieve_messages(
            self.scope, self.conv.id, "synthetic", before_sequence=2,
        ))

    def test_backup_denies(self):
        self.closed(lambda: self.store.backup_to(
            Path(self.tmp.name) / "closed-backup.sqlite3",
        ))

    def test_wal_checkpoint_denies(self):
        self.closed(lambda: self.store.wal_checkpoint("PASSIVE"))

    def test_health_reports_failed_when_closed(self):
        report = self.store.storage_health(deep=True)
        self.assertEqual(report["state"], FAILED)
        self.assertEqual(report["reason"], "STORE_CLOSED")

    def test_close_is_idempotent(self):
        self.store.close()
        self.store.close()
        self.closed(lambda: self.store.get_conversation(self.scope, self.conv.id))

    def test_closed_store_cannot_reopen_via_method_but_new_store_preserves_data(self):
        self.closed(lambda: self.store.get_conversation(self.scope, self.conv.id))
        with_store = SQLiteChatStore(self.path)
        try:
            self.assertEqual(
                with_store.get_conversation(self.scope, self.conv.id).id,
                self.conv.id,
            )
            self.assertEqual(
                with_store.get_message(self.scope, self.conv.id, self.msg.id).content,
                "synthetic-only-data",
            )
            self.assertEqual(
                with_store.get_conversation(self.scope, self.conv.id).message_count,
                1,
            )
        finally:
            with_store.close()

    def test_raw_scope_is_still_caller_constructible_expected_red(self):
        # NOT a solved security issue. A malicious caller that can create
        # a Scope object and access the store can copy three identifiers.
        raw = Scope("synthetic-owner", "synthetic-tenant", "trader")
        reopened = SQLiteChatStore(self.path)
        try:
            self.assertEqual(
                reopened.get_conversation(raw, self.conv.id).title,
                "SYNTHETIC_PRIVATE",
            )
        finally:
            reopened.close()
        print("A193_SCOPE_FORGERY=UNCHANGED_REQUIRES_REAL_AUTHENTICATION_RED", flush=True)

    def test_product_binding_trusts_host_access_mapping_expected_red(self):
        # A product binding is NOT a standalone authenticator. If the host
        # passed user-controlled fields without server verification, this
        # synthetic forged dict looks BOUND despite no password check.
        forged = {
            "allowed": True,
            "mode": "AUTHENTICATED",
            "role": "ADMIN",
            "session": {
                "role": "ADMIN",
                "username": "synthetic-owner",
                "credential_fingerprint": "caller-crafted-nonempty",
                "permissions": ["app:read", "aion:admin"],
            },
        }
        decision = validate_product_binding(forged, self.scope)
        self.assertTrue(decision["bound"])
        self.assertTrue(decision["authenticated"])
        self.assertFalse(decision["grants_authority"])
        print("A193_HOST_ACCESS_CLAIMS=NOT_INDEPENDENT_AUTHENTICATION_RED", flush=True)


if __name__ == "__main__":
    unittest.main()
