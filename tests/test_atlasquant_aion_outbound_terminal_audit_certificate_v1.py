import copy
import unittest

from atlasquant_aion_outbound_terminal_audit_certificate_v1 import (
    build_terminal_finalization,
    build_finalization_persistence_attestation,
    build_audit_seal,
    build_audit_seal_persistence_attestation,
    build_terminal_certificate,
    verify_terminal_certificate,
    terminal_chain_policy,
)
from atlasquant_aion_sealed_provider_outcome_reconciliation_v1 import (
    CALL_BOUNDARY_SCHEMA,
    build_outcome_receipt,
    build_reconciliation_authorization,
    build_outcome_reconciliation,
)


D = lambda c: "sha256:" + (c * 64)
OUTCOME_AT = "2026-10-08T10:01:38+00:00"
RECON_ISSUED = "2026-10-08T10:02:00+00:00"
RECON_EXPIRES = "2026-10-08T10:03:30+00:00"
RECON_NOW = "2026-10-08T10:02:10+00:00"
RECON_OBSERVED = "2026-10-08T10:02:20+00:00"


class AionOutboundTerminalAuditCertificateV1Tests(unittest.TestCase):
    def boundary(self):
        return {
            "schema": CALL_BOUNDARY_SCHEMA,
            "state": "SEALED_SINGLE_CALL_READY",
            "call_boundary_digest": D("1"),
            "call_attempt_id": "call-email-1",
            "execution_id": "execution-email-1",
            "observability_trace_id": "trace-email-1",
            "durable_dispatch_record_digest": D("2"),
            "provider_identity_ref": "provider://email/primary",
            "runtime_build_digest": D("3"),
            "subject_digest": D("4"),
            "requested_action": "SEND_EMAIL",
            "payload_digest": D("5"),
            "idempotency_key_digest": D("6"),
            "effect_key_digest": D("7"),
            "provider_request_correlation_digest": D("8"),
        }

    def success_receipt(self):
        return build_outcome_receipt(
            self.boundary(),
            requested_outcome="CONFIRMED_SUCCESS",
            provider_response_evidence_digest=D("9"),
            observed_at=OUTCOME_AT,
            provider_identity_match=True,
            runtime_build_match=True,
            execution_id_match=True,
            trace_id_match=True,
            provider_request_correlation_match=True,
            idempotency_key_match=True,
            effect_key_match=True,
            response_schema_valid=True,
            response_authenticity_verified=True,
            provider_success_semantics_attested=True,
            effect_confirmation_complete=True,
            expected_postcondition_match=True,
        )

    def unknown_receipt(self):
        return build_outcome_receipt(
            self.boundary(),
            requested_outcome="CONFIRMED_SUCCESS",
            observed_at=OUTCOME_AT,
            ambiguity_triggers=["TIMEOUT_AFTER_DISPATCH"],
            provider_identity_match=True,
            runtime_build_match=True,
            execution_id_match=True,
            trace_id_match=True,
            provider_request_correlation_match=True,
            idempotency_key_match=True,
            effect_key_match=True,
        )

    def reconciled_success(self):
        receipt = self.unknown_receipt()
        auth = build_reconciliation_authorization(
            receipt,
            authorization_id="recon-auth-1",
            decision="AUTHORIZE_OUTCOME_RECONCILIATION",
            owner_binding_digest=D("a"),
            owner_key_fingerprint=D("b"),
            signed_request_digest=D("c"),
            nonce_digest=D("d"),
            verified_owner_signature=True,
            verified_active_trust_root=True,
            persistent_nonce_replay_guard_verified=True,
            nonce_single_use_claimed=True,
            issued_at=RECON_ISSUED,
            expires_at=RECON_EXPIRES,
            now=RECON_NOW,
        )
        recon = build_outcome_reconciliation(
            receipt,
            auth,
            reconciliation_id="recon-1",
            evidence_class="PROVIDER_SIGNED_EVENT_OR_RECEIPT",
            evidence_source_digest=D("e"),
            evidence_record_digest=D("f"),
            provider_identity_match=True,
            execution_id_match=True,
            trace_id_match=True,
            provider_request_correlation_match=True,
            idempotency_key_match=True,
            effect_key_match=True,
            evidence_source_attested=True,
            evidence_schema_valid=True,
            evidence_authenticity_verified=True,
            evidence_freshness_verified=True,
            evidence_sequence_monotonic=True,
            success_evidence_complete=True,
            expected_postcondition_match=True,
            terminal_failure_or_no_effect_evidence_complete=False,
            conflicting_evidence_present=False,
            observed_at=RECON_OBSERVED,
        )
        return receipt, recon

    def finalization(self, receipt=None, reconciliation=None):
        receipt = receipt or self.success_receipt()
        return build_terminal_finalization(
            receipt,
            reconciliation,
            terminal_revision=1,
            terminal_evidence_set_digest=D("a"),
            finops_observation_digest=D("b"),
            execution_id_match=True,
            trace_id_match=True,
            idempotency_key_match=True,
            effect_key_match=True,
            provider_request_correlation_match=True,
            provider_identity_match=True,
            terminal_evidence_authenticated=True,
            terminal_evidence_fresh=True,
            unresolved_conflict_present=False,
            pending_reconciliation=False,
            pending_rollback_or_compensation=False,
            finops_within_policy=True,
            effect_confirmation_complete=True,
            expected_postcondition_match=True,
            no_effect_or_terminal_rejection_complete=False,
        )

    def terminal_chain(self):
        final = self.finalization()
        fp = build_finalization_persistence_attestation(
            final,
            finalization_record_digest=D("c"),
            writer_attestation_digest=D("d"),
            read_after_write_verified=True,
            atomic_write_or_cas_verified=True,
            writer_identity_verified=True,
        )
        seal = build_audit_seal(
            final,
            fp,
            pre_terminal_audit_chain_digest=D("e"),
        )
        sp = build_audit_seal_persistence_attestation(
            seal,
            audit_seal_persistence_record_digest=D("f"),
            writer_attestation_digest=D("1"),
            reopen_consistency_verified=True,
            read_after_write_verified=True,
            writer_identity_verified=True,
        )
        cert = build_terminal_certificate(final, fp, seal, sp)
        return final, fp, seal, sp, cert

    def test_confirmed_success_can_be_finalized_but_not_executed(self):
        final = self.finalization()
        self.assertEqual(final["state"], "READY_FOR_FINALIZATION_PERSISTENCE")
        self.assertEqual(final["final_execution_state"], "FINALIZED_SUCCESS")
        self.assertEqual(final["source_terminal_outcome"], "CONFIRMED_SUCCESS")
        self.assertFalse(final["finalization_is_retry"])
        self.assertFalse(final["execution_reopened"])
        self.assertFalse(final["external_effect_replayed"])
        self.assertFalse(final["provider_called"])
        self.assertFalse(final["network_called"])
        self.assertFalse(final["final_state_persisted_by_this_module"])
        self.assertFalse(final["external_action_executed"])

    def test_unknown_outcome_cannot_be_finalized(self):
        final = self.finalization(receipt=self.unknown_receipt())
        self.assertEqual(final["state"], "BLOCKED")
        self.assertIn("RECONCILIATION_REQUIRED_FOR_UNKNOWN", final["blockers"])
        self.assertIn("UNKNOWN_OUTCOME_CANNOT_BE_FINALIZED", final["blockers"])
        self.assertEqual(final["final_execution_state"], "")

    def test_reconciled_success_can_be_finalized(self):
        receipt, recon = self.reconciled_success()
        final = self.finalization(receipt=receipt, reconciliation=recon)
        self.assertEqual(final["state"], "READY_FOR_FINALIZATION_PERSISTENCE")
        self.assertEqual(final["final_execution_state"], "FINALIZED_SUCCESS")
        self.assertEqual(
            final["source_terminal_outcome"],
            "RECONCILED_CONFIRMED_SUCCESS",
        )
        self.assertTrue(final["reconciliation_digest"].startswith("sha256:"))

    def test_unresolved_conflict_and_pending_work_block_finalization(self):
        receipt = self.success_receipt()
        final = build_terminal_finalization(
            receipt,
            terminal_revision=1,
            terminal_evidence_set_digest=D("a"),
            finops_observation_digest=D("b"),
            execution_id_match=True,
            trace_id_match=True,
            idempotency_key_match=True,
            effect_key_match=True,
            provider_request_correlation_match=True,
            provider_identity_match=True,
            terminal_evidence_authenticated=True,
            terminal_evidence_fresh=True,
            unresolved_conflict_present=True,
            pending_reconciliation=True,
            pending_rollback_or_compensation=True,
            finops_within_policy=True,
            effect_confirmation_complete=True,
            expected_postcondition_match=True,
        )
        self.assertEqual(final["state"], "BLOCKED")
        self.assertIn("UNRESOLVED_TERMINAL_CONFLICT", final["blockers"])
        self.assertIn("PENDING_RECONCILIATION", final["blockers"])
        self.assertIn("PENDING_ROLLBACK_OR_COMPENSATION", final["blockers"])

    def test_finalization_persistence_attestation_is_external_proof_only(self):
        final = self.finalization()
        fp = build_finalization_persistence_attestation(
            final,
            finalization_record_digest=D("c"),
            writer_attestation_digest=D("d"),
            read_after_write_verified=True,
            atomic_write_or_cas_verified=True,
            writer_identity_verified=True,
        )
        self.assertEqual(fp["state"], "FINALIZATION_PERSISTENCE_ATTESTED")
        self.assertFalse(fp["persisted_by_this_module"])
        self.assertFalse(fp["provider_called"])
        self.assertFalse(fp["network_called"])

    def test_audit_seal_requires_persisted_finalization_and_creates_no_authority(self):
        final, fp, seal, _, _ = self.terminal_chain()
        self.assertEqual(seal["state"], "AUDIT_SEAL_READY_FOR_PERSISTENCE")
        self.assertTrue(seal["seal_is_immutable"])
        self.assertTrue(seal["seal_is_append_only"])
        self.assertFalse(seal["seal_creates_execution_authority"])
        self.assertFalse(seal["seal_authorizes_retry"])
        self.assertFalse(seal["seal_authorizes_reopen"])
        self.assertFalse(seal["seal_authorizes_external_effect"])
        self.assertFalse(seal["real_signature_created"])
        self.assertFalse(seal["seal_persisted_by_this_module"])

    def test_terminal_certificate_is_read_only_evidence(self):
        _, _, _, _, cert = self.terminal_chain()
        self.assertEqual(cert["state"], "TERMINAL_CERTIFICATE_READY")
        self.assertTrue(cert["certificate_is_read_only"])
        self.assertFalse(cert["certificate_is_execution_authorization"])
        self.assertFalse(cert["certificate_authorizes_retry"])
        self.assertFalse(cert["certificate_authorizes_reopen"])
        self.assertFalse(cert["certificate_authorizes_external_effect"])
        self.assertFalse(cert["certificate_is_real_signature"])
        self.assertFalse(cert["certificate_persisted_by_this_module"])
        self.assertFalse(cert["provider_called"])
        self.assertFalse(cert["network_called"])
        self.assertTrue(verify_terminal_certificate(cert)["valid"])

    def test_certificate_tamper_detection(self):
        _, _, _, _, cert = self.terminal_chain()
        tampered = copy.deepcopy(cert)
        tampered["manifest"]["terminal_revision"] = 2
        checked = verify_terminal_certificate(tampered)
        self.assertFalse(checked["valid"])
        self.assertIn("CERTIFICATE_DIGEST_MISMATCH", checked["blockers"])

    def test_policy_is_fail_closed(self):
        policy = terminal_chain_policy()
        self.assertFalse(policy["unknown_outcome_can_be_finalized"])
        self.assertFalse(policy["still_unknown_outcome_can_be_finalized"])
        self.assertTrue(policy["terminal_evidence_required"])
        self.assertTrue(policy["terminal_evidence_authentication_required"])
        self.assertTrue(policy["terminal_evidence_freshness_required"])
        self.assertTrue(policy["success_requires_effect_confirmation"])
        self.assertTrue(policy["success_requires_expected_postcondition_match"])
        self.assertTrue(
            policy["terminal_failure_requires_no_effect_or_terminal_rejection"]
        )
        self.assertTrue(policy["unresolved_conflict_blocks_finalization"])
        self.assertTrue(policy["pending_reconciliation_blocks_finalization"])
        self.assertTrue(
            policy["pending_rollback_or_compensation_blocks_finalization"]
        )
        self.assertFalse(policy["finalization_is_retry"])
        self.assertFalse(policy["execution_reopen_allowed"])
        self.assertTrue(policy["audit_seal_is_immutable"])
        self.assertTrue(policy["terminal_certificate_is_read_only"])
        self.assertFalse(
            policy["terminal_certificate_is_execution_authorization"]
        )
        self.assertFalse(policy["terminal_certificate_authorizes_retry"])
        self.assertFalse(policy["terminal_certificate_authorizes_reopen"])
        self.assertFalse(policy["terminal_certificate_is_real_signature"])
        self.assertFalse(policy["provider_called"])
        self.assertFalse(policy["network_called"])
        self.assertFalse(policy["message_sent"])
        self.assertFalse(policy["contract_exported"])
        self.assertFalse(policy["signature_requested"])
        self.assertFalse(policy["worker_armed"])
        self.assertFalse(policy["deploy_executed"])
        self.assertFalse(policy["core_checkpoint_write"])
        self.assertFalse(policy["external_action_executed"])
        self.assertFalse(policy["executes_action"])


if __name__ == "__main__":
    unittest.main()
