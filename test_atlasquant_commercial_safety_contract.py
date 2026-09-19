import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parent

class AtlasQuantCommercialSafetyContractTests(unittest.TestCase):
    def sources(self):
        return [
            ROOT/"atlasquant_access_control.py",
            ROOT/"atlasquant_access_panel.py",
            ROOT/"atlasquant_account_portal.py",
            ROOT/"atlasquant_registry_admin.py",
            ROOT/"atlasquant_sales_center.py",
            ROOT/"atlasquant_commercial_launch_guard.py",
        ]

    def test_commercial_modules_do_not_enable_live_trading(self):
        joined="\n".join(p.read_text(encoding="utf-8") for p in self.sources())
        forbidden=(
            "real_orders=True",
            "broker_connection=True",
            "automatic_gate_change=True",
            "automatic_promotion=True",
            "automatic_launch=True",
        )
        for token in forbidden:
            with self.subTest(token=token):
                self.assertNotIn(token,joined)

    def test_account_and_sales_modules_do_not_write_streamlit_secrets(self):
        joined="\n".join(p.read_text(encoding="utf-8") for p in self.sources())
        self.assertNotIn("st.secrets[",joined)
        self.assertNotIn("st.secrets.update",joined)

    def test_registry_and_sales_core_are_network_free(self):
        for name in (
            "atlasquant_registry_admin.py",
            "atlasquant_commercial_launch_guard.py",
        ):
            src=(ROOT/name).read_text(encoding="utf-8")
            with self.subTest(name=name):
                self.assertNotIn("requests.",src)
                self.assertNotIn("httpx.",src)
                self.assertNotIn("urllib.request",src)

if __name__=="__main__":
    unittest.main()
