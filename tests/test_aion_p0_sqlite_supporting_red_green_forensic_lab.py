"""Forensic LAB: unchanged SQLite owner-thread test-source RED vs GREEN.

This verifies pinned source and metadata, not remote Actions logs authenticity
at test runtime. The run/job IDs were read from GitHub historical job logs.
The TWO original canonical SQLite P0 identities remain UNMAPPED and OPEN.
"""
from __future__ import annotations
import json
from pathlib import Path
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[1]
DOCS=ROOT/"docs"/"aion"
PIN=DOCS/"AION_P0_SQLITE_SUPPORTING_RED_GREEN_FORENSIC_20261020.json"
GAPS=DOCS/"AION_P0_SIX_EXIT_EVIDENCE_GAP_MATRIX_20261020.json"
SIX=DOCS/"AION_P0_SIX_BLOCKERS_CANONICAL_EVIDENCE_REGISTER_20261019.json"

class SQLiteSupportingRedGreenEvidenceLAB(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d=json.loads(PIN.read_text(encoding="utf-8"))
        cls.g=json.loads(GAPS.read_text(encoding="utf-8"))
        cls.s=json.loads(SIX.read_text(encoding="utf-8"))

    def test_01_same_exact_original_test_blob_still_tracked(self):
        src=self.d["test_source"]
        self.assertTrue((ROOT/src).exists())
        result=subprocess.run(
            ["git","hash-object",src],cwd=ROOT,capture_output=True,text=True,check=True)
        self.assertEqual(result.stdout.strip(),self.d["unchanged_test_blob_sha"])
        self.assertTrue(self.d["test_source_same_between_snapshots"])
        self.assertTrue(self.d["lab_green"]["same_test_source_sha_as_red"])

    def test_02_red_original_jobs_have_4_fails_9_errors_each(self):
        self.assertEqual(self.d["red"]["run_id"],"39316307777")
        self.assertEqual(self.d["red"]["commit"],"4f9c6acb4d3d1c081ad13c98434c52bdd78b861e")
        for os,row in self.d["red"]["jobs"].items():
            with self.subTest(os=os):
                self.assertEqual(row["total"],15)
                self.assertEqual((row["fail"],row["error"],row["pass"]),(4,9,2))
                self.assertTrue(row["job_id"].isdigit())

    def test_03_red_and_green_product_store_blob_are_distinct(self):
        self.assertEqual(self.d["red"]["store_source_blob"],
                         "6df8ad55673acaca6eeeb0bc3e3898d7a10b08ba")
        self.assertEqual(self.d["lab_green"]["store_source_blob"],
                         "951428ac5e76a0185c58121aa4fdb6823271b5b7")
        self.assertNotEqual(self.d["red"]["store_source_blob"],
                            self.d["lab_green"]["store_source_blob"])
        self.assertTrue(self.d["lab_green"]["source_code_changed"])

    def test_04_green_run_pins_actual_root_suite_number_12(self):
        green=self.d["lab_green"]
        self.assertEqual(green["run_id"],"39415147568")
        self.assertEqual(green["root_module_index"],12)
        self.assertEqual(green["root_module_name"],
                         "test_aion_p0_sqlite_chat_store_owner_thread_lab")
        self.assertEqual(green["ubuntu"],"PASS")
        self.assertEqual(green["windows"],"PASS")

    def test_05_read_and_write_are_both_present_only_as_lab_examples(self):
        red=self.d["red"]
        self.assertGreaterEqual(len(red["observed_read_examples"]),4)
        self.assertGreaterEqual(len(red["observed_write_examples"]),4)
        original=(ROOT/self.d["test_source"]).read_text(encoding="utf-8")
        for test in red["observed_read_examples"]+red["observed_write_examples"]:
            with self.subTest(method=test):
                self.assertIn("def "+test+"(",original)

    def test_06_supporting_evidence_not_misclassified_as_original_six_p0(self):
        self.assertFalse(self.d["historical_original_sqlite_read_p0_exact_case_mapped"])
        self.assertFalse(self.d["historical_original_sqlite_write_p0_exact_case_mapped"])
        self.assertEqual(self.d["status"],
            "SUPPORTING_LAB_ONLY__TWO_SQLITE_P0_STILL_OPEN_UNMAPPED")
        by_id={r["id"]:r for r in self.g["p0"]}
        for name in ("SQLITE_COMPAT_READ_PATH","SQLITE_COMPAT_WRITE_PATH"):
            self.assertEqual(by_id[name]["canonical_85_case_mapping_status"],
                             "UNMAPPED_EXACT_ORIGINAL_INCIDENT")
            self.assertIsNone(by_id[name]["canonical_85_case_id"])

    def test_07_no_canonical_green_quality_security_approval(self):
        for k in ("current_producer_enrolled","worker_allowed",
                  "real_external_effect_tested",
                  "quality_full_reexecuted_for_this_comparison",
                  "security_full_reexecuted_for_this_comparison"):
            self.assertIs(self.d[k],False,k)
        self.assertEqual(self.d["p0_homologated"],0)
        self.assertEqual(self.g["homologated_p0"],0)

    def test_08_historical_six_register_remains_unedited(self):
        p={r["id"]:r for r in self.s["p0"]}
        self.assertIsNone(p["SQLITE_COMPAT_READ_PATH"]["canonical_tracker_id"])
        self.assertIsNone(p["SQLITE_COMPAT_WRITE_PATH"]["canonical_tracker_id"])
        self.assertIn("UNMAPPED",p["SQLITE_COMPAT_READ_PATH"]["status"])
        self.assertIn("UNMAPPED",p["SQLITE_COMPAT_WRITE_PATH"]["status"])

if __name__=="__main__":
    unittest.main()
