import unittest
import pandas as pd

from atlasquant_strategy_walkforward import (
    walk_forward_frame,
    walk_forward_summary,
    walk_forward_report,
)


def row(i, r, *, setup="FVG"):
    return {
        "signal_time":pd.Timestamp("2026-09-01T00:00:00Z")+pd.Timedelta(hours=i),
        "setup":setup,
        "outcome":"GAIN" if r>0 else ("LOSS" if r<0 else "BREAKEVEN"),
        "net_r":float(r),
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


class StrategyWalkForwardTests(unittest.TestCase):
    def test_expanding_train_never_uses_future_test_trades(self):
        suite=empty_suite()
        suite["FVG"]["results"]=[row(i,1.0) for i in range(20)]
        df=walk_forward_frame(suite,initial_train_pct=50,test_windows=2)
        fvg=df[df["strategy"]=="FVG"].reset_index(drop=True)
        self.assertEqual(list(fvg["train_trades"]),[10,15])
        self.assertEqual(list(fvg["test_trades"]),[5,5])
        self.assertLess(fvg.iloc[0]["train_end"],fvg.iloc[0]["test_start"])
        self.assertLess(fvg.iloc[1]["train_end"],fvg.iloc[1]["test_start"])

    def test_positive_all_oos_windows_requires_every_test_positive(self):
        suite=empty_suite()
        suite["OTE"]["results"]=[row(i,1.0,setup="OTE") for i in range(30)]
        report=walk_forward_report(
            suite,
            initial_train_pct=60,
            test_windows=3,
            min_train_trades=10,
            min_test_trades=3,
        )
        ote=report["summary"][report["summary"]["strategy"]=="OTE"].iloc[0]
        self.assertEqual(ote["walk_forward_status"],"POSITIVE_ALL_OOS_WINDOWS")
        self.assertEqual(ote["positive_test_windows"],3)
        self.assertTrue(bool(ote["all_windows_sufficient"]))

    def test_mixed_oos_windows_are_not_labeled_positive(self):
        suite=empty_suite()
        values=[1.0]*18 + [1.0]*4 + [-1.0]*4 + [0.5]*4
        suite["CRT"]["results"]=[row(i,r,setup="CRT") for i,r in enumerate(values)]
        report=walk_forward_report(
            suite,
            initial_train_pct=60,
            test_windows=3,
            min_train_trades=10,
            min_test_trades=3,
        )
        crt=report["summary"][report["summary"]["strategy"]=="CRT"].iloc[0]
        self.assertEqual(crt["walk_forward_status"],"MIXED_OOS_WINDOWS")
        self.assertGreaterEqual(crt["positive_test_windows"],1)
        self.assertGreaterEqual(crt["negative_test_windows"],1)

    def test_small_oos_windows_fail_closed(self):
        suite=empty_suite()
        suite["AMD_PO3"]["results"]=[row(i,1.0,setup="AMD_PO3") for i in range(15)]
        report=walk_forward_report(
            suite,
            initial_train_pct=60,
            test_windows=3,
            min_train_trades=5,
            min_test_trades=4,
        )
        amd=report["summary"][report["summary"]["strategy"]=="AMD_PO3"].iloc[0]
        self.assertEqual(amd["walk_forward_status"],"INSUFFICIENT")
        self.assertFalse(bool(amd["all_windows_sufficient"]))


    def test_nonfinite_oos_metrics_fail_closed(self):
        for bad in (float("nan"),float("inf"),float("-inf")):
            with self.subTest(value=bad):
                detail=pd.DataFrame([
                    {"strategy":"FVG","operacional":"FVG","window":"W1","window_index":1,"train_trades":10,"test_trades":5,"train_expectancy_r":0.2,"test_expectancy_r":0.2,"expectancy_delta_r":0.0,"test_net_r":1.0},
                    {"strategy":"FVG","operacional":"FVG","window":"W2","window_index":2,"train_trades":15,"test_trades":5,"train_expectancy_r":0.2,"test_expectancy_r":bad,"expectancy_delta_r":0.0,"test_net_r":1.0},
                    {"strategy":"FVG","operacional":"FVG","window":"W3","window_index":3,"train_trades":20,"test_trades":5,"train_expectancy_r":0.2,"test_expectancy_r":0.3,"expectancy_delta_r":0.1,"test_net_r":1.0},
                ])
                out=walk_forward_summary(detail,expected_windows=3,min_train_trades=10,min_test_trades=5)
                fvg=out[out["strategy"]=="FVG"].iloc[0]
                self.assertEqual(fvg["walk_forward_status"],"INSUFFICIENT")
                self.assertFalse(bool(fvg["all_windows_sufficient"]))

    def test_expectancy_delta_is_test_minus_train(self):
        suite=empty_suite()
        suite["FVG"]["results"]=[row(i,1.0) for i in range(10)] + [row(i+10,0.5) for i in range(10)]
        df=walk_forward_frame(suite,initial_train_pct=50,test_windows=1)
        fvg=df[df["strategy"]=="FVG"].iloc[0]
        self.assertAlmostEqual(fvg["train_expectancy_r"],1.0)
        self.assertAlmostEqual(fvg["test_expectancy_r"],0.5)
        self.assertAlmostEqual(fvg["expectancy_delta_r"],-0.5)

    def test_invalid_initial_train_pct_fails_closed(self):
        with self.assertRaises(ValueError):
            walk_forward_frame(empty_suite(),initial_train_pct=30)
        with self.assertRaises(ValueError):
            walk_forward_frame(empty_suite(),initial_train_pct=95)


    def test_invalid_sample_counts_fail_closed(self):
        for bad in (float("nan"),float("inf"),float("-inf"),-1):
            with self.subTest(trades=bad):
                d=pd.DataFrame([
                    {"strategy":"FVG","window_index":1,"train_trades":10,"test_trades":5,"train_expectancy_r":0.2,"test_expectancy_r":0.2,"expectancy_delta_r":0.0,"test_net_r":1.0},
                    {"strategy":"FVG","window_index":2,"train_trades":bad,"test_trades":5,"train_expectancy_r":0.2,"test_expectancy_r":0.2,"expectancy_delta_r":0.0,"test_net_r":1.0},
                    {"strategy":"FVG","window_index":3,"train_trades":20,"test_trades":5,"train_expectancy_r":0.2,"test_expectancy_r":0.2,"expectancy_delta_r":0.0,"test_net_r":1.0},
                ])
                x=walk_forward_summary(d,expected_windows=3,min_train_trades=10,min_test_trades=5)
                r=x[x["strategy"]=="FVG"].iloc[0]
                self.assertEqual(r["walk_forward_status"],"INSUFFICIENT")
                self.assertFalse(bool(r["all_windows_sufficient"]))



if __name__=="__main__":
    unittest.main()
