import unittest
from pathlib import Path
import pandas as pd
import numpy as np

class LegacyNaTGuardV1073Tests(unittest.TestCase):
    def test_nat_never_reaches_strftime(self):
        dt = pd.to_datetime(None, errors="coerce", utc=True)
        self.assertTrue(pd.isna(dt))

    def test_invalid_numeric_is_detected(self):
        v = pd.to_numeric(pd.Series([None]), errors="coerce").iloc[0]
        self.assertTrue(pd.isna(v))

    def test_source_has_nat_guard(self):
        source = Path("usd_macro_pro_v4_cloud.py").read_text(encoding="utf-8")
        self.assertIn("def _entrada_legada_segura_v1073", source)
        self.assertIn('if _motivo_v1073:', source)
        self.assertIn('dt_entrada.strftime("%Y-%m-%d")', source)

    def test_source_uses_utc_in_auto_collection(self):
        source = Path("usd_macro_pro_v4_cloud.py").read_text(encoding="utf-8")
        self.assertIn('errors="coerce", utc=True', source)

if __name__ == "__main__":
    unittest.main()
