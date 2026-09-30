import ast
import unittest
from pathlib import Path

from atlasquant_aion_business_post_activation_expansion_boundary import (
    EXPANSION_ACKNOWLEDGEMENTS,
    REQUIRED_EXPANSION_DECISION_TOKEN,
    REQUIRED_POST_ACTIVATION_CHECKS,
    expansion_boundary_packet,
    post_activation_verification_requirements,
    verify_activation_receipt,
)


AUTH_DIGEST = "a" * 64


def _execution_review():
    return {
        "schema": "ATLASQUANT_AION_BUSINESS_RUNTIME_ACTIVATION_EXECUTION_REVIEW_V1",
        "state": "RUNTIME_ACTIVATION_EXECUTION_REVIEW_REQUIRED",
        "authorization_digest": AUTH_DIGEST,
        "target_scope": "pilot",
        "target_tenant_ids": ["tenant-demo-001"],
        "required_post_activation_checks": list(REQUIRED_POST_ACTIVATION_CHECKS),
        "activation_execution_authorized": False,
        "runtime_activated": False,
        "automatic_expansion_allowed": False,
        "client_actions_authorized": False,
        "billing_authorized": False,
        "executes_action": False,
    }


def _verified():
    return verify_activation_receipt(
        _execution_review(),
        activated_scope="pilot",
        activated_tenant_ids=["tenant-demo-001"],
        health_checks={name: "success" for name in REQUIRED_POST_ACTIVATION_CHECKS},
        activation_evidence_ref="activation://receipt-001",
        runtime_enabled_for_authorized_scope=True,
    )


class BusinessPostActivationExpansionBoundaryTests(unittest.TestCase):
    def test_requirements_keep_scope_expansion_blocked(self):
        row = post_activation_verification_requirements()
        self.assertEqual(row["state"], "POST_ACTIVATION_EVIDENCE_REQUIRED")
        self.assertEqual(
            row["required_checks"],
            list(REQUIRED_POST_ACTIVATION_CHECKS),
        )
        self.assertFalse(row["automatic_expansion_allowed"])
        self.assertFalse(row["scope_expansion_authorized"])
        self.assertFalse(row["client_actions_authorized"])
        self.assertFalse(row["billing_authorized"])
        self.assertFalse(row["executes_action"])

    def test_matching_receipt_freezes_verified_scope(self):
        row = _verified()
        self.assertEqual(
            row["state"],
            "RUNTIME_ACTIVATION_VERIFIED_SCOPE_FROZEN",
        )
        self.assertTrue(row["runtime_activation_verified"])
        self.assertTrue(row["scope_frozen"])
        self.assertEqual(row["activated_scope"], "pilot")
        self.assertEqual(row["activated_tenant_ids"], ["tenant-demo-001"])
        self.assertEqual(len(row["activation_verification_digest"]), 64)
        self.assertFalse(row["automatic_expansion_allowed"])
        self.assertFalse(row["scope_expansion_authorized"])
        self.assertFalse(row["executes_action"])

    def test_scope_or_tenant_drift_blocks_receipt(self):
        row = verify_activation_receipt(
            _execution_review(),
            activated_scope="bounded_production",
            activated_tenant_ids=["tenant-demo-001", "tenant-extra"],
            health_checks={name: "success" for name in REQUIRED_POST_ACTIVATION_CHECKS},
            activation_evidence_ref="activation://receipt-001",
            runtime_enabled_for_authorized_scope=True,
        )
        self.assertEqual(row["state"], "POST_ACTIVATION_VERIFICATION_BLOCKED")
        self.assertIn(
            "activated_scope_matches_authorized_scope",
            row["blockers"],
        )
        self.assertIn(
            "activated_tenants_match_authorized_tenants",
            row["blockers"],
        )
        self.assertFalse(row["scope_expansion_authorized"])

    def test_failed_health_or_missing_runtime_confirmation_blocks(self):
        checks = {name: "success" for name in REQUIRED_POST_ACTIVATION_CHECKS}
        checks["tenant_isolation"] = "failure"
        row = verify_activation_receipt(
            _execution_review(),
            activated_scope="pilot",
            activated_tenant_ids=["tenant-demo-001"],
            health_checks=checks,
            activation_evidence_ref="activation://receipt-001",
            runtime_enabled_for_authorized_scope=False,
        )
        self.assertEqual(row["state"], "POST_ACTIVATION_VERIFICATION_BLOCKED")
        self.assertIn("all_post_activation_checks_success", row["blockers"])
        self.assertIn(
            "runtime_enabled_only_for_authorized_scope_confirmed",
            row["blockers"],
        )

    def test_expansion_boundary_requires_explicit_separate_decision(self):
        packet = expansion_boundary_packet(_verified())
        self.assertEqual(
            packet["state"],
            "EXPLICIT_EXPANSION_DECISION_REQUIRED",
        )
        self.assertEqual(
            packet["required_decision_token"],
            REQUIRED_EXPANSION_DECISION_TOKEN,
        )
        self.assertEqual(
            packet["required_acknowledgements"],
            list(EXPANSION_ACKNOWLEDGEMENTS),
        )
        self.assertFalse(packet["generic_confirmation_is_authorization"])
        self.assertFalse(packet["automatic_expansion_allowed"])
        self.assertFalse(packet["scope_expansion_authorized"])
        self.assertFalse(packet["expansion_execution_authorized"])
        self.assertFalse(packet["client_actions_authorized"])
        self.assertFalse(packet["billing_authorized"])
        self.assertFalse(packet["executes_action"])

    def test_forged_unbounded_verification_cannot_open_expansion_boundary(self):
        row = dict(_verified())
        row["activated_scope"] = "pilot"
        row["activated_tenant_ids"] = [f"tenant-{i}" for i in range(11)]
        packet = expansion_boundary_packet(row)
        self.assertEqual(packet["state"], "NOT_READY")
        self.assertEqual(packet["required_decision_token"], "")
        self.assertFalse(packet["scope_expansion_authorized"])
        self.assertFalse(packet["executes_action"])

    def test_unverified_receipt_cannot_open_expansion_boundary(self):
        bad = dict(_verified())
        bad["state"] = "POST_ACTIVATION_VERIFICATION_BLOCKED"
        packet = expansion_boundary_packet(bad)
        self.assertEqual(packet["state"], "NOT_READY")
        self.assertEqual(packet["required_decision_token"], "")
        self.assertFalse(packet["scope_expansion_authorized"])

    def test_admin_exposes_seventeenth_boundary_view(self):
        source = Path("atlasquant_aion_admin.py").read_text(encoding="utf-8")
        self.assertIn(
            "17 · Pós-ativação & fronteira de expansão",
            source,
        )
        self.assertIn(
            "business_post_activation_boundary_requirements",
            source,
        )

    def test_module_has_no_network_git_process_or_runtime_executor(self):
        source = Path(
            "atlasquant_aion_business_post_activation_expansion_boundary.py"
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
