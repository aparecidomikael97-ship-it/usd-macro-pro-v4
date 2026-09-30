import ast
import unittest
from pathlib import Path

from atlasquant_aion_business_training import (
    OBJECTIONS,
    SCENARIOS,
    TRAINING_FLOW,
    delivery_walkthrough,
    diagnostic_brief,
    objection_answer,
    objection_catalog,
    package_fit,
    scenario_catalog,
    simulated_sales_conversation,
    training_scorecard,
    training_session,
)


class BusinessGuidedTrainingTests(unittest.TestCase):
    def test_catalog_has_three_fictional_niches(self):
        catalog = scenario_catalog()
        self.assertEqual(len(catalog), 3)
        self.assertEqual(len(SCENARIOS), 3)
        self.assertTrue(any(row["segment"] == "Clínica" for row in catalog))
        self.assertTrue(any(row["segment"] == "Imobiliária" for row in catalog))
        self.assertTrue(any(row["segment"] == "Prestador de Serviços" for row in catalog))

    def test_training_flow_is_bounded_and_never_real_runtime(self):
        first = training_session("CLINICA_LOCAL", step=1)
        last = training_session("CLINICA_LOCAL", step=999)
        invalid = training_session("UNKNOWN", step="x")
        self.assertEqual(first["step"], 1)
        self.assertEqual(last["step"], len(TRAINING_FLOW))
        self.assertEqual(invalid["scenario"]["id"], "CLINICA_LOCAL")
        for row in (first, last, invalid):
            self.assertEqual(row["mode"], "FICTIONAL_TRAINING")
            self.assertFalse(row["real_client"])
            self.assertFalse(row["runtime_activated"])
            self.assertFalse(row["executes_action"])

    def test_diagnostic_keeps_fixture_truth_boundary(self):
        brief = diagnostic_brief("IMOBILIARIA_LOCAL")
        self.assertEqual(brief["truth_state"], "FICTIONAL_FIXTURE")
        self.assertIn("Qualificação", brief["priority_gaps"])
        self.assertIn("Leads sem acompanhamento", brief["priority_gaps"])
        self.assertGreaterEqual(len(brief["questions_to_confirm"]), 5)
        self.assertFalse(brief["executes_action"])

    def test_package_fit_uses_bundle_not_isolated_tool(self):
        clinic = package_fit("CLINICA_LOCAL")
        service = package_fit("SERVICO_LOCAL")
        self.assertEqual(clinic["package_id"], "ATENDIMENTO_CONVERSAO")
        self.assertEqual(service["package_id"], "AION_BUSINESS_COMPLETO")
        for fit in (clinic, service):
            self.assertGreaterEqual(len(fit["components"]), 4)
            self.assertFalse(fit["pricing_defined"])
            self.assertTrue(fit["requires_real_diagnostic_before_proposal"])
            self.assertFalse(fit["promises_result"])
            self.assertFalse(fit["executes_action"])

    def test_delivery_explains_installation_and_monthly_maintenance(self):
        delivery = delivery_walkthrough("CLINICA_LOCAL")
        self.assertTrue(delivery["installation_plus_monthly_maintenance"])
        self.assertIn("Onboarding e definição do escopo", delivery["what_client_receives"])
        self.assertIn("Rotina de manutenção e suporte", delivery["what_client_receives"])
        self.assertIn("O que está acontecendo", delivery["what_client_sees"])
        self.assertFalse(delivery["pricing_defined"])
        self.assertFalse(delivery["runtime_activated"])
        self.assertFalse(delivery["executes_action"])

    def test_objections_include_no_guarantee_and_unknown_fails_safe(self):
        self.assertEqual(len(objection_catalog()), len(OBJECTIONS))
        guarantee = objection_answer("GARANTIA_VENDAS")
        self.assertIn("Não.", guarantee["answer"])
        self.assertFalse(guarantee["promises_result"])
        unknown = objection_answer("SLA_DESCONHECIDO")
        self.assertEqual(unknown["state"], "UNKNOWN_OBJECTION")
        self.assertIn("Não invente", unknown["answer"])
        self.assertFalse(unknown["executes_action"])

    def test_simulated_conversation_is_explicitly_demo_and_scope_first(self):
        conversation = simulated_sales_conversation("CLINICA_LOCAL")
        self.assertGreaterEqual(len(conversation), 6)
        self.assertEqual(conversation[0]["speaker"], "ADMIN")
        self.assertIn("Antes de falar de tecnologia", conversation[0]["text"])
        all_text = " ".join(row["text"] for row in conversation)
        self.assertIn("diagnóstico", all_text)
        self.assertIn("empresa real", all_text)
        self.assertIn("manutenção", all_text)

    def test_scorecard_requires_every_safety_and_sales_learning_check(self):
        empty = training_scorecard()
        self.assertEqual(empty["progress_pct"], 0.0)
        self.assertFalse(empty["training_complete"])
        complete = training_scorecard(
            explained_problem_before_technology=True,
            separated_fact_from_assumption=True,
            explained_package_scope=True,
            explained_installation_and_maintenance=True,
            avoided_financial_guarantee=True,
            explained_client_portal=True,
            asked_for_next_step=True,
        )
        self.assertEqual(complete["progress_pct"], 100.0)
        self.assertTrue(complete["training_complete"])
        self.assertFalse(complete["authorizes_sales"])
        self.assertFalse(complete["authorizes_runtime"])
        self.assertFalse(complete["executes_action"])

    def test_module_has_no_external_io_or_provider_imports(self):
        source = Path("atlasquant_aion_business_training.py").read_text(encoding="utf-8")
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
