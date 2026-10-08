import copy
import unittest

from atlasquant_aion_approval_outbound_dispatch_bridge_v1 import (
    build_approval_decision_evidence,
    build_outbound_adapter_manifest,
    build_outbound_dispatch_bridge,
)
from atlasquant_aion_contract_communication_draft_approval_v1 import (
    build_communication_draft,
    build_human_approval_packet,
)
from atlasquant_aion_outbound_execution_authorization_durable_dispatch_v1 import (
    MECHANISM,
    build_authorization_persistence_attestation,
    build_durable_dispatch_record_candidate,
    build_fresh_outbound_execution_authorization,
    build_sealed_payload_attestation,
)
from atlasquant_aion_sealed_provider_outcome_reconciliation_v1 import (
    RECONCILIATION_MECHANISM,
    build_dispatch_write_attestation,
    build_outcome_receipt,
    build_outcome_reconciliation,
    build_provider_runtime_attestation,
    build_reconciliation_authorization,
    build_sealed_provider_call_boundary,
    outcome_chain_policy,
    verify_outcome_chain_record,
)


D = lambda c: "sha256:" + (c * 64)
OWNER = D("a")
PRINCIPAL = D("b")
APPROVAL_RECEIPT = D("c")
BRIDGE_IDEMPOTENCY = D("d")
BRIDGE_EFFECT = D("e")
ADAPTER_BUILD = D("f")
OWNER_KEY = D("1")
SIGNED_REQUEST = D("2")
AUTH_NONCE = D("3")
AUTH_RECORD = D("4")
AUTH_WRITER = D("5")
PAYLOAD = D("6")
RECIPIENT = D("7")
ENDPOINT = D("8")
CREDENTIAL = D("9")
HEADERS = D("a")
TRANSPORT = D("b")
TIMEOUT = D("c")
LEASE = D("d")
DISPATCH_RECORD = D("e")
DISPATCH_WRITER = D("f")
RUNTIME_BUILD = D("1")
PROVIDER_CORRELATION = D("2")
PROVIDER_RESPONSE = D("3")
RECON_SOURCE = D("4")
RECON_RECORD = D("5")
RECON_KEY = D("6")
RECON_REQUEST = D("7")
RECON_NONCE = D("8")

APPROVAL_DECIDED = "2026-10-08T10:00:00+00:00"
APPROVAL_EXPIRES = "2026-10-08T10:04:00+00:00"
BRIDGE_NOW = "2026-10-08T10:01:00+00:00"
AUTH_ISSUED = "2026-10-08T10:01:10+00:00"
AUTH_EXPIRES = "2026-10-08T10:02:40+00:00"
AUTH_NOW = "2026-10-08T10:01:20+00:00"
PERSISTED_AT = "2026-10-08T10:01:25+00:00"
PAYLOAD_CHECKED = "2026-10-08T10:01:30+00:00"
DISPATCH_AT = "2026-10-08T10:01:35+00:00"
RUNTIME_CHECKED = "2026-10-08T10:01:36+00:00"
OUTCOME_AT = "2026-10-08T10:01:38+00:00"
RECON_ISSUED = "2026-10-08T10:02:00+00:00"
RECON_EXPIRES = "2026-10-08T10:03:30+00:00"
RECON_NOW = "2026-10-08T10:02:10+00:00"
RECON_OBSERVED = "2026-10-08T10:02:20+00:00"


class AionSealedProviderOutcomeReconciliationV1Tests(unittest.TestCase):
    def upstream(self):
        draft = build_communication_draft(
            channel="EMAIL",
            recipient_ref="contact://client-1/primary",
            subject="Contrato para revisão",
            body="Segue o rascunho aprovado para revisão.",
        )
        packet = build_human_approval_packet(
            draft,
            action="SEND_EMAIL",
            owner_binding_digest=OWNER,
            reason="Approve exact email.",
        )
        approval = build_approval_decision_evidence(
            approval_packet=packet,
            approval_id="approval-email-1",
            approval_version=2,
            decision="APPROVED",
            human_principal_ref="owner://mikael",
            human_principal_binding_digest=PRINCIPAL,
            owner_binding_digest=OWNER,
            authenticated_receipt_digest=APPROVAL_RECEIPT,
            approval_packet_digest=packet["approval_packet_digest"],
            subject_digest=packet["subject_digest"],
            requested_action=packet["requested_action"],
            decided_at=APPROVAL_DECIDED,
            expires_at=APPROVAL_EXPIRES,
            authenticated_human_receipt_verified=True,
            owner_session_or_signature_verified=True,
            approval_consumed=False,
        )
        adapter = build_outbound_adapter_manifest(
            adapter_id="email-adapter-1",
            adapter_kind="EMAIL_PROVIDER",
            version="1.0.0",
            binary_or_build_digest=ADAPTER_BUILD,
            logical_capabilities=["SEND_EMAIL"],
            signed_manifest_verified=True,
        )
        bridge = build_outbound_dispatch_bridge(
            draft,
            packet,
            approval,
            adapter,
            bridge_id="bridge-email-1",
            idempotency_key_digest=BRIDGE_IDEMPOTENCY,
            effect_key_digest=BRIDGE_EFFECT,
            now=BRIDGE_NOW,
        )
        auth = build_fresh_outbound_execution_authorization(
            bridge,
            authorization_id="exec-auth-email-1",
            decision="AUTHORIZE_OUTBOUND_EXECUTION",
            mechanism=MECHANISM,
            owner_binding_digest=OWNER,
            owner_key_fingerprint=OWNER_KEY,
            signed_request_digest=SIGNED_REQUEST,
            authorization_nonce_digest=AUTH_NONCE,
            verified_owner_signature=True,
            verified_active_trust_root=True,
            persistent_nonce_replay_guard_verified=True,
            nonce_single_use_claimed=True,
            issued_at=AUTH_ISSUED,
            expires_at=AUTH_EXPIRES,
            now=AUTH_NOW,
        )
        persistence = build_authorization_persistence_attestation(
            auth,
            persisted_record_digest=AUTH_RECORD,
            writer_attestation_digest=AUTH_WRITER,
            persisted_at=PERSISTED_AT,
            read_after_write_verified=True,
            atomic_write_or_cas_verified=True,
            writer_identity_verified=True,
            now=PERSISTED_AT,
        )
        payload = build_sealed_payload_attestation(
            bridge,
            auth,
            persistence,
            payload_digest=PAYLOAD,
            payload_schema_ref="schema://outbound/email-v1",
            recipient_resolution_digest=RECIPIENT,
            endpoint_reference_digest=ENDPOINT,
            credential_reference_digest=CREDENTIAL,
            request_headers_policy_digest=HEADERS,
            transport_policy_digest=TRANSPORT,
            timeout_policy_digest=TIMEOUT,
            verified_by_trusted_adapter=True,
            checked_at=PAYLOAD_CHECKED,
            now=PAYLOAD_CHECKED,
        )
        candidate = build_durable_dispatch_record_candidate(
            bridge,
            auth,
            persistence,
            payload,
            execution_id="execution-email-1",
            task_id="task-email-1",
            step_id="step-send-email-1",
            lease_identity_digest=LEASE,
            observability_trace_id="trace-email-1",
            recorded_at=DISPATCH_AT,
        )
        self.assertEqual(
            candidate["state"],
            "READY_FOR_DURABLE_DISPATCH_RECORD_WRITE",
        )
        return candidate

    def boundary(self):
        candidate = self.upstream()
        dispatch = build_dispatch_write_attestation(
            candidate,
            durable_dispatch_record_digest=DISPATCH_RECORD,
            store_writer_attestation_digest=DISPATCH_WRITER,
            persisted_state="DISPATCH_RECORDED",
            lease_ownership_verified=True,
            lease_not_expired=True,
            idempotency_reservation_verified=True,
            effect_key_reservation_verified=True,
            authorization_consumed_atomically=True,
            read_after_write_verified=True,
            writer_identity_verified=True,
            persisted_at=DISPATCH_AT,
        )
        runtime = build_provider_runtime_attestation(
            candidate,
            provider_identity_ref="provider://email/primary",
            runtime_build_digest=RUNTIME_BUILD,
            adapter_manifest_digest=candidate["adapter_manifest_digest"],
            endpoint_reference_digest=candidate["endpoint_reference_digest"],
            credential_reference_digest=candidate["credential_reference_digest"],
            signed_runtime_verified=True,
            endpoint_allowlist_verified=True,
            credential_scope_verified=True,
            credential_not_expired=True,
            redirect_disabled_or_bounded=True,
            timeout_policy_verified=True,
            transport_policy_verified=True,
            checked_at=RUNTIME_CHECKED,
            now=RUNTIME_CHECKED,
        )
        boundary = build_sealed_provider_call_boundary(
            candidate,
            dispatch,
            runtime,
            call_attempt_id="call-email-1",
            provider_request_correlation_digest=PROVIDER_CORRELATION,
        )
        return candidate, dispatch, runtime, boundary

    def unknown_receipt(self):
        *_, boundary = self.boundary()
        return build_outcome_receipt(
            boundary,
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
            response_schema_valid=False,
            response_authenticity_verified=False,
            provider_success_semantics_attested=False,
            effect_confirmation_complete=False,
            expected_postcondition_match=False,
        )

    def reconciliation_auth(self, receipt=None, **changes):
        receipt = receipt or self.unknown_receipt()
        kwargs = {
            "outcome_receipt": receipt,
            "authorization_id": "recon-auth-1",
            "decision": "AUTHORIZE_OUTCOME_RECONCILIATION",
            "owner_binding_digest": OWNER,
            "owner_key_fingerprint": RECON_KEY,
            "signed_request_digest": RECON_REQUEST,
            "nonce_digest": RECON_NONCE,
            "verified_owner_signature": True,
            "verified_active_trust_root": True,
            "persistent_nonce_replay_guard_verified": True,
            "nonce_single_use_claimed": True,
            "issued_at": RECON_ISSUED,
            "expires_at": RECON_EXPIRES,
            "now": RECON_NOW,
        }
        kwargs.update(changes)
        return build_reconciliation_authorization(**kwargs)

    def test_call_boundary_requires_real_dispatch_write_attestation(self):
        candidate, dispatch, runtime, boundary = self.boundary()
        self.assertEqual(dispatch["state"], "DISPATCH_RECORDED_ATTESTED")
        self.assertTrue(dispatch["authorization_consumed_atomically"])
        self.assertFalse(dispatch["dispatch_written_by_this_module"])
        self.assertFalse(dispatch["provider_called"])

        self.assertEqual(boundary["state"], "SEALED_SINGLE_CALL_READY")
        self.assertTrue(boundary["exactly_one_call_attempt_allowed"])
        self.assertFalse(boundary["provider_switch_allowed"])
        self.assertFalse(boundary["endpoint_switch_allowed"])
        self.assertFalse(boundary["credential_switch_allowed"])
        self.assertFalse(boundary["payload_mutation_allowed"])
        self.assertFalse(boundary["provider_called"])
        self.assertFalse(boundary["network_called"])
        self.assertFalse(boundary["call_attempt_started"])
        self.assertFalse(boundary["external_action_executed"])

    def test_dispatch_attestation_fails_without_atomic_authorization_consumption(self):
        candidate = self.upstream()
        dispatch = build_dispatch_write_attestation(
            candidate,
            durable_dispatch_record_digest=DISPATCH_RECORD,
            store_writer_attestation_digest=DISPATCH_WRITER,
            persisted_state="DISPATCH_RECORDED",
            lease_ownership_verified=True,
            lease_not_expired=True,
            idempotency_reservation_verified=True,
            effect_key_reservation_verified=True,
            authorization_consumed_atomically=False,
            read_after_write_verified=True,
            writer_identity_verified=True,
            persisted_at=DISPATCH_AT,
        )
        self.assertEqual(dispatch["state"], "BLOCKED")
        self.assertIn(
            "AUTHORIZATION_ATOMIC_CONSUMPTION_REQUIRED",
            dispatch["blockers"],
        )

    def test_complete_positive_evidence_can_confirm_success(self):
        *_, boundary = self.boundary()
        receipt = build_outcome_receipt(
            boundary,
            requested_outcome="CONFIRMED_SUCCESS",
            provider_response_evidence_digest=PROVIDER_RESPONSE,
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
        self.assertEqual(receipt["state"], "OUTCOME_RECEIPT_READY")
        self.assertEqual(receipt["outcome_state"], "CONFIRMED_SUCCESS")
        self.assertFalse(receipt["success_inferred_from_silence"])
        self.assertFalse(receipt["provider_called_by_this_module"])
        self.assertFalse(receipt["retry_executed"])

    def test_success_request_with_incomplete_evidence_becomes_unknown(self):
        *_, boundary = self.boundary()
        receipt = build_outcome_receipt(
            boundary,
            requested_outcome="CONFIRMED_SUCCESS",
            provider_response_evidence_digest=PROVIDER_RESPONSE,
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
            effect_confirmation_complete=False,
            expected_postcondition_match=False,
        )
        self.assertEqual(receipt["outcome_state"], "OUTCOME_UNKNOWN")
        self.assertIn(
            "EFFECT_CONFIRMATION_EVIDENCE_INCOMPLETE",
            receipt["ambiguity_triggers"],
        )
        self.assertFalse(receipt["outcome_unknown_automatic_retry_allowed"])

    def test_timeout_always_wins_over_claimed_success(self):
        receipt = self.unknown_receipt()
        self.assertEqual(receipt["state"], "OUTCOME_RECEIPT_READY")
        self.assertEqual(receipt["outcome_state"], "OUTCOME_UNKNOWN")
        self.assertIn(
            "TIMEOUT_AFTER_DISPATCH",
            receipt["ambiguity_triggers"],
        )
        self.assertTrue(receipt["receipt_is_immutable"])
        self.assertFalse(receipt["original_receipt_mutable"])
        self.assertTrue(
            receipt["outcome_unknown_requires_separate_reconciliation"]
        )
        self.assertFalse(receipt["outcome_unknown_automatic_retry_allowed"])

    def test_authoritative_terminal_failure_requires_no_effect_evidence(self):
        *_, boundary = self.boundary()
        receipt = build_outcome_receipt(
            boundary,
            requested_outcome="CONFIRMED_TERMINAL_FAILURE",
            provider_response_evidence_digest=PROVIDER_RESPONSE,
            observed_at=OUTCOME_AT,
            provider_identity_match=True,
            execution_id_match=True,
            provider_request_correlation_match=True,
            response_schema_valid=True,
            response_authenticity_verified=True,
            provider_terminal_failure_semantics_attested=True,
            no_effect_or_terminal_rejection_evidence_complete=True,
        )
        self.assertEqual(
            receipt["outcome_state"],
            "CONFIRMED_TERMINAL_FAILURE",
        )
        self.assertFalse(receipt["failure_inferred_from_silence"])

    def test_reconciliation_needs_separate_fresh_owner_authorization(self):
        receipt = self.unknown_receipt()
        denied = self.reconciliation_auth(
            receipt,
            decision="DENY_OUTCOME_RECONCILIATION",
        )
        self.assertEqual(denied["state"], "RECONCILIATION_DENIED")
        self.assertFalse(denied["reconciliation_authorized"])
        self.assertFalse(denied["retry_authorized"])
        self.assertFalse(denied["new_attempt_authorized"])

        allowed = self.reconciliation_auth(receipt)
        self.assertEqual(allowed["state"], "RECONCILIATION_AUTHORIZED")
        self.assertTrue(allowed["reconciliation_authorized"])
        self.assertFalse(allowed["authorization_consumed"])
        self.assertFalse(allowed["provider_query_authorized_by_this_module"])
        self.assertFalse(allowed["retry_authorized"])

    def test_complete_authoritative_evidence_can_reconcile_success(self):
        receipt = self.unknown_receipt()
        auth = self.reconciliation_auth(receipt)
        reconciliation = build_outcome_reconciliation(
            receipt,
            auth,
            reconciliation_id="recon-1",
            evidence_class="PROVIDER_SIGNED_EVENT_OR_RECEIPT",
            evidence_source_digest=RECON_SOURCE,
            evidence_record_digest=RECON_RECORD,
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
        self.assertEqual(reconciliation["state"], "RECONCILIATION_RECORD_READY")
        self.assertEqual(
            reconciliation["reconciled_outcome_state"],
            "RECONCILED_CONFIRMED_SUCCESS",
        )
        self.assertTrue(reconciliation["original_receipt_immutable"])
        self.assertFalse(reconciliation["original_receipt_mutated"])
        self.assertFalse(reconciliation["reconciliation_is_retry"])
        self.assertFalse(reconciliation["external_effect_replayed"])
        self.assertFalse(reconciliation["automatic_retry_allowed"])
        self.assertFalse(reconciliation["new_attempt_authorized"])

    def test_conflicting_evidence_preserves_unknown(self):
        receipt = self.unknown_receipt()
        auth = self.reconciliation_auth(receipt)
        reconciliation = build_outcome_reconciliation(
            receipt,
            auth,
            reconciliation_id="recon-conflict",
            evidence_class="PROVIDER_AUTHORITATIVE_OPERATION_STATUS",
            evidence_source_digest=RECON_SOURCE,
            evidence_record_digest=RECON_RECORD,
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
            terminal_failure_or_no_effect_evidence_complete=True,
            conflicting_evidence_present=True,
            observed_at=RECON_OBSERVED,
        )
        self.assertEqual(
            reconciliation["reconciled_outcome_state"],
            "STILL_OUTCOME_UNKNOWN",
        )
        self.assertFalse(reconciliation["automatic_retry_allowed"])

    def test_incomplete_reconciliation_evidence_preserves_unknown(self):
        receipt = self.unknown_receipt()
        auth = self.reconciliation_auth(receipt)
        reconciliation = build_outcome_reconciliation(
            receipt,
            auth,
            reconciliation_id="recon-incomplete",
            evidence_class="IMMUTABLE_DOWNSTREAM_AUDIT_RECORD",
            evidence_source_digest=RECON_SOURCE,
            evidence_record_digest=RECON_RECORD,
            provider_identity_match=True,
            execution_id_match=True,
            trace_id_match=False,
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
        self.assertEqual(
            reconciliation["reconciled_outcome_state"],
            "STILL_OUTCOME_UNKNOWN",
        )

    def test_record_verifier_detects_bound_field_and_boundary_tampering(self):
        candidate, dispatch, runtime, boundary = self.boundary()
        self.assertTrue(verify_outcome_chain_record(dispatch)["valid"])
        self.assertTrue(verify_outcome_chain_record(runtime)["valid"])
        self.assertTrue(verify_outcome_chain_record(boundary)["valid"])

        tampered_binding = copy.deepcopy(boundary)
        tampered_binding["provider_request_correlation_digest"] = D("0")
        verified_binding = verify_outcome_chain_record(tampered_binding)
        self.assertFalse(verified_binding["valid"])
        self.assertIn("RECORD_DIGEST_MISMATCH", verified_binding["blockers"])

        tampered_boundary = copy.deepcopy(boundary)
        tampered_boundary["provider_called"] = True
        verified_boundary = verify_outcome_chain_record(tampered_boundary)
        self.assertFalse(verified_boundary["valid"])
        self.assertIn(
            "RECORD_BOUNDARY_INVALID:provider_called",
            verified_boundary["blockers"],
        )

        receipt = self.unknown_receipt()
        self.assertTrue(verify_outcome_chain_record(receipt)["valid"])
        auth = self.reconciliation_auth(receipt)
        self.assertTrue(verify_outcome_chain_record(auth)["valid"])

        reconciliation = build_outcome_reconciliation(
            receipt,
            auth,
            reconciliation_id="recon-verify",
            evidence_class="PROVIDER_SIGNED_EVENT_OR_RECEIPT",
            evidence_source_digest=RECON_SOURCE,
            evidence_record_digest=RECON_RECORD,
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
        self.assertTrue(verify_outcome_chain_record(reconciliation)["valid"])

    def test_policy_is_fail_closed(self):
        policy = outcome_chain_policy()
        self.assertTrue(policy["durable_dispatch_record_required_before_call"])
        self.assertTrue(
            policy["authorization_consumed_atomically_before_call"]
        )
        self.assertTrue(policy["provider_runtime_attestation_required"])
        self.assertTrue(policy["sealed_exact_single_call_required"])
        self.assertFalse(policy["provider_switch_after_dispatch_allowed"])
        self.assertFalse(policy["endpoint_switch_after_dispatch_allowed"])
        self.assertFalse(policy["credential_switch_after_dispatch_allowed"])
        self.assertFalse(policy["payload_mutation_after_dispatch_allowed"])
        self.assertTrue(policy["success_requires_complete_positive_evidence"])
        self.assertTrue(
            policy["terminal_failure_requires_authoritative_evidence"]
        )
        self.assertFalse(policy["silence_is_success"])
        self.assertFalse(policy["silence_is_terminal_failure"])
        self.assertTrue(policy["ambiguity_always_outcome_unknown"])
        self.assertTrue(policy["outcome_receipt_append_only"])
        self.assertTrue(policy["outcome_receipt_immutable"])
        self.assertFalse(policy["outcome_unknown_automatic_retry_allowed"])
        self.assertTrue(
            policy["outcome_unknown_requires_separate_reconciliation"]
        )
        self.assertTrue(
            policy["reconciliation_requires_separate_owner_authorization"]
        )
        self.assertTrue(policy["reconciliation_original_receipt_immutable"])
        self.assertFalse(policy["reconciliation_is_retry"])
        self.assertTrue(policy["conflicting_evidence_preserves_unknown"])
        self.assertTrue(policy["incomplete_evidence_preserves_unknown"])
        self.assertTrue(policy["new_attempt_requires_confirmed_no_effect"])
        self.assertTrue(
            policy["new_attempt_requires_fresh_owner_authorization"]
        )
        self.assertTrue(policy["new_attempt_requires_new_durable_dispatch"])
        self.assertFalse(policy["dispatch_written_by_this_module"])
        self.assertFalse(policy["authorization_consumed_by_this_module"])
        self.assertFalse(policy["provider_called"])
        self.assertFalse(policy["network_called"])
        self.assertFalse(policy["message_sent"])
        self.assertFalse(policy["contract_exported"])
        self.assertFalse(policy["signature_requested"])
        self.assertFalse(policy["retry_executed"])
        self.assertFalse(policy["worker_armed"])
        self.assertFalse(policy["deploy_executed"])
        self.assertFalse(policy["core_checkpoint_write"])
        self.assertFalse(policy["external_action_executed"])
        self.assertFalse(policy["executes_action"])


if __name__ == "__main__":
    unittest.main()
