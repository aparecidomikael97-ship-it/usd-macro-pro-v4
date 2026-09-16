import unittest
from pathlib import Path

from atlasquant_backtest_panel import load_tradingview_pine_asset

ROOT=Path(__file__).resolve().parent
PINE=ROOT/"tradingview"/"atlasquant_bos_choch_ob_strategy_v1.pine"


class TradingViewAssetsTests(unittest.TestCase):
    def test_pine_asset_exists_and_is_strategy(self):
        text=PINE.read_text(encoding="utf-8")
        self.assertIn("//@version=5",text)
        self.assertIn("strategy(",text)
        self.assertIn("strategy.entry",text)
        self.assertIn("strategy.exit",text)

    def test_no_known_lookahead_primitives(self):
        text=PINE.read_text(encoding="utf-8").lower()
        self.assertNotIn("lookahead_on",text)
        self.assertNotIn("barmerge.lookahead",text)
        self.assertNotIn("request.security",text)

    def test_confirmed_pivots_and_structure_are_present(self):
        text=PINE.read_text(encoding="utf-8")
        self.assertIn("ta.pivothigh",text)
        self.assertIn("ta.pivotlow",text)
        self.assertIn("bar_index - rightBars",text)
        self.assertIn("consumedHighBar",text)
        self.assertIn("consumedLowBar",text)
        self.assertIn('"CHOCH"',text)
        self.assertIn('"BOS"',text)

    def test_order_block_and_risk_controls_are_explicit(self):
        text=PINE.read_text(encoding="utf-8")
        self.assertIn("maxOrigin",text)
        self.assertIn("bodyAtrMin",text)
        self.assertIn("rangeAtrMin",text)
        self.assertIn("stopBufferAtr",text)
        self.assertIn("rrTarget",text)
        self.assertIn("pendingEntry",text)
        self.assertIn("pendingStop",text)
        self.assertIn("pendingTarget",text)

    def test_panel_loader_returns_exact_asset(self):
        expected=PINE.read_text(encoding="utf-8")
        self.assertEqual(load_tradingview_pine_asset(),expected)


if __name__=="__main__":
    unittest.main()
