import unittest
from unittest.mock import patch

import pandas as pd

import usd_macro_pro_v4_cloud as app


class _Resp:
    def __init__(self, text):
        self.text = text


class FredPublicCsvTests(unittest.TestCase):
    def test_public_csv_reads_official_level_without_api_key(self):
        csv = "observation_date,CPIAUCSL\n2025-07-01,320.0\n2026-07-01,329.6\n"
        with patch.object(app, "_get", return_value=_Resp(csv)):
            df = app._fred_csv_publico("CPIAUCSL", limite=12)
        self.assertEqual(len(df), 2)
        self.assertAlmostEqual(float(df.iloc[-1]["value"]), 329.6)
        self.assertEqual(df.attrs.get("fred_source"), "CSV público oficial FRED")

    def test_public_csv_pc1_calculates_year_over_year(self):
        dates = pd.date_range("2025-01-01", periods=13, freq="MS")
        vals = [100.0] * 12 + [103.0]
        csv = "observation_date,CPIAUCSL\n" + "\n".join(
            f"{d.date()},{v}" for d, v in zip(dates, vals)
        ) + "\n"
        with patch.object(app, "_get", return_value=_Resp(csv)):
            df = app._fred_csv_publico("CPIAUCSL", limite=12, unidades="pc1")
        self.assertFalse(df.empty)
        self.assertAlmostEqual(float(df.iloc[-1]["value"]), 3.0, places=6)

    def test_quality_uses_loaded_official_data_not_api_key_presence(self):
        audit = [
            {"Fonte": "CSV público oficial FRED · X", "Status": "🟢 Atual"}
            for _ in range(11)
        ]
        with patch.object(app, "carregar_macro_eua", return_value={"_auditoria": audit}):
            pontos, rotulo = app.qualidade_dados_usd()
        self.assertEqual(pontos, 100)
        self.assertEqual(rotulo, "ALTA")


if __name__ == "__main__":
    unittest.main()
