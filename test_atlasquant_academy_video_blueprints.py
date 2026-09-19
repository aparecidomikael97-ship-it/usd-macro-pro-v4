import unittest

from atlasquant_academy import ACADEMY_TOPICS
from atlasquant_academy_video_blueprints import (
    MAX_VIDEO_SECONDS,
    blueprint_catalog,
    blueprints_ready,
    video_blueprint,
)


class AtlasQuantAcademyVideoBlueprintTests(unittest.TestCase):
    def test_every_academy_topic_has_a_blueprint_under_20_minutes(self):
        rows=blueprint_catalog()
        self.assertEqual(len(rows),len(ACADEMY_TOPICS))
        self.assertTrue(blueprints_ready())
        for row in rows:
            with self.subTest(topic=row["topic_id"]):
                self.assertTrue(row["within_20_min"])
                self.assertLessEqual(row["total_seconds"],MAX_VIDEO_SECONDS)
                self.assertGreater(row["total_seconds"],0)
                self.assertTrue(row["animation_first"])
                self.assertFalse(row["rendered_video"])
                self.assertFalse(row["published_video"])

    def test_fvg_blueprint_teaches_three_candle_imbalance_visually(self):
        row=video_blueprint("fvg")
        text=" ".join(x["visual"]+" "+x["teaching"] for x in row["scenes"]).casefold()
        self.assertIn("três",text)
        self.assertIn("vela 1",text)
        self.assertIn("vela 3",text)
        self.assertIn("sem sobreposição",text)
        self.assertIn("displacement",text)

    def test_ote_blueprint_contains_equilibrium_and_ote_zone(self):
        row=video_blueprint("ote")
        text=" ".join(x["visual"]+" "+x["teaching"] for x in row["scenes"])
        self.assertIn("50%",text)
        self.assertIn("62%–79%",text)
        self.assertIn("70,5%",text)
        self.assertIn("não número mágico",text)

    def test_order_block_blueprint_rejects_last_opposite_candle_shortcut(self):
        row=video_blueprint("order-block")
        text=(" ".join(x["teaching"] for x in row["scenes"])+" "+row["hook"]).casefold()
        self.assertIn("última vela",text)
        self.assertIn("estrutura",text)
        self.assertIn("invalidação",text)

    def test_volume_profile_blueprint_discloses_spot_fx_volume_limitation(self):
        row=video_blueprint("volume-profile")
        text=" ".join(x["teaching"] for x in row["scenes"]).casefold()
        self.assertIn("não existe um volume centralizado único",text)
        self.assertIn("fonte",text)

    def test_app_guide_explains_radar_voice_and_beginner_mode(self):
        row=video_blueprint("atlasquant-reading")
        text=" ".join(x["title"]+" "+x["teaching"] for x in row["scenes"]).casefold()
        self.assertIn("radar",text)
        self.assertIn("voz",text)
        self.assertIn("iniciante",text)
        self.assertIn("não executa ordens",text)

    def test_unknown_topic_fails_closed(self):
        self.assertIsNone(video_blueprint("topic-that-does-not-exist"))


if __name__=="__main__":
    unittest.main()
