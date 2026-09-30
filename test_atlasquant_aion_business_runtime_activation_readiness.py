import ast
import unittest
from pathlib import Path

from atlasquant_aion_business_runtime_activation_readiness import (
    ACTIVATION_ACKNOWLEDGEMENTS,
    ALLOWED_ACTIVATION_SCOPES,
    MAX_BOUNDED_TENANTS,
    REQUIRED_POST_ACTIVATION_CHECKS,
    REQUIRED_RUNTIME_DECISION_TOKEN,
    activation_authorization_requirements,
    post_activation_verification_template,
    record_runtime_activation_authorization,
    runtime_activation_execution_review_packet,
    runtime_activation_preflight,
)


DEPLOY_DIGEST = "a" * 64
DEPLOYED_SHA = "b" * 40


def _boundary():
    return {
        "schema": "ATLASQUANT_AION_BUSINESS_RUNTIME_BOUNDARY_PACKET_V1",
        "state": "EXPLICIT_RUNTIME_DECISION_REQUIRED",
        "deployment_verification_digest": DEPLOY_DIGEST,
        "deployed_sha": DEPLOYED_SHA,
        "deployed_environment": "production",
        "required_decision_token": REQUIRED_RUNTIME_DECISION_TOKEN,
        "required_acknowledgements": [],
        "generic_confirmation_is_authorization": False,
        "runtime_activation_authorized": False,
        "runtime_activated": False,
        "pilot_authorized": False,
        "client_actions_authorized": False,
        "executes_action": False,
    }


def _preflight(scope="pilot", tenants=None):
    if tenants is None:
        tenants = ["tenant-demo-001"]
    return runtime_activation_preflight(
        _boundary(),
        target_scope=scope,
        target_tenant_ids=tenants,
        monitoring_plan_ref="docs://monitoring-plan",
        rollback_plan_ref="docs://rollback-plan",
        privacy_ready=True,
        support_ready=True,
        finance_guardrails_ready=True,
        integrations_healthy=True,
    )


class BusinessRuntimeActivationReadinessTests(unittest.TestCase):
    def test_requirements_keep_runtime_off_and_execution_separate(self):
        row = activation_authorization_requirements()
        self.assertEqual(row["state"], "EXPLICIT_RUNTIME_DECISION_REQUIRED")
        self.assertEqual(
            row["required_decision_token"],
            REQUIRED_RUNTIME_DECISION_TOKEN,
        )
        self.assertEqual(
            row["allowed_activation_scopes"],
            list(ALLOWED_ACTIVATION_SCOPES),
        )
        self.assertFalse(row["generic_confirmation_is_authorization"])
        self.assertFalse(row["runtime_activation_authorized"])
        self.assertFalse(row["activation_execution_authorized"])
        self.assertFalse(row["runtime_activated"])
        self.assertFalse(row["automatic_expansion_allowed"])
        self.assertFalse(row["executes_action"])

    def test_good_pilot_preflight_is_bounded_but_not_authorized(self):
        row = _preflight()
        self.assertEqual(
            row["state"],
            "READY_FOR_EXPLICIT_RUNTIME_AUTHORIZATION",
        )
        self.assertEqual(row["target_scope"], "pilot")
        self.assertEqual(row["target_tenant_ids"], ["tenant-demo-001"])
        self.assertEqual(len(row["preflight_digest"]), 64)
        self.assertEqual(row["blockers"], [])
        self.assertFalse(row["runtime_activation_authorized"])
        self.assertFalse(row["activation_execution_authorized"])
        self.assertFalse(row["runtime_activated"])
        self.assertFalse(row["executes_action"])

    def test_sandbox_requires_zero_real_tenant_ids(self):
        good = _preflight(scope="sandbox", tenants=[])
        self.assertEqual(
            good["state"],
            "READY_FOR_EXPLICIT_RUNTIME_AUTHORIZATION",
        )
        bad = _preflight(scope="sandbox", tenants=["real-client"])
        self.assertEqual(
            bad["state"],
            "RUNTIME_ACTIVATION_PREFLIGHT_BLOCKED",
        )
        self.assertIn("tenant_scope_bounded", bad["blockers"])

    def test_pilot_requires_bounded_tenant_list(self):
        empty = _preflight(scope="pilot", tenants=[])
        self.assertEqual(
            empty["state"],
            "RUNTIME_ACTIVATION_PREFLIGHT_BLOCKED",
        )
        self.assertIn("tenant_scope_bounded", empty["blockers"])

        too_many = _preflight(
            scope="pilot",
            tenants=[f"tenant-{i}" for i in range(MAX_BOUNDED_TENANTS + 1)],
        )
        self.assertEqual(
            too_many["state"],
            "RUNTIME_ACTIVATION_PREFLIGHT_BLOCKED",
        )
        self.assertIn("tenant_scope_bounded", too_many["blockers"])

    def test_missing_privacy_support_finance_or_integration_blocks(self):
        row = runtime_activation_preflight(
            _boundary(),
            target_scope="pilot",
            target_tenant_ids=["tenant-demo-001"],
            monitoring_plan_ref="docs://monitoring-plan",
            rollback_plan_ref="docs://rollback-plan",
            privacy_ready=False,
            support_ready=False,
            finance_guardrails_ready=False,
            integrations_healthy=False,
        )
        self.assertEqual(
            row["state"],
            "RUNTIME_ACTIVATION_PREFLIGHT_BLOCKED",
        )
        for blocker in (
            "privacy_ready",
            "support_ready",
            "finance_guardrails_ready",
            "integrations_healthy",
        ):
            self.assertIn(blocker, row["blockers"])

    def test_generic_confirmation_cannot_authorize_runtime(self):
        row = record_runtime_activation_authorization(
            _preflight(),
            decision_token="vamos lá",
            acknowledgements={
                name: True for name in ACTIVATION_ACKNOWLEDGEMENTS
            },
            actor="Mikael",
        )
        self.assertEqual(row["state"], "BLOCKED")
        self.assertFalse(row["authorization_recorded"])
        self.assertFalse(row["runtime_activation_authorized"])
        self.assertFalse(row["activation_execution_authorized"])

    def test_exact_token_records_authorization_but_executes_nothing(self):
        row = record_runtime_activation_authorization(
            _preflight(),
            decision_token=REQUIRED_RUNTIME_DECISION_TOKEN,
            acknowledgements={
                name: True for name in ACTIVATION_ACKNOWLEDGEMENTS
            },
            actor="Mikael",
        )
        self.assertEqual(
            row["state"],
            "RUNTIME_ACTIVATION_AUTHORIZATION_RECORDED",
        )
        self.assertTrue(row["authorization_recorded"])
        self.assertTrue(row["runtime_activation_authorized"])
        self.assertEqual(len(row["authorization_digest"]), 64)
        self.assertFalse(row["activation_execution_authorized"])
        self.assertFalse(row["runtime_activated"])
        self.assertFalse(row["automatic_expansion_allowed"])
        self.assertFalse(row["client_actions_authorized"])
        self.assertFalse(row["billing_authorized"])
        self.assertFalse(row["executes_action"])

    def test_execution_review_packet_is_still_non_executing(self):
        authorization = record_runtime_activation_authorization(
            _preflight(),
            decision_token=REQUIRED_RUNTIME_DECISION_TOKEN,
            acknowledgements={
                name: True for name in ACTIVATION_ACKNOWLEDGEMENTS
            },
            actor="Mikael",
        )
        packet = runtime_activation_execution_review_packet(authorization)
        self.assertEqual(
            packet["state"],
            "RUNTIME_ACTIVATION_EXECUTION_REVIEW_REQUIRED",
        )
        self.assertEqual(
            packet["required_post_activation_checks"],
            list(REQUIRED_POST_ACTIVATION_CHECKS),
        )
        self.assertFalse(packet["activation_execution_authorized"])
        self.assertFalse(packet["runtime_activated"])
        self.assertFalse(packet["automatic_expansion_allowed"])
        self.assertFalse(packet["executes_action"])

    def test_forged_unbounded_authorization_cannot_reach_execution_review(self):
        authorization = record_runtime_activation_authorization(
            _preflight(),
            decision_token=REQUIRED_RUNTIME_DECISION_TOKEN,
            acknowledgements={
                name: True for name in ACTIVATION_ACKNOWLEDGEMENTS
            },
            actor="Mikael",
        )
        authorization["target_scope"] = "pilot"
        authorization["target_tenant_ids"] = [
            f"tenant-{i}" for i in range(MAX_BOUNDED_TENANTS + 1)
        ]
        packet = runtime_activation_execution_review_packet(authorization)
        self.assertEqual(packet["state"], "NOT_READY")
        self.assertFalse(packet["activation_execution_authorized"])
        self.assertFalse(packet["runtime_activated"])
        self.assertFalse(packet["executes_action"])

    def test_post_activation_template_requires_real_evidence(self):
        row = post_activation_verification_template()
        self.assertEqual(row["state"], "POST_ACTIVATION_EVIDENCE_REQUIRED")
        self.assertEqual(
            row["required_checks"],
            list(REQUIRED_POST_ACTIVATION_CHECKS),
        )
        self.assertFalse(row["runtime_health_verified"])
        self.assertFalse(row["automatic_expansion_allowed"])
        self.assertFalse(row["executes_action"])

    def test_admin_exposes_sixteenth_readiness_view(self):
        source = Path("atlasquant_aion_admin.py").read_text(encoding="utf-8")
        self.assertIn(
            "16 · Prontidão para ativação controlada",
            source,
        )
        self.assertIn(
            "business_runtime_activation_requirements",
            source,
        )

    def test_module_has_no_network_git_process_or_runtime_executor(self):
        source = Path(
            "atlasquant_aion_business_runtime_activation_readiness.py"
        ).read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported = []
        for node in tree.body:
            if isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.append(node.module or "")
        for banned in (
            "requests",
            "urllib",
            "httpx",
            "socket",
            "subprocess",
            "github",
            "paramiko",
            "docker",
            "kubernetes",
        ):
            self.assertNotIn(banned, imported)


if __name__ == "__main__":
    unittest.main()
