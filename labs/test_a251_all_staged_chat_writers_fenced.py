"""A251 LAB — protect remaining public SQLiteChatStore write methods.

Disposable SQLite, no provider, no external identity or real financial effect.
The A247 local pre-COMMIT marker is not independently tamper resistant.
"""
from contextlib import closing
import hashlib
import inspect
from pathlib import Path
import sqlite3
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest import mock

from aion_chat.models import (
    Attachment, ContextSummary, ConversationCheckpoint, Message, Scope,
)
from aion_chat.store import (
    FAILED, HEALTHY, SQLiteChatStore, StorageUnavailableError,
    StoreCommitOutcomeUncertainError,
)
from labs.test_a246_chat_commit_uncertainty import LostAckConnection


SCOPE = Scope("owner-a251", "tenant-a251", "workspace-a251")
MARKER = ".aion-message-commit-pending"


def _marker(dbpath):
    return Path(str(dbpath) + MARKER)


def _attachment(conversation_id, suffix="one"):
    digest = hashlib.sha256(suffix.encode("ascii")).hexdigest()
    return Attachment(
        conversation_id, suffix + ".txt", "text/plain",
        len(suffix), digest, digest + ".blob",
    )


def _seed(store):
    c = store.create_conversation(SCOPE, "a251")
    m = store.append_message(SCOPE, Message(c.id, "user", "one", id="a251-m1"))
    return c, m


def _record_count(path, kind):
    with closing(sqlite3.connect(str(path))) as db:
        return db.execute(
            "SELECT COUNT(*) FROM records WHERE kind=?", (kind,)
        ).fetchone()[0]


class A251AllStagedChatWritersTests(unittest.TestCase):
    def test_01_normal_archive_attachment_checkpoint_and_summary(self):
        with TemporaryDirectory(prefix="a251-normal-") as raw:
            path = Path(raw) / "chat.db"
            db = SQLiteChatStore(path)
            try:
                c, m = _seed(db)
                attachment = _attachment(c.id)
                db.add_attachment_metadata(SCOPE, attachment)
                checkpoint = ConversationCheckpoint(c.id, through_sequence=1)
                self.assertIsNone(db.save_checkpoint(SCOPE, checkpoint))
                summary = ContextSummary(
                    c.id, through_sequence=1, content="one summary",
                    source_message_ids=[m.id],
                )
                self.assertIsNone(db.save_context_summary(SCOPE, summary))
                archived = db.archive_conversation(SCOPE, c.id)
                self.assertTrue(archived.archived)
                self.assertEqual(db.get_attachment(SCOPE, c.id, attachment.id).id, attachment.id)
                self.assertEqual(db.get_latest_checkpoint(SCOPE, c.id).id, checkpoint.id)
                self.assertEqual(db.get_latest_summary(SCOPE, c.id).id, summary.id)
                self.assertEqual(db.get_conversation(SCOPE, c.id).latest_checkpoint, checkpoint.id)
                self.assertFalse(_marker(path).exists())
                self.assertEqual(db.require_healthy()["state"], HEALTHY)
            finally:
                db.close()
            reopened = SQLiteChatStore(path)
            try:
                self.assertTrue(reopened.get_conversation(SCOPE, c.id).archived)
            finally:
                reopened.close()
            self.assertEqual(_record_count(path, "attachment"), 1)
            self.assertEqual(_record_count(path, "checkpoint"), 1)
            self.assertEqual(_record_count(path, "summary"), 1)

    def test_02_each_writer_fences_real_commit_with_lost_ack(self):
        for operation in ("archive", "attachment", "checkpoint", "summary"):
            with self.subTest(operation=operation), TemporaryDirectory(
                prefix="a251-" + operation + "-"
            ) as raw:
                path = Path(raw) / "chat.db"
                db = SQLiteChatStore(path)
                c, m = _seed(db)
                attachment = _attachment(c.id, operation)
                checkpoint = ConversationCheckpoint(c.id, through_sequence=1)
                summary = ContextSummary(
                    c.id, through_sequence=1, content="uncertain",
                    source_message_ids=[m.id],
                )
                db.db = LostAckConnection(db.db, after_commit=True)
                try:
                    with self.assertRaisesRegex(
                        StoreCommitOutcomeUncertainError, "COMMIT outcome unknown"
                    ):
                        if operation == "archive":
                            db.archive_conversation(SCOPE, c.id)
                        elif operation == "attachment":
                            db.add_attachment_metadata(SCOPE, attachment)
                        elif operation == "checkpoint":
                            db.save_checkpoint(SCOPE, checkpoint)
                        else:
                            db.save_context_summary(SCOPE, summary)
                    self.assertEqual(db._health_state, FAILED)
                    self.assertTrue(_marker(path).is_file())
                    with self.assertRaises(StorageUnavailableError):
                        db.create_conversation(SCOPE, "no retry")
                finally:
                    db.close()
                with closing(sqlite3.connect(str(path))) as check:
                    if operation == "archive":
                        self.assertTrue(check.execute(
                            "SELECT archived FROM conversations WHERE id=?", (c.id,)
                        ).fetchone()[0])
                    else:
                        self.assertEqual(
                            check.execute(
                                "SELECT COUNT(*) FROM records WHERE kind=?", (operation,)
                            ).fetchone()[0],
                            1,
                        )
                with mock.patch("aion_chat.store.sqlite3.connect") as connect:
                    with self.assertRaises(StorageUnavailableError):
                        SQLiteChatStore(path)
                    connect.assert_not_called()

    def test_03_validation_and_wrong_scope_fail_before_commit(self):
        with TemporaryDirectory(prefix="a251-precommit-") as raw:
            path = Path(raw) / "chat.db"
            db = SQLiteChatStore(path)
            try:
                c, m = _seed(db)
                wrong = Scope("other-owner", SCOPE.tenant_id, SCOPE.workspace_id)
                with self.assertRaises(LookupError):
                    db.archive_conversation(wrong, c.id)
                bad_attachment = _attachment(c.id)
                bad_attachment.name = "../unsafe.txt"
                with self.assertRaises(ValueError):
                    db.add_attachment_metadata(SCOPE, bad_attachment)
                good = ConversationCheckpoint(c.id, through_sequence=1)
                db.save_checkpoint(SCOPE, good)
                with self.assertRaises(ValueError):
                    db.save_checkpoint(
                        SCOPE, ConversationCheckpoint(c.id, through_sequence=1),
                    )
                with self.assertRaises(LookupError):
                    db.save_context_summary(
                        SCOPE, ContextSummary(
                            c.id, through_sequence=1, content="bad",
                            source_message_ids=["missing-message"],
                        ),
                    )
                self.assertFalse(_marker(path).exists())
                self.assertEqual(db.require_healthy()["state"], HEALTHY)
                self.assertFalse(db.get_conversation(SCOPE, c.id).archived)
            finally:
                db.close()

    def test_04_real_subprocess_exits_after_archive_commit(self):
        with TemporaryDirectory(prefix="a251-crash-") as raw:
            path = Path(raw) / "chat.db"
            db = SQLiteChatStore(path)
            c, _ = _seed(db)
            db.close()
            script = """
import os, sys
from pathlib import Path
from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
path=Path(sys.argv[1])
store=SQLiteChatStore(path)
store._clear_message_commit_marker=lambda: os._exit(75)
store.archive_conversation(
    Scope("owner-a251", "tenant-a251", "workspace-a251"), sys.argv[2]
)
os._exit(91)
"""
            proc = subprocess.run(
                [sys.executable, "-B", "-c", script, str(path), c.id],
                capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(proc.returncode, 75, (proc.stdout, proc.stderr))
            with closing(sqlite3.connect(str(path))) as check:
                self.assertEqual(check.execute(
                    "SELECT archived FROM conversations WHERE id=?", (c.id,)
                ).fetchone()[0], 1)
            self.assertTrue(_marker(path).is_file())
            with self.assertRaises(StorageUnavailableError):
                SQLiteChatStore(path)

    def test_05_cross_process_checkpoint_and_summary_writers(self):
        with TemporaryDirectory(prefix="a251-multiprocess-") as raw:
            path = Path(raw) / "chat.db"
            db = SQLiteChatStore(path)
            c, m = _seed(db)
            db.close()
            script = """
import sys
from pathlib import Path
from aion_chat.models import ContextSummary, Scope
from aion_chat.store import SQLiteChatStore
path, cid, mid, worker = Path(sys.argv[1]), sys.argv[2], sys.argv[3], sys.argv[4]
store=SQLiteChatStore(path)
scope=Scope("owner-a251", "tenant-a251", "workspace-a251")
try:
    for i in range(4):
        store.save_context_summary(scope, ContextSummary(
            cid, through_sequence=1,
            content=f"worker-{worker}-{i}", source_message_ids=[mid],
        ))
finally:
    store.close()
"""
            workers = [
                subprocess.Popen(
                    [sys.executable, "-B", "-c", script, str(path), c.id, m.id, str(i)],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                )
                for i in range(3)
            ]
            try:
                for worker in workers:
                    out, err = worker.communicate(timeout=35)
                    self.assertEqual(worker.returncode, 0, (out, err))
            finally:
                for worker in workers:
                    if worker.poll() is None:
                        worker.kill()
                        worker.communicate(timeout=5)
            self.assertEqual(_record_count(path, "summary"), 12)
            self.assertFalse(_marker(path).exists())

    def test_06_public_write_routes_use_shared_guard(self):
        """Explicit contract regression; private raw SQLite writes still possible."""
        for name in (
            "create_conversation", "append_message", "archive_conversation",
            "add_attachment_metadata", "save_checkpoint", "save_context_summary",
        ):
            with self.subTest(method=name):
                source = inspect.getsource(getattr(SQLiteChatStore, name))
                self.assertIn("@_local_commit_gate", source)
                self.assertNotIn("with self.db:", source)
                self.assertTrue(
                    "_fenced_chat_transaction" in source
                    or "_commit_fenced_chat_write" in source
                )

    @unittest.expectedFailure
    def test_07_red_local_marker_not_independent_of_host_deletion(self):
        """Other P0 tests already show host tamper; do not overclaim A251."""
        with TemporaryDirectory(prefix="a251-hostred-") as raw:
            path = Path(raw) / "chat.db"
            db = SQLiteChatStore(path)
            c, _ = _seed(db)
            db.db = LostAckConnection(db.db, after_commit=True)
            try:
                with self.assertRaises(StoreCommitOutcomeUncertainError):
                    db.archive_conversation(SCOPE, c.id)
            finally:
                db.close()
            _marker(path).unlink()
            # Desired independent veto; actual host can delete this file.
            with self.assertRaises(StorageUnavailableError):
                reopened = SQLiteChatStore(path)
                reopened.close()


if __name__ == "__main__":
    unittest.main()
