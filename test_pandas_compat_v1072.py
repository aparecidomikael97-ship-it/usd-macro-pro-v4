import unittest
from pathlib import Path
import pandas as pd
import numpy as np

class PandasCompatV1072Tests(unittest.TestCase):
    def test_timestamp_assignment_problem_is_reproduced_and_fix_is_present(self):
        # Reproduz o cenário: CSV vazio pode inferir float64 para data_saida.
        df = pd.DataFrame({
            "data_saida": [np.nan],
            "preco_saida": [np.nan],
            "retorno_pct": [np.nan],
            "acertou": [np.nan],
            "avaliado": [False],
        })

        # Normalização equivalente à V10.7.2.
        df["data_saida"] = pd.to_datetime(df["data_saida"], errors="coerce", utc=True)
        df["acertou"] = df["acertou"].astype("object")

        ts = pd.Timestamp("2026-09-14T20:00:00Z")
        df.at[0, "data_saida"] = ts
        df.at[0, "acertou"] = True

        self.assertEqual(df.at[0, "data_saida"], ts)
        self.assertIs(df.at[0, "acertou"], True)

    def test_source_contains_v1072_normalizer(self):
        source = Path("usd_macro_pro_v4_cloud.py").read_text(encoding="utf-8")
        self.assertIn("def _normalizar_tipos_sinais_v1072", source)
        self.assertIn('df.at[i, "data_saida"] = pd.to_datetime(dt_saida, utc=True)', source)

if __name__ == "__main__":
    unittest.main()
