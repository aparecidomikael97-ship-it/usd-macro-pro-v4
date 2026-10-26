"""G82 tests-first close containment and native lock characterization.

Pinned G81 baseline: eed76454512e900dc48081e52c3ad966b074770a.
Eight unittest cases: five intentional RED close-failure specifications;
three expected PASS cases (normal close and two retained-lock hazards).
No expectedFailure decorators: host must observe the original-code RED.
Not executed by Codex in the restricted Windows sandbox. Windows/Linux,
synthetic temporary SQLite only; no providers, network or money.
P0=0/6 HARD NO-GO. Detachment is safety containment, not native release.
"""
from pathlib import Path
import sqlite3
import tempfile
import unittest

from aion_chat.models import Scope
from aion_chat.store import FAILED, SQLiteChatStore, StorageUnavailableError


SCOPE = Scope("g82-owner", "g82-tenant", "g82-workspace")


class CloseFaultProxy:
    """Fault only at deterministic body/close boundaries; retain raw ownership."""

    def __init__(self, raw, store, close_error=None, *, after_close=False, body_error=None):
        self.raw = raw
        self.store = store
        self.close_error = close_error
        self.after_close = after_close
        self.body_error = body_error
        self.body_fired = False
        self.close_count = 0
        self.native_close_count = 0
        self.begin_count = 0
        self.commit_count = 0
        self.rollback_count = 0
        self.detached_at_close = None
        self.failed_at_close = None
        self.pending_at_close = None

    def execute(self, sql, *args, **kwargs):
        normalized = " ".join(sql.upper().split())
        if normalized == "BEGIN IMMEDIATE":
            self.begin_count += 1
        result = self.raw.execute(sql, *args, **kwargs)
        if (self.body_error is not None and not self.body_fired
                and normalized.startswith("INSERT INTO CONVERSATIONS")):
            self.body_fired = True
            # Real insertion under BEGIN IMMEDIATE establishes a native writer.
            raise self.body_error
        return result

    def commit(self):
        self.commit_count += 1
        return self.raw.commit()

    def rollback(self):
        self.rollback_count += 1
        return self.raw.rollback()

    def close(self):
        self.close_count += 1
        self.detached_at_close = self.store.db is None
        self.failed_at_close = self.store._health_state == FAILED
        self.pending_at_close = self.raw.in_transaction
        if self.close_error is not None and not self.after_close:
            raise self.close_error
        self.raw.close()
        self.native_close_count += 1
        if self.close_error is not None:
            raise self.close_error

    def __getattr__(self, name):
        return getattr(self.raw, name)


class G82CloseFailureReuseLock(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="aion-g82-close-")
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "chat.sqlite3"
        self.store = SQLiteChatStore(self.path)
        self.raw = self.store.db
        self.addCleanup(self.cleanup_raw)

    def cleanup_raw(self):
        # Always registered, including assertion failures. Bypass the proxy;
        # never rely on store.close() to release a deliberately stranded handle.
        try:
            self.raw.in_transaction
        except sqlite3.ProgrammingError:
            pass
        else:
            self.raw.close()
        self.store.db = None

    def capture(self, operation):
        # Catch retained interrupts without terminating the unittest runner.
        try:
            operation()
        except BaseException as error:
            return error
        self.fail("expected operation to raise")

    def assert_contained(self):
        # Subtests expose each independent requirement on the original code.
        with self.subTest(requirement="detached"):
            self.assertIsNone(self.store.db)
        with self.subTest(requirement="health_failed"):
            self.assertEqual(self.store.storage_health(deep=True)["state"], FAILED)
        with self.subTest(requirement="create_refused"):
            self.assertIsInstance(
                self.capture(lambda: self.store.create_conversation(SCOPE, "denied")),
                StorageUnavailableError,
            )

    def exercise_explicit_close(self, error, *, after_close=False):
        proxy = CloseFaultProxy(self.raw, self.store, error, after_close=after_close)
        self.store.db = proxy  # The sole fault-injection seam.
        self.assertIs(self.capture(self.store.close), error)
        self.assertEqual(proxy.close_count, 1)
        self.assertTrue(proxy.detached_at_close)
        self.assertEqual(self.store._health_state, FAILED)
        self.assertEqual(proxy.native_close_count, int(after_close))
        if after_close:
            with self.assertRaises(sqlite3.ProgrammingError):
                self.raw.execute("SELECT 1")
        else:
            # A live handle is permitted here; forced native closure is not
            # part of the containment contract. Fixture cleanup owns release.
            self.assertEqual(self.raw.execute("SELECT 1").fetchone()[0], 1)
        self.assert_contained()

    # Intentional original-code RED: retained error, detach, failed health,
    # and denial of subsequent create even if the native handle is still live.
    def test_01_red_close_keyboard_before_native_close(self):
        self.exercise_explicit_close(KeyboardInterrupt("G82_CLOSE_BEFORE"))

    def test_02_red_close_exit_before_native_close(self):
        self.exercise_explicit_close(SystemExit("G82_CLOSE_BEFORE"))

    def test_03_red_close_keyboard_after_native_close(self):
        self.exercise_explicit_close(KeyboardInterrupt("G82_CLOSE_AFTER"), after_close=True)

    def test_04_red_close_exit_after_native_close(self):
        self.exercise_explicit_close(SystemExit("G82_CLOSE_AFTER"), after_close=True)

    def test_05_red_close_oserror_before_native_close(self):
        self.exercise_explicit_close(OSError("G82_CLOSE_BEFORE"))

    def test_06_pass_normal_close_is_idempotent(self):
        proxy = CloseFaultProxy(self.raw, self.store)
        self.store.db = proxy
        self.store.close()
        self.store.close()
        self.assertEqual(proxy.close_count, 1)
        self.assertEqual(proxy.native_close_count, 1)
        with self.assertRaises(sqlite3.ProgrammingError):
            self.raw.execute("SELECT 1")
        self.assert_contained()

    def exercise_quarantine_lock(self, secondary):
        primary = KeyboardInterrupt("G82_RETAINED_BODY_INTERRUPT")
        proxy = CloseFaultProxy(self.raw, self.store, secondary, body_error=primary)
        self.store.db = proxy
        caught = self.capture(lambda: self.store.create_conversation(SCOPE, "interrupted"))
        self.assertIs(caught, primary)
        self.assertIsNot(caught, secondary)
        self.assertTrue(proxy.body_fired)
        self.assertTrue(proxy.detached_at_close)
        self.assertTrue(proxy.failed_at_close)
        self.assertTrue(proxy.pending_at_close)
        self.assertEqual(self.store._health_state, FAILED)
        self.assert_contained()
        self.assertEqual(proxy.begin_count, 1)
        self.assertEqual(proxy.commit_count, 0)
        self.assertEqual(proxy.rollback_count, 0)
        self.assertEqual(proxy.close_count, 1)
        self.assertEqual(proxy.native_close_count, 0)
        self.assertTrue(self.raw.in_transaction)

        # BEFORE fixture cleanup: safety containment passed, but the native
        # writer remains locked. A brand-new connection supplies the evidence.
        fresh = sqlite3.connect(str(self.path), timeout=0)
        try:
            error = self.capture(lambda: fresh.execute("BEGIN IMMEDIATE"))
            self.assertIsInstance(error, sqlite3.OperationalError)
            code = getattr(error, "sqlite_errorcode", None)
            if code is not None:
                self.assertEqual(code & 0xFF, sqlite3.SQLITE_BUSY)
            else:
                self.assertIn("locked", str(error).lower())
            self.assertFalse(fresh.in_transaction)
        finally:
            fresh.close()

        self.cleanup_raw()  # Explicit fixture release, NOT implementation release.
        fresh = sqlite3.connect(str(self.path), timeout=0)
        try:
            fresh.execute("BEGIN IMMEDIATE")
            self.assertTrue(fresh.in_transaction)
            self.assertEqual(fresh.execute("SELECT COUNT(*) FROM conversations").fetchone()[0], 0)
        finally:
            fresh.rollback()
            fresh.close()
        self.assertEqual(proxy.native_close_count, 0)

    def test_07_pass_quarantine_secondary_keyboard_retains_lock_until_cleanup(self):
        self.exercise_quarantine_lock(KeyboardInterrupt("G82_SECONDARY_CLOSE"))

    def test_08_pass_quarantine_secondary_exit_retains_lock_until_cleanup(self):
        self.exercise_quarantine_lock(SystemExit("G82_SECONDARY_CLOSE"))


if __name__ == "__main__":
    unittest.main()
