"""AION P0 LAB #1330: Budget.guard invalid-result schema parity and consumers.

Offline, no producer, no worker, no external API, no real authority.
The source fix under test ONLY adds explicit False on a previously invalid
response path; success preflight must NEVER grant execution authority.
"""
from __future__ import annotations

import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_cumulative_authority_budget import CumulativeAuthorityBudget
import test_atlasquant_aion_execution_saga as saga_fx

NOW = saga_fx.NOW
SECURITY_FLAGS = (
    "grants_authority",
    "execution_allowed_by_this_component",
    "executes_action",
)


class BudgetGuardSchemaParityLAB(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = SQLiteChatStore(Path(self.tmp.name) / "budget-schema-lab.sqlite3")
        self.addCleanup(self.store.close)
        self.scope = Scope("schema-owner", "schema-tenant", "schema-space")
        self.budget = CumulativeAuthorityBudget(
            self.store, self.scope, authority_budget_ref="budget-schema",
            policy_version="schema-v1",
            max_transaction_risk_points=3,
        )

    def decision(self):
        return {
            "owner_id": self.scope.owner_id,
            "tenant_id": self.scope.tenant_id,
            "workspace_id": self.scope.workspace_id,
            "transaction_id": "tx-schema",
            "authority_budget_ref": "budget-schema",
            "policy_version": "schema-v1",
            "capability_class": "LOW_RISK",
            "action": "stage_without_external_effect",
            "risk_points": 1,
        }

    def assert_inert(self, output, *, allowed):
        self.assertIs(output["allowed"], allowed)
        for key in SECURITY_FLAGS:
            self.assertIn(key, output, f"missing explicit authority flag: {key}")
            self.assertIs(output[key], False, f"unexpected external authority: {key}")
        self.assertEqual(output["scope"], {
            "owner_id": self.scope.owner_id,
            "tenant_id": self.scope.tenant_id,
            "workspace_id": self.scope.workspace_id,
        })

    def test_01_valid_preflight_still_has_no_execution_authority(self):
        out = self.budget.guard(self.decision(), now=NOW)
        self.assert_inert(out, allowed=True)
        self.assertEqual(out["reason"], "ALLOW")

    def test_02_identity_scope_policy_and_budget_mismatches_all_deny(self):
        for field, bad in (
            ("owner_id", "foreign-owner"),
            ("tenant_id", "foreign-tenant"),
            ("workspace_id", "foreign-space"),
            ("policy_version", "foreign-policy"),
            ("authority_budget_ref", "foreign-budget"),
        ):
            with self.subTest(field=field):
                forged = {**self.decision(), field: bad}
                out = self.budget.guard(forged, now=NOW)
                self.assert_inert(out, allowed=False)
                self.assertEqual(out["reason"], "AUTHORITY_BUDGET_BINDING_INVALID:ValueError")

    def test_03_invalid_risk_and_capability_all_deny_with_explicit_flags(self):
        for field, bad in (
            ("risk_points", -1),
            ("risk_points", 101),
            ("risk_points", True),
            ("risk_points", "2"),
            ("capability_class", "MADE_UP_CAPABILITY"),
            ("action", ""),
        ):
            with self.subTest(field=field, value=bad):
                forged = {**self.decision(), field: bad}
                out = self.budget.guard(forged, now=NOW)
                self.assert_inert(out, allowed=False)
                self.assertTrue(out["reason"].startswith(
                    "AUTHORITY_BUDGET_BINDING_INVALID:"))

    def test_04_missing_transaction_binding_denies_with_explicit_flags(self):
        for field in ("transaction_id", "authority_budget_ref", "policy_version"):
            with self.subTest(field=field):
                forged = self.decision()
                del forged[field]
                out = self.budget.guard(forged, now=NOW)
                self.assert_inert(out, allowed=False)
                self.assertTrue(out["reason"].startswith(
                    "AUTHORITY_BUDGET_BINDING_INVALID:"))

    def test_05_budget_limit_exceeded_stays_denied_with_explicit_flags(self):
        forged = {**self.decision(), "risk_points": 4}
        out = self.budget.guard(forged, now=NOW)
        self.assert_inert(out, allowed=False)
        self.assertIn("TRANSACTION_RISK_LIMIT", out["blockers"])

    def test_06_critical_capability_still_hard_denied_with_explicit_flags(self):
        forged = {**self.decision(), "capability_class": "CRITICAL"}
        out = self.budget.guard(forged, now=NOW)
        self.assert_inert(out, allowed=False)
        self.assertIn("CRITICAL_CAPABILITY_REQUIRES_SEPARATE_HUMAN_GATE",
                      out["blockers"])

    def test_07_invalid_response_never_records_local_budget_effect(self):
        invalid = {**self.decision(), "workspace_id": "forged-space"}
        before = self.budget.snapshot("tx-schema", now=NOW)
        out = self.budget.guard(invalid, now=NOW)
        self.assert_inert(out, allowed=False)
        after = self.budget.snapshot("tx-schema", now=NOW)
        self.assertEqual(after, before)
        self.assertEqual(after["transaction_effects"], 0)


class BudgetGuardActualConsumersLAB(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.fx = saga_fx.ExecutionSagaTests()
        self.fx.setUp()
        self.store, self.outbox, self.budget, self.saga = self.fx._components(
            self.tmp.name)
        self.addCleanup(self.store.close)
        self.fx._create(self.saga)
        self.first = self.fx._enqueue_forward(self.saga)
        self.key = self.first["outbox"]["idempotency_key"]

    class HostileAdapter:
        def __init__(self):
            self.attribute_reads = 0

        @property
        def send(self):
            self.attribute_reads += 1
            raise AssertionError("no external adapter descriptor permitted")

        @property
        def reconcile(self):
            self.attribute_reads += 1
            raise AssertionError("no external reconcile descriptor permitted")

    def dispatch(self, guard):
        row = self.outbox.claim_next(
            "schema-lab-worker", now=NOW + timedelta(seconds=1),
            lease_seconds=60)
        self.assertIsNotNone(row)
        self.assertEqual(row["idempotency_key"], self.key)
        adapter = self.HostileAdapter()
        try:
            result = self.outbox.dispatch_claimed(
                self.key, worker_id="schema-lab-worker",
                authorize=saga_fx.policy(self.fx.scope),
                cumulative_authority_guard=guard,
                adapter=adapter, now=NOW + timedelta(seconds=2))
            return result, adapter
        except BaseException:
            self.assertEqual(adapter.attribute_reads, 0)
            raise

    def test_08_outbox_does_not_use_deny_result_as_permission(self):
        def guard(decision):
            forged = {**decision, "tenant_id": "forged-tenant"}
            result = self.saga.authority_guard(forged, now=NOW)
            for field in SECURITY_FLAGS:
                self.assertIs(result[field], False)
            self.assertIs(result["allowed"], False)
            return result
        result, adapter = self.dispatch(guard)
        self.assertEqual(result["state"], "BLOCKED_REAPPROVAL")
        self.assertIn("AUTHORITY_BUDGET_BINDING_INVALID", result["last_error"])
        self.assertEqual(adapter.attribute_reads, 0)
        self.assertEqual(self.outbox.effect_count(), 0)

    def test_09_no_budget_guard_blocks_before_adapter_access(self):
        result, adapter = self.dispatch(None)
        self.assertEqual(result["state"], "BLOCKED_REAPPROVAL")
        self.assertEqual(result["last_error"], "CUMULATIVE_AUTHORITY_GUARD_REQUIRED")
        self.assertEqual(adapter.attribute_reads, 0)
        self.assertEqual(self.outbox.effect_count(), 0)

    def test_10_even_valid_budget_passes_to_independent_producer_hardstop(self):
        def guard(decision):
            preflight = self.saga.authority_guard(decision, now=NOW)
            self.assertIs(preflight["allowed"], True)
            for field in SECURITY_FLAGS:
                self.assertIs(preflight[field], False)
            return preflight
        with self.assertRaisesRegex(
            PermissionError, "^INDEPENDENT_PRODUCER_NOT_ENROLLED$"
        ):
            self.dispatch(guard)
        self.assertEqual(self.outbox.get(self.key)["state"], "BLOCKED_PRODUCER")
        self.assertEqual(self.outbox.effect_count(), 0)


if __name__ == "__main__":
    unittest.main()
