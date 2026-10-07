from __future__ import annotations

import unittest

import atlasquant_aion_b2b_fresh_owner_execution_authorization_contract_v1 as fresh
import atlasquant_aion_b2b_future_executor_boundary_v2 as boundary
import atlasquant_aion_b2b_future_executor_capability_contract_v1 as capability
import atlasquant_aion_b2b_idempotency_replay_contract_v1 as replay
import atlasquant_aion_b2b_owner_renewal_action_adapter_plan_v2 as adapter
import atlasquant_aion_b2b_owner_renewal_action_adapter_receipt_v2 as receipts
import atlasquant_aion_b2b_owner_renewal_action_execution_ceremony as ceremony
import atlasquant_aion_b2b_real_receipt_authenticator_contract_v1 as auth
import atlasquant_aion_b2b_rollback_compensation_contract_v1 as rollback
from test_atlasquant_aion_b2b_owner_renewal_action_adapter_v2 import (
    args_v2,
    receipt_args_v2,
)


def approved_rollback_review():
    plan = adapter.build_owner_renewal_action_adapter_plan_v2(**args_v2())
    receipt = receipts.validate_synthetic_owner_renewal_action_receipt_v2(
        **receipt_args_v2()
    )
    boundary_review = boundary.evaluate_future_executor_boundary(
        adapter_plan_v2=plan,
        synthetic_receipt_validation=receipt,
    )
    capability_review = capability.build_future_executor_capability_contract(
        boundary_review=boundary_review,
    )
    auth_review = auth.build_real_receipt_authenticator_contract(
        capability_review=capability_review,
    )
    replay_review = replay.build_idempotency_replay_contract(
        authenticator_review=auth_review,
    )
    return rollback.build_rollback_compensation_contract(
        idempotency_replay_review=replay_review,
    )


class FreshOwnerExecutionAuthorizationContractV1Tests(unittest.TestCase):
    def assert_no_authority(self, out):
        for key in fresh.FALSE_FIELDS:
            self.assertIs(out[key], False, key)

    def test_approved_rollback_unlocks_design_only(self):
        out = fresh.build_fresh_owner_execution_authorization_contract(
            rollback_compensation_review=approved_rollback_review(),
        )
        self.assertEqual(out["state"], fresh.READY)
        self.assertTrue(out["fresh_owner_authorization_design_only"])
        self.assertTrue(out["reuses_existing_execution_ceremony"])
        self.assertFalse(out["generic_chat_is_authorization"])
        self.assertFalse(out["authorization_reuse_allowed"])
        self.assertEqual(out["next_allowed_step"], fresh.NEXT_ALLOWED_STEP)
        self.assert_no_authority(out)

    def test_existing_execution_ceremony_is_reused_exactly(self):
        out = fresh.build_fresh_owner_execution_authorization_contract(
            rollback_compensation_review=approved_rollback_review(),
        )
        self.assertEqual(out["existing_execution_ceremony_schema"], ceremony.SCHEMA)
        self.assertEqual(out["existing_execution_request_schema"], ceremony.REQUEST_SCHEMA)
        self.assertEqual(out["existing_execution_result_schema"], ceremony.RESULT_SCHEMA)
        self.assertEqual(out["required_purpose"], ceremony.PURPOSE)
        self.assertEqual(out["required_mechanism"], ceremony.MECHANISM)
        self.assertEqual(out["max_authorization_window_seconds"], 120)
        self.assertEqual(out["required_decision"], "AUTHORIZE_BUSINESS_ACTION_EXECUTION")
        self.assert_no_authority(out)

    def test_rollback_review_must_be_exact_ready_state(self):
        row = approved_rollback_review()
        row["state"] = "BLOCKED"
        out = fresh.build_fresh_owner_execution_authorization_contract(
            rollback_compensation_review=row,
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "ROLLBACK_COMPENSATION_DESIGN_REVIEW_REQUIRED",
            out["blockers"],
        )
        self.assert_no_authority(out)

    def test_production_rollback_cannot_be_falsely_promoted(self):
        row = approved_rollback_review()
        row["production_rollback_proven"] = True
        out = fresh.build_fresh_owner_execution_authorization_contract(
            rollback_compensation_review=row,
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("PRODUCTION_ROLLBACK_MUST_REMAIN_UNPROVEN", out["blockers"])
        self.assert_no_authority(out)

    def test_historical_authorization_reuse_is_forbidden(self):
        row = approved_rollback_review()
        row["authorization_reuse_allowed"] = True
        out = fresh.build_fresh_owner_execution_authorization_contract(
            rollback_compensation_review=row,
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("AUTHORIZATION_REUSE_MUST_BE_FORBIDDEN", out["blockers"])
        self.assert_no_authority(out)

    def test_upstream_authority_flip_blocks(self):
        row = approved_rollback_review()
        row["compensation_authorized"] = True
        out = fresh.build_fresh_owner_execution_authorization_contract(
            rollback_compensation_review=row,
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "ROLLBACK_COMPENSATION_UNSAFE_FIELD:compensation_authorized",
            out["blockers"],
        )
        self.assert_no_authority(out)

    def test_proofs_require_signature_nonce_persistence_and_generic_chat_rejection(self):
        out = fresh.build_fresh_owner_execution_authorization_contract(
            rollback_compensation_review=approved_rollback_review(),
        )
        proofs = set(out["required_proofs"])
        self.assertTrue({
            "ED25519_EXTERNAL_OWNER_EXECUTION_SIGNATURE",
            "ACTIVE_TRUST_ROOT_KEY",
            "FRESH_NONCE_REQUIRED",
            "PERSISTENT_NONCE_REPLAY_REJECTION",
            "AUTHORIZATION_WINDOW_MAX_120_SECONDS",
            "EXECUTION_REQUEST_REBUILD_MATCH",
            "EXECUTION_DECISION_AUTHORIZE_EXPLICIT",
            "EXECUTION_RECORD_PERSISTENCE_REQUIRED",
            "EXECUTION_PERSISTENCE_ATTESTATION_REQUIRED",
            "EXECUTION_WRITER_ATTESTATION_REQUIRED",
            "GENERIC_CHAT_REJECTED_AS_EXECUTION",
            "AUTHORIZATION_SINGLE_USE",
        }.issubset(proofs))
        self.assert_no_authority(out)

    def test_contract_does_not_verify_or_persist_any_authorization(self):
        out = fresh.build_fresh_owner_execution_authorization_contract(
            rollback_compensation_review=approved_rollback_review(),
        )
        for key in (
            "execution_request_issued",
            "owner_execution_identity_verified",
            "owner_execution_signature_verified",
            "execution_decision_verified",
            "execution_authorization_intent_verified",
            "nonce_claimed",
            "nonce_registry_written",
            "execution_record_created",
            "execution_record_persisted",
            "persistence_attested",
            "writer_attested",
            "fresh_execution_authorization_verified",
        ):
            self.assertFalse(out[key], key)
        self.assert_no_authority(out)

    def test_generic_chat_never_becomes_execution_authority(self):
        out = fresh.build_fresh_owner_execution_authorization_contract(
            rollback_compensation_review=approved_rollback_review(),
        )
        self.assertFalse(out["generic_chat_is_authorization"])
        self.assertFalse(out["generic_chat_instruction_accepted_as_execution"])
        self.assertFalse(out["business_action_authorized"])
        self.assertFalse(out["executes_action"])
        self.assert_no_authority(out)

    def test_next_step_is_runtime_guards_design_only(self):
        out = fresh.build_fresh_owner_execution_authorization_contract(
            rollback_compensation_review=approved_rollback_review(),
        )
        self.assertEqual(
            out["next_allowed_step"],
            "DESIGN_RUNTIME_EXECUTION_GUARDS_CONTRACT_ONLY",
        )
        self.assertFalse(out["executor_implementation_allowed"])
        self.assertFalse(out["production_mutation_authorized"])
        self.assert_no_authority(out)


if __name__ == "__main__":
    unittest.main()
