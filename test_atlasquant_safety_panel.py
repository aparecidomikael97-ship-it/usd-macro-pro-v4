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


if __name__=="__main__":
    unittest.main()
