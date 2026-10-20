"""18 lab crosswalk checks of P0 closure evidence — NOT a homologation gate."""
from __future__ import annotations
import json
from pathlib import Path
import unittest

from atlasquant_aion_p0_external_evidence_admission_lab import APPROVAL_GAPS


ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "docs/aion/AION_P0_EXTERNAL_EVIDENCE_ADMISSION_CROSSWALK_LAB_20261020.json"
CANON = ROOT / "docs/aion/AION_P0_SIX_EXIT_EVIDENCE_GAP_MATRIX_20261020.json"
IDS = {
    "OWNER_REAL_IDENTITY", "PRODUCER_RECEIPT_AUTHENTICITY",
    "FIRST_ATTEMPT_UNCERTAIN_RECOVERY", "H0_POST_RESTART_AVAILABILITY",
    "SQLITE_COMPAT_READ_PATH", "SQLITE_COMPAT_WRITE_PATH",
}


class EvidenceCrosswalkLAB(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads(PATH.read_text(encoding="utf-8"))
        cls.canon = json.loads(CANON.read_text(encoding="utf-8"))
        cls.by_id = {p["id"]: p for p in cls.data["p0"]}

    def test_01_six_exact_ids_and_unique(self):
        self.assertEqual(set(self.by_id), IDS)
        self.assertEqual(len(self.data["p0"]), len(self.by_id))

    def test_02_original_p0_register_ids_unchanged(self):
        self.assertEqual(set(r["id"] for r in self.canon["p0"]), IDS)

    def test_03_reference_existing_canonical_document(self):
        self.assertEqual(self.data["canonical_reference"], CANON.relative_to(ROOT).as_posix())

    def test_04_all_p0_still_unhomologated(self):
        self.assertEqual(self.data["homologated_p0"], 0)
        self.assertEqual(self.canon["homologated_p0"], 0)
        for p0 in self.data["p0"]:
            self.assertIs(p0["homologated"], False)

    def test_05_global_hard_no_go(self):
        self.assertEqual(self.data["global_status"], "HARD_NO_GO")
        self.assertEqual(self.canon["status"], "HARD_NO_GO")

    def test_06_all_external_proof_claims_false(self):
        for k in ("external_signer_enrolled", "independent_head_verified",
                  "independent_producer_receipt_verified"):
            self.assertIs(self.data[k], False, k)

    def test_07_no_runtime_or_automatic_retry(self):
        for k in ("worker_allowed", "automatic_retry_allowed"):
            self.assertIs(self.data[k], False, k)
        for p0 in self.data["p0"]:
            self.assertIs(p0["approved_for_runtime"], False)

    def test_08_all_individual_proofs_and_test_lineages_open(self):
        for p0 in self.data["p0"]:
            self.assertIs(p0["external_proof_enrolled"], False)
            self.assertIs(p0["original_test_mapping_closed"], False)

    def test_09_no_spend(self):
        self.assertEqual(self.data["authorized_new_spend_brl"], 0)

    def test_10_references_current_static_admission_gaps(self):
        self.assertEqual(set(self.data["admission_gaps"]), set(APPROVAL_GAPS))
        self.assertEqual(len(self.data["admission_gaps"]),
                         len(set(self.data["admission_gaps"])))

    def test_11_every_p0_artifact_list_is_actionable(self):
        for p0 in self.data["p0"]:
            with self.subTest(id=p0["id"]):
                self.assertGreaterEqual(len(p0["required_independent_artifacts"]), 3)
                self.assertTrue(all(isinstance(a, str) and len(a) > 35
                                    for a in p0["required_independent_artifacts"]))

    def test_12_every_p0_blocker_traces_to_admission_or_quality(self):
        for p0 in self.data["p0"]:
            self.assertTrue(p0["blocking_admission_gaps"])
            self.assertTrue(set(p0["blocking_admission_gaps"])
                            <= set(APPROVAL_GAPS))

    def test_13_four_external_gate_classes_distinguished_from_sqlite(self):
        external = {r["id"] for r in self.data["p0"] if r["evidence_class"] != "CANONICAL_FORENSIC"}
        self.assertEqual(external, IDS - {"SQLITE_COMPAT_READ_PATH", "SQLITE_COMPAT_WRITE_PATH"})
        self.assertEqual(len(external), 4)

    def test_14_both_sqlite_paths_unmapped_and_no_lab_promotion(self):
        for id in ("SQLITE_COMPAT_READ_PATH", "SQLITE_COMPAT_WRITE_PATH"):
            row = self.by_id[id]
            canon = next(x for x in self.canon["p0"] if x["id"] == id)
            self.assertEqual(row["evidence_class"], "CANONICAL_FORENSIC")
            self.assertIsNone(canon["canonical_85_case_id"])
            self.assertEqual(canon["canonical_85_case_mapping_status"],
                             "UNMAPPED_EXACT_ORIGINAL_INCIDENT")
            self.assertIn("STAGING LAB", row["notes"])

    def test_15_owner_proof_remains_external_physical(self):
        self.assertEqual(self.by_id["OWNER_REAL_IDENTITY"]["evidence_class"], "EXTERNAL_PHYSICAL")
        self.assertIn("HUMAN_OWNER", self.by_id["OWNER_REAL_IDENTITY"]["title"])

    def test_16_canonical_quality_and_security_no_false_green(self):
        self.assertIs(self.data["quality_full_green"], False)
        self.assertIs(self.data["security_full_green"], False)
        self.assertIs(self.canon["full_quality_green"], False)
        self.assertIs(self.canon["full_security_green"], False)

    def test_17_historical_external_producer_32_still_unwaived(self):
        self.assertEqual(self.data["latest_baseline"]["outbox_saga_unwaived"], 32)
        self.assertEqual(self.canon["outbox_saga_32"]["total"], 32)
        self.assertEqual(self.canon["outbox_saga_32"]["case_status"], "ALL_OPEN_NOT_WAIVED")

    def test_18_baseline_is_historical_not_new_ci_pass(self):
        base = self.data["latest_baseline"]
        self.assertEqual((base["quality_tests"], base["fail"], base["error"]),
                         (6562, 52, 34))
        self.assertIn("not rerun", base["source"])
        self.assertEqual(self.data["origin"], "LAB_READ_ONLY_NON_AUTHORITATIVE")


if __name__ == "__main__":
    unittest.main()
