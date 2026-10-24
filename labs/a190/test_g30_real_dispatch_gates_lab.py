"""G30: real ExecutionOutbox dispatch fail-closed tests. No external adapter."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest
from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_execution_outbox import ExecutionOutbox

NOW = datetime(2026, 10, 24, 16, tzinfo=timezone.utc)
SCOPE = Scope("g30-owner", "g30-tenant", "g30-workspace")
WORKER = "g30-worker"

class Trap:
    def __init__(self): self.lookups = 0
    @property
    def send(self):
        self.lookups += 1
        raise AssertionError("synthetic adapter was accessed")
    @property
    def reconcile(self):
        self.lookups += 1
        raise AssertionError("synthetic reconcile was accessed")

class G30RealDispatch(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="g30-dispatch-")
        self.addCleanup(tmp.cleanup)
        self.store = SQLiteChatStore(Path(tmp.name)/"real.sqlite3")
        self.addCleanup(self.store.close)
        self.outbox = ExecutionOutbox(self.store, SCOPE)
        self.trap = Trap()

    def stage(self, **kw):
        args = dict(intent_ref="intent-1", action="synthetic_no_effect",
            payload={"amount_minor":1000}, aggregate_key="aggregate-1",
            policy_version="p1", authorization_ref="a1", created_at=NOW,
            valid_until=NOW+timedelta(minutes=5))
        args.update(kw)
        return self.outbox.enqueue(**args)

    def claim(self, **kw):
        item = self.stage(**kw)
        claim = self.outbox.claim_next(WORKER, now=NOW, lease_seconds=60)
        self.assertEqual(claim["idempotency_key"], item["idempotency_key"])
        return claim

    def auth(self, claim, **kw):
        decision = claim["decision"]
        value = dict(allowed=True, actor_id=SCOPE.owner_id,
            tenant_id=SCOPE.tenant_id, workspace_id=SCOPE.workspace_id,
            policy_version=decision["policy_version"],
            authorization_ref=decision["authorization_ref"])
        value.update(kw)
        return value

    def dispatch(self, claim, auth=None, guard=None, now=None, worker=WORKER):
        if auth is None: auth = self.auth(claim)
        return self.outbox.dispatch_claimed(
            claim["idempotency_key"], worker_id=worker,
            authorize=auth if callable(auth) else lambda _:auth,
            adapter=self.trap, cumulative_authority_guard=guard,
            now=now if now is not None else NOW+timedelta(seconds=1))

    def deny(self, state, reason, **changes):
        claim = self.claim()
        item = self.dispatch(claim, self.auth(claim, **changes))
        self.assertEqual((item["state"],item["last_error"]),(state,reason))
        self.assertEqual(self.trap.lookups,0)
        self.assertEqual(self.outbox.effect_count(),0)

    def test_01_policy_change(self):
        self.deny("BLOCKED_REAPPROVAL","POLICY_VERSION_CHANGED",policy_version="p2")
        print("G30_POLICY_GATE_GREEN=NO_ADAPTER")

    def test_02_authorization_change(self):
        self.deny("BLOCKED_REAPPROVAL","AUTHORIZATION_CHANGED",authorization_ref="a2")
        print("G30_AUTH_GATE_GREEN=NO_ADAPTER")

    def test_03_owner_mismatch(self):
        self.deny("REVOKED","ACTOR_MISMATCH",actor_id="other-owner")

    def test_04_tenant_mismatch(self):
        self.deny("REVOKED","TENANT_ID_MISMATCH",tenant_id="other-tenant")

    def test_05_workspace_mismatch(self):
        self.deny("REVOKED","WORKSPACE_ID_MISMATCH",workspace_id="other-workspace")

    def test_06_explicit_revocation(self):
        self.deny("REVOKED","AUTHORITY_REVOKED",allowed=False)

    def test_07_reauth_missing(self):
        claim = self.claim(requires_reauth=True,reauth_ref="reauth-v1")
        item = self.dispatch(claim)
        self.assertEqual(item["last_error"],"REAUTH_REQUIRED")
        self.assertEqual(self.trap.lookups,0)

    def test_08_reauth_mismatch(self):
        claim = self.claim(requires_reauth=True,reauth_ref="reauth-v1")
        item = self.dispatch(claim,self.auth(claim,reauthenticated=True,reauth_ref="reauth-v2"))
        self.assertEqual(item["last_error"],"REAUTH_TRANSACTION_MISMATCH")
        self.assertEqual(self.trap.lookups,0)

    def test_09_expired_authority(self):
        claim = self.claim(valid_until=NOW+timedelta(seconds=1))
        item = self.dispatch(claim)
        self.assertEqual(item["last_error"],"AUTHORITY_EXPIRED")
        self.assertEqual(self.trap.lookups,0)

    def test_10_authority_callback_exception(self):
        claim = self.claim()
        def fail(_): raise ConnectionError("synthetic auth failure")
        item = self.dispatch(claim,fail)
        self.assertEqual(item["last_error"],"AUTHORITY_REVALIDATION_FAILED")
        self.assertEqual(self.trap.lookups,0)

    def test_11_wrong_worker(self):
        claim = self.claim()
        with self.assertRaises(PermissionError):
            self.dispatch(claim,worker="other-worker")
        self.assertEqual(self.trap.lookups,0)

    def test_12_expired_lease(self):
        claim = self.claim()
        with self.assertRaises(TimeoutError):
            self.dispatch(claim,now=NOW+timedelta(seconds=60))
        self.assertEqual(self.trap.lookups,0)

    def test_13_no_witness_no_send(self):
        claim = self.claim()
        item = self.dispatch(claim)
        self.assertEqual(item["state"],"UNCERTAIN")
        self.assertEqual(item["dispatch_state"],"UNCERTAIN_PRE_DISPATCH_RESERVATION_REQUIRED")
        self.assertEqual(self.trap.lookups,0)
        self.assertEqual(self.outbox.effect_count(),0)
        print("G30_NO_WITNESS_GREEN=UNCERTAIN_ZERO_SEND")

    def test_14_replay_policy_at_dispatch_denied(self):
        self.stage()
        replay = self.stage(policy_version="p2")
        self.assertEqual(replay["enqueue_state"],"IDEMPOTENT")
        self.assertEqual(replay["decision"]["policy_version"],"p1")
        claim = self.outbox.claim_next(WORKER,now=NOW)
        result = self.dispatch(claim,self.auth(claim,policy_version="p2"))
        self.assertEqual(result["last_error"],"POLICY_VERSION_CHANGED")
        self.assertEqual(self.trap.lookups,0)
        print("G30_REPLAY_DISPATCH_GREEN=STALE_POLICY_BLOCKED")

    def test_15_uncertain_is_not_reclaimed_or_reconciled_without_trust(self):
        claim = self.claim()
        self.dispatch(claim)
        self.assertIsNone(self.outbox.claim_next(WORKER,now=NOW+timedelta(minutes=2)))
        result = self.outbox.reconcile(claim["idempotency_key"],
            adapter=self.trap,authorize=lambda _:self.auth(claim),
            now=NOW+timedelta(seconds=3))
        self.assertEqual(result["reconcile_state"],"EXTERNAL_TRUST_NOT_CONFIGURED")
        self.assertEqual(self.trap.lookups,0)

if __name__ == "__main__": unittest.main()
