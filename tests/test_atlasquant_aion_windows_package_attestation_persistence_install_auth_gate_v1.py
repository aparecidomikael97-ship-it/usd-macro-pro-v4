import base64
import copy
import unittest

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

from atlasquant_aion_windows_installation_manifest_package_attestation_v1 import (
    PACKAGE_ATTESTATION_SCHEMA,
)
from atlasquant_aion_windows_package_attestation_persistence_install_auth_gate_v1 import (
    OWNER_SIGNATURE_CONTEXT,
    AUTHORIZE_DECISION,
    DENY_DECISION,
    READY_PERSISTENCE_CONTRACT_STATE,
    READY_PERSISTENCE_SHAPE_STATE,
    READY_INSTALL_GATE_STATE,
    READY_OWNER_SIGNATURE_STATE,
    OWNER_INSTALL_AUTH_VERIFIED_PENDING_PERSISTENCE,
    OWNER_INSTALL_DENIAL_VERIFIED,
    READY_AUTH_PERSISTENCE_SHAPE_STATE,
    READY_REVIEW_STATE,
    owner_key_fingerprint,
    build_package_attestation_persistence_contract,
    validate_future_package_persistence_attestation_shape,
    build_installation_gate,
    build_owner_install_authorization_request,
    verify_owner_install_signature,
    validate_future_install_auth_persistence_shape,
    build_implementation_review,
    installation_gate_policy,
)

D=lambda c:"sha256:"+(c*64)

class PackageAttestationPersistenceInstallAuthGateV1Tests(unittest.TestCase):
    def setUp(self):
        self.owner_private=Ed25519PrivateKey.generate()
        raw=self.owner_private.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        self.owner_public_b64=base64.b64encode(raw).decode("ascii")
        self.owner_fp=owner_key_fingerprint(self.owner_public_b64)

    def package_attestation(self,**changes):
        row={
            "schema":PACKAGE_ATTESTATION_SCHEMA,
            "state":"PACKAGE_ATTESTED_OFFLINE_NOT_INSTALLED",
            "package_attestation_digest":D("1"),
            "manifest_digest":D("2"),
            "archive_digest":D("3"),
            "sbom_digest":D("4"),
            "build_provenance_digest":D("5"),
            "dependency_lock_digest":D("6"),
            "authenticode_binary_digest":D("7"),
            "authenticode_evidence_digest":D("8"),
            "release_review_digest":D("9"),
            "package_signer_fingerprint":D("a"),
            "package_family":"AtlasQuant.AION.RepositoryMutationRuntime",
            "package_version":"1.0.0",
            "build_id":"build://first-prod-build-0001",
            "build_commit_sha":"a"*40,
            "manifest_signature_verified":True,
            "authenticode_signature_verified":True,
            "authenticode_trusted_chain_verified":True,
            "authenticode_timestamp_verified":True,
            "authenticode_publisher_match_verified":True,
            "package_installed":False,
        }
        row.update(changes)
        return row

    def persistence_contract(self):
        out=build_package_attestation_persistence_contract(
            self.package_attestation(),
            persistence_namespace="aion/windows/package-attestation/v1",
            writer_manifest_digest=D("b"),
            package_store_design_digest=D("c"),
        )
        self.assertEqual(out["state"],READY_PERSISTENCE_CONTRACT_STATE,out["blockers"])
        return out

    def persistence_attestation(self,contract=None,**changes):
        c=contract or self.persistence_contract()
        kwargs=dict(
            contract=c,
            record_key=D("1"),
            record_digest=D("2"),
            writer_manifest_digest=c["writer_manifest_digest"],
            write_receipt_digest=D("3"),
            cas_observation_digest=D("4"),
            read_after_write_observation_digest=D("5"),
            reopen_observation_digest=D("6"),
            persisted_at="2026-10-08T16:30:00+00:00",
            now="2026-10-08T16:30:30+00:00",
            caller_claims_persistence_verified=False,
        )
        kwargs.update(changes)
        return validate_future_package_persistence_attestation_shape(**kwargs)

    def gate(self,contract=None):
        c=contract or self.persistence_contract()
        out=build_installation_gate(
            c,
            installation_target_digest=D("d"),
            owner_acl_policy_digest=D("e"),
            startup_policy_digest=D("f"),
            rollback_archive_digest=D("1"),
            rollback_manifest_digest=D("2"),
            uninstall_manifest_digest=D("3"),
            install_plan_digest=D("4"),
            owner_binding_digest=D("5"),
        )
        self.assertEqual(out["state"],READY_INSTALL_GATE_STATE,out["blockers"])
        return out

    def request(self,gate=None,persistence=None,decision=AUTHORIZE_DECISION,**changes):
        g=gate or self.gate()
        p=persistence or self.persistence_attestation()
        kwargs=dict(
            gate=g,
            persistence_attestation=p,
            authorization_id="install-auth://first-prod-install-0001",
            decision=decision,
            nonce="nonce://first-prod-install-0001",
            owner_public_key_b64=self.owner_public_b64,
            expected_owner_key_fingerprint=self.owner_fp,
            issued_at="2026-10-08T16:31:00+00:00",
            expires_at="2026-10-08T16:32:00+00:00",
            now="2026-10-08T16:31:10+00:00",
        )
        kwargs.update(changes)
        return build_owner_install_authorization_request(**kwargs)

    def sign(self,request_result):
        return base64.b64encode(self.owner_private.sign(
            OWNER_SIGNATURE_CONTEXT+request_result["request_digest"].encode("ascii")
        )).decode("ascii")

    def test_package_persistence_contract_is_strict_and_nonwriting(self):
        c=self.persistence_contract()
        self.assertTrue(c["append_only_required"])
        self.assertTrue(c["compare_and_set_required"])
        self.assertTrue(c["exactly_once_required"])
        self.assertTrue(c["read_after_write_required"])
        self.assertTrue(c["reopen_consistency_required"])
        self.assertFalse(c["replace_allowed"])
        self.assertFalse(c["delete_allowed"])
        self.assertFalse(c["attestation_persisted"])
        self.assertFalse(c["physical_persistence_verified"])
        self.assertFalse(c["installation_authorized"])
        self.assertFalse(c["package_installed"])

    def test_incomplete_or_unverified_package_attestation_blocks(self):
        for changes,expected in (
            ({"state":"BLOCKED"},"PACKAGE_ATTESTED_OFFLINE_NOT_INSTALLED_REQUIRED"),
            ({"manifest_signature_verified":False},"PACKAGE_RELEASE_SIGNATURE_VERIFICATION_REQUIRED"),
            ({"authenticode_trusted_chain_verified":False},"AUTHENTICODE_TRUSTED_CHAIN_VERIFICATION_REQUIRED"),
            ({"authenticode_timestamp_verified":False},"AUTHENTICODE_TIMESTAMP_VERIFICATION_REQUIRED"),
        ):
            with self.subTest(expected=expected):
                out=build_package_attestation_persistence_contract(
                    self.package_attestation(**changes),
                    persistence_namespace="aion/windows/package-attestation/v1",
                    writer_manifest_digest=D("b"),
                    package_store_design_digest=D("c"),
                )
                self.assertEqual(out["state"],"BLOCKED")
                self.assertIn(expected,out["blockers"])

    def test_persistence_shape_never_becomes_trusted_by_shape(self):
        p=self.persistence_attestation()
        self.assertEqual(p["state"],READY_PERSISTENCE_SHAPE_STATE,p["blockers"])
        self.assertTrue(p["shape_valid"])
        self.assertFalse(p["persistence_trusted"])
        self.assertFalse(p["cas_verified"])
        self.assertFalse(p["read_after_write_verified"])
        self.assertFalse(p["reopen_verified"])
        self.assertFalse(p["installation_authorized"])
        self.assertFalse(p["package_installed"])

    def test_stale_or_self_asserted_package_persistence_blocks(self):
        stale=self.persistence_attestation(now="2026-10-08T16:33:00+00:00")
        self.assertEqual(stale["state"],"BLOCKED")
        self.assertIn("PACKAGE_PERSISTENCE_ATTESTATION_STALE",stale["blockers"])
        fake=self.persistence_attestation(caller_claims_persistence_verified=True)
        self.assertEqual(fake["state"],"BLOCKED")
        self.assertIn("CALLER_PACKAGE_PERSISTENCE_TRUST_CLAIM_NOT_ACCEPTED",fake["blockers"])

    def test_installation_gate_binds_rollback_and_never_authorizes(self):
        g=self.gate()
        self.assertTrue(g["package_persistence_reopen_required"])
        self.assertTrue(g["rollback_material_required"])
        self.assertTrue(g["uninstall_manifest_required"])
        self.assertFalse(g["generic_chat_is_install_authorization"])
        self.assertTrue(g["owner_install_authorization_must_be_separate"])
        self.assertTrue(g["owner_install_authorization_must_be_fresh"])
        self.assertTrue(g["owner_install_authorization_must_be_single_use"])
        self.assertFalse(g["installation_authorized"])
        self.assertFalse(g["install_token_issued"])
        self.assertFalse(g["installation_started"])
        self.assertFalse(g["package_installed"])
        self.assertFalse(g["filesystem_modified"])
        self.assertFalse(g["windows_acl_modified"])
        self.assertFalse(g["windows_registry_modified"])
        self.assertFalse(g["startup_entry_created"])

    def test_request_binds_exact_package_and_generic_chat_is_not_authority(self):
        r=self.request()
        self.assertEqual(r["state"],READY_OWNER_SIGNATURE_STATE,r["blockers"])
        self.assertEqual(r["request"]["decision"],AUTHORIZE_DECISION)
        self.assertFalse(r["request"]["generic_chat_instruction_accepted_as_install_authorization"])
        self.assertFalse(r["owner_signature_verified"])
        self.assertFalse(r["nonce_claimed"])
        self.assertFalse(r["authorization_persisted"])
        self.assertFalse(r["authorization_consumed"])
        self.assertFalse(r["installation_authorized"])
        self.assertFalse(r["install_token_issued"])
        self.assertFalse(r["installation_started"])
        self.assertFalse(r["package_installed"])

    def test_valid_owner_signature_is_pending_persistence_only(self):
        r=self.request()
        out=verify_owner_install_signature(
            r,
            owner_public_key_b64=self.owner_public_b64,
            signature_b64=self.sign(r),
            expected_owner_key_fingerprint=self.owner_fp,
            now="2026-10-08T16:31:20+00:00",
        )
        self.assertEqual(out["state"],OWNER_INSTALL_AUTH_VERIFIED_PENDING_PERSISTENCE,out["blockers"])
        self.assertTrue(out["owner_signature_verified"])
        self.assertTrue(out["installation_intent_verified"])
        self.assertFalse(out["denial_intent_verified"])
        self.assertFalse(out["generic_chat_instruction_accepted_as_install_authorization"])
        self.assertFalse(out["nonce_claimed"])
        self.assertFalse(out["persistent_nonce_replay_guard_verified"])
        self.assertFalse(out["authorization_persisted"])
        self.assertFalse(out["authorization_consumed"])
        self.assertFalse(out["installation_authorized"])
        self.assertFalse(out["install_token_issued"])
        self.assertFalse(out["installation_started"])
        self.assertFalse(out["package_installed"])

    def test_signed_denial_never_becomes_install_authority(self):
        r=self.request(decision=DENY_DECISION)
        out=verify_owner_install_signature(
            r,
            owner_public_key_b64=self.owner_public_b64,
            signature_b64=self.sign(r),
            expected_owner_key_fingerprint=self.owner_fp,
            now="2026-10-08T16:31:20+00:00",
        )
        self.assertEqual(out["state"],OWNER_INSTALL_DENIAL_VERIFIED)
        self.assertTrue(out["denial_intent_verified"])
        self.assertFalse(out["installation_intent_verified"])
        self.assertFalse(out["installation_authorized"])

    def test_wrong_signature_post_signature_tamper_and_expiry_block(self):
        r=self.request()
        wrong=Ed25519PrivateKey.generate()
        wrong_sig=base64.b64encode(wrong.sign(
            OWNER_SIGNATURE_CONTEXT+r["request_digest"].encode("ascii")
        )).decode("ascii")
        bad=verify_owner_install_signature(
            r,owner_public_key_b64=self.owner_public_b64,signature_b64=wrong_sig,
            expected_owner_key_fingerprint=self.owner_fp,now="2026-10-08T16:31:20+00:00")
        self.assertEqual(bad["state"],"BLOCKED")
        self.assertIn("OWNER_INSTALL_AUTHORIZATION_SIGNATURE_INVALID",bad["blockers"])

        tampered=copy.deepcopy(r)
        tampered["request"]["archive_digest"]=D("0")
        bad2=verify_owner_install_signature(
            tampered,owner_public_key_b64=self.owner_public_b64,signature_b64=self.sign(r),
            expected_owner_key_fingerprint=self.owner_fp,now="2026-10-08T16:31:20+00:00")
        self.assertEqual(bad2["state"],"BLOCKED")
        self.assertIn("INSTALL_AUTH_REQUEST_DIGEST_MISMATCH",bad2["blockers"])

        expired=verify_owner_install_signature(
            r,owner_public_key_b64=self.owner_public_b64,signature_b64=self.sign(r),
            expected_owner_key_fingerprint=self.owner_fp,now="2026-10-08T16:32:00+00:00")
        self.assertEqual(expired["state"],"BLOCKED")
        self.assertIn("INSTALL_AUTHORIZATION_EXPIRED",expired["blockers"])

    def test_install_auth_persistence_shape_remains_untrusted(self):
        r=self.request()
        owner=verify_owner_install_signature(
            r,owner_public_key_b64=self.owner_public_b64,signature_b64=self.sign(r),
            expected_owner_key_fingerprint=self.owner_fp,now="2026-10-08T16:31:20+00:00")
        out=validate_future_install_auth_persistence_shape(
            owner,
            nonce_registry_record_digest=D("1"),
            authorization_record_digest=D("2"),
            writer_manifest_digest=D("3"),
            write_receipt_digest=D("4"),
            cas_observation_digest=D("5"),
            read_after_write_observation_digest=D("6"),
            reopen_observation_digest=D("7"),
            replay_guard_observation_digest=D("8"),
            nonce_single_use_observation_digest=D("9"),
            authorization_consumed=False,
        )
        self.assertEqual(out["state"],READY_AUTH_PERSISTENCE_SHAPE_STATE,out["blockers"])
        self.assertTrue(out["shape_valid"])
        for f in ("nonce_claimed_trusted","persistent_nonce_replay_guard_verified",
                  "nonce_single_use_verified","authorization_persisted_trusted",
                  "cas_verified","read_after_write_verified","reopen_verified",
                  "authorization_consumed","installation_authorized","install_token_issued",
                  "installation_started","package_installed"):
            self.assertFalse(out[f],f)

    def test_consumed_or_self_asserted_install_authorization_persistence_blocks(self):
        r=self.request()
        owner=verify_owner_install_signature(
            r,owner_public_key_b64=self.owner_public_b64,signature_b64=self.sign(r),
            expected_owner_key_fingerprint=self.owner_fp,now="2026-10-08T16:31:20+00:00")
        common=dict(
            owner_verification=owner,
            nonce_registry_record_digest=D("1"),
            authorization_record_digest=D("2"),
            writer_manifest_digest=D("3"),
            write_receipt_digest=D("4"),
            cas_observation_digest=D("5"),
            read_after_write_observation_digest=D("6"),
            reopen_observation_digest=D("7"),
            replay_guard_observation_digest=D("8"),
            nonce_single_use_observation_digest=D("9"),
        )
        consumed=validate_future_install_auth_persistence_shape(
            **common,authorization_consumed=True)
        self.assertEqual(consumed["state"],"BLOCKED")
        self.assertIn("INSTALL_AUTHORIZATION_MUST_BE_UNCONSUMED",consumed["blockers"])
        fake=validate_future_install_auth_persistence_shape(
            **common,authorization_consumed=False,caller_claims_persistence_verified=True)
        self.assertEqual(fake["state"],"BLOCKED")
        self.assertIn("CALLER_INSTALL_AUTH_PERSISTENCE_TRUST_CLAIM_NOT_ACCEPTED",fake["blockers"])

    def test_implementation_review_stops_before_installation(self):
        g=self.gate()
        review=build_implementation_review(
            g,
            package_persistence_writer_design_digest=D("1"),
            package_reopen_verifier_design_digest=D("2"),
            install_nonce_registry_design_digest=D("3"),
            install_authorization_writer_design_digest=D("4"),
            install_preflight_design_digest=D("5"),
        )
        self.assertEqual(review["state"],READY_REVIEW_STATE,review["blockers"])
        for f in ("package_persistence_writer_implemented","package_reopen_verifier_implemented",
                  "install_nonce_registry_implemented","install_authorization_writer_implemented",
                  "install_preflight_implemented","package_attestation_persisted",
                  "package_attestation_reopen_verified","owner_install_authorization_persisted",
                  "installation_authorized","install_token_issued","installation_started",
                  "package_installed","filesystem_modified","windows_acl_modified",
                  "windows_registry_modified","startup_entry_created","network_called","github_api_called"):
            self.assertFalse(review[f],f)

    def test_policy_is_fail_closed(self):
        p=installation_gate_policy()
        self.assertEqual(p["package_attestation_state_required"],"PACKAGE_ATTESTED_OFFLINE_NOT_INSTALLED")
        self.assertTrue(p["package_persistence_append_only_required"])
        self.assertTrue(p["package_persistence_cas_required"])
        self.assertTrue(p["package_persistence_reopen_required"])
        self.assertTrue(p["fresh_owner_install_signature_required"])
        self.assertTrue(p["persistent_nonce_replay_guard_required"])
        self.assertTrue(p["single_use_install_authorization_required"])
        self.assertTrue(p["rollback_material_required"])
        self.assertTrue(p["uninstall_manifest_required"])
        self.assertFalse(p["generic_chat_is_install_authorization"])
        self.assertFalse(p["caller_package_persistence_claim_is_authority"])
        self.assertFalse(p["caller_install_auth_persistence_claim_is_authority"])
        for f in ("package_persistence_writer_implemented","package_reopen_verifier_implemented",
                  "install_nonce_registry_implemented","install_authorization_writer_implemented",
                  "package_attestation_persisted","package_attestation_reopen_verified",
                  "owner_install_authorization_persisted","installation_authorized",
                  "install_token_issued","installation_started","package_installed","files_copied",
                  "filesystem_modified","windows_acl_modified","windows_registry_modified",
                  "startup_entry_created","scheduled_task_installed","windows_service_installed",
                  "process_spawned","network_called","github_api_called",
                  "live_repository_mutation_authorized","live_repository_mutation_performed",
                  "production_repository_mutation_performed","deploy_executed","worker_activated",
                  "provider_activated","production_persistence_activated"):
            self.assertFalse(p[f],f)

if __name__=="__main__":
    unittest.main()
