"""A246 LAB: ambiguous SQLite message COMMIT must fail closed in-process.

All fixtures are disposable. The simulated missing acknowledgment is injected
immediately before or after an actual SQLite commit, not a physical power loss.
"""
from contextlib import closing
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from aion_chat.models import Message, Scope
from aion_chat.store import (
    FAILED, HEALTHY, SQLiteChatStore,
    StorageUnavailableError, StoreCommitOutcomeUncertainError,
)

SCOPE = Scope("owner-a246", "tenant-a246", "workspace-a246")


class LostAckConnection:
    """Proxy that injects one exception at the SQLite COMMIT boundary."""

    def __init__(self, raw, *, after_commit):
        self.raw = raw
        self.after_commit = after_commit
        self.commit_calls = 0
        self.rollback_calls = 0

    def execute(self, *args, **kwargs):
        return self.raw.execute(*args, **kwargs)

    def commit(self):
        self.commit_calls += 1
        if self.after_commit:
            self.raw.commit()
        raise sqlite3.OperationalError("synthetic missing COMMIT acknowledgment")

    def rollback(self):
        self.rollback_calls += 1
        return self.raw.rollback()

    def close(self):
        return self.raw.close()


class A246ChatCommitUncertaintyTests(unittest.TestCase):
    def test_01_ordinary_message_commit_works(self):
        with TemporaryDirectory(prefix="a246-normal-") as raw:
            store = SQLiteChatStore(Path(raw) / "chat.db")
            try:
                c = store.create_conversation(SCOPE, "normal")
                row = store.append_message(
                    SCOPE, Message(c.id, "user", "normal", id="a246-normal-message"),
                )
                self.assertEqual(row.sequence, 1)
                self.assertEqual(store.require_healthy()["state"], HEALTHY)
                self.assertEqual(store.get_conversation(SCOPE, c.id).message_count, 1)
            finally:
                store.close()

    def _exercise_fault(self, *, after_commit):
        with TemporaryDirectory(prefix="a246-uncertain-") as raw:
            path = Path(raw) / "chat.db"
            store = SQLiteChatStore(path)
            conversation = store.create_conversation(SCOPE, "commit uncertainty")
            injected = LostAckConnection(store.db, after_commit=after_commit)
            store.db = injected
            msg = Message(
                conversation.id, "user", "synthetic-commit-boundary",
                id="a246-fixed-message-id",
            )
            try:
                with self.assertRaisesRegex(
                    StoreCommitOutcomeUncertainError, "outcome unknown",
                ):
                    store.append_message(SCOPE, msg)
                self.assertEqual(injected.commit_calls, 1)
                self.assertEqual(store._health_state, FAILED)
                self.assertEqual(
                    store._health_reason, "COMMIT_OUTCOME_UNKNOWN_ZERO_AUTO_RETRY",
                )
                with self.assertRaises(StorageUnavailableError):
                    store.append_message(SCOPE, msg)
                with self.assertRaises(StorageUnavailableError):
                    store.create_conversation(SCOPE, "must not proceed")
                with self.assertRaises(StorageUnavailableError):
                    store.require_healthy()
                with closing(sqlite3.connect(str(path))) as verify:
                    observed = verify.execute(
                        "SELECT COUNT(*) FROM messages WHERE id=?",
                        (msg.id,),
                    ).fetchone()[0]
                self.assertEqual(observed, 1 if after_commit else 0)
                return path
            finally:
                store.close()

    def test_02_real_commit_then_missing_ack_is_uncertain_and_sticky(self):
        self._exercise_fault(after_commit=True)

    def test_03_exception_before_commit_is_also_conservatively_blocked(self):
        self._exercise_fault(after_commit=False)

    def test_04_closed_failed_store_cannot_be_revived_by_health_check(self):
        with TemporaryDirectory(prefix="a246-sticky-") as raw:
            path = Path(raw) / "chat.db"
            store = SQLiteChatStore(path)
            c = store.create_conversation(SCOPE, "sticky")
            store.db = LostAckConnection(store.db, after_commit=True)
            try:
                with self.assertRaises(StoreCommitOutcomeUncertainError):
                    store.append_message(
                        SCOPE, Message(c.id, "user", "uncertain", id="a246-sticky-msg"),
                    )
                self.assertEqual(store.storage_health(deep=True)["state"], FAILED)
                store.close()
                self.assertEqual(store.storage_health()["state"], FAILED)
            finally:
                store.close()

    def test_05_restart_denied_by_local_fence_after_lost_ack(self):
        """A247 adds local restart veto; still no independent authority."""
        with TemporaryDirectory(prefix="a246-restart-") as raw:
            path = Path(raw) / "chat.db"
            first = SQLiteChatStore(path)
            c = first.create_conversation(SCOPE, "restart")
            first.db = LostAckConnection(first.db, after_commit=True)
            try:
                with self.assertRaises(StoreCommitOutcomeUncertainError):
                    first.append_message(
                        SCOPE, Message(c.id, "user", "unknown", id="a246-restart-msg"),
                    )
            finally:
                first.close()
            # A247: local marker persists and vetoes re-open. A hostile host
            # can delete it, so this is NOT independent reconciliation.
            with self.assertRaises(StorageUnavailableError):
                second = SQLiteChatStore(path)
                second.close()


if __name__ == "__main__":
    unittest.main()
