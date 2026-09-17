import unittest

import pandas as pd

from atlasquant_setup_performance_v114 import component_pair_frame, sample_state


class SetupPerformanceV114Tests(unittest.TestCase):
    def test_pair_frame_uses_only_closed_numeric_trades(self):
        df = pd.DataFrame([
            {
                "trade_id": "1", "pair": "EUR/USD", "status": "CLOSED",
                "realized_r": 2.0, "exit_time": "2026-09-17T12:00:00Z",
                "fvg_status": "FVG ATIVO",
            },
            {
                "trade_id": "2", "pair": "EUR/USD", "status": "CLOSED",
                "realized_r": -1.0, "exit_time": "2026-09-17T13:00:00Z",
                "fvg_status": "FVG ATIVO",
            },
            {
                "trade_id": "3", "pair": "EUR/USD", "status": "OPEN",
                "realized_r": None, "exit_time": None,
                "fvg_status": "FVG ATIVO",
            },
            {
                "trade_id": "4", "pair": "GBP/USD", "status": "CLOSED",
                "realized_r": 0.0, "exit_time": "2026-09-17T14:00:00Z",
                "fvg_status": "FVG INVALIDADO",
            },
        ])
        out = component_pair_frame(df, "FVG")
        eur = out[(out["pair"] == "EUR/USD") & (out["state"] == "FVG ATIVO")].iloc[0]
        self.assertEqual(int(eur["trades_closed"]), 2)
        self.assertEqual(int(eur["wins"]), 1)
        self.assertEqual(int(eur["losses"]), 1)
        self.assertEqual(float(eur["net_r"]), 1.0)
        self.assertEqual(float(eur["profit_factor_r"]), 2.0)

        gbp = out[(out["pair"] == "GBP/USD") & (out["state"] == "FVG INVALIDADO")].iloc[0]
        self.assertEqual(int(gbp["breakeven"]), 1)
        self.assertEqual(float(gbp["win_rate_pct"]), 0.0)

    def test_unknown_component_is_safe(self):
        df = pd.DataFrame([{"pair": "EUR/USD", "status": "CLOSED", "realized_r": 1.0}])
        self.assertTrue(component_pair_frame(df, "UNKNOWN").empty)

    def test_sample_states(self):
        self.assertEqual(sample_state(0), "AGUARDANDO AMOSTRA")
        self.assertEqual(sample_state(1), "AMOSTRA PEQUENA")
        self.assertEqual(sample_state(30), "AMOSTRA EM FORMAÇÃO")
        self.assertEqual(sample_state(100), "AMOSTRA MAIS MADURA")


if __name__ == "__main__":
    unittest.main()
