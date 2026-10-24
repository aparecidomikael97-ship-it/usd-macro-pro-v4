"""A190 G14: REAL SQLite local native marker hardening and remaining REDs.

All data live in per-test temporary directories. The new persistent marker can
detect distinct *locally initialized* databases, NOT native SQLite VFS fd
identity, clones preserving the marker, host rollback, or production authority.
"""
from contextlib import closing
from pathlib import Path
from unittest.mock import patch
import os
import shutil
import sqlite3
import tempfile
import unittest

from aion_chat.models import Scope
from aion_chat.staged_store import OperationScopedSQLiteChatStore
from aion_chat.store import FAILED, SQLiteChatStore, StorageUnavailableError


class G14NativeMarkerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="a190-g14-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root / "origin.sqlite3"
        self.scope = Scope("synthetic-owner", "synthetic-tenant", "synthetic-workspace")

    @staticmethod
    def marker(path):
        store = SQLiteChatStore(path)
        try:
            return store.db.execute(
                "SELECT marker FROM aion_native_marker_v1 WHERE singleton=1"
            ).fetchone()[0]
        finally:
            store.close()

    def facade(self):
        bound = OperationScopedSQLiteChatStore(self.path)
        self.addCleanup(bound.close)
        return bound

    def test_01_two_distinct_native_databases_have_different_markers(self):
        first = self.marker(self.path)
        second = self.marker(self.root / "unrelated.sqlite3")
        self.assertEqual(len(first), 32)
        self.assertEqual(len(second), 32)
        self.assertNotEqual(first, second)
        print("G14_DIFFERENT_NATIVE_DB_BOOTSTRAPS=DIFFERENT_LOCAL_MARKERS")

    def test_02_reopen_after_legitimate_wal_writes_keeps_marker(self):
        handle = self.facade()
        before = self.marker(self.path)
        first = handle.create_conversation(self.scope, title="one")
        self.assertIsNotNone(first)
        self.assertEqual(len(handle.list_conversations(self.scope).items), 1)
        after = self.marker(self.path)
        self.assertEqual(before, after)
        self.assertEqual(handle.storage_health()["state"], "healthy")
        print("G14_LEGIT_WAL_MUTATION=MARKER_STABLE")

    def test_03_path_same_but_changed_marker_denied_before_read(self):
        handle = self.facade()
        original = self.marker(self.path)
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute(
                "UPDATE aion_native_marker_v1 SET marker=? WHERE singleton=1",
                ("f" * 32 if original != "f" * 32 else "e" * 32,),
            )
        with self.assertRaisesRegex(StorageUnavailableError, "G14_NATIVE_MARKER_DRIFT"):
            handle.list_conversations(self.scope)
        with self.assertRaises(StorageUnavailableError):
            handle.create_conversation(self.scope)
        self.assertEqual(handle.storage_health()["state"], FAILED)
        print("G14_LOCAL_MARKER_DRIFT=READ_WRITE_FACADE_LATCHED")

    def test_04_invalid_marker_content_refuses_native_sqlite_bootstrap(self):
        self.marker(self.path)
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("UPDATE aion_native_marker_v1 SET marker='short' WHERE singleton=1")
        with self.assertRaisesRegex(StorageUnavailableError, "G14_LOCAL_NATIVE_MARKER_INVALID"):
            SQLiteChatStore(self.path)
        print("G14_INVALID_LOCAL_MARKER=FAIL_CLOSED")

    def test_05_postcommit_marker_swap_reports_uncertain_and_no_retry(self):
        handle = self.facade()

        class TamperAfterCommit(SQLiteChatStore):
            def create_conversation(self, *args, **kwargs):
                result = super().create_conversation(*args, **kwargs)
                current = self.db.execute(
                    "SELECT marker FROM aion_native_marker_v1 WHERE singleton=1"
                ).fetchone()[0]
                self.db.execute(
                    "UPDATE aion_native_marker_v1 SET marker=? WHERE singleton=1",
                    ("a" * 32 if current != "a" * 32 else "b" * 32,),
                )
                self.db.commit()
                return result

        with patch("aion_chat.staged_store.SQLiteChatStore", TamperAfterCommit):
            with self.assertRaisesRegex(
                StorageUnavailableError, "G14_NATIVE_MARKER_POST_OPERATION_OUTCOME_UNKNOWN"
            ):
                handle.create_conversation(self.scope, title="already-committed")
        with closing(sqlite3.connect(self.path)) as db, db:
            self.assertEqual(
                db.execute("SELECT count(*) FROM conversations").fetchone()[0], 1
            )
        with self.assertRaises(StorageUnavailableError):
            handle.create_conversation(self.scope, title="blind-replay")
        print("G14_AFTER_COMMIT_MARKER_DRIFT=UNCERTAIN_NO_AUTOMATIC_REPLAY")

    def test_06_real_backup_clone_preserves_marker_not_antirollback(self):
        handle = self.facade()
        handle.create_conversation(self.scope, title="before-backup")
        source_marker = self.marker(self.path)
        backup = self.root / "copy.sqlite3"
        native = SQLiteChatStore(self.path)
        native.backup_to(backup)
        native.close()
        self.assertEqual(source_marker, self.marker(backup))
        print("G14_BACKUP_CLONE_PRESERVES_MARKER=NOT_EXTERNAL_ANTIROLLBACK_RED")

    def _clone_swap(self, *, write):
        handle = self.facade()
        source_marker = self.marker(self.path)
        clone = self.root / ("clone-write.sqlite3" if write else "clone-read.sqlite3")
        shutil.copyfile(self.path, clone)
        rogue = SQLiteChatStore(clone)
        if not write:
            rogue.create_conversation(self.scope, title="rogue-clone-only")
        rogue.close()
        self.assertEqual(source_marker, self.marker(clone))

        path = self.path
        saved = self.root / "saved.sqlite3"
        detached = self.root / "detached.sqlite3"

        class SameNameClone(SQLiteChatStore):
            def __init__(self, requested):
                path.rename(saved)
                shutil.copyfile(clone, path)
                try:
                    super().__init__(requested)
                    self.db.execute("PRAGMA journal_mode=DELETE")
                    path.rename(detached)
                    saved.rename(path)
                except BaseException:
                    self.close()
                    if path.exists():
                        path.unlink()
                    if saved.exists():
                        saved.rename(path)
                    raise

        try:
            with patch("aion_chat.staged_store.SQLiteChatStore", SameNameClone):
                if write:
                    outcome = handle.create_conversation(self.scope, title="detached-write")
                else:
                    outcome = handle.list_conversations(self.scope)
        except OSError:
            if os.name != "nt":
                raise
            print("G14_SAME_MARKER_CLONE_ABA=WINDOWS_OS_DENIED_NOT_VFS_PROOF")
            return
        except sqlite3.OperationalError as exc:
            if not write or getattr(exc, "sqlite_errorname", "") != "SQLITE_READONLY_DBMOVED":
                raise
            print("G14_SAME_MARKER_CLONE_WRITE=SQLITE_NATIVE_OS_DENIED")
            return
        except StorageUnavailableError:
            # A post-commit alarm does not prove that a write was prevented.
            if not write:
                raise
            outcome = None

        if write:
            with closing(sqlite3.connect(path)) as db, db:
                self.assertEqual(
                    db.execute("SELECT count(*) FROM conversations").fetchone()[0], 0
                )
            with closing(sqlite3.connect(detached)) as db, db:
                count = db.execute("SELECT count(*) FROM conversations").fetchone()[0]
                self.assertEqual(count, 1)
            print("G14_CLONED_NATIVE_MARKER_WRITE=DETACHED_EFFECT_RED")
        else:
            self.assertEqual(
                [item.title for item in outcome.items], ["rogue-clone-only"]
            )
            with closing(sqlite3.connect(path)) as db, db:
                self.assertEqual(
                    db.execute("SELECT count(*) FROM conversations").fetchone()[0], 0
                )
            print("G14_CLONED_NATIVE_MARKER_READ=WRONG_FILE_ACCEPTED_RED")

    def test_07_same_marker_clone_can_still_be_read_red_or_os_denied(self):
        self._clone_swap(write=False)

    def test_08_same_marker_clone_write_remains_unproven_red_or_os_denied(self):
        self._clone_swap(write=True)


if __name__ == "__main__":
    unittest.main()
