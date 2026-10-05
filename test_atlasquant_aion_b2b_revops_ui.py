from __future__ import annotations

import unittest

from atlasquant_reference_ui import module_panel, reference_html


def revops_model(**overrides):
    row = {
        "schema": "ATLASQUANT_AION_B2B_REVOPS_READ_MODEL_V1",
        "state": "READY",
        "source_state": "READY_WITH_REVIEW",
        "scope": {
            "owner_id": "owner-a",
            "tenant_id": "tenant-a",
            "workspace_id": "business",
        },
        "metrics": {
            "accepted_records": 25,
            "rejected_records": 0,
            "company_count": 20,
            "duplicate_company_candidate_count": 2,
            "stale_record_count": 3,
            "due_next_action_count": 4,
            "do_not_contact_count": 1,
            "unknown_contact_count": 2,
            "contact_evidence_coverage_pct": 88.0,
            "next_action_coverage_pct": 96.0,
            "owner_coverage_pct": 100.0,
        },
        "stage_counts": {
            "LEAD": 8,
            "DIAGNOSTIC": 5,
            "DEMO": 3,
            "PROPOSAL": 4,
            "CONTRACT": 2,
            "PAYMENT": 1,
            "IMPLEMENTATION": 1,
            "APPROVAL": 0,
            "PUBLISHED": 0,
            "FOLLOWUP": 1,
            "ACTIVE_SERVICE": 0,
            "CLOSED_LOST": 1,
        },
        "review_signals": ["STALE_RECORDS_PRESENT"],
        "evidence_digest": "sha256:revops",
        "read_only": True,
        "raw_records_exposed": False,
        "contact_data_exposed": False,
        "crm_write": False,
        "automatic_outreach": False,
        "automatic_followup": False,
        "automatic_stage_change": False,
        "automatic_owner_assignment": False,
        "automatic_price_commitment": False,
        "automatic_contract_commitment": False,
        "provider_called": False,
        "production_mutation": False,
        "grants_authority": False,
        "executes_action": False,
    }
    row.update(overrides)
    return row


class AionB2BRevOpsUITests(unittest.TestCase):
    def test_revenue_route_renders_aggregate_revops_metrics(self):
        html = module_panel(
            "negocios",
            "revenue",
            revops_read_model=revops_model(),
        )
        self.assertIn('data-revops-readonly="true"', html)
        self.assertIn("LEADS VÁLIDOS", html)
        self.assertIn(">25<", html)
        self.assertIn("EMPRESAS", html)
        self.assertIn(">20<", html)
        self.assertIn("PRÓXIMAS AÇÕES VENCIDAS", html)
        self.assertIn(">4<", html)
        self.assertIn("OWNER COBERTO", html)
        self.assertIn(">100%<", html)
        self.assertIn("EVIDÊNCIA DE CONTATO", html)
        self.assertIn(">88%<", html)
        self.assertIn("RevOps agregado", html)

    def test_leads_route_shows_top_of_funnel_without_raw_records(self):
        html = module_panel(
            "negocios",
            "leads",
            revops_read_model=revops_model(),
        )
        for label in ("LEAD", "DIAGNÓSTICO", "DEMO", "PROPOSTA"):
            self.assertIn(label, html)
        self.assertNotIn("secret-lead", html)
        self.assertNotIn("company_label", html)
        self.assertNotIn("record_owner_ref", html)

    def test_crm_route_shows_operating_stages_without_action_controls(self):
        html = module_panel(
            "negocios",
            "crm",
            revops_read_model=revops_model(),
        )
        for label in ("CONTRATO", "IMPLANTAÇÃO", "FOLLOW-UP", "SERVIÇO ATIVO"):
            self.assertIn(label, html)
        for forbidden in (
            "Enviar agora",
            "Disparar follow-up",
            "Mover estágio",
            "Excluir lead",
            "Fechar contrato",
        ):
            self.assertNotIn(forbidden, html)

    def test_invalid_revops_model_does_not_render_metrics(self):
        html = module_panel(
            "negocios",
            "revenue",
            revops_read_model=revops_model(state="BLOCKED"),
        )
        self.assertNotIn('data-revops-readonly="true"', html)
        self.assertNotIn("LEADS VÁLIDOS", html)
        self.assertIn("PRÉVIA", html)

    def test_partial_model_is_labeled_partial_not_confirmed(self):
        html = module_panel(
            "negocios",
            "revenue",
            revops_read_model=revops_model(state="PARTIAL"),
        )
        self.assertIn("REVOPS PARCIAL", html)
        self.assertIn("SOMENTE LEITURA · RevOps agregado", html)

    def test_reference_html_accepts_revops_without_business_customer_model(self):
        html = reference_html(
            "negocios",
            selected="revenue",
            revops_read_model=revops_model(),
            business_read_model=None,
        )
        self.assertIn("Captação / Revenue Ops", html)
        self.assertIn("LEADS VÁLIDOS", html)
        self.assertIn("EXECUÇÃO", html)
        self.assertIn("BLOQUEADA", html)

    def test_non_revops_business_route_does_not_reuse_revops_metrics(self):
        html = module_panel(
            "negocios",
            "finops",
            revops_read_model=revops_model(),
        )
        self.assertNotIn("LEADS VÁLIDOS", html)
        self.assertNotIn('data-revops-readonly="true"', html)

    def test_read_model_cannot_enable_execution_by_ui_claim(self):
        malicious = revops_model(executes_action=True)
        html = module_panel(
            "negocios",
            "revenue",
            revops_read_model=malicious,
        )
        self.assertNotIn("LEADS VÁLIDOS", html)
        self.assertIn("EXECUÇÃO", html)
        self.assertIn("BLOQUEADA", html)


if __name__ == "__main__":
    unittest.main()
