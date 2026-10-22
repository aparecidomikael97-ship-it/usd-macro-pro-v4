"""A181 LAB cross-file recovery and rollback adversarial tests.

Two SQLite files on SAME CI machine are only a logical isolation test; NOT
a physically independent witness, authenticated remote custodian or H0 SLA.
All keys and effects are synthetic; the only 'send' is an in-memory counter.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import timedelta
from pathlib import Path
import secrets
import shutil
import sqlite3
import tempfile
import unittest

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from aion_chat.first_attempt_witness_lab import (
    PinnedFirstAttemptWitnessLab, _effect_digest,
)
from aion_chat.separate_custody_a181_lab import (
    CustodyUnavailable, SeparateSQLiteCustodyLab,
)
from atlasquant_aion_execution_outbox import ExecutionOutbox
from test_atlasquant_aion_execution_outbox import NOW, policy
from test_atlasquant_aion_first_attempt_witness_a180_lab import (
    LabAdapter, fake_confirmed,
)
from test_atlasquant_aion_signed_receipt_a178_lab import public_bytes


ISSUER = "synthetic-independent-custodian"
KEY_ID = "synthetic-custodian-key"
PRIVATE = Ed25519PrivateKey.from_private_bytes(b"\x0d" * 32)
PAYLOAD = {"to": "example.invalid", "template": "synthetic-one"}


class A181SeparateCustodyRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.host_dir = root / "aion-host"
        self.custody_dir = root / "synthetic-custodian"
        self.host_dir.mkdir()
        self.custody_dir.mkdir()
        self.host_db = self.host_dir / "host.sqlite3"
        self.custody_db = self.custody_dir / "independent.sqlite3"
        self.scope = Scope("owner-lab", "tenant-lab", "workspace-lab")
        self.custody = self.bootstrap()

    def bootstrap(self):
        return SeparateSQLiteCustodyLab.bootstrap_lab(
            self.custody_db, issuer=ISSUER, key_id=KEY_ID,
            signer=PRIVATE.sign, now=NOW,
        )

    def reopen_custody(self):
        return SeparateSQLiteCustodyLab(
            self.custody_db, issuer=ISSUER, key_id=KEY_ID,
            signer=PRIVATE.sign, now=NOW,
        )

    def guard(self, *, reserve=None):
        return PinnedFirstAttemptWitnessLab(
            issuer=ISSUER, key_id=KEY_ID,
            public_key=public_bytes(PRIVATE),
            reserve=self.custody.reserve if reserve is None else reserve,
            now=NOW+timedelta(seconds=2),
        )

    def host(self, ref="business-event-1", *, payload=None, scope=None,
             guard=None):
        scope = scope or self.scope
        store = SQLiteChatStore(self.host_db)
        options = {
            "first_attempt_guard": self.guard() if guard is None else guard,
            "evidence_verifier": fake_confirmed,
        }
        outbox = ExecutionOutbox(store, scope, **options)
        row = outbox.enqueue(
            intent_ref=ref, action="send_email",
            payload=payload or PAYLOAD, aggregate_key="account-1",
            policy_version="policy-v1", authorization_ref="approval-1",
            created_at=NOW, valid_until=NOW+timedelta(minutes=5))
        return store, outbox, row

    def claim_and_send(self, out, row, *, scope=None):
        claimed = out.claim_next("worker-lab", now=NOW, lease_seconds=60)
        self.assertIsNotNone(claimed)
        adapter = LabAdapter()
        result = out.dispatch_claimed(
            row["idempotency_key"], worker_id="worker-lab",
            authorize=policy(scope or self.scope),adapter=adapter,
            now=NOW+timedelta(seconds=1),
        )
        return result, adapter

    def assert_denied_from_fresh_host(self, ref="business-event-different-id"):
        store, out, row = self.host(ref)
        try:
            state, adapter = self.claim_and_send(out, row)
            self.assertEqual(state["state"], "UNCERTAIN")
            self.assertEqual(adapter.send_calls, 0)
            self.assertIsNone(
                out.claim_next("worker-again", now=NOW+timedelta(seconds=3)))
        finally:
            store.close()

    def test_01_destroy_host_db_reopen_same_effect_new_id_denied(self):
        store,out,row=self.host()
        try:
            state,adapter=self.claim_and_send(out,row)
            self.assertEqual(state["state"],"CONFIRMED")
            self.assertEqual(adapter.send_calls,1)
        finally:
            store.close()
        self.host_db.unlink()
        self.custody=self.reopen_custody()
        self.assert_denied_from_fresh_host()
        self.assertEqual(self.custody.snapshot()["count"],1)
        print("A181_HOST_DB_DELETED_WITNESS_SURVIVES=NO_REPLAY")

    def test_02_restore_host_snapshot_before_send_custody_denies(self):
        store,out,row=self.host()
        self.assertIsNotNone(out.claim_next("worker-lab",now=NOW,lease_seconds=60))
        snapshot=self.host_dir/"backup-before-send.sqlite3"
        with closing(sqlite3.connect(str(self.host_db))) as source:
            with closing(sqlite3.connect(str(snapshot))) as dest:
                source.backup(dest)
        adapter=LabAdapter()
        confirmed=out.dispatch_claimed(
            row["idempotency_key"],worker_id="worker-lab",
            authorize=policy(self.scope),adapter=adapter,
            now=NOW+timedelta(seconds=1))
        self.assertEqual(confirmed["state"],"CONFIRMED")
        self.assertEqual(adapter.send_calls,1)
        store.close()
        shutil.copyfile(snapshot,self.host_db)
        self.custody=self.reopen_custody()
        reopened=SQLiteChatStore(self.host_db)
        try:
            candidate=ExecutionOutbox(
                reopened,self.scope,first_attempt_guard=self.guard(),
                evidence_verifier=fake_confirmed)
            self.assertEqual(candidate.get(row["idempotency_key"])["state"],"CLAIMED")
            resumed=LabAdapter()
            result=candidate.dispatch_claimed(
                row["idempotency_key"],worker_id="worker-lab",
                authorize=policy(self.scope),adapter=resumed,
                now=NOW+timedelta(seconds=2))
            self.assertEqual(result["state"],"UNCERTAIN")
            self.assertEqual(resumed.send_calls,0)
        finally:
            reopened.close()
        print("A181_HOST_ROLLBACK_WITH_CUSTODY_INTACT=NO_REPLAY")

    def test_03_custody_commit_then_lost_reply_denies_send_and_future_replay(self):
        def lost(challenge,request):
            self.custody.reserve(challenge,request)
            raise TimeoutError("commit completed but reply lost")
        store,out,row=self.host(guard=self.guard(reserve=lost))
        try:
            state,adapter=self.claim_and_send(out,row)
            self.assertEqual(state["state"],"UNCERTAIN")
            self.assertEqual(adapter.send_calls,0)
            self.assertEqual(self.custody.snapshot()["count"],1)
        finally:
            store.close()
        self.host_db.unlink()
        self.custody=self.reopen_custody()
        self.assert_denied_from_fresh_host()
        print("A181_LOST_RESERVATION_REPLY_AND_HOST_LOSS=NO_SEND")

    def test_04_custodian_file_missing_denies_send(self):
        self.custody_db.rename(self.custody_dir/"offline.sqlite3")
        store,out,row=self.host()
        try:
            state,adapter=self.claim_and_send(out,row)
            self.assertEqual(state["state"],"UNCERTAIN")
            self.assertEqual(adapter.send_calls,0)
        finally:
            store.close()
        print("A181_CUSTODY_FILE_MISSING=FAIL_CLOSED")

    def test_05_missing_custody_cannot_auto_rebootstrap(self):
        self.custody_db.unlink()
        with self.assertRaises(CustodyUnavailable):
            self.reopen_custody()
        with self.assertRaises(CustodyUnavailable):
            self.custody.snapshot()
        print("A181_CUSTODY_MISSING_ON_RECOVERY=HARD_DENY")

    def test_06_explicit_fresh_rebootstrap_after_wipe_is_bypass(self):
        store,out,row=self.host()
        try:
            self.assertEqual(self.claim_and_send(out,row)[0]["state"],"CONFIRMED")
        finally:
            store.close()
        self.host_db.unlink()
        self.custody_db.unlink()
        # Critical negative result: a privileged actor can deliberately
        # enroll a brand-new empty synthetic custodian after total loss.
        self.custody=self.bootstrap()
        second,again,newrow=self.host("new-request-for-same-effect")
        try:
            state,adapter=self.claim_and_send(again,newrow)
            self.assertEqual(state["state"],"CONFIRMED")
            self.assertEqual(adapter.send_calls,1)
        finally:
            second.close()
        print("A181_CUSTODY_REENROLL_AFTER_WIPE=REPLAY_ACCEPTED_NO_ROOT")

    def test_07_restore_custody_snapshot_allows_duplicate_effect(self):
        snapshot=self.custody_dir/"custody-pre-send-snapshot.sqlite3"
        with closing(sqlite3.connect(str(self.custody_db))) as source:
            with closing(sqlite3.connect(str(snapshot))) as dest:
                source.backup(dest)
        store,out,row=self.host()
        try:
            self.assertEqual(self.claim_and_send(out,row)[0]["state"],"CONFIRMED")
        finally:
            store.close()
        self.host_db.unlink()
        shutil.copyfile(snapshot,self.custody_db)
        self.custody=self.reopen_custody()
        second,again,newrow=self.host("new-id-with-old-custody-snapshot")
        try:
            state,adapter=self.claim_and_send(again,newrow)
            self.assertEqual(state["state"],"CONFIRMED")
            self.assertEqual(adapter.send_calls,1)
        finally:
            second.close()
        print("A181_CUSTODY_SNAPSHOT_ROLLBACK=REPLAY_ACCEPTED_NOT_ATTESTED")

    def test_08_different_real_payload_is_not_blocked(self):
        store,out,row=self.host()
        try:
            self.assertEqual(self.claim_and_send(out,row)[0]["state"],"CONFIRMED")
        finally:
            store.close()
        store,out,row=self.host("new-business-event",payload={
            "to":"another.invalid", "template":"synthetic-one"})
        try:
            state,adapter=self.claim_and_send(out,row)
            self.assertEqual(state["state"],"CONFIRMED")
            self.assertEqual(adapter.send_calls,1)
            self.assertEqual(self.custody.snapshot()["count"],2)
        finally:
            store.close()

    def test_09_same_declared_effect_new_intent_id_does_not_reopen(self):
        store,out,row=self.host()
        try:
            self.assertEqual(self.claim_and_send(out,row)[0]["state"],"CONFIRMED")
        finally:
            store.close()
        store,out,newrow=self.host("new-request-id-same-effect")
        try:
            state,adapter=self.claim_and_send(out,newrow)
            self.assertEqual(state["state"],"UNCERTAIN")
            self.assertEqual(adapter.send_calls,0)
        finally:
            store.close()

    def test_10_two_custodian_db_connections_only_one_reserves_effect(self):
        store,out,row=self.host()
        decision=row["decision"]
        request={
            "idempotency_key":row["idempotency_key"],
            "effect_digest":_effect_digest(decision),
            "decision_sha256":__import__(
                "aion_chat.signed_receipt_lab",fromlist=["decision_sha256"]
            ).decision_sha256(decision),
            "owner_id":decision["owner_id"],
            "tenant_id":decision["tenant_id"],
            "workspace_id":decision["workspace_id"],
        }
        store.close()
        def reserve(i):
            body=dict(request)
            body["idempotency_key"]=f"{i+1:064x}"
            custodian=self.reopen_custody()
            return custodian.reserve(secrets.token_hex(32),body)
        with ThreadPoolExecutor(max_workers=8) as pool:
            responses=list(pool.map(reserve,range(8)))
        self.assertEqual(sum("signature" in x for x in responses),1)
        self.assertEqual(sum(x.get("status")=="ALREADY_RESERVED" for x in responses),7)
        self.assertEqual(self.custody.snapshot()["high_water"],1)
        print("A181_CONCURRENT_TWO_IDS_ONE_EFFECT=ONE_RESERVATION")

    def test_11_corrupt_custody_db_fails_closed(self):
        with self.custody_db.open("wb") as stream:
            stream.write(b"corrupted not SQLite")
        with self.assertRaises(CustodyUnavailable):
            self.reopen_custody()
        store,out,row=self.host()
        try:
            state,adapter=self.claim_and_send(out,row)
            self.assertEqual(state["state"],"UNCERTAIN")
            self.assertEqual(adapter.send_calls,0)
        finally:
            store.close()

    def test_12_signer_fails_after_commit_reservation_survives(self):
        def signer_unavailable(_message):
            raise OSError("synthetic signer unavailable")
        self.custody=SeparateSQLiteCustodyLab(
            self.custody_db,issuer=ISSUER,key_id=KEY_ID,
            signer=signer_unavailable,now=NOW)
        store,out,row=self.host()
        try:
            state,adapter=self.claim_and_send(out,row)
            self.assertEqual(state["state"],"UNCERTAIN")
            self.assertEqual(adapter.send_calls,0)
            self.assertEqual(self.custody.snapshot()["count"],1)
        finally:
            store.close()
        self.host_db.unlink()
        self.custody=self.reopen_custody()
        self.assert_denied_from_fresh_host()
        print("A181_SIGNER_CRASH_AFTER_COMMIT=NO_REPLAY")

    def test_13_second_explicit_bootstrap_over_existing_denied(self):
        with self.assertRaises(CustodyUnavailable):
            self.bootstrap()

    def test_14_untrusted_true_callback_still_bypasses_witness(self):
        # Known architectural limit: the Outbox permits a caller-injected
        # boolean guard. An internal actor with that authority can lie.
        self.custody_db.unlink()
        store,out,row=self.host(guard=lambda _intent: True)
        try:
            state,adapter=self.claim_and_send(out,row)
            self.assertEqual(state["state"],"CONFIRMED")
            self.assertEqual(adapter.send_calls,1)
        finally:
            store.close()
        print("A181_INJECTED_TRUE_GUARD=FAKE_AUTHORITY_ACCEPTED")

    def test_15_identical_declared_effect_may_block_legitimate_recurrence(self):
        store,out,row=self.host()
        try:
            self.assertEqual(self.claim_and_send(out,row)[0]["state"],"CONFIRMED")
        finally:
            store.close()
        # Separate legitimate event intended to repeat identical payload:
        # digest lacks authenticated event identity; false-positive denial.
        store,out,row=self.host("separate-legitimate-event-with-same-payload")
        try:
            state,adapter=self.claim_and_send(out,row)
            self.assertEqual(state["state"],"UNCERTAIN")
            self.assertEqual(adapter.send_calls,0)
        finally:
            store.close()
        print("A181_DISTINCT_IDENTICAL_LEGITIMATE_EVENT=DENIED_FALSE_POSITIVE")


if __name__ == "__main__":
    unittest.main()
