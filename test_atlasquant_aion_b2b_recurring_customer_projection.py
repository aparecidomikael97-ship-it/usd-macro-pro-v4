from __future__ import annotations

import unittest

from atlasquant_aion_b2b_customer_portal import (
    PORTAL_SCOPE,
    customer_portal_access,
    customer_portal_html,
    customer_portal_view_model,
)
from atlasquant_aion_b2b_recurring_customer_projection import (
    SCHEMA,
    build_recurring_customer_projection,
)
from atlasquant_aion_b2b_value_bound_service_cycle import (
    SCHEMA as SERVICE_CYCLE_SCHEMA,
)
from atlasquant_aion_tenant import tenant_namespace


def access(
    *,
    username="cliente_empresa",
    role="USER",
    fingerprint="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
):
    return {
        "authenticated": True,
        "username": username,
        "role": role,
        "session": {
            "username": username,
            "role": role,
            "credential_fingerprint": fingerprint,
        },
    }


def binding(current_access=None, **overrides):
    current_access = current_access or access()
    auth_tenant = tenant_namespace(current_access)["tenant_id"]
    row = {
        "state": "CONFIRMED",
        "enabled": True,
        "portal_scope": PORTAL_SCOPE,
        "subject_tenant_id": auth_tenant,
        "service_tenant_id": "service-tenant-001",
        "workspace_id": "service-workspace-001",
        "customer_id": "customer-001",
        "package": "PROFISSIONAL",
        "binding_ref": "customer-binding:001",
        "allowed_sections": ["overview", "value", "usage", "support"],
    }
    row.update(overrides)
    return row


def read_model(**overrides):
    row = {
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
            "capacity": {
                "used": 40,
                "limit": 60,
                "utilization_pct": 66.67,
            },
            "calls": {
                "used": 700,
                "limit": 1000,
                "utilization_pct": 70.0,
            },
            "tokens": {
                "used": 700000,
                "limit": 1000000,
                "utilization_pct": 70.0,
            },
            "support_tickets": {
                "used": 20,
                "limit": 40,
                "utilization_pct": 50.0,
            },
        },
        "support": {
            "avg_first_response_hours": 2.0,
            "avg_resolution_hours": 12.0,
            "critical_open_tickets": 0,
            "first_response_sla_met": True,
            "resolution_sla_met": True,
        },
        "review_reasons": ["INTERNAL_RENEWAL_REVIEW"],
        "incident_reasons": [],
        "generated_at": "2026-10-05T17:00:00-04:00",
        "evidence_digest": "sha256:service-read-model",
        "read_only": True,
        "grants_authority": False,
        "executes_action": False,
    }
    row.update(overrides)
    return row


def service_cycle(**overrides):
    row = {
        "schema": SERVICE_CYCLE_SCHEMA,
        "state": "HEALTHY",
        "decision": "RENEWAL_REVIEW_CANDIDATE",
        "scope": {
            "owner_id": "owner-a",
            "tenant_id": "service-tenant-001",
            "workspace_id": "service-workspace-001",
        },
        "owner_id": "owner-a",
        "tenant_id": "service-tenant-001",
        "workspace_id": "service-workspace-001",
        "customer_id": "customer-001",
        "pilot_id": "pilot-001",
        "package": "PROFISSIONAL",
        "health_score": 88.0,
        "observed_roi_pct": 60.0,
        "actual_service_cost_brl": 2200.0,
        "review_reasons": [],
        "incident_reasons": [],
        "blockers": [],
        "contract_digest": "sha256:contract",
        "value_bound_conversion_digest": "sha256:value-bound",
        "source_cycle_evidence_digest": "sha256:source-cycle",
        "evidence_digest": "sha256:service-cycle",
        "owner_review_required": True,
        "customer_visible": False,
        "contains_internal_finops": True,
        "requires_customer_safe_projection": True,
        "source_value_decision": "EXPANSION_REVIEW_CANDIDATE",
        "source_conversion_decision": (
            "EXPANSION_COMMERCIAL_REVIEW_CANDIDATE"
        ),
        "automatic_renewal": False,
        "automatic_expansion": False,
        "automatic_package_change": False,
        "automatic_pause": False,
        "automatic_termination": False,
        "automatic_billing": False,
        "automatic_quota_increase": False,
        "automatic_role_change": False,
        "automatic_integration_change": False,
        "automatic_customer_contact": False,
        "automatic_provisioning": False,
        "automatic_deploy": False,
        "provider_called": False,
        "production_mutation": False,
        "executes_action": False,
    }
    row.update(overrides)
    return row


def portal_access_result(current=None, model=None):
    current = current or access()
    model = model or read_model()
    return customer_portal_access(
        current,
        binding(current),
        model,
    )


def projection(**overrides):
    args = {
        "portal_access_result": portal_access_result(),
        "service_cycle": service_cycle(),
        "service_read_model": read_model(),
    }
    args.update(overrides)
    return build_recurring_customer_projection(**args)


class RecurringCustomerProjectionTests(unittest.TestCase):
    def test_safe_projection_keeps_customer_metrics_only(self):
        out = projection()
        self.assertEqual(out["schema"], SCHEMA)
        self.assertEqual(out["state"], "READY")
        self.assertTrue(out["allowed"])
        self.assertEqual(out["customer_id"], "customer-001")
        self.assertEqual(out["pilot_id"], "pilot-001")
        self.assertEqual(out["service_status"], "SAUDÁVEL")
        self.assertEqual(out["health_score"], 88.0)
        self.assertEqual(out["observed_roi_pct"], 60.0)
        self.assertEqual(
            out["usage"]["capacity"]["utilization_pct"],
            66.67,
        )
        self.assertTrue(out["support"]["first_response_sla_met"])
        self.assertFalse(out["internal_service_cost_exposed"])
        self.assertFalse(out["provider_margin_exposed"])
        self.assertFalse(out["retention_risk_exposed"])
        self.assertFalse(out["internal_recommendation_exposed"])
        self.assertFalse(out["internal_review_reasons_exposed"])
        for forbidden in (
            "actual_service_cost_brl",
            "service_decision",
            "review_reasons",
            "incident_reasons",
            "source_value_decision",
            "source_conversion_decision",
            "allowed_owner_choices",
        ):
            self.assertNotIn(forbidden, out)

    def test_cross_customer_cycle_blocks(self):
        out = projection(
            service_cycle=service_cycle(customer_id="customer-other"),
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("SERVICE_CYCLE_CUSTOMER_MISMATCH", out["blockers"])

    def test_cross_tenant_read_model_blocks(self):
        model = read_model()
        model["scope"] = {
            **model["scope"],
            "tenant_id": "tenant-other",
        }
        out = projection(service_read_model=model)
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("SERVICE_READ_MODEL_TENANT_MISMATCH", out["blockers"])

    def test_cycle_and_read_model_state_must_match(self):
        out = projection(
            service_cycle=service_cycle(
                state="REMEDIATION",
                decision="REMEDIATE_REVIEW",
            )
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("SERVICE_STATE_LINEAGE_MISMATCH", out["blockers"])

    def test_remediation_projects_customer_safe_status_without_recommendation(self):
        model = read_model(
            service_state="REMEDIATION",
            service_decision="REMEDIATE_REVIEW",
            health_label="ATENÇÃO",
            review_reasons=["INTERNAL_REMEDIATION_REASON"],
        )
        cycle = service_cycle(
            state="REMEDIATION",
            decision="REMEDIATE_REVIEW",
            review_reasons=["FIRST_RESPONSE_SLA_MISSED"],
        )
        out = build_recurring_customer_projection(
            portal_access_result=portal_access_result(model=model),
            service_cycle=cycle,
            service_read_model=model,
        )
        self.assertEqual(out["state"], "READY")
        self.assertEqual(out["service_status"], "EM ACOMPANHAMENTO")
        self.assertNotIn("service_decision", out)
        self.assertNotIn("review_reasons", out)

    def test_unsafe_cycle_authority_fails_closed(self):
        out = projection(
            service_cycle=service_cycle(automatic_renewal=True),
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "SERVICE_CYCLE_UNSAFE_FIELD:automatic_renewal",
            out["blockers"],
        )

    def test_projection_integrates_into_customer_portal_without_internal_leaks(self):
        current = access()
        model = read_model()
        safe = build_recurring_customer_projection(
            portal_access_result=portal_access_result(current, model),
            service_cycle=service_cycle(),
            service_read_model=model,
        )
        view = customer_portal_view_model(
            current,
            binding(current),
            model,
            None,
            None,
            None,
            safe,
        )
        self.assertEqual(view["state"], "READY")
        self.assertEqual(view["service_state"], "SAUDÁVEL")
        self.assertEqual(view["service_decision"], "")
        self.assertEqual(view["review_reasons"], [])
        self.assertEqual(view["incident_reasons"], [])
        self.assertFalse(view["internal_service_cost_exposed"])
        self.assertFalse(view["recurring_internal_recommendation_exposed"])
        html = customer_portal_html(view)
        for forbidden in (
            "2200",
            "RENEWAL_REVIEW_CANDIDATE",
            "INTERNAL_RENEWAL_REVIEW",
            "EXPANSION_REVIEW_CANDIDATE",
            "EXPANSION_COMMERCIAL_REVIEW_CANDIDATE",
            "MARGEM",
            "RISCO DE RETENÇÃO",
        ):
            self.assertNotIn(forbidden, html)
        for expected in (
            "SAÚDE",
            "88%",
            "ROI OBSERVADO",
            "60%",
            "SAUDÁVEL",
        ):
            self.assertIn(expected, html)

    def test_injected_forbidden_projection_field_blocks_portal(self):
        current = access()
        model = read_model()
        safe = projection()
        safe["actual_service_cost_brl"] = 2200.0
        view = customer_portal_view_model(
            current,
            binding(current),
            model,
            None,
            None,
            None,
            safe,
        )
        self.assertEqual(view["state"], "BLOCKED")
        self.assertIn(
            "RECURRING_PROJECTION_FORBIDDEN_FIELD:actual_service_cost_brl",
            view["blockers"],
        )

    def test_portal_without_recurring_projection_remains_compatible(self):
        current = access()
        model = read_model(review_reasons=[])
        view = customer_portal_view_model(
            current,
            binding(current),
            model,
        )
        self.assertEqual(view["state"], "READY")
        self.assertEqual(
            view["service_decision"],
            "RENEWAL_REVIEW_CANDIDATE",
        )

    def test_projection_never_grants_authority(self):
        out = projection()
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


if __name__ == "__main__":
    unittest.main()
