import unittest

from atlasquant_tradingview_parity import validate_tradingview_parity


class TradingViewParityTests(unittest.TestCase):
    def test_static_parity_contract_is_green(self):
        report=validate_tradingview_parity()
        failed=[x for x in report["checks"] if not x["ok"]]
        self.assertEqual(failed,[],msg=str(failed))
        self.assertEqual(report["status"],"OK")
        self.assertGreaterEqual(report["passed"],30)

    def test_limitations_are_explicit(self):
        report=validate_tradingview_parity()
        text=" ".join(report["limitations"]).lower()
        self.assertIn("não compila pine",text)
        self.assertIn("tradingview",text)
        self.assertIn("timezone",text)


if __name__=="__main__":
    unittest.main()
