import inspect
import unittest
import pandas as pd

from atlasquant_backtest_panel import (
    read_csv_bytes,
    normalize_tradingview_candles,
    normalize_signal_sheet,
    signal_template_csv,
    candles_template_csv,
    render_operational_backtest_panel,
    load_tradingview_fvg_pine_asset,
    load_tradingview_ote_pine_asset,
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

    def test_panel_exposes_automatic_replay(self):
        source=inspect.getsource(render_operational_backtest_panel)
        self.assertIn("Rodar backtest automático",source)
        self.assertIn("single_position_per_pair=True",source)
        self.assertIn("generate_bos_choch_ob_signals",source)

    def test_panel_exposes_separate_fvg_replay(self):
        source=inspect.getsource(render_operational_backtest_panel)
        self.assertIn("Rodar backtest FVG",source)
        self.assertIn("generate_fvg_signals",source)
        self.assertIn('key_suffix="fvg"',source)

    def test_fvg_pine_loader_returns_content(self):
        text=load_tradingview_fvg_pine_asset()
        self.assertIn("AtlasQuant FVG Research V1",text)
        self.assertIn("strategy.entry",text)

    def test_panel_exposes_separate_ote_replay(self):
        source=inspect.getsource(render_operational_backtest_panel)
        self.assertIn("Rodar backtest OTE",source)
        self.assertIn("generate_ote_signals",source)
        self.assertIn('key_suffix="ote"',source)

    def test_ote_pine_loader_returns_content(self):
        text=load_tradingview_ote_pine_asset()
        self.assertIn("AtlasQuant OTE Research V1",text)
        self.assertIn("strategy.entry",text)

    def test_csv_bytes_read_utf8(self):
        raw=b"time,open,high,low,close\n2026-09-15T00:00:00Z,1,2,0.5,1.5\n"
        out=read_csv_bytes(raw)
        self.assertEqual(len(out),1)
        self.assertIn("time",out.columns)


if __name__=="__main__":
    unittest.main()
