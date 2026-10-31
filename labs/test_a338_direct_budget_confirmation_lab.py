"""A338 LAB: direct budget ledger confirmation is not producer proof.

All effects and ledger rows are synthetic in temporary SQLite stores.
No provider, signer, owner, network, worker, or real effect is exercised.
"""
from collections.abc import Mapping
from contextlib import contextmanager
from datetime import timedelta
from tempfile import TemporaryDirectory
import unittest

import atlasquant_aion_cumulative_authority_budget as budget_module
import test_atlasquant_aion_cumulative_authority_budget as fixtures


NOW = fixtures.NOW
REASON = "INDEPENDENT_PRODUCER_RECEIPT_NOT_ENROLLED"


class UntrustedDecision(Mapping):
    def __getitem__(self, key):
        raise AssertionError("A338_UNTRUSTED_MAPPING_READ")

    def __iter__(self):
        raise AssertionError("A338_UNTRUSTED_MAPPING_ITERATED")

    def __len__(self):
        raise AssertionError("A338_UNTRUSTED_MAPPING_LENGTH")


class A338DirectBudgetConfirmationTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.CumulativeAuthorityBudgetTests()
        self.fixture.setUp()

    @contextmanager
    def lab(self, **limits):
        with TemporaryDirectory() as directory:
            store, budget = self.fixture._components(directory, **limits)
            try:
                yield store, budget
            finally:
                store.close()

    def _decision(self):
        return fixtures.decision(self.fixture.scope)

    def _snapshot(self, budget):
        return budget.snapshot("tx-1", now=NOW)

    def _deny_without_spend(self, budget, callback):
        before = self._snapshot(budget)
        changed = budget.db.total_changes
        with self.assertRaisesRegex(PermissionError, REASON):
            callback()
        self.assertEqual(budget.db.total_changes, changed)
        self.assertEqual(self._snapshot(budget), before)

    def test_01_valid_local_decision_and_effect_ref_do_not_prove_external_effect(self):
        with self.lab() as (_store, budget):
            self._deny_without_spend(
                budget,
                lambda: budget.record_confirmed(
                    self._decision(),
                    idempotency_key="locally-asserted-key",
                    effect_ref="LOCAL_EFFECT_NOT_A_RECEIPT",
                    confirmed_at=NOW,
                ),
            )
            self.assertEqual(self._snapshot(budget)["transaction_effects"], 0)

    def test_02_various_claimed_receipt_strings_cannot_debit_budget(self):
        for effect in ("COMMITTED_EFFECT", "SIGNED-EXTERNAL-RECEIPT", "PROVIDER_OK"):
            with self.subTest(effect=effect):
                with self.lab() as (_store, budget):
                    self._deny_without_spend(
                        budget,
                        lambda effect=effect: budget.record_confirmed(
                            self._decision(),
                            idempotency_key="locally-asserted-key",
                            effect_ref=effect,
                            confirmed_at=NOW,
                        ),
                    )

    def test_03_future_timestamp_does_not_authenticate_local_confirmation(self):
        with self.lab() as (_store, budget):
            self._deny_without_spend(
                budget,
                lambda: budget.record_confirmed(
                    self._decision(),
                    idempotency_key="LOCAL_ISSUER",
                    effect_ref="FUTURE_CLAIM",
                    confirmed_at=NOW + timedelta(days=10),
                ),
            )

    def test_04_denial_does_not_evaluate_hostile_mapping(self):
        with self.lab() as (_store, budget):
            self._deny_without_spend(
                budget,
                lambda: budget.record_confirmed(
                    UntrustedDecision(),
                    idempotency_key="local-key",
                    effect_ref="local-effect",
                    confirmed_at=NOW,
                ),
            )

    def test_05_guard_is_still_read_only_and_grants_no_authority_after_denial(self):
        with self.lab() as (_store, budget):
            decision = self._decision()
            self._deny_without_spend(
                budget,
                lambda: budget.record_confirmed(
                    decision,
                    idempotency_key="local-key",
                    effect_ref="local-effect",
                    confirmed_at=NOW,
                ),
            )
            result = budget.guard(decision, now=NOW)
            self.assertTrue(result["allowed"])
            self.assertFalse(result["grants_authority"])
            self.assertFalse(result["execution_allowed_by_this_component"])
            self.assertEqual(self._snapshot(budget)["transaction_effects"], 0)

    def test_06_locally_seeded_idempotent_row_is_not_external_confirmation(self):
        with self.lab() as (_store, budget):
            decision = self._decision()
            key = "synthetic-existing-key"
            effect = "LOCAL_EFFECT_ROW"
            # This is a deliberately untrusted SQL fixture, not a receipt.
            with budget.db:
                budget.db.execute(
                    """INSERT INTO aion_authority_spend(
                         idempotency_key,owner,tenant,workspace,transaction_id,
                         authority_budget_ref,policy_version,capability_class,action,
                         risk_points,effect_ref,confirmed_at,decision_digest
                       ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        key, self.fixture.scope.owner_id,
                        self.fixture.scope.tenant_id,
                        self.fixture.scope.workspace_id,
                        decision["transaction_id"], decision["authority_budget_ref"],
                        decision["policy_version"], decision["capability_class"],
                        decision["action"], decision["risk_points"], effect,
                        NOW.isoformat(), budget_module._digest(dict(decision)),
                    ),
                )
            self.assertEqual(self._snapshot(budget)["transaction_effects"], 1)
            self._deny_without_spend(
                budget,
                lambda: budget.record_confirmed(
                    decision,
                    idempotency_key=key,
                    effect_ref=effect,
                    confirmed_at=NOW,
                ),
            )
            self.assertEqual(self._snapshot(budget)["transaction_effects"], 1)


    def test_07_guard_rejects_risk_limit_from_explicitly_synthetic_sqlite_rows(self):
        with self.lab(max_transaction_risk_points=3) as (_store, budget):
            decision = fixtures.decision(self.fixture.scope, risk_points=2)
            # Seed LOCAL accounting only; never invoke productive confirmation.
            with budget.db:
                budget.db.execute(
                    """INSERT INTO aion_authority_spend(
                         idempotency_key,owner,tenant,workspace,transaction_id,
                         authority_budget_ref,policy_version,capability_class,action,
                         risk_points,effect_ref,confirmed_at,decision_digest
                       ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        "synthetic-existing-risk", self.fixture.scope.owner_id,
                        self.fixture.scope.tenant_id,
                        self.fixture.scope.workspace_id,
                        decision["transaction_id"], decision["authority_budget_ref"],
                        decision["policy_version"], decision["capability_class"],
                        decision["action"], decision["risk_points"],
                        "LOCAL_UNTRUSTED_ACCOUNTING", NOW.isoformat(),
                        budget_module._digest(dict(decision)),
                    ),
                )
            changes = budget.db.total_changes
            out = budget.guard(decision, now=NOW)
            self.assertFalse(out["allowed"])
            self.assertIn("TRANSACTION_RISK_LIMIT", out["blockers"])
            self.assertFalse(out["grants_authority"])
            self.assertFalse(out["execution_allowed_by_this_component"])
            self.assertEqual(budget.db.total_changes, changes)
            self.assertEqual(self._snapshot(budget)["transaction_effects"], 1)


if __name__ == "__main__":
    unittest.main()
