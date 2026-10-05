from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_cumulative_authority_budget import CumulativeAuthorityBudget


NOW = datetime(2026, 10, 5, 9, 0, tzinfo=timezone.utc)


def decision(
    scope,
    *,
    transaction_id="tx-1",
    budget_ref="budget-1",
    policy_version="policy-v1",
    action="send_email",
    capability_class="LOW_RISK",
    risk_points=1,
):
    return {
        "owner_id": scope.owner_id,
        "tenant_id": scope.tenant_id,
        "workspace_id": scope.workspace_id,
        "transaction_id": transaction_id,
        "authority_budget_ref": budget_ref,
        "policy_version": policy_version,
        "action": action,
        "capability_class": capability_class,
        "risk_points": risk_points,
    }


class CumulativeAuthorityBudgetTests(unittest.TestCase):
    def setUp(self):
        self.scope = Scope("mikael", "tenant-a", "workspace-a")

    def _components(self, raw, **limits):
        store = SQLiteChatStore(Path(raw) / "chat.sqlite3")
        budget = CumulativeAuthorityBudget(
            store,
            self.scope,
            authority_budget_ref="budget-1",
            policy_version="policy-v1",
            **limits,
        )
        return store, budget

    def test_empty_budget_allows_bound_low_risk_candidate_but_grants_no_authority(self):
        with tempfile.TemporaryDirectory() as raw:
            store, budget = self._components(raw)
            out = budget.guard(decision(self.scope), now=NOW)
            self.assertTrue(out["allowed"])
            self.assertEqual(out["reason"], "ALLOW")
            self.assertFalse(out["grants_authority"])
            self.assertFalse(out["execution_allowed_by_this_component"])
            self.assertFalse(out["executes_action"])
            store.close()

    def test_confirmed_effect_is_recorded_idempotently(self):
        with tempfile.TemporaryDirectory() as raw:
            store, budget = self._components(raw)
            d = decision(self.scope, risk_points=2)
            first = budget.record_confirmed(
                d,
                idempotency_key="idem-1",
                effect_ref="effect-1",
                confirmed_at=NOW,
            )
            second = budget.record_confirmed(
                d,
                idempotency_key="idem-1",
                effect_ref="effect-1",
                confirmed_at=NOW + timedelta(seconds=5),
            )
            self.assertEqual(first["state"], "RECORDED")
            self.assertEqual(second["state"], "IDEMPOTENT")
            snap = budget.snapshot("tx-1", now=NOW + timedelta(seconds=10))
            self.assertEqual(snap["window_effects"], 1)
            self.assertEqual(snap["window_risk_points"], 2)
            self.assertEqual(snap["transaction_effects"], 1)
            store.close()

    def test_spend_idempotency_collision_is_blocked(self):
        with tempfile.TemporaryDirectory() as raw:
            store, budget = self._components(raw)
            d = decision(self.scope)
            budget.record_confirmed(
                d,
                idempotency_key="idem-1",
                effect_ref="effect-1",
                confirmed_at=NOW,
            )
            with self.assertRaisesRegex(ValueError, "idempotency collision"):
                budget.record_confirmed(
                    d,
                    idempotency_key="idem-1",
                    effect_ref="different-effect",
                    confirmed_at=NOW,
                )
            store.close()

    def test_transaction_effect_limit_blocks_authority_accumulation(self):
        with tempfile.TemporaryDirectory() as raw:
            store, budget = self._components(
                raw,
                max_transaction_effects=2,
                max_transaction_risk_points=10,
            )
            for i in range(2):
                d = decision(self.scope, action=f"action-{i}")
                budget.record_confirmed(
                    d,
                    idempotency_key=f"idem-{i}",
                    effect_ref=f"effect-{i}",
                    confirmed_at=NOW + timedelta(seconds=i),
                )
            out = budget.guard(
                decision(self.scope, action="action-3"),
                now=NOW + timedelta(seconds=3),
            )
            self.assertFalse(out["allowed"])
            self.assertIn("TRANSACTION_EFFECT_LIMIT", out["blockers"])
            store.close()

    def test_transaction_risk_limit_blocks_many_small_steps(self):
        with tempfile.TemporaryDirectory() as raw:
            store, budget = self._components(
                raw,
                max_transaction_effects=10,
                max_transaction_risk_points=5,
            )
            for i in range(2):
                d = decision(self.scope, action=f"a-{i}", risk_points=2)
                budget.record_confirmed(
                    d,
                    idempotency_key=f"idem-{i}",
                    effect_ref=f"effect-{i}",
                    confirmed_at=NOW + timedelta(seconds=i),
                )
            out = budget.guard(
                decision(self.scope, action="a-3", risk_points=2),
                now=NOW + timedelta(seconds=3),
            )
            self.assertFalse(out["allowed"])
            self.assertIn("TRANSACTION_RISK_LIMIT", out["blockers"])
            store.close()

    def test_scope_window_counts_multiple_transactions(self):
        with tempfile.TemporaryDirectory() as raw:
            store, budget = self._components(
                raw,
                max_window_effects=2,
                max_transaction_effects=10,
            )
            for i, tx in enumerate(("tx-1", "tx-2")):
                d = decision(self.scope, transaction_id=tx, action=f"a-{i}")
                budget.record_confirmed(
                    d,
                    idempotency_key=f"idem-{i}",
                    effect_ref=f"effect-{i}",
                    confirmed_at=NOW + timedelta(seconds=i),
                )
            out = budget.guard(
                decision(self.scope, transaction_id="tx-3", action="a-3"),
                now=NOW + timedelta(seconds=3),
            )
            self.assertFalse(out["allowed"])
            self.assertIn("WINDOW_EFFECT_LIMIT", out["blockers"])
            store.close()

    def test_window_risk_limit_counts_across_transactions(self):
        with tempfile.TemporaryDirectory() as raw:
            store, budget = self._components(
                raw,
                max_window_risk_points=5,
                max_transaction_risk_points=10,
            )
            budget.record_confirmed(
                decision(self.scope, transaction_id="tx-a", risk_points=3),
                idempotency_key="idem-a",
                effect_ref="effect-a",
                confirmed_at=NOW,
            )
            out = budget.guard(
                decision(self.scope, transaction_id="tx-b", risk_points=3),
                now=NOW + timedelta(seconds=1),
            )
            self.assertFalse(out["allowed"])
            self.assertIn("WINDOW_RISK_LIMIT", out["blockers"])
            store.close()

    def test_capability_diversity_limit_blocks_authority_creep(self):
        with tempfile.TemporaryDirectory() as raw:
            store, budget = self._components(
                raw,
                max_window_distinct_capabilities=2,
                max_window_effects=10,
            )
            for i, cap in enumerate(("LOW_RISK", "MEDIUM_RISK")):
                budget.record_confirmed(
                    decision(
                        self.scope,
                        transaction_id=f"tx-{i}",
                        action=f"a-{i}",
                        capability_class=cap,
                    ),
                    idempotency_key=f"idem-{i}",
                    effect_ref=f"effect-{i}",
                    confirmed_at=NOW + timedelta(seconds=i),
                )
            out = budget.guard(
                decision(
                    self.scope,
                    transaction_id="tx-3",
                    action="a-3",
                    capability_class="HIGH_RISK",
                ),
                now=NOW + timedelta(seconds=3),
            )
            self.assertFalse(out["allowed"])
            self.assertIn("WINDOW_CAPABILITY_DIVERSITY_LIMIT", out["blockers"])
            store.close()

    def test_critical_capability_never_passes_budget_guard(self):
        with tempfile.TemporaryDirectory() as raw:
            store, budget = self._components(raw)
            out = budget.guard(
                decision(self.scope, capability_class="CRITICAL"),
                now=NOW,
            )
            self.assertFalse(out["allowed"])
            self.assertIn(
                "CRITICAL_CAPABILITY_REQUIRES_SEPARATE_HUMAN_GATE",
                out["blockers"],
            )
            store.close()

    def test_budget_ref_policy_and_scope_mismatches_fail_closed(self):
        with tempfile.TemporaryDirectory() as raw:
            store, budget = self._components(raw)
            cases = [
                decision(self.scope, budget_ref="other-budget"),
                decision(self.scope, policy_version="policy-v2"),
                {
                    **decision(self.scope),
                    "tenant_id": "tenant-b",
                },
            ]
            for item in cases:
                out = budget.guard(item, now=NOW)
                self.assertFalse(out["allowed"])
                self.assertTrue(out["reason"].startswith("AUTHORITY_BUDGET_BINDING_INVALID"))
            store.close()

    def test_old_effect_outside_window_does_not_consume_current_window(self):
        with tempfile.TemporaryDirectory() as raw:
            store, budget = self._components(
                raw,
                window_seconds=60,
                max_window_effects=1,
            )
            budget.record_confirmed(
                decision(self.scope, transaction_id="old-tx"),
                idempotency_key="old-idem",
                effect_ref="old-effect",
                confirmed_at=NOW - timedelta(minutes=10),
            )
            out = budget.guard(
                decision(self.scope, transaction_id="new-tx"),
                now=NOW,
            )
            self.assertTrue(out["allowed"])
            self.assertEqual(out["before"]["window_effects"], 0)
            store.close()

    def test_budget_ledger_survives_store_reopen(self):
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "chat.sqlite3"
            store = SQLiteChatStore(path)
            budget = CumulativeAuthorityBudget(
                store,
                self.scope,
                authority_budget_ref="budget-1",
                policy_version="policy-v1",
            )
            budget.record_confirmed(
                decision(self.scope),
                idempotency_key="idem-1",
                effect_ref="effect-1",
                confirmed_at=NOW,
            )
            store.close()

            reopened = SQLiteChatStore(path)
            recovered = CumulativeAuthorityBudget(
                reopened,
                self.scope,
                authority_budget_ref="budget-1",
                policy_version="policy-v1",
            )
            snap = recovered.snapshot("tx-1", now=NOW + timedelta(seconds=1))
            self.assertEqual(snap["transaction_effects"], 1)
            reopened.close()


if __name__ == "__main__":
    unittest.main()
