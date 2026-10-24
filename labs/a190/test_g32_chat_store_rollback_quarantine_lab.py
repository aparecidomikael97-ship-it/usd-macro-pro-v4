"""A190 G32 — real SQLiteChatStore write-path quarantine, synthetic failures.

No real disk faults, power loss, independent witness or provider effects.
Passing tests show local failure containment, not external custody.
"""
from pathlib import Path
import sqlite3
import tempfile
import unittest

from aion_chat.models import (
    Scope, Message, Attachment, ConversationCheckpoint, ContextSummary,
)
from aion_chat.store import SQLiteChatStore, StorageUnavailableError

SCOPE = Scope("g32-owner", "g32-tenant", "g32-workspace")


class WriteFaultProxy:
    def __init__(self, raw, needle, *, rollback_fails=True, error_cls=RuntimeError,
                 close_fails=False):
        self.raw = raw
        self.needle = needle
        self.rollback_fails = rollback_fails
        self.error_cls = error_cls
        self.close_fails = close_fails
        self.rollbacks = 0
        self.closes = 0

    def execute(self, sql, *args, **kwargs):
        if self.needle in sql:
            raise self.error_cls("G32_PRIMARY_CHAT_WRITE_ERROR")
        return self.raw.execute(sql, *args, **kwargs)

    def rollback(self):
        self.rollbacks += 1
        if self.rollback_fails:
            raise OSError("G32_SECONDARY_ROLLBACK_ERROR")
        return self.raw.rollback()

    def close(self):
        self.closes += 1
        self.raw.close()
        if self.close_fails:
            raise OSError("G32_SECONDARY_CLOSE_ERROR")

    def __getattr__(self, attr):
        return getattr(self.raw, attr)


class G32ChatStoreTransactions(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="aion-g32-chat-")
        self.addCleanup(self.tmp.cleanup)
        self.store = SQLiteChatStore(Path(self.tmp.name) / "chat.sqlite3")
        self.addCleanup(self.store.close)
        self.raw = self.store.db
        self.addCleanup(self.restore_if_safe)
        self.conversation = None

    def restore_if_safe(self):
        # Never resurrect a quarantined store. Merely unwrap a healthy proxy.
        if self.store.db is not None:
            self.store.db = self.raw

    def fault(self, needle, *, rollback_fails=True, error_cls=RuntimeError,
              close_fails=False):
        proxy = WriteFaultProxy(
            self.raw, needle, rollback_fails=rollback_fails,
            error_cls=error_cls, close_fails=close_fails,
        )
        self.store.db = proxy
        return proxy

    def make_conversation(self):
        self.conversation = self.store.create_conversation(SCOPE, "g32 synthetic")
        return self.conversation

    def attachment(self):
        digest = "a" * 64
        return Attachment(
            conversation_id=self.conversation.id,
            name="synthetic.txt", mime_type="text/plain", size=0,
            digest=digest, storage_reference=digest + ".blob",
        )

    def assert_quarantine(self, primary_exception):
        self.assertEqual(str(primary_exception), "G32_PRIMARY_CHAT_WRITE_ERROR")
        self.assertIsInstance(primary_exception.__cause__, OSError)
        self.assertIn("G32_SECONDARY_ROLLBACK_ERROR",
                      str(primary_exception.__cause__))
        self.assertIsNone(self.store.db)
        self.assertEqual(self.store.storage_health()["state"], "failed")
        with self.assertRaises(StorageUnavailableError):
            self.store.require_healthy()
        with self.assertRaises(StorageUnavailableError):
            self.store.create_conversation(SCOPE, "after-failure")
        print("G32_CHAT_QUARANTINE_GREEN=PRIMARY_PRESERVED_CONNECTION_DETACHED")

    def assert_failed_operation(self, callback):
        with self.assertRaisesRegex(
            RuntimeError, "G32_PRIMARY_CHAT_WRITE_ERROR"
        ) as caught:
            callback()
        self.assert_quarantine(caught.exception)

    def test_01_create_conversation_normal(self):
        c = self.make_conversation()
        self.assertEqual(self.store.get_conversation(SCOPE, c.id).id, c.id)

    def test_02_archive_conversation_normal(self):
        c = self.make_conversation()
        result = self.store.archive_conversation(SCOPE, c.id)
        self.assertTrue(result.archived)

    def test_03_append_message_normal(self):
        c = self.make_conversation()
        message = self.store.append_message(SCOPE, Message(c.id, "user", "synthetic"))
        self.assertEqual(message.sequence, 1)
        self.assertEqual(len(self.store.list_messages(SCOPE, c.id).items), 1)

    def test_04_attachment_metadata_normal(self):
        self.make_conversation()
        row = self.store.add_attachment_metadata(SCOPE, self.attachment())
        self.assertEqual(self.store.get_attachment(SCOPE, self.conversation.id, row.id).id, row.id)

    def test_05_checkpoint_normal(self):
        c = self.make_conversation()
        checkpoint = ConversationCheckpoint(c.id, 0)
        self.store.save_checkpoint(SCOPE, checkpoint)
        self.assertEqual(self.store.get_latest_checkpoint(SCOPE, c.id).id, checkpoint.id)

    def test_06_context_summary_normal(self):
        c = self.make_conversation()
        summary = ContextSummary(c.id, 0, "synthetic summary")
        self.store.save_context_summary(SCOPE, summary)
        self.assertEqual(self.store.get_latest_summary(SCOPE, c.id).id, summary.id)

    def test_07_create_failure_and_rollback_failure_quarantines(self):
        proxy = self.fault("INSERT INTO conversations")
        self.assert_failed_operation(
            lambda: self.store.create_conversation(SCOPE, "synthetic failure")
        )
        self.assertEqual(proxy.rollbacks, 1)
        self.assertEqual(proxy.closes, 1)

    def test_08_archive_failure_and_rollback_failure_quarantines(self):
        c = self.make_conversation()
        self.fault("UPDATE conversations SET")
        self.assert_failed_operation(lambda: self.store.archive_conversation(SCOPE, c.id))

    def test_09_append_failure_and_rollback_failure_quarantines(self):
        c = self.make_conversation()
        self.fault("INSERT INTO messages")
        self.assert_failed_operation(
            lambda: self.store.append_message(SCOPE, Message(c.id, "user", "synthetic"))
        )
        print("G32_APPEND_MESSAGE_GREEN=NO_SILENT_ROLLBACK_FAILURE")

    def test_10_attachment_failure_and_rollback_failure_quarantines(self):
        self.make_conversation()
        self.fault("INSERT INTO records")
        self.assert_failed_operation(
            lambda: self.store.add_attachment_metadata(SCOPE, self.attachment())
        )

    def test_11_checkpoint_failure_and_rollback_failure_quarantines(self):
        c = self.make_conversation()
        self.fault("INSERT INTO records")
        self.assert_failed_operation(
            lambda: self.store.save_checkpoint(SCOPE, ConversationCheckpoint(c.id, 0))
        )

    def test_12_summary_failure_and_rollback_failure_quarantines(self):
        c = self.make_conversation()
        self.fault("INSERT INTO records")
        self.assert_failed_operation(
            lambda: self.store.save_context_summary(
                SCOPE, ContextSummary(c.id, 0, "synthetic")
            )
        )

    def test_13_successful_rollback_keeps_primary_and_healthy(self):
        proxy = self.fault("INSERT INTO conversations", rollback_fails=False)
        with self.assertRaisesRegex(RuntimeError, "G32_PRIMARY_CHAT_WRITE_ERROR"):
            self.store.create_conversation(SCOPE, "synthetic")
        self.assertEqual(proxy.rollbacks, 1)
        self.assertFalse(self.raw.in_transaction)
        self.assertIsNotNone(self.store.db)

    def test_14_append_successful_rollback_does_not_quarantine(self):
        c = self.make_conversation()
        proxy = self.fault("INSERT INTO messages", rollback_fails=False)
        with self.assertRaisesRegex(RuntimeError, "G32_PRIMARY_CHAT_WRITE_ERROR"):
            self.store.append_message(SCOPE, Message(c.id, "user", "synthetic"))
        self.assertEqual(proxy.rollbacks, 1)
        self.assertFalse(self.raw.in_transaction)
        self.assertEqual(len(self.store.list_messages(SCOPE, c.id).items), 0)

    def test_15_rollback_failure_original_sqlite_error_type_preserved(self):
        proxy = self.fault("INSERT INTO conversations", error_cls=sqlite3.DatabaseError)
        with self.assertRaisesRegex(
            sqlite3.DatabaseError, "G32_PRIMARY_CHAT_WRITE_ERROR"
        ) as caught:
            self.store.create_conversation(SCOPE, "synthetic")
        self.assertIsInstance(caught.exception.__cause__, OSError)
        self.assertIsNone(self.store.db)
        self.assertEqual(proxy.rollbacks, 1)

    def test_16_close_failure_cannot_reenable_quarantined_store(self):
        proxy = self.fault("INSERT INTO conversations", close_fails=True)
        self.assert_failed_operation(
            lambda: self.store.create_conversation(SCOPE, "synthetic")
        )
        self.assertEqual(proxy.closes, 1)

    def test_17_logic_error_with_failed_rollback_is_fail_closed(self):
        c = self.make_conversation()
        first = ConversationCheckpoint(c.id, 0)
        self.store.save_checkpoint(SCOPE, first)
        proxy = self.fault("__never_match__")
        with self.assertRaisesRegex(
            ValueError, "coverage must advance"
        ) as caught:
            self.store.save_checkpoint(SCOPE, ConversationCheckpoint(c.id, 0))
        self.assertIsInstance(caught.exception.__cause__, OSError)
        self.assertIsNone(self.store.db)
        self.assertEqual(proxy.rollbacks, 1)

    def test_18_failed_rollback_prevents_new_store_calls(self):
        self.fault("INSERT INTO conversations")
        with self.assertRaises(RuntimeError):
            self.store.create_conversation(SCOPE, "synthetic")
        for _ in range(2):
            with self.assertRaises(StorageUnavailableError):
                self.store.create_conversation(SCOPE, "retry")
        self.assertIsNone(self.store.db)
        print("G32_NO_RETRY_GREEN=STICKY_FAIL_CLOSED_AFTER_ROLLBACK_ERROR")

    def test_19_local_reopen_not_external_recovery_proof(self):
        self.make_conversation()
        self.fault("UPDATE conversations SET")
        with self.assertRaises(RuntimeError):
            self.store.archive_conversation(SCOPE, self.conversation.id)
        reopened = SQLiteChatStore(self.store.path)
        try:
            original = reopened.get_conversation(SCOPE, self.conversation.id)
            self.assertFalse(original.archived)
            # The reopened local DB cannot attest to independent freshness.
            self.assertEqual(reopened.require_healthy()["state"], "healthy")
            print("G32_REOPEN_LIMIT=LOCAL_SQLITE_IS_NOT_EXTERNAL_FRESHNESS")
        finally:
            reopened.close()

    def test_20_no_external_effect_or_trusted_attestation(self):
        c = self.make_conversation()
        self.assertEqual(self.store.get_conversation(SCOPE, c.id).message_count, 0)
        self.assertFalse(hasattr(self.store, "send"))
        self.assertFalse(hasattr(self.store, "verified_external_witness"))


if __name__ == "__main__":
    unittest.main()
