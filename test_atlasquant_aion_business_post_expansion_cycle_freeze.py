import ast
import unittest
from pathlib import Path

from atlasquant_aion_business_post_expansion_cycle_freeze import (
    BOUNDARY_SCHEMA,
    REQUIRED_EXPANSION_DECISION_TOKEN,
    REQUIRED_POST_EXPANSION_CHECKS,
    post_expansion_verification_requirements,
    renewed_expansion_boundary_packet,
    verify_expansion_receipt,
)


AUTH_DIGEST = "a" * 64


def _execution_review():
    return {
        "schema": "ATLASQUANT_AION_BUSINESS_SCOPE_EXPANSION_EXECUTION_REVIEW_V1",
        "state": "SCOPE_EXPANSION_EXECUTION_REVIEW_REQUIRED",
        "authorization_digest": AUTH_DIGEST,
        "current_scope": "pilot",
        "current_tenant_ids": ["tenant-001"],
        "proposed_scope": "pilot",
        "proposed_tenant_ids": ["tenant-001", "tenant-002"],
        "required_post_expansion_checks": list(REQUIRED_POST_EXPANSION_CHECKS),
        "expansion_execution_authorized": False,
        "automatic_expansion_allowed": False,
        "client_actions_authorized": False,
        "billing_authorized": False,
        "executes_action": False,
    }


def _verified():
    return verify_expansion_receipt(
        _execution_review(),
        observed_scope="pilot",
        observed_tenant_ids=["tenant-001", "tenant-002"],
        health_checks={name: "success" for name in REQUIRED_POST_EXPANSION_CHECKS},
        expansion_evidence_ref="expansion://receipt-001",
        runtime_matches_authorized_expansion=True,
    )


class BusinessPostExpansionCycleFreezeTests(unittest.TestCase):
    def test_requirements_stay_non_executing(self):
        row = post_expansion_verification_requirements()
        self.assertEqual(row["state"], "POST_EXPANSION_EVIDENCE_REQUIRED")
        self.assertEqual(row["required_checks"], list(REQUIRED_POST_EXPANSION_CHECKS))
        self.assertFalse(row["scope_expansion_verified"])
        self.assertFalse(row["scope_frozen"])
        self.assertFalse(row["automatic_expansion_allowed"])
        self.assertFalse(row["executes_action"])

    def test_matching_receipt_verifies_and_freezes_scope(self):
        row = _verified()
        self.assertEqual(row["state"], "SCOPE_EXPANSION_VERIFIED_AND_FROZEN")
        self.assertTrue(row["scope_expansion_verified"])
        self.assertTrue(row["scope_frozen"])
        self.assertEqual(row["previous_tenant_ids"], ["tenant-001"])
        self.assertEqual(
            row["verified_tenant_ids"],
            ["tenant-001", "tenant-002"],
        )
        self.assertEqual(len(row["expansion_verification_digest"]), 64)
        self.assertFalse(row["automatic_expansion_allowed"])
        self.assertFalse(row["scope_expansion_authorized"])
        self.assertFalse(row["executes_action"])

    def test_observed_scope_or_tenant_drift_blocks(self):
        row = verify_expansion_receipt(
            _execution_review(),
            observed_scope="bounded_production",
            observed_tenant_ids=["tenant-001", "tenant-003"],
            health_checks={name: "success" for name in REQUIRED_POST_EXPANSION_CHECKS},
            expansion_evidence_ref="expansion://receipt-001",
            runtime_matches_authorized_expansion=True,
        )
        self.assertEqual(row["state"], "POST_EXPANSION_VERIFICATION_BLOCKED")
        self.assertIn("observed_scope_matches_proposed_scope", row["blockers"])
        self.assertIn("observed_tenants_match_proposed_tenants", row["blockers"])

    def test_forged_scope_skip_execution_review_is_rejected(self):
        packet = dict(_execution_review())
        packet["current_scope"] = "sandbox"
        packet["current_tenant_ids"] = []
        packet["proposed_scope"] = "bounded_production"
        packet["proposed_tenant_ids"] = ["tenant-001"]
        row = verify_expansion_receipt(
            packet,
            observed_scope="bounded_production",
            observed_tenant_ids=["tenant-001"],
            health_checks={name: "success" for name in REQUIRED_POST_EXPANSION_CHECKS},
            expansion_evidence_ref="expansion://forged-skip",
            runtime_matches_authorized_expansion=True,
        )
        self.assertEqual(row["state"], "POST_EXPANSION_VERIFICATION_BLOCKED")
        self.assertIn("proposed_scope_bounded", row["blockers"])
        self.assertFalse(row["scope_expansion_verified"])
        self.assertFalse(row["executes_action"])

    def test_failed_checks_or_runtime_mismatch_blocks(self):
        checks = {name: "success" for name in REQUIRED_POST_EXPANSION_CHECKS}
        checks["capacity_guardrail"] = "failure"
        row = verify_expansion_receipt(
            _execution_review(),
            observed_scope="pilot",
            observed_tenant_ids=["tenant-001", "tenant-002"],
            health_checks=checks,
            expansion_evidence_ref="expansion://receipt-001",
            runtime_matches_authorized_expansion=False,
        )
        self.assertEqual(row["state"], "POST_EXPANSION_VERIFICATION_BLOCKED")
        self.assertIn("all_post_expansion_checks_success", row["blockers"])
        self.assertIn(
            "runtime_matches_authorized_expansion_confirmed",
            row["blockers"],
        )

    def test_verified_scope_reopens_only_explicit_boundary(self):
        packet = renewed_expansion_boundary_packet(_verified())
        self.assertEqual(packet["schema"], BOUNDARY_SCHEMA)
        self.assertEqual(packet["state"], "EXPLICIT_EXPANSION_DECISION_REQUIRED")
        self.assertEqual(packet["current_scope"], "pilot")
        self.assertEqual(
            packet["current_tenant_ids"],
            ["tenant-001", "tenant-002"],
        )
        self.assertEqual(
            packet["required_decision_token"],
            REQUIRED_EXPANSION_DECISION_TOKEN,
        )
        self.assertFalse(packet["generic_confirmation_is_authorization"])
        self.assertFalse(packet["automatic_expansion_allowed"])
        self.assertFalse(packet["scope_expansion_authorized"])
        self.assertFalse(packet["expansion_execution_authorized"])
        self.assertFalse(packet["executes_action"])

    def test_forged_unbounded_verification_cannot_reopen_boundary(self):
        row = dict(_verified())
        row["verified_tenant_ids"] = [f"tenant-{i}" for i in range(11)]
        packet = renewed_expansion_boundary_packet(row)
        self.assertEqual(packet["state"], "NOT_READY")
        self.assertEqual(packet["required_decision_token"], "")
        self.assertFalse(packet["scope_expansion_authorized"])

    def test_unverified_receipt_cannot_reopen_boundary(self):
        row = dict(_verified())
        row["state"] = "POST_EXPANSION_VERIFICATION_BLOCKED"
        packet = renewed_expansion_boundary_packet(row)
        self.assertEqual(packet["state"], "NOT_READY")
        self.assertFalse(packet["scope_expansion_authorized"])

    def test_admin_exposes_nineteenth_view(self):
        source = Path("atlasquant_aion_admin.py").read_text(encoding="utf-8")
        self.assertIn("19 · Pós-expansão & congelamento do ciclo", source)
        self.assertIn("business_post_expansion_verification_requirements", source)

    def test_module_has_no_network_git_process_or_runtime_executor(self):
        source = Path(
            "atlasquant_aion_business_post_expansion_cycle_freeze.py"
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
