import unittest
from unittest.mock import patch

import pandas as pd

import autopilot_paper_v112 as paper_runner
from paper_friction_v116 import apply_paper_friction, summarize_net


class PaperFrictionV116Tests(unittest.TestCase):
    def test_closed_trade_keeps_gross_and_adds_net(self):
        src = pd.DataFrame([{
            "trade_id": "x1", "status": "CLOSED", "result": "WIN", "realized_r": 2.0,
        }])
        out = apply_paper_friction(src)
        self.assertEqual(float(out.iloc[0]["realized_r"]), 2.0)
        self.assertEqual(float(out.iloc[0]["gross_r"]), 2.0)
        self.assertAlmostEqual(float(out.iloc[0]["total_friction_r"]), 0.06, places=8)
        self.assertAlmostEqual(float(out.iloc[0]["net_r"]), 1.94, places=8)
        self.assertEqual(out.iloc[0]["result"], "WIN")

    def test_open_trade_is_not_charged_early(self):
        src = pd.DataFrame([{
            "trade_id": "x2", "status": "OPEN", "result": "", "realized_r": None,
        }])
        out = apply_paper_friction(src)
        self.assertTrue(pd.isna(out.iloc[0]["net_r"]))
        self.assertTrue(pd.isna(out.iloc[0]["total_friction_r"]))

    def test_summary_reports_gross_cost_and_net(self):
        src = pd.DataFrame([
            {"status": "CLOSED", "realized_r": 2.0},
            {"status": "CLOSED", "realized_r": -1.0},
        ])
        s = summarize_net(src)
        self.assertEqual(s["closed_costed"], 2)
        self.assertAlmostEqual(s["gross_r"], 1.0, places=8)
        self.assertAlmostEqual(s["friction_r"], 0.12, places=8)
        self.assertAlmostEqual(s["net_r"], 0.88, places=8)
        self.assertFalse(s["safety"]["real_orders"])
        self.assertFalse(s["safety"]["broker_connection"])
        self.assertFalse(s["safety"]["auto_strategy_selection"])

    def test_autopilot_persists_costed_ledger_and_status(self):
        closed = pd.DataFrame([{
            "trade_id": "x3",
            "status": "CLOSED",
            "result": "WIN",
            "realized_r": 2.0,
        }])
        saved_csv = {}
        saved_json = {}

        def fake_get_json(path, default):
            return {}, ""

        def fake_get_csv(path):
            return pd.DataFrame(), ""

        def fake_put_csv(path, frame, message):
            saved_csv[path] = frame.copy()
            return True, ""

        def fake_put_json(path, payload, message):
            saved_json[path] = dict(payload)
            return True, ""

        legacy_summary = {
            "trades_total": 1,
            "pending_entries": 0,
            "open_positions": 0,
            "closed_trades": 1,
            "wins": 1,
            "losses": 0,
            "breakeven": 0,
            "win_rate_pct": 100.0,
            "net_r": 2.0,
            "avg_r": 2.0,
            "profit_factor_r": None,
        }

        with patch.object(paper_runner.base, "gh_get_json", side_effect=fake_get_json), \
             patch.object(paper_runner.base, "gh_get_csv", side_effect=fake_get_csv), \
             patch.object(paper_runner.base, "gh_put_csv", side_effect=fake_put_csv), \
             patch.object(paper_runner.base, "gh_put_json", side_effect=fake_put_json), \
             patch.object(paper_runner, "run_paper_cycle", return_value=(closed, {"trades_closed": 1})), \
             patch.object(paper_runner, "summarize_paper_trades", return_value=legacy_summary):
            ok, summary, errors = paper_runner._paper_cycle()

        self.assertTrue(ok)
        self.assertEqual(errors, [])
        persisted = saved_csv[paper_runner.PAPER_CSV_PATH]
        self.assertAlmostEqual(float(persisted.iloc[0]["gross_r"]), 2.0, places=8)
        self.assertAlmostEqual(float(persisted.iloc[0]["friction_r"]) if "friction_r" in persisted.columns else float(persisted.iloc[0]["total_friction_r"]), 0.06, places=8)
        self.assertAlmostEqual(float(persisted.iloc[0]["net_r"]), 1.94, places=8)
        self.assertAlmostEqual(float(summary["net_r_after_friction"]), 1.94, places=8)

        status = saved_json[paper_runner.base.STATUS_PATH]["paper_trading_v112"]
        self.assertEqual(status["friction_version"], "V11.6_PAPER_FRICTION")
        self.assertAlmostEqual(float(status["net_r_after_friction"]), 1.94, places=8)
        self.assertFalse(summary["safety"]["friction_changes_signal"])
        self.assertFalse(summary["safety"]["friction_changes_result_classification"])


if __name__ == "__main__":
    unittest.main()
