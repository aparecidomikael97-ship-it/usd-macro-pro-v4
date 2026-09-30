import ast
import unittest
from pathlib import Path

from atlasquant_aion_business_client_portal_demo import (
    SECTIONS,
    append_demo_history,
    build_client_portal_demo,
    portal_attention_summary,
    portal_section,
)
from atlasquant_aion_business_proposal_simulator import (
    build_proposal_draft,
    client_radar,
    diagnose_business,
    recommend_package,
)


def _fixture():
    raw = {
        "company_name": "Clínica Horizonte Demo",
        "segment": "Clínica",
        "channels": ["WhatsApp", "Instagram"],
        "goals": ["reduzir demora", "recuperar leads"],
        "weekly_leads": 120,
        "avg_response_hours": 4.5,
        "abandoned_quotes_monthly": 18,
        "returning_customers_pct": 14,
        "content_posts_monthly": 2,
        "has_followup_process": False,
        "has_crm": False,
        "has_sla": False,
        "tracks_conversion": False,
    }
    diagnostic = diagnose_business(raw)
    fit = recommend_package(diagnostic)
    radar = client_radar(diagnostic)
    proposal = build_proposal_draft(diagnostic, fit)
    return diagnostic, radar, fit, proposal


class BusinessClientPortalDemoTests(unittest.TestCase):
    def test_portal_is_simple_demo_and_runtime_off(self):
        diagnostic, radar, fit, proposal = _fixture()
        portal = build_client_portal_demo(diagnostic, radar, fit, proposal)
        self.assertEqual(portal["mode"], "DEMO_ONLY")
        self.assertEqual(portal["company"], "Clínica Horizonte Demo")
        self.assertEqual(portal["tagline"], "Poderoso por dentro. Simples por fora.")
        self.assertEqual(portal["sections"], list(SECTIONS))
        self.assertEqual(portal["runtime_state"], "OFF")
        self.assertEqual(portal["external_actions_state"], "OFF")
        self.assertEqual(portal["payment_state"], "OFF")
        self.assertEqual(portal["publication_state"], "OFF")
        self.assertFalse(portal["executes_action"])
        self.assertFalse(portal["data_state"]["real_client_connected"])
        self.assertFalse(portal["data_state"]["real_client_verified"])
        self.assertTrue(portal["data_state"]["demo_fixture_only"])

    def test_portal_has_four_radar_cards_and_action_plan(self):
        diagnostic, radar, fit, proposal = _fixture()
        portal = build_client_portal_demo(diagnostic, radar, fit, proposal)
        self.assertEqual(len(portal["radar"]["cards"]), 4)
        self.assertGreaterEqual(len(portal["action_plan"]), 3)
        self.assertTrue(all(item["status"] == "PENDING_REVIEW" for item in portal["action_plan"]))
        self.assertEqual(portal["radar"]["source"], "DEMO_USER_INPUT")

    def test_portal_never_fabricates_real_results(self):
        diagnostic, radar, fit, proposal = _fixture()
        portal = build_client_portal_demo(diagnostic, radar, fit, proposal)
        results = portal["results"]
        self.assertEqual(results["state"], "NO_REAL_RESULTS")
        self.assertEqual(results["metrics"], [])
        self.assertIn("não inventa desempenho", results["message"])

    def test_attention_summary_is_derived_from_action_plan_only(self):
        diagnostic, radar, fit, proposal = _fixture()
        portal = build_client_portal_demo(diagnostic, radar, fit, proposal)
        summary = portal_attention_summary(portal)
        self.assertIn(summary["state"], {"CRITICAL", "ATTENTION", "WATCH", "STABLE"})
        self.assertEqual(summary["pending_actions"], len(portal["action_plan"]))
        self.assertFalse(summary["executes_action"])

    def test_each_known_section_is_available_and_unknown_fails_closed(self):
        diagnostic, radar, fit, proposal = _fixture()
        portal = build_client_portal_demo(diagnostic, radar, fit, proposal)
        for section in SECTIONS:
            with self.subTest(section=section):
                result = portal_section(portal, section)
                self.assertEqual(result["state"], "DEMO")
                self.assertEqual(result["section"], section)
                self.assertFalse(result["executes_action"])
                self.assertEqual(result["runtime_state"], "OFF")
        unknown = portal_section(portal, "Financeiro secreto")
        self.assertEqual(unknown["state"], "UNKNOWN_SECTION")
        self.assertEqual(unknown["payload"], {})
        self.assertFalse(unknown["executes_action"])

    def test_history_append_is_copy_only_and_keeps_runtime_off(self):
        diagnostic, radar, fit, proposal = _fixture()
        portal = build_client_portal_demo(diagnostic, radar, fit, proposal)
        original_count = len(portal["history"])
        updated = append_demo_history(
            portal,
            event="RADAR_REVIEWED",
            label="Radar fictício revisado no treinamento",
        )
        self.assertEqual(len(portal["history"]), original_count)
        self.assertEqual(len(updated["history"]), original_count + 1)
        self.assertEqual(updated["history"][-1]["event"], "RADAR_REVIEWED")
        self.assertEqual(updated["runtime_state"], "OFF")
        self.assertEqual(updated["external_actions_state"], "OFF")
        self.assertFalse(updated["executes_action"])

    def test_module_has_no_external_io_or_provider_imports(self):
        source = Path("atlasquant_aion_business_client_portal_demo.py").read_text(encoding="utf-8")
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
