"""G33: ambiguous commit before/after acknowledgement, real Chat SQLite LAB.

A simulated driver can throw before performing COMMIT or after committing
successfully. Both outcomes must quarantine the same connection, never
pretend that a successful rollback proves zero effects.
"""
from pathlib import Path
from contextlib import contextmanager
import tempfile
import unittest

from aion_chat.models import (
    Scope, Message, ConversationCheckpoint, ContextSummary, Attachment,
)
from aion_chat.store import SQLiteChatStore, StorageUnavailableError

SCOPE = Scope("g33-owner", "g33-tenant", "g33-workspace")


class CommitFault:
    def __init__(self, real, *, after):
        self.real = real
        self.after = after
        self.commit_count = 0
        self.rollback_count = 0
        self.close_count = 0

    def commit(self):
        self.commit_count += 1
        if self.after:
            self.real.commit()
        raise OSError("G33_COMMIT_ACK_UNKNOWN")

    def rollback(self):
        self.rollback_count += 1
        return self.real.rollback()

    def close(self):
        self.close_count += 1
        return self.real.close()

    def __getattr__(self, name):
        return getattr(self.real, name)


class G33ChatCommitAmbiguity(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="aion-g33-chat-")
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "store.sqlite3"
        self.store = SQLiteChatStore(self.path)
        self.addCleanup(self.store.close)
        self.original = self.store.db
        self.addCleanup(self.restore_if_healthy)

    def restore_if_healthy(self):
        if self.store.db is not None:
            self.store.db = self.original

    def fail_commit(self, operation, *, after):
        proxy = CommitFault(self.original, after=after)
        self.store.db = proxy
        with self.assertRaisesRegex(OSError, "G33_COMMIT_ACK_UNKNOWN") as captured:
            operation()
        self.assertEqual(proxy.commit_count, 1)
        self.assertEqual(proxy.rollback_count, 0)
        self.assertEqual(proxy.close_count, 1)
        self.assertIsNone(self.store.db)
        self.assertEqual(self.store.storage_health()["state"], "failed")
        with self.assertRaises(StorageUnavailableError):
            self.store.require_healthy()
        with self.assertRaises(StorageUnavailableError):
            self.store.create_conversation(SCOPE, "must-not-retry")
        self.assertTrue(any("COMMIT_OUTCOME_UNCERTAIN" in n for n in
                            getattr(captured.exception, "__notes__", [])))
        return captured.exception

    @contextmanager
    def reopen(self):
        db = SQLiteChatStore(self.path)
        try:
            yield db
        finally:
            db.close()

    def test_01_create_precommit_error_quarantines(self):
        self.fail_commit(lambda: self.store.create_conversation(SCOPE, "before"), after=False)
        with self.reopen() as db:
            self.assertEqual(len(db.list_conversations(SCOPE).items), 0)
        print("G33_CHAT_PRECOMMIT_GREEN=UNKNOWN_ACK_QUARANTINE_NO_ROLLBACK")

    def test_02_create_postcommit_error_quarantines_even_when_persisted(self):
        self.fail_commit(lambda: self.store.create_conversation(SCOPE, "after"), after=True)
        with self.reopen() as db:
            self.assertEqual(len(db.list_conversations(SCOPE).items), 1)
        print("G33_CHAT_POSTCOMMIT_RED=PERSISTED_BUT_CALLER_GOT_ERROR")

    def test_03_append_precommit_error_not_persisted(self):
        c = self.store.create_conversation(SCOPE, "chat")
        self.fail_commit(
            lambda: self.store.append_message(SCOPE, Message(c.id, "user", "pre")), after=False
        )
        with self.reopen() as db:
            self.assertEqual(len(db.list_messages(SCOPE, c.id).items), 0)

    def test_04_append_postcommit_error_persisted_but_uncertain(self):
        c = self.store.create_conversation(SCOPE, "chat")
        self.fail_commit(
            lambda: self.store.append_message(SCOPE, Message(c.id, "user", "post")), after=True
        )
        with self.reopen() as db:
            self.assertEqual(len(db.list_messages(SCOPE, c.id).items), 1)
        print("G33_MESSAGE_POSTCOMMIT_RED=MESSAGE_PERSISTED_ERROR_RETURNED")

    def test_05_archive_precommit(self):
        c = self.store.create_conversation(SCOPE, "test")
        self.fail_commit(lambda: self.store.archive_conversation(SCOPE, c.id), after=False)
        with self.reopen() as db:
            self.assertFalse(db.get_conversation(SCOPE, c.id).archived)

    def test_06_archive_postcommit(self):
        c = self.store.create_conversation(SCOPE, "test")
        self.fail_commit(lambda: self.store.archive_conversation(SCOPE, c.id), after=True)
        with self.reopen() as db:
            self.assertTrue(db.get_conversation(SCOPE, c.id).archived)

    def test_07_checkpoint_precommit(self):
        c = self.store.create_conversation(SCOPE, "test")
        self.fail_commit(lambda: self.store.save_checkpoint(
            SCOPE, ConversationCheckpoint(c.id, 0)), after=False)
        with self.reopen() as db:
            self.assertIsNone(db.get_latest_checkpoint(SCOPE, c.id))

    def test_08_checkpoint_postcommit(self):
        c = self.store.create_conversation(SCOPE, "test")
        self.fail_commit(lambda: self.store.save_checkpoint(
            SCOPE, ConversationCheckpoint(c.id, 0)), after=True)
        with self.reopen() as db:
            self.assertIsNotNone(db.get_latest_checkpoint(SCOPE, c.id))

    def test_09_summary_precommit(self):
        c = self.store.create_conversation(SCOPE, "test")
        self.fail_commit(lambda: self.store.save_context_summary(
            SCOPE, ContextSummary(c.id, 0, "pre")), after=False)
        with self.reopen() as db:
            self.assertIsNone(db.get_latest_summary(SCOPE, c.id))

    def test_10_summary_postcommit(self):
        c = self.store.create_conversation(SCOPE, "test")
        self.fail_commit(lambda: self.store.save_context_summary(
            SCOPE, ContextSummary(c.id, 0, "post")), after=True)
        with self.reopen() as db:
            self.assertIsNotNone(db.get_latest_summary(SCOPE, c.id))

    def attachment(self, cid):
        digest = "a" * 64
        return Attachment(cid, "synthetic.txt", "text/plain", 0,
                          digest, digest + ".blob")

    def test_11_attachment_precommit(self):
        c = self.store.create_conversation(SCOPE, "test")
        att = self.attachment(c.id)
        self.fail_commit(lambda: self.store.add_attachment_metadata(SCOPE, att), after=False)
        with self.reopen() as db:
            with self.assertRaises(LookupError):
                db.get_attachment(SCOPE, c.id, att.id)

    def test_12_attachment_postcommit(self):
        c = self.store.create_conversation(SCOPE, "test")
        att = self.attachment(c.id)
        self.fail_commit(lambda: self.store.add_attachment_metadata(SCOPE, att), after=True)
        with self.reopen() as db:
            self.assertEqual(db.get_attachment(SCOPE, c.id, att.id).id, att.id)


if __name__ == "__main__":
    unittest.main()
