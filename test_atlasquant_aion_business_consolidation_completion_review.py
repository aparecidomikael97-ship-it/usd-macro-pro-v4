import ast
import unittest
from pathlib import Path

from atlasquant_aion_business_consolidation_completion_review import (
    FINAL_ACKNOWLEDGEMENTS,
    REQUIRED_DECISION_TOKEN,
    REQUIRED_FINAL_CHECKS,
    completion_review_template,
    final_admin_decision_request,
    record_final_admin_acknowledgement,
    validate_completion_evidence,
)
from atlasquant_aion_business_consolidation_progress_ledger import SCHEMA as LEDGER_SCHEMA


FINAL_SHA = "b" * 40
LEDGER_DIGEST = "c" * 64


def _ledger():
    return {
        "schema": LEDGER_SCHEMA,
        "state": "CONSOLIDATION_COMPLETE_REVIEW_REQUIRED",
        "ledger_complete": True,
        "completion_review_required": True,
        "completed_count": 19,
        "total_steps": 19,
        "ledger_digest": LEDGER_DIGEST,
        "current_main_sha": FINAL_SHA,
        "deploy_authorized": False,
        "runtime_activation_authorized": False,
        "executes_action": False,
    }


def _checks(value="success"):
    return {name: value for name in REQUIRED_FINAL_CHECKS}


class ConsolidationCompletionReviewTests(unittest.TestCase):
    def test_template_is_read_only_and_requires_final_evidence(self):
        row = completion_review_template()
        self.assertEqual(row["state"], "COMPLETION_EVIDENCE_REQUIRED")
        self.assertEqual(row["required_decision_token"], REQUIRED_DECISION_TOKEN)
        self.assertFalse(row["ready_for_final_admin_review"])
        self.assertFalse(row["technical_consolidation_complete"])
        self.assertFalse(row["deploy_authorized"])
        self.assertFalse(row["runtime_activation_authorized"])
        self.assertFalse(row["executes_action"])

    def test_complete_evidence_reaches_final_admin_review_only(self):
        row = validate_completion_evidence(
            _ledger(),
            final_main_sha=FINAL_SHA,
            check_results=_checks(),
            business_runtime_off=True,
            deploy_decision_separate=True,
            final_evidence_ref="github://main/final-ci-bundle",
        )
        self.assertEqual(row["state"], "READY_FOR_FINAL_ADMIN_REVIEW")
        self.assertTrue(row["ready_for_final_admin_review"])
        self.assertEqual(len(row["completion_review_digest"]), 64)
        self.assertEqual(row["blockers"], [])
        self.assertFalse(row["technical_consolidation_complete"])
        self.assertFalse(row["deploy_authorized"])
        self.assertFalse(row["production_release_authorized"])
        self.assertFalse(row["runtime_activation_authorized"])
        self.assertFalse(row["executes_action"])

    def test_main_sha_mismatch_blocks(self):
        row = validate_completion_evidence(
            _ledger(),
            final_main_sha="d" * 40,
            check_results=_checks(),
            business_runtime_off=True,
            deploy_decision_separate=True,
            final_evidence_ref="github://main/final-ci-bundle",
        )
        self.assertEqual(row["state"], "COMPLETION_BLOCKED")
        self.assertIn("final_main_sha_matches_ledger", row["blockers"])
        self.assertFalse(row["ready_for_final_admin_review"])

    def test_failed_required_check_blocks(self):
        checks = _checks()
        checks["mobile_dom"] = "failure"
        row = validate_completion_evidence(
            _ledger(),
            final_main_sha=FINAL_SHA,
            check_results=checks,
            business_runtime_off=True,
            deploy_decision_separate=True,
            final_evidence_ref="github://main/final-ci-bundle",
        )
        self.assertEqual(row["state"], "COMPLETION_BLOCKED")
        self.assertIn("all_required_final_checks_success", row["blockers"])
        self.assertIn("ui_mobile_success", row["blockers"])

    def test_runtime_or_deploy_boundary_blocks(self):
        runtime = validate_completion_evidence(
            _ledger(),
            final_main_sha=FINAL_SHA,
            check_results=_checks(),
            business_runtime_off=False,
            deploy_decision_separate=True,
            final_evidence_ref="github://main/final-ci-bundle",
        )
        self.assertIn("business_runtime_off", runtime["blockers"])
        deploy = validate_completion_evidence(
            _ledger(),
            final_main_sha=FINAL_SHA,
            check_results=_checks(),
            business_runtime_off=True,
            deploy_decision_separate=False,
            final_evidence_ref="github://main/final-ci-bundle",
        )
        self.assertIn("deploy_decision_separate", deploy["blockers"])

    def test_final_request_requires_valid_review_and_still_authorizes_nothing(self):
        review = validate_completion_evidence(
            _ledger(),
            final_main_sha=FINAL_SHA,
            check_results=_checks(),
            business_runtime_off=True,
            deploy_decision_separate=True,
            final_evidence_ref="github://main/final-ci-bundle",
        )
        request = final_admin_decision_request(review)
        self.assertEqual(request["state"], "FINAL_ADMIN_ACKNOWLEDGEMENT_REQUIRED")
        self.assertEqual(request["required_decision_token"], REQUIRED_DECISION_TOKEN)
        self.assertFalse(request["generic_confirmation_is_authorization"])
        self.assertFalse(request["technical_consolidation_complete"])
        self.assertFalse(request["deploy_authorized"])
        self.assertFalse(request["runtime_activation_authorized"])

    def test_generic_confirmation_cannot_acknowledge_completion(self):
        review = validate_completion_evidence(
            _ledger(),
            final_main_sha=FINAL_SHA,
            check_results=_checks(),
            business_runtime_off=True,
            deploy_decision_separate=True,
            final_evidence_ref="github://main/final-ci-bundle",
        )
        request = final_admin_decision_request(review)
        result = record_final_admin_acknowledgement(
            request,
            decision_token="vamos lá",
            acknowledgements={name: True for name in FINAL_ACKNOWLEDGEMENTS},
            actor="Mikael",
        )
        self.assertEqual(result["state"], "BLOCKED")
        self.assertFalse(result["technical_consolidation_complete"])
        self.assertFalse(result["deploy_authorized"])

    def test_exact_acknowledgement_can_close_technical_review_but_not_deploy(self):
        review = validate_completion_evidence(
            _ledger(),
            final_main_sha=FINAL_SHA,
            check_results=_checks(),
            business_runtime_off=True,
            deploy_decision_separate=True,
            final_evidence_ref="github://main/final-ci-bundle",
        )
        request = final_admin_decision_request(review)
        result = record_final_admin_acknowledgement(
            request,
            decision_token=REQUIRED_DECISION_TOKEN,
            acknowledgements={name: True for name in FINAL_ACKNOWLEDGEMENTS},
            actor="Mikael",
        )
        self.assertEqual(result["state"], "TECHNICAL_CONSOLIDATION_ACKNOWLEDGED")
        self.assertTrue(result["technical_consolidation_complete"])
        self.assertEqual(len(result["acknowledgement_digest"]), 64)
        self.assertTrue(result["deploy_decision_required_separately"])
        self.assertFalse(result["deploy_authorized"])
        self.assertFalse(result["production_release_authorized"])
        self.assertFalse(result["runtime_activation_authorized"])
        self.assertFalse(result["executes_action"])

    def test_module_has_no_network_git_or_process_executor(self):
        source = Path(
            "atlasquant_aion_business_consolidation_completion_review.py"
        ).read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported = []
        for node in tree.body:
            if isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.append(node.module or "")
        for banned in ("requests", "urllib", "httpx", "socket", "subprocess", "github"):
            self.assertNotIn(banned, imported)


if __name__ == "__main__":
    unittest.main()
