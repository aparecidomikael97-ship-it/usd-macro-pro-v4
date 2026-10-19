"""P0 LAB: direct authority-budget SQLite calls must fail closed on foreign thread.

Contracts are frozen BEFORE modification of the A118 CumulativeAuthorityBudget.
Real SQLiteChatStore and persistent budget ledger in temporary directories.
Synthetic records are NOT authenticated external effect receipts.
No provider, Worker, sending, network, merge or production credentials.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore, StorageUnavailableError, HEALTHY
from atlasquant_aion_cumulative_authority_budget import CumulativeAuthorityBudget
from test_atlasquant_aion_cumulative_authority_budget import decision

NOW = datetime(2026, 10, 19, 21, 0, tzinfo=timezone.utc)
SCOPE = Scope("p0-budget-owner", "p0-budget-tenant", "p0-budget-workspace")
THREAD_DENIAL = "SQLITE_STORE_CONNECTION_THREAD_MISMATCH"
NESTED_DENIAL = "AUTHORITY_BUDGET_NESTED_TRANSACTION_UNSUPPORTED"


class P0BudgetSQLiteOwnerThreadTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="p0-budget-sqlite-")
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "budget.sqlite3"
        self.store = SQLiteChatStore(self.path)
        self.addCleanup(self.store.close)
        self.budget = CumulativeAuthorityBudget(
            self.store, SCOPE, authority_budget_ref="fixture-budget",
            policy_version="fixture-policy",
        )
        self.row = decision(
            SCOPE, transaction_id="fixture-transaction",
            budget_ref="fixture-budget", policy_version="fixture-policy",
            action="fixture-no-provider", capability_class="LOW_RISK", risk_points=2
        )

    def audit(self):
        self.assertEqual(self.store.storage_health(deep=True)["state"], HEALTHY)
        own = self.budget.snapshot("fixture-transaction", now=NOW)
        self.assertEqual(own["transaction_effects"], 0)
        self.assertEqual(own["window_effects"], 0)
        self.assertFalse(own["grants_authority"])
        self.assertFalse(own["executes_action"])

    def foreign_denial(self, callback):
        self.audit()
        with ThreadPoolExecutor(max_workers=1) as pool:
            with self.assertRaisesRegex(StorageUnavailableError, THREAD_DENIAL):
                pool.submit(callback).result(timeout=15)
        self.audit()

    def test_01_foreign_valid_guard_refused_before_read(self):
        self.foreign_denial(lambda: self.budget.guard(self.row, now=NOW))

    def test_02_foreign_invalid_guard_refused_before_binding_fallback(self):
        # Even a budget-binding error in a foreign thread cannot be mistaken
        # for a normal policy decision or mutate store health.
        self.foreign_denial(lambda: self.budget.guard({}, now=NOW))

    def test_03_foreign_snapshot_refused(self):
        self.foreign_denial(lambda: self.budget.snapshot("fixture-transaction", now=NOW))

    def test_04_foreign_record_confirmed_refused_before_sql_begin(self):
        self.foreign_denial(lambda: self.budget.record_confirmed(
            self.row, idempotency_key="fixture-only-key",
            effect_ref="synthetic-only-effect", confirmed_at=NOW,
        ))

    def test_05_foreign_record_invalid_arguments_still_refused(self):
        self.foreign_denial(lambda: self.budget.record_confirmed(
            {}, idempotency_key="", effect_ref="", confirmed_at=NOW,
        ))

    def test_06_foreign_private_snapshot_still_refused(self):
        self.foreign_denial(lambda: self.budget._snapshot(
            transaction_id="fixture-transaction", now=NOW,
        ))

    def test_07_foreign_scope_args_still_refused(self):
        self.foreign_denial(self.budget._scope_args)

    def test_08_denial_does_not_rollback_external_transaction(self):
        self.store.db.execute("CREATE TABLE p0_budget_sentinel (k TEXT PRIMARY KEY)")
        self.store.db.execute("BEGIN IMMEDIATE")
        try:
            self.store.db.execute("INSERT INTO p0_budget_sentinel VALUES ('pending')")
            with ThreadPoolExecutor(max_workers=1) as pool:
                with self.assertRaisesRegex(StorageUnavailableError, THREAD_DENIAL):
                    pool.submit(lambda: self.budget.record_confirmed(
                        self.row, idempotency_key="fixture-other",
                        effect_ref="synthetic-only-effect", confirmed_at=NOW,
                    )).result(timeout=15)
            self.assertTrue(self.store.db.in_transaction)
            self.assertEqual(self.store.db.execute(
                "SELECT COUNT(*) FROM p0_budget_sentinel"
            ).fetchone()[0], 1)
            self.assertEqual(self.budget.snapshot("fixture-transaction", now=NOW)["transaction_effects"], 0)
        finally:
            self.store.db.rollback()
        self.audit()

    def test_09_owner_guard_is_readonly_not_authorization(self):
        out = self.budget.guard(self.row, now=NOW)
        self.assertTrue(out["allowed"])
        self.assertFalse(out["grants_authority"])
        self.assertFalse(out["execution_allowed_by_this_component"])
        self.assertFalse(out["executes_action"])
        self.audit()

    def test_10_owner_guard_rejects_scope_mismatch_without_effect(self):
        other = dict(self.row)
        other["tenant_id"] = "another-tenant"
        out = self.budget.guard(other, now=NOW)
        self.assertFalse(out["allowed"])
        self.assertFalse(out["grants_authority"])
        self.audit()

    def test_11_owner_record_is_synthetic_and_idempotent(self):
        first = self.budget.record_confirmed(
            self.row, idempotency_key="fixture-key-one",
            effect_ref="synthetic-no-provider", confirmed_at=NOW
        )
        again = self.budget.record_confirmed(
            self.row, idempotency_key="fixture-key-one",
            effect_ref="synthetic-no-provider", confirmed_at=NOW
        )
        self.assertEqual(first["state"], "RECORDED")
        self.assertEqual(again["state"], "IDEMPOTENT")
        self.assertFalse(first["grants_authority"])
        self.assertFalse(first["executes_action"])
        self.assertEqual(self.budget.snapshot("fixture-transaction", now=NOW)["transaction_effects"], 1)

    def test_12_record_confirmed_nested_tx_requires_typed_denial_and_preserves_parent(self):
        self.store.db.execute("CREATE TABLE p0_budget_parent (k TEXT PRIMARY KEY)")
        self.store.db.execute("BEGIN IMMEDIATE")
        try:
            self.store.db.execute("INSERT INTO p0_budget_parent VALUES ('caller')")
            with self.assertRaisesRegex(RuntimeError, NESTED_DENIAL):
                self.budget.record_confirmed(
                    self.row, idempotency_key="fixture-no-commit",
                    effect_ref="synthetic-only-effect", confirmed_at=NOW
                )
            self.assertTrue(self.store.db.in_transaction)
            self.assertEqual(self.store.db.execute(
                "SELECT COUNT(*) FROM p0_budget_parent"
            ).fetchone()[0], 1)
            self.assertEqual(self.budget.snapshot("fixture-transaction", now=NOW)["transaction_effects"], 0)
        finally:
            self.store.db.rollback()
        self.audit()

    def test_13_nested_denial_preserves_savepoint_owner(self):
        self.store.db.execute("SAVEPOINT caller_budget_savepoint")
        try:
            with self.assertRaisesRegex(RuntimeError, NESTED_DENIAL):
                self.budget.record_confirmed(
                    self.row, idempotency_key="fixture-no-commit",
                    effect_ref="synthetic-only-effect", confirmed_at=NOW
                )
            self.assertTrue(self.store.db.in_transaction)
            self.store.db.execute("ROLLBACK TO SAVEPOINT caller_budget_savepoint")
            self.store.db.execute("RELEASE SAVEPOINT caller_budget_savepoint")
        finally:
            if self.store.db.in_transaction:
                self.store.db.rollback()
        self.audit()

    def test_14_owner_can_commit_own_transaction_after_denial(self):
        self.store.db.execute("CREATE TABLE p0_budget_commit (k TEXT PRIMARY KEY)")
        self.store.db.execute("BEGIN IMMEDIATE")
        try:
            self.store.db.execute("INSERT INTO p0_budget_commit VALUES ('unrelated')")
            with self.assertRaisesRegex(RuntimeError, NESTED_DENIAL):
                self.budget.record_confirmed(
                    self.row, idempotency_key="fixture-no-commit",
                    effect_ref="synthetic-only-effect", confirmed_at=NOW
                )
            self.assertTrue(self.store.db.in_transaction)
            self.store.db.commit()
        finally:
            if self.store.db.in_transaction:
                self.store.db.rollback()
        self.assertEqual(self.store.db.execute(
            "SELECT COUNT(*) FROM p0_budget_commit"
        ).fetchone()[0], 1)
        self.audit()

    def test_15_separate_store_owned_by_foreign_thread_is_allowed_to_read(self):
        def run():
            store = SQLiteChatStore(self.path)
            try:
                budget = CumulativeAuthorityBudget(
                    store, SCOPE, authority_budget_ref="fixture-budget",
                    policy_version="fixture-policy",
                )
                return budget.snapshot("fixture-transaction", now=NOW)
            finally:
                store.close()
        with ThreadPoolExecutor(max_workers=1) as pool:
            snap = pool.submit(run).result(timeout=20)
        self.assertEqual(snap["transaction_effects"], 0)
        self.assertFalse(snap["grants_authority"])
        self.audit()


if __name__ == "__main__":
    unittest.main()
