"""P0 LAB RED-FIRST: Outbox denial must not commit a caller-owned SQLite txn.

This checks actual SQLiteChatStore + ExecutionOutbox, NOT an external provider.
A prior application BEGIN IMMEDIATE/SAVEPOINT must survive an attempted
dispatch or private pre-send denial; the Outbox must reject before any policy
callback, adapter property, mutation, COMMIT or ROLLBACK of caller work.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_execution_outbox import ExecutionOutbox

NOW = datetime(2026, 10, 21, 15, 0, tzinfo=timezone.utc)
SCOPE = Scope("owner-lab", "tenant-lab", "workspace-lab")
ERROR = "OUTBOX_NESTED_TRANSACTION_UNSUPPORTED"


class HostileAdapter:
    @property
    def send(self):
        raise AssertionError("ADAPTER_SEND_MUST_NOT_BE_INSPECTED")


class AionOutboxParentTxnDenialLab(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory(prefix="aion-p0-outbox-parent-txn-")
        self.addCleanup(tmp.cleanup)
        self.store=SQLiteChatStore(Path(tmp.name)/"outbox.sqlite3")
        self.addCleanup(self.store.close)
        self.outbox=ExecutionOutbox(self.store,SCOPE)
        self.db=self.store.db
        self.db.execute("CREATE TABLE lab_caller_state (note TEXT NOT NULL)")
        self.intent=self.outbox.enqueue(
            intent_ref="first-lab-intent", action="local_note_staging_only",
            payload={"test_only":True}, aggregate_key="single-scope",
            policy_version="lab-policy", authorization_ref="lab-approval",
            created_at=NOW, valid_until=NOW+timedelta(minutes=5),
        )
        self.key=self.intent["idempotency_key"]
        self.claimed=self.outbox.claim_next("local-worker",now=NOW,lease_seconds=60)
        self.assertIsNotNone(self.claimed)
        self.assertEqual(self.claimed["state"],"CLAIMED")
        self.assertEqual(self.claimed["idempotency_key"],self.key)

    def _denial(self, decision):
        return {"allowed":False,"reason":"LAB_POLICY_BLOCK"}

    def _dispatch(self, authorize=None):
        return self.outbox.dispatch_claimed(
            self.key,worker_id="local-worker",
            authorize=self._denial if authorize is None else authorize,
            adapter=HostileAdapter(),now=NOW+timedelta(seconds=5),
        )

    def _marker_count(self):
        return self.db.execute("SELECT COUNT(*) FROM lab_caller_state").fetchone()[0]

    def _assert_claim_untouched(self):
        row=self.outbox.get(self.key)
        self.assertEqual(row["state"],"CLAIMED")
        self.assertEqual(row["lease_owner"],"local-worker")
        self.assertEqual(row["attempts"],1)
        self.assertEqual(self.outbox.effect_count(),0)

    def test_01_dispatch_denied_auth_cannot_commit_parent_transaction(self):
        self.db.execute("BEGIN IMMEDIATE")
        self.db.execute("INSERT INTO lab_caller_state VALUES ('uncommitted')")
        with self.assertRaisesRegex(RuntimeError,ERROR):
            self._dispatch()
        self.assertTrue(self.db.in_transaction)
        self.assertEqual(self._marker_count(),1)
        self._assert_claim_untouched()
        self.db.rollback()
        self.assertEqual(self._marker_count(),0)
        self._assert_claim_untouched()

    def test_02_private_block_denies_borrowed_transaction_before_mutation(self):
        self.db.execute("BEGIN IMMEDIATE")
        self.db.execute("INSERT INTO lab_caller_state VALUES ('uncommitted')")
        with self.assertRaisesRegex(RuntimeError,ERROR):
            self.outbox._set_blocked(self.key,"REVOKED","LAB_DENIAL",
                                     expected=self.claimed)
        self.assertTrue(self.db.in_transaction)
        self.assertEqual(self._marker_count(),1)
        self._assert_claim_untouched()
        self.db.rollback()
        self.assertEqual(self._marker_count(),0)
        self._assert_claim_untouched()

    def test_03_nested_savepoint_survives_dispatch_denial(self):
        self.db.execute("BEGIN IMMEDIATE")
        self.db.execute("INSERT INTO lab_caller_state VALUES ('parent')")
        self.db.execute("SAVEPOINT lab_caller_save")
        self.db.execute("INSERT INTO lab_caller_state VALUES ('savepoint')")
        with self.assertRaisesRegex(RuntimeError,ERROR):
            self._dispatch()
        self.assertTrue(self.db.in_transaction)
        self.assertEqual(self._marker_count(),2)
        self.db.execute("ROLLBACK TO SAVEPOINT lab_caller_save")
        self.assertEqual(self._marker_count(),1)
        self.db.execute("RELEASE SAVEPOINT lab_caller_save")
        self.db.rollback()
        self.assertEqual(self._marker_count(),0)
        self._assert_claim_untouched()

    def test_04_nested_transaction_must_not_consult_authorizer(self):
        invocations=[]
        def spy(decision):
            invocations.append("POLICY")
            raise AssertionError("POLICY_NOT_ALLOWED_IN_NESTED_TXN")
        self.db.execute("BEGIN IMMEDIATE")
        try:
            with self.assertRaisesRegex(RuntimeError,ERROR):
                self._dispatch(authorize=spy)
            self.assertEqual(invocations,[])
            self._assert_claim_untouched()
        finally:
            if self.db.in_transaction:
                self.db.rollback()

    def test_05_transaction_does_not_get_committed_on_private_cas_stale(self):
        self.db.execute("BEGIN IMMEDIATE")
        self.db.execute("INSERT INTO lab_caller_state VALUES ('parent')")
        bad={**self.claimed,"lease_until":"2026-10-21T15:30:00+00:00"}
        with self.assertRaisesRegex(RuntimeError,ERROR):
            self.outbox._set_blocked(self.key,"BLOCKED_REAPPROVAL","LAB_STALE",
                                     expected=bad)
        self.assertTrue(self.db.in_transaction)
        self._assert_claim_untouched()
        self.db.rollback()
        self.assertEqual(self._marker_count(),0)

    def test_06_standalone_auth_denial_preserves_no_adapter_and_commits_its_own(self):
        out=self._dispatch()
        self.assertFalse(self.db.in_transaction)
        self.assertIn(out["state"],("REVOKED","BLOCKED_REAPPROVAL"))
        self.assertEqual(out["lease_owner"],"")
        self.assertEqual(self.outbox.effect_count(),0)

    def test_07_standalone_private_block_keeps_pre_dispatch_fence(self):
        out=self.outbox._set_blocked(self.key,"REVOKED","LAB_BLOCK",
                                     expected=self.claimed)
        self.assertEqual(out["state"],"REVOKED")
        self.assertEqual(out["last_error"],"LAB_BLOCK")
        self.assertFalse(self.db.in_transaction)
        self.assertEqual(self.outbox.effect_count(),0)

    def test_08_release_expired_claims_existing_parent_guard_unchanged(self):
        self.db.execute("BEGIN IMMEDIATE")
        self.db.execute("INSERT INTO lab_caller_state VALUES ('parent')")
        with self.assertRaisesRegex(RuntimeError,ERROR):
            self.outbox.release_expired_claims(now=NOW+timedelta(minutes=10))
        self.assertTrue(self.db.in_transaction)
        self.assertEqual(self._marker_count(),1)
        self.db.rollback()
        self.assertEqual(self._marker_count(),0)

    def test_09_parent_savepoint_with_private_block_can_roll_back_normally(self):
        self.db.execute("BEGIN IMMEDIATE")
        self.db.execute("SAVEPOINT my_subtask")
        self.db.execute("INSERT INTO lab_caller_state VALUES ('subtask')")
        with self.assertRaisesRegex(RuntimeError,ERROR):
            self.outbox._set_blocked(self.key,"REVOKED","NO_CONSENT",
                                     expected=self.claimed)
        self.db.execute("ROLLBACK TO SAVEPOINT my_subtask")
        self.db.execute("RELEASE SAVEPOINT my_subtask")
        self.db.commit()
        self.assertEqual(self._marker_count(),0)
        self._assert_claim_untouched()


if __name__=="__main__":
    unittest.main()
