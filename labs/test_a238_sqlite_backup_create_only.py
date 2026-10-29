"""A238: SQLite backup publication must never replace an existing live pathname.

LAB only: local filesystem behavior, not FD/VFS attestation or power-loss proof.
"""
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import errno
import os
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest
from unittest import mock

from aion_chat.store import (
    BackupPublicationUncertainError,
    SQLiteChatStore,
    StorageUnavailableError,
)


def _new_store(path, value):
    store = SQLiteChatStore(path)
    store.db.execute("CREATE TABLE proof (value INTEGER NOT NULL)")
    store.db.execute("INSERT INTO proof VALUES (?)", (value,))
    store.db.commit()
    return store


def _read(path):
    with closing(sqlite3.connect(str(path))) as db:
        return db.execute("SELECT value FROM proof").fetchone()[0]


class A238BackupCreateOnlyTests(unittest.TestCase):
    def test_01_new_backup_works_without_durability_claim(self):
        with TemporaryDirectory(prefix="a238-") as raw:
            root = Path(raw)
            source = _new_store(root / "source.db", 19)
            try:
                result = source.backup_to(root / "backup.db")
                self.assertEqual(result["state"], "BACKUP_VERIFIED")
                self.assertFalse(result["power_loss_durability_verified"])
                self.assertEqual(_read(root / "backup.db"), 19)
            finally:
                source.close()

    def test_02_existing_live_database_not_replaced_or_forked(self):
        with TemporaryDirectory(prefix="a238-") as raw:
            root = Path(raw)
            source = _new_store(root / "source.db", 19)
            existing = _new_store(root / "backup.db", 71)
            try:
                with self.assertRaises(StorageUnavailableError):
                    source.backup_to(root / "backup.db")
                self.assertEqual(existing.db.execute("SELECT value FROM proof").fetchone()[0], 71)
                self.assertEqual(_read(root / "backup.db"), 71)
            finally:
                existing.close()
                source.close()

    def test_03_dangling_symlink_is_not_overwritten(self):
        with TemporaryDirectory(prefix="a238-") as raw:
            root = Path(raw)
            source = _new_store(root / "source.db", 19)
            target = root / "backup.db"
            try:
                try:
                    target.symlink_to(root / "missing.db")
                except (OSError, NotImplementedError) as exc:
                    self.skipTest("symlink unavailable: " + str(exc))
                with self.assertRaises(StorageUnavailableError):
                    source.backup_to(target)
                self.assertTrue(target.is_symlink())
                self.assertFalse((root / "missing.db").exists())
            finally:
                source.close()

    def test_04_existing_directory_is_never_replaced(self):
        with TemporaryDirectory(prefix="a238-") as raw:
            root = Path(raw)
            source = _new_store(root / "source.db", 19)
            target = root / "backup.db"
            target.mkdir()
            try:
                with self.assertRaises(StorageUnavailableError):
                    source.backup_to(target)
                self.assertTrue(target.is_dir())
            finally:
                source.close()

    def test_05_orphaned_sqlite_sidecars_veto_backup(self):
        for suffix in ("-wal", "-shm", "-journal"):
            with self.subTest(suffix=suffix), TemporaryDirectory(prefix="a238-") as raw:
                root = Path(raw)
                source = _new_store(root / "source.db", 19)
                target = root / "backup.db"
                Path(str(target) + suffix).write_bytes(b"orphan")
                try:
                    with self.assertRaises(StorageUnavailableError):
                        source.backup_to(target)
                    self.assertFalse(target.exists())
                finally:
                    source.close()

    def test_06_concurrent_creator_during_publish_wins_without_overwrite(self):
        with TemporaryDirectory(prefix="a238-") as raw:
            root = Path(raw)
            source = _new_store(root / "source.db", 19)
            target = root / "backup.db"
            def competing_link(src, dst):
                Path(dst).write_bytes(b"winner")
                raise FileExistsError(errno.EEXIST, "target already created", str(dst))
            try:
                with mock.patch("aion_chat.store.os.link", side_effect=competing_link):
                    with self.assertRaises(StorageUnavailableError):
                        source.backup_to(target)
                self.assertEqual(target.read_bytes(), b"winner")
            finally:
                source.close()

    def test_07_directory_sync_failure_after_link_is_uncertain(self):
        with TemporaryDirectory(prefix="a238-") as raw:
            root = Path(raw)
            source = _new_store(root / "source.db", 19)
            target = root / "backup.db"
            try:
                with mock.patch("aion_chat.store._sync_staging_restore_directory",
                                side_effect=OSError(errno.EIO, "synthetic dir fsync")):
                    with self.assertRaises(BackupPublicationUncertainError):
                        source.backup_to(target)
                self.assertEqual(_read(target), 19)
                with self.assertRaises(StorageUnavailableError):
                    source.backup_to(target)
            finally:
                source.close()

    def test_08_temp_cleanup_failure_after_link_is_uncertain(self):
        with TemporaryDirectory(prefix="a238-") as raw:
            root = Path(raw)
            source = _new_store(root / "source.db", 19)
            target = root / "backup.db"
            original = Path.unlink
            def fail_temp_unlink(path, *args, **kwargs):
                if path.name.startswith("backup.db.tmp-"):
                    raise OSError(errno.EIO, "synthetic cleanup failure")
                return original(path, *args, **kwargs)
            try:
                with mock.patch.object(Path, "unlink", fail_temp_unlink):
                    with self.assertRaises(BackupPublicationUncertainError):
                        source.backup_to(target)
                self.assertEqual(_read(target), 19)
            finally:
                source.close()

    def test_09_sidecar_race_after_link_is_uncertain(self):
        with TemporaryDirectory(prefix="a238-") as raw:
            root = Path(raw)
            source = _new_store(root / "source.db", 19)
            target = root / "backup.db"
            def sidecar_then_return(directory):
                Path(str(target) + "-wal").write_bytes(b"raced")
                return False
            try:
                with mock.patch("aion_chat.store._sync_staging_restore_directory",
                                side_effect=sidecar_then_return):
                    with self.assertRaises(BackupPublicationUncertainError):
                        source.backup_to(target)
                self.assertTrue(target.exists())
            finally:
                source.close()

    def test_10_target_inode_swap_after_link_is_uncertain(self):
        with TemporaryDirectory(prefix="a238-") as raw:
            root = Path(raw)
            source = _new_store(root / "source.db", 19)
            target = root / "backup.db"
            def replace_after_link(directory):
                target.unlink()
                target.write_bytes(b"foreign")
                return False
            try:
                with mock.patch("aion_chat.store._sync_staging_restore_directory",
                                side_effect=replace_after_link):
                    with self.assertRaises(BackupPublicationUncertainError):
                        source.backup_to(target)
                self.assertEqual(target.read_bytes(), b"foreign")
            finally:
                source.close()

    def test_11_two_independent_backup_creators_one_winner(self):
        with TemporaryDirectory(prefix="a238-") as raw:
            root = Path(raw)
            sources = []
            for value in (19, 71):
                path = root / ("source-%s.db" % value)
                s = _new_store(path, value)
                s.close()
                sources.append(path)
            target = root / "shared-backup.db"
            def attempt(path):
                store = SQLiteChatStore(path)
                try:
                    store.backup_to(target)
                    return "created"
                except StorageUnavailableError:
                    return "denied"
                finally:
                    store.close()
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(attempt, sources))
            self.assertCountEqual(results, ("created", "denied"))
            self.assertIn(_read(target), (19, 71))

    def test_12_unsupported_directory_sync_does_not_certify_powerloss(self):
        with TemporaryDirectory(prefix="a238-") as raw:
            root = Path(raw)
            source = _new_store(root / "source.db", 19)
            try:
                with mock.patch("aion_chat.store._sync_staging_restore_directory",
                                return_value=False):
                    result = source.backup_to(root / "backup.db")
                self.assertFalse(result["directory_sync_requested"])
                self.assertFalse(result["power_loss_durability_verified"])
            finally:
                source.close()
