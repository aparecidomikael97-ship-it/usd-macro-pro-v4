import unittest

from atlasquant_aion_gateway import local_answer, provider_status, route_model


class AtlasQuantAionGatewayTests(unittest.TestCase):
    def test_gateway_is_zero_cost_local_by_default(self):
        status = provider_status()
        self.assertEqual(status["state"], "ZERO_COST_LOCAL")
        self.assertFalse(status["external_enabled"])
        self.assertFalse(status["automatic_billing"])

    def test_external_provider_request_stays_blocked_without_feature_flag(self):
        status = provider_status(env={"AION_MODEL_PROVIDER": "external"})
        self.assertEqual(status["state"], "BLOCKED_BY_FEATURE_FLAG")
        self.assertFalse(status["external_enabled"])

    def test_external_flag_does_not_claim_incomplete_provider_is_ready(self):
        status = provider_status(
            feature_flags={"external_llm": True},
            env={"AION_MODEL_PROVIDER": "openai"},
        )
        self.assertEqual(status["state"], "MISSING_API_KEY")
        self.assertFalse(status["external_enabled"])

    def test_external_provider_is_ready_only_with_complete_config_and_flag(self):
        status = provider_status(
            feature_flags={"external_llm": True},
            env={
                "AION_MODEL_PROVIDER": "openai",
                "OPENAI_API_KEY": "sk-test-secret-value",
                "AION_OPENAI_FAST_MODEL": "fast-model",
                "AION_OPENAI_REASONING_MODEL": "reasoning-model",
                "AION_OPENAI_INPUT_USD_PER_MTOK": "1",
                "AION_OPENAI_OUTPUT_USD_PER_MTOK": "2",
            },
        )
        self.assertEqual(status["state"], "EXTERNAL_READY")
        self.assertTrue(status["external_enabled"])
        self.assertNotIn("sk-test-secret-value", str(status))

    def test_route_model_does_not_execute(self):
        route = route_model("corrigir código da interface")
        self.assertEqual(route["domain"], "development")
        self.assertFalse(route["executes_action"])

    def test_local_answer_uses_checkpoint_continuity_for_where_we_stopped(self):
        result = local_answer(
            "onde paramos no sistema?",
            checkpoint={
                "continuity":{
                    "missions":[{
                        "mission_id":"MIS-1",
                        "title":"Fechar interface AION",
                        "domain":"development",
                        "status":"IN_PROGRESS",
                        "objective":"",
                        "outcome":"",
                        "blocker":"",
                        "next_action":"Rodar testes mobile.",
                        "evidence_refs":[],
                        "created_at":"2026-09-24T20:00:00+00:00",
                        "updated_at":"2026-09-24T20:10:00+00:00",
                        "started_at":"2026-09-24T20:10:00+00:00",
                        "completed_at":"",
                        "source":"ADMIN",
                    }],
                    "handoffs":[],
                },
                "operating":{"tasks":[],"events":[]},
            },
        )
        self.assertIn("Fechar interface AION",result["answer"])
        self.assertIn("Rodar testes mobile",result["answer"])
        self.assertIn("síntese do estado estruturado",result["answer"])
        self.assertIn("Nenhum próximo passo é executado automaticamente",result["answer"])
        self.assertFalse(result["executes_action"])

    def test_persisted_handoff_is_identified_as_continuity_source(self):
        result = local_answer(
            "qual o próximo bloco?",
            checkpoint={
                "continuity":{
                    "missions":[],
                    "handoffs":[{
                        "handoff_id":"HOF-1",
                        "created_at":"2026-09-24T21:00:00+00:00",
                        "current_focus":"Publicar versão atual",
                        "completed":["Guardian fechado"],
                        "blockers":["Render não conectado"],
                        "next_steps":["Conectar Render"],
                        "evidence_refs":[],
                        "checkpoint_digest":"abc",
                        "source":"ADMIN",
                    }],
                },
                "operating":{"tasks":[],"events":[]},
            },
        )
        self.assertIn("Publicar versão atual",result["answer"])
        self.assertIn("Conectar Render",result["answer"])
        self.assertIn("último handoff persistido",result["answer"])

    def test_local_answer_does_not_invent_fresh_market_state(self):
        result = local_answer(
            "como está o radar forex agora?",
            checkpoint={"aion": {"priority": "AION"}},
            system_context={},
        )
        self.assertEqual(result["domain"], "trading")
        self.assertIn("não confirmado", result["answer"].lower())
        self.assertFalse(result["real_orders_enabled"])


if __name__ == "__main__":
    unittest.main()
