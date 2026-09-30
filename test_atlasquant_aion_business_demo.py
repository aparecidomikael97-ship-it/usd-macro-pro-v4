import ast
import unittest
from pathlib import Path

from atlasquant_aion_business_demo import (
    CLIENT_JOURNEY,
    PACKAGES,
    PILLARS,
    REVENUE_ENGINES,
    TRAINING_STEPS,
    admin_training_demo,
    business_demo_snapshot,
    business_demo_html,
    client_portal_demo,
    demo_business_radar,
)


class BusinessDemoTests(unittest.TestCase):
    def test_snapshot_consolidates_new_business_scope(self):
        snapshot = business_demo_snapshot()
        self.assertEqual(snapshot["mode"], "DEMO_SANDBOX")
        self.assertEqual(snapshot["certification_state"], "CERTIFIED")
        self.assertEqual(snapshot["runtime_state"], "OFF")
        self.assertEqual(snapshot["tagline"], "Poderoso por dentro. Simples por fora.")
        self.assertEqual(len(snapshot["pillars"]), 4)
        self.assertEqual([item["label"] for item in snapshot["pillars"]], [
            "Atrair", "Atender", "Converter", "Reter",
        ])
        self.assertEqual(len(snapshot["revenue_engines"]), 5)
        self.assertEqual(len(snapshot["packages"]), 4)
        self.assertEqual(snapshot["client_journey"], list(CLIENT_JOURNEY))
        self.assertFalse(snapshot["legacy_marketplace_primary"])
        self.assertTrue(snapshot["legacy_marketplace_compatibility_only"])
        self.assertFalse(snapshot["promises_financial_result"])
        self.assertFalse(snapshot["executes_action"])
        self.assertFalse(snapshot["payment_enabled"])
        self.assertFalse(snapshot["publication_enabled"])
        self.assertFalse(snapshot["external_contact_enabled"])
        self.assertFalse(snapshot["runtime_activated"])

    def test_approved_scope_constants_are_complete(self):
        self.assertEqual(len(PILLARS), 4)
        self.assertEqual(len(REVENUE_ENGINES), 5)
        self.assertEqual(len(PACKAGES), 4)
        self.assertEqual(len(TRAINING_STEPS), 7)
        self.assertIn("Prospecção", CLIENT_JOURNEY)
        self.assertIn("Renovação", CLIENT_JOURNEY)

    def test_demo_radar_uses_fixture_and_never_claims_real_client_data(self):
        radar = demo_business_radar({
            "leads_open": 42,
            "avg_response_hours": 3.5,
            "abandoned_quotes": 8,
            "returning_customers_pct": 12,
        })
        self.assertEqual(radar["state"], "ATTENTION")
        titles = [item["title"] for item in radar["alerts"]]
        self.assertIn("Tempo de resposta alto", titles)
        self.assertIn("Orçamentos sem retorno", titles)
        self.assertIn("Fila de leads elevada", titles)
        self.assertIn("Retenção pode ser trabalhada", titles)
        self.assertFalse(radar["is_real_client_data"])
        self.assertFalse(radar["promises_result"])
        self.assertFalse(radar["executes_action"])

    def test_demo_radar_is_incomplete_when_fixture_missing(self):
        radar = demo_business_radar({"leads_open": 5})
        self.assertEqual(radar["state"], "INCOMPLETE")
        self.assertIn("avg_response_hours", radar["missing"])
        self.assertFalse(radar["is_real_client_data"])

    def test_client_portal_is_simple_demo_shell(self):
        portal = client_portal_demo("Clínica Exemplo", package_id="GESTAO_INTELIGENTE")
        self.assertEqual(portal["company_name"], "Clínica Exemplo")
        self.assertEqual(portal["package"]["label"], "Gestão Inteligente")
        self.assertEqual(portal["client_language"], "SIMPLE")
        self.assertTrue(portal["technical_complexity_hidden"])
        self.assertFalse(portal["real_client_connected"])
        self.assertFalse(portal["runtime_activated"])
        self.assertFalse(portal["executes_action"])

    def test_unknown_package_falls_back_to_first_safe_package(self):
        portal = client_portal_demo("Demo", package_id="UNKNOWN")
        self.assertEqual(portal["package"]["id"], PACKAGES[0]["id"])
        self.assertFalse(portal["executes_action"])

    def test_training_is_bounded_and_has_no_action(self):
        first = admin_training_demo(1)
        last = admin_training_demo(999)
        invalid = admin_training_demo("x")
        self.assertEqual(first["current_step"], 1)
        self.assertEqual(last["current_step"], len(TRAINING_STEPS))
        self.assertEqual(invalid["current_step"], 1)
        self.assertFalse(first["completion_is_certification"])
        self.assertFalse(last["executes_action"])

    def test_demo_html_is_mobile_responsive_and_explicitly_fake(self):
        html = business_demo_html()
        self.assertIn("AION BUSINESS // DEMO SEGURA", html)
        self.assertIn("Poderoso por dentro. Simples por fora.", html)
        self.assertIn("BUSINESS CERTIFIED", html)
        self.assertIn("RUNTIME OFF", html)
        self.assertIn("SEM AÇÃO EXTERNA", html)
        self.assertIn("4 pilares", html)
        self.assertIn("Pacotes para vender solução completa", html)
        self.assertIn("Jornada comercial", html)
        self.assertIn("dados fictícios", html)
        self.assertIn("Marketplace/dropshipping", html)
        self.assertIn("@media(max-width:760px)", html)
        self.assertIn("@media(max-width:430px)", html)
        self.assertEqual(html.count('class="aqb-card"'), 4)
        self.assertEqual(html.count('class="aqb-package"'), 4)
        self.assertEqual(html.count('class="aqb-step"'), len(CLIENT_JOURNEY))
        self.assertNotIn("href=", html)
        self.assertNotIn("<form", html)

    def test_module_has_no_network_process_or_external_sdk_imports(self):
        source = Path("atlasquant_aion_business_demo.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        names = []
        for node in tree.body:
            if isinstance(node, ast.Import):
                names.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                names.append(node.module or "")
        for banned in ("requests", "urllib", "httpx", "socket", "subprocess", "openai", "streamlit"):
            self.assertNotIn(banned, names)


if __name__ == "__main__":
    unittest.main()
