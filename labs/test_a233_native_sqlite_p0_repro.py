"""A233: adversarial experiments on real, disposable SQLite files."""
import dataclasses
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from labs.a233_native_sqlite_p0_repro import (
    probe_same_inode_restore, probe_wal_backup_comparison, probe_commit_ack_lost,
)


class A233NativeSQLiteP0Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rollback = probe_same_inode_restore()
        cls.wal = probe_wal_backup_comparison()
        cls.ack = probe_commit_ack_lost()

    def test_01_real_same_inode_retrograde_read(self):
        self.assertEqual(
            (self.rollback.original, self.rollback.updated, self.rollback.after_restore),
            (1, 2, 1),
        )

    def test_02_original_path_still_exists_after_rollback(self):
        self.assertTrue(self.rollback.path_unchanged)

    def test_03_same_inode_restoration_observed(self):
        self.assertTrue(self.rollback.inode_unchanged)

    def test_04_old_hash_reappears_after_restore(self):
        self.assertTrue(self.rollback.restored_sha_matches_old_bytes)

    def test_05_p0_5_still_open(self):
        self.assertFalse(self.rollback.native_read_identity_proven)
        self.assertFalse(self.rollback.p0_5_homologated)

    def test_06_live_wal_source_has_two_committed_rows(self):
        self.assertEqual(self.wal.live_count, 2)

    def test_07_raw_main_file_copy_is_stale(self):
        self.assertEqual(self.wal.main_only_copy_count, 1)
        self.assertLess(self.wal.main_only_copy_count, self.wal.live_count)

    def test_08_sqlite_backup_api_captures_wal_committed_rows(self):
        self.assertEqual(self.wal.sqlite_backup_count, 2)
        self.assertEqual(self.wal.sqlite_backup_count, self.wal.live_count)

    def test_09_wal_sidecar_existed_while_copy_taken(self):
        self.assertTrue(self.wal.wal_sidecar_present)

    def test_10_consistent_backup_does_not_homologate_p0_6(self):
        self.assertFalse(self.wal.native_write_identity_proven)
        self.assertFalse(self.wal.p0_6_homologated)

    def test_11_real_sqlite_commit_survives_lost_application_ack(self):
        self.assertEqual(self.ack.persisted_rows, 1)

    def test_12_lost_ack_blocks_auto_retry(self):
        self.assertEqual(self.ack.reported_state, "UNCERTAIN")
        self.assertFalse(self.ack.can_auto_retry)

    def test_13_db_commit_does_not_prove_external_provider_effect(self):
        self.assertFalse(self.ack.external_effect_verified)
        self.assertFalse(self.ack.p0_6_homologated)

    def test_14_observations_are_immutable(self):
        for result in (self.rollback, self.wal, self.ack):
            with self.assertRaises(dataclasses.FrozenInstanceError):
                result.p0_6_homologated = True

    def test_15_real_staged_store_backup_uses_sqlite_backup_api(self):
        # Exercise existing staging code, not merely the new lab helper.
        with TemporaryDirectory(prefix="a233-staged-") as root:
            live = Path(root) / "chat.db"
            target = Path(root) / "backup.db"
            store = SQLiteChatStore(live)
            try:
                scope = Scope("owner-lab", "tenant-lab", "workspace-lab")
                store.create_conversation(scope, "A233 TEST ONLY")
                report = store.backup_to(target)
                self.assertEqual(report["state"], "BACKUP_VERIFIED")
                with sqlite3.connect(str(target)) as target_db:
                    self.assertEqual(
                        target_db.execute("SELECT COUNT(*) FROM conversations").fetchone()[0],
                        1,
                    )
            finally:
                store.close()


if __name__ == "__main__":
    unittest.main()
