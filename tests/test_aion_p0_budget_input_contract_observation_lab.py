"""AION LAB candidate: normative negative budget input contract.

This file is adapted from diagnostic tests in a separate review branch.
It now REQUIRES non-Mapping denial rather than accepting previous observed
gaps. No external sender/worker, receipt or real effect is executed.
"""
from __future__ import annotations

import tempfile
import unittest
from collections.abc import Mapping
from datetime import timedelta
from pathlib import Path

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_cumulative_authority_budget import CumulativeAuthorityBudget
import test_atlasquant_aion_execution_saga as saga_fx

NOW = saga_fx.NOW


class BudgetInputContractObservationsLAB(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.TemporaryDirectory()
        self.addCleanup(self.root.cleanup)
        self.store = SQLiteChatStore(Path(self.root.name) / "input-contract.sqlite3")
        self.addCleanup(self.store.close)
        self.scope = Scope("input-owner", "input-tenant", "input-workspace")
        self.budget = CumulativeAuthorityBudget(
            self.store, self.scope, authority_budget_ref="input-budget",
            policy_version="input-policy", max_transaction_effects=3,
        )

    def decision(self):
        return {
            "owner_id": self.scope.owner_id,
            "tenant_id": self.scope.tenant_id,
            "workspace_id": self.scope.workspace_id,
            "transaction_id": "input-tx",
            "authority_budget_ref": "input-budget",
            "policy_version": "input-policy",
            "capability_class": "LOW_RISK",
            "risk_points": 1,
            "action": "only_inert_preflight",
        }

    def assert_no_effects(self):
        snapshot = self.budget.snapshot("input-tx", now=NOW)
        self.assertEqual(snapshot["transaction_effects"], 0)
        self.assertEqual(snapshot["window_effects"], 0)

    def assert_no_external_authority(self, result):
        self.assertIs(result["grants_authority"], False)
        self.assertIs(result["execution_allowed_by_this_component"], False)
        self.assertIs(result["executes_action"], False)

    def test_01_baseline_dict_preflight_is_not_external_authority(self):
        out = self.budget.guard(self.decision(), now=NOW)
        self.assertIs(out["allowed"], True)
        self.assert_no_external_authority(out)
        self.assert_no_effects()

    def test_02_observed_gap_list_of_field_pairs_is_accepted_as_preflight(self):
        # Normative candidate: a list of pairs is not a Mapping and must deny.
        malformed = list(self.decision().items())
        self.assertNotIsInstance(malformed, dict)
        out = self.budget.guard(malformed, now=NOW)
        self.assertIs(out["allowed"], False, "non-Mapping input must be denied")
        self.assert_no_external_authority(out)
        self.assert_no_effects()

    def test_03_observed_gap_tuple_of_field_pairs_is_also_accepted(self):
        # Normative candidate: a tuple of pairs is not a Mapping and must deny.
        malformed = tuple(self.decision().items())
        self.assertNotIsInstance(malformed, dict)
        out = self.budget.guard(malformed, now=NOW)
        self.assertIs(out["allowed"], False, "non-Mapping input must be denied")
        self.assert_no_external_authority(out)
        self.assert_no_effects()

    def test_04_truthy_nonmapping_malformed_values_raise_without_effect(self):
        # Normative candidate: malformed truthy inputs never throw or allow.
        for malformed in (37, "not-a-mapping", True, [("owner_id", "wrong")]):
            with self.subTest(type=type(malformed).__name__):
                out = self.budget.guard(malformed, now=NOW)
                self.assertIs(out["allowed"], False)
                self.assert_no_external_authority(out)
                self.assertTrue(out["reason"].startswith(
                    "AUTHORITY_BUDGET_BINDING_INVALID:"))
                self.assert_no_effects()

    def test_05_falsy_nonmapping_values_return_explicit_denial(self):
        for malformed in (None, False, 0, "", [], ()):
            with self.subTest(type=type(malformed).__name__):
                out = self.budget.guard(malformed, now=NOW)
                self.assertIs(out["allowed"], False)
                self.assert_no_external_authority(out)
                self.assert_no_effects()

    def test_06_correctly_typed_but_wrong_scope_is_denied_not_promoted(self):
        forged = {**self.decision(), "tenant_id": "foreign-tenant"}
        out = self.budget.guard(forged, now=NOW)
        self.assertIs(out["allowed"], False)
        self.assert_no_external_authority(out)
        self.assert_no_effects()

    def test_07_no_sql_authority_written_by_any_guard_observation(self):
        values = [self.decision(), list(self.decision().items()),
                  tuple(self.decision().items()),
                  {**self.decision(), "risk_points": 100}]
        for item in values:
            self.budget.guard(item, now=NOW)
        self.assert_no_effects()


    def test_10_hostile_mapping_diagnostic_get_cannot_raise_or_approve(self):
        class HostileMapping(Mapping):
            def __len__(self):
                return 1
            def __iter__(self):
                raise RuntimeError("LOCAL_ITER_NOT_TRUSTED")
            def __getitem__(self, key):
                raise RuntimeError("LOCAL_INDEX_NOT_TRUSTED")
            def get(self, key, default=None):
                raise RuntimeError("LOCAL_GET_NOT_TRUSTED")
        out = self.budget.guard(HostileMapping(), now=NOW)
        self.assertIs(out["allowed"], False)
        self.assertEqual(out["transaction_id"], "")
        self.assertTrue(out["reason"].startswith(
            "AUTHORITY_BUDGET_BINDING_INVALID:"))
        self.assert_no_external_authority(out)
        self.assert_no_effects()


class BudgetInputRealConsumerObservationsLAB(unittest.TestCase):
    def setUp(self):
        self.fx = saga_fx.ExecutionSagaTests()
        self.fx.setUp()
        self.root = tempfile.TemporaryDirectory()
        self.addCleanup(self.root.cleanup)
        self.store, self.outbox, self.budget, self.saga = self.fx._components(
            self.root.name)
        self.addCleanup(self.store.close)
        self.fx._create(self.saga)
        self.first = self.fx._enqueue_forward(self.saga)
        self.key = self.first["outbox"]["idempotency_key"]

    def test_08_saga_direct_nonmapping_preflight_is_only_local_not_authority(self):
        decision = self.first["outbox"]["decision"]
        preflight = self.saga.authority_guard(list(decision.items()), now=NOW)
        # Normative candidate: non-Mapping list must deny at Saga facade.
        self.assertIs(preflight["allowed"], False)
        for name in ("grants_authority", "execution_allowed_by_this_component",
                     "executes_action"):
            self.assertIs(preflight[name], False)
        self.assertEqual(self.outbox.effect_count(), 0)

    def test_09_outbox_catches_guard_input_exception_and_denies_before_adapter(self):
        class DangerousAdapter:
            def __init__(self):
                self.descriptor_reads = 0
            @property
            def send(self):
                self.descriptor_reads += 1
                raise AssertionError("PROVIDER_BOUNDARY_CROSSED")
        adapter = DangerousAdapter()
        claimed = self.outbox.claim_next("input-lab-claim",
            now=NOW + timedelta(seconds=1), lease_seconds=60)
        self.assertEqual(claimed["idempotency_key"], self.key)
        called = []
        def bad_guard(_decision):
            called.append(True)
            return self.saga.authority_guard(100, now=NOW)
        result = self.outbox.dispatch_claimed(
            self.key, worker_id="input-lab-claim",
            authorize=saga_fx.policy(self.fx.scope),
            cumulative_authority_guard=bad_guard,
            adapter=adapter, now=NOW + timedelta(seconds=2))
        self.assertEqual(called, [True])
        self.assertEqual(result["state"], "BLOCKED_REAPPROVAL")
        self.assertEqual(result["last_error"], "AUTHORITY_BUDGET_BINDING_INVALID:TypeError")
        self.assertEqual(adapter.descriptor_reads, 0)
        self.assertEqual(self.outbox.effect_count(), 0)


if __name__ == "__main__":
    unittest.main()
