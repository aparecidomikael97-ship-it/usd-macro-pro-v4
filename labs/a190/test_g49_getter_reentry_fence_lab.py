"""A190 G49 synthetic adapter getter reentry: no second send after phase drift.

All callbacks are synthetic LAB-only; SQLite is temporary; adapter never uses
a network, provider or customer credentials. Red tests precede candidate fix.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_execution_outbox import ExecutionOutbox

NOW = datetime(2026, 10, 24, 20, tzinfo=timezone.utc)
SCOPE = Scope("g49-owner","g49-tenant","g49-space")
WORKER = "g49-worker"


class SyntheticAdapter:
    def __init__(self, before_getter=None):
        self.getters = 0
        self.calls = 0
        self.before_getter = before_getter

    @property
    def send(self):
        self.getters += 1
        if self.before_getter:
            self.before_getter()
        return self.send_stub

    def send_stub(self, decision, key):
        self.calls += 1
        return {"accepted":True, "confirmed":False,
                "effect_ref":"synthetic-local-second-request"}


class G49GetterStateDrift(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory(prefix="g49-getter-")
        self.addCleanup(tmp.cleanup)
        self.path=Path(tmp.name)/"synthetic.sqlite3"
        self.store=SQLiteChatStore(self.path)
        self.addCleanup(self.store.close)
        self.outbox=ExecutionOutbox(
            self.store,SCOPE,unsafe_allow_synthetic_lab_callbacks=True,
            first_attempt_guard=lambda _: True,
            evidence_verifier=lambda *_: False,
            strict_binding_integrity_lab=True,
            strict_authority_scope_lab=True,
        )
        row=self.outbox.enqueue(
            intent_ref="synthetic-getter-case",
            action="synthetic_no_provider",
            payload={"amount_minor":42},
            aggregate_key="g49-sequence",
            policy_version="p1",authorization_ref="g49-auth",
            created_at=NOW,valid_until=NOW+timedelta(minutes=5),
        )
        self.key=row["idempotency_key"]
        self.claim=self.outbox.claim_next(
            WORKER,now=NOW,lease_seconds=120,
        )
        if self.claim is None:
            raise AssertionError("synthetic precondition: expected CLAIMED")

    def dispatch(self,adapter,engine=None):
        return (engine or self.outbox).dispatch_claimed(
            self.key,worker_id=WORKER,
            authorize=lambda _: {
                "allowed": True, "actor_id": SCOPE.owner_id,
                "tenant_id": SCOPE.tenant_id,
                "workspace_id": SCOPE.workspace_id,
                "policy_version":"p1", "authorization_ref":"g49-auth",
            },
            adapter=adapter,now=NOW+timedelta(seconds=1),
        )

    def row(self):
        return self.outbox.get(self.key)

    def change(self, field, value):
        if field not in {"state","attempts","lease_owner","lease_until"}:
            raise ValueError("invalid synthetic mutation")
        self.store.db.execute(
            f"UPDATE action_outbox SET {field}=? WHERE idempotency_key=?",
            (value,self.key),
        )
        self.store.db.commit()

    def assert_denied_after_getter(self, mutate):
        adapter=SyntheticAdapter(before_getter=mutate)
        with self.assertRaisesRegex(
            RuntimeError,"G49_GETTER_CHANGED_CLAIM_NO_SEND"
        ):
            self.dispatch(adapter)
        self.assertEqual(adapter.getters,1)
        self.assertEqual(adapter.calls,0)
        return adapter

    def test_01_unchanged_phase_permits_synthetic_stub_once(self):
        adapter=SyntheticAdapter()
        r=self.dispatch(adapter)
        self.assertEqual(adapter.getters,1)
        self.assertEqual(adapter.calls,1)
        self.assertEqual(r["state"],"SENT")
        self.assertEqual(self.outbox.effect_count(),0)

    def test_02_getter_confirms_same_key_before_second_send_denied(self):
        def inner_confirm():
            self.outbox._confirm(
                self.key,effect_ref="synthetic-getter-confirmation",
                confirmed_at=NOW+timedelta(seconds=2),
                result={"origin":"local-test-only"},
            )
        self.assert_denied_after_getter(inner_confirm)
        self.assertEqual(self.row()["state"],"CONFIRMED")
        self.assertEqual(self.outbox.effect_count(),1)
        print("G49_CONFIRM_REENTRY_GREEN=NO_SECOND_SEND")

    def test_03_getter_changes_worker_denied(self):
        self.assert_denied_after_getter(
            lambda:self.change("lease_owner","g49-foreign-worker")
        )
        self.assertEqual(self.outbox.effect_count(),0)
        print("G49_OWNER_DRIFT_GREEN=ZERO_SEND")

    def test_04_getter_changes_generation_denied(self):
        self.assert_denied_after_getter(
            lambda:self.change("attempts",self.claim["attempts"]+1)
        )
        self.assertEqual(self.outbox.effect_count(),0)
        print("G49_EPOCH_DRIFT_GREEN=ZERO_SEND")

    def test_05_getter_changes_lease_deadline_denied(self):
        self.assert_denied_after_getter(
            lambda:self.change(
                "lease_until",(NOW+timedelta(minutes=1)).isoformat()
            )
        )
        self.assertEqual(self.outbox.effect_count(),0)
        print("G49_LEASE_DRIFT_GREEN=ZERO_SEND")

    def test_06_getter_revokes_operation_denied(self):
        self.assert_denied_after_getter(
            lambda:self.change("state","REVOKED")
        )
        self.assertEqual(self.outbox.effect_count(),0)

    def test_07_default_no_callback_mode_still_blocks_adapter_getter(self):
        default=ExecutionOutbox(
            self.store,SCOPE,strict_binding_integrity_lab=True
        )
        adapter=SyntheticAdapter()
        r=self.dispatch(adapter,engine=default)
        self.assertEqual(r["state"],"UNCERTAIN")
        self.assertEqual(adapter.getters,0)
        self.assertEqual(adapter.calls,0)
        self.assertEqual(self.outbox.effect_count(),0)
        print("G49_DEFAULT_BLOCK_GREEN=NO_STUB_ACCESS")


if __name__ == "__main__":
    unittest.main()
