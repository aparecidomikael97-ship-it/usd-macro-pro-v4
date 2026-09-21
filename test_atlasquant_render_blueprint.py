import unittest
from pathlib import Path


class AtlasQuantRenderBlueprintContractTests(unittest.TestCase):
    def setUp(self):
        self.text=Path("render.yaml").read_text(encoding="utf-8")

    def test_production_service_is_pinned_to_main(self):
        self.assertIn("name: atlasquant-private",self.text)
        self.assertIn("branch: main",self.text)
        self.assertIn("autoDeployTrigger: checksPass",self.text)

    def test_streamlit_commands_and_health_are_explicit(self):
        self.assertIn("pip install -r requirements.txt",self.text)
        self.assertIn("streamlit run usd_macro_pro_v4_cloud.py",self.text)
        self.assertIn("--server.address 0.0.0.0",self.text)
        self.assertIn("--server.port $PORT",self.text)
        self.assertIn("healthCheckPath: /_stcore/health",self.text)

    def test_blueprint_contains_no_known_secret_material(self):
        lowered=self.text.lower()
        for forbidden in ("api_key:", "token:", "password:", "secret:"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden,lowered)


if __name__=="__main__":
    unittest.main()
