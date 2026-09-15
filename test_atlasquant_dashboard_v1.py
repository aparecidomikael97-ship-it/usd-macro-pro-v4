import unittest
import pandas as pd

from atlasquant_dashboard_v1 import (
    build_g8_radar, radar_summary, strengths_from_ranking,
    focus_rows, focus_card_html,
)


class AtlasQuantDashboardTests(unittest.TestCase):
    def setUp(self):
        self.ranking = pd.DataFrame({
            "Código": ["USD","EUR","GBP","JPY","CHF","CAD","AUD","NZD","BRL"],
            "Pontuação_Final": [80,60,75,35,50,45,55,40,52],
        })

    def test_extracts_only_g8(self):
        strengths = strengths_from_ranking(self.ranking)
        self.assertEqual(len(strengths), 8)
        self.assertNotIn("BRL", strengths)

    def test_builds_28_unique_pairs(self):
        radar = build_g8_radar(self.ranking)
        self.assertEqual(len(radar), 28)
        self.assertEqual(radar["Par"].nunique(), 28)

    def test_crosses_are_included(self):
        radar = build_g8_radar(self.ranking)
        self.assertIn("EUR/NZD", set(radar["Par"]))
        self.assertIn("GBP/CAD", set(radar["Par"]))

    def test_top_is_highest_relative_intensity(self):
        radar = build_g8_radar(self.ranking)
        self.assertGreaterEqual(radar.iloc[0]["Intensidade relativa"], radar.iloc[-1]["Intensidade relativa"])
        s = radar_summary(radar)
        self.assertEqual(s["total"], 28)

    def test_focus_cards_never_claim_entry_authorization(self):
        radar = build_g8_radar(self.ranking)
        rows = focus_rows(radar, 3)
        self.assertEqual(len(rows), 3)
        self.assertTrue(all(r["operational_state"] == "AGUARDAR CONFIRMAÇÃO" for r in rows))

    def test_focus_card_escapes_pair_and_state(self):
        html = focus_card_html({
            "pair": "<script>x</script>",
            "side": "COMPRA",
            "base_strength": 80,
            "quote_strength": 40,
            "difference": 40,
            "intensity": 90,
            "operational_state": "<b>GO</b>",
        })
        self.assertNotIn("<script>", html)
        self.assertNotIn("<b>GO</b>", html)
        self.assertIn("&lt;script&gt;", html)


if __name__ == "__main__":
    unittest.main()
