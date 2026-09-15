import unittest
import pandas as pd

from atlasquant_dashboard_v1 import build_g8_radar, radar_summary, strengths_from_ranking


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


if __name__ == "__main__":
    unittest.main()
