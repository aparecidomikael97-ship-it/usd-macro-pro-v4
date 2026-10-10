"""Real-SQLite unit/fault tests; full product-flow inversions run separately."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager, closing
from pathlib import Path
import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from aion_chat.models import Message, Scope
from aion_chat.staged_store import OperationScopedSQLiteChatStore
from aion_chat.store import SQLiteChatStore, StorageUnavailableError
import atlasquant_aion_chat_request_binding as binding


AUTH = {"session": {"credential_fingerprint": "unit-fixture-only"}}
SCOPE = Scope("unit-owner", "tenant-a", "workspace-a")


def descriptors(ticket):
    metadata = {"turn_id": "TURN-" + ticket["input_digest"],
                "identity_binding_digest": "b" * 64}
    return (Message(ticket["conversation_id"], "user", "unit input", metadata=dict(metadata)),
            Message(ticket["conversation_id"], "assistant", "unit output", metadata=dict(metadata), truth_state="UNKNOWN"))


@contextmanager
def test_db(path):
    with closing(sqlite3.connect(path)) as db:
        with db:
            yield db


class BrowserBindingUnitTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "chat.sqlite3"
        self.store = OperationScopedSQLiteChatStore(self.path)
        self.addCleanup(self.store.close)
        self.digests = binding.request_digests(SCOPE, AUTH, "unit input")

    def reserve(self, rid="request-a", cid="", *, scope=SCOPE, digests=None):
        return binding.reserve_request(self.store, scope, rid, cid, cid, *(digests or self.digests))

    def prepare(self, ticket):
        pair = descriptors(ticket)
        binding.bind_expected_pair(self.path, SCOPE, ticket, *pair)
        return pair

    def persist(self, pair):
        for message in pair:
            self.store.append_message(SCOPE, message)

    def count(self, cid):
        with test_db(self.path) as db:
            return db.execute("SELECT count(*) FROM messages WHERE cid=?", (cid,)).fetchone()[0]

    def test_complete_pair_replay_has_two_rows_and_no_new_permit(self):
        ticket = self.reserve()
        self.persist(self.prepare(ticket))
        self.assertTrue(binding.reconcile_request(self.path, SCOPE, ticket, completed=True)["local_history_persisted"])
        replay = self.reserve(cid=ticket["conversation_id"])
        self.assertFalse(replay["fresh"])
        self.assertNotIn("_permit", replay)
        out = binding.reconcile_request(self.path, SCOPE, replay)
        self.assertEqual(out["state"], "LOCAL_PAIR_RECONCILED")
        self.assertFalse(out["retry_authorized"])
        self.assertFalse(out["message_write_attempted"])
        self.assertEqual(self.count(ticket["conversation_id"]), 2)

    def test_partial_pair_stays_blocked_and_cannot_be_completed_automatically(self):
        ticket = self.reserve()
        pair = self.prepare(ticket)
        self.store.append_message(SCOPE, pair[0])
        replay = self.reserve(cid=ticket["conversation_id"])
        out = binding.reconcile_request(self.path, SCOPE, replay)
        self.assertEqual(out["state"], "BLOCKED_RECONCILIATION_REQUIRED")
        self.assertFalse(out["retry_authorized"])
        self.assertEqual(self.count(ticket["conversation_id"]), 1)
        with self.assertRaises(StorageUnavailableError):
            binding.bind_expected_pair(self.path, SCOPE, replay, *pair)
        with self.assertRaises(StorageUnavailableError):
            self.reserve("another-request", ticket["conversation_id"])

    def test_prepared_absence_never_becomes_permission_to_retry(self):
        ticket = self.reserve()
        self.prepare(ticket)
        replay = self.reserve(cid=ticket["conversation_id"])
        self.assertEqual(binding.reconcile_request(self.path, SCOPE, replay)["state"], "BLOCKED_RECONCILIATION_REQUIRED")
        self.assertEqual(self.count(ticket["conversation_id"]), 0)

    def test_admitted_but_unprepared_crash_stays_blocked(self):
        ticket = self.reserve()
        replay = self.reserve(cid=ticket["conversation_id"])
        self.assertEqual(binding.reconcile_request(self.path, SCOPE, replay)["state"], "BLOCKED_RECONCILIATION_REQUIRED")
        self.assertEqual(self.count(ticket["conversation_id"]), 0)

    def test_same_request_changed_content_or_credential_is_rejected(self):
        ticket = self.reserve()
        for digests in (("0" * 64, self.digests[1]), (self.digests[0], "0" * 64)):
            with self.subTest(digests=digests), self.assertRaises(ValueError):
                self.reserve(cid=ticket["conversation_id"], digests=digests)
        self.assertEqual(self.count(ticket["conversation_id"]), 0)

    def test_same_request_changed_conversation_is_rejected(self):
        ticket = self.reserve()
        other = self.store.create_conversation(SCOPE).id
        with self.assertRaises(ValueError):
            self.reserve(cid=other)
        self.assertEqual(self.count(ticket["conversation_id"]), 0)

    def test_wrong_tenant_owner_workspace_cannot_read_or_bind_other_conversation(self):
        ticket = self.reserve()
        self.persist(self.prepare(ticket))
        for scope in (Scope("other-owner", "tenant-a", "workspace-a"),
                      Scope("unit-owner", "tenant-b", "workspace-a"),
                      Scope("unit-owner", "tenant-a", "workspace-b")):
            with self.subTest(scope=scope), self.assertRaises(LookupError):
                self.reserve(scope=scope, cid=ticket["conversation_id"])
        self.assertEqual(self.count(ticket["conversation_id"]), 2)

    def test_same_request_id_is_independent_in_other_tenant(self):
        first = self.reserve()
        other_scope = Scope("unit-owner", "tenant-b", "workspace-a")
        other = self.reserve(scope=other_scope, digests=binding.request_digests(other_scope, AUTH, "unit input"))
        self.assertTrue(other["fresh"])
        self.assertNotEqual(other["conversation_id"], first["conversation_id"])

    def test_concurrent_same_request_has_only_one_first_attempt(self):
        with ThreadPoolExecutor(max_workers=4) as pool:
            tickets = list(pool.map(lambda _: self.reserve(), range(4)))
        self.assertEqual(sum(t["fresh"] for t in tickets), 1)
        self.assertEqual(len({t["conversation_id"] for t in tickets}), 1)
        fresh = next(t for t in tickets if t["fresh"])
        self.persist(self.prepare(fresh))
        self.assertEqual(self.count(fresh["conversation_id"]), 2)

    def test_false_success_without_rows_fails_independent_readback(self):
        ticket = self.reserve()
        self.prepare(ticket)
        proof = binding.reconcile_request(self.path, SCOPE, ticket, completed=True)
        self.assertFalse(proof["local_history_persisted"])
        self.assertFalse(proof["execution_authorized"])

    def test_receipt_or_content_tamper_stays_blocked(self):
        for field in ("content", "metadata"):
            with self.subTest(field=field):
                ticket = self.reserve("tamper-" + field)
                self.persist(self.prepare(ticket))
                with test_db(self.path) as db:
                    row = db.execute("SELECT id,data FROM messages WHERE cid=? ORDER BY seq DESC LIMIT 1", (ticket["conversation_id"],)).fetchone()
                    data = json.loads(row[1])
                    if field == "content": data["content"] = "changed"
                    else: data["metadata"]["identity_binding_digest"] = "c" * 64
                    db.execute("UPDATE messages SET data=? WHERE id=?", (json.dumps(data), row[0]))
                proof = binding.reconcile_request(self.path, SCOPE, ticket)
                self.assertFalse(proof["local_history_persisted"])
                self.assertEqual(self.count(ticket["conversation_id"]), 2)

    def test_unknown_binding_state_does_not_become_success(self):
        ticket = self.reserve()
        self.persist(self.prepare(ticket))
        with test_db(self.path) as db:
            db.execute(f"UPDATE {binding.TABLE} SET state='NEW_UNKNOWN_STATE'")
        self.assertEqual(binding.reconcile_request(self.path, SCOPE, ticket)["state"], "BLOCKED_RECONCILIATION_REQUIRED")

    def test_commit_then_timeout_is_not_authorization_for_repetition(self):
        ticket = self.reserve()
        pair = self.prepare(ticket)
        original = SQLiteChatStore.append_message
        def commit_then_timeout(native, scope, message):
            original(native, scope, message)
            raise TimeoutError("fixture after actual commit")
        with patch.object(SQLiteChatStore, "append_message", commit_then_timeout):
            with self.assertRaises(TimeoutError): self.store.append_message(SCOPE, pair[0])
        replay = self.reserve(cid=ticket["conversation_id"])
        self.assertEqual(binding.reconcile_request(self.path, SCOPE, replay)["state"], "BLOCKED_RECONCILIATION_REQUIRED")
        self.assertEqual(self.count(ticket["conversation_id"]), 1)

    def test_legacy_unbound_messages_require_migration_evidence(self):
        cid = self.store.create_conversation(SCOPE).id
        self.store.append_message(SCOPE, Message(cid, "user", "legacy"))
        with self.assertRaisesRegex(StorageUnavailableError, "legacy"):
            self.reserve(cid=cid)
        self.assertEqual(self.count(cid), 1)

    def test_pending_cannot_be_cleared_with_no_write_claim(self):
        ticket = self.reserve()
        pair = self.prepare(ticket)
        self.store.append_message(SCOPE, pair[0])
        binding.finish_without_write(self.path, SCOPE, ticket)
        self.assertEqual(binding.reconcile_request(self.path, SCOPE, ticket)["state"], "BLOCKED_RECONCILIATION_REQUIRED")

    def test_no_write_preflight_is_not_success_or_retry_and_allows_new_intent(self):
        ticket = self.reserve()
        binding.finish_without_write(self.path, SCOPE, ticket)
        replay = self.reserve(cid=ticket["conversation_id"])
        proof = binding.reconcile_request(self.path, SCOPE, replay)
        self.assertEqual(proof["state"], "REQUEST_ALREADY_SEEN_NO_WRITE")
        self.assertFalse(proof["local_history_persisted"])
        self.assertFalse(proof["retry_authorized"])
        self.assertTrue(self.reserve("different-request", ticket["conversation_id"])["fresh"])

    def test_invalid_request_identity_is_rejected_before_admission(self):
        for rid in (" ", "bad\x00id", " leading", "x" * 101):
            with self.subTest(rid=rid), self.assertRaises(ValueError):
                self.reserve(rid)

    def test_real_process_exit_after_commit_or_before_assistant_commit(self):
        for after_commit in (True, False):
            with self.subTest(after_commit=after_commit):
                path = self.path.with_name("child-" + str(after_commit) + ".sqlite3")
                code = '''import os,sys
from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
import aion_chat.staged_store as staged
import atlasquant_aion_chat_request_binding as b
from tests.test_aion_browser_request_binding_units import AUTH,descriptors
s=Scope('unit-owner','tenant-a','workspace-a')
class Die(SQLiteChatStore):
 def append_message(self,scope,message):
  if message.role=='assistant' and sys.argv[2]=='False':os._exit(24)
  result=super().append_message(scope,message)
  if message.role=='assistant':os._exit(23)
  return result
staged.SQLiteChatStore=Die
store=staged.OperationScopedSQLiteChatStore(sys.argv[1])
t=b.reserve_request(store,s,'request-a','','',*b.request_digests(s,AUTH,'unit input'))
pair=descriptors(t);b.bind_expected_pair(store.path,s,t,*pair)
for m in pair:store.append_message(s,m)
'''
                p = subprocess.run([sys.executable, "-B", "-c", code, str(path), str(after_commit)],
                                   cwd=Path(__file__).resolve().parent.parent, capture_output=True, timeout=20)
                self.assertEqual(p.returncode, 23 if after_commit else 24, p.stderr.decode(errors="replace"))
                store = OperationScopedSQLiteChatStore(path)
                self.addCleanup(store.close)
                ticket = binding.reserve_request(store, SCOPE, "request-a", "", "", *self.digests)
                self.assertFalse(ticket["fresh"])
                proof = binding.reconcile_request(path, SCOPE, ticket)
                self.assertEqual(proof["local_history_persisted"], after_commit)
                with test_db(path) as db:
                    self.assertEqual(db.execute("SELECT count(*) FROM messages").fetchone()[0], 2 if after_commit else 1)


if __name__ == "__main__":
    unittest.main()
