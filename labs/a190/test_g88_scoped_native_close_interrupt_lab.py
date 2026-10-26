"""G88 RED-first: operation-scoped SQLite errors must never reauthorize reuse.

Real temporary SQLite, synthetic close/body interrupts only. A failed native
close may retain a writer lock; logical quarantine cannot release it. Tests
never send to providers or invoke Worker. P0 0/6; HARD NO-GO.
"""
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from aion_chat.models import Message, Scope
from aion_chat.staged_store import OperationScopedSQLiteChatStore
from aion_chat.store import FAILED, SQLiteChatStore, StorageUnavailableError


SCOPE = Scope("g88-owner", "g88-tenant", "g88-workspace")


class G88ScopedNativeCloseInterrupt(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="aion-g88-native-close-")
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "chat.sqlite3"
        self.handle = OperationScopedSQLiteChatStore(self.path)
        self.addCleanup(self.handle.close)
        self.cid = self.handle.create_conversation(SCOPE, "existing").id
        self.raw_connections = []

    @staticmethod
    def capture(callback):
        try:
            callback()
        except BaseException as error:
            return error
        return None

    def writer_available(self):
        probe = sqlite3.connect(str(self.path), timeout=0)
        try:
            probe.execute("BEGIN IMMEDIATE")
            self.assertTrue(probe.in_transaction)
        finally:
            probe.close()

    def writer_blocked(self):
        probe = sqlite3.connect(str(self.path), timeout=0)
        try:
            with self.assertRaises(sqlite3.OperationalError) as caught:
                probe.execute("BEGIN IMMEDIATE")
            self.assertRegex(str(caught.exception).lower(), "locked|busy")
        finally:
            probe.close()

    def inject_close_fault(self, fault, *, after):
        original = SQLiteChatStore.close
        close_counts = []
        def failing_close(native):
            close_counts.append(native)
            raw = native.db
            if not after:
                # Keep a real native writer lock while the public facade must
                # be latched; release only through fixture cleanup, never retry.
                raw.execute("BEGIN IMMEDIATE")
                self.raw_connections.append(raw)
                raise fault
            original(native)
            raise fault
        return failing_close, close_counts

    def cleanup_retained(self):
        for raw in self.raw_connections:
            raw.close()
        self.raw_connections.clear()
        self.writer_available()

    def assert_quarantined(self):
        with self.subTest(contract="health_failed"):
            self.assertEqual(self.handle.storage_health()["state"], FAILED)
        with self.subTest(contract="no_reopen_for_read"):
            caught = self.capture(lambda: self.handle.get_conversation(SCOPE, self.cid))
            self.assertIsInstance(caught, StorageUnavailableError)
        with self.subTest(contract="no_reopen_for_write"):
            caught = self.capture(lambda: self.handle.append_message(
                SCOPE, Message(self.cid, "user", "must-not-retry")))
            self.assertIsInstance(caught, StorageUnavailableError)

    def exercise_secondary(self, fault, *, after, primary=None, marker):
        failing_close, called = self.inject_close_fault(fault, after=after)
        # LIFO cleanup: close retained raw before deleting the temporary DB.
        self.addCleanup(self.cleanup_retained)
        def operation():
            if primary is not None:
                with patch.object(SQLiteChatStore, "get_conversation", side_effect=primary):
                    self.handle.get_conversation(SCOPE, self.cid)
            else:
                self.handle.append_message(SCOPE, Message(
                    self.cid, "user", "persisted-before-close-fault"))
        with patch.object(SQLiteChatStore, "close", failing_close):
            caught = self.capture(operation)
        with self.subTest(contract="original_error_identity"):
            self.assertIs(caught, primary if primary is not None else fault)
        with self.subTest(contract="single_close_no_retry"):
            self.assertEqual(len(called), 1)
        if after:
            with self.subTest(contract="native_close_already_completed"):
                self.writer_available()
        else:
            with self.subTest(contract="native_writer_lock_still_retained"):
                self.writer_blocked()
        self.assert_quarantined()
        print(marker)

    def test_01_close_keyboard_interrupt_before_native_close(self):
        self.exercise_secondary(
            KeyboardInterrupt("G88_CLOSE_BEFORE_KI"), after=False,
            marker="G88_CLOSE_KI_GREEN=QUARANTINED_LOCK_UNCERTAIN")

    def test_02_close_system_exit_after_native_close(self):
        self.exercise_secondary(
            SystemExit("G88_CLOSE_AFTER_EXIT"), after=True,
            marker="G88_CLOSE_EXIT_GREEN=QUARANTINED_NATIVE_RELEASED")

    def test_03_primary_lookup_error_survives_secondary_keyboard_interrupt(self):
        self.exercise_secondary(
            KeyboardInterrupt("G88_SECONDARY_KI"), after=False,
            primary=LookupError("G88_PRIMARY_NOT_FOUND"),
            marker="G88_PRIMARY_LOOKUP_GREEN=NOT_MASKED_AND_QUARANTINED")

    def test_04_primary_storage_error_survives_secondary_system_exit(self):
        self.exercise_secondary(
            SystemExit("G88_SECONDARY_EXIT"), after=True,
            primary=StorageUnavailableError("G88_PRIMARY_UNAVAILABLE"),
            marker="G88_PRIMARY_STORAGE_GREEN=NOT_MASKED_AND_QUARANTINED")

    def exercise_primary_body_interrupt(self, error, marker):
        with patch.object(SQLiteChatStore, "get_conversation", side_effect=error):
            caught = self.capture(
                lambda: self.handle.get_conversation(SCOPE, self.cid))
        self.assertIs(caught, error)
        self.assert_quarantined()
        self.writer_available()
        print(marker)

    def test_05_primary_keyboard_interrupt_from_read_body_latches_facade(self):
        self.exercise_primary_body_interrupt(
            KeyboardInterrupt("G88_BODY_KI"),
            "G88_BODY_KI_GREEN=NO_REUSE")

    def test_06_primary_system_exit_from_read_body_latches_facade(self):
        self.exercise_primary_body_interrupt(
            SystemExit("G88_BODY_EXIT"),
            "G88_BODY_EXIT_GREEN=NO_REUSE")


if __name__ == "__main__":
    unittest.main()
