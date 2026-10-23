"""A183 artifact snapshots: native :memory: input, real temp files, synthetic faults."""
from contextlib import closing
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from aion_chat.pinned_snapshot_a183_lab import PinnedSQLiteSnapshotLab
from aion_chat.store import StorageUnavailableError


class PinnedSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/"artifact.db"
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("create table events(value integer)")
            db.execute("insert into events values(1)")
        self.digest=sha256(self.path.read_bytes()).hexdigest()

    def snapshot(self):
        s=PinnedSQLiteSnapshotLab(self.path,expected_sha256=self.digest)
        self.addCleanup(s.close);return s

    def test_native_memory_reads_exact_pinned_bytes(self):
        s=self.snapshot()
        self.assertEqual(s.rows("select value from events"),[(1,)])
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("update events set value=2")
        self.assertEqual(s.rows("select value from events"),[(1,)])
        with self.assertRaisesRegex(StorageUnavailableError,"DIGEST"):
            self.snapshot()
        print("A183_NATIVE_MEMORY_EXACT_PINNED_ARTIFACT=READ_OLD_PINNED_BYTES")

    def test_restore_under_same_inode_is_denied_by_retained_digest(self):
        old=self.path.read_bytes()
        with closing(sqlite3.connect(self.path)) as db, db:db.execute("update events set value=2")
        current=sha256(self.path.read_bytes()).hexdigest()
        inode=self.path.stat().st_ino
        self.path.write_bytes(old)
        self.assertEqual(self.path.stat().st_ino,inode)
        with self.assertRaisesRegex(StorageUnavailableError,"DIGEST"):
            PinnedSQLiteSnapshotLab(self.path,expected_sha256=current)

    def test_missing_or_malformed_pin_denies(self):
        for digest in (None,"",True,"0"*63):
            with self.subTest(digest=digest),self.assertRaises(StorageUnavailableError):
                PinnedSQLiteSnapshotLab(self.path,expected_sha256=digest)

    def test_wal_header_and_sidecars_denied(self):
        for suffix in ("-wal","-shm","-journal"):
            p=Path(str(self.path)+suffix);p.write_bytes(b"x")
            with self.assertRaisesRegex(StorageUnavailableError,"SIDECAR"):self.snapshot()
            p.unlink()
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("pragma journal_mode=wal")
        digest=sha256(self.path.read_bytes()).hexdigest()
        with self.assertRaisesRegex(StorageUnavailableError,"OFFLINE"):
            PinnedSQLiteSnapshotLab(self.path,expected_sha256=digest)

    def test_authorizer_denies_writes_attach_pragma_and_unsafe_functions(self):
        s=self.snapshot()
        for sql in ("delete from events","create table bad(x)",
                    "attach ':memory:' as other","pragma database_list",
                    "select load_extension('missing')"):
            with self.subTest(sql=sql),self.assertRaises(sqlite3.DatabaseError):
                s.rows(sql)
        self.assertEqual(s.rows("select count(*) from events"),[(1,)])

    def test_persist_and_backup_fail_closed_no_file_created(self):
        s=self.snapshot();target=self.path.parent/"must-not-exist.db"
        before=self.path.read_bytes()
        for method in (s.persist,s.backup_to):
            with self.assertRaisesRegex(StorageUnavailableError,"ZERO_AUTO_RESEND"):
                method(target)
        self.assertFalse(target.exists());self.assertEqual(self.path.read_bytes(),before)

    def test_threads_have_separate_native_connections(self):
        s=self.snapshot()
        with ThreadPoolExecutor(max_workers=6) as pool:
            values=list(pool.map(lambda _:s.rows("select value from events"),range(12)))
        self.assertEqual(values,[[(1,)]]*12)

    def test_new_process_retains_explicit_digest(self):
        code=("from aion_chat.pinned_snapshot_a183_lab import PinnedSQLiteSnapshotLab;"
              "import sys; s=PinnedSQLiteSnapshotLab(sys.argv[1],expected_sha256=sys.argv[2]);"
              "assert s.rows('select value from events')==[(1,)];s.close()")
        run=subprocess.run([sys.executable,"-B","-c",code,str(self.path),self.digest],
                           capture_output=True,text=True,timeout=20)
        self.assertEqual(run.returncode,0,run.stderr)

    def test_renamed_or_deleted_source_cannot_change_captured_memory(self):
        s=self.snapshot();self.path.rename(self.path.with_suffix(".moved"))
        self.assertEqual(s.rows("select value from events"),[(1,)])
        with self.assertRaises(StorageUnavailableError):self.snapshot()

    def test_symlink_denied_or_os_capability_reported(self):
        alias=self.path.with_suffix(".link")
        try:alias.symlink_to(self.path)
        except OSError as exc:
            print("A183_SYMLINK_CREATION_UNAVAILABLE="+type(exc).__name__)
            return
        with self.assertRaisesRegex(StorageUnavailableError,"ALIAS"):
            PinnedSQLiteSnapshotLab(alias,expected_sha256=self.digest)

    def test_changed_during_fd_read_denied(self):
        real=os.read;done=False
        def interrupted(fd,n):
            nonlocal done
            data=real(fd,n)
            if not done:
                done=True
                Path(str(self.path)+"-journal").write_bytes(b"uncertain")
            return data
        with patch("aion_chat.pinned_snapshot_a183_lab.os.read",side_effect=interrupted):
            with self.assertRaisesRegex(StorageUnavailableError,"SIDECAR"):self.snapshot()

    def test_closed_handle_denies(self):
        s=self.snapshot();s.close()
        with self.assertRaises(StorageUnavailableError):s.rows("select value from events")

    def test_size_bound_and_invalid_sqlite_are_denied(self):
        self.path.write_bytes(b"x"*100)
        with self.assertRaisesRegex(StorageUnavailableError,"OFFLINE"):
            PinnedSQLiteSnapshotLab(self.path,expected_sha256=sha256(self.path.read_bytes()).hexdigest())


if __name__=="__main__":unittest.main(verbosity=2)

