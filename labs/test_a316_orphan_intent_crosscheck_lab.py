"""A316 LAB: local receipt/message cross-check and its same-host limits.

Every write is in a disposable SQLite fixture. No external provider/Worker,
deployment, real client data, paid service, restore, or authorized resend.
"""
from contextlib import closing
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from aion_chat.models import Message, Scope
from aion_chat.store import (
    FAILED, SQLiteChatStore, StorageUnavailableError,
)

SCOPE = Scope("a316-lab-owner", "a316-lab-tenant", "a316-lab-workspace")


def _count(path, table):
    assert table in ("messages", "a315_local_intent_receipts")
    with closing(sqlite3.connect(str(path))) as reader:
        return reader.execute("SELECT COUNT(*) FROM " + table).fetchone()[0]


class A316LocalReceiptMessageCrosscheckTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = TemporaryDirectory(prefix="a315-lab-a316-")
        self.addCleanup(self.tempdir.cleanup)
        self.path = Path(self.tempdir.name) / "synthetic.db"
        (self.path.parent / ".a315-synthetic-only").write_text(
            "A315 DISPOSABLE SYNTHETIC LAB ONLY\n", encoding="utf-8"
        )
        self.store = self.open_store()
        self.cid = self.store.create_conversation(
            SCOPE, "A315 TEST A316 synthetic conversation",
        ).id

    def open_store(self):
        store = SQLiteChatStore(
            self.path, strict_local_data_version=True,
            strict_private_write_helpers=True,
            strict_sql_authorizer=True, strict_semantic_intent=True,
        )
        self.addCleanup(store.close)
        return store

    def append(self, *, intent="A316-one", transport="A316-transport-A",
               cid=None, scope=SCOPE, content="A315 TEST one local intent"):
        return self.store.append_message_once(
            scope,
            Message(cid or self.cid, "user", content, id=transport),
            intent_id=intent,
        )

    def assert_no_real_authority(self, report):
        self.assertEqual(report["p0_homologated"], 0)
        self.assertTrue(report["hard_no_go"])
        self.assertTrue(report["zero_auto_resend"])
        self.assertFalse(report["independent_custody"])
        self.assertFalse(report["external_semantic_exactly_once"])
        self.assertFalse(report["provider_outcome_proven"])
        self.assertFalse(report["can_resume"])
        self.assertFalse(report["can_resend"])
        self.assertFalse(report["can_auto_retry"])
        self.assertFalse(report["can_authorize_real_effect"])
        self.assertEqual(report["automatic_retries"], 0)

    def test_message_and_receipt_store_the_same_intent_and_digest(self):
        report = self.append()
        self.assertEqual(report["status"], "LOCAL_ACKED_ONCE")
        with closing(sqlite3.connect(str(self.path))) as reader:
            raw = reader.execute(
                "SELECT data FROM messages WHERE id=?",
                (report["message_id"],),
            ).fetchone()[0]
            row = reader.execute(
                "SELECT intent_id,payload_digest,message_id "
                "FROM a315_local_intent_receipts"
            ).fetchone()
        metadata = json.loads(raw)["metadata"]
        self.assertEqual(metadata["a316_semantic_intent_id"], row[0])
        self.assertEqual(metadata["a316_payload_digest"], row[1])
        self.assertEqual(report["local_payload_digest"], row[1])
        self.assertEqual(row[2], report["message_id"])
        self.assert_no_real_authority(report)

    def test_replay_with_new_transport_still_does_not_write(self):
        first = self.append()
        second = self.append(transport="A316-transport-B")
        self.assertEqual(second["status"], "DUPLICATE_LOCAL_NO_EFFECT")
        self.assertEqual(second["message_id"], first["message_id"])
        self.assertEqual(_count(self.path, "messages"), 1)
        self.assertEqual(_count(self.path, "a315_local_intent_receipts"), 1)
        self.assert_no_real_authority(second)

    def test_replay_after_restart_preserves_trace(self):
        first = self.append()
        self.store.close()
        self.store = self.open_store()
        replay = self.append(transport="A316-transport-C")
        self.assertEqual(replay["status"], "DUPLICATE_LOCAL_NO_EFFECT")
        self.assertEqual(replay["message_id"], first["message_id"])
        self.assertEqual(_count(self.path, "messages"), 1)

    def test_receipt_only_deletion_is_sticky_veto_across_restart(self):
        self.append()
        self.store.close()
        with closing(sqlite3.connect(str(self.path))) as attacker:
            attacker.execute("DELETE FROM a315_local_intent_receipts")
            attacker.commit()
        self.store = self.open_store()
        with self.assertRaises(StorageUnavailableError):
            self.append(transport="A316-transport-B")
        self.assertEqual(
            self.store._health_reason,
            "A316_LOCAL_INTENT_RECEIPT_MISSING_ZERO_AUTO_RETRY",
        )
        self.assertEqual(self.store._health_state, FAILED)
        self.assertEqual(_count(self.path, "messages"), 1)
        self.assertEqual(_count(self.path, "a315_local_intent_receipts"), 0)
        with self.assertRaises(StorageUnavailableError):
            self.append(transport="A316-transport-C")

    def test_orphan_in_another_conversation_same_scope_is_found(self):
        original = self.append()
        self.store.close()
        with closing(sqlite3.connect(str(self.path))) as attacker:
            attacker.execute(
                "DELETE FROM a315_local_intent_receipts WHERE intent_id=?",
                ("A316-one",),
            )
            attacker.commit()
        self.store = self.open_store()
        other = self.store.create_conversation(
            SCOPE, "A315 TEST another conversation"
        ).id
        with self.assertRaises(StorageUnavailableError):
            self.append(cid=other, transport="A316-other-CID")
        self.assertEqual(
            self.store._health_reason,
            "A316_LOCAL_INTENT_RECEIPT_MISSING_ZERO_AUTO_RETRY",
        )
        self.assertEqual(original["status"], "LOCAL_ACKED_ONCE")
        self.assertEqual(_count(self.path, "messages"), 1)

    def test_another_scope_does_not_inherit_orphan_veto(self):
        self.append()
        self.store.close()
        with closing(sqlite3.connect(str(self.path))) as attacker:
            attacker.execute("DELETE FROM a315_local_intent_receipts")
            attacker.commit()
        self.store = self.open_store()
        other = Scope("a316-lab-owner", "a316-second-tenant",
                      "a316-lab-workspace")
        other_cid = self.store.create_conversation(
            other, "A315 TEST other tenant"
        ).id
        second = self.append(
            scope=other, cid=other_cid, transport="A316-second-tenant"
        )
        self.assertEqual(second["status"], "LOCAL_ACKED_ONCE")
        self.assertEqual(_count(self.path, "messages"), 2)

    def test_receipt_present_but_message_metadata_scrubbed_is_denied(self):
        self.append()
        self.store.close()
        with closing(sqlite3.connect(str(self.path))) as attacker:
            raw = attacker.execute(
                "SELECT data FROM messages WHERE id=?",
                ("A316-transport-A",),
            ).fetchone()[0]
            record = json.loads(raw)
            record["metadata"].pop("a316_semantic_intent_id")
            attacker.execute(
                "UPDATE messages SET data=? WHERE id=?",
                (json.dumps(record), "A316-transport-A"),
            )
            attacker.commit()
        self.store = self.open_store()
        with self.assertRaises(StorageUnavailableError):
            self.append(transport="A316-transport-B")
        self.assertEqual(
            self.store._health_reason,
            "A315_LOCAL_INTENT_RECEIPT_DIVERGED",
        )
        self.assertEqual(_count(self.path, "messages"), 1)

    def test_receipt_present_but_digest_scrubbed_is_denied(self):
        self.append()
        self.store.close()
        with closing(sqlite3.connect(str(self.path))) as attacker:
            raw = attacker.execute(
                "SELECT data FROM messages WHERE id=?",
                ("A316-transport-A",),
            ).fetchone()[0]
            record = json.loads(raw)
            record["metadata"]["a316_payload_digest"] = "0" * 64
            attacker.execute(
                "UPDATE messages SET data=? WHERE id=?",
                (json.dumps(record), "A316-transport-A"),
            )
            attacker.commit()
        self.store = self.open_store()
        with self.assertRaises(StorageUnavailableError):
            self.append(transport="A316-transport-B")
        self.assertEqual(
            self.store._health_reason,
            "A315_LOCAL_INTENT_RECEIPT_DIVERGED",
        )

    def test_receipt_and_message_trace_scrubbed_can_still_duplicate(self):
        """The same host owns BOTH local traces: P0-3 remains open."""
        first = self.append()
        self.store.close()
        with closing(sqlite3.connect(str(self.path))) as attacker:
            data = json.loads(attacker.execute(
                "SELECT data FROM messages WHERE id=?",
                (first["message_id"],),
            ).fetchone()[0])
            data["metadata"].pop("a316_semantic_intent_id", None)
            data["metadata"].pop("a316_payload_digest", None)
            attacker.execute(
                "UPDATE messages SET data=? WHERE id=?",
                (json.dumps(data), first["message_id"]),
            )
            attacker.execute(
                "DELETE FROM a315_local_intent_receipts WHERE intent_id=?",
                ("A316-one",),
            )
            attacker.commit()
        self.store = self.open_store()
        duplicate = self.append(transport="A316-transport-B")
        self.assertEqual(duplicate["status"], "LOCAL_ACKED_ONCE")
        self.assertEqual(_count(self.path, "messages"), 2)
        self.assertEqual(_count(self.path, "a315_local_intent_receipts"), 1)
        self.assertFalse(duplicate["independent_custody"])
        self.assert_no_real_authority(duplicate)

    def test_receipt_only_removal_does_not_publish_second_marker(self):
        self.append()
        self.store.close()
        with closing(sqlite3.connect(str(self.path))) as attacker:
            attacker.execute("DELETE FROM a315_local_intent_receipts")
            attacker.commit()
        self.store = self.open_store()
        from unittest import mock
        with mock.patch.object(
            self.store, "_publish_message_commit_marker",
            wraps=self.store._publish_message_commit_marker
        ) as spy:
            with self.assertRaises(StorageUnavailableError):
                self.append(transport="A316-no-marker")
        spy.assert_not_called()
        self.assertFalse(self.store._message_commit_marker.exists())

    def test_different_intent_is_still_allowed(self):
        self.append()
        different = self.append(
            intent="A316-other", transport="A316-transport-B",
            content="A315 TEST a separate local request"
        )
        self.assertEqual(different["status"], "LOCAL_ACKED_ONCE")
        self.assertEqual(_count(self.path, "messages"), 2)

    def test_caller_supplied_metadata_is_still_not_trusted(self):
        from aion_chat.models import Message
        with self.assertRaises(ValueError):
            self.store.append_message_once(
                SCOPE,
                Message(
                    self.cid, "user", "A315 TEST forged source",
                    id="forged-transport",
                    metadata={"a316_semantic_intent_id": "A316-one"},
                ),
                intent_id="A316-one",
            )
        self.assertEqual(_count(self.path, "messages"), 0)


if __name__ == "__main__":
    unittest.main()
