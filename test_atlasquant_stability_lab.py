import unittest
import pandas as pd

from atlasquant_stability_lab import (
    forex_session, add_stability_dimensions, temporal_folds,
    session_metrics, stability_summary,
)


class AtlasQuantStabilityLabTests(unittest.TestCase):
    def frame(self, n=90):
        rows=[]
        for i in range(n):
            month=1+(i//30)
            rows.append({
                "registrado_em":f"2026-{month:02d}-{(i%28)+1:02d}T14:00:00Z",
                "par":"EUR/USD" if i%2==0 else "GBP/USD",
                "direcao":"BUY",
                "score_mestre":80,
                "qualidade":"80%",
                "retorno_24h_pct":1.0 if i%2==0 else 0.5,
            })
        return pd.DataFrame(rows)

    def test_invalid_timestamp(self):
        self.assertEqual(forex_session("bad"),"Sem horário")

    def test_session_is_timezone_aware(self):
        label=forex_session("2026-01-15T14:00:00Z")
        self.assertIn(label,{"London/NY overlap","London","New York","Asia/Tokyo","Fora das sessões principais"})

    def test_adds_session_dimension(self):
        data=add_stability_dimensions(self.frame(3),"24h")
        self.assertIn("Sessão",data.columns)

    def test_three_temporal_folds(self):
        f=temporal_folds(self.frame(90),"24h",folds=3)
        self.assertEqual(len(f),3)
        self.assertTrue((f["Amostra"]==30).all())

    def test_session_metrics_count_all_rows(self):
        s=session_metrics(self.frame(20),"24h",min_samples=1)
        self.assertEqual(int(s["Amostra"].sum()),20)

    def test_stable_summary_requires_enough_samples(self):
        f=temporal_folds(self.frame(90),"24h",folds=3)
        s=stability_summary(f,min_fold_samples=30,max_hit_rate_spread_pp=15)
        self.assertTrue(s["all_folds_sufficient"])
        self.assertEqual(s["status"],"STABLE")
        self.assertFalse(s["auto_change_allowed"])

    def test_small_folds_are_insufficient(self):
        f=temporal_folds(self.frame(9),"24h",folds=3)
        s=stability_summary(f,min_fold_samples=30)
        self.assertEqual(s["status"],"INSUFFICIENT")

    def test_inconsistent_sign_is_not_stable(self):
        f=pd.DataFrame({
            "Amostra":[30,30,30],
            "Taxa observada %":[55,55,55],
            "Retorno médio %":[1.0,-1.0,1.0],
        })
        s=stability_summary(f,min_fold_samples=30)
        self.assertEqual(s["status"],"UNSTABLE")

    def test_regime_only_when_present(self):
        df=self.frame(3)
        data=add_stability_dimensions(df,"24h")
        self.assertNotIn("Regime",data.columns)
        df["regime"]=["trend","range","trend"]
        data2=add_stability_dimensions(df,"24h")
        self.assertIn("Regime",data2.columns)


    def test_stability_summary_rejects_nonfinite_or_negative_sample_counts(self):
        for bad in (float("nan"),float("inf"),float("-inf"),-1):
            with self.subTest(sample=bad):
                f=pd.DataFrame({
                    "Amostra":[30,30,bad],
                    "Taxa observada %":[55,55,55],
                    "Retorno médio %":[1.0,1.0,1.0],
                })
                s=stability_summary(f,min_fold_samples=30)
                self.assertEqual(s["status"],"INSUFFICIENT")
                self.assertFalse(s["all_folds_sufficient"])

    def test_temporal_and_session_metrics_exclude_nonfinite_returns(self):
        df=self.frame(6)
        df.loc[0,"retorno_24h_pct"]=float("nan")
        df.loc[1,"retorno_24h_pct"]=float("inf")
        df.loc[2,"retorno_24h_pct"]=float("-inf")
        folds=temporal_folds(df,"24h",folds=3)
        sessions=session_metrics(df,"24h",min_samples=1)
        self.assertEqual(int(folds["Amostra"].sum()),3)
        self.assertEqual(int(sessions["Amostra"].sum()),3)


    def test_invalid_stability_thresholds_fail_closed(self):
        folds=temporal_folds(self.frame(90),"24h",folds=3)
        for bad in (0,-1,float("nan"),float("inf"),True,"bad"):
            with self.subTest(min_fold=bad):
                s=stability_summary(folds,min_fold_samples=bad)
                self.assertEqual(s["status"],"INSUFFICIENT")
                self.assertFalse(s["thresholds_valid"])
            with self.subTest(session=bad):
                self.assertTrue(session_metrics(self.frame(20),"24h",min_samples=bad).empty)
            with self.subTest(folds=bad):
                self.assertTrue(temporal_folds(self.frame(90),"24h",folds=bad).empty)

    def test_invalid_spread_limit_fails_closed(self):
        folds=temporal_folds(self.frame(90),"24h",folds=3)
        for bad in (-1,float("nan"),float("inf"),"bad"):
            with self.subTest(spread=bad):
                s=stability_summary(folds,min_fold_samples=30,max_hit_rate_spread_pp=bad)
                self.assertEqual(s["status"],"INSUFFICIENT")
                self.assertFalse(s["thresholds_valid"])


if __name__=="__main__":
    unittest.main()
