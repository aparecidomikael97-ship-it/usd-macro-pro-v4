import ast
import unittest
from pathlib import Path

from atlasquant_aion_business_release_boundary_handoff import (
    DEPLOY_ACKNOWLEDGEMENTS,
    REQUIRED_DEPLOY_DECISION_TOKEN,
    build_release_handoff,
    deploy_decision_request,
    release_handoff_template,
)


ACK_DIGEST = "a" * 64
FINAL_SHA = "b" * 40
ROLLBACK_SHA = "c" * 40


def _ack():
    return {
        "schema": "ATLASQUANT_AION_BUSINESS_FINAL_ADMIN_ACKNOWLEDGEMENT_V1",
        "state": "TECHNICAL_CONSOLIDATION_ACKNOWLEDGED",
        "technical_consolidation_complete": True,
        "acknowledgement_digest": ACK_DIGEST,
        "final_main_sha": FINAL_SHA,
        "deploy_decision_required_separately": True,
        "deploy_authorized": False,
        "runtime_activation_authorized": False,
        "executes_action": False,
    }


class BusinessReleaseBoundaryHandoffTests(unittest.TestCase):
    def test_template_requires_technical_ack_and_authorizes_nothing(self):
        row = release_handoff_template()
        self.assertEqual(row["state"], "TECHNICAL_ACKNOWLEDGEMENT_REQUIRED")
        self.assertEqual(row["required_deploy_decision_token"], REQUIRED_DEPLOY_DECISION_TOKEN)
        self.assertFalse(row["ready_for_deploy_decision_review"])
        self.assertFalse(row["deploy_authorized"])
        self.assertFalse(row["deploy_executed"])
        self.assertFalse(row["runtime_activation_authorized"])
        self.assertFalse(row["executes_action"])

    def test_valid_handoff_only_reaches_separate_deploy_decision(self):
        row = build_release_handoff(
            _ack(),
            target_environment="production",
            deployment_plan_ref="docs://deploy-plan-v1",
            rollback_reference_sha=ROLLBACK_SHA,
            monitoring_plan_ref="docs://monitoring-plan-v1",
            business_runtime_off=True,
            runtime_decision_separate=True,
        )
        self.assertEqual(row["state"], "READY_FOR_SEPARATE_DEPLOY_DECISION")
        self.assertTrue(row["ready_for_deploy_decision_review"])
        self.assertEqual(len(row["handoff_digest"]), 64)
        self.assertEqual(row["blockers"], [])
        self.assertFalse(row["deploy_authorized"])
        self.assertFalse(row["deploy_executed"])
        self.assertFalse(row["runtime_activation_authorized"])
        self.assertFalse(row["runtime_activated"])
        self.assertFalse(row["client_actions_authorized"])
        self.assertFalse(row["executes_action"])

    def test_runtime_must_be_off_and_separate(self):
        row = build_release_handoff(
            _ack(),
            target_environment="production",
            deployment_plan_ref="docs://deploy-plan-v1",
            rollback_reference_sha=ROLLBACK_SHA,
            monitoring_plan_ref="docs://monitoring-plan-v1",
            business_runtime_off=False,
            runtime_decision_separate=False,
        )
        self.assertEqual(row["state"], "HANDOFF_BLOCKED")
        self.assertIn("business_runtime_off_before_deploy", row["blockers"])
        self.assertIn("runtime_decision_separate", row["blockers"])

    def test_missing_rollback_or_monitoring_blocks(self):
        row = build_release_handoff(
            _ack(),
            target_environment="production",
            deployment_plan_ref="docs://deploy-plan-v1",
            rollback_reference_sha="",
            monitoring_plan_ref="",
            business_runtime_off=True,
            runtime_decision_separate=True,
        )
        self.assertEqual(row["state"], "HANDOFF_BLOCKED")
        self.assertIn("rollback_reference_present", row["blockers"])
        self.assertIn("monitoring_plan_reference_present", row["blockers"])

    def test_invalid_technical_ack_blocks(self):
        ack = _ack()
        ack["state"] = "BLOCKED"
        row = build_release_handoff(
            ack,
            target_environment="production",
            deployment_plan_ref="docs://deploy-plan-v1",
            rollback_reference_sha=ROLLBACK_SHA,
            monitoring_plan_ref="docs://monitoring-plan-v1",
            business_runtime_off=True,
            runtime_decision_separate=True,
        )
        self.assertEqual(row["state"], "HANDOFF_BLOCKED")
        self.assertIn("technical_consolidation_acknowledged", row["blockers"])

    def test_deploy_request_requires_handoff_and_still_does_not_authorize(self):
        handoff = build_release_handoff(
            _ack(),
            target_environment="production",
            deployment_plan_ref="docs://deploy-plan-v1",
            rollback_reference_sha=ROLLBACK_SHA,
            monitoring_plan_ref="docs://monitoring-plan-v1",
            business_runtime_off=True,
            runtime_decision_separate=True,
        )
        request = deploy_decision_request(handoff)
        self.assertEqual(request["state"], "EXPLICIT_DEPLOY_DECISION_REQUIRED")
        self.assertEqual(request["required_decision_token"], REQUIRED_DEPLOY_DECISION_TOKEN)
        self.assertEqual(request["required_acknowledgements"], list(DEPLOY_ACKNOWLEDGEMENTS))
        self.assertFalse(request["generic_confirmation_is_authorization"])
        self.assertFalse(request["deploy_authorized"])
        self.assertFalse(request["deploy_executed"])
        self.assertFalse(request["runtime_activation_authorized"])
        self.assertFalse(request["executes_action"])

    def test_incomplete_handoff_cannot_form_deploy_request(self):
        request = deploy_decision_request(release_handoff_template())
        self.assertEqual(request["state"], "NOT_READY")
        self.assertEqual(request["required_decision_token"], "")
        self.assertFalse(request["deploy_authorized"])

    def test_module_has_no_network_git_or_process_executor(self):
        source = Path(
            "atlasquant_aion_business_release_boundary_handoff.py"
        ).read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported = []
        for node in tree.body:
            if isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.append(node.module or "")
        for banned in ("requests", "urllib", "httpx", "socket", "subprocess", "github"):
            self.assertNotIn(banned, imported)


if __name__ == "__main__":
    unittest.main()
