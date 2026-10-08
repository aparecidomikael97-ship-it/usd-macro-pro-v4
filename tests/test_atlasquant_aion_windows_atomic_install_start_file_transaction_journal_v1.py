import copy
import unittest

from atlasquant_aion_windows_install_token_preinstall_revalidation_v1 import (
    PREINSTALL_CONTRACT_SCHEMA,
    TOKEN_TEMPLATE_SCHEMA,
    READY_PREINSTALL_CONTRACT_STATE,
    READY_TOKEN_TEMPLATE_STATE,
)
from atlasquant_aion_windows_atomic_install_start_file_transaction_journal_v1 import (
    READY_CONTRACT_STATE,
    READY_COMMIT_STATE,
    READY_COMMIT_ATTESTATION_SHAPE,
    READY_JOURNAL_PLAN_STATE,
    READY_JOURNAL_ENTRY_STATE,
    CLASSIFIED_OPERATION_STATE,
    READY_RECOVERY_STATE,
    READY_REVIEW_STATE,
    OP_APPLIED,
    OP_FAILED,
    OP_UNKNOWN,
    build_atomic_install_contract,
    build_install_commitment_candidate,
    validate_future_install_commitment_attestation_shape,
    build_transaction_journal_plan,
    build_journal_entry_candidate,
    classify_future_operation_observation,
    build_recovery_contract,
    build_implementation_review,
    atomic_install_policy,
)

D=lambda c:"sha256:"+(c*64)

class AtomicInstallStartFileTransactionJournalV1Tests(unittest.TestCase):
    def upstream(self):
        pre={
            "schema":PREINSTALL_CONTRACT_SCHEMA,
            "state":READY_PREINSTALL_CONTRACT_STATE,
            "preinstall_contract_digest":D("1"),
        }
        token={
            "schema":TOKEN_TEMPLATE_SCHEMA,
            "state":READY_TOKEN_TEMPLATE_STATE,
            "token_template_digest":D("2"),
            "installation_gate_digest":D("3"),
            "package_attestation_digest":D("4"),
            "installation_manifest_digest":D("5"),
            "installation_target_digest":D("6"),
            "owner_acl_policy_digest":D("7"),
            "startup_policy_digest":D("8"),
            "rollback_archive_digest":D("9"),
            "rollback_manifest_digest":D("a"),
            "uninstall_manifest_digest":D("b"),
            "install_plan_digest":D("c"),
            "owner_install_authorization_verification_digest":D("d"),
            "install_auth_persistence_attestation_digest":D("e"),
            "token_nonce_digest":D("f"),
            "token_issued":False,
            "token_signed":False,
            "token_persisted":False,
            "token_consumed":False,
            "owner_install_authorization_consumed":False,
            "installation_authorized":False,
            "installation_started":False,
            "files_copied":False,
            "package_installed":False,
        }
        return pre,token

    def contract(self):
        pre,token=self.upstream()
        out=build_atomic_install_contract(
            pre,token,
            install_writer_manifest_digest=D("1"),
            journal_writer_manifest_digest=D("2"),
            mutation_executor_manifest_digest=D("3"),
            recovery_policy_digest=D("4"),
        )
        self.assertEqual(out["state"],READY_CONTRACT_STATE,out["blockers"])
        return out

    def commitment(self,contract=None):
        c=contract or self.contract()
        out=build_install_commitment_candidate(
            c,
            installation_id="install://first-prod-install-0001",
            owner_install_authorization_record_digest=D("5"),
            install_token_record_digest=D("6"),
            final_pre_copy_revalidation_digest=D("7"),
            expected_owner_auth_state="UNCONSUMED",
            expected_token_state="UNCONSUMED",
            expected_pre_install_revision=20,
        )
        self.assertEqual(out["state"],READY_COMMIT_STATE,out["blockers"])
        return out

    def operations(self):
        return [
            {
                "operation_id":"op://001-copy-runtime",
                "operation_kind":"COPY_NEW_FILE",
                "target_digest":D("1"),
                "before_state_digest":D("2"),
                "intended_after_state_digest":D("3"),
                "rollback_action_digest":D("4"),
                "source_artifact_digest":D("5"),
            },
            {
                "operation_id":"op://002-replace-config",
                "operation_kind":"REPLACE_EXISTING_FILE",
                "target_digest":D("6"),
                "before_state_digest":D("7"),
                "intended_after_state_digest":D("8"),
                "rollback_action_digest":D("9"),
                "source_artifact_digest":D("a"),
            },
            {
                "operation_id":"op://003-owner-acl",
                "operation_kind":"SET_OWNER_ACL",
                "target_digest":D("b"),
                "before_state_digest":D("c"),
                "intended_after_state_digest":D("d"),
                "rollback_action_digest":D("e"),
                "source_artifact_digest":D("f"),
            },
            {
                "operation_id":"op://004-startup",
                "operation_kind":"CREATE_STARTUP_ENTRY",
                "target_digest":D("1"),
                "before_state_digest":D("2"),
                "intended_after_state_digest":D("3"),
                "rollback_action_digest":D("4"),
                "source_artifact_digest":D("5"),
            },
        ]

    def plan(self):
        c=self.contract();commit=self.commitment(c)
        plan=build_transaction_journal_plan(c,commit,self.operations())
        self.assertEqual(plan["state"],READY_JOURNAL_PLAN_STATE,plan["blockers"])
        return c,commit,plan

    def first_entry(self):
        *_,plan=self.plan()
        entry=build_journal_entry_candidate(
            plan,
            sequence=1,
            previous_entry_digest=plan["journal_genesis_digest"],
        )
        self.assertEqual(entry["state"],READY_JOURNAL_ENTRY_STATE,entry["blockers"])
        return entry

    def test_contract_uses_write_ahead_journal_and_no_fake_fs_atomicity(self):
        c=self.contract()
        self.assertTrue(c["write_ahead_install_commit_required"])
        self.assertTrue(c["owner_authorization_and_token_consumed_in_same_cas_required"])
        self.assertFalse(c["filesystem_mutation_in_database_transaction_claim_allowed"])
        self.assertTrue(c["journal_append_only_required"])
        self.assertTrue(c["one_mutation_at_a_time_required"])
        self.assertTrue(c["before_state_capture_required"])
        self.assertTrue(c["after_state_readback_required"])
        self.assertTrue(c["rollback_binding_required_for_every_mutation"])
        self.assertFalse(c["automatic_forward_retry_after_unknown_allowed"])
        self.assertFalse(c["automatic_forward_continue_after_unknown_allowed"])
        self.assertTrue(c["separate_reconciliation_required"])
        for f in (
            "install_commitment_written","owner_install_authorization_consumed",
            "install_token_consumed","journal_persisted","installation_started",
            "files_copied","filesystem_modified","windows_acl_modified",
            "startup_entry_created","package_installed","network_called",
        ):
            self.assertFalse(c[f],f)

    def test_consumed_upstream_token_blocks_contract(self):
        pre,token=self.upstream()
        token["token_consumed"]=True
        out=build_atomic_install_contract(
            pre,token,
            install_writer_manifest_digest=D("1"),
            journal_writer_manifest_digest=D("2"),
            mutation_executor_manifest_digest=D("3"),
            recovery_policy_digest=D("4"),
        )
        self.assertEqual(out["state"],"BLOCKED")
        self.assertIn("UPSTREAM_TOKEN_CONSUMED_MUST_REMAIN_FALSE",out["blockers"])

    def test_commitment_requires_unconsumed_owner_auth_and_token(self):
        c=self.contract()
        cases=(
            ("CONSUMED","UNCONSUMED","OWNER_INSTALL_AUTH_EXPECTED_STATE_MUST_BE_UNCONSUMED"),
            ("UNCONSUMED","CONSUMED","INSTALL_TOKEN_EXPECTED_STATE_MUST_BE_UNCONSUMED"),
        )
        for owner_state,token_state,expected in cases:
            out=build_install_commitment_candidate(
                c,
                installation_id="install://first-prod-install-0001",
                owner_install_authorization_record_digest=D("5"),
                install_token_record_digest=D("6"),
                final_pre_copy_revalidation_digest=D("7"),
                expected_owner_auth_state=owner_state,
                expected_token_state=token_state,
                expected_pre_install_revision=20,
            )
            self.assertEqual(out["state"],"BLOCKED")
            self.assertIn(expected,out["blockers"])

    def test_commit_candidate_describes_atomic_consumption_but_writes_nothing(self):
        c=self.commitment()
        self.assertTrue(c["atomic_compare_and_set_required"])
        self.assertTrue(c["owner_install_authorization_consumed_if_written"])
        self.assertTrue(c["install_token_consumed_if_written"])
        self.assertTrue(c["install_record_persisted_if_written"])
        self.assertEqual(c["post_commit_owner_auth_state"],"CONSUMED_FOR_INSTALL")
        self.assertEqual(c["post_commit_token_state"],"CONSUMED_FOR_INSTALL")
        self.assertEqual(c["post_commit_install_state"],"INSTALL_COMMITTED")
        self.assertFalse(c["install_commitment_written"])
        self.assertFalse(c["owner_install_authorization_consumed"])
        self.assertFalse(c["install_token_consumed"])
        self.assertFalse(c["installation_started"])
        self.assertFalse(c["files_copied"])

    def test_commit_attestation_shape_is_untrusted_and_self_claim_blocks(self):
        c=self.commitment()
        common=dict(
            install_commitment_record_digest=D("1"),
            writer_manifest_digest=D("2"),
            write_receipt_digest=D("3"),
            cas_observation_digest=D("4"),
            read_after_write_observation_digest=D("5"),
            reopen_observation_digest=D("6"),
            owner_install_authorization_consumption_observation_digest=D("7"),
            install_token_consumption_observation_digest=D("8"),
        )
        out=validate_future_install_commitment_attestation_shape(c,**common)
        self.assertEqual(out["state"],READY_COMMIT_ATTESTATION_SHAPE,out["blockers"])
        self.assertTrue(out["shape_valid"])
        for f in (
            "commitment_persisted_trusted","cas_verified","read_after_write_verified",
            "reopen_verified","owner_install_authorization_consumption_verified",
            "install_token_consumption_verified","journal_creation_allowed",
            "installation_started","files_copied",
        ):
            self.assertFalse(out[f],f)
        fake=validate_future_install_commitment_attestation_shape(
            c,**common,caller_claims_commitment_trusted=True
        )
        self.assertEqual(fake["state"],"BLOCKED")
        self.assertIn("CALLER_INSTALL_COMMITMENT_TRUST_CLAIM_NOT_ACCEPTED",fake["blockers"])

    def test_journal_plan_is_append_only_and_every_operation_has_rollback(self):
        _,_,plan=self.plan()
        self.assertEqual(plan["operation_count"],4)
        self.assertTrue(plan["append_only_required"])
        self.assertTrue(plan["sequence_strictly_increasing_required"])
        self.assertTrue(plan["before_state_capture_required"])
        self.assertTrue(plan["after_state_readback_required"])
        self.assertTrue(plan["rollback_binding_required"])
        self.assertFalse(plan["operation_reorder_allowed"])
        self.assertFalse(plan["operation_delete_allowed"])
        self.assertFalse(plan["operation_replace_allowed"])
        self.assertFalse(plan["journal_persisted"])
        self.assertFalse(plan["installation_started"])
        self.assertFalse(plan["filesystem_modified"])
        for row in plan["operations"]:
            self.assertTrue(row["rollback_action_digest"].startswith("sha256:"))

    def test_duplicate_operation_or_missing_rollback_blocks_plan(self):
        c=self.contract();commit=self.commitment(c)
        duplicate=self.operations()
        duplicate[1]["operation_id"]=duplicate[0]["operation_id"]
        out=build_transaction_journal_plan(c,commit,duplicate)
        self.assertEqual(out["state"],"BLOCKED")
        self.assertTrue(any(x.startswith("DUPLICATE_JOURNAL_OPERATION_ID:") for x in out["blockers"]))

        missing=self.operations()
        missing[2]["rollback_action_digest"]=""
        out2=build_transaction_journal_plan(c,commit,missing)
        self.assertEqual(out2["state"],"BLOCKED")
        self.assertIn("ROLLBACK_ACTION_DIGEST_REQUIRED:3",out2["blockers"])

    def test_journal_chain_requires_exact_prior_entry(self):
        _,_,plan=self.plan()
        first=build_journal_entry_candidate(
            plan,sequence=1,previous_entry_digest=plan["journal_genesis_digest"]
        )
        self.assertEqual(first["state"],READY_JOURNAL_ENTRY_STATE,first["blockers"])

        second=build_journal_entry_candidate(
            plan,sequence=2,previous_entry=first,
            previous_entry_digest=first["journal_entry_digest"],
        )
        self.assertEqual(second["state"],READY_JOURNAL_ENTRY_STATE,second["blockers"])

        forged=build_journal_entry_candidate(
            plan,sequence=2,previous_entry=first,
            previous_entry_digest=D("0"),
        )
        self.assertEqual(forged["state"],"BLOCKED")
        self.assertIn("PREVIOUS_JOURNAL_ENTRY_DIGEST_MISMATCH",forged["blockers"])

        jumped=copy.deepcopy(first)
        jumped["sequence"]=8
        bad=build_journal_entry_candidate(
            plan,sequence=2,previous_entry=jumped,
            previous_entry_digest=jumped["journal_entry_digest"],
        )
        self.assertEqual(bad["state"],"BLOCKED")
        self.assertIn("PRIOR_JOURNAL_ENTRY_SEQUENCE_MISMATCH",bad["blockers"])

    def test_applied_operation_requires_before_after_write_and_rollback_proof(self):
        e=self.first_entry()
        good=classify_future_operation_observation(
            e,requested_outcome=OP_APPLIED,operation_attempted=True,
            before_state_observation_digest=e["before_state_digest"],
            mutation_write_observation_digest=D("a"),
            after_state_observation_digest=e["intended_after_state_digest"],
            rollback_material_presence_digest=D("b"),
        )
        self.assertEqual(good["state"],CLASSIFIED_OPERATION_STATE,good["blockers"])
        self.assertEqual(good["final_outcome"],OP_APPLIED)
        self.assertTrue(good["operation_applied_confirmed"])
        self.assertTrue(good["forward_progress_allowed"])
        self.assertTrue(good["automatic_continue_allowed"])
        self.assertFalse(good["automatic_retry_allowed"])
        self.assertFalse(good["observation_is_physical_truth_trusted"])

        missing=classify_future_operation_observation(
            e,requested_outcome=OP_APPLIED,operation_attempted=True,
            before_state_observation_digest=e["before_state_digest"],
            mutation_write_observation_digest=D("a"),
            after_state_observation_digest="",
            rollback_material_presence_digest=D("b"),
        )
        self.assertEqual(missing["final_outcome"],OP_UNKNOWN)
        self.assertFalse(missing["forward_progress_allowed"])
        self.assertTrue(missing["reconciliation_required"])
        self.assertTrue(missing["rollback_required"])

    def test_after_state_mismatch_and_ambiguity_become_unknown(self):
        e=self.first_entry()
        mismatch=classify_future_operation_observation(
            e,requested_outcome=OP_APPLIED,operation_attempted=True,
            before_state_observation_digest=e["before_state_digest"],
            mutation_write_observation_digest=D("a"),
            after_state_observation_digest=D("0"),
            rollback_material_presence_digest=D("b"),
        )
        self.assertEqual(mismatch["final_outcome"],OP_UNKNOWN)

        ambiguous=classify_future_operation_observation(
            e,requested_outcome=OP_APPLIED,operation_attempted=True,
            before_state_observation_digest=e["before_state_digest"],
            mutation_write_observation_digest=D("a"),
            after_state_observation_digest=e["intended_after_state_digest"],
            rollback_material_presence_digest=D("b"),
            ambiguity_evidence_digest=D("c"),
        )
        self.assertEqual(ambiguous["final_outcome"],OP_UNKNOWN)
        self.assertFalse(ambiguous["automatic_retry_allowed"])
        self.assertFalse(ambiguous["automatic_continue_allowed"])

    def test_terminal_failure_requires_authoritative_no_write_evidence(self):
        e=self.first_entry()
        good=classify_future_operation_observation(
            e,requested_outcome=OP_FAILED,operation_attempted=True,
            terminal_failure_evidence_digest=D("d"),
        )
        self.assertEqual(good["final_outcome"],OP_FAILED)
        self.assertTrue(good["operation_terminal_failure_confirmed"])
        self.assertTrue(good["rollback_required"])

        uncertain=classify_future_operation_observation(
            e,requested_outcome=OP_FAILED,operation_attempted=True,
            mutation_write_observation_digest=D("e"),
            terminal_failure_evidence_digest=D("d"),
        )
        self.assertEqual(uncertain["final_outcome"],OP_UNKNOWN)

    def test_unknown_requires_reverse_order_recovery_and_no_forward_retry(self):
        _,_,plan=self.plan()
        first=build_journal_entry_candidate(
            plan,sequence=1,previous_entry_digest=plan["journal_genesis_digest"]
        )
        second=build_journal_entry_candidate(
            plan,sequence=2,previous_entry=first,
            previous_entry_digest=first["journal_entry_digest"],
        )
        unknown=classify_future_operation_observation(
            second,requested_outcome=OP_UNKNOWN,operation_attempted=True,
            ambiguity_evidence_digest=D("f"),
        )
        recovery=build_recovery_contract(
            plan,unknown,
            journal_reopen_policy_digest=D("1"),
            filesystem_readback_policy_digest=D("2"),
            rollback_executor_manifest_digest=D("3"),
        )
        self.assertEqual(recovery["state"],READY_RECOVERY_STATE,recovery["blockers"])
        self.assertEqual(recovery["rollback_sequences"],[2,1])
        self.assertTrue(recovery["rollback_reverse_order_required"])
        self.assertFalse(recovery["automatic_forward_retry_allowed"])
        self.assertFalse(recovery["automatic_forward_continue_allowed"])
        self.assertFalse(recovery["new_installation_authorized"])
        self.assertFalse(recovery["rollback_authorized_by_this_contract"])
        self.assertFalse(recovery["rollback_performed"])
        self.assertFalse(recovery["reconciliation_completed"])

    def test_implementation_review_stops_before_first_mutation(self):
        c,_,plan=self.plan()
        review=build_implementation_review(
            c,plan,
            install_commit_writer_source_digest=D("1"),
            journal_writer_source_digest=D("2"),
            mutation_executor_source_digest=D("3"),
            recovery_reconciler_source_digest=D("4"),
        )
        self.assertEqual(review["state"],READY_REVIEW_STATE,review["blockers"])
        for f in (
            "install_commit_writer_implemented","journal_writer_implemented",
            "mutation_executor_implemented","recovery_reconciler_implemented",
            "install_commitment_written","owner_install_authorization_consumed",
            "install_token_consumed","journal_persisted","installation_started",
            "files_copied","filesystem_modified","windows_acl_modified",
            "windows_registry_modified","startup_entry_created","rollback_performed",
            "package_installed","network_called","github_api_called",
        ):
            self.assertFalse(review[f],f)

    def test_policy_is_fail_closed(self):
        p=atomic_install_policy()
        self.assertTrue(p["write_ahead_install_commit_required"])
        self.assertTrue(p["owner_authorization_and_token_consumed_in_same_cas_required"])
        self.assertFalse(p["filesystem_mutation_in_database_transaction_claim_allowed"])
        self.assertTrue(p["journal_append_only_required"])
        self.assertTrue(p["journal_sequence_strict_required"])
        self.assertFalse(p["operation_reorder_allowed"])
        self.assertFalse(p["operation_delete_allowed"])
        self.assertFalse(p["operation_replace_allowed"])
        self.assertTrue(p["one_mutation_at_a_time_required"])
        self.assertTrue(p["before_state_capture_required"])
        self.assertTrue(p["after_state_readback_required"])
        self.assertTrue(p["rollback_binding_required_for_every_mutation"])
        self.assertFalse(p["automatic_forward_retry_after_unknown_allowed"])
        self.assertFalse(p["automatic_forward_continue_after_unknown_allowed"])
        self.assertTrue(p["unknown_requires_reconciliation"])
        self.assertTrue(p["unknown_requires_rollback_review"])
        self.assertTrue(p["terminal_failure_requires_authoritative_evidence"])
        self.assertTrue(p["ambiguity_overrides_requested_success"])
        self.assertTrue(p["rollback_reverse_order_required"])
        self.assertFalse(p["generic_chat_is_install_mutation_authority"])
        for f in (
            "install_commit_writer_implemented","journal_writer_implemented",
            "mutation_executor_implemented","recovery_reconciler_implemented",
            "install_commitment_written","owner_install_authorization_consumed",
            "install_token_consumed","journal_persisted","installation_started",
            "files_copied","filesystem_modified","windows_acl_modified",
            "windows_registry_modified","startup_entry_created","scheduled_task_installed",
            "windows_service_installed","rollback_performed","package_installed",
            "process_spawned","network_called","github_api_called",
            "live_repository_mutation_authorized","live_repository_mutation_performed",
            "production_repository_mutation_performed","deploy_executed",
            "worker_activated","provider_activated","production_persistence_activated",
        ):
            self.assertFalse(p[f],f)

if __name__=="__main__":
    unittest.main()
