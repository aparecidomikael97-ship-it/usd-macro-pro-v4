import unittest

from atlasquant_intermarket_context import build_intermarket_snapshot


class IntermarketContextTests(unittest.TestCase):
    def test_missing_state_is_unavailable(self):
        out=build_intermarket_snapshot("EUR/USD",None)
        self.assertFalse(out["available"])
        self.assertEqual(out["direction"],"INDISPONÍVEL")
        self.assertFalse(out["changes_gate"])

    def test_one_group_is_not_enough(self):
        state={"EUR/USD":{"drivers":[
            {"group":"rates","name":"US-DE 2Y spread","direction":"SELL","strength":80,"quality":90,"fresh":True}
        ]}}
        out=build_intermarket_snapshot("EUR/USD",state)
        self.assertFalse(out["available"])
        self.assertEqual(out["groups"],1)
        self.assertIn("dois grupos",out["detail"])

    def test_two_independent_groups_can_form_context(self):
        state={"EUR/USD":{"drivers":[
            {"group":"rates","name":"US-DE 2Y spread","direction":"SELL","strength":80,"quality":90,"fresh":True},
            {"group":"risk","name":"risk regime","direction":"SELL","strength":60,"quality":80,"fresh":True},
        ]}}
        out=build_intermarket_snapshot("EUR/USD",state)
        self.assertTrue(out["available"])
        self.assertEqual(out["direction"],"VENDA")
        self.assertGreater(out["agreement_pct"],90)
        self.assertFalse(out["decision_effect"])
        self.assertFalse(out["changes_score_mestre"])

    def test_stale_driver_is_excluded(self):
        state={"EUR/USD":{"drivers":[
            {"group":"rates","name":"rates","direction":"BUY","strength":80,"quality":90,"fresh":False},
            {"group":"risk","name":"risk","direction":"BUY","strength":80,"quality":90,"fresh":True},
        ]}}
        out=build_intermarket_snapshot("EUR/USD",state)
        self.assertFalse(out["available"])
        self.assertEqual(out["stale_drivers"],1)

    def test_correlated_items_in_same_group_count_once(self):
        state={"EUR/USD":{"drivers":[
            {"group":"usd_proxies","name":"proxy A","direction":"SELL","strength":70,"quality":80,"fresh":True},
            {"group":"usd_proxies","name":"proxy B","direction":"SELL","strength":70,"quality":80,"fresh":True},
            {"group":"rates","name":"yield spread","direction":"SELL","strength":60,"quality":80,"fresh":True},
        ]}}
        out=build_intermarket_snapshot("EUR/USD",state)
        self.assertTrue(out["available"])
        self.assertEqual(out["groups"],2)


if __name__=="__main__":
    unittest.main()
