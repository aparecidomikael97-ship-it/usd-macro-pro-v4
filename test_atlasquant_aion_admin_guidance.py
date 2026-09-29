from datetime import datetime, timezone
import unittest

from atlasquant_aion_admin_guidance import (
    admin_subject_ref,
    build_admin_copilot_snapshot,
    build_admin_onboarding_payload,
    build_admin_onboarding_snapshot,
    complete_admin_onboarding_step,
)


NOW = datetime(2026, 9, 29, 1, 0, tzinfo=timezone.utc)
STARTED = "2026-09-29T01:00:00+00:00"


class AionAdminGuidanceTests(unittest.TestCase):
    def access(self):
        return {
            "role": "ADMIN",
            "session": {
                "role": "ADMIN",
                "username": "admin.one",
                "credential_fingerprint": "abc123fingerprint",
            },
        }

    def test_subject_ref_is_opaque_and_stable(self):
        first = admin_subject_ref(self.access())
        second = admin_subject_ref(self.access())
        self.assertEqual(first, second)
        self.assertTrue(first.startswith("admin-"))
        self.assertNotIn("admin.one", first)
        self.assertNotIn("abc123fingerprint", first)

    def test_missing_session_identity_fails_closed(self):
        self.assertEqual(admin_subject_ref({"role": "ADMIN"}), "")
        snapshot = build_admin_onboarding_snapshot(
            {"role": "ADMIN"},
            experience_mode="ADVANCED",
            started_at=STARTED,
            now=NOW,
        )
        self.assertEqual(snapshot["state"], "BLOCKED")
        self.assertEqual(snapshot["rejection"]["code"], "SUBJECT_REF_INVALID")

    def test_payload_only_copies_exact_boolean_flags(self):
        payload = build_admin_onboarding_payload(
            self.access(),
            experience_mode="ADVANCED",
            started_at=STARTED,
            feature_flags={
                "external_llm": False,
                "real_broker_execution": True,
                "bad_string": "false",
                "bad_int": 1,
            },
            system_context={"operational_integration_confirmed": "true"},
        )
        self.assertEqual(
            payload["feature_flags"],
            {
                "external_llm": False,
                "real_broker_execution": True,
            },
        )
        self.assertNotIn("operational_integration_confirmed", payload)

    def test_operational_confirmation_requires_exact_bool(self):
        payload = build_admin_onboarding_payload(
            self.access(),
            experience_mode="ADVANCED",
            started_at=STARTED,
            system_context={"operational_integration_confirmed": True},
        )
        self.assertIs(payload["operational_integration_confirmed"], True)

    def test_onboarding_remains_read_only_and_real_trading_blocked(self):
        snapshot = build_admin_onboarding_snapshot(
            self.access(),
            experience_mode="ADVANCED",
            started_at=STARTED,
            feature_flags={"real_broker_execution": True},
            now=NOW,
        )
        self.assertFalse(snapshot["real_trading_enabled"])
        self.assertFalse(snapshot["executes_action"])
        self.assertFalse(snapshot["feature_flag_changed"])
        self.assertFalse(snapshot["runtime_written"])

    def test_explicit_session_step_can_advance_without_runtime_side_effects(self):
        report = complete_admin_onboarding_step(
            self.access(),
            None,
            "role_confirmed",
            experience_mode="ADVANCED",
            started_at=STARTED,
            feature_flags={"real_broker_execution": False},
            now=NOW,
        )
        self.assertIn("role_confirmed", report["completed_step_ids"])
        self.assertFalse(report["executes_action"])
        self.assertFalse(report["runtime_written"])
        self.assertFalse(report["real_trading_enabled"])

    def test_copilot_reuses_status_health_and_cost_evidence(self):
        copilot = build_admin_copilot_snapshot(
            status_board={
                "attention": [],
                "system_health_center": {
                    "items": [{
                        "id": "runtime",
                        "label": "Runtime",
                        "state": "BLOCKED",
                        "detail": "bloqueado",
                    }]
                },
                "cost_center": {
                    "state": "PARTIAL",
                    "confirmed_monthly_usd": 10,
                    "estimated_monthly_usd": 4,
                },
            },
            reliability_snapshot={"posture": "UNKNOWN"},
        )
        self.assertEqual(copilot["state"], "ATTENTION")
        self.assertTrue(any(row["id"].startswith("health:") for row in copilot["items"]))
        self.assertTrue(any(row["id"] == "cost:evidence" for row in copilot["items"]))
        self.assertFalse(copilot["executes_action"])
        self.assertFalse(copilot["real_trading_enabled"])

    def test_copilot_never_promotes_setup(self):
        copilot = build_admin_copilot_snapshot(
            status_board={},
            reliability_snapshot={"posture": "CONTROLLED"},
        )
        self.assertFalse(copilot["promotes_setup"])
        self.assertFalse(copilot["automatic_setup_promotion"])
        self.assertFalse(copilot["automatic_feature_change"])


if __name__ == "__main__":
    unittest.main()
