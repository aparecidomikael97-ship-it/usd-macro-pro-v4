"""G89 RED-first: scoped SQLite anchor-close fault cannot mask primary.

Real temporary SQLite and OS anchor descriptor with synthetic os.close faults;
no provider, deployment, Worker, real funds or external custody.
Never claim native SQLite VFS pinning or H0 antirollback. P0=0/6 HARD NO-GO.
"""
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from aion_chat.models import Message, Scope
from aion_chat.staged_store import OperationScopedSQLiteChatStore
from aion_chat.store import FAILED, SQLiteChatStore, StorageUnavailableError


SCOPE = Scope("g89-owner", "g89-tenant", "g89-workspace")


class G89AnchorCloseFault(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="aion-g89-anchor-close-")
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "chat.sqlite3"
        self.handle = OperationScopedSQLiteChatStore(self.path)
        self.addCleanup(self.handle.close)
        self.cid = self.handle.create_conversation(SCOPE, "seed").id
        self.original_os_close = os.close
        self.retained = []
        self.addCleanup(self.cleanup_retained)

    def cleanup_retained(self):
        for fd in self.retained:
            self.original_os_close(fd)
        self.retained.clear()

    @staticmethod
    def capture(callback):
        try:
            return callback()
        except BaseException as error:
            return error

    def assert_quarantined(self):
        with self.subTest(contract="failed_health"):
            self.assertEqual(self.handle.storage_health()["state"], FAILED)
        with self.subTest(contract="read_denied"):
            caught = self.capture(lambda: self.handle.get_conversation(SCOPE, self.cid))
            self.assertIsInstance(caught, StorageUnavailableError)
        with self.subTest(contract="write_denied"):
            caught = self.capture(lambda: self.handle.append_message(
                SCOPE, Message(self.cid, "user", "no-retry")))
            self.assertIsInstance(caught, StorageUnavailableError)

    def exercise(self, *, primary=None, after, write=False, marker):
        recorded, close_calls = [], []
        original_anchor = OperationScopedSQLiteChatStore._open_identity_anchor

        def tracked_anchor(instance, identity):
            fd = original_anchor(instance, identity)
            recorded.append(fd)
            return fd

        def faulted_close(fd):
            if recorded and fd == recorded[-1]:
                close_calls.append(fd)
                if after:
                    self.original_os_close(fd)
                else:
                    self.retained.append(fd)
                raise OSError("G89_SYNTHETIC_ANCHOR_CLOSE_FAILURE")
            return self.original_os_close(fd)

        def operation():
            if write:
                return self.handle.append_message(
                    SCOPE, Message(self.cid, "user", "committed-before-anchor-close"))
            return self.handle.get_conversation(SCOPE, self.cid)

        with patch.object(OperationScopedSQLiteChatStore, "_open_identity_anchor", tracked_anchor):
            with patch("aion_chat.staged_store.os.close", side_effect=faulted_close):
                if primary is not None:
                    with patch.object(SQLiteChatStore, "get_conversation", side_effect=primary):
                        caught = self.capture(operation)
                else:
                    caught = self.capture(operation)

        self.assertEqual(len(recorded), 1)
        self.assertEqual(close_calls, recorded)
        with self.subTest(contract="original_error_identity"):
            if primary is not None:
                self.assertIs(caught, primary)
            else:
                self.assertIsInstance(caught, StorageUnavailableError)
                self.assertIn("BOUND_DATABASE_ANCHOR_CLOSE_FAILED", str(caught))
        with self.subTest(contract="native_descriptor_outcome"):
            if after:
                with self.assertRaises(OSError):
                    os.fstat(recorded[0])
            else:
                self.assertEqual(os.fstat(recorded[0]).st_ino,
                                 self.path.stat().st_ino)
        self.assert_quarantined()
        if write:
            fresh = SQLiteChatStore(self.path)
            try:
                self.assertEqual(fresh.get_conversation(SCOPE, self.cid).message_count, 1)
            finally:
                fresh.close()
        print(marker)

    def test_01_read_success_anchor_preclose_oserror_quarantines(self):
        self.exercise(
            after=False,
            marker="G89_READ_PRECLOSE_GREEN=ANCHOR_RETAINED_NO_REUSE")

    def test_02_committed_write_anchor_postclose_oserror_quarantines(self):
        self.exercise(
            after=True, write=True,
            marker="G89_WRITE_POSTCLOSE_GREEN=COMMIT_UNCERTAIN_NO_RETRY")

    def test_03_primary_lookup_survives_secondary_anchor_oserror(self):
        self.exercise(
            primary=LookupError("G89_PRIMARY_LOOKUP"),
            after=False,
            marker="G89_LOOKUP_PRIMARY_GREEN=NOT_MASKED")

    def test_04_primary_storage_unavailable_survives_anchor_oserror(self):
        self.exercise(
            primary=StorageUnavailableError("G89_PRIMARY_STORAGE"),
            after=True,
            marker="G89_STORAGE_PRIMARY_GREEN=NOT_MASKED")

    def test_05_primary_keyboard_interrupt_survives_anchor_oserror(self):
        self.exercise(
            primary=KeyboardInterrupt("G89_PRIMARY_KI"),
            after=False,
            marker="G89_KI_PRIMARY_GREEN=NOT_MASKED")

    def test_06_primary_system_exit_survives_anchor_oserror(self):
        self.exercise(
            primary=SystemExit("G89_PRIMARY_EXIT"),
            after=True,
            marker="G89_EXIT_PRIMARY_GREEN=NOT_MASKED")

    def test_07_unfaulted_anchor_close_leaves_facade_healthy(self):
        result = self.handle.get_conversation(SCOPE, self.cid)
        self.assertEqual(result.id, self.cid)
        self.assertNotEqual(self.handle.storage_health()["state"], FAILED)
        print("G89_NORMAL_GREEN=HEALTHY_CONTROL")


if __name__ == "__main__":
    unittest.main()
