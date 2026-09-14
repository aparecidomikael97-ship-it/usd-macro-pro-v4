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

from currency_news_v1062 import (
    _backfill_today_rows_v1062,
    _validation_columns_v1061,
)

def intel():
    cur = {}
    for c in ("USD","EUR","GBP","JPY","CHF","CAD","AUD","NZD"):
        cur[c] = {
            "news_score": 60 if c == "USD" else 50,
            "effective_independent_stories": 5,
            "shared_story_ratio": 0.1,
        }
    return {"currencies": cur}

class CurrencyNewsV1062Tests(unittest.TestCase):
    def test_schema_has_backfill_fields(self):
        cols = _validation_columns_v1061()
        for c in ("signal_frozen_at", "entry_origin", "backfilled_at"):
            self.assertIn(c, cols)

    def test_backfill_existing_directional_row(self):
        day = "2026-09-14"
        df = pd.DataFrame([{
            "day_utc": day,
            "pair": "USD/CHF",
            "entry_price": None,
            "news_side": "BUY",
            "validation_status": "SEM_PRECO_FRESCO",
        }])
        pair_df = pd.DataFrame([{
            "Par": "USD/CHF",
            "Motor base": "COMPRA USD/CHF",
            "Diferencial notícias": 3.2,
            "Alinhamento": "🟢 CONFIRMA",
            "Cobertura notícias": 80,
            "Convicção heurística": 60,
        }])
        ts = pd.Timestamp("2026-09-14T15:45:00Z")
        price_map = {
            "USD/CHF": {
                "price": 0.8175,
                "fresh": True,
                "candle": ts,
                "processado_em": ts,
            }
        }
        out, n, _, pairs = _backfill_today_rows_v1062(
            df, intel(), pair_df, price_map, day, "2026-09-14T15:46:00+00:00"
        )
        self.assertEqual(n, 1)
        self.assertEqual(pairs, ["USD/CHF"])
        self.assertAlmostEqual(float(out.iloc[0]["entry_price"]), 0.8175)
        self.assertEqual(out.iloc[0]["validation_status"], "PENDENTE")
        self.assertEqual(out.iloc[0]["entry_origin"], "BACKFILL_M15_FRESCO")
        self.assertTrue(str(out.iloc[0]["signal_frozen_at"]))

    def test_never_overwrites_existing_price(self):
        day = "2026-09-14"
        df = pd.DataFrame([{
            "day_utc": day,
            "pair": "USD/CHF",
            "entry_price": 0.8100,
            "news_side": "BUY",
            "validation_status": "PENDENTE",
        }])
        pair_df = pd.DataFrame([{
            "Par": "USD/CHF",
            "Motor base": "COMPRA USD/CHF",
            "Diferencial notícias": 4.0,
            "Alinhamento": "🟢 CONFIRMA",
            "Cobertura notícias": 90,
            "Convicção heurística": 70,
        }])
        ts = pd.Timestamp("2026-09-14T16:00:00Z")
        price_map = {"USD/CHF": {"price": 0.9000, "fresh": True, "candle": ts}}
        out, n, _, _ = _backfill_today_rows_v1062(
            df, intel(), pair_df, price_map, day, "2026-09-14T16:01:00+00:00"
        )
        self.assertEqual(n, 0)
        self.assertAlmostEqual(float(out.iloc[0]["entry_price"]), 0.8100)

    def test_direction_can_become_neutral_before_price(self):
        day = "2026-09-14"
        df = pd.DataFrame([{
            "day_utc": day,
            "pair": "GBP/USD",
            "entry_price": None,
            "news_side": "SELL",
            "validation_status": "SEM_PRECO_FRESCO",
        }])
        pair_df = pd.DataFrame([{
            "Par": "GBP/USD",
            "Motor base": "VENDA GBP/USD",
            "Diferencial notícias": 0.5,
            "Alinhamento": "⚪ NEUTRO",
            "Cobertura notícias": 80,
            "Convicção heurística": 10,
        }])
        out, n, refreshed, _ = _backfill_today_rows_v1062(
            df, intel(), pair_df, {}, day, "2026-09-14T16:05:00+00:00"
        )
        self.assertEqual(n, 0)
        self.assertGreaterEqual(refreshed, 1)
        self.assertEqual(out.iloc[0]["news_side"], "NEUTRAL")
        self.assertEqual(out.iloc[0]["validation_status"], "OBSERVACAO_NEUTRA")
        self.assertTrue(pd.isna(out.iloc[0]["entry_price"]))

if __name__ == "__main__":
    unittest.main()
