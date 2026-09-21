import tempfile
import unittest
from pathlib import Path

from atlasquant_build_identity import source_fingerprint, short_source_fingerprint


class AtlasQuantBuildIdentityTests(unittest.TestCase):
    def test_fingerprint_is_deterministic_and_changes_with_executable_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/"a.py").write_text("A=1\n",encoding="utf-8")
            (root/"requirements.txt").write_text("streamlit\n",encoding="utf-8")
            first=source_fingerprint(root)
            self.assertEqual(first,source_fingerprint(root))
            (root/"a.py").write_text("A=2\n",encoding="utf-8")
            self.assertNotEqual(first,source_fingerprint(root))

    def test_tests_and_runtime_data_do_not_change_production_bundle_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/"app.py").write_text("VALUE=1\n",encoding="utf-8")
            first=source_fingerprint(root)
            (root/"test_app.py").write_text("assert True\n",encoding="utf-8")
            (root/"dados").mkdir()
            (root/"dados"/"runtime.json").write_text('{"x":1}',encoding="utf-8")
            self.assertEqual(first,source_fingerprint(root))

    def test_short_identity_is_safe_non_secret_hex(self):
        value=short_source_fingerprint(Path(__file__).resolve().parent,16)
        self.assertEqual(len(value),16)
        self.assertTrue(all(ch in "0123456789abcdef" for ch in value))


if __name__=="__main__":
    unittest.main()
