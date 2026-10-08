import copy
import unittest

from atlasquant_aion_owner_stack_pre_merge_readiness_v1 import STACK
from atlasquant_aion_owner_stack_live_merge_step_preflight_challenge_v1 import (
    MAX_CHALLENGE_WINDOW_SECONDS,
    build_live_merge_step_preflight,
    build_owner_authorization_challenge,
    live_merge_step_policy,
    verify_owner_authorization_challenge,
)


D = lambda c: "sha256:" + (c * 64)
MAIN_SHA = "a" * 40
MAIN_TREE = "b" * 40
ISSUED = "2026-10-08T10:00:00+00:00"
EXPIRES = "2026-10-08T10:01:00+00:00"
NOW = "2026-10-08T10:00:30+00:00"


class AionOwnerStackLiveMergeStepPreflightChallengeV1Tests(unittest.TestCase):
    def item(self, number):
        return next(row for row in STACK if row["number"] == number)

    def workflows(self, item):
        return [
            {
                "name": name,
                "status": "completed",
                "conclusion": "success",
            }
            for name in item["required_workflows"]
        ]

    def files(self, item):
        return [
            {
                "filename": path,
                "status": "added",
                "deletions": 0,
            }
            for path in item["files"]
        ]

    def root_ready_preflight(self):
        item = self.item(1015)
        result = build_live_merge_step_preflight(
            pr_number=1015,
            requested_mutation="PR_DRAFT_TO_READY",
            observed_main_sha=MAIN_SHA,
            observed_main_tree_sha=MAIN_TREE,
            observed_pr_state="open",
            observed_draft=True,
            observed_mergeable=True,
            observed_base="main",
            observed_head=item["head"],
            observed_head_sha=item["head_sha"],
            observed_files=self.files(item),
            observed_workflows=self.workflows(item),
            parent_confirmed_in_main=False,
            current_readiness_digest=D("1"),
            rollback_plan_digest=D("2"),
        )
        self.assertEqual(result["state"], "LIVE_STEP_PREFLIGHT_READY")
        return result

    def challenge(self, preflight=None, **changes):
        preflight = preflight or self.root_ready_preflight()
        kwargs = {
            "preflight": preflight,
            "challenge_id": "merge-challenge-1015-ready-1",
            "owner_subject": "owner://mikael",
            "owner_binding_digest": D("3"),
            "nonce_digest": D("4"),
            "issued_at": ISSUED,
            "expires_at": EXPIRES,
        }
        kwargs.update(changes)
        return build_owner_authorization_challenge(**kwargs)

    def test_root_draft_to_ready_preflight_is_ready_but_non_mutating(self):
        preflight = self.root_ready_preflight()
        self.assertEqual(preflight["requested_mutation"], "PR_DRAFT_TO_READY")
        self.assertTrue(
            preflight["live_state_revalidation_required_immediately_before_mutation"]
        )
        self.assertTrue(preflight["owner_authorization_challenge_required"])
        self.assertFalse(preflight["generic_chat_is_authorization"])
        self.assertFalse(preflight["real_owner_signature_verified"])
        self.assertFalse(preflight["authorization_granted"])
        self.assertFalse(preflight["repository_mutation_authorized"])
        self.assertFalse(preflight["repository_mutation_performed"])
        self.assertFalse(preflight["draft_transition_executed"])
        self.assertFalse(preflight["executes_action"])

    def test_child_retarget_requires_parent_and_ready_state(self):
        item = self.item(1016)
        ready = build_live_merge_step_preflight(
            pr_number=1016,
            requested_mutation="PR_RETARGET_TO_MAIN",
            observed_main_sha=MAIN_SHA,
            observed_main_tree_sha=MAIN_TREE,
            observed_pr_state="open",
            observed_draft=False,
            observed_mergeable=True,
            observed_base=item["base"],
            observed_head=item["head"],
            observed_head_sha=item["head_sha"],
            observed_files=self.files(item),
            observed_workflows=self.workflows(item),
            parent_confirmed_in_main=True,
            current_readiness_digest=D("1"),
            rollback_plan_digest=D("2"),
        )
        self.assertEqual(ready["state"], "LIVE_STEP_PREFLIGHT_READY")

        blocked = build_live_merge_step_preflight(
            pr_number=1016,
            requested_mutation="PR_RETARGET_TO_MAIN",
            observed_main_sha=MAIN_SHA,
            observed_main_tree_sha=MAIN_TREE,
            observed_pr_state="open",
            observed_draft=False,
            observed_mergeable=True,
            observed_base=item["base"],
            observed_head=item["head"],
            observed_head_sha=item["head_sha"],
            observed_files=self.files(item),
            observed_workflows=self.workflows(item),
            parent_confirmed_in_main=False,
            current_readiness_digest=D("1"),
            rollback_plan_digest=D("2"),
        )
        self.assertEqual(blocked["state"], "BLOCKED")
        self.assertIn("PARENT_CONFIRMATION_REQUIRED", blocked["blockers"])

    def test_merge_preflight_requires_base_main_and_pr_not_draft(self):
        item = self.item(1016)
        ready = build_live_merge_step_preflight(
            pr_number=1016,
            requested_mutation="SQUASH_MERGE_TO_MAIN",
            observed_main_sha=MAIN_SHA,
            observed_main_tree_sha=MAIN_TREE,
            observed_pr_state="open",
            observed_draft=False,
            observed_mergeable=True,
            observed_base="main",
            observed_head=item["head"],
            observed_head_sha=item["head_sha"],
            observed_files=self.files(item),
            observed_workflows=self.workflows(item),
            parent_confirmed_in_main=True,
            current_readiness_digest=D("1"),
            rollback_plan_digest=D("2"),
        )
        self.assertEqual(ready["state"], "LIVE_STEP_PREFLIGHT_READY")

        blocked = build_live_merge_step_preflight(
            pr_number=1016,
            requested_mutation="SQUASH_MERGE_TO_MAIN",
            observed_main_sha=MAIN_SHA,
            observed_main_tree_sha=MAIN_TREE,
            observed_pr_state="open",
            observed_draft=True,
            observed_mergeable=True,
            observed_base=item["base"],
            observed_head=item["head"],
            observed_head_sha=item["head_sha"],
            observed_files=self.files(item),
            observed_workflows=self.workflows(item),
            parent_confirmed_in_main=True,
            current_readiness_digest=D("1"),
            rollback_plan_digest=D("2"),
        )
        self.assertEqual(blocked["state"], "BLOCKED")
        self.assertIn("PR_MUST_BE_READY_BEFORE_MERGE", blocked["blockers"])
        self.assertIn("MERGE_BASE_MUST_BE_MAIN", blocked["blockers"])

    def test_preflight_blocks_head_file_and_gate_drift(self):
        item = self.item(1029)
        workflows = self.workflows(item)
        workflows[0]["conclusion"] = "failure"
        files = self.files(item) + [{"filename": "unexpected.py"}]
        result = build_live_merge_step_preflight(
            pr_number=1029,
            requested_mutation="SQUASH_MERGE_TO_MAIN",
            observed_main_sha=MAIN_SHA,
            observed_main_tree_sha=MAIN_TREE,
            observed_pr_state="open",
            observed_draft=False,
            observed_mergeable=True,
            observed_base="main",
            observed_head=item["head"],
            observed_head_sha="0" * 40,
            observed_files=files,
            observed_workflows=workflows,
            parent_confirmed_in_main=True,
            current_readiness_digest=D("1"),
            rollback_plan_digest=D("2"),
        )
        self.assertEqual(result["state"], "BLOCKED")
        self.assertIn("HEAD_SHA_MISMATCH", result["blockers"])
        self.assertIn("EXACT_FILE_DELTA_REQUIRED", result["blockers"])
        self.assertIn("FOUR_FILE_DELTA_REQUIRED", result["blockers"])
        self.assertTrue(
            any(
                blocker.startswith("REQUIRED_WORKFLOW_NOT_GREEN:")
                for blocker in result["blockers"]
            )
        )

    def test_challenge_binds_exact_live_state_and_is_not_authorization(self):
        challenge = self.challenge()
        self.assertEqual(
            challenge["state"],
            "OWNER_AUTHORIZATION_CHALLENGE_READY",
            challenge["blockers"],
        )
        self.assertEqual(challenge["pr_number"], 1015)
        self.assertEqual(challenge["requested_mutation"], "PR_DRAFT_TO_READY")
        self.assertIn("AUTHORIZE PR_DRAFT_TO_READY PR #1015", challenge["confirmation_text"])
        self.assertFalse(challenge["challenge_is_authorization"])
        self.assertFalse(challenge["generic_chat_is_authorization"])
        self.assertFalse(challenge["chat_acknowledgement_accepted_as_signature"])
        self.assertTrue(challenge["owner_signature_required"])
        self.assertTrue(challenge["external_signature_verification_required"])
        self.assertTrue(challenge["persistent_nonce_replay_rejection_required"])
        self.assertTrue(challenge["single_use_authorization_required"])
        self.assertTrue(challenge["state_rebuild_match_required_at_execution_time"])
        self.assertFalse(challenge["real_owner_signature_verified"])
        self.assertFalse(challenge["authorization_granted"])
        self.assertFalse(challenge["repository_mutation_authorized"])
        self.assertFalse(challenge["repository_mutation_performed"])
        self.assertFalse(challenge["draft_transition_executed"])
        self.assertFalse(challenge["executes_action"])

    def test_challenge_window_cannot_exceed_120_seconds(self):
        challenge = self.challenge(
            expires_at="2026-10-08T10:02:01+00:00",
        )
        self.assertEqual(challenge["state"], "BLOCKED")
        self.assertIn("CHALLENGE_WINDOW_TOO_LONG", challenge["blockers"])
        self.assertEqual(MAX_CHALLENGE_WINDOW_SECONDS, 120)

    def test_challenge_verifier_detects_tampering_and_expiry(self):
        challenge = self.challenge()
        valid = verify_owner_authorization_challenge(
            challenge,
            now=NOW,
        )
        self.assertTrue(valid["valid"])
        self.assertFalse(valid["signature_verified"])
        self.assertFalse(valid["authorization_granted"])
        self.assertFalse(valid["repository_mutation_authorized"])
        self.assertFalse(valid["repository_mutation_performed"])

        tampered = copy.deepcopy(challenge)
        tampered["head_sha"] = "0" * 40
        invalid = verify_owner_authorization_challenge(
            tampered,
            now=NOW,
        )
        self.assertFalse(invalid["valid"])
        self.assertIn("CHALLENGE_DIGEST_MISMATCH", invalid["blockers"])

        expired = verify_owner_authorization_challenge(
            challenge,
            now="2026-10-08T10:01:01+00:00",
        )
        self.assertFalse(expired["valid"])
        self.assertIn("CHALLENGE_EXPIRED", expired["blockers"])

    def test_blocked_preflight_cannot_build_ready_challenge(self):
        blocked = dict(self.root_ready_preflight())
        blocked["state"] = "BLOCKED"
        blocked["blockers"] = ["SYNTHETIC_BLOCKER"]
        challenge = self.challenge(preflight=blocked)
        self.assertEqual(challenge["state"], "BLOCKED")
        self.assertIn("LIVE_STEP_PREFLIGHT_REQUIRED", challenge["blockers"])

    def test_each_mutation_requires_distinct_challenge_material(self):
        root = self.root_ready_preflight()
        c1 = self.challenge(root)

        merge_item = self.item(1015)
        merge_preflight = build_live_merge_step_preflight(
            pr_number=1015,
            requested_mutation="SQUASH_MERGE_TO_MAIN",
            observed_main_sha=MAIN_SHA,
            observed_main_tree_sha=MAIN_TREE,
            observed_pr_state="open",
            observed_draft=False,
            observed_mergeable=True,
            observed_base="main",
            observed_head=merge_item["head"],
            observed_head_sha=merge_item["head_sha"],
            observed_files=self.files(merge_item),
            observed_workflows=self.workflows(merge_item),
            parent_confirmed_in_main=False,
            current_readiness_digest=D("1"),
            rollback_plan_digest=D("2"),
        )
        c2 = build_owner_authorization_challenge(
            merge_preflight,
            challenge_id="merge-challenge-1015-merge-1",
            owner_subject="owner://mikael",
            owner_binding_digest=D("3"),
            nonce_digest=D("5"),
            issued_at=ISSUED,
            expires_at=EXPIRES,
        )
        self.assertEqual(c2["state"], "OWNER_AUTHORIZATION_CHALLENGE_READY")
        self.assertNotEqual(c1["challenge_digest"], c2["challenge_digest"])
        self.assertNotEqual(c1["nonce_digest"], c2["nonce_digest"])
        self.assertNotEqual(c1["confirmation_text"], c2["confirmation_text"])

    def test_policy_keeps_all_repository_mutations_separate_and_manual(self):
        policy = live_merge_step_policy()
        self.assertEqual(
            policy["supported_mutations"],
            ["PR_DRAFT_TO_READY", "PR_RETARGET_TO_MAIN", "SQUASH_MERGE_TO_MAIN"],
        )
        self.assertTrue(policy["live_main_sha_required"])
        self.assertTrue(policy["live_main_tree_sha_required"])
        self.assertTrue(policy["exact_head_sha_required"])
        self.assertTrue(policy["exact_four_file_delta_required"])
        self.assertTrue(policy["required_gates_green_required"])
        self.assertTrue(policy["parent_confirmation_required_for_children"])
        self.assertTrue(policy["draft_to_ready_is_separate_mutation"])
        self.assertTrue(policy["retarget_to_main_is_separate_mutation"])
        self.assertTrue(policy["squash_merge_is_separate_mutation"])
        self.assertFalse(policy["authorization_reuse_across_mutations_allowed"])
        self.assertFalse(policy["authorization_reuse_across_prs_allowed"])
        self.assertEqual(policy["challenge_window_max_seconds"], 120)
        self.assertFalse(policy["generic_chat_is_authorization"])
        self.assertFalse(policy["chat_acknowledgement_accepted_as_signature"])
        self.assertTrue(policy["owner_signature_required"])
        self.assertTrue(policy["external_signature_verification_required"])
        self.assertTrue(policy["persistent_nonce_replay_rejection_required"])
        self.assertTrue(policy["single_use_authorization_required"])
        self.assertTrue(policy["state_rebuild_match_required_at_execution_time"])
        self.assertFalse(policy["challenge_is_authorization"])
        self.assertFalse(policy["authorization_granted"])
        self.assertFalse(policy["repository_mutation_authorized"])
        self.assertFalse(policy["repository_mutation_performed"])
        self.assertFalse(policy["automatic_draft_transition_allowed"])
        self.assertFalse(policy["automatic_retarget_allowed"])
        self.assertFalse(policy["automatic_rebase_allowed"])
        self.assertFalse(policy["automatic_merge_allowed"])
        self.assertFalse(policy["automatic_branch_delete_allowed"])
        self.assertFalse(policy["automatic_deploy_allowed"])
        self.assertFalse(policy["worker_activation_allowed"])
        self.assertFalse(policy["provider_activation_allowed"])
        self.assertFalse(policy["merge_executed"])
        self.assertFalse(policy["retarget_executed"])
        self.assertFalse(policy["draft_transition_executed"])
        self.assertFalse(policy["deploy_executed"])
        self.assertFalse(policy["external_action_executed"])
        self.assertFalse(policy["executes_action"])


if __name__ == "__main__":
    unittest.main()
