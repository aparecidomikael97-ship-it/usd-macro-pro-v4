"""A283 LAB: untrusted offline CSV preflight, quality and A282-only comparison."""
from datetime import datetime, timedelta, timezone
from unittest import mock
import unittest

import atlasquant_aion_csv_readiness_lab as a283
from atlasquant_aion_csv_readiness_lab import (
    SCHEMA, SPEC, MIN_TRAIN_CANDLES, MIN_HOLDOUT_CANDLES,
    preflight_historical_csv, compare_if_preflight_ready_csv,
    compare_if_preflight_ready_batch,
)
from atlasquant_aion_three_variant_comparison_lab import MAX_SERIES

START = datetime(2026, 9, 30, 22, 0, tzinfo=timezone.utc)
NOW = datetime(2026, 10, 30, 12, tzinfo=timezone.utc)


def stamp(i, period=15, gap_at=None, extra_minutes=30):
    shifted = extra_minutes if gap_at is not None and i >= gap_at else 0
    return (START + timedelta(minutes=i*period + shifted)).isoformat()


def dataset(n=240, *, period=15, flat=False, gap_at=None):
    lines = ["closed_at,open,high,low,close"]
    for i in range(n):
        price = 100.0 if flat else round(100 + (i % 17 - 8) * 0.2, 4)
        if flat:
            high = low = price
        else:
            high, low = round(price + 0.6, 4), round(price - 0.6, 4)
        lines.append(f"{stamp(i,period,gap_at)},{price},{high},{low},{price}")
    return "\n".join(lines) + "\n"


def one_input(**kw):
    base = {
        "csv_text": dataset(), "symbol": "EURUSD",
        "timeframe": "M15", "timestamp_basis": "CLOSE",
        "now": NOW, "validation_start": stamp(120),
    }
    base.update(kw)
    return base


def preflight(**kw):
    return preflight_historical_csv(**one_input(**kw))


def compare(**kw):
    data = one_input(**kw)
    return compare_if_preflight_ready_csv(
        **data, cost_r=0.1, slippage_r=0.05,
        max_wait_bars=3, max_hold_bars=4,
    )


def slice_(symbol="EURUSD", timeframe="M15", **kw):
    data = one_input(symbol=symbol, timeframe=timeframe, **kw)
    data.pop("now")
    return data


def batch(items=None, **kw):
    options = {
        "now": NOW, "cost_r": 0.1, "slippage_r": 0.05,
        "max_wait_bars": 3, "max_hold_bars": 4,
    }
    options.update(kw)
    return compare_if_preflight_ready_batch(
        [slice_()] if items is None else items, **options
    )


class A283HistoricalCsvReadinessTests(unittest.TestCase):
    def test_01_structural_gate_never_claims_external_authenticity(self):
        result = preflight()
        self.assertEqual(result["schema"], SCHEMA)
        self.assertTrue(result["valid"])
        self.assertTrue(result["ready_for_offline_research"])
        self.assertFalse(result["external_provider_attested"])
        self.assertFalse(result["source_export_time_attested"])
        self.assertFalse(result["market_sessions_verified"])
        self.assertFalse(result["data_origin_authenticity_verified"])
        self.assertFalse(result["strategy_edge_proven"])
        self.assertTrue(result["historical_only"])
        self.assertFalse(result["authorizes_send"])
        self.assertEqual(result["p0_homologated"], 0)

    def test_02_same_split_has_at_least_100_closed_candles_each(self):
        result = preflight()
        self.assertEqual(MIN_TRAIN_CANDLES, 100)
        self.assertEqual(MIN_HOLDOUT_CANDLES, 100)
        self.assertEqual(result["total_candles"], 240)
        self.assertEqual(result["train"]["candle_count"], 120)
        self.assertEqual(result["holdout"]["candle_count"], 120)
        self.assertEqual(result["validation_start_utc"], stamp(120))
        self.assertEqual(result["blocking_reasons"], [])

    def test_03_quality_counts_nonflat_and_close_diversity(self):
        result = preflight()
        self.assertEqual(result["train"]["distinct_close_values"], 17)
        self.assertEqual(result["holdout"]["distinct_close_values"], 17)
        self.assertEqual(result["train"]["nonflat_ohlc_bars"], 120)
        self.assertEqual(result["holdout"]["flat_ohlc_bars"], 0)
        self.assertEqual(len(result["normalized_candles_sha256"]), 64)

    def test_04_100_plus_100_exact_threshold_passes_structure(self):
        result = preflight(csv_text=dataset(200), validation_start=stamp(100))
        self.assertTrue(result["valid"])
        self.assertTrue(result["ready_for_offline_research"])
        self.assertEqual(result["holdout"]["candle_count"], 100)

    def test_05_short_history_blocked_without_attempting_comparison(self):
        result = compare(csv_text=dataset(180), validation_start=stamp(90))
        self.assertFalse(result["valid"])
        self.assertEqual(result["status"], "BLOCKED_INSUFFICIENT_STRUCTURAL_SAMPLE")
        self.assertIn("TRAIN_TOO_FEW_CANDLES", result["blocking_reasons"])
        self.assertIn("HOLDOUT_TOO_FEW_CANDLES", result["blocking_reasons"])
        self.assertIsNone(result["comparison"])

    def test_06_long_but_flat_history_is_not_structurally_ready(self):
        result = preflight(csv_text=dataset(flat=True))
        self.assertTrue(result["valid"])
        self.assertFalse(result["ready_for_offline_research"])
        self.assertIn("TRAIN_LOW_CLOSE_DIVERSITY", result["blocking_reasons"])
        self.assertIn("HOLDOUT_TOO_FEW_NONFLAT_BARS", result["blocking_reasons"])

    def test_07_missing_intervals_are_advisory_not_fabricated_feed_outage(self):
        result = preflight(csv_text=dataset(gap_at=150))
        self.assertTrue(result["valid"])
        self.assertTrue(result["ready_for_offline_research"])
        self.assertEqual(result["spacing"]["intervals_longer_than_one_period"], 1)
        self.assertEqual(result["spacing"]["elapsed_empty_periods_lower_bound"], 2)
        self.assertFalse(result["spacing"]["missing_candles_proven"])
        self.assertIn(
            "INTERVAL_GAPS_NOT_ATTRIBUTABLE_TO_MARKET_VS_FEED",
            result["advisory_warnings"],
        )

    def test_08_normal_fixed_intervals_have_no_advisory_warning(self):
        result = preflight()
        self.assertEqual(result["spacing"]["intervals_longer_than_one_period"], 0)
        self.assertEqual(result["spacing"]["nonintegral_period_intervals"], 0)
        self.assertEqual(result["spacing"]["max_interval_minutes"], 15)
        self.assertEqual(result["advisory_warnings"], [])

    def test_09_utc_boundary_must_match_exact_closed_candle(self):
        result = preflight(validation_start="2026-10-02T03:01:00+00:00")
        self.assertFalse(result["valid"])
        self.assertFalse(result["ready_for_offline_research"])
        self.assertEqual(result["error"], "BOUNDARY_NOT_A_CLOSED_CANDLE")

    def test_10_naive_boundary_is_not_accepted(self):
        result = preflight(validation_start="2026-10-02T03:00:00")
        self.assertFalse(result["valid"])
        self.assertEqual(result["error"], "BOUNDARY_NOT_A_CLOSED_CANDLE")

    def test_11_corrupt_ohlc_blocks_before_research(self):
        bad = dataset().replace("99.0,99.6,98.4,99.0", "99.0,NaN,98.4,99.0")
        result = preflight(csv_text=bad)
        self.assertFalse(result["valid"])
        self.assertTrue(result["error"].startswith("INVALID_CSV:"))
        self.assertFalse(result["authorizes_send"])

    def test_12_unknown_symbols_and_futures_contract_alias_rejected(self):
        for symbol in ("BTCUSD", "US100", "WINZ26", "EUR/USD"):
            with self.subTest(symbol=symbol):
                result = preflight(symbol=symbol)
                self.assertFalse(result["valid"])

    def test_13_nonfx_roots_remain_unresolved_not_contract_validated(self):
        for symbol in ("WIN", "WDO"):
            with self.subTest(symbol=symbol):
                result = preflight(symbol=symbol)
                self.assertTrue(result["valid"])
                self.assertTrue(result["ready_for_offline_research"])
                self.assertIn(
                    "FUTURES_CONTRACT_EXPIRY_NOT_RESOLVED",
                    result["advisory_warnings"],
                )
                self.assertFalse(result["data_origin_authenticity_verified"])

    def test_14_hourly_timeframe_uses_only_its_own_hourly_series(self):
        result = preflight(
            csv_text=dataset(period=60), timeframe="H1",
            validation_start=stamp(120, period=60),
        )
        self.assertTrue(result["valid"])
        self.assertTrue(result["ready_for_offline_research"])
        self.assertEqual(result["spacing"]["expected_timeframe_minutes"], 60)
        self.assertEqual(result["spacing"]["max_interval_minutes"], 60)

    def test_15_timeframe_mismatch_fails_importer(self):
        result = preflight(timeframe="H1")
        self.assertFalse(result["valid"])
        self.assertTrue(result["error"].startswith("INVALID_CSV:"))

    def test_16_open_basis_advances_effective_closed_time(self):
        # Supplied timestamps are candle OPEN times, not already closed.
        result = preflight(
            timestamp_basis="OPEN",
            validation_start=stamp(121),
        )
        self.assertTrue(result["valid"])
        self.assertEqual(result["train"]["candle_count"], 120)
        self.assertEqual(result["holdout"]["first_closed_at"], stamp(121))

    def test_17_preflighted_comparison_keeps_a282_30_trade_warning(self):
        result = compare()
        self.assertTrue(result["valid"])
        self.assertTrue(result["ready_for_offline_research"])
        self.assertTrue(result["comparison"]["valid"])
        self.assertEqual(
            result["comparison_sample_status"],
            "INSUFFICIENT_HOLDOUT_SAMPLE_FOR_COMPARISON",
        )
        self.assertEqual(len(result["comparison"]["models"]), 3)
        self.assertFalse(result["comparison"]["authorizes_send"])
        self.assertTrue(result["no_orders"])

    def test_18_csv_sha_and_holdout_boundary_must_match_a282(self):
        result = compare()
        p = result["preflights"][0]
        c = result["comparison"]
        self.assertEqual(p["raw_csv_sha256"], c["raw_csv_sha256"])
        self.assertEqual(p["normalized_candles_sha256"],
                         c["normalized_candles_sha256"])
        self.assertEqual(p["validation_start_utc"], c["validation_start_utc"])

    def test_19_corrupted_a282_digest_blocks_comparison(self):
        original = a283.compare_causal_variants_csv
        def tampered(*args, **kw):
            result = original(*args, **kw)
            result["normalized_candles_sha256"] = "0" * 64
            return result
        with mock.patch.object(a283, "compare_causal_variants_csv", tampered):
            result = compare()
        self.assertFalse(result["valid"])
        self.assertEqual(result["error"], "A282_PREFLIGHT_CONTRACT_MISMATCH")
        self.assertIsNone(result["comparison"])

    def test_20_invalid_cost_fails_in_a282_without_partial_result(self):
        result = compare_if_preflight_ready_csv(
            **one_input(), cost_r=-1, slippage_r=0.05
        )
        self.assertFalse(result["valid"])
        self.assertTrue(result["error"].startswith("A282:"))
        self.assertIsNone(result["comparison"])

    def test_21_batch_preflights_forex_and_index_separately(self):
        result = batch([slice_(), slice_(symbol="US30")])
        self.assertTrue(result["valid"])
        self.assertEqual(result["series_count"], 2)
        self.assertEqual([x["symbol"] for x in result["preflights"]],
                         ["EURUSD", "US30"])
        self.assertEqual(len(result["comparison"]["series"]), 2)
        self.assertTrue(result["no_pooled_cross_asset_results"])
        self.assertNotIn("pooled_net_r", result)

    def test_22_batch_late_bad_source_never_returns_partial_results(self):
        result = batch([slice_(), slice_(symbol="US100")])
        self.assertFalse(result["valid"])
        self.assertEqual(result["preflights"], [])
        self.assertIsNone(result["comparison"])
        self.assertEqual(result["series_count"], 0)
        self.assertFalse(result["authorizes_send"])

    def test_23_batch_late_short_sample_prevents_any_backtest(self):
        bad = slice_(
            symbol="US30", csv_text=dataset(180),
            validation_start=stamp(90),
        )
        with mock.patch.object(a283, "compare_causal_variants_batch") as runner:
            result = batch([slice_(), bad])
        runner.assert_not_called()
        self.assertFalse(result["valid"])
        self.assertIn("HOLDOUT_TOO_FEW_CANDLES", result["blocking_reasons"])
        self.assertIsNone(result["comparison"])

    def test_24_duplicate_symbol_and_timeframe_blocked(self):
        result = batch([slice_(), slice_()])
        self.assertFalse(result["valid"])
        self.assertEqual(result["error"], "DUPLICATE_SYMBOL_TIMEFRAME")

    def test_25_batch_size_bound_and_unknown_metadata_rejected(self):
        for inputs in ([], [slice_()] * (MAX_SERIES + 1), "bad"):
            with self.subTest(size=len(inputs)):
                result = batch(inputs)
                self.assertFalse(result["valid"])
                self.assertIsNone(result["comparison"])
        extra = slice_()
        extra["provider_token"] = "extra field"
        result = batch([extra])
        self.assertFalse(result["valid"])
        self.assertEqual(result["error"], "INVALID_SERIES_FIELDS_0")

    def test_26_readiness_does_not_mean_30_trades_or_real_data(self):
        result = compare()
        self.assertTrue(result["ready_for_offline_research"])
        self.assertFalse(result["comparison"]["all_models_have_at_least_30_holdout_trades"])
        self.assertFalse(result["external_provider_attested"])
        self.assertFalse(result["data_origin_authenticity_verified"])
        self.assertFalse(result["source_export_time_attested"])
        self.assertFalse(result["future_lookahead_proven_absent_from_strategy_selection"])

    def test_27_deterministic_sample_hash_and_spec(self):
        self.assertEqual(preflight(), preflight())
        self.assertEqual(preflight()["spec_sha256"], a283._digest(SPEC))

    def test_28_never_workers_alerts_deploy_orders_or_p0_promotion(self):
        for result in (preflight(), compare(), batch()):
            self.assertTrue(result["no_new_data_calls"])
            self.assertTrue(result["no_orders"])
            self.assertTrue(result["no_alerts"])
            self.assertFalse(result["authorizes_send"])
            self.assertEqual(result["p0_homologated"], 0)
            self.assertTrue(result["no_live_readiness_claim"])


if __name__ == "__main__":
    unittest.main()
