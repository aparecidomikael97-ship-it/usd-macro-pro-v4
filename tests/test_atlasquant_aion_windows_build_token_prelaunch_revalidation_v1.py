import copy
import unittest

from atlasquant_aion_windows_physical_verification_build_authorization_gate_v1 import (
    GATE_CONTRACT_SCHEMA,
    READY_CONTRACT_STATE,
)
from atlasquant_aion_windows_build_token_prelaunch_revalidation_v1 import (
    PRELAUNCH_SNAPSHOT_SCHEMA,
    READY_PRELAUNCH_CONTRACT_STATE,
    READY_PRELAUNCH_SHAPE_STATE,
    READY_TOKEN_TEMPLATE_STATE,
    READY_TOKEN_ATTESTATION_SHAPE_STATE,
    READY_REVIEW_STATE,
    build_prelaunch_contract,
    validate_future_prelaunch_snapshot_shape,
    build_unissued_token_template,
    validate_future_token_issuance_attestation_shape,
    build_implementation_review,
    build_token_prelaunch_policy,
)

D=lambda c:"sha256:"+(c*64)

class BuildTokenPrelaunchV1Tests(unittest.TestCase):
    def gate(self):
        return {
            "schema":GATE_CONTRACT_SCHEMA,
            "state":READY_CONTRACT_STATE,
            "gate_contract_digest":D("1"),
            "reproducible_build_recipe_digest":D("2"),
            "offline_input_promotion_digest":D("3"),
            "sandbox_preflight_digest":D("4"),
            "package_manifest_digest":D("5"),
            "package_attestation_policy_digest":D("6"),
            "owner_binding_digest":D("7"),
            "evidence_store_contract_digest":D("8"),
            "receipt_persistence_contract_digest":D("9"),
            "build_authorized":False,
            "build_token_issued":False,
            "build_started":False,
        }

    def contract(self):
        out=build_prelaunch_contract(
            self.gate(),
            physical_certificate_verifier_digest=D("a"),
            authorization_persistence_verifier_digest=D("b"),
            token_signer_manifest_digest=D("c"),
            token_signer_key_fingerprint=D("d"),
            launch_writer_manifest_digest=D("e"),
            launch_binary_path_digest=D("f"),
            launch_binary_sha256=D("1"),
            build_script_sha256=D("2"),
            safety_stop_policy_digest=D("3"),
            circuit_breaker_policy_digest=D("4"),
            prelaunch_safety_policy_digest=D("5"),
        )
        self.assertEqual(out["state"],READY_PRELAUNCH_CONTRACT_STATE,out["blockers"])
        return out

    def snapshot(self,contract=None,**changes):
        c=contract or self.contract()
        row={
            "schema":PRELAUNCH_SNAPSHOT_SCHEMA,
            "state":"PRELAUNCH_REVALIDATION_VERIFIED",
            "snapshot_digest":D("a"),
            "gate_contract_digest":c["gate_contract_digest"],
            "reproducible_build_recipe_digest":c["reproducible_build_recipe_digest"],
            "offline_input_promotion_digest":c["offline_input_promotion_digest"],
            "sandbox_preflight_digest":c["sandbox_preflight_digest"],
            "package_manifest_digest":c["package_manifest_digest"],
            "package_attestation_policy_digest":c["package_attestation_policy_digest"],
            "owner_binding_digest":c["owner_binding_digest"],
            "evidence_store_contract_digest":c["evidence_store_contract_digest"],
            "receipt_persistence_contract_digest":c["receipt_persistence_contract_digest"],
            "launch_binary_path_digest":c["launch_binary_path_digest"],
            "launch_binary_sha256":c["launch_binary_sha256"],
            "build_script_sha256":c["build_script_sha256"],
            "safety_stop_policy_digest":c["safety_stop_policy_digest"],
            "circuit_breaker_policy_digest":c["circuit_breaker_policy_digest"],
            "prelaunch_safety_policy_digest":c["prelaunch_safety_policy_digest"],
            "physical_certificate_digest":D("b"),
            "verification_receipt_digest":D("c"),
            "verification_receipt_signature_digest":D("d"),
            "receipt_persistence_attestation_digest":D("e"),
            "receipt_reopen_observation_digest":D("f"),
            "evidence_chain_digest":D("1"),
            "evidence_chain_reopen_observation_digest":D("2"),
            "collector_manifest_digest":D("3"),
            "verifier_manifest_digest":D("4"),
            "host_binding_digest":D("5"),
            "owner_authorization_verification_digest":D("6"),
            "authorization_persistence_attestation_digest":D("7"),
            "authorization_record_digest":D("8"),
            "authorization_reopen_observation_digest":D("9"),
            "nonce_registry_record_digest":D("a"),
            "nonce_replay_guard_observation_digest":D("b"),
            "nonce_single_use_observation_digest":D("c"),
            "environment_contract_digest":D("d"),
            "process_contract_digest":D("e"),
            "network_contract_digest":D("f"),
            "safety_stop_observation_digest":D("1"),
            "circuit_breaker_observation_digest":D("2"),
            "safety_state_digest":D("3"),
            "verified_total":12,
            "required_total":12,
            "physical_certificate_trust_verified":True,
            "all_requirements_reverified":True,
            "verification_receipt_signature_reverified":True,
            "verification_receipt_persistence_reverified":True,
            "receipt_reopen_reverified":True,
            "evidence_chain_reopen_reverified":True,
            "owner_signature_reverified":True,
            "owner_authorization_persistence_reverified":True,
            "owner_authorization_reopen_reverified":True,
            "owner_authorization_fresh":True,
            "owner_authorization_unconsumed":True,
            "persistent_nonce_replay_guard_reverified":True,
            "nonce_single_use_reverified":True,
            "host_binding_reverified":True,
            "package_manifest_reverified":True,
            "build_recipe_reverified":True,
            "offline_input_promotion_reverified":True,
            "sandbox_preflight_reverified":True,
            "pinned_python_binary_reverified":True,
            "build_script_reverified":True,
            "environment_scrub_reverified":True,
            "process_allowlist_reverified":True,
            "network_deny_reverified":True,
            "safety_stop_armed":True,
            "safety_stop_engaged":False,
            "circuit_breaker_armed":True,
            "circuit_breaker_healthy":True,
            "no_new_safety_blockers":True,
            "authorization_consumed":False,
            "build_started":False,
            "captured_at":"2026-10-08T16:10:00+00:00",
        }
        row.update(changes)
        return row

    def review(self,contract=None,snapshot=None,now="2026-10-08T16:10:05+00:00"):
        c=contract or self.contract()
        s=snapshot or self.snapshot(c)
        return validate_future_prelaunch_snapshot_shape(c,s,now=now)

    def test_contract_is_final_but_nonexecuting(self):
        c=self.contract()
        for field in ("prelaunch_revalidation_implemented","prelaunch_revalidation_executed",
                      "external_trust_verified","safety_stop_physically_checked",
                      "circuit_breaker_physically_checked","build_token_implemented",
                      "build_token_issued","build_token_signed","build_token_consumed",
                      "build_authorized","build_started","process_spawned","filesystem_modified","network_called"):
            self.assertFalse(c[field],field)

    def test_prelaunch_shape_can_pass_but_remains_untrusted(self):
        r=self.review()
        self.assertEqual(r["state"],READY_PRELAUNCH_SHAPE_STATE,r["blockers"])
        self.assertTrue(r["shape_valid"])
        self.assertFalse(r["external_trust_verified_by_this_module"])
        self.assertFalse(r["physical_revalidation_trusted"])
        self.assertFalse(r["authorization_persistence_trusted"])
        self.assertFalse(r["nonce_state_trusted"])
        self.assertFalse(r["safety_stop_state_trusted"])
        self.assertFalse(r["circuit_breaker_state_trusted"])
        self.assertFalse(r["build_token_issuance_allowed"])
        self.assertFalse(r["build_authorized"])
        self.assertFalse(r["build_started"])

    def test_prelaunch_snapshot_over_ten_seconds_blocks(self):
        r=self.review(now="2026-10-08T16:10:11+00:00")
        self.assertEqual(r["state"],"BLOCKED")
        self.assertIn("PRELAUNCH_SNAPSHOT_STALE",r["blockers"])

    def test_safety_stop_or_circuit_breaker_blocks(self):
        c=self.contract()
        cases=(
            ({"safety_stop_engaged":True},"SAFETY_STOP_MUST_NOT_BE_ENGAGED"),
            ({"safety_stop_armed":False},"PRELAUNCH_REQUIRED_TRUE:safety_stop_armed"),
            ({"circuit_breaker_healthy":False},"PRELAUNCH_REQUIRED_TRUE:circuit_breaker_healthy"),
        )
        for changes,expected in cases:
            with self.subTest(expected=expected):
                r=self.review(c,self.snapshot(c,**changes))
                self.assertEqual(r["state"],"BLOCKED")
                self.assertIn(expected,r["blockers"])

    def test_consumed_owner_authorization_blocks(self):
        c=self.contract()
        r=self.review(c,self.snapshot(c,authorization_consumed=True))
        self.assertEqual(r["state"],"BLOCKED")
        self.assertIn("OWNER_AUTHORIZATION_ALREADY_CONSUMED",r["blockers"])

    def test_binding_tamper_blocks(self):
        c=self.contract()
        for field in ("package_manifest_digest","reproducible_build_recipe_digest",
                      "offline_input_promotion_digest","sandbox_preflight_digest",
                      "launch_binary_sha256","build_script_sha256"):
            with self.subTest(field=field):
                r=self.review(c,self.snapshot(c,**{field:D("0")}))
                self.assertEqual(r["state"],"BLOCKED")
                self.assertIn("PRELAUNCH_BINDING_MISMATCH:"+field,r["blockers"])

    def test_unissued_token_is_single_use_and_max_fifteen_seconds(self):
        c=self.contract();r=self.review(c)
        token=build_unissued_token_template(
            c,r,token_id="build-token://first-prod-0001",token_nonce_digest=D("7"),
            issued_at="2026-10-08T16:10:06+00:00",expires_at="2026-10-08T16:10:20+00:00")
        self.assertEqual(token["state"],READY_TOKEN_TEMPLATE_STATE,token["blockers"])
        self.assertTrue(token["single_use"])
        self.assertEqual(token["max_uses"],1)
        self.assertEqual(token["max_process_count"],1)
        self.assertEqual(token["max_child_process_count"],0)
        self.assertTrue(token["requires_atomic_authorization_consumption_with_launch"])
        self.assertTrue(token["requires_atomic_token_consumption_with_launch"])
        self.assertTrue(token["requires_final_pre_spawn_revalidation"])
        for f in ("token_implemented","token_issued","token_signed","token_persisted",
                  "token_consumed","owner_authorization_consumed","launch_authorized",
                  "build_authorized","build_started","process_spawned"):
            self.assertFalse(token[f],f)

    def test_token_lifetime_over_fifteen_seconds_blocks(self):
        c=self.contract();r=self.review(c)
        token=build_unissued_token_template(
            c,r,token_id="build-token://first-prod-0001",token_nonce_digest=D("7"),
            issued_at="2026-10-08T16:10:06+00:00",expires_at="2026-10-08T16:10:22+00:00")
        self.assertEqual(token["state"],"BLOCKED")
        self.assertIn("BUILD_TOKEN_LIFETIME_TOO_LONG",token["blockers"])

    def test_future_token_attestation_shape_remains_untrusted(self):
        c=self.contract();r=self.review(c)
        token=build_unissued_token_template(
            c,r,token_id="build-token://first-prod-0001",token_nonce_digest=D("7"),
            issued_at="2026-10-08T16:10:06+00:00",expires_at="2026-10-08T16:10:20+00:00")
        att=validate_future_token_issuance_attestation_shape(
            token,token_digest=D("1"),token_signature_digest=D("2"),
            token_signer_manifest_digest=token["token_signer_manifest_digest"],
            token_record_digest=D("3"),token_nonce_record_digest=D("4"),
            write_receipt_digest=D("5"),cas_observation_digest=D("6"),
            read_after_write_observation_digest=D("7"),reopen_observation_digest=D("8"),
            owner_authorization_consumed=False,token_consumed=False,
            caller_claims_token_trusted=False)
        self.assertEqual(att["state"],READY_TOKEN_ATTESTATION_SHAPE_STATE,att["blockers"])
        self.assertTrue(att["shape_valid"])
        for f in ("token_signature_verified","token_persisted_trusted","token_nonce_single_use_verified",
                  "cas_verified","read_after_write_verified","reopen_verified",
                  "final_pre_spawn_revalidation_verified","owner_authorization_consumed",
                  "token_consumed","launch_authorized","build_authorized","build_started","process_spawned"):
            self.assertFalse(att[f],f)

    def test_caller_cannot_self_assert_token_trust(self):
        c=self.contract();r=self.review(c)
        token=build_unissued_token_template(
            c,r,token_id="build-token://first-prod-0001",token_nonce_digest=D("7"),
            issued_at="2026-10-08T16:10:06+00:00",expires_at="2026-10-08T16:10:20+00:00")
        att=validate_future_token_issuance_attestation_shape(
            token,token_digest=D("1"),token_signature_digest=D("2"),
            token_signer_manifest_digest=token["token_signer_manifest_digest"],
            token_record_digest=D("3"),token_nonce_record_digest=D("4"),
            write_receipt_digest=D("5"),cas_observation_digest=D("6"),
            read_after_write_observation_digest=D("7"),reopen_observation_digest=D("8"),
            owner_authorization_consumed=False,token_consumed=False,
            caller_claims_token_trusted=True)
        self.assertEqual(att["state"],"BLOCKED")
        self.assertIn("CALLER_BUILD_TOKEN_TRUST_CLAIM_NOT_ACCEPTED",att["blockers"])

    def test_implementation_review_stops_before_spawn(self):
        c=self.contract();r=self.review(c)
        token=build_unissued_token_template(
            c,r,token_id="build-token://first-prod-0001",token_nonce_digest=D("7"),
            issued_at="2026-10-08T16:10:06+00:00",expires_at="2026-10-08T16:10:20+00:00")
        review=build_implementation_review(
            c,token,prelaunch_verifier_source_digest=D("1"),token_signer_source_digest=D("2"),
            token_store_writer_design_digest=D("3"),atomic_launch_consumer_design_digest=D("4"),
            final_pre_spawn_revalidation_design_digest=D("5"))
        self.assertEqual(review["state"],READY_REVIEW_STATE,review["blockers"])
        for f in ("prelaunch_verifier_implemented","prelaunch_revalidation_executed",
                  "token_signer_implemented","token_store_writer_implemented",
                  "atomic_launch_consumer_implemented","final_pre_spawn_revalidation_implemented",
                  "build_token_implemented","build_token_issued","build_token_signed",
                  "build_token_persisted","build_token_consumed","owner_authorization_consumed",
                  "launch_authorized","build_authorized","build_started","process_spawned",
                  "filesystem_modified","network_called","github_api_called",
                  "live_repository_mutation_performed"):
            self.assertFalse(review[f],f)

    def test_policy_is_fail_closed(self):
        p=build_token_prelaunch_policy()
        self.assertEqual(p["max_prelaunch_snapshot_age_seconds"],10)
        self.assertEqual(p["max_build_token_lifetime_seconds"],15)
        self.assertTrue(p["prelaunch_revalidation_required"])
        self.assertTrue(p["final_pre_spawn_revalidation_required"])
        self.assertTrue(p["safety_stop_armed_required"])
        self.assertTrue(p["safety_stop_must_not_be_engaged"])
        self.assertTrue(p["circuit_breaker_armed_required"])
        self.assertTrue(p["circuit_breaker_healthy_required"])
        self.assertTrue(p["token_single_use_required"])
        self.assertTrue(p["atomic_owner_authorization_consumption_with_launch_required"])
        self.assertTrue(p["atomic_token_consumption_with_launch_required"])
        self.assertFalse(p["caller_prelaunch_claim_is_authority"])
        self.assertFalse(p["caller_token_trust_claim_is_authority"])
        self.assertFalse(p["generic_chat_is_launch_authority"])
        for f in ("prelaunch_revalidation_implemented","prelaunch_revalidation_executed",
                  "prelaunch_external_trust_verified","token_signer_implemented",
                  "build_token_implemented","build_token_issued","build_token_signed",
                  "build_token_persisted","build_token_consumed","owner_authorization_consumed",
                  "launch_authorized","build_authorized","build_started","package_built",
                  "package_installed","process_spawned","filesystem_modified","network_called",
                  "github_api_called","live_repository_mutation_authorized",
                  "live_repository_mutation_performed","production_repository_mutation_performed",
                  "deploy_executed","worker_activated","provider_activated",
                  "production_persistence_activated"):
            self.assertFalse(p[f],f)

if __name__=="__main__":
    unittest.main()
