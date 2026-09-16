import unittest

from atlasquant_safety_panel import build_safety_input, evaluate_live_safety


class AtlasQuantSafetyPanelTests(unittest.TestCase):
    def base(self):
        return {
            "executable":True,
            "stale_technical":False,
            "hard_blocks":[],
            "data_ready":{"sufficient":True,"score":92},
        }

    def test_clean_context_can_be_green(self):
        r=evaluate_live_safety(self.base(),{"app_headless_ok":True,"twelve_daily_blocked":False})
        self.assertEqual(r["traffic_light"],"GREEN")

    def test_source_block_forces_red(self):
        r=evaluate_live_safety(self.base(),{"app_headless_ok":True,"twelve_daily_blocked":True})
        self.assertEqual(r["traffic_light"],"RED")

    def test_unhealthy_update_forces_red(self):
        r=evaluate_live_safety(self.base(),{"app_headless_ok":False})
        self.assertEqual(r["traffic_light"],"RED")

    def test_stale_technical_forces_red(self):
        p=self.base(); p["stale_technical"]=True
        r=evaluate_live_safety(p,{"app_headless_ok":True})
        self.assertEqual(r["traffic_light"],"RED")

    def test_not_executable_but_clean_waits(self):
        p=self.base(); p["executable"]=False
        r=evaluate_live_safety(p,{"app_headless_ok":True})
        self.assertEqual(r["traffic_light"],"YELLOW")

    def test_existing_hard_block_propagates(self):
        p=self.base(); p["hard_blocks"]=["evento bloqueado"]
        r=evaluate_live_safety(p,{"app_headless_ok":True})
        self.assertEqual(r["traffic_light"],"RED")
        self.assertIn("evento bloqueado",r["hard_blocks"])

    def test_adapter_never_uses_priority_as_data_quality(self):
        p=self.base(); p["priority"]=100; p["data_ready"]["score"]=40
        inp=build_safety_input(p,{"app_headless_ok":True})
        self.assertEqual(inp.data_quality,40)

    def test_regime_override_can_only_add_caution(self):
        p=self.base()
        r=evaluate_live_safety(
            p,
            {"app_headless_ok":True},
            regime_supported_override=False,
        )
        self.assertEqual(r["traffic_light"],"YELLOW")
        self.assertIn("Regime atual", " ".join(r["warnings"]))

    def test_exact_event_override_can_block(self):
        p=self.base()
        r=evaluate_live_safety(
            p,
            {"app_headless_ok":True},
            major_event_minutes_override=10,
        )
        self.assertEqual(r["traffic_light"],"RED")
        self.assertTrue(any("Evento de alto impacto" in x for x in r["hard_blocks"]))

    def test_missing_event_override_does_not_invent_block(self):
        p=self.base()
        p.pop("major_event_minutes",None)
        r=evaluate_live_safety(
            p,
            {"app_headless_ok":True},
            major_event_minutes_override=None,
        )
        self.assertNotEqual(r["traffic_light"],"RED")


if __name__=="__main__":
    unittest.main()
