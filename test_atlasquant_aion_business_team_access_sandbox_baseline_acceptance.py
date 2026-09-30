import ast
import unittest
from pathlib import Path

from atlasquant_aion_business_team_access_sandbox_baseline_acceptance import (
    DECISION_TOKEN,
    REQUIRED_ACKNOWLEDGEMENTS,
    SCHEMA,
    baseline_acceptance_requirements,
    baseline_acceptance_template,
    validate_baseline_acceptance,
    verify_baseline_acceptance_binding,
)
from atlasquant_aion_business_team_access_windows_operator_handoff import (
    SCHEMA as HANDOFF_SCHEMA,
)
from atlasquant_aion_business_team_access_sandbox_evidence import (
    SCHEMA as BASELINE_SCHEMA,
)


SESSION = "a" * 32


def _handoff():
    return {
        "schema": HANDOFF_SCHEMA,
        "state": "READY_FOR_ADMIN_TEAM_ACCESS_REAL_BASELINE_ACCEPTANCE_REVIEW",
        "operator_session_id": SESSION,
        "readiness_digest": "b" * 64,
        "baseline_evidence_digest": "c" * 64,
        "reviewed_by": "admin.demo",
        "handoff_digest": "d" * 64,
        "baseline_accepted": False,
        "lifecycle_plan_authorized": False,
        "lifecycle_execution_authorized": False,
        "production_authorized": False,
        "executes_action": False,
    }


def _record():
    return {
        "schema": SCHEMA,
        "decision": DECISION_TOKEN,
        "handoff_digest": "d" * 64,
        "baseline_evidence_digest": "c" * 64,
        "readiness_digest": "b" * 64,
        "operator_session_id": SESSION,
        "approved_by": "admin.demo",
        "approved_at": "2026-09-30T21:15:00+00:00",
        "sandbox_only": True,
        "production_targeted": False,
        "secret_material_included": False,
        "acknowledgements": {
            name: True for name in REQUIRED_ACKNOWLEDGEMENTS
        },
    }


def _baseline():
    return {
        "schema": BASELINE_SCHEMA,
        "state": "READY_FOR_ADMIN_TEAM_ACCESS_SANDBOX_LIFECYCLE_TEST_REVIEW",
        "evidence_digest": "c" * 64,
        "operator_session_id": SESSION,
        "executes_action": False,
    }


class TeamAccessSandboxBaselineAcceptanceTests(unittest.TestCase):
    def test_requirements_reject_generic_language(self):
        req = baseline_acceptance_requirements()
        self.assertEqual(req["state"], "BASELINE_ACCEPTANCE_INPUT_REQUIRED")
        self.assertFalse(req["generic_language_is_acceptance"])
        self.assertFalse(req["baseline_accepted"])
        self.assertFalse(req["lifecycle_plan_input_authorized"])
        self.assertFalse(req["lifecycle_execution_authorized"])

    def test_template_binds_exact_handoff(self):
        template = baseline_acceptance_template(_handoff())
        self.assertEqual(
            template["state"], "BASELINE_ACCEPTANCE_INPUT_REQUIRED"
        )
        self.assertEqual(template["handoff_digest"], "d" * 64)
        self.assertEqual(template["baseline_evidence_digest"], "c" * 64)
        self.assertEqual(template["operator_session_id"], SESSION)

    def test_explicit_record_accepts_baseline_for_plan_input_only(self):
        result = validate_baseline_acceptance(_handoff(), _record())
        self.assertEqual(
            result["state"], "EXPLICIT_SANDBOX_BASELINE_ACCEPTANCE_VERIFIED"
        )
        self.assertTrue(result["acceptance_record_verified"])
        self.assertTrue(result["baseline_accepted"])
        self.assertTrue(result["lifecycle_plan_input_authorized"])
        self.assertTrue(result["acceptance_record_digest"])
        self.assertFalse(result["lifecycle_execution_authorized"])
        self.assertFalse(result["automatic_plan_creation_authorized"])
        self.assertFalse(result["production_authorized"])
        self.assertFalse(result["executes_action"])

        binding = verify_baseline_acceptance_binding(_baseline(), result)
        self.assertTrue(binding["binding_match"])
        self.assertTrue(binding["lifecycle_plan_input_authorized"])
        self.assertFalse(binding["lifecycle_execution_authorized"])

    def test_generic_token_or_session_drift_rejects(self):
        row = _record()
        row["decision"] = "vamos lá"
        row["operator_session_id"] = "e" * 32
        result = validate_baseline_acceptance(_handoff(), row)
        self.assertEqual(
            result["state"], "SANDBOX_BASELINE_ACCEPTANCE_REJECTED"
        )
        self.assertIn("decision_token", result["blockers"])
        self.assertIn("operator_session_id", result["blockers"])
        self.assertFalse(result["baseline_accepted"])

    def test_baseline_drift_breaks_binding(self):
        result = validate_baseline_acceptance(_handoff(), _record())
        baseline = _baseline()
        baseline["evidence_digest"] = "f" * 64
        binding = verify_baseline_acceptance_binding(baseline, result)
        self.assertFalse(binding["binding_match"])

    def test_module_has_no_network_process_or_executor_imports(self):
        source = Path(
            "atlasquant_aion_business_team_access_sandbox_baseline_acceptance.py"
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
