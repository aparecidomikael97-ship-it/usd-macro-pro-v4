import unittest

from atlasquant_operational_plan import build_operational_plan


class AtlasQuantOperationalPlanTests(unittest.TestCase):
    def base(self):
        return {
            "pair":"EUR/USD","side":"BUY","direction":"🟢 COMPRA EUR/USD",
            "gate":"READY","m15":"CONFIRMADO","next_action":"Aguardar pullback no FVG",
            "target":"PDH 1.1000","price":1.0950,"event":"NORMAL",
            "data_ready":{"sufficient":True,"score":92},
            "hard_blocks":[],"soft_blocks":[],"executable":False,
        }

    def test_ready_but_not_executable_waits(self):
        p=self.base()
        plan=build_operational_plan(p)
        self.assertEqual(plan["status"],"WAIT")

    def test_executable_ready_searches_only_current_side(self):
        p=self.base(); p["executable"]=True
        plan=build_operational_plan(p)
        self.assertEqual(plan["status"],"SEARCH_ENTRY")
        self.assertIn("compras",plan["instruction"])

    def test_insufficient_data_blocks_even_if_executable(self):
        p=self.base(); p["executable"]=True; p["data_ready"]["sufficient"]=False
        plan=build_operational_plan(p)
        self.assertEqual(plan["status"],"NO_TRADE")

    def test_hard_block_always_blocks(self):
        p=self.base(); p["executable"]=True; p["hard_blocks"]=["M15 stale"]
        self.assertEqual(build_operational_plan(p)["status"],"NO_TRADE")

    def test_existing_target_is_preserved_not_invented(self):
        p=self.base()
        self.assertEqual(build_operational_plan(p)["target"],"PDH 1.1000")
        p["target"]="—"
        self.assertEqual(build_operational_plan(p)["target"],"—")

    def test_no_entry_or_stop_fields_are_invented(self):
        plan=build_operational_plan(self.base())
        self.assertNotIn("entry",plan)
        self.assertNotIn("stop",plan)

    def test_event_risk_is_added_to_invalidation(self):
        p=self.base(); p["event"]="ALTO FOMC"
        joined=" ".join(build_operational_plan(p)["invalidation"])
        self.assertIn("FOMC",joined)


    def test_soft_block_keeps_plan_in_wait_even_if_motor_executable(self):
        p=self.base(); p["executable"]=True; p["soft_blocks"]=["Evento próximo"]
        plan=build_operational_plan(p)
        self.assertEqual(plan["status"],"WAIT")
        self.assertEqual(plan["label"],"AGUARDAR CONFIRMAÇÃO")
        self.assertIn("alerta",plan["instruction"].lower())



if __name__=="__main__":
    unittest.main()
