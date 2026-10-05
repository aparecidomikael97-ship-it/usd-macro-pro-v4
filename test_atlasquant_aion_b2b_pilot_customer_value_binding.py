import unittest

from atlasquant_aion_b2b_pilot_customer_value_binding import (
    BINDING_SCHEMA,
    PORTAL_ACCESS_SCHEMA,
    SCHEMA,
    VALUE_SCHEMA,
    bind_pilot_value_to_customer_portal,
)


def portal_access(**overrides):
    row = {
        "schema": PORTAL_ACCESS_SCHEMA,
        "state": "ALLOW",
        "allowed": True,
        "customer_id": "customer-001",
        "package": "PROFISSIONAL",
        "viewer_tenant_id": "a" * 32,
        "service_tenant_id": "tenant-service-001",
        "workspace_id": "business",
        "allowed_sections": ["overview", "value"],
        "binding_ref": "portal-binding:customer-001",
        "blockers": [],
        "read_only": True,
        "admin_memory_access": False,
        "other_tenant_access": False,
        "grants_authority": False,
        "automatic_billing": False,
        "automatic_renewal": False,
        "automatic_quota_change": False,
        "automatic_role_change": False,
        "automatic_customer_contact": False,
        "automatic_deploy": False,
        "production_mutation": False,
        "executes_action": False,
    }
    row.update(overrides)
    return row


def pilot_binding(**overrides):
    row = {
        "schema": BINDING_SCHEMA,
        "state": "CONFIRMED",
        "enabled": True,
        "customer_id": "customer-001",
        "pilot_id": "pilot-001",
        "service_tenant_id": "tenant-service-001",
        "workspace_id": "business",
        "binding_ref": "pilot-customer-binding:001",
        "evidence_refs": [
            "pilot:identity",
            "customer:identity",
            "tenant:scope",
        ],
    }
    row.update(overrides)
    return row


def value_model(**overrides):
    row = {
        "schema": VALUE_SCHEMA,
        "view": "CUSTOMER",
        "state": "READY",
        "scope": {
            "tenant_id": "tenant-service-001",
            "workspace_id": "business",
        },
        "pilot_id": "pilot-001",
        "value_state": "STRONG_VALUE",
        "health_score": 90.0,
        "value_trend": "IMPROVING",
        "quick_win_completion_pct": 100.0,
        "quick_win_achieved_pct": 100.0,
        "quick_wins": [
            {
                "quick_win": "Resposta mais rápida",
                "state": "MEASURED",
                "achieved": True,
            },
            {
                "quick_win": "Follow-up consistente",
                "state": "MEASURED",
                "achieved": True,
            },
        ],
        "observed_savings_brl": 3000.0,
        "observed_roi_pct": 100.0,
        "customer_fee_brl": 1500.0,
        "customer_value_to_fee_ratio": 2.0,
        "customer_net_value_brl": 1500.0,
        "customer_payback_covered": True,
        "evidence_digest": "sha256:" + "1" * 64,
        "read_only": True,
        "internal_economics_visible": False,
        "customer_safe": True,
        "provider_delivery_cost_exposed": False,
        "provider_margin_exposed": False,
        "retention_risk_exposed": False,
        "internal_recommendation_exposed": False,
        "renewal_control_exposed": False,
        "expansion_control_exposed": False,
        "billing_control_exposed": False,
        "customer_contact_control_exposed": False,
        "grants_authority": False,
        "executes_action": False,
    }
    row.update(overrides)
    return row


def bind(**overrides):
    args = {
        "portal_access_result": portal_access(),
        "pilot_binding": pilot_binding(),
        "pilot_value_read_model": value_model(),
    }
    args.update(overrides)
    return bind_pilot_value_to_customer_portal(**args)


class PilotCustomerValueBindingTests(unittest.TestCase):
    def test_exact_binding_produces_customer_safe_bundle(self):
        out = bind()
        self.assertEqual(out["schema"], SCHEMA)
        self.assertEqual(out["state"], "READY")
        self.assertTrue(out["allowed"])
        self.assertEqual(out["customer_id"], "customer-001")
        self.assertEqual(out["pilot_id"], "pilot-001")
        self.assertEqual(out["service_tenant_id"], "tenant-service-001")
        self.assertEqual(out["workspace_id"], "business")
        self.assertEqual(out["pilot_value"]["observed_savings_brl"], 3000.0)
        self.assertEqual(out["pilot_value"]["observed_roi_pct"], 100.0)
        self.assertTrue(out["read_only"])
        self.assertTrue(out["customer_safe"])
        self.assertFalse(out["internal_economics_exposed"])
        self.assertFalse(out["retention_risk_exposed"])
        self.assertFalse(out["internal_recommendation_exposed"])
        self.assertFalse(out["grants_authority"])
        self.assertFalse(out["executes_action"])

    def test_customer_mismatch_blocks(self):
        out = bind(
            pilot_binding=pilot_binding(customer_id="customer-002")
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("PILOT_BINDING_CUSTOMER_MISMATCH", out["blockers"])

    def test_pilot_mismatch_blocks(self):
        out = bind(
            pilot_value_read_model=value_model(pilot_id="pilot-002")
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("PILOT_VALUE_PILOT_MISMATCH", out["blockers"])

    def test_tenant_and_workspace_mismatch_block(self):
        out = bind(
            pilot_value_read_model=value_model(
                scope={
                    "tenant_id": "tenant-other",
                    "workspace_id": "other-workspace",
                }
            )
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("PILOT_VALUE_TENANT_MISMATCH", out["blockers"])
        self.assertIn("PILOT_VALUE_WORKSPACE_MISMATCH", out["blockers"])

    def test_admin_projection_is_rejected(self):
        out = bind(
            pilot_value_read_model=value_model(
                view="ADMIN",
                customer_safe=False,
                internal_economics_visible=True,
            )
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("PILOT_VALUE_NOT_CUSTOMER_PROJECTION", out["blockers"])
        self.assertIn("PILOT_VALUE_NOT_CUSTOMER_SAFE", out["blockers"])
        self.assertIn(
            "PILOT_VALUE_INTERNAL_ECONOMICS_UNSAFE",
            out["blockers"],
        )

    def test_internal_margin_field_injected_into_customer_model_blocks(self):
        out = bind(
            pilot_value_read_model=value_model(
                provider_gross_margin_brl=1200.0
            )
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "PILOT_VALUE_FORBIDDEN_FIELD:provider_gross_margin_brl",
            out["blockers"],
        )

    def test_internal_recommendation_or_retention_fields_block(self):
        out = bind(
            pilot_value_read_model=value_model(
                recommendation="EXPANSION_REVIEW_CANDIDATE",
                retention_risk="LOW",
            )
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "PILOT_VALUE_FORBIDDEN_FIELD:recommendation",
            out["blockers"],
        )
        self.assertIn(
            "PILOT_VALUE_FORBIDDEN_FIELD:retention_risk",
            out["blockers"],
        )

    def test_unconfirmed_or_under_evidenced_binding_blocks(self):
        out = bind(
            pilot_binding=pilot_binding(
                state="DRAFT",
                evidence_refs=["one"],
            )
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "PILOT_CUSTOMER_BINDING_NOT_CONFIRMED",
            out["blockers"],
        )
        self.assertIn(
            "PILOT_BINDING_EVIDENCE_INSUFFICIENT",
            out["blockers"],
        )

    def test_portal_access_must_already_be_allowed(self):
        out = bind(
            portal_access_result=portal_access(
                state="BLOCKED",
                allowed=False,
            )
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("PORTAL_ACCESS_NOT_ALLOWED", out["blockers"])

    def test_any_value_control_exposure_blocks(self):
        for key in (
            "provider_delivery_cost_exposed",
            "provider_margin_exposed",
            "retention_risk_exposed",
            "internal_recommendation_exposed",
            "renewal_control_exposed",
            "expansion_control_exposed",
            "billing_control_exposed",
            "customer_contact_control_exposed",
        ):
            with self.subTest(key=key):
                out = bind(
                    pilot_value_read_model=value_model(**{key: True})
                )
                self.assertEqual(out["state"], "BLOCKED")
                self.assertIn(
                    "PILOT_VALUE_UNSAFE_FIELD:" + key,
                    out["blockers"],
                )

    def test_bundle_never_grants_business_authority(self):
        out = bind()
        for key in (
            "grants_authority",
            "automatic_billing",
            "automatic_renewal",
            "automatic_expansion",
            "automatic_customer_contact",
            "automatic_deploy",
            "production_mutation",
            "executes_action",
        ):
            self.assertFalse(out[key], key)

    def test_evidence_digest_is_deterministic(self):
        first = bind()
        second = bind()
        self.assertEqual(first["evidence_digest"], second["evidence_digest"])
        self.assertTrue(first["evidence_digest"].startswith("sha256:"))


if __name__ == "__main__":
    unittest.main()
