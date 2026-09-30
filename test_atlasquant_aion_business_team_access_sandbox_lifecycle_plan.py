import ast
import unittest
from pathlib import Path

from atlasquant_aion_business_team_access_sandbox_evidence import SCHEMA as EVIDENCE_SCHEMA
from atlasquant_aion_business_team_access_sandbox_lifecycle_plan import (
    REQUIRED_ACKNOWLEDGEMENTS,
    REQUIRED_DECISION_TOKEN,
    build_lifecycle_test_plan,
    lifecycle_plan_policy,
)


def _baseline():
    return {
        "schema": EVIDENCE_SCHEMA,
        "version": "1",
        "state": "READY_FOR_ADMIN_TEAM_ACCESS_SANDBOX_LIFECYCLE_TEST_REVIEW",
        "evidence_digest": "a" * 64,
        "executes_action": False,
    }


class TeamAccessSandboxLifecyclePlanTests(unittest.TestCase):
    def test_policy_requires_explicit_sandbox_decision(self):
        policy = lifecycle_plan_policy()
        self.assertEqual(
            policy["state"], "TEAM_ACCESS_SANDBOX_LIFECYCLE_PLAN_POLICY_DEFINED"
        )
        self.assertEqual(policy["required_decision_token"], REQUIRED_DECISION_TOKEN)
        self.assertEqual(
            policy["required_acknowledgements"],
            list(REQUIRED_ACKNOWLEDGEMENTS),
        )
        self.assertFalse(policy["automatic_apply"])
        self.assertFalse(policy["production_targets_allowed"])
        self.assertFalse(policy["executes_action"])

    def test_valid_baseline_builds_non_executing_ten_step_plan(self):
        plan = build_lifecycle_test_plan(
            _baseline(),
            test_username="sandbox.operador.demo",
            tenant_ids=["tenant-a"],
            factor_type="PASSKEY",
            requested_by="admin.demo",
        )
        self.assertEqual(
            plan["state"],
            "READY_FOR_ADMIN_TEAM_ACCESS_SANDBOX_LIFECYCLE_EXECUTION_DECISION",
        )
        self.assertEqual(len(plan["steps"]), 10)
        self.assertTrue(plan["plan_digest"])
        self.assertFalse(plan["decision_recorded"])
        self.assertFalse(plan["account_creation_authorized"])
        self.assertFalse(plan["registry_write_authorized"])
        self.assertFalse(plan["session_revocation_authorized"])
        self.assertFalse(plan["production_authorized"])
        self.assertFalse(plan["executes_action"])

    def test_non_sandbox_username_or_bad_factor_blocks(self):
        plan = build_lifecycle_test_plan(
            _baseline(),
            test_username="operador.demo",
            tenant_ids=["tenant-a"],
            factor_type="SMS",
            requested_by="admin.demo",
        )
        self.assertEqual(
            plan["state"], "TEAM_ACCESS_SANDBOX_LIFECYCLE_PLAN_BLOCKED"
        )
        self.assertIn("test_username_sandbox_scoped", plan["blockers"])
        self.assertIn("factor_allowed", plan["blockers"])
        self.assertEqual(plan["steps"], [])
        self.assertEqual(plan["plan_digest"], "")

    def test_missing_baseline_or_tenant_blocks(self):
        plan = build_lifecycle_test_plan(
            {},
            test_username="sandbox.operador.demo",
            tenant_ids=[],
            factor_type="TOTP",
            requested_by="admin.demo",
        )
        self.assertEqual(
            plan["state"], "TEAM_ACCESS_SANDBOX_LIFECYCLE_PLAN_BLOCKED"
        )
        self.assertIn("baseline_review_ready", plan["blockers"])
        self.assertIn("tenant_scope_present", plan["blockers"])

    def test_module_has_no_network_process_or_provider_imports(self):
        source = Path(
            "atlasquant_aion_business_team_access_sandbox_lifecycle_plan.py"
        ).read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        self.assertFalse(
            imported.intersection(
                {"requests", "httpx", "socket", "subprocess", "docker"}
            )
        )


if __name__ == "__main__":
    unittest.main()
