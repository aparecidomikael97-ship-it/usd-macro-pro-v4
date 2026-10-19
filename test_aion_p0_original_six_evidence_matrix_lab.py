"""P0 evidence-integrity audit, NOT proof of operational trust.

Checks six explicit OPEN requirements against real repo files and pins A118
sources for historic replay gate. Imports no Worker, sends no messages and
cannot turn historical unit-test PASS into real-world certification.
"""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "docs/aion/AION_P0_SIX_BLOCKERS_CANONICAL_EVIDENCE_REGISTER_20261019.json"
EXPECTED = {
    "OWNER_REAL_IDENTITY", "PRODUCER_RECEIPT_AUTHENTICITY",
    "FIRST_ATTEMPT_UNCERTAIN_RECOVERY", "H0_POST_RESTART_AVAILABILITY",
    "SQLITE_COMPAT_READ_PATH", "SQLITE_COMPAT_WRITE_PATH",
}


def load():
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def blob_sha(path: Path):
    # Git applies the repo's text conversion rules; hashing checkout bytes
    # manually fails on Windows CRLF even if the *tracked Git blob* is pinned.
    p = subprocess.run(
        ["git", "hash-object", str(path)], cwd=ROOT,
        capture_output=True, text=True, check=True,
    )
    return p.stdout.strip()


class AionP0OriginalEvidenceAuditTests(unittest.TestCase):
    def test_01_all_six_p0_present_exactly_once(self):
        doc = load()
        self.assertEqual(doc["p0_total"], 6)
        self.assertEqual(len(doc["p0"]), 6)
        self.assertEqual({p["id"] for p in doc["p0"]}, EXPECTED)

    def test_02_no_p0_homologated_or_credential_falsely_enrolled(self):
        doc=load()
        self.assertEqual(doc["p0_homologated"], 0)
        self.assertEqual(doc["status"], "HARD_NO_GO")
        self.assertIs(doc["operational_worker_authorized"], False)
        self.assertIs(doc["automatic_retry_authorized"], False)
        self.assertIs(doc["lab_pass_is_homologation"], False)

    def test_03_every_p0_has_explicit_missing_independent_evidence(self):
        doc=load()
        for p in doc["p0"]:
            with self.subTest(p0=p["id"]):
                self.assertTrue(p["status"].startswith("OPEN_"))
                self.assertIs(p["independent_evidence_obtained"], False)
                self.assertGreaterEqual(len(p["missing"]), 3)
                self.assertTrue(p["lab_reference"].startswith("https://github.com/"))
                self.assertNotIn("homologated", p["lab_fact"].lower())

    def test_04_every_linked_module_is_present_in_checkout(self):
        for p in load()["p0"]:
            for name in p["source"]:
                with self.subTest(p0=p["id"], file=name):
                    self.assertTrue((ROOT / name).is_file(), name)

    def test_05_sqlite_p0_original_failure_ids_explicitly_unmapped(self):
        for p in load()["p0"]:
            if p["id"].startswith("SQLITE_COMPAT_"):
                self.assertIsNone(p["canonical_tracker_id"])
                self.assertIn("UNMAPPED", p["status"])
                self.assertIn("exact historic failing", " ".join(p["missing"]))

    def test_06_security_and_quality_historical_status_not_falsely_current(self):
        doc=load()
        q=doc["historical_quality"]
        s=doc["historical_security"]
        self.assertEqual(q["failures"], 50)
        self.assertEqual(q["errors"], 34)
        self.assertGreater(q["recorded_cases"], 6500)
        self.assertEqual(s["recorded_cases"], 365)
        self.assertEqual(q["evidence_status"], "HISTORICAL_NOT_RERUN_AS_CURRENT")
        self.assertEqual(s["evidence_status"], "HISTORICAL_NOT_RERUN_AS_CURRENT")

    def test_07_original_m71_reactivation_sources_pinned_a118(self):
        doc=load()
        m=doc["cross_cutting_unresolved"][0]
        expected=m["original_code_blobs"]
        # The historical A118 original is pinned in Git history, while
        # this LAB checkout contains the deliberate M71 fail-closed fix.
        original = subprocess.run(
            ["git", "rev-parse",
             "c62fab663c6349d7320f7843c8d09587c514426b:atlasquant_aion_global_worker_reactivation_gate.py"],
            cwd=ROOT, capture_output=True, text=True, check=True,
        ).stdout.strip()
        self.assertEqual(original, expected["reactivation_gate"])
        self.assertEqual(
            blob_sha(ROOT / "atlasquant_aion_global_worker_reactivation_gate.py"),
            m["current_lab_gate_blob"],
        )
        self.assertIn("LAB_DIRECT_VALIDATOR_HARDSTOP_GREEN", m["status"])
        self.assertEqual(
            blob_sha(ROOT / "atlasquant_aion_global_worker_incident_reconciliation.py"),
            expected["incident_reconciliation"],
        )
        self.assertEqual(
            blob_sha(ROOT / "atlasquant_aion_global_worker_activation.py"),
            "df43bb4371c784396069f4ede51205b0aa19cc0a",
        )
        self.assertIs(m["counts_toward_six"], False)

    def test_08_m71_original_safety_assertion_is_now_green_on_lab_fix(self):
        # SAME original M71 safety assertion is never weakened or xfailed.
        # Its PRE-FIX RED is retained by the immutable Actions run below;
        # on this LAB patch the assertion must return GREEN (BLOCKED).
        p=subprocess.run(
            [sys.executable,"-B","-m","unittest","-v",
             "test_aion_p0_m71_original_stale_gate_safety_negative_lab"],
            cwd=ROOT, capture_output=True,text=True,timeout=45,
        )
        combined=p.stdout + "\n" + p.stderr
        self.assertEqual(p.returncode, 0, combined)
        self.assertNotIn("M71_RED_STALE_READY_GATE_ACCEPTED_AFTER_REOPENED_INCIDENT", combined)
        self.assertIn("Ran 1 test", combined)
        m=load()["cross_cutting_unresolved"][0]
        self.assertIn("/actions/runs/39335321672", m["original_red_baseline_run"])
        self.assertIn("/actions/runs/39335745839", m["fixed_focused_lab_run"])
        self.assertIs(m["counts_toward_six"], False)
        print("M71_A118_HISTORICAL_RED_RETAINED_LAB_DIRECT_VALIDATOR_GREEN_NO_GO")

    def test_09_no_external_witness_buried_in_p0_descriptions(self):
        doc=load()
        for p in doc["p0"]:
            self.assertIs(p["independent_evidence_obtained"], False)
            self.assertNotIn(p["status"], ("CLOSED", "GO", "READY", "HOMOLOGATED"))
        self.assertEqual(doc["decision"],
                         "NO_PROMOTION_WITHOUT_EXACT_CANONICAL_FAILURE_MAPPING_AND_INDEPENDENT_EVIDENCE")

    def test_10_all_6_p0_independent_from_crosscut_m71(self):
        doc=load()
        self.assertEqual(len(doc["cross_cutting_unresolved"]), 1)
        self.assertEqual(doc["cross_cutting_unresolved"][0]["id"],
                         "M71_STALE_REACTIVATION_GATE_REPLAY")
        self.assertNotIn("M71_STALE_REACTIVATION_GATE_REPLAY",EXPECTED)


if __name__=="__main__":
    unittest.main()
