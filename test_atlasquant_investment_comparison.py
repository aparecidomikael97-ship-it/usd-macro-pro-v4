import unittest

from atlasquant_investment_ecosystem import investment_product_comparison
from atlasquant_investment_panel import investment_sections


class InvestmentComparisonTests(unittest.TestCase):
    def test_empty_source_never_creates_products_or_recommendation(self):
        snapshot = investment_product_comparison([])
        self.assertEqual(snapshot["state"], "NÃO CONFIRMADO")
        self.assertEqual(snapshot["rows"], [])
        self.assertFalse(snapshot["personalized_recommendation"])
        self.assertFalse(snapshot["automatic_orders"])

    def test_missing_provenance_stays_unconfirmed_and_fields_are_not_estimated(self):
        snapshot = investment_product_comparison([
            {"produto": "CDB", "taxa_bruta": "110% CDI", "prazo": "12 meses"},
        ])
        row = snapshot["rows"][0]
        self.assertEqual(row["Estado"], "NÃO CONFIRMADO")
        self.assertEqual(row["Fonte"], "FONTE AUSENTE")
        self.assertIsNone(row["Rentabilidade líquida"])
        self.assertIsNone(row["Liquidez"])
        self.assertIsNone(row["Risco"])

    def test_proven_product_keeps_source_timestamp_and_supplied_values(self):
        snapshot = investment_product_comparison([
            {
                "product": "Tesouro observado",
                "asset_class": "Renda fixa",
                "gross_return": "IPCA + taxa observada",
                "net_return": "valor líquido fornecido",
                "term": "2035",
                "liquidity": "conforme fonte",
                "risk": "conforme fonte",
                "costs": "conforme fonte",
                "source": "Fonte oficial",
                "timestamp": "2026-09-27T12:00:00Z",
            },
        ])
        self.assertEqual(snapshot["state"], "CONFIRMADO")
        self.assertEqual(snapshot["confirmed"], 1)
        self.assertEqual(snapshot["rows"][0]["Rentabilidade líquida"], "valor líquido fornecido")

    def test_comparator_is_advanced_without_changing_beginner_journey(self):
        self.assertNotIn("Comparador", investment_sections("Iniciante"))
        self.assertIn("Comparador", investment_sections("Avançado"))


if __name__ == "__main__":
    unittest.main()
