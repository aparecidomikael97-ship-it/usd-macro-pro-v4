import copy
import unittest

from atlasquant_aion_approval_outbound_dispatch_bridge_v1 import (
    build_approval_decision_evidence,
    build_outbound_adapter_manifest,
    build_outbound_dispatch_bridge,
    current_subject_digest,
    outbound_dispatch_policy,
    verify_outbound_dispatch_bridge,
)
from atlasquant_aion_contract_communication_draft_approval_v1 import (
    build_communication_draft,
    build_contract_draft,
    build_human_approval_packet,
)


OWNER = "sha256:" + ("a" * 64)
PRINCIPAL = "sha256:" + ("b" * 64)
RECEIPT = "sha256:" + ("c" * 64)
IDEMPOTENCY = "sha256:" + ("d" * 64)
EFFECT = "sha256:" + ("e" * 64)
BUILD = "sha256:" + ("f" * 64)
DECIDED = "2026-10-08T10:00:00+00:00"
EXPIRES = "2026-10-08T10:04:00+00:00"
NOW = "2026-10-08T10:01:00+00:00"


class AionApprovalOutboundDispatchBridgeV1Tests(unittest.TestCase):
    def email_draft(self):
        return build_communication_draft(
            channel="EMAIL",
            recipient_ref="contact://client-1/primary",
            subject="Contrato para revisão",
            body="Segue o rascunho aprovado para sua revisão.",
            attachment_refs=["artifact://contract-1-draft.pdf"],
            conversation_ref="crm://client-1/thread-1",
        )

    def email_packet(self, draft=None):
        draft = draft or self.email_draft()
        return build_human_approval_packet(
            draft,
            action="SEND_EMAIL",
            owner_binding_digest=OWNER,
            reason="Approve this exact outbound email draft.",
        )

    def approved_evidence(self, packet=None, **changes):
        packet = packet or self.email_packet()
        kwargs = {
            "approval_packet": packet,
            "approval_id": "approval-email-1",
            "approval_version": 2,
            "decision": "APPROVED",
            "human_principal_ref": "owner://mikael",
            "human_principal_binding_digest": PRINCIPAL,
            "owner_binding_digest": OWNER,
            "authenticated_receipt_digest": RECEIPT,
            "approval_packet_digest": packet["approval_packet_digest"],
            "subject_digest": packet["subject_digest"],
            "requested_action": packet["requested_action"],
            "decided_at": DECIDED,
            "expires_at": EXPIRES,
            "authenticated_human_receipt_verified": True,
            "owner_session_or_signature_verified": True,
            "approval_consumed": False,
        }
        kwargs.update(changes)
        return build_approval_decision_evidence(**kwargs)

    def email_adapter(self, **changes):
        kwargs = {
            "adapter_id": "email-provider-adapter-1",
            "adapter_kind": "EMAIL_PROVIDER",
            "version": "1.0.0",
            "binary_or_build_digest": BUILD,
            "logical_capabilities": ["SEND_EMAIL"],
            "signed_manifest_verified": True,
        }
        kwargs.update(changes)
        return build_outbound_adapter_manifest(**kwargs)

    def ready_bridge(self):
        draft = self.email_draft()
        packet = self.email_packet(draft)
        evidence = self.approved_evidence(packet)
        adapter = self.email_adapter()
        bridge = build_outbound_dispatch_bridge(
            draft,
            packet,
            evidence,
            adapter,
            bridge_id="bridge-email-1",
            idempotency_key_digest=IDEMPOTENCY,
            effect_key_digest=EFFECT,
            now=NOW,
        )
        return draft, packet, evidence, adapter, bridge

    def test_approved_exact_draft_becomes_review_candidate_only(self):
        draft, packet, evidence, adapter, bridge = self.ready_bridge()
        self.assertEqual(
            bridge["state"],
            "READY_FOR_EXECUTION_AUTHORIZATION_REVIEW",
        )
        self.assertEqual(
            bridge["subject_digest"],
            current_subject_digest(draft),
        )
        self.assertTrue(bridge["approved_subject_immutable"])
        self.assertTrue(bridge["draft_rebuild_match"])
        self.assertTrue(bridge["fresh_approval_verified"])
        self.assertTrue(bridge["adapter_capability_verified"])
        self.assertTrue(
            bridge["single_use_execution_authorization_still_required"]
        )
        self.assertTrue(bridge["durable_dispatch_record_still_required"])
        self.assertTrue(bridge["pre_dispatch_revalidation_still_required"])
        self.assertTrue(bridge["outcome_receipt_still_required"])
        self.assertFalse(bridge["approval_consumed"])
        self.assertFalse(bridge["execution_authorization_issued"])
        self.assertFalse(bridge["execution_authorized"])
        self.assertFalse(bridge["dispatch_record_written"])
        self.assertFalse(bridge["recipient_resolved"])
        self.assertFalse(bridge["endpoint_resolved"])
        self.assertFalse(bridge["credentials_loaded"])
        self.assertFalse(bridge["payload_materialized"])
        self.assertFalse(bridge["provider_called"])
        self.assertFalse(bridge["network_called"])
        self.assertFalse(bridge["message_sent"])
        self.assertFalse(bridge["external_action_executed"])
        self.assertFalse(bridge["executes_action"])
        self.assertTrue(verify_outbound_dispatch_bridge(bridge)["valid"])

    def test_any_post_approval_draft_mutation_blocks(self):
        draft = self.email_draft()
        packet = self.email_packet(draft)
        evidence = self.approved_evidence(packet)
        adapter = self.email_adapter()

        tampered = copy.deepcopy(draft)
        tampered["body"] = "Texto alterado após a aprovação."

        bridge = build_outbound_dispatch_bridge(
            tampered,
            packet,
            evidence,
            adapter,
            bridge_id="bridge-email-tampered",
            idempotency_key_digest=IDEMPOTENCY,
            effect_key_digest=EFFECT,
            now=NOW,
        )
        self.assertEqual(bridge["state"], "BLOCKED")
        self.assertIn("DRAFT_MUTATED_AFTER_DIGEST", bridge["blockers"])
        self.assertIn(
            "APPROVAL_PACKET_SUBJECT_DIGEST_MISMATCH",
            bridge["blockers"],
        )
        self.assertIn(
            "APPROVAL_EVIDENCE_SUBJECT_DIGEST_MISMATCH",
            bridge["blockers"],
        )
        self.assertFalse(bridge["execution_authorized"])
        self.assertFalse(bridge["message_sent"])

    def test_rejected_decision_never_reaches_bridge_ready(self):
        draft = self.email_draft()
        packet = self.email_packet(draft)
        rejected = self.approved_evidence(
            packet,
            decision="REJECTED",
        )
        self.assertEqual(rejected["state"], "REJECTED_EVIDENCE_READY")
        self.assertFalse(rejected["execution_authorized"])

        bridge = build_outbound_dispatch_bridge(
            draft,
            packet,
            rejected,
            self.email_adapter(),
            bridge_id="bridge-rejected",
            idempotency_key_digest=IDEMPOTENCY,
            effect_key_digest=EFFECT,
            now=NOW,
        )
        self.assertEqual(bridge["state"], "BLOCKED")
        self.assertIn(
            "APPROVED_DECISION_EVIDENCE_REQUIRED",
            bridge["blockers"],
        )
        self.assertIn(
            "APPROVAL_DECISION_MUST_BE_APPROVED",
            bridge["blockers"],
        )

    def test_expired_approval_blocks(self):
        draft = self.email_draft()
        packet = self.email_packet(draft)
        evidence = self.approved_evidence(packet)
        bridge = build_outbound_dispatch_bridge(
            draft,
            packet,
            evidence,
            self.email_adapter(),
            bridge_id="bridge-expired",
            idempotency_key_digest=IDEMPOTENCY,
            effect_key_digest=EFFECT,
            now="2026-10-08T10:05:00+00:00",
        )
        self.assertEqual(bridge["state"], "BLOCKED")
        self.assertIn("APPROVAL_EXPIRED", bridge["blockers"])

    def test_consumed_approval_blocks_reuse(self):
        draft = self.email_draft()
        packet = self.email_packet(draft)
        evidence = self.approved_evidence(
            packet,
            approval_consumed=True,
        )
        bridge = build_outbound_dispatch_bridge(
            draft,
            packet,
            evidence,
            self.email_adapter(),
            bridge_id="bridge-replay",
            idempotency_key_digest=IDEMPOTENCY,
            effect_key_digest=EFFECT,
            now=NOW,
        )
        self.assertEqual(bridge["state"], "BLOCKED")
        self.assertIn("APPROVAL_ALREADY_CONSUMED", bridge["blockers"])

    def test_unverified_human_identity_blocks_approval_evidence(self):
        packet = self.email_packet()
        evidence = self.approved_evidence(
            packet,
            authenticated_human_receipt_verified=False,
            owner_session_or_signature_verified=False,
        )
        self.assertEqual(evidence["state"], "BLOCKED")
        self.assertIn(
            "AUTHENTICATED_HUMAN_RECEIPT_REQUIRED",
            evidence["blockers"],
        )
        self.assertIn(
            "OWNER_SESSION_OR_SIGNATURE_VERIFICATION_REQUIRED",
            evidence["blockers"],
        )
        self.assertFalse(evidence["execution_authorized"])

    def test_adapter_capability_and_kind_must_match_action(self):
        draft = self.email_draft()
        packet = self.email_packet(draft)
        evidence = self.approved_evidence(packet)

        wrong_kind = build_outbound_adapter_manifest(
            adapter_id="whatsapp-adapter-1",
            adapter_kind="WHATSAPP_PROVIDER",
            version="1.0.0",
            binary_or_build_digest=BUILD,
            logical_capabilities=["SEND_WHATSAPP"],
            signed_manifest_verified=True,
        )
        bridge = build_outbound_dispatch_bridge(
            draft,
            packet,
            evidence,
            wrong_kind,
            bridge_id="bridge-wrong-adapter",
            idempotency_key_digest=IDEMPOTENCY,
            effect_key_digest=EFFECT,
            now=NOW,
        )
        self.assertEqual(bridge["state"], "BLOCKED")
        self.assertIn("ADAPTER_KIND_ACTION_MISMATCH", bridge["blockers"])
        self.assertIn("ADAPTER_CAPABILITY_MISSING", bridge["blockers"])

    def test_unsigned_adapter_manifest_is_blocked(self):
        adapter = self.email_adapter(signed_manifest_verified=False)
        self.assertEqual(adapter["state"], "BLOCKED")
        self.assertIn(
            "SIGNED_ADAPTER_MANIFEST_REQUIRED",
            adapter["blockers"],
        )
        self.assertFalse(adapter["network_called"])
        self.assertFalse(adapter["executes_action"])

    def test_idempotency_and_effect_keys_must_be_distinct(self):
        draft = self.email_draft()
        packet = self.email_packet(draft)
        bridge = build_outbound_dispatch_bridge(
            draft,
            packet,
            self.approved_evidence(packet),
            self.email_adapter(),
            bridge_id="bridge-keys",
            idempotency_key_digest=IDEMPOTENCY,
            effect_key_digest=IDEMPOTENCY,
            now=NOW,
        )
        self.assertEqual(bridge["state"], "BLOCKED")
        self.assertIn(
            "IDEMPOTENCY_AND_EFFECT_KEYS_MUST_DIFFER",
            bridge["blockers"],
        )

    def test_contract_export_uses_separate_adapter_kind_and_still_does_not_sign(self):
        contract = build_contract_draft(
            contract_id="contract-export-1",
            title="AION Services Draft",
            party_refs=["party://atlasquant", "party://client-1"],
            source_refs=["source://terms/template-1"],
            clauses=[
                {
                    "clause_id": "scope",
                    "heading": "Scope",
                    "body": "The scope remains subject to review.",
                    "summary": "Scope clause.",
                    "source_ref": "source://terms/template-1#scope",
                    "state": "PROPOSED",
                    "risk_severity": "LOW",
                }
            ],
        )
        packet = build_human_approval_packet(
            contract,
            action="EXPORT_CONTRACT_FOR_SIGNATURE_REVIEW",
            owner_binding_digest=OWNER,
            reason="Approve exact draft for signature-review export only.",
        )
        evidence = build_approval_decision_evidence(
            approval_packet=packet,
            approval_id="approval-contract-1",
            approval_version=2,
            decision="APPROVED",
            human_principal_ref="owner://mikael",
            human_principal_binding_digest=PRINCIPAL,
            owner_binding_digest=OWNER,
            authenticated_receipt_digest=RECEIPT,
            approval_packet_digest=packet["approval_packet_digest"],
            subject_digest=packet["subject_digest"],
            requested_action=packet["requested_action"],
            decided_at=DECIDED,
            expires_at=EXPIRES,
            authenticated_human_receipt_verified=True,
            owner_session_or_signature_verified=True,
        )
        adapter = build_outbound_adapter_manifest(
            adapter_id="contract-export-adapter-1",
            adapter_kind="CONTRACT_EXPORT_ADAPTER",
            version="1.0.0",
            binary_or_build_digest=BUILD,
            logical_capabilities=[
                "EXPORT_CONTRACT_FOR_SIGNATURE_REVIEW"
            ],
            signed_manifest_verified=True,
        )
        bridge = build_outbound_dispatch_bridge(
            contract,
            packet,
            evidence,
            adapter,
            bridge_id="bridge-contract-1",
            idempotency_key_digest=IDEMPOTENCY,
            effect_key_digest=EFFECT,
            now=NOW,
        )
        self.assertEqual(
            bridge["state"],
            "READY_FOR_EXECUTION_AUTHORIZATION_REVIEW",
        )
        self.assertEqual(
            bridge["adapter_kind"],
            "CONTRACT_EXPORT_ADAPTER",
        )
        self.assertFalse(bridge["contract_exported"])
        self.assertFalse(bridge["signature_requested"])
        self.assertFalse(bridge["external_action_executed"])

    def test_bridge_digest_detects_tampering(self):
        *_, bridge = self.ready_bridge()
        self.assertTrue(verify_outbound_dispatch_bridge(bridge)["valid"])

        tampered = copy.deepcopy(bridge)
        tampered["adapter_id"] = "different-adapter"
        verified = verify_outbound_dispatch_bridge(tampered)
        self.assertFalse(verified["valid"])
        self.assertIn("BRIDGE_DIGEST_MISMATCH", verified["blockers"])

    def test_policy_keeps_approval_and_execution_separate(self):
        policy = outbound_dispatch_policy()
        self.assertTrue(policy["exact_approved_subject_digest_required"])
        self.assertTrue(policy["post_approval_mutation_blocks"])
        self.assertTrue(policy["authenticated_human_receipt_required"])
        self.assertTrue(
            policy["owner_session_or_signature_verification_required"]
        )
        self.assertTrue(policy["approval_freshness_required"])
        self.assertTrue(policy["approval_single_use_required"])
        self.assertFalse(policy["approval_is_execution_authorization"])
        self.assertTrue(policy["adapter_signed_manifest_required"])
        self.assertTrue(
            policy["adapter_exact_action_capability_required"]
        )
        self.assertFalse(policy["dynamic_provider_switch_after_approval"])
        self.assertFalse(policy["raw_recipient_in_control_plane"])
        self.assertFalse(policy["endpoint_in_control_plane"])
        self.assertFalse(policy["credential_material_in_control_plane"])
        self.assertTrue(policy["idempotency_key_digest_required"])
        self.assertTrue(policy["effect_key_digest_required"])
        self.assertTrue(
            policy["fresh_execution_authorization_still_required"]
        )
        self.assertTrue(policy["durable_dispatch_record_still_required"])
        self.assertTrue(
            policy["pre_dispatch_revalidation_still_required"]
        )
        self.assertTrue(policy["outcome_receipt_still_required"])
        self.assertFalse(policy["approval_consumed"])
        self.assertFalse(policy["execution_authorization_issued"])
        self.assertFalse(policy["execution_authorized"])
        self.assertFalse(policy["dispatch_record_written"])
        self.assertFalse(policy["recipient_resolved"])
        self.assertFalse(policy["endpoint_resolved"])
        self.assertFalse(policy["credentials_loaded"])
        self.assertFalse(policy["payload_materialized"])
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
