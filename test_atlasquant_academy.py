import unittest

from atlasquant_advanced_learning import (
    ADVANCED_MODULES,
    advanced_module,
    guided_learning_ready,
    guided_video_script,
)
from atlasquant_academy import (
    ACADEMY_TOPICS,
    ACADEMY_REQUIRED_TOPIC_IDS,
    academy_catalog,
    academy_coverage_report,
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

    def test_quarterly_curriculum_is_complete_and_advanced(self):
        ids={"quarterly-theory","quarterly-multitimeframe","quarterly-amd","quarterly-execution"}
        rows=[academy_topic(topic_id) for topic_id in ids]
        self.assertTrue(all(rows))
        self.assertTrue(all(x["level"]=="Avançado" for x in rows))
        self.assertTrue(all(x["category"]=="ICT / SMC" for x in rows))
        self.assertTrue(any(x["id"]=="quarterly-theory" for x in academy_search("quarterly")))
        self.assertIn("AMD",academy_topic("quarterly-amd")["title"])

    def test_core_curriculum_contract_covers_macro_technical_and_risk(self):
        required={
            "macro-foundations","microeconomics-markets","cpi","pce","nfp","pmi-ism","gdp",
            "central-banks","g8-central-banks","fomc-dotplot","calendar-surprise","dxy-crossasset",
            "geopolitics-fx","relative-strength","liquidity-structure","fvg","ote","crt-amd",
            "quarterly-theory","quarterly-multitimeframe","quarterly-amd",
            "quarterly-execution","risk","atlasquant-reading",
        }
        ids={str(x["id"]) for x in ACADEMY_TOPICS}
        self.assertTrue(required.issubset(ids))
        self.assertIn("Iniciante",{x["level"] for x in ACADEMY_TOPICS})
        self.assertIn("Intermediário",{x["level"] for x in ACADEMY_TOPICS})
        self.assertIn("Avançado",{x["level"] for x in ACADEMY_TOPICS})

    def test_master_backlog_curriculum_has_explicit_micro_geopolitics_and_g8_banks(self):
        micro=academy_topic("microeconomics-markets")
        geo=academy_topic("geopolitics-fx")
        banks=academy_topic("g8-central-banks")
        self.assertIsNotNone(micro)
        self.assertIsNotNone(geo)
        self.assertIsNotNone(banks)
        joined=" ".join([
            micro["summary"],micro["watch"],geo["summary"],geo["watch"],
            banks["summary"],banks["watch"],banks["forex"],
        ])
        for term in ("oferta","demanda","geopolítica","ECB","BoE","BoJ","RBA","RBNZ","SNB"):
            with self.subTest(term=term):
                self.assertIn(term.casefold(),joined.casefold())

    def test_academy_coverage_report_fails_no_requirement_and_keeps_media_external(self):
        report=academy_coverage_report()
        self.assertEqual(report["schema"],"ATLASQUANT_ACADEMY_COVERAGE_V1")
        self.assertTrue(report["text_ready"])
        self.assertTrue(report["video_scripts_ready"])
        self.assertEqual(report["missing_required"],[])
        self.assertEqual(report["duplicate_ids"],0)
        self.assertEqual(report["required_topics"],len(ACADEMY_REQUIRED_TOPIC_IDS))
        self.assertTrue(report["rendered_media_required_externally"])
        self.assertFalse(report["trading_side_effects"])

    def test_advanced_guided_path_has_all_approved_modules(self):
        ids=[x["id"] for x in ADVANCED_MODULES]
        required={
            "start","macro","micro","geopolitics","fundamental","news",
            "technical","ict-smc","sessions","evidence","radar",
        }
        self.assertTrue(required.issubset(ids))
        self.assertEqual(len(ids),len(set(ids)))
        self.assertTrue(guided_learning_ready())

    def test_each_advanced_module_is_didactic_and_connected_to_radar(self):
        required={"id","tab","title","intro","why","market","atlas","example","pitfalls","radar"}
        for item in ADVANCED_MODULES:
            with self.subTest(module=item["id"]):
                self.assertTrue(required.issubset(item))
                self.assertTrue(all(str(item[k]).strip() for k in required if k!="pitfalls"))
                self.assertGreaterEqual(len(item["pitfalls"]),2)
                self.assertTrue(str(item["radar"]).strip())

    def test_short_video_scripts_are_ready_but_not_falsely_published(self):
        for item in ADVANCED_MODULES:
            media=guided_video_script(item["id"])
            self.assertTrue(media["script_ready"])
            self.assertFalse(media["rendered_video"])
            self.assertFalse(media["published_video"])
            self.assertGreaterEqual(media["estimated_seconds"],45)
            self.assertLessEqual(media["estimated_seconds"],75)
        self.assertIsNone(guided_video_script("missing"))
        self.assertIsNone(advanced_module("missing"))

    def test_indicator_module_explains_previous_consensus_actual_without_mechanical_rule(self):
        item=advanced_module("news")
        joined=" ".join(str(item[k]) for k in ("intro","why","market","atlas","example","pitfalls")).casefold()
        self.assertIn("anterior",joined)
        self.assertIn("consenso",joined)
        self.assertIn("atual",joined)
        self.assertIn("não têm o mesmo significado",joined)

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
