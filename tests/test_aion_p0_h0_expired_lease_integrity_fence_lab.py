"""AION P0 H0 RED-FIRST: expired CLAIMED lease cannot recycle corrupt decisions.

Exercises real SQLiteChatStore and ExecutionOutbox in disposable files.
Before patch, release_expired_claims() advances expired CLAIMED -> RETRY
even where get() reports local_integrity=MISMATCH or a scoped join is lost.
No adapter, Worker, external effect, network, witness or provider is used.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_execution_outbox import ExecutionOutbox

NOW = datetime(2026,10,21,16,0,tzinfo=timezone.utc)
OWNER=Scope("lease-owner","lease-tenant","lease-workspace")
DENY="OUTBOX_EXPIRED_CLAIM_LOCAL_INTEGRITY_MISMATCH"


class ExpiredClaimIntegrityFenceLab(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory(prefix="aion-expired-claim-integrity-")
        self.addCleanup(tmp.cleanup)
        self.store=SQLiteChatStore(Path(tmp.name)/"expired.sqlite3")
        self.addCleanup(self.store.close)
        self.db=self.store.db
        self.box=ExecutionOutbox(self.store,OWNER)
        self.key=self.enqueue("a")
        claimed=self.box.claim_next("lab-worker",now=NOW,lease_seconds=15)
        self.assertIsNotNone(claimed)
        self.assertEqual(claimed["idempotency_key"],self.key)
        self.assertEqual(claimed["state"],"CLAIMED")

    def enqueue(self,label):
        return self.box.enqueue(
            intent_ref="intent-"+label,
            action="LAB_STAGE_ONLY",
            payload={"label":label,"test_only":True},
            aggregate_key="aggregate-"+label,
            policy_version="policy-local-test",
            authorization_ref="not-external-approval",
            created_at=NOW,
            valid_until=NOW+timedelta(minutes=5),
        )["idempotency_key"]

    def _raw(self,key=None):
        return self.db.execute(
            "SELECT state,attempts,lease_owner,lease_until,last_error "
            "FROM action_outbox WHERE idempotency_key=?",
            (self.key if key is None else key,),
        ).fetchone()

    def _decision(self,key=None):
        return self.db.execute(
            "SELECT d.data FROM action_decisions d "
            "JOIN action_outbox o ON o.decision_id=d.decision_id "
            "WHERE o.idempotency_key=?",
            (self.key if key is None else key,),
        ).fetchone()[0]

    def corrupt_data(self,change):
        doc=json.loads(self._decision())
        new=change(doc)
        with self.db:
            self.db.execute(
                "UPDATE action_decisions SET data=? WHERE decision_id=("
                "SELECT decision_id FROM action_outbox WHERE idempotency_key=?)",
                (new,self.key),
            )

    def corrupt_column(self,column,value):
        assert column in {"authorization_ref","valid_until","action","owner","payload_digest"}
        with self.db:
            self.db.execute(
                "UPDATE action_decisions SET "+column+"=? WHERE decision_id=("
                "SELECT decision_id FROM action_outbox WHERE idempotency_key=?)",
                (value,self.key),
            )

    def assert_quarantined_not_recycled(self):
        before=tuple(self.db.iterdump())
        original=tuple(self._raw())
        with self.assertRaisesRegex(PermissionError,DENY):
            self.box.release_expired_claims(now=NOW+timedelta(seconds=25))
        self.assertEqual(tuple(self.db.iterdump()),before)
        self.assertEqual(tuple(self._raw()),original)
        self.assertEqual(self._raw()[0],"CLAIMED")
        self.assertEqual(self._raw()[1],1)
        self.assertEqual(self.box.effect_count(),0)

    def test_01_unmodified_clean_expired_pre_dispatch_claim_recycles(self):
        self.assertEqual(self.box.get(self.key)["local_integrity"],"MATCH")
        changed=self.box.release_expired_claims(now=NOW+timedelta(seconds=25))
        self.assertEqual(changed,1)
        self.assertEqual(self.box.get(self.key)["state"],"RETRY")
        self.assertEqual(self.box.effect_count(),0)

    def test_02_forged_grants_authority_true_cannot_recycle(self):
        self.corrupt_data(lambda d:json.dumps({**d,"grants_authority":True},sort_keys=True,separators=(",",":")))
        self.assertEqual(self.box.get(self.key)["local_integrity"],"MISMATCH")
        self.assert_quarantined_not_recycled()

    def test_03_payload_changed_cannot_recycle(self):
        self.corrupt_data(lambda d:json.dumps({**d,"payload":{"lab":"forged"}},sort_keys=True,separators=(",",":")))
        self.assert_quarantined_not_recycled()

    def test_04_noncanonical_json_cannot_recycle(self):
        self.corrupt_data(lambda d:" "+json.dumps(d,sort_keys=True,separators=(",",":")))
        self.assert_quarantined_not_recycled()

    def test_05_duplicate_key_split_view_cannot_recycle(self):
        self.corrupt_data(lambda d:json.dumps(d,sort_keys=True,separators=(",",":"))[:-1]+',"grants_authority":true}')
        self.assert_quarantined_not_recycled()

    def test_06_malformed_json_cannot_recycle(self):
        self.corrupt_data(lambda d:'{"broken":')
        self.assert_quarantined_not_recycled()

    def test_07_authorization_column_changed_cannot_recycle(self):
        self.corrupt_column("authorization_ref","forged-local-approval")
        self.assert_quarantined_not_recycled()

    def test_08_deadline_column_changed_cannot_recycle(self):
        self.corrupt_column("valid_until","2099-01-01T00:00:00+00:00")
        self.assert_quarantined_not_recycled()

    def test_09_action_column_changed_cannot_recycle(self):
        self.corrupt_column("action","different-action")
        self.assert_quarantined_not_recycled()

    def test_10_payload_digest_column_changed_cannot_recycle(self):
        self.corrupt_column("payload_digest","f"*64)
        self.assert_quarantined_not_recycled()

    def test_11_foreign_scope_decision_pointer_cannot_recycle(self):
        self.corrupt_column("owner","foreign-owner")
        with self.assertRaises(LookupError):
            self.box.get(self.key)
        self.assert_quarantined_not_recycled()

    def test_12_corrupt_and_healthy_claims_must_roll_back_as_one_batch(self):
        other=self.enqueue("b")
        second=self.box.claim_next("lab-worker",now=NOW,lease_seconds=15)
        self.assertEqual(second["idempotency_key"],other)
        self.corrupt_column("authorization_ref","forged")
        self.assert_quarantined_not_recycled()
        self.assertEqual(self._raw(other)[0],"CLAIMED")
        self.assertEqual(self.box.get(other)["local_integrity"],"MATCH")

    def test_13_nonexpired_corrupt_claim_does_not_change(self):
        self.corrupt_column("authorization_ref","forged")
        before=tuple(self.db.iterdump())
        self.assertEqual(self.box.release_expired_claims(now=NOW+timedelta(seconds=10)),0)
        self.assertEqual(before,tuple(self.db.iterdump()))
        self.assertEqual(self._raw()[0],"CLAIMED")

    def test_14_uncertain_or_dispatched_marker_not_downgraded(self):
        with self.db:
            self.db.execute(
                "UPDATE action_outbox SET dispatch_started_at=? WHERE idempotency_key=?",
                (NOW.isoformat(),self.key),
            )
        before=tuple(self.db.iterdump())
        self.assertEqual(self.box.release_expired_claims(now=NOW+timedelta(seconds=25)),0)
        self.assertEqual(before,tuple(self.db.iterdump()))
        self.assertEqual(self._raw()[0],"CLAIMED")

    def test_15_double_release_of_clean_claim_cannot_increment_attempt(self):
        self.assertEqual(self.box.release_expired_claims(now=NOW+timedelta(seconds=25)),1)
        self.assertEqual(self.box.release_expired_claims(now=NOW+timedelta(seconds=25)),0)
        self.assertEqual(self._raw()[0],"RETRY")
        self.assertEqual(self._raw()[1],1)
        self.assertEqual(self.box.effect_count(),0)

    def test_16_existing_parent_transaction_hardstop_preserved(self):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            with self.assertRaisesRegex(RuntimeError,"OUTBOX_NESTED_TRANSACTION_UNSUPPORTED"):
                self.box.release_expired_claims(now=NOW+timedelta(seconds=25))
            self.assertTrue(self.db.in_transaction)
            self.assertEqual(self._raw()[0],"CLAIMED")
        finally:
            self.db.rollback()


if __name__=="__main__":
    unittest.main()
