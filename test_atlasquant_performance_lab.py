import unittest
import pandas as pd

from atlasquant_performance_lab import (
    prepare_performance_history, overall_metrics, grouped_metrics,
    performance_readiness, available_dimensions,
)


class AtlasQuantPerformanceLabTests(unittest.TestCase):
    def frame(self):
        return pd.DataFrame({
            "registrado_em":[
                "2026-01-01T00:00:00Z","2026-01-02T00:00:00Z",
                "2026-02-01T00:00:00Z","2026-03-01T00:00:00Z",
            ],
            "par":["EUR/USD","EUR/USD","GBP/USD","GBP/USD"],
            "direcao":["BUY","BUY","SELL","SELL"],
            "score_mestre":[75,85,92,92],
            "qualidade":["80%","70%","90%","90%"],
            "retorno_1h_pct":[1.0,-1.0,0.5,-0.25],
            "retorno_4h_pct":[1.2,-0.8,0.7,-0.1],
            "retorno_24h_pct":[2.0,-1.0,1.0,-0.5],
        })

    def test_prepare_uses_only_completed_rows(self):
        df=self.frame()
        df.loc[0,"retorno_24h_pct"]=None
        out=prepare_performance_history(df,"24h")
        self.assertEqual(len(out),3)

    def test_overall_metrics(self):
        m=overall_metrics(self.frame(),"24h")
        self.assertEqual(m["samples"],4)
        self.assertEqual(m["wins"],2)
        self.assertEqual(m["losses"],2)
        self.assertEqual(m["hit_rate_pct"],50.0)

    def test_grouped_by_pair(self):
        g=grouped_metrics(self.frame(),"24h","par",min_group_samples=2)
        self.assertEqual(set(g["par"]),{"EUR/USD","GBP/USD"})
        self.assertTrue(g["Amostra suficiente"].all())

    def test_score_and_quality_dimensions_exist(self):
        data=prepare_performance_history(self.frame(),"24h")
        dims=available_dimensions(data)
        self.assertIn("Faixa Score",dims)
        self.assertIn("Faixa Qualidade",dims)
        self.assertIn("Mês",dims)

    def test_optional_session_dimension(self):
        df=self.frame(); df["sessao"]=["London","London","NY","NY"]
        data=prepare_performance_history(df,"24h")
        self.assertIn("sessao",available_dimensions(data))

    def test_small_sample_is_building(self):
        r=performance_readiness(self.frame(),"24h",min_total_samples=100,min_group_samples=2)
        self.assertEqual(r["status"],"BUILDING")
        self.assertFalse(r["auto_model_change_allowed"])

    def test_reviewable_requires_breadth(self):
        rows=[]
        for month in ("2026-01","2026-02","2026-03"):
            for pair in ("EUR/USD","GBP/USD"):
                for i in range(30):
                    rows.append({
                        "registrado_em":f"{month}-01T00:00:00Z",
                        "par":pair,"direcao":"BUY","score_mestre":80,
                        "qualidade":"80%","retorno_24h_pct":1.0 if i%2==0 else -0.5,
                    })
        r=performance_readiness(pd.DataFrame(rows),"24h",min_total_samples=100,min_group_samples=30)
        self.assertEqual(r["status"],"REVIEWABLE")
        self.assertFalse(r["auto_model_change_allowed"])

    def test_missing_required_columns_fails_closed(self):
        self.assertTrue(prepare_performance_history(pd.DataFrame({"x":[1]}),"24h").empty)


    def test_nonfinite_returns_are_excluded_from_all_performance_metrics(self):
        df=self.frame()
        df.loc[0,"retorno_24h_pct"]=float("nan")
        df.loc[1,"retorno_24h_pct"]=float("inf")
        df.loc[2,"retorno_24h_pct"]=float("-inf")
        out=prepare_performance_history(df,"24h")
        self.assertEqual(len(out),1)
        m=overall_metrics(df,"24h")
        self.assertEqual(m["samples"],1)
        self.assertTrue(pd.notna(m["mean_return_pct"]))


if __name__=="__main__":
    unittest.main()
