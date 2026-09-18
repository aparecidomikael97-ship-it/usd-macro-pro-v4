from pathlib import Path
import unittest


class WindowsPrivateLauncherTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = Path("AtlasQuant_Windows_Privado.bat").read_text(
            encoding="utf-8", errors="strict"
        )

    def test_launcher_keeps_streamlit_local_only(self):
        self.assertIn("--server.address 127.0.0.1", self.text)
        self.assertNotIn("--server.address 0.0.0.0", self.text)

    def test_launcher_uses_isolated_environment(self):
        self.assertIn(".venv\\Scripts\\python.exe", self.text)
        self.assertIn("-m venv .venv", self.text)
        self.assertIn("-r requirements.txt", self.text)

    def test_launcher_targets_atlasquant_entrypoint(self):
        self.assertIn('usd_macro_pro_v4_cloud.py', self.text)
        self.assertIn("ATLASQUANT - WINDOWS PRIVADO", self.text)

    def test_launcher_does_not_install_or_call_broker_tools(self):
        lowered = self.text.lower()
        for forbidden in ("metatrader", "mt5", "broker api", "place_order", "send_order"):
            self.assertNotIn(forbidden, lowered)

    def test_launcher_offers_twelve_data_local_setup(self):
        self.assertIn("Configurar Twelve Data local", self.text)
        self.assertIn("AtlasQuant_Configurar_TwelveData.ps1", self.text)


if __name__ == "__main__":
    unittest.main()
