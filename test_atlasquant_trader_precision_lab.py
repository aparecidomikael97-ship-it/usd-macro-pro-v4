"""LAB regression contract: exactly 28 pair currency context and FVG/OB resolution."""
from datetime import datetime, timedelta, timezone
from math import log
import unittest

from atlasquant_trader_precision_lab import (
    CURRENCIES, PAIRS, PairWindow, Zone,
    assess_28_pair_strength, resolve_near_fvg_ob,
)

T0 = datetime(2026, 10, 27, 0, 0, tzinfo=timezone.utc)
T1 = T0 + timedelta(hours=1)
NOW = T1 + timedelta(minutes=1)


def all_windows(returns=None):
    returns = returns or {}
    return {
        p: PairWindow(returns.get(p, 0.0), T0, T1, "fixed_research_feed")
        for p in PAIRS
    }


def strength(data):
    return assess_28_pair_strength(
        data, now=NOW, max_age=timedelta(minutes=5)
    )


def zone(ident, *, kind="FVG", lo=1.10, hi=1.11, q=0.8,
         side="BUY", pair="EURUSD", tf="H1", invalid=False, epoch=100):
    return Zone(ident, pair, tf, side, kind, lo, hi, q, epoch, invalid)


ATR = {("EURUSD", "H1"): 0.01, ("EURUSD", "H4"): 0.02,
       ("GBPUSD", "H1"): 0.01}


class Full28PairStrengthTests(unittest.TestCase):
    def test_01_full_unique_fx_universe(self):
        self.assertEqual(len(PAIRS), 28)
        self.assertEqual(len(set(PAIRS)), 28)
        self.assertEqual(set(CURRENCIES),
                         {c for pair in PAIRS for c in (pair[:3], pair[3:])})
        for c in CURRENCIES:
            self.assertEqual(sum(c in (p[:3], p[3:]) for p in PAIRS), 7)

    def test_02_flat_market_zero_currency_strength(self):
        out = strength(all_windows())
        self.assertTrue(out.ready_for_research)
        self.assertTrue(all(v == 0 for v in out.currency_scores.values()))
        self.assertEqual(out.max_abs_residual, 0)

    def test_03_exact_latent_cross_section_recovered(self):
        latent = {c: (i - 3.5) * 0.001 for i, c in enumerate(CURRENCIES)}
        data = all_windows({p: latent[p[:3]] - latent[p[3:]] for p in PAIRS})
        out = strength(data)
        self.assertTrue(out.ready_for_research)
        for c in CURRENCIES:
            self.assertAlmostEqual(out.currency_scores[c], latent[c], places=12)
        self.assertAlmostEqual(out.max_abs_residual, 0, places=12)

    def test_04_pair_context_is_antisymmetric_by_definition(self):
        data = all_windows({"EURUSD": log(1.01), "GBPUSD": log(0.99)})
        out = strength(data)
        self.assertAlmostEqual(sum(out.currency_scores.values()), 0, places=12)
        self.assertAlmostEqual(
            out.pair_context["EURUSD"],
            out.currency_scores["EUR"] - out.currency_scores["USD"],
        )

    def test_05_triangle_inconsistency_exposed_as_residual(self):
        out = strength(all_windows({"EURUSD": 0.01}))
        self.assertTrue(out.ready_for_research)
        self.assertGreater(out.max_abs_residual, 0)
        self.assertEqual(out.reason, "relative_strength_not_entry_signal")

    def test_06_missing_pair_fails_closed(self):
        data = all_windows()
        data.pop("CHFJPY")
        self.assertFalse(strength(data).ready_for_research)

    def test_07_extra_or_unrecognized_pair_fails_closed(self):
        data = all_windows()
        data["EURRUB"] = data["EURUSD"]
        self.assertFalse(strength(data).ready_for_research)

    def test_08_nan_inf_bool_invalid_inputs_fail_closed(self):
        for bad in (float("nan"), float("inf"), True, "0.01"):
            with self.subTest(value=str(bad)):
                data = all_windows()
                data["GBPJPY"] = PairWindow(bad, T0, T1, "fixed_research_feed")
                self.assertFalse(strength(data).ready_for_research)

    def test_09_stale_and_future_data_fail_closed(self):
        self.assertFalse(assess_28_pair_strength(
            all_windows(), now=T1+timedelta(days=1),
            max_age=timedelta(minutes=5)).ready_for_research)
        self.assertFalse(assess_28_pair_strength(
            all_windows(), now=T0, max_age=timedelta(minutes=5)
        ).ready_for_research)

    def test_10_mixed_feed_or_window_fails_closed(self):
        data = all_windows()
        data["USDJPY"] = PairWindow(0.0, T0, T1, "other-feed")
        self.assertFalse(strength(data).ready_for_research)
        data["USDJPY"] = PairWindow(0.0, T0+timedelta(minutes=1), T1, "fixed_research_feed")
        self.assertFalse(strength(data).ready_for_research)

    def test_11_naive_and_reversed_timestamps_fail_closed(self):
        data = all_windows()
        data["EURGBP"] = PairWindow(0.0, T0.replace(tzinfo=None), T1, "fixed_research_feed")
        self.assertFalse(strength(data).ready_for_research)
        data["EURGBP"] = PairWindow(0.0, T1, T0, "fixed_research_feed")
        self.assertFalse(strength(data).ready_for_research)

    def test_12_nonpositive_ttl_fails_closed(self):
        for ttl in (timedelta(0), timedelta(minutes=-1)):
            self.assertFalse(assess_28_pair_strength(
                all_windows(), now=NOW, max_age=ttl).ready_for_research)


class NearFvgObTests(unittest.TestCase):
    def test_13_higher_quality_fvg_suppresses_near_ob(self):
        out = resolve_near_fvg_ob([
            zone("a-fvg", q=0.95),
            zone("b-ob", kind="OB", lo=1.111, hi=1.121, q=0.75)
        ], ATR)
        self.assertEqual([x.origin_id for x in out.selected], ["a-fvg"])
        self.assertEqual(out.suppressed_by, (("b-ob", "a-fvg"),))

    def test_14_better_quality_ob_wins_not_blind_fvg_bias(self):
        out = resolve_near_fvg_ob([
            zone("a-fvg", q=0.75),
            zone("b-ob", kind="OB", lo=1.111, hi=1.121, q=0.95)
        ], ATR)
        self.assertEqual([x.origin_id for x in out.selected], ["b-ob"])

    def test_15_exact_score_tie_prefers_fvg(self):
        out = resolve_near_fvg_ob([
            zone("z-ob", kind="OB"),
            zone("a-fvg")
        ], ATR)
        self.assertEqual([x.origin_id for x in out.selected], ["a-fvg"])

    def test_16_far_apart_zones_remain_distinct(self):
        out = resolve_near_fvg_ob([
            zone("a-fvg"), zone("b-ob", kind="OB", lo=1.12, hi=1.13)
        ], ATR)
        self.assertEqual(len(out.selected), 2)
        self.assertEqual(out.suppressed_by, ())

    def test_17_opposite_sides_not_deduplicated(self):
        out = resolve_near_fvg_ob([
            zone("buy"), zone("sell", kind="OB", side="SELL")
        ], ATR)
        self.assertEqual(len(out.selected), 2)

    def test_18_other_pair_and_timeframe_not_deduplicated(self):
        out = resolve_near_fvg_ob([
            zone("h1"), zone("h4", kind="OB", tf="H4"),
            zone("gbp", kind="OB", pair="GBPUSD")
        ], ATR)
        self.assertEqual(len(out.selected), 3)

    def test_19_invalidated_zone_excluded(self):
        out = resolve_near_fvg_ob([
            zone("invalid", q=1.0, invalid=True), zone("valid", q=0.3)
        ], ATR)
        self.assertEqual([x.origin_id for x in out.selected], ["valid"])
        self.assertEqual(out.invalidated_ids, ("invalid",))

    def test_20_duplicate_identity_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "duplicate origin"):
            resolve_near_fvg_ob([zone("same"), zone("same", kind="OB")], ATR)

    def test_21_invalid_score_bounds_and_atr_fail_closed(self):
        for bad_score in (float("nan"), -0.1, 1.1, True):
            with self.subTest(score=str(bad_score)), self.assertRaises(ValueError):
                resolve_near_fvg_ob([zone("x", q=bad_score)], ATR)
        with self.assertRaisesRegex(ValueError, "ATR"):
            resolve_near_fvg_ob([zone("x")], {})
        with self.assertRaisesRegex(ValueError, "proximity"):
            resolve_near_fvg_ob([zone("x")], ATR, max_gap_atr=-1)

    def test_22_input_order_does_not_change_winner(self):
        a, b = zone("a", q=0.95), zone("b", kind="OB", q=0.90)
        forward = resolve_near_fvg_ob([a, b], ATR)
        reverse = resolve_near_fvg_ob([b, a], ATR)
        self.assertEqual(forward, reverse)

    def test_23_per_winner_suppression_does_not_overmerge_chain(self):
        out = resolve_near_fvg_ob([
            zone("a", lo=1.100, hi=1.101, q=0.99),
            zone("b", lo=1.102, hi=1.103, q=0.90),
            zone("c", lo=1.104, hi=1.105, q=0.80),
        ], ATR, max_gap_atr=0.15)
        self.assertEqual({z.origin_id for z in out.selected}, {"a", "c"})
        self.assertEqual(out.suppressed_by, (("b", "a"),))


if __name__ == "__main__":
    unittest.main(verbosity=2)
