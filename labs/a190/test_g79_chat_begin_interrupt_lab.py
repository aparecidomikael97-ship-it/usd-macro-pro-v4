"""G79 adversarial RED specification for BEGIN quarantine only.

Pinned baseline: G78 003b5e6a22e712e46235fe303e4c75b958f4b9f8.
Host-run FIRST, outside the Codex sandbox (known SQLite temp access denial).
Not executed by Codex; RED/GREEN requires host evidence. P0: 0/6 HARD NO-GO.
Only temporary local SQLite and synthetic faults: no HTTP/provider effects.
G32/G33 fixture ideas are reused without importing or inheriting their tests.
_rollback_or_quarantine is deliberately outside this specification's scope.
"""
from pathlib import Path
import tempfile
import unittest

from aion_chat.models import Scope
from aion_chat.store import FAILED, SQLiteChatStore, StorageUnavailableError


SCOPE = Scope("g79-owner", "g79-tenant", "g79-workspace")


class BeginFaultProxy:
    """Throw the retained primary before or after a real BEGIN IMMEDIATE."""

    def __init__(self, raw, *, after, primary, close_error=None):
        self.raw = raw
        self.after = after
        self.primary = primary
        self.close_error = close_error
        self.begin_count = 0
        self.real_begin_count = 0
        self.rollback_count = 0
        self.close_count = 0
        self.insert_count = 0

    def execute(self, sql, *args, **kwargs):
        if sql.strip().upper() == "BEGIN IMMEDIATE":
            self.begin_count += 1
            if self.after:
                self.raw.execute(sql, *args, **kwargs)
                self.real_begin_count += 1
            raise self.primary
        if sql.lstrip().upper().startswith("INSERT INTO CONVERSATIONS"):
            self.insert_count += 1
        return self.raw.execute(sql, *args, **kwargs)

    def rollback(self):
        self.rollback_count += 1
        return self.raw.rollback()

    def close(self):
        self.close_count += 1
        # Release the actual handle/lock before injecting the secondary fault.
        self.raw.close()
        if self.close_error is not None:
            raise self.close_error

    def __getattr__(self, name):
        return getattr(self.raw, name)


class G79ChatBeginInterrupt(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="aion-g79-chat-")
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "chat.sqlite3"
        self.store = SQLiteChatStore(self.path)
        self.raw = self.store.db
        self.addCleanup(self.cleanup_raw)

    def cleanup_raw(self):
        # A failed assertion must not leave a write lock or re-invoke the
        # faulting proxy.close. Never resurrect a quarantined connection.
        self.raw.close()
        self.store.db = None

    def assert_begin_quarantined(self, *, after, primary, close_error=None):
        proxy = BeginFaultProxy(
            self.raw, after=after, primary=primary, close_error=close_error
        )
        # Schema initialization is complete before installing the fault.
        self.store.db = proxy
        with self.assertRaises(BaseException) as caught:
            self.store.create_conversation(SCOPE, "g79-must-not-exist")

        # Catch BaseException so a secondary SystemExit is an identity failure,
        # rather than an exit from the host test runner.
        self.assertIs(caught.exception, primary)
        self.assertEqual(proxy.begin_count, 1)
        self.assertEqual(proxy.real_begin_count, int(after))
        self.assertEqual(proxy.insert_count, 0)
        self.assertEqual(proxy.rollback_count, 0)
        self.assertEqual(proxy.close_count, 1)
        self.assertIsNone(self.store.db)
        self.assertEqual(self.store.storage_health()["state"], FAILED)
        with self.assertRaises(StorageUnavailableError):
            self.store.require_healthy()
        for _ in range(2):
            with self.assertRaises(StorageUnavailableError):
                self.store.create_conversation(SCOPE, "g79-denied-retry")
        self.assertEqual(proxy.begin_count, 1)
        self.assertEqual(proxy.rollback_count, 0)
        self.assertEqual(proxy.close_count, 1)
        self.assertEqual(proxy.insert_count, 0)

        # Fresh construction on the same file must work after physical close.
        # A BEGIN alone creates no conversation, even when it acquired a lock.
        fresh = SQLiteChatStore(self.path)
        try:
            self.assertEqual(fresh.require_healthy()["state"], "healthy")
            self.assertEqual(fresh.list_conversations(SCOPE).items, [])
            self.assertEqual(
                fresh.db.execute("SELECT COUNT(*) FROM conversations").fetchone()[0],
                0,
            )
        finally:
            fresh.close()

    def test_01_keyboard_interrupt_before_begin(self):
        self.assert_begin_quarantined(
            after=False, primary=KeyboardInterrupt("G79_BEGIN_BEFORE")
        )

    def test_02_keyboard_interrupt_after_begin(self):
        self.assert_begin_quarantined(
            after=True, primary=KeyboardInterrupt("G79_BEGIN_AFTER")
        )

    def test_03_system_exit_before_begin(self):
        self.assert_begin_quarantined(
            after=False, primary=SystemExit("G79_BEGIN_BEFORE")
        )

    def test_04_system_exit_after_begin(self):
        self.assert_begin_quarantined(
            after=True, primary=SystemExit("G79_BEGIN_AFTER")
        )

    def test_05_secondary_system_exit_after_raw_close_before_begin(self):
        # OSError already enters quarantine, isolating close-error masking.
        self.assert_begin_quarantined(
            after=False, primary=OSError("G79_PRIMARY_BEGIN_BEFORE"),
            close_error=SystemExit("G79_SECONDARY_CLOSE"),
        )

    def test_06_secondary_system_exit_after_raw_close_after_begin(self):
        self.assert_begin_quarantined(
            after=True, primary=OSError("G79_PRIMARY_BEGIN_AFTER"),
            close_error=SystemExit("G79_SECONDARY_CLOSE"),
        )

    def test_07_oserror_before_begin_control(self):
        self.assert_begin_quarantined(
            after=False, primary=OSError("G79_BEGIN_BEFORE_CONTROL")
        )

    def test_08_oserror_after_begin_control(self):
        self.assert_begin_quarantined(
            after=True, primary=OSError("G79_BEGIN_AFTER_CONTROL")
        )


if __name__ == "__main__":
    unittest.main()
