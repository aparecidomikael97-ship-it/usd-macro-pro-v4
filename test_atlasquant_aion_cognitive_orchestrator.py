import unittest

from atlasquant_aion_cognitive_orchestrator import (
    build_research_plan,
    orchestrator_snapshot,
    route_specialists,
    verify_claims,
)


class AtlasQuantAionCognitiveOrchestratorTests(unittest.TestCase):
    def test_multi_domain_question_routes_to_relevant_specialists(self):
        out=route_specialists(
            "Analise o CPI, o impacto no Forex e veja se há problema de segurança no feed.",
            domain_hint="trading",
        )
        ids={x["id"] for x in out["selected"]}
        self.assertIn("macro",ids)
        self.assertIn("market_structure",ids)
        self.assertIn("security",ids)
        self.assertTrue(out["critic_required"])
        self.assertFalse(out["executes_model_call"])

    def test_unknown_question_still_routes_to_research_and_memory(self):
        out=route_specialists("Explique isso com cuidado")
        ids={x["id"] for x in out["selected"]}
        self.assertIn("research",ids)
        self.assertIn("memory",ids)

    def test_time_sensitive_research_requires_live_confirmation(self):
        plan=build_research_plan(
            "O que está acontecendo no mercado agora?",
            specialists=route_specialists("mercado agora")["selected"],
            system_context={
                "source_mesh":{"market_live_confirmed":False},
                "reliability":{"degraded_mode":{"state":"DEGRADED_SAFE"}},
            },
        )
        self.assertTrue(plan["time_sensitive"])
        self.assertFalse(plan["market_live_confirmed"])
        self.assertTrue(plan["blockers"])
        self.assertFalse(plan["web_research_executed"])

    def test_confirmed_claim_without_source_is_revised(self):
        out=verify_claims([
            {
                "claim":"O deploy foi concluído.",
                "truth_state":"CONFIRMED",
                "source_refs":[],
            }
        ])
        self.assertEqual(out["state"],"REVISE")
        self.assertIn(
            "CONFIRMED_WITHOUT_SOURCE",
            [x["issue"] for x in out["issues"]],
        )

    def test_external_action_claim_without_evidence_is_blocked(self):
        out=verify_claims([
            {
                "claim":"A publicação foi executada.",
                "truth_state":"CONFIRMED",
                "source_refs":[],
                "external_action_claim":True,
            }
        ])
        self.assertEqual(out["state"],"BLOCK")
        self.assertFalse(out["executes_action"])

    def test_sensitive_claim_during_fail_closed_is_blocked(self):
        out=verify_claims(
            [{
                "claim":"O sistema está seguro para uma ação sensível.",
                "truth_state":"INFERENCE",
                "source_refs":["guardian"],
                "sensitive":True,
            }],
            reliability={"degraded_mode":{"state":"FAIL_CLOSED"}},
        )
        self.assertEqual(out["state"],"BLOCK")

    def test_verified_claims_do_not_expose_chain_of_thought(self):
        out=verify_claims([
            {
                "claim":"Checkpoint íntegro.",
                "truth_state":"CONFIRMED",
                "source_refs":["checkpoint_integrity"],
            }
        ],evidence=[
            {
                "claim":"checkpoint_integrity",
                "kind":"CONFIRMED",
                "source":"runtime",
                "value":"CONFIRMED",
            }
        ])
        self.assertEqual(out["state"],"PASS")
        self.assertFalse(out["private_chain_of_thought_exposed"])

    def test_snapshot_is_zero_cost_and_action_free(self):
        out=orchestrator_snapshot(
            "Pesquise Payroll e impacto no USD",
            domain_hint="trading",
            memory_hits=[{"path":"macro.md","excerpt":"Payroll"}],
            system_context={
                "source_mesh":{"market_live_confirmed":True},
                "reliability":{"degraded_mode":{"state":"NORMAL"}},
            },
        )
        self.assertGreater(out["routing"]["selected_count"],0)
        self.assertTrue(out["critic_gate"]["required"])
        self.assertFalse(out["synthesis_contract"]["show_private_chain_of_thought"])
        self.assertFalse(out["automatic_web_research"])
        self.assertFalse(out["automatic_external_model_call"])
        self.assertFalse(out["automatic_action"])
        self.assertFalse(out["real_orders_enabled"])


if __name__=="__main__":
    unittest.main()
