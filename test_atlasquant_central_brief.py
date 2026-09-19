import unittest

from atlasquant_central_brief import build_central_brief


class AtlasQuantCentralBriefTests(unittest.TestCase):
    def test_green_only_with_executable_and_ready(self):
        packs=[{
            "pair":"EUR/USD","priority":91,"executable":True,"state":"🟢 EXECUTÁVEL",
            "data_ready":{"sufficient":True}
        }]
        b=build_central_brief(packs,{"app_headless_ok":True})
        self.assertEqual(b["traffic_light"],"GREEN")
        self.assertEqual(b["state"],"PROCURAR ENTRADA")
        self.assertEqual(b["executable"],1)

    def test_not_ready_fails_closed(self):
        packs=[{
            "pair":"GBP/USD","priority":99,"executable":True,"state":"🟢 EXECUTÁVEL",
            "data_ready":{"sufficient":False}
        }]
        b=build_central_brief(packs,{})
        self.assertEqual(b["traffic_light"],"RED")
        self.assertEqual(b["state"],"NÃO OPERAR")
        self.assertEqual(b["executable"],0)

    def test_waiting_context_is_yellow(self):
        packs=[{
            "pair":"USD/JPY","priority":80,"executable":False,"state":"🟡 AGUARDAR GATILHO",
            "data_ready":{"sufficient":True}
        }]
        b=build_central_brief(packs,{"app_headless_ok":True})
        self.assertEqual(b["traffic_light"],"YELLOW")
        self.assertEqual(b["state"],"AGUARDAR CONFIRMAÇÃO")

    def test_all_blocked_is_red(self):
        packs=[
            {"pair":"EUR/USD","priority":70,"state":"🔴 BLOQUEADO","data_ready":{"sufficient":True}},
            {"pair":"GBP/USD","priority":60,"state":"🔴 BLOQUEADO","data_ready":{"sufficient":True}},
        ]
        b=build_central_brief(packs,{"app_headless_ok":True})
        self.assertEqual(b["traffic_light"],"RED")
        self.assertEqual(b["blocked"],2)

    def test_reports_process_and_source_health_separately(self):
        b=build_central_brief([],{"app_headless_ok":False,"twelve_daily_blocked":True})
        self.assertFalse(b["process_ok"])
        self.assertTrue(b["source_blocked"])


    def test_executable_pack_is_not_green_when_process_or_source_is_unhealthy(self):
        pack={
            "pair":"EUR/USD","priority":91,"executable":True,"state":"🟢 EXECUTÁVEL",
            "data_ready":{"sufficient":True}
        }
        for auto in (
            {"app_headless_ok":False,"twelve_daily_blocked":False},
            {"app_headless_ok":True,"twelve_daily_blocked":True},
            {},
        ):
            with self.subTest(auto=auto):
                b=build_central_brief([pack],auto)
                self.assertEqual(b["traffic_light"],"RED")
                self.assertEqual(b["state"],"NÃO OPERAR")



if __name__=="__main__":
    unittest.main()
