import copy
import unittest

from atlasquant_aion_owner_stack_pre_merge_readiness_v1 import (
    PINNED_MAIN_SHA,
    STACK,
    build_merge_sequence_plan,
    evaluate_pre_merge_readiness,
    pinned_stack_manifest,
    pre_merge_policy,
)


class AionOwnerStackPreMergeReadinessV1Tests(unittest.TestCase):
    def observed_rows(self):
        rows = []
        for item in STACK:
            rows.append(
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
            )
        return rows

    def readiness(self):
        result = evaluate_pre_merge_readiness(
            self.observed_rows(),
            observed_main_sha=PINNED_MAIN_SHA,
        )
        self.assertEqual(
            result["state"],
            "READY_FOR_HUMAN_OWNER_MERGE_SEQUENCE_REVIEW",
            result["blockers"],
        )
        return result

    def test_manifest_pins_linear_stack(self):
        manifest = pinned_stack_manifest()
        self.assertEqual(manifest["stack_size"], 15)
        self.assertEqual(manifest["main_sha"], PINNED_MAIN_SHA)
        self.assertFalse(manifest["merge_authorized"])
        self.assertFalse(manifest["executes_action"])

        rows = manifest["stack"]
        self.assertEqual(rows[0]["number"], 1015)
        self.assertEqual(rows[0]["base"], "main")
        self.assertEqual(rows[-1]["number"], 1029)
        for index in range(1, len(rows)):
            self.assertEqual(rows[index]["base"], rows[index - 1]["head"])
        for row in rows:
            self.assertEqual(len(row["files"]), 4)

    def test_exact_current_snapshot_is_review_ready_not_merge_authorized(self):
        result = self.readiness()
        self.assertEqual(result["stack_size"], 15)
        self.assertTrue(result["snapshot_pinned"])
        self.assertTrue(result["snapshot_invalidated_by_main_change"])
        self.assertTrue(result["snapshot_invalidated_by_pr_head_change"])
        self.assertTrue(result["snapshot_invalidated_by_base_change"])
        self.assertTrue(result["snapshot_invalidated_by_file_delta_change"])
        self.assertTrue(result["snapshot_invalidated_by_gate_regression"])
        self.assertTrue(result["requires_human_owner_review"])
        self.assertFalse(result["merge_authorized"])
        self.assertFalse(result["retarget_authorized"])
        self.assertFalse(result["rebase_authorized"])
        self.assertFalse(result["deploy_authorized"])
        self.assertFalse(result["worker_activation_authorized"])
        self.assertFalse(result["provider_activation_authorized"])
        self.assertFalse(result["external_action_authorized"])
        self.assertFalse(result["merge_executed"])
        self.assertFalse(result["executes_action"])

    def test_main_drift_invalidates_snapshot(self):
        result = evaluate_pre_merge_readiness(
            self.observed_rows(),
            observed_main_sha="0" * 40,
        )
        self.assertEqual(result["state"], "BLOCKED")
        self.assertIn("MAIN_SHA_DRIFT", result["blockers"])

    def test_head_sha_drift_invalidates_one_pr_and_stack(self):
        rows = self.observed_rows()
        rows[7]["head_sha"] = "0" * 40
        result = evaluate_pre_merge_readiness(
            rows,
            observed_main_sha=PINNED_MAIN_SHA,
        )
        self.assertEqual(result["state"], "BLOCKED")
        self.assertIn("PR_1022:HEAD_SHA_DRIFT", result["blockers"])

    def test_base_drift_invalidates_snapshot(self):
        rows = self.observed_rows()
        rows[10]["base"] = "main"
        result = evaluate_pre_merge_readiness(
            rows,
            observed_main_sha=PINNED_MAIN_SHA,
        )
        self.assertEqual(result["state"], "BLOCKED")
        self.assertIn("PR_1025:BASE_DRIFT", result["blockers"])

    def test_file_leak_or_deletion_blocks(self):
        rows = self.observed_rows()
        rows[3]["files"].append(
            {
                "filename": "unexpected.py",
                "status": "added",
                "deletions": 0,
            }
        )
        rows[4]["files"][0]["deletions"] = 1
        result = evaluate_pre_merge_readiness(
            rows,
            observed_main_sha=PINNED_MAIN_SHA,
        )
        self.assertEqual(result["state"], "BLOCKED")
        self.assertIn("PR_1018:FILE_DELTA_DRIFT", result["blockers"])
        self.assertIn("PR_1018:FOUR_FILE_DELTA_REQUIRED", result["blockers"])
        self.assertTrue(
            any(
                item.startswith("PR_1019:DELETION_NOT_ALLOWED:")
                for item in result["blockers"]
            )
        )

    def test_gate_regression_blocks(self):
        rows = self.observed_rows()
        rows[-1]["workflows"][0]["conclusion"] = "failure"
        result = evaluate_pre_merge_readiness(
            rows,
            observed_main_sha=PINNED_MAIN_SHA,
        )
        self.assertEqual(result["state"], "BLOCKED")
        self.assertIn(
            "PR_1029:REQUIRED_WORKFLOW_NOT_GREEN:"
            "AION Owner Stack Integration Certification V1",
            result["blockers"],
        )

    def test_non_draft_pr_blocks_pre_authorization_snapshot(self):
        rows = self.observed_rows()
        rows[0]["draft"] = False
        result = evaluate_pre_merge_readiness(
            rows,
            observed_main_sha=PINNED_MAIN_SHA,
        )
        self.assertEqual(result["state"], "BLOCKED")
        self.assertIn(
            "PR_1015:PR_MUST_REMAIN_DRAFT_BEFORE_OWNER_AUTHORIZATION",
            result["blockers"],
        )

    def test_merge_sequence_is_strict_parent_before_child(self):
        plan = build_merge_sequence_plan(self.readiness())
        self.assertEqual(plan["state"], "MERGE_SEQUENCE_PLAN_READY")
        self.assertEqual(plan["step_count"], 15)
        self.assertEqual(
            plan["merge_strategy"],
            "STRICT_SEQUENTIAL_PARENT_BEFORE_CHILD",
        )
        self.assertTrue(
            plan["squash_merge_permitted_only_with_explicit_owner_authorization"]
        )
        self.assertTrue(
            plan["branch_deletion_should_be_deferred_until_children_are_rebased_or_retargeted"]
        )
        self.assertTrue(
            plan["after_final_pr_merge_main_full_stack_certification_required"]
        )
        self.assertTrue(plan["after_final_pr_merge_post_merge_main_audit_required"])
        self.assertTrue(plan["rollback_plan_required_before_sequence"])
        self.assertFalse(plan["merge_authorized"])
        self.assertFalse(plan["retarget_authorized"])
        self.assertFalse(plan["rebase_authorized"])
        self.assertFalse(plan["branch_delete_authorized"])
        self.assertFalse(plan["deploy_authorized"])
        self.assertFalse(plan["executes_action"])

        first = plan["steps"][0]
        self.assertEqual(first["pr_number"], 1015)
        self.assertFalse(first["previous_step_must_be_confirmed_merged"])
        self.assertFalse(
            first["child_base_must_be_re_evaluated_after_parent_merge"]
        )

        for step in plan["steps"][1:]:
            self.assertTrue(step["previous_step_must_be_confirmed_merged"])
            self.assertTrue(
                step["child_base_must_be_re_evaluated_after_parent_merge"]
            )
            self.assertTrue(
                step["retarget_to_main_only_after_parent_is_confirmed_in_main"]
            )
            self.assertTrue(
                step["post_retarget_diff_must_still_equal_expected_file_delta"]
            )
            self.assertTrue(step["post_retarget_gate_rerun_required"])
            self.assertTrue(step["old_readiness_does_not_carry_across_retarget"])
            self.assertEqual(step["expected_file_count"], 4)
            self.assertFalse(step["deletions_allowed"])
            self.assertTrue(step["stop_on_any_ambiguity"])

    def test_blocked_readiness_cannot_generate_sequence(self):
        blocked = evaluate_pre_merge_readiness(
            [],
            observed_main_sha=PINNED_MAIN_SHA,
        )
        plan = build_merge_sequence_plan(blocked)
        self.assertEqual(plan["state"], "BLOCKED")
        self.assertEqual(plan["steps"], [])
        self.assertFalse(plan["merge_authorized"])
        self.assertFalse(plan["executes_action"])

    def test_policy_forbids_automatic_mutation(self):
        policy = pre_merge_policy()
        self.assertTrue(policy["pinned_main_sha_required"])
        self.assertTrue(policy["exact_linear_stack_required"])
        self.assertTrue(policy["exact_head_sha_required"])
        self.assertTrue(policy["exact_four_file_delta_required"])
        self.assertTrue(policy["zero_deletion_delta_required"])
        self.assertTrue(policy["revalidate_after_each_parent_merge"])
        self.assertTrue(policy["old_readiness_invalid_after_main_change"])
        self.assertTrue(policy["retarget_child_only_after_parent_confirmed_in_main"])
        self.assertTrue(policy["rerun_child_gate_after_retarget"])
        self.assertFalse(policy["delete_parent_branch_before_child_retarget"])
        self.assertTrue(policy["final_full_stack_certification_on_main_required"])
        self.assertTrue(policy["final_post_merge_main_audit_required"])
        self.assertTrue(
            policy["explicit_owner_authorization_required_for_each_mutation"]
        )
        self.assertFalse(policy["automatic_merge_allowed"])
        self.assertFalse(policy["automatic_retarget_allowed"])
        self.assertFalse(policy["automatic_rebase_allowed"])
        self.assertFalse(policy["automatic_branch_delete_allowed"])
        self.assertFalse(policy["automatic_deploy_allowed"])
        self.assertFalse(policy["worker_activation_allowed"])
        self.assertFalse(policy["provider_activation_allowed"])
        self.assertFalse(policy["production_persistence_activation_allowed"])
        self.assertFalse(policy["merge_authorized"])
        self.assertFalse(policy["deploy_authorized"])
        self.assertFalse(policy["merge_executed"])
        self.assertFalse(policy["external_action_executed"])
        self.assertFalse(policy["core_checkpoint_write"])
        self.assertFalse(policy["executes_action"])


if __name__ == "__main__":
    unittest.main()
