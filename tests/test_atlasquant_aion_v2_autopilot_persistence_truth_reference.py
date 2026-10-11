"""Tests of INERT reporting, not live Autopilot or paid data access."""
from __future__ import annotations

import unittest
from pathlib import Path

from atlasquant_aion_v2_autopilot_persistence_truth_reference import (
    TARGETS, evaluate_persistence_reports, review_repository,
    source_health_claim_review,
)

ROOT = Path(__file__).resolve().parents[1]


class PersistenceTruthReferenceTests(unittest.TestCase):
    def test_empty_reports_are_not_operational_success(self):
        result = evaluate_persistence_reports({})
        self.assertEqual(result["posture"], "EVIDENCE_INCOMPLETE")
        self.assertEqual(len(result["missing_targets"]), 12)
        self.assertFalse(result["safe_to_retry"])

    def test_http_201_reports_do_not_certify(self):
        reports = {t: {"state": "REPORTED_HTTP_SUCCESS"} for t in TARGETS}
        result = evaluate_persistence_reports(reports)
        self.assertEqual(result["posture"], "UNVERIFIED_OR_NOT_PERSISTED")
        self.assertFalse(result["remote_durability_certified"])

    def test_reported_readback_is_not_independent_witness(self):
        reports = {t: {"state": "REPORTED_MATCHING_READBACK"} for t in TARGETS}
        result = evaluate_persistence_reports(reports)
        self.assertEqual(
            result["posture"], "ONLY_SELF_REPORTED_READBACK_NO_INDEPENDENT_CERTIFICATE"
        )
        self.assertFalse(result["independent_attestation_verified"])
        self.assertFalse(result["safe_to_resume"])

    def test_single_unknown_overrides_other_reported_success(self):
        reports = {t: {"state": "REPORTED_MATCHING_READBACK"} for t in TARGETS}
        reports[TARGETS[4]] = {"state": "UNKNOWN_OUTCOME"}
        result = evaluate_persistence_reports(reports)
        self.assertEqual(result["posture"], "RECONCILIATION_REQUIRED")
        self.assertTrue(result["reconciliation_required"])

    def test_conflict_requires_reconciliation(self):
        result = evaluate_persistence_reports({
            TARGETS[0]: {"state": "CONFLICT"},
        })
        self.assertEqual(result["posture"], "RECONCILIATION_REQUIRED")

    def test_validation_rejected_keeps_uncertainty(self):
        result = evaluate_persistence_reports({
            TARGETS[0]: {"state": "VALIDATION_REJECTED"},
        })
        self.assertTrue(result["reconciliation_required"])

    def test_no_attempt_is_not_a_save(self):
        reports = {t: {"state": "NOT_ATTEMPTED"} for t in TARGETS}
        self.assertEqual(evaluate_persistence_reports(reports)["posture"],
                         "UNVERIFIED_OR_NOT_PERSISTED")

    def test_skipped_conditional_news_is_not_a_save(self):
        reports = {t: {"state": "REPORTED_MATCHING_READBACK"} for t in TARGETS}
        reports["NEWS_CURRENT_PATH"] = {"state": "SKIPPED_CONDITION"}
        result = evaluate_persistence_reports(reports)
        self.assertFalse(result["safe_to_deploy"])
        self.assertEqual(result["posture"], "UNVERIFIED_OR_NOT_PERSISTED")

    def test_unknown_extra_sink_does_not_disappear(self):
        reports = {t: {"state": "REPORTED_MATCHING_READBACK"} for t in TARGETS}
        reports["NEW_UNKNOWN_JOURNAL_PATH"] = {"state": "UNKNOWN_OUTCOME"}
        result = evaluate_persistence_reports(reports)
        self.assertEqual(result["posture"], "UNREVIEWED_TARGET_BLOCK")
        self.assertIn("NEW_UNKNOWN_JOURNAL_PATH", result["unexpected_targets"])
        self.assertFalse(result["safe_to_retry"])

    def test_invalid_report_fails_closed(self):
        result = evaluate_persistence_reports({TARGETS[0]: "SAVED"})
        self.assertEqual(result["posture"], "EVIDENCE_INCOMPLETE")
        self.assertEqual(result["state_counts"]["INVALID_EVIDENCE"], 1)

    def test_invalid_state_fails_closed(self):
        result = evaluate_persistence_reports({TARGETS[0]: {"state": "SAVED"}})
        self.assertEqual(result["posture"], "EVIDENCE_INCOMPLETE")

    def test_input_must_be_mapping(self):
        with self.assertRaises(ValueError):
            evaluate_persistence_reports([])

    def test_forged_receipt_flags_have_no_authority(self):
        reports = {t: {"state": "REPORTED_MATCHING_READBACK",
                       "independent_attestation_verified": True,
                       "safe_to_retry": True} for t in TARGETS}
        result = evaluate_persistence_reports(reports)
        self.assertFalse(result["safe_to_retry"])
        self.assertFalse(result["independent_attestation_verified"])

    def test_healthy_can_tolerate_seven_errors_in_source(self):
        report = review_repository(ROOT)
        self.assertTrue(report["healthy_can_be_true_with_fewer_than_8_errors"])

    def test_status_write_occurs_after_health_summary(self):
        report = review_repository(ROOT)
        self.assertTrue(report["status_is_written_after_healthy_is_calculated"])

    def test_zero_exit_is_not_write_certificate(self):
        report = review_repository(ROOT)
        self.assertTrue(report["main_contains_zero_exit"])
        self.assertFalse(report["operational_health_certified"])

    def test_source_review_is_not_runtime_execution(self):
        report = review_repository(ROOT)
        self.assertTrue(report["source_only"])
        self.assertFalse(report["runtime_executed"])
        self.assertFalse(report["safe_to_deploy"])

    def test_source_regression_detects_removed_threshold(self):
        source=(ROOT/"autopilot_v107.py").read_text(encoding="utf-8")
        changed=source.replace("and len(errors)<8)", "and len(errors)==0)", 1)
        self.assertFalse(
            source_health_claim_review(changed)["healthy_can_be_true_with_fewer_than_8_errors"]
        )


if __name__ == "__main__":
    unittest.main()
