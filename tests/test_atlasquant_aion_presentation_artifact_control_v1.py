import copy
import unittest

from atlasquant_aion_presentation_artifact_control_v1 import (
    ATTESTATION_SCHEMA,
    build_presentation_artifact_request,
    build_presentation_control_intent,
    evaluate_generated_artifact_attestation,
    presentation_policy,
    verify_presentation_artifact_request,
)
from atlasquant_aion_teaching_meeting_orchestrator_v1 import (
    advance_meeting_session,
    build_meeting_deck,
    start_meeting_session,
)


OWNER = "sha256:" + ("a" * 64)
ARTIFACT = "sha256:" + ("b" * 64)


class AionPresentationArtifactControlV1Tests(unittest.TestCase):
    def deck(self):
        return build_meeting_deck(
            sector="Clínica",
            audience="Direção e comercial",
            objective="Apresentar implantação AION",
            slides=[
                {
                    "slide_id": "s-1",
                    "title": "Abertura",
                    "kind": "TITLE",
                    "objective": "Apresentar a reunião",
                    "content_ref": "deck://clinic/title",
                },
                {
                    "slide_id": "s-2",
                    "title": "Indicadores",
                    "kind": "CHART",
                    "objective": "Mostrar dados validados",
                    "content_ref": "deck://clinic/chart",
                    "evidence_refs": ["evidence://clinic/kpis"],
                    "data_refs": ["data://clinic/kpis"],
                    "validation_refs": ["validation://clinic/kpis"],
                },
                {
                    "slide_id": "s-3",
                    "title": "Próximos passos",
                    "kind": "NEXT_STEPS",
                    "objective": "Fechar próximos passos",
                    "content_ref": "deck://clinic/next",
                },
            ],
        )

    def request(self):
        return build_presentation_artifact_request(
            self.deck(),
            artifact_id="presentation-clinic-1",
            include_speaker_notes=True,
        )

    def attestation(self, request=None, **changes):
        request = request or self.request()
        value = {
            "schema": ATTESTATION_SCHEMA,
            "verified": True,
            "request_digest": request["request_digest"],
            "artifact_ref": "artifact://presentation-clinic-1",
            "artifact_digest": ARTIFACT,
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
        value.update(changes)
        return value

    def artifact_result(self):
        request = self.request()
        result = evaluate_generated_artifact_attestation(
            request,
            self.attestation(request),
        )
        self.assertTrue(result["valid"])
        return request, result

    def meeting_session(self):
        deck = self.deck()
        session = start_meeting_session(
            deck,
            meeting_id="meeting-ppt-1",
            owner_binding_digest=OWNER,
        )
        return deck, session

    def test_request_binds_chart_lineage_without_creating_file(self):
        request = self.request()
        self.assertEqual(request["state"], "READY")
        self.assertEqual(request["output_format"], "PPTX")
        self.assertEqual(request["target_application"], "MICROSOFT_POWERPOINT")
        self.assertEqual(request["aspect_ratio"], "16:9")
        self.assertEqual(request["slide_count"], 3)
        self.assertEqual(request["chart_count"], 1)
        self.assertEqual(request["chart_manifest"][0]["slide_id"], "s-2")
        self.assertTrue(
            request["chart_manifest"][0]["chart_source_digest"].startswith(
                "sha256:"
            )
        )
        self.assertTrue(request["chart_data_lineage_required"])
        self.assertTrue(request["chart_validation_lineage_required"])
        self.assertTrue(request["metric_evidence_lineage_required"])
        self.assertFalse(request["macros_allowed"])
        self.assertFalse(request["vba_allowed"])
        self.assertFalse(request["external_links_allowed"])
        self.assertFalse(request["external_relationships_allowed"])
        self.assertFalse(request["embedded_ole_objects_allowed"])
        self.assertFalse(request["remote_fetch_during_presentation_allowed"])
        self.assertFalse(request["credentials_allowed"])
        self.assertFalse(request["real_customer_data_allowed"])
        self.assertFalse(request["artifact_file_created"])
        self.assertFalse(request["charts_rendered"])
        self.assertFalse(request["powerpoint_opened"])
        self.assertFalse(request["presentation_started"])
        self.assertFalse(request["provider_called"])
        self.assertFalse(request["network_called"])
        self.assertFalse(request["external_action_executed"])
        self.assertFalse(request["executes_action"])
        self.assertTrue(
            verify_presentation_artifact_request(request)["valid"]
        )

    def test_tampered_deck_is_blocked(self):
        deck = self.deck()
        tampered = copy.deepcopy(deck)
        tampered["slide_manifest"][1]["data_refs"] = ["data://tampered"]
        request = build_presentation_artifact_request(
            tampered,
            artifact_id="tampered",
        )
        self.assertEqual(request["state"], "BLOCKED")
        self.assertIn(
            "MEETING_DECK_DIGEST_MISMATCH",
            request["blockers"],
        )

    def test_generated_artifact_attestation_rejects_unsafe_pptx(self):
        request = self.request()
        result = evaluate_generated_artifact_attestation(
            request,
            self.attestation(
                request,
                macros_present=True,
                vba_project_present=True,
                external_links_present=True,
                external_relationships_present=True,
                embedded_ole_objects_present=True,
                remote_fetch_required=True,
                credentials_present=True,
                real_customer_data_present=True,
            ),
        )
        self.assertFalse(result["valid"])
        for key in (
            "macros_present",
            "vba_project_present",
            "external_links_present",
            "external_relationships_present",
            "embedded_ole_objects_present",
            "remote_fetch_required",
            "credentials_present",
            "real_customer_data_present",
        ):
            self.assertIn(
                "ARTIFACT_FORBIDDEN_OR_UNVERIFIED:" + key,
                result["blockers"],
            )

    def test_valid_artifact_attestation_is_evidence_only(self):
        request = self.request()
        result = evaluate_generated_artifact_attestation(
            request,
            self.attestation(request),
        )
        self.assertTrue(result["valid"])
        self.assertEqual(result["state"], "VALID")
        self.assertEqual(result["artifact_digest"], ARTIFACT)
        self.assertFalse(result["artifact_opened_by_this_module"])
        self.assertFalse(result["artifact_generated_by_this_module"])
        self.assertFalse(result["powerpoint_started_by_this_module"])
        self.assertFalse(result["external_action_executed_by_this_module"])
        self.assertFalse(result["executes_action"])

    def test_control_intent_uses_meeting_session_as_slide_source_of_truth(self):
        deck, session = self.meeting_session()
        request, artifact = self.artifact_result()

        session = advance_meeting_session(session, deck, event="START")
        session = advance_meeting_session(
            session,
            deck,
            event="NEXT_SLIDE",
        )
        self.assertEqual(session["current_slide_id"], "s-2")

        intent = build_presentation_control_intent(
            session,
            deck,
            artifact,
            action="SYNC_TO_MEETING_SLIDE",
        )
        self.assertEqual(intent["state"], "READY")
        self.assertEqual(intent["meeting_state"], "PRESENTING")
        self.assertEqual(intent["slide_id"], "s-2")
        self.assertEqual(intent["slide_index"], 1)
        self.assertEqual(intent["artifact_digest"], ARTIFACT)
        self.assertTrue(intent["uses_meeting_orchestrator_as_source_of_truth"])
        self.assertFalse(intent["keyboard_event_sent"])
        self.assertFalse(intent["mouse_event_sent"])
        self.assertFalse(intent["powerpoint_opened"])
        self.assertFalse(intent["slideshow_started"])
        self.assertFalse(intent["slide_changed_physically"])
        self.assertFalse(intent["subprocess_called"])
        self.assertFalse(intent["network_called"])
        self.assertFalse(intent["external_action_executed"])
        self.assertFalse(intent["executes_action"])

    def test_qa_pause_and_resume_keep_same_control_slide(self):
        deck, session = self.meeting_session()
        _, artifact = self.artifact_result()
        session = advance_meeting_session(session, deck, event="START")
        session = advance_meeting_session(
            session,
            deck,
            event="NEXT_SLIDE",
        )
        paused = advance_meeting_session(
            session,
            deck,
            event="QUESTION",
            question="Qual a origem desse gráfico?",
        )
        pause_intent = build_presentation_control_intent(
            paused,
            deck,
            artifact,
            action="SYNC_TO_MEETING_SLIDE",
        )
        self.assertEqual(pause_intent["state"], "READY")
        self.assertEqual(pause_intent["meeting_state"], "PAUSED_FOR_QA")
        self.assertEqual(pause_intent["slide_id"], "s-2")
        self.assertEqual(pause_intent["slide_index"], 1)

        answered = advance_meeting_session(
            paused,
            deck,
            event="ANSWERED",
        )
        resumed = advance_meeting_session(
            answered,
            deck,
            event="RESUME",
        )
        resume_intent = build_presentation_control_intent(
            resumed,
            deck,
            artifact,
            action="SYNC_TO_MEETING_SLIDE",
        )
        self.assertEqual(resume_intent["state"], "READY")
        self.assertEqual(resume_intent["slide_id"], "s-2")
        self.assertEqual(resume_intent["slide_index"], 1)

    def test_control_rejects_session_deck_mismatch(self):
        deck, session = self.meeting_session()
        _, artifact = self.artifact_result()
        session = advance_meeting_session(session, deck, event="START")

        other = copy.deepcopy(deck)
        other["deck_digest"] = "sha256:" + ("f" * 64)
        intent = build_presentation_control_intent(
            session,
            other,
            artifact,
            action="SYNC_TO_MEETING_SLIDE",
        )
        self.assertEqual(intent["state"], "BLOCKED")
        self.assertIn(
            "MEETING_DECK_DIGEST_MISMATCH",
            intent["blockers"],
        )
        self.assertIn(
            "MEETING_SESSION_DECK_MISMATCH",
            intent["blockers"],
        )

    def test_policy_is_fail_closed(self):
        policy = presentation_policy()
        self.assertTrue(policy["meeting_orchestrator_is_slide_source_of_truth"])
        self.assertTrue(policy["chart_data_lineage_required"])
        self.assertTrue(policy["chart_validation_lineage_required"])
        self.assertTrue(policy["metric_evidence_lineage_required"])
        self.assertFalse(policy["macros_allowed"])
        self.assertFalse(policy["vba_allowed"])
        self.assertFalse(policy["external_links_allowed"])
        self.assertFalse(policy["external_relationships_allowed"])
        self.assertFalse(policy["embedded_ole_objects_allowed"])
        self.assertFalse(policy["remote_fetch_during_presentation_allowed"])
        self.assertFalse(policy["credentials_allowed"])
        self.assertFalse(policy["real_customer_data_allowed"])
        self.assertFalse(policy["artifact_file_created"])
        self.assertFalse(policy["charts_rendered"])
        self.assertFalse(policy["powerpoint_opened"])
        self.assertFalse(policy["presentation_started"])
        self.assertFalse(policy["keyboard_event_sent"])
        self.assertFalse(policy["mouse_event_sent"])
        self.assertFalse(policy["subprocess_called"])
        self.assertFalse(policy["provider_called"])
        self.assertFalse(policy["network_called"])
        self.assertFalse(policy["worker_armed"])
        self.assertFalse(policy["deploy_executed"])
        self.assertFalse(policy["core_checkpoint_write"])
        self.assertFalse(policy["external_action_executed"])
        self.assertFalse(policy["executes_action"])


if __name__ == "__main__":
    unittest.main()
