"""A330 LAB: normative fail-closed Mapping input contract for Budget.guard.

Directly checks the real CumulativeAuthorityBudget. A valid local budget
preflight still does not authorize a send, Worker, provider or external effect.
This file replaces broken-behavior observational expectations with normative
denials; no P0 is homologated and no real account is enrolled.
"""
from datetime import datetime, timezone
from pathlib import Path
import tempfile
from types import MappingProxyType
import unittest

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_cumulative_authority_budget import CumulativeAuthorityBudget

NOW = datetime(2026, 10, 31, 9, 0, tzinfo=timezone.utc)


class A330BudgetMappingContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="a330-budget-lab-")
        self.addCleanup(self.temp.cleanup)
        self.store = SQLiteChatStore(
            Path(self.temp.name) / "only-synthetic.sqlite"
        )
        self.addCleanup(self.store.close)
        self.scope = Scope("a330-owner", "a330-tenant", "a330-workspace")
        self.budget = CumulativeAuthorityBudget(
            self.store, self.scope,
            authority_budget_ref="a330-budget",
            policy_version="a330-policy",
        )

    def decision(self):
        return {
            "owner_id": self.scope.owner_id,
            "tenant_id": self.scope.tenant_id,
            "workspace_id": self.scope.workspace_id,
            "transaction_id": "a330-intent",
            "authority_budget_ref": "a330-budget",
            "policy_version": "a330-policy",
            "action": "synthetic_no_effect",
            "capability_class": "LOW_RISK",
            "risk_points": 1,
        }

    def assert_no_authority(self, result):
        self.assertIs(result["grants_authority"], False)
        self.assertIs(
            result["execution_allowed_by_this_component"], False
        )
        self.assertIs(result["executes_action"], False)
        self.assertEqual(result["schema"],
                         "ATLASQUANT_AION_CUMULATIVE_AUTHORITY_BUDGET_V1")

    def assert_no_spend(self):
        snap = self.budget.snapshot("a330-intent", now=NOW)
        self.assertEqual(snap["transaction_effects"], 0)
        self.assertEqual(snap["window_effects"], 0)

    def test_valid_plain_dict_remains_inert_preflight(self):
        r = self.budget.guard(self.decision(), now=NOW)
        self.assertTrue(r["allowed"])
        self.assert_no_authority(r)
        self.assert_no_spend()

    def test_valid_readonly_mapping_is_not_rejected_as_sequence(self):
        r = self.budget.guard(MappingProxyType(self.decision()), now=NOW)
        self.assertTrue(r["allowed"])
        self.assert_no_authority(r)
        self.assert_no_spend()

    def test_list_tuple_and_items_of_valid_pairs_are_denied(self):
        decision = self.decision()
        for malformed in (
            list(decision.items()), tuple(decision.items()),
            decision.items(),
        ):
            with self.subTest(kind=type(malformed).__name__):
                r = self.budget.guard(malformed, now=NOW)
                self.assertIs(r["allowed"], False)
                self.assertTrue(r["reason"].startswith(
                    "AUTHORITY_BUDGET_BINDING_INVALID:"
                ))
                self.assert_no_authority(r)
                self.assert_no_spend()

    def test_truthy_nonmappings_get_structured_denial_not_attributeerror(self):
        for malformed in (
            37, True, "not-a-mapping", b"not-a-mapping",
            [("owner_id", "a330-owner")], ("owner_id", "fake"),
        ):
            with self.subTest(kind=type(malformed).__name__):
                r = self.budget.guard(malformed, now=NOW)
                self.assertIs(r["allowed"], False)
                self.assert_no_authority(r)
                self.assert_no_spend()

    def test_falsy_nonmappings_are_also_denied_with_all_flags(self):
        for malformed in (None, False, 0, "", b"", [], ()):
            with self.subTest(value=repr(malformed)):
                r = self.budget.guard(malformed, now=NOW)
                self.assertIs(r["allowed"], False)
                self.assert_no_authority(r)
                self.assert_no_spend()

    def test_hostile_nonmapping_is_not_queried_stringified_or_booleanized(self):
        class Hostile:
            def __bool__(self):
                raise AssertionError("UNTRUSTED_BOOL_CALLED")
            def __str__(self):
                raise AssertionError("UNTRUSTED_STR_CALLED")
            @property
            def get(self):
                raise AssertionError("UNTRUSTED_GET_READ")
        r = self.budget.guard(Hostile(), now=NOW)
        self.assertIs(r["allowed"], False)
        self.assert_no_authority(r)
        self.assert_no_spend()

    def test_invalid_dict_transaction_id_object_not_stringified_in_denial(self):
        class HostileId:
            def __str__(self):
                raise AssertionError("UNTRUSTED_TX_STRINGIFIED")
            def __bool__(self):
                raise AssertionError("UNTRUSTED_TX_BOOL_CALLED")
        invalid = {**self.decision(), "transaction_id": HostileId()}
        r = self.budget.guard(invalid, now=NOW)
        self.assertIs(r["allowed"], False)
        self.assertEqual(r["transaction_id"], "")
        self.assert_no_authority(r)
        self.assert_no_spend()

    def test_invalid_plain_dict_safe_transaction_id_is_preserved(self):
        invalid = {**self.decision(), "tenant_id": "forged-tenant"}
        r = self.budget.guard(invalid, now=NOW)
        self.assertIs(r["allowed"], False)
        self.assertEqual(r["transaction_id"], "a330-intent")
        self.assert_no_authority(r)
        self.assert_no_spend()

    def test_valid_critical_capability_remains_denied(self):
        critical = {**self.decision(), "capability_class": "CRITICAL"}
        r = self.budget.guard(critical, now=NOW)
        self.assertFalse(r["allowed"])
        self.assertIn(
            "CRITICAL_CAPABILITY_REQUIRES_SEPARATE_HUMAN_GATE",
            r["blockers"],
        )
        self.assert_no_authority(r)
        self.assert_no_spend()

    def test_no_guard_result_writes_effect_ledger(self):
        cases = (
            self.decision(),
            list(self.decision().items()),
            tuple(self.decision().items()),
            {**self.decision(), "risk_points": 100},
            None, 42, "invalid",
        )
        for item in cases:
            with self.subTest(kind=type(item).__name__):
                result = self.budget.guard(item, now=NOW)
                self.assert_no_authority(result)
        self.assert_no_spend()


if __name__ == "__main__":
    unittest.main()
