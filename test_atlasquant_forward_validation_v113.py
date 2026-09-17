import unittest

import pandas as pd

from atlasquant_forward_validation_v113 import (
    comparison_frame,
    extract_backtest_evidence,
    paper_metrics,
    paper_records_from_frame,
    paper_sample_state,
)


class ForwardValidationV113Tests(unittest.TestCase):
    def test_empty_paper_is_safe(self):
        metrics = paper_metrics(pd.DataFrame())
        self.assertEqual(metrics["trades"], 0)
        self.assertEqual(metrics["net_r"], 0.0)
        self.assertEqual(metrics["sample_state"], "AGUARDANDO AMOSTRA")

    def test_only_closed_trades_enter_forward_sample(self):
        df = pd.DataFrame([
            {"status": "CLOSED", "result": "WIN", "realized_r": 2.0, "pair": "EUR/USD"},
            {"status": "OPEN", "result": "", "realized_r": 0.0, "pair": "GBP/USD"},
            {"status": "CLOSED", "result": "LOSS", "realized_r": -1.0, "pair": "USD/JPY"},
            {"status": "CLOSED", "result": "BREAKEVEN", "realized_r": 0.0, "pair": "USD/CAD"},
            {"status": "CLOSED", "result": "WIN", "realized_r": 1.0, "pair": "USD/CHF"},
        ])
        records = paper_records_from_frame(df)
        self.assertEqual(len(records), 4)
        metrics = paper_metrics(df)
        self.assertEqual(metrics["trades"], 4)
        self.assertEqual(metrics["wins"], 2)
        self.assertEqual(metrics["losses"], 1)
        self.assertEqual(metrics["breakeven"], 1)
        self.assertEqual(metrics["win_rate_pct"], 50.0)
        self.assertEqual(metrics["net_r"], 2.0)
        self.assertEqual(metrics["expectancy_r"], 0.5)
        self.assertEqual(metrics["profit_factor"], 3.0)
        self.assertEqual(metrics["max_drawdown_r"], 1.0)

    def test_snapshot_evidence_is_extracted_without_ranking(self):
        snapshot = {
            "evidence": {
                "bundle": {
                    "evidence_summary": [
                        {
                            "strategy": "fvg",
                            "operacional": "FVG",
                            "trades": 25,
                            "win_rate_pct": 48.0,
                            "expectancy_r": 0.12,
                            "net_r": 3.0,
                            "profit_factor": 1.2,
                            "max_drawdown_r": 4.0,
                            "sample_tier": "SMALL",
                        }
                    ]
                }
            }
        }
        evidence = extract_backtest_evidence(snapshot)
        self.assertEqual(len(evidence), 1)
        self.assertEqual(evidence.iloc[0]["operacional"], "FVG")

        frame = comparison_frame(snapshot, pd.DataFrame())
        self.assertEqual(list(frame["fonte"]), ["BACKTEST HISTÓRICO", "PAPER PROSPECTIVO"])
        self.assertEqual(frame.iloc[0]["operacional"], "FVG")
        self.assertEqual(frame.iloc[1]["trades"], 0)
        self.assertNotIn("score", frame.columns)
        self.assertNotIn("ranking", frame.columns)

    def test_malformed_snapshot_fails_soft(self):
        self.assertTrue(extract_backtest_evidence(None).empty)
        self.assertTrue(extract_backtest_evidence({"evidence": {"bundle": {"evidence_summary": "bad"}}}).empty)

    def test_sample_state_thresholds(self):
        self.assertEqual(paper_sample_state(0), "AGUARDANDO AMOSTRA")
        self.assertEqual(paper_sample_state(1), "AMOSTRA PEQUENA")
        self.assertEqual(paper_sample_state(29), "AMOSTRA PEQUENA")
        self.assertEqual(paper_sample_state(30), "AMOSTRA EM FORMAÇÃO")
        self.assertEqual(paper_sample_state(99), "AMOSTRA EM FORMAÇÃO")
        self.assertEqual(paper_sample_state(100), "AMOSTRA MAIS MADURA")


if __name__ == "__main__":
    unittest.main()
