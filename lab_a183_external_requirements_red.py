"""A183 external/native acceptance requirements deliberately RED, no masking."""
from pathlib import Path
import tempfile
import unittest
from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore, StorageUnavailableError
from aion_chat.staged_store import OperationScopedSQLiteChatStore
import lab_a182_external_requirements_red as a182

class ExternalRequirementsRed(a182.ExternalRequirementsRed):
    pass

class LiveNativeRollbackRequirementsRed(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/"live.db"
        self.scope=Scope("owner","tenant","workspace")
        store=SQLiteChatStore(self.path)
        store.create_conversation(self.scope,title="before")
        store.close()
        self.old=self.path.read_bytes()
        self.handle=OperationScopedSQLiteChatStore(self.path)
        self.addCleanup(self.handle.close)
        self.handle.create_conversation(self.scope,title="after")
        self.assertEqual(len(self.handle.list_conversations(self.scope).items),2)
        inode=self.path.stat().st_ino
        self.path.write_bytes(self.old)
        self.assertEqual(self.path.stat().st_ino,inode)

    def test_live_restore_same_inode_must_be_attested_before_read(self):
        with self.assertRaises(StorageUnavailableError,
                msg="UNMET: authenticated live snapshot/version and native VFS identity"):
            self.handle.list_conversations(self.scope)

    def test_live_restore_same_inode_must_not_reopen_write_authority(self):
        with self.assertRaises(StorageUnavailableError,
                msg="UNMET: rollback-proof native write boundary"):
            self.handle.create_conversation(self.scope,title="reopened-after-rollback")

if __name__=="__main__":unittest.main(verbosity=2)

