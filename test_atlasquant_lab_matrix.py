import unittest

from atlasquant_lab_matrix import (
    LAB_TIMEFRAMES,
    TRADING_STYLES,
    cells_for_style,
    lab_matrix,
)
from atlasquant_setup_validation import SETUP_CATALOG


class LabMatrixTests(unittest.TestCase):
    def test_requested_timeframes_styles_and_setups_are_covered(self):
        self.assertEqual(LAB_TIMEFRAMES, ("M15", "M30", "H1", "H4", "D1", "W1"))
        self.assertEqual(set(TRADING_STYLES), {"DAY_TRADE", "INTRADAY", "SWING", "POSITION"})
        ids = {x["id"] for x in SETUP_CATALOG}
        for required in ("amd-po3", "fvg", "bos-choch-ob", "breaker-mitigation", "ote", "ppr"):
            self.assertIn(required, ids)
        matrix = lab_matrix()
        self.assertEqual(len(matrix["cells"]), len(LAB_TIMEFRAMES) * len(SETUP_CATALOG))
        for style in TRADING_STYLES:
            self.assertTrue(cells_for_style(matrix, style), style)
        self.assertEqual({c["trading_style"] for c in cells_for_style(matrix, "position")}, {"POSITION"})
        self.assertEqual({c["timeframe_label"] for c in cells_for_style(matrix, "POSITION")}, {"Semanal"})

    def test_empty_matrix_never_fabricates_results(self):
        matrix = lab_matrix()
        self.assertFalse(matrix["fabricated_values"])
        self.assertFalse(matrix["runs_backtest"])
        for cell in matrix["cells"]:
            self.assertIn(cell["state"], {"SEM_EVIDENCIA", "BLOQUEADO"})
            self.assertTrue(all(v is None for v in cell["metrics"].values()))
            self.assertFalse(cell["real_orders_enabled"])

    def test_recorded_evidence_fills_only_its_exact_cell(self):
        rows = [{"setup_id": "FVG", "timeframe": "4h", "samples": 120, "expectancy_r": 0.1,
                 "profit_factor": 1.2, "max_drawdown_r": 6, "source": "ledger 2026-09"}]
        matrix = lab_matrix(rows)
        filled = [c for c in matrix["cells"] if c["state"] == "EVIDENCIA_REGISTRADA"]
        self.assertEqual(len(filled), 1)
        self.assertEqual((filled[0]["timeframe"], filled[0]["setup_id"]), ("H4", "fvg"))
        self.assertEqual(filled[0]["trading_style"], "SWING")

    def test_partial_or_bad_evidence_stays_empty_not_estimated(self):
        rows = [
            {"setup_id": "ote", "timeframe": "H1", "samples": 50, "expectancy_r": "n/d", "source": ""},
            {"setup_id": "ote", "timeframe": "M5", "samples": 999, "expectancy_r": 1, "profit_factor": 2,
             "max_drawdown_r": 1, "source": "x"},
            {"setup_id": "unknown", "timeframe": "H1", "samples": 1},
            {"setup_id": "fvg", "timeframe": "D1", "samples": 10.5, "expectancy_r": float("inf"),
             "profit_factor": True, "max_drawdown_r": 2, "source": "x"},
        ]
        matrix = lab_matrix(rows)
        partial = {(c["timeframe"], c["setup_id"]): c for c in matrix["cells"] if c["state"] == "EVIDENCIA_INCOMPLETA"}
        self.assertEqual(set(partial), {("H1", "ote"), ("D1", "fvg")})
        self.assertIsNone(partial[("H1", "ote")]["metrics"]["expectancy_r"])
        self.assertIsNone(partial[("D1", "fvg")]["metrics"]["samples"])
        self.assertIsNone(partial[("D1", "fvg")]["metrics"]["profit_factor"])
        self.assertEqual(matrix["counts"]["EVIDENCIA_REGISTRADA"], 0)

    def test_undefined_setup_is_blocked_even_with_evidence(self):
        rows = [{"setup_id": "ppr", "timeframe": "H1", "samples": 200, "expectancy_r": 1,
                 "profit_factor": 3, "max_drawdown_r": 1, "source": "x"}]
        cell = next(c for c in lab_matrix(rows)["cells"] if c["setup_id"] == "ppr" and c["timeframe"] == "H1")
        self.assertEqual(cell["state"], "BLOQUEADO")
        self.assertTrue(all(v is None for v in cell["metrics"].values()))


if __name__ == "__main__":
    unittest.main()
