import ast
import unittest
from pathlib import Path

from atlasquant_aion_business_consolidation_execution_review_packet import (
    build_execution_review_packet,
    review_packet_template,
    verify_review_packet,
)
from atlasquant_aion_business_consolidation_execution_preflight import (
    SCHEMA as PREFLIGHT_SCHEMA,
)

TARGET_SHA = "a" * 40
BASE_SHA = "b" * 40
ROLLBACK_SHA = "c" * 40
REQUEST_DIGEST = "d" * 64


def _preflight():
    return {
        "schema": PREFLIGHT_SCHEMA,
        "state": "MERGE_EXECUTION_REVIEW_REQUIRED",
        "ready_for_separate_execution_review": True,
        "target_pr": 394,
        "target": {"pr": 394, "head_sha": TARGET_SHA},
        "pre_merge_main_sha": ROLLBACK_SHA,
        "rollback_reference_sha": ROLLBACK_SHA,
        "request_digest": REQUEST_DIGEST,
        "post_step_requirements": ["run full required CI"],
        "stop_on_any_drift": True,
        "merge_execution_authorized": False,
        "executes_action": False,
    }


class ExecutionReviewPacketTests(unittest.TestCase):
    def test_template_never_executes(self):
        row = review_packet_template()
        self.assertEqual(row["state"], "PREFLIGHT_REQUIRED")
        self.assertTrue(row["human_execution_review_required"])
        self.assertFalse(row["authorization_created"])
        self.assertFalse(row["merge_execution_authorized"])
        self.assertFalse(row["executes_action"])

    def test_valid_preflight_builds_review_packet_only(self):
        row = build_execution_review_packet(
            _preflight(),
            repository="aparecidomikael97-ship-it/usd-macro-pro-v4",
            candidate_head_sha=TARGET_SHA,
            base_head_sha=BASE_SHA,
            evidence_ref="github-actions:preflight:420",
            reviewer="Mikael",
        )
        self.assertEqual(row["state"], "READY_FOR_HUMAN_EXECUTION_REVIEW")
        self.assertTrue(row["ready_for_human_execution_review"])
        self.assertEqual(len(row["packet_digest"]), 64)
        self.assertFalse(row["authorization_created"])
        self.assertFalse(row["merge_execution_authorized"])
        self.assertFalse(row["deploy_authorized"])
        self.assertFalse(row["runtime_activation_authorized"])
        self.assertFalse(row["executes_action"])

        verified = verify_review_packet(
            row,
            expected_packet_digest=row["packet_digest"],
            target_head_sha=TARGET_SHA,
            rollback_reference_sha=ROLLBACK_SHA,
        )
        self.assertTrue(verified["binding_match"])
        self.assertFalse(verified["merge_execution_authorized"])

    def test_target_sha_drift_blocks_packet(self):
        row = build_execution_review_packet(
            _preflight(),
            repository="aparecidomikael97-ship-it/usd-macro-pro-v4",
            candidate_head_sha="e" * 40,
            base_head_sha=BASE_SHA,
            evidence_ref="github-actions:preflight:420",
            reviewer="Mikael",
        )
        self.assertEqual(row["state"], "BLOCKED")
        self.assertIn("candidate_head_sha", row["blockers"])

    def test_missing_evidence_or_reviewer_blocks(self):
        row = build_execution_review_packet(
            _preflight(),
            repository="aparecidomikael97-ship-it/usd-macro-pro-v4",
            candidate_head_sha=TARGET_SHA,
            base_head_sha=BASE_SHA,
            evidence_ref="",
            reviewer="",
        )
        self.assertEqual(row["state"], "BLOCKED")
        self.assertIn("evidence_ref", row["blockers"])
        self.assertIn("reviewer", row["blockers"])

    def test_invalid_preflight_cannot_be_promoted(self):
        bad = _preflight()
        bad["state"] = "BLOCKED"
        row = build_execution_review_packet(
            bad,
            repository="aparecidomikael97-ship-it/usd-macro-pro-v4",
            candidate_head_sha=TARGET_SHA,
            base_head_sha=BASE_SHA,
            evidence_ref="github-actions:preflight:420",
            reviewer="Mikael",
        )
        self.assertEqual(row["state"], "BLOCKED")
        self.assertIn("preflight_state", row["blockers"])

    def test_module_has_no_network_git_or_process_executor(self):
        source = Path("atlasquant_aion_business_consolidation_execution_review_packet.py").read_text(encoding="utf-8")
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
