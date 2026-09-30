import ast
import unittest
from pathlib import Path

from atlasquant_aion_business_team_access_sandbox_lifecycle_authorization import (
    SCHEMA,
    authorization_record_requirements,
    authorization_record_template,
    validate_authorization_record,
    verify_authorization_binding,
)
from atlasquant_aion_business_team_access_sandbox_lifecycle_plan import (
    REQUIRED_ACKNOWLEDGEMENTS,
    REQUIRED_DECISION_TOKEN,
    SCHEMA as PLAN_SCHEMA,
)


def _plan():
    return {
        "schema": PLAN_SCHEMA,
        "version": "1",
        "state": "READY_FOR_ADMIN_TEAM_ACCESS_SANDBOX_LIFECYCLE_EXECUTION_DECISION",
        "plan_digest": "a" * 64,
        "baseline_evidence_digest": "b" * 64,
        "requested_by": "admin.demo",
        "test_username": "sandbox.operador.demo",
        "factor_type": "PASSKEY",
        "tenant_ids": ["tenant-a"],
        "decision_recorded": False,
        "executes_action": False,
    }


def _record():
    return {
        "schema": SCHEMA,
        "version": "1",
        "decision": REQUIRED_DECISION_TOKEN,
        "plan_digest": "a" * 64,
        "baseline_evidence_digest": "b" * 64,
        "approved_by": "admin.demo",
        "approved_at": "2026-09-30T20:50:00+00:00",
        "sandbox_only": True,
        "production_targeted": False,
        "secret_material_included": False,
        "executor_enabled": False,
        "acknowledgements": {
            name: True for name in REQUIRED_ACKNOWLEDGEMENTS
        },
    }


class TeamAccessSandboxLifecycleAuthorizationTests(unittest.TestCase):
    def test_requirements_do_not_treat_generic_language_as_authorization(self):
        req = authorization_record_requirements()
        self.assertEqual(req["state"], "HUMAN_AUTHORIZATION_RECORD_REQUIRED")
        self.assertFalse(req["generic_language_is_authorization"])
        self.assertFalse(req["authorization_record_verified"])
        self.assertFalse(req["executor_enabled"])
        self.assertFalse(req["production_authorized"])
        self.assertFalse(req["executes_action"])

    def test_template_binds_exact_plan_and_expected_approver(self):
        template = authorization_record_template(_plan())
        self.assertEqual(template["state"], "HUMAN_AUTHORIZATION_RECORD_REQUIRED")
        self.assertEqual(template["plan_digest"], "a" * 64)
        self.assertEqual(template["baseline_evidence_digest"], "b" * 64)
        self.assertEqual(template["expected_approved_by"], "admin.demo")
        self.assertEqual(template["test_username"], "sandbox.operador.demo")

    def test_exact_record_can_be_verified_without_enabling_executor(self):
        result = validate_authorization_record(_plan(), _record())
        self.assertEqual(
            result["state"],
            "EXPLICIT_SANDBOX_LIFECYCLE_AUTHORIZATION_RECORD_VERIFIED",
        )
        self.assertTrue(result["authorization_record_verified"])
        self.assertTrue(result["sandbox_lifecycle_manual_execution_authorized"])
        self.assertTrue(result["record_digest"])
        self.assertFalse(result["automatic_execution_authorized"])
        self.assertFalse(result["executor_enabled"])
        self.assertFalse(result["production_authorized"])
        self.assertFalse(result["executes_action"])
        binding = verify_authorization_binding(_plan(), result)
        self.assertTrue(binding["binding_match"])

    def test_generic_or_incomplete_record_is_rejected(self):
        row = _record()
        row["decision"] = "vamos lá"
        row["acknowledgements"]["STOP_ON_FIRST_MISMATCH"] = False
        result = validate_authorization_record(_plan(), row)
        self.assertEqual(
            result["state"], "SANDBOX_LIFECYCLE_AUTHORIZATION_REJECTED"
        )
        self.assertIn("decision_token", result["blockers"])
        self.assertIn("acknowledgements", result["blockers"])
        self.assertFalse(result["sandbox_lifecycle_manual_execution_authorized"])
        self.assertEqual(result["record_digest"], "")

    def test_plan_drift_rejects_binding(self):
        verified = validate_authorization_record(_plan(), _record())
        changed = _plan()
        changed["plan_digest"] = "c" * 64
        binding = verify_authorization_binding(changed, verified)
        self.assertFalse(binding["binding_match"])

    def test_module_has_no_network_process_or_provider_imports(self):
        source = Path(
            "atlasquant_aion_business_team_access_sandbox_lifecycle_authorization.py"
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
