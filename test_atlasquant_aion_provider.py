import unittest

from atlasquant_aion_provider import (
    build_provider_prompt,
    estimate_request_cost,
    execute_openai_answer,
    provider_config,
    provider_configuration_status,
)


class _FakeResponse:
    def __init__(self,status_code=200,payload=None):
        self.status_code=status_code
        self._payload=payload or {}
    def json(self):
        return self._payload


class _FakeSession:
    def __init__(self,response):
        self.response=response
        self.calls=[]
    def post(self,url,headers=None,json=None,timeout=None):
        self.calls.append({
            "url":url,
            "headers":dict(headers or {}),
            "json":dict(json or {}),
            "timeout":timeout,
        })
        return self.response


class AtlasQuantAionProviderTests(unittest.TestCase):
    def _env(self):
        return {
            "AION_MODEL_PROVIDER":"openai",
            "OPENAI_API_KEY":"sk-test-secret-value",
            "AION_OPENAI_FAST_MODEL":"fast-model",
            "AION_OPENAI_REASONING_MODEL":"reasoning-model",
            "AION_OPENAI_INPUT_USD_PER_MTOK":"1.0",
            "AION_OPENAI_OUTPUT_USD_PER_MTOK":"2.0",
            "AION_OPENAI_MAX_OUTPUT_TOKENS":"500",
        }

    def test_provider_ready_requires_key_models_and_pricing(self):
        status=provider_configuration_status(self._env())
        self.assertTrue(status["ready"])
        self.assertEqual(status["state"],"EXTERNAL_READY")
        self.assertFalse(status["api_key_exposed"])
        self.assertNotIn("sk-test",str(status))

    def test_missing_pricing_fails_closed(self):
        env=self._env()
        env["AION_OPENAI_INPUT_USD_PER_MTOK"]=""
        status=provider_configuration_status(env)
        self.assertFalse(status["ready"])
        self.assertEqual(status["state"],"MISSING_PRICING_CONFIG")

    def test_estimate_is_positive_when_pricing_exists(self):
        cfg=provider_config(self._env())
        estimate=estimate_request_cost("texto de teste",config=cfg)
        self.assertTrue(estimate["estimable"])
        self.assertGreater(estimate["estimated_max_cost_usd"],0)

    def test_prompt_redacts_common_secret_patterns(self):
        prompt=build_provider_prompt(
            "verifique token=supersecretvalue",
            domain="development",
            memory_hits=[{"path":"x","excerpt":"Bearer abcdefghijklmnopqrstuvwxyz"}],
            system_context={"source_build":"abc","environment":"LOCAL"},
        )
        self.assertNotIn("supersecretvalue",prompt)
        self.assertNotIn("abcdefghijklmnopqrstuvwxyz",prompt)
        self.assertIn("[REDACTED]",prompt)

    def test_prompt_carries_reliability_and_source_conflict_state(self):
        prompt=build_provider_prompt(
            "analise o sistema",
            domain="central",
            system_context={
                "source_build":"abc",
                "environment":"LOCAL",
                "reliability":{
                    "posture":"DEGRADED",
                    "degraded_mode":{"state":"DEGRADED_SAFE"},
                    "data_guardian":{
                        "reconciliation":{"conflict_count":3}
                    },
                },
            },
        )
        self.assertIn("Reliability posture: DEGRADED",prompt)
        self.assertIn("Modo degradado: DEGRADED_SAFE",prompt)
        self.assertIn("Conflitos de fonte confirmados: 3",prompt)
        self.assertIn("não escolha uma fonte escondido",prompt)

    def test_prompt_carries_live_event_truth_and_hypothesis_contract(self):
        prompt=build_provider_prompt(
            "o que aconteceu no mercado?",
            domain="trading",
            system_context={
                "live_event_intelligence":{
                    "state":"WATCHING",
                    "alert_count":2,
                    "urgent_review_count":1,
                    "top_alerts":[{
                        "headline":"Reported military strike near energy route",
                        "truth_state":"INFERENCE",
                        "impact_truth_state":"HYPOTHESIS",
                    }],
                },
            },
        )
        self.assertIn("Live Event Intelligence: WATCHING",prompt)
        self.assertIn("Urgentes para revisão: 1",prompt)
        self.assertIn("truth=INFERENCE",prompt)
        self.assertIn("impact=HYPOTHESIS",prompt)
        self.assertIn("nunca autorização/sinal de trade",prompt)

    def test_prompt_contains_cognitive_council_critic_and_no_chain_of_thought_rule(self):
        prompt=build_provider_prompt(
            "Pesquise CPI e impacto no Forex",
            domain="trading",
            memory_hits=[{"path":"macro.md","excerpt":"CPI"}],
            system_context={
                "source_mesh":{"market_live_confirmed":True},
                "reliability":{"degraded_mode":{"state":"NORMAL"}},
            },
        )
        self.assertIn("Conselho Cognitivo:",prompt)
        self.assertIn("Critic obrigatório: True",prompt)
        self.assertIn("Não exponha chain-of-thought",prompt)
        self.assertIn("proveniência, frescor, independência, contradições",prompt)
        self.assertIn("Entradas WISDOM são memória revisável",prompt)
        self.assertIn("não trate a lição como confirmação atual",prompt)
        self.assertIn("EVIDÊNCIAS DE MEMÓRIA AUDITÁVEL DISPONÍVEIS",prompt)

    def test_external_call_is_blocked_without_explicit_approval(self):
        session=_FakeSession(_FakeResponse())
        result=execute_openai_answer(
            "pergunta normal",
            lane="EXTERNAL_FAST",
            budget={"allow_paid":True,"monthly_limit_usd":10},
            external_feature_enabled=True,
            request_approved=False,
            values=self._env(),
            session=session,
        )
        self.assertFalse(result["called"])
        self.assertEqual(result["state"],"BLOCKED_APPROVAL")
        self.assertEqual(session.calls,[])

    def test_sensitive_prompt_is_never_sent(self):
        session=_FakeSession(_FakeResponse())
        result=execute_openai_answer(
            "minha senha é 123",
            lane="EXTERNAL_FAST",
            budget={"allow_paid":True,"monthly_limit_usd":10},
            external_feature_enabled=True,
            request_approved=True,
            values=self._env(),
            session=session,
        )
        self.assertFalse(result["called"])
        self.assertEqual(result["state"],"BLOCKED_PRIVACY")
        self.assertEqual(session.calls,[])

    def test_successful_response_is_unverified_model_output_and_no_action(self):
        payload={
            "id":"resp_test",
            "output":[{
                "type":"message",
                "content":[{"type":"output_text","text":"Resposta do modelo"}],
            }],
            "usage":{"input_tokens":100,"output_tokens":50},
        }
        session=_FakeSession(_FakeResponse(200,payload))
        result=execute_openai_answer(
            "pergunta normal sem dados sensíveis",
            lane="EXTERNAL_REASONING",
            budget={"allow_paid":True,"monthly_limit_usd":10,"spent_usd_estimate":0},
            external_feature_enabled=True,
            request_approved=True,
            values=self._env(),
            session=session,
        )
        self.assertTrue(result["called"])
        self.assertEqual(result["state"],"ANSWER_READY")
        self.assertEqual(result["answer"],"Resposta do modelo")
        self.assertEqual(result["truth_state"],"MODEL_OUTPUT_UNVERIFIED")
        self.assertFalse(result["executes_action"])
        self.assertFalse(result["real_orders_enabled"])
        self.assertEqual(session.calls[0]["json"]["model"],"reasoning-model")
        self.assertIn("Authorization",session.calls[0]["headers"])
        self.assertNotIn("sk-test-secret-value",str(result))

    def test_budget_blocks_call_before_network(self):
        session=_FakeSession(_FakeResponse())
        result=execute_openai_answer(
            "pergunta normal",
            lane="EXTERNAL_FAST",
            budget={"allow_paid":True,"monthly_limit_usd":0.000001},
            external_feature_enabled=True,
            request_approved=True,
            values=self._env(),
            session=session,
        )
        self.assertFalse(result["called"])
        self.assertEqual(result["state"],"BLOCKED_BUDGET")
        self.assertEqual(session.calls,[])


if __name__=="__main__":
    unittest.main()
