"""A315: real SQLite semantic intent once across restarts, LAB ONLY.

Test a tangible local P0-3 improvement and deliberately demonstrate that
the host can still roll back local custody. 0/6 P0 operationally homologated.
"""
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest import mock

from aion_chat.models import Message, Scope
from aion_chat.store import (
    FAILED, SQLiteChatStore, StorageUnavailableError,
    StoreCommitOutcomeUncertainError,
)
from labs.a291_chat_write_gate_commit_fence_lab import (
    SyntheticAckLossConnection,
)

SCOPE = Scope("a315-synthetic-owner", "a315-synthetic-tenant",
              "a315-synthetic-workspace")
MARKER = ".a315-synthetic-only"
MARKER_CONTENT = "A315 DISPOSABLE SYNTHETIC LAB ONLY\n"

CHILD = """
import json,sys
from aion_chat.models import Message,Scope
from aion_chat.store import SQLiteChatStore
db,conversation,intent,transport,body = sys.argv[1:]
scope=Scope("a315-synthetic-owner","a315-synthetic-tenant",
            "a315-synthetic-workspace")
store=SQLiteChatStore(
    db,strict_local_data_version=True,
    strict_private_write_helpers=True,strict_sql_authorizer=True,
    strict_semantic_intent=True)
try:
    result=store.append_message_once(
        scope,Message(conversation,"user",body,id=transport),
        intent_id=intent)
    print(json.dumps(result,sort_keys=True))
finally:
    store.close()
"""


def sqlite_count(path, table):
    assert table in ("messages", "a315_local_intent_receipts")
    with closing(sqlite3.connect(str(path))) as conn:
        return conn.execute("SELECT COUNT(*) FROM " + table).fetchone()[0]


class A315AtomicSemanticIntentTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory(prefix="a315-lab-")
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        (self.folder / MARKER).write_text(MARKER_CONTENT, encoding="utf-8")
        self.path = self.folder / "only-synthetic.sqlite"
        self.store = self.open_store()

    def open_store(self):
        store = SQLiteChatStore(
            self.path, strict_local_data_version=True,
            strict_private_write_helpers=True, strict_sql_authorizer=True,
            strict_semantic_intent=True,
        )
        self.addCleanup(store.close)
        return store

    def seed(self, scope=SCOPE):
        return self.store.create_conversation(
            scope, "A315 TEST synthetic conversation"
        ).id

    def append(self, cid, intent="semantic-1", message="transport-A",
               content="A315 TEST no external provider", scope=SCOPE):
        return self.store.append_message_once(
            scope, Message(cid, "user", content, id=message),
            intent_id=intent,
        )

    def assert_hard_no_go(self, r):
        self.assertTrue(r["local_sqlite_only"])
        self.assertFalse(r["independent_custody"])
        self.assertFalse(r["provider_outcome_proven"])
        self.assertFalse(r["external_semantic_exactly_once"])
        self.assertFalse(r["can_authorize_real_effect"])
        self.assertFalse(r["can_resume"])
        self.assertFalse(r["can_resend"])
        self.assertFalse(r["can_auto_retry"])
        self.assertEqual(r["automatic_retries"], 0)
        self.assertTrue(r["zero_auto_resend"])
        self.assertTrue(r["hard_no_go"])
        self.assertEqual(r["p0_homologated"], 0)

    def test_real_atomic_insert_once_and_one_local_receipt(self):
        cid = self.seed()
        first = self.append(cid)
        self.assertEqual(first["status"], "LOCAL_ACKED_ONCE")
        self.assertEqual(first["message_id"], "transport-A")
        self.assertEqual(first["sequence"], 1)
        self.assertEqual(sqlite_count(self.path, "messages"), 1)
        self.assertEqual(sqlite_count(
            self.path, "a315_local_intent_receipts"), 1)
        self.assertFalse(self.store._message_commit_marker.exists())
        self.assert_hard_no_go(first)

    def test_same_intent_new_transport_id_still_one_effect(self):
        cid = self.seed()
        first = self.append(cid, message="transport-A")
        replay = self.append(cid, message="transport-B")
        self.assertEqual(replay["status"], "DUPLICATE_LOCAL_NO_EFFECT")
        self.assertEqual(replay["message_id"], first["message_id"])
        self.assertEqual(replay["sequence"], first["sequence"])
        self.assertEqual(replay["local_payload_digest"],
                         first["local_payload_digest"])
        self.assertEqual(sqlite_count(self.path, "messages"), 1)
        self.assertEqual(sqlite_count(
            self.path, "a315_local_intent_receipts"), 1)
        self.assertFalse(self.store._message_commit_marker.exists())
        self.assert_hard_no_go(replay)

    def test_same_intent_changed_semantic_content_is_denied(self):
        cid = self.seed()
        self.append(cid)
        conflict = self.append(
            cid, message="transport-B",
            content="A315 TEST changed content",
        )
        self.assertEqual(conflict["status"], "INTENT_PAYLOAD_CONFLICT_DENIED")
        self.assertIsNone(conflict["message_id"])
        self.assertEqual(sqlite_count(self.path, "messages"), 1)
        self.assert_hard_no_go(conflict)

    def test_same_intent_other_conversation_denied_by_digest(self):
        cid = self.seed()
        other = self.seed()
        self.append(cid, intent="shared-semantic-id")
        conflict = self.append(other, intent="shared-semantic-id",
                               message="different-conversation")
        self.assertEqual(conflict["status"], "INTENT_PAYLOAD_CONFLICT_DENIED")
        self.assertEqual(sqlite_count(self.path, "messages"), 1)

    def test_distinct_semantic_ids_each_have_one_effect(self):
        cid = self.seed()
        a = self.append(cid, intent="semantic-a", message="transport-A")
        b = self.append(cid, intent="semantic-b", message="transport-B")
        self.assertEqual([a["sequence"], b["sequence"]], [1, 2])
        self.assertEqual(sqlite_count(self.path, "messages"), 2)
        self.assertEqual(sqlite_count(
            self.path, "a315_local_intent_receipts"), 2)

    def test_same_intent_other_scope_does_not_cross_tenants(self):
        cid = self.seed()
        other_scope = Scope(
            "a315-synthetic-owner", "a315-different-tenant",
            "a315-synthetic-workspace",
        )
        other_cid = self.seed(other_scope)
        a = self.append(cid, intent="intent-across-scopes")
        b = self.append(
            other_cid, intent="intent-across-scopes",
            message="transport-B", scope=other_scope,
        )
        self.assertEqual(a["status"], "LOCAL_ACKED_ONCE")
        self.assertEqual(b["status"], "LOCAL_ACKED_ONCE")
        self.assertEqual(sqlite_count(self.path, "messages"), 2)

    def test_reopen_after_local_ack_preserves_semantic_intent(self):
        cid = self.seed()
        original = self.append(cid)
        self.store.close()
        self.store = self.open_store()
        replay = self.append(cid, message="after-restart-ID")
        self.assertEqual(replay["status"], "DUPLICATE_LOCAL_NO_EFFECT")
        self.assertEqual(replay["message_id"], original["message_id"])
        self.assertEqual(sqlite_count(self.path, "messages"), 1)

    def test_fresh_python_process_replay_is_rejected(self):
        cid = self.seed()
        self.append(cid)
        self.store.close()
        completed = subprocess.run(
            [sys.executable, "-c", CHILD, str(self.path), cid,
             "semantic-1", "fresh-process-id",
             "A315 TEST no external provider"],
            capture_output=True, text=True, check=False, timeout=15,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        response = json.loads(completed.stdout)
        self.assertEqual(response["status"], "DUPLICATE_LOCAL_NO_EFFECT")
        self.assertEqual(response["message_id"], "transport-A")
        self.assertEqual(sqlite_count(self.path, "messages"), 1)
        self.assert_hard_no_go(response)

    def test_lost_ack_after_real_commit_is_sticky_and_never_retried(self):
        cid = self.seed()
        self.store.close()
        actual = sqlite3.connect

        def synthetic_connect(*args, **kwargs):
            return actual(*args, **kwargs,
                          factory=SyntheticAckLossConnection)

        with mock.patch("aion_chat.store.sqlite3.connect",
                        side_effect=synthetic_connect):
            self.store = self.open_store()
        self.store.db.fault_once = "after"
        with self.assertRaises(StoreCommitOutcomeUncertainError):
            self.append(cid, intent="unknown-ack",
                        message="one-real-sqlite-commit")
        self.assertEqual(
            self.store._health_reason, "COMMIT_OUTCOME_UNKNOWN_ZERO_AUTO_RETRY"
        )
        self.assertTrue(self.store._message_commit_marker.exists())
        self.assertEqual(sqlite_count(self.path, "messages"), 1)
        self.assertEqual(sqlite_count(
            self.path, "a315_local_intent_receipts"), 1)
        with self.assertRaises(StorageUnavailableError):
            self.append(cid, intent="unknown-ack",
                        message="auto-retry-forbidden")
        self.assertEqual(sqlite_count(self.path, "messages"), 1)
        self.store.close()
        with self.assertRaises(StorageUnavailableError):
            self.open_store()

    def test_duplicate_does_not_publish_new_commit_marker(self):
        cid = self.seed()
        self.append(cid)
        with mock.patch.object(
            self.store, "_publish_message_commit_marker",
            wraps=self.store._publish_message_commit_marker,
        ) as publish:
            answer = self.append(cid, message="no-extra-marker")
        self.assertEqual(answer["status"], "DUPLICATE_LOCAL_NO_EFFECT")
        publish.assert_not_called()

    def test_conflict_does_not_publish_new_commit_marker(self):
        cid = self.seed()
        self.append(cid)
        with mock.patch.object(
            self.store, "_publish_message_commit_marker",
            wraps=self.store._publish_message_commit_marker,
        ) as publish:
            answer = self.append(cid, message="other-ID",
                                 content="A315 TEST tampered payload")
        self.assertEqual(answer["status"], "INTENT_PAYLOAD_CONFLICT_DENIED")
        publish.assert_not_called()

    def test_direct_old_append_api_sticky_veto_in_strict_mode(self):
        cid = self.seed()
        with self.assertRaises(StorageUnavailableError):
            self.store.append_message(
                SCOPE, Message(cid, "user", "A315 TEST attempted bypass")
            )
        self.assertEqual(self.store._health_state, FAILED)
        self.assertEqual(self.store._health_reason,
                         "SEMANTIC_INTENT_REQUIRED_ZERO_AUTO_RETRY")
        self.assertEqual(sqlite_count(self.path, "messages"), 0)

    def test_unmarked_path_rejected_before_db_created(self):
        self.store.close()
        with TemporaryDirectory(prefix="a315-lab-") as other:
            dest = Path(other) / "not-authorized.sqlite"
            with self.assertRaises(StorageUnavailableError):
                SQLiteChatStore(
                    dest, strict_private_write_helpers=True,
                    strict_sql_authorizer=True, strict_semantic_intent=True,
                )
            self.assertFalse(dest.exists())

    def test_other_prefix_even_with_marker_rejected(self):
        self.store.close()
        with TemporaryDirectory(prefix="not-a315-") as other:
            path = Path(other) / "db.sqlite"
            (Path(other) / MARKER).write_text(
                MARKER_CONTENT, encoding="utf-8",
            )
            with self.assertRaises(StorageUnavailableError):
                SQLiteChatStore(
                    path, strict_private_write_helpers=True,
                    strict_sql_authorizer=True, strict_semantic_intent=True,
                )
            self.assertFalse(path.exists())

    def test_flags_fail_closed_when_combination_invalid(self):
        self.store.close()
        for kwargs in (
            {"strict_semantic_intent": True},
            {"strict_semantic_intent": True,
             "strict_private_write_helpers": True},
            {"strict_semantic_intent": True,
             "strict_sql_authorizer": True},
        ):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ValueError):
                    SQLiteChatStore(self.path, **kwargs)

    def test_invalid_flag_types_are_rejected(self):
        self.store.close()
        for value in (None, 1, 0, "true", {}, []):
            with self.subTest(value=repr(value)):
                with self.assertRaises(TypeError):
                    SQLiteChatStore(
                        self.path, strict_semantic_intent=value,
                    )

    def test_legacy_append_behavior_unchanged_when_optin_off(self):
        self.store.close()
        legacy = SQLiteChatStore(self.path)
        try:
            cid = legacy.create_conversation(SCOPE, "legacy")
            m = legacy.append_message(
                SCOPE, Message(cid.id, "user", "legacy content",
                               id="legacy-msg"),
            )
            self.assertEqual(m.id, "legacy-msg")
        finally:
            legacy.close()

    def test_intent_key_types_and_missing_id_are_denied(self):
        cid = self.seed()
        for bad in (None, True, 0, "", "!", [], {}, "x" * 81):
            with self.subTest(bad=repr(bad)):
                with self.assertRaises(ValueError):
                    self.append(cid, intent=bad)
        self.assertEqual(sqlite_count(self.path, "messages"), 0)

    def test_non_synthetic_or_malformed_message_is_rejected(self):
        cid = self.seed()
        messages = [
            Message(cid, "assistant", "A315 TEST correct prefix"),
            Message(cid, "user", "real customer data"),
            Message(cid, "user", "A315 TEST okay", attachments=["a"]),
            Message(cid, "user", "A315 TEST okay",
                    metadata={"internal": "bypass"}),
            Message(cid, "user", "A315 TEST okay", task_metadata={}),
        ]
        for msg in messages:
            with self.subTest(msg=repr(msg)):
                with self.assertRaises(ValueError):
                    self.store.append_message_once(
                        SCOPE, msg, intent_id="synthetic-intent"
                    )
        self.assertEqual(sqlite_count(self.path, "messages"), 0)

    def test_message_id_unique_collision_fails_closed(self):
        cid = self.seed()
        self.append(cid, intent="one", message="same-transport")
        with self.assertRaises(StorageUnavailableError):
            self.append(cid, intent="two", message="same-transport")
        self.assertEqual(
            self.store._health_reason,
            "A315_SQLITE_CONSTRAINT_DENIED_NO_RETRY",
        )
        self.assertEqual(sqlite_count(self.path, "messages"), 1)
        self.assertEqual(sqlite_count(
            self.path, "a315_local_intent_receipts"), 1)

    def test_deleted_local_receipt_quarantines_orphan_after_restart(self):
        """A316: receipt-only loss is detected using message-side intent."""
        cid = self.seed()
        self.append(cid, message="message-A")
        self.store.close()
        with closing(sqlite3.connect(str(self.path))) as attacker:
            attacker.execute(
                "DELETE FROM a315_local_intent_receipts "
                "WHERE intent_id=?", ("semantic-1",)
            )
            attacker.commit()
        self.store = self.open_store()
        with self.assertRaises(StorageUnavailableError):
            self.append(cid, message="message-B")
        self.assertEqual(self.store._health_state, FAILED)
        self.assertEqual(
            self.store._health_reason,
            "A316_LOCAL_INTENT_RECEIPT_MISSING_ZERO_AUTO_RETRY",
        )
        self.assertEqual(sqlite_count(self.path, "messages"), 1)
        self.assertEqual(sqlite_count(
            self.path, "a315_local_intent_receipts"), 0)

    def test_corrupt_message_content_diverging_from_receipt_fails_closed(self):
        cid = self.seed()
        self.append(cid)
        self.store.close()
        with closing(sqlite3.connect(str(self.path))) as attacker:
            attacker.execute(
                "UPDATE messages SET content=? WHERE id=?",
                ("A315 TEST tampered content", "transport-A"),
            )
            attacker.commit()
        self.store = self.open_store()
        with self.assertRaises(StorageUnavailableError):
            self.append(cid, message="would-be-retry")
        self.assertEqual(self.store._health_state, FAILED)
        self.assertEqual(
            self.store._health_reason, "A315_LOCAL_INTENT_RECEIPT_DIVERGED"
        )
        self.assertEqual(sqlite_count(self.path, "messages"), 1)


if __name__ == "__main__":
    unittest.main()
