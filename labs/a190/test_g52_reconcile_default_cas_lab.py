"""A190 G52: stale local reconcile replies never rewrite newer SQLite state.

Disposable SQLite and synthetic callbacks only. No Worker, real provider,
customer data, financial execution, network or external receipt authority.
Tests intentionally committed before production-code change for RED/GREEN.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_execution_outbox import ExecutionOutbox

NOW = datetime(2026, 10, 25, 16, tzinfo=timezone.utc)
SCOPE = Scope("g52-owner", "g52-tenant", "g52-space")
WORKER = "g52-local-worker"


class FakeLookup:
    def __init__(self, on_get=None, on_call=None, response=None):
        self.getters = 0
        self.calls = 0
        self.on_get = on_get
        self.on_call = on_call
        self.response = response if response is not None else {
            "found": True, "confirmed": True, "effect_ref": "g52-local-receipt"
        }

    @property
    def reconcile(self):
        self.getters += 1
        if self.on_get:
            self.on_get()
        return self._lookup

    def _lookup(self, key, decision):
        self.calls += 1
        if self.on_call:
            self.on_call()
        return dict(self.response)


class G52DefaultSnapshot(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="a190-g52-")
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "synthetic.sqlite3"
        self.store = SQLiteChatStore(self.path)
        self.addCleanup(self.store.close)
        self.base = ExecutionOutbox(self.store, SCOPE)
        self.key = self.base.enqueue(
            intent_ref="g52-disposable-intent", action="synthetic-no-provider",
            payload={"amount_minor": 23}, aggregate_key="g52-group",
            policy_version="p1", authorization_ref="g52-auth",
            created_at=NOW, valid_until=NOW + timedelta(minutes=5),
        )["idempotency_key"]
        self.base.claim_next(WORKER, now=NOW, lease_seconds=60)
        class GetterDenied:
            @property
            def send(self):
                raise AssertionError("NO_SYNTHETIC_SEND_EXPECTED")
        out = self.base.dispatch_claimed(
            self.key, worker_id=WORKER, adapter=GetterDenied(),
            authorize=self.permit,
            now=NOW + timedelta(seconds=1),
        )
        self.assertEqual(out["state"], "UNCERTAIN")
        self.lab = self.make_lab()

    def make_lab(self, verifier=None, **overrides):
        config = dict(
            unsafe_allow_synthetic_lab_callbacks=True,
            strict_reconciliation_auth_lab=True,
            evidence_verifier=verifier or (lambda *_: True),
            # Do not opt in to G42 strict CAS. This is the default case.
        )
        config.update(overrides)
        return ExecutionOutbox(self.store, SCOPE, **config)

    def permit(self, _):
        return {"allowed": True, "actor_id": SCOPE.owner_id,
                "tenant_id": SCOPE.tenant_id,
                "workspace_id": SCOPE.workspace_id,
                "purpose": "RECONCILE_LOOKUP"}

    def scan(self, adapter, engine=None, authorize=None):
        return (engine or self.lab).reconcile(
            self.key, adapter=adapter,
            authorize=authorize or self.permit,
            now=NOW + timedelta(minutes=10),
        )

    def confirm(self, ref="g52-previous-confirmed"):
        return self.base._confirm(
            self.key, effect_ref=ref,
            confirmed_at=NOW + timedelta(minutes=8),
        )

    def mutate(self, sql_fragment):
        self.store.db.execute(
            "UPDATE action_outbox SET " + sql_fragment +
            " WHERE idempotency_key=?", (self.key,))
        self.store.db.commit()

    def state(self):
        return self.base.get(self.key)

    def assert_stale(self, result, state):
        self.assertEqual(result["reconcile_state"], "G42_STALE_REPLY_NO_WRITE")
        self.assertEqual(result["state"], state)
        self.assertEqual(self.state()["state"], state)

    def test_01_default_normal_synthetic_lookup_can_confirm(self):
        lookup = FakeLookup()
        result = self.scan(lookup)
        self.assertEqual(lookup.calls, 1)
        self.assertEqual(result["reconcile_state"], "CONFIRMED")
        self.assertEqual(self.lab.effect_count(), 1)
        print("G52_VALID_LOOKUP_GREEN=LOCAL_CONFIRM_ONLY")

    def test_02_negative_reply_cannot_report_stale_uncertain_after_confirmation(self):
        lookup = FakeLookup(
            on_call=lambda: self.confirm("winner"),
            response={"found": False, "authoritative_absence": True},
        )
        result = self.scan(lookup)
        self.assert_stale(result, "CONFIRMED")
        self.assertEqual(self.state()["effect_ref"], "winner")
        self.assertEqual(self.lab.effect_count(), 1)
        print("G52_NEGATIVE_STALE_GREEN=CONFIRMED_PRESERVED")

    def test_03_positive_reply_cannot_resurrect_local_revocation(self):
        lookup = FakeLookup(on_call=lambda: self.mutate("state='REVOKED'"))
        result = self.scan(lookup)
        self.assert_stale(result, "REVOKED")
        self.assertEqual(self.lab.effect_count(), 0)
        print("G52_REVOKED_GREEN=NO_FAKE_CONFIRM")

    def test_04_local_verifier_reentry_cannot_reconfirm_existing_receipt(self):
        first_ref = "winner"
        def verifier(kind, intent, result):
            self.confirm(first_ref)
            return True
        self.lab = self.make_lab(verifier=verifier)
        result = self.scan(FakeLookup(response={
            "found": True, "confirmed": True, "effect_ref": first_ref,
        }))
        self.assert_stale(result, "CONFIRMED")
        original = (NOW + timedelta(minutes=8)).isoformat()
        self.assertEqual(self.state()["confirmed_at"], original)
        effect = self.store.db.execute(
            "SELECT confirmed_at FROM action_effects WHERE idempotency_key=?",
            (self.key,),
        ).fetchone()
        self.assertEqual(effect["confirmed_at"], original)
        print("G52_RECEIPT_GREEN=ORIGINAL_TIMESTAMP")

    def test_05_getter_mutation_cannot_hide_changed_lease(self):
        lookup = FakeLookup(
            on_get=lambda: self.mutate("lease_until='later-lease'"),
            response={"found": False},
        )
        result = self.scan(lookup)
        self.assert_stale(result, "UNCERTAIN")
        self.assertEqual(lookup.calls, 0)
        self.assertEqual(self.lab.effect_count(), 0)
        print("G52_GETTER_GREEN=NO_LOOKUP_AFTER_DRIFT")

    def test_06_exception_after_local_confirmation_cannot_report_uncertain(self):
        def inner():
            self.confirm("winner")
            raise OSError("synthetic-unavailable")
        lookup = FakeLookup(on_call=inner)
        result = self.scan(lookup)
        self.assert_stale(result, "CONFIRMED")
        self.assertEqual(self.lab.effect_count(), 1)

    def test_07_denied_authorization_cannot_return_stale_intent(self):
        def revoke_then_deny(_):
            self.mutate("state='REVOKED'")
            return {"allowed": False}
        lookup = FakeLookup()
        result = self.scan(lookup, authorize=revoke_then_deny)
        self.assert_stale(result, "REVOKED")
        self.assertEqual(lookup.getters, 0)
        self.assertEqual(self.lab.effect_count(), 0)
        print("G52_AUTH_REENTRY_GREEN=NO_STALE_VIEW")

    def test_08_default_quarantine_blocks_getter_regardless_of_candidate(self):
        quarantined = ExecutionOutbox(self.store, SCOPE)
        lookup = FakeLookup()
        result = self.scan(lookup, engine=quarantined)
        self.assertEqual(result["reconcile_state"], "EXTERNAL_TRUST_NOT_CONFIGURED")
        self.assertEqual(lookup.getters, 0)
        self.assertEqual(self.lab.effect_count(), 0)

    def test_09_explicit_false_cas_still_rejects_stale_negative(self):
        engine = self.make_lab(strict_reconcile_snapshot_cas_lab=False)
        lookup = FakeLookup(on_call=lambda: self.confirm("winner"),
                            response={"found": False})
        result = self.scan(lookup, engine=engine)
        self.assert_stale(result, "CONFIRMED")
        self.assertEqual(self.lab.effect_count(), 1)

    def test_10_callback_generation_drift_keeps_uncertain_and_zero_ledger(self):
        lookup = FakeLookup(
            on_call=lambda: self.mutate("attempts=attempts+1"),
            response={"found": True, "confirmed": True,
                      "effect_ref": "fake-late"},
        )
        result = self.scan(lookup)
        self.assert_stale(result, "UNCERTAIN")
        self.assertEqual(self.lab.effect_count(), 0)
        print("G52_EPOCH_GREEN=NO_UNAUTHORIZED_LEDGER")


if __name__ == "__main__":
    unittest.main()
