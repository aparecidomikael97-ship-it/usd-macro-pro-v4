import unittest

from atlasquant_aion_owner_stack_pre_merge_readiness_v1 import (
    PINNED_MAIN_SHA,
    STACK,
    build_merge_sequence_plan,
    evaluate_pre_merge_readiness,
)
from atlasquant_aion_owner_stack_merge_rollback_recovery_v1 import (
    PINNED_MAIN_TREE_SHA,
    build_rollback_recovery_plan,
    evaluate_merge_journal,
    rollback_order,
    rollback_policy,
    verify_full_recovery,
)


class AionOwnerStackMergeRollbackRecoveryV1Tests(unittest.TestCase):
    def observed_rows(self):
        return [
            {
                "number": item["number"],
                "state": "open",
                "draft": True,
                "mergeable": True,
                "base": item["base"],
                "head": item["head"],
                "head_sha": item["head_sha"],
                "files": [
                    {"filename": path, "status": "added", "deletions": 0}
                    for path in item["files"]
                ],
                "workflows": [
                    {
                        "name": name,
                        "status": "completed",
                        "conclusion": "success",
                    }
                    for name in item["required_workflows"]
                ],
            }
            for item in STACK
        ]

    def readiness_and_sequence(self):
        readiness = evaluate_pre_merge_readiness(
            self.observed_rows(),
            observed_main_sha=PINNED_MAIN_SHA,
        )
        self.assertEqual(
            readiness["state"],
            "READY_FOR_HUMAN_OWNER_MERGE_SEQUENCE_REVIEW",
        )
        sequence = build_merge_sequence_plan(readiness)
        self.assertEqual(sequence["state"], "MERGE_SEQUENCE_PLAN_READY")
        return readiness, sequence

    def test_rollback_plan_is_ready_but_non_authoritative(self):
        readiness, sequence = self.readiness_and_sequence()
        plan = build_rollback_recovery_plan(
            readiness,
            sequence,
            observed_anchor_main_sha=PINNED_MAIN_SHA,
            observed_anchor_tree_sha=PINNED_MAIN_TREE_SHA,
        )
        self.assertEqual(
            plan["state"],
            "READY_FOR_HUMAN_OWNER_ROLLBACK_PLAN_REVIEW",
            plan["blockers"],
        )
        self.assertEqual(plan["anchor_main_sha"], PINNED_MAIN_SHA)
        self.assertEqual(plan["anchor_main_tree_sha"], PINNED_MAIN_TREE_SHA)
        self.assertEqual(len(plan["steps"]), 15)
        self.assertEqual(
            plan["rollback_strategy"],
            "REVERT_COMMITS_IN_REVERSE_DEPENDENCY_ORDER",
        )
        self.assertTrue(plan["recovery_comparison_uses_tree_not_commit_sha"])
        self.assertTrue(plan["anchor_history_may_differ_after_revert"])
        self.assertTrue(plan["anchor_tree_must_match_for_full_stack_recovery"])
        self.assertFalse(plan["force_push_allowed"])
        self.assertFalse(plan["remote_main_reset_allowed"])
        self.assertFalse(plan["history_rewrite_allowed"])
        self.assertFalse(plan["automatic_revert_allowed"])
        self.assertFalse(plan["merge_authorized"])
        self.assertFalse(plan["rollback_authorized"])
        self.assertFalse(plan["revert_authorized"])
        self.assertFalse(plan["repository_mutation_performed"])
        self.assertFalse(plan["executes_action"])

    def test_anchor_drift_blocks_plan(self):
        readiness, sequence = self.readiness_and_sequence()
        plan = build_rollback_recovery_plan(
            readiness,
            sequence,
            observed_anchor_main_sha="0" * 40,
            observed_anchor_tree_sha="1" * 40,
        )
        self.assertEqual(plan["state"], "BLOCKED")
        self.assertIn("ANCHOR_MAIN_SHA_MISMATCH", plan["blockers"])
        self.assertIn("ANCHOR_MAIN_TREE_SHA_MISMATCH", plan["blockers"])

    def test_failure_at_parent_reverts_descendants_first(self):
        order = rollback_order(
            [1015, 1016, 1017, 1018],
            failure_at_pr=1016,
        )
        self.assertEqual(order["state"], "ROLLBACK_ORDER_READY")
        self.assertEqual(order["revert_pr_order"], [1018, 1017, 1016])
        self.assertTrue(order["reverse_dependency_order"])
        self.assertFalse(order["force_push_allowed"])
        self.assertFalse(order["remote_main_reset_allowed"])
        self.assertFalse(order["automatic_revert_allowed"])
        self.assertFalse(order["revert_authorized"])
        self.assertFalse(order["executes_action"])

    def test_noncanonical_merge_history_blocks_rollback_order(self):
        order = rollback_order(
            [1015, 1017, 1016],
            failure_at_pr=1016,
        )
        self.assertEqual(order["state"], "BLOCKED")
        self.assertIn(
            "MERGED_SEQUENCE_NOT_PARENT_BEFORE_CHILD",
            order["blockers"],
        )

    def test_unmerged_failure_target_blocks(self):
        order = rollback_order([1015, 1016], failure_at_pr=1017)
        self.assertEqual(order["state"], "BLOCKED")
        self.assertIn(
            "FAILURE_PR_MUST_ALREADY_BE_MERGED",
            order["blockers"],
        )

    def test_merge_journal_prefix_requires_continuous_main_chain(self):
        entries = [
            {
                "pr_number": 1015,
                "pre_merge_main_sha": PINNED_MAIN_SHA,
                "post_merge_main_sha": "1" * 40,
                "merge_commit_sha": "2" * 40,
                "pre_merge_tree_sha": PINNED_MAIN_TREE_SHA,
                "post_merge_tree_sha": "3" * 40,
                "owner_authorization_verified": True,
                "exact_file_delta_verified": True,
                "required_gates_green": True,
                "deploy_executed": False,
                "worker_activated": False,
                "provider_activated": False,
            },
            {
                "pr_number": 1016,
                "pre_merge_main_sha": "1" * 40,
                "post_merge_main_sha": "4" * 40,
                "merge_commit_sha": "5" * 40,
                "pre_merge_tree_sha": "3" * 40,
                "post_merge_tree_sha": "6" * 40,
                "owner_authorization_verified": True,
                "exact_file_delta_verified": True,
                "required_gates_green": True,
                "deploy_executed": False,
                "worker_activated": False,
                "provider_activated": False,
            },
        ]
        result = evaluate_merge_journal(
            entries,
            expected_sequence_prefix=[1015, 1016],
        )
        self.assertEqual(
            result["state"],
            "MERGE_JOURNAL_PREFIX_VERIFIED",
            result["blockers"],
        )
        self.assertEqual(result["verified_prefix"], [1015, 1016])
        self.assertEqual(result["next_expected_pr"], 1017)
        self.assertFalse(result["merge_authorized"])
        self.assertFalse(result["rollback_authorized"])
        self.assertFalse(result["repository_mutation_performed"])

    def test_merge_journal_detects_unrelated_or_broken_main_chain(self):
        entries = [
            {
                "pr_number": 1015,
                "pre_merge_main_sha": "0" * 40,
                "post_merge_main_sha": "1" * 40,
                "merge_commit_sha": "2" * 40,
                "pre_merge_tree_sha": PINNED_MAIN_TREE_SHA,
                "post_merge_tree_sha": "3" * 40,
                "owner_authorization_verified": True,
                "exact_file_delta_verified": True,
                "required_gates_green": True,
                "deploy_executed": False,
                "worker_activated": False,
                "provider_activated": False,
            }
        ]
        result = evaluate_merge_journal(
            entries,
            expected_sequence_prefix=[1015],
        )
        self.assertEqual(result["state"], "BLOCKED")
        self.assertIn(
            "PR_1015:MAIN_CHAIN_DISCONTINUITY",
            result["blockers"],
        )

    def test_full_recovery_uses_tree_equivalence_not_commit_equality(self):
        result = verify_full_recovery(
            recovery_tree_sha=PINNED_MAIN_TREE_SHA,
            unresolved_revert_conflicts=False,
            all_revert_commits_verified=True,
            quality_gates_green=True,
            full_stack_gate_green_if_applicable=True,
            deploy_executed_during_recovery=False,
            worker_activated_during_recovery=False,
            provider_activated_during_recovery=False,
        )
        self.assertEqual(result["state"], "RECOVERY_TREE_VERIFIED")
        self.assertTrue(result["history_preserved"])
        self.assertFalse(result["anchor_commit_sha_equality_required"])
        self.assertTrue(result["anchor_tree_sha_equality_required"])
        self.assertFalse(result["force_push_used"])
        self.assertFalse(result["remote_reset_used"])
        self.assertFalse(result["recovery_authorized"])
        self.assertFalse(result["executes_action"])

    def test_wrong_recovery_tree_blocks(self):
        result = verify_full_recovery(
            recovery_tree_sha="0" * 40,
            unresolved_revert_conflicts=False,
            all_revert_commits_verified=True,
            quality_gates_green=True,
            full_stack_gate_green_if_applicable=True,
            deploy_executed_during_recovery=False,
            worker_activated_during_recovery=False,
            provider_activated_during_recovery=False,
        )
        self.assertEqual(result["state"], "BLOCKED")
        self.assertIn(
            "RECOVERY_TREE_DOES_NOT_MATCH_ANCHOR",
            result["blockers"],
        )

    def test_policy_forbids_destructive_or_automatic_rollback(self):
        policy = rollback_policy()
        self.assertTrue(policy["preserve_git_history"])
        self.assertFalse(policy["force_push_allowed"])
        self.assertFalse(policy["remote_main_reset_allowed"])
        self.assertFalse(policy["history_rewrite_allowed"])
        self.assertTrue(policy["dependent_children_reverted_before_parent"])
        self.assertTrue(policy["reverse_dependency_order_required"])
        self.assertTrue(
            policy["unrelated_main_drift_requires_human_reconciliation"]
        )
        self.assertTrue(
            policy["rollback_conflict_requires_human_reconciliation"]
        )
        self.assertFalse(policy["automatic_revert_allowed"])
        self.assertFalse(policy["automatic_branch_delete_allowed"])
        self.assertFalse(policy["automatic_deploy_rollback_allowed"])
        self.assertFalse(policy["automatic_production_data_rollback_allowed"])
        self.assertTrue(policy["tree_level_recovery_verification_required"])
        self.assertFalse(
            policy["commit_sha_equality_with_anchor_required"]
        )
        self.assertTrue(policy["quality_gates_after_recovery_required"])
        self.assertFalse(policy["merge_authorized"])
        self.assertFalse(policy["rollback_authorized"])
        self.assertFalse(policy["revert_authorized"])
        self.assertFalse(policy["deploy_authorized"])
        self.assertFalse(policy["repository_mutation_performed"])
        self.assertFalse(policy["external_action_executed"])
        self.assertFalse(policy["executes_action"])


if __name__ == "__main__":
    unittest.main()
