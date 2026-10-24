"""A190 G15 adversarial proof that Linux /proc fd deltas are NOT SQLite VFS proof.

Synthetic databases and owners only; no service credentials, real provider,
production DB, external writes, merge, deploy, or Worker.
"""
from contextlib import closing
from pathlib import Path
import os
import shutil
import sqlite3
import sys
import tempfile
import unittest

from labs.a190.g15_sqlite_procfd_probe_lab import LinuxProcFdHeuristic


class G15NativeFdLimitTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="aion-g15-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root / "live.sqlite3"
        self.clone = self.root / "clone.sqlite3"
        self._initialize(self.path, "source")
        shutil.copyfile(self.path, self.clone)
        with closing(sqlite3.connect(self.clone)) as db, db:
            db.execute("INSERT INTO synthetic_events(value) VALUES('clone-only')")

    @staticmethod
    def _initialize(path, role):
        with closing(sqlite3.connect(path)) as db, db:
            db.execute("PRAGMA journal_mode=DELETE")
            db.execute("CREATE TABLE synthetic_events(value TEXT NOT NULL)")
            db.execute("CREATE TABLE aion_native_marker_v1(singleton INTEGER PRIMARY KEY, marker TEXT)")
            db.execute("INSERT INTO aion_native_marker_v1 VALUES(1, ?)", ("a" * 32,))
            db.execute("INSERT INTO synthetic_events VALUES(?)", (role,))

    @staticmethod
    def _identity(path):
        info = path.stat()
        return (info.st_dev, info.st_ino)

    def test_01_no_new_descriptor_cannot_authorize(self):
        evidence = LinuxProcFdHeuristic().observe(self._identity(self.path))
        self.assertFalse(evidence.is_native_attestation)
        self.assertIn(evidence.status, ("INCONCLUSIVE_NO_NEW_FD", "UNSUPPORTED_FAIL_CLOSED"))
        print("G15_NO_NEW_FD=INCONCLUSIVE_NOT_AUTHORIZED")

    def test_02_normal_connection_yields_only_candidate_not_attestation(self):
        heuristic = LinuxProcFdHeuristic()
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM synthetic_events").fetchone()[0], 1)
            obs = heuristic.observe(self._identity(self.path))
        self.assertFalse(obs.is_native_attestation)
        if sys.platform == "linux":
            self.assertEqual(obs.status, "CANDIDATE_MATCH_NOT_ATTESTATION")
        else:
            self.assertEqual(obs.status, "UNSUPPORTED_FAIL_CLOSED")
        print("G15_TRUE_NATIVE_DB=ONLY_UNTRUSTED_CANDIDATE")

    def test_03_copied_local_marker_has_no_native_provenance(self):
        with closing(sqlite3.connect(self.path)) as source:
            live_marker = source.execute("SELECT marker FROM aion_native_marker_v1").fetchone()[0]
        with closing(sqlite3.connect(self.clone)) as copy:
            clone_marker = copy.execute("SELECT marker FROM aion_native_marker_v1").fetchone()[0]
        self.assertEqual(live_marker, clone_marker)
        self.assertNotEqual(self._identity(self.path), self._identity(self.clone))
        print("G15_SAME_LOCAL_MARKER_DIFFERENT_NATIVE_INODE=RED")

    @unittest.skipUnless(sys.platform == "linux", "Linux /proc fd probe only")
    def test_04_same_marker_same_declared_path_clone_is_detectable_as_candidate(self):
        saved = self.root / "saved.sqlite3"
        detached = self.root / "detached.sqlite3"
        heuristic = LinuxProcFdHeuristic()
        self.path.rename(saved)
        shutil.copyfile(self.clone, self.path)
        rogue = None
        try:
            rogue = sqlite3.connect(self.path)
            rows = rogue.execute("PRAGMA database_list").fetchall()
            self.assertIn("live.sqlite3", rows[0][2])
            self.path.rename(detached)
            saved.rename(self.path)
            # PRAGMA gives the same pathname, but the actual native FD points
            # to the clone inode. The heuristic notices this simple case.
            obs = heuristic.observe(self._identity(self.path))
            self.assertEqual(obs.status, "OBSERVED_FD_MISMATCH_NOT_CONNECTION_PROOF")
            self.assertEqual(
                rogue.execute("SELECT count(*) FROM synthetic_events").fetchone()[0], 2
            )
            self.assertEqual(
                sqlite3.connect(self.path).execute(
                    "SELECT count(*) FROM synthetic_events").fetchone()[0], 1
            )
            self.assertFalse(obs.is_native_attestation)
            print("G15_CLONE_NATIVE_FD=OBSERVED_MISMATCH_BUT_NO_VFS_PROOF")
        finally:
            if rogue is not None:
                rogue.close()
            if saved.exists() and not self.path.exists():
                saved.rename(self.path)

    @unittest.skipUnless(sys.platform == "linux", "Linux /proc fd probe only")
    def test_05_preopened_rogue_plus_true_decoy_fools_procfd_delta_red(self):
        saved = self.root / "original.sqlite3"
        detached = self.root / "rogue-detached.sqlite3"
        self.path.rename(saved)
        shutil.copyfile(self.clone, self.path)
        rogue = None
        try:
            rogue = sqlite3.connect(self.path)
            self.assertEqual(
                rogue.execute("SELECT count(*) FROM synthetic_events").fetchone()[0], 2
            )
            self.path.rename(detached)
            saved.rename(self.path)
            # Baseline contains the WRONG native file before the probe starts.
            # Open a decoy to the honest path AFTER the probe starts. The
            # heuristic will approve its fd, despite the real supplied SQLite
            # connection still targeting the detached wrong file.
            heuristic = LinuxProcFdHeuristic()
            with closing(sqlite3.connect(self.path)) as decoy:
                self.assertEqual(
                    decoy.execute("SELECT count(*) FROM synthetic_events").fetchone()[0], 1
                )
                obs = heuristic.observe(self._identity(self.path))
                self.assertEqual(obs.status, "CANDIDATE_MATCH_NOT_ATTESTATION")
                self.assertEqual(
                    rogue.execute("SELECT count(*) FROM synthetic_events").fetchone()[0], 2
                )
                self.assertFalse(obs.is_native_attestation)
            print("G15_PREOPENED_WRONG_NATIVE_PLUS_DECOY=FALSE_MATCH_RED")
        finally:
            if rogue is not None:
                rogue.close()
            if saved.exists() and not self.path.exists():
                saved.rename(self.path)

    @unittest.skipUnless(sys.platform == "linux", "Linux /proc fd probe only")
    def test_06_two_new_database_fds_deny_ambiguous_attribution(self):
        heuristic = LinuxProcFdHeuristic()
        with closing(sqlite3.connect(self.path)) as one:
            with closing(sqlite3.connect(self.clone)) as two:
                self.assertEqual(one.execute("SELECT count(*) FROM synthetic_events").fetchone()[0], 1)
                self.assertEqual(two.execute("SELECT count(*) FROM synthetic_events").fetchone()[0], 2)
                obs = heuristic.observe(self._identity(self.path))
        self.assertEqual(obs.status, "INCONCLUSIVE_AMBIGUOUS_FDS")
        self.assertGreaterEqual(obs.candidate_count, 2)
        self.assertFalse(obs.is_native_attestation)
        print("G15_TWO_NEW_FDS=AMBIGUOUS_NOT_AUTHORIZED")

    def test_07_no_python_stdlib_connection_native_vfs_handle_contract(self):
        # Python's public sqlite3.Connection interface exposes DB path queries,
        # but no documented sqlite3_file_control + sqlite3_file OS FD binding.
        self.assertFalse(hasattr(sqlite3.Connection, "file_control"))
        self.assertFalse(hasattr(sqlite3.Connection, "get_native_os_file_handle"))
        print("G15_PUBLIC_PYTHON_SQLITE3_NATIVE_FILE_BINDING=ABSENT")

    def test_08_observation_never_counts_as_owner_or_rollback_proof(self):
        proof = LinuxProcFdHeuristic()
        with closing(sqlite3.connect(self.path)) as db:
            db.execute("SELECT 1").fetchone()
            status = proof.observe(self._identity(self.path))
        self.assertFalse(status.is_native_attestation)
        # Read-only observation does not update synthetic business data.
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(
                db.execute("SELECT count(*) FROM synthetic_events").fetchone()[0], 1
            )
        print("G15_OBSERVATION_ONLY=NO_OWNER_NO_ROLLBACK_NO_P0_HOMOLOGATION")


if __name__ == "__main__":
    unittest.main()
