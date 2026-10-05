import unittest

from atlasquant_aion_tenant import tenant_namespace
from atlasquant_aion_b2b_customer_portal import (
    PORTAL_SCOPE,
    customer_portal_access,
    customer_portal_html,
    customer_portal_view_model,
)
from atlasquant_aion_b2b_pilot_customer_value_binding import (
    BINDING_SCHEMA,
    VALUE_SCHEMA,
    bind_pilot_value_to_customer_portal,
)


def access():
    return {
        "allowed": True,
        "mode": "AUTHENTICATED",
        "role": "USER",
        "session": {
            "username": "cliente.01",
            "role": "USER",
            "credential_fingerprint": "a" * 24,
        },
    }


def portal_binding(current_access=None, sections=None):
    current_access = current_access or access()
    return {
        "state": "CONFIRMED",
        "enabled": True,
        "portal_scope": PORTAL_SCOPE,
        "subject_tenant_id": tenant_namespace(current_access)["tenant_id"],
        "service_tenant_id": "service-tenant-001",
        "workspace_id": "service-workspace-001",
        "customer_id": "customer-001",
        "package": "PROFISSIONAL",
        "binding_ref": "customer-binding:001",
        "allowed_sections": sections or ["overview", "value", "usage", "support"],
    }


def service_read_model():
    return {
        "schema": "ATLASQUANT_AION_B2B_PORTAL_READ_MODEL_V1",
        "state": "READY",
        "scope": {
            "owner_id": "owner-a",
            "tenant_id": "service-tenant-001",
            "workspace_id": "service-workspace-001",
        },
        "customer_id": "customer-001",
        "package": "PROFISSIONAL",
        "service_state": "HEALTHY",
        "service_decision": "RENEWAL_REVIEW_CANDIDATE",
        "health_label": "SAUDÁVEL",
        "health_score": 88.0,
        "observed_roi_pct": 60.0,
        "actual_service_cost_brl": 2200.0,
        "usage": {
            "capacity": {"used": 40, "limit": 60, "utilization_pct": 66.67},
            "calls": {"used": 700, "limit": 1000, "utilization_pct": 70.0},
            "tokens": {"used": 700000, "limit": 1000000, "utilization_pct": 70.0},
            "support_tickets": {"used": 20, "limit": 40, "utilization_pct": 50.0},
        },
        "support": {
            "avg_first_response_hours": 2.0,
            "avg_resolution_hours": 12.0,
            "critical_open_tickets": 0,
            "first_response_sla_met": True,
            "resolution_sla_met": True,
        },
        "review_reasons": [],
        "incident_reasons": [],
        "generated_at": "2026-10-05T16:30:00-04:00",
        "evidence_digest": "sha256:service-read-model",
        "read_only": True,
        "grants_authority": False,
        "executes_action": False,
    }


def pilot_binding():
    return {
        "schema": BINDING_SCHEMA,
        "state": "CONFIRMED",
        "enabled": True,
        "customer_id": "customer-001",
        "pilot_id": "pilot-001",
        "service_tenant_id": "service-tenant-001",
        "workspace_id": "service-workspace-001",
        "binding_ref": "pilot-customer-binding:001",
        "evidence_refs": [
            "pilot:identity",
            "customer:identity",
            "tenant:scope",
        ],
    }


def pilot_value_model(**overrides):
    row = {
        "schema": VALUE_SCHEMA,
        "view": "CUSTOMER",
        "state": "READY",
        "scope": {
            "tenant_id": "service-tenant-001",
            "workspace_id": "service-workspace-001",
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
            }
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


def bound_value(current=None):
    current = current or access()
    p_binding = portal_binding(current)
    p_access = customer_portal_access(
        current,
        p_binding,
        service_read_model(),
    )
    return bind_pilot_value_to_customer_portal(
        portal_access_result=p_access,
        pilot_binding=pilot_binding(),
        pilot_value_read_model=pilot_value_model(),
    )


class CustomerPortalPilotValueTests(unittest.TestCase):
    def test_exact_bound_pilot_value_reaches_customer_portal(self):
        current = access()
        p_binding = portal_binding(current)
        view = customer_portal_view_model(
            current,
            p_binding,
            service_read_model(),
            None,
            None,
            bound_value(current),
        )
        self.assertEqual(view["state"], "READY")
        self.assertEqual(view["pilot_value"]["pilot_id"], "pilot-001")
        self.assertEqual(
            view["pilot_value"]["observed_savings_brl"],
            3000.0,
        )
        self.assertEqual(
            view["pilot_value"]["observed_roi_pct"],
            100.0,
        )
        self.assertFalse(view["pilot_value_internal_economics_exposed"])
        self.assertFalse(view["pilot_value_retention_risk_exposed"])
        self.assertFalse(view["pilot_value_internal_recommendation_exposed"])

    def test_bound_pilot_value_renders_customer_safe_cards(self):
        current = access()
        view = customer_portal_view_model(
            current,
            portal_binding(current),
            service_read_model(),
            None,
            None,
            bound_value(current),
        )
        html = customer_portal_html(view)
        for expected in (
            "VALOR DO PILOTO",
            "STRONG_VALUE",
            "IMPROVING",
            "ROI DO PILOTO",
            "100%",
            "ECONOMIA OBSERVADA",
            "R$ 3000",
            "QUICK WINS",
            "PAYBACK",
            "COBERTO",
        ):
            self.assertIn(expected, html)

    def test_internal_margin_risk_and_recommendation_never_render(self):
        current = access()
        view = customer_portal_view_model(
            current,
            portal_binding(current),
            service_read_model(),
            None,
            None,
            bound_value(current),
        )
        html = customer_portal_html(view)
        for forbidden in (
            "provider_gross_margin",
            "provider_delivery_cost",
            "retention_risk",
            "EXPANSION_REVIEW_CANDIDATE",
            "MARGEM",
            "RISCO DE RETENÇÃO",
        ):
            self.assertNotIn(forbidden, html)

    def test_missing_value_section_hides_bound_pilot_value(self):
        current = access()
        view = customer_portal_view_model(
            current,
            portal_binding(current, sections=["overview", "support"]),
            service_read_model(),
            None,
            None,
            bound_value(current),
        )
        self.assertEqual(view["state"], "READY")
        html = customer_portal_html(view)
        self.assertNotIn("VALOR DO PILOTO", html)
        self.assertNotIn("ROI DO PILOTO", html)
        self.assertNotIn("ECONOMIA OBSERVADA", html)

    def test_cross_customer_bundle_blocks_entire_portal_view(self):
        current = access()
        bad = dict(bound_value(current))
        bad["customer_id"] = "customer-other"
        view = customer_portal_view_model(
            current,
            portal_binding(current),
            service_read_model(),
            None,
            None,
            bad,
        )
        self.assertEqual(view["state"], "BLOCKED")
        self.assertIn(
            "PILOT_VALUE_BINDING_CUSTOMER_MISMATCH",
            view["blockers"],
        )

    def test_forbidden_internal_field_in_bundle_blocks_portal(self):
        current = access()
        bad = dict(bound_value(current))
        bad["pilot_value"] = dict(bad["pilot_value"])
        bad["pilot_value"]["provider_gross_margin_brl"] = 1200.0
        view = customer_portal_view_model(
            current,
            portal_binding(current),
            service_read_model(),
            None,
            None,
            bad,
        )
        self.assertEqual(view["state"], "BLOCKED")
        self.assertIn(
            "PILOT_VALUE_BINDING_FORBIDDEN_FIELD:provider_gross_margin_brl",
            view["blockers"],
        )

    def test_portal_without_pilot_value_remains_backward_compatible(self):
        current = access()
        view = customer_portal_view_model(
            current,
            portal_binding(current),
            service_read_model(),
        )
        self.assertEqual(view["state"], "READY")
        self.assertEqual(view["pilot_value"], {})
        html = customer_portal_html(view)
        self.assertIn("ROI OBSERVADO", html)
        self.assertNotIn("ROI DO PILOTO", html)

    def test_pilot_value_adds_no_action_controls(self):
        current = access()
        view = customer_portal_view_model(
            current,
            portal_binding(current),
            service_read_model(),
            None,
            None,
            bound_value(current),
        )
        html = customer_portal_html(view)
        for forbidden in (
            "Renovar agora",
            "Expandir agora",
            "Cobrar agora",
            "Contratar agora",
            "Ativar piloto",
            "Contatar agora",
        ):
            self.assertNotIn(forbidden, html)
        for key in (
            "grants_authority",
            "automatic_billing",
            "automatic_renewal",
            "automatic_quota_change",
            "automatic_role_change",
            "automatic_customer_contact",
            "automatic_deploy",
            "production_mutation",
            "executes_action",
        ):
            self.assertFalse(view[key], key)


if __name__ == "__main__":
    unittest.main()
