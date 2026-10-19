"""P0 SQLiteChatStore own-connection thread boundary: original RED -> LAB GREEN.

These tests use the original staged SQLiteChatStore, with an ephemeral database
in a temp directory. A borrowed SQLite handle must fail explicitly BEFORE
SQLite I/O, backup, rollback or the health-state mutation. A fresh handle
constructed inside another thread remains supported. No provider/Worker/network
or production paths.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest

from aion_chat.models import Message, Scope
from aion_chat.store import SQLiteChatStore, StorageUnavailableError, HEALTHY

SCOPE = Scope("p0-test-owner", "p0-test-tenant", "p0-test-workspace")
DENIAL = "SQLITE_STORE_CONNECTION_THREAD_MISMATCH"


class P0SQLiteStoreOwnerThreadTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="p0-store-owner-thread-")
        self.addCleanup(self.temp.cleanup)
        self.db_path = Path(self.temp.name) / "chat.sqlite3"
        self.store = SQLiteChatStore(self.db_path)
        self.addCleanup(self.store.close)
        self.conversation = self.store.create_conversation(SCOPE, "Lab thread safety")
        self.before_health = self.store.storage_health(deep=True)
        self.assertEqual(self.before_health["state"], HEALTHY)

    def cross_thread_denied(self, callback):
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(callback)
            with self.assertRaisesRegex(StorageUnavailableError, DENIAL):
                future.result(timeout=12)
        self.assertIsNotNone(self.store.db)
        self.assertEqual(self.store._health_state, HEALTHY,
                         "cross-thread caller must not poison staging health")
        self.assertEqual(self.store.storage_health(deep=True)["state"], HEALTHY)
        self.assertEqual(
            self.store.get_conversation(SCOPE, self.conversation.id).title,
            "Lab thread safety",
        )

    def test_01_health_probe_denies_foreign_thread_without_failed_state(self):
        self.cross_thread_denied(lambda: self.store.storage_health(deep=True))

    def test_02_require_healthy_denies_foreign_thread_without_poisoning(self):
        self.cross_thread_denied(self.store.require_healthy)

    def test_03_close_denies_foreign_thread_but_owner_can_still_use(self):
        self.cross_thread_denied(self.store.close)

    def test_04_wal_checkpoint_denies_foreign_thread(self):
        self.cross_thread_denied(lambda: self.store.wal_checkpoint("PASSIVE"))

    def test_05_backup_to_denies_foreign_thread_before_file_is_created(self):
        dest = Path(self.temp.name) / "must-not-be-created.sqlite3"
        self.cross_thread_denied(lambda: self.store.backup_to(dest))
        self.assertFalse(dest.exists())

    def test_06_get_conversation_denies_foreign_thread(self):
        self.cross_thread_denied(
            lambda: self.store.get_conversation(SCOPE, self.conversation.id)
        )

    def test_07_create_conversation_denies_foreign_thread_before_write(self):
        self.cross_thread_denied(
            lambda: self.store.create_conversation(SCOPE, "must not appear")
        )
        self.assertEqual(len(self.store.list_conversations(SCOPE).items), 1)

    def test_08_list_conversations_denies_foreign_thread(self):
        self.cross_thread_denied(lambda: self.store.list_conversations(SCOPE))

    def test_09_append_message_denies_before_begin_and_rollback(self):
        m = Message(self.conversation.id, "user", "test-only", id="p0-test-msg")
        self.cross_thread_denied(lambda: self.store.append_message(SCOPE, m))
        self.assertEqual(len(self.store.list_messages(SCOPE, self.conversation.id).items), 0)

    def test_10_archive_conversation_denies_foreign_thread(self):
        self.cross_thread_denied(
            lambda: self.store.archive_conversation(SCOPE, self.conversation.id)
        )
        self.assertFalse(self.store.get_conversation(SCOPE, self.conversation.id).archived)

    def test_11_list_messages_denies_foreign_thread(self):
        self.cross_thread_denied(
            lambda: self.store.list_messages(SCOPE, self.conversation.id)
        )

    def test_12_wrong_thread_does_not_end_parent_transaction(self):
        self.store.db.execute("CREATE TABLE p0_thread_tx_sentinel (id TEXT PRIMARY KEY)")
        self.store.db.execute("BEGIN IMMEDIATE")
        try:
            self.store.db.execute(
                "INSERT INTO p0_thread_tx_sentinel VALUES ('caller-pending')"
            )
            with ThreadPoolExecutor(max_workers=1) as pool:
                with self.assertRaisesRegex(StorageUnavailableError, DENIAL):
                    pool.submit(lambda: self.store.append_message(
                        SCOPE, Message(self.conversation.id, "user", "foreign")
                    )).result(timeout=12)
            self.assertTrue(self.store.db.in_transaction)
            self.assertEqual(self.store.db.execute(
                "SELECT COUNT(*) FROM p0_thread_tx_sentinel"
            ).fetchone()[0], 1)
            self.assertEqual(self.store._health_state, HEALTHY)
        finally:
            if self.store.db.in_transaction:
                self.store.db.rollback()

    def test_13_fresh_store_per_thread_still_reads_same_committed_data(self):
        def own_store():
            other = SQLiteChatStore(self.db_path)
            try:
                return other.get_conversation(SCOPE, self.conversation.id).title
            finally:
                other.close()
        with ThreadPoolExecutor(max_workers=1) as pool:
            self.assertEqual(pool.submit(own_store).result(timeout=12), "Lab thread safety")
        self.assertEqual(self.store.storage_health(deep=True)["state"], HEALTHY)

    def test_14_owned_backup_and_wal_checkpoint_still_succeed(self):
        backup = Path(self.temp.name) / "verified-backup.sqlite3"
        result = self.store.backup_to(backup)
        self.assertEqual(result["state"], "BACKUP_VERIFIED")
        self.assertTrue(backup.is_file())
        self.assertFalse(self.store.wal_checkpoint("PASSIVE")["busy"])

    def test_15_correct_thread_can_write_and_read_after_foreign_denial(self):
        self.cross_thread_denied(lambda: self.store.list_conversations(SCOPE))
        msg = self.store.append_message(SCOPE, Message(
            self.conversation.id, "user", "owner thread", id="safe-owner-msg"
        ))
        self.assertEqual(msg.sequence, 1)
        self.assertEqual(self.store.get_message(
            SCOPE, self.conversation.id, "safe-owner-msg"
        ).content, "owner thread")


if __name__ == "__main__":
    unittest.main()
