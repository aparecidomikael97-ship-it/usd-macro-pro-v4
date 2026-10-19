"""P0 LAB: original 32 Outbox/Saga RED cases, internal-state recovery controls.

Never import these fixtures into a product host. No real producer, network,
external writer, Worker, or authenticated effect is involved. This suite tests
currently reachable safe state transitions and explicit DENIAL of effect
promotion; it DOES NOT waive the 23+9 historical Quality failures.
"""
from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_execution_outbox import ExecutionOutbox
import test_atlasquant_aion_execution_saga as saga_fx

ROOT = Path(__file__).resolve().parent
NOW = saga_fx.NOW
REGISTRY = ROOT / "docs/aion/AION_P0_QUALITY_CANONICAL_85_FAILURES_CASE_REGISTRY_20261019.json"


class _HostileAdapter:
    @property
    def send(self):
        raise AssertionError("adapter.send descriptor must not be read")

    @property
    def reconcile(self):
        raise AssertionError("adapter.reconcile descriptor must not be read")


class OutboxInternalStateLAB(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = SQLiteChatStore(Path(self.tmp.name) / "sandbox.sqlite3")
        self.addCleanup(self.store.close)
        self.scope = Scope("owner-lab", "tenant-lab", "workspace-lab")
        self.outbox = ExecutionOutbox(self.store, self.scope)

    def enqueue(self, *, ref="intent-lab-1", aggregate="same-client", payload=None):
        return self.outbox.enqueue(
            intent_ref=ref,
            action="stage_only",
            payload=payload if payload is not None else {"purpose": "local-test"},
            aggregate_key=aggregate,
            policy_version="policy-v1",
            authorization_ref="approval-local-fixture",
            created_at=NOW,
            valid_until=NOW + timedelta(minutes=5),
        )

    def authorization(self, _decision):
        return {
            "allowed": True,
            "actor_id": self.scope.owner_id,
            "tenant_id": self.scope.tenant_id,
            "workspace_id": self.scope.workspace_id,
            "policy_version": "policy-v1",
            "authorization_ref": "approval-local-fixture",
            "reauthenticated": True,
            "reauth_ref": "reauth-local",
        }

    def test_01_historical_case_ledger_exact_32_unwaived(self):
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
        entries = [
            row for row in data["entries"]
            if row["module"] in (
                "test_atlasquant_aion_execution_outbox",
                "test_atlasquant_aion_execution_saga",
            )
        ]
        counts = {
            mod: sum(row["module"] == mod for row in entries)
            for mod in ("test_atlasquant_aion_execution_outbox",
                        "test_atlasquant_aion_execution_saga")
        }
        self.assertEqual(list(counts.values()), [23, 9])
        self.assertEqual(len(entries), 32)
        identities = [
            (x["module"], x["test_class"], x["case"], x["subtest_context"])
            for x in entries
        ]
        self.assertEqual(len(set(identities)), 32)
        self.assertEqual(sum(x["subtest_context"] is not None for x in entries), 4)
        self.assertTrue(all(x["kind"] == "ERROR" and
                            x["triage_status"] == "OPEN_NOT_WAIVED"
                            for x in entries))
        self.assertEqual(data["fail_total"], 51)
        self.assertEqual(data["error_total"], 34)

    def test_02_enqueue_is_idempotent_and_payload_collision_denied(self):
        first = self.enqueue()
        duplicate = self.enqueue()
        self.assertEqual(first["enqueue_state"], "ENQUEUED")
        self.assertEqual(duplicate["enqueue_state"], "IDEMPOTENT")
        self.assertEqual(first["idempotency_key"], duplicate["idempotency_key"])
        with self.assertRaisesRegex(ValueError, "idempotency collision"):
            self.enqueue(payload={"purpose": "different"})
        self.assertEqual(len(self.outbox.list()), 1)
        self.assertEqual(self.outbox.effect_count(), 0)

    def test_03_outbox_and_decision_rollback_together_on_sqlite_failure(self):
        self.store.db.executescript("""
            CREATE TRIGGER lab_no_outbox
            BEFORE INSERT ON action_outbox
            BEGIN SELECT RAISE(ABORT, 'lab atomicity fault'); END;
        """)
        with self.assertRaises(sqlite3.IntegrityError):
            self.enqueue()
        self.assertEqual(self.store.db.execute(
            "SELECT count(*) FROM action_outbox").fetchone()[0], 0)
        self.assertEqual(self.store.db.execute(
            "SELECT count(*) FROM action_decisions").fetchone()[0], 0)

    def test_04_no_producer_denied_before_adapter_property_access(self):
        item = self.enqueue()
        key = item["idempotency_key"]
        claimed = self.outbox.claim_next(
            "local-claim", now=NOW + timedelta(seconds=1), lease_seconds=60)
        self.assertEqual(claimed["state"], "CLAIMED")
        with self.assertRaisesRegex(
            PermissionError, "^INDEPENDENT_PRODUCER_NOT_ENROLLED$"
        ):
            self.outbox.dispatch_claimed(
                key, worker_id="local-claim", authorize=self.authorization,
                adapter=_HostileAdapter(), now=NOW + timedelta(seconds=2))
        row = self.outbox.get(key)
        self.assertEqual(row["state"], "BLOCKED_PRODUCER")
        self.assertEqual(row["last_error"], "INDEPENDENT_PRODUCER_NOT_ENROLLED")
        self.assertEqual(row["lease_owner"], "")
        self.assertEqual(self.outbox.effect_count(), 0)

    def test_05_blocked_producer_keeps_aggregate_order(self):
        first = self.enqueue()
        second = self.enqueue(ref="intent-lab-2")
        self.outbox.claim_next("local-claim", now=NOW + timedelta(seconds=1))
        with self.assertRaisesRegex(PermissionError, "INDEPENDENT_PRODUCER_NOT_ENROLLED"):
            self.outbox.dispatch_claimed(
                first["idempotency_key"], worker_id="local-claim",
                authorize=self.authorization, adapter=_HostileAdapter(),
                now=NOW + timedelta(seconds=2))
        self.assertEqual(self.outbox.get(second["idempotency_key"])["state"], "PENDING")
        self.assertIsNone(
            self.outbox.claim_next("local-second", now=NOW + timedelta(seconds=3)))
        self.assertEqual(self.outbox.effect_count(), 0)

    def test_06_reconcile_uncertain_never_reads_adapter_or_authorize(self):
        item = self.enqueue()
        key = item["idempotency_key"]
        with self.store.db:
            self.store.db.execute(
                "UPDATE action_outbox SET state='UNCERTAIN',last_error='SYNTHETIC_UNKNOWN' "
                "WHERE idempotency_key=?", (key,))
        before = self.outbox.get(key)
        def forbidden_authorize(_decision):
            raise AssertionError("authorization callback must not be invoked")
        with self.assertRaisesRegex(
            PermissionError, "^INDEPENDENT_PRODUCER_NOT_ENROLLED$"
        ):
            self.outbox.reconcile(
                key, adapter=_HostileAdapter(), authorize=forbidden_authorize,
                now=NOW + timedelta(seconds=2))
        self.assertEqual(self.outbox.get(key), before)
        self.assertEqual(self.outbox.effect_count(), 0)

    def test_07_ambiguous_effect_cannot_be_revoked_by_local_block(self):
        item = self.enqueue()
        key = item["idempotency_key"]
        with self.store.db:
            self.store.db.execute(
                "UPDATE action_outbox SET state='SENT',last_error='SYNTHETIC_UNKNOWN' "
                "WHERE idempotency_key=?", (key,))
        before = self.outbox.get(key)
        with self.assertRaisesRegex(
            PermissionError, "UNCERTAIN_EFFECT_STATE_CANNOT_BE_REVOKED"
        ):
            self.outbox._set_blocked(
                key, "REVOKED", "lab_fake_absence", expected=before)
        self.assertEqual(self.outbox.get(key), before)
        self.assertEqual(self.outbox.effect_count(), 0)

    def test_08_private_confirm_never_promotes_local_boolean(self):
        item = self.enqueue()
        with self.assertRaisesRegex(
            PermissionError, "^INDEPENDENT_PRODUCER_RECEIPT_NOT_ENROLLED$"
        ):
            self.outbox._confirm(
                item["idempotency_key"], expected=item,
                effect_ref="LOCAL-NOT-TRUSTED", confirmed_at=NOW)
        self.assertEqual(self.outbox.get(item["idempotency_key"])["state"], "PENDING")
        self.assertEqual(self.outbox.effect_count(), 0)

    def test_09_lease_expiration_cannot_cross_external_boundary(self):
        item = self.enqueue()
        key = item["idempotency_key"]
        self.outbox.claim_next(
            "local-claim", now=NOW + timedelta(seconds=1), lease_seconds=3)
        with self.assertRaisesRegex(TimeoutError, "lease expired"):
            self.outbox.dispatch_claimed(
                key, worker_id="local-claim", authorize=self.authorization,
                adapter=_HostileAdapter(), now=NOW + timedelta(seconds=5))
        self.assertEqual(self.outbox.effect_count(), 0)


class SagaInternalStateLAB(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.fx = saga_fx.ExecutionSagaTests()
        self.fx.setUp()
        self.store, self.outbox, self.budget, self.saga = self.fx._components(
            self.tmp.name)
        self.addCleanup(self.store.close)
        self.fx._create(self.saga)

    def stage(self):
        return self.fx._enqueue_forward(self.saga)

    def test_10_first_forward_step_is_only_staged_no_effect(self):
        result = self.stage()
        self.assertEqual(result["state"], "ENQUEUED")
        self.assertFalse(result["executes_action"])
        self.assertEqual(result["saga"]["steps"][0]["state"], "ENQUEUED")
        self.assertEqual(result["saga"]["steps"][1]["state"], "PENDING")
        self.assertEqual(result["outbox"]["state"], "PENDING")
        self.assertEqual(self.outbox.effect_count(), 0)

    def test_11_saga_outbox_atomic_rollback_on_step_update_fault(self):
        with self.store.db:
            self.store.db.execute("""
                CREATE TRIGGER lab_saga_staging_fault
                BEFORE UPDATE OF state ON aion_execution_saga_steps
                BEGIN SELECT RAISE(ABORT, 'lab saga rollback'); END;
            """)
        with self.assertRaises(sqlite3.IntegrityError):
            self.stage()
        self.assertEqual(len(self.outbox.list()), 0)
        self.assertEqual(self.saga.get("saga-1")["state"], "PLANNED")
        self.assertEqual(self.saga.get("saga-1")["steps"][0]["state"], "PENDING")
        self.assertEqual(self.outbox.effect_count(), 0)

    def test_12_untrusted_confirmed_outbox_cannot_complete_saga(self):
        staged = self.stage()
        key = staged["outbox"]["idempotency_key"]
        with self.store.db:
            self.store.db.execute(
                "UPDATE action_outbox SET state='CONFIRMED',"
                "effect_ref='FAKE-LOCAL',confirmed_at=? WHERE idempotency_key=?",
                (NOW.isoformat(), key))
        before = self.saga.get("saga-1")
        with self.assertRaisesRegex(
            PermissionError, "^INDEPENDENT_PRODUCER_RECEIPT_NOT_ENROLLED$"
        ):
            self.saga.sync_forward_outcome(
                "saga-1", "one", now=NOW + timedelta(seconds=1))
        self.assertEqual(self.saga.get("saga-1"), before)
        self.assertEqual(self.outbox.effect_count(), 0)

    def test_13_untrusted_failed_outbox_is_not_no_effect_fence(self):
        staged = self.stage()
        key = staged["outbox"]["idempotency_key"]
        with self.store.db:
            self.store.db.execute(
                "UPDATE action_outbox SET state='FAILED',"
                "last_error='FAKE-LOCAL-ABSENCE' WHERE idempotency_key=?", (key,))
        before = self.saga.get("saga-1")
        with self.assertRaisesRegex(
            PermissionError, "^INDEPENDENT_PRODUCER_NO_EFFECT_FENCE_NOT_ENROLLED$"
        ):
            self.saga.sync_forward_outcome(
                "saga-1", "one", now=NOW + timedelta(seconds=1))
        self.assertEqual(self.saga.get("saga-1"), before)
        self.assertEqual(self.outbox.effect_count(), 0)

    def test_14_untrusted_compensation_outcome_is_not_promoted(self):
        staged = self.stage()
        key = staged["outbox"]["idempotency_key"]
        for state, expected in (
            ("CONFIRMED", "INDEPENDENT_PRODUCER_RECEIPT_NOT_ENROLLED"),
            ("FAILED", "INDEPENDENT_PRODUCER_NO_EFFECT_FENCE_NOT_ENROLLED"),
        ):
            with self.subTest(state=state):
                with self.store.db:
                    self.store.db.execute(
                        "UPDATE action_outbox SET state=? WHERE idempotency_key=?",
                        (state, key))
                    self.store.db.execute(
                        "UPDATE aion_execution_saga_steps "
                        "SET compensation_outbox_key=? "
                        "WHERE saga_id='saga-1' AND step_key='one'", (key,))
                before = self.saga.get("saga-1")
                with self.assertRaisesRegex(PermissionError, "^" + expected + "$"):
                    self.saga.sync_compensation_outcome(
                        "saga-1", "one", now=NOW + timedelta(seconds=2))
                self.assertEqual(self.saga.get("saga-1"), before)
                self.assertEqual(self.outbox.effect_count(), 0)

    def test_15_pending_outbox_sync_is_inert_internal_transition(self):
        self.stage()
        before_count = self.outbox.effect_count()
        result = self.saga.sync_forward_outcome(
            "saga-1", "one", now=NOW + timedelta(seconds=1))
        self.assertEqual(result["state"], "RUNNING")
        self.assertFalse(result["executes_action"])
        self.assertEqual(result["step_state"], "ENQUEUED")
        self.assertEqual(self.outbox.effect_count(), before_count)

    def test_16_compensation_requires_independent_authority_even_if_locally_eligible(self):
        self.stage()
        with self.store.db:
            self.store.db.execute(
                "UPDATE aion_execution_sagas SET state='COMPENSATION_REQUIRED' "
                "WHERE saga_id='saga-1'")
            self.store.db.execute(
                "UPDATE aion_execution_saga_steps SET state='CONFIRMED' "
                "WHERE saga_id='saga-1' AND step_key='one'")
        before = self.saga.get("saga-1")
        with self.assertRaisesRegex(
            PermissionError, "^INDEPENDENT_PRODUCER_RECEIPT_NOT_ENROLLED$"
        ):
            self.saga.prepare_compensation(
                "saga-1", explicit_human_approval=True,
                approval_ref="FAKE-LAB-ONLY", reauth_ref="FAKE-LAB-ONLY",
                now=NOW + timedelta(seconds=1))
        self.assertEqual(self.saga.get("saga-1"), before)
        self.assertEqual(self.outbox.effect_count(), 0)


if __name__ == "__main__":
    unittest.main()
