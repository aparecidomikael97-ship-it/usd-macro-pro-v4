import base64
import copy
import unittest

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

from atlasquant_aion_windows_immutable_evidence_receipt_persistence_v1 import (
    STORE_SCHEMA,
    RECEIPT_PERSISTENCE_SCHEMA,
    READY_STORE_STATE,
    READY_RECEIPT_PERSISTENCE_STATE,
)
from atlasquant_aion_windows_physical_verification_build_authorization_gate_v1 import (
    PHYSICAL_CERTIFICATE_SCHEMA,
    OWNER_SIGNATURE_CONTEXT,
    AUTHORIZE_DECISION,
    DENY_DECISION,
    READY_CONTRACT_STATE,
    READY_OWNER_SIGNATURE_STATE,
    OWNER_AUTH_VERIFIED_PENDING_PERSISTENCE,
    OWNER_DENIAL_VERIFIED,
    READY_AUTH_PERSISTENCE_SHAPE_STATE,
    READY_LAUNCH_REVIEW_STATE,
    build_gate_contract,
    validate_physical_certificate_shape,
    build_owner_authorization_request,
    verify_owner_authorization_signature,
    validate_authorization_persistence_shape,
    build_launch_gate_implementation_review,
    build_authorization_gate_policy,
    owner_key_fingerprint,
)


D = lambda c: "sha256:" + (c * 64)


class AionWindowsPhysicalVerificationBuildAuthorizationGateV1Tests(
    unittest.TestCase
):
    def setUp(self):
        self.owner_private = Ed25519PrivateKey.generate()
        raw = self.owner_private.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        self.owner_public_b64 = base64.b64encode(raw).decode("ascii")
        self.owner_fp = owner_key_fingerprint(self.owner_public_b64)

    def upstream(self):
        store = {
            "schema": STORE_SCHEMA,
            "state": READY_STORE_STATE,
            "store_contract_digest": D("1"),
        }
        receipt = {
            "schema": RECEIPT_PERSISTENCE_SCHEMA,
            "state": READY_RECEIPT_PERSISTENCE_STATE,
            "receipt_persistence_contract_digest": D("2"),
            "receipt_issued": False,
            "receipt_persisted": False,
        }
        return store, receipt

    def gate(self):
        store, receipt = self.upstream()
        gate = build_gate_contract(
            store,
            receipt,
            reproducible_build_recipe_digest=D("3"),
            offline_input_promotion_digest=D("4"),
            sandbox_preflight_digest=D("5"),
            package_manifest_digest=D("6"),
            package_attestation_policy_digest=D("7"),
            owner_binding_digest=D("8"),
        )
        self.assertEqual(
            gate["state"],
            READY_CONTRACT_STATE,
            gate["blockers"],
        )
        return gate

    def certificate(self, gate=None, **changes):
        gate = gate or self.gate()
        row = {
            "schema": PHYSICAL_CERTIFICATE_SCHEMA,
            "state": "PHYSICAL_VERIFICATION_CERTIFICATE_VERIFIED",
            "certificate_digest": D("9"),
            "evidence_store_contract_digest":
                gate["evidence_store_contract_digest"],
            "receipt_persistence_contract_digest":
                gate["receipt_persistence_contract_digest"],
            "verification_receipt_digest": D("a"),
            "verification_receipt_signature_digest": D("b"),
            "receipt_persistence_attestation_digest": D("c"),
            "receipt_reopen_observation_digest": D("d"),
            "evidence_chain_digest": D("e"),
            "evidence_chain_reopen_observation_digest": D("f"),
            "collector_manifest_digest": D("1"),
            "verifier_manifest_digest": D("2"),
            "host_binding_digest": D("3"),
            "reproducible_build_recipe_digest":
                gate["reproducible_build_recipe_digest"],
            "offline_input_promotion_digest":
                gate["offline_input_promotion_digest"],
            "sandbox_preflight_digest":
                gate["sandbox_preflight_digest"],
            "owner_binding_digest": gate["owner_binding_digest"],
            "verified_total": 12,
            "required_total": 12,
            "all_requirements_verified": True,
            "receipt_signature_verified": True,
            "receipt_persisted_verified": True,
            "receipt_cas_verified": True,
            "receipt_read_after_write_verified": True,
            "receipt_reopen_verified": True,
            "evidence_chain_reopen_verified": True,
            "freshness_verified": True,
            "no_unresolved_blockers": True,
            "issued_at": "2026-10-08T16:00:00+00:00",
        }
        row.update(changes)
        return row

    def owner_request(
        self,
        gate=None,
        certificate=None,
        decision=AUTHORIZE_DECISION,
        **changes,
    ):
        gate = gate or self.gate()
        certificate = certificate or self.certificate(gate)
        kwargs = {
            "gate_contract": gate,
            "physical_certificate": certificate,
            "authorization_id": "build-auth://first-production-v1",
            "decision": decision,
            "nonce": "nonce://first-production-build-0001",
            "owner_public_key_b64": self.owner_public_b64,
            "expected_owner_key_fingerprint": self.owner_fp,
            "issued_at": "2026-10-08T16:00:10+00:00",
            "expires_at": "2026-10-08T16:01:10+00:00",
            "now": "2026-10-08T16:00:20+00:00",
        }
        kwargs.update(changes)
        return build_owner_authorization_request(**kwargs)

    def sign(self, request_result):
        message = (
            OWNER_SIGNATURE_CONTEXT
            + request_result["request_digest"].encode("ascii")
        )
        return base64.b64encode(
            self.owner_private.sign(message)
        ).decode("ascii")

    def test_gate_contract_requires_separate_owner_authorization(self):
        gate = self.gate()
        self.assertFalse(gate["generic_chat_is_build_authorization"])
        self.assertTrue(gate["owner_authorization_must_be_separate"])
        self.assertTrue(gate["owner_authorization_must_be_fresh"])
        self.assertTrue(gate["owner_authorization_must_be_single_use"])
        self.assertTrue(gate["physical_certificate_required"])
        self.assertTrue(gate["signed_persisted_receipt_required"])
        self.assertTrue(gate["receipt_reopen_required"])
        self.assertTrue(gate["evidence_chain_reopen_required"])
        self.assertFalse(gate["build_authorized"])
        self.assertFalse(gate["build_token_issued"])
        self.assertFalse(gate["build_started"])
        self.assertFalse(gate["process_spawned"])
        self.assertFalse(gate["filesystem_modified"])
        self.assertFalse(gate["network_called"])

    def test_upstream_schema_drift_blocks_gate(self):
        store, receipt = self.upstream()
        bad_store = dict(store)
        bad_store["schema"] = "WRONG"
        gate = build_gate_contract(
            bad_store,
            receipt,
            reproducible_build_recipe_digest=D("3"),
            offline_input_promotion_digest=D("4"),
            sandbox_preflight_digest=D("5"),
            package_manifest_digest=D("6"),
            package_attestation_policy_digest=D("7"),
            owner_binding_digest=D("8"),
        )
        self.assertEqual(gate["state"], "BLOCKED")
        self.assertIn(
            "EVIDENCE_STORE_CONTRACT_SCHEMA_MISMATCH",
            gate["blockers"],
        )

    def test_physical_certificate_shape_requires_all_twelve_and_persistence(self):
        gate = self.gate()
        cert = self.certificate(gate)
        review = validate_physical_certificate_shape(
            gate,
            cert,
            now="2026-10-08T16:00:20+00:00",
        )
        self.assertEqual(
            review["state"],
            "PHYSICAL_CERTIFICATE_SHAPE_VALID_BUT_EXTERNAL_TRUST_REQUIRED",
            review["blockers"],
        )
        self.assertTrue(review["certificate_shape_valid"])
        self.assertFalse(review["physical_truth_trusted_by_this_module"])
        self.assertFalse(review["build_authorized"])

        eleven = self.certificate(gate, verified_total=11)
        blocked = validate_physical_certificate_shape(
            gate,
            eleven,
            now="2026-10-08T16:00:20+00:00",
        )
        self.assertEqual(blocked["state"], "BLOCKED")
        self.assertIn(
            "ALL_12_PHYSICAL_REQUIREMENTS_MUST_BE_VERIFIED",
            blocked["blockers"],
        )

        no_reopen = self.certificate(gate, receipt_reopen_verified=False)
        blocked2 = validate_physical_certificate_shape(
            gate,
            no_reopen,
            now="2026-10-08T16:00:20+00:00",
        )
        self.assertEqual(blocked2["state"], "BLOCKED")
        self.assertIn(
            "RECEIPT_REOPEN_VERIFICATION_REQUIRED",
            blocked2["blockers"],
        )

    def test_physical_certificate_must_be_fresh(self):
        gate = self.gate()
        stale = self.certificate(
            gate,
            issued_at="2026-10-08T15:58:00+00:00",
        )
        review = validate_physical_certificate_shape(
            gate,
            stale,
            now="2026-10-08T16:00:20+00:00",
        )
        self.assertEqual(review["state"], "BLOCKED")
        self.assertIn("PHYSICAL_CERTIFICATE_STALE", review["blockers"])

    def test_physical_certificate_binding_tamper_blocks(self):
        gate = self.gate()
        for field, expected in (
            (
                "reproducible_build_recipe_digest",
                "PHYSICAL_CERTIFICATE_RECIPE_MISMATCH",
            ),
            (
                "offline_input_promotion_digest",
                "PHYSICAL_CERTIFICATE_INPUT_PROMOTION_MISMATCH",
            ),
            (
                "sandbox_preflight_digest",
                "PHYSICAL_CERTIFICATE_SANDBOX_PREFLIGHT_MISMATCH",
            ),
            (
                "owner_binding_digest",
                "PHYSICAL_CERTIFICATE_OWNER_BINDING_MISMATCH",
            ),
            (
                "evidence_store_contract_digest",
                "PHYSICAL_CERTIFICATE_EVIDENCE_STORE_BINDING_MISMATCH",
            ),
            (
                "receipt_persistence_contract_digest",
                "PHYSICAL_CERTIFICATE_RECEIPT_PERSISTENCE_BINDING_MISMATCH",
            ),
        ):
            with self.subTest(field=field):
                cert = self.certificate(gate, **{field: D("0")})
                review = validate_physical_certificate_shape(
                    gate,
                    cert,
                    now="2026-10-08T16:00:20+00:00",
                )
                self.assertEqual(review["state"], "BLOCKED")
                self.assertIn(expected, review["blockers"])

    def test_owner_request_is_separate_fresh_and_chat_is_never_authority(self):
        request = self.owner_request()
        self.assertEqual(
            request["state"],
            READY_OWNER_SIGNATURE_STATE,
            request["blockers"],
        )
        self.assertTrue(request["request_digest"].startswith("sha256:"))
        self.assertEqual(
            request["request"]["decision"],
            AUTHORIZE_DECISION,
        )
        self.assertFalse(
            request["request"][
                "generic_chat_instruction_accepted_as_build_authorization"
            ]
        )
        self.assertFalse(request["owner_signature_verified"])
        self.assertFalse(request["nonce_claimed"])
        self.assertFalse(request["authorization_persisted"])
        self.assertFalse(request["authorization_consumed"])
        self.assertFalse(request["build_authorized"])
        self.assertFalse(request["build_token_issued"])
        self.assertFalse(request["build_started"])

    def test_owner_signature_verifies_but_does_not_authorize_build(self):
        request = self.owner_request()
        result = verify_owner_authorization_signature(
            request,
            owner_public_key_b64=self.owner_public_b64,
            signature_b64=self.sign(request),
            expected_owner_key_fingerprint=self.owner_fp,
            now="2026-10-08T16:00:30+00:00",
        )
        self.assertEqual(
            result["state"],
            OWNER_AUTH_VERIFIED_PENDING_PERSISTENCE,
            result["blockers"],
        )
        self.assertTrue(result["owner_identity_cryptographically_bound"])
        self.assertTrue(result["owner_signature_verified"])
        self.assertTrue(result["authorization_intent_verified"])
        self.assertFalse(result["denial_intent_verified"])
        self.assertFalse(
            result["generic_chat_instruction_accepted_as_build_authorization"]
        )
        self.assertFalse(result["nonce_claimed"])
        self.assertFalse(result["persistent_nonce_replay_guard_verified"])
        self.assertFalse(result["authorization_persisted"])
        self.assertFalse(result["authorization_consumed"])
        self.assertFalse(result["build_authorized"])
        self.assertFalse(result["build_token_issued"])
        self.assertFalse(result["build_started"])

    def test_signed_denial_never_becomes_authorization(self):
        request = self.owner_request(decision=DENY_DECISION)
        result = verify_owner_authorization_signature(
            request,
            owner_public_key_b64=self.owner_public_b64,
            signature_b64=self.sign(request),
            expected_owner_key_fingerprint=self.owner_fp,
            now="2026-10-08T16:00:30+00:00",
        )
        self.assertEqual(result["state"], OWNER_DENIAL_VERIFIED)
        self.assertFalse(result["authorization_intent_verified"])
        self.assertTrue(result["denial_intent_verified"])
        self.assertFalse(result["build_authorized"])

    def test_wrong_owner_signature_or_post_signature_tamper_blocks(self):
        request = self.owner_request()
        wrong_private = Ed25519PrivateKey.generate()
        wrong_sig = base64.b64encode(
            wrong_private.sign(
                OWNER_SIGNATURE_CONTEXT
                + request["request_digest"].encode("ascii")
            )
        ).decode("ascii")
        bad = verify_owner_authorization_signature(
            request,
            owner_public_key_b64=self.owner_public_b64,
            signature_b64=wrong_sig,
            expected_owner_key_fingerprint=self.owner_fp,
            now="2026-10-08T16:00:30+00:00",
        )
        self.assertEqual(bad["state"], "BLOCKED")
        self.assertIn(
            "OWNER_BUILD_AUTHORIZATION_SIGNATURE_INVALID",
            bad["blockers"],
        )

        tampered = copy.deepcopy(request)
        tampered["request"]["package_manifest_digest"] = D("0")
        bad2 = verify_owner_authorization_signature(
            tampered,
            owner_public_key_b64=self.owner_public_b64,
            signature_b64=self.sign(request),
            expected_owner_key_fingerprint=self.owner_fp,
            now="2026-10-08T16:00:30+00:00",
        )
        self.assertEqual(bad2["state"], "BLOCKED")
        self.assertIn(
            "BUILD_AUTHORIZATION_REQUEST_DIGEST_MISMATCH",
            bad2["blockers"],
        )

    def test_owner_authorization_expiry_blocks(self):
        request = self.owner_request(
            issued_at="2026-10-08T16:00:10+00:00",
            expires_at="2026-10-08T16:00:40+00:00",
            now="2026-10-08T16:00:20+00:00",
        )
        result = verify_owner_authorization_signature(
            request,
            owner_public_key_b64=self.owner_public_b64,
            signature_b64=self.sign(request),
            expected_owner_key_fingerprint=self.owner_fp,
            now="2026-10-08T16:00:40+00:00",
        )
        self.assertEqual(result["state"], "BLOCKED")
        self.assertIn("BUILD_AUTHORIZATION_EXPIRED", result["blockers"])

    def test_authorization_persistence_shape_is_still_untrusted(self):
        request = self.owner_request()
        owner = verify_owner_authorization_signature(
            request,
            owner_public_key_b64=self.owner_public_b64,
            signature_b64=self.sign(request),
            expected_owner_key_fingerprint=self.owner_fp,
            now="2026-10-08T16:00:30+00:00",
        )
        persistence = validate_authorization_persistence_shape(
            owner,
            nonce_registry_record_digest=D("1"),
            authorization_record_digest=D("2"),
            writer_manifest_digest=D("3"),
            write_receipt_digest=D("4"),
            cas_observation_digest=D("5"),
            read_after_write_observation_digest=D("6"),
            reopen_observation_digest=D("7"),
            persistent_nonce_replay_guard_observation_digest=D("8"),
            nonce_single_use_observation_digest=D("9"),
            authorization_consumed=False,
        )
        self.assertEqual(
            persistence["state"],
            READY_AUTH_PERSISTENCE_SHAPE_STATE,
            persistence["blockers"],
        )
        self.assertTrue(persistence["shape_valid"])
        self.assertFalse(persistence["nonce_claimed_trusted"])
        self.assertFalse(
            persistence["persistent_nonce_replay_guard_verified"]
        )
        self.assertFalse(persistence["nonce_single_use_verified"])
        self.assertFalse(persistence["authorization_persisted_trusted"])
        self.assertFalse(persistence["cas_verified"])
        self.assertFalse(persistence["read_after_write_verified"])
        self.assertFalse(persistence["reopen_verified"])
        self.assertFalse(persistence["authorization_consumed"])
        self.assertFalse(persistence["build_authorized"])
        self.assertFalse(persistence["build_token_issued"])
        self.assertFalse(persistence["build_started"])

    def test_persistence_self_claim_and_consumed_auth_block(self):
        request = self.owner_request()
        owner = verify_owner_authorization_signature(
            request,
            owner_public_key_b64=self.owner_public_b64,
            signature_b64=self.sign(request),
            expected_owner_key_fingerprint=self.owner_fp,
            now="2026-10-08T16:00:30+00:00",
        )
        common = dict(
            owner_verification=owner,
            nonce_registry_record_digest=D("1"),
            authorization_record_digest=D("2"),
            writer_manifest_digest=D("3"),
            write_receipt_digest=D("4"),
            cas_observation_digest=D("5"),
            read_after_write_observation_digest=D("6"),
            reopen_observation_digest=D("7"),
            persistent_nonce_replay_guard_observation_digest=D("8"),
            nonce_single_use_observation_digest=D("9"),
        )
        claimed = validate_authorization_persistence_shape(
            **common,
            authorization_consumed=False,
            caller_claims_persistence_verified=True,
        )
        self.assertEqual(claimed["state"], "BLOCKED")
        self.assertIn(
            "CALLER_AUTHORIZATION_PERSISTENCE_CLAIM_NOT_TRUSTED",
            claimed["blockers"],
        )

        consumed = validate_authorization_persistence_shape(
            **common,
            authorization_consumed=True,
        )
        self.assertEqual(consumed["state"], "BLOCKED")
        self.assertIn(
            "BUILD_AUTHORIZATION_MUST_BE_UNCONSUMED",
            consumed["blockers"],
        )

    def test_launch_review_closes_design_but_issues_nothing(self):
        gate = self.gate()
        review = build_launch_gate_implementation_review(
            gate,
            physical_certificate_verifier_design_digest=D("1"),
            owner_nonce_registry_design_digest=D("2"),
            authorization_writer_design_digest=D("3"),
            launch_token_design_digest=D("4"),
            prelaunch_revalidation_design_digest=D("5"),
        )
        self.assertEqual(
            review["state"],
            READY_LAUNCH_REVIEW_STATE,
            review["blockers"],
        )
        self.assertEqual(
            review["next_pc_phase"],
            "IMPLEMENT_PHYSICAL_VERIFICATION_AND_FRESH_OWNER_BUILD_AUTHORIZATION_GATE",
        )
        self.assertFalse(review["launch_gate_implemented"])
        self.assertFalse(review["physical_certificate_trusted"])
        self.assertFalse(review["owner_nonce_registry_implemented"])
        self.assertFalse(
            review["owner_authorization_persistence_implemented"]
        )
        self.assertFalse(review["prelaunch_revalidation_implemented"])
        self.assertFalse(review["build_token_implemented"])
        self.assertFalse(review["build_token_issued"])
        self.assertFalse(review["build_authorized"])
        self.assertFalse(review["build_started"])
        self.assertFalse(review["process_spawned"])
        self.assertFalse(review["filesystem_modified"])
        self.assertFalse(review["network_called"])
        self.assertFalse(review["github_api_called"])
        self.assertFalse(review["live_repository_mutation_performed"])

    def test_policy_is_fail_closed_and_generic_chat_never_authorizes(self):
        policy = build_authorization_gate_policy()
        self.assertEqual(policy["verified_requirement_count_required"], 12)
        self.assertFalse(policy["generic_chat_is_build_authorization"])
        self.assertFalse(policy["chat_acknowledgement_is_authorization"])
        self.assertTrue(policy["explicit_owner_signature_required"])
        self.assertTrue(policy["owner_key_fingerprint_binding_required"])
        self.assertTrue(policy["fresh_nonce_required"])
        self.assertTrue(policy["persistent_nonce_replay_guard_required"])
        self.assertTrue(policy["single_use_authorization_required"])
        self.assertTrue(policy["authorization_persistence_required"])
        self.assertTrue(policy["authorization_cas_required"])
        self.assertTrue(policy["authorization_read_after_write_required"])
        self.assertTrue(policy["authorization_reopen_required"])
        self.assertTrue(policy["physical_certificate_required"])
        self.assertTrue(policy["all_12_physical_requirements_required"])
        self.assertTrue(policy["signed_verifier_receipt_required"])
        self.assertTrue(policy["persisted_verifier_receipt_required"])
        self.assertTrue(policy["receipt_reopen_required"])
        self.assertTrue(policy["evidence_chain_reopen_required"])
        self.assertTrue(policy["prelaunch_revalidation_required"])
        self.assertFalse(
            policy["caller_physical_verification_claim_is_authority"]
        )
        self.assertFalse(
            policy["caller_authorization_persistence_claim_is_authority"]
        )
        for field in (
            "launch_gate_implemented",
            "physical_certificate_trusted",
            "owner_nonce_registry_implemented",
            "owner_authorization_persistence_implemented",
            "build_token_implemented",
            "build_token_issued",
            "build_authorized",
            "build_started",
            "package_built",
            "package_installed",
            "process_spawned",
            "filesystem_modified",
            "network_called",
            "github_api_called",
            "live_repository_mutation_authorized",
            "live_repository_mutation_performed",
            "production_repository_mutation_performed",
            "deploy_executed",
            "worker_activated",
            "provider_activated",
            "production_persistence_activated",
        ):
            self.assertFalse(policy[field], field)


if __name__ == "__main__":
    unittest.main()
