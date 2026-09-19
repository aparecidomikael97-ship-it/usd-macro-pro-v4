import unittest
import pandas as pd

from atlasquant_strategy_comparator import (
    STRATEGY_ORDER,
    comparison_frame,
    breakdown_frame,
    combined_ledger,
    run_strategy_suite,
)


def result(setup, outcome, r, session="London", pair="EUR/USD"):
    return {
        "setup":setup,
        "outcome":outcome,
        "net_r":r,
        "session":session,
        "pair":pair,
        "same_bar_ambiguous":False,
    }


class StrategyComparatorTests(unittest.TestCase):
    def test_comparison_keeps_strategies_separate(self):
        suite={
            "BOS_CHOCH_OB":{"label":"BOS/CHOCH + Order Block","results":[result("BOS",-1,-1)]},
            "FVG":{"label":"FVG","results":[result("FVG","GAIN",2.0),result("FVG","LOSS",-1.0)]},
            "OTE":{"label":"OTE 62–79%","results":[]},
            "CRT":{"label":"CRT","results":[]},
            "AMD_PO3":{"label":"AMD / Power of Three","results":[]},
        }
        # Fix first row to a valid outcome string while keeping -1R.
        suite["BOS_CHOCH_OB"]["results"][0]["outcome"]="LOSS"
        df=comparison_frame(suite,min_trades_for_rank=1)
        self.assertEqual(list(df["strategy"]),list(STRATEGY_ORDER))
        fvg=df[df["strategy"]=="FVG"].iloc[0]
        bos=df[df["strategy"]=="BOS_CHOCH_OB"].iloc[0]
        self.assertEqual(fvg["trades"],2)
        self.assertAlmostEqual(fvg["net_r"],1.0)
        self.assertEqual(bos["trades"],1)
        self.assertAlmostEqual(bos["net_r"],-1.0)

    def test_observed_rank_excludes_small_samples(self):
        big=[result("FVG","GAIN",1.0) for _ in range(20)]
        tiny=[result("OTE","GAIN",5.0)]
        suite={
            "BOS_CHOCH_OB":{"results":[]},
            "FVG":{"results":big},
            "OTE":{"results":tiny},
            "CRT":{"results":[]},
            "AMD_PO3":{"results":[]},
        }
        df=comparison_frame(suite,min_trades_for_rank=20)
        fvg=df[df["strategy"]=="FVG"].iloc[0]
        ote=df[df["strategy"]=="OTE"].iloc[0]
        self.assertEqual(int(fvg["observed_expectancy_rank"]),1)
        self.assertFalse(bool(ote["eligible_observed_rank"]))
        self.assertTrue(pd.isna(ote["observed_expectancy_rank"]))


    def test_nonfinite_metrics_cannot_receive_observed_rank(self):
        bad=[result("FVG","GAIN",float("inf")) for _ in range(20)]
        suite={k:{"results":[]} for k in STRATEGY_ORDER}
        suite["FVG"]={"results":bad}
        df=comparison_frame(suite,min_trades_for_rank=20)
        fvg=df[df["strategy"]=="FVG"].iloc[0]
        self.assertFalse(bool(fvg["eligible_observed_rank"]))
        self.assertTrue(pd.isna(fvg["observed_expectancy_rank"]))
        self.assertTrue(pd.isna(fvg["net_r_per_drawdown"]))

    def test_breakdown_preserves_strategy_and_session(self):
        suite={
            "BOS_CHOCH_OB":{"results":[
                result("BOS","GAIN",2.0,"London"),
                result("BOS","LOSS",-1.0,"New York"),
            ]},
            "FVG":{"results":[result("FVG","GAIN",1.0,"London")]},
            "OTE":{"results":[]},
            "CRT":{"results":[]},
            "AMD_PO3":{"results":[]},
        }
        df=breakdown_frame(suite,"session")
        self.assertIn("strategy",df.columns)
        self.assertEqual(set(df["session"]),{"London","New York"})
        self.assertEqual(len(df[df["strategy"]=="BOS_CHOCH_OB"]),2)

    def test_combined_ledger_adds_strategy_identity(self):
        suite={
            "BOS_CHOCH_OB":{"label":"BOS","results":[result("BOS","GAIN",1.0)]},
            "FVG":{"label":"FVG","results":[result("FVG","LOSS",-1.0)]},
            "OTE":{"results":[]},
            "CRT":{"results":[]},
            "AMD_PO3":{"results":[]},
        }
        df=combined_ledger(suite)
        self.assertEqual(set(df["strategy_family"]),{"BOS_CHOCH_OB","FVG"})
        self.assertEqual(len(df),2)

    def test_run_suite_returns_all_five_strategies_even_without_signals(self):
        n=40
        d=pd.DataFrame({
            "datetime":pd.date_range("2026-09-15T00:00:00Z",periods=n,freq="15min",tz="UTC"),
            "open":[10.0]*n,
            "high":[10.1]*n,
            "low":[9.9]*n,
            "close":[10.0]*n,
        })
        suite=run_strategy_suite(d,pair="EUR/USD",max_wait_bars=4,max_hold_bars=8)
        self.assertEqual(list(suite.keys()),list(STRATEGY_ORDER))
        for key in STRATEGY_ORDER:
            self.assertIn("signals",suite[key])
            self.assertIn("results",suite[key])
            self.assertEqual(suite[key]["strategy"],key)


if __name__=="__main__":
    unittest.main()
