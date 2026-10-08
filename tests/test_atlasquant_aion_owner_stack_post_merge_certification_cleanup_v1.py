import unittest

from atlasquant_aion_owner_stack_post_merge_certification_cleanup_v1 import (
    GOVERNANCE_BRANCHES,
    POST_MERGE_REQUIRED_WORKFLOWS,
    PRODUCT_BRANCHES,
    PRODUCT_FILES,
    PRODUCT_PRS,
    build_branch_cleanup_plan,
    build_post_merge_main_certification,
    post_merge_cleanup_policy,
    verify_branch_cleanup_candidate,
)


D = lambda c: "sha256:" + (c * 64)
MAIN_SHA = "a" * 40
MAIN_TREE = "b" * 40


class AionOwnerStackPostMergeCertificationCleanupV1Tests(unittest.TestCase):
    def workflows(self):
        return [
            {
                "name": name,
                "status": "completed",
                "conclusion": "success",
            }
            for name in POST_MERGE_REQUIRED_WORKFLOWS
        ]

    def certification(self, **changes):
        kwargs = {
            "observed_main_sha": MAIN_SHA,
            "observed_main_tree_sha": MAIN_TREE,
            "merged_pr_numbers": list(PRODUCT_PRS),
            "observed_owner_stack_files": list(PRODUCT_FILES),
            "observed_workflows": self.workflows(),
            "merge_journal_digest": D("1"),
            "rollback_plan_digest": D("2"),
            "full_stack_certification_digest": D("3"),
            "full_stack_certification_on_main": True,
            "all_expected_prs_confirmed_in_main": True,
            "frozen_core_integrity_verified": True,
            "no_unresolved_merge_conflicts": True,
            "no_unexpected_main_drift": True,
            "deploy_executed_during_sequence": False,
            "worker_activated_during_sequence": False,
            "provider_activated_during_sequence": False,
            "production_persistence_activated_during_sequence": False,
        }
        kwargs.update(changes)
        return build_post_merge_main_certification(**kwargs)

    def branch_observations(self):
        return [
            {
                "branch": branch,
                "exists": True,
                "merged_to_main_verified": True,
                "head_evidence_preserved": True,
                "pr_metadata_preserved": True,
                "workflow_evidence_preserved": True,
                "evidence_manifest_digest": D(str((index % 9) + 1)),
                "open_pr_dependents": [],
                "unmerged_commit_count": 0,
                "protected_branch": False,
                "is_default_branch": False,
            }
            for index, branch in enumerate(PRODUCT_BRANCHES)
        ]

    def test_post_merge_main_certification_happy_path(self):
        cert = self.certification()
        self.assertEqual(cert["state"], "POST_MERGE_MAIN_CERTIFIED", cert["blockers"])
        self.assertEqual(cert["merged_prs"], list(PRODUCT_PRS))
        self.assertEqual(len(cert["owner_stack_files"]), 60)
        self.assertTrue(cert["product_stack_closed"])
        self.assertFalse(cert["governance_prs_included_in_product_certification"])
        self.assertTrue(cert["branch_cleanup_may_be_evaluated"])
        self.assertFalse(cert["branch_deletion_authorized"])
        self.assertFalse(cert["deploy_authorized"])
        self.assertFalse(cert["worker_activation_authorized"])
        self.assertFalse(cert["provider_activation_authorized"])
        self.assertFalse(cert["repository_mutation_performed"])
        self.assertFalse(cert["executes_action"])

    def test_missing_product_pr_blocks_certification(self):
        cert = self.certification(merged_pr_numbers=list(PRODUCT_PRS[:-1]))
        self.assertEqual(cert["state"], "BLOCKED")
        self.assertIn("EXACT_PRODUCT_PR_SEQUENCE_REQUIRED", cert["blockers"])

    def test_missing_owner_stack_file_blocks_certification(self):
        cert = self.certification(observed_owner_stack_files=list(PRODUCT_FILES[:-1]))
        self.assertEqual(cert["state"], "BLOCKED")
        self.assertIn("EXACT_OWNER_STACK_FILE_INVENTORY_REQUIRED", cert["blockers"])
        self.assertIn("OWNER_STACK_FILE_COUNT_MUST_BE_60", cert["blockers"])

    def test_post_merge_gate_regression_blocks(self):
        workflows = self.workflows()
        workflows[0]["conclusion"] = "failure"
        cert = self.certification(observed_workflows=workflows)
        self.assertEqual(cert["state"], "BLOCKED")
        self.assertTrue(
            any(
                blocker.startswith("POST_MERGE_WORKFLOW_NOT_GREEN:")
                for blocker in cert["blockers"]
            )
        )

    def test_any_activation_during_merge_sequence_blocks_closure(self):
        cert = self.certification(
            deploy_executed_during_sequence=True,
            worker_activated_during_sequence=True,
            provider_activated_during_sequence=True,
            production_persistence_activated_during_sequence=True,
        )
        self.assertEqual(cert["state"], "BLOCKED")
        self.assertIn("DEPLOY_MUST_REMAIN_FALSE", cert["blockers"])
        self.assertIn("WORKER_MUST_REMAIN_FALSE", cert["blockers"])
        self.assertIn("PROVIDER_ACTIVATION_MUST_REMAIN_FALSE", cert["blockers"])
        self.assertIn(
            "PRODUCTION_PERSISTENCE_ACTIVATION_MUST_REMAIN_FALSE",
            cert["blockers"],
        )

    def test_branch_cleanup_happy_path_is_review_only(self):
        plan = build_branch_cleanup_plan(
            self.certification(),
            self.branch_observations(),
        )
        self.assertEqual(plan["state"], "BRANCH_CLEANUP_PLAN_READY", plan["blockers"])
        self.assertEqual(len(plan["eligible_branches"]), 15)
        self.assertEqual(plan["blocked_branches"], [])
        self.assertEqual(plan["cleanup_order"][0], PRODUCT_BRANCHES[-1])
        self.assertEqual(plan["cleanup_order"][-1], PRODUCT_BRANCHES[0])
        self.assertTrue(plan["child_before_parent_cleanup_order"])
        self.assertTrue(plan["branch_deletion_requires_separate_owner_authorization"])
        self.assertFalse(plan["branch_deletion_authorized"])
        self.assertFalse(plan["branch_deleted"])
        self.assertFalse(plan["repository_mutation_performed"])
        self.assertEqual(
            plan["governance_branches_excluded_from_product_cleanup"],
            list(GOVERNANCE_BRANCHES),
        )
        self.assertTrue(plan["governance_branches_require_separate_disposition"])

    def test_open_meta_pr_dependency_blocks_1029_branch_cleanup(self):
        observations = self.branch_observations()
        target = PRODUCT_BRANCHES[-1]
        for row in observations:
            if row["branch"] == target:
                row["open_pr_dependents"] = ["PR #1030"]
        plan = build_branch_cleanup_plan(self.certification(), observations)
        self.assertEqual(plan["state"], "BRANCH_CLEANUP_PLAN_READY")
        self.assertIn(target, plan["blocked_branches"])
        row = next(item for item in plan["rows"] if item["branch"] == target)
        self.assertEqual(row["state"], "BLOCKED")
        self.assertIn("OPEN_PR_DEPENDENCY_PRESENT", row["blockers"])
        self.assertEqual(row["open_pr_dependents"], ["PR #1030"])

    def test_unmerged_commits_and_protection_block_cleanup(self):
        observations = self.branch_observations()
        observations[0]["unmerged_commit_count"] = 1
        observations[1]["protected_branch"] = True
        observations[2]["is_default_branch"] = True
        plan = build_branch_cleanup_plan(self.certification(), observations)

        first = next(
            row for row in plan["rows"]
            if row["branch"] == observations[0]["branch"]
        )
        second = next(
            row for row in plan["rows"]
            if row["branch"] == observations[1]["branch"]
        )
        third = next(
            row for row in plan["rows"]
            if row["branch"] == observations[2]["branch"]
        )
        self.assertIn("UNMERGED_COMMITS_PRESENT", first["blockers"])
        self.assertIn("PROTECTED_BRANCH_MUST_NOT_BE_DELETED", second["blockers"])
        self.assertIn("DEFAULT_BRANCH_MUST_NOT_BE_DELETED", third["blockers"])

    def test_cleanup_candidate_verifier_never_authorizes_deletion(self):
        plan = build_branch_cleanup_plan(
            self.certification(),
            self.branch_observations(),
        )
        result = verify_branch_cleanup_candidate(
            plan,
            branch=PRODUCT_BRANCHES[-1],
        )
        self.assertTrue(result["valid"])
        self.assertEqual(result["state"], "CLEANUP_CANDIDATE_VALID")
        self.assertTrue(result["owner_authorization_still_required"])
        self.assertFalse(result["branch_deletion_authorized"])
        self.assertFalse(result["branch_deleted"])
        self.assertFalse(result["repository_mutation_performed"])
        self.assertFalse(result["executes_action"])

    def test_blocked_branch_fails_candidate_verification(self):
        observations = self.branch_observations()
        target = PRODUCT_BRANCHES[-1]
        observations[-1]["open_pr_dependents"] = ["PR #1030"]
        plan = build_branch_cleanup_plan(self.certification(), observations)
        result = verify_branch_cleanup_candidate(plan, branch=target)
        self.assertFalse(result["valid"])
        self.assertEqual(result["state"], "BLOCKED")
        self.assertIn("BRANCH_NOT_ELIGIBLE", result["blockers"])
        self.assertIn("OPEN_PR_DEPENDENCY_PRESENT", result["blockers"])

    def test_policy_is_fail_closed(self):
        policy = post_merge_cleanup_policy()
        self.assertEqual(policy["product_branch_count"], 15)
        self.assertEqual(policy["product_file_count"], 60)
        self.assertTrue(
            policy["post_merge_full_stack_certification_on_main_required"]
        )
        self.assertTrue(policy["post_merge_quality_gate_required"])
        self.assertTrue(policy["post_merge_release_readiness_required"])
        self.assertTrue(policy["post_merge_core_certification_required"])
        self.assertTrue(policy["post_merge_core_security_gate_required"])
        self.assertTrue(policy["frozen_core_integrity_required"])
        self.assertTrue(policy["merge_journal_required"])
        self.assertTrue(policy["rollback_plan_digest_required"])
        self.assertTrue(policy["branch_cleanup_only_after_main_certification"])
        self.assertTrue(policy["branch_cleanup_child_before_parent"])
        self.assertTrue(policy["open_pr_dependency_blocks_branch_deletion"])
        self.assertTrue(policy["unmerged_commits_block_branch_deletion"])
        self.assertTrue(
            policy["evidence_preservation_required_before_branch_deletion"]
        )
        self.assertFalse(policy["default_branch_deletion_allowed"])
        self.assertFalse(policy["protected_branch_deletion_allowed"])
        self.assertTrue(policy["governance_branches_require_separate_disposition"])
        self.assertFalse(policy["automatic_branch_deletion_allowed"])
        self.assertTrue(
            policy["branch_deletion_requires_separate_owner_authorization"]
        )
        self.assertFalse(policy["branch_deletion_authorized"])
        self.assertFalse(policy["branch_deleted"])
        self.assertFalse(policy["deploy_authorized"])
        self.assertFalse(policy["worker_activation_authorized"])
        self.assertFalse(policy["provider_activation_authorized"])
        self.assertFalse(policy["production_persistence_activation_authorized"])
        self.assertFalse(policy["repository_mutation_performed"])
        self.assertFalse(policy["external_action_executed"])
        self.assertFalse(policy["executes_action"])


if __name__ == "__main__":
    unittest.main()
