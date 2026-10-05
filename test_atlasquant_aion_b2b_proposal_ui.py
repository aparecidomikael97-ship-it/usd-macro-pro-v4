from __future__ import annotations

import unittest

from atlasquant_reference_ui import module_panel, reference_html


def proposal_draft(**overrides):
    row = {
        "schema": "ATLASQUANT_AION_B2B_PROPOSAL_DRAFT_V1",
        "state": "DRAFT_FOR_HUMAN_REVIEW",
        "proposal": {
            "owner_id": "owner-a",
            "tenant_id": "tenant-a",
            "workspace_id": "business",
            "proposal_id": "proposal-001",
            "candidate_id": "candidate-001",
            "company_label": "Empresa Exemplo",
            "package": "PROFISSIONAL",
            "pricing": {
                "mode": "INDICATIVE",
                "indicative_setup_fee_brl": 2500.0,
                "indicative_monthly_fee_brl": 4500.0,
                "pricing_basis_ref": "pricing-review:001",
                "currency": "BRL",
                "binding": False,
            },
            "scope_items": [
                "Diagnóstico operacional",
                "Estruturação de CRM",
                "Acompanhamento de indicadores",
            ],
            "exclusions": [
                "Sem compromisso automático de preço",
                "Sem deploy sem aprovação",
            ],
            "implementation_phases": [
                "Diagnóstico e baseline",
                "Piloto controlado",
                "Revisão humana",
            ],
            "assumptions": [
                "Dados autorizados",
                "Responsável disponível",
            ],
            "validity_days": 15,
            "diagnostic_digest": "sha256:diag",
            "readiness_evidence_digest": "sha256:ready",
            "human_commercial_author_ref": "commercial-owner:001",
            "evidence_refs": ["commercial:scope", "commercial:terms"],
        },
        "proposal_digest": "sha256:proposal",
        "non_binding": True,
        "owner_review_required": True,
        "customer_send_allowed": False,
        "contract_ready": False,
        "price_commitment": False,
        "automatic_proposal_generation": False,
        "automatic_pricing": False,
        "automatic_customer_contact": False,
        "automatic_contract": False,
        "automatic_billing": False,
        "automatic_provisioning": False,
        "crm_write": False,
        "provider_called": False,
        "production_mutation": False,
        "executes_action": False,
    }
    row.update(overrides)
    return row


class AionB2BProposalUITests(unittest.TestCase):
    def test_proposals_route_renders_read_only_draft_summary(self):
        html = module_panel(
            "negocios",
            "proposals",
            proposal_draft=proposal_draft(),
        )
        self.assertIn('data-proposal-readonly="true"', html)
        self.assertIn("PROPOSTA", html)
        self.assertIn("proposal-001", html)
        self.assertIn("PROFISSIONAL", html)
        self.assertIn("INDICATIVE", html)
        self.assertIn("R$ 2.500,00", html)
        self.assertIn("R$ 4.500,00", html)
        self.assertIn("DRAFT NÃO VINCULANTE", html)
        self.assertIn("ENVIO AO CLIENTE BLOQUEADO", html)

    def test_scope_is_visible_but_no_action_controls_exist(self):
        html = module_panel(
            "negocios",
            "proposals",
            proposal_draft=proposal_draft(),
        )
        for expected in (
            "Diagnóstico operacional",
            "Estruturação de CRM",
            "Acompanhamento de indicadores",
        ):
            self.assertIn(expected, html)
        for forbidden in (
            "Enviar proposta",
            "Enviar agora",
            "Assinar",
            "Cobrar",
            "Aceitar proposta",
            "Gerar contrato",
            "Pagar",
        ):
            self.assertNotIn(forbidden, html)

    def test_tbd_price_renders_without_numeric_commitment(self):
        draft = proposal_draft()
        draft["proposal"] = dict(draft["proposal"])
        draft["proposal"]["pricing"] = {
            "mode": "TBD",
            "indicative_setup_fee_brl": None,
            "indicative_monthly_fee_brl": None,
            "pricing_basis_ref": "",
            "currency": "BRL",
            "binding": False,
        }
        html = module_panel(
            "negocios",
            "proposals",
            proposal_draft=draft,
        )
        self.assertIn(">TBD<", html)
        self.assertIn("Preço ainda não definido", html)
        self.assertNotIn("R$ 4.500,00", html)

    def test_invalid_or_blocked_draft_falls_back_to_preview(self):
        html = module_panel(
            "negocios",
            "proposals",
            proposal_draft=proposal_draft(state="BLOCKED"),
        )
        self.assertNotIn('data-proposal-readonly="true"', html)
        self.assertNotIn("proposal-001", html)
        self.assertIn("PRÉVIA", html)

    def test_send_flag_flip_blocks_rendering(self):
        html = module_panel(
            "negocios",
            "proposals",
            proposal_draft=proposal_draft(customer_send_allowed=True),
        )
        self.assertNotIn('data-proposal-readonly="true"', html)
        self.assertNotIn("proposal-001", html)
        self.assertIn("BLOQUEADA", html)

    def test_contract_or_price_commitment_flip_blocks_rendering(self):
        for key in ("contract_ready", "price_commitment"):
            with self.subTest(key=key):
                draft = proposal_draft()
                draft[key] = True
                html = module_panel(
                    "negocios",
                    "proposals",
                    proposal_draft=draft,
                )
                self.assertNotIn('data-proposal-readonly="true"', html)
                self.assertNotIn("proposal-001", html)

    def test_automatic_action_flag_flip_blocks_rendering(self):
        for key in (
            "automatic_proposal_generation",
            "automatic_pricing",
            "automatic_customer_contact",
            "automatic_contract",
            "automatic_billing",
            "crm_write",
            "executes_action",
        ):
            with self.subTest(key=key):
                draft = proposal_draft()
                draft[key] = True
                html = module_panel(
                    "negocios",
                    "proposals",
                    proposal_draft=draft,
                )
                self.assertNotIn('data-proposal-readonly="true"', html)

    def test_other_business_routes_do_not_reuse_proposal_draft(self):
        html = module_panel(
            "negocios",
            "finops",
            proposal_draft=proposal_draft(),
        )
        self.assertNotIn("proposal-001", html)
        self.assertNotIn('data-proposal-readonly="true"', html)

    def test_reference_html_accepts_proposal_draft(self):
        html = reference_html(
            "negocios",
            selected="proposals",
            proposal_draft=proposal_draft(),
        )
        self.assertIn("Propostas", html)
        self.assertIn("proposal-001", html)
        self.assertIn("EXECUÇÃO", html)
        self.assertIn("BLOQUEADA", html)


if __name__ == "__main__":
    unittest.main()
