import unittest
from pathlib import Path


class AtlasQuantAionLiveEventRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.src=Path("usd_macro_pro_v4_cloud.py").read_text(encoding="utf-8")

    def test_app_imports_live_event_intelligence(self):
        self.assertIn(
            "from atlasquant_aion_live_events import live_event_snapshot",
            self.src,
        )

    def test_source_runtime_helper_builds_event_snapshot_from_existing_inputs(self):
        self.assertIn("event_intelligence = live_event_snapshot(",self.src)
        self.assertIn("news_payload=news_payload",self.src)
        self.assertIn("news_provenance=news_source",self.src)
        self.assertIn("next_event=next_event",self.src)
        self.assertIn("return mesh, market_context, event_intelligence",self.src)

    def test_app_overlays_persisted_background_journal(self):
        self.assertIn(
            "from atlasquant_aion_event_journal import overlay_journal",
            self.src,
        )
        self.assertIn('"dados/aion_live_event_journal_v1.json"',self.src)
        self.assertIn("event_intelligence = overlay_journal(",self.src)
        self.assertIn('"background_journal_provenance"',self.src)
        self.assertIn('"background_journal_confirmed"',self.src)

    def test_aion_system_context_receives_live_event_snapshot(self):
        self.assertIn("_aion_live_events",self.src)
        self.assertIn('"live_event_intelligence": _aion_live_events',self.src)

    def test_runtime_does_not_claim_continuous_monitoring(self):
        self.assertNotIn('"continuous_runtime_confirmed": True',self.src)
        self.assertNotIn('"automatic_notification_sent": True',self.src)


if __name__=="__main__":
    unittest.main()
