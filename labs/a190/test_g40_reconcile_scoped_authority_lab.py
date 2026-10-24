"""G40 LAB: scoped reconciliation LOOKUP permission over real SQLite Outbox.

All callbacks/adapters are synthetic, opted in only on disposable DBs. No
provider, real receipt, Worker, customer data, or enabled production SEND.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_execution_outbox import ExecutionOutbox

NOW = datetime(2026, 10, 24, 16, tzinfo=timezone.utc)
SCOPE = Scope("g40-owner", "g40-tenant", "g40-workspace")
WORKER = "g40-worker"


class NoLookup:
    def __init__(self):
        self.reads = 0

    @property
    def reconcile(self):
        self.reads += 1
        raise AssertionError("G40_FORBIDDEN_LOOKUP")


class SyntheticAdapter:
    def __init__(self, response=None):
        self.lookups = 0
        self.calls = 0
        self.response = response or {"found": False}

    @property
    def reconcile(self):
        self.lookups += 1
        return self._reconcile

    def _reconcile(self, key, decision):
        self.calls += 1
        return dict(self.response)


class G40ScopedReconciliation(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="g40-reconcile-")
        self.addCleanup(tmp.cleanup)
        self.store = SQLiteChatStore(Path(tmp.name) / "chat.sqlite3")
        self.addCleanup(self.store.close)
        self.base = ExecutionOutbox(self.store, SCOPE)
        row = self.base.enqueue(
            intent_ref="g40-intent", action="synthetic_no_provider",
            payload={"amount_minor": 1000}, aggregate_key="g40-aggregate",
            policy_version="p1", authorization_ref="a1",
            created_at=NOW, valid_until=NOW+timedelta(minutes=5),
        )
        self.key = row["idempotency_key"]
        claimed = self.base.claim_next(WORKER, now=NOW, lease_seconds=60)
        self.assertEqual(claimed["idempotency_key"], self.key)
        observed = self.base.dispatch_claimed(
            self.key, worker_id=WORKER,
            authorize=lambda _: {
                "allowed": True, "actor_id": SCOPE.owner_id,
                "policy_version": "p1", "authorization_ref": "a1",
            },
            adapter=NoLookup(), now=NOW+timedelta(seconds=1),
        )
        self.assertEqual(observed["state"], "UNCERTAIN")
        self.lab = ExecutionOutbox(
            self.store, SCOPE, unsafe_allow_synthetic_lab_callbacks=True,
            evidence_verifier=lambda *_: True,
            strict_reconciliation_auth_lab=True,
        )

    def permission(self, **changes):
        data = dict(
            allowed=True, purpose="RECONCILE_LOOKUP",
            actor_id=SCOPE.owner_id,
            tenant_id=SCOPE.tenant_id,
            workspace_id=SCOPE.workspace_id,
        )
        data.update(changes)
        return data

    def perform(self, permission, *, adapter=None, outbox=None):
        adapter = adapter if adapter is not None else NoLookup()
        gate = outbox or self.lab
        before = gate.get(self.key)
        result = gate.reconcile(
            self.key, adapter=adapter,
            authorize=lambda _: permission,
            now=NOW+timedelta(minutes=30),
        )
        return before, result, adapter

    def test_01_authorized_lookup_occurs_without_send(self):
        adapter = SyntheticAdapter()
        before, result, _ = self.perform(self.permission(), adapter=adapter)
        self.assertEqual(result["reconcile_state"], "STILL_UNCERTAIN")
        self.assertEqual(result["state"], "UNCERTAIN")
        self.assertEqual(adapter.lookups, 1)
        self.assertEqual(adapter.calls, 1)
        self.assertEqual(self.lab.effect_count(), 0)
        print("G40_LOOKUP_AUTH_GREEN=SCOPED_RECONCILIATION_ONLY")

    def test_02_denied_permission_never_looks_up(self):
        before, result, adapter = self.perform(self.permission(allowed=False))
        self.assertEqual(result["reconcile_state"], "RECONCILE_AUTH_DENIED_NO_LOOKUP")
        self.assertEqual(result["state"], before["state"])
        self.assertEqual(result["last_error"], before["last_error"])
        self.assertEqual(adapter.reads, 0)
        print("G40_RECONCILE_DENY_GREEN=NO_ADAPTER_PROPERTY_ACCESS")

    def test_03_missing_purpose_denies(self):
        p = self.permission()
        del p["purpose"]
        _, result, adapter = self.perform(p)
        self.assertEqual(result["reconcile_state"], "RECONCILE_AUTH_DENIED_NO_LOOKUP")
        self.assertEqual(adapter.reads, 0)

    def test_04_wrong_purpose_send_approval_not_valid_for_lookup(self):
        _, result, adapter = self.perform(self.permission(purpose="SEND"))
        self.assertEqual(result["reconcile_state"], "RECONCILE_AUTH_DENIED_NO_LOOKUP")
        self.assertEqual(adapter.reads, 0)

    def test_05_missing_tenant_denies(self):
        p = self.permission()
        del p["tenant_id"]
        _, result, adapter = self.perform(p)
        self.assertEqual(result["reconcile_state"], "RECONCILE_AUTH_DENIED_NO_LOOKUP")
        self.assertEqual(adapter.reads, 0)

    def test_06_wrong_tenant_denies(self):
        _, result, adapter = self.perform(self.permission(tenant_id="other"))
        self.assertEqual(result["reconcile_state"], "RECONCILE_AUTH_DENIED_NO_LOOKUP")
        self.assertEqual(adapter.reads, 0)

    def test_07_missing_workspace_denies(self):
        p = self.permission()
        del p["workspace_id"]
        _, result, adapter = self.perform(p)
        self.assertEqual(result["reconcile_state"], "RECONCILE_AUTH_DENIED_NO_LOOKUP")
        self.assertEqual(adapter.reads, 0)

    def test_08_wrong_workspace_denies(self):
        _, result, adapter = self.perform(self.permission(workspace_id="other"))
        self.assertEqual(result["reconcile_state"], "RECONCILE_AUTH_DENIED_NO_LOOKUP")
        self.assertEqual(adapter.reads, 0)

    def test_09_wrong_actor_denies(self):
        _, result, adapter = self.perform(self.permission(actor_id="other"))
        self.assertEqual(result["reconcile_state"], "RECONCILE_AUTH_DENIED_NO_LOOKUP")
        self.assertEqual(adapter.reads, 0)

    def test_10_callback_exception_denies_without_state_change(self):
        trap = NoLookup()
        before = self.lab.get(self.key)
        result = self.lab.reconcile(
            self.key, adapter=trap,
            authorize=lambda _: (_ for _ in ()).throw(RuntimeError("offline")),
            now=NOW + timedelta(minutes=30),
        )
        self.assertEqual(result["reconcile_state"], "RECONCILE_AUTH_DENIED_NO_LOOKUP")
        self.assertEqual(trap.reads, 0)
        self.assertEqual(self.lab.get(self.key), before)

    def test_11_none_or_wrong_type_permission_denied(self):
        trap = NoLookup()
        for p in (None, "yes", [], self.permission(tenant_id=None),
                  self.permission(workspace_id=1)):
            with self.subTest(value=p):
                _, result, _ = self.perform(p, adapter=trap)
                self.assertEqual(result["reconcile_state"], "RECONCILE_AUTH_DENIED_NO_LOOKUP")
                self.assertEqual(trap.reads, 0)

    def test_12_expired_send_authorization_does_not_block_scoped_lookup(self):
        adapter = SyntheticAdapter()
        _, result, _ = self.perform(self.permission(), adapter=adapter)
        self.assertEqual(result["reconcile_state"], "STILL_UNCERTAIN")
        self.assertEqual(adapter.calls, 1)
        # No SEND-approval renewal or retry even though historic TTL expired.
        self.assertEqual(self.lab.get(self.key)["state"], "UNCERTAIN")
        print("G40_EXPIRED_SEND_GREEN=RECONCILE_LOOKUP_SEPARATE_AUTHORITY")

    def test_13_synthetic_confirm_needs_lookup_authority_first(self):
        adapter = SyntheticAdapter({
            "found": True, "confirmed": True,
            "effect_ref": "g40-synthetic-only",
        })
        _, denied, _ = self.perform(self.permission(purpose="SEND"), adapter=adapter)
        self.assertEqual(denied["reconcile_state"], "RECONCILE_AUTH_DENIED_NO_LOOKUP")
        self.assertEqual(adapter.calls, 0)
        _, allowed, _ = self.perform(self.permission(), adapter=adapter)
        self.assertEqual(allowed["state"], "CONFIRMED")
        self.assertEqual(self.lab.effect_count(), 1)
        self.assertEqual(adapter.calls, 1)
        print("G40_SYNTHETIC_CONFIRM_LIMIT=LOCAL_VERIFIER_NOT_PROVIDER_RECEIPT")

    def test_14_untrusted_absence_does_not_become_retry(self):
        adapter = SyntheticAdapter({
            "found": False, "authoritative_absence": True,
        })
        _, observed, _ = self.perform(self.permission(), adapter=adapter)
        self.assertEqual(observed["state"], "UNCERTAIN")
        self.assertEqual(observed["reconcile_state"], "STILL_UNCERTAIN")
        self.assertEqual(self.lab.effect_count(), 0)
        self.assertIsNone(self.lab.claim_next(WORKER,now=NOW+timedelta(minutes=6)))

    def test_15_default_outbox_does_not_reconcile_even_with_scope(self):
        trap = NoLookup()
        result = self.base.reconcile(
            self.key, adapter=trap,
            authorize=lambda _: self.permission(),
            now=NOW+timedelta(minutes=30),
        )
        self.assertEqual(result["reconcile_state"], "EXTERNAL_TRUST_NOT_CONFIGURED")
        self.assertEqual(trap.reads, 0)

    def test_16_opt_in_requires_bool(self):
        with self.assertRaises(TypeError):
            ExecutionOutbox(self.store,SCOPE,strict_reconciliation_auth_lab=1)

    def test_17_callback_mutation_denied(self):
        trap=NoLookup()
        def altered(d):
            d["authorization_ref"]="tampered"
            return self.permission()
        result=self.lab.reconcile(self.key,adapter=trap,
            authorize=altered,now=NOW+timedelta(minutes=30))
        self.assertEqual(result["reconcile_state"],"RECONCILE_AUTH_DENIED_NO_LOOKUP")
        self.assertEqual(trap.reads,0)

    def test_18_status_query_does_not_revoke_or_resend(self):
        prior=self.lab.get(self.key)
        for reason in (self.permission(allowed=False),
                       self.permission(purpose="SEND")):
            self.perform(reason)
        now=self.lab.get(self.key)
        self.assertEqual(now,prior)
        self.assertEqual(now["state"],"UNCERTAIN")


if __name__=="__main__":
    unittest.main()
