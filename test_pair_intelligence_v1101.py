import unittest
from pathlib import Path

class PairIntelligenceV1101Tests(unittest.TestCase):
    def test_source_separates_process_and_data_health(self):
        src=Path("pair_intelligence_v110.py").read_text(encoding="utf-8")
        self.assertIn("Saúde do processo x prontidão dos dados",src)
        self.assertIn("Dados técnicos suficientes",src)
        self.assertIn("Data Readiness — dados suficientes para decisão?",src)
    def test_institutional_nd_when_data_missing(self):
        src=Path("pair_intelligence_v110.py").read_text(encoding="utf-8")
        self.assertIn('else "N/D"',src)
    def test_premium_discount_is_operationalized(self):
        src=Path("pair_intelligence_v110.py").read_text(encoding="utf-8")
        self.assertIn("premium_discount_operational",src)

if __name__=='__main__': unittest.main()
