"""G84 RED-first: direct SQLite constructor interrupts must quarantine locally.

Continuation of G83 at db0904c2cd732ea19b72a929e3a08bef2baee209.
All data and exceptions synthetic. No provider SEND, Worker, merge, deploy
or H0 external custody claim. Logical detach cannot force native lock release.
"""
from pathlib import Path
import sqlite3
import tempfile
import unittest

from aion_chat.models import Scope
from aion_chat.store import FAILED, SQLiteChatStore, StorageUnavailableError
from labs.a190.test_g83_constructor_cleanup_interruption_lab import StartupFaultProxy


SCOPE = Scope("g84-owner", "g84-tenant", "g84-workspace")


class G84DirectConstructorInterrupt(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="aion-g84-direct-startup-")
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "chat.sqlite3"

    def capture(self, callback):
        try:
            callback()
        except BaseException as error:
            return error
        return None

    def writer_available(self):
        fresh = sqlite3.connect(str(self.path), timeout=0)
        try:
            fresh.execute("BEGIN IMMEDIATE")
            self.assertTrue(fresh.in_transaction)
        finally:
            fresh.close()

    def writer_locked(self):
        fresh = sqlite3.connect(str(self.path), timeout=0)
        try:
            with self.assertRaisesRegex(sqlite3.OperationalError, r"locked|busy"):
                fresh.execute("BEGIN IMMEDIATE")
            self.assertFalse(fresh.in_transaction)
        finally:
            fresh.close()

    def exercise_interrupt(self, primary, secondary, *, after, marker):
        instances, proxies = [], []

        class CapturedStore(SQLiteChatStore):
            def __new__(cls, *args, **kwargs):
                instance = super().__new__(cls)
                instances.append(instance)
                return instance

        def factory(*args, **kwargs):
            raw = sqlite3.connect(*args, **kwargs)
            proxy = StartupFaultProxy(raw, primary, secondary, after=after)
            proxies.append(proxy)

            def dispose_raw():
                # Fixture ownership ONLY; never retry a failing store close.
                if not proxy.native_closed:
                    raw.close()
                    proxy.native_closed = True
                self.writer_available()

            self.addCleanup(dispose_raw)
            return proxy

        caught = self.capture(
            lambda: CapturedStore(self.path, connection_factory=factory)
        )
        self.assertEqual(len(instances), 1)
        self.assertEqual(len(proxies), 1)
        store, proxy = instances[0], proxies[0]
        self.assertIs(caught, primary)
        self.assertEqual(proxy.schema_count, 1)
        with self.subTest(contract="close_attempted_once"):
            self.assertEqual(proxy.close_count, 1)
        with self.subTest(contract="failed_state"):
            self.assertEqual(store._health_state, FAILED)
            self.assertEqual(store.storage_health()["state"], FAILED)
        with self.subTest(contract="detached"):
            self.assertIsNone(store.db)
        with self.subTest(contract="no_rollback_or_auto_retry"):
            self.assertEqual(proxy.rollback_count, 0)
            self.assertEqual(proxy.schema_count, 1)
        with self.subTest(contract="subsequent_operation_denied"):
            before = proxy.execute_count
            blocked = self.capture(lambda: store.create_conversation(SCOPE, "never"))
            self.assertIsInstance(blocked, StorageUnavailableError)
            self.assertEqual(proxy.execute_count, before)
        if secondary is not None and not after:
            with self.subTest(contract="native_lock_remains_uncertain"):
                self.assertTrue(proxy.raw.in_transaction)
                self.writer_locked()
        else:
            with self.subTest(contract="native_closed"):
                self.assertTrue(proxy.native_closed)
                self.writer_available()
        print(marker)

    def test_01_direct_keyboard_interrupt_cleanup_succeeds(self):
        self.exercise_interrupt(
            KeyboardInterrupt("G84_PRIMARY_KI"), None,
            after=False, marker="G84_DIRECT_KI_GREEN=FAILED_AND_DETACHED"
        )

    def test_02_direct_system_exit_cleanup_succeeds(self):
        self.exercise_interrupt(
            SystemExit("G84_PRIMARY_EXIT"), None,
            after=False, marker="G84_DIRECT_EXIT_GREEN=FAILED_AND_DETACHED"
        )

    def test_03_primary_keyboard_interrupt_secondary_close_interrupt(self):
        self.exercise_interrupt(
            KeyboardInterrupt("G84_PRIMARY_KI"),
            KeyboardInterrupt("G84_SECONDARY_CLOSE_KI"),
            after=False, marker="G84_SECONDARY_BEFORE_GREEN=PRIMARY_PRESERVED_LOCK_UNCERTAIN"
        )

    def test_04_primary_system_exit_secondary_after_native_close(self):
        self.exercise_interrupt(
            SystemExit("G84_PRIMARY_EXIT"),
            SystemExit("G84_SECONDARY_AFTER_CLOSE_EXIT"),
            after=True, marker="G84_SECONDARY_AFTER_GREEN=PRIMARY_PRESERVED_NATIVE_CLOSED"
        )

    def exercise_factory_interrupt(self, primary, marker):
        instances, calls = [], []

        class CapturedStore(SQLiteChatStore):
            def __new__(cls, *args, **kwargs):
                instance = super().__new__(cls)
                instances.append(instance)
                return instance

        def factory(*args, **kwargs):
            calls.append((args, kwargs))
            raise primary

        caught = self.capture(
            lambda: CapturedStore(self.path, connection_factory=factory)
        )
        self.assertIs(caught, primary)
        self.assertEqual(len(instances), 1)
        self.assertEqual(len(calls), 1)
        store = instances[0]
        self.assertEqual(store._health_state, FAILED)
        self.assertEqual(store.storage_health()["state"], FAILED)
        self.assertIsNone(store.db)
        denied = self.capture(lambda: store.create_conversation(SCOPE, "never"))
        self.assertIsInstance(denied, StorageUnavailableError)
        self.writer_available()
        print(marker)

    def test_05_factory_keyboard_interrupt_no_handle_is_failed(self):
        self.exercise_factory_interrupt(
            KeyboardInterrupt("G84_FACTORY_KI"),
            "G84_FACTORY_KI_GREEN=FAILED_NO_RETRY"
        )

    def test_06_factory_system_exit_no_handle_is_failed(self):
        self.exercise_factory_interrupt(
            SystemExit("G84_FACTORY_EXIT"),
            "G84_FACTORY_EXIT_GREEN=FAILED_NO_RETRY"
        )


if __name__ == "__main__":
    unittest.main()
