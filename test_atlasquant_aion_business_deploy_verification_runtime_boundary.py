import ast
import unittest
from pathlib import Path

from atlasquant_aion_business_deploy_verification_runtime_boundary import (
    DEPLOY_ACKNOWLEDGEMENTS,
    REQUIRED_DEPLOY_DECISION_TOKEN,
    REQUIRED_DEPLOY_HEALTH_CHECKS,
    REQUIRED_RUNTIME_DECISION_TOKEN,
    deploy_authorization_requirements,
    deployment_preflight,
    deployment_verification_template,
    record_deploy_authorization,
    runtime_boundary_packet,
    verify_deployment_receipt,
)


HANDOFF_DIGEST = "a" * 64
FINAL_SHA = "b" * 40
ROLLBACK_SHA = "c" * 40


def _request():
    return {
        "schema": "ATLASQUANT_AION_BUSINESS_DEPLOY_DECISION_REQUEST_V1",
        "state": "EXPLICIT_DEPLOY_DECISION_REQUIRED",
        "handoff_digest": HANDOFF_DIGEST,
        "final_main_sha": FINAL_SHA,
        "target_environment": "production",
        "rollback_reference_sha": ROLLBACK_SHA,
        "required_decision_token": REQUIRED_DEPLOY_DECISION_TOKEN,
        "required_acknowledgements": list(DEPLOY_ACKNOWLEDGEMENTS),
        "generic_confirmation_is_authorization": False,
        "deploy_authorized": False,
        "deploy_executed": False,
        "runtime_activation_authorized": False,
        "runtime_activated": False,
        "executes_action": False,
    }


def _authorization():
    return record_deploy_authorization(
        _request(),
        decision_token=REQUIRED_DEPLOY_DECISION_TOKEN,
        acknowledgements={name: True for name in DEPLOY_ACKNOWLEDGEMENTS},
        actor="Mikael",
    )


def _preflight():
    return deployment_preflight(
        _authorization(),
        deployment_plan_ref="docs://deploy-plan",
        monitoring_plan_ref="docs://monitoring-plan",
        business_runtime_off=True,
        current_main_sha=FINAL_SHA,
    )


class BusinessDeployVerificationRuntimeBoundaryTests(unittest.TestCase):
    def test_requirements_keep_generic_language_non_authorizing(self):
        row = deploy_authorization_requirements()
        self.assertEqual(row["state"], "EXPLICIT_DEPLOY_DECISION_REQUIRED")
        self.assertFalse(row["generic_confirmation_is_authorization"])
        self.assertFalse(row["deploy_authorized"])
        self.assertFalse(row["deploy_executed"])
        self.assertFalse(row["runtime_activation_authorized"])
        self.assertFalse(row["executes_action"])

    def test_generic_confirmation_cannot_record_deploy_authorization(self):
        row = record_deploy_authorization(
            _request(),
            decision_token="vamos lá",
            acknowledgements={name: True for name in DEPLOY_ACKNOWLEDGEMENTS},
            actor="Mikael",
        )
        self.assertEqual(row["state"], "BLOCKED")
        self.assertFalse(row["deploy_authorization_recorded"])
        self.assertFalse(row["deploy_execution_authorized"])

    def test_exact_deploy_only_token_records_authorization_but_executes_nothing(self):
        row = _authorization()
        self.assertEqual(row["state"], "DEPLOY_AUTHORIZATION_RECORDED")
        self.assertTrue(row["deploy_authorization_recorded"])
        self.assertTrue(row["deploy_execution_authorized"])
        self.assertEqual(len(row["authorization_digest"]), 64)
        self.assertFalse(row["deploy_executed"])
        self.assertFalse(row["runtime_activation_authorized"])
        self.assertFalse(row["runtime_activated"])
        self.assertFalse(row["client_actions_authorized"])
        self.assertFalse(row["executes_action"])

    def test_preflight_requires_authorized_sha_runtime_off_and_plans(self):
        row = _preflight()
        self.assertEqual(row["state"], "DEPLOY_EXECUTION_REVIEW_REQUIRED")
        self.assertEqual(len(row["preflight_digest"]), 64)
        self.assertEqual(row["blockers"], [])
        self.assertFalse(row["deploy_execution_authorized"])
        self.assertFalse(row["deploy_executed"])
        self.assertFalse(row["runtime_activation_authorized"])
        bad = deployment_preflight(
            _authorization(),
            deployment_plan_ref="",
            monitoring_plan_ref="",
            business_runtime_off=False,
            current_main_sha="d" * 40,
        )
        self.assertEqual(bad["state"], "DEPLOY_PREFLIGHT_BLOCKED")
        self.assertIn("main_sha_matches_authorized_sha", bad["blockers"])
        self.assertIn("deployment_plan_present", bad["blockers"])
        self.assertIn("monitoring_plan_present", bad["blockers"])
        self.assertIn("business_runtime_off", bad["blockers"])

    def test_verification_template_needs_real_receipt(self):
        row = deployment_verification_template()
        self.assertEqual(row["state"], "DEPLOY_RECEIPT_REQUIRED")
        self.assertEqual(row["required_health_checks"], list(REQUIRED_DEPLOY_HEALTH_CHECKS))
        self.assertFalse(row["deploy_verified"])
        self.assertTrue(row["runtime_decision_required_separately"])
        self.assertFalse(row["runtime_activation_authorized"])

    def test_good_deploy_receipt_still_keeps_runtime_separate(self):
        row = verify_deployment_receipt(
            _preflight(),
            deployed_sha=FINAL_SHA,
            deployed_environment="production",
            health_checks={name: "success" for name in REQUIRED_DEPLOY_HEALTH_CHECKS},
            business_runtime_off_after_deploy=True,
            deploy_evidence_ref="deploy://receipt-001",
        )
        self.assertEqual(row["state"], "DEPLOY_VERIFIED_RUNTIME_DECISION_SEPARATE")
        self.assertTrue(row["deploy_verified"])
        self.assertEqual(len(row["deployment_verification_digest"]), 64)
        self.assertTrue(row["runtime_decision_required_separately"])
        self.assertFalse(row["runtime_activation_authorized"])
        self.assertFalse(row["runtime_activated"])
        self.assertFalse(row["client_actions_authorized"])
        self.assertFalse(row["executes_action"])

    def test_deploy_sha_health_or_runtime_drift_blocks(self):
        checks = {name: "success" for name in REQUIRED_DEPLOY_HEALTH_CHECKS}
        checks["application_health"] = "failure"
        row = verify_deployment_receipt(
            _preflight(),
            deployed_sha="d" * 40,
            deployed_environment="production",
            health_checks=checks,
            business_runtime_off_after_deploy=False,
            deploy_evidence_ref="deploy://receipt-001",
        )
        self.assertEqual(row["state"], "DEPLOY_VERIFICATION_BLOCKED")
        self.assertIn("deployed_sha_matches_authorized_main", row["blockers"])
        self.assertIn("all_deploy_health_checks_success", row["blockers"])
        self.assertIn("business_runtime_off_after_deploy", row["blockers"])

    def test_runtime_boundary_requires_verified_deploy_and_authorizes_nothing(self):
        verification = verify_deployment_receipt(
            _preflight(),
            deployed_sha=FINAL_SHA,
            deployed_environment="production",
            health_checks={name: "success" for name in REQUIRED_DEPLOY_HEALTH_CHECKS},
            business_runtime_off_after_deploy=True,
            deploy_evidence_ref="deploy://receipt-001",
        )
        packet = runtime_boundary_packet(verification)
        self.assertEqual(packet["state"], "EXPLICIT_RUNTIME_DECISION_REQUIRED")
        self.assertEqual(packet["required_decision_token"], REQUIRED_RUNTIME_DECISION_TOKEN)
        self.assertFalse(packet["generic_confirmation_is_authorization"])
        self.assertFalse(packet["runtime_activation_authorized"])
        self.assertFalse(packet["runtime_activated"])
        self.assertFalse(packet["pilot_authorized"])
        self.assertFalse(packet["client_actions_authorized"])
        self.assertFalse(packet["executes_action"])

    def test_module_has_no_network_git_process_or_deploy_executor(self):
        source = Path(
            "atlasquant_aion_business_deploy_verification_runtime_boundary.py"
        ).read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported = []
        for node in tree.body:
            if isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.append(node.module or "")
        for banned in (
            "requests", "urllib", "httpx", "socket", "subprocess", "github",
            "paramiko", "docker", "kubernetes",
        ):
            self.assertNotIn(banned, imported)


if __name__ == "__main__":
    unittest.main()
