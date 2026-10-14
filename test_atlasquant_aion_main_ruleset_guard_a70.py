"""A70 negative regression suite: no admin requests and no git mutations."""
import copy
from pathlib import Path
import unittest

from atlasquant_aion_main_ruleset_guard_a70 import (
    CHECK_SOURCE_APP_ID,
    REQUIRED_CHECKS,
    audit_observed,
    evaluate_ruleset,
    read_proposal,
)

ROOT = Path(__file__).resolve().parent


class MainRulesetA70Tests(unittest.TestCase):
    def setUp(self):
        self.good = read_proposal()

    def test_01_exact_main_only_active_rule_and_checks_are_valid(self):
        self.assertEqual(evaluate_ruleset(self.good), [])
        self.assertEqual(
            {s["context"] for r in self.good["rules"]
             if r["type"] == "required_status_checks"
             for s in r["parameters"]["required_status_checks"]},
            REQUIRED_CHECKS,
        )

    def test_02_actual_unprotected_empty_ruleset_is_hard_no_go(self):
        result = audit_observed({"protected": False}, [])
        self.assertEqual(result["status"], "HARD_NO_GO")
        self.assertIn("A70_MAIN_UNPROTECTED", result["missing"])
        self.assertIn("A70_NO_ACTIVE_RULESET", result["missing"])
        self.assertFalse(result["approves_merge"])

    def test_03_protected_flag_alone_does_not_certify_checks(self):
        result = audit_observed({"protected": True}, [])
        self.assertEqual(result["status"], "HARD_NO_GO")

    def test_04_ruleset_summary_only_cannot_count_as_verified(self):
        result = audit_observed(
            {"protected": True},
            [{"id": 2, "name": "ATLASQUANT_MAIN_P0_GUARD", "enforcement": "active"}],
        )
        self.assertIn("A70_NO_VERIFIED_RULESET_DETAILS", result["missing"])

    def test_05_synthetic_complete_rule_is_necessary_but_not_independent_witness(self):
        result = audit_observed({"protected": True}, [self.good])
        self.assertEqual(result["status"], "PROTECTION_POLICY_VERIFIED")
        self.assertFalse(result["independent_f1_t1_witness"])
        self.assertFalse(result["approves_merge"])
        self.assertFalse(result["applies_any_change"])

    def test_06_monitor_mode_or_bypass_is_rejected(self):
        altered = copy.deepcopy(self.good)
        altered["enforcement"] = "evaluate"
        self.assertIn("A70_NOT_ACTIVE_BRANCH_GUARD", evaluate_ruleset(altered))
        altered = copy.deepcopy(self.good)
        altered["bypass_actors"] = [{"actor_id": 1, "actor_type": "RepositoryRole", "bypass_mode": "always"}]
        self.assertIn("A70_BYPASS_NOT_EMPTY", evaluate_ruleset(altered))

    def test_07_wildcard_or_runtime_scope_rejected(self):
        for include in (["~ALL"], ["refs/heads/*"], ["refs/heads/atlasquant-runtime"]):
            with self.subTest(include=include):
                altered = copy.deepcopy(self.good)
                altered["conditions"]["ref_name"]["include"] = include
                self.assertIn("A70_MAIN_ONLY_SCOPE_REQUIRED", evaluate_ruleset(altered))

    def test_08_missing_pr_requirement_rejected(self):
        altered = copy.deepcopy(self.good)
        altered["rules"] = [r for r in altered["rules"] if r["type"] != "pull_request"]
        self.assertIn("A70_PR_REQUIRED_OR_REVIEW_POLICY_CHANGED", evaluate_ruleset(altered))

    def test_09_changed_owner_review_expectations_rejected(self):
        altered = copy.deepcopy(self.good)
        altered["rules"][0]["parameters"]["require_code_owner_review"] = True
        self.assertIn("A70_PR_REQUIRED_OR_REVIEW_POLICY_CHANGED", evaluate_ruleset(altered))

    def test_10_wrong_source_or_missing_adversarial_gate_rejected(self):
        altered = copy.deepcopy(self.good)
        altered["rules"][1]["parameters"]["required_status_checks"][0]["integration_id"] = 0
        self.assertIn("A70_REQUIRED_CHECK_SET_OR_SOURCE_MISMATCH", evaluate_ruleset(altered))
        altered = copy.deepcopy(self.good)
        altered["rules"][1]["parameters"]["required_status_checks"] = [
            z for z in altered["rules"][1]["parameters"]["required_status_checks"]
            if z["context"] != "AION adversarial contracts"
        ]
        self.assertIn("A70_REQUIRED_CHECK_SET_OR_SOURCE_MISMATCH", evaluate_ruleset(altered))

    def test_11_missing_strict_mode_force_push_or_deletion_rejected(self):
        altered = copy.deepcopy(self.good)
        altered["rules"][1]["parameters"]["strict_required_status_checks_policy"] = False
        self.assertIn("A70_STRICT_REQUIRED_CHECKS_MISSING", evaluate_ruleset(altered))
        for name, failure in (
            ("deletion", "A70_DELETION_NOT_BLOCKED"),
            ("non_fast_forward", "A70_FORCE_PUSH_NOT_BLOCKED"),
        ):
            with self.subTest(name=name):
                altered = copy.deepcopy(self.good)
                altered["rules"] = [r for r in altered["rules"] if r["type"] != name]
                self.assertIn(failure, evaluate_ruleset(altered))

    def test_12_real_workflow_produces_three_required_names_on_pr_main(self):
        quality = (ROOT / ".github/workflows/quality-tests.yml").read_text(encoding="utf-8")
        security = (ROOT / ".github/workflows/aion-core-security-gate.yml").read_text(encoding="utf-8")
        self.assertIn("main", quality.split("  pull_request:", 1)[1].split("  push:", 1)[0])
        self.assertIn("  test:\n    runs-on:", quality)
        self.assertIn("  pull_request:\n    branches: [main,", security)
        self.assertIn("name: AION adversarial contracts", security)
        self.assertIn("name: Supply-chain audit", security)
        self.assertEqual(CHECK_SOURCE_APP_ID, 15368)


if __name__ == "__main__":
    unittest.main()
