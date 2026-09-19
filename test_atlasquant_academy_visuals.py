import unittest

from atlasquant_academy_visuals import concept_visual_html, visual_topics


class AtlasQuantAcademyVisualsTests(unittest.TestCase):
    def test_key_visual_topics_are_available(self):
        topics=set(visual_topics())
        self.assertTrue({"fvg","ote","liquidity-sweeps","order-block","bos-choch-mss","volume-profile"}.issubset(topics))

    def test_visuals_are_local_html_css_svg_only(self):
        for topic in visual_topics():
            with self.subTest(topic=topic):
                html=concept_visual_html(topic).casefold()
                self.assertTrue(html)
                self.assertNotIn("<script",html)
                self.assertNotIn("http://",html)
                self.assertNotIn("https://",html)
                self.assertNotIn("iframe",html)

    def test_fvg_visual_labels_precise_three_candle_gap(self):
        html=concept_visual_html("fvg").casefold()
        self.assertIn("3 velas",html)
        self.assertIn("high vela 1",html)
        self.assertIn("low vela 3",html)
        self.assertIn("displacement",html)

    def test_ote_visual_has_requested_reference_levels(self):
        html=concept_visual_html("ote")
        self.assertIn("50%",html)
        self.assertIn("62",html)
        self.assertIn("70,5%",html)
        self.assertIn("79%",html)

    def test_volume_profile_visual_discloses_source_limit(self):
        html=concept_visual_html("volume-profile").casefold()
        self.assertIn("forex spot",html)
        self.assertIn("não é o volume centralizado",html)

    def test_unknown_topic_has_no_fake_visual(self):
        self.assertEqual(concept_visual_html("unknown"),"")


if __name__=="__main__":
    unittest.main()
