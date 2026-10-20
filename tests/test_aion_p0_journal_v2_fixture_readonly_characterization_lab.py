"""Synthetic disposable SQLite fixture for the two 12-Oct Journal.db() errors.

NO importing or changing original Journal source (not in current GitHub tree).
Shows semantics of a read-only SQLite API and a TEST-ONLY separate raw
sqlite3.connect() mutation used to characterize tampering. Passing tests
does NOT mean the production API, legacy 76, or antirollback is fixed.
"""
from __future__ import annotations

from contextlib import closing
from hashlib import sha256
from pathlib import Path
import sqlite3
import tempfile
import unittest


class SyntheticJournalV2FixtureLAB(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix="aion_p0_journal_lab_")
        self.path=Path(self.tmp.name)/"fixture.sqlite3"
        with sqlite3.connect(self.path) as con:
            con.execute("CREATE TABLE journal (id INTEGER PRIMARY KEY, content TEXT NOT NULL)")
            con.execute("INSERT INTO journal(id,content) VALUES (1,'original-entry')")
        self.expected=sha256(b"original-entry").hexdigest()

    def tearDown(self):
        self.tmp.cleanup()

    def public_readonly_view(self):
        # REFERENCE ONLY: NOT a call to production Journal.db().
        return sqlite3.connect(self.path.as_uri()+"?mode=ro",uri=True)

    def fixture_raw_writer(self):
        # Explicitly confined to TemporaryDirectory. Never production path.
        return sqlite3.connect(self.path)

    def read(self,connection):
        return connection.execute("SELECT content FROM journal WHERE id=1").fetchone()[0]

    def simulated_integrity(self):
        with closing(self.public_readonly_view()) as con:
            data=self.read(con)
        return sha256(data.encode("utf-8")).hexdigest()==self.expected

    def test_01_synthetic_public_readonly_can_read(self):
        with closing(self.public_readonly_view()) as con:
            self.assertEqual(self.read(con),"original-entry")

    def test_02_synthetic_public_readonly_rejects_update(self):
        with closing(self.public_readonly_view()) as con:
            with self.assertRaises(sqlite3.OperationalError):
                con.execute("UPDATE journal SET content='forged' WHERE id=1")
        self.assertTrue(self.simulated_integrity())

    def test_03_synthetic_public_readonly_rejects_insert(self):
        with closing(self.public_readonly_view()) as con:
            with self.assertRaises(sqlite3.OperationalError):
                con.execute("INSERT INTO journal(id,content) VALUES(2,'x')")

    def test_04_synthetic_public_readonly_rejects_delete(self):
        with closing(self.public_readonly_view()) as con:
            with self.assertRaises(sqlite3.OperationalError):
                con.execute("DELETE FROM journal WHERE id=1")

    def test_05_test_only_raw_connection_can_intentionally_corrupt(self):
        with closing(self.fixture_raw_writer()) as con, con:
            con.execute("UPDATE journal SET content='forged-entry' WHERE id=1")
        self.assertFalse(self.simulated_integrity())

    def test_06_corrupt_content_does_not_change_test_only_expected_hash(self):
        before=self.expected
        with closing(self.fixture_raw_writer()) as con, con:
            con.execute("UPDATE journal SET content='forged-entry' WHERE id=1")
        self.assertEqual(self.expected,before)
        self.assertFalse(self.simulated_integrity())

    def test_07_migration_does_not_make_public_view_writable(self):
        with closing(self.fixture_raw_writer()) as con, con:
            con.execute("UPDATE journal SET content='attacker' WHERE id=1")
        with closing(self.public_readonly_view()) as con:
            self.assertEqual(self.read(con),"attacker")
            with self.assertRaises(sqlite3.OperationalError):
                con.execute("UPDATE journal SET content='second' WHERE id=1")

    def test_08_rollback_in_test_fixture_does_not_commit_corruption(self):
        con=self.fixture_raw_writer()
        try:
            con.execute("BEGIN IMMEDIATE")
            con.execute("UPDATE journal SET content='forged' WHERE id=1")
            con.rollback()
        finally:
            con.close()
        self.assertTrue(self.simulated_integrity())

    def test_09_explicit_commit_of_test_corruption_is_visible_to_new_read_handle(self):
        with closing(self.fixture_raw_writer()) as con, con:
            con.execute("UPDATE journal SET content='bad' WHERE id=1")
        with closing(self.public_readonly_view()) as con:
            self.assertEqual(self.read(con),"bad")
        self.assertFalse(self.simulated_integrity())

    def test_10_public_view_cannot_create_nonexistent_db(self):
        missing=Path(self.tmp.name)/"missing.sqlite3"
        with self.assertRaises(sqlite3.OperationalError):
            sqlite3.connect(missing.as_uri()+"?mode=ro",uri=True)
        self.assertFalse(missing.exists())

    def test_11_db_replacement_can_defeat_local_expectation_and_is_not_external_proof(self):
        with closing(self.fixture_raw_writer()) as con, con:
            con.execute("UPDATE journal SET content='attacker' WHERE id=1")
        # This test deliberately illustrates detectable tampering under a
        # preserved expected hash, NOT durable external witness authenticity.
        self.assertFalse(self.simulated_integrity())
        self.assertEqual(self.expected,sha256(b"original-entry").hexdigest())

    def test_12_original_fixture_no_remote_or_production_effect(self):
        self.assertTrue(self.path.is_relative_to(Path(self.tmp.name)))
        self.assertTrue(self.simulated_integrity())


if __name__=="__main__":
    unittest.main()
