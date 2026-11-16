"""Offline cache bridge tests: no network, no writes, no signal promotion."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from math import exp
import unittest

from atlasquant_instrument_registry import FX_28, FX_CURRENCIES
from atlasquant_trader_precision_cache_bridge_lab import (
    assess_existing_fx28_cache_offline,
)

NOW = datetime(2026, 10, 27, 12, 40, tzinfo=timezone.utc)
T0 = datetime(2026, 10, 27, 12, 0, tzinfo=timezone.utc)
T1 = T0 + timedelta(minutes=15)
FETCH = T0 + timedelta(minutes=35)
AGE = timedelta(minutes=30)


def candle(ts, close):
    return {"datetime": ts.isoformat(), "open": close,
            "high": close * 1.001, "low": close * 0.999,
            "close": close}


def cache(latent=None):
    latent = latent or {c: 0.0 for c in FX_CURRENCIES}
    rows = {}
    for pair in FX_28:
        log_ret = latent[pair[:3]] - latent[pair[3:]]
        symbol = pair[:3] + "/" + pair[3:] + "|15min"
        rows[symbol] = {
            "fetched_at": FETCH.isoformat(),
            "records": [candle(T0, 1.0), candle(T1, exp(log_ret))],
        }
    return {"series": rows}


def evaluate(state, *, now=NOW, age=AGE):
    return assess_existing_fx28_cache_offline(state, now=now, max_age=age)


class TraderCacheBridgeTests(unittest.TestCase):
    def test_01_all_28_closed_synchronized_pairs_are_context_only(self):
        result = evaluate(cache())
        self.assertTrue(result.ready_for_research)
        self.assertEqual(len(result.strength.currency_scores), 8)
        self.assertEqual(len(result.strength.pair_context), 28)
        self.assertFalse(hasattr(result, "allows_trading"))

    def test_02_latent_relative_fx_strength_is_recovered(self):
        latent = {c: (i - 3.5) * 0.0005 for i, c in enumerate(sorted(FX_CURRENCIES))}
        result = evaluate(cache(latent))
        self.assertTrue(result.ready_for_research)
        for currency in FX_CURRENCIES:
            self.assertAlmostEqual(
                result.strength.currency_scores[currency], latent[currency],
                places=12)

    def test_03_one_missing_pair_blocks_all_strength_not_27_28(self):
        state = cache()
        state["series"].pop("CHF/JPY|15min")
        result = evaluate(state)
        self.assertFalse(result.ready_for_research)
        self.assertEqual(result.missing_pairs, ("CHFJPY",))
        self.assertIsNone(result.strength)

    def test_04_alias_duplicate_denied_instead_of_arbitrary_preference(self):
        state = cache()
        state["series"]["EURUSD|15min"] = deepcopy(state["series"]["EUR/USD|15min"])
        result = evaluate(state)
        self.assertEqual(result.invalid_pairs, ("EURUSD",))

    def test_05_bare_symbol_works_as_documented_alias(self):
        state = cache()
        state["series"]["EURUSD|15min"] = state["series"].pop("EUR/USD|15min")
        self.assertTrue(evaluate(state).ready_for_research)

    def test_06_future_or_stale_provider_fetch_denied(self):
        for bad in (NOW + timedelta(seconds=1), NOW - timedelta(hours=2)):
            with self.subTest(fetched=str(bad)):
                state = cache()
                state["series"]["USD/JPY|15min"]["fetched_at"] = bad.isoformat()
                self.assertIn("USDJPY", evaluate(state).invalid_pairs)

    def test_07_bad_candle_value_ohlc_and_nonfinite_denied(self):
        for bad in (-1.0, float("nan"), True, "1.2"):
            with self.subTest(close=str(bad)):
                state = cache()
                state["series"]["USD/CAD|15min"]["records"][-1]["close"] = bad
                self.assertIn("USDCAD", evaluate(state).invalid_pairs)
        state = cache()
        state["series"]["USD/CAD|15min"]["records"][-1]["high"] = 0.5
        self.assertIn("USDCAD", evaluate(state).invalid_pairs)

    def test_08_naive_or_malformed_timestamp_denied(self):
        for timestamp in ("2026-10-27T12:15:00", "not-a-time"):
            with self.subTest(ts=timestamp):
                state = cache()
                state["series"]["EUR/GBP|15min"]["records"][-1]["datetime"] = timestamp
                self.assertIn("EURGBP", evaluate(state).invalid_pairs)

    def test_09_duplicate_bar_timestamp_denied(self):
        state = cache()
        row = state["series"]["EUR/CHF|15min"]["records"]
        row[-1]["datetime"] = row[0]["datetime"]
        self.assertIn("EURCHF", evaluate(state).invalid_pairs)

    def test_10_candle_gap_bigger_than_m15_denied(self):
        state = cache()
        row = state["series"]["EUR/JPY|15min"]["records"]
        row[0]["datetime"] = (T0 - timedelta(minutes=15)).isoformat()
        self.assertIn("EURJPY", evaluate(state).invalid_pairs)

    def test_11_last_open_candle_ignored_without_lookahead(self):
        state = cache()
        for row in state["series"].values():
            row["records"].append(candle(T1 + timedelta(minutes=15), 10.0))
        result = evaluate(state)
        self.assertTrue(result.ready_for_research)
        self.assertEqual(result.strength.max_abs_residual, 0.0)

    def test_12_one_different_closed_window_denies_global_result(self):
        state = cache()
        state["series"]["GBP/JPY|15min"]["records"] = [
            candle(T0-timedelta(minutes=15), 1.0), candle(T0, 1.0)]
        result = evaluate(state)
        self.assertFalse(result.ready_for_research)
        self.assertEqual(result.reason, "different_time_windows_or_feeds")

    def test_13_invalid_top_level_or_naive_now_fail_closed(self):
        for state in (None, {}, [], {"series": []}):
            self.assertFalse(evaluate(state).ready_for_research)
        self.assertFalse(evaluate(cache(), now=NOW.replace(tzinfo=None)).ready_for_research)

    def test_14_read_only_input_including_unrelated_cache_keys(self):
        state = cache()
        state["series"]["BTC/USD|15min"] = {"unrelated": True}
        old = deepcopy(state)
        self.assertTrue(evaluate(state).ready_for_research)
        self.assertEqual(state, old)

    def test_15_minimum_age_and_fetched_before_close_fail(self):
        self.assertFalse(evaluate(cache(), age=timedelta(0)).ready_for_research)
        state = cache()
        state["series"]["NZD/JPY|15min"]["fetched_at"] = T1.isoformat()
        self.assertIn("NZDJPY", evaluate(state).invalid_pairs)


if __name__ == "__main__":
    unittest.main(verbosity=2)
