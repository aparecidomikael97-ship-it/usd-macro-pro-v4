"""A145 RED-first specification: a valid SQLite snapshot can be stale.

Standalone standard-library LAB tests. These demonstrate the threat model, NOT
a production anti-rollback guarantee or a trusted external witness.
"""
import hashlib
import os
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path


def digest(rows):
    return hashlib.sha256(repr(rows).encode("utf-8")).hexdigest()


def read_state(path):
    with sqlite3.connect(path) as db:
        rows = db.execute("SELECT seq, intent FROM events ORDER BY seq").fetchall()
        integrity = db.execute("PRAGMA integrity_check").fetchone()[0]
    return rows, integrity


class RollbackThreatModelLab(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.db = root / "ledger.sqlite"
        self.old = root / "snapshot.sqlite"
        with sqlite3.connect(self.db) as db:
            db.execute("CREATE TABLE events (seq INTEGER PRIMARY KEY, intent TEXT NOT NULL UNIQUE)")
            db.execute("INSERT INTO events VALUES (1, 'intent-1')")
        shutil.copy2(self.db, self.old)

    def test_valid_old_snapshot_is_not_detected_by_sqlite_integrity(self):
        with sqlite3.connect(self.db) as db:
            db.execute("INSERT INTO events VALUES (2, 'intent-2')")
        newer, _ = read_state(self.db)
        shutil.copy2(self.old, self.db)
        restored, integrity = read_state(self.db)
        self.assertEqual(integrity, "ok")
        self.assertEqual(restored, [(1, "intent-1")])
        self.assertNotEqual(digest(restored), digest(newer))

    def test_trusted_outside_digest_would_reject_old_snapshot(self):
        with sqlite3.connect(self.db) as db:
            db.execute("INSERT INTO events VALUES (2, 'intent-2')")
        current, _ = read_state(self.db)
        expected = digest(current)  # synthetic stand-in, NOT independent authority
        shutil.copy2(self.old, self.db)
        restored, _ = read_state(self.db)
        self.assertNotEqual(digest(restored), expected)

    def test_missing_witness_must_not_be_treated_as_approval(self):
        witness = None
        self.assertFalse(witness is not None)

    def test_same_domain_witness_can_be_rolled_back_together(self):
        witness = Path(self.temp.name) / "witness.txt"
        initial, _ = read_state(self.db)
        witness.write_text(digest(initial), encoding="ascii")
        old_witness = witness.read_text(encoding="ascii")
        with sqlite3.connect(self.db) as db:
            db.execute("INSERT INTO events VALUES (2, 'intent-2')")
        witness.write_text(digest(read_state(self.db)[0]), encoding="ascii")
        shutil.copy2(self.old, self.db)
        witness.write_text(old_witness, encoding="ascii")
        self.assertEqual(witness.read_text(encoding="ascii"), digest(read_state(self.db)[0]))


if __name__ == "__main__":
    unittest.main()
