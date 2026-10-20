"""LAB forensic invariants for 10-Oct READ / 14-Oct WRITE candidates.

Reads pinned local Git objects and the immutable earlier six-P0 crosswalk.
It does NOT decide original incident identity or runtime readiness.
No Git/network mutations, no SQLite production connection, no provider.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
RECEIPT = ROOT/"docs/aion/AION_P0_SQLITE_PRE19_CANDIDATE_RECEIPTS_20261020.json"
SIX = ROOT/"docs/aion/AION_P0_SIX_EXIT_EVIDENCE_GAP_MATRIX_20261020.json"


def git_file(commit: str, path: str) -> str:
    p = subprocess.run(
        ["git", "show", f"{commit}:{path}"], cwd=ROOT,
        capture_output=True, check=True, timeout=30,
    )
    return p.stdout.decode("utf-8")


def git_blob(commit: str, path: str) -> str:
    p = subprocess.run(
        ["git", "rev-parse", f"{commit}:{path}"], cwd=ROOT,
        capture_output=True, check=True, timeout=30,
    )
    return p.stdout.decode().strip()


def method_dump(module_source: str, name: str) -> str:
    tree = ast.parse(module_source)
    for cls in tree.body:
        if isinstance(cls, ast.ClassDef):
            for node in cls.body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
                    return ast.dump(node, include_attributes=False)
    raise AssertionError("HISTORICAL_TEST_METHOD_NOT_FOUND:" + name)


class SQLitePre19HistoricalAdjudicationLAB(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = json.loads(RECEIPT.read_text(encoding="utf-8"))
        cls.six = json.loads(SIX.read_text(encoding="utf-8"))
        cls.read = cls.r["candidate_read"]
        cls.write = cls.r["candidate_write"]

    def test_01_exact_two_unique_candidate_ids(self):
        self.assertEqual({self.read["p0_id"], self.write["p0_id"]},
                         {"SQLITE_COMPAT_READ_PATH", "SQLITE_COMPAT_WRITE_PATH"})

    def test_02_both_candidate_statuses_never_promote(self):
        for c in (self.read, self.write):
            self.assertIn("NOT_ORIGINAL_ATTRIBUTION", c["status"])
            self.assertIs(c["mainline_homologated"], False)

    def test_03_six_p0_unchanged_and_unmapped(self):
        by_id = {v["id"]: v for v in self.six["p0"]}
        for p0 in ("SQLITE_COMPAT_READ_PATH", "SQLITE_COMPAT_WRITE_PATH"):
            self.assertIsNone(by_id[p0]["canonical_85_case_id"])
            self.assertEqual(by_id[p0]["canonical_85_case_mapping_status"],
                             "UNMAPPED_EXACT_ORIGINAL_INCIDENT")
            self.assertIs(by_id[p0]["closed"], False)

    def test_04_no_global_authority_claims(self):
        self.assertEqual(self.r["global_gate"], "HARD_NO_GO")
        self.assertEqual(self.r["homologated_p0"], 0)
        self.assertIs(self.r["original_six_identity_proved"], False)
        for field in ("worker_allowed", "automatic_retry_allowed",
                      "merge_allowed", "deploy_allowed"):
            self.assertIs(self.r[field], False, field)
        self.assertEqual(self.r["authorized_new_spend_brl"], 0)

    def test_05_read_pre_fix_original_red_run_not_fabricated(self):
        for field in ("pre_fix_red_run_id", "pre_fix_red_sha", "pre_fix_test_case_id"):
            self.assertIsNone(self.read[field])
        self.assertEqual(self.read["green_coverage"], "GREEN_SCOPED_CANDIDATE_ONLY")

    def test_06_read_green_test_sha_pinned(self):
        self.assertEqual(
            git_blob(self.read["final_candidate_sha"], self.read["test_file"]),
            self.read["test_blob_sha"],
        )

    def test_07_read_exact_host_rerun_test_exists(self):
        txt = git_file(self.read["final_candidate_sha"], self.read["test_file"])
        self.assertIn("def "+self.read["exact_focus_test"]+"(", txt)
        self.assertIn("test_native_connection_remains_thread_affine", txt)

    def test_08_read_green_jobs_unique_and_scoped(self):
        self.assertEqual(self.read["candidate_pr"], 1195)
        self.assertEqual(self.read["green_run_id"], 38089857958)
        self.assertEqual(self.read["green_jobs"], [114323888424, 114323888544])
        self.assertEqual(self.read["green_tests_per_os"], 37)

    def test_09_later_read_lab_is_separate_from_original_pre19(self):
        v = self.read["separate_later_diagnostic"]
        self.assertEqual(v["run_id"], 39316307777)
        self.assertEqual((v["tests"],v["fail"],v["error"],v["passed"]), (15,4,9,2))
        self.assertEqual(v["association"], "LATER_LAB_NOT_PRE19_FIRST_REPORT")
        self.assertNotEqual(v["commit"], self.read["final_candidate_sha"])

    def test_10_write_red_and_green_exact_distinct_refs(self):
        self.assertEqual(self.write["candidate_pr"], 1281)
        self.assertEqual(self.write["red_run_id"], 38583150088)
        self.assertEqual(self.write["green_run_id"], 38584114098)
        self.assertNotEqual(self.write["red_commit"], self.write["green_commit"])

    def test_11_write_red_and_green_test_blobs_verified(self):
        path = self.write["source_test_file"]
        self.assertEqual(git_blob(self.write["red_commit"], path),
                         self.write["red_test_blob_sha"])
        self.assertEqual(git_blob(self.write["green_commit"], path),
                         self.write["green_test_blob_sha"])
        self.assertNotEqual(self.write["red_test_blob_sha"],
                            self.write["green_test_blob_sha"])

    def test_12_write_two_failure_tests_ast_identical_even_if_file_changed(self):
        path = self.write["source_test_file"]
        red = git_file(self.write["red_commit"], path)
        green = git_file(self.write["green_commit"], path)
        self.assertEqual(len(self.write["source_test_functions_identical_between_red_green"]), 2)
        for name in self.write["source_test_functions_identical_between_red_green"]:
            with self.subTest(name=name):
                self.assertEqual(method_dump(red, name), method_dump(green, name))
        self.assertIs(self.write["source_full_test_blob_unchanged"], False)

    def test_13_write_green_adds_two_non_authority_checks(self):
        red = git_file(self.write["red_commit"], self.write["source_test_file"])
        green = git_file(self.write["green_commit"], self.write["source_test_file"])
        self.assertNotIn("def test_05_outer_transaction_rollback_", red)
        self.assertNotIn("def test_06_nested_enqueue_sql_failure_", red)
        self.assertIn("def test_05_outer_transaction_rollback_", green)
        self.assertIn("def test_06_nested_enqueue_sql_failure_", green)

    def test_14_write_red_and_green_test_counts_truthful(self):
        self.assertEqual((self.write["red_total"], self.write["red_fail"]), (8, 2))
        self.assertEqual((self.write["green_total"], self.write["green_fail"]), (10, 0))
        self.assertNotEqual(self.write["red_job"], self.write["green_job"])

    def test_15_original_write_outbox_blobs_verifiable(self):
        path = "atlasquant_aion_execution_outbox.py"
        self.assertEqual(git_blob(self.write["red_commit"], path),
                         self.write["red_outbox_blob_sha"])
        self.assertEqual(git_blob(self.write["green_commit"], path),
                         self.write["green_outbox_blob_sha"])

    def test_16_original_write_saga_blobs_verifiable(self):
        path = "atlasquant_aion_execution_saga.py"
        self.assertEqual(git_blob(self.write["red_commit"], path),
                         self.write["red_saga_blob_sha"])
        self.assertEqual(git_blob(self.write["green_commit"], path),
                         self.write["green_saga_blob_sha"])

    def test_17_nested_savepoint_only_in_green_outbox(self):
        old = git_file(self.write["red_commit"], "atlasquant_aion_execution_outbox.py")
        new = git_file(self.write["green_commit"], "atlasquant_aion_execution_outbox.py")
        self.assertNotIn("SAVEPOINT aion_outbox_enqueue", old)
        self.assertIn("SAVEPOINT aion_outbox_enqueue", new)

    def test_18_write_saga_uses_explicit_transactions(self):
        s = git_file(self.write["green_commit"], "atlasquant_aion_execution_saga.py")
        self.assertIn("BEGIN IMMEDIATE", s)
        self.assertIn("def enqueue_next", s)

    def test_19_distinct_write_staging_and_provider_effect(self):
        self.assertEqual(self.write["test_kind"],
                         "A61_LOCAL_SAGA_OUTBOX_ATOMIC_STAGING_NOT_PROVIDER")
        self.assertIn("NO", self.write["fix_candidate"].upper())
        self.assertIn("not link original", self.write["notes"])

    def test_20_source_code_mappings_are_not_authority(self):
        self.assertTrue(len(self.r["required_original_confirmation"]) >= 6)
        self.assertIn("independent audit", " ".join(self.r["required_original_confirmation"]))
        self.assertFalse(self.six["full_quality_green"])
        self.assertFalse(self.six["full_security_green"])
        self.assertFalse(self.six["worker_allowed"])

    def test_21_canonical_p0_reference_exact(self):
        self.assertEqual(self.r["canonical_file"], SIX.relative_to(ROOT).as_posix())

    def test_22_candidate_dates_strict_historical(self):
        self.assertEqual(self.read["observed_at"], "2026-10-10")
        self.assertEqual(self.write["observed_at"], "2026-10-14")
        self.assertLess(self.read["observed_at"], self.write["observed_at"])

    def test_23_read_test_file_not_same_as_write(self):
        self.assertNotEqual(self.read["test_file"], self.write["source_test_file"])

    def test_24_evidence_is_local_read_only_never_enrollment(self):
        self.assertIn("LAB_PROVENANCE_NOT_ORIGINAL_P0_HOMOLOGATION",
                      self.r["trust_status"])
        self.assertNotIn("READY", self.r["global_gate"])


if __name__ == "__main__":
    unittest.main()
