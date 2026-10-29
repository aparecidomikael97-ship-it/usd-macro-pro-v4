"""A245 — fail-closed pathname startup window plus an honest P0-5 XFAIL.

Disposable staging SQLite only. Neither path identity nor SQLite quick_check
attests the VFS/FD, external rollback floor, or real-world durability.
"""
from contextlib import closing
import os
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest
from unittest import mock

from aion_chat.models import Scope
from aion_chat.store import HEALTHY, SQLiteChatStore, StorageUnavailableError


SCOPE = Scope("owner-a245", "tenant-a245", "workspace-a245")


def _create_existing(path):
    store = SQLiteChatStore(path)
    try:
        store.create_conversation(SCOPE, "initial")
    finally:
        store.close()


class A245ConnectPathFenceTests(unittest.TestCase):
    def test_01_new_database_initializes_normally(self):
        with TemporaryDirectory(prefix="a245-new-") as raw:
            path = Path(raw) / "new.db"
            self.assertFalse(path.exists())
            store = SQLiteChatStore(path)
            try:
                self.assertEqual(store.require_healthy()["state"], HEALTHY)
                self.assertEqual(store._pathname_binding_reason(), "OK")
            finally:
                store.close()

    def test_02_existing_database_reopens_normally(self):
        with TemporaryDirectory(prefix="a245-existing-") as raw:
            path = Path(raw) / "live.db"
            _create_existing(path)
            store = SQLiteChatStore(path)
            try:
                self.assertEqual(store.require_healthy()["state"], HEALTHY)
                with closing(sqlite3.connect(str(path))) as db:
                    self.assertEqual(
                        db.execute("SELECT count(*) FROM conversations").fetchone()[0], 1
                    )
            finally:
                store.close()

    def test_03_changed_identity_during_connect_fails_closed_on_all_platforms(self):
        with TemporaryDirectory(prefix="a245-fake-") as raw:
            path = Path(raw) / "live.db"
            _create_existing(path)
            real_stat = Path.stat
            path_stat_calls = 0

            def simulated_stat(candidate, *args, **kwargs):
                nonlocal path_stat_calls
                result = real_stat(candidate, *args, **kwargs)
                if candidate == path:
                    path_stat_calls += 1
                    if path_stat_calls == 2:
                        fields = list(result)
                        fields[1] = int(result.st_ino) + 1
                        return os.stat_result(fields)
                return result

            with mock.patch.object(Path, "stat", simulated_stat):
                with self.assertRaisesRegex(
                    StorageUnavailableError, "pathname changed while opening"
                ):
                    SQLiteChatStore(path)
            self.assertGreaterEqual(path_stat_calls, 2)
            reopened = SQLiteChatStore(path)
            reopened.close()

    def test_04_real_path_swap_immediately_after_connect_denied_if_supported(self):
        with TemporaryDirectory(prefix="a245-swap-") as raw:
            root = Path(raw)
            path, replacement = root / "live.db", root / "replacement.db"
            _create_existing(path)
            with closing(sqlite3.connect(str(replacement))) as db:
                db.execute("CREATE TABLE unrelated (value INTEGER)")
                db.commit()

            real_connect = sqlite3.connect
            called = 0

            def connect_and_swap(*args, **kwargs):
                nonlocal called
                connection = real_connect(*args, **kwargs)
                called += 1
                try:
                    os.replace(replacement, path)
                except OSError as exc:
                    connection.close()
                    self.skipTest("OS forbids swapping an opened SQLite path: " + str(exc))
                return connection

            with mock.patch("aion_chat.store.sqlite3.connect", side_effect=connect_and_swap):
                with self.assertRaisesRegex(
                    StorageUnavailableError, "pathname changed while opening"
                ):
                    SQLiteChatStore(path)
            self.assertEqual(called, 1)

    def test_05_existing_symlink_denied_before_open(self):
        with TemporaryDirectory(prefix="a245-link-") as raw:
            root = Path(raw)
            path, link = root / "real.db", root / "link.db"
            _create_existing(path)
            try:
                link.symlink_to(path)
            except (OSError, NotImplementedError) as exc:
                self.skipTest("symlink creation unavailable: " + str(exc))
            with mock.patch("aion_chat.store.sqlite3.connect") as fake_connect:
                with self.assertRaisesRegex(
                    StorageUnavailableError, "preconnect pathname is not a regular file"
                ):
                    SQLiteChatStore(link)
            fake_connect.assert_not_called()

    def test_06_pathname_check_is_not_a_native_vfs_attestation(self):
        with TemporaryDirectory(prefix="a245-limits-") as raw:
            path = Path(raw) / "live.db"
            _create_existing(path)
            store = SQLiteChatStore(path)
            try:
                self.assertEqual(store._pathname_binding_reason(), "OK")
                self.assertEqual(store.require_healthy()["state"], HEALTHY)
                # These results prove only the staging pathname/SQLite
                # structural checks. They are NOT an external antirollback or
                # native opened-FD certificate.
            finally:
                store.close()

    @unittest.expectedFailure
    def test_07_red_p0_5_closed_same_inode_rollback_should_be_denied(self):
        """Desired invariant remains RED: host can restore old valid SQLite bytes."""
        with TemporaryDirectory(prefix="a245-rollback-") as raw:
            path = Path(raw) / "live.db"
            _create_existing(path)
            saved = path.read_bytes()
            original_stat = path.stat()

            store = SQLiteChatStore(path)
            try:
                store.create_conversation(SCOPE, "second committed conversation")
            finally:
                store.close()
            with closing(sqlite3.connect(str(path))) as db:
                self.assertEqual(
                    db.execute("SELECT count(*) FROM conversations").fetchone()[0], 2
                )

            with path.open("r+b") as handle:
                handle.write(saved)
                handle.truncate(len(saved))
                handle.flush()
                os.fsync(handle.fileno())
            restored_stat = path.stat()
            self.assertEqual(
                (original_stat.st_dev, original_stat.st_ino),
                (restored_stat.st_dev, restored_stat.st_ino),
            )
            with closing(sqlite3.connect(str(path))) as db:
                self.assertEqual(
                    db.execute("SELECT count(*) FROM conversations").fetchone()[0], 1
                )
            # The safe behavior would reject stale state across restarts.
            # Until there is an independent monotonic anchor, it does NOT.
            with self.assertRaises(StorageUnavailableError):
                reopened = SQLiteChatStore(path)
                reopened.close()


if __name__ == "__main__":
    unittest.main()
