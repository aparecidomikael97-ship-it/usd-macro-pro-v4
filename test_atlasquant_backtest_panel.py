import unittest
import pandas as pd

from atlasquant_backtest_panel import (
    read_csv_bytes,
    normalize_tradingview_candles,
    normalize_signal_sheet,
    signal_template_csv,
    candles_template_csv,
)


class BacktestPanelTests(unittest.TestCase):
    def test_tradingview_time_alias_is_normalized(self):
        raw=pd.DataFrame({
            "time":["2026-09-15T00:00:00Z"],
            "open":[1.1],"high":[1.2],"low":[1.0],"close":[1.15],
        })
        out=normalize_tradingview_candles(raw)
        self.assertEqual(list(out.columns),["datetime","open","high","low","close"])
        self.assertEqual(len(out),1)

    def test_portuguese_candle_aliases_are_normalized(self):
        raw=pd.DataFrame({
            "data":["2026-09-15T00:00:00Z"],
            "abertura":[1.1],"máxima":[1.2],"mínima":[1.0],"fechamento":[1.15],
        })
        out=normalize_tradingview_candles(raw)
        self.assertEqual(len(out),1)
        self.assertAlmostEqual(out.iloc[0]["close"],1.15)

    def test_signal_sheet_accepts_portuguese_aliases(self):
        raw=pd.DataFrame({
            "data_hora":["2026-09-15T00:00:00Z"],
            "par":["EUR/USD"],
            "operacional":["OB+CHOCH"],
            "sessão":["Londres"],
            "direção":["COMPRA"],
            "entrada":[1.10],"sl":[1.09],"alvo":[1.12],
        })
        out=normalize_signal_sheet(raw)
        self.assertEqual(out.iloc[0]["side"],"BUY")
        self.assertEqual(out.iloc[0]["setup"],"OB+CHOCH")
        self.assertEqual(out.iloc[0]["pair"],"EUR/USD")

    def test_default_pair_fills_missing_pair(self):
        raw=pd.DataFrame({
            "signal_time":["2026-09-15T00:00:00Z"],
            "side":["SELL"],"entry":[1.10],"stop":[1.11],"target":[1.08],
        })
        out=normalize_signal_sheet(raw,default_pair="GBP/USD")
        self.assertEqual(out.iloc[0]["pair"],"GBP/USD")

    def test_missing_required_signal_columns_fails_closed(self):
        raw=pd.DataFrame({"side":["BUY"],"entry":[1.1]})
        out=normalize_signal_sheet(raw,default_pair="EUR/USD")
        self.assertTrue(out.empty)

    def test_templates_have_only_headers(self):
        self.assertEqual(signal_template_csv().count("\n"),1)
        self.assertIn("signal_time",signal_template_csv())
        self.assertEqual(candles_template_csv().count("\n"),1)
        self.assertIn("datetime",candles_template_csv())

    def test_csv_bytes_read_utf8(self):
        raw=b"time,open,high,low,close\n2026-09-15T00:00:00Z,1,2,0.5,1.5\n"
        out=read_csv_bytes(raw)
        self.assertEqual(len(out),1)
        self.assertIn("time",out.columns)


if __name__=="__main__":
    unittest.main()
