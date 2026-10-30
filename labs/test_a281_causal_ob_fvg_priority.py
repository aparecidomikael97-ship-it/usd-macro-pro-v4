"""A281: causal opposite-candle OB proxies, same-close FVG preference."""
from datetime import datetime, timezone
import unittest

from atlasquant_aion_causal_ob_fvg_lab import (
    SCHEMA, SPEC, generate_causal_ob_fvg_csv,
    research_ob_fvg_backtest_csv,
)
from atlasquant_aion_causal_structure_lab import generate_causal_structure_csv
from labs.test_a280_causal_structure_lab import ROWS, NOW, stamp


def file_data(rows=ROWS, opens=None):
    altered = opens or {}
    data = ["closed_at,open,high,low,close"]
    for i, (close, high, low) in enumerate(rows):
        opened = altered.get(i, close)
        data.append(f"{stamp(i)},{opened},{high},{low},{close}")
    return "\n".join(data) + "\n"


def run(rows=ROWS, opens=None, **overrides):
    args = {
        "symbol": "EURUSD", "timeframe": "M15",
        "timestamp_basis": "CLOSE", "now": NOW,
    }
    args.update(overrides)
    return generate_causal_ob_fvg_csv(file_data(rows, opens), **args)


def study(rows=ROWS, opens=None, **overrides):
    args = {
        "symbol": "EURUSD", "timeframe": "M15",
        "timestamp_basis": "CLOSE", "now": NOW,
        "validation_start": stamp(8),
        "cost_r": 0.1, "slippage_r": 0.05,
        "max_wait_bars": 3, "max_hold_bars": 4,
    }
    args.update(overrides)
    return research_ob_fvg_backtest_csv(file_data(rows, opens), **args)


def ob_only_rows():
    modified = list(ROWS)
    # BOS remains at index 11; no same-close FVG, or gap in index 12.
    modified[11] = (20, 20.5, 16.0)
    modified[12] = (19, 19.5, 16.0)
    return modified


def down_bos_rows():
    rows = list(ROWS[:19])
    rows.extend([
        (10, 10.5, 9.5),  # index 19 pivot low
        (12, 12.5, 11.5),
        (13, 13.5, 12.5), # 21 closes -> confirms 19
        (9, 9.5, 8.5),    # 22 crosses pivot -> BOS DOWN
    ])
    return rows


def audit_at(result, index):
    return next(x for x in result["ob_audit"]
                if x["signal_time"] == stamp(index))


class A281CausalObFvgTests(unittest.TestCase):
    def test_01_mechanical_ob_is_not_institutional_attestation(self):
        result = run(opens={10: 16})
        self.assertEqual(result["schema"], SCHEMA)
        self.assertTrue(result["valid"])
        self.assertTrue(result["historical_only"])
        self.assertTrue(result["research_only"])
        self.assertFalse(result["ob_is_institutionally_verified"])
        self.assertFalse(result["fvg_superiority_proven"])
        self.assertFalse(result["plans_captured_when_generated"])
        self.assertTrue(result["no_retroactive_signal_repainting"])
        self.assertTrue(result["no_new_data_calls"])
        self.assertTrue(result["no_orders"])
        self.assertFalse(result["authorizes_send"])
        self.assertEqual(result["p0_homologated"], 0)

    def test_02_fvg_preferred_when_ob_zone_touches_same_bos_bar_gap(self):
        result = run(opens={10: 16})
        ob = audit_at(result, 11)
        self.assertEqual(ob["status"], "FVG_PREFERRED_SAME_CLOSE_NEAR_ZONE")
        self.assertFalse(ob["accepted"])
        self.assertEqual(ob["opposite_candle_time"], stamp(10))
        self.assertEqual(ob["zone_low"], 14.5)
        self.assertEqual(ob["zone_high"], 16.5)
        self.assertEqual(ob["bos_confirmed_at"], stamp(11))
        self.assertEqual(result["ob_suppressed_by_same_close_fvg"], 1)
        self.assertFalse(any(p["setup"] == "OB" and p["signal_time"] == stamp(11)
                             for p in result["combined_candidate_plans"]))
        self.assertTrue(any(p["setup"] == "FVG" and p["signal_time"] == stamp(11)
                            for p in result["combined_candidate_plans"]))

    def test_03_no_opposite_body_means_no_invented_order_block(self):
        result = run()
        self.assertTrue(result["valid"])
        self.assertEqual(result["missing_opposite_body"], 1)
        self.assertEqual(result["ob_retained"], 0)
        self.assertEqual(audit_at(result, 11)["status"],
                         "NO_OPPOSITE_BODY_IN_PAST_LOOKBACK")

    def test_04_ob_retained_when_no_same_close_fvg_nearby(self):
        result = run(ob_only_rows(), opens={10: 16})
        self.assertTrue(result["valid"])
        ob = audit_at(result, 11)
        self.assertTrue(ob["accepted"])
        self.assertEqual(ob["status"], "OB_PROXY_RETAINED")
        self.assertEqual(result["ob_retained"], 1)
        plan = next(p for p in result["combined_candidate_plans"]
                    if p["setup"] == "OB" and p["signal_time"] == stamp(11))
        self.assertEqual(plan["side"], "BUY")
        self.assertAlmostEqual(plan["entry"], 15.5)
        self.assertAlmostEqual(plan["stop"], 14.3)
        self.assertAlmostEqual(plan["target"], 17.9)

    def test_05_later_fvg_cannot_retroactively_erase_prior_ob(self):
        base = ob_only_rows()
        extended = list(base)
        extended[12] = (19, 19.5, 18.5)  # creates a new FVG at 12
        past, future = run(base, opens={10: 16}), run(extended, opens={10: 16})
        self.assertEqual(audit_at(past, 11), audit_at(future, 11))
        self.assertTrue(audit_at(past, 11)["accepted"])
        self.assertTrue(audit_at(future, 11)["accepted"])

    def test_06_prefix_deterministic_even_with_additional_future_rows(self):
        full = run(ob_only_rows(), opens={10: 16})
        prefix = run(ob_only_rows()[:12], opens={10: 16})
        self.assertEqual(prefix["ob_audit"], [a for a in full["ob_audit"]
                                              if a["signal_time"] <= stamp(11)])
        self.assertEqual(
            [p for p in prefix["combined_candidate_plans"]
             if p["signal_time"] <= stamp(11)],
            [p for p in full["combined_candidate_plans"]
             if p["signal_time"] <= stamp(11)],
        )

    def test_07_bearish_bos_can_derive_ob_from_prior_bullish_body(self):
        rows = down_bos_rows()
        result = run(rows, opens={21: 12})
        self.assertTrue(result["valid"])
        bearish = audit_at(result, 22)
        self.assertTrue(bearish["accepted"])
        self.assertEqual(bearish["side"], "SELL")
        self.assertEqual(bearish["opposite_candle_time"], stamp(21))
        plan = next(p for p in result["combined_candidate_plans"]
                    if p["setup"] == "OB" and p["signal_time"] == stamp(22))
        self.assertAlmostEqual(plan["entry"], 13.0)
        self.assertAlmostEqual(plan["stop"], 13.6)
        self.assertAlmostEqual(plan["target"], 11.8)

    def test_08_bearish_bos_missing_opposite_body_fails_closed_locally(self):
        result = run(down_bos_rows())
        self.assertTrue(result["valid"])
        self.assertEqual(audit_at(result, 22)["status"],
                         "NO_OPPOSITE_BODY_IN_PAST_LOOKBACK")

    def test_09_an_ob_never_uses_the_bos_candle_as_opposite(self):
        result = run(ob_only_rows(), opens={10: 16})
        ob = audit_at(result, 11)
        self.assertLess(ob["opposite_candle_time"], ob["signal_time"])
        self.assertLess(ob["opposite_candle_index"], 11)
        self.assertEqual(ob["observed_closed_bars"], 12)

    def test_10_one_ob_per_confirmed_bos_and_no_future_pair_dependency(self):
        result = run(ob_only_rows(), opens={10: 16})
        bos = [e for e in result["structure_events"] if e["kind"] == "BOS"]
        self.assertEqual(result["bos_events"], len(bos))
        self.assertEqual(len(result["ob_audit"]), len(bos))

    def test_11_only_one_zone_candidate_at_simultaneous_overlap(self):
        result = run(opens={10: 16})
        same = [p for p in result["combined_candidate_plans"]
                if p["signal_time"] == stamp(11)]
        self.assertEqual(len(same), 1)
        self.assertEqual(same[0]["setup"], "FVG")

    def test_12_a277_setup_comparison_uses_holdout_and_no_orders(self):
        result = study(ob_only_rows(), opens={10: 16})
        self.assertTrue(result["valid"])
        self.assertEqual(result["validation_start_utc"], stamp(8))
        self.assertEqual(result["train"]["summary"]["trades"], 0)
        self.assertGreaterEqual(result["ob_retained"], 1)
        self.assertTrue(any(x["setup"] == "OB"
                            for x in result["holdout"]["setups"]))
        self.assertFalse(result["ob_is_institutionally_verified"])
        self.assertFalse(result["authorizes_send"])
        self.assertTrue(result["no_orders"])
        self.assertEqual(result["p0_homologated"], 0)

    def test_13_prefix_hash_is_from_bos_not_future_market_context(self):
        result = run(ob_only_rows(), opens={10: 16})
        structure = generate_causal_structure_csv(
            file_data(ob_only_rows(), {10: 16}),
            symbol="EURUSD", timeframe="M15",
            timestamp_basis="CLOSE", now=NOW,
        )
        bos = next(e for e in structure["structure_events"]
                   if e["detected_at"] == stamp(11))
        self.assertEqual(audit_at(result, 11)["prefix_sha256"],
                         bos["prefix_sha256"])

    def test_14_all_radar_nonfx_remain_proxies_not_contract_mappings(self):
        for symbol in ("DXY", "US30", "NAS100", "SPX500", "IBOV", "WIN", "WDO"):
            with self.subTest(symbol=symbol):
                result = run(ob_only_rows(), opens={10: 16}, symbol=symbol)
                self.assertTrue(result["valid"])
                self.assertFalse(result["ob_is_institutionally_verified"])
                self.assertFalse(result["authorizes_send"])

    def test_15_invalid_contract_alias_and_unknown_market_refused(self):
        for symbol in ("WINZ26", "EUR/USD", "US100", "BTCUSD"):
            with self.subTest(symbol=symbol):
                result = run(symbol=symbol)
                self.assertFalse(result["valid"])
                self.assertEqual(result["combined_candidate_plans"], [])

    def test_16_invalid_csv_fails_without_partial_old_ob(self):
        text = file_data(ob_only_rows(), {10: 16})
        corrupted = text.replace("16,16.5,14.5,15", "16,NaN,14.5,15")
        result = generate_causal_ob_fvg_csv(
            corrupted, symbol="EURUSD", timeframe="M15",
            timestamp_basis="CLOSE", now=NOW,
        )
        self.assertFalse(result["valid"])
        self.assertEqual(result["ob_audit"], [])
        self.assertEqual(result["combined_candidate_plans"], [])

    def test_17_bad_cost_or_holdout_cut_never_bypasses_a277_guard(self):
        bad = study(ob_only_rows(), opens={10: 16}, cost_r=-1)
        self.assertFalse(bad["valid"])
        self.assertIsNone(bad["train"])
        self.assertIsNone(bad["holdout"])
        other = study(ob_only_rows(), opens={10: 16},
                      validation_start="2026-10-01T00:07:00+00:00")
        self.assertFalse(other["valid"])
        self.assertIsNone(other["holdout"])

    def test_18_spec_is_fixed_and_fvg_priority_is_not_asserted_superior(self):
        first, second = run(opens={10: 16}), run(opens={10: 16})
        self.assertEqual(first["strategy_spec_sha256"],
                         second["strategy_spec_sha256"])
        self.assertEqual(SPEC["opposite_candle_lookback"], 5)
        self.assertTrue(SPEC["no_retroactive_suppression"])
        self.assertFalse(first["fvg_superiority_proven"])
        self.assertEqual(first["combined_candidate_plans"],
                         second["combined_candidate_plans"])

    def test_19_research_does_not_fabricate_a278_attestation_or_live_evidence(self):
        result = study(ob_only_rows(), opens={10: 16})
        self.assertFalse(result["plans_captured_when_generated"])
        self.assertNotIn("plan_journal_head_sha256", result)
        self.assertNotIn("fresh_m15_pairs", result)
        self.assertFalse(result["authorizes_send"])
        self.assertFalse(result["ob_is_institutionally_verified"])

    def test_20_practical_scope_keeps_no_worker_orders_alerts_or_new_calls(self):
        result = run(opens={10: 16})
        self.assertTrue(result["no_new_data_calls"])
        self.assertTrue(result["no_orders"])
        self.assertTrue(result["no_alerts"])
        self.assertFalse(result["authorizes_send"])
        self.assertEqual(result["p0_homologated"], 0)


if __name__ == "__main__":
    unittest.main()
