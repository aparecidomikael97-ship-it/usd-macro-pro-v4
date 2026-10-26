"""G80 tests-first specification for rollback interruption quarantine.

Pinned G79 baseline: 21bde47cec7e60f26a762d03829090eb8af24060.
Not executed by Codex: host must establish RED outside the Windows sandbox.
P0: 0/6 HARD NO-GO. Temporary local SQLite and synthetic faults only.
Reuse G32's local SQLite fixture pattern without importing/inheriting tests.
The body always raises a normal RuntimeError AFTER a real conversation INSERT.
Body KeyboardInterrupt handling is explicitly outside this specification.
No network, provider, Worker, external custody or durability claims.
"""
from pathlib import Path
import tempfile
import unittest

from aion_chat.models import Scope
from aion_chat.store import FAILED, SQLiteChatStore, StorageUnavailableError


SCOPE = Scope("g80-owner", "g80-tenant", "g80-workspace")


class RollbackFaultProxy:
    """Retain all faults; interrupt rollback before or after its real effect."""

    def __init__(self, raw, *, after, rollback_error, close_error=None):
        self.raw = raw
        self.after = after
        self.primary = RuntimeError("G80_PRIMARY_AFTER_REAL_INSERT")
        self.rollback_error = rollback_error
        self.close_error = close_error
        self.inserts = 0
        self.real_inserts = 0
        self.rollbacks = 0
        self.real_rollbacks = 0
        self.commits = 0
        self.closes = 0
        self.inserted_id = None
        self.pending_at_fault = False
        self.pending_at_close = None

    def execute(self, sql, *args, **kwargs):
        if sql.lstrip().upper().startswith("INSERT INTO CONVERSATIONS"):
            self.inserts += 1
            self.raw.execute(sql, *args, **kwargs)
            self.real_inserts += 1
            self.inserted_id = args[0][0]
            self.pending_at_fault = self.raw.in_transaction
            raise self.primary
        return self.raw.execute(sql, *args, **kwargs)

    def rollback(self):
        self.rollbacks += 1
        if self.after:
            self.raw.rollback()
            self.real_rollbacks += 1
        raise self.rollback_error

    def commit(self):
        self.commits += 1
        return self.raw.commit()

    def close(self):
        self.closes += 1
        self.pending_at_close = self.raw.in_transaction
        # SQLite close rolls back the pending INSERT in before-rollback cases.
        # Inject the secondary only after releasing the real handle and lock.
        self.raw.close()
        if self.close_error is not None:
            raise self.close_error

    def __getattr__(self, name):
        return getattr(self.raw, name)


class G80ChatRollbackInterrupt(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="aion-g80-chat-")
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "chat.sqlite3"
        self.store = SQLiteChatStore(self.path)
        self.raw = self.store.db
        self.addCleanup(self.cleanup_raw)

    def cleanup_raw(self):
        # Failed RED assertions must release locks without invoking the proxy
        # again or resurrecting a quarantined store. SQLite close is idempotent.
        self.raw.close()
        self.store.db = None

    def assert_rollback_quarantined(self, *, after, rollback_error,
                                    close_error=None):
        proxy = RollbackFaultProxy(
            self.raw, after=after, rollback_error=rollback_error,
            close_error=close_error,
        )
        # Install only after schema initialization; exercise the public write.
        self.store.db = proxy
        with self.assertRaises(BaseException) as caught:
            self.store.create_conversation(SCOPE, "g80-must-not-survive")

        # Capture BaseException so leaked interrupts fail identity assertions
        # instead of interrupting/exiting the host test runner.
        self.assertEqual(proxy.inserts, 1)
        self.assertEqual(proxy.real_inserts, 1)
        self.assertIsNotNone(proxy.inserted_id)
        self.assertTrue(proxy.pending_at_fault)
        self.assertIs(caught.exception, proxy.primary)
        self.assertIs(caught.exception.__cause__, rollback_error)
        self.assertEqual(proxy.rollbacks, 1)
        self.assertEqual(proxy.real_rollbacks, int(after))
        self.assertEqual(proxy.commits, 0)
        self.assertEqual(proxy.closes, 1)
        self.assertIs(proxy.pending_at_close, not after)
        self.assertIsNone(self.store.db)
        self.assertEqual(self.store.storage_health()["state"], FAILED)
        with self.assertRaises(StorageUnavailableError):
            self.store.require_healthy()
        for _ in range(2):
            with self.assertRaises(StorageUnavailableError):
                self.store.create_conversation(SCOPE, "g80-denied-retry")
        self.assertEqual(proxy.inserts, 1)
        self.assertEqual(proxy.rollbacks, 1)
        self.assertEqual(proxy.commits, 0)
        self.assertEqual(proxy.closes, 1)

        # Reopen before fixture cleanup, proving quarantine itself released the
        # handle and removed the real pending row. Local evidence only.
        fresh = SQLiteChatStore(self.path)
        try:
            self.assertEqual(fresh.require_healthy()["state"], "healthy")
            with self.assertRaises(LookupError):
                fresh.get_conversation(SCOPE, proxy.inserted_id)
            self.assertEqual(fresh.list_conversations(SCOPE).items, [])
            self.assertEqual(
                fresh.db.execute("SELECT COUNT(*) FROM conversations").fetchone()[0],
                0,
            )
        finally:
            fresh.close()

    def test_01_keyboard_interrupt_before_real_rollback(self):
        self.assert_rollback_quarantined(
            after=False, rollback_error=KeyboardInterrupt("G80_ROLLBACK_BEFORE")
        )

    def test_02_keyboard_interrupt_after_real_rollback(self):
        self.assert_rollback_quarantined(
            after=True, rollback_error=KeyboardInterrupt("G80_ROLLBACK_AFTER")
        )

    def test_03_system_exit_before_real_rollback(self):
        self.assert_rollback_quarantined(
            after=False, rollback_error=SystemExit("G80_ROLLBACK_BEFORE")
        )

    def test_04_system_exit_after_real_rollback(self):
        self.assert_rollback_quarantined(
            after=True, rollback_error=SystemExit("G80_ROLLBACK_AFTER")
        )

    def test_05_secondary_close_system_exit_preserves_primary_and_cause(self):
        # OSError reaches existing quarantine, isolating close-error masking.
        self.assert_rollback_quarantined(
            after=False, rollback_error=OSError("G80_ROLLBACK_CLOSE_CASE"),
            close_error=SystemExit("G80_SECONDARY_CLOSE"),
        )

    def test_06_oserror_rollback_control(self):
        self.assert_rollback_quarantined(
            after=False, rollback_error=OSError("G80_ROLLBACK_CONTROL")
        )


if __name__ == "__main__":
    unittest.main()
