"""G132: real SQLite WAL joint-rollback counterexample. LAB ONLY; never SEND."""
import json
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path


def make_store(root):
    db = root / "operations.sqlite3"
    witness = root / "local_witness.json"
    with sqlite3.connect(db) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("CREATE TABLE reservations (seq INTEGER PRIMARY KEY, original_event TEXT UNIQUE NOT NULL, request_id TEXT NOT NULL)")
    witness.write_text(json.dumps({"epoch": 0}), encoding="utf-8")
    return db, witness


def reserve(db, witness, original_event, request_id):
    """Deliberately insufficient app-managed local gate: NO external identity/authority."""
    if not witness.exists():
        return "DENIED_MISSING_WITNESS"
    try:
        epoch = json.loads(witness.read_text(encoding="utf-8"))["epoch"]
        if type(epoch) is not int or epoch < 0:
            return "DENIED_INVALID_WITNESS"
    except (ValueError, OSError, KeyError, TypeError):
        return "DENIED_INVALID_WITNESS"
    with sqlite3.connect(db) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        db_epoch = conn.execute("SELECT COUNT(*) FROM reservations").fetchone()[0]
        if db_epoch != epoch:
            return "DENIED_EPOCH_MISMATCH"
        if conn.execute("SELECT 1 FROM reservations WHERE original_event=?", (original_event,)).fetchone():
            return "UNCERTAIN_NO_AUTO_RESEND"
        conn.execute("INSERT INTO reservations(seq, original_event, request_id) VALUES(?,?,?)",
                     (epoch + 1, original_event, request_id))
    # This local file can be replaced along with the database; not independent custody.
    temp = witness.with_suffix(".tmp")
    temp.write_text(json.dumps({"epoch": epoch + 1}), encoding="utf-8")
    temp.replace(witness)
    return "LOCAL_RESERVATION_ONLY_NOT_AUTHORITY"


def snapshot(db, witness, directory):
    directory.mkdir()
    copydb = directory / "snapshot.sqlite3"
    with sqlite3.connect(db) as conn, sqlite3.connect(copydb) as target:
        conn.backup(target)  # Includes committed WAL; unlike raw main-file copy.
    shutil.copy2(witness, directory / "witness.json")
    return copydb


def restore_db(db, copydb):
    # No open SQLite connections. Restore all native storage, including sidecars.
    for p in (db, Path(str(db) + "-wal"), Path(str(db) + "-shm")):
        p.unlink(missing_ok=True)
    shutil.copy2(copydb, db)


class G132RealSQLiteJointRollback(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.db, self.witness = make_store(self.root)
        self.snapshot_db = snapshot(self.db, self.witness, self.root / "old")
        self.effects = []  # Fake effects live outside app rollback; no provider call.

    def effect_once_in_lab(self, event, request):
        result = reserve(self.db, self.witness, event, request)
        if result == "LOCAL_RESERVATION_ONLY_NOT_AUTHORITY":
            self.effects.append((event, request))
        return result

    def test_01_joint_rollback_readmits_same_original_event(self):
        self.assertEqual(self.effect_once_in_lab("event-A", "r1"), "LOCAL_RESERVATION_ONLY_NOT_AUTHORITY")
        # ACK lost; attacker restores both DB and witness, not the fake external effects.
        restore_db(self.db, self.snapshot_db)
        shutil.copy2(self.root / "old" / "witness.json", self.witness)
        self.assertEqual(self.effect_once_in_lab("event-A", "r2"), "LOCAL_RESERVATION_ONLY_NOT_AUTHORITY")
        self.assertEqual(self.effects, [("event-A", "r1"), ("event-A", "r2")])
        print("G132_JOINT_DB_WITNESS_ROLLBACK=UNSAFE_READMISSION_REPRODUCED_NOT_P0")

    def test_02_database_only_rollback_is_denied_by_intact_witness(self):
        self.effect_once_in_lab("event-A", "r1")
        restore_db(self.db, self.snapshot_db)
        self.assertEqual(self.effect_once_in_lab("event-A", "r2"), "DENIED_EPOCH_MISMATCH")
        self.assertEqual(len(self.effects), 1)

    def test_03_witness_only_rollback_is_denied_by_intact_database(self):
        self.effect_once_in_lab("event-A", "r1")
        shutil.copy2(self.root / "old" / "witness.json", self.witness)
        self.assertEqual(self.effect_once_in_lab("event-A", "r2"), "DENIED_EPOCH_MISMATCH")
        self.assertEqual(len(self.effects), 1)

    def test_04_missing_witness_at_h0_fails_closed(self):
        self.witness.unlink()
        self.assertEqual(self.effect_once_in_lab("event-A", "r1"), "DENIED_MISSING_WITNESS")
        self.assertEqual(self.effects, [])
        print("G132_H0_WITNESS_MISSING=NO_EFFECT")

    def test_05_ack_lost_without_rollback_keeps_no_auto_retry(self):
        self.effect_once_in_lab("event-A", "r1")
        self.assertEqual(self.effect_once_in_lab("event-A", "r2"), "UNCERTAIN_NO_AUTO_RESEND")
        self.assertEqual(len(self.effects), 1)
        print("G132_ACK_LOSS_WITH_INTACT_STATE=UNCERTAIN_ZERO_AUTO_RESEND")

    def test_06_untrusted_new_original_event_can_duplicate_semantics(self):
        self.effect_once_in_lab("claim-A", "r1")
        self.assertEqual(self.effect_once_in_lab("claim-B", "r2"), "LOCAL_RESERVATION_ONLY_NOT_AUTHORITY")
        self.assertEqual(len(self.effects), 2)
        print("G132_SELF_CLAIMED_EVENT_ID=DOUBLE_SYNTHETIC_EFFECT_NOT_AUTHENTICATED")


if __name__ == "__main__":
    unittest.main()
