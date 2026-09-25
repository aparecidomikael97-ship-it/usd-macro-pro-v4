import unittest

from atlasquant_aion_intelligence import (
    commander_briefing,
    evidence_audit,
    evidence_confidence,
    scenario_events,
    simulate_macro_scenario,
)


class AtlasQuantAionOperationalIntelligenceTests(unittest.TestCase):
    def test_auditor_detects_confirmed_conflict_without_executing(self):
        audit = evidence_audit([
            {"claim":"deploy","kind":"CONFIRMED","source":"runtime","value":"a"},
            {"claim":"deploy","kind":"CONFIRMED","source":"main","value":"b"},
        ])
        self.assertEqual(audit["status"], "CONFLICT")
        self.assertEqual(audit["conflict_count"], 1)
        self.assertFalse(audit["executes_action"])
        self.assertFalse(audit["real_orders_enabled"])

    def test_evidence_confidence_is_not_profit_probability(self):
        confidence = evidence_confidence([
            {"claim":"c1","kind":"CONFIRMED","source":"source-a","value":1},
            {"claim":"c2","kind":"CONFIRMED","source":"source-b","value":2},
            {"claim":"c3","kind":"INFERENCE","source":"source-c","value":3},
        ])
        self.assertGreater(confidence["score"], 0)
        self.assertFalse(confidence["is_profit_probability"])
        self.assertFalse(confidence["is_market_outcome_probability"])

    def test_single_source_confidence_is_capped(self):
        confidence = evidence_confidence([
            {"claim":f"c{i}","kind":"CONFIRMED","source":"same-source","value":i}
            for i in range(8)
        ])
        self.assertLessEqual(confidence["score"], 60)
        self.assertTrue(confidence["single_source_cap_applied"])

    def test_conflict_caps_evidence_confidence(self):
        audit = evidence_audit([
            {"claim":"x","kind":"CONFIRMED","source":"a","value":"up"},
            {"claim":"x","kind":"CONFIRMED","source":"b","value":"down"},
            {"claim":"y","kind":"CONFIRMED","source":"c","value":"ok"},
        ])
        confidence = evidence_confidence(audit)
        self.assertLessEqual(confidence["score"], 35)
        self.assertTrue(confidence["conflicts_cap_applied"])

    def test_commander_prefers_explicit_executive_next_action(self):
        out = commander_briefing(
            checkpoint={
                "continuity":{
                    "missions":[{
                        "title":"Melhorar AION",
                        "status":"IN_PROGRESS",
                        "next_action":"Continuar módulo.",
                        "blocker":"",
                    }]
                }
            },
            system_context={
                "truth_state":"CONFIRMED",
                "release_gate":{"state":"VERIFY_PRODUCTION"},
                "publication_truth":{"state":"MAIN_MATCH_PRODUCTION_UNVERIFIED"},
            },
            executive_snapshot={
                "primary":{
                    "priority":"P2",
                    "area":"🛠️ Desenvolvimento",
                    "title":"Gate de liberação pendente",
                    "next_action":"Validar produção.",
                }
            },
        )
        self.assertEqual(out["mode"], "COMMANDER")
        self.assertEqual(out["posture"], "VALIDATION")
        self.assertEqual(out["objective"], "Melhorar AION")
        self.assertEqual(out["next_action"], "Validar produção.")
        self.assertFalse(out["automatic_deploy"])
        self.assertFalse(out["real_orders_enabled"])

    def test_commander_blocks_when_release_gate_is_blocked(self):
        out = commander_briefing(
            system_context={
                "truth_state":"CONFIRMED",
                "release_gate":{
                    "state":"BLOCKED",
                    "next_action":"Revalidar tela crítica.",
                },
                "publication_truth":{"state":"UNKNOWN"},
            },
            executive_snapshot={
                "primary":{
                    "priority":"P1",
                    "title":"Gate bloqueado",
                    "next_action":"Revalidar tela crítica.",
                }
            },
        )
        self.assertEqual(out["posture"], "BLOCKED")
        self.assertTrue(out["blockers"])

    def test_macro_simulator_labels_output_as_hypothesis(self):
        out = simulate_macro_scenario(
            "CPI",
            "ABOVE",
            evidence=[
                {"claim":"calendar","kind":"CONFIRMED","source":"calendar","value":"CPI"},
                {"claim":"consensus","kind":"CONFIRMED","source":"source-b","value":"3.0"},
            ],
        )
        self.assertEqual(out["state"], "HYPOTHESIS")
        self.assertEqual(out["scenario_truth_kind"], "HYPOTHESIS")
        self.assertTrue(out["requires_live_confirmation"])
        self.assertFalse(out["is_live_forecast"])
        self.assertFalse(out["is_trade_signal"])
        self.assertGreater(len(out["channels"]), 0)
        self.assertTrue(all(x["truth_kind"]=="HYPOTHESIS" for x in out["channels"]))

    def test_unknown_macro_scenario_fails_closed(self):
        out = simulate_macro_scenario("UNKNOWN_EVENT", "SIDEWAYS")
        self.assertEqual(out["state"], "UNKNOWN")
        self.assertEqual(out["channels"], [])
        self.assertFalse(out["is_trade_signal"])

    def test_expected_scenario_library_is_available(self):
        events = scenario_events()
        for name in ("CPI","PCE","PAYROLL","FOMC","GEOPOLITICAL_RISK"):
            self.assertIn(name, events)


if __name__ == "__main__":
    unittest.main()
