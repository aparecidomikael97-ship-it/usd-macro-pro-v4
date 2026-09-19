import unittest

from atlasquant_academy import (
    ACADEMY_TOPICS,
    academy_catalog,
    academy_minimum_text_ready,
    academy_progress,
    academy_search,
    academy_topic,
)


class AtlasQuantAcademyTests(unittest.TestCase):
    def test_minimum_curriculum_is_present_and_ids_are_unique(self):
        ids=[x["id"] for x in ACADEMY_TOPICS]
        self.assertGreaterEqual(len(ids),20)
        self.assertEqual(len(ids),len(set(ids)))
        self.assertTrue(academy_minimum_text_ready())

    def test_required_topic_fields_are_nonempty(self):
        required={"id","category","title","level","summary","watch","forex","pitfall"}
        for topic in ACADEMY_TOPICS:
            with self.subTest(topic=topic.get("id")):
                self.assertTrue(required.issubset(topic))
                for key in required:
                    self.assertTrue(str(topic[key]).strip())

    def test_search_is_case_insensitive_and_empty_query_returns_catalog(self):
        self.assertTrue(any(x["id"]=="cpi" for x in academy_search("CPI")))
        self.assertTrue(any(x["id"]=="fomc-dotplot" for x in academy_search("fed")))
        self.assertEqual(len(academy_search("")),len(ACADEMY_TOPICS))

    def test_catalog_filters_category_and_level(self):
        rows=academy_catalog(category="ICT / SMC",level="Intermediário")
        self.assertTrue(rows)
        self.assertTrue(all(x["category"]=="ICT / SMC" for x in rows))
        self.assertTrue(all(x["level"]=="Intermediário" for x in rows))

    def test_topic_lookup_fails_closed_for_unknown(self):
        self.assertEqual(academy_topic("cpi")["title"],"CPI / IPC e Core CPI")
        self.assertIsNone(academy_topic("missing-topic"))

    def test_progress_ignores_unknown_and_duplicates(self):
        out=academy_progress(["cpi","cpi","risk","unknown",""])
        self.assertEqual(out["completed"],2)
        self.assertEqual(set(out["completed_ids"]),{"cpi","risk"})
        self.assertGreater(out["pct"],0)
        self.assertLess(out["pct"],100)

    def test_content_never_calls_internal_score_probability(self):
        joined=" ".join(
            str(topic[key])
            for topic in ACADEMY_TOPICS
            for key in ("summary","watch","forex","pitfall")
        ).lower()
        self.assertNotIn("90% de chance",joined)
        self.assertNotIn("garantia de lucro",joined)


if __name__=="__main__":
    unittest.main()
