"""Read-only SQLite P0 forensic Git-object lineage — not P0 homologation.

Authenticates *local Git object equality and chronology in checked-out history*,
not original incident identity, runtime/cloud producer safety or GitHub job log
cryptographic signature. All decisions remain HARD_NO_GO and P0 0/6.
"""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[1]
MATRIX=ROOT/"docs/aion/AION_P0_SQLITE_ORIGINAL_LAB_LINEAGE_20261020.json"
SIX=ROOT/"docs/aion/AION_P0_SIX_BLOCKERS_CANONICAL_EVIDENCE_REGISTER_20261019.json"

def git(*args,check=True):
    r=subprocess.run(["git",*args],cwd=ROOT,capture_output=True,text=True,check=check,timeout=30)
    return r.stdout.strip(),r.returncode

class SQLiteOriginalVsLabLineageLAB(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d=json.loads(MATRIX.read_text(encoding="utf-8"))
        cls.six=json.loads(SIX.read_text(encoding="utf-8"))

    def test_01_scope_and_p0_truth_remain_hard_no_go(self):
        self.assertEqual(self.d["status"],"HARD_NO_GO_ORIGINAL_TWO_SQLITE_P0_UNMAPPED")
        state=self.d["current_state"]
        self.assertEqual(state["p0_homologated"],0)
        self.assertIs(state["worker_enabled"],False)
        self.assertIs(state["automatic_resend_enabled"],False)
        self.assertIs(state["original_two_sqlite_p0_open"],True)
        self.assertIs(state["new_suite_green_does_not_map_original_incidents"],True)

    def test_02_test_creation_commits_19_oct_pinned_and_files_exist(self):
        self.assertEqual(len(self.d["source_test_families"]),3)
        for test in self.d["source_test_families"]:
            with self.subTest(path=test["source"]):
                self.assertTrue(test["created_on"].startswith("2026-10-19"))
                self.assertIs(test["dated_oct19_lab_not_a_proven_original_canonical_incident"],True)
                self.assertTrue((ROOT/test["source"]).is_file())
                self.assertEqual(git("cat-file","-t",test["initial_commit"])[0],"commit")
                at_create=git("rev-parse",test["initial_commit"]+":"+test["source"])[0]
                self.assertEqual(len(at_create),40)
                # It was a *later LAB test creation*, not the historical P0 incident ID.
                self.assertNotEqual(test["initial_commit"],
                                    self.d["red_observed"]["commit"])

    def test_03_test_named_original_does_not_identify_original_six_p0(self):
        families=self.d["source_test_families"]
        self.assertIn("original",families[0]["source"])
        self.assertIn("NOT proven",families[0]["original_in_filename_means"])
        p={x["id"]:x for x in self.six["p0"]}
        for name in ("SQLITE_COMPAT_READ_PATH","SQLITE_COMPAT_WRITE_PATH"):
            with self.subTest(p0=name):
                self.assertIsNone(p[name]["canonical_tracker_id"])
                self.assertIn("UNMAPPED",p[name]["status"])
        self.assertFalse(self.d["original_six_sqlite_read_case_identified"])
        self.assertFalse(self.d["original_six_sqlite_write_case_identified"])

    def test_04_original_red_is_exact_parent_of_owner_thread_fix(self):
        patch=self.d["patches"][0]
        self.assertEqual(patch["commit"],"2eed980be36143535ef94e3f52f53852030708b1")
        self.assertEqual(patch["parent"],self.d["red_observed"]["commit"])
        self.assertEqual(git("rev-parse",patch["commit"]+"^")[0],patch["parent"])

    def test_05_all_three_fixes_touch_only_same_product_store_py(self):
        self.assertEqual(len(self.d["patches"]),3)
        for p in self.d["patches"]:
            with self.subTest(commit=p["commit"]):
                self.assertEqual(git("rev-parse",p["commit"]+"^")[0],p["parent"])
                self.assertEqual(git("diff","--name-only",p["parent"],p["commit"])[0],
                                 "aion_chat/store.py")
                self.assertEqual(p["file"],"aion_chat/store.py")

    def test_06_owner_thread_original_test_blob_same_red_and_green(self):
        red=self.d["red_observed"]
        green=self.d["green_observed"]
        name=red["suite"]
        self.assertEqual(name,"test_aion_p0_sqlite_chat_store_owner_thread_lab.py")
        red_blob=git("rev-parse",red["commit"]+":"+name)[0]
        green_blob=git("rev-parse",green["commit"]+":"+name)[0]
        current_blob=git("hash-object",name)[0]
        self.assertEqual(red_blob,red["suite_blob"])
        self.assertEqual(green_blob,green["owner_thread_suite_blob"])
        self.assertEqual(red_blob,green_blob)
        self.assertEqual(current_blob,red_blob)

    def test_07_red_and_green_store_blobs_are_valid_and_changed(self):
        red=self.d["red_observed"]
        green=self.d["green_observed"]
        path="aion_chat/store.py"
        self.assertEqual(git("rev-parse",red["commit"]+":"+path)[0],
                         red["store_blob"])
        self.assertEqual(git("rev-parse",green["commit"]+":"+path)[0],
                         green["store_blob"])
        self.assertNotEqual(red["store_blob"],green["store_blob"])

    def test_08_red_jobs_15_cases_and_4f9e_per_os_persist_not_waived(self):
        d=self.d["red_observed"]
        self.assertEqual(d["run"],"39316307777")
        self.assertEqual(len(d["jobs"]),2)
        self.assertEqual({r["os"] for r in d["jobs"]},{"Ubuntu","Windows"})
        for r in d["jobs"]:
            with self.subTest(os=r["os"]):
                self.assertEqual((r["total"],r["failures"],r["errors"],r["passes"]),
                                 (15,4,9,2))
                self.assertEqual(r["total"],r["failures"]+r["errors"]+r["passes"])
                self.assertTrue(r["job_id"].isdigit())
        self.assertTrue(self.d["green_observed"]["suite_green_ubuntu"])
        self.assertTrue(self.d["green_observed"]["suite_green_windows"])

    def test_09_actual_thread_fix_preserves_native_sqlite_thread_check(self):
        p=self.d["patches"][0]
        blob,_=git("show",p["commit"]+":aion_chat/store.py")
        self.assertIn("self._connection_owner_thread = threading.current_thread()",blob)
        self.assertIn("if threading.current_thread() is not self._connection_owner_thread:",blob)
        self.assertIn('SQLITE_STORE_CONNECTION_THREAD_MISMATCH',blob)
        self.assertIn('sqlite3.connect(str(self.path), timeout=',blob)
        self.assertNotIn('check_same_thread=False',blob)

    def test_10_restore_and_wal_fixes_are_separate_containment_not_external_witness(self):
        restore=self.d["patches"][1]
        wal=self.d["patches"][2]
        restore_source=git("show",restore["commit"]+":aion_chat/store.py")[0]
        wal_source=git("show",wal["commit"]+":aion_chat/store.py")[0]
        self.assertIn("P0_EXECUTION_RESTORE_REQUIRES_INDEPENDENT_WITNESS",restore_source)
        self.assertIn("_EXECUTION_LEDGER_TABLES",restore_source)
        self.assertIn("_require_chat_only_restore_file",restore_source)
        self.assertIn("P0_RESTORE_TARGET_SIDECAR_UNVERIFIED",wal_source)
        self.assertIn("_require_restore_target_safe",wal_source)
        self.assertFalse(self.d["current_state"]["producer_issuer_enrolled"])

    def test_11_latest_quality_and_32_errors_still_are_historical_red(self):
        d=self.d["current_state"]
        self.assertEqual(d["complete_quality_last_run"],"39334210568")
        self.assertEqual((d["complete_quality_last_fail"],
                          d["complete_quality_last_error"]),(51,34))
        self.assertEqual(d["outbox_saga_error_open"],32)

    def test_12_next_required_evidence_excludes_lab_shortcut(self):
        d=self.d
        self.assertGreaterEqual(len(d["next_missing_evidence"]),4)
        self.assertTrue(any("before 19 October" in s for s in d["next_missing_evidence"]))
        self.assertFalse(d["original_six_sqlite_read_case_identified"])
        self.assertFalse(d["original_six_sqlite_write_case_identified"])
        self.assertFalse(d["current_state"]["real_physical_reboot_verified"])

if __name__=="__main__":
    unittest.main()
