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
