"""G82 tests-first close failure and physical writer-lock specification.

Pinned G81 HEAD: eed76454512e900dc48081e52c3ad966b074770a.
Not executed by Codex: host must establish RED outside the Windows sandbox.
Temporary local SQLite and retained synthetic faults only. No external calls.
Logical quarantine does not guarantee native handle or writer-lock release.
"""
from pathlib import Path
import sqlite3
import tempfile
import unittest

from aion_chat.models import Scope
from aion_chat.store import FAILED, HEALTHY, SQLiteChatStore, StorageUnavailableError


SCOPE = Scope("g82-owner", "g82-tenant", "g82-workspace")


class CloseFaultProxy:
    """Keep the raw handle alive even when the store drops its reference."""

    def __init__(self, raw, *, after=False, fault=None, body_fault=None):
        self.raw = raw
        self.after = after
        self.fault = fault
        self.body_fault = body_fault
        self.close_count = 0
        self.pending_at_close = None
        self.body_count = 0

    def execute(self, sql, *args, **kwargs):
        result = self.raw.execute(sql, *args, **kwargs)
        if (self.body_fault is not None
                and sql.lstrip().upper().startswith("INSERT INTO CONVERSATIONS")):
            self.body_count += 1
            raise self.body_fault
        return result

    def close(self):
        self.close_count += 1
        self.pending_at_close = self.raw.in_transaction
        if self.fault is not None and not self.after:
            raise self.fault
        self.raw.close()
        if self.fault is not None:
            raise self.fault

    def __getattr__(self, name):
        return getattr(self.raw, name)


class G82CloseFailureLock(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="aion-g82-close-")
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / "chat.sqlite3"
        self.store = SQLiteChatStore(self.path)
        self.raw = self.store.db
        # LIFO: native cleanup and the post-cleanup lock probe precede tmp removal.
        self.addCleanup(self.cleanup_raw)

    def cleanup_raw(self):
        # Bypass the retained fault proxy, including after a RED assertion.
        try:
            self.raw.close()
        finally:
            self.store.db = None
        # A busy result before cleanup is meaningful only if cleanup releases it.
        self.assert_writer_available()

    def capture(self, operation):
        # Retain BaseException objects without allowing them to exit the runner.
        try:
            operation()
        except BaseException as error:
            return error
        return None

    def assert_writer_available(self):
        fresh = sqlite3.connect(str(self.path), timeout=0)
        try:
            fresh.execute("BEGIN IMMEDIATE")
            self.assertTrue(fresh.in_transaction)
        finally:
            fresh.rollback()
            fresh.close()

    def assert_writer_blocked(self):
        fresh = sqlite3.connect(str(self.path), timeout=0)
        try:
            with self.assertRaises(sqlite3.OperationalError) as caught:
                fresh.execute("BEGIN IMMEDIATE")
            self.assertRegex(str(caught.exception).lower(), r"busy|locked")
            self.assertFalse(fresh.in_transaction)
        finally:
            fresh.rollback()
            fresh.close()

    def assert_store_denied(self):
        # Separate subtests expose each contract failure on the pinned baseline.
        with self.subTest(contract="detached"):
            self.assertIsNone(self.store.db)
        with self.subTest(contract="failed_health"):
            self.assertEqual(self.store.storage_health()["state"], FAILED)
        with self.subTest(contract="denied_create"):
            caught = self.capture(lambda: self.store.create_conversation(SCOPE, "denied"))
            self.assertIsInstance(caught, StorageUnavailableError)

    def exercise_close_fault(self, fault, *, after):
        self.assertEqual(self.store.storage_health()["state"], HEALTHY)
        self.proxy = CloseFaultProxy(self.raw, after=after, fault=fault)
        self.store.db = self.proxy
        self.raw.execute("BEGIN IMMEDIATE")
        caught = self.capture(self.store.close)
        self.assertIs(caught, fault)
        self.assertIs(self.proxy.fault, fault)
        self.assertEqual(self.proxy.close_count, 1)
        self.assertTrue(self.proxy.pending_at_close)
        # Probe BEFORE cleanup and before logical assertions can fail RED.
        if after:
            self.assert_writer_available()
            with self.assertRaises(sqlite3.ProgrammingError):
                self.raw.execute("SELECT 1")
        else:
            self.assertTrue(self.raw.in_transaction)
            self.assert_writer_blocked()
        self.assert_store_denied()
        # Failed close is also idempotent: no second native close or retry.
        self.assertIsNone(self.store.close())
        self.assertEqual(self.proxy.close_count, 1)
        if not after:
            self.assert_writer_blocked()

    def test_close_keyboard_interrupt_before_native_close(self):
        self.exercise_close_fault(KeyboardInterrupt("G82_BEFORE_KI"), after=False)

    def test_close_system_exit_before_native_close(self):
        self.exercise_close_fault(SystemExit("G82_BEFORE_EXIT"), after=False)

    def test_close_keyboard_interrupt_after_native_close(self):
        self.exercise_close_fault(KeyboardInterrupt("G82_AFTER_KI"), after=True)

    def test_close_system_exit_after_native_close(self):
        self.exercise_close_fault(SystemExit("G82_AFTER_EXIT"), after=True)

    def test_regular_close_releases_lock_and_is_idempotent(self):
        created = self.store.create_conversation(SCOPE, "regular-close-control")
        self.assertIsNotNone(created.id)
        self.assertEqual(self.store.storage_health()["state"], HEALTHY)
        self.proxy = CloseFaultProxy(self.raw)
        self.store.db = self.proxy
        self.raw.execute("BEGIN IMMEDIATE")
        self.assertIsNone(self.store.close())
        self.assertEqual(self.proxy.close_count, 1)
        self.assertTrue(self.proxy.pending_at_close)
        self.assert_writer_available()
        self.assert_store_denied()
        self.assertIsNone(self.store.close())
        self.assertEqual(self.proxy.close_count, 1)

    def test_g81_body_quarantine_denies_reuse_but_retains_native_writer_lock(self):
        primary = KeyboardInterrupt("G82_BODY_AFTER_REAL_INSERT")
        secondary = SystemExit("G82_QUARANTINE_BEFORE_NATIVE_CLOSE")
        self.proxy = CloseFaultProxy(self.raw, fault=secondary, body_fault=primary)
        self.store.db = self.proxy
        caught = self.capture(lambda: self.store.create_conversation(SCOPE, "pending"))
        self.assertIs(caught, primary)
        self.assertIsNot(caught, secondary)
        self.assertIs(self.proxy.body_fault, primary)
        self.assertIs(self.proxy.fault, secondary)
        self.assertEqual(self.proxy.body_count, 1)
        self.assertEqual(self.proxy.close_count, 1)
        self.assertTrue(self.proxy.pending_at_close)
        self.assertTrue(self.raw.in_transaction)
        self.assertEqual(self.raw.execute("SELECT COUNT(*) FROM conversations").fetchone()[0], 1)
        self.assert_writer_blocked()
        self.assert_store_denied()
        self.assertIsNone(self.store.close())
        self.assertEqual(self.proxy.close_count, 1)
        # Only cleanup_raw releases this lock; logical denial alone cannot do so.
        self.assert_writer_blocked()


if __name__ == "__main__":
    unittest.main()
