import unittest
import pandas as pd

from engine import audit_quality, closed_candles, historical_close, pair_ready, period_age


class ValidationTests(unittest.TestCase):
    def test_monthly_reference_period(self):
        self.assertEqual(period_age("PCE anual", "01/07/2026", "2026-09-13"), 44)

    def test_quarterly_reference_period(self):
        self.assertEqual(period_age("PIB", "01/04/2026", "2026-09-13"), 75)

    def test_daily_missing_and_bad_observation(self):
        self.assertEqual(period_age("Treasury 2 anos", "10/09/2026", "2026-09-13"), 3)
        self.assertIsNone(period_age("PIB", None))
        self.assertIsNone(period_age("PIB", "not-a-date"))

    def test_quality_requires_observations(self):
        self.assertEqual(audit_quality([])[0], 0)
        self.assertEqual(
            audit_quality([
                {"Status": "🟢 Atual", "Fonte": "FRED · X"},
                {"Status": "Fallback", "Fonte": "Valor de segurança"},
            ])[0],
            50,
        )

    def test_pair_blocks_fallback_and_bad_pair(self):
        rows = [{"Status": "🟢 Atual", "Fonte": "FRED"}]
        self.assertFalse(pair_ready("EUR/USD", rows, {"EUR": {"fonte": "FRED + fallback parcial"}}))
        self.assertTrue(pair_ready("EUR/USD", rows, {"EUR": {"fonte": "FRED + transformação anual"}}))
        self.assertFalse(pair_ready("EURUSD", rows, {"EUR": {"fonte": "FRED"}}))

    def test_numeric_strings_and_open_candles(self):
        df = pd.DataFrame([
            {"datetime": "2026-09-10 12:00Z", "open": "1", "high": "2", "low": ".5", "close": "1.2"},
            {"datetime": "2026-09-10 12:15Z", "open": 1, "high": 2, "low": .5, "close": 1.3},
        ])
        out = closed_candles(df, "15min", "2026-09-10 12:20Z")
        self.assertEqual(len(out), 1)
        self.assertAlmostEqual(float(out.iloc[0]["close"]), 1.2)

    def test_invalid_geometry_excluded(self):
        df = pd.DataFrame([
            {"datetime": "2026-09-10 12:00Z", "open": 1, "high": .1, "low": .5, "close": 1.3},
            {"datetime": "2026-09-10 12:00Z", "open": 1, "high": 2, "low": .5, "close": 1.2},
        ])
        out = closed_candles(df, "15min", "2026-09-10 12:20Z")
        self.assertEqual(len(out), 1)

    def test_missing_columns_and_bad_interval(self):
        with self.assertRaises(ValueError):
            closed_candles(pd.DataFrame([{"datetime": "2026-09-10"}]), "15min", "2026-09-10 12:20Z")
        with self.assertRaises(ValueError):
            closed_candles(pd.DataFrame(columns=["datetime", "open", "high", "low", "close"]), "5min")

    def test_stale_candles_rejected(self):
        df = pd.DataFrame([
            {"datetime": "2026-09-10 12:00Z", "open": 1, "high": 2, "low": .5, "close": 1.2},
        ])
        with self.assertRaises(ValueError):
            closed_candles(df, "15min", "2026-09-11 12:20Z")

    def history(self, timestamp, target="2026-09-10 12:15Z", now="2026-09-12 12:00Z", close="1.25"):
        class Response:
            def raise_for_status(self):
                pass
            def json(self):
                return {"values": [{"datetime": timestamp, "close": close}]}
        return historical_close("EUR/USD", target, "fake", lambda *a, **k: Response(), now)

    def test_horizon_uses_close_time(self):
        result = self.history("2026-09-10 12:00Z")
        self.assertEqual(result[0], 1.25)
        self.assertEqual(pd.Timestamp(result[1]), pd.Timestamp("2026-09-10 12:15Z"))

    def test_distant_history_rejected(self):
        self.assertIsNone(self.history("2026-09-11 12:00Z")[0])

    def test_unclosed_historical_bar_rejected(self):
        result = self.history("2026-09-10 12:15Z", target="2026-09-10 12:20Z", now="2026-09-10 12:25Z")
        self.assertIsNone(result[0])

    def test_future_horizon_and_missing_key(self):
        future = historical_close("EUR/USD", "2026-09-11 12:00Z", "fake", lambda *a, **k: None, "2026-09-10 12:00Z")
        self.assertIn("ainda não venceu", future[2])
        missing = historical_close("EUR/USD", "2026-09-10 12:00Z", "", lambda *a, **k: None, "2026-09-10 13:00Z")
        self.assertIn("ausente", missing[2])

    def test_bad_provider_payload_stays_safe(self):
        class Response:
            def raise_for_status(self):
                pass
            def json(self):
                return [1, 2, 3]
        result = historical_close("EUR/USD", "2026-09-10 12:00Z", "fake", lambda *a, **k: Response(), "2026-09-10 13:00Z")
        self.assertIsNone(result[0])
        self.assertIn("inesperada", result[2])


if __name__ == "__main__":
    unittest.main()
