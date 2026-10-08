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
    PURPOSE,
    build_owner_signature_attestation,
    build_explicit_owner_mutation_decision,
    build_repository_mutation_authorization_receipt,
    build_authorization_receipt_persistence_attestation,
)
from atlasquant_aion_repository_mutation_executor_boundary_v1 import (
    build_authorization_consumption_candidate,
    build_atomic_consumption_attestation,
    build_repository_mutation_executor_boundary,
)
from atlasquant_aion_signed_github_mutation_adapter_outcome_v1 import (
    FORBIDDEN_ADAPTER_CAPABILITIES,
    build_signed_github_mutation_adapter_attestation,
    build_external_mutation_attempt_observation,
    build_immutable_mutation_outcome_receipt,
)
from atlasquant_aion_github_mutation_outcome_reconciliation_v1 import (
    RECONCILIATION_PURPOSE,
    RECONCILIATION_MECHANISM,
    build_reconciliation_authorization,
    build_authoritative_reconciliation_evidence,
    build_outcome_reconciliation_record,
)
from atlasquant_aion_repository_mutation_terminal_audit_certificate_v1 import (
    build_terminal_audit_certificate,
    build_certificate_persistence_attestation,
    verify_terminal_audit_certificate,
    terminal_audit_certificate_policy,
)


D = lambda c: "sha256:" + (c * 64)


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


class AionRepositoryMutationTerminalAuditCertificateV1Tests(unittest.TestCase):
    def base_chain(self):
        item = next(row for row in STACK if row["number"] == 1015)
        preflight = build_live_merge_step_preflight(
            pr_number=1015,
            requested_mutation="PR_DRAFT_TO_READY",
            observed_main_sha="a" * 40,
            observed_main_tree_sha="b" * 40,
            observed_pr_state="open",
            observed_draft=True,
            observed_mergeable=True,
            observed_base="main",
            observed_head=item["head"],
            observed_head_sha=item["head_sha"],
            observed_files=[{"filename": p} for p in item["files"]],
            observed_workflows=[
                {"name": n, "status": "completed", "conclusion": "success"}
                for n in item["required_workflows"]
            ],
            parent_confirmed_in_main=False,
            current_readiness_digest=D("1"),
            rollback_plan_digest=D("2"),
        )
        challenge = build_owner_authorization_challenge(
            preflight,
            challenge_id="terminal-chain-challenge-1",
            owner_subject="owner://mikael",
            owner_binding_digest=D("3"),
            nonce_digest=D("4"),
            issued_at="2026-10-08T10:00:00+00:00",
            expires_at="2026-10-08T10:02:00+00:00",
        )
        signature = build_owner_signature_attestation(
            challenge,
            owner_key_fingerprint=D("5"),
            signed_challenge_digest=challenge["challenge_digest"],
            signature_attestation_id="terminal-chain-signature-1",
            verified_owner_signature=True,
            verified_active_trust_root=True,
            signer_owner_subject_match=True,
            signer_owner_binding_match=True,
            persistent_nonce_replay_guard_verified=True,
            challenge_nonce_single_use_claimed=True,
            signature_verified_at="2026-10-08T10:00:10+00:00",
        )
        decision_material = {
            "decision_id": "terminal-chain-decision-1",
            "purpose": PURPOSE,
            "decision": "AUTHORIZE_REPOSITORY_MUTATION",
            "challenge_digest": challenge["challenge_digest"],
            "signature_attestation_digest": signature[
                "signature_attestation_digest"
            ],
            "pr_number": challenge["pr_number"],
            "requested_mutation": challenge["requested_mutation"],
            "owner_subject": challenge["owner_subject"],
            "owner_binding_digest": challenge["owner_binding_digest"],
            "owner_key_fingerprint": D("5"),
            "decision_nonce_digest": D("6"),
            "issued_at": "2026-10-08T10:00:15+00:00",
            "expires_at": "2026-10-08T10:01:45+00:00",
        }
        decision = build_explicit_owner_mutation_decision(
            challenge,
            signature,
            decision_id="terminal-chain-decision-1",
            decision="AUTHORIZE_REPOSITORY_MUTATION",
            signed_decision_digest=digest(decision_material),
            decision_nonce_digest=D("6"),
            owner_key_fingerprint=D("5"),
            verified_owner_decision_signature=True,
            verified_active_trust_root=True,
            persistent_decision_nonce_replay_guard_verified=True,
            decision_nonce_single_use_claimed=True,
            issued_at="2026-10-08T10:00:15+00:00",
            expires_at="2026-10-08T10:01:45+00:00",
            now="2026-10-08T10:00:20+00:00",
        )
        authorization = build_repository_mutation_authorization_receipt(
            challenge,
            signature,
            decision,
            preflight,
            receipt_id="terminal-chain-authorization-1",
            authorization_nonce_digest=D("7"),
            persistent_authorization_nonce_replay_guard_verified=True,
            authorization_nonce_single_use_claimed=True,
            issued_at="2026-10-08T10:00:25+00:00",
            expires_at="2026-10-08T10:01:30+00:00",
            now="2026-10-08T10:00:30+00:00",
        )
        persistence = build_authorization_receipt_persistence_attestation(
            authorization,
            persisted_record_digest=D("8"),
            writer_attestation_digest=D("9"),
            persisted_at="2026-10-08T10:00:35+00:00",
            read_after_write_verified=True,
            atomic_write_or_cas_verified=True,
            writer_identity_verified=True,
            now="2026-10-08T10:00:40+00:00",
        )
        candidate = build_authorization_consumption_candidate(
            authorization,
            persistence,
            preflight,
            execution_attempt_id="terminal-chain-attempt-1",
            repository_ref_digest=D("a"),
            idempotency_key_digest=D("b"),
            effect_key_digest=D("c"),
            lease_identity_digest=D("d"),
            checked_at="2026-10-08T10:00:45+00:00",
            now="2026-10-08T10:00:50+00:00",
        )
        consumption = build_atomic_consumption_attestation(
            candidate,
            consumption_record_digest=D("e"),
            writer_attestation_digest=D("f"),
            consumed_at="2026-10-08T10:00:52+00:00",
            atomic_compare_and_set_verified=True,
            read_after_write_verified=True,
            writer_identity_verified=True,
            prior_unconsumed_state_verified=True,
            future_reuse_rejection_verified=True,
        )
        boundary = build_repository_mutation_executor_boundary(
            candidate,
            consumption,
            adapter_manifest_digest=D("1"),
            adapter_build_digest=D("2"),
            signed_adapter_verified=True,
            repository_identity_match=True,
            least_privilege_scope_verified=True,
            target_pr_match=True,
            requested_mutation_match=True,
            main_sha_match=True,
            head_sha_match=True,
            base_branch_match=True,
            file_delta_match=True,
            workflow_snapshot_match=True,
            checked_at="2026-10-08T10:00:55+00:00",
            now="2026-10-08T10:01:00+00:00",
        )
        adapter = build_signed_github_mutation_adapter_attestation(
            boundary,
            adapter_id="github-terminal-adapter-v1",
            adapter_version="1.0.0",
            adapter_manifest_digest=D("1"),
            adapter_build_digest=D("2"),
            supply_chain_evidence_digest=D("3"),
            repository_identity_digest=D("4"),
            capability_scope_digest=D("5"),
            response_schema_digest=D("6"),
            error_taxonomy_digest=D("7"),
            postcondition_policy_digest=D("8"),
            signed_adapter_verified=True,
            trusted_signing_root_verified=True,
            repository_identity_match=True,
            least_privilege_scope_verified=True,
            logical_operation_allowlist=["SET_PR_READY_FOR_REVIEW"],
            forbidden_capabilities_declared=list(
                FORBIDDEN_ADAPTER_CAPABILITIES
            ),
            checked_at="2026-10-08T10:01:01+00:00",
        )
        attempt = build_external_mutation_attempt_observation(
            boundary,
            adapter,
            observation_id="terminal-attempt-observation-1",
            request_correlation_digest=D("9"),
            transport_observation_digest=D("a"),
            provider_request_identity_digest=D("b"),
            attempted_at="2026-10-08T10:01:02+00:00",
            observed_at="2026-10-08T10:01:05+00:00",
            trusted_adapter_observation_verified=True,
            request_dispatch_observed=True,
            network_transport_observed=True,
        )
        for row in (
            preflight, challenge, signature, decision, authorization,
            persistence, candidate, consumption, boundary, adapter, attempt,
        ):
            self.assertNotEqual(row.get("state"), "BLOCKED", row.get("blockers"))
        return {
            "preflight": preflight,
            "authorization": authorization,
            "persistence": persistence,
            "consumption": consumption,
            "boundary": boundary,
            "adapter": adapter,
            "attempt": attempt,
        }

    def success_outcome(self, chain=None):
        chain = chain or self.base_chain()
        outcome = build_immutable_mutation_outcome_receipt(
            chain["attempt"],
            receipt_id="terminal-success-outcome-1",
            declared_outcome="CONFIRMED_SUCCESS",
            provider_response_evidence_digest=D("c"),
            postcondition_evidence_digest=D("d"),
            terminal_failure_evidence_digest="",
            ambiguity_evidence_digest="",
            ambiguity_triggers=[],
            provider_response_received=True,
            response_correlation_verified=True,
            response_authenticity_verified=True,
            response_schema_verified=True,
            provider_success_semantics_verified=True,
            provider_terminal_failure_semantics_verified=False,
            repository_postcondition_readback_verified=True,
            expected_postcondition_match=True,
            authoritative_no_effect_or_terminal_rejection_verified=False,
            evidence_complete=True,
            observed_at="2026-10-08T10:01:07+00:00",
        )
        self.assertEqual(
            outcome["outcome"],
            "CONFIRMED_SUCCESS",
            outcome["blockers"],
        )
        return outcome

    def failure_outcome(self, chain=None):
        chain = chain or self.base_chain()
        outcome = build_immutable_mutation_outcome_receipt(
            chain["attempt"],
            receipt_id="terminal-failure-outcome-1",
            declared_outcome="CONFIRMED_TERMINAL_FAILURE",
            provider_response_evidence_digest=D("c"),
            postcondition_evidence_digest="",
            terminal_failure_evidence_digest=D("d"),
            ambiguity_evidence_digest="",
            ambiguity_triggers=[],
            provider_response_received=True,
            response_correlation_verified=True,
            response_authenticity_verified=True,
            response_schema_verified=True,
            provider_success_semantics_verified=False,
            provider_terminal_failure_semantics_verified=True,
            repository_postcondition_readback_verified=False,
            expected_postcondition_match=False,
            authoritative_no_effect_or_terminal_rejection_verified=True,
            evidence_complete=True,
            observed_at="2026-10-08T10:01:07+00:00",
        )
        self.assertEqual(
            outcome["outcome"],
            "CONFIRMED_TERMINAL_FAILURE",
            outcome["blockers"],
        )
        return outcome

    def unknown_outcome(self, chain=None):
        chain = chain or self.base_chain()
        outcome = build_immutable_mutation_outcome_receipt(
            chain["attempt"],
            receipt_id="terminal-unknown-outcome-1",
            declared_outcome="OUTCOME_UNKNOWN",
            provider_response_evidence_digest=D("c"),
            postcondition_evidence_digest="",
            terminal_failure_evidence_digest="",
            ambiguity_evidence_digest=D("d"),
            ambiguity_triggers=["TIMEOUT_AFTER_DISPATCH"],
            provider_response_received=False,
            response_correlation_verified=False,
            response_authenticity_verified=False,
            response_schema_verified=False,
            provider_success_semantics_verified=False,
            provider_terminal_failure_semantics_verified=False,
            repository_postcondition_readback_verified=False,
            expected_postcondition_match=False,
            authoritative_no_effect_or_terminal_rejection_verified=False,
            evidence_complete=True,
            observed_at="2026-10-08T10:01:07+00:00",
        )
        self.assertEqual(outcome["outcome"], "OUTCOME_UNKNOWN")
        return outcome

    def reconciliation_authorization(self, outcome):
        signed_material = {
            "authorization_id": "terminal-recon-auth-1",
            "purpose": RECONCILIATION_PURPOSE,
            "mechanism": RECONCILIATION_MECHANISM,
            "decision": "AUTHORIZE_GITHUB_MUTATION_RECONCILIATION",
            "owner_subject": "owner://mikael",
            "owner_binding_digest": D("e"),
            "owner_key_fingerprint": D("f"),
            "nonce_digest": D("1"),
            "original_outcome_receipt_digest": outcome[
                "outcome_receipt_digest"
            ],
            "execution_attempt_id": outcome["execution_attempt_id"],
            "pr_number": outcome["pr_number"],
            "requested_mutation": outcome["requested_mutation"],
            "request_correlation_digest": outcome[
                "request_correlation_digest"
            ],
            "idempotency_key_digest": outcome["idempotency_key_digest"],
            "effect_key_digest": outcome["effect_key_digest"],
            "issued_at": "2026-10-08T10:02:00+00:00",
            "expires_at": "2026-10-08T10:03:30+00:00",
        }
        auth = build_reconciliation_authorization(
            outcome,
            authorization_id="terminal-recon-auth-1",
            decision="AUTHORIZE_GITHUB_MUTATION_RECONCILIATION",
            owner_subject="owner://mikael",
            owner_binding_digest=D("e"),
            owner_key_fingerprint=D("f"),
            nonce_digest=D("1"),
            signed_authorization_digest=digest(signed_material),
            verified_owner_signature=True,
            verified_active_trust_root=True,
            persistent_nonce_replay_guard_verified=True,
            nonce_single_use_claimed=True,
            issued_at="2026-10-08T10:02:00+00:00",
            expires_at="2026-10-08T10:03:30+00:00",
            now="2026-10-08T10:02:15+00:00",
        )
        self.assertEqual(auth["state"], "RECONCILIATION_AUTHORIZED")
        return auth

    def reconciled(self, outcome, *, success=False, no_effect=False, conflict=False):
        auth = self.reconciliation_authorization(outcome)
        evidence = build_authoritative_reconciliation_evidence(
            outcome,
            auth,
            evidence_id="terminal-recon-evidence-1",
            evidence_classes=["GITHUB_PR_STATE_READBACK"],
            evidence_source_digest=D("2"),
            evidence_set_digest=D("3"),
            repository_observation_digest=D("4"),
            pr_state_evidence_digest=D("5"),
            main_state_evidence_digest=D("6"),
            repository_identity_match=True,
            pr_number_match=True,
            requested_mutation_match=True,
            execution_attempt_id_match=True,
            request_correlation_match=True,
            idempotency_key_match=True,
            effect_key_match=True,
            evidence_source_attested=True,
            evidence_schema_valid=True,
            evidence_authenticity_verified=True,
            evidence_freshness_verified=True,
            evidence_sequence_monotonic=True,
            independent_repository_readback_verified=True,
            success_postcondition_verified=success,
            authoritative_no_effect_verified=no_effect,
            authoritative_terminal_rejection_verified=False,
            conflicting_evidence_present=conflict,
            observed_at="2026-10-08T10:02:20+00:00",
            now="2026-10-08T10:02:25+00:00",
        )
        self.assertEqual(
            evidence["state"],
            "AUTHORITATIVE_RECONCILIATION_EVIDENCE_ATTESTED",
            evidence["blockers"],
        )
        record = build_outcome_reconciliation_record(
            outcome,
            auth,
            evidence,
            reconciliation_id="terminal-reconciliation-record-1",
            evidence_complete=True,
            observed_at="2026-10-08T10:02:30+00:00",
        )
        self.assertEqual(record["state"], "RECONCILIATION_RECORD_READY")
        return record

    def certificate(self, chain, outcome, reconciliation=None, **changes):
        kwargs = {
            "authorization_receipt": chain["authorization"],
            "authorization_persistence": chain["persistence"],
            "consumption_attestation": chain["consumption"],
            "executor_boundary": chain["boundary"],
            "adapter_attestation": chain["adapter"],
            "attempt_observation": chain["attempt"],
            "outcome_receipt": outcome,
            "reconciliation_record": reconciliation,
            "certificate_revision": 1,
            "audit_chain_digest": D("7"),
            "evidence_bundle_digest": D("8"),
            "rollback_plan_digest": D("9"),
            "lineage_evidence_authenticated": True,
            "lineage_evidence_complete": True,
            "unresolved_lineage_conflict_present": False,
        }
        kwargs.update(changes)
        return build_terminal_audit_certificate(**kwargs)

    def test_primary_success_certifies_final_success(self):
        chain = self.base_chain()
        cert = self.certificate(chain, self.success_outcome(chain))
        self.assertEqual(cert["state"], "AUDIT_CERTIFICATE_READY", cert["blockers"])
        self.assertEqual(cert["certificate_outcome"], "CERTIFIED_FINAL_SUCCESS")
        self.assertTrue(cert["terminal_closed"])
        self.assertFalse(cert["open_ambiguous"])
        self.assertFalse(cert["reconciliation_required"])
        self.assertTrue(cert["certificate_is_read_only"])
        self.assertTrue(cert["certificate_is_immutable"])
        self.assertFalse(cert["certificate_is_execution_authorization"])
        self.assertFalse(cert["certificate_authorizes_retry"])
        self.assertFalse(cert["certificate_authorizes_new_attempt"])
        self.assertFalse(cert["certificate_authorizes_repository_mutation"])
        self.assertTrue(verify_terminal_audit_certificate(cert)["valid"])

    def test_primary_terminal_failure_certifies_final_failure(self):
        chain = self.base_chain()
        cert = self.certificate(chain, self.failure_outcome(chain))
        self.assertEqual(
            cert["certificate_outcome"],
            "CERTIFIED_FINAL_TERMINAL_FAILURE",
        )
        self.assertTrue(cert["terminal_closed"])
        self.assertFalse(cert["open_ambiguous"])

    def test_unknown_without_reconciliation_certifies_open_ambiguous(self):
        chain = self.base_chain()
        cert = self.certificate(chain, self.unknown_outcome(chain))
        self.assertEqual(
            cert["certificate_outcome"],
            "CERTIFIED_OPEN_AMBIGUOUS",
        )
        self.assertFalse(cert["terminal_closed"])
        self.assertTrue(cert["open_ambiguous"])
        self.assertTrue(cert["reconciliation_required"])
        self.assertFalse(cert["certificate_authorizes_retry"])
        self.assertFalse(cert["certificate_authorizes_new_attempt"])

    def test_reconciled_success_certifies_final_success(self):
        chain = self.base_chain()
        outcome = self.unknown_outcome(chain)
        recon = self.reconciled(outcome, success=True)
        cert = self.certificate(chain, outcome, recon)
        self.assertEqual(cert["certificate_outcome"], "CERTIFIED_FINAL_SUCCESS")
        self.assertTrue(cert["terminal_closed"])
        self.assertTrue(cert["manifest"]["reconciliation_digest"].startswith("sha256:"))

    def test_reconciled_no_effect_certifies_terminal_failure_not_retry(self):
        chain = self.base_chain()
        outcome = self.unknown_outcome(chain)
        recon = self.reconciled(outcome, no_effect=True)
        cert = self.certificate(chain, outcome, recon)
        self.assertEqual(
            cert["certificate_outcome"],
            "CERTIFIED_FINAL_TERMINAL_FAILURE",
        )
        self.assertTrue(cert["terminal_closed"])
        self.assertFalse(cert["certificate_authorizes_retry"])
        self.assertFalse(cert["certificate_authorizes_new_attempt"])

    def test_still_unknown_after_reconciliation_remains_open(self):
        chain = self.base_chain()
        outcome = self.unknown_outcome(chain)
        recon = self.reconciled(outcome, success=True, no_effect=True)
        self.assertEqual(recon["reconciled_outcome"], "STILL_OUTCOME_UNKNOWN")
        cert = self.certificate(chain, outcome, recon)
        self.assertEqual(cert["certificate_outcome"], "CERTIFIED_OPEN_AMBIGUOUS")
        self.assertFalse(cert["terminal_closed"])
        self.assertTrue(cert["reconciliation_required"])

    def test_reconciliation_on_primary_final_outcome_blocks(self):
        chain = self.base_chain()
        success = self.success_outcome(chain)
        fake_recon = {
            "schema": "ATLASQUANT_AION_GITHUB_MUTATION_RECONCILIATION_RECORD_V1",
            "state": "RECONCILIATION_RECORD_READY",
        }
        cert = self.certificate(chain, success, fake_recon)
        self.assertEqual(cert["state"], "BLOCKED")
        self.assertIn(
            "RECONCILIATION_NOT_ALLOWED_FOR_PRIMARY_FINAL_OUTCOME",
            cert["blockers"],
        )

    def test_lineage_tamper_blocks_certificate(self):
        chain = self.base_chain()
        chain["attempt"] = copy.deepcopy(chain["attempt"])
        chain["attempt"]["executor_boundary_digest"] = D("0")
        cert = self.certificate(chain, self.success_outcome(self.base_chain()))
        self.assertEqual(cert["state"], "BLOCKED")
        self.assertIn(
            "ATTEMPT_EXECUTOR_BOUNDARY_BINDING_MISMATCH",
            cert["blockers"],
        )

    def test_unresolved_lineage_conflict_blocks(self):
        chain = self.base_chain()
        cert = self.certificate(
            chain,
            self.success_outcome(chain),
            unresolved_lineage_conflict_present=True,
        )
        self.assertEqual(cert["state"], "BLOCKED")
        self.assertIn("UNRESOLVED_LINEAGE_CONFLICT", cert["blockers"])

    def test_certificate_persistence_is_external_proof_only(self):
        chain = self.base_chain()
        cert = self.certificate(chain, self.success_outcome(chain))
        persistence = build_certificate_persistence_attestation(
            cert,
            persistence_record_digest=D("a"),
            writer_attestation_digest=D("b"),
            read_after_write_verified=True,
            atomic_write_or_cas_verified=True,
            writer_identity_verified=True,
            reopen_consistency_verified=True,
        )
        self.assertEqual(
            persistence["state"],
            "AUDIT_CERTIFICATE_PERSISTENCE_ATTESTED",
            persistence["blockers"],
        )
        self.assertFalse(persistence["persisted_by_this_module"])
        self.assertFalse(persistence["certificate_authorizes_retry"])
        self.assertFalse(
            persistence["certificate_authorizes_repository_mutation"]
        )
        self.assertFalse(persistence["github_api_called_by_this_module"])
        self.assertFalse(persistence["repository_mutation_performed"])

    def test_certificate_tamper_is_detected(self):
        chain = self.base_chain()
        cert = self.certificate(chain, self.success_outcome(chain))
        tampered = copy.deepcopy(cert)
        tampered["manifest"]["certificate_revision"] = 2
        checked = verify_terminal_audit_certificate(tampered)
        self.assertFalse(checked["valid"])
        self.assertIn("CERTIFICATE_DIGEST_MISMATCH", checked["blockers"])

    def test_policy_is_read_only_and_fail_closed(self):
        policy = terminal_audit_certificate_policy()
        self.assertTrue(policy["full_lineage_required"])
        self.assertTrue(policy["authorization_receipt_required"])
        self.assertTrue(policy["authorization_persistence_required"])
        self.assertTrue(policy["authorization_consumption_required"])
        self.assertTrue(policy["executor_boundary_required"])
        self.assertTrue(policy["signed_adapter_attestation_required"])
        self.assertTrue(policy["attempt_observation_required"])
        self.assertTrue(policy["immutable_outcome_receipt_required"])
        self.assertTrue(
            policy["unknown_without_resolution_certifies_open_ambiguous"]
        )
        self.assertTrue(policy["still_unknown_certifies_open_ambiguous"])
        self.assertTrue(policy["original_outcome_receipt_remains_immutable"])
        self.assertTrue(policy["certificate_is_read_only"])
        self.assertTrue(policy["certificate_is_immutable"])
        self.assertFalse(policy["certificate_is_execution_authorization"])
        self.assertFalse(policy["certificate_authorizes_retry"])
        self.assertFalse(policy["certificate_authorizes_reopen"])
        self.assertFalse(policy["certificate_authorizes_new_attempt"])
        self.assertFalse(
            policy["certificate_authorizes_repository_mutation"]
        )
        self.assertFalse(policy["automatic_retry_allowed"])
        self.assertFalse(policy["repository_mutation_replayed"])
        self.assertFalse(policy["github_query_performed_by_this_module"])
        self.assertFalse(policy["github_api_called_by_this_module"])
        self.assertFalse(policy["network_called_by_this_module"])
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
