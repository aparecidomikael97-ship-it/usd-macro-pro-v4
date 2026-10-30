"""A310 LAB: SQLite opcode authorizer composed with A309 helper guard.

Real SQLite, disposable fixtures and synthetic ACK loss. An exposed Python
connection can remove its own authorizer: NEVER treat local PASS as P0-6 GO.
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
from labs.a292_staged_chat_write_inventory_lab import _synthetic_attachment

SCOPE = Scope("owner-a310", "tenant-a310", "workspace-a310")


def raw_count(path, table):
    assert table in ("conversations", "messages", "records")
    with closing(sqlite3.connect(str(path))) as reader:
        return reader.execute("SELECT COUNT(*) FROM " + table).fetchone()[0]


class A310OptinSQLAuthorizerTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory(prefix="a310-sql-authorizer-")
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "db.sqlite"
        self.store = SQLiteChatStore(
            self.path,
            strict_private_write_helpers=True,
            strict_sql_authorizer=True,
            strict_local_data_version=True,
        )
        self.addCleanup(self.store.close)

    def seed(self):
        return self.store.create_conversation(SCOPE, "A310 original")

    def test_guard_is_opt_in_and_composed_with_a309(self):
        self.assertTrue(self.store._strict_sql_authorizer)
        self.assertTrue(self.store._strict_private_write_helpers)
        self.assertIsNone(self.store._sql_authorizer_writer_tid)
        self.assertEqual(self.store.storage_health(deep=True)["state"], HEALTHY)

    def test_all_six_legitimate_chat_writers_survive(self):
        original = self.store._publish_message_commit_marker
        with mock.patch.object(
            self.store, "_publish_message_commit_marker", wraps=original
        ) as marker_spy:
            conv = self.seed()
            m = self.store.append_message(
                SCOPE, Message(conv.id, "user", "one", id="a310-message")
            )
            self.store.add_attachment_metadata(
                SCOPE, _synthetic_attachment(conv.id)
            )
            self.store.save_checkpoint(
                SCOPE, ConversationCheckpoint(conv.id, m.sequence)
            )
            self.store.save_context_summary(
                SCOPE, ContextSummary(
                    conv.id, m.sequence, "a310", source_message_ids=[m.id]
                ),
            )
            self.store.archive_conversation(SCOPE, conv.id)
        self.assertEqual(marker_spy.call_count, 6)
        self.assertEqual(raw_count(self.path, "conversations"), 1)
        self.assertEqual(raw_count(self.path, "messages"), 1)
        self.assertEqual(raw_count(self.path, "records"), 3)
        self.assertIsNone(self.store._sql_authorizer_writer_tid)
        self.assertEqual(self.store._private_helper_write_depth, 0)
        self.assertEqual(self.store.storage_health(deep=True)["state"], HEALTHY)
        self.assertFalse(self.store._message_commit_marker.exists())

    def test_direct_raw_update_denied(self):
        c = self.seed()
        with self.assertRaises(sqlite3.DatabaseError):
            self.store.db.execute(
                "UPDATE conversations SET title=? WHERE id=?",
                ("forbidden", c.id),
            )
        self.assertEqual(
            self.store.get_conversation(SCOPE, c.id).title, "A310 original"
        )
        self.assertGreater(self.store._sql_authorizer_denials, 0)

    def test_direct_raw_insert_denied(self):
        self.seed()
        before = raw_count(self.path, "conversations")
        with self.assertRaises(sqlite3.DatabaseError):
            self.store.db.execute(
                "INSERT INTO conversations VALUES ('fake','o','t','w','u',0,'fake','{}')"
            )
        self.assertEqual(raw_count(self.path, "conversations"), before)

    def test_direct_raw_delete_denied(self):
        c = self.seed()
        with self.assertRaises(sqlite3.DatabaseError):
            self.store.db.execute(
                "DELETE FROM conversations WHERE id=?", (c.id,)
            )
        self.assertEqual(raw_count(self.path, "conversations"), 1)

    def test_direct_schema_create_denied(self):
        with self.assertRaises(sqlite3.DatabaseError):
            self.store.db.execute("CREATE TABLE rogue (id INTEGER)")
        with closing(sqlite3.connect(str(self.path))) as reader:
            self.assertIsNone(reader.execute(
                "SELECT name FROM sqlite_master WHERE name='rogue'"
            ).fetchone())

    def test_direct_attach_denied(self):
        target = Path(self.directory.name) / "rogue.sqlite"
        with self.assertRaises(sqlite3.DatabaseError):
            self.store.db.execute(
                "ATTACH DATABASE ? AS malicious", (str(target),)
            )

    def test_direct_write_pragma_denied(self):
        with self.assertRaises(sqlite3.DatabaseError):
            self.store.db.execute("PRAGMA writable_schema=ON")
        self.assertEqual(self.store.storage_health(deep=True)["state"], HEALTHY)

    def test_journal_mode_mutation_denied(self):
        with self.assertRaises(sqlite3.DatabaseError):
            self.store.db.execute("PRAGMA journal_mode=DELETE")
        self.assertEqual(
            str(self.store.db.execute("PRAGMA journal_mode").fetchone()[0]).lower(),
            "wal",
        )

    def test_read_only_pragmas_still_available(self):
        self.assertEqual(
            self.store.db.execute("PRAGMA quick_check").fetchone()[0], "ok"
        )
        self.assertIsInstance(
            self.store.db.execute("PRAGMA data_version").fetchone()[0], int
        )

    def test_raw_begin_immediate_denied_outside_method(self):
        with self.assertRaises(sqlite3.DatabaseError):
            self.store.db.execute("BEGIN IMMEDIATE")
        self.assertFalse(self.store.db.in_transaction)

    def test_cache_rearm_prevents_reusing_prior_update_statement(self):
        conv = self.seed()
        self.store.archive_conversation(SCOPE, conv.id)
        c = self.store.get_conversation(SCOPE, conv.id)
        c.title = "cached attempt"
        # Same SQL string that the authorized _update executed earlier.
        with self.assertRaises(sqlite3.DatabaseError):
            self.store.db.execute(
                "UPDATE conversations SET updated=?,archived=?,title=?,data=? WHERE id=?",
                (c.updated_at, c.archived, c.title, "{}", c.id),
            )
        self.assertNotEqual(
            self.store.get_conversation(SCOPE, conv.id).title, "cached attempt"
        )

    def test_legacy_default_unchanged_no_sql_authorizer(self):
        self.store.close()
        legacy = SQLiteChatStore(self.path, strict_private_write_helpers=True)
        try:
            self.assertFalse(legacy._strict_sql_authorizer)
            c = legacy.create_conversation(SCOPE, "legacy")
            legacy.db.execute(
                "UPDATE conversations SET title='legacy-raw' WHERE id=?",
                (c.id,),
            )
            legacy.db.commit()
            self.assertEqual(
                legacy.db.execute(
                    "SELECT title FROM conversations WHERE id=?",
                    (c.id,),
                ).fetchone()[0], "legacy-raw"
            )
        finally:
            legacy.close()

    def test_invalid_optin_type_refused(self):
        self.store.close()
        for value in (None, 1, 0, "True", [], {}):
            with self.subTest(value=str(value)):
                with self.assertRaises(TypeError):
                    SQLiteChatStore(self.path, strict_sql_authorizer=value)

    def test_authorizer_requires_a309_helper_guard(self):
        self.store.close()
        with self.assertRaises(ValueError):
            SQLiteChatStore(self.path, strict_sql_authorizer=True)

    def test_private_context_invoked_without_public_writer_denied(self):
        c = self.seed()
        with self.assertRaises(sqlite3.DatabaseError):
            with self.store._fenced_chat_transaction():
                changed = self.store.get_conversation(SCOPE, c.id)
                changed.title = "not allowed"
                self.store._update(changed)
        self.assertEqual(raw_count(self.path, "conversations"), 1)

    def test_raw_helper_still_denied_as_in_a309(self):
        c = self.seed()
        changed = self.store.get_conversation(SCOPE, c.id)
        changed.title = "unfenced"
        with self.assertRaises(StorageUnavailableError):
            self.store._update(changed)
        self.assertEqual(
            self.store._health_reason,
            "PRIVATE_HELPER_OUTSIDE_FENCED_WRITE_ZERO_AUTO_RETRY"
        )
        self.assertEqual(raw_count(self.path, "conversations"), 1)

    def test_read_methods_after_rearm_still_work(self):
        c = self.seed()
        self.store.append_message(
            SCOPE, Message(c.id, "user", "visible", id="a310-read")
        )
        rows = self.store.list_messages(SCOPE, c.id).items
        self.assertEqual([m.id for m in rows], ["a310-read"])
        self.assertEqual(self.store.storage_health(deep=True)["state"], HEALTHY)

    def test_untrusted_host_can_disable_sql_authorizer_and_bypass(self):
        """Essential negative control: this is NOT an independent boundary."""
        c = self.seed()
        self.store.db.set_authorizer(None)
        self.store.db.execute(
            "UPDATE conversations SET title='host-bypass' WHERE id=?",
            (c.id,),
        )
        self.store.db.commit()
        self.assertEqual(
            self.store.db.execute(
                "SELECT title FROM conversations WHERE id=?", (c.id,)
            ).fetchone()[0], "host-bypass"
        )
        self.assertFalse(self.store._message_commit_marker.exists())
        self.assertEqual(self.store._health_state, HEALTHY)

    def test_no_external_authority_or_provider_effects(self):
        self.assertTrue(self.store._strict_sql_authorizer)
        self.assertFalse(self.store._message_commit_marker.exists())
        # No new external authority, native FD proof or P0 release.
        self.assertEqual(self.store._health_state, HEALTHY)


class A310UnknownAckTests(unittest.TestCase):
    def test_lost_ack_after_commit_still_denies_retry(self):
        with TemporaryDirectory(prefix="a310-ack-") as raw:
            path = Path(raw) / "db.sqlite"
            original_connect = sqlite3.connect
            def synthetic_connect(*args, **kwargs):
                return original_connect(
                    *args, **kwargs, factory=SyntheticAckLossConnection
                )
            with mock.patch(
                "aion_chat.store.sqlite3.connect",
                side_effect=synthetic_connect,
            ):
                store = SQLiteChatStore(
                    path, strict_private_write_helpers=True,
                    strict_sql_authorizer=True,
                    strict_local_data_version=True,
                )
            try:
                conv = store.create_conversation(SCOPE, "unknown ACK")
                store.db.fault_once = "after"
                with self.assertRaises(StoreCommitOutcomeUncertainError):
                    store.append_message(
                        SCOPE, Message(
                            conv.id, "user", "once", id="a310-ack-message"
                        ),
                    )
                self.assertTrue(store._message_commit_marker.exists())
                self.assertEqual(
                    store._health_reason,
                    "COMMIT_OUTCOME_UNKNOWN_ZERO_AUTO_RETRY",
                )
                self.assertEqual(raw_count(path, "messages"), 1)
                with self.assertRaises(StorageUnavailableError):
                    store.append_message(
                        SCOPE, Message(
                            conv.id, "user", "retry", id="a310-ack-retry"
                        ),
                    )
                self.assertEqual(raw_count(path, "messages"), 1)
            finally:
                store.close()
            with self.assertRaises(StorageUnavailableError):
                SQLiteChatStore(
                    path, strict_private_write_helpers=True,
                    strict_sql_authorizer=True,
                )


if __name__ == "__main__":
    unittest.main()
