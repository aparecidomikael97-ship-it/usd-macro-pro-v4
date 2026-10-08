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
    outbound_execution_dispatch_policy,
    verify_durable_dispatch_record_candidate,
)


OWNER = "sha256:" + ("a" * 64)
PRINCIPAL = "sha256:" + ("b" * 64)
APPROVAL_RECEIPT = "sha256:" + ("c" * 64)
BRIDGE_IDEMPOTENCY = "sha256:" + ("d" * 64)
BRIDGE_EFFECT = "sha256:" + ("e" * 64)
ADAPTER_BUILD = "sha256:" + ("f" * 64)
OWNER_KEY = "sha256:" + ("1" * 64)
SIGNED_REQUEST = "sha256:" + ("2" * 64)
AUTH_NONCE = "sha256:" + ("3" * 64)
AUTH_RECORD = "sha256:" + ("4" * 64)
WRITER = "sha256:" + ("5" * 64)
PAYLOAD = "sha256:" + ("6" * 64)
RECIPIENT = "sha256:" + ("7" * 64)
ENDPOINT = "sha256:" + ("8" * 64)
CREDENTIAL = "sha256:" + ("9" * 64)
HEADERS = "sha256:" + ("a" * 64)
TRANSPORT = "sha256:" + ("b" * 64)
TIMEOUT = "sha256:" + ("c" * 64)
LEASE = "sha256:" + ("d" * 64)

APPROVAL_DECIDED = "2026-10-08T10:00:00+00:00"
APPROVAL_EXPIRES = "2026-10-08T10:04:00+00:00"
BRIDGE_NOW = "2026-10-08T10:01:00+00:00"
AUTH_ISSUED = "2026-10-08T10:01:10+00:00"
AUTH_EXPIRES = "2026-10-08T10:02:40+00:00"
AUTH_NOW = "2026-10-08T10:01:20+00:00"
PERSISTED_AT = "2026-10-08T10:01:25+00:00"
PAYLOAD_CHECKED = "2026-10-08T10:01:30+00:00"
DISPATCH_AT = "2026-10-08T10:01:35+00:00"


class AionOutboundExecutionAuthorizationDurableDispatchV1Tests(unittest.TestCase):
    def bridge(self):
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
        self.assertEqual(
            bridge["state"],
            "READY_FOR_EXECUTION_AUTHORIZATION_REVIEW",
        )
        return bridge

    def authorization(self, bridge=None, **changes):
        bridge = bridge or self.bridge()
        kwargs = {
            "bridge": bridge,
            "authorization_id": "exec-auth-email-1",
            "decision": "AUTHORIZE_OUTBOUND_EXECUTION",
            "mechanism": MECHANISM,
            "owner_binding_digest": OWNER,
            "owner_key_fingerprint": OWNER_KEY,
            "signed_request_digest": SIGNED_REQUEST,
            "authorization_nonce_digest": AUTH_NONCE,
            "verified_owner_signature": True,
            "verified_active_trust_root": True,
            "persistent_nonce_replay_guard_verified": True,
            "nonce_single_use_claimed": True,
            "issued_at": AUTH_ISSUED,
            "expires_at": AUTH_EXPIRES,
            "now": AUTH_NOW,
        }
        kwargs.update(changes)
        return build_fresh_outbound_execution_authorization(**kwargs)

    def persistence(self, authorization=None, **changes):
        authorization = authorization or self.authorization()
        kwargs = {
            "authorization": authorization,
            "persisted_record_digest": AUTH_RECORD,
            "writer_attestation_digest": WRITER,
            "persisted_at": PERSISTED_AT,
            "read_after_write_verified": True,
            "atomic_write_or_cas_verified": True,
            "writer_identity_verified": True,
            "now": PERSISTED_AT,
        }
        kwargs.update(changes)
        return build_authorization_persistence_attestation(**kwargs)

    def payload(self, bridge=None, authorization=None, persistence=None, **changes):
        bridge = bridge or self.bridge()
        authorization = authorization or self.authorization(bridge)
        persistence = persistence or self.persistence(authorization)
        kwargs = {
            "bridge": bridge,
            "authorization": authorization,
            "authorization_persistence": persistence,
            "payload_digest": PAYLOAD,
            "payload_schema_ref": "schema://outbound/email-v1",
            "recipient_resolution_digest": RECIPIENT,
            "endpoint_reference_digest": ENDPOINT,
            "credential_reference_digest": CREDENTIAL,
            "request_headers_policy_digest": HEADERS,
            "transport_policy_digest": TRANSPORT,
            "timeout_policy_digest": TIMEOUT,
            "verified_by_trusted_adapter": True,
            "checked_at": PAYLOAD_CHECKED,
            "now": PAYLOAD_CHECKED,
        }
        kwargs.update(changes)
        return build_sealed_payload_attestation(**kwargs)

    def candidate(self):
        bridge = self.bridge()
        auth = self.authorization(bridge)
        persistence = self.persistence(auth)
        payload = self.payload(bridge, auth, persistence)
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
        return bridge, auth, persistence, payload, candidate

    def test_fresh_execution_intent_is_not_dispatch(self):
        auth = self.authorization()
        self.assertEqual(auth["state"], "FRESH_EXECUTION_INTENT_VERIFIED")
        self.assertTrue(auth["fresh_execution_intent_verified"])
        self.assertFalse(auth["authorization_persisted"])
        self.assertFalse(auth["persistence_attested"])
        self.assertFalse(auth["authorization_consumed"])
        self.assertFalse(auth["execution_command_generated"])
        self.assertFalse(auth["dispatch_record_written"])
        self.assertFalse(auth["execution_authorized"])
        self.assertFalse(auth["provider_called"])
        self.assertFalse(auth["network_called"])
        self.assertFalse(auth["external_action_executed"])

    def test_execution_authorization_requires_fresh_owner_crypto_and_nonce_guard(self):
        blocked = self.authorization(
            verified_owner_signature=False,
            verified_active_trust_root=False,
            persistent_nonce_replay_guard_verified=False,
            nonce_single_use_claimed=False,
        )
        self.assertEqual(blocked["state"], "BLOCKED")
        for expected in (
            "OWNER_EXECUTION_SIGNATURE_NOT_VERIFIED",
            "ACTIVE_TRUST_ROOT_NOT_VERIFIED",
            "PERSISTENT_NONCE_REPLAY_GUARD_REQUIRED",
            "NONCE_SINGLE_USE_CLAIM_REQUIRED",
        ):
            self.assertIn(expected, blocked["blockers"])

    def test_denied_execution_intent_never_advances(self):
        denied = self.authorization(decision="DENY_OUTBOUND_EXECUTION")
        self.assertEqual(denied["state"], "EXECUTION_DENIED")
        self.assertTrue(denied["execution_intent_denied"])
        self.assertFalse(denied["fresh_execution_intent_verified"])
        persistence = self.persistence(denied)
        self.assertEqual(persistence["state"], "BLOCKED")
        self.assertIn("FRESH_EXECUTION_INTENT_REQUIRED", persistence["blockers"])

    def test_authorization_must_be_persisted_with_independent_attestation(self):
        auth = self.authorization()
        persistence = self.persistence(auth)
        self.assertEqual(
            persistence["state"],
            "PERSISTED_AUTHORIZATION_ATTESTED",
        )
        self.assertTrue(persistence["read_after_write_verified"])
        self.assertTrue(persistence["atomic_write_or_cas_verified"])
        self.assertTrue(persistence["writer_identity_verified"])
        self.assertFalse(persistence["authorization_persisted_by_this_module"])
        self.assertFalse(persistence["authorization_consumed"])
        self.assertFalse(persistence["dispatch_record_written"])

        blocked = self.persistence(
            auth,
            read_after_write_verified=False,
            atomic_write_or_cas_verified=False,
            writer_identity_verified=False,
        )
        self.assertEqual(blocked["state"], "BLOCKED")
        self.assertIn(
            "READ_AFTER_WRITE_VERIFICATION_REQUIRED",
            blocked["blockers"],
        )
        self.assertIn("ATOMIC_WRITE_OR_CAS_REQUIRED", blocked["blockers"])
        self.assertIn(
            "WRITER_IDENTITY_VERIFICATION_REQUIRED",
            blocked["blockers"],
        )

    def test_payload_attestation_requires_persisted_authorization(self):
        bridge = self.bridge()
        auth = self.authorization(bridge)
        fake_persistence = {}
        payload = self.payload(
            bridge,
            auth,
            fake_persistence,
        )
        self.assertEqual(payload["state"], "BLOCKED")
        self.assertIn(
            "AUTHORIZATION_PERSISTENCE_SCHEMA_MISMATCH",
            payload["blockers"],
        )
        self.assertIn(
            "PERSISTED_AUTHORIZATION_ATTESTATION_REQUIRED",
            payload["blockers"],
        )

    def test_payload_attestation_contains_only_digests_not_raw_material(self):
        bridge = self.bridge()
        auth = self.authorization(bridge)
        persistence = self.persistence(auth)
        payload = self.payload(bridge, auth, persistence)
        self.assertEqual(payload["state"], "SEALED_PAYLOAD_ATTESTED")
        self.assertFalse(payload["raw_recipient_included"])
        self.assertFalse(payload["raw_endpoint_included"])
        self.assertFalse(payload["raw_credential_included"])
        self.assertFalse(payload["raw_payload_included"])
        self.assertFalse(payload["authorization_consumed"])
        self.assertFalse(payload["dispatch_record_written"])
        self.assertFalse(payload["provider_called"])
        self.assertFalse(payload["network_called"])

    def test_stale_payload_attestation_blocks(self):
        bridge = self.bridge()
        auth = self.authorization(bridge)
        persistence = self.persistence(auth)
        payload = self.payload(
            bridge,
            auth,
            persistence,
            checked_at="2026-10-08T10:00:30+00:00",
            now=PAYLOAD_CHECKED,
        )
        self.assertEqual(payload["state"], "BLOCKED")
        self.assertIn("PAYLOAD_ATTESTATION_STALE", payload["blockers"])

    def test_durable_dispatch_candidate_is_write_candidate_only(self):
        bridge, auth, persistence, payload, candidate = self.candidate()
        self.assertEqual(
            candidate["state"],
            "READY_FOR_DURABLE_DISPATCH_RECORD_WRITE",
        )
        self.assertEqual(candidate["mode"], "EXTERNAL_EFFECT")
        self.assertEqual(candidate["pre_record_state_required"], "LEASED")
        self.assertEqual(candidate["post_record_state"], "DISPATCH_RECORDED")
        self.assertTrue(
            candidate["authorization_persistence_attestation_required"]
        )
        self.assertTrue(
            candidate["authorization_consumption_required_atomically_with_write"]
        )
        self.assertTrue(candidate["durable_store_write_required"])
        self.assertTrue(candidate["post_record_crash_becomes_outcome_unknown"])
        self.assertTrue(candidate["post_record_timeout_becomes_outcome_unknown"])
        self.assertTrue(
            candidate["post_record_ambiguous_ack_becomes_outcome_unknown"]
        )
        self.assertFalse(candidate["outcome_unknown_automatic_retry_allowed"])
        self.assertTrue(
            candidate["outcome_unknown_requires_explicit_reconciliation"]
        )
        self.assertTrue(candidate["outcome_receipt_required"])
        self.assertFalse(candidate["dispatch_record_written"])
        self.assertFalse(candidate["authorization_consumed"])
        self.assertFalse(candidate["provider_call_allowed_after_this_module"])
        self.assertFalse(candidate["provider_called"])
        self.assertFalse(candidate["network_called"])
        self.assertFalse(candidate["message_sent"])
        self.assertFalse(candidate["external_action_executed"])
        self.assertTrue(
            verify_durable_dispatch_record_candidate(candidate)["valid"]
        )

    def test_candidate_digest_detects_tampering(self):
        *_, candidate = self.candidate()
        tampered = dict(candidate)
        tampered["payload_digest"] = "sha256:" + ("0" * 64)
        verified = verify_durable_dispatch_record_candidate(tampered)
        self.assertFalse(verified["valid"])
        self.assertIn(
            "DISPATCH_CANDIDATE_DIGEST_MISMATCH",
            verified["blockers"],
        )

    def test_policy_is_fail_closed(self):
        policy = outbound_execution_dispatch_policy()
        self.assertTrue(policy["fresh_execution_intent_required"])
        self.assertEqual(policy["execution_mechanism"], MECHANISM)
        self.assertTrue(policy["persistent_nonce_replay_guard_required"])
        self.assertTrue(policy["single_use_nonce_required"])
        self.assertTrue(
            policy["authorization_must_match_exact_bridge_digest"]
        )
        self.assertFalse(policy["authorization_is_provider_call"])
        self.assertTrue(policy["authorization_persistence_separate"])
        self.assertTrue(
            policy["authorization_persistence_attestation_required"]
        )
        self.assertTrue(policy["sealed_payload_attestation_required"])
        self.assertFalse(policy["raw_recipient_in_control_plane"])
        self.assertFalse(policy["raw_endpoint_in_control_plane"])
        self.assertFalse(policy["raw_credential_in_control_plane"])
        self.assertFalse(policy["raw_payload_in_control_plane"])
        self.assertTrue(
            policy["durable_dispatch_write_before_external_effect"]
        )
        self.assertTrue(
            policy["authorization_consumption_atomic_with_dispatch_write"]
        )
        self.assertTrue(
            policy["post_record_ambiguity_becomes_outcome_unknown"]
        )
        self.assertFalse(policy["outcome_unknown_automatic_retry_allowed"])
        self.assertTrue(
            policy["outcome_unknown_requires_explicit_reconciliation"]
        )
        self.assertTrue(policy["outcome_receipt_required"])
        self.assertFalse(policy["authorization_persisted"])
        self.assertFalse(policy["authorization_consumed"])
        self.assertFalse(policy["dispatch_record_written"])
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
