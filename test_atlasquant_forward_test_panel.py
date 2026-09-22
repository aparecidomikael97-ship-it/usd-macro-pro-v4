import unittest
from pathlib import Path

from atlasquant_forward_test_panel import forward_timeframe_rows, forward_setup_rows


class ForwardTestPanelTests(unittest.TestCase):
    def sample(self):
        return {
            "candidates_total":5,
            "closed_trades":1,
            "by_timeframe":{
                "M15":{
                    "candidates":3,"blocked_context":1,"blocked_data":0,"blocked_timeframe":0,"blocked_risk":1,
                    "pending":0,"open":0,"closed":1,"wins":1,"losses":0,"net_r":1.4,
                    "hard_block_reasons":{"Gate bloqueado":2},
                    "soft_block_reasons":{"M15 sem gatilho":1},
                    "timeframe_block_reasons":{"SOURCE_EQUALS_EXECUTION":3},
                },
                "H1":{
                    "candidates":2,"blocked_context":1,"blocked_data":0,"blocked_timeframe":1,"blocked_risk":0,
                    "pending":0,"open":0,"closed":0,"wins":0,"losses":0,"net_r":0.0,
                    "timeframe_block_reasons":{"EXECUTION_FRAME_NOT_AVAILABLE:H1":1},
                },
            },
            "by_setup":{
                "fvg":{"candidates":3,"blocked_context":1,"blocked_timeframe":0,"blocked_risk":1,"pending":0,"open":0,"closed":1,"wins":1,"losses":0,"win_rate_pct":100.0,"net_r":1.4}
            },
            "timeframe_execution_readiness":{
                "by_timeframe":{
                    "M15":{"pairs_with_exact_data":7,"pairs_paper_ready":7},
                    "M30":{"pairs_with_exact_data":7,"pairs_paper_ready":0},
                    "H1":{"pairs_with_exact_data":7,"pairs_paper_ready":7},
                    "H4":{"pairs_with_exact_data":7,"pairs_paper_ready":0},
                    "D1":{"pairs_with_exact_data":7,"pairs_paper_ready":0},
                    "W1":{"pairs_with_exact_data":7,"pairs_paper_ready":0},
                }
            },
        }

    def test_timeframe_rows_always_cover_m15_to_w1(self):
        rows=forward_timeframe_rows(self.sample())
        self.assertEqual([r["Timeframe"] for r in rows],["M15","M30","H1","H4","D1","W1"])
        m30=next(r for r in rows if r["Timeframe"]=="M30")
        self.assertEqual(m30["Candles exatos"],7)
        self.assertEqual(m30["Pares Paper prontos"],0)

    def test_blockers_are_visible_and_source_equals_execution_is_not_noise(self):
        rows=forward_timeframe_rows(self.sample())
        m15=next(r for r in rows if r["Timeframe"]=="M15")
        h1=next(r for r in rows if r["Timeframe"]=="H1")
        self.assertIn("Gate bloqueado",m15["Principais bloqueios"])
        self.assertNotIn("SOURCE_EQUALS_EXECUTION",m15["Principais bloqueios"])
        self.assertIn("EXECUTION_FRAME_NOT_AVAILABLE:H1",h1["Principais bloqueios"])

    def test_daily_gain_risk_blocks_are_visible_in_forward_tables(self):
        rows=forward_timeframe_rows(self.sample())
        m15=next(r for r in rows if r["Timeframe"]=="M15")
        self.assertEqual(m15["Bloq. risco"],1)
        setups=forward_setup_rows(self.sample())
        self.assertEqual(setups[0]["Bloq. risco"],1)

    def test_setup_rows_keep_forward_results_separate(self):
        rows=forward_setup_rows(self.sample())
        self.assertEqual(rows[0]["Operacional"],"fvg")
        self.assertEqual(rows[0]["Fechados"],1)
        self.assertEqual(rows[0]["Wins"],1)
        self.assertEqual(rows[0]["Net R"],1.4)

    def test_main_backtest_tab_loads_persisted_model_paper_summary(self):
        src=Path("usd_macro_pro_v4_cloud.py").read_text(encoding="utf-8")
        tab=src.index('if _aq_active_index == 7:')
        block=src[tab:tab+2600]
        self.assertIn('dados/model_paper_summary_v1.json',block)
        self.assertIn('render_forward_test_panel(',block)
        self.assertLess(block.index('render_forward_test_panel('),block.index('render_operational_backtest_panel()'))


if __name__=="__main__":
    unittest.main()
