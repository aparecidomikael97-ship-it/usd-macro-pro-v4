import ast
import unittest
from pathlib import Path

from atlasquant_aion_business_consolidation_post_merge_verification import (
    REQUIRED_POST_MERGE_CHECKS,
    post_merge_verification_template,
    rollback_review_packet,
    verify_post_merge_step,
)
from atlasquant_aion_business_consolidation_execution_review_packet import (
    SCHEMA as REVIEW_PACKET_SCHEMA,
)

TARGET_PR = 394
TARGET_HEAD_SHA = "a" * 40
PRE_MERGE_SHA = "b" * 40
MERGE_SHA = "c" * 40


def _packet():
    import hashlib
    import json
    payload = {
        "repository": "aparecidomikael97-ship-it/usd-macro-pro-v4",
        "target_pr": TARGET_PR,
        "target_head_sha": TARGET_HEAD_SHA,
        "base_head_sha": "d" * 40,
        "pre_merge_main_sha": PRE_MERGE_SHA,
        "rollback_reference_sha": PRE_MERGE_SHA,
        "request_digest": "e" * 64,
        "evidence_ref": "github-actions:review-packet:421",
        "reviewer": "Mikael",
        "post_step_requirements": ["run full required CI"],
        "stop_on_any_drift": True,
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return {
        "schema": REVIEW_PACKET_SCHEMA,
        "state": "READY_FOR_HUMAN_EXECUTION_REVIEW",
        "ready_for_human_execution_review": True,
        "packet_digest": digest,
        "payload": payload,
        "target_pr": TARGET_PR,
        "target_head_sha": TARGET_HEAD_SHA,
        "rollback_reference_sha": PRE_MERGE_SHA,
        "merge_execution_authorized": False,
    }


def _checks():
    return {name: "success" for name in REQUIRED_POST_MERGE_CHECKS}


class PostMergeVerificationTests(unittest.TestCase):
    def test_template_requires_real_post_merge_evidence(self):
        row = post_merge_verification_template()
        self.assertEqual(row["state"], "POST_MERGE_EVIDENCE_REQUIRED")
        self.assertFalse(row["step_verified"])
        self.assertFalse(row["next_preflight_allowed"])
        self.assertFalse(row["automatic_rollback"])
        self.assertFalse(row["executes_action"])

    def test_good_evidence_verifies_step_for_next_preflight_only(self):
        row = verify_post_merge_step(
            _packet(),
            target_pr=TARGET_PR,
            expected_merge_sha=MERGE_SHA,
            observed_main_sha=MERGE_SHA,
            pre_merge_main_sha=PRE_MERGE_SHA,
            rollback_reference_sha=PRE_MERGE_SHA,
            check_results=_checks(),
            business_runtime_off=True,
            deploy_authority_absent=True,
            evidence_ref="github-actions:post-merge:example",
        )
        self.assertEqual(row["state"], "STEP_VERIFIED_FOR_NEXT_PREFLIGHT")
        self.assertTrue(row["step_verified"])
        self.assertTrue(row["next_preflight_allowed"])
        self.assertEqual(len(row["verification_receipt_digest"]), 64)
        self.assertFalse(row["rollback_execution_authorized"])
        self.assertFalse(row["merge_authorized"])
        self.assertFalse(row["executes_action"])

    def test_failed_check_requires_human_rollback_review(self):
        checks = _checks()
        checks["ui_smoke"] = "failure"
        row = verify_post_merge_step(
            _packet(),
            target_pr=TARGET_PR,
            expected_merge_sha=MERGE_SHA,
            observed_main_sha=MERGE_SHA,
            pre_merge_main_sha=PRE_MERGE_SHA,
            rollback_reference_sha=PRE_MERGE_SHA,
            check_results=checks,
            business_runtime_off=True,
            deploy_authority_absent=True,
            evidence_ref="github-actions:post-merge:example",
        )
        self.assertEqual(row["state"], "ROLLBACK_REVIEW_REQUIRED")
        self.assertIn("required_check_not_success", row["failures"])
        rollback = rollback_review_packet(row)
        self.assertEqual(rollback["state"], "HUMAN_ROLLBACK_REVIEW_REQUIRED")
        self.assertFalse(rollback["automatic_rollback"])
        self.assertFalse(rollback["rollback_execution_authorized"])

    def test_sha_drift_and_runtime_change_require_review(self):
        row = verify_post_merge_step(
            _packet(),
            target_pr=TARGET_PR,
            expected_merge_sha=MERGE_SHA,
            observed_main_sha="f" * 40,
            pre_merge_main_sha=PRE_MERGE_SHA,
            rollback_reference_sha=PRE_MERGE_SHA,
            check_results=_checks(),
            business_runtime_off=False,
            deploy_authority_absent=True,
            evidence_ref="github-actions:post-merge:example",
        )
        self.assertEqual(row["state"], "ROLLBACK_REVIEW_REQUIRED")
        self.assertIn("merge_result_sha_mismatch", row["failures"])
        self.assertIn("runtime_posture_changed", row["failures"])
        self.assertFalse(row["next_preflight_allowed"])

    def test_wrong_rollback_reference_blocks_next_step(self):
        row = verify_post_merge_step(
            _packet(),
            target_pr=TARGET_PR,
            expected_merge_sha=MERGE_SHA,
            observed_main_sha=MERGE_SHA,
            pre_merge_main_sha=PRE_MERGE_SHA,
            rollback_reference_sha="9" * 40,
            check_results=_checks(),
            business_runtime_off=True,
            deploy_authority_absent=True,
            evidence_ref="github-actions:post-merge:example",
        )
        self.assertEqual(row["state"], "ROLLBACK_REVIEW_REQUIRED")
        self.assertIn("rollback_reference_missing", row["failures"])

    def test_missing_evidence_does_not_fake_failure_or_success(self):
        row = verify_post_merge_step(
            _packet(),
            target_pr=TARGET_PR,
            expected_merge_sha="",
            observed_main_sha="",
            pre_merge_main_sha=PRE_MERGE_SHA,
            rollback_reference_sha=PRE_MERGE_SHA,
            check_results={},
            business_runtime_off=True,
            deploy_authority_absent=True,
            evidence_ref="",
        )
        self.assertEqual(row["state"], "POST_MERGE_EVIDENCE_REQUIRED")
        self.assertFalse(row["step_verified"])
        self.assertFalse(row["next_preflight_allowed"])

    def test_module_has_no_network_git_or_process_executor(self):
        source = Path("atlasquant_aion_business_consolidation_post_merge_verification.py").read_text(encoding="utf-8")
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
