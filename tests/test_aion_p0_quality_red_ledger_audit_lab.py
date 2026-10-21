"""Self-contained security/regression tests for the canonical Quality RED ledger.

Synthetic job lines in tests exercise the read-only parser; they are NOT
claimed to be a real CI run. The authoritative ledger comes from the actual
Quality job at the SHA declared in docs/aion/evidence.
"""
from __future__ import annotations

from copy import deepcopy
from collections import Counter
import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT / "tools"))
from aion_p0_quality_red_ledger import (  # noqa: E402
    EvidenceError, compare_log, extract_canonical_job, load_ledger,
    validate_ledger,
)


def make_log(headers, *, modules=588, tests=6895, sha="a"*40, claimed=None):
    counted=Counter(line.split(":",1)[0] for line in headers)
    failure=claimed if claimed is not None else (counted["FAIL"],counted["ERROR"])
    return "\n".join([
        f"2026-10-21T00:00:00Z AION_P0_CANONICAL_UNMODIFIED_MODULES {modules}",
        f"2026-10-21T00:00:01Z AION_P0_CANONICAL_ROOT_HEAD {sha}",
        *(f"2026-10-21T00:00:02Z {line}" for line in headers),
        f"2026-10-21T00:02:00Z Ran {tests} tests in 60.0s",
        f"2026-10-21T00:02:01Z FAILED (failures={failure[0]}, errors={failure[1]})",
        "2026-10-21T00:02:02Z Ran 64 tests in 1.0s",
    ])+"\n"


class QualityRedLedgerInvariantTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ledger=load_ledger()
        cls.ids=[r["identifier"] for r in cls.ledger["entries"]]

    def test_01_baseline_provenance_exact_head_and_full_85(self):
        b=self.ledger["baseline"]
        self.assertEqual(b["head_sha"],"0630441417fb1ec0e42a06ca0b104a311a6de399")
        self.assertEqual((b["modules"],b["tests"],b["pass"],b["fail"],b["error"]),
                         (588,6895,6810,51,34))
        self.assertEqual(len(self.ids),85)
        self.assertEqual(len(set(self.ids)),85)

    def test_02_classifications_do_not_mint_authority(self):
        groups=Counter(r["family"] for r in self.ledger["entries"])
        self.assertEqual(groups, {
            "INDEPENDENT_PRODUCER_GATE":32,
            "LEGACY_ACTIVATION_PLAN_EXPECTATION":3,
            "LEGACY_WORKER_EXPECTATION":50,
        })
        policy=self.ledger["rules"]
        self.assertEqual(policy["workflow_governance"],"HARD_NO_GO")
        self.assertIs(policy["worker_enabled"],False)
        self.assertIs(policy["automatic_resend_allowed"],False)
        self.assertIs(policy["legacy_tests_waived"],False)

    def test_03_synthetic_exact_headers_still_red_no_homologation(self):
        report=compare_log(self.ledger,make_log(self.ids))
        self.assertTrue(report["same_identifiers"])
        self.assertEqual(report["verdict"],"STABLE_RED_NO_HOMOLOGATION")
        self.assertFalse(report["quality_pass"])
        self.assertFalse(report["worker_activation_allowed"])
        self.assertFalse(report["auto_resend_allowed"])
        self.assertEqual(report["homologated_p0_count"],0)

    def test_04_single_new_failure_cannot_hide_unchanged_count(self):
        modified=self.ids.copy()
        lost=next(i for i,x in enumerate(modified) if x.startswith("FAIL: "))
        modified[lost]="FAIL: test_new_unexpected_failure (test_demo.Demo.test_new_unexpected_failure)"
        report=compare_log(self.ledger,make_log(modified))
        self.assertFalse(report["same_identifiers"])
        self.assertEqual(report["verdict"],"RED_DRIFT_MANUAL_REVIEW")
        self.assertEqual(len(report["added_failure_identifiers"]),1)
        self.assertEqual(len(report["missing_failure_identifiers_require_manual_review"]),1)
        self.assertFalse(report["quality_pass"])

    def test_05_disappeared_failure_requires_review_not_automatic_green(self):
        filtered=[x for x in self.ids if x!=self.ids[0]]
        report=compare_log(self.ledger,make_log(filtered))
        self.assertFalse(report["same_identifiers"])
        self.assertEqual(len(report["missing_failure_identifiers_require_manual_review"]),1)
        self.assertFalse(report["worker_activation_allowed"])

    def test_06_summary_count_mismatch_is_rejected(self):
        with self.assertRaisesRegex(EvidenceError,"CANONICAL_FAILURE_HEADERS_INCOMPLETE"):
            extract_canonical_job(make_log(self.ids,claimed=(50,34)))

    def test_07_duplicate_test_header_cannot_be_silently_counted(self):
        with self.assertRaisesRegex(EvidenceError,"CANONICAL_DUPLICATE_IDENTIFIERS"):
            extract_canonical_job(make_log(self.ids+[self.ids[0]]))

    def test_08_truncated_or_abridged_log_is_not_evidence(self):
        with self.assertRaises(EvidenceError):
            extract_canonical_job("FAIL: test_fake (test_demo.Demo.test_fake)")

    def test_09_wrong_quality_module_set_is_not_accepted(self):
        with self.assertRaisesRegex(EvidenceError,"CANONICAL_LOG_WRONG_SUITE"):
            extract_canonical_job(make_log(self.ids,modules=587))

    def test_10_malformed_baseline_cannot_change_hard_no_go(self):
        altered=deepcopy(self.ledger)
        altered["rules"]["worker_enabled"]=True
        with self.assertRaisesRegex(EvidenceError,"LEDGER_UNSAFE_AUTHORITY_CLAIM"):
            validate_ledger(altered)

    def test_11_identifier_removed_from_baseline_must_not_silently_pass(self):
        altered=deepcopy(self.ledger)
        altered["entries"].pop()
        with self.assertRaisesRegex(EvidenceError,"LEDGER_RECORD_COUNT_MISMATCH"):
            validate_ledger(altered)

    def test_12_duplicate_baseline_identifier_is_denied(self):
        altered=deepcopy(self.ledger)
        altered["entries"][1]["identifier"]=altered["entries"][0]["identifier"]
        altered["entries"][1]["kind"]=altered["entries"][0]["kind"]
        altered["entries"][1]["module"]=altered["entries"][0]["module"]
        with self.assertRaisesRegex(EvidenceError,"LEDGER_DUPLICATE_IDENTIFIER"):
            validate_ledger(altered)

    def test_13_broken_baseline_origin_sha_is_denied(self):
        altered=deepcopy(self.ledger)
        altered["baseline"]["head_sha"]="not-a-commit"
        with self.assertRaisesRegex(EvidenceError,"LEDGER_SHA_INVALID"):
            validate_ledger(altered)

    def test_14_wrong_head_provenance_is_exposed_in_output(self):
        report=compare_log(self.ledger,make_log(self.ids,sha="b"*40))
        self.assertEqual(report["current_head_sha"],"b"*40)
        self.assertNotEqual(report["current_head_sha"],report["baseline_head_sha"])
        self.assertEqual(report["governance"],"HARD_NO_GO")


if __name__=="__main__":
    unittest.main()
