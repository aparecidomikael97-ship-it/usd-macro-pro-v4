import unittest

from atlasquant_regime_detector import regime_snapshot, detect_regime_change


class AtlasQuantRegimeDetectorTests(unittest.TestCase):
    def base(self):
        return {
            "pair":"EUR/USD","side":"BUY","direction":"🟢 COMPRA EUR/USD",
            "state":"🟡 AGUARDAR","macro_diff":12,"priority":80,"score":78,
            "quality":85,"executable":False,"gate":"WAIT","m15":"AGUARDAR",
            "event":"NORMAL","hard_blocks":[],
            "data_ready":{"sufficient":True,"score":90},
        }

    def test_first_snapshot_is_baseline(self):
        r=detect_regime_change(self.base(),None)
        self.assertEqual(r["status"],"BASELINE")
        self.assertIsNone(r["supported"])

    def test_identical_context_is_stable(self):
        p=self.base()
        r=detect_regime_change(p,regime_snapshot(p))
        self.assertEqual(r["status"],"STABLE")
        self.assertTrue(r["supported"])

    def test_buy_to_sell_is_shift(self):
        old=regime_snapshot(self.base())
        cur=self.base(); cur["side"]="SELL"; cur["direction"]="🔴 VENDA EUR/USD"
        r=detect_regime_change(cur,old)
        self.assertEqual(r["status"],"SHIFT")
        self.assertFalse(r["supported"])

    def test_macro_sign_flip_is_shift(self):
        old=regime_snapshot(self.base())
        cur=self.base(); cur["macro_diff"]=-12
        r=detect_regime_change(cur,old)
        self.assertEqual(r["status"],"SHIFT")

    def test_large_priority_change_is_transition(self):
        old=regime_snapshot(self.base())
        cur=self.base(); cur["priority"]=55
        r=detect_regime_change(cur,old)
        self.assertEqual(r["status"],"TRANSITION")
        self.assertFalse(r["supported"])

    def test_new_hard_block_is_shift(self):
        old=regime_snapshot(self.base())
        cur=self.base(); cur["hard_blocks"]=["dados stale"]
        self.assertEqual(detect_regime_change(cur,old)["status"],"SHIFT")

    def test_small_gate_change_is_watch(self):
        old=regime_snapshot(self.base())
        cur=self.base(); cur["gate"]="ATTENTION"
        r=detect_regime_change(cur,old)
        self.assertEqual(r["status"],"WATCH")
        self.assertTrue(r["supported"])

    def test_data_insufficient_forces_transition(self):
        old=regime_snapshot(self.base())
        cur=self.base(); cur["data_ready"]["sufficient"]=False
        r=detect_regime_change(cur,old)
        self.assertIn(r["status"],("TRANSITION","SHIFT"))
        self.assertFalse(r["supported"])

    def test_snapshot_normalizes_numbers(self):
        p=self.base(); p["priority"]=float("nan")
        self.assertIsNone(regime_snapshot(p)["priority"])


if __name__=="__main__":
    unittest.main()
