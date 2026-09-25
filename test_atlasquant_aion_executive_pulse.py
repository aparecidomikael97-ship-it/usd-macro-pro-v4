import unittest

from atlasquant_aion_executive_pulse import executive_pulse, compact_attention_rows


class AtlasQuantAionExecutivePulseTests(unittest.TestCase):
    def test_checkpoint_conflict_is_highest_precedence_and_non_executing(self):
        out=executive_pulse(
            runtime_result={"status":"CONFIRMED","integrity":{"state":"MISMATCH"}},
            incident_snapshot={
                "total":1,
                "counts":{"CRITICAL":1},
                "incidents":[{
                    "severity":"CRITICAL",
                    "title":"Incidente crítico",
                    "detail":"Falha crítica",
                    "source":"test",
                }],
            },
            checkpoint_conflict=True,
        )
        self.assertEqual(out["posture"],"CRITICAL")
        self.assertEqual(out["primary"]["title"],"Conflito do Checkpoint Mestre")
        self.assertEqual(out["recommended_workspace"],"🛠️ Desenvolvimento")
        self.assertFalse(out["executes_action"])
        self.assertFalse(out["real_orders_enabled"])

    def test_critical_incident_becomes_p0_when_no_checkpoint_conflict(self):
        out=executive_pulse(
            runtime_result={"status":"CONFIRMED","integrity":{"state":"CONFIRMED"}},
            incident_snapshot={
                "total":1,
                "counts":{"CRITICAL":1},
                "incidents":[{
                    "severity":"CRITICAL",
                    "title":"Falha de health",
                    "detail":"Health falhou.",
                    "source":"health",
                }],
            },
        )
        self.assertEqual(out["posture"],"CRITICAL")
        self.assertEqual(out["primary"]["priority"],"P0")
        self.assertEqual(out["recommended_workspace"],"🧪 Laboratório")

    def test_pending_approval_routes_to_its_workspace(self):
        out=executive_pulse(
            runtime_result={"status":"CONFIRMED","integrity":{"state":"CONFIRMED"}},
            approval_inbox={
                "status":"CONFIRMED",
                "total":1,
                "next_items":[{
                    "priority":"P1",
                    "area":"studio",
                    "title":"Publicar vídeo",
                }],
            },
        )
        self.assertEqual(out["posture"],"ATTENTION")
        self.assertEqual(out["primary"]["area"],"🎬 Studio")
        self.assertIn("nenhuma aprovação é automática",out["primary"]["next_action"])

    def test_dirty_checkpoint_is_review_not_critical(self):
        out=executive_pulse(
            runtime_result={"status":"CONFIRMED","integrity":{"state":"CONFIRMED"}},
            checkpoint_dirty=True,
        )
        self.assertEqual(out["posture"],"REVIEW")
        self.assertEqual(out["primary"]["priority"],"P2")
        self.assertEqual(out["recommended_workspace"],"🛠️ Desenvolvimento")

    def test_unknown_runtime_never_claims_controlled(self):
        out=executive_pulse(runtime_result={"status":"UNKNOWN"})
        self.assertEqual(out["posture"],"REVIEW")
        self.assertEqual(out["runtime_status"],"UNKNOWN")
        self.assertIn("Runtime",out["primary"]["title"])

    def test_no_urgent_signal_can_be_controlled_without_claiming_external_health(self):
        out=executive_pulse(
            runtime_result={"status":"CONFIRMED","integrity":{"state":"CONFIRMED"}},
            status_board={"has_unresolved":False},
        )
        self.assertEqual(out["posture"],"CONTROLLED")
        self.assertIn("não substitui validação externa",out["primary"]["next_action"].lower())

    def test_confirmed_interface_failure_becomes_p1_attention(self):
        out=executive_pulse(
            runtime_result={"status":"CONFIRMED","integrity":{"state":"CONFIRMED"}},
            interface_validation={
                "state":"ATTENTION",
                "confirmed":1,
                "total":3,
                "remaining":2,
                "next_action":"Revalidar Painel Mestre.",
                "all_confirmed_current_build":False,
            },
        )
        self.assertEqual(out["posture"],"ATTENTION")
        self.assertEqual(out["primary"]["priority"],"P1")
        self.assertIn("interface",out["primary"]["title"].lower())
        self.assertEqual(out["interface_validation_confirmed"],1)
        self.assertEqual(out["interface_validation_remaining"],2)
        self.assertFalse(out["interface_validation_complete"])

    def test_incomplete_interface_validation_is_review_not_failure(self):
        out=executive_pulse(
            runtime_result={"status":"CONFIRMED","integrity":{"state":"CONFIRMED"}},
            interface_validation={
                "state":"IN_PROGRESS",
                "confirmed":2,
                "total":3,
                "remaining":1,
                "next_action":"Validar Radar avançado.",
                "all_confirmed_current_build":False,
            },
        )
        self.assertEqual(out["posture"],"REVIEW")
        self.assertEqual(out["primary"]["priority"],"P2")
        self.assertIn("incompleta",out["primary"]["title"].lower())
        self.assertIn("não é tratada como falha",out["primary"]["detail"])

    def test_complete_interface_validation_adds_no_attention_by_itself(self):
        out=executive_pulse(
            runtime_result={"status":"CONFIRMED","integrity":{"state":"CONFIRMED"}},
            status_board={"has_unresolved":False},
            interface_validation={
                "state":"COMPLETE",
                "confirmed":3,
                "total":3,
                "remaining":0,
                "all_confirmed_current_build":True,
            },
        )
        self.assertEqual(out["posture"],"CONTROLLED")
        self.assertTrue(out["interface_validation_complete"])
        self.assertEqual(out["interface_validation_confirmed"],3)

    def test_publication_mismatch_becomes_p1_attention(self):
        out=executive_pulse(
            runtime_result={"status":"CONFIRMED","integrity":{"state":"CONFIRMED"}},
            publication_truth={
                "state":"RUNTIME_BEHIND_OR_DIVERGED",
                "main_match":"MISMATCH",
                "production_verification":"UNKNOWN",
                "can_claim_latest_main_live":False,
                "next_action":"Revisar deploy.",
            },
        )
        self.assertEqual(out["posture"],"ATTENTION")
        self.assertEqual(out["primary"]["priority"],"P1")
        self.assertIn("main",out["primary"]["title"].lower())
        self.assertEqual(out["publication_main_match"],"MISMATCH")
        self.assertFalse(out["can_claim_latest_main_live"])

    def test_unverified_publication_is_review_not_live_claim(self):
        out=executive_pulse(
            runtime_result={"status":"CONFIRMED","integrity":{"state":"CONFIRMED"}},
            publication_truth={
                "state":"MAIN_MATCH_PRODUCTION_UNVERIFIED",
                "main_match":"MATCH",
                "production_verification":"UNKNOWN",
                "can_claim_latest_main_live":False,
                "next_action":"Validar produção.",
            },
        )
        self.assertEqual(out["posture"],"REVIEW")
        self.assertEqual(out["primary"]["priority"],"P2")
        self.assertIn("não confirmada",out["primary"]["title"].lower())
        self.assertEqual(out["publication_state"],"MAIN_MATCH_PRODUCTION_UNVERIFIED")
        self.assertFalse(out["can_claim_latest_main_live"])

    def test_verified_publication_adds_no_attention_by_itself(self):
        out=executive_pulse(
            runtime_result={"status":"CONFIRMED","integrity":{"state":"CONFIRMED"}},
            status_board={"has_unresolved":False},
            publication_truth={
                "state":"PRODUCTION_VERIFIED",
                "main_match":"MATCH",
                "production_verification":"VERIFIED",
                "can_claim_latest_main_live":True,
            },
        )
        self.assertEqual(out["posture"],"CONTROLLED")
        self.assertTrue(out["can_claim_latest_main_live"])
        self.assertEqual(out["production_verification"],"VERIFIED")

    def test_compact_rows_are_presentation_only(self):
        out=executive_pulse(
            runtime_result={"status":"CONFIRMED","integrity":{"state":"CONFIRMED"}},
            checkpoint_dirty=True,
            foundation_diagnostics=[{"component":"provider"}],
        )
        rows=compact_attention_rows(out)
        self.assertTrue(rows)
        self.assertIn("Prioridade",rows[0])
        self.assertIn("Próxima ação",rows[0])
        self.assertFalse(out["executes_action"])


if __name__=="__main__":
    unittest.main()
