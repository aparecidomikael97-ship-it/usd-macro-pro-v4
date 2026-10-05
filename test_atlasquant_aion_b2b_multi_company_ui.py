from __future__ import annotations

import unittest

from atlasquant_reference_ui import module_panel, reference_html


def multi_company_model(**overrides):
    row = {
        "schema": "ATLASQUANT_AION_B2B_MULTI_COMPANY_READ_MODEL_V1",
        "state": "READY",
        "scope": {
            "owner_id": "owner-a",
            "tenant_id": "atlasquant-owner",
            "workspace_id": "business",
        },
        "admission_state": "REVIEWABLE",
        "admission_decision": "TENANT_ADMISSION_REVIEW_CANDIDATE",
        "service_tenant_id": "customer-001-prod",
        "package": "PROFISSIONAL",
        "projected_active_tenants": 3,
        "quota_projection": {
            "capacity_units": {
                "requested": 40,
                "projected_allocated": 120,
                "portfolio_limit": 300,
                "reserve_pct": 60.0,
                "single_tenant_share_pct": 13.33,
            },
            "calls_per_cycle": {
                "requested": 1000,
                "projected_allocated": 3000,
                "portfolio_limit": 10000,
                "reserve_pct": 70.0,
                "single_tenant_share_pct": 10.0,
            },
            "tokens_per_cycle": {
                "requested": 1000000,
                "projected_allocated": 3000000,
                "portfolio_limit": 10000000,
                "reserve_pct": 70.0,
                "single_tenant_share_pct": 10.0,
            },
            "support_tickets_per_cycle": {
                "requested": 20,
                "projected_allocated": 60,
                "portfolio_limit": 200,
                "reserve_pct": 70.0,
                "single_tenant_share_pct": 10.0,
            },
        },
        "minimum_portfolio_reserve_pct": 60.0,
        "maximum_single_tenant_share_pct": 13.33,
        "capacity_reason_count": 0,
        "isolation_reason_count": 0,
        "review_reasons": [],
        "evidence_digest": "sha256:" + "1" * 64,
        "owner_admission_approval_required": True,
        "read_only": True,
        "other_tenant_identity_exposed": False,
        "customer_identity_exposed": False,
        "tenant_creation_control_exposed": False,
        "quota_control_exposed": False,
        "provisioning_control_exposed": False,
        "billing_control_exposed": False,
        "grants_authority": False,
        "executes_action": False,
    }
    row.update(overrides)
    return row


class AionB2BMultiCompanyUITests(unittest.TestCase):
    def test_companies_route_renders_read_only_admission_summary(self):
        html = module_panel(
            "negocios",
            "companies",
            multi_company_read_model=multi_company_model(),
        )
        self.assertIn('data-multi-company-readonly="true"', html)
        self.assertIn("ADMISSÃO", html)
        self.assertIn("REVISÃO DE ADMISSÃO", html)
        self.assertIn("TENANT CANDIDATO", html)
        self.assertIn("customer-001-prod", html)
        self.assertIn("PROFISSIONAL", html)
        self.assertIn("TENANTS PROJETADOS", html)
        self.assertIn("RESERVA MÍN.", html)
        self.assertIn("60%", html)
        self.assertIn("CONCENTRAÇÃO MÁX.", html)
        self.assertIn("13.33%", html)
        self.assertIn(
            "SEM CRIAÇÃO DE TENANT OU QUOTA",
            html,
        )

    def test_companies_ui_does_not_render_other_customer_identity(self):
        html = module_panel(
            "negocios",
            "companies",
            multi_company_read_model=multi_company_model(),
        )
        for forbidden in (
            "customer-alpha",
            "customer-beta",
            "tenant-alpha-001",
            "tenant-beta-001",
            "customer_id",
            "other_tenant",
        ):
            self.assertNotIn(forbidden, html)

    def test_companies_ui_has_no_tenant_or_quota_action_controls(self):
        html = module_panel(
            "negocios",
            "companies",
            multi_company_read_model=multi_company_model(),
        )
        for forbidden in (
            ">Criar tenant<",
            ">Criar empresa<",
            ">Alterar quota<",
            ">Aumentar quota<",
            ">Provisionar<",
            ">Cobrar<",
            ">Deploy<",
            'data-action="tenant"',
            'data-action="quota"',
        ):
            self.assertNotIn(forbidden, html)

    def test_capacity_hold_is_visible_without_action(self):
        html = module_panel(
            "negocios",
            "companies",
            multi_company_read_model=multi_company_model(
                admission_state="CAPACITY_HOLD",
                admission_decision="CAPACITY_REVIEW",
                capacity_reason_count=2,
            ),
        )
        self.assertIn("HOLD DE CAPACIDADE", html)
        self.assertIn("ALERTAS CAPACIDADE", html)
        self.assertNotIn(">Provisionar<", html)

    def test_isolation_hold_is_visible_without_other_identity(self):
        html = module_panel(
            "negocios",
            "companies",
            multi_company_read_model=multi_company_model(
                admission_state="ISOLATION_HOLD",
                admission_decision="ISOLATION_REVIEW",
                isolation_reason_count=1,
            ),
        )
        self.assertIn("HOLD DE ISOLAMENTO", html)
        self.assertIn("ALERTAS ISOLAMENTO", html)
        self.assertNotIn("tenant-alpha-001", html)

    def test_unsafe_read_model_is_not_rendered(self):
        html = module_panel(
            "negocios",
            "companies",
            multi_company_read_model=multi_company_model(
                tenant_creation_control_exposed=True
            ),
        )
        self.assertNotIn('data-multi-company-readonly="true"', html)

    def test_reference_html_marks_capacity_validated_and_execution_blocked(self):
        html = reference_html(
            "negocios",
            selected="companies",
            multi_company_read_model=multi_company_model(),
        )
        self.assertIn("CAPACIDADE MULTIEMPRESA VALIDADA", html)
        self.assertIn(
            "SOMENTE LEITURA · admissão multiempresa em revisão",
            html,
        )
        self.assertIn(
            "<small>EXECUÇÃO</small><strong>BLOQUEADA</strong>",
            html,
        )

    def test_other_routes_do_not_render_multi_company_panel(self):
        html = module_panel(
            "negocios",
            "b2b",
            multi_company_read_model=multi_company_model(),
        )
        self.assertNotIn('data-multi-company-readonly="true"', html)


if __name__ == "__main__":
    unittest.main()
