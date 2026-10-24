"""G40: synthetic clock TOCTOU after first-witness reservation, real SQLite.

The in-process witness and clock callbacks are NOT trustworthy; synthetic
adapter stubs never connect to an external service or customer account.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_execution_outbox import ExecutionOutbox

NOW = datetime(2026,10,24,16,tzinfo=timezone.utc)
SCOPE = Scope("g40-fresh-owner","g40-fresh-tenant","g40-fresh-workspace")
WORKER = "g40-fresh-worker"


class AdapterProbe:
    def __init__(self):
        self.getters=0
        self.calls=0

    @property
    def send(self):
        self.getters+=1
        return self._send

    def _send(self, decision, key):
        self.calls+=1
        return {"accepted": True, "effect_ref": "g40-local-synthetic"}


class G40FreshClockAfterWitness(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory(prefix="g40-fresh-")
        self.addCleanup(tmp.cleanup)
        self.store=SQLiteChatStore(Path(tmp.name)/"chat.sqlite3")
        self.addCleanup(self.store.close)
        self.clock=NOW+timedelta(seconds=2)
        self.witness_reads=0
        self.adapter=AdapterProbe()

    def witness(self, intent):
        self.witness_reads+=1
        return True

    def now(self):
        return self.clock

    def build(self, *, ttl=300, lease_seconds=300, witness=None, clock=None):
        self.outbox=ExecutionOutbox(self.store,SCOPE,
            unsafe_allow_synthetic_lab_callbacks=True,
            first_attempt_guard=witness if witness is not None else self.witness,
            evidence_verifier=lambda *_:False,
            fresh_dispatch_clock_lab=clock if clock is not None else self.now,
            strict_authority_scope_lab=True)
        item=self.outbox.enqueue(intent_ref="g40-event",action="synthetic_no_provider",
            payload={"amount_minor":1000},aggregate_key="g40-invoice",
            policy_version="p1",authorization_ref="a1",
            created_at=NOW,valid_until=NOW+timedelta(seconds=ttl))
        claimed=self.outbox.claim_next(WORKER,now=NOW,lease_seconds=lease_seconds)
        self.assertEqual(item["idempotency_key"],claimed["idempotency_key"])
        return claimed

    def authority(self, decision):
        return dict(allowed=True,actor_id=SCOPE.owner_id,tenant_id=SCOPE.tenant_id,
            workspace_id=SCOPE.workspace_id,
            policy_version="p1",authorization_ref="a1")

    def dispatch(self, claimed, auth=None):
        return self.outbox.dispatch_claimed(
            claimed["idempotency_key"],worker_id=WORKER,
            authorize=auth if auth is not None else self.authority,
            adapter=self.adapter,now=NOW+timedelta(seconds=1))

    def no_adapter(self):
        self.assertEqual(self.adapter.getters,0)
        self.assertEqual(self.adapter.calls,0)
        self.assertEqual(self.outbox.effect_count(),0)

    def test_01_fresh_valid_clock_passes_only_test_stub(self):
        claimed=self.build()
        result=self.dispatch(claimed)
        self.assertEqual(result["state"],"SENT")
        self.assertEqual(self.adapter.calls,1)
        self.assertEqual(self.outbox.effect_count(),0)
        print("G40_FRESH_VALID_LIMIT=ONLY_SYNTHETIC_TEST_STUB_SEND")

    def test_02_authority_expires_after_callback_no_adapter(self):
        claimed=self.build(ttl=5)
        def slow(decision):
            self.clock=NOW+timedelta(seconds=5)
            return self.authority(decision)
        result=self.dispatch(claimed,auth=slow)
        self.assertEqual(result["state"],"UNCERTAIN")
        self.assertEqual(result["last_error"],"AUTHORITY_EXPIRED_AFTER_WITNESS_NO_SEND")
        self.no_adapter()
        print("G40_TTL_AFTER_CALLBACK_GREEN=UNCERTAIN_ZERO_SEND")

    def test_03_lease_expires_after_callback_no_adapter(self):
        claimed=self.build(ttl=300,lease_seconds=30)
        def slow(decision):
            self.clock=NOW+timedelta(seconds=31)
            return self.authority(decision)
        result=self.dispatch(claimed,auth=slow)
        self.assertEqual(result["last_error"],"LEASE_EXPIRED_NO_SEND")
        self.assertEqual(result["state"],"UNCERTAIN")
        self.no_adapter()
        print("G40_LEASE_AFTER_CALLBACK_GREEN=UNCERTAIN_ZERO_SEND")

    def test_04_equal_to_expiry_denies(self):
        claimed=self.build(ttl=60,lease_seconds=300)
        self.clock=NOW+timedelta(seconds=60)
        result=self.dispatch(claimed)
        self.assertEqual(result["last_error"],"AUTHORITY_EXPIRED_AFTER_WITNESS_NO_SEND")
        self.no_adapter()

    def test_05_equal_to_lease_boundary_denies(self):
        claimed=self.build(ttl=300,lease_seconds=60)
        self.clock=NOW+timedelta(seconds=60)
        result=self.dispatch(claimed)
        self.assertEqual(result["last_error"],"LEASE_EXPIRED_NO_SEND")
        self.no_adapter()

    def test_06_clock_rewind_denies(self):
        claimed=self.build()
        self.clock=NOW
        result=self.dispatch(claimed)
        self.assertEqual(result["last_error"],"CLOCK_REWOUND_NO_SEND")
        self.no_adapter()
        print("G40_CLOCK_ROLLBACK_GREEN=UNCERTAIN_ZERO_SEND")

    def test_07_clock_exception_denies(self):
        def offline():
            raise RuntimeError("G40_CLOCK_OFFLINE")
        claimed=self.build(clock=offline)
        result=self.dispatch(claimed)
        self.assertEqual(result["last_error"],"FRESH_CLOCK_UNAVAILABLE_NO_SEND")
        self.no_adapter()

    def test_08_invalid_naive_clock_denies(self):
        claimed=self.build(clock=lambda: datetime(2026,10,24,16))
        result=self.dispatch(claimed)
        self.assertEqual(result["last_error"],"FRESH_CLOCK_UNAVAILABLE_NO_SEND")
        self.no_adapter()

    def test_09_invalid_clock_string_denies(self):
        claimed=self.build(clock=lambda: "not-an-iso-timestamp")
        result=self.dispatch(claimed)
        self.assertEqual(result["last_error"],"FRESH_CLOCK_UNAVAILABLE_NO_SEND")
        self.no_adapter()

    def test_10_clock_is_not_external_trust_root_red(self):
        claimed=self.build(ttl=5,clock=lambda: NOW+timedelta(seconds=2))
        result=self.dispatch(claimed)
        self.assertEqual(result["state"],"SENT")
        self.assertEqual(self.adapter.calls,1)
        print("G40_LOCAL_CLOCK_RED=UNTRUSTED_HOST_CAN_SUPPLY_FALSE_FRESH_TIME")

    def test_11_expired_after_witness_cannot_reclaim(self):
        claimed=self.build(ttl=4)
        self.clock=NOW+timedelta(seconds=4)
        result=self.dispatch(claimed)
        self.assertEqual(result["state"],"UNCERTAIN")
        self.assertIsNone(self.outbox.claim_next(WORKER,now=NOW+timedelta(seconds=10)))
        self.no_adapter()

    def test_12_changed_worker_lease_owner_fails_after_witness(self):
        def change_owner(_):
            self.outbox.db.execute(
                "UPDATE action_outbox SET lease_owner='another-worker' "
                "WHERE idempotency_key=?", (self.key,))
            self.outbox.db.commit()
            return True
        claimed=self.build(witness=change_owner)
        self.key=claimed["idempotency_key"]
        result=self.dispatch(claimed)
        self.assertEqual(result["last_error"],"CLAIM_CHANGED_NO_SEND")
        self.no_adapter()

    def test_13_witness_denied_still_avoids_clock_and_adapter(self):
        seen=[]
        def clock():
            seen.append("clock")
            return NOW+timedelta(seconds=2)
        claimed=self.build(witness=lambda _:False,clock=clock)
        result=self.dispatch(claimed)
        self.assertEqual(result["state"],"UNCERTAIN")
        self.assertEqual(result["last_error"],"FIRST_ATTEMPT_WITNESS_UNVERIFIED_NO_SEND")
        self.assertEqual(seen,[])
        self.no_adapter()

    def test_14_default_outbox_still_blocks_synthetic_send(self):
        outbox=ExecutionOutbox(self.store,SCOPE,
            fresh_dispatch_clock_lab=lambda:NOW+timedelta(seconds=2))
        row=outbox.enqueue(intent_ref="g40-other",action="synthetic_no_provider",
            payload={"amount_minor":1000},aggregate_key="g40-other",
            policy_version="p1",authorization_ref="a1",
            created_at=NOW,valid_until=NOW+timedelta(minutes=3))
        claimed=outbox.claim_next(WORKER,now=NOW)
        result=outbox.dispatch_claimed(row["idempotency_key"],
            worker_id=WORKER,authorize=self.authority,
            adapter=self.adapter,now=NOW+timedelta(seconds=1))
        self.assertEqual(result["state"],"UNCERTAIN")
        self.no_adapter()

    def test_15_clock_option_must_be_callable(self):
        with self.assertRaises(TypeError):
            ExecutionOutbox(self.store,SCOPE,fresh_dispatch_clock_lab=True)

    def test_16_post_witness_hold_never_auto_retry(self):
        claimed=self.build(ttl=6)
        self.clock=NOW+timedelta(seconds=7)
        state=self.dispatch(claimed)
        self.assertEqual(state["state"],"UNCERTAIN")
        self.assertFalse(state["executes_action"])
        self.assertEqual(self.outbox.effect_count(),0)
        self.no_adapter()


if __name__=="__main__":
    unittest.main()
