"""G42 read-only reconciliation snapshot CAS vs reentrant callbacks.

All adapters/receipts and authoritative decisions are SYNTHETIC. A passing
suite cannot prove provider receipt authenticity or independent P0 trust.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import shutil
import tempfile
import unittest

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_execution_outbox import ExecutionOutbox

SCOPE = Scope("g42-owner", "g42-tenant", "g42-workspace")
NOW = datetime(2026, 10, 24, 16, tzinfo=timezone.utc)
WORKER = "g42-test-only-worker"


class ReconcileStub:
    def __init__(self, *, on_get=None, on_call=None, response=None):
        self.getters = 0
        self.calls = 0
        self.on_get = on_get
        self.on_call = on_call
        self.response = response if response is not None else {
            "found": True, "confirmed": True, "effect_ref": "g42-result"
        }

    @property
    def reconcile(self):
        self.getters += 1
        if self.on_get:
            self.on_get()
        return self._call

    def _call(self, key, decision):
        self.calls += 1
        if self.on_call:
            self.on_call()
        return dict(self.response)


class GetterTrap:
    def __init__(self):
        self.getters = 0

    @property
    def reconcile(self):
        self.getters += 1
        raise AssertionError("G42_ADAPTER_GETTER_MUST_NOT_RUN")


class G42ReconciliationCAS(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="aion-g42-")
        self.addCleanup(temp.cleanup)
        self.file = Path(temp.name) / "outbox.sqlite3"
        self.store = SQLiteChatStore(self.file)
        self.addCleanup(lambda: self.store.close())
        self.base = ExecutionOutbox(self.store, SCOPE)
        row = self.base.enqueue(
            intent_ref="synthetic-business-request",
            action="synthetic_no_provider",
            payload={"amount_minor": 1000},
            aggregate_key="synthetic-batch",
            policy_version="p1",
            authorization_ref="auth1",
            created_at=NOW,
            valid_until=NOW + timedelta(minutes=5),
        )
        self.key = row["idempotency_key"]
        claim = self.base.claim_next(WORKER, now=NOW, lease_seconds=60)
        self.assertEqual(claim["idempotency_key"], self.key)
        denied = self.base.dispatch_claimed(
            self.key, worker_id=WORKER, now=NOW + timedelta(seconds=1),
            authorize=lambda d: {"allowed": True, "actor_id": SCOPE.owner_id,
                                 "policy_version": "p1",
                                 "authorization_ref": "auth1"},
            adapter=GetterTrap(),
        )
        self.assertEqual(denied["state"], "UNCERTAIN")
        self.assertEqual(denied["last_error"], "FIRST_ATTEMPT_WITNESS_UNVERIFIED_NO_SEND")
        self.lab = self.make_lab()
        self.assertEqual(self.lab.effect_count(), 0)

    def make_lab(self, *, verifier=None, strict=True, strict_auth=True):
        return ExecutionOutbox(
            self.store, SCOPE,
            unsafe_allow_synthetic_lab_callbacks=True,
            strict_reconciliation_auth_lab=strict_auth,
            strict_reconcile_snapshot_cas_lab=strict,
            evidence_verifier=verifier if verifier is not None else
                (lambda *_: True),
        )

    def permission(self, **changes):
        permit = dict(
            allowed=True, purpose="RECONCILE_LOOKUP",
            actor_id=SCOPE.owner_id,
            tenant_id=SCOPE.tenant_id,
            workspace_id=SCOPE.workspace_id,
        )
        permit.update(changes)
        return permit

    def check(self, adapter, *, auth=None, lab=None):
        return (lab or self.lab).reconcile(
            self.key, adapter=adapter,
            authorize=lambda _: self.permission() if auth is None else auth,
            now=NOW + timedelta(minutes=10),
        )

    def current(self):
        return self.lab.get(self.key)

    def fake_confirm(self, ref="winner"):
        return self.base._confirm(
            self.key, effect_ref=ref, confirmed_at=NOW + timedelta(minutes=8),
            result={"synthetic": True},
        )

    def mutate(self, fragment, args=()):
        with self.lab._managed_write_transaction():
            self.lab.db.execute(
                "UPDATE action_outbox SET " + fragment +
                " WHERE idempotency_key=? AND owner=? AND tenant=? AND workspace=?",
                (*args, self.key, SCOPE.owner_id,
                 SCOPE.tenant_id, SCOPE.workspace_id),
            )

    def assert_stale(self, result, *, state=None):
        self.assertEqual(result["reconcile_state"], "G42_STALE_REPLY_NO_WRITE")
        self.assertEqual(result["state"], state or self.current()["state"])

    def test_01_synthetic_positive_receipt_confirms_only_locally(self):
        fake = ReconcileStub()
        result = self.check(fake)
        self.assertEqual(result["state"], "CONFIRMED")
        self.assertEqual(result["reconcile_state"], "CONFIRMED")
        self.assertEqual(self.lab.effect_count(), 1)
        self.assertEqual(fake.calls, 1)
        self.assertFalse(result["executes_action"])
        print("G42_MATCHED_SNAPSHOT_GREEN=ONE_ATOMIC_SYNTHETIC_EFFECT")

    def test_02_authority_denied_never_touches_getter(self):
        trap = GetterTrap()
        result = self.check(trap, auth=self.permission(allowed=False))
        self.assertEqual(result["reconcile_state"], "RECONCILE_AUTH_DENIED_NO_LOOKUP")
        self.assertEqual(trap.getters, 0)
        self.assertEqual(self.current()["state"], "UNCERTAIN")

    def test_03_getter_confirms_before_reconcile_call(self):
        fake = ReconcileStub(on_get=lambda: self.fake_confirm("winner"))
        result = self.check(fake)
        self.assert_stale(result, state="CONFIRMED")
        self.assertEqual(fake.calls, 0)
        self.assertEqual(self.current()["effect_ref"], "winner")
        self.assertEqual(self.lab.effect_count(), 1)
        print("G42_GETTER_REENTRY_GREEN=CONFIRMED_NOT_DOWNGRADED")

    def test_04_getter_revokes_before_reconcile_call(self):
        fake = ReconcileStub(on_get=lambda: self.mutate(
            "state='REVOKED', last_error='g42-synthetic-revoked'"))
        result = self.check(fake)
        self.assert_stale(result, state="REVOKED")
        self.assertEqual(fake.calls, 0)
        self.assertEqual(self.lab.effect_count(), 0)

    def test_05_getter_changes_attempts_generation(self):
        fake = ReconcileStub(on_get=lambda: self.mutate("attempts=attempts+1"))
        result = self.check(fake)
        self.assert_stale(result, state="UNCERTAIN")
        self.assertEqual(fake.calls, 0)
        self.assertEqual(self.current()["attempts"], 2)

    def test_06_getter_changes_lease_owner(self):
        fake = ReconcileStub(on_get=lambda: self.mutate(
            "lease_owner='another-worker'"))
        result = self.check(fake)
        self.assert_stale(result)
        self.assertEqual(fake.calls, 0)

    def test_07_callback_confirms_then_returns_conflicting_ref(self):
        fake = ReconcileStub(
            on_call=lambda: self.fake_confirm("winner"),
            response={"found": True, "confirmed": True, "effect_ref": "loser"})
        result = self.check(fake)
        self.assert_stale(result, state="CONFIRMED")
        self.assertEqual(self.current()["effect_ref"], "winner")
        self.assertEqual(self.lab.effect_count(), 1)
        print("G42_CALLBACK_REENTRY_GREEN=LOSING_RESULT_NOT_CONFIRMED")

    def test_08_callback_confirms_then_raises(self):
        def confirmed_then_error():
            self.fake_confirm("winner")
            raise OSError("g42-synthetic-lookup-response-unknown")
        fake = ReconcileStub(on_call=confirmed_then_error)
        result = self.check(fake)
        self.assert_stale(result, state="CONFIRMED")
        self.assertEqual(self.current()["effect_ref"], "winner")
        self.assertEqual(self.lab.effect_count(), 1)

    def test_09_callback_changes_phase_then_returns_negative(self):
        fake = ReconcileStub(
            on_call=lambda: self.mutate("state='SENT', sent_at='g42-synthetic'"),
            response={"found": False, "authoritative_absence": True})
        result = self.check(fake)
        self.assert_stale(result, state="SENT")
        self.assertEqual(self.lab.effect_count(), 0)

    def test_10_callback_changes_effect_ref_then_false_does_not_restore(self):
        fake = ReconcileStub(
            on_call=lambda: self.mutate("effect_ref='synthetic-other'"),
            response={"found": False})
        result = self.check(fake)
        self.assert_stale(result)
        self.assertEqual(self.current()["effect_ref"], "synthetic-other")

    def test_11_evidence_verifier_confirms_reentrantly(self):
        def verifier(kind, intent, result):
            self.fake_confirm("winner")
            return True
        self.lab = self.make_lab(verifier=verifier)
        fake = ReconcileStub(response={
            "found": True, "confirmed": True, "effect_ref": "loser"})
        result = self.check(fake)
        self.assert_stale(result, state="CONFIRMED")
        self.assertEqual(self.current()["effect_ref"], "winner")
        self.assertEqual(self.lab.effect_count(), 1)
        print("G42_VERIFIER_REENTRY_GREEN=EXISTING_LEDGER_PRESERVED")

    def test_12_evidence_verifier_mutates_epoch_then_accepts(self):
        def verifier(kind, intent, result):
            self.mutate("attempts=attempts+1")
            return True
        self.lab = self.make_lab(verifier=verifier)
        result = self.check(ReconcileStub())
        self.assert_stale(result)
        self.assertEqual(self.lab.effect_count(), 0)

    def test_13_direct_stale_preflight_rolls_back_effect_insert(self):
        original = self.lab._g42_reconcile_snapshot_lab(self.current())
        self.mutate("attempts=attempts+1")
        with self.assertRaisesRegex(RuntimeError, "G42_RECONCILE_SNAPSHOT_STALE_NO_LEDGER"):
            self.lab._confirm(
                self.key, effect_ref="bad-late-ref",
                confirmed_at=NOW + timedelta(minutes=10),
                result={"synthetic": True},
                reconcile_snapshot_lab=original,
            )
        self.assertEqual(self.lab.effect_count(), 0)
        self.assertEqual(self.current()["state"], "UNCERTAIN")
        self.assertFalse(self.lab.db.in_transaction)

    def test_14_already_confirmed_cannot_be_reconciled_again(self):
        self.check(ReconcileStub())
        fake = ReconcileStub()
        with self.assertRaisesRegex(ValueError, "only SENT or UNCERTAIN"):
            self.check(fake)
        self.assertEqual(fake.getters, 0)
        self.assertEqual(self.lab.effect_count(), 1)

    def test_15_not_found_stays_uncertain_without_retry(self):
        fake = ReconcileStub(response={
            "found": False, "authoritative_absence": True})
        result = self.check(fake)
        self.assertEqual(result["reconcile_state"], "STILL_UNCERTAIN")
        self.assertEqual(result["state"], "UNCERTAIN")
        self.assertIsNone(self.lab.claim_next(
            WORKER, now=NOW + timedelta(minutes=11)))
        self.assertEqual(self.lab.effect_count(), 0)

    def test_16_untrusted_verifier_disabled_does_not_confirm(self):
        self.lab = self.make_lab(verifier=lambda *_: False)
        result = self.check(ReconcileStub())
        self.assertEqual(result["state"], "UNCERTAIN")
        self.assertEqual(self.lab.effect_count(), 0)

    def test_17_reopen_preserves_snapshots_and_confirmation(self):
        self.store.close()
        self.store = SQLiteChatStore(self.file)
        self.lab = self.make_lab()
        result = self.check(ReconcileStub())
        self.assertEqual(result["state"], "CONFIRMED")
        self.store.close()
        self.store = SQLiteChatStore(self.file)
        self.lab = self.make_lab()
        self.assertEqual(self.lab.effect_count(), 1)
        self.assertEqual(self.current()["effect_ref"], "g42-result")
        print("G42_REOPEN_GREEN=PERSISTENT_CONFIRM_AND_EFFECT_LEDGER")

    def test_18_legacy_reconcile_stale_response_is_always_fenced_g52(self):
        # G52 upgrades the historical intentional RED to an actual no-write gate
        # for unsafe synthetic callback mode, even with strict flag disabled.
        legacy = self.make_lab(strict=False)
        fake = ReconcileStub(
            on_call=lambda: self.fake_confirm("winner"),
            response={"found": False})
        result = self.check(fake, lab=legacy)
        self.assertEqual(result["reconcile_state"], "G42_STALE_REPLY_NO_WRITE")
        self.assertEqual(result["state"], "CONFIRMED")
        self.assertEqual(legacy.get(self.key)["state"], "CONFIRMED")
        self.assertEqual(legacy.effect_count(), 1)
        print("G52_G42_LEGACY_STALE_GREEN=NO_OLD_SNAPSHOT")

    def test_19_fake_verifier_true_still_not_real_provider_receipt_red(self):
        result = self.check(ReconcileStub(response={
            "found": True, "confirmed": True, "effect_ref": "fabricated"}))
        self.assertEqual(result["state"], "CONFIRMED")
        self.assertEqual(self.current()["effect_ref"], "fabricated")
        print("G42_LOCAL_RECEIPT_RED=HOST_CALLBACK_ACCEPTS_FABRICATED_EFFECT")

    def test_20_host_rollback_restores_old_uncertain_snapshot_red(self):
        self.store.close()
        backup = self.file.parent / "outbox-before-confirm.sqlite3"
        shutil.copyfile(self.file, backup)
        self.store = SQLiteChatStore(self.file)
        self.lab = self.make_lab()
        self.check(ReconcileStub())
        self.assertEqual(self.current()["state"], "CONFIRMED")
        self.store.close()
        shutil.copyfile(backup, self.file)
        self.store = SQLiteChatStore(self.file)
        self.lab = self.make_lab()
        self.assertEqual(self.current()["state"], "UNCERTAIN")
        self.assertEqual(self.lab.effect_count(), 0)
        print("G42_HOST_ROLLBACK_RED=LOCAL_CAS_CANNOT_RECOVER_LOST_CONFIRMATION")

    def test_21_option_must_be_true_boolean(self):
        with self.assertRaisesRegex(TypeError, "strict_reconcile_snapshot_cas_lab"):
            ExecutionOutbox(self.store, SCOPE, strict_reconcile_snapshot_cas_lab=1)

    def test_22_default_quarantine_ignores_even_scoped_synthetic_reply(self):
        denied = ExecutionOutbox(
            self.store, SCOPE, strict_reconcile_snapshot_cas_lab=True)
        fake = GetterTrap()
        result = denied.reconcile(
            self.key, adapter=fake, authorize=lambda _: self.permission(),
            now=NOW + timedelta(minutes=10),
        )
        self.assertEqual(result["reconcile_state"], "EXTERNAL_TRUST_NOT_CONFIGURED")
        self.assertEqual(fake.getters, 0)
        self.assertEqual(denied.effect_count(), 0)


    def test_23_reconfirm_same_effect_keeps_original_timestamp(self):
        first = self.check(ReconcileStub())
        self.assertEqual(first["state"], "CONFIRMED")
        original = self.current()
        count_before = self.lab.effect_count()
        repeated = self.lab._confirm(
            self.key, effect_ref="g42-result",
            confirmed_at=NOW + timedelta(hours=1),
            result={"synthetic": "replay-with-different-metadata"},
        )
        self.assertEqual(repeated["confirmed_at"], original["confirmed_at"])
        self.assertEqual(repeated["effect_ref"], original["effect_ref"])
        self.assertEqual(self.lab.effect_count(), count_before)
        ledger = self.store.db.execute(
            "SELECT confirmed_at FROM action_effects WHERE idempotency_key=?",
            (self.key,),
        ).fetchone()
        self.assertEqual(ledger["confirmed_at"], original["confirmed_at"])
        print("G42_RECONFIRM_IDEMPOTENT_GREEN=ORIGINAL_TIMESTAMP_AND_LEDGER_FROZEN")

    def test_24_reconfirm_conflicting_ref_denied_without_mutation(self):
        self.check(ReconcileStub())
        original = self.current()
        with self.assertRaisesRegex(RuntimeError, "G42_CONFIRMED_LEDGER_INVARIANT_DENY"):
            self.lab._confirm(
                self.key, effect_ref="conflicting-ref",
                confirmed_at=NOW + timedelta(hours=1),
                result={"synthetic": True},
            )
        self.assertEqual(self.current(), original)
        self.assertEqual(self.lab.effect_count(), 1)

    def test_25_revoked_row_cannot_be_synthetically_confirmed(self):
        self.mutate("state='REVOKED', last_error='synthetic-revocation'")
        original = self.current()
        with self.assertRaisesRegex(RuntimeError, "G42_UNSAFE_PRECONFIRM_PHASE_DENY"):
            self.lab._confirm(
                self.key, effect_ref="synthetic-invalid",
                confirmed_at=NOW + timedelta(minutes=10),
                result={"synthetic": True},
            )
        self.assertEqual(self.current(), original)
        self.assertEqual(self.lab.effect_count(), 0)
        self.assertFalse(self.lab.db.in_transaction)

    def test_26_failed_row_cannot_be_synthetically_confirmed(self):
        self.mutate("state='FAILED', last_error='synthetic-failed'")
        with self.assertRaisesRegex(RuntimeError, "G42_UNSAFE_PRECONFIRM_PHASE_DENY"):
            self.lab._confirm(
                self.key, effect_ref="synthetic-invalid",
                confirmed_at=NOW + timedelta(minutes=10),
            )
        self.assertEqual(self.current()["state"], "FAILED")
        self.assertEqual(self.lab.effect_count(), 0)

    def test_27_existing_confirmed_row_with_inconsistent_ledger_denied(self):
        self.check(ReconcileStub())
        self.store.db.execute(
            "UPDATE action_effects SET confirmed_at='1999-01-01T00:00:00+00:00' "
            "WHERE idempotency_key=?", (self.key,)
        )
        self.store.db.commit()
        old = self.current()
        with self.assertRaisesRegex(RuntimeError, "G42_CONFIRMED_LEDGER_INVARIANT_DENY"):
            self.lab._confirm(
                self.key, effect_ref="g42-result",
                confirmed_at=NOW + timedelta(hours=1),
            )
        self.assertEqual(self.current(), old)
        self.assertFalse(self.lab.db.in_transaction)
        print("G42_LEDGER_INCONSISTENCY_GREEN=REFUSE_TO_REWRITE_CONTRADICTORY_HISTORY")

    def test_28_legacy_outbox_json_projection_stale_red(self):
        self.check(ReconcileStub())
        raw = self.store.db.execute(
            "SELECT data FROM action_outbox WHERE idempotency_key=?",
            (self.key,),
        ).fetchone()["data"]
        import json
        projected = json.loads(raw)
        self.assertEqual(self.current()["state"], "CONFIRMED")
        self.assertEqual(projected["state"], "PENDING")
        print("G42_SNAPSHOT_JSON_RED=LEGACY_EMBEDDED_STATE_NOT_TRANSITIONED")


if __name__ == "__main__":
    unittest.main()
