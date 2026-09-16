import unittest

from atlasquant_ui_v1 import NAVIGATION_LABELS, hero_html, navigation_labels, score_semantics


class AtlasQuantUiTests(unittest.TestCase):
    def test_navigation_keeps_existing_tab_count(self):
        self.assertEqual(len(NAVIGATION_LABELS), 15)
        self.assertEqual(navigation_labels()[0], "🎯 Central")
        self.assertEqual(navigation_labels()[-1], "🤖 Autopilot")

    def test_score_semantics_is_not_probability(self):
        self.assertEqual(score_semantics(80)["label"], "FORTE")
        self.assertEqual(score_semantics(50)["label"], "NEUTRO")
        self.assertEqual(score_semantics(None)["label"], "SEM DADO")

    def test_score_is_clamped_for_presentation(self):
        self.assertEqual(score_semantics(999)["label"], "FORTE")
        self.assertEqual(score_semantics(-10)["label"], "MUITO FRACO")

    def test_header_escapes_external_text(self):
        html = hero_html('<script>alert(1)</script>', 'dev')
        self.assertNotIn('<script>', html)
        self.assertIn('&lt;script&gt;', html)
        self.assertIn('ATLASQUANT', html)


if __name__ == "__main__":
    unittest.main()
