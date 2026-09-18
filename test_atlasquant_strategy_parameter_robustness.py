import unittest
import pandas as pd

from atlasquant_strategy_parameter_robustness import (
    STRATEGY_ORDER,
    predefined_parameter_grid,
    parameter_robustness_frame,
    parameter_robustness_summary,
    parameter_robustness_report,
)


class StrategyParameterRobustnessTests(unittest.TestCase):
    def test_predefined_grid_has_base_and_three_variants_per_strategy(self):
        grid=predefined_parameter_grid()
        self.assertEqual(list(grid.keys()),list(STRATEGY_ORDER))
        for strategy in STRATEGY_ORDER:
            self.assertEqual(len(grid[strategy]),3)
            names=[x["variant"] for x in grid[strategy]]
            self.assertIn("BASE",names)

    def test_grid_copy_is_defensive(self):
        grid=predefined_parameter_grid()
        grid["FVG"][0]["params"]["min_gap_atr"]=99.0
        fresh=predefined_parameter_grid()
        self.assertNotEqual(fresh["FVG"][0]["params"]["min_gap_atr"],99.0)

    def test_flat_history_returns_all_predefined_variants_without_ranking(self):
        n=40
        d=pd.DataFrame({
            "datetime":pd.date_range("2026-09-15T00:00:00Z",periods=n,freq="15min",tz="UTC"),
            "open":[10.0]*n,
            "high":[10.1]*n,
            "low":[9.9]*n,
            "close":[10.0]*n,
        })
        out=parameter_robustness_frame(
            d,pair="EUR/USD",max_wait_bars=4,max_hold_bars=8
        )
        self.assertEqual(len(out),15)
        self.assertEqual(set(out["strategy"]),set(STRATEGY_ORDER))
        self.assertNotIn("rank",out.columns)
        self.assertNotIn("best_variant",out.columns)

    def test_positive_all_variants_status_requires_sufficient_samples(self):
        rows=[]
        for strategy in STRATEGY_ORDER:
            for variant in ("A","BASE","C"):
                rows.append({
                    "strategy":strategy,
                    "operacional":strategy,
                    "variant":variant,
                    "is_base":variant=="BASE",
                    "trades":20,
                    "expectancy_r":0.25,
                })
        summary=parameter_robustness_summary(pd.DataFrame(rows),min_trades_per_variant=20)
        self.assertTrue((summary["parameter_robustness_status"]=="POSITIVE_ALL_PREDEFINED_VARIANTS").all())
        self.assertTrue((summary["positive_variants"]==3).all())

    def test_mixed_variants_are_not_called_consistently_positive(self):
        rows=[]
        for variant,exp in (("A",0.3),("BASE",0.1),("C",-0.2)):
            rows.append({
                "strategy":"FVG",
                "operacional":"FVG",
                "variant":variant,
                "is_base":variant=="BASE",
                "trades":25,
                "expectancy_r":exp,
            })
        detail=pd.DataFrame(rows)
        summary=parameter_robustness_summary(detail,min_trades_per_variant=20)
        fvg=summary[summary["strategy"]=="FVG"].iloc[0]
        self.assertEqual(fvg["parameter_robustness_status"],"MIXED_PREDEFINED_VARIANTS")
        self.assertAlmostEqual(fvg["base_expectancy_r"],0.1)
        self.assertAlmostEqual(fvg["expectancy_spread_r"],0.5)

    def test_small_variant_sample_fails_closed(self):
        rows=[
            {"strategy":"OTE","operacional":"OTE","variant":"A","is_base":False,"trades":20,"expectancy_r":0.2},
            {"strategy":"OTE","operacional":"OTE","variant":"BASE","is_base":True,"trades":20,"expectancy_r":0.2},
            {"strategy":"OTE","operacional":"OTE","variant":"C","is_base":False,"trades":4,"expectancy_r":1.0},
        ]
        summary=parameter_robustness_summary(pd.DataFrame(rows),min_trades_per_variant=20)
        ote=summary[summary["strategy"]=="OTE"].iloc[0]
        self.assertEqual(ote["parameter_robustness_status"],"INSUFFICIENT")
        self.assertFalse(bool(ote["all_variants_sufficient"]))


    def test_nonfinite_expectancy_never_gets_positive_status(self):
        for bad in (float("nan"),float("inf"),float("-inf")):
            with self.subTest(expectancy=bad):
                rows=[
                    {"strategy":"FVG","operacional":"FVG","variant":"A","is_base":False,"trades":25,"expectancy_r":0.2},
                    {"strategy":"FVG","operacional":"FVG","variant":"BASE","is_base":True,"trades":25,"expectancy_r":bad},
                    {"strategy":"FVG","operacional":"FVG","variant":"C","is_base":False,"trades":25,"expectancy_r":0.3},
                ]
                summary=parameter_robustness_summary(pd.DataFrame(rows),min_trades_per_variant=20)
                fvg=summary[summary["strategy"]=="FVG"].iloc[0]
                self.assertEqual(fvg["parameter_robustness_status"],"INSUFFICIENT")
                self.assertFalse(bool(fvg["all_variants_sufficient"]))
                self.assertIsNone(fvg["base_expectancy_r"])

    def test_report_exposes_summary_and_variants(self):
        n=40
        d=pd.DataFrame({
            "datetime":pd.date_range("2026-09-15T00:00:00Z",periods=n,freq="15min",tz="UTC"),
            "open":[10.0]*n,
            "high":[10.1]*n,
            "low":[9.9]*n,
            "close":[10.0]*n,
        })
        report=parameter_robustness_report(
            d,pair="EUR/USD",max_wait_bars=4,max_hold_bars=8,min_trades_per_variant=5
        )
        self.assertIn("summary",report)
        self.assertIn("variants",report)
        self.assertEqual(len(report["summary"]),5)
        self.assertEqual(len(report["variants"]),15)


if __name__=="__main__":
    unittest.main()
