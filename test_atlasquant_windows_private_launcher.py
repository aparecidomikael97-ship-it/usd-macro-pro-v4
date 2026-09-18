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

    def test_launcher_keeps_private_default_and_explicit_mobile_lan_mode(self):
        self.assertIn('"--server.address", "127.0.0.1"', self.ps1)
        self.assertIn("function Start-AtlasQuantMobile", self.ps1)
        self.assertIn('"--server.address", $lanIp', self.ps1)
        self.assertIn('$mobileUrl = "http://" + $lanIp + ":8501"', self.ps1)
        self.assertIn("NAO use localhost ou 127.0.0.1", self.ps1)
        self.assertNotIn('"--server.address", "0.0.0.0"', self.ps1)
        self.assertIn("Continuar? (S/N)", self.ps1)
        self.assertIn("Use somente em uma rede Wi-Fi confiavel.", self.ps1)
        self.assertIn("Nao encaminhe a porta 8501 no roteador", self.ps1)
        self.assertIn("Iniciar modo celular - Wi-Fi local", self.ps1)

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

    def test_launcher_offers_fred_local_setup(self):
        self.assertIn("Configurar FRED local", self.ps1)
        self.assertIn("AtlasQuant_Configurar_FRED.ps1", self.ps1)
        self.assertIn("$env:CHAVE_FRED = $fred", self.ps1)
        self.assertIn("[OK] FRED local carregado para esta sessao.", self.ps1)

    def test_launcher_uses_persistent_user_secret_store(self):
        self.assertIn('Join-Path $env:LOCALAPPDATA "AtlasQuant"', self.ps1)
        self.assertIn('$stablePath', self.ps1)
        self.assertIn('$legacyPath', self.ps1)

    def test_launcher_reads_persistent_keys_with_native_powershell(self):
        self.assertIn('Get-Content -LiteralPath $secretsPath', self.ps1)
        self.assertIn('StartsWith($Name + " =")', self.ps1)
        self.assertIn('$parts = $line -split "=", 2', self.ps1)
        self.assertNotIn('tomllib.loads', self.ps1)

    def test_launcher_loads_all_four_api_keys(self):
        self.assertIn('$env:CHAVE_FRED = $fred', self.ps1)
        self.assertIn('$env:CHAVE_TWELVE_DATA = $twelve', self.ps1)
        self.assertIn('$env:CHAVE_EODHD = $eodhd', self.ps1)
        self.assertIn('$env:CHAVE_NEWSAPI = $newsapi', self.ps1)
        self.assertIn("Configurar as 4 APIs locais", self.ps1)
        self.assertIn("AtlasQuant_Configurar_APIs.ps1", self.ps1)

    def test_launcher_keeps_window_open_on_errors(self):
        self.assertIn("A janela permanecera aberta para voce poder ler o erro.", self.ps1)
        self.assertIn("Pause-AtlasQuant", self.ps1)

    def test_launcher_replaces_stale_atlasquant_on_port_8501(self):
        self.assertIn("Get-NetTCPConnection -LocalPort 8501", self.ps1)
        self.assertIn("Get-CimInstance Win32_Process", self.ps1)
        self.assertIn('cmd -match "streamlit"', self.ps1)
        self.assertIn('cmd -match "usd_macro_pro_v4_cloud.py"', self.ps1)
        self.assertIn("AtlasQuant anterior detectado na porta 8501", self.ps1)
        self.assertIn("Get-AtlasQuantPidFile", self.ps1)

    def test_launcher_runs_streamlit_in_background(self):
        self.assertIn("Start-Process -FilePath $python", self.ps1)
        self.assertIn(".atlasquant_streamlit.pid", self.ps1)
        self.assertIn("Get-AtlasQuantProcess", self.ps1)
        self.assertIn("Stop-AtlasQuant", self.ps1)
        self.assertIn("Voce pode fechar este launcher; o AtlasQuant continuara rodando.", self.ps1)

    def test_launcher_injects_local_twelve_secret_into_child_environment(self):
        self.assertIn("function Import-AtlasQuantLocalSecrets", self.ps1)
        self.assertIn("$env:CHAVE_TWELVE_DATA = $twelve", self.ps1)
        self.assertIn("[OK] Twelve Data local carregado para esta sessao.", self.ps1)
        self.assertNotIn("setx CHAVE_TWELVE_DATA", self.ps1)


if __name__ == "__main__":
    unittest.main()


class PersistentSecretConfiguratorTests(unittest.TestCase):
    def test_configurators_store_secrets_outside_build_folder(self):
        twelve = Path("AtlasQuant_Configurar_TwelveData.ps1").read_text(encoding="utf-8")
        fred = Path("AtlasQuant_Configurar_FRED.ps1").read_text(encoding="utf-8")
        all_apis = Path("AtlasQuant_Configurar_APIs.ps1").read_text(encoding="utf-8")
        for script in (twelve, fred, all_apis):
            self.assertIn('Join-Path $env:LOCALAPPDATA "AtlasQuant"', script)
            self.assertNotIn('$streamlitDir = Join-Path $root ".streamlit"', script)

    def test_unified_configurator_contains_all_four_keys(self):
        script = Path("AtlasQuant_Configurar_APIs.ps1").read_text(encoding="utf-8")
        for key in ("CHAVE_FRED", "CHAVE_TWELVE_DATA", "CHAVE_EODHD", "CHAVE_NEWSAPI"):
            self.assertIn(key, script)


class TwelveDataConfiguratorEncodingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.script = Path("AtlasQuant_Configurar_TwelveData.ps1").read_text(encoding="utf-8")

    def test_twelve_data_secret_uses_utf8_without_bom(self):
        self.assertIn("UTF8Encoding($false)", self.script)
        self.assertIn("WriteAllLines", self.script)
        self.assertNotIn("Set-Content -Path $secretsPath -Value $output -Encoding UTF8", self.script)
