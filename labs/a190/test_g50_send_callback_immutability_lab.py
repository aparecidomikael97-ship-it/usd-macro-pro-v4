"""AION A190 G50 synthetic send callback reentry: terminal local ledger immutability.

All real effects prohibited. Temporary SQLite, in-process test stubs only.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest
from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_execution_outbox import ExecutionOutbox
from atlasquant_aion_outbox_binding_lab import binding_issue_lab

NOW=datetime(2026,10,24,21,tzinfo=timezone.utc)
SCOPE=Scope("g50-owner","g50-tenant","g50-space")
WORKER="g50-worker"


class SyntheticReentrantSend:
    def __init__(self,outbox,key,fail=False):
        self.outbox=outbox
        self.key=key
        self.fail=fail
        self.calls=0

    def send(self,decision,key):
        self.calls+=1
        self.outbox._confirm(
            self.key,effect_ref="g50-local-effect",
            confirmed_at=NOW+timedelta(seconds=2),
            result={"proof":"SYNTHETIC-NOT-PROVIDER"},
        )
        if self.fail:
            raise OSError("synthetic-lost-response-after-local-confirm")
        return {"accepted":True,"confirmed":False,
                "effect_ref":"g50-other-local-ref"}


class SyntheticOrdinarySend:
    calls=0
    def send(self,decision,key):
        self.calls+=1
        return {"accepted":True,"confirmed":False,
                "effect_ref":"g50-no-confirmation"}


class G50AfterSendReentry(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory(prefix="g50-callback-")
        self.addCleanup(tmp.cleanup)
        self.path=Path(tmp.name)/"synthetic.sqlite3"
        self.store=SQLiteChatStore(self.path)
        self.addCleanup(self.store.close)
        self.outbox=ExecutionOutbox(
            self.store,SCOPE,
            unsafe_allow_synthetic_lab_callbacks=True,
            first_attempt_guard=lambda _:True,
            evidence_verifier=lambda *_:False,
            strict_binding_integrity_lab=True,
            strict_authority_scope_lab=True,
        )
        self.key=self.outbox.enqueue(
            intent_ref="synthetic-no-provider",action="synthetic_action",
            payload={"amount_minor":55},aggregate_key="g50-group",
            policy_version="p1",authorization_ref="g50-ref",
            created_at=NOW,valid_until=NOW+timedelta(minutes=5)
        )["idempotency_key"]
        claim=self.outbox.claim_next(WORKER,now=NOW,lease_seconds=100)
        self.assertEqual(claim["idempotency_key"],self.key)

    def dispatch(self,adapter):
        return self.outbox.dispatch_claimed(
            self.key,worker_id=WORKER,adapter=adapter,
            authorize=lambda _:dict(
                allowed=True,actor_id=SCOPE.owner_id,
                tenant_id=SCOPE.tenant_id,
                workspace_id=SCOPE.workspace_id,
                policy_version="p1",authorization_ref="g50-ref"),
            now=NOW+timedelta(seconds=1)
        )

    def binding(self):
        return binding_issue_lab(self.store.db,self.key,
            (SCOPE.owner_id,SCOPE.tenant_id,SCOPE.workspace_id))

    def verify_terminal(self,adapter):
        self.assertEqual(adapter.calls,1)
        self.assertEqual(self.outbox.get(self.key)["state"],"CONFIRMED")
        self.assertEqual(self.outbox.get(self.key)["effect_ref"],"g50-local-effect")
        self.assertEqual(self.outbox.effect_count(),1)
        self.assertEqual(self.binding(),"OK")
        self.assertIsNone(self.outbox.claim_next(
            WORKER,now=NOW+timedelta(minutes=2)))

    def test_01_valid_stub_without_confirmation_stays_sent(self):
        adapter=SyntheticOrdinarySend()
        result=self.dispatch(adapter)
        self.assertEqual(result["state"],"SENT")
        self.assertEqual(adapter.calls,1)
        self.assertEqual(self.outbox.effect_count(),0)

    def test_02_confirm_then_return_must_preserve_local_terminal(self):
        adapter=SyntheticReentrantSend(self.outbox,self.key)
        with self.assertRaisesRegex(RuntimeError,
            "G50_SEND_CALLBACK_CHANGED_NO_OVERWRITE"):
            self.dispatch(adapter)
        self.verify_terminal(adapter)
        print("G50_REENTRY_RETURN_GREEN=CONFIRMED_LEDGER_IMMUTABLE")

    def test_03_confirm_then_raise_must_preserve_local_terminal(self):
        adapter=SyntheticReentrantSend(self.outbox,self.key,fail=True)
        with self.assertRaisesRegex(RuntimeError,
            "G50_SEND_CALLBACK_CHANGED_NO_OVERWRITE"):
            self.dispatch(adapter)
        self.verify_terminal(adapter)
        print("G50_REENTRY_EXCEPTION_GREEN=CONFIRMED_NOT_UNCERTAIN")

    def test_04_default_without_witness_has_zero_adapter_calls(self):
        strict_default=ExecutionOutbox(
            self.store,SCOPE,strict_binding_integrity_lab=True
        )
        adapter=SyntheticOrdinarySend()
        result=strict_default.dispatch_claimed(
            self.key,worker_id=WORKER,adapter=adapter,
            authorize=lambda _:dict(
                allowed=True,actor_id=SCOPE.owner_id,
                policy_version="p1",authorization_ref="g50-ref"),
            now=NOW+timedelta(seconds=1)
        )
        self.assertEqual(result["state"],"UNCERTAIN")
        self.assertEqual(adapter.calls,0)
        self.assertEqual(self.outbox.effect_count(),0)


if __name__=="__main__":
    unittest.main()
