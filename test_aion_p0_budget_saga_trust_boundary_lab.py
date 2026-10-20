"""P0 LAB: budget preflight and Saga compensation/plan boundaries.

All persisted effect rows here are explicitly LOCAL ADVERSARIAL FIXTURES,
never provider receipts or execution testimony. Positive internal budget
preflight is NOT permission to dispatch, record an external effect, skip
producer enrollment, or compensate. Legacy Quality errors remain OPEN.
"""
from __future__ import annotations

from datetime import timedelta
from pathlib import Path
import tempfile
import unittest

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_cumulative_authority_budget import CumulativeAuthorityBudget
from atlasquant_aion_execution_outbox import ExecutionOutbox
from atlasquant_aion_execution_saga import ExecutionSagaCoordinator
from atlasquant_aion_saga_sequence_policy import select_compensation_step
import test_atlasquant_aion_execution_saga as historical

NOW = historical.NOW


class BudgetPreflightWithoutAuthorityLAB(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = SQLiteChatStore(Path(self.tmp.name) / "local-budget.sqlite3")
        self.addCleanup(self.store.close)
        self.scope = Scope("budget-owner", "budget-tenant", "budget-workspace")

    def budget(self, **limits):
        return CumulativeAuthorityBudget(
            self.store, self.scope,
            authority_budget_ref="budget-local",
            policy_version="policy-local",
            **limits,
        )

    def decision(self, *, transaction="tx-a", capability="LOW_RISK", risk=1):
        return {
            "owner_id": self.scope.owner_id,
            "tenant_id": self.scope.tenant_id,
            "workspace_id": self.scope.workspace_id,
            "transaction_id": transaction,
            "authority_budget_ref": "budget-local",
            "policy_version": "policy-local",
            "capability_class": capability,
            "risk_points": risk,
            "action": "local_preflight_only",
        }

    def local_ledger_row(self, *, key, transaction="tx-a", risk=1,
                         capability="LOW_RISK", seconds=0):
        """Direct SQL TEST fixture. Even a syntactically valid ledger is NOT proof."""
        with self.store.db:
            self.store.db.execute(
                """INSERT INTO aion_authority_spend(
                    idempotency_key,owner,tenant,workspace,transaction_id,
                    authority_budget_ref,policy_version,capability_class,
                    action,risk_points,effect_ref,confirmed_at,decision_digest
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (key,self.scope.owner_id,self.scope.tenant_id,
                 self.scope.workspace_id,transaction,"budget-local",
                 "policy-local",capability,"LAB_NOT_EXECUTED",risk,
                 "LAB_FAKE_EFFECT_" + key,
                 (NOW+timedelta(seconds=seconds)).isoformat(),
                 "LAB_UNTRUSTED_LEDGER_DIGEST"),
            )

    def assert_inert(self, result):
        self.assertFalse(result["grants_authority"])
        # Invalid binding responses currently omit this field. This is a
        # documented OPEN schema-parity gap, not proof of authorization.
        self.assertFalse(result.get("execution_allowed_by_this_component", False))
        self.assertFalse(result["executes_action"])

    def test_01_empty_budget_can_preflight_but_never_grants_authority(self):
        budget = self.budget()
        result = budget.guard(self.decision(), now=NOW)
        self.assertTrue(result["allowed"])
        self.assertEqual(result["reason"], "ALLOW")
        self.assert_inert(result)
        self.assertEqual(budget.snapshot("tx-a", now=NOW)["transaction_effects"], 0)

    def test_02_cross_transaction_window_from_local_rows_denies_new_candidate(self):
        budget = self.budget(max_window_effects=1)
        self.local_ledger_row(key="lab-row-1",transaction="tx-one")
        outcome = budget.guard(self.decision(transaction="tx-two"),
                               now=NOW+timedelta(seconds=1))
        self.assertFalse(outcome["allowed"])
        self.assertIn("WINDOW_EFFECT_LIMIT", outcome["blockers"])
        self.assertEqual(outcome["before"]["transaction_effects"],0)
        self.assertEqual(outcome["before"]["window_effects"],1)
        self.assert_inert(outcome)

    def test_03_transaction_risk_accumulates_internally_without_claiming_proof(self):
        budget = self.budget(max_transaction_risk_points=3)
        self.local_ledger_row(key="lab-risk-1",risk=2)
        outcome = budget.guard(self.decision(risk=2),
                               now=NOW+timedelta(seconds=1))
        self.assertFalse(outcome["allowed"])
        self.assertIn("TRANSACTION_RISK_LIMIT",outcome["blockers"])
        self.assertEqual(outcome["projected_after"]["transaction_risk_points"],4)
        self.assert_inert(outcome)

    def test_04_capability_diversity_limit_cannot_be_rebranded_as_approval(self):
        budget = self.budget(max_window_distinct_capabilities=2)
        self.local_ledger_row(key="lab-cap-low",capability="LOW_RISK")
        self.local_ledger_row(key="lab-cap-medium",capability="MEDIUM_RISK")
        outcome=budget.guard(self.decision(transaction="tx-new",
                                           capability="HIGH_RISK"),
                             now=NOW+timedelta(seconds=1))
        self.assertFalse(outcome["allowed"])
        self.assertIn("WINDOW_CAPABILITY_DIVERSITY_LIMIT",outcome["blockers"])
        self.assert_inert(outcome)

    def test_05_wrong_scope_budget_reference_policy_denied_even_if_under_budget(self):
        budget = self.budget()
        for field, fake in (
            ("owner_id","other-owner"),
            ("tenant_id","other-tenant"),
            ("workspace_id","other-workspace"),
            ("authority_budget_ref","other-budget"),
            ("policy_version","other-policy"),
        ):
            with self.subTest(field=field):
                forged = {**self.decision(), field:fake}
                out=budget.guard(forged,now=NOW)
                self.assertFalse(out["allowed"])
                self.assertTrue(out["reason"].startswith(
                    "AUTHORITY_BUDGET_BINDING_INVALID"))
                self.assert_inert(out)
                # Track rather than conceal the invalid-path response shape.
                self.assertNotIn("execution_allowed_by_this_component", out,
                    "Update the open schema-parity finding if production changes")

    def test_06_critical_capability_never_passes_budget_preflight(self):
        budget=self.budget()
        out=budget.guard(self.decision(capability="CRITICAL"), now=NOW)
        self.assertFalse(out["allowed"])
        self.assertIn("CRITICAL_CAPABILITY_REQUIRES_SEPARATE_HUMAN_GATE",
                      out["blockers"])
        self.assert_inert(out)

    def test_07_nested_budget_write_denied_without_rolling_back_parent(self):
        budget=self.budget()
        self.store.db.execute("CREATE TABLE lab_parent_tx (marker INTEGER NOT NULL)")
        self.store.db.execute("BEGIN IMMEDIATE")
        try:
            self.store.db.execute("INSERT INTO lab_parent_tx(marker) VALUES(19)")
            with self.assertRaisesRegex(
                RuntimeError,"AUTHORITY_BUDGET_NESTED_TRANSACTION_UNSUPPORTED"
            ):
                budget.record_confirmed(
                    self.decision(),idempotency_key="LAB_NOT_PROVEN",
                    effect_ref="LAB_NOT_AN_EFFECT",confirmed_at=NOW)
            self.assertTrue(self.store.db.in_transaction)
            self.assertEqual(self.store.db.execute(
                "SELECT marker FROM lab_parent_tx").fetchone()[0],19)
            self.store.db.commit()
        except BaseException:
            if self.store.db.in_transaction: self.store.db.rollback()
            raise
        self.assertEqual(self.store.db.execute(
            "SELECT marker FROM lab_parent_tx").fetchone()[0],19)
        self.assertEqual(budget.snapshot("tx-a",now=NOW)["transaction_effects"],0)

    def test_08_local_budget_row_does_not_create_outbox_effect_or_execution(self):
        budget=self.budget()
        self.local_ledger_row(key="LAB_CANNOT_VERIFY")
        self.assertEqual(budget.snapshot("tx-a",now=NOW)["transaction_effects"],1)
        outbox=ExecutionOutbox(self.store,self.scope)
        self.assertEqual(outbox.effect_count(),0)
        result=budget.guard(self.decision(transaction="tx-other"),
                            now=NOW+timedelta(seconds=1))
        self.assertTrue(result["allowed"])
        self.assert_inert(result)


class SagaPlanAndCompensationTrustLAB(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store=SQLiteChatStore(Path(self.tmp.name)/"local-saga.sqlite3")
        self.addCleanup(self.store.close)
        self.scope=Scope("plan-owner","plan-tenant","plan-space")

    def components(self, **limits):
        budget=CumulativeAuthorityBudget(
            self.store,self.scope,
            authority_budget_ref="budget-saga-local",
            policy_version="policy-saga-local",**limits)
        outbox=ExecutionOutbox(self.store,self.scope)
        saga=ExecutionSagaCoordinator(
            self.store,self.scope,outbox=outbox,authority_budget=budget)
        return budget,outbox,saga

    def steps(self):
        return [
            {"step_key":"one","action":"local_stage_one",
             "payload":{"n":1},"capability_class":"LOW_RISK",
             "risk_points":1,"reversible":True,
             "compensation_action":"local_undo_one",
             "compensation_payload":{"undo":1},
             "compensation_risk_points":1},
            {"step_key":"two","action":"local_stage_two",
             "payload":{"n":2},"capability_class":"LOW_RISK",
             "risk_points":1,"reversible":True,
             "compensation_action":"local_undo_two",
             "compensation_payload":{"undo":2},
             "compensation_risk_points":1},
        ]

    def test_09_saga_plan_rejects_worst_case_compensation_risk(self):
        budget,outbox,saga=self.components(max_transaction_risk_points=3)
        with self.assertRaisesRegex(
            ValueError,"rollback risk reserve exceeds"
        ):
            saga.create(saga_id="saga-risk",steps=self.steps(),created_at=NOW)
        self.assertEqual(outbox.list(),[])
        self.assertEqual(budget.snapshot("saga-risk",now=NOW)["transaction_effects"],0)

    def test_10_saga_plan_rejects_rollback_effect_reserve(self):
        budget,outbox,saga=self.components(max_transaction_effects=3)
        with self.assertRaisesRegex(
            ValueError,"rollback effect reserve exceeds"
        ):
            saga.create(saga_id="saga-effects",steps=self.steps(),created_at=NOW)
        self.assertEqual(outbox.list(),[])
        self.assertEqual(budget.snapshot("saga-effects",now=NOW)["transaction_effects"],0)

    def test_11_saga_critical_step_cannot_be_created_or_staged(self):
        budget,outbox,saga=self.components()
        planned=self.steps()
        planned[0]["capability_class"]="CRITICAL"
        with self.assertRaisesRegex(ValueError,"critical capability"):
            saga.create(saga_id="saga-critical",steps=planned,created_at=NOW)
        self.assertEqual(outbox.list(),[])

    def test_12_second_forward_candidate_refuses_untrusted_local_confirmation(self):
        budget,outbox,saga=self.components()
        saga.create(saga_id="saga-stage",steps=self.steps(),created_at=NOW)
        first=saga.enqueue_next("saga-stage",
            authorization_ref="lab-approval",created_at=NOW,
            valid_until=NOW+timedelta(minutes=5))
        self.assertEqual(first["state"],"ENQUEUED")
        key=first["outbox"]["idempotency_key"]
        with self.store.db:
            self.store.db.execute(
                "UPDATE aion_execution_saga_steps SET state='CONFIRMED' "
                "WHERE saga_id='saga-stage' AND step_key='one'")
            self.store.db.execute(
                "UPDATE action_outbox SET state='CONFIRMED',"
                "effect_ref='LAB_FAKE' WHERE idempotency_key=?",(key,))
        before=saga.get("saga-stage")
        with self.assertRaisesRegex(
            PermissionError,"INDEPENDENT_PRODUCER_RECEIPT_NOT_ENROLLED"
        ):
            saga.enqueue_next("saga-stage",
                authorization_ref="lab-approval-2",
                created_at=NOW+timedelta(seconds=1),
                valid_until=NOW+timedelta(minutes=5))
        self.assertEqual(saga.get("saga-stage"),before)
        self.assertEqual(len(outbox.list()),1)
        self.assertEqual(outbox.effect_count(),0)
        self.assertEqual(budget.snapshot("saga-stage",now=NOW)["transaction_effects"],0)

    def test_13_compensation_candidate_cannot_override_independent_denial(self):
        budget,outbox,saga=self.components()
        saga.create(saga_id="saga-comp",steps=self.steps(),created_at=NOW)
        # ADVERARIAL TEST-ONLY projection, no real confirmation/approval.
        with self.store.db:
            self.store.db.execute(
                "UPDATE aion_execution_sagas SET state='COMPENSATING',"
                "compensation_approval_ref='LAB_FAKE_APPROVAL',"
                "compensation_reauth_ref='LAB_FAKE_REAUTH' "
                "WHERE saga_id='saga-comp'")
            self.store.db.execute(
                "UPDATE aion_execution_saga_steps SET "
                "state='COMPENSATION_PENDING',effect_ref='LAB_FAKE_EFFECT' "
                "WHERE saga_id='saga-comp'")
        snapshot=saga.get("saga-comp")
        self.assertEqual(select_compensation_step(
            snapshot["state"],snapshot["steps"]),1)
        with self.assertRaisesRegex(
            PermissionError,"INDEPENDENT_PRODUCER_COMPENSATION_NOT_ENROLLED"
        ):
            saga.enqueue_next_compensation(
                "saga-comp",valid_until=NOW+timedelta(minutes=5),
                created_at=NOW+timedelta(seconds=1))
        self.assertEqual(saga.get("saga-comp"),snapshot)
        self.assertEqual(outbox.list(),[])
        self.assertEqual(budget.snapshot("saga-comp",now=NOW)["transaction_effects"],0)

    def test_14_saga_genesis_event_drift_blocks_enqueue_before_outbox_mutation(self):
        budget,outbox,saga=self.components()
        saga.create(saga_id="saga-tamper",steps=self.steps(),created_at=NOW)
        with self.store.db:
            self.store.db.execute(
                "UPDATE aion_execution_saga_events "
                "SET event_hash='LAB_TAMPERED' WHERE saga_id='saga-tamper' "
                "AND sequence=1")
        with self.assertRaisesRegex(
            PermissionError,"SAGA_LOCAL_INTEGRITY_MISMATCH"
        ):
            saga.enqueue_next(
                "saga-tamper",authorization_ref="LAB_NOT_TRUSTED",
                created_at=NOW,valid_until=NOW+timedelta(minutes=5))
        self.assertEqual(outbox.list(),[])
        self.assertEqual(budget.snapshot("saga-tamper",now=NOW)["transaction_effects"],0)


if __name__=="__main__":
    unittest.main()
