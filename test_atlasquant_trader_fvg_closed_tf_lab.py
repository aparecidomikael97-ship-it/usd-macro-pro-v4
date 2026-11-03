"""Synthetic three-candle FVG geometry, no future data or trading."""
import copy
import unittest
from datetime import datetime, timedelta, timezone

from atlasquant_trader_fvg_closed_tf_lab import (
    SCHEMA, study_fvg_closed_timeframes_lab,
)

NOW = datetime(2026, 10, 30, 20, tzinfo=timezone.utc)
START = datetime(2026, 10, 30, 8, tzinfo=timezone.utc)


def candle(minutes, open_, high, low, close):
    return {
        "open_at_utc": (START + timedelta(minutes=minutes)).isoformat(),
        "open": open_, "high": high, "low": low, "close": close,
    }


def book():
    return {
        "state": "LAB_SYNTHETIC_OHLC_ONLY",
        "source": "SYNTHETIC_FIXTURE_ONLY",
        "symbol": "EUR/USD", "price_kind": "SYNTHETIC_BID_OHLC",
        "as_of_utc": "2026-10-30T20:00:00Z",
        "timeframes": {
            "M15": [
                candle(0, "1.1000", "1.1005", "1.0995", "1.1000"),
                candle(15, "1.1020", "1.1030", "1.1015", "1.1025"),
                candle(30, "1.1040", "1.1045", "1.1020", "1.1035"),
            ],
            "H1": [
                candle(0, "1.1000", "1.1010", "1.0995", "1.1005"),
                candle(60, "1.1005", "1.1010", "1.0999", "1.1006"),
                candle(120, "1.1006", "1.1010", "1.0998", "1.1002"),
            ],
            "H4": [
                candle(0, "1.1000", "1.1030", "1.0990", "1.1005"),
            ],
        },
    }


def evaluate(data=None, at=NOW):
    return study_fvg_closed_timeframes_lab(book() if data is None else data, evaluated_at=at)


class FvgClosedTfLabTests(unittest.TestCase):
    def test_bullish_m15_gap_formed_only_after_third_candle_closes(self):
        out = evaluate()
        self.assertEqual(out["schema"], SCHEMA)
        self.assertEqual(out["state"], "LAB_FVG_STRUCTURAL_STUDY_ONLY")
        m15 = out["timeframe_checks"]["M15"]
        self.assertEqual(m15["state"], "LAB_CLOSED_CANDLES_ONLY")
        self.assertEqual(len(m15["candidates"]), 1)
        candidate = m15["candidates"][0]
        self.assertEqual(candidate["timeframe"], "M15")
        self.assertEqual(candidate["direction"], "BULLISH")
        self.assertEqual(candidate["lower"], "1.1005")
        self.assertEqual(candidate["upper"], "1.1020")
        self.assertEqual(candidate["formed_after_utc"], "2026-10-30T08:45:00+00:00")
        self.assertEqual(candidate["subsequent_state"], "UNTESTED")
        self.assertFalse(candidate["trade_signal"])

    def test_h1_does_not_inherit_m15_gap_and_h4_needs_more_history(self):
        out = evaluate()["timeframe_checks"]
        self.assertEqual(out["H1"]["candidates"], [])
        self.assertEqual(out["H4"]["state"], "INSUFFICIENT_HISTORY")
        self.assertEqual(out["H4"]["candidates"], [])

    def test_h1_bearish_gap_is_labeled_only_as_h1(self):
        data = book()
        data["timeframes"]["H1"] = [
            candle(0, "1.1055", "1.1060", "1.1050", "1.1055"),
            candle(60, "1.1040", "1.1045", "1.1035", "1.1040"),
            candle(120, "1.1025", "1.1030", "1.1020", "1.1025"),
        ]
        out = evaluate(data)["timeframe_checks"]["H1"]
        self.assertEqual(out["state"], "LAB_CLOSED_CANDLES_ONLY")
        self.assertEqual(len(out["candidates"]), 1)
        self.assertEqual(out["candidates"][0]["direction"], "BEARISH")
        self.assertEqual(out["candidates"][0]["timeframe"], "H1")

    def test_m15_gap_touched_only_by_later_closed_candle(self):
        data = book()
        data["timeframes"]["M15"].append(
            candle(45, "1.1020", "1.1025", "1.1010", "1.1018"))
        out = evaluate(data)["timeframe_checks"]["M15"]["candidates"][0]
        self.assertEqual(out["subsequent_state"], "TOUCHED")
        self.assertEqual(out["formed_after_utc"], "2026-10-30T08:45:00+00:00")

    def test_m15_gap_fully_filled_only_by_later_closed_candle(self):
        data = book()
        data["timeframes"]["M15"].append(
            candle(45, "1.1020", "1.1024", "1.1000", "1.1010"))
        out = evaluate(data)["timeframe_checks"]["M15"]["candidates"][0]
        self.assertEqual(out["subsequent_state"], "FULLY_FILLED")

    def test_small_gap_below_uncalibrated_threshold_not_emitted(self):
        data = book()
        data["timeframes"]["M15"][2] = (
            candle(30, "1.1010", "1.1015", "1.1006", "1.1010"))
        self.assertEqual(evaluate(data)["timeframe_checks"]["M15"]["candidates"], [])

    def test_h4_candidate_requires_three_complete_h4_candles(self):
        data = book()
        data["timeframes"]["H4"] = [
            candle(0, "1.1000", "1.1005", "1.0995", "1.1000"),
            candle(240, "1.1020", "1.1030", "1.1010", "1.1020"),
            candle(480, "1.1040", "1.1050", "1.1020", "1.1040"),
        ]
        data["as_of_utc"] = "2026-10-30T20:00:00Z"
        h4 = evaluate(data)["timeframe_checks"]["H4"]
        self.assertEqual(h4["state"], "LAB_CLOSED_CANDLES_ONLY")
        self.assertEqual(h4["candidates"][0]["timeframe"], "H4")

    def test_unclosed_last_candle_is_refused(self):
        data = book()
        data["as_of_utc"] = "2026-10-30T10:59:59Z"
        checks = evaluate(data)["timeframe_checks"]
        self.assertEqual(checks["H1"]["state"], "QUARANTINED")
        self.assertEqual(checks["H4"]["state"], "QUARANTINED")

    def test_gaps_duplicates_and_reversed_order_are_not_scanned(self):
        for minutes in (15, 60):
            data = book()
            data["timeframes"]["M15"][2]["open_at_utc"] = (
                START + timedelta(minutes=minutes)).isoformat()
            self.assertEqual(evaluate(data)["timeframe_checks"]["M15"]["state"],
                             "QUARANTINED")

    def test_wrong_timeframe_alignment_is_denied_without_guessing_broker_clock(self):
        data = book()
        data["timeframes"]["H1"][0]["open_at_utc"] = (
            START + timedelta(minutes=30)).isoformat()
        self.assertEqual(evaluate(data)["timeframe_checks"]["H1"]["state"], "QUARANTINED")

    def test_unzoned_and_non_utc_candle_are_denied(self):
        for value in ("2026-10-30T08:00:00", "2026-10-30T10:00:00+02:00"):
            data = book()
            data["timeframes"]["M15"][0]["open_at_utc"] = value
            self.assertEqual(evaluate(data)["timeframe_checks"]["M15"]["state"], "QUARANTINED")

    def test_malformed_ohlc_and_nan_fail_closed(self):
        for key, value in (("high", "1.0000"), ("close", "NaN"),
                           ("open", None), ("low", True)):
            data = book()
            data["timeframes"]["M15"][1][key] = value
            self.assertEqual(evaluate(data)["timeframe_checks"]["M15"]["state"], "QUARANTINED")

    def test_extra_timeframe_or_book_claim_refused(self):
        data = book()
        data["timeframes"]["D1"] = []
        self.assertEqual(evaluate(data)["state"], "LAB_FVG_INPUT_QUARANTINED")
        data = book()
        data["trade_authorized"] = True
        self.assertEqual(evaluate(data)["state"], "LAB_FVG_INPUT_QUARANTINED")

    def test_only_explicit_synthetic_input_accepted(self):
        for field, changed in (("state", "REAL_FVG"), ("source", "BROKER_LIVE"),
                               ("price_kind", "TRADABLE_ASK"), ("symbol", "INVALID")):
            data = book()
            data[field] = changed
            self.assertEqual(evaluate(data)["state"], "LAB_FVG_INPUT_QUARANTINED")

    def test_future_book_clock_and_naive_evaluation_denied(self):
        data = book()
        data["as_of_utc"] = "2026-11-03T00:00:00Z"
        self.assertEqual(evaluate(data)["state"], "LAB_FVG_INPUT_QUARANTINED")
        with self.assertRaises(ValueError):
            evaluate(at=datetime(2026, 10, 30, 20))

    def test_not_a_real_zone_or_trade_in_success_or_refusal(self):
        for result in (evaluate(), evaluate({})):
            self.assertEqual(result["verified_market_zones"], 0)
            self.assertIsNone(result["live_bias"])
            self.assertIsNone(result["live_radar"])
            self.assertIsNone(result["trade_signal"])
            for k in ("predictive_accuracy_proven", "can_feed_live_radar",
                      "can_feed_real_oos", "trade_authorized",
                      "worker_enabled", "scheduler_enabled"):
                self.assertFalse(result[k], k)


if __name__ == "__main__":
    unittest.main()
