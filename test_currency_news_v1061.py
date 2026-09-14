import unittest
import pandas as pd

try:
    import streamlit  # noqa
except Exception:
    import sys, types
    st = types.ModuleType("streamlit")
    st.session_state = {}
    def cache_data(*args, **kwargs):
        def deco(fn):
            fn.clear = lambda: None
            return fn
        return deco
    st.cache_data = cache_data
    st.secrets = {}
    sys.modules["streamlit"] = st

from currency_news_v1061 import (
    CURRENCY_PROFILES,
    _assign_global_story_clusters,
    analyze_articles,
    pair_news_table,
    _directional_return_v1061,
    _validation_columns_v1061,
)

class CurrencyNewsV1061Tests(unittest.TestCase):
    def test_global_cluster_reduces_independence(self):
        now = pd.Timestamp.now(tz="UTC").isoformat()
        raw = {
            "USD": [{"title":"Fed and ECB signal rates may stay high", "published_at":now, "source":"Reuters"}],
            "EUR": [{"title":"Fed and ECB signal rates may stay higher", "published_at":now, "source":"Reuters"}],
            "GBP": [], "JPY": [], "CHF": [], "CAD": [], "AUD": [], "NZD": [],
        }
        clustered, meta = _assign_global_story_clusters(raw, threshold=0.60)
        self.assertEqual(meta["global_unique_stories"], 1)
        self.assertEqual(meta["global_shared_stories"], 1)
        self.assertLess(clustered["USD"][0]["independence_factor"], 1.0)
        self.assertEqual(clustered["USD"][0]["shared_currency_count"], 2)

    def test_confidence_and_coverage_are_capped(self):
        now = pd.Timestamp.now(tz="UTC").isoformat()
        items = []
        for i in range(20):
            items.append({
                "title": f"Bank of England hawkish rate hike signal stronger than expected item {i}",
                "published_at": now,
                "source": "Reuters",
                "independence_factor": 1.0,
                "shared_currency_count": 1,
                "shared_currencies": "GBP",
            })
        out = analyze_articles("GBP", items)
        self.assertLessEqual(out["directional_confidence"], 90)
        self.assertLessEqual(out["coverage_quality"], 92)

    def test_directional_return(self):
        self.assertAlmostEqual(_directional_return_v1061("BUY", 100, 101), 1.0, places=6)
        self.assertAlmostEqual(_directional_return_v1061("SELL", 100, 99), 1.0, places=6)

    def test_validation_schema(self):
        cols = _validation_columns_v1061()
        for c in ("hit_1h", "hit_4h", "hit_24h", "alignment", "conviction"):
            self.assertIn(c, cols)

    def test_pair_table_has_calibration_fields(self):
        intelligence = {"currencies":{
            "EUR":{"net_impact":-4,"news_score":35,"coverage_quality":70,
                   "directional_confidence":60,"effective_independent_stories":5},
            "USD":{"net_impact":4,"news_score":65,"coverage_quality":75,
                   "directional_confidence":65,"effective_independent_stories":6},
            "GBP":{"net_impact":0,"news_score":50,"coverage_quality":50,
                   "directional_confidence":20,"effective_independent_stories":3},
            "AUD":{"net_impact":0,"news_score":50,"coverage_quality":50,
                   "directional_confidence":20,"effective_independent_stories":3},
            "NZD":{"net_impact":0,"news_score":50,"coverage_quality":50,
                   "directional_confidence":20,"effective_independent_stories":3},
            "JPY":{"net_impact":0,"news_score":50,"coverage_quality":50,
                   "directional_confidence":20,"effective_independent_stories":3},
            "CHF":{"net_impact":0,"news_score":50,"coverage_quality":50,
                   "directional_confidence":20,"effective_independent_stories":3},
            "CAD":{"net_impact":0,"news_score":50,"coverage_quality":50,
                   "directional_confidence":20,"effective_independent_stories":3},
        }}
        matrix = pd.DataFrame([{"Par":"EUR/USD","Direção":"VENDA EUR/USD"}])
        df = pair_news_table(intelligence, matrix)
        row = df[df["Par"]=="EUR/USD"].iloc[0]
        self.assertEqual(row["Alinhamento"], "🟢 CONFIRMA")
        self.assertIn("Convicção heurística", df.columns)
        self.assertIn("Histórias independentes", df.columns)

if __name__ == "__main__":
    unittest.main()
