import unittest

from atlasquant_strategy_friction import (
    build_friction_scenarios,
    friction_sensitivity_frame,
    friction_sensitivity_summary,
    friction_sensitivity_report,
    friction_breakdown_frame,
)


def trade(gross_r, *, setup="FVG"):
    return {
        "setup":setup,
        "outcome":"GAIN" if gross_r>0 else ("LOSS" if gross_r<0 else "BREAKEVEN"),
        "gross_r":float(gross_r),
        "cost_r":0.0,
        "slippage_r":0.0,
        "net_r":float(gross_r),
        "same_bar_ambiguous":False,
    }


def empty_suite():
    return {
        "BOS_CHOCH_OB":{"results":[]},
        "FVG":{"results":[]},
        "OTE":{"results":[]},
        "CRT":{"results":[]},
        "AMD_PO3":{"results":[]},
    }


class StrategyFrictionTests(unittest.TestCase):
    def test_scenarios_include_zero_baseline_and_cost_slippage(self):
        scenarios=build_friction_scenarios(
            base_cost_r=0.03,
            slippage_levels_r=[0.0,0.02,0.05],
        )
        self.assertEqual(scenarios[0]["scenario"],"ZERO_FRICTION")
        pairs={(x["cost_r"],x["slippage_r"]) for x in scenarios}
        self.assertIn((0.03,0.0),pairs)
        self.assertIn((0.03,0.02),pairs)
        self.assertIn((0.03,0.05),pairs)

    def test_repricing_uses_same_trades_and_deducts_total_friction(self):
        suite=empty_suite()
        suite["FVG"]["results"]=[trade(2.0),trade(-1.0)]
        scenarios=build_friction_scenarios(
            base_cost_r=0.10,
            slippage_levels_r=[0.05],
        )
        detail=friction_sensitivity_frame(suite,scenarios)
        fvg=detail[detail["strategy"]=="FVG"].sort_values("total_friction_r")
        self.assertEqual(set(fvg["trades"]),{2})
        stressed=fvg.iloc[-1]
        self.assertAlmostEqual(stressed["total_friction_r"],0.15)
        self.assertAlmostEqual(stressed["net_r"],0.7)
        self.assertAlmostEqual(stressed["expectancy_r"],0.35)

    def test_positive_all_tested_friction_status(self):
        suite=empty_suite()
        suite["OTE"]["results"]=[trade(1.0,setup="OTE") for _ in range(20)]
        report=friction_sensitivity_report(
            suite,
            base_cost_r=0.05,
            slippage_levels_r=[0.0,0.05,0.10],
            min_trades=20,
        )
        ote=report["summary"][report["summary"]["strategy"]=="OTE"].iloc[0]
        self.assertEqual(ote["sensitivity_status"],"POSITIVE_ALL_TESTED_FRICTION")
        self.assertEqual(ote["positive_scenarios"],ote["scenarios_tested"])

    def test_breaks_under_tested_friction_marks_first_nonpositive(self):
        suite=empty_suite()
        suite["CRT"]["results"]=[trade(0.08,setup="CRT") for _ in range(20)]
        report=friction_sensitivity_report(
            suite,
            base_cost_r=0.03,
            slippage_levels_r=[0.0,0.02,0.05,0.10],
            min_trades=20,
        )
        crt=report["summary"][report["summary"]["strategy"]=="CRT"].iloc[0]
        self.assertEqual(crt["sensitivity_status"],"BREAKS_UNDER_TESTED_FRICTION")
        self.assertAlmostEqual(crt["first_nonpositive_total_friction_r"],0.08)

    def test_nonpositive_baseline_is_not_called_resilient(self):
        suite=empty_suite()
        suite["AMD_PO3"]["results"]=[trade(-0.1,setup="AMD_PO3") for _ in range(20)]
        report=friction_sensitivity_report(
            suite,
            base_cost_r=0.02,
            slippage_levels_r=[0.0,0.05],
            min_trades=20,
        )
        amd=report["summary"][report["summary"]["strategy"]=="AMD_PO3"].iloc[0]
        self.assertEqual(amd["sensitivity_status"],"NONPOSITIVE_BASELINE")

    def test_small_sample_is_insufficient(self):
        suite=empty_suite()
        suite["FVG"]["results"]=[trade(1.0) for _ in range(5)]
        report=friction_sensitivity_report(
            suite,
            base_cost_r=0.02,
            slippage_levels_r=[0.0,0.05],
            min_trades=20,
        )
        fvg=report["summary"][report["summary"]["strategy"]=="FVG"].iloc[0]
        self.assertEqual(fvg["sensitivity_status"],"INSUFFICIENT")

    def test_breakdown_preserves_session_pair_and_scenario(self):
        suite=empty_suite()
        a=trade(1.0)
        a["session"]="London"
        a["pair"]="EUR/USD"
        b=trade(-1.0)
        b["session"]="New York"
        b["pair"]="EUR/USD"
        suite["FVG"]["results"]=[a,b]
        scenarios=build_friction_scenarios(
            base_cost_r=0.05,
            slippage_levels_r=[0.0,0.05],
        )
        out=friction_breakdown_frame(
            suite,
            scenarios,
            dimensions=("session","pair"),
        )
        fvg=out[out["strategy"]=="FVG"]
        self.assertEqual(set(fvg["dimension"]),{"session","pair"})
        self.assertEqual(set(fvg[fvg["dimension"]=="session"]["segment"]),{"London","New York"})
        self.assertEqual(set(fvg[fvg["dimension"]=="pair"]["segment"]),{"EUR/USD"})
        self.assertGreaterEqual(fvg["scenario"].nunique(),2)

    def test_report_exposes_segment_breakdown(self):
        suite=empty_suite()
        a=trade(1.0)
        a["session"]="London"
        a["pair"]="EUR/USD"
        suite["FVG"]["results"]=[a for _ in range(20)]
        report=friction_sensitivity_report(
            suite,
            base_cost_r=0.02,
            slippage_levels_r=[0.0,0.05],
            min_trades=20,
        )
        self.assertIn("breakdown",report)
        self.assertFalse(report["breakdown"].empty)
        self.assertIn("dimension",report["breakdown"].columns)

    def test_negative_inputs_fail_closed(self):
        with self.assertRaises(ValueError):
            build_friction_scenarios(base_cost_r=-0.01)
        with self.assertRaises(ValueError):
            build_friction_scenarios(base_cost_r=0.0,slippage_levels_r=[-0.01])


if __name__=="__main__":
    unittest.main()
