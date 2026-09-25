import unittest
from pathlib import Path


class AtlasQuantAionSourceMeshRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.src=Path("usd_macro_pro_v4_cloud.py").read_text(encoding="utf-8")

    def test_app_imports_source_mesh_contract(self):
        self.assertIn(
            "from atlasquant_aion_source_mesh import source_mesh_snapshot",
            self.src,
        )

    def test_aion_reads_runtime_status_and_news_with_existing_runtime_reader(self):
        self.assertIn(
            '"dados/autopilot_status_v107.json"',
            self.src,
        )
        self.assertIn(
            '"dados/currency_news_current_v107.json"',
            self.src,
        )
        self.assertIn("_github_get_json_v937(",self.src)

    def test_aion_source_mesh_uses_existing_macro_calendar_and_pair_matrix_evidence(self):
        self.assertIn("mesh = source_mesh_snapshot(",self.src)
        self.assertIn("macro_us=macro_eua",self.src)
        self.assertIn("next_event=_aion_next_event",self.src)
        self.assertIn("pair_matrix_status=_aion_pair_matrix_status",self.src)
        self.assertIn("autopilot_status=",self.src)

    def test_live_market_context_comes_only_from_mesh_confirmation(self):
        self.assertIn(
            'market_live = bool(mesh.get("market_live_confirmed", False))',
            self.src,
        )
        self.assertIn('"fresh_confirmed": market_live',self.src)
        self.assertIn('"source_mesh": _aion_source_mesh',self.src)
        self.assertIn('"source_observations": list(_aion_source_mesh.get("observations", []) or [])',self.src)

    def test_fed_news_is_explicitly_inference_not_official_fact(self):
        self.assertIn('"source": "Fed Narrative RSS"',self.src)
        self.assertIn(
            '"truth_state": "INFERENCE" if fed_headlines > 0 else "UNKNOWN"',
            self.src,
        )
        self.assertIn(
            "Leitura heurística de narrativa; não é comunicado oficial nem fato de mercado.",
            self.src,
        )


if __name__=="__main__":
    unittest.main()
