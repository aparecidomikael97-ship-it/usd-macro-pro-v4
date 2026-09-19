import unittest
from pathlib import Path

class AtlasQuantReleaseDocumentationTests(unittest.TestCase):
    def test_final_docs_do_not_fake_public_launch_or_real_trading(self):
        paths=[
            Path("README.md"),
            Path("docs/release/ATLASQUANT_RELEASE_FINAL.md"),
            Path("docs/release/FINAL_ACCEPTANCE_MATRIX.md"),
            Path("docs/release/EXTERNAL_DEPENDENCY_HANDOFF.md"),
        ]
        for path in paths:
            with self.subTest(path=str(path)):
                self.assertTrue(path.is_file())
                text=path.read_text(encoding="utf-8").casefold()
                self.assertIn("ordens reais",text)
                self.assertTrue(
                    "dependências externas" in text
                    or "dependencias externas" in text
                    or "ação externa necessária" in text
                )

    def test_store_and_provider_templates_never_request_secret_values_in_repo(self):
        paths=[
            Path("docs/release/PROVIDER_SETUP_TEMPLATE.md"),
            Path("native/README.md"),
            Path("native/android/PACKAGING_CHECKLIST.md"),
            Path("native/apple/PACKAGING_CHECKLIST.md"),
        ]
        joined="\n".join(p.read_text(encoding="utf-8") for p in paths).casefold()
        self.assertIn("nunca",joined)
        self.assertIn("secret",joined)
        self.assertIn("fora do repositório",joined)
        self.assertNotIn("api_key=",joined)

if __name__=="__main__":
    unittest.main()
