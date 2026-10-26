"""G94 RED-first: durable execution kernel must close every native SQLite handle.

The sqlite3.Connection context manager commits/rolls back but DOES NOT close.
Use real temporary SQLite plus a tracking proxy to prove native close exactly
once on constructor, success and error paths. Fixture-owned raw handles are
always released before Windows temp directory deletion, even while RED.
No Worker, providers, external SEND, credential use or P0 homologation.
"""
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from atlasquant_aion_durable_execution_kernel import (
    DurableExecutionError, DurableExecutionStore,
)


class NativeConnectionProbe:
    def __init__(self, raw, *, fail_query=False):
        self.raw = raw
        self.closed = 0
        self.entered = 0
        self.exited = 0
        self.fail_query = fail_query

    def __enter__(self):
        self.entered += 1
        self.raw.__enter__()
        return self

    def __exit__(self, *details):
        self.exited += 1
        return self.raw.__exit__(*details)

    def execute(self, sql, *args, **kwargs):
        if self.fail_query and "SELECT * FROM executions WHERE execution_id" in sql:
            raise sqlite3.OperationalError("G94_SYNTHETIC_QUERY_DENIED")
        return self.raw.execute(sql, *args, **kwargs)

    def close(self):
        self.closed += 1
        return self.raw.close()

    def __getattr__(self, name):
        return getattr(self.raw, name)


class G94DurableNativeClose(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="aion-g94-explicit-close-")
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "execution.sqlite3"
        self.original_connect = DurableExecutionStore._connect
        self.probes = []

    def tracked(self, *, fail_query=False):
        def connect(store):
            raw = self.original_connect(store)
            self.addCleanup(raw.close)
            proxy = NativeConnectionProbe(raw, fail_query=fail_query)
            self.probes.append(proxy)
            return proxy
        return connect

    def assert_all_native_closed(self):
        self.assertTrue(self.probes)
        for i, spy in enumerate(self.probes):
            with self.subTest(connection=i, contract="transaction_exited"):
                self.assertEqual(spy.entered, 1)
                self.assertEqual(spy.exited, 1)
            with self.subTest(connection=i, contract="single_physical_close"):
                self.assertEqual(spy.closed, 1)
            with self.subTest(connection=i, contract="native_handle_released"):
                with self.assertRaises(sqlite3.ProgrammingError):
                    spy.raw.execute("SELECT 1")

    def make_store(self):
        return DurableExecutionStore(self.path)

    def test_01_constructor_transaction_closes_native_handle(self):
        with patch.object(DurableExecutionStore, "_connect", self.tracked()):
            self.make_store()
        self.assertEqual(len(self.probes), 1)
        self.assert_all_native_closed()
        print("G94_CONSTRUCTOR_GREEN=NATIVE_CLOSE_AFTER_SCHEMA_COMMIT")

    def test_02_missing_get_error_still_closes_native_handle(self):
        self.make_store()
        with patch.object(DurableExecutionStore, "_connect", self.tracked()):
            with self.assertRaises(DurableExecutionError) as caught:
                self.make_store().get("not-an-execution")
        self.assertEqual(str(caught.exception), "EXECUTION_NOT_FOUND")
        self.assert_all_native_closed()
        print("G94_GET_MISSING_GREEN=PRIMARY_ERROR_NATIVE_CLOSED")

    def test_03_idempotency_lookup_closes_native_handle(self):
        store = self.make_store()
        with patch.object(DurableExecutionStore, "_connect", self.tracked()):
            self.assertIsNone(store._find_by_idempotency("no-such-idempotency"))
        self.assert_all_native_closed()
        print("G94_IDEMPOTENCY_GREEN=NO_LINGERING_CONNECTION")

    def test_04_sqlite_query_error_rolls_back_and_closes(self):
        store = self.make_store()
        with patch.object(DurableExecutionStore, "_connect", self.tracked(fail_query=True)):
            with self.assertRaisesRegex(sqlite3.OperationalError, "G94_SYNTHETIC_QUERY_DENIED"):
                store.get("not-an-execution")
        self.assert_all_native_closed()
        print("G94_SQLITE_ERROR_GREEN=TRANSACTION_EXIT_AND_NATIVE_CLOSE")

    def test_05_prepare_and_read_use_no_orphan_handles(self):
        store = self.make_store()
        with patch.object(DurableExecutionStore, "_connect", self.tracked()):
            prepared = store.prepare(
                task_id="g94-task",
                step_id="g94-step",
                idempotency_key="g94-idempotency",
                effect_key="g94-effect",
                payload_digest="sha256:" + "a" * 64,
                mode="LOCAL_SAFE",
                now_ts="2026-10-26T08:00:00Z",
                deadline_at="2026-10-26T09:00:00Z",
            )
        self.assertIsNotNone(prepared)
        self.assertGreaterEqual(len(self.probes), 2)
        self.assert_all_native_closed()
        print("G94_PREPARE_GREEN=TRANSACTIONS_COMMIT_AND_CLOSE")


if __name__ == "__main__":
    unittest.main()
