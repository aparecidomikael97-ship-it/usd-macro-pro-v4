import unittest

from atlasquant_confluence_map import build_confluence_map, confluence_summary


class AtlasQuantConfluenceMapTests(unittest.TestCase):
    def base(self):
        return {
            "side":"BUY","macro_diff":12,"quality":85,"h4":"CONFIRMA","h1":"CONFIRMA",
            "ict_read":80,"inst_read":78,"event":"NORMAL","gate":"READY","executable":True,
            "hard_blocks":[],"stale_technical":[],
            "ict_fresh":{"ready":True,"label":"ICT ATUAL"},
            "data_ready":{"sufficient":True,"score":92,"institutional_data_ready":True},
        }

    def test_has_seven_layers(self):
        self.assertEqual(len(build_confluence_map(self.base())),7)

    def test_clean_ready_context_has_no_red(self):
        layers=build_confluence_map(self.base())
        self.assertEqual(confluence_summary(layers)["red"],0)

    def test_insufficient_data_is_red(self):
        p=self.base(); p["data_ready"]["sufficient"]=False; p["data_ready"]["score"]=30
        data=[x for x in build_confluence_map(p) if x["name"]=="Dados"][0]
        self.assertEqual(data["status"],"RED")

    def test_stale_topdown_is_red(self):
        p=self.base(); p["stale_technical"]=["H4: old confirmation"]
        top=[x for x in build_confluence_map(p) if x["name"]=="Top-down"][0]
        self.assertEqual(top["status"],"RED")

    def test_high_event_is_red(self):
        p=self.base(); p["event"]="ALTO FOMC"
        event=[x for x in build_confluence_map(p) if x["name"]=="Evento"][0]
        self.assertEqual(event["status"],"RED")

    def test_hard_block_forces_gate_red(self):
        p=self.base(); p["hard_blocks"]=["dados insuficientes"]
        gate=[x for x in build_confluence_map(p) if x["name"]=="Gate final"][0]
        self.assertEqual(gate["status"],"RED")

    def test_non_executable_gate_is_yellow(self):
        p=self.base(); p["executable"]=False
        gate=[x for x in build_confluence_map(p) if x["name"]=="Gate final"][0]
        self.assertEqual(gate["status"],"YELLOW")


if __name__=="__main__":
    unittest.main()
