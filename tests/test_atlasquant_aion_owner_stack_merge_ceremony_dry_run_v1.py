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
)
from atlasquant_aion_owner_stack_merge_ceremony_dry_run_v1 import (
    dry_run_policy,
    simulate_merge_ceremony,
    simulate_rollback_ceremony,
)


class AionOwnerStackMergeCeremonyDryRunV1Tests(unittest.TestCase):
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
                    {
                        "filename": path,
                        "status": "added",
                        "deletions": 0,
                    }
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

    def upstream(self):
        readiness = evaluate_pre_merge_readiness(
            self.observed_rows(),
            observed_main_sha=PINNED_MAIN_SHA,
        )
        self.assertEqual(
            readiness["state"],
            "READY_FOR_HUMAN_OWNER_MERGE_SEQUENCE_REVIEW",
            readiness["blockers"],
        )
        sequence = build_merge_sequence_plan(readiness)
        self.assertEqual(sequence["state"], "MERGE_SEQUENCE_PLAN_READY")

        rollback = build_rollback_recovery_plan(
            readiness,
            sequence,
            observed_anchor_main_sha=PINNED_MAIN_SHA,
            observed_anchor_tree_sha=PINNED_MAIN_TREE_SHA,
        )
        self.assertEqual(
            rollback["state"],
            "READY_FOR_HUMAN_OWNER_ROLLBACK_PLAN_REVIEW",
            rollback["blockers"],
        )
        return readiness, sequence, rollback

    def test_full_merge_ceremony_dry_run_completes_all_15_steps(self):
        readiness, sequence, rollback = self.upstream()
        result = simulate_merge_ceremony(readiness, sequence, rollback)
        self.assertEqual(result["state"], "DRY_RUN_SEQUENCE_COMPLETED")
        self.assertEqual(result["completed_count"], 15)
        self.assertEqual(result["completed_prs"], list(range(1015, 1030)))
        self.assertIsNone(result["stop_pr"])
        self.assertNotEqual(result["final_virtual_main_sha"], PINNED_MAIN_SHA)
        self.assertNotEqual(result["final_virtual_tree_sha"], PINNED_MAIN_TREE_SHA)
        self.assertTrue(result["synthetic_only"])
        self.assertTrue(result["virtual_shas_are_not_git_objects"])
        self.assertFalse(result["real_owner_authorization_used"])
        self.assertFalse(result["repository_mutation_performed"])
        self.assertFalse(result["actual_merge_executed"])
        self.assertFalse(result["actual_retarget_executed"])
        self.assertFalse(result["actual_rebase_executed"])
        self.assertFalse(result["actual_revert_executed"])
        self.assertFalse(result["merge_authorized"])
        self.assertFalse(result["executes_action"])

    def test_every_child_simulates_retarget_and_fresh_revalidation(self):
        readiness, sequence, rollback = self.upstream()
        result = simulate_merge_ceremony(readiness, sequence, rollback)
        first = result["steps"][0]
        self.assertFalse(first["child_retarget_required"])
        self.assertFalse(first["retarget_simulated"])

        for step in result["steps"][1:]:
            self.assertTrue(step["child_retarget_required"])
            self.assertTrue(step["retarget_simulated"])
            self.assertEqual(step["retarget_target"], "main")
            self.assertFalse(step["actual_retarget_performed"])
            self.assertFalse(step["actual_rebase_performed"])
            self.assertTrue(step["post_retarget_diff_exact"])
            self.assertTrue(step["post_retarget_gate_green"])
            self.assertFalse(
                step["old_readiness_reused_after_virtual_base_change"]
            )
            self.assertTrue(step["fresh_virtual_revalidation_performed"])

    def test_gate_failure_stops_exactly_at_failed_pr(self):
        readiness, sequence, rollback = self.upstream()
        result = simulate_merge_ceremony(
            readiness,
            sequence,
            rollback,
            injected_faults={1022: ["GATE_FAILURE"]},
        )
        self.assertEqual(result["state"], "DRY_RUN_STOP_CONDITION_VERIFIED")
        self.assertEqual(result["stop_pr"], 1022)
        self.assertEqual(result["completed_prs"], list(range(1015, 1022)))
        self.assertEqual(result["steps"][-1]["pr_number"], 1022)
        self.assertIn("GATE_FAILURE", result["steps"][-1]["blockers"])
        self.assertFalse(result["steps"][-1]["merge_simulated"])
        self.assertFalse(result["repository_mutation_performed"])

    def test_post_retarget_diff_drift_stops_child(self):
        readiness, sequence, rollback = self.upstream()
        result = simulate_merge_ceremony(
            readiness,
            sequence,
            rollback,
            injected_faults={1025: ["POST_RETARGET_DIFF_DRIFT"]},
        )
        self.assertEqual(result["stop_pr"], 1025)
        self.assertIn(
            "POST_RETARGET_DIFF_DRIFT",
            result["steps"][-1]["blockers"],
        )
        self.assertFalse(result["steps"][-1]["post_retarget_diff_exact"])
        self.assertFalse(result["steps"][-1]["actual_retarget_performed"])

    def test_main_drift_and_missing_owner_authorization_are_hard_stops(self):
        readiness, sequence, rollback = self.upstream()
        drift = simulate_merge_ceremony(
            readiness,
            sequence,
            rollback,
            injected_faults={1018: ["MAIN_DRIFT"]},
        )
        self.assertEqual(drift["stop_pr"], 1018)
        self.assertIn("MAIN_DRIFT", drift["steps"][-1]["blockers"])

        auth = simulate_merge_ceremony(
            readiness,
            sequence,
            rollback,
            injected_faults={1016: ["OWNER_AUTHORIZATION_MISSING"]},
        )
        self.assertEqual(auth["stop_pr"], 1016)
        self.assertIn(
            "OWNER_AUTHORIZATION_MISSING",
            auth["steps"][-1]["blockers"],
        )
        self.assertFalse(
            auth["steps"][-1]["synthetic_owner_authorization_simulated"]
        )

    def test_unexpected_activation_or_deploy_stops(self):
        readiness, sequence, rollback = self.upstream()
        result = simulate_merge_ceremony(
            readiness,
            sequence,
            rollback,
            injected_faults={
                1027: [
                    "UNEXPECTED_DEPLOY",
                    "UNEXPECTED_WORKER_ACTIVATION",
                    "UNEXPECTED_PROVIDER_ACTIVATION",
                ]
            },
        )
        self.assertEqual(result["stop_pr"], 1027)
        self.assertIn("UNEXPECTED_DEPLOY", result["steps"][-1]["blockers"])
        self.assertIn(
            "UNEXPECTED_WORKER_ACTIVATION",
            result["steps"][-1]["blockers"],
        )
        self.assertIn(
            "UNEXPECTED_PROVIDER_ACTIVATION",
            result["steps"][-1]["blockers"],
        )

    def test_full_rollback_dry_run_reverts_all_in_reverse_order(self):
        result = simulate_rollback_ceremony(
            list(range(1015, 1030)),
            failure_at_pr=1015,
        )
        self.assertEqual(result["state"], "FULL_ROLLBACK_DRY_RUN_COMPLETED")
        self.assertEqual(
            result["revert_pr_order"],
            list(reversed(range(1015, 1030))),
        )
        self.assertEqual(result["remaining_prs"], [])
        self.assertEqual(
            result["virtual_recovery_tree_sha"],
            PINNED_MAIN_TREE_SHA,
        )
        self.assertTrue(result["anchor_tree_match_simulated"])
        self.assertTrue(result["history_preserved_simulated"])
        self.assertFalse(result["actual_revert_executed"])
        self.assertFalse(result["force_push_used"])
        self.assertFalse(result["remote_reset_used"])
        self.assertFalse(result["history_rewrite_used"])
        self.assertFalse(result["repository_mutation_performed"])
        self.assertFalse(result["revert_authorized"])

    def test_partial_rollback_removes_failed_pr_and_descendants_only(self):
        result = simulate_rollback_ceremony(
            list(range(1015, 1030)),
            failure_at_pr=1024,
        )
        self.assertEqual(
            result["state"],
            "PARTIAL_ROLLBACK_DRY_RUN_COMPLETED",
        )
        self.assertEqual(
            result["revert_pr_order"],
            list(reversed(range(1024, 1030))),
        )
        self.assertEqual(result["remaining_prs"], list(range(1015, 1024)))
        self.assertFalse(result["anchor_tree_match_simulated"])
        self.assertNotEqual(
            result["virtual_recovery_tree_sha"],
            PINNED_MAIN_TREE_SHA,
        )

    def test_noncanonical_merged_sequence_blocks_rollback_simulation(self):
        result = simulate_rollback_ceremony(
            [1015, 1017, 1016],
            failure_at_pr=1016,
        )
        self.assertEqual(result["state"], "BLOCKED")
        self.assertIn(
            "MERGED_SEQUENCE_NOT_PARENT_BEFORE_CHILD",
            result["blockers"],
        )
        self.assertEqual(result["virtual_revert_steps"], [])
        self.assertFalse(result["actual_revert_executed"])

    def test_invalid_upstream_blocks_dry_run(self):
        result = simulate_merge_ceremony({}, {}, {})
        self.assertEqual(result["state"], "BLOCKED")
        self.assertEqual(result["steps"], [])
        self.assertFalse(result["repository_mutation_performed"])
        self.assertFalse(result["merge_authorized"])

    def test_policy_is_strictly_synthetic_and_non_mutating(self):
        policy = dry_run_policy()
        self.assertTrue(policy["strict_parent_before_child_simulated"])
        self.assertTrue(policy["main_advance_simulated_per_step"])
        self.assertTrue(policy["child_retarget_simulated_after_parent"])
        self.assertTrue(policy["fresh_revalidation_simulated_after_base_change"])
        self.assertFalse(
            policy["old_readiness_reuse_after_base_change_allowed"]
        )
        self.assertTrue(policy["exact_file_delta_rechecked_per_step"])
        self.assertTrue(policy["zero_deletion_rechecked_per_step"])
        self.assertTrue(policy["gate_rerun_rechecked_per_step"])
        self.assertTrue(policy["stop_on_main_drift"])
        self.assertTrue(policy["stop_on_head_drift"])
        self.assertTrue(policy["stop_on_base_drift"])
        self.assertTrue(policy["stop_on_file_delta_drift"])
        self.assertTrue(policy["stop_on_gate_failure"])
        self.assertTrue(policy["stop_on_missing_owner_authorization"])
        self.assertTrue(policy["stop_on_retarget_conflict"])
        self.assertTrue(policy["stop_on_merge_conflict"])
        self.assertTrue(policy["rollback_reverse_dependency_order_simulated"])
        self.assertTrue(policy["virtual_shas_are_not_git_objects"])
        self.assertTrue(
            policy["synthetic_owner_authorization_is_not_real_authorization"]
        )
        self.assertFalse(policy["repository_mutation_performed"])
        self.assertFalse(policy["actual_merge_executed"])
        self.assertFalse(policy["actual_retarget_executed"])
        self.assertFalse(policy["actual_rebase_executed"])
        self.assertFalse(policy["actual_revert_executed"])
        self.assertFalse(policy["merge_authorized"])
        self.assertFalse(policy["retarget_authorized"])
        self.assertFalse(policy["rebase_authorized"])
        self.assertFalse(policy["revert_authorized"])
        self.assertFalse(policy["deploy_authorized"])
        self.assertFalse(policy["worker_activation_authorized"])
        self.assertFalse(policy["provider_activation_authorized"])
        self.assertFalse(policy["external_action_executed"])
        self.assertFalse(policy["executes_action"])


if __name__ == "__main__":
    unittest.main()
