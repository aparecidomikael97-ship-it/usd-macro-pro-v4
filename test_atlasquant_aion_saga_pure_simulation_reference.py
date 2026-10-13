"""A.40 TEST-ONLY pure Saga reference: no import/use of real AION runtime.

All outcomes here are HYPOTHETICAL labels, NOT independent producer receipts.
This file cannot write an Outbox, Saga DB, effect ledger, or perform send/reconcile.
The historic 8 real-Saga simulation tests stay RED and are not replaced/waived.
"""
from __future__ import annotations

import unittest

SIM_COMMITTED = "SIMULATED_ONLY_COMMITTED"
SIM_NO_EFFECT = "SIMULATED_ONLY_NO_EFFECT"
SIM_UNKNOWN = "SIMULATED_ONLY_UNCERTAIN"
_ALLOWED_OUTCOMES = frozenset((SIM_COMMITTED, SIM_NO_EFFECT, SIM_UNKNOWN))


class _TestOnlyScopeBudget:
    """Not CumulativeAuthorityBudget; tracks fictional effect counts only."""

    def __init__(self, limit: int = 10):
        self.limit = limit
        self.hypothetical_effects = 0

    def can_prepare_another(self) -> bool:
        return self.hypothetical_effects < self.limit

    def record_simulated(self):
        if self.hypothetical_effects >= self.limit:
            raise ValueError("SIMULATED_SCOPE_EFFECT_LIMIT")
        self.hypothetical_effects += 1


class _TestOnlySagaProjection:
    """Independent in-memory projection. No productive integrations exist."""

    def __init__(self, reversible=(True, True), *, budget=None):
        if not reversible:
            raise ValueError("one or more hypothetical steps required")
        self.steps = [
            {"state": "PENDING", "reversible": bool(x), "comp_state": "",
             "step_key": f"sim-step-{idx+1}"}
            for idx, x in enumerate(reversible)
        ]
        self.state = "PLANNED"
        self.hypothetical_compensation_order = []
        self.budget = budget or _TestOnlyScopeBudget()
        self.external_action_authorized = False
        self.effect_ledger_authorized = False
        self.retry_authorized = False
        self.proof_status = "SIMULATED_ONLY_NO_EXTERNAL_EVIDENCE"

    def _check_simulated(self, outcome):
        # These labels must never accept a real receipt, signature, bool or
        # even a dict containing a "trusted" field.
        if type(outcome) is not str or outcome not in _ALLOWED_OUTCOMES:
            raise TypeError("ONLY_EXPLICIT_SIMULATED_OUTCOMES_ALLOWED")

    def enqueue_forward(self):
        if self.state not in {"PLANNED", "RUNNING"}:
            raise ValueError("SIMULATED_SAGA_FORWARD_FROZEN")
        if any(s["state"] in {"ENQUEUED", "UNCERTAIN"} for s in self.steps):
            raise ValueError("SIMULATED_PREVIOUS_STEP_UNSETTLED")
        if not self.budget.can_prepare_another():
            raise ValueError("SIMULATED_SCOPE_EFFECT_LIMIT")
        pending = next((i for i, s in enumerate(self.steps)
                        if s["state"] == "PENDING"), None)
        if pending is None:
            raise ValueError("SIMULATED_NO_PENDING_FORWARD")
        if any(s["state"] != "CONFIRMED" for s in self.steps[:pending]):
            raise ValueError("SIMULATED_PREVIOUS_STEP_NOT_CONFIRMED")
        self.steps[pending]["state"] = "ENQUEUED"
        self.state = "RUNNING"
        return pending

    def observe_forward(self, index, outcome, *, review=False):
        self._check_simulated(outcome)
        step = self.steps[index]
        if step["state"] == "UNCERTAIN":
            if review is not True:
                raise PermissionError("SIMULATED_UNCERTAIN_NEEDS_HYPOTHETICAL_REVIEW")
        elif step["state"] != "ENQUEUED":
            raise ValueError("SIMULATED_FORWARD_NOT_ENQUEUED")
        if outcome == SIM_UNKNOWN:
            step["state"] = "UNCERTAIN"
            self.state = "RECONCILIATION_REQUIRED"
        elif outcome == SIM_COMMITTED:
            self.budget.record_simulated()
            step["state"] = "CONFIRMED"
            self.state = ("COMPLETED" if all(
                s["state"] == "CONFIRMED" for s in self.steps
            ) else "RUNNING")
        else:
            step["state"] = "FAILED"
            prior = self.steps[:index]
            if any(s["state"] == "CONFIRMED" and not s["reversible"] for s in prior):
                self.state = "MANUAL_INTERVENTION_REQUIRED"
            elif any(s["state"] == "CONFIRMED" for s in prior):
                self.state = "COMPENSATION_REQUIRED"
            else:
                self.state = "FAILED"
        return self.state

    def prepare_compensation(self, *, explicit_human_approval=False):
        if self.state != "COMPENSATION_REQUIRED":
            raise PermissionError("SIMULATED_COMPENSATION_NOT_ELIGIBLE")
        if explicit_human_approval is not True:
            raise PermissionError("SIMULATED_HUMAN_APPROVAL_REQUIRED")
        eligible = [s for s in self.steps if s["state"] == "CONFIRMED"]
        if not eligible or any(not s["reversible"] for s in eligible):
            raise PermissionError("SIMULATED_MANUAL_REQUIRED")
        for step in eligible:
            step["comp_state"] = "COMPENSATION_PENDING"
        self.state = "COMPENSATING"

    def enqueue_compensation(self):
        if self.state != "COMPENSATING":
            raise ValueError("SIMULATED_COMPENSATION_FROZEN")
        if any(s["comp_state"] in {"COMPENSATION_ENQUEUED", "UNCERTAIN"}
               for s in self.steps):
            raise ValueError("SIMULATED_PREVIOUS_COMPENSATION_UNSETTLED")
        pending = [i for i, s in enumerate(self.steps)
                   if s["comp_state"] == "COMPENSATION_PENDING"]
        if not pending:
            raise ValueError("SIMULATED_NO_PENDING_COMPENSATION")
        index = max(pending)
        self.steps[index]["comp_state"] = "COMPENSATION_ENQUEUED"
        return index

    def observe_compensation(self, index, outcome, *, review=False):
        self._check_simulated(outcome)
        step = self.steps[index]
        if step["comp_state"] == "UNCERTAIN":
            if review is not True:
                raise PermissionError("SIMULATED_COMPENSATION_NEEDS_HYPOTHETICAL_REVIEW")
        elif step["comp_state"] != "COMPENSATION_ENQUEUED":
            raise ValueError("SIMULATED_COMPENSATION_NOT_ENQUEUED")
        if outcome == SIM_UNKNOWN:
            step["comp_state"] = "UNCERTAIN"
            self.state = "RECONCILIATION_REQUIRED"
        elif outcome == SIM_COMMITTED:
            self.budget.record_simulated()
            step["comp_state"] = "COMPENSATED"
            self.hypothetical_compensation_order.append(index)
            self.state = ("COMPENSATING" if any(
                s["comp_state"] == "COMPENSATION_PENDING" for s in self.steps
            ) else "COMPENSATED")
        else:
            step["comp_state"] = "COMPENSATION_FAILED"
            self.state = "MANUAL_INTERVENTION_REQUIRED"
        return self.state

    def proof_assertion(self):
        return {
            "proof_status": self.proof_status,
            "external_action_authorized": self.external_action_authorized,
            "effect_ledger_authorized": self.effect_ledger_authorized,
            "retry_authorized": self.retry_authorized,
            "hypothetical_effects": self.budget.hypothetical_effects,
        }


class TestOnlySagaStateMachineReferences(unittest.TestCase):
    """Eight historical logic scenarios recast as NONPRODUCTIVE pure projections."""

    def assert_only_simulated(self, model):
        p = model.proof_assertion()
        self.assertEqual(p["proof_status"], "SIMULATED_ONLY_NO_EXTERNAL_EVIDENCE")
        self.assertIs(p["external_action_authorized"], False)
        self.assertIs(p["effect_ledger_authorized"], False)
        self.assertIs(p["retry_authorized"], False)

    def test_01_two_forward_hypothetical_commits_preserve_order(self):
        m = _TestOnlySagaProjection()
        self.assertEqual(m.enqueue_forward(), 0)
        with self.assertRaisesRegex(ValueError, "PREVIOUS_STEP_UNSETTLED"):
            m.enqueue_forward()
        self.assertEqual(m.observe_forward(0, SIM_COMMITTED), "RUNNING")
        self.assertEqual(m.enqueue_forward(), 1)
        self.assertEqual(m.observe_forward(1, SIM_COMMITTED), "COMPLETED")
        self.assertEqual([s["state"] for s in m.steps], ["CONFIRMED", "CONFIRMED"])
        self.assertEqual(m.budget.hypothetical_effects, 2)
        self.assert_only_simulated(m)

    def test_02_second_hypothetical_failure_needs_approval_then_reverse(self):
        m = _TestOnlySagaProjection()
        m.enqueue_forward()
        m.observe_forward(0, SIM_COMMITTED)
        m.enqueue_forward()
        self.assertEqual(m.observe_forward(1, SIM_NO_EFFECT), "COMPENSATION_REQUIRED")
        with self.assertRaisesRegex(PermissionError, "HUMAN_APPROVAL_REQUIRED"):
            m.prepare_compensation()
        m.prepare_compensation(explicit_human_approval=True)
        self.assertEqual(m.enqueue_compensation(), 0)
        self.assertEqual(m.observe_compensation(0, SIM_COMMITTED), "COMPENSATED")
        self.assertEqual(m.hypothetical_compensation_order, [0])
        self.assert_only_simulated(m)

    def test_03_three_steps_compensate_highest_ordinal_first(self):
        m = _TestOnlySagaProjection((True, True, True))
        for index in (0, 1):
            self.assertEqual(m.enqueue_forward(), index)
            m.observe_forward(index, SIM_COMMITTED)
        self.assertEqual(m.enqueue_forward(), 2)
        self.assertEqual(m.observe_forward(2, SIM_NO_EFFECT), "COMPENSATION_REQUIRED")
        m.prepare_compensation(explicit_human_approval=True)
        self.assertEqual(m.enqueue_compensation(), 1)
        self.assertEqual(m.observe_compensation(1, SIM_COMMITTED), "COMPENSATING")
        self.assertEqual(m.enqueue_compensation(), 0)
        self.assertEqual(m.observe_compensation(0, SIM_COMMITTED), "COMPENSATED")
        self.assertEqual(m.hypothetical_compensation_order, [1, 0])
        self.assert_only_simulated(m)

    def test_04_irreversible_prior_effect_escalates_manual(self):
        m = _TestOnlySagaProjection((False, True))
        m.enqueue_forward()
        m.observe_forward(0, SIM_COMMITTED)
        m.enqueue_forward()
        self.assertEqual(m.observe_forward(1, SIM_NO_EFFECT),
                         "MANUAL_INTERVENTION_REQUIRED")
        with self.assertRaisesRegex(PermissionError, "COMPENSATION_NOT_ELIGIBLE"):
            m.prepare_compensation(explicit_human_approval=True)
        self.assert_only_simulated(m)

    def test_05_unknown_forward_freezes_until_simulated_review(self):
        m = _TestOnlySagaProjection()
        m.enqueue_forward()
        self.assertEqual(m.observe_forward(0, SIM_UNKNOWN),
                         "RECONCILIATION_REQUIRED")
        with self.assertRaisesRegex(ValueError, "FORWARD_FROZEN"):
            m.enqueue_forward()
        with self.assertRaisesRegex(PermissionError, "NEEDS_HYPOTHETICAL_REVIEW"):
            m.observe_forward(0, SIM_COMMITTED)
        self.assertEqual(m.observe_forward(0, SIM_COMMITTED, review=True),
                         "RUNNING")
        self.assert_only_simulated(m)

    def test_06_unknown_compensation_freezes_reverse_order(self):
        m = _TestOnlySagaProjection((True, True, True))
        for index in (0, 1):
            m.enqueue_forward()
            m.observe_forward(index, SIM_COMMITTED)
        m.enqueue_forward()
        m.observe_forward(2, SIM_NO_EFFECT)
        m.prepare_compensation(explicit_human_approval=True)
        self.assertEqual(m.enqueue_compensation(), 1)
        self.assertEqual(m.observe_compensation(1, SIM_UNKNOWN),
                         "RECONCILIATION_REQUIRED")
        with self.assertRaisesRegex(ValueError, "COMPENSATION_FROZEN"):
            m.enqueue_compensation()
        with self.assertRaisesRegex(PermissionError, "NEEDS_HYPOTHETICAL_REVIEW"):
            m.observe_compensation(1, SIM_COMMITTED)
        self.assertEqual(m.observe_compensation(1, SIM_COMMITTED, review=True),
                         "COMPENSATING")
        self.assertEqual(m.enqueue_compensation(), 0)
        self.assert_only_simulated(m)

    def test_07_unverified_compensation_negative_never_auto_finishes(self):
        m = _TestOnlySagaProjection()
        m.enqueue_forward()
        m.observe_forward(0, SIM_COMMITTED)
        m.enqueue_forward()
        m.observe_forward(1, SIM_NO_EFFECT)
        m.prepare_compensation(explicit_human_approval=True)
        self.assertEqual(m.enqueue_compensation(), 0)
        self.assertEqual(m.observe_compensation(0, SIM_UNKNOWN),
                         "RECONCILIATION_REQUIRED")
        with self.assertRaisesRegex(ValueError, "COMPENSATION_FROZEN"):
            m.enqueue_compensation()
        self.assertEqual(m.observe_compensation(0, SIM_NO_EFFECT, review=True),
                         "MANUAL_INTERVENTION_REQUIRED")
        self.assert_only_simulated(m)

    def test_08_scope_effect_budget_limits_second_fictional_transaction(self):
        shared = _TestOnlyScopeBudget(limit=1)
        first = _TestOnlySagaProjection((True,), budget=shared)
        self.assertEqual(first.enqueue_forward(), 0)
        self.assertEqual(first.observe_forward(0, SIM_COMMITTED), "COMPLETED")
        another = _TestOnlySagaProjection((True,), budget=shared)
        with self.assertRaisesRegex(ValueError, "SIMULATED_SCOPE_EFFECT_LIMIT"):
            another.enqueue_forward()
        self.assert_only_simulated(first)
        self.assert_only_simulated(another)

    def test_09_real_looking_receipts_and_trust_flags_are_not_simulation(self):
        model = _TestOnlySagaProjection()
        model.enqueue_forward()
        for object_in in (
            True,
            "CONFIRMED",
            "NO_EFFECT_FENCED",
            {"confirmed": True, "trusted": True},
            {"claimed_signature": "a" * 128},
        ):
            with self.subTest(candidate=repr(object_in)):
                with self.assertRaisesRegex(
                    TypeError, "ONLY_EXPLICIT_SIMULATED_OUTCOMES_ALLOWED",
                ):
                    model.observe_forward(0, object_in)
        self.assertEqual(model.steps[0]["state"], "ENQUEUED")
        self.assert_only_simulated(model)


if __name__ == "__main__":
    unittest.main()
