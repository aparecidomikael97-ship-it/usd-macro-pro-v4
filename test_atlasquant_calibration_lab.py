import unittest
import pandas as pd

from atlasquant_calibration_lab import (
    score_band, wilson_interval, calibration_table, calibration_summary,
)


class AtlasQuantCalibrationLabTests(unittest.TestCase):
    def test_score_bands(self):
        self.assertEqual(score_band(69),"<70")
        self.assertEqual(score_band(70),"70–79")
        self.assertEqual(score_band(85),"80–89")
        self.assertEqual(score_band(95),"90+")

    def test_invalid_score(self):
        self.assertEqual(score_band(float("nan")),"SEM SCORE")

    def test_wilson_bounds_are_valid(self):
        lo,hi=wilson_interval(8,10)
        self.assertGreaterEqual(lo,0)
        self.assertLessEqual(hi,100)
        self.assertLess(lo,hi)

    def test_table_uses_only_completed_outcomes(self):
        df=pd.DataFrame({
            "score_mestre":[75,85,95],
            "retorno_24h_pct":[1.0,None,-1.0],
        })
        t=calibration_table(df,"24h",min_band_samples=1)
        self.assertEqual(int(t["Amostra"].sum()),2)

    def test_positive_directional_return_is_hit(self):
        df=pd.DataFrame({
            "score_mestre":[75,75],
            "retorno_24h_pct":[1.0,-1.0],
        })
        t=calibration_table(df,"24h",min_band_samples=1)
        row=t[t["Faixa"]=="70–79"].iloc[0]
        self.assertEqual(int(row["Acertos"]),1)
        self.assertEqual(float(row["Taxa observada %"]),50.0)

    def test_small_band_not_sufficient(self):
        df=pd.DataFrame({"score_mestre":[95],"retorno_24h_pct":[1.0]})
        t=calibration_table(df,"24h",min_band_samples=30)
        self.assertFalse(bool(t[t["Faixa"]=="90+"].iloc[0]["Amostra suficiente"]))

    def test_consistent_monotonic_summary(self):
        rows=[]
        for score,hits in ((75,15),(85,20),(95,25)):
            for i in range(30):
                rows.append({"score_mestre":score,"retorno_24h_pct":1.0 if i<hits else -1.0})
        t=calibration_table(pd.DataFrame(rows),"24h",min_band_samples=30)
        s=calibration_summary(t,min_total_samples=90)
        self.assertTrue(s["monotonic"])
        self.assertEqual(s["status"],"CONSISTENT")
        self.assertFalse(s["auto_reweight_allowed"])

    def test_non_monotonic_is_unstable(self):
        rows=[]
        for score,hits in ((75,25),(85,10),(95,20)):
            for i in range(30):
                rows.append({"score_mestre":score,"retorno_24h_pct":1.0 if i<hits else -1.0})
        s=calibration_summary(
            calibration_table(pd.DataFrame(rows),"24h",min_band_samples=30),
            min_total_samples=90,
        )
        self.assertEqual(s["status"],"UNSTABLE")

    def test_never_auto_reweights(self):
        s=calibration_summary(pd.DataFrame(),min_total_samples=1)
        self.assertFalse(s["auto_reweight_allowed"])


    def test_nonfinite_scores_and_returns_are_excluded(self):
        df=pd.DataFrame({
            "score_mestre":[75,float("nan"),float("inf"),85,95],
            "retorno_24h_pct":[1.0,1.0,1.0,float("inf"),float("-inf")],
        })
        t=calibration_table(df,"24h",min_band_samples=1)
        self.assertEqual(int(t["Amostra"].sum()),1)

    def test_summary_invalid_sample_counts_fail_closed(self):
        for bad in (float("nan"),float("inf"),float("-inf"),-1):
            with self.subTest(sample=bad):
                table=pd.DataFrame({
                    "Faixa":["70–79","80–89"],
                    "Amostra":[30,bad],
                    "Amostra suficiente":[True,True],
                    "Taxa observada %":[50.0,60.0],
                })
                s=calibration_summary(table,min_total_samples=1)
                self.assertEqual(s["status"],"INSUFFICIENT")
                self.assertEqual(s["total_samples"],0)
                self.assertFalse(s["auto_reweight_allowed"])


if __name__=="__main__":
    unittest.main()
