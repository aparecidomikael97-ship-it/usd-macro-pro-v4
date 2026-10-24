"""G30 budget guard denial cases on real Outbox; no provider."""
from datetime import datetime,timedelta,timezone
from pathlib import Path
import tempfile,unittest
from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_execution_outbox import ExecutionOutbox
NOW=datetime(2026,10,24,16,tzinfo=timezone.utc)
SCOPE=Scope("g30-owner-budget","g30-tenant-budget","g30-workspace-budget")
class Trap:
    def __init__(self):self.reads=0
    @property
    def send(self):
        self.reads+=1
        raise AssertionError("synthetic adapter accessed")
class G30Budget(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory(prefix="g30-budget-")
        self.addCleanup(tmp.cleanup)
        self.store=SQLiteChatStore(Path(tmp.name)/"real.sqlite3")
        self.addCleanup(self.store.close)
        self.outbox=ExecutionOutbox(self.store,SCOPE)
        self.trap=Trap()
        self.outbox.enqueue(intent_ref="g30-intent",action="synthetic",
            payload={"amount_minor":1000},aggregate_key="g30-aggregate",
            policy_version="p1",authorization_ref="a1",created_at=NOW,
            valid_until=NOW+timedelta(minutes=5),
            transaction_id="txn-1",authority_budget_ref="budget-1",
            risk_points=3,capability_class="LAB")
        self.claim=self.outbox.claim_next("g30-worker",now=NOW,lease_seconds=60)
    def run_dispatch(self,guard):
        result=self.outbox.dispatch_claimed(self.claim["idempotency_key"],
            worker_id="g30-worker",authorize=lambda _:dict(allowed=True,
                actor_id=SCOPE.owner_id,policy_version="p1",authorization_ref="a1"),
            cumulative_authority_guard=guard,adapter=self.trap,
            now=NOW+timedelta(seconds=1))
        self.assertEqual(self.trap.reads,0)
        self.assertEqual(self.outbox.effect_count(),0)
        return result
    def test_01_missing_guard_denies(self):
        self.assertEqual(self.run_dispatch(None)["last_error"],
            "CUMULATIVE_AUTHORITY_GUARD_REQUIRED")
    def test_02_guard_exception_denies(self):
        def fault(_):raise TimeoutError("synthetic")
        self.assertEqual(self.run_dispatch(fault)["last_error"],
            "CUMULATIVE_AUTHORITY_GUARD_FAILED")
    def test_03_guard_false_denies(self):
        self.assertEqual(self.run_dispatch(lambda _:{"allowed":False,
            "reason":"SYNTHETIC_LIMIT_REACHED"})["last_error"],"SYNTHETIC_LIMIT_REACHED")
    def test_04_budget_ref_mismatch_denies(self):
        self.assertEqual(self.run_dispatch(lambda _:dict(allowed=True,
            authority_budget_ref="wrong",transaction_id="txn-1"))["last_error"],
            "CUMULATIVE_AUTHORITY_BUDGET_REF_MISMATCH")
    def test_05_transaction_mismatch_denies(self):
        self.assertEqual(self.run_dispatch(lambda _:dict(allowed=True,
            authority_budget_ref="budget-1",transaction_id="wrong"))["last_error"],
            "CUMULATIVE_AUTHORITY_TRANSACTION_MISMATCH")
    def test_06_valid_budget_still_uncertain(self):
        result=self.run_dispatch(lambda _:dict(allowed=True,
            authority_budget_ref="budget-1",transaction_id="txn-1"))
        self.assertEqual(result["state"],"UNCERTAIN")
        self.assertEqual(result["dispatch_state"],"UNCERTAIN_PRE_DISPATCH_RESERVATION_REQUIRED")
        print("G30_BUDGET_WITNESS_GREEN=NO_SEND")
if __name__=="__main__":unittest.main()
