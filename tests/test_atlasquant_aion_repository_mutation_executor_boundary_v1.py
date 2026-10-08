import hashlib
import json
import unittest

from atlasquant_aion_owner_stack_pre_merge_readiness_v1 import STACK
from atlasquant_aion_owner_stack_live_merge_step_preflight_challenge_v1 import (
    build_live_merge_step_preflight,
    build_owner_authorization_challenge,
)
from atlasquant_aion_repository_mutation_authorization_receipt_v1 import (
    PURPOSE,
    build_authorization_receipt_persistence_attestation,
    build_explicit_owner_mutation_decision,
    build_owner_signature_attestation,
    build_repository_mutation_authorization_receipt,
)
from atlasquant_aion_repository_mutation_executor_boundary_v1 import (
    MAX_EXECUTION_PREFLIGHT_AGE_SECONDS,
    build_atomic_consumption_attestation,
    build_authorization_consumption_candidate,
    build_repository_mutation_executor_boundary,
    repository_mutation_executor_policy,
    verify_executor_boundary,
)

D = lambda c: "sha256:" + (c * 64)
MAIN_SHA = "a" * 40
MAIN_TREE = "b" * 40


def digest(value):
    return "sha256:" + hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
            default=str,
        ).encode("utf-8")
    ).hexdigest()


class AionRepositoryMutationExecutorBoundaryV1Tests(unittest.TestCase):
    def item(self):
        return next(row for row in STACK if row["number"] == 1015)

    def preflight(self):
        item = self.item()
        return build_live_merge_step_preflight(
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
            observed_files=[{"filename": p} for p in item["files"]],
            observed_workflows=[
                {"name": n, "status": "completed", "conclusion": "success"}
                for n in item["required_workflows"]
            ],
            parent_confirmed_in_main=False,
            current_readiness_digest=D("1"),
            rollback_plan_digest=D("2"),
        )

    def receipt_and_persistence(self):
        preflight = self.preflight()
        challenge = build_owner_authorization_challenge(
            preflight,
            challenge_id="challenge-executor-1",
            owner_subject="owner://mikael",
            owner_binding_digest=D("3"),
            nonce_digest=D("4"),
            issued_at="2026-10-08T10:00:00+00:00",
            expires_at="2026-10-08T10:02:00+00:00",
        )
        signature = build_owner_signature_attestation(
            challenge,
            owner_key_fingerprint=D("5"),
            signed_challenge_digest=challenge["challenge_digest"],
            signature_attestation_id="signature-executor-1",
            verified_owner_signature=True,
            verified_active_trust_root=True,
            signer_owner_subject_match=True,
            signer_owner_binding_match=True,
            persistent_nonce_replay_guard_verified=True,
            challenge_nonce_single_use_claimed=True,
            signature_verified_at="2026-10-08T10:00:10+00:00",
        )
        decision_material = {
            "decision_id": "decision-executor-1",
            "purpose": PURPOSE,
            "decision": "AUTHORIZE_REPOSITORY_MUTATION",
            "challenge_digest": challenge["challenge_digest"],
            "signature_attestation_digest": signature[
                "signature_attestation_digest"
            ],
            "pr_number": challenge["pr_number"],
            "requested_mutation": challenge["requested_mutation"],
            "owner_subject": challenge["owner_subject"],
            "owner_binding_digest": challenge["owner_binding_digest"],
            "owner_key_fingerprint": D("5"),
            "decision_nonce_digest": D("6"),
            "issued_at": "2026-10-08T10:00:15+00:00",
            "expires_at": "2026-10-08T10:01:45+00:00",
        }
        decision = build_explicit_owner_mutation_decision(
            challenge,
            signature,
            decision_id="decision-executor-1",
            decision="AUTHORIZE_REPOSITORY_MUTATION",
            signed_decision_digest=digest(decision_material),
            decision_nonce_digest=D("6"),
            owner_key_fingerprint=D("5"),
            verified_owner_decision_signature=True,
            verified_active_trust_root=True,
            persistent_decision_nonce_replay_guard_verified=True,
            decision_nonce_single_use_claimed=True,
            issued_at="2026-10-08T10:00:15+00:00",
            expires_at="2026-10-08T10:01:45+00:00",
            now="2026-10-08T10:00:20+00:00",
        )
        receipt = build_repository_mutation_authorization_receipt(
            challenge,
            signature,
            decision,
            preflight,
            receipt_id="receipt-executor-1",
            authorization_nonce_digest=D("7"),
            persistent_authorization_nonce_replay_guard_verified=True,
            authorization_nonce_single_use_claimed=True,
            issued_at="2026-10-08T10:00:25+00:00",
            expires_at="2026-10-08T10:01:30+00:00",
            now="2026-10-08T10:00:30+00:00",
        )
        persistence = build_authorization_receipt_persistence_attestation(
            receipt,
            persisted_record_digest=D("8"),
            writer_attestation_digest=D("9"),
            persisted_at="2026-10-08T10:00:35+00:00",
            read_after_write_verified=True,
            atomic_write_or_cas_verified=True,
            writer_identity_verified=True,
            now="2026-10-08T10:00:40+00:00",
        )
        self.assertEqual(receipt["state"], "REPOSITORY_MUTATION_AUTHORIZATION_VERIFIED")
        self.assertEqual(
            persistence["state"],
            "AUTHORIZATION_RECEIPT_PERSISTENCE_ATTESTED",
        )
        return preflight, receipt, persistence

    def candidate(self):
        preflight, receipt, persistence = self.receipt_and_persistence()
        candidate = build_authorization_consumption_candidate(
            receipt,
            persistence,
            preflight,
            execution_attempt_id="repo-attempt-1",
            repository_ref_digest=D("a"),
            idempotency_key_digest=D("b"),
            effect_key_digest=D("c"),
            lease_identity_digest=D("d"),
            checked_at="2026-10-08T10:00:45+00:00",
            now="2026-10-08T10:00:50+00:00",
        )
        return preflight, receipt, persistence, candidate

    def consumed(self):
        *_, candidate = self.candidate()
        att = build_atomic_consumption_attestation(
            candidate,
            consumption_record_digest=D("e"),
            writer_attestation_digest=D("f"),
            consumed_at="2026-10-08T10:00:52+00:00",
            atomic_compare_and_set_verified=True,
            read_after_write_verified=True,
            writer_identity_verified=True,
            prior_unconsumed_state_verified=True,
            future_reuse_rejection_verified=True,
        )
        return candidate, att

    def test_candidate_requires_persisted_fresh_exact_authorization(self):
        _, _, _, candidate = self.candidate()
        self.assertEqual(
            candidate["state"],
            "READY_FOR_ATOMIC_AUTHORIZATION_CONSUMPTION",
            candidate["blockers"],
        )
        self.assertEqual(candidate["logical_operation"], "SET_PR_READY_FOR_REVIEW")
        self.assertFalse(candidate["authorization_consumed"])
        self.assertFalse(candidate["authorization_consumed_by_this_module"])
        self.assertFalse(candidate["repository_mutation_request_generated"])
        self.assertFalse(candidate["repository_mutation_authorized_by_candidate"])
        self.assertFalse(candidate["github_api_called"])
        self.assertFalse(candidate["network_called"])
        self.assertFalse(candidate["repository_mutation_performed"])

    def test_state_drift_blocks_candidate(self):
        preflight, receipt, persistence = self.receipt_and_persistence()
        drifted = dict(preflight)
        drifted["observed_head_sha"] = "0" * 40
        candidate = build_authorization_consumption_candidate(
            receipt,
            persistence,
            drifted,
            execution_attempt_id="repo-attempt-drift",
            repository_ref_digest=D("a"),
            idempotency_key_digest=D("b"),
            effect_key_digest=D("c"),
            lease_identity_digest=D("d"),
            checked_at="2026-10-08T10:00:45+00:00",
            now="2026-10-08T10:00:50+00:00",
        )
        self.assertEqual(candidate["state"], "BLOCKED")
        self.assertIn(
            "EXECUTION_TIME_STATE_MISMATCH:head_sha",
            candidate["blockers"],
        )

    def test_stale_execution_preflight_blocks_candidate(self):
        preflight, receipt, persistence = self.receipt_and_persistence()
        candidate = build_authorization_consumption_candidate(
            receipt,
            persistence,
            preflight,
            execution_attempt_id="repo-attempt-stale",
            repository_ref_digest=D("a"),
            idempotency_key_digest=D("b"),
            effect_key_digest=D("c"),
            lease_identity_digest=D("d"),
            checked_at="2026-10-08T10:00:20+00:00",
            now="2026-10-08T10:00:50+00:00",
        )
        self.assertEqual(candidate["state"], "BLOCKED")
        self.assertIn("EXECUTION_PREFLIGHT_STALE", candidate["blockers"])
        self.assertEqual(MAX_EXECUTION_PREFLIGHT_AGE_SECONDS, 15)

    def test_atomic_consumption_requires_cas_and_future_reuse_rejection(self):
        *_, candidate = self.candidate()
        blocked = build_atomic_consumption_attestation(
            candidate,
            consumption_record_digest=D("e"),
            writer_attestation_digest=D("f"),
            consumed_at="2026-10-08T10:00:52+00:00",
            atomic_compare_and_set_verified=False,
            read_after_write_verified=True,
            writer_identity_verified=True,
            prior_unconsumed_state_verified=True,
            future_reuse_rejection_verified=False,
        )
        self.assertEqual(blocked["state"], "BLOCKED")
        self.assertIn("ATOMIC_COMPARE_AND_SET_REQUIRED", blocked["blockers"])
        self.assertIn("FUTURE_REUSE_REJECTION_REQUIRED", blocked["blockers"])

    def test_consumption_after_receipt_expiry_blocks(self):
        *_, candidate = self.candidate()
        blocked = build_atomic_consumption_attestation(
            candidate,
            consumption_record_digest=D("e"),
            writer_attestation_digest=D("f"),
            consumed_at="2026-10-08T10:01:31+00:00",
            atomic_compare_and_set_verified=True,
            read_after_write_verified=True,
            writer_identity_verified=True,
            prior_unconsumed_state_verified=True,
            future_reuse_rejection_verified=True,
        )
        self.assertEqual(blocked["state"], "BLOCKED")
        self.assertIn("AUTHORIZATION_CONSUMED_AFTER_EXPIRY", blocked["blockers"])

    def test_consumption_attestation_is_external_proof_only(self):
        candidate, att = self.consumed()
        self.assertEqual(att["state"], "AUTHORIZATION_CONSUMPTION_ATTESTED")
        self.assertTrue(att["authorization_consumed"])
        self.assertFalse(att["authorization_consumed_by_this_module"])
        self.assertFalse(att["repository_mutation_performed"])
        self.assertFalse(att["github_api_called"])
        self.assertFalse(att["network_called"])

    def test_executor_boundary_ready_but_calls_nothing(self):
        candidate, att = self.consumed()
        boundary = build_repository_mutation_executor_boundary(
            candidate,
            att,
            adapter_manifest_digest=D("1"),
            adapter_build_digest=D("2"),
            signed_adapter_verified=True,
            repository_identity_match=True,
            least_privilege_scope_verified=True,
            target_pr_match=True,
            requested_mutation_match=True,
            main_sha_match=True,
            head_sha_match=True,
            base_branch_match=True,
            file_delta_match=True,
            workflow_snapshot_match=True,
            checked_at="2026-10-08T10:00:55+00:00",
            now="2026-10-08T10:01:00+00:00",
        )
        self.assertEqual(
            boundary["state"],
            "READY_FOR_SINGLE_REPOSITORY_MUTATION_ATTEMPT",
            boundary["blockers"],
        )
        self.assertTrue(boundary["exactly_one_mutation_attempt_allowed"])
        self.assertTrue(boundary["authorization_consumed_before_attempt"])
        self.assertFalse(boundary["repository_switch_allowed"])
        self.assertFalse(boundary["pr_switch_allowed"])
        self.assertFalse(boundary["mutation_switch_allowed"])
        self.assertFalse(boundary["scope_expansion_allowed"])
        self.assertFalse(boundary["api_request_generated"])
        self.assertFalse(boundary["api_method_selected"])
        self.assertFalse(boundary["api_endpoint_included"])
        self.assertFalse(boundary["credential_material_included"])
        self.assertFalse(boundary["github_api_called"])
        self.assertFalse(boundary["network_called"])
        self.assertFalse(boundary["repository_mutation_performed"])
        self.assertTrue(verify_executor_boundary(boundary)["valid"])

    def test_stale_consumption_blocks_executor_boundary(self):
        candidate, att = self.consumed()
        boundary = build_repository_mutation_executor_boundary(
            candidate,
            att,
            adapter_manifest_digest=D("1"),
            adapter_build_digest=D("2"),
            signed_adapter_verified=True,
            repository_identity_match=True,
            least_privilege_scope_verified=True,
            target_pr_match=True,
            requested_mutation_match=True,
            main_sha_match=True,
            head_sha_match=True,
            base_branch_match=True,
            file_delta_match=True,
            workflow_snapshot_match=True,
            checked_at="2026-10-08T10:01:10+00:00",
            now="2026-10-08T10:01:10+00:00",
        )
        self.assertEqual(boundary["state"], "BLOCKED")
        self.assertIn("AUTHORIZATION_CONSUMPTION_STALE", boundary["blockers"])

    def test_boundary_tamper_is_detected(self):
        candidate, att = self.consumed()
        boundary = build_repository_mutation_executor_boundary(
            candidate,
            att,
            adapter_manifest_digest=D("1"),
            adapter_build_digest=D("2"),
            signed_adapter_verified=True,
            repository_identity_match=True,
            least_privilege_scope_verified=True,
            target_pr_match=True,
            requested_mutation_match=True,
            main_sha_match=True,
            head_sha_match=True,
            base_branch_match=True,
            file_delta_match=True,
            workflow_snapshot_match=True,
            checked_at="2026-10-08T10:00:55+00:00",
            now="2026-10-08T10:01:00+00:00",
        )
        tampered = dict(boundary)
        tampered["head_sha"] = "0" * 40
        checked = verify_executor_boundary(tampered)
        self.assertFalse(checked["valid"])
        self.assertIn("EXECUTOR_BOUNDARY_DIGEST_MISMATCH", checked["blockers"])

    def test_policy_is_fail_closed(self):
        policy = repository_mutation_executor_policy()
        self.assertTrue(policy["authorization_receipt_must_be_verified"])
        self.assertTrue(policy["authorization_receipt_must_be_persisted"])
        self.assertTrue(policy["execution_time_live_state_rebuild_required"])
        self.assertTrue(policy["atomic_authorization_consumption_required"])
        self.assertTrue(policy["future_reuse_rejection_required"])
        self.assertTrue(policy["authorization_consumed_before_attempt"])
        self.assertTrue(policy["signed_adapter_required"])
        self.assertTrue(policy["least_privilege_scope_required"])
        self.assertTrue(policy["single_mutation_attempt_only"])
        self.assertFalse(policy["repository_switch_allowed"])
        self.assertFalse(policy["pr_switch_allowed"])
        self.assertFalse(policy["mutation_switch_allowed"])
        self.assertFalse(policy["scope_expansion_allowed"])
        self.assertFalse(policy["raw_api_request_generation_allowed"])
        self.assertFalse(policy["raw_api_endpoint_included"])
        self.assertFalse(policy["credential_material_included"])
        self.assertFalse(policy["github_api_called"])
        self.assertFalse(policy["network_called"])
        self.assertFalse(policy["repository_mutation_performed"])
        self.assertFalse(policy["merge_executed"])
        self.assertFalse(policy["retarget_executed"])
        self.assertFalse(policy["draft_transition_executed"])
        self.assertFalse(policy["branch_deleted"])
        self.assertFalse(policy["deploy_executed"])
        self.assertFalse(policy["worker_activation_allowed"])
        self.assertFalse(policy["provider_activation_allowed"])
        self.assertFalse(policy["production_persistence_activation_allowed"])
        self.assertFalse(policy["external_action_executed"])
        self.assertFalse(policy["executes_action"])


if __name__ == "__main__":
    unittest.main()
