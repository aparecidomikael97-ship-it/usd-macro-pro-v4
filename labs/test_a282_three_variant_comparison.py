"""A282: fair, bounded, fixed-parameter descriptive comparison in offline LAB."""
from datetime import datetime, timezone
from unittest import mock
import unittest

import atlasquant_aion_three_variant_comparison_lab as compare
from atlasquant_aion_three_variant_comparison_lab import (
    SCHEMA, SPEC, MAX_SERIES, MIN_HOLDOUT_TRADES,
    compare_causal_variants_csv, compare_causal_variants_batch,
)
from labs.test_a280_causal_structure_lab import ROWS, NOW, stamp
from labs.test_a281_causal_ob_fvg_priority import file_data, ob_only_rows


def single(**overrides):
    options = {
        "symbol": "EURUSD", "timeframe": "M15", "timestamp_basis": "CLOSE",
        "now": NOW, "validation_start": stamp(8),
        "cost_r": 0.1, "slippage_r": 0.05,
        "max_wait_bars": 3, "max_hold_bars": 4,
    }
    csv_text = overrides.pop("csv_text", file_data(ob_only_rows(), {10: 16}))
    options.update(overrides)
    return compare_causal_variants_csv(csv_text, **options)


def series(symbol="EURUSD", timeframe="M15", csv_text=None, boundary=None):
    return {
        "symbol": symbol, "timeframe": timeframe,
        "timestamp_basis": "CLOSE",
        "csv_text": (csv_text if csv_text is not None
                     else file_data(ob_only_rows(), {10: 16})),
        "validation_start": boundary or stamp(8),
    }


def batch(slices=None, **kw):
    opts = {"now": NOW, "cost_r": 0.1, "slippage_r": 0.05,
            "max_wait_bars": 3, "max_hold_bars": 4}
    opts.update(kw)
    return compare_causal_variants_batch(
        [series()] if slices is None else slices, **opts
    )


class A282ThreeVariantComparisonTests(unittest.TestCase):
    def test_01_provenance_and_security_remain_unattested_no_go(self):
        result = single()
        self.assertEqual(result["schema"], SCHEMA)
        self.assertTrue(result["valid"])
        self.assertTrue(result["historical_only"])
        self.assertTrue(result["research_only"])
        self.assertFalse(result["source_is_externally_attested"])
        self.assertFalse(result["holdout_is_independently_attested"])
        self.assertFalse(result["historical_plans_captured_in_real_time"])
        self.assertFalse(result["actual_market_return_prediction"])
        self.assertFalse(result["actual_ict_zones_verified"])
        self.assertFalse(result["authorizes_send"])
        self.assertTrue(result["no_orders"])
        self.assertTrue(result["no_alerts"])
        self.assertEqual(result["p0_homologated"], 0)

    def test_02_three_fixed_model_labels_no_search_or_ranking(self):
        result = single()
        labels = [row["model"] for row in result["models"]]
        self.assertEqual(labels, [
            "FVG_SMA5", "FVG_BOS", "FVG_BOS_PLUS_OB_PROXY",
        ])
        self.assertTrue(SPEC["no_winner_selection"])
        self.assertTrue(SPEC["no_adaptive_parameter_selection"])
        self.assertTrue(result["no_model_ranking"])
        self.assertNotIn("winner", result)
        self.assertNotIn("recommended_model", result)

    def test_03_identical_csv_hash_and_normalized_history_for_all(self):
        result = single()
        self.assertEqual(len({
            row["source_raw_csv_sha256"] for row in result["models"]
        }), 1)
        self.assertEqual(len({
            row["source_normalized_candles_sha256"]
            for row in result["models"]
        }), 1)
        self.assertEqual(
            result["raw_csv_sha256"],
            result["models"][2]["source_raw_csv_sha256"],
        )

    def test_04_identical_split_and_costs_for_all(self):
        result = single()
        for row in result["models"]:
            self.assertEqual(row["validation_start_utc"], stamp(8))
            self.assertEqual(row["assumed_cost_r"], 0.1)
            self.assertEqual(row["assumed_slippage_r"], 0.05)
            self.assertTrue(row["no_lookahead_execution"])
            self.assertTrue(row["single_position_per_asset"])
            self.assertEqual(row["train"]["candle_count"], 8)
            self.assertEqual(row["holdout"]["candle_count"], 12)

    def test_05_filter_counts_cannot_increase_baseline_fvg(self):
        result = single()
        a, b, c = result["models"]
        self.assertGreaterEqual(a["historical_candidate_count"],
                                b["historical_candidate_count"])
        self.assertGreaterEqual(c["historical_candidate_count"],
                                b["historical_candidate_count"])

    def test_06_minimum_30_executed_holdout_trades_not_met(self):
        result = single()
        self.assertEqual(MIN_HOLDOUT_TRADES, 30)
        self.assertFalse(result["all_models_have_at_least_30_holdout_trades"])
        self.assertEqual(result["status"],
                         "INSUFFICIENT_HOLDOUT_SAMPLE_FOR_COMPARISON")
        self.assertTrue(all(
            not r["holdout"]["adequate_descriptive_sample"]
            for r in result["models"]
        ))

    def test_07_no_trade_report_not_conflated_with_high_win_rate(self):
        result = single(csv_text=file_data([(10, 10.4, 9.6)] * 20))
        self.assertTrue(result["valid"])
        for row in result["models"]:
            self.assertEqual(row["historical_candidate_count"], 0)
            self.assertEqual(row["holdout"]["summary"]["trades"], 0)
            self.assertEqual(row["holdout"]["summary"]["sample_status"],
                             "INSUFFICIENT_SAMPLE")

    def test_08_train_and_holdout_separate_even_if_first_has_no_trades(self):
        result = single()
        for row in result["models"]:
            self.assertEqual(row["train"]["summary"]["trades"], 0)
            self.assertEqual(row["train"]["summary"]["sample_status"],
                             "INSUFFICIENT_SAMPLE")
            self.assertNotEqual(row["train"]["ledger_sha256"],
                                row["holdout"]["ledger_sha256"])

    def test_09_repeated_evaluation_is_deterministic(self):
        self.assertEqual(single(), single())

    def test_10_unknown_asset_rejected_without_partial_models(self):
        result = single(symbol="US100")
        self.assertFalse(result["valid"])
        self.assertEqual(result["models"], [])
        self.assertFalse(result["authorizes_send"])

    def test_11_unresolved_futures_expiry_rejected(self):
        result = single(symbol="WINZ26")
        self.assertFalse(result["valid"])
        self.assertEqual(result["models"], [])

    def test_12_corrupt_ohlc_rejected(self):
        bad = file_data(ROWS).replace("16,16.5,15.5,16", "16,NaN,15.5,16")
        result = single(csv_text=bad)
        self.assertFalse(result["valid"])
        self.assertEqual(result["models"], [])

    def test_13_split_boundary_not_actual_candle_rejected(self):
        result = single(validation_start="2026-10-01T00:07:00+00:00")
        self.assertFalse(result["valid"])
        self.assertEqual(result["models"], [])

    def test_14_invalid_cost_fails_closed(self):
        for cost in (-1, float("nan"), True):
            with self.subTest(cost=str(cost)):
                result = single(cost_r=cost)
                self.assertFalse(result["valid"])
                self.assertEqual(result["models"], [])

    def test_15_bad_windows_cannot_bypass_a277_engine(self):
        result = single(max_wait_bars=0)
        self.assertFalse(result["valid"])
        self.assertEqual(result["models"], [])

    def test_16_stress_friction_scenarios_preserved_without_ranking(self):
        result = single()
        for row in result["models"]:
            scenarios = row["holdout"]["friction_scenarios"]
            self.assertEqual([x["scenario"] for x in scenarios], [
                "ZERO_FRICTION", "CONFIGURED", "STRESS_X2",
            ])
            self.assertEqual(len(row["holdout"]["friction_scenarios_sha256"]), 64)
        self.assertNotIn("pooled_net_r", result)

    def test_17_batch_separates_fx_and_index_risk_units(self):
        result = batch([series(), series(symbol="US30")])
        self.assertTrue(result["valid"])
        self.assertEqual(result["series_count"], 2)
        self.assertEqual([x["symbol"] for x in result["series"]],
                         ["EURUSD", "US30"])
        self.assertEqual(result["models"], [])
        self.assertTrue(result["no_pooling_or_winner_selection"])
        self.assertTrue(result["no_cross_asset_r_aggregation"])
        self.assertNotIn("portfolio_net_r", result)

    def test_18_batch_separates_timeframes(self):
        data = file_data(ob_only_rows(), {10: 16})
        # H1 must have its own valid, hourly spaced series.
        hourly_lines = ["closed_at,open,high,low,close"]
        for i, (_, high, low) in enumerate(ob_only_rows()):
            close = ob_only_rows()[i][0]
            opened = 16 if i == 10 else close
            hourly_lines.append(
                f"{stamp(i*4)},{opened},{high},{low},{close}"
            )
        hourly_csv = "\n".join(hourly_lines) + "\n"
        result = batch([
            series(), series(timeframe="H1", csv_text=hourly_csv,
                             boundary=stamp(8*4)),
        ])
        self.assertTrue(result["valid"])
        self.assertEqual([x["timeframe"] for x in result["series"]],
                         ["M15", "H1"])

    def test_19_duplicate_symbol_and_timeframe_rejected(self):
        result = batch([series(), series()])
        self.assertFalse(result["valid"])
        self.assertEqual(result["error"], "DUPLICATE_SYMBOL_TIMEFRAME")
        self.assertEqual(result["series"], [])

    def test_20_batch_limit_and_empty_batch_rejected(self):
        for items in ([], [series()] * (MAX_SERIES + 1), "wrong"):
            with self.subTest(n=len(items)):
                result = batch(items)
                self.assertFalse(result["valid"])
                self.assertEqual(result["series_count"], 0)

    def test_21_batch_strict_schema_rejects_unknown_fields(self):
        item = series()
        item["api_key"] = "should_not_be_accepted"
        result = batch([item])
        self.assertFalse(result["valid"])
        self.assertTrue(result["error"].startswith("INVALID_SERIES_FIELDS_AT_"))
        self.assertEqual(result["series"], [])

    def test_22_late_batch_failure_discards_prior_completed_series(self):
        invalid = series(symbol="BTCUSD")
        result = batch([series(), invalid])
        self.assertFalse(result["valid"])
        self.assertEqual(result["series"], [])
        self.assertEqual(result["series_count"], 0)
        self.assertFalse(result["authorizes_send"])

    def test_23_invalid_unhashable_id_does_not_raise(self):
        item = series()
        item["symbol"] = ["EURUSD"]
        result = batch([item])
        self.assertFalse(result["valid"])
        self.assertEqual(result["error"], "INVALID_SERIES_ID_AT_0")

    def test_24_cross_model_source_mismatch_fails_entire_group(self):
        original = compare.research_causal_fvg_backtest_csv
        def tampered(*a, **kw):
            response = original(*a, **kw)
            response["raw_csv_sha256"] = "0" * 64
            return response
        patched = (
            ("FVG_SMA5", tampered, "candidate_count"),
            compare.MODELS[1], compare.MODELS[2],
        )
        with mock.patch.object(compare, "MODELS", patched):
            result = single()
        self.assertFalse(result["valid"])
        self.assertEqual(result["error"], "CROSS_MODEL_COMPARABILITY_FAILURE")
        self.assertEqual(result["models"], [])

    def test_25_partition_threshold_contract_is_descriptive_only(self):
        simple = {
            "summary": {"trades": 30, "signals": 30, "no_trade": 0,
                        "sample_status": "DESCRIPTIVE_ONLY_NO_PREDICTION"},
            "ledger": [{"status": "TARGET", "net_r": 1.0}] * 30,
            "friction_scenarios": [], "censored_trades": 0,
            "candle_count": 100,
        }
        viewed = compare._partition_view(simple)
        self.assertTrue(viewed["adequate_descriptive_sample"])
        simple["summary"]["sample_status"] = "INSUFFICIENT_SAMPLE"
        self.assertIsNone(compare._partition_view(simple))

    def test_26_batch_uses_no_network_and_no_real_p0_assertion(self):
        result = batch()
        self.assertTrue(result["valid"])
        self.assertTrue(result["no_new_data_calls"])
        self.assertTrue(result["no_orders"])
        self.assertTrue(result["no_alerts"])
        self.assertFalse(result["authorizes_send"])
        self.assertEqual(result["p0_homologated"], 0)
        self.assertFalse(result["source_is_externally_attested"])


if __name__ == "__main__":
    unittest.main()
