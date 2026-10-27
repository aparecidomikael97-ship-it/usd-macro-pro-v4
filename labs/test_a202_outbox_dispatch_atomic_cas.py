"""A202 real SQLite adversarial dispatch race; synthetic adapter, zero network.

Two independent SQLiteChatStore connections race the same persisted CLAIMED
row under the SAME worker_id. Both pass authorization before either crosses
the boundary. Without rowcount-checked atomic CAS, they can both invoke SEND.

This protects only against this local concurrency bug, NOT against rollback,
forged original intentions, independently anchored first-attempt receipts,
provider replay, or any of the six external P0 obligations.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Barrier, BrokenBarrierError, Lock
import tempfile
import unittest

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_execution_outbox import ExecutionOutbox

NOW=datetime(2026, 10, 27, 22, 0, tzinfo=timezone.utc)
WORKER="same-worker-reentered"
SCOPE=Scope("synthetic-owner", "synthetic-tenant", "synthetic-workspace")


class FakeNonIdempotentEffect:
    """Counts every actual call; the adapter has NO external idempotency."""
    def __init__(self):
        self.lock=Lock()
        self.effects=[]

    def send(self, decision, key):
        with self.lock:
            self.effects.append((key, decision["intent_ref"]))
            serial=len(self.effects)
        return {
            "accepted": True, "confirmed": True,
            "effect_ref": "SYNTHETIC-EFFECT-"+str(serial),
        }


class A202SameLeaseOwnerDispatchRaceTests(unittest.TestCase):
    def seed_claim(self, root):
        path=Path(root)/"a202.sqlite3"
        store=SQLiteChatStore(path)
        outbox=ExecutionOutbox(store,SCOPE)
        pending=outbox.enqueue(
            intent_ref="one-original-intent",
            action="synthetic_local_effect",
            payload={"synthetic": "no-network"},
            aggregate_key="one-aggregate",
            policy_version="policy-v1",
            authorization_ref="synthetic-approval",
            created_at=NOW,
            valid_until=NOW+timedelta(minutes=5),
        )
        claimed=outbox.claim_next(WORKER,now=NOW,lease_seconds=120)
        self.assertEqual(claimed["state"],"CLAIMED")
        self.assertEqual(pending["idempotency_key"],claimed["idempotency_key"])
        return path,store,outbox,claimed["idempotency_key"]

    def authorize(self, decision):
        return {
            "allowed": True,
            "actor_id": SCOPE.owner_id,
            "tenant_id": SCOPE.tenant_id,
            "workspace_id": SCOPE.workspace_id,
            "policy_version": decision["policy_version"],
            "authorization_ref": decision["authorization_ref"],
        }

    def test_01_two_real_sqlite_connections_same_worker_must_only_send_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            path,store1,outbox1,key=self.seed_claim(tmp)
            store2=SQLiteChatStore(path)
            outbox2=ExecutionOutbox(store2,SCOPE)
            try:
                self.assertIsNot(store1.db,store2.db)
                self.assertEqual(outbox2.get(key)["state"],"CLAIMED")
                gate=Barrier(2,timeout=20)
                adapter=FakeNonIdempotentEffect()

                def authorized_with_barrier(decision):
                    try:
                        gate.wait()
                    except BrokenBarrierError as e:
                        raise AssertionError("both dispatches must pass read+auth") from e
                    return self.authorize(decision)

                def dispatch(outbox):
                    return outbox.dispatch_claimed(
                        key,worker_id=WORKER,
                        authorize=authorized_with_barrier,
                        adapter=adapter,now=NOW,
                    )

                with ThreadPoolExecutor(max_workers=2) as pool:
                    a=pool.submit(dispatch,outbox1)
                    b=pool.submit(dispatch,outbox2)
                    results=[a.result(timeout=40),b.result(timeout=40)]

                # Before A202 fix, this is RED: actual two sends despite the
                # persisted single local lease, and effects could diverge.
                self.assertEqual(
                    len(adapter.effects),1,
                    "A202_FAIL: two calls reached synthetic SEND for same "
                    "claimed semantic intent and worker ID",
                )
                self.assertEqual(
                    sum(x.get("dispatch_state")=="CONFIRMED" for x in results),
                    1,
                )
                self.assertEqual(
                    sum(x.get("dispatch_state")=="NOT_DISPATCHED_STATE_CHANGED" for x in results),
                    1,
                )
                self.assertEqual(outbox1.get(key)["state"],"CONFIRMED")
            finally:
                store2.close()
                store1.close()

    def test_02_repeated_claimed_dispatch_after_confirm_never_resends(self):
        with tempfile.TemporaryDirectory() as tmp:
            _,store,outbox,key=self.seed_claim(tmp)
            try:
                adapter=FakeNonIdempotentEffect()
                first=outbox.dispatch_claimed(
                    key,worker_id=WORKER,authorize=self.authorize,
                    adapter=adapter,now=NOW,
                )
                self.assertEqual(first["dispatch_state"],"CONFIRMED")
                with self.assertRaisesRegex(ValueError,"must be CLAIMED"):
                    outbox.dispatch_claimed(
                        key,worker_id=WORKER,authorize=self.authorize,
                        adapter=adapter,now=NOW,
                    )
                self.assertEqual(len(adapter.effects),1)
            finally:
                store.close()

    def test_03_reapproval_denied_does_not_enter_adapter(self):
        with tempfile.TemporaryDirectory() as tmp:
            _,store,outbox,key=self.seed_claim(tmp)
            try:
                adapter=FakeNonIdempotentEffect()
                result=outbox.dispatch_claimed(
                    key,worker_id=WORKER,
                    authorize=lambda d:{**self.authorize(d),"allowed":False},
                    adapter=adapter,now=NOW,
                )
                self.assertEqual(result["state"],"REVOKED")
                self.assertEqual(adapter.effects,[])
            finally:
                store.close()


if __name__=="__main__":
    unittest.main()
