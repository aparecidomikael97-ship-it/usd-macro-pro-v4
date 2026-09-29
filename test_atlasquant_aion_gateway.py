import unittest

from atlasquant_aion_gateway import local_answer, provider_status, route_model
from atlasquant_aion_model_registry import canonical_fingerprint


TRUSTED = {"tenant_id": "tenant-a", "workspace_id": "administration", "role": "ADMIN"}
EXTERNAL_ENV = {
    "AION_MODEL_PROVIDER": "openai",
    "OPENAI_API_KEY": "sk-test-secret-value",
    "AION_OPENAI_FAST_MODEL": "fast-model",
    "AION_OPENAI_REASONING_MODEL": "reasoning-model",
    "AION_OPENAI_INPUT_USD_PER_MTOK": "1",
    "AION_OPENAI_OUTPUT_USD_PER_MTOK": "2",
}


def approved_registry():
    row = {
        "schema": "ATLASQUANT_AION_MODEL_REGISTRY_V1",
        "provider": "openai",
        "model_id": "fast-model",
        "version": "1",
        "capability": "gateway routing",
        "tenant_id": "tenant-a",
        "workspace_id": "administration",
        "benchmark_refs": ["ci:gateway"],
        "evaluation_state": "HUMAN_REVIEW_CANDIDATE",
        "evaluation_date": "2026-09-29T12:00:00+00:00",
        "latency_ms": 100,
        "reliability": 0.99,
        "cost_class": "ZERO",
        "estimated_cost_usd": 0.0,
        "privacy_class": "PRIVATE",
        "known_failures": [],
        "modalities": ["text"],
        "context_limit": 8192,
        "approval_state": "APPROVED",
        "rollback_target": "local",
        "fallback": "",
        "blockers": [],
        "budget_decision": None,
        "eligible_as_default": True,
        "executes_provider_call": False,
        "executes_billing": False,
        "activates_paid_api": False,
        "digest_kind": "CANONICAL_FINGERPRINT",
        "digest_is_signature": False,
        "notes": "approved offline",
    }
    row["fingerprint"] = canonical_fingerprint(row)
    return {"schema": "ATLASQUANT_AION_MODEL_REGISTRY_V1", "models": [row]}


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
        self.assertEqual(route["lane"], "local_deterministic")
        self.assertFalse(route["executes_action"])
        self.assertFalse(route["executes_provider_call"])
        self.assertFalse(route["executes_billing"])

    def test_ready_provider_without_registry_stays_local(self):
        route = route_model(
            "resuma este status",
            feature_flags={"external_llm": True},
            env=EXTERNAL_ENV,
            trusted_context=TRUSTED,
            model_id="fast-model",
            model_version="1",
        )
        self.assertEqual(route["provider_state"], "EXTERNAL_READY")
        self.assertEqual(route["lane"], "local_deterministic")
        self.assertFalse(route["registry_approved"])
        self.assertIn("NOT_FOUND", route["registry_blockers"])
        self.assertFalse(route["external_lane_allowed"])

    def test_approved_registry_can_expose_external_route_without_calling_provider(self):
        route = route_model(
            "resuma este status",
            feature_flags={"external_llm": True},
            env=EXTERNAL_ENV,
            registry=approved_registry(),
            trusted_context=TRUSTED,
            model_id="fast-model",
            model_version="1",
        )
        self.assertEqual(route["provider_state"], "EXTERNAL_READY")
        self.assertEqual(route["lane"], "external_provider")
        self.assertTrue(route["registry_approved"])
        self.assertTrue(route["external_lane_allowed"])
        self.assertEqual(route["routing_lane"], "EXTERNAL_FAST")
        self.assertFalse(route["executes_provider_call"])
        self.assertFalse(route["executes_billing"])

    def test_tampered_or_cross_tenant_registry_falls_back_local(self):
        registry = approved_registry()
        registry["models"][0]["notes"] = "tampered"
        tampered = route_model(
            "resuma este status",
            feature_flags={"external_llm": True},
            env=EXTERNAL_ENV,
            registry=registry,
            trusted_context=TRUSTED,
            model_id="fast-model",
            model_version="1",
        )
        self.assertEqual(tampered["lane"], "local_deterministic")
        self.assertIn("MODEL_RECORD_INTEGRITY_FAILED", tampered["registry_blockers"])

        cross_tenant = route_model(
            "resuma este status",
            feature_flags={"external_llm": True},
            env=EXTERNAL_ENV,
            registry=approved_registry(),
            trusted_context={"tenant_id": "tenant-b", "workspace_id": "administration", "role": "ADMIN"},
            model_id="fast-model",
            model_version="1",
        )
        self.assertEqual(cross_tenant["lane"], "local_deterministic")
        self.assertIn("SCOPE_MISMATCH", cross_tenant["registry_blockers"])

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

    def test_local_answer_exposes_audited_evidence_confidence(self):
        result = local_answer(
            "como está o radar forex?",
            checkpoint={"aion":{"priority":"AION"}},
            system_context={
                "truth_state":"CONFIRMED",
                "source_build":"build-a",
                "market_status":"não confirmado nesta tela",
            },
        )
        self.assertIn("evidence_audit", result)
        self.assertIn("evidence_confidence", result)
        self.assertEqual(
            result["confidence_basis"],
            "EVIDENCE_QUALITY_NOT_PROFIT_PROBABILITY",
        )
        self.assertFalse(result["evidence_confidence"]["is_profit_probability"])
        self.assertFalse(
            result["evidence_confidence"]["is_market_outcome_probability"]
        )
        self.assertFalse(result["executes_action"])

    def test_local_answer_discloses_fail_closed_reliability(self):
        result = local_answer(
            "como está o sistema?",
            checkpoint={"aion":{"priority":"AION"}},
            system_context={
                "reliability":{
                    "posture":"CRITICAL",
                    "degraded_mode":{"state":"FAIL_CLOSED"},
                    "data_guardian":{
                        "reconciliation":{"conflict_count":2}
                    },
                }
            },
        )
        self.assertEqual(result["reliability_posture"],"CRITICAL")
        self.assertEqual(result["degraded_mode_state"],"FAIL_CLOSED")
        self.assertEqual(result["source_conflicts"],2)
        self.assertIn("não vou escolher uma versão silenciosamente",result["answer"])
        self.assertIn("FAIL-CLOSED",result["answer"])
        self.assertFalse(result["executes_action"])

    def test_local_answer_surfaces_urgent_event_as_inference_not_signal(self):
        result=local_answer(
            "tem alguma notícia urgente?",
            checkpoint={"aion":{"priority":"AION"}},
            system_context={
                "live_event_intelligence":{
                    "state":"WATCHING",
                    "alert_count":1,
                    "urgent_review_count":1,
                    "top_alerts":[{
                        "headline":"Reported military strike near oil route",
                        "truth_state":"INFERENCE",
                        "impact_truth_state":"HYPOTHESIS",
                    }],
                }
            },
        )
        self.assertEqual(result["live_event_state"],"WATCHING")
        self.assertEqual(result["live_event_urgent_review"],1)
        self.assertIn("verdade: INFERENCE",result["answer"])
        self.assertIn("hipótese, não sinal de trade",result["answer"])
        self.assertFalse(result["executes_action"])

    def test_local_answer_exposes_cognitive_specialists_and_critic(self):
        result=local_answer(
            "Analise CPI, Forex e confirme as fontes antes de responder.",
            checkpoint={"aion":{"priority":"AION"}},
            memory_hits=[{"path":"macro.md","excerpt":"CPI"}],
            system_context={
                "source_mesh":{"market_live_confirmed":True},
                "reliability":{"degraded_mode":{"state":"NORMAL"}},
            },
        )
        self.assertIn("cognitive_orchestrator",result)
        self.assertGreaterEqual(result["cognitive_specialists"],2)
        self.assertTrue(result["critic_required"])
        self.assertIn("Conselho cognitivo selecionado",result["answer"])
        self.assertFalse(result["executes_action"])

    def test_local_answer_exposes_epistemic_gate_for_memory(self):
        result=local_answer(
            "o que ficou aprovado?",
            checkpoint={"aion":{"priority":"AION"}},
            memory_hits=[{
                "path":"docs/decision.md",
                "excerpt":"Decisão aprovada.",
                "sha256":"a"*64,
            }],
        )
        self.assertEqual(result["epistemic_state"],"SUPPORTED")
        self.assertFalse(result["memory_action_authorized"])
        self.assertFalse(result["epistemic_core"]["action_authorized"])

    def test_local_answer_exposes_data_decision_fabric_contract(self):
        result=local_answer(
            "estado das decisoes",
            checkpoint={
                "aion":{"priority":"AION"},
                "data_decision_fabric":{"events":[],"decisions":[]},
            },
        )
        self.assertIn("data_decision_fabric",result)
        self.assertEqual(result["fabric_conflicts"],0)
        self.assertEqual(result["fabric_human_review_candidates"],0)
        self.assertFalse(result["executes_action"])
        self.assertFalse(result["real_orders_enabled"])

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
