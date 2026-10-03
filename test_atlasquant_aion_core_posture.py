"""Read-only core posture: observability, release, rollback, audit and contracts."""
import unittest

from atlasquant_aion_core_posture import (
    SCHEMA,
    aion_core_observability_snapshot,
    build_rollback_plan,
    executor_safety_posture,
    normalize_audit_trail,
    normalize_security_flag,
    provider_degraded_decision,
    staged_release_plan,
    validate_contract_envelope,
)


class CorePostureTests(unittest.TestCase):
    def test_missing_evidence_is_not_healthy_and_future_runtime_stays_blocked(self):
        snapshot = aion_core_observability_snapshot()
        self.assertEqual(snapshot["schema"], SCHEMA)
        self.assertTrue(all(row["state"] == "NOT_EVIDENCED" for row in snapshot["sections"].values()))
        self.assertFalse(snapshot["healthy_invented"])
        self.assertFalse(snapshot["provider_called"])
        claimed = aion_core_observability_snapshot({"specialist": {"state": "HEALTHY"}})
        self.assertEqual(claimed["sections"]["specialist"]["state"], "UNKNOWN")
        verified = aion_core_observability_snapshot({
            "memory": {"state": "HEALTHY", "evidence_verified": True, "detail": "local digest"},
        })
        self.assertEqual(verified["sections"]["memory"]["state"], "HEALTHY")
        self.assertEqual(verified["sections"]["provider"]["state"], "NOT_EVIDENCED")
        for row in snapshot["specialists"]:
            self.assertFalse(row["runtime_capability_available"])
            self.assertFalse(row["specialist_certified"])
            self.assertEqual(row["certification_state"], "NOT_CERTIFIED")
            self.assertEqual(row["state"], "BLOCKED")

    def test_flags_and_release_stages_do_not_activate(self):
        for value in ("true", "TRUE", "yes", "approved", 1, [], None):
            flag = normalize_security_flag("REAL_TRADING_ENABLED", value)
            self.assertFalse(flag["enabled"])
            self.assertTrue(flag["immutable_off"])
        self.assertFalse(normalize_security_flag("UNKNOWN_FLAG", "true")["enabled"])
        self.assertFalse(normalize_security_flag("SOME_FEATURE", "false")["enabled"])
        self.assertTrue(normalize_security_flag("SOME_FEATURE", True)["enabled"])
        for stage in ("LAB", "SHADOW", "PAPER", "ADMIN", "PUBLIC", "GA"):
            plan = staged_release_plan(stage, {"gate_passed": True, "human_release_approved": "true"})
            self.assertEqual(plan["effective_stage"], "DISABLED")
            self.assertFalse(plan["promoted"])
            self.assertFalse(plan["activates_runtime"])
            self.assertFalse(plan["real_trading_enabled"])

    def test_rollback_audit_provider_and_contracts_fail_closed(self):
        self.assertEqual(build_rollback_plan(None)["state"], "UNKNOWN")
        self.assertFalse(build_rollback_plan({"known_good_version": "1"})["ready"])
        ready = build_rollback_plan({
            "checkpoint_intact": True,
            "known_good_version": "core-1",
            "artifact_ref": "checkpoint:local",
            "checkpoint_ref": "checkpoint:local",
            "reason": "drill",
        })
        self.assertEqual(ready["state"], "READY")
        self.assertFalse(ready["executes_rollback"])
        self.assertTrue(ready["human_approval_required"])
        trail = normalize_audit_trail([{
            "requester": "mikael",
            "tenant": "tenant-a",
            "authorization_result": "DENIED",
            "token": "secret-value",
            "evidence_refs": ["docs/aion/ARCHITECTURE.md"],
        }])
        self.assertFalse(trail["authorizes_action"])
        self.assertFalse(trail["records"][0]["authorizes_action"])
        self.assertNotIn("secret-value", str(trail))
        stale = provider_degraded_decision("stale_response", {"fresh": False, "truth_state": "CONFIRMED"})
        self.assertFalse(stale["cache_used_as_current_fact"])
        self.assertEqual(stale["truth_state"], "UNKNOWN")
        self.assertFalse(stale["provider_called"])
        self.assertFalse(stale["simulated_provider_result"])
        missing = provider_degraded_decision("missing_evidence")
        self.assertEqual(missing["mode"], "UNKNOWN")
        fresh = provider_degraded_decision("provider_unavailable", {"fresh": True, "truth_state": "CONFIRMED"})
        self.assertTrue(fresh["cache_visible"])
        self.assertEqual(fresh["truth_state"], "CONFIRMED")
        rejected = validate_contract_envelope(
            {"schema": "OTHER", "version": "1", "state": "NOPE", "count": "x"},
            schema=SCHEMA,
            supported_versions=(1,),
            enum_fields={"state": ("READY", "BLOCKED")},
            field_types={"count": int},
        )
        self.assertFalse(rejected["accepted"])
        self.assertTrue(any(item.startswith("SCHEMA") or item.startswith("VERSION") for item in rejected["errors"]))
        accepted = validate_contract_envelope(
            {"schema": SCHEMA, "version": 1, "state": "READY", "count": 1},
            schema=SCHEMA,
            supported_versions=(1,),
            enum_fields={"state": ("READY", "BLOCKED")},
            field_types={"count": int},
        )
        self.assertTrue(accepted["accepted"])
        posture = executor_safety_posture()
        self.assertTrue(posture["retry_bounded"])
        self.assertLessEqual(posture["max_attempts"], 5)
        self.assertFalse(posture["global_worker_enabled"])
        self.assertFalse(posture["executes_action"])


if __name__ == "__main__":
    unittest.main()
