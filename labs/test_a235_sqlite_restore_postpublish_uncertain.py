"""A235 — 15 native SQLite regressions for post-publish uncertainty.

Only ephemeral on-disk SQLite databases; no production connections, provider,
Worker, external custody or spend. P0-5/P0-6 remain open.
"""
from __future__ import annotations

from contextlib import closing
import errno
import os
from pathlib import Path
import shutil
import sqlite3
from tempfile import TemporaryDirectory
import unittest
from unittest import mock

from aion_chat.models import Scope
from aion_chat.store import (
    SQLiteChatStore, RestorePublicationUncertainError, StorageUnavailableError,
)
from atlasquant_aion_chat_storage_resilience import (
    create_verified_staging_backup, restore_verified_staging_backup,
)


def _new_db(path: Path, number: int) -> None:
    with closing(sqlite3.connect(str(path))) as db:
        db.execute("PRAGMA journal_mode=DELETE")
        db.execute("CREATE TABLE item (value INTEGER NOT NULL)")
        db.execute("INSERT INTO item VALUES (?)", (number,))
        db.commit()


def _read(path: Path) -> int:
    with closing(sqlite3.connect(str(path))) as db:
        return int(db.execute("SELECT value FROM item").fetchone()[0])


class A235SQLitePostPublishUncertaintyTests(unittest.TestCase):
    def _two_paths(self, root: str):
        base = Path(root)
        src, target = base / "source.db", base / "restored.db"
        _new_db(src, 13)
        return src, target

    def _race_sidecar(self, suffix: str):
        with TemporaryDirectory(prefix="a235-") as raw:
            src, target = self._two_paths(raw)
            link = os.link
            def simulate(source, destination):
                Path(str(destination) + suffix).write_bytes(b"synthetic-sidecar")
                return link(source, destination)
            with mock.patch("aion_chat.store.os.link", side_effect=simulate):
                with self.assertRaises( RestorePublicationUncertainError) as cm:
                    SQLiteChatStore.restore_from_backup(src, target)
            self.assertIn("SIDECAR_RACE_ZERO_AUTO_RETRY", str(cm.exception))
            self.assertTrue(target.exists())
            self.assertEqual(_read(target), 13)
            self.assertTrue(Path(str(target) + suffix).exists())
            self.assertEqual(list(Path(raw).glob("restored.db.restore-*")), [])
            # As publication took place, the next attempt is never allowed.
            with self.assertRaises(StorageUnavailableError):
                SQLiteChatStore.restore_from_backup(src, target)

    def test_01_fresh_publication_succeeds(self):
        with TemporaryDirectory(prefix="a235-") as raw:
            src, target = self._two_paths(raw)
            result = SQLiteChatStore.restore_from_backup(src, target)
            self.assertEqual(result["state"], "RESTORE_VERIFIED")
            self.assertEqual(_read(target), 13)

    def test_02_post_link_cleanup_failure_is_uncertain(self):
        with TemporaryDirectory(prefix="a235-") as raw:
            src, target = self._two_paths(raw)
            original_unlink = Path.unlink
            def deny_temp(path, *args, **kwargs):
                if path.name.startswith("restored.db.restore-"):
                    raise PermissionError(errno.EACCES, "synthetic cleanup denied")
                return original_unlink(path, *args, **kwargs)
            with mock.patch("aion_chat.store.Path.unlink", autospec=True, side_effect=deny_temp):
                with self.assertRaises(RestorePublicationUncertainError) as cm:
                    SQLiteChatStore.restore_from_backup(src, target)
            self.assertIn("POST_LINK_IO_ZERO_AUTO_RETRY", str(cm.exception))
            self.assertTrue(target.is_file())
            self.assertEqual(_read(target), 13)

    def test_03_uncertain_cleanup_must_not_delete_new_target(self):
        with TemporaryDirectory(prefix="a235-") as raw:
            src, target = self._two_paths(raw)
            original_unlink = Path.unlink
            def deny_temp(path, *args, **kwargs):
                if path.name.startswith("restored.db.restore-"):
                    raise PermissionError(errno.EACCES, "synthetic cleanup denied")
                return original_unlink(path, *args, **kwargs)
            with mock.patch("aion_chat.store.Path.unlink", autospec=True, side_effect=deny_temp):
                with self.assertRaises(RestorePublicationUncertainError):
                    SQLiteChatStore.restore_from_backup(src, target)
            self.assertEqual(_read(target), 13)
            with self.assertRaises(StorageUnavailableError):
                SQLiteChatStore.restore_from_backup(src, target)

    def test_04_wal_created_during_link_is_not_accepted(self):
        self._race_sidecar("-wal")

    def test_05_shm_created_during_link_is_not_accepted(self):
        self._race_sidecar("-shm")

    def test_06_journal_created_during_link_is_not_accepted(self):
        self._race_sidecar("-journal")

    def test_07_target_replaced_after_link_fails_uncertain(self):
        with TemporaryDirectory(prefix="a235-") as raw:
            src, target = self._two_paths(raw)
            substitute = Path(raw)/"other.db"
            _new_db(substitute, 72)
            original_link = os.link
            def swap(source, destination):
                original_link(source, destination)
                Path(destination).unlink()
                shutil.copyfile(substitute, destination)
            with mock.patch("aion_chat.store.os.link", side_effect=swap):
                with self.assertRaises(RestorePublicationUncertainError) as cm:
                    SQLiteChatStore.restore_from_backup(src, target)
            self.assertIn("TARGET_CHANGED_ZERO_AUTO_RETRY", str(cm.exception))
            self.assertEqual(_read(target), 72)
            with self.assertRaises(StorageUnavailableError):
                SQLiteChatStore.restore_from_backup(src, target)

    def test_08_target_disappears_after_link_fails_uncertain(self):
        with TemporaryDirectory(prefix="a235-") as raw:
            src, target = self._two_paths(raw)
            original_link = os.link
            def remove(source, destination):
                original_link(source, destination)
                Path(destination).unlink()
            with mock.patch("aion_chat.store.os.link", side_effect=remove):
                with self.assertRaises(RestorePublicationUncertainError) as cm:
                    SQLiteChatStore.restore_from_backup(src, target)
            self.assertIn("POST_LINK_IO_ZERO_AUTO_RETRY", str(cm.exception))
            self.assertFalse(target.exists())

    def test_09_sidecar_existing_before_publication_is_preflight_denial(self):
        with TemporaryDirectory(prefix="a235-") as raw:
            src, target = self._two_paths(raw)
            wal = Path(str(target) + "-wal")
            wal.write_bytes(b"block")
            with self.assertRaises(StorageUnavailableError) as cm:
                SQLiteChatStore.restore_from_backup(src, target)
            self.assertNotIsInstance(cm.exception, RestorePublicationUncertainError)
            self.assertFalse(target.exists())

    def test_10_prepublication_invalid_source_never_published(self):
        with TemporaryDirectory(prefix="a235-") as raw:
            src, target = self._two_paths(raw)
            src.write_bytes(b"not sqlite")
            with self.assertRaises(StorageUnavailableError) as cm:
                SQLiteChatStore.restore_from_backup(src, target)
            self.assertNotIsInstance(cm.exception, RestorePublicationUncertainError)
            self.assertFalse(target.exists())

    def test_11_prepublication_link_rejection_does_not_publish(self):
        with TemporaryDirectory(prefix="a235-") as raw:
            src, target = self._two_paths(raw)
            with mock.patch("aion_chat.store.os.link",
                            side_effect=OSError(errno.EPERM, "no link")):
                with self.assertRaises(StorageUnavailableError) as cm:
                    SQLiteChatStore.restore_from_backup(src, target)
            self.assertNotIsInstance(cm.exception, RestorePublicationUncertainError)
            self.assertFalse(target.exists())

    def test_12_second_restore_after_success_stays_denied(self):
        with TemporaryDirectory(prefix="a235-") as raw:
            src, target = self._two_paths(raw)
            SQLiteChatStore.restore_from_backup(src, target)
            with self.assertRaises(StorageUnavailableError):
                SQLiteChatStore.restore_from_backup(src, target)
            self.assertEqual(_read(target), 13)

    def test_13_existing_target_is_preserved_under_uncertainty_guard(self):
        with TemporaryDirectory(prefix="a235-") as raw:
            src, target = self._two_paths(raw)
            _new_db(target, 98)
            with self.assertRaises(StorageUnavailableError):
                SQLiteChatStore.restore_from_backup(src, target)
            self.assertEqual(_read(target), 98)

    def test_14_staging_restore_wrapper_preserves_uncertain_class(self):
        with TemporaryDirectory(prefix="a235-") as raw:
            root = Path(raw)
            store = SQLiteChatStore(root / "chat.db")
            try:
                store.create_conversation(Scope("owner", "tenant", "workspace"), "A235")
                create_verified_staging_backup(store, root / "backup.db")
            finally:
                store.close()
            original_link = os.link
            def inject(source, destination):
                Path(str(destination) + "-wal").write_bytes(b"synthetic")
                return original_link(source, destination)
            target = root / "restored.db"
            with mock.patch("aion_chat.store.os.link", side_effect=inject):
                with self.assertRaises(RestorePublicationUncertainError):
                    restore_verified_staging_backup(root / "backup.db", target)
            self.assertTrue(target.exists())

    def test_15_uncertainty_is_subclass_of_fail_closed_error(self):
        self.assertTrue(issubclass(RestorePublicationUncertainError,
                                   StorageUnavailableError))


if __name__ == "__main__":
    unittest.main()
