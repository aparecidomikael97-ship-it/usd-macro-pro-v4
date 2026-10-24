"""A190 G4 LAB — native SQLite WAL/SHM, live handle vs path, and file identity.

All files live inside unique TemporaryDirectory paths. These are real OS file
operations, not a mock SQLite engine, but there is NO custom VFS, independent
root, power-loss test, privileged attacker or real provider effect.
A passing negative control demonstrates a RED security limitation, NOT P0 green.
"""
from __future__ import annotations

from contextlib import closing
import hashlib
import os
from pathlib import Path
import shutil
import sqlite3
import tempfile
import unittest

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore


class A190G4NativeSQLiteFileBoundaryLab(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="a190-g4-native-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def _connect(self, name="main.sqlite", **kwargs):
        connection = sqlite3.connect(self.root / name, timeout=0.2, **kwargs)
        # Always explicitly close before TemporaryDirectory cleanup (Windows).
        self.addCleanup(connection.close)
        return connection

    @staticmethod
    def _table(connection, value="baseline"):
        connection.execute("PRAGMA journal_mode=DELETE")
        connection.execute("CREATE TABLE facts (id INTEGER PRIMARY KEY, v TEXT NOT NULL)")
        connection.execute("INSERT INTO facts(id,v) VALUES(1,?)", (value,))
        connection.commit()

    @staticmethod
    def _count(connection):
        return connection.execute("SELECT COUNT(*) FROM facts").fetchone()[0]

    def test_wal_committed_row_absent_from_main_db_copy_but_backup_includes_it_red(self):
        """Real WAL contains committed data missing from a raw main-file copy."""
        main = self.root / "wal.sqlite"
        main_only = self.root / "main-file-only.sqlite"
        proper_backup = self.root / "sqlite-backup.sqlite"
        writer = sqlite3.connect(main, timeout=0.2)
        try:
            self.assertEqual(writer.execute("PRAGMA journal_mode=WAL").fetchone()[0], "wal")
            writer.execute("PRAGMA wal_autocheckpoint=0")
            writer.execute("CREATE TABLE facts (id INTEGER PRIMARY KEY, v TEXT NOT NULL)")
            writer.commit()
            checkpoint = writer.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
            self.assertEqual(checkpoint[0], 0)

            writer.execute("INSERT INTO facts(id,v) VALUES(1,'committed-in-wal')")
            writer.commit()
            wal = Path(str(main) + "-wal")
            shm = Path(str(main) + "-shm")
            self.assertTrue(wal.is_file(), "real SQLite -wal sidecar must exist")
            self.assertTrue(shm.is_file(), "real SQLite -shm sidecar must exist")
            self.assertGreater(wal.stat().st_size, 32)
            self.assertEqual(self._count(writer), 1)

            # Deliberately BAD backup technique, but no mutation of the live DB.
            shutil.copyfile(main, main_only)
            with closing(sqlite3.connect(main_only, timeout=0.2)) as copied:
                self.assertEqual(self._count(copied), 0)
            with closing(sqlite3.connect(proper_backup, timeout=0.2)) as target:
                writer.backup(target)
                self.assertEqual(self._count(target), 1)
            self.assertEqual(self._count(writer), 1)
            print("A190_G4_MAIN_FILE_ONLY_COPY=LOST_COMMITTED_WAL_ROW_RED")
            print("A190_G4_SQLITE_BACKUP_API=INCLUDES_COMMITTED_WAL_ROW")
            print("A190_G4_REAL_WAL_AND_SHM=CREATED_AND_EXERCISED")
        finally:
            writer.close()

    def test_live_reader_snapshot_retains_wal_and_blocks_truncate_checkpoint(self):
        """A live SQL snapshot can keep WAL sidecar relevant after COMMIT."""
        main = self.root / "reader.sqlite"
        writer = sqlite3.connect(main, timeout=0.2)
        reader = None
        observer = None
        try:
            self.assertEqual(writer.execute("PRAGMA journal_mode=WAL").fetchone()[0], "wal")
            writer.execute("PRAGMA wal_autocheckpoint=0")
            writer.execute("CREATE TABLE facts (id INTEGER PRIMARY KEY, v TEXT NOT NULL)")
            writer.commit()
            self.assertEqual(writer.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()[0], 0)

            reader = sqlite3.connect(main, timeout=0.2, isolation_level=None)
            reader.execute("BEGIN")
            self.assertEqual(self._count(reader), 0)  # Pins a real reader snapshot.
            writer.execute("INSERT INTO facts(id,v) VALUES(1,'later')")
            writer.commit()
            self.assertEqual(self._count(reader), 0)
            observer = sqlite3.connect(main, timeout=0.2)
            self.assertEqual(self._count(observer), 1)
            self.assertTrue(Path(str(main) + "-wal").is_file())
            self.assertTrue(Path(str(main) + "-shm").is_file())

            busy, _, _ = writer.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
            self.assertEqual(busy, 1, "live reader must prevent safe WAL truncate")
            reader.rollback()
            self.assertEqual(writer.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()[0], 0)
            self.assertEqual(self._count(writer), 1)
            print("A190_G4_PINNED_SQLITE_READER=STALE_SNAPSHOT_WITH_NEWER_COMMITTED_WAL")
            print("A190_G4_LIVE_READER_PREVENTS_WAL_TRUNCATE=BUSY_THEN_SUCCESS")
        finally:
            if observer is not None:
                observer.close()
            if reader is not None:
                reader.close()
            writer.close()

    def test_live_path_replace_exercises_actual_os_handle_behavior(self):
        """Linux can point a path at a new DB while an old SQLite handle remains."""
        original = self.root / "active.sqlite"
        replacement = self.root / "replacement.sqlite"
        with closing(sqlite3.connect(original, timeout=0.2)) as seed:
            self._table(seed, "OLD_LIVE_HANDLE")
        with closing(sqlite3.connect(replacement, timeout=0.2)) as seed:
            self._table(seed, "NEW_PATH_CONTENT")

        keeper = sqlite3.connect(original, isolation_level=None, timeout=0.2)
        fd = None
        try:
            keeper.execute("BEGIN")
            self.assertEqual(
                keeper.execute("SELECT v FROM facts WHERE id=1").fetchone()[0],
                "OLD_LIVE_HANDLE",
            )
            fd = os.open(original, os.O_RDONLY)
            old_dev_inode = (os.fstat(fd).st_dev, os.fstat(fd).st_ino)
            try:
                os.replace(replacement, original)
                succeeded = True
            except OSError as exc:
                if os.name != "nt":
                    raise
                if getattr(exc, "winerror", None) not in (5, 32) and exc.errno not in (1, 13, 16):
                    raise
                succeeded = False

            if succeeded:
                # A new path opening and an already-open SQLite handle disagree.
                with closing(sqlite3.connect(original, timeout=0.2)) as fresh:
                    self.assertEqual(
                        fresh.execute("SELECT v FROM facts WHERE id=1").fetchone()[0],
                        "NEW_PATH_CONTENT",
                    )
                self.assertEqual(
                    keeper.execute("SELECT v FROM facts WHERE id=1").fetchone()[0],
                    "OLD_LIVE_HANDLE",
                )
                if os.name != "nt":
                    new_dev_inode = (original.stat().st_dev, original.stat().st_ino)
                    self.assertNotEqual(old_dev_inode, new_dev_inode)
                print("A190_G4_LIVE_PATH_REPLACEMENT_RESULT=STALE_OPEN_HANDLE_VS_NEW_PATH")
            else:
                # On Windows SQLite/open file often denies deletion while open.
                self.assertTrue(replacement.exists())
                self.assertEqual(
                    keeper.execute("SELECT v FROM facts WHERE id=1").fetchone()[0],
                    "OLD_LIVE_HANDLE",
                )
                with closing(sqlite3.connect(original, timeout=0.2)) as fresh:
                    self.assertEqual(
                        fresh.execute("SELECT v FROM facts WHERE id=1").fetchone()[0],
                        "OLD_LIVE_HANDLE",
                    )
                print("A190_G4_LIVE_PATH_REPLACEMENT_RESULT=OS_DENIED_WHILE_HANDLE_OPEN")
                keeper.rollback()
                keeper.close()
                os.close(fd)
                fd = None
                os.replace(replacement, original)
                with closing(sqlite3.connect(original, timeout=0.2)) as fresh:
                    self.assertEqual(
                        fresh.execute("SELECT v FROM facts WHERE id=1").fetchone()[0],
                        "NEW_PATH_CONTENT",
                    )
                print("A190_G4_AFTER_CLOSING_HANDLES=PATH_REPLACEMENT_SUCCEEDED")
        finally:
            keeper.close()
            if fd is not None:
                os.close(fd)

    def test_same_file_identity_cannot_prove_unchanged_sqlite_content_red(self):
        """Inode/file index only is not a monotonic receipt or content integrity."""
        db = self.root / "same-file.sqlite"
        with closing(sqlite3.connect(db, timeout=0.2)) as connection:
            self._table(connection, "0001")
            stat_before = db.stat()
            digest_before = hashlib.sha256(db.read_bytes()).hexdigest()
            connection.execute("UPDATE facts SET v='0002' WHERE id=1")
            connection.commit()
            stat_after = db.stat()
            digest_after = hashlib.sha256(db.read_bytes()).hexdigest()
            self.assertEqual(
                (stat_before.st_dev, stat_before.st_ino),
                (stat_after.st_dev, stat_after.st_ino),
            )
            self.assertNotEqual(digest_before, digest_after)
            self.assertEqual(
                connection.execute("SELECT v FROM facts WHERE id=1").fetchone()[0],
                "0002",
            )
        print("A190_G4_SAME_NATIVE_FILE_ID_DIFFERENT_COMMITTED_CONTENT=RED")

    def test_actual_aion_store_wal_raw_copy_omits_committed_conversation_red(self):
        """AION SQLiteChatStore live connection; raw DB-only copy is not its backup API."""
        db = self.root / "aion-live.sqlite"
        raw_copy = self.root / "aion-raw-copy.sqlite"
        scope = Scope(
            owner_id="synthetic-owner", tenant_id="synthetic-tenant",
            workspace_id="synthetic-workspace",
        )
        store = SQLiteChatStore(db)
        try:
            self.assertEqual(
                store.db.execute("PRAGMA journal_mode=WAL").fetchone()[0], "wal"
            )
            store.db.execute("PRAGMA wal_autocheckpoint=0")
            self.assertEqual(
                store.db.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()[0],
                0,
            )
            self.assertEqual(
                store.db.execute("SELECT COUNT(*) FROM conversations").fetchone()[0], 0
            )
            store.create_conversation(scope, title="LAB:COMMITTED_WAL_ONLY")
            self.assertEqual(
                store.db.execute("SELECT COUNT(*) FROM conversations").fetchone()[0], 1
            )
            self.assertGreater(Path(str(db) + "-wal").stat().st_size, 32)
            shutil.copyfile(db, raw_copy)
            with closing(sqlite3.connect(raw_copy, timeout=0.2)) as copied:
                self.assertEqual(
                    copied.execute("SELECT COUNT(*) FROM conversations").fetchone()[0],
                    0,
                )
            print("A190_G4_REAL_AION_SQLITE_CHAT_STORE_MAIN_ONLY_COPY=STALE_RED")
        finally:
            store.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
