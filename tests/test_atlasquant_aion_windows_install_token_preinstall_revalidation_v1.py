import unittest

from atlasquant_aion_windows_package_attestation_persistence_install_auth_gate_v1 import (
    INSTALL_GATE_SCHEMA,
    READY_INSTALL_GATE_STATE,
)
from atlasquant_aion_windows_install_token_preinstall_revalidation_v1 import (
    PREINSTALL_SNAPSHOT_SCHEMA,
    READY_PREINSTALL_CONTRACT_STATE,
    READY_PREINSTALL_SHAPE_STATE,
    READY_TOKEN_TEMPLATE_STATE,
    READY_TOKEN_ATTESTATION_SHAPE_STATE,
    READY_REVIEW_STATE,
    build_preinstall_contract,
    validate_future_preinstall_snapshot_shape,
    build_unissued_install_token_template,
    validate_future_install_token_issuance_attestation_shape,
    build_implementation_review,
    install_token_preinstall_policy,
)

D=lambda c:"sha256:"+(c*64)

class InstallTokenPreinstallRevalidationV1Tests(unittest.TestCase):
    def gate(self):
        return {
            "schema":INSTALL_GATE_SCHEMA,
            "state":READY_INSTALL_GATE_STATE,
            "installation_gate_digest":D("1"),
            "persistence_contract_digest":D("2"),
            "package_attestation_digest":D("3"),
            "installation_manifest_digest":D("4"),
            "archive_digest":D("5"),
            "installation_target_digest":D("6"),
            "owner_acl_policy_digest":D("7"),
            "startup_policy_digest":D("8"),
            "rollback_archive_digest":D("9"),
            "rollback_manifest_digest":D("a"),
            "uninstall_manifest_digest":D("b"),
            "install_plan_digest":D("c"),
            "owner_binding_digest":D("d"),
            "installation_authorized":False,
            "install_token_issued":False,
            "installation_started":False,
            "package_installed":False,
        }

    def contract(self):
        out=build_preinstall_contract(
            self.gate(),
            package_persistence_verifier_digest=D("1"),
            install_authorization_persistence_verifier_digest=D("2"),
            token_signer_manifest_digest=D("3"),
            token_signer_key_fingerprint=D("4"),
            install_writer_manifest_digest=D("5"),
            target_state_verifier_digest=D("6"),
            rollback_verifier_digest=D("7"),
            safety_stop_policy_digest=D("8"),
            circuit_breaker_policy_digest=D("9"),
            preinstall_safety_policy_digest=D("a"),
        )
        self.assertEqual(out["state"],READY_PREINSTALL_CONTRACT_STATE,out["blockers"])
        return out

    def snapshot(self,contract=None,**changes):
        c=contract or self.contract()
        row={
            "schema":PREINSTALL_SNAPSHOT_SCHEMA,
            "state":"PREINSTALL_REVALIDATION_VERIFIED",
            "snapshot_digest":D("1"),
            "installation_gate_digest":c["installation_gate_digest"],
            "persistence_contract_digest":c["persistence_contract_digest"],
            "package_attestation_digest":c["package_attestation_digest"],
            "installation_manifest_digest":c["installation_manifest_digest"],
            "archive_digest":c["archive_digest"],
            "installation_target_digest":c["installation_target_digest"],
            "owner_acl_policy_digest":c["owner_acl_policy_digest"],
            "startup_policy_digest":c["startup_policy_digest"],
            "rollback_archive_digest":c["rollback_archive_digest"],
            "rollback_manifest_digest":c["rollback_manifest_digest"],
            "uninstall_manifest_digest":c["uninstall_manifest_digest"],
            "install_plan_digest":c["install_plan_digest"],
            "owner_binding_digest":c["owner_binding_digest"],
            "safety_stop_policy_digest":c["safety_stop_policy_digest"],
            "circuit_breaker_policy_digest":c["circuit_breaker_policy_digest"],
            "preinstall_safety_policy_digest":c["preinstall_safety_policy_digest"],
            "package_persistence_attestation_digest":D("2"),
            "package_reopen_observation_digest":D("3"),
            "owner_install_authorization_verification_digest":D("4"),
            "install_auth_persistence_attestation_digest":D("5"),
            "install_auth_reopen_observation_digest":D("6"),
            "nonce_registry_record_digest":D("7"),
            "nonce_replay_guard_observation_digest":D("8"),
            "nonce_single_use_observation_digest":D("9"),
            "target_state_observation_digest":D("a"),
            "disk_space_observation_digest":D("b"),
            "windows_version_observation_digest":D("c"),
            "acl_preflight_observation_digest":D("d"),
            "startup_preflight_observation_digest":D("e"),
            "rollback_material_observation_digest":D("f"),
            "uninstall_material_observation_digest":D("1"),
            "install_plan_observation_digest":D("2"),
            "safety_stop_observation_digest":D("3"),
            "circuit_breaker_observation_digest":D("4"),
            "safety_state_digest":D("5"),
            "package_attestation_reverified":True,
            "package_persistence_reverified":True,
            "package_reopen_reverified":True,
            "owner_install_signature_reverified":True,
            "owner_install_authorization_persistence_reverified":True,
            "owner_install_authorization_reopen_reverified":True,
            "owner_install_authorization_fresh":True,
            "owner_install_authorization_unconsumed":True,
            "persistent_nonce_replay_guard_reverified":True,
            "nonce_single_use_reverified":True,
            "installation_target_reverified":True,
            "installation_target_safe":True,
            "disk_space_reverified":True,
            "minimum_windows_version_reverified":True,
            "owner_acl_policy_reverified":True,
            "startup_policy_reverified":True,
            "rollback_archive_reverified":True,
            "rollback_manifest_reverified":True,
            "uninstall_manifest_reverified":True,
            "install_plan_reverified":True,
            "no_unexpected_existing_files":True,
            "unexpected_existing_file_count":0,
            "safety_stop_armed":True,
            "safety_stop_engaged":False,
            "circuit_breaker_armed":True,
            "circuit_breaker_healthy":True,
            "no_new_safety_blockers":True,
            "authorization_consumed":False,
            "install_token_consumed":False,
            "installation_started":False,
            "captured_at":"2026-10-08T16:40:00+00:00",
        }
        row.update(changes)
        return row

    def review(self,contract=None,snapshot=None,now="2026-10-08T16:40:05+00:00"):
        c=contract or self.contract()
        s=snapshot or self.snapshot(c)
        return validate_future_preinstall_snapshot_shape(c,s,now=now)

    def test_contract_is_final_but_noninstalling(self):
        c=self.contract()
        for field in (
            "preinstall_revalidation_implemented","preinstall_revalidation_executed",
            "external_trust_verified","safety_stop_physically_checked",
            "circuit_breaker_physically_checked","install_token_implemented",
            "install_token_issued","install_token_signed","install_token_consumed",
            "owner_install_authorization_consumed","installation_authorized",
            "installation_started","files_copied","filesystem_modified",
            "windows_acl_modified","windows_registry_modified","startup_entry_created",
            "process_spawned","network_called",
        ):
            self.assertFalse(c[field],field)

    def test_preinstall_shape_can_pass_but_remains_untrusted(self):
        r=self.review()
        self.assertEqual(r["state"],READY_PREINSTALL_SHAPE_STATE,r["blockers"])
        self.assertTrue(r["shape_valid"])
        for field in (
            "external_trust_verified_by_this_module","package_persistence_trusted",
            "install_authorization_persistence_trusted","nonce_state_trusted",
            "target_state_trusted","rollback_state_trusted",
            "safety_stop_state_trusted","circuit_breaker_state_trusted",
            "install_token_issuance_allowed","installation_authorized",
            "installation_started","files_copied",
        ):
            self.assertFalse(r[field],field)

    def test_snapshot_over_ten_seconds_blocks(self):
        r=self.review(now="2026-10-08T16:40:11+00:00")
        self.assertEqual(r["state"],"BLOCKED")
        self.assertIn("PREINSTALL_SNAPSHOT_STALE",r["blockers"])

    def test_binding_drift_blocks(self):
        c=self.contract()
        for field in (
            "package_attestation_digest","installation_manifest_digest",
            "installation_target_digest","owner_acl_policy_digest",
            "startup_policy_digest","rollback_archive_digest",
            "rollback_manifest_digest","uninstall_manifest_digest","install_plan_digest",
        ):
            with self.subTest(field=field):
                r=self.review(c,self.snapshot(c,**{field:D("0")}))
                self.assertEqual(r["state"],"BLOCKED")
                self.assertIn("PREINSTALL_BINDING_MISMATCH:"+field,r["blockers"])

    def test_rollback_uninstall_and_target_safety_are_mandatory(self):
        c=self.contract()
        cases=(
            ({"rollback_archive_reverified":False},"PREINSTALL_REQUIRED_TRUE:rollback_archive_reverified"),
            ({"rollback_manifest_reverified":False},"PREINSTALL_REQUIRED_TRUE:rollback_manifest_reverified"),
            ({"uninstall_manifest_reverified":False},"PREINSTALL_REQUIRED_TRUE:uninstall_manifest_reverified"),
            ({"installation_target_safe":False},"PREINSTALL_REQUIRED_TRUE:installation_target_safe"),
        )
        for changes,expected in cases:
            with self.subTest(expected=expected):
                r=self.review(c,self.snapshot(c,**changes))
                self.assertEqual(r["state"],"BLOCKED")
                self.assertIn(expected,r["blockers"])

    def test_unexpected_existing_files_block(self):
        c=self.contract()
        r=self.review(c,self.snapshot(
            c,no_unexpected_existing_files=False,unexpected_existing_file_count=1
        ))
        self.assertEqual(r["state"],"BLOCKED")
        self.assertIn("PREINSTALL_REQUIRED_TRUE:no_unexpected_existing_files",r["blockers"])
        self.assertIn("UNEXPECTED_EXISTING_INSTALLATION_FILES_FORBIDDEN",r["blockers"])

    def test_safety_stop_and_circuit_breaker_block(self):
        c=self.contract()
        cases=(
            ({"safety_stop_engaged":True},"SAFETY_STOP_MUST_NOT_BE_ENGAGED"),
            ({"safety_stop_armed":False},"PREINSTALL_REQUIRED_TRUE:safety_stop_armed"),
            ({"circuit_breaker_healthy":False},"PREINSTALL_REQUIRED_TRUE:circuit_breaker_healthy"),
        )
        for changes,expected in cases:
            with self.subTest(expected=expected):
                r=self.review(c,self.snapshot(c,**changes))
                self.assertEqual(r["state"],"BLOCKED")
                self.assertIn(expected,r["blockers"])

    def test_consumed_owner_auth_or_token_blocks(self):
        c=self.contract()
        owner=self.review(c,self.snapshot(c,authorization_consumed=True))
        self.assertEqual(owner["state"],"BLOCKED")
        self.assertIn("OWNER_INSTALL_AUTHORIZATION_ALREADY_CONSUMED",owner["blockers"])
        token=self.review(c,self.snapshot(c,install_token_consumed=True))
        self.assertEqual(token["state"],"BLOCKED")
        self.assertIn("INSTALL_TOKEN_ALREADY_CONSUMED",token["blockers"])

    def test_unissued_install_token_is_single_use_and_short_lived(self):
        c=self.contract();r=self.review(c)
        token=build_unissued_install_token_template(
            c,r,token_id="install-token://first-prod-install-0001",
            token_nonce_digest=D("6"),
            issued_at="2026-10-08T16:40:06+00:00",
            expires_at="2026-10-08T16:40:20+00:00",
        )
        self.assertEqual(token["state"],READY_TOKEN_TEMPLATE_STATE,token["blockers"])
        self.assertTrue(token["single_use"])
        self.assertEqual(token["max_uses"],1)
        self.assertEqual(token["max_installation_sessions"],1)
        self.assertEqual(token["max_installation_targets"],1)
        self.assertTrue(token["requires_atomic_owner_authorization_consumption_with_install_start"])
        self.assertTrue(token["requires_atomic_token_consumption_with_install_start"])
        self.assertTrue(token["requires_final_pre_copy_revalidation"])
        for f in (
            "token_implemented","token_issued","token_signed","token_persisted",
            "token_consumed","owner_install_authorization_consumed",
            "installation_authorized","installation_started","files_copied","package_installed",
        ):
            self.assertFalse(token[f],f)

    def test_install_token_lifetime_over_fifteen_seconds_blocks(self):
        c=self.contract();r=self.review(c)
        token=build_unissued_install_token_template(
            c,r,token_id="install-token://first-prod-install-0001",
            token_nonce_digest=D("6"),
            issued_at="2026-10-08T16:40:06+00:00",
            expires_at="2026-10-08T16:40:22+00:00",
        )
        self.assertEqual(token["state"],"BLOCKED")
        self.assertIn("INSTALL_TOKEN_LIFETIME_TOO_LONG",token["blockers"])

    def test_token_issuance_attestation_remains_untrusted(self):
        c=self.contract();r=self.review(c)
        token=build_unissued_install_token_template(
            c,r,token_id="install-token://first-prod-install-0001",
            token_nonce_digest=D("6"),
            issued_at="2026-10-08T16:40:06+00:00",
            expires_at="2026-10-08T16:40:20+00:00",
        )
        att=validate_future_install_token_issuance_attestation_shape(
            token,
            token_digest=D("1"),token_signature_digest=D("2"),
            token_signer_manifest_digest=token["token_signer_manifest_digest"],
            token_record_digest=D("3"),token_nonce_record_digest=D("4"),
            write_receipt_digest=D("5"),cas_observation_digest=D("6"),
            read_after_write_observation_digest=D("7"),reopen_observation_digest=D("8"),
            owner_install_authorization_consumed=False,token_consumed=False,
            caller_claims_token_trusted=False,
        )
        self.assertEqual(att["state"],READY_TOKEN_ATTESTATION_SHAPE_STATE,att["blockers"])
        self.assertTrue(att["shape_valid"])
        for f in (
            "token_signature_verified","token_persisted_trusted",
            "token_nonce_single_use_verified","cas_verified","read_after_write_verified",
            "reopen_verified","final_pre_copy_revalidation_verified",
            "owner_install_authorization_consumed","token_consumed",
            "installation_authorized","installation_started","files_copied","package_installed",
        ):
            self.assertFalse(att[f],f)

    def test_self_asserted_token_trust_and_consumed_states_block(self):
        c=self.contract();r=self.review(c)
        token=build_unissued_install_token_template(
            c,r,token_id="install-token://first-prod-install-0001",
            token_nonce_digest=D("6"),
            issued_at="2026-10-08T16:40:06+00:00",
            expires_at="2026-10-08T16:40:20+00:00",
        )
        common=dict(
            token_template=token,
            token_digest=D("1"),token_signature_digest=D("2"),
            token_signer_manifest_digest=token["token_signer_manifest_digest"],
            token_record_digest=D("3"),token_nonce_record_digest=D("4"),
            write_receipt_digest=D("5"),cas_observation_digest=D("6"),
            read_after_write_observation_digest=D("7"),reopen_observation_digest=D("8"),
        )
        fake=validate_future_install_token_issuance_attestation_shape(
            **common,owner_install_authorization_consumed=False,token_consumed=False,
            caller_claims_token_trusted=True,
        )
        self.assertEqual(fake["state"],"BLOCKED")
        self.assertIn("CALLER_INSTALL_TOKEN_TRUST_CLAIM_NOT_ACCEPTED",fake["blockers"])
        consumed=validate_future_install_token_issuance_attestation_shape(
            **common,owner_install_authorization_consumed=True,token_consumed=False,
        )
        self.assertEqual(consumed["state"],"BLOCKED")
        self.assertIn(
            "OWNER_INSTALL_AUTHORIZATION_MUST_BE_UNCONSUMED_BEFORE_INSTALL_START",
            consumed["blockers"],
        )

    def test_implementation_review_stops_before_first_copy(self):
        c=self.contract();r=self.review(c)
        token=build_unissued_install_token_template(
            c,r,token_id="install-token://first-prod-install-0001",
            token_nonce_digest=D("6"),
            issued_at="2026-10-08T16:40:06+00:00",
            expires_at="2026-10-08T16:40:20+00:00",
        )
        review=build_implementation_review(
            c,token,
            preinstall_verifier_source_digest=D("1"),
            token_signer_source_digest=D("2"),
            token_store_writer_design_digest=D("3"),
            atomic_install_start_consumer_design_digest=D("4"),
            final_pre_copy_revalidation_design_digest=D("5"),
        )
        self.assertEqual(review["state"],READY_REVIEW_STATE,review["blockers"])
        for f in (
            "preinstall_verifier_implemented","preinstall_revalidation_executed",
            "token_signer_implemented","token_store_writer_implemented",
            "atomic_install_start_consumer_implemented","final_pre_copy_revalidation_implemented",
            "install_token_implemented","install_token_issued","install_token_signed",
            "install_token_persisted","install_token_consumed",
            "owner_install_authorization_consumed","installation_authorized",
            "installation_started","files_copied","package_installed",
            "filesystem_modified","windows_acl_modified","windows_registry_modified",
            "startup_entry_created","network_called","github_api_called",
        ):
            self.assertFalse(review[f],f)

    def test_policy_is_fail_closed(self):
        p=install_token_preinstall_policy()
        self.assertEqual(p["max_preinstall_snapshot_age_seconds"],10)
        self.assertEqual(p["max_install_token_lifetime_seconds"],15)
        self.assertTrue(p["preinstall_revalidation_required"])
        self.assertTrue(p["final_pre_copy_revalidation_required"])
        self.assertTrue(p["same_package_attestation_required"])
        self.assertTrue(p["same_rollback_material_required"])
        self.assertTrue(p["same_uninstall_manifest_required"])
        self.assertTrue(p["target_state_reverification_required"])
        self.assertTrue(p["no_unexpected_existing_files_required"])
        self.assertTrue(p["safety_stop_armed_required"])
        self.assertTrue(p["safety_stop_must_not_be_engaged"])
        self.assertTrue(p["circuit_breaker_healthy_required"])
        self.assertTrue(p["token_single_use_required"])
        self.assertTrue(p["atomic_owner_install_authorization_consumption_with_install_start_required"])
        self.assertTrue(p["atomic_token_consumption_with_install_start_required"])
        self.assertFalse(p["caller_preinstall_claim_is_authority"])
        self.assertFalse(p["caller_token_trust_claim_is_authority"])
        self.assertFalse(p["generic_chat_is_install_start_authority"])
        for f in (
            "preinstall_revalidation_implemented","preinstall_revalidation_executed",
            "preinstall_external_trust_verified","token_signer_implemented",
            "install_token_implemented","install_token_issued","install_token_signed",
            "install_token_persisted","install_token_consumed",
            "owner_install_authorization_consumed","installation_authorized",
            "installation_started","files_copied","package_installed","filesystem_modified",
            "windows_acl_modified","windows_registry_modified","startup_entry_created",
            "scheduled_task_installed","windows_service_installed","process_spawned",
            "network_called","github_api_called","live_repository_mutation_authorized",
            "live_repository_mutation_performed","production_repository_mutation_performed",
            "deploy_executed","worker_activated","provider_activated",
            "production_persistence_activated",
        ):
            self.assertFalse(p[f],f)

if __name__=="__main__":
    unittest.main()
