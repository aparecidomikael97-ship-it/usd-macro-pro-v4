import unittest
import pandas as pd

from ict_structure_v111 import (
    _bias_before, _structure_events,
    detect_bos_choch, detect_order_block, build_structure_snapshot,
)


def frame(closes, spread=0.10):
    idx = pd.date_range("2026-09-15T00:00:00Z", periods=len(closes), freq="15min", tz="UTC")
    rows = []
    prev = closes[0]
    for i, close in enumerate(closes):
        open_ = prev if i else close
        rows.append({
            "datetime": idx[i],
            "open": open_,
            "high": max(open_, close) + spread,
            "low": min(open_, close) - spread,
            "close": close,
        })
        prev = close
    return pd.DataFrame(rows)


def custom_frame(rows):
    d = pd.DataFrame(rows, columns=["open","high","low","close"])
    d["datetime"] = pd.date_range(
        "2026-09-15T00:00:00Z", periods=len(d), freq="15min", tz="UTC"
    )
    return d[["datetime","open","high","low","close"]]


class ICTStructureV111Tests(unittest.TestCase):
    def test_bullish_bos_after_higher_highs_and_lows(self):
        d = frame([10,11,12,11,10.5,11.5,13,12,11.5,12.5,14,13,12.5,13.5,15])
        r = detect_bos_choch(d, "BUY")
        self.assertEqual(r["event"], "BOS")
        self.assertIn("BOS CONFIRMADO", r["status"])
        self.assertEqual(r["event_side"], "BUY")

    def test_bullish_choch_after_bearish_structure(self):
        d = frame([15,14,13,14,14.5,13,12,13,13.5,12.5,11,12,12.5,13.5,15])
        r = detect_bos_choch(d, "BUY")
        self.assertEqual(r["event"], "CHOCH")
        self.assertIn("CHOCH CONFIRMADO", r["status"])
        self.assertEqual(r["prior_bias"], "BEARISH")

    def test_bearish_bos_after_lower_highs_and_lows(self):
        d = frame([15,14,13,14,14.5,13.5,12,13,13.5,12.5,11,12,12.5,11.5,10])
        r = detect_bos_choch(d, "SELL")
        self.assertEqual(r["event"], "BOS")
        self.assertIn("BOS CONFIRMADO", r["status"])
        self.assertEqual(r["event_side"], "SELL")

    def test_bearish_choch_after_bullish_structure(self):
        d = frame([10,11,12,11,10.5,12,13,12,11.5,12.5,14,13,12.5,11.5,10])
        r = detect_bos_choch(d, "SELL")
        self.assertEqual(r["event"], "CHOCH")
        self.assertIn("CHOCH CONFIRMADO", r["status"])
        self.assertEqual(r["prior_bias"], "BULLISH")

    def test_order_block_requires_break_and_displacement(self):
        d = frame([10,11,12,11,10.5,11.5,13,12,11.5,12.5,14,13,12.5,13.5,15])
        r = detect_order_block(d, "BUY")
        self.assertIn("ORDER BLOCK", r["status"])
        self.assertGreaterEqual(r["score"], 68)
        self.assertLess(r["zone_low"], r["zone_high"])
        self.assertEqual(r["structure_event"], "BOS")

    def test_order_block_mitigation(self):
        d = frame([10,11,12,11,10.5,11.5,13,12,11.5,12.5,14,13,12.5,13.5,15,13.0])
        r = detect_order_block(d, "BUY")
        self.assertIn("MITIGAÇÃO", r["status"])
        self.assertTrue(r["inside"])
        self.assertFalse(r["invalidated"])

    def test_order_block_invalidation_is_fail_closed(self):
        d = frame([10,11,12,11,10.5,11.5,13,12,11.5,12.5,14,13,12.5,13.5,15,10.0])
        r = detect_order_block(d, "BUY")
        self.assertEqual(r["status"], "🔴 ORDER BLOCK INVALIDADO")
        self.assertTrue(r["invalidated"])
        self.assertEqual(r["score"], 10)

    def test_insufficient_data_never_claims_bos_choch_or_order_block(self):
        d = frame([10,10.1,10.2,10.1,10.0])
        structure = detect_bos_choch(d, "BUY")
        ob = detect_order_block(d, "BUY")
        self.assertEqual(structure["score"], 0)
        self.assertEqual(ob["score"], 0)
        self.assertIn("INDISPONÍVEL", structure["status"])
        self.assertIn("SEM ORDER BLOCK", ob["status"])

    def test_sideways_range_does_not_create_structure_event(self):
        d = frame([10.0,10.1,10.0,10.1,10.0,10.1,10.0,10.1,10.0,10.1,10.0,10.1,10.0,10.1])
        r = detect_bos_choch(d, "BUY")
        self.assertEqual(r["event"], "NONE")
        self.assertLessEqual(r["score"], 35)

    def test_equalish_pivots_within_tolerance_are_not_directional_bias(self):
        highs = [(2,1.10000),(6,1.10003)]
        lows = [(4,1.09900),(8,1.09902)]
        self.assertEqual(_bias_before(highs,lows,8,tolerance=0.00005),"MIXED")

    def test_same_swing_cannot_generate_two_structure_breaks(self):
        d = custom_frame([
            (10.0,10.2,9.8,10.0),
            (10.0,11.2,9.9,11.0),
            (11.0,12.0,10.5,11.8),
            (11.8,11.5,10.0,10.5),
            (10.5,11.0,9.5,10.0),
            (10.0,11.5,10.2,11.0),
            (11.0,13.0,10.8,12.5),
            (12.5,12.0,10.0,11.5),
            (11.5,13.2,11.0,12.7),
            (12.7,12.9,11.8,12.0),
            (12.0,12.4,11.4,11.9),
        ])
        events = _structure_events(d)
        pivot_ids = [(x["side"],x["pivot_index"]) for x in events]
        self.assertEqual(len(pivot_ids),len(set(pivot_ids)))

    def test_marginal_close_inside_noise_tolerance_is_not_break(self):
        d = custom_frame([
            (10.0,10.3,9.7,10.0),
            (10.0,11.1,9.8,10.8),
            (10.8,12.0,10.4,11.7),
            (11.7,11.4,10.2,10.6),
            (10.6,11.0,9.4,10.0),
            (10.0,11.4,9.9,11.0),
            (11.0,12.2,10.8,12.01),
            (12.01,11.9,10.7,11.5),
            (11.5,11.8,10.5,11.2),
            (11.2,11.7,10.4,11.0),
            (11.0,11.6,10.3,10.9),
            (10.9,11.5,10.2,10.8),
        ])
        events = _structure_events(d)
        self.assertFalse(any(x["index"] == 6 and x["side"] == "BUY" for x in events))

    def test_macro_wait_never_claims_structure(self):
        d = frame([10 + i * 0.1 for i in range(30)])
        r = build_structure_snapshot(d, "WAIT")
        self.assertEqual(r["structure"]["score"], 0)
        self.assertEqual(r["order_block"]["score"], 0)
        self.assertIn("não representam probabilidade", r["algorithm_note"])


if __name__ == "__main__":
    unittest.main()
