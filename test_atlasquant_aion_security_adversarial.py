from __future__ import annotations

import unittest

from atlasquant_aion_fortress import instruction_boundary, proof_of_safety, source_authority
from atlasquant_aion_resilience import (
    agent_firewall,
    new_delegation,
    resource_governor,
    safe_mode_posture,
)


class AtlasQuantAionSecurityAdversarialTests(unittest.TestCase):
    def setUp(self):
        self.admin = {"role": "ADMIN", "username": "admin"}

    def test_untrusted_sources_never_gain_command_authority_from_flags(self):
        for source in ("WEB", "DOCUMENT", "EMAIL", "TOOL_OUTPUT", "EXTERNAL_AI", "UNKNOWN"):
            with self.subTest(source=source):
                authority = source_authority(
                    source,
                    authenticated_admin=True,
                    signed_system_policy=True,
                )
                self.assertFalse(authority["can_issue_action"])
                self.assertFalse(authority["may_override_policy"])
                self.assertFalse(authority["may_expand_permissions"])

    def test_checkpoint_and_internal_memory_are_evidence_not_authorization(self):
        for source in ("CHECKPOINT", "INTERNAL_MEMORY"):
            with self.subTest(source=source):
                authority = source_authority(source)
                self.assertEqual(authority["authority"], "EVIDENCE")
                self.assertFalse(authority["can_issue_action"])

    def test_instruction_in_every_untrusted_channel_is_blocked(self):
        for source in ("WEB", "DOCUMENT", "EMAIL", "TOOL_OUTPUT", "EXTERNAL_AI", "UNKNOWN"):
            with self.subTest(source=source):
                boundary = instruction_boundary(source, contains_action_instruction=True)
                self.assertEqual(boundary["state"], "BLOCK_INSTRUCTION")
                self.assertTrue(boundary["content_may_be_read"])
                self.assertFalse(boundary["content_may_control_tools"])

    def test_external_ai_cannot_turn_approval_into_authority(self):
        proof = proof_of_safety(
            "save_checkpoint",
            self.admin,
            approved=True,
            source_kind="EXTERNAL_AI",
            authenticated_admin=True,
            scope="Attempted delegated write from external model",
            artifacts=["dados/aion/checkpoint_master.json"],
            tests=[{"state": "PASS"}],
            rollback_plan="Restore previous revision",
            uncertainty_pct=0,
            impact="LOW",
            reversible=True,
        )
        self.assertEqual(proof["state"], "BLOCK")
        self.assertIn("SOURCE_HAS_NO_COMMAND_AUTHORITY", proof["blockers"])
        self.assertFalse(proof["eligible_for_downstream_executor"])

    def test_sensitive_capabilities_are_not_delegable_even_by_admin(self):
        sensitive = (
            "REAL_TRADING",
            "WRITE_SECRET",
            "CHARGE_CUSTOMER",
            "MERGE_MAIN",
            "DEPLOY_PRODUCTION",
            "CHANGE_POLICY",
            "EXPAND_PERMISSIONS",
            "DISABLE_SECURITY",
        )
        for capability in sensitive:
            with self.subTest(capability=capability):
                delegation = new_delegation(
                    issuer_kind="ADMIN",
                    subject_kind="AGENT",
                    subject_ref="worker-1",
                    workspace_id="central",
                    requested_capabilities=[capability],
                    issuer_capabilities=[capability],
                    authenticated_admin=True,
                    scope="Adversarial delegation test",
                    evidence_refs=["test-case"],
                )
                self.assertEqual(delegation["state"], "BLOCKED")
                self.assertNotIn(capability, delegation["granted_capabilities"])
                self.assertIn(f"NON_DELEGABLE:{capability}", delegation["blockers"])

    def test_aion_core_cannot_delegate_capability_missing_from_parent(self):
        delegation = new_delegation(
            issuer_kind="AION_CORE",
            subject_kind="AGENT",
            subject_ref="worker-2",
            workspace_id="central",
            requested_capabilities=["WRITE_CHECKPOINT"],
            issuer_capabilities=["READ_CONTEXT"],
            scope="Least privilege test",
            evidence_refs=["test-case"],
        )
        self.assertEqual(delegation["state"], "BLOCKED")
        self.assertIn("CAPABILITY_NOT_IN_PARENT:WRITE_CHECKPOINT", delegation["blockers"])

    def test_agent_delegation_is_bound_to_workspace(self):
        delegation = new_delegation(
            issuer_kind="ADMIN",
            subject_kind="AGENT",
            subject_ref="worker-3",
            workspace_id="business",
            requested_capabilities=["DRAFT"],
            issuer_capabilities=["DRAFT"],
            authenticated_admin=True,
            scope="Draft only inside business",
            evidence_refs=["test-case"],
        )
        self.assertEqual(delegation["state"], "ACTIVE")

        allowed = agent_firewall(
            source_kind="AGENT",
            requested_capability="DRAFT",
            workspace_id="business",
            delegation=delegation,
        )
        denied = agent_firewall(
            source_kind="AGENT",
            requested_capability="DRAFT",
            workspace_id="development",
            delegation=delegation,
        )
        self.assertEqual(allowed["state"], "PASS_TO_GUARDIAN")
        self.assertEqual(denied["state"], "BLOCK")
        self.assertIn("VALID_DELEGATION_REQUIRED", denied["blockers"])

    def test_external_ai_never_controls_tools_directly_even_with_delegation(self):
        delegation = new_delegation(
            issuer_kind="ADMIN",
            subject_kind="EXTERNAL_AI",
            subject_ref="external-model",
            workspace_id="central",
            requested_capabilities=["DRAFT"],
            issuer_capabilities=["DRAFT"],
            authenticated_admin=True,
            scope="Content generation only",
            evidence_refs=["test-case"],
        )
        result = agent_firewall(
            source_kind="EXTERNAL_AI",
            requested_capability="DRAFT",
            workspace_id="central",
            delegation=delegation,
        )
        self.assertEqual(result["state"], "BLOCK")
        self.assertIn("EXTERNAL_AI_DIRECT_TOOL_CONTROL_BLOCKED", result["blockers"])

    def test_resource_governor_throttles_then_breaks_before_unbounded_loop(self):
        throttle = resource_governor(
            "agent",
            call_limit=100,
            calls_used=80,
            token_limit=1000,
            tokens_used=10,
            wall_seconds_limit=100,
            wall_seconds_used=1,
            memory_mb_limit=100,
            memory_mb_used=1,
        )
        broken = resource_governor(
            "agent",
            call_limit=100,
            calls_used=101,
            token_limit=1000,
            tokens_used=10,
            wall_seconds_limit=100,
            wall_seconds_used=1,
            memory_mb_limit=100,
            memory_mb_used=1,
        )
        self.assertEqual(throttle["state"], "THROTTLE")
        self.assertFalse(throttle["allow_new_sensitive_work"])
        self.assertEqual(broken["state"], "CIRCUIT_BREAK")
        self.assertFalse(broken["allow_new_sensitive_work"])

    def test_secret_exposure_forces_emergency_stop_recommendation(self):
        posture = safe_mode_posture(secret_exposure=True)
        self.assertEqual(posture["mode"], "EMERGENCY_STOP_RECOMMENDED")
        self.assertFalse(posture["sensitive_tools_allowed"])
        self.assertFalse(posture["external_side_effects_allowed"])
        self.assertTrue(posture["requires_independent_controller_for_kill_switch"])


if __name__ == "__main__":
    unittest.main()
