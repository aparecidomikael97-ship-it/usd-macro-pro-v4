import unittest

from atlasquant_aion_release_layers import (
    assess_feature_release,
    build_release_matrix,
    required_evidence,
)


class AionReleaseLayersTests(unittest.TestCase):
    def full_evidence(self):
        return {
            "operational_verified": True,
            "health_confirmed": True,
            "release_gate_confirmed": True,
            "cost_reviewed": True,
            "rollback_ready": True,
            "privacy_reviewed": True,
            "tenant_isolation_confirmed": True,
        }

    def test_disabled_layer_needs_no_evidence(self):
        out = assess_feature_release(
            feature="external_llm",
            requested_layer="DISABLED",
            feature_flag_enabled=False,
            evidence={},
        )
        self.assertEqual(out["state"], "ELIGIBLE")
        self.assertEqual(out["required_evidence"], [])
        self.assertFalse(out["eligible_for_manual_application"])
        self.assertFalse(out["executes_action"])

    def test_flag_on_never_proves_operational_readiness(self):
        out = assess_feature_release(
            feature="external_llm",
            requested_layer="INTERNAL",
            feature_flag_enabled=True,
            evidence={},
        )
        self.assertEqual(out["state"], "EVIDENCE_PENDING")
        self.assertIn("operational_verified", out["missing_evidence"])

    def test_internal_layer_needs_three_confirmations(self):
        out = assess_feature_release(
            feature="external_llm",
            requested_layer="INTERNAL",
            feature_flag_enabled=True,
            evidence={
                "operational_verified": True,
                "health_confirmed": True,
                "release_gate_confirmed": True,
            },
        )
        self.assertEqual(out["state"], "ELIGIBLE")
        self.assertTrue(out["eligible_for_manual_application"])

    def test_pilot_requires_human_approval_after_evidence(self):
        evidence = self.full_evidence()
        out = assess_feature_release(
            feature="social_publish",
            requested_layer="PILOT",
            feature_flag_enabled=True,
            evidence=evidence,
            admin_approved=False,
        )
        self.assertEqual(out["state"], "HUMAN_REVIEW_READY")
        self.assertTrue(out["admin_approval_required"])
        self.assertFalse(out["eligible_for_manual_application"])

        approved = assess_feature_release(
            feature="social_publish",
            requested_layer="PILOT",
            feature_flag_enabled=True,
            evidence=evidence,
            admin_approved=True,
        )
        self.assertEqual(approved["state"], "ELIGIBLE")
        self.assertTrue(approved["eligible_for_manual_application"])

    def test_general_requires_tenant_isolation_for_subscriber_facing_feature(self):
        evidence = self.full_evidence()
        evidence["tenant_isolation_confirmed"] = False
        out = assess_feature_release(
            feature="external_llm",
            requested_layer="GENERAL",
            feature_flag_enabled=True,
            evidence=evidence,
            admin_approved=True,
        )
        self.assertEqual(out["state"], "EVIDENCE_PENDING")
        self.assertIn("tenant_isolation_confirmed", out["missing_evidence"])

    def test_production_deploy_general_does_not_require_tenant_isolation(self):
        required = required_evidence("production_deploy", "GENERAL")
        self.assertNotIn("tenant_isolation_confirmed", required)
        out = assess_feature_release(
            feature="production_deploy",
            requested_layer="GENERAL",
            feature_flag_enabled=True,
            evidence=self.full_evidence(),
            admin_approved=True,
        )
        self.assertEqual(out["state"], "ELIGIBLE")
        self.assertFalse(out["automatic_deploy"])

    def test_auto_merge_general_is_forbidden_even_with_full_evidence(self):
        out = assess_feature_release(
            feature="auto_merge",
            requested_layer="GENERAL",
            feature_flag_enabled=True,
            evidence=self.full_evidence(),
            admin_approved=True,
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("GENERAL_LAYER_FORBIDDEN", out["blockers"])
        self.assertFalse(out["eligible_for_manual_application"])

    def test_real_trading_is_always_blocked(self):
        for layer in ("INTERNAL", "PILOT", "GENERAL"):
            with self.subTest(layer=layer):
                out = assess_feature_release(
                    feature="real_broker_execution",
                    requested_layer=layer,
                    feature_flag_enabled=True,
                    evidence=self.full_evidence(),
                    admin_approved=True,
                )
                self.assertEqual(out["state"], "BLOCKED")
                self.assertIn("REAL_TRADING_ALWAYS_BLOCKED", out["blockers"])
                self.assertFalse(out["real_trading_enabled"])

    def test_flag_off_blocks_non_disabled_layer(self):
        out = assess_feature_release(
            feature="social_publish",
            requested_layer="PILOT",
            feature_flag_enabled=False,
            evidence=self.full_evidence(),
            admin_approved=True,
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("FEATURE_FLAG_OFF", out["blockers"])

    def test_unknown_feature_name_does_not_gain_permission(self):
        out = assess_feature_release(
            feature="",
            requested_layer="INTERNAL",
            feature_flag_enabled=True,
            evidence=self.full_evidence(),
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("FEATURE_REQUIRED", out["blockers"])

    def test_invalid_layer_fails_to_disabled(self):
        out = assess_feature_release(
            feature="external_llm",
            requested_layer="anything",
            feature_flag_enabled=True,
            evidence=self.full_evidence(),
            admin_approved=True,
        )
        self.assertEqual(out["requested_layer"], "DISABLED")
        self.assertEqual(out["state"], "ELIGIBLE")
        self.assertFalse(out["eligible_for_manual_application"])

    def test_matrix_blocked_precedence(self):
        matrix = build_release_matrix([
            {
                "feature": "external_llm",
                "requested_layer": "INTERNAL",
                "feature_flag_enabled": True,
                "evidence": self.full_evidence(),
            },
            {
                "feature": "real_broker_execution",
                "requested_layer": "INTERNAL",
                "feature_flag_enabled": True,
                "evidence": self.full_evidence(),
            },
        ])
        self.assertEqual(matrix["state"], "BLOCKED")
        self.assertEqual(matrix["counts"]["BLOCKED"], 1)
        self.assertFalse(matrix["automatic_flag_change"])
        self.assertFalse(matrix["real_trading_enabled"])

    def test_no_automatic_actions_anywhere(self):
        out = assess_feature_release(
            feature="payment_provider",
            requested_layer="PILOT",
            feature_flag_enabled=True,
            evidence=self.full_evidence(),
            admin_approved=True,
        )
        self.assertFalse(out["automatic_flag_change"])
        self.assertFalse(out["automatic_deploy"])
        self.assertFalse(out["automatic_publish"])
        self.assertFalse(out["automatic_charge"])
        self.assertFalse(out["automatic_entitlement_change"])
        self.assertFalse(out["executes_action"])


if __name__ == "__main__":
    unittest.main()
