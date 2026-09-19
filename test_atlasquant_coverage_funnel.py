import unittest
import pandas as pd

from atlasquant_coverage_funnel import (
    build_coverage_matrix, coverage_summary, expansion_watchlist,
    DEFAULT_OPERATIONAL_PAIRS,
)


class AtlasQuantCoverageFunnelTests(unittest.TestCase):
    def setUp(self):
        self.ranking=pd.DataFrame({
            "Código":["USD","EUR","GBP","JPY","CHF","CAD","AUD","NZD"],
            "Pontuação_Final":[80,60,75,35,50,45,55,40],
        })

    def test_covers_all_28_pairs(self):
        m=build_coverage_matrix(self.ranking)
        self.assertEqual(len(m),28)

    def test_exactly_seven_default_full_pipeline_pairs(self):
        m=build_coverage_matrix(self.ranking)
        self.assertEqual(int((m["Cobertura operacional"]=="PIPELINE COMPLETO").sum()),7)
        self.assertEqual(set(m[m["Cobertura operacional"]=="PIPELINE COMPLETO"]["Par"]),set(DEFAULT_OPERATIONAL_PAIRS))

    def test_macro_only_pairs_never_executable(self):
        m=build_coverage_matrix(self.ranking)
        macro=m[m["Cobertura operacional"]=="RADAR MACRO"]
        self.assertTrue((macro["Pode receber status executável?"]=="NÃO").all())

    def test_summary_is_28_7_21(self):
        s=coverage_summary(build_coverage_matrix(self.ranking))
        self.assertEqual(s["total"],28)
        self.assertEqual(s["full"],7)
        self.assertEqual(s["macro_only"],21)
        self.assertEqual(s["coverage_pct"],25.0)

    def test_expansion_watchlist_excludes_operational_pairs(self):
        m=build_coverage_matrix(self.ranking)
        w=expansion_watchlist(m,5)
        self.assertTrue(set(w["Par"]).isdisjoint(set(DEFAULT_OPERATIONAL_PAIRS)))

    def test_custom_supported_pairs(self):
        m=build_coverage_matrix(self.ranking,operational_pairs=("EUR/NZD",))
        self.assertEqual(int((m["Cobertura operacional"]=="PIPELINE COMPLETO").sum()),1)


    def test_watchlist_excludes_nonfinite_intensity_and_invalid_top_n(self):
        m=build_coverage_matrix(self.ranking).copy()
        idx=m.index[m["Cobertura operacional"]=="RADAR MACRO"][:3]
        m.loc[idx[0],"Intensidade relativa"]=float("nan")
        m.loc[idx[1],"Intensidade relativa"]=float("inf")
        m.loc[idx[2],"Intensidade relativa"]=float("-inf")
        w=expansion_watchlist(m,top_n=28)
        self.assertTrue(pd.to_numeric(w["Intensidade relativa"],errors="coerce").map(lambda x: pd.notna(x) and abs(float(x))!=float("inf")).all())
        self.assertTrue(expansion_watchlist(m,top_n=0).empty)
        self.assertTrue(expansion_watchlist(m,top_n="bad").empty)

    def test_watchlist_missing_required_columns_fails_closed(self):
        self.assertTrue(expansion_watchlist(pd.DataFrame({"Par":["EUR/GBP"]})).empty)


if __name__=="__main__":
    unittest.main()
