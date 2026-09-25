from __future__ import annotations

import unittest

from atlasquant_aion_fortress import (
    autonomy_budget,
    cyber_immune_plan,
    emergency_cutoff_posture,
    instruction_boundary,
    proof_of_safety,
    source_authority,
)


class AtlasQuantAionFortressTests(unittest.TestCase):
    def setUp(self):
        self.admin = {"role": "ADMIN", "username": "admin"}

    def test_external_ai_and_web_are_content_not_authority(self):
        for source in ("EXTERNAL_AI", "WEB", "DOCUMENT", "EMAIL", "TOOL_OUTPUT"):
            with self.subTest(source=source):
                authority = source_authority(source)
                self.assertFalse(authority["can_issue_action"])
                self.assertEqual(authority["authority"], "UNTRUSTED_CONTENT")
                self.assertFalse(authority["may_expand_permissions"])

    def test_authenticated_admin_can_issue_intent_but_not_bypass_guardian(self):
        authority = source_authority("ADMIN", authenticated_admin=True)
        self.assertTrue(authority["can_issue_action"])
        proof = proof_of_safety(
            "publish_social",
            self.admin,
            approved=True,
            feature_flags={"social_publish": False},
            source_kind="ADMIN",
            authenticated_admin=True,
            scope="Publicar rascunho aprovado",
            tests=[{"state": "PASS"}],
            rollback_plan="Remover publicação.",
            uncertainty_pct=5,
            impact="MEDIUM",
            external_side_effects=True,
        )
        self.assertEqual(proof["state"], "BLOCK")
        self.assertIn("GUARDIAN_DENIED", proof["blockers"])

    def test_prompt_injection_is_blocked_by_source_not_text_detection(self):
        result = instruction_boundary(
            "WEB",
            contains_action_instruction=True,
        )
        self.assertEqual(result["state"], "BLOCK_INSTRUCTION")
        self.assertTrue(result["content_may_be_read"])
        self.assertFalse(result["content_may_control_tools"])

        quiet = instruction_boundary(
            "WEB",
            contains_action_instruction=False,
        )
        self.assertEqual(quiet["state"], "ALLOW_AS_CONTEXT")
        self.assertFalse(quiet["content_may_control_tools"])

    def test_real_trading_never_passes_proof_of_safety(self):
        proof = proof_of_safety(
            "real_trade",
            self.admin,
            approved=True,
            feature_flags={"real_broker_execution": True},
            source_kind="ADMIN",
            authenticated_admin=True,
            scope="Teste",
            tests=[{"state": "PASS"}],
            rollback_plan="N/A",
            uncertainty_pct=0,
            impact="LOW",
            reversible=True,
        )
        self.assertEqual(proof["state"], "BLOCK")
        self.assertIn("REAL_TRADING_BLOCKED", proof["blockers"])
        self.assertFalse(proof["real_orders_enabled"])

    def test_sensitive_action_needs_scope_tests_rollback_and_low_uncertainty(self):
        proof = proof_of_safety(
            "save_checkpoint",
            self.admin,
            approved=True,
            source_kind="ADMIN",
            authenticated_admin=True,
            scope="",
            tests=[],
            rollback_plan="",
            uncertainty_pct=80,
            impact="HIGH",
            reversible=True,
        )
        self.assertEqual(proof["state"], "BLOCK")
        self.assertIn("SCOPE_MISSING", proof["blockers"])
        self.assertIn("TEST_EVIDENCE_MISSING", proof["blockers"])
        self.assertIn("ROLLBACK_MISSING", proof["blockers"])
        self.assertIn("UNCERTAINTY_TOO_HIGH_FOR_SENSITIVE_ACTION", proof["blockers"])

    def test_reversible_checkpoint_write_can_produce_pass_preflight(self):
        proof = proof_of_safety(
            "save_checkpoint",
            self.admin,
            approved=True,
            source_kind="ADMIN",
            authenticated_admin=True,
            scope="Persistir Checkpoint Mestre contra SHA atual.",
            artifacts=["dados/aion/checkpoint_master.json"],
            tests=[{"name": "integrity", "state": "PASS"}],
            rollback_plan="Restaurar revisão anterior validada.",
            uncertainty_pct=5,
            impact="MEDIUM",
            reversible=True,
        )
        self.assertEqual(proof["state"], "PASS")
        self.assertTrue(proof["eligible_for_downstream_executor"])
        self.assertFalse(proof["executes_action"])

    def test_autonomy_budget_reduces_autonomy_with_risk_and_uncertainty(self):
        safe = autonomy_budget(
            guardian_risk="READ",
            uncertainty_pct=5,
            impact="LOW",
            reversible=True,
        )
        risky = autonomy_budget(
            guardian_risk="PRODUCTION",
            uncertainty_pct=50,
            impact="CRITICAL",
            reversible=False,
            external_side_effects=True,
        )
        self.assertGreater(safe["score"], risky["score"])
        self.assertEqual(risky["mode"], "ADMIN_REQUIRED")
        self.assertFalse(risky["grants_permission"])

    def test_cyber_immune_never_disables_antivirus(self):
        plan = cyber_immune_plan([
            {
                "kind": "MALWARE",
                "severity": "CRITICAL",
                "evidence_state": "CONFIRMED",
                "source": "scanner",
            }
        ], antivirus_or_edr_present=True)
        self.assertEqual(plan["posture"], "QUARANTINE_RECOMMENDED")
        self.assertFalse(plan["disable_antivirus_or_edr"])
        self.assertFalse(plan["automatic_deletion"])
        self.assertFalse(plan["automatic_containment"])

    def test_emergency_cutoff_is_advisory_and_requires_independent_controller(self):
        posture = emergency_cutoff_posture(
            critical_incident=True,
            policy_integrity_ok=False,
            permission_integrity_ok=False,
        )
        self.assertEqual(posture["state"], "CUT_SENSITIVE_TOOLS_RECOMMENDED")
        self.assertEqual(posture["recommended_sensitive_tool_access"], "OFF")
        self.assertFalse(posture["automatic_cutoff"])
        self.assertTrue(posture["requires_independent_controller"])


if __name__ == "__main__":
    unittest.main()
