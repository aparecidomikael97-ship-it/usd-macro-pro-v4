import ast
import unittest
from pathlib import Path

from atlasquant_aion_business_consolidation_progress_ledger import (
    build_progress_ledger,
    completion_review_packet,
    progress_ledger_template,
)
from atlasquant_aion_business_consolidation_post_merge_verification import (
    SCHEMA as POST_MERGE_SCHEMA,
)

ROOT = "a" * 40


def _step(pr, rollback_sha, observed_sha, receipt_char):
    return {
        "schema": POST_MERGE_SCHEMA,
        "state": "STEP_VERIFIED_FOR_NEXT_PREFLIGHT",
        "step_verified": True,
        "next_preflight_allowed": True,
        "target_pr": pr,
        "verification_receipt_digest": receipt_char * 64,
        "observed_main_sha": observed_sha,
        "rollback_reference_sha": rollback_sha,
        "executes_action": False,
    }


class ConsolidationProgressLedgerTests(unittest.TestCase):
    def test_template_is_non_executing(self):
        row = progress_ledger_template()
        self.assertEqual(row["state"], "ROOT_MAIN_SHA_REQUIRED")
        self.assertEqual(row["total_steps"], 19)
        self.assertEqual(row["next_expected_pr"], 394)
        self.assertFalse(row["deploy_authorized"])
        self.assertFalse(row["runtime_activation_authorized"])
        self.assertFalse(row["executes_action"])

    def test_empty_valid_ledger_points_to_first_pr(self):
        row = build_progress_ledger([], root_main_sha=ROOT)
        self.assertEqual(row["state"], "READY_FOR_FIRST_PREFLIGHT")
        self.assertEqual(row["completed_count"], 0)
        self.assertEqual(row["next_expected_pr"], 394)
        self.assertTrue(row["next_preflight_allowed"])
        self.assertFalse(row["merge_authorized"])

    def test_verified_prefix_advances_exactly_one_position(self):
        sha1 = "b" * 40
        sha2 = "c" * 40
        rows = [
            _step(394, ROOT, sha1, "1"),
            _step(395, sha1, sha2, "2"),
        ]
        row = build_progress_ledger(rows, root_main_sha=ROOT)
        self.assertEqual(row["state"], "READY_FOR_NEXT_PREFLIGHT")
        self.assertEqual(row["completed_count"], 2)
        self.assertEqual(row["next_expected_pr"], 396)
        self.assertEqual(row["current_main_sha"], sha2)
        self.assertEqual(len(row["ledger_digest"]), 64)

    def test_skipped_pr_blocks_ledger(self):
        sha1 = "b" * 40
        row = build_progress_ledger(
            [_step(395, ROOT, sha1, "1")],
            root_main_sha=ROOT,
        )
        self.assertEqual(row["state"], "LEDGER_BLOCKED")
        self.assertIn("step_1", row["blockers"])
        self.assertIn("target_pr_order", row["entries"][0]["blockers"])
        self.assertFalse(row["next_preflight_allowed"])

    def test_broken_rollback_chain_blocks_ledger(self):
        sha1 = "b" * 40
        sha2 = "c" * 40
        rows = [
            _step(394, ROOT, sha1, "1"),
            _step(395, "d" * 40, sha2, "2"),
        ]
        row = build_progress_ledger(rows, root_main_sha=ROOT)
        self.assertEqual(row["state"], "LEDGER_BLOCKED")
        self.assertIn("rollback_chain", row["entries"][1]["blockers"])

    def test_duplicate_receipt_or_main_sha_blocks(self):
        sha1 = "b" * 40
        rows = [
            _step(394, ROOT, sha1, "1"),
            _step(395, sha1, sha1, "1"),
        ]
        row = build_progress_ledger(rows, root_main_sha=ROOT)
        self.assertEqual(row["state"], "LEDGER_BLOCKED")
        self.assertIn("duplicate_receipt", row["entries"][1]["blockers"])
        self.assertIn("duplicate_main_sha", row["entries"][1]["blockers"])

    def test_all_19_verified_steps_require_final_human_review(self):
        rows = []
        previous = ROOT
        alphabet = "123456789abcdefghi"
        for index, pr in enumerate(range(394, 413)):
            observed = f"{index + 1:040x}"
            rows.append(_step(pr, previous, observed, alphabet[index]))
            previous = observed
        row = build_progress_ledger(rows, root_main_sha=ROOT)
        self.assertEqual(row["state"], "CONSOLIDATION_COMPLETE_REVIEW_REQUIRED")
        self.assertEqual(row["completed_count"], 19)
        self.assertIsNone(row["next_expected_pr"])
        self.assertFalse(row["next_preflight_allowed"])
        self.assertTrue(row["completion_review_required"])
        packet = completion_review_packet(row)
        self.assertEqual(packet["state"], "FINAL_HUMAN_REVIEW_REQUIRED")
        self.assertFalse(packet["deploy_authorized"])
        self.assertFalse(packet["production_release_authorized"])
        self.assertFalse(packet["executes_action"])

    def test_module_has_no_network_git_or_process_executor(self):
        source = Path("atlasquant_aion_business_consolidation_progress_ledger.py").read_text(encoding="utf-8")
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
