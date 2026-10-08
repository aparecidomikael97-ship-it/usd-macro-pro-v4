import copy
import unittest

from atlasquant_aion_owner_stack_integration_certification_v1 import (
    REQUIRED_DIMENSIONS,
    build_integration_evidence,
    certify_owner_stack,
    owner_stack_policy_snapshot,
)
from atlasquant_aion_owner_experience_v1 import (
    command_plan,
    owner_binding,
)
from atlasquant_aion_cognitive_continuity_v1 import (
    cognitive_memory_snapshot,
    prepare_cognitive_continuity,
)
from atlasquant_aion_chat_resume_bridge import SCHEMA as CHAT_RESUME_SCHEMA
from atlasquant_aion_voice_hotword_runtime_v1 import (
    detect_voice_activation,
    route_voice_command,
)
from atlasquant_aion_secure_local_agent_v1 import (
    build_local_action_request,
    evaluate_dispatch_readiness,
)
from atlasquant_aion_teaching_meeting_orchestrator_v1 import (
    advance_meeting_session,
    build_meeting_deck,
    start_meeting_session,
)
from atlasquant_aion_presentation_artifact_control_v1 import (
    ATTESTATION_SCHEMA,
    build_presentation_artifact_request,
    build_presentation_control_intent,
    evaluate_generated_artifact_attestation,
)
from atlasquant_aion_contract_communication_draft_approval_v1 import (
    build_communication_draft,
    build_human_approval_packet,
)
from atlasquant_aion_approval_outbound_dispatch_bridge_v1 import (
    build_approval_decision_evidence,
    build_outbound_adapter_manifest,
    build_outbound_dispatch_bridge,
)


D = lambda c: "sha256:" + (c * 64)
OWNER_BINDING_FALLBACK = D("a")
HEAD_SHA = "1" * 40


class AionOwnerStackIntegrationCertificationV1Tests(unittest.TestCase):
    def access(self):
        return {
            "allowed": True,
            "mode": "AUTHENTICATED",
            "role": "ADMIN",
            "session": {
                "username": "mikael",
                "role": "ADMIN",
                "permissions": ["app:read", "aion:admin", "aion:checkpoint"],
                "credential_fingerprint": "owner-test-fingerprint",
            },
        }

    def assertion(self):
        return {
            "verified": True,
            "principal": "HUMAN_OWNER",
            "subject": "mikael",
            "issuer": "integration-certification-test",
        }

    def test_identity_voice_local_agent_handoff_stays_non_executing(self):
        binding = owner_binding(self.access(), self.assertion())
        self.assertTrue(binding["bound"])
        owner_digest = binding["binding_digest"]

        activation = detect_voice_activation(
            "AION, abre o ChatGPT",
            mode="HOTWORD",
        )
        self.assertTrue(activation["activation_detected"])
        self.assertFalse(activation["grants_owner_authority"])

        route = route_voice_command(
            "AION, abre o ChatGPT",
            activation=activation,
            device="DESKTOP",
            owner_bound=binding["bound"],
            owner_binding_digest=owner_digest,
            session_id="voice-session-integration-1",
            activation_id="activation-integration-1",
            captured_at="2026-10-08T10:00:00+00:00",
        )
        self.assertEqual(route["state"], "ROUTE_READY")
        self.assertEqual(route["adapter_required"], "SECURE_LOCAL_AGENT")
        self.assertFalse(route["external_action_executed"])

        plan = command_plan(
            "AION, abre o ChatGPT",
            device="desktop",
            owner_bound=True,
        )
        request = build_local_action_request(
            plan,
            command_text="AION, abre o ChatGPT",
            owner_subject="mikael",
            owner_binding_digest=owner_digest,
            command_id="cmd-integration-1",
            command_nonce="nonce-integration-1",
            device_id="windows-owner-desktop-1",
            platform="WINDOWS",
            issued_at="2026-10-08T10:00:00+00:00",
            expires_at="2026-10-08T10:00:30+00:00",
        )
        self.assertEqual(request["state"], "REQUEST_READY")

        host = {
            "verified": True,
            "source": "TRUSTED_OWNER_DESKTOP_HOST",
            "mechanism": "WINDOWS_HELLO",
            "fresh_owner_command": True,
            "generic_chat_acknowledgement": False,
            "owner_subject": request["owner_subject"],
            "owner_binding_digest": request["owner_binding_digest"],
            "request_digest": request["request_digest"],
            "command_nonce_digest": request["command_nonce_digest"],
            "cryptographic_verification_performed": True,
        }
        replay = {
            "verified": True,
            "request_digest": request["request_digest"],
            "command_nonce_digest": request["command_nonce_digest"],
            "fresh": True,
            "single_use_claimed": True,
            "durable_replay_rejection": True,
        }
        dispatch = evaluate_dispatch_readiness(
            request,
            trusted_host_authorization=host,
            replay_guard_attestation=replay,
            now="2026-10-08T10:00:10+00:00",
        )
        self.assertEqual(dispatch["state"], "DISPATCH_READY")
        self.assertTrue(dispatch["dispatch_ready"])
        self.assertFalse(dispatch["physical_execution_performed"])
        self.assertFalse(dispatch["network_called"])
        self.assertFalse(dispatch["external_action_executed"])

    def test_memory_continuity_handoff_transfers_digests_not_auth(self):
        snapshot = cognitive_memory_snapshot(
            {},
            {},
            persona="owner",
            domain="BUSINESS",
            accessor_profile="AION_CORE",
            explicit_domains=["BUSINESS"],
            tenant_id="owner",
            limit_per_channel=5,
        )
        self.assertEqual(snapshot["state"], "READY")
        resume = {
            "schema": CHAT_RESUME_SCHEMA,
            "state": "READY",
            "conversation_id": "conv-integration-1",
            "identity_binding_complete": True,
            "identity_binding_digest": D("1"),
            "context_digest": D("2"),
            "checkpoint_id": "checkpoint-integration-1",
            "summary_id": "summary-integration-1",
            "authentication_transferred": False,
            "session_token_transferred": False,
            "credentials_transferred": False,
            "provider_called": False,
            "network_called": False,
            "external_action_executed": False,
            "executes_action": False,
        }
        result = prepare_cognitive_continuity(
            snapshot,
            resume,
            source_device="desktop",
            target_device="mobile",
            owner_subject="mikael",
            conversation_id="conv-integration-1",
            last_turn_id="turn-12",
            missions=[],
            handoffs=[],
            tasks=[],
            events=[],
            checkpoint_digest=D("3"),
            mode="TEACHING",
            topic="Negócios B2B",
            slide=4,
        )
        self.assertEqual(result["state"], "READY")
        self.assertTrue(result["requires_target_reauthentication"])
        self.assertFalse(result["authentication_transferred"])
        self.assertFalse(result["session_token_transferred"])
        self.assertFalse(result["credentials_transferred"])
        self.assertFalse(
            result["cognitive_memory"]["raw_memory_transferred"]
        )
        self.assertFalse(result["resume"]["raw_context_transferred"])
        self.assertFalse(result["external_action_executed"])

    def test_meeting_presentation_handoff_preserves_exact_slide(self):
        deck = build_meeting_deck(
            sector="Clínica",
            audience="Direção",
            objective="Demonstrar AION",
            slides=[
                {
                    "slide_id": "s-1",
                    "title": "Abertura",
                    "kind": "TITLE",
                    "objective": "Abrir",
                    "content_ref": "deck://integration/title",
                },
                {
                    "slide_id": "s-2",
                    "title": "Indicadores",
                    "kind": "CHART",
                    "objective": "Mostrar evidência",
                    "content_ref": "deck://integration/chart",
                    "evidence_refs": ["evidence://integration/chart"],
                    "data_refs": ["data://integration/chart"],
                    "validation_refs": ["validation://integration/chart"],
                },
                {
                    "slide_id": "s-3",
                    "title": "Próximos passos",
                    "kind": "NEXT_STEPS",
                    "objective": "Fechar",
                    "content_ref": "deck://integration/next",
                },
            ],
        )
        session = start_meeting_session(
            deck,
            meeting_id="meeting-integration-1",
            owner_binding_digest=OWNER_BINDING_FALLBACK,
        )
        session = advance_meeting_session(session, deck, event="START")
        session = advance_meeting_session(session, deck, event="NEXT_SLIDE")
        self.assertEqual(session["current_slide_id"], "s-2")
        paused = advance_meeting_session(
            session,
            deck,
            event="QUESTION",
            question="Qual a origem dos dados?",
        )
        answered = advance_meeting_session(paused, deck, event="ANSWERED")
        resumed = advance_meeting_session(answered, deck, event="RESUME")
        self.assertEqual(resumed["current_slide_id"], "s-2")
        self.assertEqual(resumed["current_slide_index"], 1)

        request = build_presentation_artifact_request(
            deck,
            artifact_id="presentation-integration-1",
        )
        attestation = {
            "schema": ATTESTATION_SCHEMA,
            "verified": True,
            "request_digest": request["request_digest"],
            "artifact_ref": "artifact://presentation-integration-1",
            "artifact_digest": D("b"),
            "format": "PPTX",
            "slide_count": request["slide_count"],
            "slide_order_verified": True,
            "chart_lineage_verified": True,
            "metric_evidence_verified": True,
            "speaker_notes_policy_verified": True,
            "macros_present": False,
            "vba_project_present": False,
            "external_links_present": False,
            "external_relationships_present": False,
            "embedded_ole_objects_present": False,
            "remote_fetch_required": False,
            "credentials_present": False,
            "real_customer_data_present": False,
        }
        artifact = evaluate_generated_artifact_attestation(
            request,
            attestation,
        )
        self.assertTrue(artifact["valid"])
        intent = build_presentation_control_intent(
            resumed,
            deck,
            artifact,
            action="SYNC_TO_MEETING_SLIDE",
        )
        self.assertEqual(intent["state"], "READY")
        self.assertEqual(intent["slide_id"], "s-2")
        self.assertEqual(intent["slide_index"], 1)
        self.assertFalse(intent["powerpoint_opened"])
        self.assertFalse(intent["slideshow_started"])
        self.assertFalse(intent["external_action_executed"])

    def test_draft_approval_bridge_never_collapses_approval_into_execution(self):
        draft = build_communication_draft(
            channel="EMAIL",
            recipient_ref="contact://integration-client/primary",
            subject="Rascunho para revisão",
            body="Segue o conteúdo sintético aprovado para revisão.",
        )
        packet = build_human_approval_packet(
            draft,
            action="SEND_EMAIL",
            owner_binding_digest=OWNER_BINDING_FALLBACK,
            reason="Synthetic integration approval.",
        )
        approval = build_approval_decision_evidence(
            approval_packet=packet,
            approval_id="approval-integration-1",
            approval_version=2,
            decision="APPROVED",
            human_principal_ref="owner://mikael",
            human_principal_binding_digest=D("b"),
            owner_binding_digest=OWNER_BINDING_FALLBACK,
            authenticated_receipt_digest=D("c"),
            approval_packet_digest=packet["approval_packet_digest"],
            subject_digest=packet["subject_digest"],
            requested_action="SEND_EMAIL",
            decided_at="2026-10-08T10:00:00+00:00",
            expires_at="2026-10-08T10:04:00+00:00",
            authenticated_human_receipt_verified=True,
            owner_session_or_signature_verified=True,
            approval_consumed=False,
        )
        adapter = build_outbound_adapter_manifest(
            adapter_id="email-integration-adapter-1",
            adapter_kind="EMAIL_PROVIDER",
            version="1.0.0",
            binary_or_build_digest=D("d"),
            logical_capabilities=["SEND_EMAIL"],
            signed_manifest_verified=True,
        )
        bridge = build_outbound_dispatch_bridge(
            draft,
            packet,
            approval,
            adapter,
            bridge_id="bridge-integration-1",
            idempotency_key_digest=D("e"),
            effect_key_digest=D("f"),
            now="2026-10-08T10:01:00+00:00",
        )
        self.assertEqual(
            bridge["state"],
            "READY_FOR_EXECUTION_AUTHORIZATION_REVIEW",
        )
        self.assertFalse(approval["execution_authorized"])
        self.assertFalse(bridge["execution_authorization_issued"])
        self.assertFalse(bridge["execution_authorized"])
        self.assertFalse(bridge["provider_called"])
        self.assertFalse(bridge["network_called"])
        self.assertFalse(bridge["message_sent"])

    def test_policy_snapshot_covers_all_owner_stack_layers(self):
        snapshot = owner_stack_policy_snapshot()
        self.assertEqual(snapshot["state"], "VALID")
        self.assertEqual(
            snapshot["policy_count"],
            snapshot["expected_policy_count"],
        )
        self.assertEqual(snapshot["policy_count"], 14)
        for row in snapshot["policies"]:
            self.assertEqual(row["forbidden_true_violations"], [])
            self.assertFalse(row["executes_action"])

    def _valid_evidence_rows(self):
        snapshot = owner_stack_policy_snapshot()
        policy_by_dimension = {
            row["dimension"]: row for row in snapshot["policies"]
        }
        rows = []
        for dimension in REQUIRED_DIMENSIONS:
            material = policy_by_dimension.get(
                dimension,
                {
                    "cross_stack": dimension == "CROSS_STACK_HANDOFFS",
                    "global_boundary": (
                        dimension == "GLOBAL_NO_SIDE_EFFECT_BOUNDARY"
                    ),
                    "external_action_executed": False,
                    "network_called": False,
                    "provider_called": False,
                    "deploy_executed": False,
                    "worker_armed": False,
                    "core_checkpoint_write": False,
                },
            )
            rows.append(
                build_integration_evidence(
                    dimension=dimension,
                    source_ref="ci://owner-stack-integration-v1",
                    evidence_material=material,
                    test_count=1,
                    passed=True,
                )
            )
        return rows

    def test_full_synthetic_certification_candidate_requires_every_dimension(self):
        result = certify_owner_stack(
            self._valid_evidence_rows(),
            source_ref="ci://owner-stack-integration-v1",
            head_sha=HEAD_SHA,
        )
        self.assertEqual(
            result["state"],
            "SYNTHETIC_OWNER_STACK_CERTIFICATION_CANDIDATE",
        )
        self.assertEqual(
            result["dimension_count"],
            result["required_dimension_count"],
        )
        self.assertEqual(result["missing_dimensions"], [])
        self.assertTrue(result["synthetic_only"])
        self.assertFalse(result["production_ready"])
        self.assertFalse(result["merge_authorized"])
        self.assertFalse(result["deploy_authorized"])
        self.assertFalse(result["worker_activation_authorized"])
        self.assertFalse(result["physical_runtime_certified"])
        self.assertFalse(result["provider_execution_certified"])
        self.assertFalse(result["external_action_authorized"])
        self.assertFalse(result["external_action_executed"])
        self.assertFalse(result["network_called"])
        self.assertFalse(result["provider_called"])

    def test_missing_dimension_blocks_certification(self):
        rows = self._valid_evidence_rows()[:-1]
        result = certify_owner_stack(
            rows,
            source_ref="ci://owner-stack-integration-v1",
            head_sha=HEAD_SHA,
        )
        self.assertEqual(result["state"], "BLOCKED")
        self.assertIn(
            "GLOBAL_NO_SIDE_EFFECT_BOUNDARY",
            result["missing_dimensions"],
        )

    def test_side_effect_claim_cannot_be_certification_evidence(self):
        bad = build_integration_evidence(
            dimension="GLOBAL_NO_SIDE_EFFECT_BOUNDARY",
            source_ref="ci://owner-stack-integration-v1",
            evidence_material={"network_called": True},
            test_count=1,
            passed=True,
        )
        self.assertEqual(bad["state"], "INVALID")
        self.assertIn(
            "EVIDENCE_SIDE_EFFECT_TRUE:network_called",
            bad["blockers"],
        )


if __name__ == "__main__":
    unittest.main()
