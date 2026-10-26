"""G81 tests-first body-interrupt specification.

Pinned G80 baseline: 0a61fc2ff774a4e871a3801dc86209c76aa94fdb.
Not executed by Codex; host must establish RED outside the Windows sandbox.
P0=0/6 HARD NO-GO. Synthetic temporary SQLite only; no API/network,
deployment, Worker, payments, external custody or durability claims.
"""
from pathlib import Path
import json
import sqlite3
import tempfile
import unittest

from aion_chat.models import Message, Scope
from aion_chat.store import FAILED, SQLiteChatStore, StorageUnavailableError


SCOPE = Scope("g81-owner", "g81-tenant", "g81-workspace")


class BodyFaultProxy:
    """Raise retained body faults and optional faults around native close."""

    def __init__(self, raw, target, after, primary, *, store=None, close_error=None):
        if close_error not in (None, "after_native_close", "before_native_close"):
            raise ValueError("unknown close error mode")
        self.raw = raw
        self.store = store
        self.close_error = close_error
        self.close_exception = SystemExit("G81_SYNTHETIC_CLOSE_ERROR")
        self.detached_at_close = None
        self.failed_at_close = None
        self.target = target
        self.after = after
        self.primary = primary
        self.begin_count = 0
        self.commit_count = 0
        self.rollback_count = 0
        self.close_count = 0
        self.target_count = 0
        self.real_target_count = 0
        self.real_message_inserts = 0
        self.pending_at_fault = None
        self.pending_at_close = None
        self.visible_at_fault = None
        self.row_id = None
        self.fired = False

    def execute(self, sql, *args, **kwargs):
        normalized = " ".join(sql.upper().split())
        if normalized == "BEGIN IMMEDIATE":
            self.begin_count += 1
        target = normalized.startswith(self.target)
        if target and not self.fired:
            self.fired = True
            self.target_count += 1
            self.row_id = args[0][-1] if self.target.startswith("UPDATE") else args[0][0]
            if self.after:
                self.raw.execute(sql, *args, **kwargs)
                self.real_target_count += 1
                if normalized.startswith("INSERT INTO MESSAGES"):
                    self.real_message_inserts += 1
            self.pending_at_fault = self.raw.in_transaction
            table = "messages" if self.target.startswith("INSERT INTO MESSAGES") else "conversations"
            self.visible_at_fault = self.raw.execute(
                "SELECT COUNT(*) FROM " + table + " WHERE id=?", (self.row_id,)
            ).fetchone()[0]
            raise self.primary
        result = self.raw.execute(sql, *args, **kwargs)
        if normalized.startswith("INSERT INTO MESSAGES"):
            self.real_message_inserts += 1
        return result

    def commit(self):
        self.commit_count += 1
        return self.raw.commit()

    def rollback(self):
        self.rollback_count += 1
        return self.raw.rollback()

    def close(self):
        if self.store is not None:
            self.detached_at_close = self.store.db is None
            self.failed_at_close = self.store._health_state == FAILED
        self.close_count += 1
        self.pending_at_close = self.raw.in_transaction
        if self.close_error == "before_native_close":
            raise self.close_exception
        self.raw.close()
        if self.close_error == "after_native_close":
            raise self.close_exception

    def __getattr__(self, name):
        return getattr(self.raw, name)


class G81ChatBodyInterrupt(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="aion-g81-chat-")
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "chat.sqlite3"
        self.store = SQLiteChatStore(self.path)
        self.raw = self.store.db
        self.addCleanup(self.cleanup_raw)

    def cleanup_raw(self):
        # Never reattach the raw handle or call the fault proxy during cleanup.
        # On RED or a before-native-close fault, release the native handle.
        try:
            self.raw.in_transaction
        except sqlite3.ProgrammingError:
            pass  # Quarantine already physically closed it.
        else:
            self.raw.close()
        self.store.db = None

    def capture(self, operation):
        # Leaked interrupts and unexpected exceptions become assertion failures,
        # never runner exits or misleading unittest ERROR results.
        try:
            operation()
        except BaseException as error:
            return error
        self.fail("write did not propagate the retained body fault")

    def fresh_absence_and_lock(self, conversation, message):
        # Runs BEFORE cleanup: native BEGIN IMMEDIATE proves the writer lock
        # was released by the implementation rather than by the test fixture.
        fresh = sqlite3.connect(str(self.path), timeout=0)
        try:
            fresh.execute("BEGIN IMMEDIATE")
            if conversation is None:
                self.assertEqual(fresh.execute("SELECT COUNT(*) FROM conversations").fetchone()[0], 0)
            else:
                rows = fresh.execute("SELECT id,data FROM conversations").fetchall()
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0][0], conversation.id)
                self.assertEqual(json.loads(rows[0][1]), json.loads(self.original_conversation))
            self.assertEqual(fresh.execute("SELECT COUNT(*) FROM messages").fetchone()[0], 0)
            if message is not None:
                self.assertIsNone(fresh.execute("SELECT id FROM messages WHERE id=?", (message.id,)).fetchone())
        finally:
            fresh.rollback()
            fresh.close()

    def exercise(self, entry, after, primary, *, update=False, control=False, close_error=None):
        conversation = message = None
        if entry == "append":
            conversation = self.store.create_conversation(SCOPE, "g81-valid-conversation")
            self.original_conversation = self.raw.execute(
                "SELECT data FROM conversations WHERE id=?", (conversation.id,)
            ).fetchone()[0]
            message = Message(conversation_id=conversation.id, role="user", content="synthetic g81")
        target = "UPDATE CONVERSATIONS" if update else (
            "INSERT INTO MESSAGES" if entry == "append" else "INSERT INTO CONVERSATIONS"
        )
        proxy = BodyFaultProxy(
            self.raw, target, after, primary,
            store=self.store if close_error else None, close_error=close_error,
        )
        self.store.db = proxy
        operation = (lambda: self.store.append_message(SCOPE, message)) if message else (
            lambda: self.store.create_conversation(SCOPE, "g81-interrupted")
        )
        caught = self.capture(operation)
        self.assertIs(caught, primary)
        if close_error:
            self.assertIsNot(caught, proxy.close_exception)
            self.assertTrue(proxy.detached_at_close)
            self.assertTrue(proxy.failed_at_close)
        self.assertEqual(proxy.begin_count, 1)
        self.assertEqual(proxy.target_count, 1)
        self.assertEqual(proxy.real_target_count, int(after))
        self.assertTrue(proxy.pending_at_fault)
        self.assertEqual(proxy.visible_at_fault, 1 if update else int(after))
        self.assertEqual(proxy.real_message_inserts, int(entry == "append" and (after or update)))
        self.assertEqual(proxy.commit_count, 0)
        if control:
            self.assertEqual(proxy.rollback_count, 1)
            self.assertEqual(proxy.close_count, 0)
            self.assertIs(self.store.db, proxy)
            self.assertFalse(self.raw.in_transaction)
            self.assertEqual(self.store.storage_health(deep=True)["state"], "healthy")
            self.fresh_absence_and_lock(conversation, message)
            # Ordinary OSError must leave the store usable after rollback.
            recovered = self.store.create_conversation(SCOPE, "g81-control-recovery")
            self.assertIsNotNone(recovered.id)
            return

        self.assertEqual(proxy.rollback_count, 0)
        # Expected baseline RED is an AssertionError here (close_count == 0).
        self.assertEqual(proxy.close_count, 1)
        self.assertTrue(proxy.pending_at_close)
        self.assertIsNone(self.store.db)
        self.assertEqual(self.store._health_state, FAILED)
        self.assertEqual(self.store.storage_health(deep=True)["state"], FAILED)
        self.assertIsInstance(self.capture(self.store.require_healthy), StorageUnavailableError)
        for _ in range(2):
            self.assertIsInstance(self.capture(operation), StorageUnavailableError)
            self.assertIsInstance(self.capture(lambda: self.store.create_conversation(SCOPE, "denied")), StorageUnavailableError)
        self.assertEqual(proxy.begin_count, 1)
        self.assertEqual(proxy.target_count, 1)
        self.assertEqual(proxy.commit_count, 0)
        self.assertEqual(proxy.rollback_count, 0)
        self.assertEqual(proxy.close_count, 1)
        if close_error == "before_native_close":
            # The close fault left the native transaction open. Quarantine is
            # proven above, but native release is deliberately NOT claimed.
            self.assertTrue(self.raw.in_transaction)
            self.cleanup_raw()
            return  # No fresh SQLite writer before fixture cleanup.
        if close_error == "after_native_close":
            with self.assertRaises(sqlite3.ProgrammingError):
                self.raw.execute("SELECT 1")
        self.fresh_absence_and_lock(conversation, message)

    def test_01_create_keyboard_before_insert(self):
        self.exercise("create", False, KeyboardInterrupt("G81_CREATE_BEFORE"))

    def test_02_create_keyboard_after_insert(self):
        self.exercise("create", True, KeyboardInterrupt("G81_CREATE_AFTER"))

    def test_03_create_exit_before_insert(self):
        self.exercise("create", False, SystemExit("G81_CREATE_BEFORE"))

    def test_04_create_exit_after_insert(self):
        self.exercise("create", True, SystemExit("G81_CREATE_AFTER"))

    def test_05_append_keyboard_before_insert(self):
        self.exercise("append", False, KeyboardInterrupt("G81_APPEND_BEFORE"))

    def test_06_append_keyboard_after_insert(self):
        self.exercise("append", True, KeyboardInterrupt("G81_APPEND_AFTER"))

    def test_07_append_exit_before_insert(self):
        self.exercise("append", False, SystemExit("G81_APPEND_BEFORE"))

    def test_08_append_exit_after_insert(self):
        self.exercise("append", True, SystemExit("G81_APPEND_AFTER"))

    def test_09_update_interrupt_after_prior_message_insert(self):
        self.exercise("append", True, SystemExit("G81_UPDATE_AFTER_INSERT"), update=True)

    def test_10_oserror_preserves_rollback_for_both_entry_points(self):
        # Separate fresh fixtures keep each control independent of recovery rows.
        for entry in ("create", "append"):
            with self.subTest(entry=entry):
                fixture = G81ChatBodyInterrupt()
                try:
                    fixture.setUp()
                    fixture.exercise(entry, True, OSError("G81_NORMAL_BODY_ERROR"), control=True)
                finally:
                    fixture.doCleanups()

    def exercise_close_error(self, entry, mode):
        for fault_type in (KeyboardInterrupt, SystemExit):
            with self.subTest(primary=fault_type.__name__, close_error=mode):
                fixture = G81ChatBodyInterrupt()
                try:
                    fixture.setUp()
                    fixture.exercise(
                        entry, True, fault_type("G81_RETAINED_BODY_ERROR"),
                        close_error=mode,
                    )
                finally:
                    fixture.doCleanups()

    def test_11_create_close_exit_after_native_close(self):
        self.exercise_close_error("create", "after_native_close")

    def test_12_append_close_exit_after_native_close(self):
        self.exercise_close_error("append", "after_native_close")

    def test_13_create_close_exit_before_native_close(self):
        self.exercise_close_error("create", "before_native_close")

    def test_14_append_close_exit_before_native_close(self):
        self.exercise_close_error("append", "before_native_close")


if __name__ == "__main__":
    unittest.main()
