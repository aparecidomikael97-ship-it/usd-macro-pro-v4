import pathlib
import unittest


ROOT=pathlib.Path(__file__).resolve().parent


class AtlasQuantQuotaShadowPanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.src=(ROOT/"autopilot_panel_v107.py").read_text(encoding="utf-8")

    def test_panel_exposes_quota_shadow_section(self):
        self.assertIn("28FX — Quota Shadow",self.src)
        self.assertIn('status.get("quota_shadow"',self.src)

    def test_panel_keeps_auto_expansion_disabled_message(self):
        self.assertIn("Auto-expansão: DESATIVADA",self.src)
        self.assertIn("Nenhuma expansão automática é permitida.",self.src)

    def test_panel_shows_manual_review_state(self):
        self.assertIn('"Revisão manual"',self.src)
        self.assertIn('"ELEGÍVEL"',self.src)
        self.assertIn('"AGUARDANDO"',self.src)


if __name__=="__main__":
    unittest.main()
