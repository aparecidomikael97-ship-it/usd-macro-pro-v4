import unittest
from pathlib import Path

from atlasquant_lab_matrix_panel import evidence_period_rows


class LabMatrixPanelTests(unittest.TestCase):
    def test_period_rows_use_only_explicit_recorded_values(self):
        rows = [{
            "executed_at": "2026-09-27T01:00:00Z",
            "asset": "EUR/USD",
            "setup_id": "fvg",
            "timeframe": "H1",
            "samples": 20,
            "win_rate_pct": None,
            "expectancy_r": 0.1,
            "profit_factor": None,
            "max_drawdown_r": 3,
            "net_result": 2,
            "source": "BACKTEST_SESSION",
            "rules_version": "fvg-v1",
        }]
        monthly = evidence_period_rows(rows, "MONTH")
        self.assertEqual(monthly[0]["Período"], "2026-09")
        self.assertIsNone(monthly[0]["Win rate %"])
        self.assertIsNone(monthly[0]["Profit factor"])
        self.assertEqual(evidence_period_rows(rows, "WEEK"), [])

    def test_invalid_timestamp_is_not_assigned_to_a_period(self):
        self.assertEqual(evidence_period_rows([{"executed_at": "not-a-date"}], "YEAR"), [])

    def test_render_entrypoint_is_fault_isolated(self):
        src = Path("usd_macro_pro_v4_cloud.py").read_text(encoding="utf-8")
        self.assertIn("from atlasquant_lab_matrix_panel import render_lab_matrix_panel", src)
        self.assertIn("render_lab_matrix_panel()", src)
        self.assertIn("nenhuma evidência foi inferida", src)

    def test_backtest_capture_records_matrix_dimensions_and_metrics(self):
        src = Path("atlasquant_backtest_panel.py").read_text(encoding="utf-8")
        for field in (
            '"trades":metrics.get("trades")',
            '"win_rate_pct":metrics.get("win_rate_pct")',
            '"expectancy_r":metrics.get("expectancy_r")',
            '"profit_factor":metrics.get("profit_factor")',
            '"max_drawdown_r":metrics.get("max_drawdown_r")',
            '"net_r":metrics.get("net_r")',
            '"timeframe":_timeframes[0]',
            '"rules_version":str(key_suffix)',
        ):
            self.assertIn(field, src)


if __name__ == "__main__":
    unittest.main()
