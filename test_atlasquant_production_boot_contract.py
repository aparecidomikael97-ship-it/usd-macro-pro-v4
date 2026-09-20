import unittest
from pathlib import Path


class ProductionBootContractTests(unittest.TestCase):
    def test_autopilot_executes_current_main_code_but_writes_runtime_data(self):
        workflow=Path(".github/workflows/autopilot-v107.yml").read_text(encoding="utf-8")
        self.assertIn("branches: [main]",workflow)
        self.assertNotIn("branches: [atlasquant-runtime]",workflow)
        self.assertIn("ref: main",workflow)
        self.assertIn('GITHUB_DATA_BRANCH: "atlasquant-runtime"',workflow)
        self.assertIn('GITHUB_BRANCH_HISTORICO: "atlasquant-runtime"',workflow)

    def test_autopilot_current_code_builds_fast_home_snapshot(self):
        src=Path("autopilot_v107.py").read_text(encoding="utf-8")
        self.assertIn('HOME_SNAPSHOT_PATH = "dados/atlasquant_home_snapshot_v1.json"',src)
        self.assertIn("build_home_snapshot_payload(",src)
        self.assertIn('status["fast_home_snapshot"]',src)
        self.assertIn("gh_put_json(",src)

    def test_production_smoke_requires_current_home_when_not_at_login(self):
        workflow=Path(".github/workflows/production-browser-smoke.yml").read_text(encoding="utf-8")
        self.assertIn('radar_visible = "Radar de Oportunidades" in body_text',workflow)
        self.assertIn('fast_snapshot_shell = "carregamento rápido por snapshot validado" in body_text',workflow)
        self.assertIn("produção carregou Streamlit, mas não abriu a Home/Radar atual",workflow)
        self.assertIn("Home/Radar demorou",workflow)
        self.assertIn("meaningful_ms > 30000",workflow)
        self.assertIn("Wait for fresh Fast Home snapshot",workflow)
        self.assertIn("atlasquant_home_snapshot_v1.json?ref=atlasquant-runtime",workflow)
        self.assertIn('obj.get("schema")=="ATLASQUANT_HOME_SNAPSHOT_V1"',workflow)

    def test_fast_home_still_precedes_heavy_provider_boot(self):
        src=Path("usd_macro_pro_v4_cloud.py").read_text(encoding="utf-8")
        shell=src.index("load_home_snapshot(")
        macro=src.index("macro_eua = carregar_macro_eua()")
        fed=src.index("fed = carregar_narrativa_fed()")
        currencies=src.index("dados_moedas = carregar_dados_moedas()")
        self.assertLess(shell,macro)
        self.assertLess(shell,fed)
        self.assertLess(shell,currencies)
        self.assertIn('if bool(_fast_result.get("handled",False)):',src[shell:macro])
        self.assertIn("st.stop()",src[shell:macro])


if __name__=="__main__":
    unittest.main()