"""Independent adversarial LAB review of candidate PR #1331.

Read-only/offline. These fixtures do not enroll a producer, attest an effect,
authenticate HUMAN_OWNER, call any provider, grant deployment, or waive a P0.
The PR under review is left unchanged on its own branch.
"""
from __future__ import annotations
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_cumulative_authority_budget import CumulativeAuthorityBudget
from atlasquant_aion_execution_outbox import ExecutionOutbox
from atlasquant_aion_execution_saga import ExecutionSagaCoordinator
import test_atlasquant_aion_execution_saga as fixture

NOW = fixture.NOW
FALSE_FLAGS = ("grants_authority", "execution_allowed_by_this_component", "executes_action")


class _ForbiddenAdapter:
    def __init__(self):
        self.attribute_reads = 0
    @property
    def send(self):
        self.attribute_reads += 1
        raise AssertionError("adapter.send must never be read")
    @property
    def reconcile(self):
        self.attribute_reads += 1
        raise AssertionError("adapter.reconcile must never be read")


class BudgetGuardIndependentReviewLAB(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.TemporaryDirectory()
        self.addCleanup(self.root.cleanup)
        self.store = SQLiteChatStore(Path(self.root.name) / "review.sqlite3")
        self.addCleanup(self.store.close)
        self.scope = Scope("review-owner","review-tenant","review-space")
        self.outbox = ExecutionOutbox(self.store,self.scope)
        self.budget = CumulativeAuthorityBudget(
            self.store,self.scope,authority_budget_ref="review-budget",
            policy_version="review-policy",max_transaction_risk_points=3)
        self.saga = ExecutionSagaCoordinator(
            self.store,self.scope,outbox=self.outbox,authority_budget=self.budget)

    def decision(self):
        return {
            "owner_id":self.scope.owner_id,
            "tenant_id":self.scope.tenant_id,
            "workspace_id":self.scope.workspace_id,
            "transaction_id":"review-tx",
            "authority_budget_ref":"review-budget",
            "policy_version":"review-policy",
            "capability_class":"LOW_RISK",
            "action":"local_only_review",
            "risk_points":1,
        }

    def assert_no_authority(self, result):
        for name in FALSE_FLAGS:
            self.assertIn(name, result)
            self.assertIs(result[name],False)
        self.assertFalse(result["executes_action"])

    def test_01_invalid_scope_matrix_explicit_denial_and_no_spend(self):
        before=self.budget.snapshot("review-tx",now=NOW)
        for key in ("owner_id","tenant_id","workspace_id"):
            with self.subTest(key=key):
                out=self.budget.guard({**self.decision(),key:"foreign"},
                                      now=NOW)
                self.assertIs(out["allowed"],False)
                self.assert_no_authority(out)
                self.assertEqual(out["reason"],
                                 "AUTHORITY_BUDGET_BINDING_INVALID:ValueError")
        self.assertEqual(before,self.budget.snapshot("review-tx",now=NOW))

    def test_02_policy_budget_transaction_and_action_missing_denial(self):
        for key in ("policy_version","authority_budget_ref","transaction_id","action"):
            with self.subTest(key=key):
                bad=self.decision()
                bad.pop(key)
                out=self.budget.guard(bad,now=NOW)
                self.assertIs(out["allowed"],False)
                self.assert_no_authority(out)

    def test_03_critical_and_over_limit_denial_still_explicit(self):
        for fake,reason in (
            ({"capability_class":"CRITICAL"},"CRITICAL_CAPABILITY_REQUIRES_SEPARATE_HUMAN_GATE"),
            ({"risk_points":4},"TRANSACTION_RISK_LIMIT")
        ):
            with self.subTest(reason=reason):
                out=self.budget.guard({**self.decision(),**fake},now=NOW)
                self.assertIs(out["allowed"],False)
                self.assert_no_authority(out)
                self.assertIn(reason,out["blockers"])

    def test_04_boolean_risk_never_accepted_as_integer_budget(self):
        for risk in (True,False):
            with self.subTest(risk=risk):
                out=self.budget.guard({**self.decision(),"risk_points":risk},now=NOW)
                self.assertIs(out["allowed"],False)
                self.assert_no_authority(out)
                self.assertIn("AUTHORITY_BUDGET_BINDING_INVALID",out["reason"])

    def test_05_positive_preflight_does_not_claim_execution(self):
        out=self.budget.guard(self.decision(),now=NOW)
        self.assertIs(out["allowed"],True)
        self.assert_no_authority(out)
        self.assertEqual(out["reason"],"ALLOW")
        self.assertEqual(self.budget.snapshot("review-tx",now=NOW)["transaction_effects"],0)

    def test_06_none_input_is_denied_with_explicit_false_flags(self):
        out=self.budget.guard(None,now=NOW)
        self.assertIs(out["allowed"],False)
        self.assert_no_authority(out)

    def test_07_truthy_nonmapping_does_not_turn_into_authority(self):
        # Input violates Mapping annotation: the current guard raises on
        # invalid response reconstruction. This is a robustness follow-up,
        # not a P0 bypass or a reason to widen PR #1331.
        for invalid in (123, "malformed", ["malformed"]):
            with self.subTest(input_type=type(invalid).__name__):
                with self.assertRaises((ValueError,TypeError,AttributeError)):
                    self.budget.guard(invalid,now=NOW)
                self.assertEqual(self.budget.snapshot("review-tx",now=NOW)[
                    "transaction_effects"],0)


class OutboxGuardIndependentReviewLAB(unittest.TestCase):
    def setUp(self):
        self.fx=fixture.ExecutionSagaTests()
        self.fx.setUp()
        self.root=tempfile.TemporaryDirectory()
        self.addCleanup(self.root.cleanup)
        self.store,self.outbox,self.budget,self.saga=self.fx._components(self.root.name)
        self.addCleanup(self.store.close)
        self.fx._create(self.saga)
        staged=self.fx._enqueue_forward(self.saga)
        self.key=staged["outbox"]["idempotency_key"]
        self.adapter=_ForbiddenAdapter()
        self.calls=0

    def _dispatch(self, guard):
        claimed=self.outbox.claim_next("review-claim",now=NOW+timedelta(seconds=1),
                                       lease_seconds=60)
        self.assertEqual(claimed["idempotency_key"],self.key)
        def authorize(decision):
            return fixture.policy(self.fx.scope)(decision)
        return self.outbox.dispatch_claimed(
            self.key,worker_id="review-claim",authorize=authorize,
            adapter=self.adapter,cumulative_authority_guard=guard,
            now=NOW+timedelta(seconds=2))

    def _verify_block(self, result,code):
        self.assertEqual(result["state"],"BLOCKED_REAPPROVAL")
        self.assertIn(code,result["last_error"])
        self.assertEqual(self.outbox.effect_count(),0)
        self.assertEqual(self.adapter.attribute_reads,0)

    def test_08_missing_budget_allowed_denies_without_adapter(self):
        out=self._dispatch(lambda decision:{"reason":"MISSING_ALLOWED"})
        self._verify_block(out,"MISSING_ALLOWED")

    def test_09_truthy_nonboolean_allowed_denies_without_adapter(self):
        out=self._dispatch(lambda decision:{"allowed":1,"reason":"NON_BOOLEAN_ALLOWED"})
        self._verify_block(out,"NON_BOOLEAN_ALLOWED")

    def test_10_malformed_nonmapping_guard_response_denies_without_adapter(self):
        out=self._dispatch(lambda decision:"ALLOW")
        self._verify_block(out,"CUMULATIVE_AUTHORITY_BUDGET_EXCEEDED")

    def test_11_guard_callback_exception_denies_without_adapter(self):
        def raising(decision):
            raise RuntimeError("LOCAL_ERROR_NOT_PERMISSION")
        out=self._dispatch(raising)
        self._verify_block(out,"CUMULATIVE_AUTHORITY_GUARD_FAILED")

    def test_12_forged_allow_with_wrong_budget_reference_denies(self):
        def forged(d):
            return {
                "allowed":True,
                "authority_budget_ref":"FOREIGN",
                "transaction_id":d["transaction_id"],
            }
        out=self._dispatch(forged)
        self._verify_block(out,"CUMULATIVE_AUTHORITY_BUDGET_REF_MISMATCH")

    def test_13_forged_allow_with_wrong_transaction_denies(self):
        def forged(d):
            return {
                "allowed":True,
                "authority_budget_ref":d["authority_budget_ref"],
                "transaction_id":"FOREIGN",
            }
        out=self._dispatch(forged)
        self._verify_block(out,"CUMULATIVE_AUTHORITY_TRANSACTION_MISMATCH")

    def test_14_all_fake_positive_flags_still_block_on_producer(self):
        def forged(d):
            return {
                "allowed":True,
                "authority_budget_ref":d["authority_budget_ref"],
                "transaction_id":d["transaction_id"],
                "grants_authority":True,
                "execution_allowed_by_this_component":True,
                "executes_action":True,
            }
        with self.assertRaisesRegex(
            PermissionError,"^INDEPENDENT_PRODUCER_NOT_ENROLLED$"):
            self._dispatch(forged)
        self.assertEqual(self.outbox.get(self.key)["state"],"BLOCKED_PRODUCER")
        self.assertEqual(self.adapter.attribute_reads,0)
        self.assertEqual(self.outbox.effect_count(),0)

    def test_15_real_budget_valid_preflight_still_producer_denied(self):
        def real(d):
            out=self.saga.authority_guard(d,now=NOW+timedelta(seconds=2))
            self.assertIs(out["allowed"],True)
            for name in FALSE_FLAGS: self.assertIs(out[name],False)
            return out
        with self.assertRaisesRegex(PermissionError,
                                    "^INDEPENDENT_PRODUCER_NOT_ENROLLED$"):
            self._dispatch(real)
        self.assertEqual(self.outbox.get(self.key)["state"],"BLOCKED_PRODUCER")
        self.assertEqual(self.adapter.attribute_reads,0)
        self.assertEqual(self.outbox.effect_count(),0)


if __name__=="__main__":
    unittest.main()
