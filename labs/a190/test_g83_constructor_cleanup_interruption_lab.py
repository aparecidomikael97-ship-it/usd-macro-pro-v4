"""G83 tests-first constructor cleanup interruption specification.

Pinned G82 baseline: e384301e95e0231b352a72acfba713ac911e7c49.
Not executed by Codex: connected host must establish true RED outside the
Windows sandbox. Temporary SQLite and retained synthetic exceptions only.
P0=0/6 HARD NO-GO. No network, provider, Worker, deployment or custody claims.
Logical detachment cannot guarantee physical release after synthetic close
failure. Never retry proxy close or roll back the uncertain raw connection.
"""
from pathlib import Path
import sqlite3
import tempfile
import unittest

from aion_chat.models import Scope
from aion_chat.store import FAILED, HEALTHY, SQLiteChatStore, StorageUnavailableError


SCOPE = Scope("g83-owner", "g83-tenant", "g83-workspace")


class StartupFaultProxy:
    def __init__(self, raw, primary, secondary, *, after):
        self.raw = raw
        self.primary = primary
        self.secondary = secondary
        self.after = after
        self.schema_count = 0
        self.execute_count = 0
        self.rollback_count = 0
        self.close_count = 0
        self.native_closed = False
        self.pending_at_close = None

    @property
    def row_factory(self):
        return self.raw.row_factory

    @row_factory.setter
    def row_factory(self, value):
        self.raw.row_factory = value

    def executescript(self, script):
        self.raw.executescript(script)
        self.schema_count += 1
        # Real schema is committed; this real writer lock survives a pre-close
        # synthetic interruption because the fixture retains the native handle.
        self.raw.execute("BEGIN IMMEDIATE")
        raise self.primary

    def execute(self, *args, **kwargs):
        self.execute_count += 1
        return self.raw.execute(*args, **kwargs)

    def rollback(self):
        self.rollback_count += 1
        return self.raw.rollback()

    def close(self):
        self.close_count += 1
        self.pending_at_close = self.raw.in_transaction
        if self.secondary is not None and not self.after:
            raise self.secondary
        self.raw.close()
        self.native_closed = True
        if self.secondary is not None:
            raise self.secondary

    def __getattr__(self, name):
        return getattr(self.raw, name)


class G83ConstructorCleanupInterruption(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="aion-g83-constructor-")
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / "chat.sqlite3"

    @staticmethod
    def capture(operation):
        # In particular, KeyboardInterrupt must become an assertion failure,
        # never an uncaught interruption of unittest or its subtest machinery.
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
            fresh.close()

    def assert_writer_blocked(self):
        fresh = sqlite3.connect(str(self.path), timeout=0)
        try:
            with self.assertRaises(sqlite3.OperationalError) as caught:
                fresh.execute("BEGIN IMMEDIATE")
            self.assertRegex(str(caught.exception).lower(), r"busy|locked")
            self.assertFalse(fresh.in_transaction)
        finally:
            fresh.close()

    def exercise_startup_failure(self, secondary, *, after):
        primary = OSError("G83_RETAINED_STARTUP_FAILURE_AFTER_REAL_BEGIN")
        instances = []
        proxies = []

        class CapturedStore(SQLiteChatStore):
            def __new__(cls, *args, **kwargs):
                instance = super().__new__(cls)
                instances.append(instance)
                return instance

        def factory(*args, **kwargs):
            raw = sqlite3.connect(*args, **kwargs)
            # Registered before injection, so RED assertions cannot leak locks.
            def cleanup_raw():
                if not proxy.native_closed:
                    # Fixture ownership only; bypass the fault proxy once.
                    raw.close()
                    proxy.native_closed = True
                self.assert_writer_available()

            self.addCleanup(cleanup_raw)
            proxy = StartupFaultProxy(raw, primary, secondary, after=after)
            proxies.append(proxy)
            return proxy

        caught = self.capture(
            lambda: CapturedStore(self.path, connection_factory=factory)
        )
        self.assertEqual(len(instances), 1)
        self.assertEqual(len(proxies), 1)
        store, proxy = instances[0], proxies[0]
        self.assertIs(proxy.primary, primary)
        self.assertIs(proxy.secondary, secondary)
        self.assertEqual(proxy.schema_count, 1)
        self.assertEqual(proxy.close_count, 1)
        self.assertTrue(proxy.pending_at_close)
        # Probe before logical assertions: pre-close must retain the real lock,
        # after-close and ordinary cleanup must already allow a fresh writer.
        if secondary is not None and not after:
            self.assertTrue(proxy.raw.in_transaction)
            self.assert_writer_blocked()
        else:
            self.assert_writer_available()
            with self.assertRaises(sqlite3.ProgrammingError):
                proxy.raw.execute("SELECT 1")

        with self.subTest(contract="startup_error_preserved"):
            self.assertIsInstance(caught, StorageUnavailableError)
        with self.subTest(contract="original_cause_identity"):
            self.assertIs(getattr(caught, "__cause__", None), primary)
        with self.subTest(contract="secondary_not_propagated"):
            self.assertIsNot(caught, secondary)
            self.assertIsNot(caught, primary)
        with self.subTest(contract="detached"):
            self.assertIsNone(store.db)
        with self.subTest(contract="failed_state"):
            self.assertEqual(store._health_state, FAILED)
        with self.subTest(contract="failed_health"):
            self.assertEqual(store.storage_health()["state"], FAILED)
        with self.subTest(contract="no_writer_reuse"):
            before = proxy.execute_count
            denied = self.capture(lambda: store.create_conversation(SCOPE, "denied"))
            self.assertIsInstance(denied, StorageUnavailableError)
            self.assertEqual(proxy.execute_count, before)
        with self.subTest(contract="no_cleanup_retry_or_rollback"):
            self.assertEqual(proxy.close_count, 1)
            self.assertEqual(proxy.rollback_count, 0)
        if secondary is not None and not after:
            self.assert_writer_blocked()
        # No store.close(), repeated proxy.close(), or uncertain raw rollback.
        # addCleanup closes the retained native handle, then proves lock release.

    def test_keyboard_interrupt_before_native_close(self):
        self.exercise_startup_failure(KeyboardInterrupt("G83_BEFORE_KI"), after=False)

    def test_system_exit_before_native_close(self):
        self.exercise_startup_failure(SystemExit("G83_BEFORE_EXIT"), after=False)

    def test_keyboard_interrupt_after_native_close(self):
        self.exercise_startup_failure(KeyboardInterrupt("G83_AFTER_KI"), after=True)

    def test_system_exit_after_native_close(self):
        self.exercise_startup_failure(SystemExit("G83_AFTER_EXIT"), after=True)

    def test_startup_error_with_successful_cleanup_control(self):
        self.exercise_startup_failure(None, after=False)

    def test_successful_constructor_control(self):
        store = SQLiteChatStore(self.path)
        self.addCleanup(store.close)
        self.assertEqual(store.storage_health(deep=True)["state"], HEALTHY)
        created = store.create_conversation(SCOPE, "g83-success-control")
        self.assertIsNotNone(created.id)
        self.assert_writer_available()


if __name__ == "__main__":
    unittest.main()
