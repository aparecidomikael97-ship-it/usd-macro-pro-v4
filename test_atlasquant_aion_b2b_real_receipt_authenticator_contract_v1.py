from __future__ import annotations

import unittest

import atlasquant_aion_b2b_future_executor_boundary_v2 as boundary
import atlasquant_aion_b2b_future_executor_capability_contract_v1 as capability
import atlasquant_aion_b2b_owner_renewal_action_adapter_plan_v2 as adapter
import atlasquant_aion_b2b_owner_renewal_action_adapter_receipt_v2 as receipts
import atlasquant_aion_b2b_real_receipt_authenticator_contract_v1 as auth
from test_atlasquant_aion_b2b_owner_renewal_action_adapter_v2 import (
    args_v2,
    receipt_args_v2,
)


def approved_capability_review():
    plan = adapter.build_owner_renewal_action_adapter_plan_v2(**args_v2())
    receipt = receipts.validate_synthetic_owner_renewal_action_receipt_v2(
        **receipt_args_v2()
    )
    boundary_review = boundary.evaluate_future_executor_boundary(
        adapter_plan_v2=plan,
        synthetic_receipt_validation=receipt,
    )
    return capability.build_future_executor_capability_contract(
        boundary_review=boundary_review,
    )


class RealReceiptAuthenticatorContractV1Tests(unittest.TestCase):
    def assert_no_authority(self, out):
        for key in auth.FALSE_FIELDS:
            self.assertIs(out[key], False, key)

    def test_approved_capability_unlocks_authenticator_design_only(self):
        out = auth.build_real_receipt_authenticator_contract(
            capability_review=approved_capability_review(),
        )
        self.assertEqual(out["state"], auth.READY)
        self.assertTrue(out["authenticator_design_only"])
        self.assertTrue(out["provider_neutral"])
        self.assertEqual(out["signature_algorithm_required"], "ED25519")
        self.assertEqual(out["digest_algorithm_required"], "SHA256")
        self.assertTrue(out["trust_root_required"])
        self.assertTrue(out["persistent_nonce_registry_required"])
        self.assertTrue(out["replay_rejection_required"])
        self.assertEqual(out["next_allowed_step"], auth.NEXT_ALLOWED_STEP)
        self.assert_no_authority(out)

    def test_capability_state_must_be_exact_ready_state(self):
        row = approved_capability_review()
        row["state"] = "BLOCKED"
        out = auth.build_real_receipt_authenticator_contract(
            capability_review=row,
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("CAPABILITY_DESIGN_REVIEW_REQUIRED", out["blockers"])
        self.assert_no_authority(out)

    def test_historical_authorization_reuse_is_forbidden(self):
        row = approved_capability_review()
        row["authorization_reuse_allowed"] = True
        out = auth.build_real_receipt_authenticator_contract(
            capability_review=row,
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("AUTHORIZATION_REUSE_MUST_BE_FORBIDDEN", out["blockers"])
        self.assert_no_authority(out)

    def test_capability_authority_flip_blocks(self):
        row = approved_capability_review()
        row["provider_selected"] = True
        out = auth.build_real_receipt_authenticator_contract(
            capability_review=row,
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("CAPABILITY_UNSAFE_FIELD:provider_selected", out["blockers"])
        self.assert_no_authority(out)

    def test_required_signed_bindings_cover_scope_and_execution_chain(self):
        out = auth.build_real_receipt_authenticator_contract(
            capability_review=approved_capability_review(),
        )
        required = set(out["required_signed_bindings"])
        self.assertTrue({
            "owner_id", "tenant_id", "workspace_id",
            "customer_id", "pilot_id", "package",
            "action_family", "operation_kind",
            "execution_request_digest", "execution_record_digest",
            "execution_intent_writer_request_digest",
            "command_plan_digest", "adapter_plan_digest", "dry_run_digest",
            "rollback_plan_digest", "idempotency_key_digest",
            "before_state_digest", "after_state_digest",
            "provider_identity_ref", "writer_identity_ref",
            "issued_at", "expires_at", "nonce", "key_id", "key_version",
        }.issubset(required))
        self.assert_no_authority(out)

    def test_verifier_proofs_require_crypto_lifecycle_freshness_and_replay(self):
        out = auth.build_real_receipt_authenticator_contract(
            capability_review=approved_capability_review(),
        )
        proofs = set(out["required_verifier_proofs"])
        self.assertTrue({
            "ED25519_SIGNATURE_VALID",
            "TRUST_ROOT_KEY_RESOLUTION",
            "KEY_STATUS_ACTIVE",
            "KEY_VERSION_MATCH",
            "KEY_NOT_BEFORE_SATISFIED",
            "KEY_NOT_AFTER_SATISFIED",
            "RECEIPT_FRESHNESS_VALID",
            "NONCE_NOT_PREVIOUSLY_CONSUMED",
            "TENANT_SCOPE_BINDING_VALID",
            "PROVIDER_IDENTITY_BINDING_VALID",
        }.issubset(proofs))
        self.assert_no_authority(out)

    def test_contract_contains_no_real_key_or_provider_material(self):
        out = auth.build_real_receipt_authenticator_contract(
            capability_review=approved_capability_review(),
        )
        text = repr(out)
        for marker in (
            "BEGIN PRIVATE KEY",
            "Bearer ",
            "sk-",
            "http://",
            "https://",
            "Authorization:",
            "curl ",
            "powershell ",
        ):
            self.assertNotIn(marker, text)
        self.assertFalse(out["key_material_loaded"])
        self.assertFalse(out["private_key_loaded"])
        self.assertFalse(out["trust_root_read_performed"])
        self.assertFalse(out["nonce_claimed"])
        self.assertFalse(out["replay_registry_written"])
        self.assert_no_authority(out)

    def test_next_step_is_idempotency_replay_design_only(self):
        out = auth.build_real_receipt_authenticator_contract(
            capability_review=approved_capability_review(),
        )
        self.assertEqual(
            out["next_allowed_step"],
            "DESIGN_IDEMPOTENCY_REPLAY_CONTRACT_ONLY",
        )
        self.assertFalse(out["real_receipt_verified"])
        self.assertFalse(out["signature_verified"])
        self.assertFalse(out["executor_implementation_allowed"])
        self.assert_no_authority(out)


if __name__ == "__main__":
    unittest.main()
