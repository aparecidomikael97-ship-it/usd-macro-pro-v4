"""Read-only six-P0 evidence crosswalk. PASS never equals P0 homologation.

Original six-control baseline (historical 50F/34E), newer canonical Quality
(51F/34E) and 32 Outbox/Saga ERROR are distinct records. In particular,
neither of the two original SQLite P0s has an exact historical red-green
case pair established by this crosswalk.
"""
from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
DOCS=ROOT/"docs"/"aion"
ORIGINAL=DOCS/"AION_P0_SIX_BLOCKERS_CANONICAL_EVIDENCE_REGISTER_20261019.json"
QUALITY=DOCS/"AION_P0_QUALITY_CANONICAL_85_FAILURES_CASE_REGISTRY_20261019.json"
RECEIPTS=DOCS/"AION_P0_32_EXTERNAL_PRODUCER_EVIDENCE_MATRIX_20261020.json"
AUDIT=DOCS/"AION_P0_SIX_EXIT_EVIDENCE_GAP_MATRIX_20261020.json"
EXPECTED={
 "OWNER_REAL_IDENTITY",
 "PRODUCER_RECEIPT_AUTHENTICITY",
 "FIRST_ATTEMPT_UNCERTAIN_RECOVERY",
 "H0_POST_RESTART_AVAILABILITY",
 "SQLITE_COMPAT_READ_PATH",
 "SQLITE_COMPAT_WRITE_PATH",
}
DENIALS=(
 "external_proof_enrolled",
 "canonical_original_red_green_pair_verified",
 "authentic_owner_approval_verified",
 "security_full_green_verified",
 "quality_full_green_verified",
 "production_allowed",
 "closed",
)

def read(path):
    return json.loads(path.read_text(encoding="utf-8"))

class SixP0ExitEvidenceGapIntegrityLAB(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.orig=read(ORIGINAL)
        cls.quality=read(QUALITY)
        cls.receipts=read(RECEIPTS)
        cls.audit=read(AUDIT)
        cls.by_id={r["id"]:r for r in cls.audit["p0"]}

    def test_01_original_six_cases_exact_and_unclosed(self):
        self.assertEqual(len(self.audit["p0"]),6)
        self.assertEqual(len(self.by_id),6)
        self.assertEqual(set(self.by_id),EXPECTED)
        self.assertEqual(self.audit["homologated_p0"],0)
        self.assertEqual(self.audit["status"],"HARD_NO_GO")
        self.assertEqual({p["id"] for p in self.orig["p0"]},EXPECTED)

    def test_02_two_quality_snapshots_not_conflated(self):
        historical=self.audit["historical_quality_register"]
        current=self.audit["newer_quality_baseline"]
        self.assertEqual((historical["fail"],historical["error"],historical["cases"]),
                         (self.orig["historical_quality"]["failures"],
                          self.orig["historical_quality"]["errors"],
                          self.orig["historical_quality"]["recorded_cases"]))
        self.assertEqual((current["fail"],current["error"],current["cases"]),
                         (self.quality["fail_total"],self.quality["error_total"],
                          self.quality["quality_total"]))
        self.assertEqual(historical["state"],"HISTORICAL_NOT_CURRENT")
        self.assertEqual(current["state"],"RED_NOT_RERUN")
        self.assertEqual(self.audit["difference_fail"],1)
        self.assertEqual(self.audit["difference_error"],0)
        self.assertEqual((historical["fail"],current["fail"]),(50,51))

    def test_03_quality85_identity_and_coverage_unmodified(self):
        a=self.audit
        self.assertEqual(a["newer_quality_baseline"]["run"],"39334210568")
        self.assertEqual(a["newer_quality_baseline"]["commit"],
                         self.quality["source_commit"])
        self.assertEqual(a["quality85_module_names"],
                         sorted(self.quality["module_totals"]))
        self.assertEqual(len(self.quality["entries"]),85)
        self.assertEqual(Counter(r["kind"] for r in self.quality["entries"]),
                         {"FAIL":51,"ERROR":34})

    def test_04_latest_85_cases_have_no_direct_sqlite_test_module(self):
        self.assertTrue(self.audit["latest_85_not_an_original_sqlite_pair_identification"])
        modules={r["module"] for r in self.quality["entries"]}
        self.assertEqual(modules,set(self.quality["module_totals"]))
        self.assertFalse(any(m.startswith("test_aion_p0_original_sqlite")
                             for m in modules))
        # This does NOT claim none of the 85 tests involve SQLite internally.

    def test_05_sqlite_historical_case_mappings_not_fabricated(self):
        for name in ("SQLITE_COMPAT_READ_PATH","SQLITE_COMPAT_WRITE_PATH"):
            with self.subTest(name=name):
                row=self.by_id[name]
                source=next(p for p in self.orig["p0"] if p["id"]==name)
                self.assertIsNone(source["canonical_tracker_id"])
                self.assertIsNone(row["canonical_85_case_id"])
                self.assertEqual(row["canonical_85_case_mapping_status"],
                                 "UNMAPPED_EXACT_ORIGINAL_INCIDENT")
                self.assertEqual(row["priority"],0)
                self.assertFalse(row["canonical_original_red_green_pair_verified"])
        self.assertIs(self.audit["original_sqlite_read_failure_tracked_exactly"],False)
        self.assertIs(self.audit["original_sqlite_write_failure_tracked_exactly"],False)

    def test_06_every_old_lab_observation_retained_without_promotion(self):
        originals={r["id"]:r for r in self.orig["p0"]}
        for row in self.audit["p0"]:
            with self.subTest(p0=row["id"]):
                p=originals[row["id"]]
                self.assertEqual(row["historical_register_status"],p["status"])
                self.assertEqual(row["historical_lab_evidence_reference"],p["lab_reference"])
                self.assertEqual(row["historical_lab_fact"],p["lab_fact"])
                self.assertEqual(row["historical_source_files"],p["source"])
                self.assertIs(row["no_unjustified_mapping_from_85"],True)

    def test_07_each_p0_has_concrete_exit_and_immediate_zero_cost_action(self):
        for row in self.audit["p0"]:
            with self.subTest(p0=row["id"]):
                self.assertGreaterEqual(len(row["required_evidence"]),4)
                self.assertTrue(all(type(x) is str and len(x)>18
                                    for x in row["required_evidence"]))
                self.assertGreater(len(row["independent_acceptance_contract"]),35)
                self.assertGreater(len(row["next_permitted_action"]),35)
                self.assertGreater(len(row["gate_owner_role"]),12)
                self.assertTrue(row["status"].startswith("OPEN_"))

    def test_08_six_positive_evidence_or_authority_flags_never_claimed(self):
        for row in self.audit["p0"]:
            with self.subTest(p0=row["id"]):
                for flag in DENIALS:
                    self.assertIs(row[flag],False,(row["id"],flag))
        for flag in ("full_quality_green","full_security_green",
                     "independent_human_owner_enrolled",
                     "independent_producer_enrolled",
                     "external_highwater_enrolled",
                     "automatic_retry_allowed","worker_allowed",
                     "provider_sends_approved","cloud_provisioning_approved"):
            self.assertIs(self.audit[flag],False,flag)
        self.assertEqual(self.audit["authorized_new_spend_brl"],0)

    def test_09_32_outbox_saga_original_errors_preserved_and_segmented(self):
        recorded=self.audit["outbox_saga_32"]
        self.assertEqual(recorded["total"],32)
        self.assertEqual(recorded["total"],self.receipts["error_total"])
        self.assertEqual(recorded["first_gate_counts"],
                         self.receipts["gate_counts"])
        self.assertEqual(recorded["first_gate_counts"],{
            "PRE_ADAPTER_PRODUCER_ENROLLMENT":23,
            "CAUSAL_COMMITTED_EFFECT_RECEIPT":8,
            "TERMINAL_NO_EFFECT_FENCE":1,
        })
        self.assertEqual(recorded["case_status"],"ALL_OPEN_NOT_WAIVED")
        self.assertEqual(set(r["status"] for r in self.receipts["cases"]),
                         {"OPEN_NOT_WAIVED"})

    def test_10_external_p0_requirements_not_exchanged_for_lab_pass(self):
        for name in ("OWNER_REAL_IDENTITY","PRODUCER_RECEIPT_AUTHENTICITY",
                     "FIRST_ATTEMPT_UNCERTAIN_RECOVERY",
                     "H0_POST_RESTART_AVAILABILITY"):
            row=self.by_id[name]
            self.assertEqual(row["priority"],1)
            self.assertFalse(row["external_proof_enrolled"])
            self.assertFalse(row["production_allowed"])
            self.assertIsNone(row["canonical_85_case_id"])

    def test_11_source_files_for_six_still_exist(self):
        for row in self.audit["p0"]:
            for f in row["historical_source_files"]:
                with self.subTest(p0=row["id"],file=f):
                    self.assertTrue((ROOT/f).is_file(),f)

    def test_12_crosswalk_does_not_depend_on_real_network_or_provider(self):
        self.assertEqual(self.audit["sources"]["original_six"],ORIGINAL.relative_to(ROOT).as_posix())
        self.assertEqual(self.audit["sources"]["quality85"],QUALITY.relative_to(ROOT).as_posix())
        self.assertEqual(self.audit["sources"]["outbox_saga32"],RECEIPTS.relative_to(ROOT).as_posix())
        self.assertEqual(self.audit["sources"]["previous_lab_run"],"39415147568")
        self.assertEqual(self.audit["homologated_p0"],0)
        self.assertEqual(self.audit["status"],"HARD_NO_GO")


if __name__=="__main__":
    unittest.main()
