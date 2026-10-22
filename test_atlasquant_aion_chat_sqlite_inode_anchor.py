"""AION SQLite LAB: independent OS descriptor/inode anchor regression.

Real local SQLite, synthetic descriptor faults; zero external effects.
An anchor descriptor belongs to this facade, NOT the SQLite native VFS.
No claim of atomic SQLite file binding, hostile-host safety or rollback proof.
"""
import os
from pathlib import Path
from types import SimpleNamespace
import stat
import tempfile
import unittest
from unittest.mock import patch

from aion_chat.models import Message, Scope
from aion_chat.staged_store import OperationScopedSQLiteChatStore
from aion_chat.store import FAILED, SQLiteChatStore, StorageUnavailableError


class SQLiteIdentityAnchorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.scope = Scope("owner", "tenant", "workspace")

    def store(self):
        handle = OperationScopedSQLiteChatStore(self.root / "anchor.sqlite3")
        self.addCleanup(handle.close)
        return handle

    def test_01_anchor_open_uses_platform_no_follow_flags(self):
        handle = self.store()
        real_open = os.open
        db_flags = []

        def observed(path, flags, *args, **kwargs):
            if Path(path) == handle.path:
                db_flags.append(flags)
            return real_open(path, flags, *args, **kwargs)

        with patch("aion_chat.staged_store.os.open", side_effect=observed):
            handle.list_conversations(self.scope)
        self.assertEqual(len(db_flags), 1)
        self.assertEqual(db_flags[0] & os.O_WRONLY, 0)
        self.assertEqual(db_flags[0] & os.O_RDWR, 0)
        for flag in ("O_BINARY", "O_CLOEXEC", "O_NOFOLLOW", "O_NONBLOCK"):
            supported = getattr(os, flag, 0)
            if supported:
                self.assertEqual(db_flags[0] & supported, supported)

    def test_02_anchor_fstat_identity_mismatch_fails_closed(self):
        handle = self.store()
        real_fstat = os.fstat
        calls = [0]

        def mismatched(fd):
            info = real_fstat(fd)
            calls[0] += 1
            return SimpleNamespace(st_mode=info.st_mode,
                                   st_dev=info.st_dev + 1,
                                   st_ino=info.st_ino)

        with patch("aion_chat.staged_store.os.fstat", side_effect=mismatched):
            with self.assertRaisesRegex(
                    StorageUnavailableError, "BOUND_DATABASE_ANCHOR_MISMATCH"):
                handle.list_conversations(self.scope)
        self.assertEqual(calls[0], 1)
        self.assertEqual(handle.storage_health()["state"], FAILED)
        with self.assertRaises(StorageUnavailableError):
            handle.list_conversations(self.scope)

    def test_03_anchor_open_failure_fails_closed(self):
        handle = self.store()
        with patch("aion_chat.staged_store.os.open",
                   side_effect=PermissionError("synthetic readonly error")):
            with self.assertRaisesRegex(
                    StorageUnavailableError, "BOUND_DATABASE_ANCHOR_UNAVAILABLE"):
                handle.list_conversations(self.scope)
        self.assertEqual(handle.storage_health()["state"], FAILED)

    def test_04_nonregular_opened_descriptor_is_denied(self):
        handle = self.store()
        real_fstat = os.fstat
        close_count = [0]
        real_close = os.close

        def nonregular(fd):
            info = real_fstat(fd)
            return SimpleNamespace(st_mode=stat.S_IFDIR,
                                   st_dev=info.st_dev, st_ino=info.st_ino)

        def close_tracked(fd):
            close_count[0] += 1
            return real_close(fd)

        with patch("aion_chat.staged_store.os.fstat", side_effect=nonregular):
            with patch("aion_chat.staged_store.os.close",
                       side_effect=close_tracked):
                with self.assertRaisesRegex(
                        StorageUnavailableError,
                        "BOUND_DATABASE_ANCHOR_NOT_REGULAR_FILE"):
                    handle.list_conversations(self.scope)
        self.assertEqual(close_count[0], 1)
        self.assertEqual(handle.storage_health()["state"], FAILED)

    def test_05_anchor_mismatch_after_open_prevents_write(self):
        handle = self.store()
        cid = handle.create_conversation(self.scope).id
        verify = handle._verify_identity_anchor
        calls = [0]

        def drift(fd, expected):
            calls[0] += 1
            if calls[0] == 2:
                raise StorageUnavailableError(
                    "BOUND_DATABASE_ANCHOR_MISMATCH")
            return verify(fd, expected)

        with patch.object(handle, "_verify_identity_anchor",
                          side_effect=drift):
            with self.assertRaisesRegex(
                    StorageUnavailableError, "BOUND_DATABASE_ANCHOR_MISMATCH"):
                handle.append_message(
                    self.scope, Message(cid, "user", "must-not-commit"))
        self.assertEqual(calls[0], 2)
        self.assertEqual(handle.storage_health()["state"], FAILED)
        native = SQLiteChatStore(handle.path)
        try:
            self.assertEqual(len(native.list_messages(self.scope, cid).items), 0)
        finally:
            native.close()

    def test_06_postcommit_anchor_mismatch_is_unknown_never_replayed(self):
        handle = self.store()
        cid = handle.create_conversation(self.scope).id
        real_fstat = os.fstat
        calls = [0]

        def drift(fd):
            info = real_fstat(fd)
            calls[0] += 1
            if calls[0] == 3:  # checked after native method may commit
                return SimpleNamespace(st_mode=info.st_mode,
                                       st_dev=info.st_dev + 1,
                                       st_ino=info.st_ino)
            return info

        with patch("aion_chat.staged_store.os.fstat", side_effect=drift):
            with self.assertRaisesRegex(
                    StorageUnavailableError, "BOUND_DATABASE_ANCHOR_MISMATCH"):
                handle.append_message(self.scope, Message(cid, "user", "once"))
        self.assertEqual(calls[0], 3)
        self.assertEqual(handle.storage_health()["state"], FAILED)
        with self.assertRaises(StorageUnavailableError):
            handle.append_message(self.scope, Message(cid, "user", "not-again"))
        native = SQLiteChatStore(handle.path)
        try:
            items = native.list_messages(self.scope, cid).items
            self.assertEqual(len(items), 1)
            self.assertEqual(items[0].content, "once")
        finally:
            native.close()


if __name__ == "__main__":
    unittest.main()
