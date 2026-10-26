"""G96 RED-first: each persistent nonce SQLite connection is closed natively.

Actual SQLite files, synthetic nonce scopes. The Connection context manager
commits/rolls back, but does not close the OS native file handle. Spy tracks
the original connection and fixture cleanup closes it on RED before temp
deletion on Windows. No real owner signing, SEND, Worker or external custody.
"""
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from atlasquant_aion_nonce_registry import PersistentNonceRegistry


NOW = "2026-10-26T12:00:00Z"
EXP = "2026-10-26T12:05:00Z"
SCOPE = "g96-synthetic-scope"


class TrackedSQLite:
    def __init__(self, raw, *, deny_sql=""):
        self.raw = raw
        self.deny_sql = deny_sql
        self.entered = 0
        self.exited = 0
        self.close_calls = 0

    def __enter__(self):
        self.entered += 1
        self.raw.__enter__()
        return self

    def __exit__(self, *args):
        self.exited += 1
        return self.raw.__exit__(*args)

    def close(self):
        self.close_calls += 1
        return self.raw.close()

    def execute(self, sql, *args, **kwargs):
        if self.deny_sql and self.deny_sql in sql:
            raise sqlite3.OperationalError("G96_SYNTHETIC_SQL_READ_FAILED")
        return self.raw.execute(sql, *args, **kwargs)

    def __getattr__(self, name):
        return getattr(self.raw, name)


class G96PersistentNonceNativeClose(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="aion-g96-nonce-close-")
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "nonce.sqlite3"
        self.real_connect = PersistentNonceRegistry._connect
        self.probes = []

    def tracked(self, *, deny_sql=""):
        def connector(registry):
            raw = self.real_connect(registry)
            self.addCleanup(raw.close)
            spy = TrackedSQLite(raw, deny_sql=deny_sql)
            self.probes.append(spy)
            return spy
        return connector

    def assert_all_closed(self):
        self.assertGreaterEqual(len(self.probes), 1)
        for number, spy in enumerate(self.probes):
            with self.subTest(connection=number, contract="transaction_closed"):
                self.assertEqual(spy.entered, 1)
                self.assertEqual(spy.exited, 1)
            with self.subTest(connection=number, contract="close_once"):
                self.assertEqual(spy.close_calls, 1)
            with self.subTest(connection=number, contract="raw_fd_released"):
                with self.assertRaises(sqlite3.ProgrammingError):
                    spy.raw.execute("SELECT 1")

    def test_01_constructor_closes_after_nonce_schema(self):
        with patch.object(PersistentNonceRegistry, "_connect", self.tracked()):
            PersistentNonceRegistry(self.path)
        self.assertEqual(len(self.probes), 1)
        self.assert_all_closed()
        print("G96_NONCE_SCHEMA_GREEN=PHYSICAL_CLOSE")

    def test_02_claim_and_duplicate_denial_close_each_handle(self):
        registry = PersistentNonceRegistry(self.path)
        with patch.object(PersistentNonceRegistry, "_connect", self.tracked()):
            self.assertTrue(registry.claim(scope=SCOPE, nonce="once", expires_at=EXP, now_ts=NOW))
            self.assertFalse(registry.claim(scope=SCOPE, nonce="once", expires_at=EXP, now_ts=NOW))
        self.assertEqual(len(self.probes), 2)
        self.assert_all_closed()
        print("G96_NONCE_CLAIM_GREEN=SUCCESS_AND_REPLAY_CLOSE")

    def test_03_contains_read_count_schema_close_handles(self):
        registry = PersistentNonceRegistry(self.path)
        self.assertTrue(registry.claim(scope=SCOPE, nonce="once", expires_at=EXP, now_ts=NOW))
        with patch.object(PersistentNonceRegistry, "_connect", self.tracked()):
            self.assertTrue(registry.contains(scope=SCOPE, nonce="once"))
            row = registry.read_claim(scope=SCOPE, nonce="once")
            self.assertEqual(row["nonce"], "once")
            self.assertEqual(registry.count(), 1)
            self.assertGreaterEqual(registry.schema_version(), 1)
        self.assertEqual(len(self.probes), 4)
        self.assert_all_closed()
        print("G96_NONCE_READS_GREEN=ALL_FOUR_CLOSE")

    def test_04_sqlite_failure_propagates_and_closes_handle(self):
        registry = PersistentNonceRegistry(self.path)
        with patch.object(
            PersistentNonceRegistry, "_connect",
            self.tracked(deny_sql="SELECT 1 FROM nonce_claims"),
        ):
            with self.assertRaisesRegex(sqlite3.OperationalError, "G96_SYNTHETIC_SQL_READ_FAILED"):
                registry.contains(scope=SCOPE, nonce="invalid")
        self.assert_all_closed()
        print("G96_NONCE_SQL_ERROR_GREEN=PRIMARY_ERROR_PRESERVED_AND_CLOSED")


if __name__ == "__main__":
    unittest.main()
