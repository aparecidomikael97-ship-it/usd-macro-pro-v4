import unittest
import pandas as pd

from atlasquant_strategy_stability import (
    temporal_fold_frame,
    temporal_stability_summary,
    temporal_stability_report,
)


def row(i, r, *, outcome=None, setup="FVG"):
    if outcome is None:
        outcome="GAIN" if r>0 else ("LOSS" if r<0 else "BREAKEVEN")
    return {
        "signal_time":pd.Timestamp("2026-09-01T00:00:00Z")+pd.Timedelta(hours=i),
        "setup":setup,
        "outcome":outcome,
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


class StrategyStabilityTests(unittest.TestCase):
    def test_temporal_folds_are_chronological_and_near_equal(self):
        suite=empty_suite()
        suite["FVG"]["results"]=[row(i,1.0 if i%2==0 else -1.0) for i in range(10)]
        folds=temporal_fold_frame(suite,folds=3)
        fvg=folds[folds["strategy"]=="FVG"].reset_index(drop=True)
        self.assertEqual(list(fvg["trades"]),[4,3,3])
        self.assertEqual(list(fvg["fold"]),["F1","F2","F3"])
        self.assertLess(fvg.iloc[0]["end_time"],fvg.iloc[1]["start_time"])
        self.assertLess(fvg.iloc[1]["end_time"],fvg.iloc[2]["start_time"])

    def test_positive_across_folds_requires_every_fold_positive(self):
        suite=empty_suite()
        suite["FVG"]["results"]=[row(i,1.0) for i in range(18)]
        report=temporal_stability_report(suite,folds=3,min_trades_per_fold=5)
        summary=report["summary"]
        fvg=summary[summary["strategy"]=="FVG"].iloc[0]
        self.assertEqual(fvg["stability_status"],"POSITIVE_ACROSS_FOLDS")
        self.assertEqual(fvg["positive_folds"],3)
        self.assertTrue(bool(fvg["all_folds_sufficient"]))

    def test_mixed_expectancy_is_not_labeled_consistent(self):
        suite=empty_suite()
        values=[1.0]*6 + [-1.0]*6 + [0.5]*6
        suite["OTE"]["results"]=[row(i,r,setup="OTE") for i,r in enumerate(values)]
        report=temporal_stability_report(suite,folds=3,min_trades_per_fold=5)
        ote=report["summary"][report["summary"]["strategy"]=="OTE"].iloc[0]
        self.assertEqual(ote["stability_status"],"MIXED_ACROSS_FOLDS")
        self.assertEqual(ote["positive_folds"],2)
        self.assertEqual(ote["negative_folds"],1)

    def test_small_fold_sample_stays_insufficient(self):
        suite=empty_suite()
        suite["CRT"]["results"]=[row(i,1.0,setup="CRT") for i in range(9)]
        report=temporal_stability_report(suite,folds=3,min_trades_per_fold=5)
        crt=report["summary"][report["summary"]["strategy"]=="CRT"].iloc[0]
        self.assertEqual(crt["stability_status"],"INSUFFICIENT")
        self.assertFalse(bool(crt["all_folds_sufficient"]))


    def test_nonfinite_fold_metrics_fail_closed(self):
        for bad in (float("nan"),float("inf"),float("-inf")):
            with self.subTest(value=bad):
                detail=pd.DataFrame([
                    {"strategy":"FVG","operacional":"FVG","fold":"F1","fold_index":1,"trades":5,"expectancy_r":0.2,"net_r":1.0},
                    {"strategy":"FVG","operacional":"FVG","fold":"F2","fold_index":2,"trades":5,"expectancy_r":bad,"net_r":1.0},
                    {"strategy":"FVG","operacional":"FVG","fold":"F3","fold_index":3,"trades":5,"expectancy_r":0.3,"net_r":1.0},
                ])
                out=temporal_stability_summary(detail,folds=3,min_trades_per_fold=5)
                fvg=out[out["strategy"]=="FVG"].iloc[0]
                self.assertEqual(fvg["stability_status"],"INSUFFICIENT")
                self.assertFalse(bool(fvg["all_folds_sufficient"]))

    def test_no_timestamp_is_excluded_from_temporal_folds(self):
        suite=empty_suite()
        suite["AMD_PO3"]["results"]=[
            {"outcome":"GAIN","net_r":1.0,"setup":"AMD_PO3"},
            row(1,1.0,setup="AMD_PO3"),
            row(2,1.0,setup="AMD_PO3"),
            row(3,1.0,setup="AMD_PO3"),
        ]
        folds=temporal_fold_frame(suite,folds=3)
        amd=folds[folds["strategy"]=="AMD_PO3"]
        self.assertEqual(int(amd["trades"].sum()),3)


if __name__=="__main__":
    unittest.main()
