import ast
import unittest
from pathlib import Path

from atlasquant_aion_business_team_access_lifecycle_plan_package import (
    lifecycle_plan_package_policy,
    validate_lifecycle_plan_package,
)
from atlasquant_aion_business_team_access_sandbox_lifecycle_plan import (
    LIFECYCLE_STEP_IDS,
    REQUIRED_ACKNOWLEDGEMENTS,
    REQUIRED_DECISION_TOKEN,
    SCHEMA as PLAN_SCHEMA,
)
import hashlib
import json


def _digest(value):
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _plan():
    mutation_steps = {1, 2, 4, 6, 7, 8}
    steps = []
    for order, step_id in enumerate(LIFECYCLE_STEP_IDS, start=1):
        steps.append({
            "order": order,
            "id": step_id,
            "mutation": order in mutation_steps,
            "requires_manual_apply": True,
            "evidence_required": ["proof"],
        })

    payload = {
        "baseline_evidence_digest": "a" * 64,
        "baseline_acceptance_record_digest": "b" * 64,
        "test_username": "sandbox.operador.demo",
        "tenant_ids": ["tenant-a"],
        "factor_type": "PASSKEY",
        "requested_by": "admin.demo",
        "steps": steps,
    }

    return {
        "schema": PLAN_SCHEMA,
        "version": "1",
        "state": "READY_FOR_ADMIN_TEAM_ACCESS_SANDBOX_LIFECYCLE_EXECUTION_DECISION",
        "gates": {"all": True},
        "blockers": [],
        **payload,
        "plan_digest": _digest(payload),
        "required_decision_token": REQUIRED_DECISION_TOKEN,
        "required_acknowledgements": list(REQUIRED_ACKNOWLEDGEMENTS),
        "decision_recorded": False,
        "account_creation_authorized": False,
        "mfa_enrollment_authorized": False,
        "registry_write_authorized": False,
        "session_revocation_authorized": False,
        "production_authorized": False,
        "deploy_authorized": False,
        "runtime_authorized": False,
        "executes_action": False,
    }


class TeamAccessLifecyclePlanPackageTests(unittest.TestCase):
    def test_policy_is_non_executing(self):
        policy = lifecycle_plan_package_policy()
        self.assertTrue(policy["plan_integrity_recalculated"])
        self.assertTrue(policy["baseline_acceptance_digest_required"])
        self.assertFalse(policy["authorization_record_created"])
        self.assertFalse(policy["step_execution_authorized"])
        self.assertFalse(policy["production_authorized"])
        self.assertFalse(policy["executes_action"])

    def test_valid_plan_package_reaches_authorization_record_boundary(self):
        result = validate_lifecycle_plan_package(_plan())
        self.assertEqual(
            result["state"],
            "READY_FOR_ADMIN_TEAM_ACCESS_LIFECYCLE_AUTHORIZATION_RECORD",
        )
        self.assertTrue(all(result["gates"].values()))
        self.assertTrue(result["package_digest"])
        self.assertFalse(result["authorization_record_created"])
        self.assertFalse(result["lifecycle_execution_authorized"])
        self.assertFalse(result["production_authorized"])

    def test_tampered_plan_digest_blocks(self):
        plan = _plan()
        plan["factor_type"] = "TOTP"
        result = validate_lifecycle_plan_package(plan)
        self.assertEqual(
            result["state"], "TEAM_ACCESS_LIFECYCLE_PLAN_PACKAGE_BLOCKED"
        )
        self.assertIn("plan_digest_integrity", result["blockers"])
        self.assertEqual(result["package_digest"], "")

    def test_step_sequence_drift_blocks(self):
        plan = _plan()
        plan["steps"][0]["id"] = "SKIP_ACCOUNT_CREATION"
        payload = {
            "baseline_evidence_digest": plan["baseline_evidence_digest"],
            "baseline_acceptance_record_digest": plan[
                "baseline_acceptance_record_digest"
            ],
            "test_username": plan["test_username"],
            "tenant_ids": plan["tenant_ids"],
            "factor_type": plan["factor_type"],
            "requested_by": plan["requested_by"],
            "steps": plan["steps"],
        }
        plan["plan_digest"] = _digest(payload)
        result = validate_lifecycle_plan_package(plan)
        self.assertIn("steps_ids_exact", result["blockers"])

    def test_module_has_no_network_process_or_executor_imports(self):
        source = Path(
            "atlasquant_aion_business_team_access_lifecycle_plan_package.py"
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
