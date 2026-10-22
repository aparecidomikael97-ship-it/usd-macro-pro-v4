"""A172 LAB: narrower directory-rename fingerprint versus valid WAL writes.

All filesystem effects are inside a temporary directory. The guard measures
path metadata, not SQLite VFS atomicity or trusted external witness.
"""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from aion_chat.models import Page, Scope
from aion_chat.staged_store import OperationScopedSQLiteChatStore
from aion_chat.store import FAILED, HEALTHY, SQLiteChatStore, StorageUnavailableError


class NarrowRenameFingerprintTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.scope = Scope("owner", "tenant", "workspace")

    def facade(self):
        handle = OperationScopedSQLiteChatStore(self.root / "main.sqlite3")
        self.addCleanup(handle.close)
        return handle

    def test_01_unrelated_directory_entry_can_false_positive(self):
        handle = self.facade()
        created = self.root / "unrelated.txt"
        Native = SQLiteChatStore

        class Intercept(Native):
            def list_conversations(self, *args, **kwargs):
                created.write_text("unrelated", encoding="utf-8")
                return Page(items=[])

        error = None
        with patch("aion_chat.staged_store.SQLiteChatStore", Intercept):
            try:
                handle.list_conversations(self.scope)
            except StorageUnavailableError as exc:
                error = exc
        self.assertTrue(created.is_file())
        if error is not None:
            self.assertIn("BOUND_DATABASE_READ_SNAPSHOT_CHANGED", str(error))
            self.assertEqual(handle.storage_health()["state"], FAILED)
            print("A172_UNRELATED_FILE=READ_DENIED_DIRECTORY_FALSE_POSITIVE")
        else:
            self.assertEqual(handle.storage_health()["state"], HEALTHY)
            print("A172_UNRELATED_FILE=TIMESTAMP_DRIFT_NOT_OBSERVED")

    def test_02_existing_unrelated_file_content_change_does_not_rename(self):
        unrelated = self.root / "existing.txt"
        unrelated.write_text("before", encoding="utf-8")
        handle = self.facade()
        Native = SQLiteChatStore

        class Intercept(Native):
            def list_conversations(self, *args, **kwargs):
                unrelated.write_text("after", encoding="utf-8")
                return Page(items=[])

        with patch("aion_chat.staged_store.SQLiteChatStore", Intercept):
            result = handle.list_conversations(self.scope)
        self.assertEqual(result.items, [])
        self.assertEqual(unrelated.read_text(encoding="utf-8"), "after")
        self.assertEqual(handle.storage_health()["state"], HEALTHY)
        print("A172_UNRELATED_CONTENT=READ_ALLOWED")

    def test_03_fingerprint_does_not_include_wal_sidecar_timestamps(self):
        handle = self.facade()
        fd = handle._open_identity_anchor(
            handle._path_identity(allow_missing=False))
        try:
            before = handle._read_snapshot(fd)
            self.assertEqual(len(before), 2)
            self.assertEqual(len(before[0]), 2)
            self.assertEqual(len(before[1]), 4)
        finally:
            import os
            os.close(fd)

    def test_04_injected_rename_fingerprint_drift_still_latches(self):
        handle = self.facade()
        with patch.object(handle, "_read_snapshot",
                          side_effect=[("stable",), ("changed",)]):
            with self.assertRaisesRegex(
                    StorageUnavailableError,
                    "BOUND_DATABASE_READ_SNAPSHOT_CHANGED"):
                handle.list_conversations(self.scope)
        self.assertEqual(handle.storage_health()["state"], FAILED)


if __name__ == "__main__":
    unittest.main()
