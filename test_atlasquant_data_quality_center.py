import unittest

from atlasquant_data_quality_center import build_data_confidence, data_confidence_visual_state


class AtlasQuantDataConfidenceTests(unittest.TestCase):
    def pack(self, ready=True, score=90, quality=85, age=20, stale=False, event="NORMAL"):
        return {
            "quality":quality,"technical_age":age,"stale_technical":stale,"event":event,
            "data_ready":{"sufficient":ready,"score":score}
        }

    def test_green_requires_strong_readiness_and_healthy_process(self):
        packs=[self.pack() for _ in range(5)]
        s=build_data_confidence(packs,{"app_headless_ok":True,"twelve_daily_blocked":False})
        self.assertEqual(s["status"],"GREEN")
        self.assertEqual(s["ready_pairs"],5)

    def test_zero_ready_is_red(self):
        packs=[self.pack(ready=False,score=40) for _ in range(3)]
        s=build_data_confidence(packs,{"app_headless_ok":True})
        self.assertEqual(s["status"],"RED")

    def test_source_block_prevents_green(self):
        packs=[self.pack() for _ in range(5)]
        s=build_data_confidence(packs,{"app_headless_ok":True,"twelve_daily_blocked":True})
        self.assertEqual(s["status"],"YELLOW")
        self.assertTrue(s["source_blocked"])

    def test_stale_pair_prevents_green(self):
        packs=[self.pack() for _ in range(4)] + [self.pack(stale=True)]
        s=build_data_confidence(packs,{"app_headless_ok":True})
        self.assertEqual(s["status"],"YELLOW")
        self.assertEqual(s["stale_pairs"],1)

    def test_missing_ages_are_counted(self):
        packs=[self.pack(age=None),self.pack(age=30)]
        s=build_data_confidence(packs,{"app_headless_ok":True})
        self.assertEqual(s["missing_age_pairs"],1)
        self.assertEqual(s["oldest_age_min"],30.0)

    def test_event_risk_is_visible_but_not_signal(self):
        packs=[self.pack(event="ALTO FOMC"),self.pack(event="NORMAL")]
        s=build_data_confidence(packs,{"app_headless_ok":True})
        self.assertEqual(s["event_risk_pairs"],1)


    def test_data_confidence_visual_state_never_implies_trade_permission(self):
        self.assertEqual(data_confidence_visual_state({"status":"GREEN"})["label"],"DADOS OPERACIONAIS")
        self.assertEqual(data_confidence_visual_state({"status":"YELLOW"})["label"],"ATENÇÃO NOS DADOS")
        self.assertEqual(data_confidence_visual_state({"status":"RED"})["label"],"DADOS INSUFICIENTES")
        self.assertEqual(data_confidence_visual_state({"status":"UNKNOWN"})["label"],"REVISAR")
        self.assertIn("não é autorização de trade",data_confidence_visual_state({"status":"GREEN"})["detail"])



if __name__=="__main__":
    unittest.main()
