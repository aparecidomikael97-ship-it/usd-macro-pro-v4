import unittest

from atlasquant_layer_consensus import build_layer_consensus


def layer(name, balance, quality=80, available=True):
    return {"id": name, "available": available, "balance": balance, "quality": quality}


class LayerConsensusTests(unittest.TestCase):
    def test_directional_consensus_is_advisory_only(self):
        out = build_layer_consensus({"research_balance": 42, "layers": [
            layer("macro", 55), layer("geopolitics", 20), layer("technical_flow", 45)
        ]})
        self.assertEqual(out["research_state"], "COMPRA")
        self.assertGreater(out["agreement_pct"], 60)
        self.assertTrue(out["advisory_only"])
        self.assertFalse(out["changes_score_mestre"])
        self.assertFalse(out["changes_gate"])
        self.assertFalse(out["real_orders_enabled"])

    def test_less_than_two_layers_fails_closed(self):
        out = build_layer_consensus({"research_balance": 80, "layers": [
            layer("macro", 80), layer("geopolitics", 0, available=False)
        ]})
        self.assertEqual(out["research_state"], "NÃO OPERAR")
        self.assertTrue(any("INSUFICIENTE" in x for x in out["blockers"]))

    def test_low_evidence_floor_fails_closed(self):
        out = build_layer_consensus({"research_balance": -50, "layers": [
            layer("macro", -60, 90), layer("technical_flow", -55, 20)
        ]})
        self.assertEqual(out["research_state"], "NÃO OPERAR")
        self.assertTrue(any("QUALIDADE" in x for x in out["blockers"]))

    def test_strong_cross_layer_conflict_fails_closed(self):
        out = build_layer_consensus({"research_balance": 18, "layers": [
            layer("macro", 70), layer("geopolitics", -65), layer("technical_flow", 40)
        ]})
        self.assertEqual(out["research_state"], "NÃO OPERAR")
        self.assertTrue(any("CONFLITO" in x for x in out["blockers"]))

    def test_neutral_without_blockers_waits(self):
        out = build_layer_consensus({"research_balance": 8, "layers": [
            layer("macro", 10), layer("technical_flow", 6)
        ]})
        self.assertEqual(out["research_state"], "AGUARDAR")
        self.assertEqual(out["research_direction"], "NEUTRO")


if __name__ == "__main__":
    unittest.main()
