import unittest
from pathlib import Path


class AtlasQuantAionEventRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.autopilot=Path("autopilot_v107.py").read_text(encoding="utf-8")
        cls.app=Path("usd_macro_pro_v4_cloud.py").read_text(encoding="utf-8")
        cls.admin=Path("atlasquant_aion_admin.py").read_text(encoding="utf-8")

    def test_autopilot_reuses_existing_news_without_extra_provider_request(self):
        self.assertIn("AION_EVENT_INTELLIGENCE_PATH",self.autopilot)
        self.assertIn("build_event_intelligence(",self.autopilot)
        self.assertIn("news_payload=intel",self.autopilot)
        self.assertIn('"performs_extra_provider_request":False',self.autopilot)
        self.assertIn('"external_notification_allowed":False',self.autopilot)
        self.assertIn('"real_orders_enabled":False',self.autopilot)

    def test_autopilot_persists_event_and_alert_journal_on_runtime_branch(self):
        self.assertIn('"dados/aion_event_intelligence_v1.json"',self.autopilot)
        self.assertIn("merge_event_journal(",self.autopilot)
        self.assertIn("merge_alert_journal(",self.autopilot)
        self.assertIn("event_intelligence_summary(",self.autopilot)
        self.assertIn("gh_put_json(",self.autopilot)
        self.assertIn('"aion_event_intelligence"',self.autopilot)

    def test_app_reads_background_event_runtime_and_exposes_it_to_aion(self):
        self.assertIn('"dados/aion_event_intelligence_v1.json"',self.app)
        self.assertIn("event_current = build_event_intelligence(",self.app)
        self.assertIn("journal_events",self.app)
        self.assertIn("journal_alerts",self.app)
        self.assertIn('"event_intelligence": _aion_event_intelligence',self.app)

    def test_reliability_governs_alerts_before_executive_pulse(self):
        reliability=self.admin.index("final_reliability = reliability_snapshot(")
        govern=self.admin.index("govern_event_alerts(",reliability)
        pulse=self.admin.index("executive_snapshot = executive_pulse(",govern)
        self.assertLess(reliability,govern)
        self.assertLess(govern,pulse)
        self.assertIn("event_intelligence_snapshot=event_intelligence_state",self.admin)

    def test_external_notification_and_market_execution_remain_blocked(self):
        self.assertIn("push externo: NÃO CONECTADO",self.admin)
        self.assertIn("Notificação externa automática: DESLIGADA",self.admin)
        self.assertIn("ordens reais: BLOQUEADAS",self.admin)
        self.assertIn('"event_intelligence_external_notifications": False',self.admin)


if __name__=="__main__":
    unittest.main()
