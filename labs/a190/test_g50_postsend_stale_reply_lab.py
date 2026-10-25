"""G50 LAB: stale synthetic post-send replies must never rewrite newer state.

Disposable local SQLite only; no Worker, real adapter, provider or external
effects. Commit RED tests before any candidate production-code patch.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_execution_outbox import ExecutionOutbox

NOW=datetime(2026,10,24,21,tzinfo=timezone.utc)
SCOPE=Scope("g50-owner","g50-tenant","g50-space")
WORKER="g50-worker"


class SyntheticSend:
    def __init__(self, before_return=None, response=None):
        self.calls=0
        self.before_return=before_return
        self.response=({"accepted":True,"confirmed":False,
                        "effect_ref":"synthetic-untrusted-only"}
                       if response is None else response)

    def send(self, decision, key):
        self.calls+=1
        if self.before_return:
            self.before_return()
        return dict(self.response)


class G50StalePostSend(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory(prefix="a190-g50-")
        self.addCleanup(tmp.cleanup)
        self.path=Path(tmp.name)/"temporary.sqlite3"
        self.store=SQLiteChatStore(self.path)
        self.addCleanup(self.store.close)
        self.outbox=ExecutionOutbox(
            self.store,SCOPE,
            unsafe_allow_synthetic_lab_callbacks=True,
            first_attempt_guard=lambda _: True,
            evidence_verifier=lambda *_: False,
            strict_binding_integrity_lab=True,
            strict_authority_scope_lab=True,
        )
        row=self.outbox.enqueue(
            intent_ref="synthetic-g50",
            action="synthetic-no-network",payload={"amount_minor":42},
            aggregate_key="g50-sequence",
            policy_version="p1",authorization_ref="g50-auth",
            created_at=NOW,valid_until=NOW+timedelta(minutes=5))
        self.key=row["idempotency_key"]
        self.claim=self.outbox.claim_next(
            WORKER,now=NOW,lease_seconds=120)
        self.assertIsNotNone(self.claim)

    def permit(self, _):
        return {"allowed":True,"actor_id":SCOPE.owner_id,
                "tenant_id":SCOPE.tenant_id,
                "workspace_id":SCOPE.workspace_id,
                "policy_version":"p1","authorization_ref":"g50-auth"}

    def dispatch(self, adapter,engine=None):
        return (engine or self.outbox).dispatch_claimed(
            self.key,worker_id=WORKER,authorize=self.permit,
            adapter=adapter,now=NOW+timedelta(seconds=1))

    def confirm(self):
        return self.outbox._confirm(
            self.key,effect_ref="synthetic-earlier-confirmation",
            confirmed_at=NOW+timedelta(seconds=2))

    def mutate(self, fragment):
        self.store.db.execute(
            "UPDATE action_outbox SET "+fragment+
            " WHERE idempotency_key=?", (self.key,))
        self.store.db.commit()

    def state(self):
        return self.outbox.get(self.key)

    def assert_stale(self, result, state):
        self.assertEqual(result["dispatch_state"],"G50_STALE_SEND_REPLY_NO_WRITE")
        self.assertEqual(result["state"],state)
        self.assertEqual(self.state()["state"],state)

    def test_01_normal_synthetic_reply_still_marks_sent(self):
        adapter=SyntheticSend()
        result=self.dispatch(adapter)
        self.assertEqual(adapter.calls,1)
        self.assertEqual(result["state"],"SENT")
        self.assertEqual(self.outbox.effect_count(),0)

    def test_02_late_rejection_never_downgrades_confirmed_ledger(self):
        adapter=SyntheticSend(
            before_return=self.confirm,
            response={"accepted":False,"retryable":True})
        result=self.dispatch(adapter)
        self.assert_stale(result,"CONFIRMED")
        self.assertEqual(self.outbox.effect_count(),1)
        self.assertEqual(self.state()["effect_ref"],"synthetic-earlier-confirmation")
        print("G50_POSTSEND_CONFIRMED_GREEN=LEDGER_NOT_DOWNGRADED")

    def test_03_late_acceptance_does_not_resurrect_revoked(self):
        adapter=SyntheticSend(before_return=lambda:
                              self.mutate("state='REVOKED'"))
        result=self.dispatch(adapter)
        self.assert_stale(result,"REVOKED")
        self.assertEqual(self.outbox.effect_count(),0)
        print("G50_POSTSEND_REVOKED_GREEN=NO_RESURRECTION")

    def test_04_late_acceptance_does_not_override_new_generation(self):
        adapter=SyntheticSend(before_return=lambda:
                              self.mutate("attempts=attempts+1"))
        result=self.dispatch(adapter)
        self.assert_stale(result,"UNCERTAIN")
        self.assertEqual(self.state()["attempts"],self.claim["attempts"]+1)
        self.assertEqual(self.outbox.effect_count(),0)
        print("G50_POSTSEND_EPOCH_GREEN=NO_STALE_TRANSITION")

    def test_05_late_rejection_keeps_replacement_worker(self):
        adapter=SyntheticSend(
            before_return=lambda:
                self.mutate("lease_owner='different-worker'"),
            response={"accepted":False,"retryable":False})
        result=self.dispatch(adapter)
        self.assert_stale(result,"UNCERTAIN")
        self.assertEqual(self.state()["lease_owner"],"different-worker")

    def test_06_exception_after_inner_confirmation_cannot_downgrade(self):
        def inner_then_exception():
            self.confirm()
            raise OSError("synthetic-lost-response")
        adapter=SyntheticSend(before_return=inner_then_exception)
        result=self.dispatch(adapter)
        self.assert_stale(result,"CONFIRMED")
        self.assertEqual(self.outbox.effect_count(),1)
        print("G50_POSTSEND_EXCEPTION_GREEN=NO_OVERWRITE")

    def test_07_normal_rejection_remains_uncertain_without_retry(self):
        adapter=SyntheticSend(response={"accepted":False,"retryable":True})
        result=self.dispatch(adapter)
        self.assertEqual(result["state"],"UNCERTAIN")
        self.assertEqual(result["dispatch_state"],"UNCERTAIN_RECONCILE_REQUIRED")
        self.assertEqual(adapter.calls,1)
        self.assertEqual(self.outbox.effect_count(),0)

if __name__=="__main__":
    unittest.main()
