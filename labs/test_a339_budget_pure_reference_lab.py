"""A339 LAB: reference budget arithmetic is synthetic, never effect proof.

The model has no productive imports. Any SQLite rows inserted below are
deliberate test-only accounting fixtures, not signed producer confirmations.
"""
from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
import atlasquant_aion_cumulative_authority_budget as productive_budget
import test_atlasquant_aion_cumulative_authority_budget as original_fixture
from labs.a339_budget_pure_reference import (
    SimulatedCandidate, SimulatedEvent, SimulatedLimits,
    simulate_append, simulate_projection,
)


NOW = original_fixture.NOW
SCOPE = ("mikael", "tenant-a", "workspace-a")


def candidate(tx="tx-1", *, scope=SCOPE, risk=1, cap="LOW_RISK", action="hypothetical"):
    return SimulatedCandidate(
        scope=scope, transaction_id=tx, risk_points=risk,
        capability_class=cap, action=action,
    )


def event(key, tx="tx-1", *, at=NOW, risk=1, cap="LOW_RISK", scope=SCOPE):
    return SimulatedEvent(
        idempotency_key=key,
        candidate=candidate(tx, scope=scope, risk=risk, cap=cap, action=key),
        local_effect_label="SYNTHETIC_ONLY_" + key,
        scenario_at=at,
    )


class A339PureBudgetReferenceTests(unittest.TestCase):
    def check_local_only(self, result):
        self.assertEqual(result["proof_scope"], "PURE_SYNTHETIC_MODEL_ONLY")
        self.assertIs(result["independent_producer_receipt_verified"], False)
        self.assertIs(result["grants_authority"], False)
        self.assertIs(result["authorizes_execution"], False)
        self.assertIs(result["executes_action"], False)

    def test_01_empty_projection_never_grants_authority(self):
        result = simulate_projection((), candidate(), now=NOW)
        self.assertTrue(result["candidate_within_simulated_limits"])
        self.assertEqual(result["before"]["transaction_effects"], 0)
        self.check_local_only(result)

    def test_02_synthetic_idempotency_and_collision_are_pure_labels(self):
        first = event("idem-1", risk=2)
        history, state = simulate_append((), first)
        self.assertEqual(state, "SYNTHETIC_ADDED_ONLY")
        again = event("idem-1", at=NOW + timedelta(seconds=5), risk=2)
        same, state = simulate_append(history, again)
        self.assertEqual(state, "SYNTHETIC_IDEMPOTENT_ONLY")
        self.assertIs(same, history)
        self.assertEqual(len(same), 1)
        with self.assertRaisesRegex(ValueError, "SYNTHETIC_IDEMPOTENCY_COLLISION"):
            simulate_append(history, event("idem-1", risk=3))
        self.assertEqual(len(history), 1)
        self.check_local_only(simulate_projection(history, candidate(), now=NOW))

    def test_03_transaction_effect_limit_projects_blocker(self):
        history = (event("first"), event("second", at=NOW + timedelta(seconds=1)))
        result = simulate_projection(
            history, candidate(action="third"),
            now=NOW + timedelta(seconds=2),
            limits=SimulatedLimits(max_transaction_effects=2),
        )
        self.assertIn("TRANSACTION_EFFECT_LIMIT", result["blockers"])
        self.assertEqual(result["before"]["transaction_effects"], 2)
        self.assertFalse(result["candidate_within_simulated_limits"])
        self.check_local_only(result)

    def test_04_transaction_risk_limit_counts_small_simulated_items(self):
        history = (event("first", risk=2), event("second", risk=2))
        result = simulate_projection(
            history, candidate(risk=2), now=NOW,
            limits=SimulatedLimits(max_transaction_risk_points=5),
        )
        self.assertIn("TRANSACTION_RISK_LIMIT", result["blockers"])
        self.assertEqual(result["projected_after"]["transaction_risk_points"], 6)
        self.check_local_only(result)

    def test_05_window_effects_count_across_simulated_transactions(self):
        history = (event("first", "tx-a"), event("second", "tx-b"))
        result = simulate_projection(
            history, candidate("tx-c"), now=NOW,
            limits=SimulatedLimits(max_window_effects=2),
        )
        self.assertIn("WINDOW_EFFECT_LIMIT", result["blockers"])
        self.assertEqual(result["before"]["transaction_effects"], 0)
        self.check_local_only(result)

    def test_06_window_risk_points_accumulate_across_transactions(self):
        history = (event("first", "tx-a", risk=3),)
        result = simulate_projection(
            history, candidate("tx-b", risk=3), now=NOW,
            limits=SimulatedLimits(max_window_risk_points=5),
        )
        self.assertIn("WINDOW_RISK_LIMIT", result["blockers"])
        self.check_local_only(result)

    def test_07_capability_diversity_limit_is_simulated_only(self):
        history = (
            event("low", "tx-a", cap="LOW_RISK"),
            event("medium", "tx-b", cap="MEDIUM_RISK"),
        )
        result = simulate_projection(
            history, candidate("tx-c", cap="HIGH_RISK"), now=NOW,
            limits=SimulatedLimits(max_window_distinct_capabilities=2),
        )
        self.assertIn("WINDOW_CAPABILITY_DIVERSITY_LIMIT", result["blockers"])
        self.assertEqual(result["projected_after"]["window_distinct_capabilities"], 3)
        self.check_local_only(result)

    def test_08_expired_window_entry_does_not_count_in_recent_window(self):
        history = (event("old", "old-tx", at=NOW - timedelta(minutes=10)),)
        result = simulate_projection(
            history, candidate("new-tx"), now=NOW,
            limits=SimulatedLimits(window_seconds=60, max_window_effects=1),
        )
        self.assertTrue(result["candidate_within_simulated_limits"])
        self.assertEqual(result["before"]["window_effects"], 0)
        self.check_local_only(result)

    def test_09_scope_isolation_and_old_transaction_counts_remain_independent(self):
        history = (
            event("own-old", at=NOW - timedelta(minutes=10), risk=2),
            event("other-tenant", scope=("mikael", "tenant-other", "workspace-a"), risk=8),
        )
        result = simulate_projection(
            history, candidate(risk=2), now=NOW,
            limits=SimulatedLimits(window_seconds=60, max_transaction_risk_points=3),
        )
        self.assertEqual(result["before"]["window_effects"], 0)
        self.assertEqual(result["before"]["transaction_effects"], 1)
        self.assertIn("TRANSACTION_RISK_LIMIT", result["blockers"])
        self.check_local_only(result)

    def test_10_critical_candidate_is_never_execution_approval(self):
        result = simulate_projection((), candidate(cap="CRITICAL"), now=NOW)
        self.assertIn("CRITICAL_CAPABILITY_REQUIRES_SEPARATE_HUMAN_GATE", result["blockers"])
        self.check_local_only(result)

    def test_11_invalid_synthetic_values_fail_without_side_effects(self):
        with self.assertRaisesRegex(ValueError, "synthetic candidate"):
            candidate(risk=True)
        with self.assertRaisesRegex(ValueError, "synthetic limit"):
            SimulatedLimits(max_window_effects=0)
        with self.assertRaisesRegex(ValueError, "timezone-aware"):
            simulate_projection((), candidate(), now=NOW.replace(tzinfo=None))

    def _seed_test_only(self, budget, entry):
        d = original_fixture.decision(
            Scope(*entry.candidate.scope),
            transaction_id=entry.candidate.transaction_id,
            action=entry.candidate.action,
            capability_class=entry.candidate.capability_class,
            risk_points=entry.candidate.risk_points,
        )
        budget.db.execute(
            """INSERT INTO aion_authority_spend(
                 idempotency_key,owner,tenant,workspace,transaction_id,
                 authority_budget_ref,policy_version,capability_class,action,
                 risk_points,effect_ref,confirmed_at,decision_digest
               ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                entry.idempotency_key, *entry.candidate.scope,
                entry.candidate.transaction_id, "budget-1", "policy-v1",
                entry.candidate.capability_class, entry.candidate.action,
                entry.candidate.risk_points, entry.local_effect_label,
                entry.scenario_at.isoformat(), productive_budget._digest(d),
            ),
        )

    def _compare_guard(self, history, next_candidate, limits, *, now=NOW, reopen=False):
        reference = simulate_projection(history, next_candidate, now=now, limits=limits)
        with TemporaryDirectory() as directory:
            path = Path(directory) / "chat.sqlite3"
            store = SQLiteChatStore(path)
            try:
                budget = productive_budget.CumulativeAuthorityBudget(
                    store, Scope(*SCOPE),
                    authority_budget_ref="budget-1", policy_version="policy-v1",
                    **vars(limits),
                )
                with store.db:
                    for row in history:
                        self._seed_test_only(budget, row)
                if reopen:
                    store.close()
                    store = SQLiteChatStore(path)
                    budget = productive_budget.CumulativeAuthorityBudget(
                        store, Scope(*SCOPE),
                        authority_budget_ref="budget-1", policy_version="policy-v1",
                        **vars(limits),
                    )
                decision = original_fixture.decision(
                    Scope(*SCOPE), transaction_id=next_candidate.transaction_id,
                    action=next_candidate.action,
                    capability_class=next_candidate.capability_class,
                    risk_points=next_candidate.risk_points,
                )
                changes = store.db.total_changes
                guard = budget.guard(decision, now=now)
                self.assertEqual(store.db.total_changes, changes)
                self.assertEqual(guard["allowed"], reference["candidate_within_simulated_limits"])
                self.assertEqual(guard["blockers"], reference["blockers"])
                self.assertEqual(guard["before"], reference["before"])
                self.assertEqual(guard["projected_after"], reference["projected_after"])
                self.assertFalse(guard["grants_authority"])
                self.assertFalse(guard["execution_allowed_by_this_component"])
                self.check_local_only(reference)
            finally:
                store.close()

    def test_12_pure_model_matches_readonly_guard_on_synthetic_sqlite_cases(self):
        cases = [
            ((event("one"), event("two")), candidate(action="third"),
             SimulatedLimits(max_transaction_effects=2), NOW),
            ((event("one", risk=2), event("two", risk=2)), candidate(risk=2),
             SimulatedLimits(max_transaction_risk_points=5), NOW),
            ((event("one", "tx-a"), event("two", "tx-b")), candidate("tx-c"),
             SimulatedLimits(max_window_effects=2), NOW),
            ((event("one", "tx-a", risk=3),), candidate("tx-b", risk=3),
             SimulatedLimits(max_window_risk_points=5), NOW),
            ((event("low", "tx-a", cap="LOW_RISK"),
              event("medium", "tx-b", cap="MEDIUM_RISK")),
             candidate("tx-c", cap="HIGH_RISK"),
             SimulatedLimits(max_window_distinct_capabilities=2), NOW),
            ((event("old", "old-tx", at=NOW - timedelta(minutes=10)),),
             candidate("new-tx"),
             SimulatedLimits(window_seconds=60, max_window_effects=1), NOW),
        ]
        for index, (history, next_candidate, limits, now) in enumerate(cases):
            with self.subTest(case=index):
                self._compare_guard(history, next_candidate, limits, now=now)

    def test_13_test_only_sqlite_reopen_preserves_accounting_without_producer_proof(self):
        history = (event("persisted", risk=2),)
        self._compare_guard(
            history, candidate(risk=1), SimulatedLimits(),
            now=NOW + timedelta(seconds=1), reopen=True,
        )

    def test_14_productive_confirmed_record_stays_denied_while_model_is_positive(self):
        with TemporaryDirectory() as directory:
            store = SQLiteChatStore(Path(directory) / "chat.sqlite3")
            try:
                budget = productive_budget.CumulativeAuthorityBudget(
                    store, Scope(*SCOPE),
                    authority_budget_ref="budget-1", policy_version="policy-v1",
                )
                model = simulate_projection((), candidate(), now=NOW)
                self.assertTrue(model["candidate_within_simulated_limits"])
                self.check_local_only(model)
                before = store.db.total_changes
                with self.assertRaisesRegex(
                    PermissionError, "INDEPENDENT_PRODUCER_RECEIPT_NOT_ENROLLED"
                ):
                    budget.record_confirmed(
                        original_fixture.decision(Scope(*SCOPE)),
                        idempotency_key="SYNTHETIC_ONLY",
                        effect_ref="NOT_A_PRODUCER_RECEIPT",
                        confirmed_at=NOW,
                    )
                self.assertEqual(store.db.total_changes, before)
                self.assertEqual(
                    budget.snapshot("tx-1", now=NOW)["transaction_effects"], 0
                )
            finally:
                store.close()


if __name__ == "__main__":
    unittest.main()
