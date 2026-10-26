"""G126 adverse proof: local detection works while epoch is held, not P0.

No live provider, external custodian, native VFS handle attestation or true
rollback-proof write authority is created. Same-host re-pin and restart
remain deliberate successful bypass demonstrations.
"""
from pathlib import Path
import tempfile
import unittest

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore, StorageUnavailableError
from labs.a190.g126_local_epoch_fence_lab import G126LocalEpochFenceLab


class G126SameInodeEpochContainmentTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "g126-local.db"
        self.scope = Scope("owner", "tenant", "workspace")
        starter = SQLiteChatStore(self.path)
        try:
            starter.create_conversation(self.scope, title="before")
        finally:
            starter.close()
        self.old_bytes = self.path.read_bytes()
        self.fence = G126LocalEpochFenceLab(self.path)
        self.addCleanup(self.fence.close)
        self.fence.create_conversation(self.scope, title="after")
        self.assertEqual(len(self.fence.list_conversations(self.scope).items), 2)

    def rollback_same_inode(self):
        inode = self.path.stat().st_ino
        self.path.write_bytes(self.old_bytes)
        self.assertEqual(self.path.stat().st_ino, inode)

    def test_01_authorized_local_write_then_read_is_observed(self):
        self.assertEqual(len(self.fence.list_conversations(self.scope).items), 2)
        self.assertEqual(
            self.fence.create_conversation(self.scope, title="third").title,
            "third",
        )
        self.assertEqual(len(self.fence.list_conversations(self.scope).items), 3)
        print("G126_LOCAL_SINGLE_WRITER_EPOCH_ADOPTION=PASS_NOT_EXTERNAL")

    def test_02_same_inode_old_bytes_denied_before_read(self):
        self.rollback_same_inode()
        with self.assertRaisesRegex(
            StorageUnavailableError, "G126_LOCAL_EPOCH_DRIFT_BEFORE_OPERATION"
        ):
            self.fence.list_conversations(self.scope)
        with self.assertRaisesRegex(
            StorageUnavailableError, "G126_LOCAL_EPOCH_QUARANTINED"
        ):
            self.fence.list_conversations(self.scope)
        print("G126_SAME_INODE_ROLLBACK_LIVE_READ=LOCALLY_DENIED")

    def test_03_same_inode_old_bytes_denied_before_write(self):
        self.rollback_same_inode()
        with self.assertRaisesRegex(
            StorageUnavailableError, "G126_LOCAL_EPOCH_DRIFT_BEFORE_OPERATION"
        ):
            self.fence.create_conversation(self.scope, title="unauthorized")
        print("G126_SAME_INODE_ROLLBACK_LIVE_WRITE=LOCALLY_DENIED")

    def test_04_host_can_repin_the_local_seal_STILL_NOT_P0(self):
        self.rollback_same_inode()
        # A privileged host that owns the Python wrapper can rewrite its
        # in-memory reference just as easily as it rewrites the DB file.
        self.fence._epoch = self.fence._capture()
        self.assertEqual(len(self.fence.list_conversations(self.scope).items), 1)
        print("G126_HOST_REPINS_DB_AND_LOCAL_EPOCH=STILL_VULNERABLE_NOT_P0")

    def test_05_restart_after_rollback_redefines_local_epoch_STILL_NOT_P0(self):
        self.fence.close()
        self.rollback_same_inode()
        restarted = G126LocalEpochFenceLab(self.path)
        self.addCleanup(restarted.close)
        self.assertEqual(len(restarted.list_conversations(self.scope).items), 1)
        print("G126_RESTART_WITH_RESTORED_DB=STILL_VULNERABLE_NOT_P0")

    def test_06_sidecar_injection_denied_before_SQLite_open(self):
        Path(str(self.path) + "-wal").write_bytes(b"host-invented-sidecar")
        with self.assertRaisesRegex(
            StorageUnavailableError, "G126_LOCAL_EPOCH_DRIFT_BEFORE_OPERATION"
        ):
            self.fence.list_conversations(self.scope)
        print("G126_LOCAL_WAL_SIDECAR_TAMPER=DENIED")

if __name__ == "__main__":
    unittest.main()
