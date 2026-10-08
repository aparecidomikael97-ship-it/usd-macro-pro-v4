"""Adversarial architecture checks only; no real enrollment or Windows mutation."""
from __future__ import annotations

import json
import unittest

from atlasquant_aion_windows_host_anchor_readonly_inventory_v1 import (
    _blocked as absent_anchor,
    CANDIDATE as ANCHOR_SHAPE_CANDIDATE,
)
from atlasquant_aion_windows_crypto_provider_enrollment_compatibility_v1 import (
    SCHEMA, PURPOSE, DESIGN_REVIEW,
    evaluate_windows_collector_root_crypto_architecture,
)

def canonical(record):
    return json.dumps(record, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("utf-8")


class CryptoCompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.anchor = absent_anchor("HOST_ANCHOR_ABSENT")

    def design(self, mode="EXTERNAL_INDEPENDENT_ED25519_CUSTODY"):
        result = {
            "schema": SCHEMA,
            "purpose": PURPOSE,
            "proposed_mode": mode,
            "collector_signature_algorithm": "ED25519",
            "owner_signature_algorithm": "ED25519",
            "collector_key_source": "EXTERNAL_SEPARATE_KEY_CUSTODIAN_PROPOSED",
            "host_binding_key_algorithm": "NONE",
            "windows_key_provider": "NONE",
            "tpm_ed25519_capability": "UNVERIFIED",
            "cross_algorithm_bridge_state": "NOT_APPLICABLE",
            "private_key_provisioning_state": "NOT_PROVISIONED",
            "trusted_policy_anchor_state": "NOT_PROVISIONED",
            "owner_approval_state": "NOT_REQUESTED",
            "physical_key_attestation_state": "NOT_COLLECTED",
            "owner_witness_separation": "REQUIRED_NOT_PHYSICALLY_VERIFIED",
            "rollback_protection_state": "NOT_VERIFIED",
            "review_nonce": "ab" * 32,
        }
        if mode == "TPM_P256_HOST_BINDING_WITH_ED25519_COLLECTOR":
            result.update(
                collector_key_source="EXTERNAL_ED25519_KEY_UNPROVISIONED",
                host_binding_key_algorithm="ECDSA_P256",
                windows_key_provider="Microsoft Platform Crypto Provider",
                cross_algorithm_bridge_state="NOT_IMPLEMENTED",
            )
        return result

    def run_review(self, record=None, anchor=None):
        if record is None:
            record = self.design()
        if anchor is None:
            anchor = self.anchor
        return evaluate_windows_collector_root_crypto_architecture(
            canonical(record), anchor)

    def permanent_denials(self, result):
        for field in (
            "ed25519_tpm_direct_support_verified",
            "hardware_protected_collector_private_key_verified",
            "host_cng_key_provider_verified",
            "cross_algorithm_bridge_implemented",
            "anchor_independently_protected",
            "owner_approval_authenticated",
            "witness_independence_verified",
            "rollback_protection_verified",
            "physical_12_requirements_verified",
            "network_16_surfaces_verified",
            "collector_key_enrolled",
            "installer_authorized", "build_authorized",
            "deploy_authorized", "safe_to_resume",
            "host_security_state_modified", "private_key_created",
        ):
            self.assertIs(result[field], False, field)

    def test_external_ed25519_review_never_enrolls(self):
        result = self.run_review()
        self.assertEqual(result["state"], DESIGN_REVIEW)
        self.assertTrue(result["design_contract_structurally_consistent"])
        self.assertIn("HOST_ANCHOR_ABSENT_MUST_REMAIN_BLOCKED", result["unresolved_gates"])
        self.permanent_denials(result)

    def test_tpm_p256_bridge_review_never_claims_implemented(self):
        result = self.run_review(
            self.design("TPM_P256_HOST_BINDING_WITH_ED25519_COLLECTOR"))
        self.assertEqual(result["state"], DESIGN_REVIEW)
        self.assertIn("DEVELOP_AND_AUDIT_CROSS_ALGORITHM_CHALLENGE_BINDING",
                      result["unresolved_gates"])
        self.permanent_denials(result)

    def test_direct_tpm_ed25519_is_never_assumed(self):
        record = self.design("DIRECT_TPM_ED25519_UNVERIFIED")
        result = self.run_review(record)
        self.assertEqual(result["reason"], "DIRECT_TPM_ED25519_SUPPORT_NOT_ESTABLISHED")
        self.permanent_denials(result)

    def test_silent_switch_from_ed25519_owner_to_ecdsa_rejected(self):
        record = self.design()
        record["owner_signature_algorithm"] = "ECDSA_P256"
        self.assertEqual(self.run_review(record)["reason"],
                         "ED25519_CONTRACT_WOULD_BE_SILENTLY_CHANGED")

    def test_silent_switch_collector_to_ecdsa_rejected(self):
        record = self.design()
        record["collector_signature_algorithm"] = "ECDSA_P256"
        self.assertEqual(self.run_review(record)["reason"],
                         "ED25519_CONTRACT_WOULD_BE_SILENTLY_CHANGED")

    def test_unknown_mode_denied(self):
        record = self.design("UNREVIEWED_MODE")
        self.assertEqual(self.run_review(record)["reason"],
                         "CRYPTO_CUSTODY_MODE_UNKNOWN")

    def test_faked_tpm_ed25519_supported_denied(self):
        record = self.design()
        record["tpm_ed25519_capability"] = "VERIFIED"
        self.assertEqual(self.run_review(record)["reason"],
                         "UNSUPPORTED_REAL_WORLD_AUTHORITY_CLAIM")

    def test_faked_owner_approval_denied(self):
        record = self.design()
        record["owner_approval_state"] = "SIGNED"
        self.assertEqual(self.run_review(record)["reason"],
                         "UNSUPPORTED_REAL_WORLD_AUTHORITY_CLAIM")

    def test_faked_key_provisioning_denied(self):
        record = self.design()
        record["private_key_provisioning_state"] = "ENROLLED"
        self.assertEqual(self.run_review(record)["reason"],
                         "UNSUPPORTED_REAL_WORLD_AUTHORITY_CLAIM")

    def test_faked_physical_key_attestation_denied(self):
        record = self.design()
        record["physical_key_attestation_state"] = "PASSED"
        self.assertEqual(self.run_review(record)["reason"],
                         "UNSUPPORTED_REAL_WORLD_AUTHORITY_CLAIM")

    def test_faked_antirollback_denied(self):
        record = self.design()
        record["rollback_protection_state"] = "VERIFIED"
        self.assertEqual(self.run_review(record)["reason"],
                         "UNSUPPORTED_REAL_WORLD_AUTHORITY_CLAIM")

    def test_external_custodian_cannot_claim_platform_ksp(self):
        record = self.design()
        record["windows_key_provider"] = "Microsoft Platform Crypto Provider"
        self.assertEqual(self.run_review(record)["reason"],
                         "EXTERNAL_ED25519_ARCHITECTURE_INCONSISTENT")

    def test_tpm_bridge_cannot_claim_implemented(self):
        record = self.design("TPM_P256_HOST_BINDING_WITH_ED25519_COLLECTOR")
        record["cross_algorithm_bridge_state"] = "IMPLEMENTED"
        self.assertEqual(self.run_review(record)["reason"],
                         "TPM_P256_ED25519_BRIDGE_ARCHITECTURE_INCONSISTENT")

    def test_tpm_bridge_needs_explicit_ecdsa_p256(self):
        record = self.design("TPM_P256_HOST_BINDING_WITH_ED25519_COLLECTOR")
        record["host_binding_key_algorithm"] = "ED25519"
        self.assertEqual(self.run_review(record)["reason"],
                         "TPM_P256_ED25519_BRIDGE_ARCHITECTURE_INCONSISTENT")

    def test_absent_anchor_cannot_be_self_promoted(self):
        fake = absent_anchor("HOST_ANCHOR_ABSENT")
        fake["host_anchor_is_protected"] = True
        self.assertEqual(self.run_review(anchor=fake)["reason"],
                         "ANCHOR_OBSERVATION_UNTRUSTED_AUTHORITY_CLAIM")

    def test_absent_anchor_cannot_inject_install_permission(self):
        fake = absent_anchor("HOST_ANCHOR_ABSENT")
        fake["installer_authorized"] = True
        self.assertEqual(self.run_review(anchor=fake)["reason"],
                         "ANCHOR_OBSERVATION_UNTRUSTED_AUTHORITY_CLAIM")

    def test_absent_anchor_cannot_claim_write(self):
        fake = absent_anchor("HOST_ANCHOR_ABSENT")
        fake["system_registry_modified"] = True
        self.assertEqual(self.run_review(anchor=fake)["reason"],
                         "ANCHOR_OBSERVATION_UNTRUSTED_AUTHORITY_CLAIM")

    def test_no_unrelated_error_may_be_treated_as_absent(self):
        fake = absent_anchor("HOST_ANCHOR_READ_DENIED")
        self.assertEqual(self.run_review(anchor=fake)["reason"],
                         "ANCHOR_OBSERVATION_BLOCKED_UNEXPECTED_REASON")

    def test_malformed_anchor_observation_rejected(self):
        for fake in (None, [], {}, {"schema":"fake","state":"BLOCKED"}):
            with self.subTest(fake=fake):
                self.assertEqual(self.run_review(anchor=fake or {})["state"], "BLOCKED")

    def test_syntax_valid_shape_still_untrusted(self):
        fake = absent_anchor("")
        fake["state"] = ANCHOR_SHAPE_CANDIDATE
        fake["anchor_schema_and_types_valid"] = True
        result = self.run_review(anchor=fake)
        self.assertEqual(result["state"], DESIGN_REVIEW)
        self.assertIn("HKLM_FORMAT_ALONE_NOT_TRUSTED", result["unresolved_gates"])
        self.permanent_denials(result)

    def test_fake_shape_without_types_rejected(self):
        fake = absent_anchor("")
        fake["state"] = ANCHOR_SHAPE_CANDIDATE
        self.assertEqual(self.run_review(anchor=fake)["reason"],
                         "ANCHOR_SHAPE_CANDIDATE_MALFORMED")

    def test_noncanonical_json_is_rejected(self):
        raw = json.dumps(self.design()).encode("utf-8")
        result = evaluate_windows_collector_root_crypto_architecture(raw, self.anchor)
        self.assertEqual(result["reason"], "CRYPTO_REVIEW_INPUT_INVALID")

    def test_duplicate_json_property_is_rejected(self):
        raw = canonical(self.design()).replace(
            b'"schema":', b'"schema":"evil","schema":', 1)
        result = evaluate_windows_collector_root_crypto_architecture(raw, self.anchor)
        self.assertEqual(result["reason"], "CRYPTO_REVIEW_INPUT_INVALID")

    def test_unknown_extra_auto_install_field_denied(self):
        record = self.design()
        record["activate_installer"] = True
        self.assertEqual(self.run_review(record)["reason"],
                         "CRYPTO_REVIEW_INPUT_INVALID")

    def test_input_type_attack_denied(self):
        record = self.design()
        record["owner_approval_state"] = True
        self.assertEqual(self.run_review(record)["reason"],
                         "CRYPTO_REVIEW_INPUT_INVALID")

    def test_nonce_type_and_length_denied(self):
        for nonce in ("a"*63, "A"*64, 7, "", None):
            with self.subTest(nonce=nonce):
                record = self.design()
                record["review_nonce"] = nonce
                self.assertEqual(self.run_review(record)["reason"],
                                 "CRYPTO_REVIEW_INPUT_INVALID")

    def test_oversized_payload_denied(self):
        raw = b"x" * 4097
        result = evaluate_windows_collector_root_crypto_architecture(raw, self.anchor)
        self.assertEqual(result["reason"], "CRYPTO_REVIEW_INPUT_INVALID")

    def test_absence_of_anchor_never_carries_enrollment_authority(self):
        result = self.run_review()
        self.assertIn("OWNER_APPROVED_ACTUAL_ENROLLMENT_SEPARATELY_REQUIRED",
                      result["unresolved_gates"])
        self.assertIn("SANDBOX_12_OF_12_PHYSICAL_MEASUREMENTS_REQUIRED",
                      result["unresolved_gates"])
        self.assertIn("NETWORK_16_OF_16_PHYSICAL_DENIAL_SURFACES_REQUIRED",
                      result["unresolved_gates"])
        self.permanent_denials(result)


if __name__ == "__main__":
    unittest.main()
