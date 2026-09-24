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
