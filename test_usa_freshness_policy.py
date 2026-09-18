import ast
from pathlib import Path
import unittest


class UsaFreshnessPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = Path("usd_macro_pro_v4_cloud.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        cls.policy = None
        for node in tree.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "FRESCURA_EUA_DIAS":
                        cls.policy = ast.literal_eval(node.value)
                        break
        if cls.policy is None:
            raise AssertionError("FRESCURA_EUA_DIAS nao encontrada")

    def test_monthly_and_quarterly_windows_avoid_false_stale_flags(self):
        self.assertGreaterEqual(self.policy["Juros do Fed"], 60)
        self.assertGreaterEqual(self.policy["PCE anual"], 90)
        self.assertGreaterEqual(self.policy["PCE Núcleo anual"], 90)
        self.assertGreaterEqual(self.policy["PIB"], 180)

    def test_daily_market_series_remain_strict(self):
        self.assertLessEqual(self.policy["Treasury 2 anos"], 5)
        self.assertLessEqual(self.policy["Treasury 10 anos"], 5)
        self.assertLessEqual(self.policy["Índice amplo do dólar"], 10)


if __name__ == "__main__":
    unittest.main()
