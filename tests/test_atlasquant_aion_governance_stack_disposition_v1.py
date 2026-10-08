import unittest

from atlasquant_aion_governance_stack_disposition_v1 import (
    ACTIVE_REFERENCE_PRS,
    CLOSE_UNMERGED_PRS,
    FROZEN_HISTORICAL_PRS,
    GOVERNANCE_STACK,
    PRODUCT_STACK_PRS,
    build_governance_disposition_plan,
    evaluate_governance_disposition_readiness,
    governance_disposition_policy,
    governance_retention_policy,
)


class AionGovernanceStackDispositionV1Tests(unittest.TestCase):
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
                "changed_files": 4,
                "deletions": 0,
                "workflows": [
                    {
                        "name": item["required_workflow"],
                        "status": "completed",
                        "conclusion": "success",
                    }
                ],
            }
            for item in GOVERNANCE_STACK
        ]

    def readiness(self, **changes):
        kwargs = {
            "observed_prs": self.observed_rows(),
            "product_stack_post_merge_certified": True,
            "product_stack_prs_confirmed_in_main": list(PRODUCT_STACK_PRS),
            "product_stack_full_gate_green_on_main": True,
            "frozen_core_integrity_verified": True,
            "deploy_remained_disabled": True,
            "worker_remained_disabled": True,
            "provider_activation_remained_disabled": True,
            "production_persistence_remained_disabled": True,
        }
        kwargs.update(changes)
        result = evaluate_governance_disposition_readiness(**kwargs)
        return result

    def test_classification_is_exact(self):
        self.assertEqual(FROZEN_HISTORICAL_PRS, (1030, 1032))
        self.assertEqual(ACTIVE_REFERENCE_PRS, (1031, 1033, 1034))
        self.assertEqual(CLOSE_UNMERGED_PRS, ())
        self.assertEqual(
            [item["number"] for item in GOVERNANCE_STACK],
            [1030, 1031, 1032, 1033, 1034],
        )
        self.assertEqual(
            GOVERNANCE_STACK[0]["disposition"],
            "MERGE_REQUIRED_FROZEN_HISTORICAL_EVIDENCE",
        )
        self.assertEqual(
            GOVERNANCE_STACK[1]["disposition"],
            "MERGE_REQUIRED_ACTIVE_GOVERNANCE_REFERENCE",
        )

    def test_happy_path_ready_for_owner_disposition_review_only(self):
        result = self.readiness()
        self.assertEqual(
            result["state"],
            "READY_FOR_HUMAN_OWNER_GOVERNANCE_DISPOSITION_REVIEW",
            result["blockers"],
        )
        self.assertEqual(result["frozen_historical_prs"], [1030, 1032])
        self.assertEqual(result["active_reference_prs"], [1031, 1033, 1034])
        self.assertEqual(result["close_unmerged_prs"], [])
        self.assertTrue(result["all_five_current_prs_required"])
        self.assertFalse(result["skip_middle_pr_allowed"])
        self.assertFalse(result["close_current_governance_pr_unmerged_allowed"])
        self.assertTrue(
            result["replacement_or_consolidation_requires_separate_design"]
        )
        self.assertFalse(result["governance_merge_authorized"])
        self.assertFalse(result["pr_close_authorized"])
        self.assertFalse(result["retarget_authorized"])
        self.assertFalse(result["rebase_authorized"])
        self.assertFalse(result["branch_delete_authorized"])
        self.assertFalse(result["deploy_authorized"])
        self.assertFalse(result["repository_mutation_performed"])
        self.assertFalse(result["executes_action"])

    def test_product_stack_must_be_certified_first(self):
        result = self.readiness(product_stack_post_merge_certified=False)
        self.assertEqual(result["state"], "BLOCKED")
        self.assertIn(
            "PRODUCT_STACK_POST_MERGE_CERTIFICATION_REQUIRED",
            result["blockers"],
        )

    def test_exact_product_stack_confirmation_required(self):
        result = self.readiness(
            product_stack_prs_confirmed_in_main=list(PRODUCT_STACK_PRS[:-1]),
        )
        self.assertEqual(result["state"], "BLOCKED")
        self.assertIn(
            "EXACT_PRODUCT_STACK_CONFIRMATION_REQUIRED",
            result["blockers"],
        )

    def test_governance_head_or_base_drift_blocks(self):
        rows = self.observed_rows()
        rows[2]["head_sha"] = "0" * 40
        rows[3]["base"] = "main"
        result = self.readiness(observed_prs=rows)
        self.assertEqual(result["state"], "BLOCKED")
        self.assertIn("PR_1032:HEAD_SHA_DRIFT", result["blockers"])
        self.assertIn("PR_1033:BASE_DRIFT", result["blockers"])

    def test_governance_gate_regression_blocks(self):
        rows = self.observed_rows()
        rows[-1]["workflows"][0]["conclusion"] = "failure"
        result = self.readiness(observed_prs=rows)
        self.assertEqual(result["state"], "BLOCKED")
        self.assertTrue(
            any(
                blocker.startswith(
                    "PR_1034:REQUIRED_WORKFLOW_NOT_GREEN:"
                )
                for blocker in result["blockers"]
            )
        )

    def test_non_draft_or_deletion_blocks(self):
        rows = self.observed_rows()
        rows[0]["draft"] = False
        rows[1]["deletions"] = 1
        result = self.readiness(observed_prs=rows)
        self.assertEqual(result["state"], "BLOCKED")
        self.assertIn(
            "PR_1030:PR_MUST_REMAIN_DRAFT_BEFORE_DISPOSITION_AUTHORIZATION",
            result["blockers"],
        )
        self.assertIn("PR_1031:ZERO_DELETIONS_REQUIRED", result["blockers"])

    def test_activation_regression_blocks_governance_disposition(self):
        result = self.readiness(
            deploy_remained_disabled=False,
            worker_remained_disabled=False,
            provider_activation_remained_disabled=False,
            production_persistence_remained_disabled=False,
        )
        self.assertEqual(result["state"], "BLOCKED")
        self.assertIn("DEPLOY_MUST_REMAIN_DISABLED", result["blockers"])
        self.assertIn("WORKER_MUST_REMAIN_DISABLED", result["blockers"])
        self.assertIn(
            "PROVIDER_ACTIVATION_MUST_REMAIN_DISABLED",
            result["blockers"],
        )
        self.assertIn(
            "PRODUCTION_PERSISTENCE_MUST_REMAIN_DISABLED",
            result["blockers"],
        )

    def test_plan_is_strict_1030_through_1034(self):
        plan = build_governance_disposition_plan(self.readiness())
        self.assertEqual(plan["state"], "GOVERNANCE_DISPOSITION_PLAN_READY")
        self.assertEqual(plan["merge_order"], [1030, 1031, 1032, 1033, 1034])
        self.assertEqual(plan["step_count"], 5)
        self.assertTrue(plan["strict_order_required"])
        self.assertFalse(plan["skip_step_allowed"])
        self.assertFalse(plan["close_unmerged_allowed"])
        self.assertTrue(
            plan["all_five_merged_before_governance_branch_cleanup"]
        )
        self.assertTrue(plan["post_merge_retention_policy_required"])
        self.assertFalse(plan["governance_merge_authorized"])
        self.assertFalse(plan["pr_close_authorized"])
        self.assertFalse(plan["retarget_authorized"])
        self.assertFalse(plan["rebase_authorized"])
        self.assertFalse(plan["branch_delete_authorized"])
        self.assertFalse(plan["deploy_authorized"])
        self.assertFalse(plan["repository_mutation_performed"])
        self.assertFalse(plan["executes_action"])

        for step in plan["steps"]:
            self.assertTrue(step["product_stack_must_already_be_certified"])
            self.assertTrue(step["parent_must_be_confirmed_in_main"])
            self.assertTrue(step["live_main_refetch_required"])
            self.assertTrue(step["separate_owner_authorization_required"])
            self.assertTrue(step["draft_to_ready_requires_separate_authorization"])
            self.assertTrue(
                step["retarget_or_rebase_requires_separate_authorization"]
            )
            self.assertTrue(step["merge_requires_separate_authorization"])
            self.assertTrue(
                step["exact_four_file_delta_required_after_base_change"]
            )
            self.assertTrue(step["zero_deletions_required_after_base_change"])
            self.assertTrue(step["dedicated_gate_rerun_required"])
            self.assertTrue(step["stop_on_any_drift_or_ambiguity"])
            self.assertTrue(step["deploy_forbidden"])
            self.assertTrue(step["worker_activation_forbidden"])
            self.assertTrue(step["provider_activation_forbidden"])
            self.assertTrue(
                step["production_persistence_activation_forbidden"]
            )

    def test_blocked_readiness_cannot_create_plan(self):
        plan = build_governance_disposition_plan(
            self.readiness(product_stack_post_merge_certified=False)
        )
        self.assertEqual(plan["state"], "BLOCKED")
        self.assertEqual(plan["steps"], [])
        self.assertFalse(plan["governance_merge_authorized"])
        self.assertFalse(plan["executes_action"])

    def test_retention_policy_preserves_history_and_active_references(self):
        policy = governance_retention_policy()
        self.assertEqual(policy["frozen_historical_prs"], [1030, 1032])
        self.assertEqual(policy["active_reference_prs"], [1031, 1033, 1034])
        self.assertEqual(policy["close_unmerged_prs"], [])
        self.assertEqual(
            policy["pr_1030_role"],
            "FROZEN_HISTORICAL_REFERENCE",
        )
        self.assertEqual(
            policy["pr_1031_role"],
            "MAINTAINED_GOVERNANCE_REFERENCE",
        )
        self.assertEqual(
            policy["pr_1032_role"],
            "FROZEN_HISTORICAL_REFERENCE",
        )
        self.assertTrue(policy["historical_v1_files_remain_in_main_after_merge"])
        self.assertTrue(
            policy["historical_v1_files_should_not_be_rewritten_to_fake_current_state"]
        )
        self.assertTrue(
            policy["active_reference_v1_can_be_superseded_by_new_version"]
        )
        self.assertTrue(policy["superseding_version_must_not_destroy_v1_evidence"])
        self.assertTrue(
            policy["consolidated_replacement_is_future_separate_design"]
        )
        self.assertFalse(
            policy["current_stack_can_be_closed_unmerged_after_consolidation"]
        )
        self.assertTrue(policy["governance_pr_metadata_should_be_preserved"])
        self.assertTrue(policy["workflow_evidence_should_be_preserved"])
        self.assertTrue(policy["head_sha_evidence_should_be_preserved"])
        self.assertTrue(policy["merge_journal_should_reference_governance_prs"])
        self.assertTrue(policy["branch_cleanup_only_after_all_dependents_resolved"])
        self.assertTrue(policy["governance_branch_cleanup_child_before_parent"])
        self.assertFalse(policy["automatic_branch_deletion_allowed"])
        self.assertFalse(policy["branch_delete_authorized"])
        self.assertFalse(policy["repository_mutation_performed"])
        self.assertFalse(policy["executes_action"])

    def test_policy_forbids_skips_and_automatic_mutation(self):
        policy = governance_disposition_policy()
        self.assertTrue(
            policy["product_stack_must_be_certified_before_governance_merge"]
        )
        self.assertEqual(policy["governance_prs"], [1030, 1031, 1032, 1033, 1034])
        self.assertTrue(policy["strict_governance_order_required"])
        self.assertTrue(policy["all_five_current_governance_prs_required"])
        self.assertFalse(policy["skip_middle_pr_allowed"])
        self.assertFalse(policy["close_current_governance_pr_unmerged_allowed"])
        self.assertTrue(
            policy["replacement_or_consolidation_requires_separate_design"]
        )
        self.assertTrue(policy["historical_evidence_preserved_in_main"])
        self.assertTrue(
            policy["historical_evidence_must_not_be_rewritten_as_current"]
        )
        self.assertTrue(policy["active_reference_may_be_superseded_not_erased"])
        self.assertTrue(policy["governance_merge_requires_live_revalidation"])
        self.assertTrue(
            policy["governance_merge_requires_separate_owner_authorization_per_mutation"]
        )
        self.assertTrue(
            policy["governance_gate_rerun_after_base_change_required"]
        )
        self.assertTrue(
            policy["governance_branch_cleanup_after_all_dependencies_resolved"]
        )
        self.assertFalse(policy["automatic_merge_allowed"])
        self.assertFalse(policy["automatic_close_allowed"])
        self.assertFalse(policy["automatic_retarget_allowed"])
        self.assertFalse(policy["automatic_rebase_allowed"])
        self.assertFalse(policy["automatic_branch_delete_allowed"])
        self.assertFalse(policy["automatic_deploy_allowed"])
        self.assertFalse(policy["worker_activation_allowed"])
        self.assertFalse(policy["provider_activation_allowed"])
        self.assertFalse(policy["production_persistence_activation_allowed"])
        self.assertFalse(policy["governance_merge_authorized"])
        self.assertFalse(policy["pr_close_authorized"])
        self.assertFalse(policy["branch_delete_authorized"])
        self.assertFalse(policy["deploy_authorized"])
        self.assertFalse(policy["repository_mutation_performed"])
        self.assertFalse(policy["external_action_executed"])
        self.assertFalse(policy["executes_action"])


if __name__ == "__main__":
    unittest.main()
