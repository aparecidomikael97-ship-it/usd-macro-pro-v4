from __future__ import annotations

import unittest

from atlasquant_aion_recovery import recovery_preflight, restore_checkpoint_revision
from atlasquant_aion_resilience import (
    circuit_breaker,
    resource_governor,
    safe_mode_posture,
    watchdog,
)


class AtlasQuantAionChaosRecoveryTests(unittest.TestCase):
    def test_provider_failure_opens_circuit_and_forces_read_only_safe_mode(self):
        breaker = circuit_breaker(
            "external-provider",
            previous_state="CLOSED",
            consecutive_failures=3,
            error_rate_pct=20,
        )
        self.assertEqual(breaker["state"], "OPEN")
        self.assertFalse(breaker["sensitive_calls_allowed"])

        safe = safe_mode_posture(open_circuits=1)
        self.assertEqual(safe["mode"], "DEGRADED_READ_ONLY")
        self.assertTrue(safe["read_allowed"])
        self.assertTrue(safe["diagnostics_allowed"])
        self.assertFalse(safe["sensitive_tools_allowed"])
        self.assertFalse(safe["external_side_effects_allowed"])

    def test_circuit_recovery_requires_two_distinct_probes(self):
        half_open = circuit_breaker(
            "external-provider",
            previous_state="OPEN",
            consecutive_failures=0,
            error_rate_pct=0,
            recovery_probe_passed=True,
        )
        self.assertEqual(half_open["state"], "HALF_OPEN")
        self.assertFalse(half_open["sensitive_calls_allowed"])

        closed = circuit_breaker(
            "external-provider",
            previous_state="HALF_OPEN",
            consecutive_failures=0,
            error_rate_pct=0,
            recovery_probe_passed=True,
        )
        self.assertEqual(closed["state"], "CLOSED")
        self.assertTrue(closed["sensitive_calls_allowed"])

    def test_stale_heartbeat_degrades_without_destructive_automation(self):
        out = watchdog(
            "prime-agent",
            heartbeat_age_seconds=601,
            stale_after_seconds=300,
            repeated_action_count=0,
            unhandled_error_count=0,
        )
        self.assertEqual(out["state"], "DEGRADED")
        self.assertIn("HEARTBEAT_STALE", out["signals"])
        self.assertEqual(out["recommended_action"], "READ_ONLY_DIAGNOSTIC")
        self.assertFalse(out["automatic_kill"])
        self.assertFalse(out["automatic_delete"])

    def test_loop_or_error_storm_recommends_isolation_not_self_destruction(self):
        loop = watchdog(
            "shadow-agent",
            heartbeat_age_seconds=2,
            repeated_action_count=5,
            loop_limit=5,
            unhandled_error_count=3,
            error_limit=3,
        )
        self.assertEqual(loop["state"], "ISOLATE_RECOMMENDED")
        self.assertIn("LOOP_SUSPECTED", loop["signals"])
        self.assertIn("ERROR_LIMIT_REACHED", loop["signals"])
        self.assertFalse(loop["automatic_kill"])
        self.assertFalse(loop["automatic_delete"])

        safe = safe_mode_posture(isolate_recommendations=1)
        self.assertEqual(safe["mode"], "DEGRADED_READ_ONLY")
        self.assertFalse(safe["sensitive_tools_allowed"])

    def test_resource_exhaustion_breaks_before_sensitive_work_continues(self):
        out = resource_governor(
            "sentinel-agent",
            call_limit=100,
            calls_used=25,
            token_limit=1000,
            tokens_used=1001,
            wall_seconds_limit=300,
            wall_seconds_used=30,
            memory_mb_limit=1024,
            memory_mb_used=128,
        )
        self.assertEqual(out["state"], "CIRCUIT_BREAK")
        self.assertFalse(out["allow_new_sensitive_work"])
        self.assertFalse(out["automatic_paid_upgrade"])
        self.assertFalse(out["automatic_permission_expansion"])

    def test_policy_integrity_failure_escalates_to_emergency_stop_recommendation(self):
        out = safe_mode_posture(policy_integrity_ok=False)
        self.assertEqual(out["mode"], "EMERGENCY_STOP_RECOMMENDED")
        self.assertIn("POLICY_INTEGRITY_FAILED", out["reasons"])
        self.assertFalse(out["sensitive_tools_allowed"])
        self.assertFalse(out["automatic_destructive_action"])
        self.assertTrue(out["requires_independent_controller_for_kill_switch"])

    def test_recovery_preflight_fails_closed_without_confirmed_current_runtime(self):
        result = recovery_preflight(
            {"status": "ERROR", "sha": "a" * 40},
            {"status": "CONFIRMED"},
        )
        self.assertFalse(result["allowed"])
        self.assertIn("not confirmed", result["reason"].lower())
        self.assertFalse(result["executes_action"])

    def test_recovery_preflight_rejects_unconfirmed_candidate(self):
        result = recovery_preflight(
            {"status": "CONFIRMED", "sha": "a" * 40},
            {"status": "ERROR", "revision": "b" * 40},
        )
        self.assertFalse(result["allowed"])
        self.assertIn("candidate is not confirmed", result["reason"].lower())
        self.assertFalse(result["executes_action"])

    def test_restore_never_runs_without_explicit_admin_approval(self):
        result = restore_checkpoint_revision({}, {}, None, approved=False)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertFalse(result["saved"])
        self.assertFalse(result["verified"])
        self.assertIn("approval", result["reason"].lower())


if __name__ == "__main__":
    unittest.main()
