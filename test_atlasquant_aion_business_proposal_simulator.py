import ast
import unittest
from pathlib import Path

from atlasquant_aion_business_proposal_simulator import (
    build_proposal_draft,
    client_radar,
    diagnose_business,
    normalize_business_intake,
    proposal_text,
    recommend_package,
)


def _input(**updates):
    data = {
        "company_name": "Clínica Horizonte Demo",
        "segment": "Clínica",
        "channels": ["WhatsApp", "Instagram"],
        "goals": ["responder mais rápido", "recuperar leads"],
        "weekly_leads": 120,
        "avg_response_hours": 4.5,
        "abandoned_quotes_monthly": 18,
        "returning_customers_pct": 14,
        "content_posts_monthly": 2,
        "has_followup_process": False,
        "has_crm": False,
        "has_sla": False,
        "tracks_conversion": False,
        "notes": "fixture de treinamento",
    }
    data.update(updates)
    return data


class BusinessDiagnosticProposalSimulatorTests(unittest.TestCase):
    def test_normalize_intake_is_explicitly_demo_and_bounded(self):
        row = normalize_business_intake(_input())
        self.assertEqual(row["company_name"], "Clínica Horizonte Demo")
        self.assertEqual(row["truth_state"], "DEMO_USER_INPUT")
        self.assertFalse(row["real_client_verified"])
        self.assertEqual(row["required_missing"], [])
        self.assertGreater(row["evidence_coverage_pct"], 80)

    def test_invalid_or_missing_required_input_fails_closed(self):
        diag = diagnose_business({"company_name": "", "segment": ""})
        self.assertEqual(diag["state"], "INCOMPLETE")
        self.assertIn("company_name", diag["missing"])
        self.assertIn("segment", diag["missing"])
        self.assertFalse(diag["executes_action"])
        bad = normalize_business_intake(_input(returning_customers_pct=101, avg_response_hours=-1))
        self.assertIsNone(bad["returning_customers_pct"])
        self.assertIsNone(bad["avg_response_hours"])

    def test_diagnostic_surfaces_four_pillars_without_promising_result(self):
        diag = diagnose_business(_input())
        self.assertEqual(diag["state"], "ATTENTION_HIGH")
        self.assertGreaterEqual(diag["high_priority_count"], 2)
        self.assertEqual(set(diag["pillar_scores"]), {"ATRAIR", "ATENDER", "CONVERTER", "RETER"})
        titles = [item["title"] for item in diag["issues"]]
        self.assertIn("Tempo de resposta elevado", titles)
        self.assertIn("Ausência de processo de follow-up", titles)
        self.assertIn("Presença de conteúdo irregular", titles)
        self.assertIn("Retenção / reativação pode ser trabalhada", titles)
        self.assertEqual(len(diag["diagnostic_digest"]), 64)
        self.assertFalse(diag["promises_result"])
        self.assertFalse(diag["real_client_verified"])
        self.assertFalse(diag["executes_action"])

    def test_package_fit_prefers_complete_solution_for_multi_domain_problem(self):
        diag = diagnose_business(_input())
        fit = recommend_package(diag)
        self.assertEqual(fit["package_id"], "AION_BUSINESS_COMPLETO")
        self.assertEqual(fit["price_state"], "TO_DEFINE_AFTER_SCOPE")
        self.assertIsNone(fit["price"])
        self.assertGreaterEqual(len(fit["deliverables"]), 5)
        self.assertTrue(all(p in fit["pillars"] for p in ("ATRAIR", "ATENDER", "CONVERTER", "RETER")))
        self.assertFalse(fit["promises_result"])
        self.assertFalse(fit["executes_action"])

    def test_client_radar_is_simple_and_marked_as_demo(self):
        diag = diagnose_business(_input())
        radar = client_radar(diag)
        self.assertEqual(radar["mode"], "DEMO_RADAR")
        self.assertEqual(len(radar["cards"]), 4)
        self.assertLessEqual(len(radar["next_actions"]), 5)
        self.assertEqual(radar["data_source"], "DEMO_USER_INPUT")
        self.assertFalse(radar["real_client_verified"])
        self.assertFalse(radar["executes_action"])

    def test_proposal_draft_has_installation_maintenance_metrics_and_no_price_claim(self):
        diag = diagnose_business(_input())
        fit = recommend_package(diag)
        draft = build_proposal_draft(diag, fit)
        self.assertEqual(draft["state"], "DRAFT_READY")
        self.assertEqual(len(draft["proposal_digest"]), 64)
        proposal = draft["proposal"]
        self.assertEqual(proposal["status"], "DRAFT_NOT_SENT")
        self.assertIn("Implantação em sandbox / ambiente controlado", proposal["implementation_phases"][2])
        self.assertIn("Suporte e incidentes", proposal["monthly_maintenance"])
        self.assertEqual(proposal["commercial_terms"]["implementation_price"], "A DEFINIR APÓS ESCOPO")
        self.assertEqual(proposal["commercial_terms"]["monthly_maintenance"], "A DEFINIR APÓS ESCOPO")
        self.assertFalse(proposal["sent"])
        self.assertFalse(proposal["signed"])
        self.assertFalse(proposal["payment_requested"])
        self.assertFalse(proposal["runtime_activated"])
        self.assertFalse(draft["promises_result"])
        self.assertFalse(draft["executes_action"])
        self.assertFalse(draft["external_write"])

    def test_incomplete_diagnostic_cannot_generate_proposal(self):
        diag = diagnose_business({"company_name": "", "segment": ""})
        draft = build_proposal_draft(diag)
        self.assertEqual(draft["state"], "BLOCKED_INCOMPLETE_DIAGNOSTIC")
        self.assertEqual(draft["proposal"], {})
        self.assertFalse(draft["executes_action"])

    def test_proposal_text_is_internal_draft_only(self):
        draft = build_proposal_draft(diagnose_business(_input()))
        text = proposal_text(draft)
        self.assertIn("Proposta preliminar AION Business", text)
        self.assertIn("PACOTE RECOMENDADO", text)
        self.assertIn("MANUTENÇÃO MENSAL", text)
        self.assertIn("A DEFINIR APÓS ESCOPO", text)
        self.assertIn("RASCUNHO INTERNO — NÃO ENVIADO / NÃO ASSINADO", text)

    def test_module_has_no_external_io_or_provider_imports(self):
        source = Path("atlasquant_aion_business_proposal_simulator.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported = []
        for node in tree.body:
            if isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.append(node.module or "")
        for banned in ("requests", "urllib", "httpx", "socket", "subprocess", "openai", "streamlit"):
            self.assertNotIn(banned, imported)


if __name__ == "__main__":
    unittest.main()
