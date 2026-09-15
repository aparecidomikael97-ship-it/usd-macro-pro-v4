import unittest
from pathlib import Path


class PairIntelligenceSourceTests(unittest.TestCase):
    def test_central_has_all_required_layers(self):
        src=Path("pair_intelligence_v110.py").read_text(encoding="utf-8")
        for term in ("SMT","Displacement","MSS","Premium/Discount","Judas/Sessão","Breaker/Mitigation","CRT","OTE","AMD / PO3","FVG"):
            self.assertIn(term,src)

    def test_g8_excludes_brl_from_header_extremes(self):
        src=Path("pair_intelligence_v110.py").read_text(encoding="utf-8")
        self.assertIn('MAJORS=("USD","EUR","GBP","JPY","CHF","CAD","AUD","NZD")',src)

    def test_no_profit_probability_claim(self):
        src=Path("pair_intelligence_v110.py").read_text(encoding="utf-8")
        self.assertIn("não é probabilidade de lucro",src.lower())


if __name__ == "__main__":
    unittest.main()
