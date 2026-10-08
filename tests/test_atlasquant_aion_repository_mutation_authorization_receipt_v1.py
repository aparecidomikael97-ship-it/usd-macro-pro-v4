import copy
import hashlib
import json
import unittest

from atlasquant_aion_owner_stack_pre_merge_readiness_v1 import STACK
from atlasquant_aion_owner_stack_live_merge_step_preflight_challenge_v1 import (
    build_live_merge_step_preflight,
    build_owner_authorization_challenge,
)
from atlasquant_aion_repository_mutation_authorization_receipt_v1 import (
    MAX_DECISION_WINDOW_SECONDS,
    MECHANISM,
    PURPOSE,
    build_authorization_receipt_persistence_attestation,
    build_explicit_owner_mutation_decision,
    build_owner_signature_attestation,
    build_repository_mutation_authorization_receipt,
    repository_mutation_authorization_policy,
    verify_repository_mutation_authorization_receipt,
)


D = lambda c: "sha256:" + (c * 64)
MAIN_SHA = "a" * 40
MAIN_TREE = "b" * 40
CHALLENGE_ISSUED = "2026-10-08T10:00:00+00:00"
CHALLENGE_EXPIRES = "2026-10-08T10:02:00+00:00"
SIGNATURE_AT = "2026-10-08T10:00:15+00:00"
DECISION_ISSUED = "2026-10-08T10:00:20+00:00"
DECISION_EXPIRES = "2026-10-08T10:01:40+00:00"
NOW = "2026-10-08T10:00:30+00:00"
RECEIPT_ISSUED = "2026-10-08T10:00:35+00:00"
RECEIPT_EXPIRES = "2026-10-08T10:01:30+00:00"


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


class AionRepositoryMutationAuthorizationReceiptV1Tests(unittest.TestCase):
    def item(self):
        return next(row for row in STACK if row["number"] == 1015)

    def preflight(self):
        item = self.item()
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
            observed_files=[
                {"filename": path, "status": "added", "deletions": 0}
                for path in item["files"]
            ],
            observed_workflows=[
                {
                    "name": name,
                    "status": "completed",
                    "conclusion": "success",
                }
                for name in item["required_workflows"]
            ],
            parent_confirmed_in_main=False,
            current_readiness_digest=D("1"),
            rollback_plan_digest=D("2"),
        )
        self.assertEqual(result["state"], "LIVE_STEP_PREFLIGHT_READY")
        return result

    def challenge(self, preflight=None):
        result = build_owner_authorization_challenge(
            preflight or self.preflight(),
            challenge_id="challenge-1015-ready-1",
            owner_subject="owner://mikael",
            owner_binding_digest=D("3"),
            nonce_digest=D("4"),
            issued_at=CHALLENGE_ISSUED,
            expires_at=CHALLENGE_EXPIRES,
        )
        self.assertEqual(
            result["state"],
            "OWNER_AUTHORIZATION_CHALLENGE_READY",
            result["blockers"],
        )
        return result

    def signature(self, challenge=None, **changes):
        challenge = challenge or self.challenge()
        kwargs = {
            "challenge": challenge,
            "owner_key_fingerprint": D("5"),
            "signed_challenge_digest": challenge["challenge_digest"],
            "signature_attestation_id": "signature-attestation-1015-1",
            "verified_owner_signature": True,
            "verified_active_trust_root": True,
            "signer_owner_subject_match": True,
            "signer_owner_binding_match": True,
            "persistent_nonce_replay_guard_verified": True,
            "challenge_nonce_single_use_claimed": True,
            "signature_verified_at": SIGNATURE_AT,
        }
        kwargs.update(changes)
        return build_owner_signature_attestation(**kwargs)

    def decision(self, challenge=None, signature=None, decision_name=None, **changes):
        challenge = challenge or self.challenge()
        signature = signature or self.signature(challenge)
        decision_name = decision_name or "AUTHORIZE_REPOSITORY_MUTATION"
        decision_id = "decision-1015-ready-1"
        decision_nonce = D("6")
        decision_material = {
            "decision_id": decision_id,
            "purpose": PURPOSE,
            "decision": decision_name,
            "challenge_digest": challenge["challenge_digest"],
            "signature_attestation_digest": signature[
                "signature_attestation_digest"
            ],
            "pr_number": challenge["pr_number"],
            "requested_mutation": challenge["requested_mutation"],
            "owner_subject": challenge["owner_subject"],
            "owner_binding_digest": challenge["owner_binding_digest"],
            "owner_key_fingerprint": D("5"),
            "decision_nonce_digest": decision_nonce,
            "issued_at": DECISION_ISSUED,
            "expires_at": DECISION_EXPIRES,
        }
        kwargs_base = {
            "challenge": challenge,
            "signature_attestation": signature,
            "decision_id": decision_id,
            "decision": decision_name,
            "signed_decision_digest": digest(decision_material),
            "decision_nonce_digest": decision_nonce,
            "owner_key_fingerprint": D("5"),
            "verified_owner_decision_signature": True,
            "verified_active_trust_root": True,
            "persistent_decision_nonce_replay_guard_verified": True,
            "decision_nonce_single_use_claimed": True,
            "issued_at": DECISION_ISSUED,
            "expires_at": DECISION_EXPIRES,
            "now": NOW,
        }
        kwargs_base.update(changes)
        return build_explicit_owner_mutation_decision(**kwargs_base)

    def receipt(
        self,
        challenge=None,
        signature=None,
        decision=None,
        rebuilt=None,
        **changes,
    ):
        challenge = challenge or self.challenge()
        signature = signature or self.signature(challenge)
        decision = decision or self.decision(challenge, signature)
        rebuilt = rebuilt or self.preflight()
        kwargs = {
            "challenge": challenge,
            "signature_attestation": signature,
            "decision_record": decision,
            "live_rebuilt_preflight": rebuilt,
            "receipt_id": "receipt-1015-ready-1",
            "authorization_nonce_digest": D("7"),
            "persistent_authorization_nonce_replay_guard_verified": True,
            "authorization_nonce_single_use_claimed": True,
            "issued_at": RECEIPT_ISSUED,
            "expires_at": RECEIPT_EXPIRES,
            "now": "2026-10-08T10:00:40+00:00",
        }
        kwargs.update(changes)
        return build_repository_mutation_authorization_receipt(**kwargs)

    def test_owner_signature_attestation_is_not_decision(self):
        challenge = self.challenge()
        signature = self.signature(challenge)
        self.assertEqual(signature["state"], "OWNER_SIGNATURE_ATTESTED")
        self.assertEqual(signature["mechanism"], MECHANISM)
        self.assertFalse(signature["signature_is_decision"])
        self.assertFalse(signature["approval_implied_by_signature"])
        self.assertEqual(signature["mutation_decision"], "UNDECIDED")
        self.assertFalse(signature["repository_mutation_authorized"])
        self.assertFalse(signature["authorization_receipt_created"])
        self.assertFalse(signature["authorization_consumed"])
        self.assertFalse(signature["repository_mutation_performed"])
        self.assertFalse(signature["executes_action"])

    def test_signature_requires_exact_challenge_digest_and_replay_guard(self):
        challenge = self.challenge()
        bad_digest = self.signature(
            challenge,
            signed_challenge_digest=D("0"),
        )
        self.assertEqual(bad_digest["state"], "BLOCKED")
        self.assertIn(
            "SIGNED_CHALLENGE_DIGEST_MISMATCH",
            bad_digest["blockers"],
        )

        no_replay = self.signature(
            challenge,
            persistent_nonce_replay_guard_verified=False,
        )
        self.assertEqual(no_replay["state"], "BLOCKED")
        self.assertIn(
            "PERSISTENT_NONCE_REPLAY_GUARD_REQUIRED",
            no_replay["blockers"],
        )

    def test_explicit_authorize_decision_is_separate_and_verified(self):
        challenge = self.challenge()
        signature = self.signature(challenge)
        decision = self.decision(challenge, signature)
        self.assertEqual(
            decision["state"],
            "OWNER_MUTATION_DECISION_AUTHORIZED",
            decision["blockers"],
        )
        self.assertTrue(decision["explicit_owner_decision_verified"])
        self.assertTrue(
            decision["repository_mutation_authorization_intent"]
        )
        self.assertFalse(decision["repository_mutation_denied"])
        self.assertFalse(decision["decision_is_execution"])
        self.assertFalse(decision["authorization_receipt_created"])
        self.assertFalse(decision["repository_mutation_performed"])

    def test_explicit_deny_decision_cannot_create_authorized_receipt(self):
        challenge = self.challenge()
        signature = self.signature(challenge)
        denied = self.decision(
            challenge,
            signature,
            decision_name="DENY_REPOSITORY_MUTATION",
        )
        self.assertEqual(
            denied["state"],
            "OWNER_MUTATION_DECISION_DENIED",
            denied["blockers"],
        )
        self.assertTrue(denied["repository_mutation_denied"])
        receipt = self.receipt(
            challenge=challenge,
            signature=signature,
            decision=denied,
        )
        self.assertEqual(receipt["state"], "BLOCKED")
        self.assertIn(
            "EXPLICIT_OWNER_AUTHORIZE_DECISION_REQUIRED",
            receipt["blockers"],
        )
        self.assertFalse(receipt["repository_mutation_authorized"])

    def test_authorization_receipt_binds_one_exact_mutation_and_executes_nothing(self):
        receipt = self.receipt()
        self.assertEqual(
            receipt["state"],
            "REPOSITORY_MUTATION_AUTHORIZATION_VERIFIED",
            receipt["blockers"],
        )
        self.assertTrue(receipt["repository_mutation_authorized"])
        self.assertTrue(receipt["authorized_for_exactly_one_mutation"])
        self.assertTrue(receipt["authorization_single_use"])
        self.assertFalse(receipt["authorization_persisted"])
        self.assertFalse(receipt["persistence_attested"])
        self.assertFalse(receipt["authorization_consumed"])
        self.assertFalse(receipt["authorization_reuse_allowed"])
        self.assertFalse(receipt["authorization_scope_expansion_allowed"])
        self.assertFalse(receipt["authorization_pr_change_allowed"])
        self.assertFalse(receipt["authorization_mutation_change_allowed"])
        self.assertFalse(receipt["authorization_head_change_allowed"])
        self.assertFalse(receipt["authorization_main_change_allowed"])
        self.assertFalse(receipt["authorization_base_change_allowed"])
        self.assertTrue(receipt["execution_time_state_rebuild_required"])
        self.assertTrue(
            receipt["execution_time_exact_receipt_match_required"]
        )
        self.assertTrue(receipt["atomic_authorization_consumption_required"])
        self.assertFalse(receipt["repository_mutation_performed"])
        self.assertFalse(receipt["merge_executed"])
        self.assertFalse(receipt["retarget_executed"])
        self.assertFalse(receipt["draft_transition_executed"])
        self.assertFalse(receipt["branch_deleted"])
        self.assertFalse(receipt["deploy_executed"])
        self.assertFalse(receipt["worker_activated"])
        self.assertFalse(receipt["provider_activated"])
        self.assertFalse(receipt["production_persistence_activated"])
        self.assertFalse(receipt["executes_action"])

    def test_live_rebuild_mismatch_blocks_receipt(self):
        rebuilt = self.preflight()
        rebuilt = copy.deepcopy(rebuilt)
        rebuilt["observed_main_sha"] = "0" * 40
        receipt = self.receipt(rebuilt=rebuilt)
        self.assertEqual(receipt["state"], "BLOCKED")
        self.assertIn(
            "LIVE_REBUILD_BINDING_MISMATCH:main_sha",
            receipt["blockers"],
        )
        self.assertFalse(receipt["repository_mutation_authorized"])

    def test_receipt_verifier_detects_tamper_and_expiry(self):
        receipt = self.receipt()
        valid = verify_repository_mutation_authorization_receipt(
            receipt,
            now="2026-10-08T10:00:50+00:00",
        )
        self.assertTrue(valid["valid"], valid["blockers"])
        self.assertTrue(valid["repository_mutation_authorized"])
        self.assertFalse(valid["authorization_consumed"])
        self.assertFalse(valid["repository_mutation_performed"])

        tampered = copy.deepcopy(receipt)
        tampered["head_sha"] = "0" * 40
        invalid = verify_repository_mutation_authorization_receipt(
            tampered,
            now="2026-10-08T10:00:50+00:00",
        )
        self.assertFalse(invalid["valid"])
        self.assertIn(
            "AUTHORIZATION_RECEIPT_DIGEST_MISMATCH",
            invalid["blockers"],
        )

        expired = verify_repository_mutation_authorization_receipt(
            receipt,
            now="2026-10-08T10:01:31+00:00",
        )
        self.assertFalse(expired["valid"])
        self.assertIn(
            "AUTHORIZATION_RECEIPT_EXPIRED",
            expired["blockers"],
        )

    def test_receipt_persistence_attestation_is_external_proof_only(self):
        receipt = self.receipt()
        attestation = build_authorization_receipt_persistence_attestation(
            receipt,
            persisted_record_digest=D("8"),
            writer_attestation_digest=D("9"),
            persisted_at="2026-10-08T10:00:45+00:00",
            read_after_write_verified=True,
            atomic_write_or_cas_verified=True,
            writer_identity_verified=True,
            now="2026-10-08T10:00:50+00:00",
        )
        self.assertEqual(
            attestation["state"],
            "AUTHORIZATION_RECEIPT_PERSISTENCE_ATTESTED",
            attestation["blockers"],
        )
        self.assertFalse(attestation["authorization_persisted_by_this_module"])
        self.assertFalse(attestation["authorization_consumed"])
        self.assertFalse(
            attestation["repository_mutation_authorized_by_this_attestation"]
        )
        self.assertFalse(attestation["repository_mutation_performed"])
        self.assertFalse(attestation["merge_executed"])
        self.assertFalse(attestation["retarget_executed"])
        self.assertFalse(attestation["draft_transition_executed"])
        self.assertFalse(attestation["executes_action"])

    def test_persistence_after_expiry_blocks(self):
        receipt = self.receipt()
        attestation = build_authorization_receipt_persistence_attestation(
            receipt,
            persisted_record_digest=D("8"),
            writer_attestation_digest=D("9"),
            persisted_at="2026-10-08T10:01:31+00:00",
            read_after_write_verified=True,
            atomic_write_or_cas_verified=True,
            writer_identity_verified=True,
            now="2026-10-08T10:01:31+00:00",
        )
        self.assertEqual(attestation["state"], "BLOCKED")
        self.assertIn(
            "RECEIPT_PERSISTED_AFTER_EXPIRY",
            attestation["blockers"],
        )
        self.assertIn(
            "AUTHORIZATION_EXPIRED_AFTER_PERSISTENCE",
            attestation["blockers"],
        )

    def test_decision_and_receipt_windows_are_bounded(self):
        challenge = self.challenge()
        signature = self.signature(challenge)
        too_long = self.decision(
            challenge,
            signature,
            expires_at="2026-10-08T10:02:21+00:00",
        )
        self.assertEqual(too_long["state"], "BLOCKED")
        self.assertIn("DECISION_WINDOW_TOO_LONG", too_long["blockers"])
        self.assertEqual(MAX_DECISION_WINDOW_SECONDS, 120)

        receipt = self.receipt(
            expires_at="2026-10-08T10:02:36+00:00",
        )
        self.assertEqual(receipt["state"], "BLOCKED")
        self.assertIn(
            "AUTHORIZATION_RECEIPT_WINDOW_TOO_LONG",
            receipt["blockers"],
        )

    def test_policy_preserves_signature_decision_execution_separation(self):
        policy = repository_mutation_authorization_policy()
        self.assertEqual(policy["purpose"], PURPOSE)
        self.assertEqual(policy["mechanism"], MECHANISM)
        self.assertTrue(policy["signature_and_decision_are_separate"])
        self.assertFalse(policy["signature_implies_authorization"])
        self.assertFalse(policy["generic_chat_is_signature"])
        self.assertFalse(policy["generic_chat_is_decision"])
        self.assertFalse(policy["generic_chat_is_authorization"])
        self.assertTrue(policy["external_owner_signature_required"])
        self.assertTrue(policy["active_trust_root_required"])
        self.assertTrue(policy["challenge_nonce_replay_guard_required"])
        self.assertTrue(policy["separate_decision_signature_required"])
        self.assertTrue(policy["separate_decision_nonce_required"])
        self.assertTrue(policy["decision_nonce_replay_guard_required"])
        self.assertTrue(policy["live_state_rebuild_required_before_receipt"])
        self.assertTrue(policy["exact_preflight_digest_match_required"])
        self.assertTrue(policy["exact_main_sha_match_required"])
        self.assertTrue(policy["exact_main_tree_sha_match_required"])
        self.assertTrue(policy["exact_head_sha_match_required"])
        self.assertTrue(policy["exact_base_match_required"])
        self.assertTrue(policy["authorization_receipt_single_use"])
        self.assertFalse(policy["authorization_reuse_allowed"])
        self.assertFalse(policy["authorization_scope_expansion_allowed"])
        self.assertFalse(policy["authorization_pr_change_allowed"])
        self.assertFalse(policy["authorization_mutation_change_allowed"])
        self.assertFalse(policy["authorization_head_change_allowed"])
        self.assertFalse(policy["authorization_main_change_allowed"])
        self.assertFalse(policy["authorization_base_change_allowed"])
        self.assertTrue(
            policy["durable_receipt_persistence_required_before_executor"]
        )
        self.assertTrue(policy["read_after_write_required"])
        self.assertTrue(policy["atomic_write_or_cas_required"])
        self.assertTrue(policy["execution_time_state_rebuild_required"])
        self.assertTrue(policy["atomic_authorization_consumption_required"])
        self.assertTrue(policy["receipt_authorization_is_not_execution"])
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
