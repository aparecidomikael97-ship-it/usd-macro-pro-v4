"""G109 RED-first: SQLite lookup failures after reservation must deny cleanly.

The G107 guard verifies a local first-attempt record after signed postproof.
sqlite3.OperationalError/DatabaseError can occur at that final read (missing
table, corruption, lock, malformed storage); G107 catches other exceptions
but not sqlite3.Error. The in-process Outbox has an additional catch-all;
these LAB tests require the guard itself to return literal False so callers
cannot accidentally promote exceptions into an authorization.

Only synthetic keys, SQLite fixtures and in-memory adapters. No provider SEND.
"""
import sqlite3
import unittest

from aion_chat.separate_custody_a181_lab import CustodyUnavailable
from labs.a190.g107_local_reservation_lookup import lookup_stored_reservation
from labs.a190.test_g102_pinned_external_attestation_admission_lab import (
    G102PinnedExternalAdmission,
)


class G109FinalRecordLookupFaults(G102PinnedExternalAdmission):
    def _raise_at_lookup(self, error):
        def deny(_effect):
            raise error
        return deny

    def test_11_real_sqlite_missing_table_normalizes_unavailable(self):
        class MissingTable:
            @staticmethod
            def _connect():
                return sqlite3.connect(":memory:")

        with self.assertRaises(CustodyUnavailable):
            lookup_stored_reservation(MissingTable(), "a" * 64)
        print("G109_SQLITE_MISSING_TABLE=NORMALIZED_DENY")

    def test_12_operational_error_after_commit_returns_literal_false(self):
        original = self.enroll_fixture()
        guard = self.make_guard(
            original,
            reservation_lookup=self._raise_at_lookup(
                sqlite3.OperationalError("G109_SYNTHETIC_SQLITE_BUSY")
            ),
        )
        self.assertIs(guard(original), False)
        self.assertEqual(self.custody.snapshot()["count"], 1)
        self.assertEqual(self.remote_sequence["count"], 1)
        print("G109_SQLITE_OPERATIONAL_AFTER_COMMIT=LITERAL_FALSE")

    def test_13_corrupt_database_error_after_commit_returns_false(self):
        original = self.enroll_fixture()
        guard = self.make_guard(
            original,
            reservation_lookup=self._raise_at_lookup(
                sqlite3.DatabaseError("G109_SYNTHETIC_DATABASE_CORRUPTION")
            ),
        )
        self.assertIs(guard(original), False)
        self.assertEqual(self.custody.snapshot()["count"], 1)
        print("G109_CORRUPT_SQLITE_AFTER_COMMIT=LITERAL_FALSE")

    def test_14_sqlite_programming_error_after_commit_returns_false(self):
        original = self.enroll_fixture()
        guard = self.make_guard(
            original,
            reservation_lookup=self._raise_at_lookup(
                sqlite3.ProgrammingError("G109_SYNTHETIC_CLOSED_CONNECTION")
            ),
        )
        self.assertIs(guard(original), False)
        self.assertEqual(self.custody.snapshot()["count"], 1)
        print("G109_CLOSED_SQLITE_AFTER_COMMIT=LITERAL_FALSE")

    def test_15_outbox_uncertain_and_zero_send_when_lookup_fails(self):
        original = self.enroll_fixture()
        guard = self.make_guard(
            original,
            reservation_lookup=self._raise_at_lookup(
                sqlite3.OperationalError("G109_SYNTHETIC_UNREADABLE_RECORD")
            ),
        )
        store, outbox, row = self.host(guard=guard)
        try:
            result, adapter = self.claim_and_send(outbox, row)
            self.assertEqual(result["state"], "UNCERTAIN")
            self.assertEqual(adapter.send_calls, 0)
            self.assertEqual(self.custody.snapshot()["count"], 1)
            self.assertEqual(self.remote_sequence["count"], 1)
        finally:
            store.close()
        print("G109_OUTBOX_UNCERTAIN_AFTER_SQL_FAULT=ZERO_SEND")

    def test_16_normal_verified_record_remains_eligible(self):
        original = self.enroll_fixture()
        guard = self.make_guard(original)
        self.assertIs(guard(original), True)
        self.assertEqual(self.custody.snapshot()["count"], 1)
        print("G109_ORIGINAL_RECORD=PASS_SYNTHETIC_ONLY")


if __name__ == "__main__":
    unittest.main()
