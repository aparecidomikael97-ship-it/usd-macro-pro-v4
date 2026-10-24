"""A190 G5 LAB: genuine killed subprocess after/before SQLite COMMIT.

Not a power-failure or reboot experiment. Every DB, intent, owner, marker and
effect is synthetic; no provider, IPC service or real-world side effect.
"UNKNOWN" in this harness is a parent policy assertion, not proof of external
outcome. Reopening the DB after a killed process does not authenticate custody.
"""
from __future__ import annotations

from contextlib import closing
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore


EVENT = "synthetic-original-event-e1"
PAYLOAD = "synthetic-intent-hash-only"
CHILD_SCRIPT = Path(__file__).resolve()


def _child_entry(mode: str, db: Path, barrier: Path) -> int:
    if mode == "probe":
        with closing(sqlite3.connect(db, timeout=1.0)) as connection:
            total = connection.execute("SELECT COUNT(*) FROM reservations").fetchone()[0]
        print(total, flush=True)
        return 0
    if mode == "reserve-exit":
        with closing(sqlite3.connect(db, timeout=1.0)) as connection:
            connection.execute(
                "INSERT INTO reservations(request_id,event_id,payload_hash) VALUES(?,?,?)",
                ("request-e1", EVENT, PAYLOAD),
            )
            connection.commit()
        print("A190_G5_LOCAL_RESERVATION_AFTER_RESTORE=ACCEPTED", flush=True)
        return 0
    if mode == "aion-commit-before-ack":
        store = SQLiteChatStore(db)
        store.db.execute("PRAGMA journal_mode=WAL")
        store.db.execute("PRAGMA wal_autocheckpoint=0")
        scope = Scope(
            owner_id="synthetic-owner", tenant_id="synthetic-tenant",
            workspace_id="synthetic-workspace",
        )
        store.create_conversation(scope, title="SYNTHETIC_POST_COMMIT_PRE_ACK")
        if store.db.execute("SELECT COUNT(*) FROM conversations").fetchone()[0] != 1:
            raise AssertionError("AION_COMMIT_NOT_VISIBLE")
        barrier.write_text(f"{mode}:{os.getpid()}", encoding="utf-8")
        # Parent kills this process before an outcome/ACK is returned.
        sys.stdin.buffer.read(1)
        raise AssertionError("ACK_MUST_NEVER_BE_SENT_IN_G5_KILL_LAB")
    if mode not in ("pre-commit", "post-commit"):
        raise ValueError("UNKNOWN_SYNTHETIC_WORKER_MODE")
    with closing(sqlite3.connect(db, timeout=1.0)) as connection:
        connection.execute(
            "INSERT INTO reservations(request_id,event_id,payload_hash) VALUES(?,?,?)",
            ("request-e1", EVENT, PAYLOAD),
        )
        if mode == "post-commit":
            connection.commit()
        barrier.write_text(f"{mode}:{os.getpid()}", encoding="utf-8")
        # pre-commit: uncommitted txn is still LIVE when killed.
        # post-commit: COMMIT completed but caller has received no final ACK.
        sys.stdin.buffer.read(1)
        raise AssertionError("ACK_MUST_NEVER_BE_SENT_IN_G5_KILL_LAB")


class A190G5RealProcessCrashH0LabTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="a190-g5-kill-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def _initialize_reservation_db(self, name="live.sqlite"):
        db = self.root / name
        with closing(sqlite3.connect(db, timeout=1.0)) as connection:
            self.assertEqual(
                connection.execute("PRAGMA journal_mode=WAL").fetchone()[0], "wal",
            )
            connection.execute("PRAGMA wal_autocheckpoint=0")
            connection.execute(
                "CREATE TABLE reservations("
                "request_id TEXT UNIQUE NOT NULL,"
                "event_id TEXT UNIQUE NOT NULL,"
                "payload_hash TEXT NOT NULL)"
            )
            connection.commit()
            self.assertEqual(
                connection.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()[0], 0,
            )
        return db

    @staticmethod
    def _command(mode, db, marker):
        return [
            sys.executable, "-B", str(CHILD_SCRIPT), "--worker",
            mode, str(db), str(marker),
        ]

    def _kill_at_known_barrier(self, mode, db):
        marker = self.root / ("barrier-" + mode + ".txt")
        process = subprocess.Popen(
            self._command(mode, db, marker),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.assertNotEqual(process.pid, os.getpid())
        try:
            deadline = time.monotonic() + 12
            while not marker.is_file() and time.monotonic() < deadline:
                if process.poll() is not None:
                    out, err = process.communicate(timeout=5)
                    self.fail(f"G5_CHILD_DIED_EARLY mode={mode} code={process.returncode} stdout={out} stderr={err}")
                time.sleep(0.025)
            self.assertTrue(marker.is_file(), f"G5_CHILD_BARRIER_NOT_REACHED_{mode}")
            self.assertEqual(marker.read_text(encoding="utf-8"), f"{mode}:{process.pid}")
            self.assertIsNone(process.poll(), "child must be LIVE at process-kill barrier")
            process.kill()  # ONLY the subprocess created inside this synthetic test.
            process.communicate(timeout=8)
            self.assertNotEqual(process.returncode, 0)
            return {"state": "UNCERTAIN", "auto_resend": False}
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate(timeout=8)

    def _fresh_process_count(self, db):
        result = subprocess.run(
            self._command("probe", db, self.root / "unused"),
            capture_output=True, text=True, check=True, timeout=10,
        )
        self.assertIn(result.stdout.strip(), ("0", "1", "2"))
        return int(result.stdout.strip())

    def test_real_kill_before_commit_reopens_without_uncommitted_row(self):
        db = self._initialize_reservation_db()
        outcome = self._kill_at_known_barrier("pre-commit", db)
        self.assertEqual(outcome, {"state": "UNCERTAIN", "auto_resend": False})
        self.assertEqual(self._fresh_process_count(db), 0)
        print("A190_G5_REAL_PROCESS_KILL_BEFORE_COMMIT=ROLLED_BACK_AFTER_REOPEN")
        print("A190_G5_PRECOMMIT_NO_ACK=UNCERTAIN_NO_AUTO_RESEND")

    def test_real_kill_after_commit_before_ack_reopens_with_row(self):
        db = self._initialize_reservation_db()
        outcome = self._kill_at_known_barrier("post-commit", db)
        self.assertEqual(outcome, {"state": "UNCERTAIN", "auto_resend": False})
        self.assertEqual(self._fresh_process_count(db), 1)
        print("A190_G5_REAL_PROCESS_KILL_AFTER_COMMIT=ROW_SURVIVES_REOPEN")
        print("A190_G5_POSTCOMMIT_MISSING_ACK=UNCERTAIN_NO_AUTO_RESEND")

    def test_local_snapshot_plus_wal_restore_undoes_crashed_history_red(self):
        """Host controlling all SQLite artifacts can erase committed history."""
        db = self._initialize_reservation_db()
        snapshot = self.root / "old-before-first-attempt.sqlite"
        # SQLite API creates an offline pre-commit snapshot, not a raw live copy.
        with closing(sqlite3.connect(db, timeout=1.0)) as source:
            with closing(sqlite3.connect(snapshot, timeout=1.0)) as target:
                source.backup(target)
                target.execute("PRAGMA journal_mode=DELETE")
                target.commit()
        self.assertEqual(self._fresh_process_count(db), 0)
        self._kill_at_known_barrier("post-commit", db)
        self.assertEqual(self._fresh_process_count(db), 1)

        # All child and probe processes have ended. No live handles remain.
        # This attacker operation touches ONLY files created in TemporaryDirectory.
        shutil.copyfile(snapshot, db)
        for suffix in ("-wal", "-shm"):
            Path(str(db) + suffix).unlink(missing_ok=True)
        self.assertEqual(self._fresh_process_count(db), 0)

        repeated = subprocess.run(
            self._command("reserve-exit", db, self.root / "unused"),
            capture_output=True, text=True, check=True, timeout=10,
        )
        self.assertIn(
            "A190_G5_LOCAL_RESERVATION_AFTER_RESTORE=ACCEPTED", repeated.stdout,
        )
        self.assertEqual(self._fresh_process_count(db), 1)
        print("A190_G5_HOST_ROLLBACK_AFTER_REAL_PROCESS_CRASH=UNSAFE_READMISSION_RED")

    def test_crashed_attempt_different_claimed_event_bypasses_semantic_uniqueness_red(self):
        db = self._initialize_reservation_db()
        self._kill_at_known_barrier("post-commit", db)
        self.assertEqual(self._fresh_process_count(db), 1)
        with closing(sqlite3.connect(db, timeout=1.0)) as connection:
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    "INSERT INTO reservations(request_id,event_id,payload_hash) VALUES(?,?,?)",
                    ("request-other", EVENT, PAYLOAD),
                )
            connection.rollback()
            connection.execute(
                "INSERT INTO reservations(request_id,event_id,payload_hash) VALUES(?,?,?)",
                ("request-third", "attacker-relabelled-event-e2", PAYLOAD),
            )
            connection.commit()
        self.assertEqual(self._fresh_process_count(db), 2)
        print("A190_G5_REAL_CRASH_THEN_RELABELED_ID=DOUBLE_LOCAL_RESERVATION_RED")

    def test_aion_live_store_commit_survives_real_process_kill_before_ack(self):
        """Actual AION SQLiteChatStore through a real killed child + reopen."""
        db = self.root / "actual-aion-store.sqlite"
        outcome = self._kill_at_known_barrier("aion-commit-before-ack", db)
        self.assertEqual(outcome, {"state": "UNCERTAIN", "auto_resend": False})
        reopened = SQLiteChatStore(db)
        try:
            self.assertEqual(
                reopened.db.execute("SELECT COUNT(*) FROM conversations").fetchone()[0],
                1,
            )
        finally:
            reopened.close()
        print("A190_G5_AION_STORE_REAL_CHILD_KILL_AFTER_COMMIT=REOPEN_SEES_CONVERSATION")
        print("A190_G5_AION_STORE_NO_ACK=NO_PROVIDER_CONFIRMATION")

if __name__ == "__main__":
    if len(sys.argv) == 6 and sys.argv[1] == "--worker":
        raise SystemExit(_child_entry(
            sys.argv[2], Path(sys.argv[3]), Path(sys.argv[4]),
        ))
    unittest.main(verbosity=2)
