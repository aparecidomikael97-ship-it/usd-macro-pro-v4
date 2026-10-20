"""P0 independent cross-review of DRAFT PRs #1331 + #1333, LAB only.

A green result means the precise budget response/type invariants below are
observed, never that Quality is green, a producer is enrolled, a receipt exists,
or a user action is authorized. Original PR heads are NEVER modified.
"""
from __future__ import annotations

from collections.abc import Mapping
from datetime import timedelta
from pathlib import Path
from types import MappingProxyType
import tempfile
import unittest

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_cumulative_authority_budget import CumulativeAuthorityBudget
from atlasquant_aion_execution_outbox import ExecutionOutbox
from atlasquant_aion_execution_saga import ExecutionSagaCoordinator
import test_atlasquant_aion_execution_saga as fx

NOW = fx.NOW
FALSE_FLAGS = (
    "grants_authority",
    "execution_allowed_by_this_component",
    "executes_action",
)


class _HostileMapping(Mapping):
    def __len__(self):
        return 1

    def __iter__(self):
        raise RuntimeError("HOSTILE_ITERATOR")

    def __getitem__(self, _key):
        raise RuntimeError("HOSTILE_ITEM")

    def get(self, _key, default=None):
        raise RuntimeError("HOSTILE_GET")


class _ExplodingString:
    def __str__(self):
        raise RuntimeError("HOSTILE_VALUE_STR")


class _AdapterMustStayOpaque:
    def __init__(self):
        self.reads = 0

    @property
    def send(self):
        self.reads += 1
        raise AssertionError("external adapter descriptor was read")

    @property
    def reconcile(self):
        self.reads += 1
        raise AssertionError("external adapter reconcile descriptor was read")


class DualPRBudgetNegativeContractReviewLAB(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = SQLiteChatStore(Path(self.temp.name) / "cross.sqlite3")
        self.addCleanup(self.store.close)
        self.scope = Scope("review-owner", "review-tenant", "review-space")
        self.budget = CumulativeAuthorityBudget(
            self.store, self.scope,
            authority_budget_ref="budget-cross",
            policy_version="policy-cross",
            max_transaction_risk_points=4,
        )

    def decision(self):
        return {
            "owner_id": self.scope.owner_id,
            "tenant_id": self.scope.tenant_id,
            "workspace_id": self.scope.workspace_id,
            "transaction_id": "transaction-cross",
            "authority_budget_ref": "budget-cross",
            "policy_version": "policy-cross",
            "action": "inert_local_preflight",
            "capability_class": "LOW_RISK",
            "risk_points": 1,
        }

    def assert_inert(self, output, *, allowed):
        self.assertIs(output["allowed"], allowed)
        for key in FALSE_FLAGS:
            self.assertIn(key, output)
            self.assertIs(output[key], False)
        self.assertEqual(self.budget.snapshot(
            "transaction-cross", now=NOW)["transaction_effects"], 0)

    def test_01_plain_mapping_allowed_only_as_preflight(self):
        result = self.budget.guard(self.decision(), now=NOW)
        self.assert_inert(result, allowed=True)
        self.assertEqual(result["reason"], "ALLOW")

    def test_02_honest_immutable_mapping_subclass_remains_accepted(self):
        frozen = MappingProxyType(self.decision())
        self.assertIsInstance(frozen, Mapping)
        result = self.budget.guard(frozen, now=NOW)
        self.assert_inert(result, allowed=True)

    def test_03_list_tuple_and_generator_pairs_are_rejected(self):
        data = self.decision()
        for value in (list(data.items()), tuple(data.items()),
                      (item for item in data.items())):
            with self.subTest(kind=type(value).__name__):
                self.assertNotIsInstance(value, Mapping)
                result = self.budget.guard(value, now=NOW)
                self.assert_inert(result, allowed=False)
                self.assertEqual(result["reason"],
                                 "AUTHORITY_BUDGET_BINDING_INVALID:TypeError")
                self.assertEqual(result["transaction_id"], "")

    def test_04_truthy_nonmapping_objects_never_raise_or_grant_preflight(self):
        for value in (True, 99, "payload", b"bytes", object()):
            with self.subTest(kind=type(value).__name__):
                result = self.budget.guard(value, now=NOW)
                self.assert_inert(result, allowed=False)
                self.assertEqual(result["transaction_id"], "")

    def test_05_falsy_nonmapping_objects_are_also_structured_denials(self):
        for value in (None, False, 0, "", [], (), {}):
            with self.subTest(kind=type(value).__name__):
                result = self.budget.guard(value, now=NOW)
                self.assert_inert(result, allowed=False)
                if not isinstance(value, Mapping):
                    self.assertEqual(result["reason"],
                                     "AUTHORITY_BUDGET_BINDING_INVALID:TypeError")

    def test_06_hostile_mapping_getter_does_not_break_denial_formatter(self):
        result = self.budget.guard(_HostileMapping(), now=NOW)
        self.assert_inert(result, allowed=False)
        self.assertEqual(result["transaction_id"], "")
        self.assertIn("AUTHORITY_BUDGET_BINDING_INVALID:", result["reason"])

    def test_07_bound_mapping_with_throwing_diagnostic_value_denied(self):
        suspicious = self.decision()
        suspicious["transaction_id"] = _ExplodingString()
        result = self.budget.guard(suspicious, now=NOW)
        self.assert_inert(result, allowed=False)
        self.assertEqual(result["transaction_id"], "")
        self.assertEqual(result["reason"],
                         "AUTHORITY_BUDGET_BINDING_INVALID:RuntimeError")

    def test_08_identity_budget_and_policy_mismatches_denied_consistently(self):
        for field in ("owner_id", "tenant_id", "workspace_id",
                      "authority_budget_ref", "policy_version"):
            with self.subTest(field=field):
                result = self.budget.guard(
                    {**self.decision(), field: "foreign-value"}, now=NOW)
                self.assert_inert(result, allowed=False)
                self.assertEqual(result["reason"],
                                 "AUTHORITY_BUDGET_BINDING_INVALID:ValueError")

    def test_09_critical_and_excess_risk_denied_with_explicit_flags(self):
        for change, reason in (
            ({"capability_class": "CRITICAL"}, "CRITICAL_CAPABILITY_REQUIRES_SEPARATE_HUMAN_GATE"),
            ({"risk_points": 5}, "TRANSACTION_RISK_LIMIT"),
        ):
            with self.subTest(reason=reason):
                result = self.budget.guard({**self.decision(), **change},
                                           now=NOW)
                self.assert_inert(result, allowed=False)
                self.assertIn(reason, result["blockers"])

    def test_10_no_new_authority_ledger_rows_from_all_preflights(self):
        cases = (self.decision(), MappingProxyType(self.decision()),
                 list(self.decision().items()), _HostileMapping(), 123)
        for case in cases:
            self.budget.guard(case, now=NOW)
        self.assertEqual(self.budget.snapshot(
            "transaction-cross", now=NOW)["transaction_effects"], 0)


class DualPRBudgetConsumersReviewLAB(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.fixture = fx.ExecutionSagaTests()
        self.fixture.setUp()
        self.store, self.outbox, self.budget, self.saga = (
            self.fixture._components(self.temp.name))
        self.addCleanup(self.store.close)
        self.fixture._create(self.saga)
        item = self.fixture._enqueue_forward(self.saga)
        self.key = item["outbox"]["idempotency_key"]
        self.adapter = _AdapterMustStayOpaque()

    def _dispatch(self, guard):
        row = self.outbox.claim_next(
            "review-worker", now=NOW + timedelta(seconds=1),
            lease_seconds=60)
        self.assertEqual(row["idempotency_key"], self.key)
        return self.outbox.dispatch_claimed(
            self.key, worker_id="review-worker",
            adapter=self.adapter, authorize=fx.policy(self.fixture.scope),
            cumulative_authority_guard=guard,
            now=NOW + timedelta(seconds=2),
        )

    def test_11_saga_facade_rejects_nonmapping_without_mutation(self):
        before = self.saga.get("saga-1")
        decision = self.outbox.get(self.key)["decision"]
        result = self.saga.authority_guard(
            list(decision.items()), now=NOW)
        self.assertIs(result["allowed"], False)
        for flag in FALSE_FLAGS:
            self.assertIs(result[flag], False)
        self.assertEqual(self.saga.get("saga-1"), before)
        self.assertEqual(self.outbox.effect_count(), 0)

    def test_12_outbox_blocks_structured_budget_denial_without_adapter(self):
        result = self._dispatch(
            lambda decision: self.saga.authority_guard(
                list(decision.items()), now=NOW))
        self.assertEqual(result["state"], "BLOCKED_REAPPROVAL")
        self.assertEqual(result["last_error"],
                         "AUTHORITY_BUDGET_BINDING_INVALID:TypeError")
        self.assertEqual(self.adapter.reads, 0)
        self.assertEqual(self.outbox.effect_count(), 0)

    def test_13_valid_mapping_budget_preflight_keeps_producer_hardstop(self):
        def preflight(decision):
            result = self.saga.authority_guard(
                MappingProxyType(decision), now=NOW)
            self.assertIs(result["allowed"], True)
            for flag in FALSE_FLAGS:
                self.assertIs(result[flag], False)
            return result
        with self.assertRaisesRegex(
            PermissionError, "^INDEPENDENT_PRODUCER_NOT_ENROLLED$"):
            self._dispatch(preflight)
        self.assertEqual(self.outbox.get(self.key)["state"], "BLOCKED_PRODUCER")
        self.assertEqual(self.adapter.reads, 0)
        self.assertEqual(self.outbox.effect_count(), 0)

    def test_14_hostile_mapping_fails_closed_before_adapter_or_effect(self):
        result = self._dispatch(
            lambda decision: self.saga.authority_guard(
                _HostileMapping(), now=NOW))
        self.assertEqual(result["state"], "BLOCKED_REAPPROVAL")
        self.assertIn("AUTHORITY_BUDGET_BINDING_INVALID:",
                      result["last_error"])
        self.assertEqual(self.adapter.reads, 0)
        self.assertEqual(self.outbox.effect_count(), 0)


if __name__ == "__main__":
    unittest.main()
