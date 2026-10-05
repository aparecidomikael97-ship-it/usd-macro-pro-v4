from __future__ import annotations

import unittest

from atlasquant_aion_tenant import tenant_namespace
from atlasquant_aion_b2b_customer_portal import (
    PORTAL_SCOPE,
    customer_portal_access,
    customer_portal_html,
    customer_portal_view_model,
    normalize_customer_portal_binding,
)


def access(role="USER", username="cliente.01", fingerprint="a" * 24):
    return {
        "allowed": True,
        "mode": "AUTHENTICATED",
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
        "generated_at": "2026-10-05T12:00:00-04:00",
        "evidence_digest": "sha256:validated-read-model",
        "read_only": True,
        "grants_authority": False,
        "executes_action": False,
    }
    row.update(overrides)
    return row


class AionB2BCustomerPortalTests(unittest.TestCase):
    def test_confirmed_user_binding_allows_exact_customer_only(self):
        current = access()
        out = customer_portal_access(current, binding(current), read_model())
        self.assertTrue(out["allowed"])
        self.assertEqual(out["state"], "ALLOW")
        self.assertEqual(out["customer_id"], "customer-001")
        self.assertFalse(out["admin_memory_access"])
        self.assertFalse(out["other_tenant_access"])
        self.assertFalse(out["executes_action"])

    def test_admin_and_sales_cannot_use_customer_portal_as_customer(self):
        for role in ("ADMIN", "SALES"):
            with self.subTest(role=role):
                current = access(role=role)
                out = customer_portal_access(current, binding(current), read_model())
                self.assertFalse(out["allowed"])
                self.assertIn("CUSTOMER_USER_ROLE_REQUIRED", out["blockers"])

    def test_credential_rotation_breaks_old_binding(self):
        original = access(fingerprint="a" * 24)
        rotated = access(fingerprint="b" * 24)
        out = customer_portal_access(rotated, binding(original), read_model())
        self.assertFalse(out["allowed"])
        self.assertIn("CUSTOMER_SUBJECT_TENANT_MISMATCH", out["blockers"])

    def test_binding_must_be_confirmed_enabled_and_scoped(self):
        current = access()
        out = customer_portal_access(
            current,
            binding(current, state="PENDING", enabled=False, portal_scope="OTHER"),
            read_model(),
        )
        self.assertIn("CUSTOMER_PORTAL_BINDING_NOT_CONFIRMED", out["blockers"])
        self.assertIn("CUSTOMER_PORTAL_BINDING_DISABLED", out["blockers"])
        self.assertIn("CUSTOMER_PORTAL_SCOPE_INVALID", out["blockers"])

    def test_service_tenant_and_workspace_mismatch_fail_closed(self):
        current = access()
        out = customer_portal_access(
            current,
            binding(current, service_tenant_id="other-tenant", workspace_id="other-workspace"),
            read_model(),
        )
        self.assertIn("CUSTOMER_SERVICE_TENANT_MISMATCH", out["blockers"])
        self.assertIn("CUSTOMER_SERVICE_WORKSPACE_MISMATCH", out["blockers"])

    def test_customer_and_package_mismatch_fail_closed(self):
        current = access()
        out = customer_portal_access(
            current,
            binding(current, customer_id="customer-999", package="COMPLETO"),
            read_model(),
        )
        self.assertIn("CUSTOMER_READ_MODEL_CUSTOMER_MISMATCH", out["blockers"])
        self.assertIn("CUSTOMER_READ_MODEL_PACKAGE_MISMATCH", out["blockers"])

    def test_authority_bearing_or_executing_read_model_is_rejected(self):
        current = access()
        out = customer_portal_access(
            current,
            binding(current),
            read_model(grants_authority=True, executes_action=True),
        )
        self.assertIn("CUSTOMER_READ_MODEL_AUTHORITY_UNSAFE", out["blockers"])
        self.assertIn("CUSTOMER_READ_MODEL_EXECUTION_UNSAFE", out["blockers"])

    def test_customer_view_filters_internal_cost_and_owner_scope(self):
        current = access()
        view = customer_portal_view_model(current, binding(current), read_model())
        self.assertEqual(view["state"], "READY")
        self.assertNotIn("actual_service_cost_brl", view)
        self.assertNotIn("scope", view)
        self.assertNotIn("owner_id", str(view))
        self.assertFalse(view["internal_service_cost_exposed"])
        self.assertFalse(view["owner_scope_exposed"])

    def test_customer_view_preserves_usage_value_and_sla(self):
        current = access()
        view = customer_portal_view_model(current, binding(current), read_model())
        self.assertEqual(view["health_score"], 88.0)
        self.assertEqual(view["observed_roi_pct"], 60.0)
        self.assertEqual(view["usage"]["capacity"]["utilization_pct"], 66.67)
        self.assertTrue(view["support"]["first_response_sla_met"])
        self.assertTrue(view["support"]["resolution_sla_met"])

    def test_binding_can_reduce_visible_sections_but_not_add_unknown_sections(self):
        current = access()
        normalized = normalize_customer_portal_binding(
            binding(current, allowed_sections=["overview", "support", "admin", "billing"])
        )
        self.assertEqual(normalized["allowed_sections"], ("overview", "support"))

    def test_html_is_read_only_and_hides_internal_cost(self):
        current = access()
        view = customer_portal_view_model(current, binding(current), read_model())
        html = customer_portal_html(view)
        self.assertIn('data-customer-portal="read-only"', html)
        self.assertIn("Portal do Cliente", html)
        self.assertIn("88%", html)
        self.assertIn("60%", html)
        self.assertIn("66.67%", html)
        self.assertNotIn("2200", html)
        self.assertNotIn("actual_service_cost", html)
        self.assertNotIn("Cobrar agora", html)
        self.assertNotIn("Renovar agora", html)
        self.assertIn("Nenhuma cobrança, renovação ou alteração operacional", html)

    def test_html_escapes_customer_supplied_text(self):
        current = access()
        malicious = read_model(customer_id="<script>alert(1)</script>")
        bound = binding(current, customer_id="<script>alert(1)</script>")
        view = customer_portal_view_model(current, bound, malicious)
        html = customer_portal_html(view)
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)

    def test_blocked_access_renders_no_customer_metrics(self):
        current = access()
        view = customer_portal_view_model(
            current,
            binding(current, enabled=False),
            read_model(),
        )
        html = customer_portal_html(view)
        self.assertEqual(view["state"], "BLOCKED")
        self.assertNotIn("88%", html)
        self.assertNotIn("60%", html)
        self.assertIn("indisponíveis", html)

    def test_no_external_authority_is_granted(self):
        current = access()
        view = customer_portal_view_model(current, binding(current), read_model())
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
