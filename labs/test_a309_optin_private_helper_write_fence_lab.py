"""A309: opt-in guard on actual SQLiteChatStore helper writes.

This test uses only disposable SQLite databases. Passing tests only prove
cooperative same-process behavior, not native VFS identity or durable custody.
"""
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory
import sqlite3
import unittest
from unittest import mock

from aion_chat.models import (
    ContextSummary, ConversationCheckpoint, Message, Scope,
)
from aion_chat.store import (
    FAILED, HEALTHY, SQLiteChatStore, StorageUnavailableError,
    StoreCommitOutcomeUncertainError,
)
from labs.a291_chat_write_gate_commit_fence_lab import SyntheticAckLossConnection
from labs.test_a246_chat_commit_uncertainty import LostAckConnection
from labs.a292_staged_chat_write_inventory_lab import (
    _synthetic_attachment, probe_real_raw_helper_bypasses,
)

SCOPE = Scope("owner-a309", "tenant-a309", "workspace-a309")


def _count(db_path, table):
    assert table in ("conversations", "messages", "records")
    with closing(sqlite3.connect(str(db_path))) as reader:
        return reader.execute("SELECT COUNT(*) FROM " + table).fetchone()[0]


class A309GuardedStoreTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = TemporaryDirectory(prefix="a309-guarded-store-")
        self.addCleanup(self.tempdir.cleanup)
        self.path = Path(self.tempdir.name) / "staging.db"
        self.store = SQLiteChatStore(
            self.path, strict_local_data_version=True,
            strict_private_write_helpers=True,
        )
        self.addCleanup(self.store.close)

    def seed(self):
        return self.store.create_conversation(SCOPE, "original-a309")

    def test_enabled_setting_is_explicit_and_real(self):
        self.assertTrue(self.store._strict_private_write_helpers)
        self.assertEqual(self.store._private_helper_write_depth, 0)
        self.assertIsNone(self.store._private_helper_write_owner)
        self.assertEqual(self.store.storage_health(deep=True)["state"], HEALTHY)

    def test_private_update_is_denied_before_dml(self):
        c = self.seed()
        c.title = "attempted-direct-helper"
        with self.assertRaises(StorageUnavailableError):
            self.store._update(c)
        self.assertEqual(self.store._health_state, FAILED)
        self.assertEqual(
            self.store._health_reason,
            "PRIVATE_HELPER_OUTSIDE_FENCED_WRITE_ZERO_AUTO_RETRY",
        )
        with closing(sqlite3.connect(str(self.path))) as reader:
            title = reader.execute(
                "SELECT title FROM conversations WHERE id=?", (c.id,)
            ).fetchone()[0]
        self.assertEqual(title, "original-a309")
        self.assertFalse(self.store._message_commit_marker.exists())

    def test_private_record_is_denied_before_dml(self):
        c = self.seed()
        cp = ConversationCheckpoint(c.id, 0)
        with self.assertRaises(StorageUnavailableError):
            self.store._save_record(SCOPE, "checkpoint", cp, 0)
        self.assertEqual(_count(self.path, "records"), 0)
        self.assertEqual(self.store._health_state, FAILED)

    def test_post_denial_cannot_be_used_again(self):
        c = self.seed()
        c.title = "bypass"
        with self.assertRaises(StorageUnavailableError):
            self.store._update(c)
        with self.assertRaises(StorageUnavailableError):
            self.store.get_conversation(SCOPE, c.id)
        with self.assertRaises(StorageUnavailableError):
            self.store.append_message(
                SCOPE, Message(c.id, "user", "attempted resend"),
            )

    def test_manual_sqlite_begin_does_not_grant_private_helper(self):
        c = self.seed()
        self.store.db.execute("BEGIN IMMEDIATE")
        try:
            c.title = "attempt-after-manual-begin"
            with self.assertRaises(StorageUnavailableError):
                self.store._update(c)
            self.assertEqual(self.store._health_state, FAILED)
        finally:
            self.store.db.rollback()
        self.assertEqual(_count(self.path, "conversations"), 1)

    def test_all_six_legitimate_writers_still_publish_fences(self):
        original = self.store._publish_message_commit_marker
        with mock.patch.object(
            self.store, "_publish_message_commit_marker", wraps=original
        ) as spy:
            conv = self.seed()
            m = self.store.append_message(
                SCOPE, Message(conv.id, "user", "a309 allowed", id="a309-message")
            )
            self.store.add_attachment_metadata(
                SCOPE, _synthetic_attachment(conv.id)
            )
            self.store.save_checkpoint(
                SCOPE, ConversationCheckpoint(conv.id, m.sequence)
            )
            self.store.save_context_summary(
                SCOPE, ContextSummary(
                    conv.id, m.sequence, "a309 summary", source_message_ids=[m.id]
                ),
            )
            self.store.archive_conversation(SCOPE, conv.id)
        self.assertEqual(spy.call_count, 6)
        self.assertEqual(_count(self.path, "conversations"), 1)
        self.assertEqual(_count(self.path, "messages"), 1)
        self.assertEqual(_count(self.path, "records"), 3)
        self.assertEqual(self.store.storage_health(deep=True)["state"], HEALTHY)
        self.assertEqual(self.store._private_helper_write_depth, 0)
        self.assertIsNone(self.store._private_helper_write_owner)
        self.assertFalse(self.store._message_commit_marker.exists())

    def test_append_message_scope_released_after_commit(self):
        conv = self.seed()
        self.store.append_message(
            SCOPE, Message(conv.id, "user", "a309", id="a309-append")
        )
        self.assertEqual(self.store._private_helper_write_depth, 0)
        self.assertIsNone(self.store._private_helper_write_owner)
        c = self.store.get_conversation(SCOPE, conv.id)
        c.title = "attempted-after-commit"
        with self.assertRaises(StorageUnavailableError):
            self.store._update(c)

    def test_transaction_context_scope_released_after_commit(self):
        conv = self.seed()
        self.store.archive_conversation(SCOPE, conv.id)
        self.assertEqual(self.store._private_helper_write_depth, 0)
        self.assertIsNone(self.store._private_helper_write_owner)
        with self.assertRaises(StorageUnavailableError):
            self.store._save_record(
                SCOPE, "checkpoint", ConversationCheckpoint(conv.id, 0), 0
            )

    def test_default_mode_remains_legacy_behavior_not_security_proof(self):
        self.store.close()
        basic = SQLiteChatStore(self.path, strict_local_data_version=True)
        try:
            self.assertFalse(basic._strict_private_write_helpers)
            c = basic.create_conversation(SCOPE, "legacy")
            modified = basic.get_conversation(SCOPE, c.id)
            modified.title = "legacy-helper-still-bypasses"
            basic._update(modified)
            basic.db.commit()
            self.assertEqual(
                basic.get_conversation(SCOPE, c.id).title,
                "legacy-helper-still-bypasses",
            )
        finally:
            basic.close()

    def test_invalid_mode_type_denied(self):
        self.store.close()
        for value in (None, 1, "true", [], 0):
            with self.subTest(value=value):
                with self.assertRaises(TypeError):
                    SQLiteChatStore(
                        self.path, strict_private_write_helpers=value
                    )

    def test_direct_db_sql_still_bypasses_guard_and_must_not_be_hidden(self):
        c = self.seed()
        self.store.db.execute(
            "UPDATE conversations SET title=? WHERE id=?",
            ("raw-db-sql-can-bypass", c.id),
        )
        self.store.db.commit()
        self.assertEqual(
            self.store.db.execute(
                "SELECT title FROM conversations WHERE id=?", (c.id,)
            ).fetchone()[0],
            "raw-db-sql-can-bypass",
        )
        self.assertFalse(self.store._message_commit_marker.exists())
        self.assertEqual(self.store._health_state, HEALTHY)

    def test_private_transaction_context_still_callable_by_host(self):
        c = self.seed()
        altered = self.store.get_conversation(SCOPE, c.id)
        altered.title = "host-can-invoke-private-context"
        # Deliberately demonstrate why an in-process private method is NOT
        # a security authorization: the host can obtain this scope itself.
        with self.store._fenced_chat_transaction():
            self.store._update(altered)
        self.assertEqual(
            self.store.get_conversation(SCOPE, c.id).title,
            "host-can-invoke-private-context",
        )
        self.assertEqual(self.store._health_state, HEALTHY)

    def test_read_only_api_still_works(self):
        c = self.seed()
        self.assertEqual(
            self.store.get_conversation(SCOPE, c.id).title, "original-a309"
        )
        self.assertEqual(self.store.list_messages(SCOPE, c.id).items, [])
        self.assertEqual(
            self.store.storage_health(deep=True)["state"], HEALTHY
        )


class A309UncertainAckTests(unittest.TestCase):
    def test_strict_guard_preserves_sticky_unknown_commit(self):
        with TemporaryDirectory(prefix="a309-ack-") as raw:
            path = Path(raw) / "storage.db"
            real_connect = sqlite3.connect

            def synthetic_connect(*args, **kwargs):
                return real_connect(
                    *args, **kwargs, factory=SyntheticAckLossConnection
                )

            with mock.patch(
                "aion_chat.store.sqlite3.connect",
                side_effect=synthetic_connect,
            ):
                store = SQLiteChatStore(
                    path, strict_local_data_version=True,
                    strict_private_write_helpers=True,
                )
            try:
                conv = store.create_conversation(SCOPE, "ack unknown")
                store.db.fault_once = "after"
                with self.assertRaises(StoreCommitOutcomeUncertainError):
                    store.append_message(
                        SCOPE, Message(
                            conv.id, "user", "once", id="a309-ack-once"
                        ),
                    )
                self.assertEqual(
                    store._health_reason,
                    "COMMIT_OUTCOME_UNKNOWN_ZERO_AUTO_RETRY",
                )
                self.assertEqual(_count(path, "messages"), 1)
                self.assertTrue(store._message_commit_marker.exists())
                self.assertEqual(store._private_helper_write_depth, 0)
                with self.assertRaises(StorageUnavailableError):
                    store.append_message(
                        SCOPE, Message(
                            conv.id, "user", "retry", id="a309-ack-retry"
                        ),
                    )
                self.assertEqual(_count(path, "messages"), 1)
            finally:
                store.close()
            with self.assertRaises(StorageUnavailableError):
                reopened = SQLiteChatStore(
                    path, strict_private_write_helpers=True,
                )
                reopened.close()


class A309LegacyConnectionProxyRegressionTests(unittest.TestCase):
    def test_legacy_lost_ack_proxy_without_in_transaction_preserves_veto(self):
        """Regression for six A246/A247 failures seen on first A309 CI."""
        with TemporaryDirectory(prefix="a309-legacy-lost-ack-") as raw:
            path = Path(raw) / "storage.db"
            store = SQLiteChatStore(path)  # opt-in MUST be false
            try:
                c = store.create_conversation(SCOPE, "legacy ack")
                proxy = LostAckConnection(store.db, after_commit=True)
                self.assertFalse(hasattr(proxy, "in_transaction"))
                store.db = proxy
                with self.assertRaises(StoreCommitOutcomeUncertainError):
                    store.append_message(
                        SCOPE, Message(c.id, "user", "once",
                                       id="a309-legacy-lost-ack"),
                    )
                self.assertEqual(_count(path, "messages"), 1)
                self.assertEqual(proxy.commit_calls, 1)
                self.assertEqual(
                    store._health_reason,
                    "COMMIT_OUTCOME_UNKNOWN_ZERO_AUTO_RETRY",
                )
                self.assertTrue(store._message_commit_marker.exists())
                with self.assertRaises(StorageUnavailableError):
                    store.append_message(
                        SCOPE, Message(c.id, "user", "no retry",
                                       id="a309-retry-denied"),
                    )
                self.assertEqual(_count(path, "messages"), 1)
            finally:
                store.close()

    def test_strict_mode_proxy_without_transaction_property_fails_closed(self):
        """An unknown transaction status is no authority to COMMIT."""
        with TemporaryDirectory(prefix="a309-strict-proxy-") as raw:
            path = Path(raw) / "storage.db"
            store = SQLiteChatStore(
                path, strict_private_write_helpers=True,
            )
            try:
                c = store.create_conversation(SCOPE, "strict")
                proxy = LostAckConnection(store.db, after_commit=True)
                self.assertFalse(hasattr(proxy, "in_transaction"))
                store.db = proxy
                with self.assertRaises(StorageUnavailableError):
                    store.append_message(
                        SCOPE, Message(c.id, "user", "untrusted",
                                       id="a309-strict-unknown-transaction"),
                    )
                self.assertEqual(
                    store._health_reason,
                    "PRIVATE_HELPER_TRANSACTION_UNVERIFIED_ZERO_AUTO_RETRY",
                )
                self.assertEqual(store._health_state, FAILED)
                self.assertEqual(proxy.commit_calls, 0)
                self.assertEqual(_count(path, "messages"), 0)
                with self.assertRaises(StorageUnavailableError):
                    store.append_message(
                        SCOPE, Message(c.id, "user", "retry",
                                       id="a309-no-retry-strict"),
                    )
            finally:
                store.close()


if __name__ == "__main__":
    unittest.main()
