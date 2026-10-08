import copy
import unittest

from atlasquant_aion_advisor_decision_support_v1 import build_advisory_assessment
from atlasquant_aion_contract_communication_draft_approval_v1 import (
    build_contract_draft,
    build_communication_draft,
    build_human_approval_packet,
    verify_human_approval_packet,
    contract_communication_policy,
)
from atlasquant_aion_data_decision_fabric import (
    new_decision_case,
    new_fabric_event,
)


OWNER = "sha256:" + ("a" * 64)
NOW = "2026-10-08T10:00:00+00:00"


class AionContractCommunicationDraftApprovalV1Tests(unittest.TestCase):
    def advisor_assessment(self):
        event = new_fabric_event(
            "Contract review evidence",
            domain="business",
            event_type="EVIDENCE",
            truth_state="CONFIRMED",
            source_ref="source://contract/review-1",
            claim_key="termination_exposure",
            value="asymmetric",
            value_summary="Termination exposure confirmed",
            observed_at=NOW,
        )
        case = new_decision_case(
            "Review termination clause before sending contract",
            domain="business",
            hypothesis="Revision may reduce asymmetric exposure.",
            required_claim_keys=["termination_exposure"],
            evidence_event_ids=[event["event_id"]],
            test_refs=[],
            risk_level="HIGH",
            impact="HIGH",
            reversible=True,
            rollback_plan="rollback://restore-prior-clause",
            requires_test=False,
            sensitive_action=False,
            created_at=NOW,
        )
        return build_advisory_assessment(
            case,
            [event],
            advisory_domain="CONTRACT",
            question="Should the termination clause be revised?",
            options=[
                {
                    "option_id": "revise",
                    "title": "Revise clause",
                    "summary": "Request a narrower termination clause.",
                    "pros": ["Reduces asymmetric exposure"],
                    "cons": ["May extend negotiation"],
                    "evidence_refs": ["source://contract/review-1"],
                    "assumption_refs": [],
                    "dependency_refs": [],
                    "reversible": True,
                    "rollback_ref": "rollback://restore-prior-clause",
                    "cost_band": "LOW",
                    "time_band": "SHORT",
                },
                {
                    "option_id": "retain",
                    "title": "Retain clause",
                    "summary": "Keep the current draft language.",
                    "pros": ["Faster negotiation"],
                    "cons": ["Maintains identified exposure"],
                    "evidence_refs": ["source://contract/review-1"],
                    "assumption_refs": [],
                    "dependency_refs": [],
                    "reversible": True,
                    "rollback_ref": "rollback://restore-prior-clause",
                    "cost_band": "LOW",
                    "time_band": "SHORT",
                },
            ],
            risks=[
                {
                    "risk_id": "clause-risk-1",
                    "category": "LEGAL_CONTRACT",
                    "severity": "HIGH",
                    "statement": "Termination wording may create asymmetric exposure.",
                    "mitigation": "Obtain specialist legal review and negotiate wording.",
                    "evidence_refs": ["source://contract/review-1"],
                    "clause_ref": "contract://msa/clause-12",
                }
            ],
            recommended_option_id="revise",
            recommendation_rationale=(
                "Current evidence supports revising the clause before signature review."
            ),
            probability_estimate={"state": "NOT_ESTIMATED"},
            now=NOW,
        )

    def low_risk_contract(self):
        return build_contract_draft(
            contract_id="contract-1",
            title="AION Business Services Agreement",
            party_refs=["party://atlasquant", "party://client-1"],
            source_refs=["source://proposal/1", "source://terms/template-1"],
            jurisdiction_ref="jurisdiction://BR/MG",
            clauses=[
                {
                    "clause_id": "scope",
                    "heading": "Scope",
                    "body": "Services are limited to the agreed implementation scope.",
                    "summary": "Defines the implementation scope.",
                    "source_ref": "source://terms/template-1#scope",
                    "state": "PROPOSED",
                    "risk_severity": "LOW",
                },
                {
                    "clause_id": "payment",
                    "heading": "Payment",
                    "body": "Commercial values remain subject to the approved proposal.",
                    "summary": "Links payment terms to the approved proposal.",
                    "source_ref": "source://proposal/1#pricing",
                    "state": "PROPOSED",
                    "risk_severity": "MEDIUM",
                },
            ],
        )

    def test_contract_draft_is_non_final_and_non_signing(self):
        contract = self.low_risk_contract()
        self.assertEqual(contract["state"], "DRAFT_READY")
        self.assertEqual(contract["clause_count"], 2)
        self.assertTrue(contract["legal_review_required"])
        self.assertTrue(contract["professional_review_required_for_high_risk"])
        self.assertFalse(contract["contract_is_final_legal_document"])
        self.assertFalse(contract["legal_advice_issued"])
        self.assertFalse(contract["binding_commitment_created"])
        self.assertFalse(contract["contract_signed"])
        self.assertFalse(contract["signature_requested"])
        self.assertFalse(contract["signature_collected"])
        self.assertFalse(contract["publication_ready"])
        self.assertFalse(contract["customer_sent"])
        self.assertFalse(contract["provider_called"])
        self.assertFalse(contract["network_called"])
        self.assertFalse(contract["crm_written"])
        self.assertFalse(contract["memory_written"])
        self.assertFalse(contract["checkpoint_written"])
        self.assertFalse(contract["external_action_executed"])
        self.assertFalse(contract["executes_action"])

    def test_high_risk_clause_requires_valid_advisor_binding(self):
        blocked = build_contract_draft(
            contract_id="contract-2",
            title="High Risk Contract",
            party_refs=["party://atlasquant", "party://client-2"],
            source_refs=["source://terms/template-2"],
            clauses=[
                {
                    "clause_id": "termination",
                    "heading": "Termination",
                    "body": "Termination language under review.",
                    "summary": "Termination clause requires risk review.",
                    "source_ref": "source://terms/template-2#termination",
                    "state": "PROPOSED",
                    "risk_severity": "HIGH",
                    "advisor_risk_refs": ["clause-risk-1"],
                }
            ],
        )
        self.assertEqual(blocked["state"], "BLOCKED")
        self.assertIn(
            "HIGH_RISK_CLAUSE_REQUIRES_ADVISOR:termination",
            blocked["blockers"],
        )

        advisor = self.advisor_assessment()
        self.assertEqual(advisor["state"], "READY_FOR_HUMAN_REVIEW")
        ready = build_contract_draft(
            contract_id="contract-2",
            title="High Risk Contract",
            party_refs=["party://atlasquant", "party://client-2"],
            source_refs=["source://terms/template-2"],
            advisor_assessment=advisor,
            clauses=[
                {
                    "clause_id": "termination",
                    "heading": "Termination",
                    "body": "Termination language under review.",
                    "summary": "Termination clause requires risk review.",
                    "source_ref": "source://terms/template-2#termination",
                    "state": "REVISED",
                    "risk_severity": "HIGH",
                    "advisor_risk_refs": ["clause-risk-1"],
                }
            ],
        )
        self.assertEqual(ready["state"], "DRAFT_READY")
        self.assertEqual(
            ready["advisor_assessment_digest"],
            advisor["assessment_digest"],
        )
        self.assertFalse(ready["clauses"][0]["legal_conclusion"])

    def test_email_draft_uses_logical_recipient_only(self):
        contract = self.low_risk_contract()
        draft = build_communication_draft(
            channel="EMAIL",
            recipient_ref="contact://client-1/primary",
            subject="Contrato para revisão",
            body="Segue o rascunho para sua revisão. Nenhuma assinatura foi solicitada.",
            attachment_refs=["artifact://contract-1-draft.pdf"],
            related_contract_digest=contract["contract_digest"],
            conversation_ref="crm://client-1/thread-1",
        )
        self.assertEqual(draft["state"], "DRAFT_READY")
        self.assertEqual(draft["channel"], "EMAIL")
        self.assertEqual(draft["recipient_ref"], "contact://client-1/primary")
        self.assertFalse(draft["recipient_address_resolved"])
        self.assertFalse(draft["recipient_phone_resolved"])
        self.assertTrue(draft["approval_required"])
        self.assertFalse(draft["approved"])
        self.assertFalse(draft["execution_authorized"])
        self.assertFalse(draft["message_sent"])
        self.assertFalse(draft["delivery_confirmed"])
        self.assertFalse(draft["provider_called"])
        self.assertFalse(draft["network_called"])
        self.assertFalse(draft["crm_written"])
        self.assertFalse(draft["external_action_executed"])
        self.assertFalse(draft["executes_action"])

    def test_raw_email_or_phone_locator_is_rejected(self):
        raw_email = build_communication_draft(
            channel="EMAIL",
            recipient_ref="client@example.com",
            subject="Teste",
            body="Mensagem",
        )
        self.assertEqual(raw_email["state"], "BLOCKED")
        self.assertIn(
            "LOGICAL_RECIPIENT_REF_REQUIRED",
            raw_email["blockers"],
        )

        raw_phone = build_communication_draft(
            channel="WHATSAPP",
            recipient_ref="+5531999999999",
            body="Mensagem",
        )
        self.assertEqual(raw_phone["state"], "BLOCKED")
        self.assertIn(
            "LOGICAL_RECIPIENT_REF_REQUIRED",
            raw_phone["blockers"],
        )

    def test_whatsapp_draft_has_no_subject_and_does_not_send(self):
        draft = build_communication_draft(
            channel="WHATSAPP",
            recipient_ref="crm://client-2/whatsapp-primary",
            subject="Should be removed",
            body="Olá. Posso enviar o rascunho para revisão?",
        )
        self.assertEqual(draft["state"], "DRAFT_READY")
        self.assertEqual(draft["subject"], "")
        self.assertFalse(draft["message_sent"])
        self.assertFalse(draft["network_called"])

    def test_email_approval_packet_is_pending_not_approved(self):
        draft = build_communication_draft(
            channel="EMAIL",
            recipient_ref="contact://client-1/primary",
            subject="Contrato para revisão",
            body="Segue o rascunho para revisão.",
        )
        packet = build_human_approval_packet(
            draft,
            action="SEND_EMAIL",
            owner_binding_digest=OWNER,
            reason="Owner must approve the exact outgoing draft.",
        )
        self.assertEqual(packet["state"], "PENDING_HUMAN_APPROVAL")
        self.assertEqual(packet["approval_gate_action"], "EXTERNAL_CHANGE")
        self.assertEqual(packet["requested_action"], "SEND_EMAIL")
        self.assertEqual(packet["subject_type"], "COMMUNICATION")
        self.assertTrue(packet["approval_required"])
        self.assertFalse(packet["approved"])
        self.assertFalse(packet["rejected"])
        self.assertFalse(packet["approval_decision_recorded"])
        self.assertFalse(packet["approval_receipt_verified"])
        self.assertFalse(packet["execution_authorized"])
        self.assertFalse(packet["approval_is_execution"])
        self.assertFalse(packet["message_sent"])
        self.assertFalse(packet["network_called"])
        self.assertTrue(verify_human_approval_packet(packet)["valid"])

    def test_contract_export_packet_does_not_request_signature_itself(self):
        contract = self.low_risk_contract()
        packet = build_human_approval_packet(
            contract,
            action="EXPORT_CONTRACT_FOR_SIGNATURE_REVIEW",
            owner_binding_digest=OWNER,
            reason="Review exact contract draft before any signature workflow.",
        )
        self.assertEqual(packet["state"], "PENDING_HUMAN_APPROVAL")
        self.assertEqual(packet["subject_type"], "CONTRACT")
        self.assertFalse(packet["contract_signed"])
        self.assertFalse(packet["execution_authorized"])
        self.assertFalse(packet["external_action_executed"])

    def test_action_mismatch_is_blocked(self):
        email = build_communication_draft(
            channel="EMAIL",
            recipient_ref="contact://client-3/primary",
            subject="Review",
            body="Please review.",
        )
        packet = build_human_approval_packet(
            email,
            action="SEND_WHATSAPP",
            owner_binding_digest=OWNER,
            reason="Wrong channel should fail closed.",
        )
        self.assertEqual(packet["state"], "BLOCKED")
        self.assertIn(
            "COMMUNICATION_ACTION_MISMATCH",
            packet["blockers"],
        )

    def test_approval_packet_digest_detects_tampering(self):
        draft = build_communication_draft(
            channel="WHATSAPP",
            recipient_ref="crm://client-4/whatsapp-primary",
            body="Mensagem para aprovação.",
        )
        packet = build_human_approval_packet(
            draft,
            action="SEND_WHATSAPP",
            owner_binding_digest=OWNER,
            reason="Owner approval required.",
        )
        self.assertTrue(verify_human_approval_packet(packet)["valid"])

        tampered = copy.deepcopy(packet)
        tampered["reason"] = "Changed after packet creation."
        verified = verify_human_approval_packet(tampered)
        self.assertFalse(verified["valid"])
        self.assertIn(
            "APPROVAL_PACKET_DIGEST_MISMATCH",
            verified["blockers"],
        )

    def test_policy_keeps_draft_approval_execution_separate(self):
        policy = contract_communication_policy()
        self.assertTrue(policy["logical_recipient_refs_only"])
        self.assertFalse(policy["raw_email_address_in_control_plane"])
        self.assertFalse(policy["raw_phone_number_in_control_plane"])
        self.assertTrue(policy["contract_draft_supported"])
        self.assertTrue(policy["clause_summary_supported"])
        self.assertTrue(policy["advisor_risk_binding_supported"])
        self.assertTrue(policy["high_risk_clause_requires_advisor"])
        self.assertFalse(policy["contract_is_final_legal_document"])
        self.assertFalse(policy["legal_advice_authority"])
        self.assertTrue(policy["legal_review_required"])
        self.assertFalse(policy["contract_signing_authority"])
        self.assertFalse(policy["signature_collection_authority"])
        self.assertFalse(policy["email_send_authority"])
        self.assertFalse(policy["whatsapp_send_authority"])
        self.assertEqual(policy["approval_gate_action"], "EXTERNAL_CHANGE")
        self.assertTrue(policy["approval_required_before_external_send"])
        self.assertFalse(policy["approval_is_execution"])
        self.assertFalse(policy["approved"])
        self.assertFalse(policy["execution_authorized"])
        self.assertFalse(policy["contract_signed"])
        self.assertFalse(policy["message_sent"])
        self.assertFalse(policy["provider_called"])
        self.assertFalse(policy["network_called"])
        self.assertFalse(policy["crm_written"])
        self.assertFalse(policy["memory_written"])
        self.assertFalse(policy["worker_armed"])
        self.assertFalse(policy["deploy_executed"])
        self.assertFalse(policy["core_checkpoint_write"])
        self.assertFalse(policy["external_action_executed"])
        self.assertFalse(policy["executes_action"])


if __name__ == "__main__":
    unittest.main()
