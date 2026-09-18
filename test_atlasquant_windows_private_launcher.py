from pathlib import Path
import unittest


class WindowsPrivateLauncherTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bat = Path("AtlasQuant_Windows_Privado.bat").read_text(
            encoding="utf-8", errors="strict"
        )
        cls.ps1 = Path("AtlasQuant_Windows_Privado.ps1").read_text(
            encoding="utf-8", errors="strict"
        )

    def test_batch_is_only_a_robust_wrapper(self):
        self.assertIn("AtlasQuant_Windows_Privado.ps1", self.bat)
        self.assertIn("powershell -NoProfile -ExecutionPolicy Bypass", self.bat)
        self.assertNotIn("goto instalar", self.bat.lower())

    def test_launcher_keeps_streamlit_local_only(self):
        self.assertIn('"--server.address", "127.0.0.1"', self.ps1)
        self.assertNotIn('"--server.address", "0.0.0.0"', self.ps1)

    def test_launcher_uses_isolated_environment(self):
        self.assertIn(".venv\\Scripts\\python.exe", self.ps1)
        self.assertIn("-m venv .venv", self.ps1)
        self.assertIn("-r requirements.txt", self.ps1)

    def test_launcher_targets_atlasquant_entrypoint(self):
        self.assertIn("usd_macro_pro_v4_cloud.py", self.ps1)
        self.assertIn("ATLASQUANT - WINDOWS PRIVADO", self.ps1)

    def test_launcher_does_not_install_or_call_broker_tools(self):
        lowered = (self.bat + "\n" + self.ps1).lower()
        for forbidden in ("metatrader", "mt5", "broker api", "place_order", "send_order"):
            self.assertNotIn(forbidden, lowered)

    def test_launcher_offers_twelve_data_local_setup(self):
        self.assertIn("Configurar Twelve Data local", self.ps1)
        self.assertIn("AtlasQuant_Configurar_TwelveData.ps1", self.ps1)

    def test_launcher_keeps_window_open_on_errors(self):
        self.assertIn("A janela permanecera aberta para voce poder ler o erro.", self.ps1)
        self.assertIn("Pause-AtlasQuant", self.ps1)

    def test_launcher_runs_streamlit_in_background(self):
        self.assertIn("Start-Process -FilePath $python", self.ps1)
        self.assertIn(".atlasquant_streamlit.pid", self.ps1)
        self.assertIn("Get-AtlasQuantProcess", self.ps1)
        self.assertIn("Stop-AtlasQuant", self.ps1)
        self.assertIn("Voce pode fechar este launcher; o AtlasQuant continuara rodando.", self.ps1)

    def test_launcher_injects_local_twelve_secret_into_child_environment(self):
        self.assertIn("function Import-AtlasQuantLocalSecrets", self.ps1)
        self.assertIn("$env:CHAVE_TWELVE_DATA = $value", self.ps1)
        self.assertIn("[OK] Twelve Data local carregado para esta sessao.", self.ps1)
        self.assertNotIn("setx CHAVE_TWELVE_DATA", self.ps1)


if __name__ == "__main__":
    unittest.main()


class TwelveDataConfiguratorEncodingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.script = Path("AtlasQuant_Configurar_TwelveData.ps1").read_text(encoding="utf-8")

    def test_twelve_data_secret_uses_utf8_without_bom(self):
        self.assertIn("UTF8Encoding($false)", self.script)
        self.assertIn("WriteAllLines", self.script)
        self.assertNotIn("Set-Content -Path $secretsPath -Value $output -Encoding UTF8", self.script)
