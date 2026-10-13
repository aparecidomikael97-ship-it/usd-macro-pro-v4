"""AION A.41: pure shared selection and real-Saga fail-closed adversarial tests.

NO producer, provider, send, reconcile, signer, witness or simulated approval.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_cumulative_authority_budget import CumulativeAuthorityBudget
from atlasquant_aion_execution_outbox import ExecutionOutbox
from atlasquant_aion_execution_saga import ExecutionSagaCoordinator
from atlasquant_aion_saga_sequence_policy import (
    select_compensation_step,
    select_forward_step,
)

NOW = datetime(2026, 10, 13, 18, 0, tzinfo=timezone.utc)


def _steps(*states):
    return [{"ordinal": i + 1, "state": state} for i, state in enumerate(states)]


class PureSequencePolicyTests(unittest.TestCase):
    def test_first_forward_candidate_requires_no_proof_in_pure_projection(self):
        self.assertEqual(select_forward_step("PLANNED", _steps("PENDING", "PENDING")), 0)

    def test_prior_unsettled_blocks_new_forward(self):
        for state in ("ENQUEUED", "RETRY", "UNCERTAIN"):
            with self.subTest(state=state):
                with self.assertRaisesRegex(ValueError, "not settled"):
                    select_forward_step("RUNNING", _steps(state, "PENDING"))

    def test_prior_negative_blocks_new_forward(self):
        for state in ("FAILED", "REVOKED", "BLOCKED_REAPPROVAL"):
            with self.subTest(state=state):
                with self.assertRaisesRegex(ValueError, "failed saga"):
                    select_forward_step("RUNNING", _steps(state, "PENDING"))

    def test_nonmatching_earlier_state_never_unlocks_later(self):
        for state in ("BLOCKED_PRODUCER", "MANUAL_REQUIRED", "COMPENSATED"):
            with self.subTest(state=state):
                with self.assertRaisesRegex(ValueError, "earlier confirmation"):
                    select_forward_step("RUNNING", _steps(state, "PENDING"))

    def test_pure_selector_can_describe_but_never_authenticate_prior_confirmation(self):
        # This candidate is a state calculation, NOT external proof.
        self.assertEqual(select_forward_step("RUNNING", _steps("CONFIRMED", "PENDING")), 1)

    def test_terminal_and_reconciliation_sagas_cannot_enqueue(self):
        for state in ("COMPLETED", "FAILED", "COMPENSATING",
                      "RECONCILIATION_REQUIRED", "PRODUCER_ENROLLMENT_REQUIRED"):
            with self.subTest(state=state):
                with self.assertRaisesRegex(ValueError, "state does not allow"):
                    select_forward_step(state, _steps("PENDING"))

    def test_no_pending_forward_candidate(self):
        with self.assertRaisesRegex(ValueError, "no pending"):
            select_forward_step("RUNNING", _steps("CONFIRMED"))

    def test_reverse_compensation_selects_highest_ordinal(self):
        self.assertEqual(select_compensation_step("COMPENSATING", _steps(
            "COMPENSATION_PENDING", "COMPENSATION_PENDING", "FAILED"
        )), 1)

    def test_unsettled_compensation_freezes_reverse_sequence(self):
        for state in ("COMPENSATION_ENQUEUED", "UNCERTAIN", "COMPENSATION_FAILED"):
            with self.subTest(state=state):
                with self.assertRaisesRegex(ValueError, "not settled"):
                    select_compensation_step("COMPENSATING", _steps(
                        "COMPENSATION_PENDING", state
                    ))

    def test_compensation_requires_prepared_pending_and_correct_saga_state(self):
        with self.assertRaisesRegex(ValueError, "not in compensation"):
            select_compensation_step("RECONCILIATION_REQUIRED",
                                     _steps("COMPENSATION_PENDING"))
        with self.assertRaisesRegex(ValueError, "no pending"):
            select_compensation_step("COMPENSATING", _steps("COMPENSATED"))

    def test_selectors_have_no_io_authority(self):
        import inspect
        import atlasquant_aion_saga_sequence_policy as pure
        source = inspect.getsource(pure)
        for forbidden in (
            "sqlite3", "ExecutionOutbox", "CumulativeAuthorityBudget",
            "SQLiteChatStore", "adapter.send(", ".dispatch_claimed(",
            "record_confirmed(", "receipt_verifier", "SIMULATED_ONLY_COMMITTED",
        ):
            self.assertNotIn(forbidden, source)


class RealSagaForgedProjectionTests(unittest.TestCase):
    def test_local_confirmed_projection_cannot_enqueue_second_forward(self):
        with tempfile.TemporaryDirectory() as raw:
            scope = Scope("owner-a", "tenant-a", "workspace-a")
            store = SQLiteChatStore(Path(raw) / "chat.sqlite3")
            try:
                outbox = ExecutionOutbox(store, scope)
                budget = CumulativeAuthorityBudget(
                    store, scope, authority_budget_ref="budget-a",
                    policy_version="policy-a",
                )
                saga = ExecutionSagaCoordinator(
                    store, scope, outbox=outbox, authority_budget=budget,
                )
                saga.create(saga_id="a41-local-forgery", steps=[
                    {
                        "step_key": key, "action": "create_crm_note",
                        "payload": {"step": key}, "capability_class": "LOW_RISK",
                        "risk_points": 1, "reversible": False,
                    }
                    for key in ("one", "two")
                ], created_at=NOW)
                first = saga.enqueue_next(
                    "a41-local-forgery",
                    authorization_ref="approval-a",
                    valid_until=NOW + timedelta(minutes=10),
                    created_at=NOW,
                )
                self.assertEqual(first["state"], "ENQUEUED")
                with saga.db:
                    row = saga.db.execute(
                        """UPDATE aion_execution_saga_steps
                           SET state='CONFIRMED',effect_ref='FAKE-LOCAL-ONLY'
                           WHERE saga_id=? AND step_key='one'
                             AND state='ENQUEUED'""",
                        ("a41-local-forgery",),
                    )
                    self.assertEqual(row.rowcount, 1)
                before = saga.get("a41-local-forgery")
                outbox_before = saga.db.execute(
                    "SELECT COUNT(*) AS n FROM action_outbox",
                ).fetchone()["n"]
                budget_before = budget.snapshot(
                    "a41-local-forgery", now=NOW,
                )["transaction_effects"]
                with self.assertRaisesRegex(
                    PermissionError, "INDEPENDENT_PRODUCER_RECEIPT_NOT_ENROLLED",
                ):
                    saga.enqueue_next(
                        "a41-local-forgery",
                        authorization_ref="approval-a",
                        valid_until=NOW + timedelta(minutes=10),
                        created_at=NOW + timedelta(seconds=1),
                    )
                self.assertEqual(saga.get("a41-local-forgery"), before)
                self.assertEqual(saga.db.execute(
                    "SELECT COUNT(*) AS n FROM action_outbox",
                ).fetchone()["n"], outbox_before)
                self.assertEqual(budget.snapshot(
                    "a41-local-forgery", now=NOW,
                )["transaction_effects"], budget_before)
            finally:
                store.close()


if __name__ == "__main__":
    unittest.main()
