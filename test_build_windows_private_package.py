import unittest

import build_windows_private_package as pkg


class WindowsPrivatePackageTests(unittest.TestCase):
    def test_secret_and_dev_paths_are_blocked(self):
        blocked = (
            ".env",
            ".streamlit/secrets.toml",
            ".github/workflows/quality-tests.yml",
            "docs/release/checklist.md",
            "test_engine.py",
            ".venv/Scripts/python.exe",
            "private.key",
            "credentials.json",
        )
        for path in blocked:
            with self.subTest(path=path):
                self.assertFalse(pkg.is_safe_package_path(path))

    def test_runtime_source_paths_remain_allowed(self):
        allowed = (
            "usd_macro_pro_v4_cloud.py",
            "requirements.txt",
            "AtlasQuant_Windows_Privado.bat",
            "atlasquant_ui_v1.py",
            "tradingview/atlasquant_fvg_strategy_v1.pine",
            "dados/example.json",
        )
        for path in allowed:
            with self.subTest(path=path):
                self.assertTrue(pkg.is_safe_package_path(path))

    def test_readme_states_local_only_and_no_real_orders(self):
        text = pkg.readme_text()
        self.assertIn("127.0.0.1:8501", text)
        self.assertIn("não ativa envio de ordens reais", text)
        self.assertIn("não contém chaves de API", text)


if __name__ == "__main__":
    unittest.main()
