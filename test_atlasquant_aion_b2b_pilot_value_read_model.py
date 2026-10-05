from __future__ import annotations

import unittest

from atlasquant_aion_b2b_pilot_value_read_model import (
    build_pilot_value_admin_read_model,
    build_pilot_value_customer_read_model,
)

SCOPE = {
    "owner_id": "owner-a",
    "tenant_id": "tenant-a",
    "workspace_id": "ws-a",
}


def value_result(**overrides):
    row = {
        "schema": "ATLASQUANT_AION_B2B_PILOT_VALUE_REALIZATION_V1",
        "state": "STRONG_VALUE",
        "recommendation": "EXPANSION_REVIEW_CANDIDATE",
        "pilot_id": "pilot-001",
        "scope": dict(SCOPE),
        "health_score": 90.0,
        "value_trend": "IMPROVING",
        "quick_win_completion_pct": 100.0,
        "quick_win_achieved_pct": 100.0,
        "quick_win_progress": [
            {
                "quick_win": "Normalize lead intake.",
                "state": "MEASURED",
                "achieved": True,
                "realized_value_brl": 800.0,
                "source_ref": "pilot:qwin:1",
            },
            {
                "quick_win": "Bounded follow-up drafts.",
                "state": "MEASURED",
                "achieved": True,
                "realized_value_brl": 700.0,
                "source_ref": "pilot:qwin:2",
            },
        ],
        "value_checkpoints": [],
        "observed_savings_brl": 3000.0,
        "observed_roi_pct": 100.0,
        "customer_fee_brl": 1500.0,
        "customer_value_to_fee_ratio": 2.0,
        "customer_net_value_brl": 1500.0,
        "customer_payback_covered": True,
        "provider_delivery_cost_brl": 1000.0,
        "provider_gross_margin_brl": 1000.0,
        "provider_gross_margin_pct": 50.0,
        "retention_risk": "LOW",
        "retention_risk_score": 0.0,
        "low_value_alert": False,
        "low_value_reasons": [],
        "review_reasons": [
            "VALUE_TREND_IMPROVING",
            "QUICK_WINS_STRONG",
            "PROVIDER_MARGIN_HEALTHY",
        ],
        "review_packet": {
            "review_reasons": [
                "VALUE_TREND_IMPROVING",
                "QUICK_WINS_STRONG",
                "PROVIDER_MARGIN_HEALTHY",
            ]
        },
        "blockers": [],
        "evidence_digest": "sha256:" + "1" * 64,
        "owner_review_required": True,
        "automatic_renewal": False,
        "automatic_expansion": False,
        "automatic_pause": False,
        "automatic_termination": False,
        "automatic_scope_change": False,
        "automatic_contract_change": False,
        "automatic_billing": False,
        "automatic_customer_contact": False,
        "automatic_provisioning": False,
        "automatic_deploy": False,
        "crm_write": False,
        "provider_called": False,
        "production_mutation": False,
        "executes_action": False,
    }
    row.update(overrides)
    return row


class AionB2BPilotValueReadModelTests(unittest.TestCase):
    def test_admin_view_contains_internal_unit_economics_read_only(self):
        out = build_pilot_value_admin_read_model(
            value_result(),
            trusted_scope=SCOPE,
        )
        self.assertEqual(out["state"], "READY")
        self.assertEqual(out["view"], "ADMIN")
        self.assertTrue(out["internal_economics_visible"])
        self.assertEqual(out["provider_delivery_cost_brl"], 1000.0)
        self.assertEqual(out["provider_gross_margin_brl"], 1000.0)
        self.assertEqual(out["provider_gross_margin_pct"], 50.0)
        self.assertEqual(out["retention_risk"], "LOW")
        self.assertEqual(
            out["recommendation"],
            "EXPANSION_REVIEW_CANDIDATE",
        )
        self.assertTrue(out["read_only"])
        self.assertFalse(out["renewal_control_exposed"])
        self.assertFalse(out["expansion_control_exposed"])
        self.assertFalse(out["executes_action"])

    def test_customer_view_exposes_customer_value_only(self):
        out = build_pilot_value_customer_read_model(
            value_result(),
            trusted_scope=SCOPE,
        )
        self.assertEqual(out["state"], "READY")
        self.assertEqual(out["view"], "CUSTOMER")
        self.assertTrue(out["customer_safe"])
        self.assertFalse(out["internal_economics_visible"])
        self.assertEqual(out["observed_savings_brl"], 3000.0)
        self.assertEqual(out["observed_roi_pct"], 100.0)
        self.assertEqual(out["customer_value_to_fee_ratio"], 2.0)
        self.assertEqual(out["customer_net_value_brl"], 1500.0)
        self.assertTrue(out["customer_payback_covered"])
        self.assertEqual(len(out["quick_wins"]), 2)

    def test_customer_view_omits_internal_margin_risk_and_recommendation(self):
        out = build_pilot_value_customer_read_model(
            value_result(),
            trusted_scope=SCOPE,
        )
        forbidden = (
            "provider_delivery_cost_brl",
            "provider_gross_margin_brl",
            "provider_gross_margin_pct",
            "retention_risk",
            "retention_risk_score",
            "recommendation",
            "review_reasons",
            "low_value_reasons",
        )
        for key in forbidden:
            self.assertNotIn(key, out)
        self.assertFalse(out["provider_delivery_cost_exposed"])
        self.assertFalse(out["provider_margin_exposed"])
        self.assertFalse(out["retention_risk_exposed"])
        self.assertFalse(out["internal_recommendation_exposed"])

    def test_customer_scope_omits_owner_identity(self):
        out = build_pilot_value_customer_read_model(
            value_result(),
            trusted_scope=SCOPE,
        )
        self.assertEqual(
            out["scope"],
            {
                "tenant_id": "tenant-a",
                "workspace_id": "ws-a",
            },
        )
        self.assertNotIn("owner_id", out["scope"])

    def test_cross_tenant_value_result_blocks_both_views(self):
        bad = value_result(
            scope={
                "owner_id": "owner-a",
                "tenant_id": "tenant-b",
                "workspace_id": "ws-a",
            }
        )
        admin = build_pilot_value_admin_read_model(
            bad,
            trusted_scope=SCOPE,
        )
        customer = build_pilot_value_customer_read_model(
            bad,
            trusted_scope=SCOPE,
        )
        self.assertEqual(admin["state"], "BLOCKED")
        self.assertEqual(customer["state"], "BLOCKED")
        self.assertIn(
            "VALUE_REALIZATION_SCOPE_MISMATCH",
            admin["blockers"],
        )

    def test_blocked_value_result_is_not_presentable(self):
        bad = value_result(
            state="BLOCKED",
            recommendation="BLOCKED",
            blockers=["COMMERCIAL_EVIDENCE_INSUFFICIENT"],
        )
        out = build_pilot_value_admin_read_model(
            bad,
            trusted_scope=SCOPE,
        )
        self.assertEqual(out["state"], "BLOCKED")

    def test_any_action_authority_flip_blocks_projection(self):
        for key in (
            "automatic_renewal",
            "automatic_expansion",
            "automatic_pause",
            "automatic_termination",
            "automatic_scope_change",
            "automatic_contract_change",
            "automatic_billing",
            "automatic_customer_contact",
            "automatic_provisioning",
            "automatic_deploy",
            "crm_write",
            "provider_called",
            "production_mutation",
            "executes_action",
        ):
            with self.subTest(key=key):
                admin = build_pilot_value_admin_read_model(
                    value_result(**{key: True}),
                    trusted_scope=SCOPE,
                )
                self.assertEqual(admin["state"], "BLOCKED")

    def test_customer_view_has_no_business_controls(self):
        out = build_pilot_value_customer_read_model(
            value_result(),
            trusted_scope=SCOPE,
        )
        for key in (
            "renewal_control_exposed",
            "expansion_control_exposed",
            "billing_control_exposed",
            "customer_contact_control_exposed",
            "grants_authority",
            "executes_action",
        ):
            self.assertFalse(out[key], key)


if __name__ == "__main__":
    unittest.main()
