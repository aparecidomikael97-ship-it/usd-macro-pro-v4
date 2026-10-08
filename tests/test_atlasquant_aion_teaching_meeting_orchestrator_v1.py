import unittest

from atlasquant_aion_teaching_meeting_orchestrator_v1 import (
    build_live_demo_plan,
    build_meeting_deck,
    build_teaching_program,
    advance_meeting_session,
    advance_teaching_session,
    orchestrator_handoff_context,
    start_meeting_session,
    start_teaching_session,
    teaching_meeting_policy,
)


OWNER = "sha256:" + ("a" * 64)
SANDBOX = "sha256:" + ("b" * 64)
ANSWER = "sha256:" + ("c" * 64)
EVALUATION = "sha256:" + ("d" * 64)


class AionTeachingMeetingOrchestratorV1Tests(unittest.TestCase):
    def teaching_program(self):
        return build_teaching_program(
            topic="Inflação e impacto no Forex",
            level="BEGINNER",
            learning_objectives=[
                "Entender CPI e Core CPI",
                "Relacionar inflação, juros e moedas",
            ],
            slides=[
                {
                    "slide_id": "t-1",
                    "title": "Objetivos",
                    "kind": "OBJECTIVES",
                    "objective": "Apresentar o que será aprendido",
                    "content_ref": "lesson://inflacao/objectives",
                },
                {
                    "slide_id": "t-2",
                    "title": "O que é inflação",
                    "kind": "CONCEPT",
                    "objective": "Explicar inflação em linguagem simples",
                    "content_ref": "lesson://inflacao/concept",
                },
                {
                    "slide_id": "t-3",
                    "title": "Exercício",
                    "kind": "EXERCISE",
                    "objective": "Verificar compreensão",
                    "content_ref": "lesson://inflacao/exercise",
                },
            ],
            exercises=[
                {
                    "exercise_id": "ex-1",
                    "slide_id": "t-3",
                    "objective": "Identificar efeito de inflação acima do esperado",
                    "prompt_ref": "exercise://inflacao/ex-1",
                    "evaluation_ref": "rubric://inflacao/ex-1",
                }
            ],
            learner_profile_ref="learner://owner/default",
        )

    def meeting_deck(self):
        return build_meeting_deck(
            sector="Clínica",
            audience="Proprietário e gestor comercial",
            objective="Demonstrar como o AION melhora atendimento e conversão",
            client_ref="client://demo/clinic",
            slides=[
                {
                    "slide_id": "m-1",
                    "title": "Abertura",
                    "kind": "TITLE",
                    "objective": "Apresentar a proposta",
                    "content_ref": "deck://clinic/title",
                },
                {
                    "slide_id": "m-2",
                    "title": "Indicadores",
                    "kind": "CHART",
                    "objective": "Mostrar indicadores validados da demonstração",
                    "content_ref": "deck://clinic/chart",
                    "evidence_refs": ["evidence://clinic/chart-source"],
                    "data_refs": ["data://clinic/synthetic-kpis"],
                    "validation_refs": ["validation://clinic/kpis-v1"],
                },
                {
                    "slide_id": "m-3",
                    "title": "Demo ao vivo",
                    "kind": "DEMO",
                    "objective": "Demonstrar fluxo sintético de atendimento",
                    "content_ref": "deck://clinic/demo",
                },
                {
                    "slide_id": "m-4",
                    "title": "Próximos passos",
                    "kind": "NEXT_STEPS",
                    "objective": "Definir o próximo passo comercial",
                    "content_ref": "deck://clinic/next",
                },
            ],
        )

    def ready_demo(self):
        return build_live_demo_plan(
            demo_script_ref="demo://clinic/lead-to-followup",
            sandbox_digest=SANDBOX,
            sandbox_attested=True,
            production_tenant_access=False,
            real_customer_data=False,
            credentials_present=False,
            external_side_effects_possible=False,
            payments_enabled=False,
            trading_enabled=False,
            publication_enabled=False,
            message_send_enabled=False,
        )

    def test_teaching_program_is_plan_only(self):
        program = self.teaching_program()
        self.assertEqual(program["state"], "READY")
        self.assertEqual(program["mode"], "TEACHING")
        self.assertEqual(program["level"], "BEGINNER")
        self.assertEqual(program["slide_count"], 3)
        self.assertEqual(program["exercise_count"], 1)
        self.assertTrue(program["adaptive_depth"])
        self.assertTrue(program["slides_enabled"])
        self.assertTrue(program["exercises_enabled"])
        self.assertFalse(program["raw_memory_written"])
        self.assertFalse(program["memory_promoted"])
        self.assertFalse(program["provider_called"])
        self.assertFalse(program["slides_rendered"])
        self.assertFalse(program["audio_played"])
        self.assertFalse(program["executes_action"])

    def test_teaching_question_resumes_exact_prior_slide(self):
        program = self.teaching_program()
        session = start_teaching_session(
            program,
            session_id="teach-1",
            owner_binding_digest=OWNER,
        )
        session = advance_teaching_session(
            session,
            program,
            event="NEXT_SLIDE",
        )
        self.assertEqual(session["current_slide_id"], "t-2")

        paused = advance_teaching_session(
            session,
            program,
            event="QUESTION",
            question="Por que juros maiores podem fortalecer a moeda?",
        )
        self.assertEqual(paused["state"], "PAUSED_FOR_QA")
        self.assertEqual(paused["return_slide_id"], "t-2")
        self.assertEqual(paused["return_slide_index"], 1)
        self.assertTrue(paused["active_question_digest"].startswith("sha256:"))
        self.assertFalse(paused["raw_question_persisted"])

        answered = advance_teaching_session(
            paused,
            program,
            event="ANSWERED",
        )
        self.assertEqual(answered["state"], "RESUME_PENDING")

        resumed = advance_teaching_session(
            answered,
            program,
            event="RESUME",
        )
        self.assertEqual(resumed["state"], "TEACHING")
        self.assertEqual(resumed["current_slide_id"], "t-2")
        self.assertEqual(resumed["current_slide_index"], 1)
        self.assertEqual(resumed["return_slide_id"], "")
        self.assertEqual(resumed["return_slide_index"], -1)

    def test_teaching_exercise_requires_verified_evaluation(self):
        program = self.teaching_program()
        session = start_teaching_session(
            program,
            session_id="teach-2",
            owner_binding_digest=OWNER,
        )
        session = advance_teaching_session(
            session,
            program,
            event="NEXT_SLIDE",
        )
        session = advance_teaching_session(
            session,
            program,
            event="NEXT_SLIDE",
        )
        exercise = advance_teaching_session(
            session,
            program,
            event="START_EXERCISE",
            exercise_id="ex-1",
        )
        self.assertEqual(exercise["state"], "EXERCISE")

        blocked = advance_teaching_session(
            exercise,
            program,
            event="SUBMIT_EXERCISE",
            answer_digest=ANSWER,
            evaluation={
                "verified": False,
                "exercise_id": "ex-1",
                "evaluation_digest": EVALUATION,
            },
        )
        self.assertEqual(blocked["transition_state"], "BLOCKED")
        self.assertIn("VERIFIED_EVALUATION_REQUIRED", blocked["blockers"])

        feedback = advance_teaching_session(
            exercise,
            program,
            event="SUBMIT_EXERCISE",
            answer_digest=ANSWER,
            evaluation={
                "verified": True,
                "exercise_id": "ex-1",
                "evaluation_digest": EVALUATION,
            },
        )
        self.assertEqual(feedback["state"], "FEEDBACK")
        self.assertEqual(feedback["last_answer_digest"], ANSWER)
        self.assertEqual(feedback["last_evaluation_digest"], EVALUATION)
        self.assertFalse(feedback["raw_answer_persisted"])
        self.assertFalse(feedback["memory_written"])
        self.assertFalse(feedback["checkpoint_written"])

    def test_meeting_chart_requires_data_validation_and_evidence(self):
        blocked = build_meeting_deck(
            sector="Clínica",
            audience="Gestor",
            objective="Apresentar proposta",
            slides=[
                {
                    "slide_id": "c-1",
                    "title": "Gráfico",
                    "kind": "CHART",
                    "objective": "Mostrar KPI",
                    "content_ref": "deck://chart",
                }
            ],
        )
        self.assertEqual(blocked["state"], "BLOCKED")
        self.assertIn(
            "EVIDENCE_REQUIRED_FOR_SLIDE:c-1",
            blocked["blockers"],
        )
        self.assertIn(
            "CHART_DATA_REF_REQUIRED:c-1",
            blocked["blockers"],
        )
        self.assertIn(
            "CHART_VALIDATION_REF_REQUIRED:c-1",
            blocked["blockers"],
        )

    def test_meeting_deck_does_not_claim_powerpoint_or_rendered_charts(self):
        deck = self.meeting_deck()
        self.assertEqual(deck["state"], "READY")
        self.assertEqual(deck["mode"], "MEETING")
        self.assertTrue(deck["pause_for_questions"])
        self.assertTrue(deck["resume_to_prior_slide"])
        self.assertTrue(deck["live_demo_supported"])
        self.assertTrue(deck["evidence_required_for_metrics"])
        self.assertTrue(deck["charts_require_data_and_validation_refs"])
        self.assertFalse(deck["powerpoint_created"])
        self.assertFalse(deck["charts_rendered"])
        self.assertFalse(deck["presentation_started"])
        self.assertFalse(deck["provider_called"])
        self.assertFalse(deck["external_action_executed"])
        self.assertFalse(deck["executes_action"])

    def test_meeting_question_resumes_exact_slide(self):
        deck = self.meeting_deck()
        session = start_meeting_session(
            deck,
            meeting_id="meeting-1",
            owner_binding_digest=OWNER,
        )
        session = advance_meeting_session(
            session,
            deck,
            event="START",
        )
        session = advance_meeting_session(
            session,
            deck,
            event="NEXT_SLIDE",
        )
        self.assertEqual(session["current_slide_id"], "m-2")

        paused = advance_meeting_session(
            session,
            deck,
            event="QUESTION",
            question="De onde vem esse indicador?",
        )
        self.assertEqual(paused["state"], "PAUSED_FOR_QA")
        self.assertEqual(paused["return_slide_id"], "m-2")
        self.assertEqual(paused["return_slide_index"], 1)
        self.assertTrue(paused["active_question_digest"].startswith("sha256:"))

        answered = advance_meeting_session(
            paused,
            deck,
            event="ANSWERED",
        )
        self.assertEqual(answered["state"], "RESUME_PENDING")

        resumed = advance_meeting_session(
            answered,
            deck,
            event="RESUME",
        )
        self.assertEqual(resumed["state"], "PRESENTING")
        self.assertEqual(resumed["current_slide_id"], "m-2")
        self.assertEqual(resumed["current_slide_index"], 1)
        self.assertFalse(resumed["slides_presented_physically"])
        self.assertFalse(resumed["powerpoint_started"])

    def test_demo_requires_synthetic_sandbox_and_zero_external_authority(self):
        blocked = build_live_demo_plan(
            demo_script_ref="demo://bad",
            sandbox_digest=SANDBOX,
            sandbox_attested=True,
            production_tenant_access=True,
            real_customer_data=True,
            credentials_present=True,
            external_side_effects_possible=True,
            payments_enabled=True,
            trading_enabled=True,
            publication_enabled=True,
            message_send_enabled=True,
            environment="PRODUCTION",
        )
        self.assertEqual(blocked["state"], "BLOCKED")
        for expected in (
            "SYNTHETIC_SANDBOX_REQUIRED",
            "PRODUCTION_TENANT_ACCESS_FORBIDDEN",
            "REAL_CUSTOMER_DATA_FORBIDDEN",
            "CREDENTIALS_PRESENT_FORBIDDEN",
            "EXTERNAL_SIDE_EFFECTS_POSSIBLE_FORBIDDEN",
            "PAYMENTS_ENABLED_FORBIDDEN",
            "TRADING_ENABLED_FORBIDDEN",
            "PUBLICATION_ENABLED_FORBIDDEN",
            "MESSAGE_SEND_ENABLED_FORBIDDEN",
        ):
            self.assertIn(expected, blocked["blockers"])

        ready = self.ready_demo()
        self.assertEqual(ready["state"], "READY")
        self.assertEqual(ready["environment"], "SYNTHETIC_SANDBOX")
        self.assertFalse(ready["physical_demo_started"])
        self.assertFalse(ready["network_called"])
        self.assertFalse(ready["external_action_executed"])
        self.assertFalse(ready["executes_action"])

    def test_demo_pause_and_return_to_same_demo_slide(self):
        deck = self.meeting_deck()
        session = start_meeting_session(
            deck,
            meeting_id="meeting-2",
            owner_binding_digest=OWNER,
        )
        session = advance_meeting_session(session, deck, event="START")
        session = advance_meeting_session(
            session,
            deck,
            event="NEXT_SLIDE",
        )
        session = advance_meeting_session(
            session,
            deck,
            event="NEXT_SLIDE",
        )
        self.assertEqual(session["current_slide_id"], "m-3")

        pending = advance_meeting_session(
            session,
            deck,
            event="DEMO_REQUEST",
        )
        self.assertEqual(pending["state"], "DEMO_PENDING")
        self.assertEqual(pending["return_slide_id"], "m-3")

        active = advance_meeting_session(
            pending,
            deck,
            event="DEMO_START",
            demo_plan=self.ready_demo(),
        )
        self.assertEqual(active["state"], "DEMO_ACTIVE")
        self.assertTrue(active["active_demo_plan_digest"].startswith("sha256:"))
        self.assertFalse(active["demo_started_physically"])

        resumed = advance_meeting_session(
            active,
            deck,
            event="DEMO_END",
        )
        self.assertEqual(resumed["state"], "PRESENTING")
        self.assertEqual(resumed["current_slide_id"], "m-3")
        self.assertEqual(resumed["current_slide_index"], 2)
        self.assertEqual(resumed["active_demo_plan_digest"], "")
        self.assertFalse(resumed["external_action_executed"])

    def test_handoff_is_digest_only_and_transfers_no_auth(self):
        program = self.teaching_program()
        session = start_teaching_session(
            program,
            session_id="teach-handoff",
            owner_binding_digest=OWNER,
        )
        handoff = orchestrator_handoff_context(
            session,
            mode="TEACHING",
        )
        self.assertEqual(handoff["state"], "READY")
        self.assertEqual(handoff["context"]["mode"], "TEACHING")
        self.assertEqual(handoff["context"]["current_slide_id"], "t-1")
        self.assertTrue(
            handoff["handoff_context_digest"].startswith("sha256:")
        )
        self.assertFalse(handoff["raw_question_transferred"])
        self.assertFalse(handoff["raw_answer_transferred"])
        self.assertFalse(handoff["raw_slide_content_transferred"])
        self.assertFalse(handoff["authentication_transferred"])
        self.assertFalse(handoff["owner_authority_transferred"])
        self.assertTrue(handoff["requires_target_reauthentication"])
        self.assertFalse(handoff["memory_written"])
        self.assertFalse(handoff["executes_action"])

    def test_policy_is_fail_closed(self):
        policy = teaching_meeting_policy()
        self.assertTrue(policy["reuses_owner_experience_modes"])
        self.assertFalse(policy["creates_second_memory_database"])
        self.assertTrue(policy["teaching_question_pause_supported"])
        self.assertTrue(policy["teaching_exact_slide_resume_required"])
        self.assertTrue(policy["teaching_exercises_supported"])
        self.assertFalse(policy["automatic_memory_promotion"])
        self.assertTrue(policy["meeting_question_pause_supported"])
        self.assertTrue(policy["meeting_exact_slide_resume_required"])
        self.assertTrue(policy["meeting_charts_require_data_refs"])
        self.assertTrue(policy["meeting_charts_require_validation_refs"])
        self.assertTrue(policy["meeting_metrics_require_evidence_refs"])
        self.assertTrue(policy["meeting_demo_requires_synthetic_sandbox"])
        self.assertFalse(policy["production_demo_authority"])
        self.assertFalse(policy["real_customer_data_in_demo"])
        self.assertFalse(policy["payments_in_demo"])
        self.assertFalse(policy["trading_in_demo"])
        self.assertFalse(policy["publication_in_demo"])
        self.assertFalse(policy["message_send_in_demo"])
        self.assertFalse(policy["powerpoint_created"])
        self.assertFalse(policy["presentation_started"])
        self.assertFalse(policy["charts_rendered"])
        self.assertFalse(policy["physical_demo_started"])
        self.assertFalse(policy["provider_called"])
        self.assertFalse(policy["network_called"])
        self.assertFalse(policy["camera_started"])
        self.assertFalse(policy["microphone_started"])
        self.assertFalse(policy["worker_armed"])
        self.assertFalse(policy["deploy_executed"])
        self.assertFalse(policy["core_checkpoint_write"])
        self.assertFalse(policy["external_action_executed"])
        self.assertFalse(policy["executes_action"])


if __name__ == "__main__":
    unittest.main()
