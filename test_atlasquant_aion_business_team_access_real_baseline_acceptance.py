import ast
import unittest
from pathlib import Path

from atlasquant_aion_business_team_access_real_baseline_acceptance import (
    SCHEMA,
    REQUIRED_ACKNOWLEDGEMENTS,
    REQUIRED_DECISION_TOKEN,
    baseline_acceptance_requirements,
    baseline_acceptance_template,
    validate_baseline_acceptance_record,
    verify_baseline_acceptance_binding,
)
from atlasquant_aion_business_team_access_windows_operator_handoff import (
    SCHEMA as HANDOFF_SCHEMA,
)


def _handoff():
    return {
        "schema": HANDOFF_SCHEMA,
        "version": "1",
        "state": "READY_FOR_ADMIN_TEAM_ACCESS_REAL_BASELINE_ACCEPTANCE_REVIEW",
        "operator_session_id": "a" * 32,
        "readiness_digest": "b" * 64,
        "baseline_evidence_digest": "c" * 64,
        "reviewed_by": "admin.demo",
        "handoff_digest": "d" * 64,
        "baseline_accepted": False,
        "lifecycle_plan_authorized": False,
        "lifecycle_execution_authorized": False,
        "production_authorized": False,
        "deploy_authorized": False,
        "runtime_authorized": False,
        "executes_action": False,
    }


def _record():
    return {
        "schema": SCHEMA,
        "version": "1",
        "decision": REQUIRED_DECISION_TOKEN,
        "handoff_digest": "d" * 64,
        "baseline_evidence_digest": "c" * 64,
        "operator_session_id": "a" * 32,
        "accepted_by": "admin.demo",
        "accepted_at": "2026-09-30T21:30:00+00:00",
        "sandbox_only": True,
        "production_promotion_requested": False,
        "lifecycle_execution_requested": False,
        "secret_material_included": False,
        "acknowledgements": {
            name: True for name in REQUIRED_ACKNOWLEDGEMENTS
        },
    }


class TeamAccessRealBaselineAcceptanceTests(unittest.TestCase):
    def test_requirements_keep_acceptance_separate_from_execution(self):
        req = baseline_acceptance_requirements()
        self.assertEqual(
            req["state"],
            "REAL_SANDBOX_BASELINE_ACCEPTANCE_RECORD_REQUIRED",
        )
        self.assertFalse(req["generic_language_is_acceptance"])
        self.assertFalse(req["baseline_accepted"])
        self.assertFalse(req["lifecycle_execution_authorized"])
        self.assertFalse(req["production_authorized"])
        self.assertFalse(req["executes_action"])

    def test_template_binds_handoff_baseline_and_session(self):
        template = baseline_acceptance_template(_handoff())
        self.assertEqual(
            template["state"],
            "REAL_SANDBOX_BASELINE_ACCEPTANCE_RECORD_REQUIRED",
        )
        self.assertEqual(template["handoff_digest"], "d" * 64)
        self.assertEqual(template["baseline_evidence_digest"], "c" * 64)
        self.assertEqual(template["operator_session_id"], "a" * 32)
        self.assertEqual(template["expected_accepted_by"], "admin.demo")

    def test_exact_record_accepts_only_for_planning(self):
        result = validate_baseline_acceptance_record(
            _handoff(), _record()
        )
        self.assertEqual(
            result["state"],
            "REAL_SANDBOX_BASELINE_ACCEPTED_FOR_LIFECYCLE_PLANNING",
        )
        self.assertTrue(result["baseline_accepted"])
        self.assertTrue(result["lifecycle_plan_creation_eligible"])
        self.assertTrue(result["acceptance_digest"])
        self.assertFalse(result["lifecycle_execution_authorized"])
        self.assertFalse(result["sandbox_step_execution_authorized"])
        self.assertFalse(result["production_authorized"])
        self.assertFalse(result["executes_action"])

        binding = verify_baseline_acceptance_binding(_handoff(), result)
        self.assertTrue(binding["binding_match"])
        self.assertTrue(binding["lifecycle_plan_creation_eligible"])
        self.assertFalse(binding["lifecycle_execution_authorized"])

    def test_generic_language_or_session_drift_is_rejected(self):
        row = _record()
        row["decision"] = "vamos lá"
        row["operator_session_id"] = "e" * 32
        result = validate_baseline_acceptance_record(
            _handoff(), row
        )
        self.assertEqual(
            result["state"],
            "REAL_SANDBOX_BASELINE_ACCEPTANCE_REJECTED",
        )
        self.assertIn("decision_token", result["blockers"])
        self.assertIn("operator_session_id", result["blockers"])
        self.assertFalse(result["baseline_accepted"])
        self.assertEqual(result["acceptance_digest"], "")

    def test_missing_acknowledgement_rejects(self):
        row = _record()
        row["acknowledgements"]["NO_PRODUCTION_PROMOTION"] = False
        result = validate_baseline_acceptance_record(
            _handoff(), row
        )
        self.assertIn("acknowledgements", result["blockers"])
        self.assertIn(
            "NO_PRODUCTION_PROMOTION",
            result["missing_acknowledgements"],
        )

    def test_module_has_no_network_process_or_executor_imports(self):
        source = Path(
            "atlasquant_aion_business_team_access_real_baseline_acceptance.py"
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
