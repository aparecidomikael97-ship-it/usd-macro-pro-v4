"""A234: real SQLite tests for fail-closed create-only restore in staging.

These characterize a partial safety correction. They do not attest a native
VFS handle, defend an OS-admin adversary, or close any P0.
"""
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from dataclasses import FrozenInstanceError
import errno
import os
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
from unittest import TestCase, mock

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore, StorageUnavailableError
from atlasquant_aion_chat_storage_resilience import (
    create_verified_staging_backup,
    restore_verified_staging_backup,
)


def _new_db(path: Path, marker: int):
    with closing(sqlite3.connect(str(path))) as db:
        db.execute("PRAGMA journal_mode=DELETE")
        db.execute("CREATE TABLE marker (id INTEGER PRIMARY KEY, value INTEGER NOT NULL)")
        db.execute("INSERT INTO marker VALUES (1, ?)", (marker,))
        db.commit()


def _read(path: Path) -> int:
    with closing(sqlite3.connect(str(path))) as db:
        return int(db.execute("SELECT value FROM marker WHERE id=1").fetchone()[0])


class A234SQLiteRestoreCreateOnlyTests(TestCase):
    def test_01_new_destination_restores_real_sqlite(self):
        with TemporaryDirectory() as raw:
            root = Path(raw); src = root/"backup.db"; dst = root/"new.db"
            _new_db(src, 13)
            result = SQLiteChatStore.restore_from_backup(src, dst)
            self.assertEqual(result["state"], "RESTORE_VERIFIED")
            self.assertEqual(_read(dst), 13)

    def test_02_existing_destination_never_overwritten(self):
        with TemporaryDirectory() as raw:
            root = Path(raw); src = root/"backup.db"; dst = root/"live.db"
            _new_db(src, 13); _new_db(dst, 42)
            before = dst.stat()
            with self.assertRaisesRegex(StorageUnavailableError, "destination or SQLite sidecars"):
                SQLiteChatStore.restore_from_backup(src, dst)
            self.assertEqual(_read(dst), 42)
            self.assertEqual((dst.stat().st_dev, dst.stat().st_ino),
                             (before.st_dev, before.st_ino))

    def test_03_open_connection_keeps_same_state_after_denial(self):
        with TemporaryDirectory() as raw:
            root = Path(raw); src = root/"backup.db"; dst = root/"live.db"
            _new_db(src, 1); _new_db(dst, 2)
            with closing(sqlite3.connect(str(dst))) as open_db:
                self.assertEqual(open_db.execute("SELECT value FROM marker").fetchone()[0], 2)
                with self.assertRaises(StorageUnavailableError):
                    SQLiteChatStore.restore_from_backup(src, dst)
                self.assertEqual(open_db.execute("SELECT value FROM marker").fetchone()[0], 2)
                self.assertEqual(_read(dst), 2)

    def test_04_duplicate_restore_never_resets_existing_state(self):
        with TemporaryDirectory() as raw:
            root = Path(raw); src = root/"backup.db"; dst = root/"new.db"
            _new_db(src, 1)
            SQLiteChatStore.restore_from_backup(src, dst)
            with closing(sqlite3.connect(str(dst))) as db:
                db.execute("UPDATE marker SET value=88 WHERE id=1")
                db.commit()
            with self.assertRaises(StorageUnavailableError):
                SQLiteChatStore.restore_from_backup(src, dst)
            self.assertEqual(_read(dst), 88)

    def test_05_same_source_and_target_rejected(self):
        with TemporaryDirectory() as raw:
            src = Path(raw)/"backup.db"; _new_db(src, 1)
            with self.assertRaises(ValueError):
                SQLiteChatStore.restore_from_backup(src, src)
            self.assertEqual(_read(src), 1)

    def test_06_wal_sidecar_alone_vetoes_restore(self):
        self._sidecar_denied("-wal")

    def test_07_shm_sidecar_alone_vetoes_restore(self):
        self._sidecar_denied("-shm")

    def test_08_journal_sidecar_alone_vetoes_restore(self):
        self._sidecar_denied("-journal")

    def _sidecar_denied(self, suffix):
        with TemporaryDirectory() as raw:
            root = Path(raw); src = root/"backup.db"; dst = root/"new.db"
            _new_db(src, 1)
            sidecar = Path(str(dst)+suffix)
            sidecar.write_bytes(b"existing-sidecar")
            with self.assertRaises(StorageUnavailableError):
                SQLiteChatStore.restore_from_backup(src, dst)
            self.assertFalse(dst.exists())
            self.assertEqual(sidecar.read_bytes(), b"existing-sidecar")

    def test_09_existing_directory_never_replaced(self):
        with TemporaryDirectory() as raw:
            root = Path(raw); src = root/"backup.db"; dst = root/"existingdir"
            _new_db(src, 1); dst.mkdir()
            with self.assertRaises(StorageUnavailableError):
                SQLiteChatStore.restore_from_backup(src, dst)
            self.assertTrue(dst.is_dir())

    def test_10_corrupt_source_does_not_create_target(self):
        with TemporaryDirectory() as raw:
            root = Path(raw); src = root/"invalid.db"; dst = root/"new.db"
            src.write_bytes(b"not a sqlite database")
            with self.assertRaises(StorageUnavailableError):
                SQLiteChatStore.restore_from_backup(src, dst)
            self.assertFalse(dst.exists())

    def test_11_atomic_publish_blocks_concurrent_second_restore(self):
        with TemporaryDirectory() as raw:
            root = Path(raw); src = root/"backup.db"; dst = root/"new.db"
            _new_db(src, 19)
            def restore(_):
                try:
                    SQLiteChatStore.restore_from_backup(src, dst)
                    return True
                except StorageUnavailableError:
                    return False
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(restore, range(2)))
            self.assertEqual(results.count(True), 1)
            self.assertEqual(results.count(False), 1)
            self.assertEqual(_read(dst), 19)

    def test_12_race_target_created_at_publish_still_not_replaced(self):
        with TemporaryDirectory() as raw:
            root = Path(raw); src = root/"backup.db"; dst = root/"new.db"
            _new_db(src, 13)
            def race(_source, destination):
                _new_db(Path(destination), 72)
                raise FileExistsError(errno.EEXIST, "target created during publish", str(destination))
            with mock.patch("aion_chat.store.os.link", side_effect=race):
                with self.assertRaises(StorageUnavailableError):
                    SQLiteChatStore.restore_from_backup(src, dst)
            self.assertEqual(_read(dst), 72)
            self.assertEqual(list(root.glob("new.db.restore-*")), [])

    def test_13_unsupported_atomic_link_fails_closed(self):
        with TemporaryDirectory() as raw:
            root = Path(raw); src = root/"backup.db"; dst = root/"new.db"
            _new_db(src, 13)
            with mock.patch("aion_chat.store.os.link",
                            side_effect=OSError(errno.EOPNOTSUPP, "unsupported")):
                with self.assertRaises(StorageUnavailableError):
                    SQLiteChatStore.restore_from_backup(src, dst)
            self.assertFalse(dst.exists())
            self.assertEqual(list(root.glob("new.db.restore-*")), [])

    def test_14_hardlinked_existing_target_is_denied(self):
        with TemporaryDirectory() as raw:
            root = Path(raw); src = root/"backup.db"; dst = root/"alias.db"
            _new_db(src, 13)
            os.link(src, dst)
            with self.assertRaises(StorageUnavailableError):
                SQLiteChatStore.restore_from_backup(src, dst)
            self.assertEqual(_read(dst), 13)

    def test_15_restore_wrapper_succeeds_only_to_fresh_path(self):
        with TemporaryDirectory() as raw:
            root = Path(raw); live = root/"chat.db"; backup = root/"snap.db"; dst = root/"restored.db"
            store = SQLiteChatStore(live)
            try:
                store.create_conversation(Scope("lab-owner", "lab-tenant", "lab-workspace"), "A234 TEST")
                create_verified_staging_backup(store, backup)
            finally:
                store.close()
            result = restore_verified_staging_backup(backup, dst)
            self.assertEqual(result["state"], "RESTORE_VERIFIED")
            self.assertEqual(result["restored_health"]["state"], "healthy")
            with self.assertRaises(StorageUnavailableError):
                restore_verified_staging_backup(backup, dst)

    def test_16_backup_creation_path_unchanged(self):
        with TemporaryDirectory() as raw:
            root = Path(raw); live = root/"chat.db"; backup = root/"snap.db"
            store = SQLiteChatStore(live)
            try:
                store.create_conversation(Scope("lab-owner", "lab-tenant", "lab-workspace"), "A234 TEST")
                result = store.backup_to(backup)
                self.assertEqual(result["state"], "BACKUP_VERIFIED")
                self.assertTrue(backup.is_file())
            finally:
                store.close()

    def test_17_no_temp_left_after_success(self):
        with TemporaryDirectory() as raw:
            root = Path(raw); src = root/"backup.db"; dst = root/"new.db"
            _new_db(src, 17)
            SQLiteChatStore.restore_from_backup(src, dst)
            self.assertEqual(list(root.glob("new.db.restore-*")), [])

    def test_18_existing_empty_file_is_not_permission_to_restore(self):
        with TemporaryDirectory() as raw:
            root = Path(raw); src = root/"backup.db"; dst = root/"empty.db"
            _new_db(src, 7); dst.touch()
            with self.assertRaises(StorageUnavailableError):
                SQLiteChatStore.restore_from_backup(src, dst)
            self.assertEqual(dst.read_bytes(), b"")

    def test_19_nested_new_directory_can_restore_without_overwrite(self):
        with TemporaryDirectory() as raw:
            root = Path(raw); src = root/"backup.db"; dst = root/"nested"/"new.db"
            _new_db(src, 4)
            result = SQLiteChatStore.restore_from_backup(src, dst)
            self.assertEqual(result["state"], "RESTORE_VERIFIED")
            self.assertEqual(_read(dst), 4)

    def test_20_does_not_prove_p0_closed_or_external_antirollback(self):
        # The positive assertions above cover only this local staging API.
        from labs.a232_six_p0_evidence_crosswalk import P0_DEFINITIONS
        self.assertIn("ATOMIC_NATIVE_SQLITE_READ_HANDLE", P0_DEFINITIONS["P0-5"][2])
        self.assertIn("POST_COMMIT_OUTCOME_RECONCILIATION", P0_DEFINITIONS["P0-6"][2])


if __name__ == "__main__":
    import unittest
    unittest.main()
