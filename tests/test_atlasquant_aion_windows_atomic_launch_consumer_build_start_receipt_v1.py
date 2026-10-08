import unittest

from atlasquant_aion_windows_build_token_prelaunch_revalidation_v1 import (
    PRELAUNCH_CONTRACT_SCHEMA,
    TOKEN_TEMPLATE_SCHEMA,
    READY_PRELAUNCH_CONTRACT_STATE,
    READY_TOKEN_TEMPLATE_STATE,
)
from atlasquant_aion_windows_atomic_launch_consumer_build_start_receipt_v1 import (
    READY_CONTRACT_STATE,
    READY_COMMIT_STATE,
    READY_COMMIT_ATTESTATION_SHAPE,
    READY_SPAWN_BOUNDARY_STATE,
    READY_START_RECEIPT_TEMPLATE_STATE,
    READY_RECONCILIATION_STATE,
    READY_REVIEW_STATE,
    START_CONFIRMED,
    START_FAILED,
    START_UNKNOWN,
    build_atomic_launch_contract,
    build_launch_commitment_candidate,
    validate_future_commitment_attestation_shape,
    build_single_spawn_boundary,
    build_unissued_start_receipt_template,
    classify_future_start_observation,
    build_reconciliation_contract,
    build_implementation_review,
    atomic_launch_policy,
)

D=lambda c:"sha256:"+(c*64)

class AtomicLaunchConsumerBuildStartReceiptV1Tests(unittest.TestCase):
    def upstream(self):
        pre={
            "schema":PRELAUNCH_CONTRACT_SCHEMA,
            "state":READY_PRELAUNCH_CONTRACT_STATE,
            "prelaunch_contract_digest":D("1"),
        }
        token={
            "schema":TOKEN_TEMPLATE_SCHEMA,
            "state":READY_TOKEN_TEMPLATE_STATE,
            "token_template_digest":D("2"),
            "gate_contract_digest":D("3"),
            "host_binding_digest":D("4"),
            "owner_authorization_verification_digest":D("5"),
            "authorization_persistence_attestation_digest":D("6"),
            "token_nonce_digest":D("7"),
            "launch_binary_path_digest":D("8"),
            "launch_binary_sha256":D("9"),
            "build_script_sha256":D("a"),
            "token_issued":False,
            "token_signed":False,
            "token_persisted":False,
            "token_consumed":False,
            "owner_authorization_consumed":False,
            "launch_authorized":False,
            "build_authorized":False,
            "build_started":False,
            "process_spawned":False,
        }
        return pre,token

    def contract(self):
        pre,token=self.upstream()
        out=build_atomic_launch_contract(
            pre,token,
            launch_writer_manifest_digest=D("b"),
            launch_consumer_manifest_digest=D("c"),
            start_observer_manifest_digest=D("d"),
            reconciliation_policy_digest=D("e"),
        )
        self.assertEqual(out["state"],READY_CONTRACT_STATE,out["blockers"])
        return out

    def commitment(self):
        out=build_launch_commitment_candidate(
            self.contract(),
            launch_id="launch://first-prod-build-0001",
            owner_authorization_record_digest=D("1"),
            build_token_record_digest=D("2"),
            final_pre_spawn_revalidation_digest=D("3"),
            expected_owner_auth_state="UNCONSUMED",
            expected_token_state="UNCONSUMED",
            expected_pre_launch_revision=10,
        )
        self.assertEqual(out["state"],READY_COMMIT_STATE,out["blockers"])
        return out

    def boundary(self):
        con=self.contract();commit=build_launch_commitment_candidate(
            con,
            launch_id="launch://first-prod-build-0001",
            owner_authorization_record_digest=D("1"),
            build_token_record_digest=D("2"),
            final_pre_spawn_revalidation_digest=D("3"),
            expected_owner_auth_state="UNCONSUMED",
            expected_token_state="UNCONSUMED",
            expected_pre_launch_revision=10,
        )
        boundary=build_single_spawn_boundary(
            con,commit,
            commitment_persistence_attestation_digest=D("4"),
            launch_lease_digest=D("5"),
            process_command_digest=D("6"),
            process_environment_digest=D("7"),
            job_object_policy_digest=D("8"),
            committed_at="2026-10-08T16:20:00+00:00",
            spawn_deadline="2026-10-08T16:20:04+00:00",
        )
        self.assertEqual(boundary["state"],READY_SPAWN_BOUNDARY_STATE,boundary["blockers"])
        return con,commit,boundary

    def receipt(self):
        *_,boundary=self.boundary()
        r=build_unissued_start_receipt_template(boundary)
        self.assertEqual(r["state"],READY_START_RECEIPT_TEMPLATE_STATE,r["blockers"])
        return r

    def test_contract_uses_write_ahead_commit_not_fake_cross_boundary_atomicity(self):
        out=self.contract()
        self.assertTrue(out["write_ahead_launch_commit_required"])
        self.assertTrue(out["owner_authorization_and_token_consumed_in_same_cas_required"])
        self.assertFalse(out["os_spawn_in_database_transaction_claim_allowed"])
        self.assertTrue(out["single_spawn_attempt_required"])
        self.assertFalse(out["automatic_retry_after_commit_allowed"])
        self.assertTrue(out["post_commit_crash_becomes_unknown"])
        self.assertTrue(out["post_commit_timeout_becomes_unknown"])
        self.assertTrue(out["post_commit_ambiguous_spawn_becomes_unknown"])
        self.assertTrue(out["separate_reconciliation_required"])
        for f in ("launch_commitment_written","owner_authorization_consumed","build_token_consumed",
                  "spawn_attempted","build_started","build_authorized","process_spawned",
                  "filesystem_modified","network_called"):
            self.assertFalse(out[f],f)

    def test_upstream_consumed_token_blocks_contract(self):
        pre,token=self.upstream()
        token["token_consumed"]=True
        out=build_atomic_launch_contract(
            pre,token,
            launch_writer_manifest_digest=D("b"),
            launch_consumer_manifest_digest=D("c"),
            start_observer_manifest_digest=D("d"),
            reconciliation_policy_digest=D("e"),
        )
        self.assertEqual(out["state"],"BLOCKED")
        self.assertIn("UPSTREAM_TOKEN_CONSUMED_MUST_REMAIN_FALSE",out["blockers"])

    def test_commitment_requires_both_states_unconsumed(self):
        con=self.contract()
        for field,value,expected in (
            ("expected_owner_auth_state","CONSUMED","OWNER_AUTHORIZATION_EXPECTED_STATE_MUST_BE_UNCONSUMED"),
            ("expected_token_state","CONSUMED","BUILD_TOKEN_EXPECTED_STATE_MUST_BE_UNCONSUMED"),
        ):
            kwargs=dict(
                contract=con,launch_id="launch://first-prod-build-0001",
                owner_authorization_record_digest=D("1"),build_token_record_digest=D("2"),
                final_pre_spawn_revalidation_digest=D("3"),
                expected_owner_auth_state="UNCONSUMED",expected_token_state="UNCONSUMED",
                expected_pre_launch_revision=10)
            kwargs[field]=value
            out=build_launch_commitment_candidate(**kwargs)
            self.assertEqual(out["state"],"BLOCKED")
            self.assertIn(expected,out["blockers"])

    def test_commitment_candidate_describes_atomic_consumption_but_writes_nothing(self):
        c=self.commitment()
        self.assertTrue(c["atomic_compare_and_set_required"])
        self.assertTrue(c["owner_authorization_consumed_if_written"])
        self.assertTrue(c["build_token_consumed_if_written"])
        self.assertTrue(c["launch_record_persisted_if_written"])
        self.assertEqual(c["post_commit_owner_auth_state"],"CONSUMED_FOR_LAUNCH")
        self.assertEqual(c["post_commit_token_state"],"CONSUMED_FOR_LAUNCH")
        self.assertEqual(c["post_commit_launch_state"],"LAUNCH_COMMITTED")
        self.assertFalse(c["launch_commitment_written"])
        self.assertFalse(c["owner_authorization_consumed"])
        self.assertFalse(c["build_token_consumed"])
        self.assertFalse(c["spawn_attempted"])
        self.assertFalse(c["build_started"])

    def test_commitment_attestation_shape_is_untrusted_and_self_claim_blocks(self):
        c=self.commitment()
        common=dict(
            launch_commitment_record_digest=D("1"),writer_manifest_digest=D("2"),
            write_receipt_digest=D("3"),cas_observation_digest=D("4"),
            read_after_write_observation_digest=D("5"),reopen_observation_digest=D("6"),
            owner_authorization_consumption_observation_digest=D("7"),
            token_consumption_observation_digest=D("8"))
        out=validate_future_commitment_attestation_shape(c,**common)
        self.assertEqual(out["state"],READY_COMMIT_ATTESTATION_SHAPE,out["blockers"])
        self.assertTrue(out["shape_valid"])
        for f in ("commitment_persisted_trusted","cas_verified","read_after_write_verified",
                  "reopen_verified","owner_authorization_consumption_verified",
                  "build_token_consumption_verified","spawn_allowed","spawn_attempted","build_started"):
            self.assertFalse(out[f],f)
        bad=validate_future_commitment_attestation_shape(
            c,**common,caller_claims_commitment_trusted=True)
        self.assertEqual(bad["state"],"BLOCKED")
        self.assertIn("CALLER_LAUNCH_COMMITMENT_TRUST_CLAIM_NOT_ACCEPTED",bad["blockers"])

    def test_spawn_window_is_at_most_five_seconds(self):
        con=self.contract();commit=build_launch_commitment_candidate(
            con,launch_id="launch://first-prod-build-0001",
            owner_authorization_record_digest=D("1"),build_token_record_digest=D("2"),
            final_pre_spawn_revalidation_digest=D("3"),
            expected_owner_auth_state="UNCONSUMED",expected_token_state="UNCONSUMED",
            expected_pre_launch_revision=10)
        bad=build_single_spawn_boundary(
            con,commit,commitment_persistence_attestation_digest=D("4"),
            launch_lease_digest=D("5"),process_command_digest=D("6"),
            process_environment_digest=D("7"),job_object_policy_digest=D("8"),
            committed_at="2026-10-08T16:20:00+00:00",
            spawn_deadline="2026-10-08T16:20:06+00:00")
        self.assertEqual(bad["state"],"BLOCKED")
        self.assertIn("SPAWN_WINDOW_TOO_LONG",bad["blockers"])

    def test_single_spawn_boundary_never_spawns(self):
        *_,b=self.boundary()
        self.assertEqual(b["max_spawn_attempts"],1)
        self.assertEqual(b["max_process_count"],1)
        self.assertEqual(b["max_child_process_count"],0)
        self.assertTrue(b["single_spawn_attempt_required"])
        self.assertFalse(b["path_lookup_allowed"])
        self.assertFalse(b["shell_allowed"])
        self.assertFalse(b["child_process_allowed"])
        self.assertFalse(b["automatic_retry_allowed"])
        self.assertFalse(b["spawn_attempted"])
        self.assertFalse(b["process_spawned"])
        self.assertFalse(b["build_started"])

    def test_start_receipt_begins_unissued_and_unobserved(self):
        r=self.receipt()
        self.assertEqual(r["outcome"],"NOT_OBSERVED")
        self.assertFalse(r["spawn_attempted"])
        self.assertFalse(r["process_spawned"])
        self.assertFalse(r["receipt_issued"])
        self.assertFalse(r["receipt_persisted"])
        self.assertFalse(r["build_started"])
        self.assertFalse(r["automatic_retry_allowed"])

    def test_confirmed_success_requires_all_positive_process_evidence(self):
        r=self.receipt()
        good=classify_future_start_observation(
            r,requested_outcome=START_CONFIRMED,spawn_attempted=True,process_spawned=True,
            process_identity_digest=D("1"),process_handle_observation_digest=D("2"),
            job_object_membership_observation_digest=D("3"),image_hash_observation_digest=D("4"),
            command_observation_digest=D("5"))
        self.assertEqual(good["final_outcome"],START_CONFIRMED)
        self.assertTrue(good["build_started_confirmed"])
        self.assertFalse(good["outcome_unknown"])
        self.assertFalse(good["automatic_retry_allowed"])
        self.assertFalse(good["observation_is_physical_truth_trusted"])

        missing=classify_future_start_observation(
            r,requested_outcome=START_CONFIRMED,spawn_attempted=True,process_spawned=True,
            process_identity_digest=D("1"),process_handle_observation_digest=D("2"),
            job_object_membership_observation_digest=D("3"),image_hash_observation_digest=D("4"),
            command_observation_digest="")
        self.assertEqual(missing["final_outcome"],START_UNKNOWN)
        self.assertTrue(missing["outcome_unknown"])
        self.assertTrue(missing["reconciliation_required"])

    def test_ambiguity_wins_over_requested_success(self):
        r=self.receipt()
        out=classify_future_start_observation(
            r,requested_outcome=START_CONFIRMED,spawn_attempted=True,process_spawned=True,
            process_identity_digest=D("1"),process_handle_observation_digest=D("2"),
            job_object_membership_observation_digest=D("3"),image_hash_observation_digest=D("4"),
            command_observation_digest=D("5"),ambiguity_evidence_digest=D("6"))
        self.assertEqual(out["final_outcome"],START_UNKNOWN)
        self.assertTrue(out["reconciliation_required"])
        self.assertFalse(out["automatic_retry_allowed"])

    def test_terminal_failure_requires_authoritative_failure_evidence(self):
        r=self.receipt()
        good=classify_future_start_observation(
            r,requested_outcome=START_FAILED,spawn_attempted=True,process_spawned=False,
            terminal_failure_evidence_digest=D("7"))
        self.assertEqual(good["final_outcome"],START_FAILED)
        self.assertTrue(good["terminal_failure_confirmed"])
        missing=classify_future_start_observation(
            r,requested_outcome=START_FAILED,spawn_attempted=True,process_spawned=False)
        self.assertEqual(missing["final_outcome"],START_UNKNOWN)

    def test_unknown_requires_separate_reconciliation_and_no_retry(self):
        r=self.receipt()
        unknown=classify_future_start_observation(
            r,requested_outcome=START_UNKNOWN,spawn_attempted=True,process_spawned=False,
            ambiguity_evidence_digest=D("8"))
        rec=build_reconciliation_contract(
            unknown,reconciliation_reader_manifest_digest=D("1"),
            process_table_readback_policy_digest=D("2"),
            durable_store_readback_policy_digest=D("3"))
        self.assertEqual(rec["state"],READY_RECONCILIATION_STATE,rec["blockers"])
        self.assertFalse(rec["automatic_retry_allowed"])
        self.assertFalse(rec["new_spawn_attempt_authorized"])
        self.assertFalse(rec["process_readback_executed"])
        self.assertFalse(rec["durable_store_readback_executed"])
        self.assertFalse(rec["reconciliation_completed"])

    def test_implementation_review_stops_before_physical_launch(self):
        con,commit,b=self.boundary();r=build_unissued_start_receipt_template(b)
        review=build_implementation_review(
            con,r,launch_writer_source_digest=D("1"),launch_consumer_source_digest=D("2"),
            start_observer_source_digest=D("3"),reconciliation_source_digest=D("4"))
        self.assertEqual(review["state"],READY_REVIEW_STATE,review["blockers"])
        for f in ("launch_writer_implemented","launch_consumer_implemented","start_observer_implemented",
                  "reconciliation_implemented","launch_commitment_written","owner_authorization_consumed",
                  "build_token_consumed","spawn_attempted","process_spawned","build_started",
                  "start_receipt_issued","start_receipt_persisted","network_called","github_api_called",
                  "live_repository_mutation_performed"):
            self.assertFalse(review[f],f)

    def test_policy_is_fail_closed(self):
        p=atomic_launch_policy()
        self.assertTrue(p["write_ahead_launch_commit_required"])
        self.assertTrue(p["owner_authorization_and_token_consumed_in_same_cas_required"])
        self.assertFalse(p["os_spawn_in_database_transaction_claim_allowed"])
        self.assertTrue(p["single_spawn_attempt_required"])
        self.assertFalse(p["automatic_retry_after_commit_allowed"])
        self.assertTrue(p["post_commit_crash_becomes_unknown"])
        self.assertTrue(p["post_commit_timeout_becomes_unknown"])
        self.assertTrue(p["post_commit_ambiguous_spawn_becomes_unknown"])
        self.assertTrue(p["separate_reconciliation_required"])
        self.assertTrue(p["start_success_requires_positive_process_evidence"])
        self.assertTrue(p["terminal_failure_requires_authoritative_no_process_evidence"])
        self.assertTrue(p["ambiguity_wins_over_requested_success"])
        self.assertFalse(p["generic_chat_is_launch_authority"])
        for f in ("launch_writer_implemented","launch_consumer_implemented","start_observer_implemented",
                  "reconciliation_implemented","launch_commitment_written","owner_authorization_consumed",
                  "build_token_consumed","spawn_attempted","process_spawned","build_started",
                  "start_receipt_issued","start_receipt_persisted","build_authorized","package_built",
                  "package_installed","filesystem_modified","network_called","github_api_called",
                  "live_repository_mutation_authorized","live_repository_mutation_performed",
                  "production_repository_mutation_performed","deploy_executed","worker_activated",
                  "provider_activated","production_persistence_activated"):
            self.assertFalse(p[f],f)

if __name__=="__main__":
    unittest.main()
