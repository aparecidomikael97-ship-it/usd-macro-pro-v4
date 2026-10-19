"""P0 LAB: targeted negative alternatives for historical Outbox/Saga CAS and reconcile REDs.

These assert actual no-producer fail-closed behavior rather than forcing old
positive adapter expectations. Historical canonical tests stay RED/OPEN; no
external producer, writer, trusted receipt, Worker or resend is simulated.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_execution_outbox import ExecutionOutbox
import test_atlasquant_aion_execution_saga as saga_fx

NOW = saga_fx.NOW
REGISTRY = Path(__file__).resolve().parent / (
    "docs/aion/AION_P0_QUALITY_CANONICAL_85_FAILURES_CASE_REGISTRY_20261019.json"
)
HISTORICAL_METHODS = (
    ("test_atlasquant_aion_execution_outbox", "OutboxReconcileStaleRetryCASP0Tests",
     "test_stale_absence_must_not_reopen_confirmed_effect"),
    ("test_atlasquant_aion_execution_outbox", "OutboxReconcileStaleRetryCASP0Tests",
     "test_stale_absence_cannot_reopen_revoked_state"),
    ("test_atlasquant_aion_execution_outbox", "OutboxReconcileStaleRetryCASP0Tests",
     "test_unverified_absence_cannot_invoke_authorize_or_reopen_retry"),
    ("test_atlasquant_aion_execution_outbox", "OutboxPostSendStateCASP0Tests",
     "test_reconcile_confirmed_cannot_revive_revoked"),
    ("test_atlasquant_aion_execution_outbox", "OutboxPostSendStateCASP0Tests",
     "test_stale_sent_response_cannot_overwrite_confirmed"),
    ("test_atlasquant_aion_execution_outbox", "OutboxPostSendStateCASP0Tests",
     "test_exception_after_peer_confirmation_never_clobbers_it"),
    ("test_atlasquant_aion_execution_outbox", "OutboxStaleStateBlockCASP0Tests",
     "test_reconcile_late_block_cannot_clobber_confirmation"),
    ("test_atlasquant_aion_execution_outbox", "OutboxUnverifiedAdapterResultP0Tests",
     "test_false_authoritative_absence_remains_quarantined"),
    ("test_atlasquant_aion_execution_outbox", "AionUntrustedPositiveAdmissionRedTests",
     "test_unverified_positive_from_reconcile_must_not_record_real_effect"),
    ("test_atlasquant_aion_execution_saga", "ExecutionSagaTests",
     "test_uncertain_forward_effect_freezes_saga_until_reconciliation"),
    ("test_atlasquant_aion_execution_saga", "ExecutionSagaTests",
     "test_uncertain_compensation_freezes_remaining_rollback_until_reconciled"),
    ("test_atlasquant_aion_execution_saga", "ExecutionSagaTests",
     "test_compensation_unverified_failure_requires_external_review_before_manual_terminal"),
)


class _HostileAdapter:
    def __init__(self):
        self.reads = 0
        self.calls = 0

    @property
    def reconcile(self):
        self.reads += 1
        raise AssertionError("adversarial reconcile descriptor accessed")

    @property
    def send(self):
        self.reads += 1
        raise AssertionError("adversarial send descriptor accessed")


class OutboxHistoricReconcileDenialLAB(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = SQLiteChatStore(Path(self.tmp.name) / "cas-local.sqlite3")
        self.addCleanup(self.store.close)
        self.scope = Scope("hist-outbox-owner", "hist-outbox-tenant", "hist-outbox-space")
        self.outbox = ExecutionOutbox(self.store, self.scope)
        self.first = self.outbox.enqueue(
            intent_ref="first", action="local_stage_only",
            payload={"kind": "no-provider"},
            aggregate_key="same-aggregate", policy_version="local-v1",
            authorization_ref="local-fixture-not-proof",
            created_at=NOW, valid_until=NOW + timedelta(minutes=5))
        self.second = self.outbox.enqueue(
            intent_ref="second", action="local_stage_only",
            payload={"kind": "no-provider-followup"},
            aggregate_key="same-aggregate", policy_version="local-v1",
            authorization_ref="local-fixture-not-proof",
            created_at=NOW, valid_until=NOW + timedelta(minutes=5))
        self.key = self.first["idempotency_key"]
        self.later = self.second["idempotency_key"]

    def _stage(self, state, *, previously_claimed=False):
        if previously_claimed:
            self.assertEqual(self.outbox.claim_next(
                "fixture-worker", now=NOW + timedelta(seconds=1),
                lease_seconds=60)["state"], "CLAIMED")
        with self.store.db:
            self.store.db.execute(
                "UPDATE action_outbox SET state=?,last_error='LOCAL_NO_RECEIPT' "
                "WHERE idempotency_key=?", (state,self.key))
        self.assertEqual(self.outbox.get(self.key)["state"], state)
        return self.outbox.get(self.key)

    def _deny_reconcile(self, *, state):
        before = self._stage(state)
        adapter = _HostileAdapter()
        auth_calls = []
        def authorize(_decision):
            auth_calls.append(True)
            raise AssertionError("authorization callback must not execute")
        with self.assertRaisesRegex(
            PermissionError, "^INDEPENDENT_PRODUCER_NOT_ENROLLED$"
        ):
            self.outbox.reconcile(
                self.key, adapter=adapter, authorize=authorize,
                now=NOW + timedelta(seconds=2))
        self.assertEqual(adapter.reads, 0)
        self.assertEqual(adapter.calls, 0)
        self.assertEqual(auth_calls, [])
        self.assertEqual(self.outbox.get(self.key), before)
        self.assertEqual(self.outbox.get(self.later)["state"], "PENDING")
        self.assertIsNone(self.outbox.claim_next(
            "second-worker", now=NOW + timedelta(seconds=3)))
        self.assertEqual(self.outbox.effect_count(), 0)

    def test_01_uncertain_negative_absence_denied_before_callback(self):
        self._deny_reconcile(state="UNCERTAIN")

    def test_02_sent_positive_self_attestation_denied_before_property(self):
        self._deny_reconcile(state="SENT")

    def test_03_locally_revoked_peer_never_revived_by_stale_reconcile(self):
        self._stage("SENT")
        with self.store.db:
            self.store.db.execute(
                "UPDATE action_outbox SET state='REVOKED' WHERE idempotency_key=?",
                (self.key,))
        adapter=_HostileAdapter()
        with self.assertRaisesRegex(ValueError,"only SENT or UNCERTAIN"):
            self.outbox.reconcile(self.key,adapter=adapter,
                authorize=lambda _:True,now=NOW+timedelta(seconds=2))
        self.assertEqual(adapter.reads,0)
        self.assertEqual(self.outbox.get(self.key)["state"],"REVOKED")
        self.assertEqual(self.outbox.effect_count(),0)

    def test_04_locally_confirmed_peer_is_not_reopened_by_late_absence(self):
        self._stage("UNCERTAIN")
        with self.store.db:
            self.store.db.execute(
                "UPDATE action_outbox SET state='CONFIRMED',"
                "effect_ref='FAKE-LOCAL-NOT-A-RECEIPT',confirmed_at=? "
                "WHERE idempotency_key=?", (NOW.isoformat(),self.key))
        adapter=_HostileAdapter()
        with self.assertRaisesRegex(ValueError,"only SENT or UNCERTAIN"):
            self.outbox.reconcile(self.key,adapter=adapter,
                authorize=lambda _:True,now=NOW+timedelta(seconds=2))
        self.assertEqual(adapter.reads,0)
        self.assertEqual(self.outbox.get(self.key)["state"],"CONFIRMED")
        self.assertEqual(self.outbox.effect_count(),0)

    def test_05_snapshot_claim_stale_state_cannot_be_revoked(self):
        self.outbox.claim_next("fixture-worker",now=NOW+timedelta(seconds=1))
        before=self.outbox.get(self.key)
        self._stage("SENT")
        with self.assertRaisesRegex(RuntimeError,"stale outbox state/lease"):
            self.outbox._set_blocked(
                self.key,"REVOKED","stale-window",expected=before)
        self.assertEqual(self.outbox.get(self.key)["state"],"SENT")
        self.assertEqual(self.outbox.effect_count(),0)

    def test_06_ambiguous_row_with_forged_local_effect_never_promotes(self):
        self._stage("SENT")
        with self.store.db:
            self.store.db.execute(
                """INSERT INTO action_effects(
                   idempotency_key,owner,tenant,workspace,effect_ref,confirmed_at,data
                   ) VALUES (?,?,?,?,?,?,?)""",
                (self.key,self.scope.owner_id,self.scope.tenant_id,
                 self.scope.workspace_id,"FAKE-LOCAL-EFFECT",NOW.isoformat(),"{}"))
        before=self.outbox.get(self.key)
        adapter=_HostileAdapter()
        with self.assertRaisesRegex(
            PermissionError,"^INDEPENDENT_PRODUCER_NOT_ENROLLED$"
        ):
            self.outbox.reconcile(self.key,adapter=adapter,
                authorize=lambda _:True,now=NOW+timedelta(seconds=2))
        self.assertEqual(adapter.reads,0)
        self.assertEqual(self.outbox.get(self.key),before)
        self.assertEqual(self.outbox.effect_count(),1)
        self.assertEqual(self.outbox.get(self.later)["state"],"PENDING")

    def test_07_revocation_during_lease_is_legal_only_before_send(self):
        self.outbox.claim_next("fixture-worker",now=NOW+timedelta(seconds=1))
        expected=self.outbox.get(self.key)
        revoked=self.outbox._set_blocked(
            self.key,"REVOKED","synthetic-policy-revoked",expected=expected)
        self.assertEqual(revoked["state"],"REVOKED")
        self.assertEqual(revoked["last_error"],"synthetic-policy-revoked")
        self.assertEqual(self.outbox.effect_count(),0)
        self.assertEqual(self.outbox.get(self.later)["state"],"PENDING")
        self.assertIsNone(self.outbox.claim_next(
            "second-worker",now=NOW+timedelta(seconds=3)))

    def test_08_self_attested_rejection_both_retry_flags_cannot_clear_fifo(self):
        for retryable in (True,False):
            with self.subTest(retryable=retryable), tempfile.TemporaryDirectory() as raw:
                store=SQLiteChatStore(Path(raw) / "isolated-rejection.sqlite3")
                try:
                    outbox=ExecutionOutbox(store,self.scope)
                    def enqueue(ref):
                        return outbox.enqueue(
                            intent_ref=ref,action="local_only",
                            payload={"ref":ref},aggregate_key="client-local",
                            policy_version="local-v1",
                            authorization_ref="local-fixture-not-proof",
                            created_at=NOW,valid_until=NOW+timedelta(minutes=5))
                    first=enqueue("first")
                    second=enqueue("second")
                    self.assertEqual(outbox.claim_next("fixture-worker",
                        now=NOW+timedelta(seconds=1))["state"],"CLAIMED")
                    class ClaimingReject:
                        def __init__(self): self.send_calls=0
                        def send(self,_decision,_key):
                            self.send_calls+=1
                            return {"accepted":False,"retryable":retryable}
                    adapter=ClaimingReject()
                    def authorize(_):
                        return {
                            "allowed":True,
                            "actor_id":self.scope.owner_id,
                            "tenant_id":self.scope.tenant_id,
                            "workspace_id":self.scope.workspace_id,
                            "policy_version":"local-v1",
                            "authorization_ref":"local-fixture-not-proof",
                            "reauthenticated":True,
                            "reauth_ref":"local-only",
                        }
                    with self.assertRaisesRegex(
                        PermissionError,"INDEPENDENT_PRODUCER_NOT_ENROLLED"
                    ):
                        outbox.dispatch_claimed(
                            first["idempotency_key"],worker_id="fixture-worker",
                            adapter=adapter,authorize=authorize,
                            now=NOW+timedelta(seconds=2))
                    self.assertEqual(adapter.send_calls,0)
                    self.assertEqual(outbox.get(first["idempotency_key"])["state"],
                                     "BLOCKED_PRODUCER")
                    self.assertEqual(outbox.get(second["idempotency_key"])["state"],
                                     "PENDING")
                    self.assertIsNone(outbox.claim_next(
                        "another-worker",now=NOW+timedelta(seconds=3)))
                    self.assertEqual(outbox.effect_count(),0)
                finally:
                    store.close()

    def test_09_historical_names_remain_red_in_source_registry(self):
        data=json.loads(REGISTRY.read_text(encoding="utf-8"))
        keys={(e["module"],e["test_class"],e["case"]):
              e for e in data["entries"]}
        self.assertEqual(len(HISTORICAL_METHODS),12)
        self.assertEqual(len(set(HISTORICAL_METHODS)),12)
        for triple in HISTORICAL_METHODS:
            with self.subTest(case=triple):
                self.assertIn(triple,keys)
                entry=keys[triple]
                self.assertEqual(entry["kind"],"ERROR")
                self.assertEqual(entry["triage_status"],"OPEN_NOT_WAIVED")


class SagaHistoricReconcileDenialLAB(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.fx=saga_fx.ExecutionSagaTests()
        self.fx.setUp()
        self.store,self.outbox,self.budget,self.saga=self.fx._components(
            self.tmp.name)
        self.addCleanup(self.store.close)
        self.fx._create(self.saga)

    def stage(self):
        return self.fx._enqueue_forward(self.saga)

    def test_10_uncertain_state_blocks_future_step_and_compensation(self):
        item=self.stage()
        key=item["outbox"]["idempotency_key"]
        with self.store.db:
            self.store.db.execute(
                "UPDATE action_outbox SET state='UNCERTAIN',"
                "last_error='LOST_LOCAL_RESPONSE_NO_PROOF' WHERE idempotency_key=?",
                (key,))
        result=self.saga.sync_forward_outcome(
            "saga-1","one",now=NOW+timedelta(seconds=1))
        self.assertEqual(result["state"],"RECONCILIATION_REQUIRED")
        with self.assertRaisesRegex(ValueError,"saga state does not allow"):
            self.fx._enqueue_forward(self.saga,offset=2)
        with self.assertRaisesRegex(ValueError,"not eligible"):
            self.saga.prepare_compensation(
                "saga-1",explicit_human_approval=True,
                approval_ref="LOCAL-ONLY",reauth_ref="LOCAL-ONLY",
                now=NOW+timedelta(seconds=2))
        self.assertEqual(self.outbox.effect_count(),0)

    def test_11_forged_positive_cannot_clear_saga_uncertainty(self):
        item=self.stage()
        key=item["outbox"]["idempotency_key"]
        with self.store.db:
            self.store.db.execute(
                "UPDATE action_outbox SET state='UNCERTAIN' WHERE idempotency_key=?",
                (key,))
        self.assertEqual(self.saga.sync_forward_outcome(
            "saga-1","one",now=NOW+timedelta(seconds=1))["state"],
            "RECONCILIATION_REQUIRED")
        snapshot=self.saga.get("saga-1")
        with self.store.db:
            self.store.db.execute(
                "UPDATE action_outbox SET state='CONFIRMED',"
                "effect_ref='LOCAL-FAKE' WHERE idempotency_key=?", (key,))
        with self.assertRaisesRegex(
            PermissionError,"INDEPENDENT_PRODUCER_RECEIPT_NOT_ENROLLED"
        ):
            self.saga.sync_forward_outcome(
                "saga-1","one",now=NOW+timedelta(seconds=2))
        self.assertEqual(self.saga.get("saga-1"),snapshot)
        self.assertEqual(self.outbox.effect_count(),0)

    def test_12_fake_failed_compensation_cannot_be_declared_terminal(self):
        item=self.stage()
        key=item["outbox"]["idempotency_key"]
        with self.store.db:
            self.store.db.execute(
                "UPDATE action_outbox SET state='FAILED' WHERE idempotency_key=?",
                (key,))
            self.store.db.execute(
                "UPDATE aion_execution_saga_steps SET compensation_outbox_key=? "
                "WHERE saga_id='saga-1' AND step_key='one'",(key,))
        before=self.saga.get("saga-1")
        with self.assertRaisesRegex(
            PermissionError,"INDEPENDENT_PRODUCER_NO_EFFECT_FENCE_NOT_ENROLLED"
        ):
            self.saga.sync_compensation_outcome(
                "saga-1","one",now=NOW+timedelta(seconds=2))
        self.assertEqual(self.saga.get("saga-1"),before)
        self.assertEqual(self.outbox.effect_count(),0)


if __name__=="__main__":
    unittest.main()
