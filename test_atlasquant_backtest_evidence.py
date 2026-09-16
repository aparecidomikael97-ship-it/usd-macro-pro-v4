import json
import unittest

import pandas as pd

from atlasquant_backtest_evidence import (
    consolidated_evidence_frame,
    build_evidence_bundle,
    evidence_bundle_json,
    evidence_markdown,
)
from atlasquant_strategy_comparator import STRATEGY_ORDER


def comparison():
    rows=[]
    for strategy in STRATEGY_ORDER:
        rows.append({
            "strategy":strategy,
            "operacional":strategy,
            "trades":25,
            "win_rate_pct":50.0,
            "expectancy_r":0.20,
            "net_r":5.0,
            "profit_factor":1.5,
            "max_drawdown_r":2.0,
            "max_loss_streak":3,
            "sample_tier":"AMOSTRA INICIAL",
        })
    return pd.DataFrame(rows)


def status_frame(column, value):
    return pd.DataFrame([
        {"strategy":s, "operacional":s, column:value}
        for s in STRATEGY_ORDER
    ])


class BacktestEvidenceTests(unittest.TestCase):
    def test_consolidates_one_row_per_strategy_without_ranking(self):
        out=consolidated_evidence_frame(
            comparison(),
            status_frame("stability_status","POSITIVE_ACROSS_FOLDS"),
            status_frame("walk_forward_status","POSITIVE_ALL_OOS_WINDOWS"),
            status_frame("sensitivity_status","POSITIVE_ALL_TESTED_FRICTION"),
            status_frame("parameter_robustness_status","POSITIVE_ALL_PREDEFINED_VARIANTS"),
        )
        self.assertEqual(list(out["strategy"]),list(STRATEGY_ORDER))
        self.assertTrue((out["evidence_coverage"]=="COMPLETE").all())
        self.assertNotIn("rank",out.columns)
        self.assertNotIn("recommendation",out.columns)

    def test_parameter_not_run_marks_partial_coverage(self):
        out=consolidated_evidence_frame(
            comparison(),
            status_frame("stability_status","POSITIVE_ACROSS_FOLDS"),
            status_frame("walk_forward_status","POSITIVE_ALL_OOS_WINDOWS"),
            status_frame("sensitivity_status","POSITIVE_ALL_TESTED_FRICTION"),
            None,
        )
        self.assertTrue((out["parameter_status"]=="NOT_RUN").all())
        self.assertTrue((out["evidence_diagnostics_available"]==3).all())
        self.assertTrue((out["evidence_coverage"]=="PARTIAL").all())

    def test_insufficient_diagnostics_do_not_count_as_available(self):
        out=consolidated_evidence_frame(
            comparison(),
            status_frame("stability_status","INSUFFICIENT"),
            status_frame("walk_forward_status","INSUFFICIENT"),
            status_frame("sensitivity_status","INSUFFICIENT"),
            None,
        )
        self.assertTrue((out["evidence_diagnostics_available"]==0).all())
        self.assertTrue((out["evidence_coverage"]=="INSUFFICIENT").all())

    def test_bundle_is_json_safe_and_preserves_research_flags(self):
        evidence=consolidated_evidence_frame(
            comparison(),
            status_frame("stability_status","POSITIVE_ACROSS_FOLDS"),
            status_frame("walk_forward_status","POSITIVE_ALL_OOS_WINDOWS"),
            status_frame("sensitivity_status","POSITIVE_ALL_TESTED_FRICTION"),
            None,
        )
        folds=pd.DataFrame([{
            "strategy":"FVG",
            "start_time":pd.Timestamp("2026-09-01T00:00:00Z"),
            "end_time":pd.Timestamp("2026-09-02T00:00:00Z"),
        }])
        bundle=build_evidence_bundle(
            pair="EUR/USD",
            evidence=evidence,
            comparison=comparison(),
            stability_summary=status_frame("stability_status","POSITIVE_ACROSS_FOLDS"),
            stability_folds=folds,
            walkforward_summary=status_frame("walk_forward_status","POSITIVE_ALL_OOS_WINDOWS"),
            walkforward_windows=pd.DataFrame(),
            friction_summary=status_frame("sensitivity_status","POSITIVE_ALL_TESTED_FRICTION"),
            friction_scenarios=pd.DataFrame(),
            friction_breakdown=pd.DataFrame(),
            parameter_summary=None,
            parameter_variants=None,
            settings={"cost_r":0.02},
        )
        raw=evidence_bundle_json(bundle)
        decoded=json.loads(raw)
        self.assertEqual(decoded["schema"],"ATLASQUANT_BACKTEST_EVIDENCE_V1")
        self.assertEqual(decoded["pair"],"EUR/USD")
        self.assertTrue(decoded["research_only"])
        self.assertTrue(decoded["no_live_gate_effect"])
        self.assertTrue(decoded["no_profit_probability"])
        self.assertIn("2026-09-01",raw)

    def test_markdown_states_limits_and_no_live_gate_effect(self):
        evidence=consolidated_evidence_frame(
            comparison(),
            status_frame("stability_status","POSITIVE_ACROSS_FOLDS"),
            status_frame("walk_forward_status","POSITIVE_ALL_OOS_WINDOWS"),
            status_frame("sensitivity_status","POSITIVE_ALL_TESTED_FRICTION"),
            None,
        )
        report=evidence_markdown(
            evidence,
            pair="EUR/USD",
            settings={"cost_r":0.02,"slippage_r":0.01},
        )
        self.assertIn("Relatório consolidado de evidências",report)
        self.assertIn("Pesquisa histórica",report)
        self.assertIn("não altera o Gate",report)
        self.assertIn("Robustez de parâmetros: NOT_RUN",report)

    def test_missing_strategy_rows_fail_closed(self):
        comp=comparison()
        comp=comp[comp["strategy"]=="FVG"].copy()
        out=consolidated_evidence_frame(
            comp,
            pd.DataFrame(),
            pd.DataFrame(),
            pd.DataFrame(),
            None,
        )
        bos=out[out["strategy"]=="BOS_CHOCH_OB"].iloc[0]
        self.assertEqual(bos["trades"],0)
        self.assertEqual(bos["evidence_coverage"],"INSUFFICIENT")


if __name__=="__main__":
    unittest.main()
