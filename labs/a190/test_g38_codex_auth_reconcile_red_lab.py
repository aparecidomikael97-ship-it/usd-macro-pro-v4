"""G38 Codex audit -> real Outbox authorization/reconciliation RED tests.

No real provider, Worker, payment or network. Synthetic callbacks use
explicit unsafe LAB opt-in only for showing boundaries that production
must NEVER treat as trustworthy. RED != production exploit.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_execution_outbox import ExecutionOutbox

NOW=datetime(2026,10,20,16,tzinfo=timezone.utc)
SCOPE=Scope("g38-auth-owner","g38-auth-tenant","g38-auth-workspace")
WORKER="g38-synthetic-worker"


class Trap:
    def __init__(self, *, result=None):
        self.send_calls=0
        self.reconcile_calls=0
        self.result = result if result is not None else {"found":False}

    def send(self, *args):
        self.send_calls+=1
        return {"accepted":True,"effect_ref":"synthetic-lab-effect"}

    def reconcile(self, *args):
        self.reconcile_calls+=1
        return dict(self.result)


class G38AuthorizationAndReconciliation(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory(prefix="aion-g38-auth-")
        self.addCleanup(tmp.cleanup)
        self.store=SQLiteChatStore(Path(tmp.name)/"outbox.sqlite3")
        self.addCleanup(self.store.close)
        self.outbox=ExecutionOutbox(self.store,SCOPE)
        self.trap=Trap()

    def stage(self, *, outbox=None, budget=False, valid_for=300):
        kw=dict(intent_ref="g38-auth-intent",
            action="synthetic_no_provider",payload={"amount_minor":1000},
            aggregate_key="synthetic-aggregate",
            policy_version="p1",authorization_ref="a1",
            created_at=NOW,valid_until=NOW+timedelta(seconds=valid_for))
        if budget:
            kw.update(transaction_id="txn-1",authority_budget_ref="budget-1",
                      risk_points=1,capability_class="LAB_ONLY")
        return (self.outbox if outbox is None else outbox).enqueue(**kw)

    def claim(self, *, outbox=None, budget=False, valid_for=300):
        o=self.outbox if outbox is None else outbox
        self.stage(outbox=o,budget=budget,valid_for=valid_for)
        return o.claim_next(WORKER,now=NOW,lease_seconds=60)

    def auth(self, **more):
        data=dict(allowed=True,actor_id=SCOPE.owner_id,
                  policy_version="p1",authorization_ref="a1")
        data.update(more)
        return data

    def dispatch(self, row, *, outbox=None, auth=None, adapter=None, guard=None):
        o=self.outbox if outbox is None else outbox
        auth_value=self.auth() if auth is None else auth
        return o.dispatch_claimed(
            row["idempotency_key"],worker_id=WORKER,
            authorize=lambda _:auth_value,
            adapter=self.trap if adapter is None else adapter,
            cumulative_authority_guard=guard,
            now=NOW+timedelta(seconds=1))

    def test_01_missing_scope_in_auth_callback_still_passes_gate_red(self):
        row=self.claim()
        result=self.dispatch(row,auth=self.auth())
        self.assertEqual(result["state"],"UNCERTAIN")
        self.assertEqual(result["last_error"],"FIRST_ATTEMPT_WITNESS_UNVERIFIED_NO_SEND")
        self.assertEqual(self.trap.send_calls,0)
        print("G38_AUTH_SCOPE_OMISSION_RED=MISSING_TENANT_WORKSPACE_GATE_PASSED_NO_SEND")

    def test_02_wrong_tenant_field_is_rejected(self):
        row=self.claim()
        result=self.dispatch(row,auth=self.auth(tenant_id="other"))
        self.assertEqual(result["last_error"],"TENANT_ID_MISMATCH")
        self.assertEqual(result["state"],"REVOKED")

    def test_03_wrong_workspace_field_is_rejected(self):
        row=self.claim()
        result=self.dispatch(row,auth=self.auth(workspace_id="other"))
        self.assertEqual(result["last_error"],"WORKSPACE_ID_MISMATCH")
        self.assertEqual(result["state"],"REVOKED")

    def test_04_explicit_matching_scope_still_no_witness(self):
        row=self.claim()
        result=self.dispatch(row,auth=self.auth(
            tenant_id=SCOPE.tenant_id,workspace_id=SCOPE.workspace_id))
        self.assertEqual(result["state"],"UNCERTAIN")
        self.assertEqual(self.trap.send_calls,0)

    def test_05_unbound_budget_not_universally_required_red(self):
        row=self.claim(budget=False)
        result=self.dispatch(row,guard=None)
        self.assertEqual(result["state"],"UNCERTAIN")
        print("G38_BUDGET_OPTIONAL_RED=NO_CUMULATIVE_GUARD_FOR_UNBOUND_INTENT")

    def test_06_explicit_budget_requires_guard(self):
        row=self.claim(budget=True)
        result=self.dispatch(row,guard=None)
        self.assertEqual(result["last_error"],"CUMULATIVE_AUTHORITY_GUARD_REQUIRED")
        self.assertEqual(result["state"],"BLOCKED_REAPPROVAL")

    def test_07_default_outbox_quarantines_supplied_true_callbacks(self):
        changed=ExecutionOutbox(
            self.store,SCOPE,
            first_attempt_guard=lambda _:True,
            evidence_verifier=lambda *_:True)
        row=self.claim(outbox=changed)
        result=self.dispatch(row,outbox=changed)
        self.assertEqual(result["state"],"UNCERTAIN")
        self.assertEqual(self.trap.send_calls,0)

    def make_uncertain(self):
        row=self.claim()
        result=self.dispatch(row)
        self.assertEqual(result["state"],"UNCERTAIN")
        return row

    def test_08_default_reconcile_does_not_consult_authorization(self):
        row=self.make_uncertain()
        invocations=[]
        def forbidden(_):
            invocations.append(True)
            raise AssertionError("reconcile auth called")
        result=self.outbox.reconcile(
            row["idempotency_key"],adapter=self.trap,
            authorize=forbidden,now=NOW+timedelta(seconds=2))
        self.assertEqual(result["reconcile_state"],"EXTERNAL_TRUST_NOT_CONFIGURED")
        self.assertEqual(invocations,[])
        self.assertEqual(self.trap.reconcile_calls,0)

    def test_09_lab_reconcile_calls_adapter_without_authorize_red(self):
        row=self.make_uncertain()
        lab=ExecutionOutbox(self.store,SCOPE,unsafe_allow_synthetic_lab_callbacks=True,
                            evidence_verifier=lambda *_:True)
        invocations=[]
        result=lab.reconcile(
            row["idempotency_key"],adapter=self.trap,
            authorize=lambda _:invocations.append("auth") or {"allowed":False},
            now=NOW+timedelta(seconds=2))
        self.assertEqual(result["reconcile_state"],"STILL_UNCERTAIN")
        self.assertEqual(invocations,[])
        self.assertEqual(self.trap.reconcile_calls,1)
        self.assertEqual(lab.effect_count(),0)
        print("G38_RECONCILE_AUTH_UNUSED_RED=LAB_RECONCILE_READ_WITHOUT_AUTH_CALLBACK")

    def test_10_lab_synthetic_evidence_can_confirm_without_authorize_red(self):
        row=self.make_uncertain()
        lab=ExecutionOutbox(self.store,SCOPE,unsafe_allow_synthetic_lab_callbacks=True,
                            evidence_verifier=lambda *_:True)
        witness=Trap(result={"found":True,"confirmed":True,
                             "effect_ref":"synthetic-effect-42"})
        invoked=[]
        result=lab.reconcile(
            row["idempotency_key"],adapter=witness,
            authorize=lambda _:invoked.append(True) or {"allowed":False},
            now=NOW+timedelta(seconds=2))
        self.assertEqual(result["state"],"CONFIRMED")
        self.assertEqual(lab.effect_count(),1)
        self.assertEqual(invoked,[])
        self.assertEqual(witness.reconcile_calls,1)
        self.assertEqual(witness.send_calls,0)
        print("G38_SYNTHETIC_RECONCILE_RED=LAB_CALLBACK_CONFIRM_WITHOUT_AUTH_RECHECK")

    def test_11_lab_stale_supplied_clock_can_reach_synthetic_send_red(self):
        lab=ExecutionOutbox(
            self.store,SCOPE,unsafe_allow_synthetic_lab_callbacks=True,
            first_attempt_guard=lambda _:True,
            evidence_verifier=lambda *_:False)
        row=self.claim(outbox=lab,valid_for=3)
        self.assertLess(
            NOW+timedelta(seconds=3),datetime.now(timezone.utc))
        trap=Trap()
        result=self.dispatch(row,outbox=lab,adapter=trap,
                             auth=self.auth(tenant_id=SCOPE.tenant_id,
                                            workspace_id=SCOPE.workspace_id))
        self.assertEqual(trap.send_calls,1)
        self.assertEqual(result["state"],"SENT")
        print("G38_STALE_CLOCK_RED=EXPLICIT_UNSAFE_LAB_CALL_USES_SUPPLIED_OLD_TIME")

    def test_12_lab_provider_absence_flag_never_auto_requeues(self):
        row=self.make_uncertain()
        lab=ExecutionOutbox(self.store,SCOPE,unsafe_allow_synthetic_lab_callbacks=True,
                            evidence_verifier=lambda *_:True)
        absent=Trap(result={"found":False,"authoritative_absence":True})
        result=lab.reconcile(
            row["idempotency_key"],adapter=absent,
            authorize=lambda _:{"allowed":False},
            now=NOW+timedelta(seconds=2))
        self.assertEqual(result["state"],"UNCERTAIN")
        self.assertEqual(result["reconcile_state"],"STILL_UNCERTAIN")
        self.assertIsNone(lab.claim_next(WORKER,now=NOW+timedelta(minutes=2)))
        self.assertEqual(absent.send_calls,0)


if __name__=="__main__":
    unittest.main()
