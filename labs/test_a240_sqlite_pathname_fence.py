"""A240 — stage-only detection of SQLite pathname replacement.

This guards the *visible pathname*, never attests the native SQLite VFS/FD.
"""
from contextlib import closing
import os
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest
from unittest import mock

from aion_chat.models import Scope
from aion_chat.store import FAILED, HEALTHY, SQLiteChatStore, StorageUnavailableError


SCOPE = Scope("owner-a240", "tenant-a240", "workspace-a240")


class A240SQLitePathnameBindingTests(unittest.TestCase):
    def test_01_normal_store_retains_pathname_identity(self):
        with TemporaryDirectory(prefix="a240-") as raw:
            store = SQLiteChatStore(Path(raw) / "live.db")
            try:
                conversation = store.create_conversation(SCOPE, "normal")
                self.assertEqual(store.get_conversation(SCOPE, conversation.id).title, "normal")
                self.assertEqual(store._pathname_binding_reason(), "OK")
                self.assertEqual(store.require_healthy()["state"], HEALTHY)
            finally:
                store.close()

    def test_02_real_replace_of_open_path_denies_stale_handle(self):
        with TemporaryDirectory(prefix="a240-") as raw:
            root = Path(raw)
            live = root / "live.db"
            replacement = root / "replacement.db"
            store = SQLiteChatStore(live)
            try:
                with closing(sqlite3.connect(str(replacement))) as db:
                    db.execute("CREATE TABLE unrelated (value INTEGER)")
                    db.commit()
                try:
                    os.replace(replacement, live)
                except OSError as exc:
                    self.skipTest("OS prevents replacing a live SQLite pathname: " + str(exc))
                self.assertEqual(store._pathname_binding_reason(), "PATH_IDENTITY_CHANGED")
                self.assertEqual(store.storage_health()["state"], FAILED)
                with self.assertRaises(StorageUnavailableError):
                    store.wal_checkpoint()
            finally:
                store.close()

    def test_03_real_path_disappearance_fails_closed(self):
        with TemporaryDirectory(prefix="a240-") as raw:
            root = Path(raw)
            live = root / "live.db"
            detached = root / "detached.db"
            store = SQLiteChatStore(live)
            try:
                try:
                    os.replace(live, detached)
                except OSError as exc:
                    self.skipTest("OS prevents renaming a live SQLite pathname: " + str(exc))
                self.assertEqual(store._pathname_binding_reason(), "PATH_MISSING_OR_UNREADABLE")
                with self.assertRaises(StorageUnavailableError):
                    store._require_open()
            finally:
                store.close()

    def test_04_synthetic_identity_change_is_sticky_failure(self):
        with TemporaryDirectory(prefix="a240-") as raw:
            store = SQLiteChatStore(Path(raw) / "live.db")
            try:
                with mock.patch.object(store, "_pathname_binding_reason",
                                       return_value="PATH_IDENTITY_CHANGED"):
                    with self.assertRaises(StorageUnavailableError):
                        store._require_open()
                self.assertEqual(store._health_state, FAILED)
                self.assertEqual(store.storage_health()["state"], FAILED)
                with self.assertRaises(StorageUnavailableError):
                    store._require_open()
            finally:
                store.close()

    def test_05_health_report_does_not_read_after_name_swap(self):
        with TemporaryDirectory(prefix="a240-") as raw:
            store = SQLiteChatStore(Path(raw) / "live.db")
            try:
                with mock.patch.object(store, "_pathname_binding_reason",
                                       return_value="PATH_NOT_REGULAR"):
                    report = store.storage_health(deep=True)
                self.assertEqual(report["state"], FAILED)
                self.assertEqual(report["reason"], "PATH_NOT_REGULAR")
                self.assertEqual(report["quick_check"], "not_run")
            finally:
                store.close()

    def test_06_backup_refuses_changed_path_before_destination_created(self):
        with TemporaryDirectory(prefix="a240-") as raw:
            root = Path(raw)
            store = SQLiteChatStore(root / "live.db")
            target = root / "backup.db"
            try:
                with mock.patch.object(store, "_pathname_binding_reason",
                                       return_value="PATH_IDENTITY_CHANGED"):
                    with self.assertRaises(StorageUnavailableError):
                        store.backup_to(target)
                self.assertFalse(target.exists())
            finally:
                store.close()

    def test_07_symlink_as_live_store_path_is_rejected_at_startup(self):
        with TemporaryDirectory(prefix="a240-") as raw:
            root = Path(raw)
            original = root / "original.db"
            created = SQLiteChatStore(original)
            created.close()
            alias = root / "alias.db"
            try:
                alias.symlink_to(original)
            except (OSError, NotImplementedError) as exc:
                self.skipTest("symlink unavailable: " + str(exc))
            with self.assertRaises(StorageUnavailableError):
                SQLiteChatStore(alias)

    def test_08_normal_wal_checkpoint_and_backup_do_not_false_alarm(self):
        with TemporaryDirectory(prefix="a240-") as raw:
            root = Path(raw)
            store = SQLiteChatStore(root / "live.db")
            try:
                store.create_conversation(SCOPE, "writes")
                store.wal_checkpoint("FULL")
                self.assertEqual(store.backup_to(root / "backup.db")["state"], "BACKUP_VERIFIED")
                self.assertEqual(store.require_healthy()["state"], HEALTHY)
            finally:
                store.close()

    def test_09_scope_lookup_refuses_after_identity_change(self):
        with TemporaryDirectory(prefix="a240-") as raw:
            store = SQLiteChatStore(Path(raw) / "live.db")
            try:
                conversation = store.create_conversation(SCOPE, "read")
                with mock.patch.object(store, "_pathname_binding_reason",
                                       return_value="PATH_IDENTITY_CHANGED"):
                    with self.assertRaises(StorageUnavailableError):
                        store.get_conversation(SCOPE, conversation.id)
            finally:
                store.close()
