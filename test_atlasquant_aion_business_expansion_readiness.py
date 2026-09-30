import ast
import unittest
from pathlib import Path

from atlasquant_aion_business_expansion_readiness import (
    EXPANSION_ACKNOWLEDGEMENTS,
    MAX_BOUNDED_TENANTS,
    REQUIRED_EXPANSION_DECISION_TOKEN,
    REQUIRED_POST_EXPANSION_CHECKS,
    expansion_authorization_requirements,
    expansion_execution_review_packet,
    expansion_preflight,
    record_expansion_authorization,
)


VERIFY_DIGEST = "a" * 64


def _boundary(scope="pilot", tenants=None):
    if tenants is None:
        tenants = ["tenant-001"]
    return {
        "schema": "ATLASQUANT_AION_BUSINESS_SCOPE_EXPANSION_BOUNDARY_PACKET_V1",
        "state": "EXPLICIT_EXPANSION_DECISION_REQUIRED",
        "activation_verification_digest": VERIFY_DIGEST,
        "current_scope": scope,
        "current_tenant_ids": tenants,
        "required_decision_token": REQUIRED_EXPANSION_DECISION_TOKEN,
        "required_acknowledgements": [],
        "generic_confirmation_is_authorization": False,
        "automatic_expansion_allowed": False,
        "scope_expansion_authorized": False,
        "expansion_execution_authorized": False,
        "client_actions_authorized": False,
        "billing_authorized": False,
        "executes_action": False,
    }


def _preflight(
    boundary=None,
    proposed_scope="pilot",
    proposed_tenants=None,
):
    if boundary is None:
        boundary = _boundary()
    if proposed_tenants is None:
        proposed_tenants = ["tenant-001", "tenant-002"]
    return expansion_preflight(
        boundary,
        proposed_scope=proposed_scope,
        proposed_tenant_ids=proposed_tenants,
        monitoring_plan_ref="docs://monitoring",
        rollback_plan_ref="docs://rollback",
        privacy_ready=True,
        support_ready=True,
        finance_guardrails_ready=True,
        integrations_healthy=True,
        capacity_ready=True,
    )


class BusinessExpansionReadinessTests(unittest.TestCase):
    def test_requirements_never_authorize_automatic_expansion(self):
        row = expansion_authorization_requirements()
        self.assertEqual(row["state"], "EXPLICIT_EXPANSION_DECISION_REQUIRED")
        self.assertEqual(
            row["required_decision_token"],
            REQUIRED_EXPANSION_DECISION_TOKEN,
        )
        self.assertFalse(row["generic_confirmation_is_authorization"])
        self.assertFalse(row["scope_expansion_authorized"])
        self.assertFalse(row["expansion_execution_authorized"])
        self.assertFalse(row["automatic_expansion_allowed"])
        self.assertFalse(row["executes_action"])

    def test_same_stage_tenant_expansion_can_reach_explicit_decision(self):
        row = _preflight()
        self.assertEqual(
            row["state"],
            "READY_FOR_EXPLICIT_EXPANSION_AUTHORIZATION",
        )
        self.assertEqual(row["current_scope"], "pilot")
        self.assertEqual(row["proposed_scope"], "pilot")
        self.assertEqual(row["proposed_tenant_ids"], ["tenant-001", "tenant-002"])
        self.assertEqual(row["blockers"], [])
        self.assertFalse(row["scope_expansion_authorized"])

    def test_pilot_can_promote_one_stage_to_bounded_production(self):
        row = _preflight(
            proposed_scope="bounded_production",
            proposed_tenants=["tenant-001"],
        )
        self.assertEqual(
            row["state"],
            "READY_FOR_EXPLICIT_EXPANSION_AUTHORIZATION",
        )

    def test_sandbox_cannot_skip_directly_to_bounded_production(self):
        row = _preflight(
            boundary=_boundary(scope="sandbox", tenants=[]),
            proposed_scope="bounded_production",
            proposed_tenants=["tenant-001"],
        )
        self.assertEqual(row["state"], "EXPANSION_PREFLIGHT_BLOCKED")
        self.assertIn("no_scope_skip_or_downgrade", row["blockers"])
        self.assertIn("sandbox_may_only_promote_to_pilot", row["blockers"])

    def test_existing_tenant_removal_blocks(self):
        row = _preflight(
            boundary=_boundary(
                scope="pilot",
                tenants=["tenant-001", "tenant-002"],
            ),
            proposed_scope="bounded_production",
            proposed_tenants=["tenant-001"],
        )
        self.assertEqual(row["state"], "EXPANSION_PREFLIGHT_BLOCKED")
        self.assertIn("existing_tenants_preserved", row["blockers"])

    def test_more_than_max_tenants_blocks(self):
        row = _preflight(
            proposed_tenants=[
                f"tenant-{i}" for i in range(MAX_BOUNDED_TENANTS + 1)
            ],
        )
        self.assertEqual(row["state"], "EXPANSION_PREFLIGHT_BLOCKED")
        self.assertIn("proposed_scope_bounded", row["blockers"])

    def test_missing_guardrails_block(self):
        row = expansion_preflight(
            _boundary(),
            proposed_scope="pilot",
            proposed_tenant_ids=["tenant-001", "tenant-002"],
            monitoring_plan_ref="",
            rollback_plan_ref="",
            privacy_ready=False,
            support_ready=False,
            finance_guardrails_ready=False,
            integrations_healthy=False,
            capacity_ready=False,
        )
        self.assertEqual(row["state"], "EXPANSION_PREFLIGHT_BLOCKED")
        for blocker in (
            "monitoring_plan_present",
            "rollback_plan_present",
            "privacy_ready",
            "support_ready",
            "finance_guardrails_ready",
            "integrations_healthy",
            "capacity_ready",
        ):
            self.assertIn(blocker, row["blockers"])

    def test_generic_confirmation_does_not_authorize_expansion(self):
        row = record_expansion_authorization(
            _preflight(),
            decision_token="vamos lá",
            acknowledgements={
                name: True for name in EXPANSION_ACKNOWLEDGEMENTS
            },
            actor="Mikael",
        )
        self.assertEqual(row["state"], "BLOCKED")
        self.assertFalse(row["authorization_recorded"])
        self.assertFalse(row["scope_expansion_authorized"])

    def test_exact_token_records_authorization_but_not_execution(self):
        row = record_expansion_authorization(
            _preflight(),
            decision_token=REQUIRED_EXPANSION_DECISION_TOKEN,
            acknowledgements={
                name: True for name in EXPANSION_ACKNOWLEDGEMENTS
            },
            actor="Mikael",
        )
        self.assertEqual(
            row["state"],
            "SCOPE_EXPANSION_AUTHORIZATION_RECORDED",
        )
        self.assertTrue(row["authorization_recorded"])
        self.assertTrue(row["scope_expansion_authorized"])
        self.assertFalse(row["expansion_execution_authorized"])
        self.assertFalse(row["automatic_expansion_allowed"])
        self.assertFalse(row["executes_action"])

    def test_execution_review_stays_non_executing(self):
        authorization = record_expansion_authorization(
            _preflight(),
            decision_token=REQUIRED_EXPANSION_DECISION_TOKEN,
            acknowledgements={
                name: True for name in EXPANSION_ACKNOWLEDGEMENTS
            },
            actor="Mikael",
        )
        packet = expansion_execution_review_packet(authorization)
        self.assertEqual(
            packet["state"],
            "SCOPE_EXPANSION_EXECUTION_REVIEW_REQUIRED",
        )
        self.assertEqual(
            packet["required_post_expansion_checks"],
            list(REQUIRED_POST_EXPANSION_CHECKS),
        )
        self.assertFalse(packet["expansion_execution_authorized"])
        self.assertFalse(packet["automatic_expansion_allowed"])
        self.assertFalse(packet["billing_authorized"])
        self.assertFalse(packet["executes_action"])

    def test_admin_exposes_eighteenth_view(self):
        source = Path("atlasquant_aion_admin.py").read_text(encoding="utf-8")
        self.assertIn("18 · Prontidão para expansão controlada", source)
        self.assertIn("business_expansion_authorization_requirements", source)

    def test_module_has_no_network_git_process_or_expansion_executor(self):
        source = Path(
            "atlasquant_aion_business_expansion_readiness.py"
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
