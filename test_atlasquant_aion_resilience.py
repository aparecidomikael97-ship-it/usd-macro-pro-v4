from __future__ import annotations
import unittest

from atlasquant_aion_resilience import (
    agent_firewall,
    circuit_breaker,
    default_resilience,
    new_delegation,
    normalize_resilience,
    principal_authority,
    resource_governor,
    safe_mode_posture,
    watchdog,
)


class AtlasQuantAionResilienceTests(unittest.TestCase):
    def test_external_ai_never_has_root_authority(self):
        out=principal_authority("EXTERNAL_AI")
        self.assertFalse(out["root_authority"])
        self.assertFalse(out["may_expand_own_permissions"])

    def test_aion_can_delegate_limited_worker_but_not_sensitive_capabilities(self):
        lease=new_delegation(
            issuer_kind="AION_CORE",
            subject_kind="AGENT",
            subject_ref="review-agent",
            workspace_id="development",
            requested_capabilities=["READ_CONTEXT","TEST_SANDBOX","DEPLOY_PRODUCTION"],
            issuer_capabilities=["READ_CONTEXT","TEST_SANDBOX","DEPLOY_PRODUCTION"],
            scope="Review candidate in sandbox.",
            evidence_refs=["mission:123"],
        )
        self.assertEqual(lease["state"],"BLOCKED")
        self.assertIn("READ_CONTEXT",lease["granted_capabilities"])
        self.assertNotIn("DEPLOY_PRODUCTION",lease["granted_capabilities"])
        self.assertTrue(any("NON_DELEGABLE:DEPLOY_PRODUCTION"==x for x in lease["blockers"]))

    def test_agent_firewall_requires_valid_delegation(self):
        denied=agent_firewall(
            source_kind="AGENT",
            requested_capability="TEST_SANDBOX",
            workspace_id="development",
            delegation=None,
        )
        self.assertEqual(denied["state"],"BLOCK")
        self.assertIn("VALID_DELEGATION_REQUIRED",denied["blockers"])

    def test_external_ai_cannot_directly_control_tools_even_with_delegation_shape(self):
        lease={
            "state":"ACTIVE",
            "workspace_id":"development",
            "granted_capabilities":["READ_CONTEXT"],
        }
        denied=agent_firewall(
            source_kind="EXTERNAL_AI",
            requested_capability="READ_CONTEXT",
            workspace_id="development",
            delegation=lease,
        )
        self.assertEqual(denied["state"],"BLOCK")
        self.assertIn("EXTERNAL_AI_DIRECT_TOOL_CONTROL_BLOCKED",denied["blockers"])

    def test_circuit_breaker_opens_after_failures(self):
        out=circuit_breaker("provider",consecutive_failures=3,error_rate_pct=20)
        self.assertEqual(out["state"],"OPEN")
        self.assertFalse(out["sensitive_calls_allowed"])
        self.assertFalse(out["automatic_restart"])

    def test_watchdog_detects_loop_and_recommends_isolation(self):
        out=watchdog(
            "agent-worker",
            heartbeat_age_seconds=5,
            repeated_action_count=5,
            loop_limit=5,
        )
        self.assertEqual(out["state"],"ISOLATE_RECOMMENDED")
        self.assertIn("LOOP_SUSPECTED",out["signals"])
        self.assertFalse(out["automatic_kill"])

    def test_resource_governor_breaks_at_budget_without_paid_upgrade(self):
        out=resource_governor(
            "research",
            call_limit=10,calls_used=10,
            token_limit=1000,tokens_used=100,
        )
        self.assertEqual(out["state"],"CIRCUIT_BREAK")
        self.assertFalse(out["automatic_paid_upgrade"])
        self.assertFalse(out["automatic_permission_expansion"])

    def test_safe_mode_is_read_only_on_open_circuit(self):
        out=safe_mode_posture(open_circuits=1)
        self.assertEqual(out["mode"],"DEGRADED_READ_ONLY")
        self.assertTrue(out["read_allowed"])
        self.assertFalse(out["sensitive_tools_allowed"])

    def test_secret_exposure_recommends_emergency_stop_without_auto_destruction(self):
        out=safe_mode_posture(secret_exposure=True)
        self.assertEqual(out["mode"],"EMERGENCY_STOP_RECOMMENDED")
        self.assertFalse(out["automatic_destructive_action"])

    def test_normalization_never_restores_non_delegable_capabilities(self):
        state=normalize_resilience({
            "delegations":[{
                "delegation_id":"DEL-X",
                "issuer_kind":"AION_CORE",
                "subject_kind":"AGENT",
                "subject_ref":"x",
                "workspace_id":"development",
                "granted_capabilities":["READ_CONTEXT","REAL_TRADING","WRITE_SECRET"],
                "state":"ACTIVE",
            }]
        })
        caps=state["delegations"][0]["granted_capabilities"]
        self.assertEqual(caps,["READ_CONTEXT"])
        self.assertFalse(state["external_ai_root_authority"])
        self.assertFalse(default_resilience()["real_trading_enabled"])


if __name__=="__main__":
    unittest.main()
