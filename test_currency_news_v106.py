import unittest
import pandas as pd

try:
    import streamlit  # noqa
except Exception:
    import sys, types
    st = types.ModuleType("streamlit")
    st.session_state = {}
    def cache_data(*args, **kwargs):
        def deco(fn): return fn
        return deco
    st.cache_data = cache_data
    sys.modules["streamlit"] = st

from currency_news_v106 import (
    CURRENCY_PROFILES, analyze_articles, pair_news_table, _jaccard,
    _headline_impact, _source_factor, _recency_factor
)

class CurrencyNewsV106Tests(unittest.TestCase):
    def test_has_eight_currencies(self):
        self.assertEqual(set(CURRENCY_PROFILES), {"USD","EUR","GBP","JPY","CHF","CAD","AUD","NZD"})

    def test_dedup_similarity(self):
        a = "Bank of England signals rates may stay high for longer"
        b = "Bank of England signals rates may stay higher for longer"
        self.assertGreater(_jaccard(a, b), 0.70)

    def test_hawkish_supports_currency(self):
        impact, direction, _ = _headline_impact(
            "GBP",
            "Bank of England turns hawkish and signals rates may stay higher for longer"
        )
        self.assertGreater(impact, 0)
        self.assertIn("Fortalece", direction)

    def test_dovish_weakens_currency(self):
        impact, direction, _ = _headline_impact(
            "CAD",
            "Bank of Canada turns dovish and opens door to more rate cuts"
        )
        self.assertLess(impact, 0)
        self.assertIn("Enfraquece", direction)

    def test_cad_oil_relationship(self):
        impact, _, _ = _headline_impact(
            "CAD",
            "Canadian dollar gains as oil rises and Bank of Canada holds rates"
        )
        self.assertGreaterEqual(impact, 0)

    def test_source_weight(self):
        self.assertGreater(_source_factor("Reuters"), _source_factor("random blog"))

    def test_recency_decay(self):
        now = pd.Timestamp.now(tz="UTC")
        recent = _recency_factor((now - pd.Timedelta(hours=2)).isoformat())
        old = _recency_factor((now - pd.Timedelta(days=6)).isoformat())
        self.assertGreater(recent, old)

    def test_article_aggregate(self):
        now = pd.Timestamp.now(tz="UTC").isoformat()
        items = [
            {
                "title":"Bank of Japan turns hawkish and signals a rate hike",
                "published_at":now, "source":"Reuters", "link":"", "provider":"test"
            },
            {
                "title":"Japan wages rise stronger than expected",
                "published_at":now, "source":"Nikkei", "link":"", "provider":"test"
            },
        ]
        out = analyze_articles("JPY", items)
        self.assertGreater(out["news_score"], 50)
        self.assertGreater(out["article_count"], 0)

    def test_pair_alignment(self):
        intelligence = {"currencies":{
            "EUR":{"net_impact":-4,"news_score":30,"coverage_quality":80},
            "USD":{"net_impact":4,"news_score":70,"coverage_quality":90},
            "GBP":{"net_impact":0,"news_score":50,"coverage_quality":80},
            "AUD":{"net_impact":0,"news_score":50,"coverage_quality":80},
            "NZD":{"net_impact":0,"news_score":50,"coverage_quality":80},
            "JPY":{"net_impact":0,"news_score":50,"coverage_quality":80},
            "CHF":{"net_impact":0,"news_score":50,"coverage_quality":80},
            "CAD":{"net_impact":0,"news_score":50,"coverage_quality":80},
        }}
        matrix = pd.DataFrame([{"Par":"EUR/USD","Direção":"VENDA EUR/USD"}])
        df = pair_news_table(intelligence, matrix)
        row = df[df["Par"]=="EUR/USD"].iloc[0]
        self.assertEqual(row["Alinhamento"], "🟢 CONFIRMA")
        self.assertIn("VENDA", row["Notícias"])

if __name__ == "__main__":
    unittest.main()
