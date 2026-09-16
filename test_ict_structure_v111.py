import unittest
import pandas as pd

from ict_structure_v111 import detect_bos_choch, detect_order_block, build_structure_snapshot


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

    def test_macro_wait_never_claims_structure(self):
        d = frame([10 + i * 0.1 for i in range(30)])
        r = build_structure_snapshot(d, "WAIT")
        self.assertEqual(r["structure"]["score"], 0)
        self.assertEqual(r["order_block"]["score"], 0)
        self.assertIn("não representam probabilidade", r["algorithm_note"])


if __name__ == "__main__":
    unittest.main()
