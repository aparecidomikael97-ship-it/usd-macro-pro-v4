import unittest

from atlasquant_academy import ACADEMY_TOPICS
from atlasquant_academy_media import (
    academy_media_bundle_markdown,
    academy_media_catalog,
    academy_media_manifest,
    academy_media_manifest_json,
    academy_media_readiness,
    academy_video_script,
    academy_video_scripts_ready,
)

class AtlasQuantAcademyMediaTests(unittest.TestCase):
    def test_every_academy_topic_has_a_script(self):
        rows=academy_media_catalog()
        self.assertEqual(len(rows),len(ACADEMY_TOPICS))
        self.assertTrue(academy_video_scripts_ready())
        self.assertEqual([x["topic_id"] for x in rows],[x["id"] for x in ACADEMY_TOPICS])

    def test_script_is_structured_and_conservative(self):
        item=academy_video_script("cpi")
        self.assertIsNotNone(item)
        self.assertTrue(item["script_ready"])
        self.assertEqual(len(item["scenes"]),5)
        self.assertGreaterEqual(item["estimated_seconds"],45)
        self.assertLessEqual(item["estimated_seconds"],180)
        text=item["narration"].casefold()
        self.assertIn("não como promessa de resultado",text)
        self.assertFalse(item["rendered_video"])
        self.assertFalse(item["published_video"])
        self.assertFalse(item["trading_side_effects"])

    def test_quarterly_topics_have_video_scripts_and_storyboards(self):
        quarterly_ids=[
            "quarterly-theory",
            "quarterly-multitimeframe",
            "quarterly-amd",
            "quarterly-execution",
        ]
        for topic_id in quarterly_ids:
            item=academy_video_script(topic_id)
            self.assertIsNotNone(item)
            self.assertTrue(item["script_ready"])
            self.assertEqual(item["level"],"Avançado")
            self.assertEqual(len(item["scenes"]),5)
            self.assertIn("Quarterly",item["title"])
            self.assertFalse(item["rendered_video"])
            self.assertFalse(item["published_video"])
            self.assertFalse(item["trading_side_effects"])

    def test_production_manifest_covers_every_topic_without_fake_publish(self):
        manifest=academy_media_manifest()
        self.assertEqual(manifest["schema"],"ATLASQUANT_ACADEMY_PRODUCTION_MANIFEST_V1")
        self.assertEqual(manifest["total_items"],len(ACADEMY_TOPICS))
        self.assertTrue(manifest["all_scripts_ready"])
        self.assertEqual(manifest["rendered_items"],0)
        self.assertEqual(manifest["published_items"],0)
        self.assertTrue(manifest["external_render_required"])
        self.assertFalse(manifest["automatic_publish"])
        self.assertFalse(manifest["trading_side_effects"])
        self.assertEqual(
            [x["topic_id"] for x in manifest["items"]],
            [x["id"] for x in ACADEMY_TOPICS],
        )
        self.assertTrue(all(x["suggested_filename"].endswith(".mp4") for x in manifest["items"]))
        self.assertTrue(all(x["status"]=="SCRIPT_READY_MEDIA_PENDING" for x in manifest["items"]))

    def test_production_bundle_exports_json_and_markdown(self):
        raw=academy_media_manifest_json()
        md=academy_media_bundle_markdown()
        self.assertIn("ATLASQUANT_ACADEMY_PRODUCTION_MANIFEST_V1",raw)
        self.assertIn("# AtlasQuant Academy",md)
        self.assertIn("### Narração",md)
        self.assertIn("### Storyboard",md)
        self.assertIn("mídia ainda não renderizada/publicada",md)

    def test_unknown_topic_fails_closed(self):
        self.assertIsNone(academy_video_script("missing-topic"))

    def test_readiness_does_not_fake_rendered_or_published_media(self):
        status=academy_media_readiness()
        self.assertTrue(status["all_scripts_ready"])
        self.assertEqual(status["scripts_ready"],len(ACADEMY_TOPICS))
        self.assertEqual(status["rendered_videos"],0)
        self.assertEqual(status["published_videos"],0)
        self.assertFalse(status["academy_video_ready"])
        self.assertFalse(status["automatic_publish"])
        self.assertFalse(status["trading_side_effects"])

if __name__=="__main__":
    unittest.main()
