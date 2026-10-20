"""AION P0 — evidence taxonomy assertions (LAB-only, never closes a gate).

Human-reviewed primary evidence is a 12-Oct GitHub issue comment, not the
later canonical 85-case Quality or the subsequent Oct19 SQLiteChatStore LAB.
This test checks a provenance transcription, NOT the authenticity of local
test source or successful migration of missing local files.
"""
from __future__ import annotations
import json
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
RECORD=ROOT/"docs/aion/AION_P0_ORIGINAL_20261012_JOURNAL_SIX_EVIDENCE_CORRECTION_20261020.json"
CANON=ROOT/"docs/aion/AION_P0_SIX_EXIT_EVIDENCE_GAP_MATRIX_20261020.json"

class OriginalSixJournalTaxonomyLAB(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.a=json.loads(RECORD.read_text(encoding="utf-8"))
        cls.previous=json.loads(CANON.read_text(encoding="utf-8"))
        cls.by_slot={r["slot"]:r for r in cls.a["original_cases"]}

    def test_01_six_original_slots_unique(self):
        self.assertEqual(len(self.a["original_cases"]),6)
        self.assertEqual(len(self.by_slot),6)

    def test_02_original_four_fail_two_error(self):
        self.assertEqual(sum(x["kind"]=="FAIL" for x in self.a["original_cases"]),4)
        self.assertEqual(sum(x["kind"]=="ERROR" for x in self.a["original_cases"]),2)

    def test_03_baseline_original_six_76(self):
        b=self.a["original_76_baseline"]
        self.assertEqual((b["pass"],b["fail"],b["error"],b["total"]),(70,4,2,76))
        self.assertEqual(b["pass"]+b["fail"]+b["error"]+b["skipped"],b["total"])
        self.assertIn("NOT_GITHUB_CANONICAL_QUALITY",b["scope"])

    def test_04_original_cases_have_no_false_closure(self):
        for row in self.a["original_cases"]:
            self.assertIs(row["fully_homologated"],False,row["slot"])
        self.assertEqual(self.a["original_p0_homologated"],0)

    def test_05_source_comment_ids_exact(self):
        ids={p["comment_id"] for p in self.a["historical_primary_sources"]}
        self.assertEqual(ids,{6130979775,6130912462,6132259470,6132086468})
        for row in self.a["historical_primary_sources"]:
            self.assertEqual(row["date"],"2026-10-12")
            self.assertIn(str(row["comment_id"]),row["url"])

    def test_06_do_not_claim_earliest_of_all_systems(self):
        self.assertIn("not claimed",self.a["first_p0_observation"])

    def test_07_original_compat_A_full_name(self):
        self.assertEqual(self.by_slot["P0_ORIGINAL_JOURNAL_COMPAT_A"]["legacy_test_full_name"],
            "test_lab_journal.JournalTests.test_readback_rejects_forged_content")

    def test_08_original_compat_B_full_name(self):
        self.assertEqual(self.by_slot["P0_ORIGINAL_JOURNAL_COMPAT_B"]["legacy_test_full_name"],
            "test_conservative_journal.ConservativeJournal.test_direct_SQL_still_bypasses_limit_characterization")

    def test_09_both_errors_are_same_public_readonly_journal_boundary(self):
        for x in self.a["original_cases"]:
            if x["kind"]=="ERROR":
                self.assertIn("read-only Journal.db()",x["symptom"])

    def test_10_original_other_four_unchanged(self):
        self.assertEqual({r["slot"] for r in self.a["original_cases"] if r["kind"]=="FAIL"},
          {"P0_ORIGINAL_OWNER","P0_ORIGINAL_RECEIPT","P0_ORIGINAL_INBOX_UNKNOWN",
           "P0_ORIGINAL_H0_RESTART"})

    def test_11_two_lab_counted_results_not_promoted(self):
        a=self.a["later_same_originals_lab"]
        b=self.a["migrated_lab_comparison"]
        self.assertEqual((a["pass"],a["fail"],a["error"],a["total"]),(73,1,2,76))
        self.assertEqual((b["pass"],b["fail"],b["error"],b["total"]),(75,1,0,76))
        self.assertIn("ONLY",b["scope"])

    def test_12_migration_keeps_legacy_tests_untouched(self):
        m=self.a["migration_observation"]
        self.assertIs(m["original_unmodified"],True)
        self.assertIs(m["fixture_only"],True)
        self.assertIs(m["migrates_test_behavior_only"],True)

    def test_13_original_local_source_missing_not_recreated(self):
        m=self.a["migration_observation"]
        self.assertIs(m["source_available_in_current_repo"],False)
        self.assertIn("not reexecuted originals",m["evidence_only_not_verified_in_this_branch"])

    def test_14_two_migrated_files_explicit(self):
        self.assertEqual(self.a["migration_observation"]["test_migration_paths"],[
         "tests_migrated/test_lab_journal_migrated_v2.py",
         "tests_migrated/test_conservative_journal_migrated_v2.py",
        ])

    def test_15_oct19_overlay_labels_preserved_not_silently_remapped(self):
        overlay=self.a["october19_overlay_mapping"]
        self.assertEqual(set(overlay["labels"]),{"SQLITE_COMPAT_READ_PATH","SQLITE_COMPAT_WRITE_PATH"})
        self.assertEqual(set(overlay["labels"]),
                         {r["id"] for r in self.previous["p0"] if r["id"].startswith("SQLITE_")})
        self.assertIs(overlay["must_not_rewrite_historical_register_without_review"],True)

    def test_16_original_case_names_not_proven_equivalent_to_later_labels(self):
        self.assertIn("HYPOTHESIS_INCOMPATIBLE",self.a["october19_overlay_mapping"]["status"])
        self.assertIn("one-to-one",self.a["october19_overlay_mapping"]["reason"])

    def test_17_previous_register_still_no_homologation(self):
        self.assertEqual(self.previous["homologated_p0"],0)
        self.assertFalse(self.previous["original_sqlite_read_failure_tracked_exactly"])
        self.assertFalse(self.previous["original_sqlite_write_failure_tracked_exactly"])

    def test_18_no_runtime_authority_no_waiver(self):
        self.assertEqual(self.a["status"],"HARD_NO_GO")
        self.assertFalse(self.a["worker_allowed"])
        self.assertFalse(self.a["automatic_retry_allowed"])
        self.assertEqual(self.a["authorized_new_spend_brl"],0)

    def test_19_later_defects_stay_distinct(self):
        by_pr={r["pr"]:r for r in self.a["later_independent_sqlite_candidacies"]}
        self.assertEqual(set(by_pr),{1195,1281})
        self.assertTrue(all("NOT_THE_TWO_OCT12_JOURNAL_ERRORS" in x["status"]
                            for x in by_pr.values()))

    def test_20_require_original_source_and_security_before_closure(self):
        needs=self.a["evidence_to_close"]
        self.assertGreaterEqual(len(needs),8)
        self.assertTrue(any("original lab source" in n for n in needs))
        self.assertTrue(any("full canonical Quality and Security" in n for n in needs))

if __name__=="__main__":
    unittest.main()
