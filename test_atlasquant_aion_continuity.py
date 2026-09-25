import unittest

from atlasquant_aion_continuity import (
    append_handoff,
    build_session_handoff,
    continuity_briefing,
    continuity_digest,
    continuity_summary,
    new_mission,
    normalize_missions,
    transition_mission,
    upsert_mission,
)


class AtlasQuantAionContinuityTests(unittest.TestCase):
    def test_new_mission_is_non_executing_and_persistable(self):
        mission=new_mission(
            "Fechar interface AION",
            domain="development",
            objective="Concluir Central e mobile.",
            next_action="Rodar UI Smoke.",
            created_at="2026-09-24T20:00:00+00:00",
        )
        self.assertEqual(mission["status"],"PLANNED")
        self.assertEqual(mission["domain"],"development")
        self.assertFalse(mission["executes_action"])
        self.assertTrue(mission["mission_id"].startswith("MIS-"))

    def test_mission_transition_tracks_start_done_and_next_action(self):
        mission=new_mission(
            "Missão A",
            created_at="2026-09-24T20:00:00+00:00",
        )
        rows=transition_mission(
            [mission],
            mission["mission_id"],
            "IN_PROGRESS",
            next_action="Validar testes.",
            changed_at="2026-09-24T20:10:00+00:00",
        )
        self.assertEqual(rows[0]["status"],"IN_PROGRESS")
        self.assertEqual(rows[0]["started_at"],"2026-09-24T20:10:00+00:00")
        rows=transition_mission(
            rows,
            mission["mission_id"],
            "DONE",
            outcome="Tudo verde.",
            evidence_refs=["PR#999","sha:abc"],
            changed_at="2026-09-24T20:30:00+00:00",
        )
        self.assertEqual(rows[0]["status"],"DONE")
        self.assertEqual(rows[0]["outcome"],"Tudo verde.")
        self.assertEqual(rows[0]["completed_at"],"2026-09-24T20:30:00+00:00")
        self.assertEqual(rows[0]["evidence_refs"],["PR#999","sha:abc"])

    def test_upsert_replaces_same_mission_without_duplicate(self):
        mission=new_mission(
            "Missão A",
            created_at="2026-09-24T20:00:00+00:00",
        )
        rows=upsert_mission([],mission)
        changed=dict(mission)
        changed["next_action"]="Novo passo"
        rows=upsert_mission(rows,changed)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["next_action"],"Novo passo")

    def test_handoff_synthesizes_only_recorded_state(self):
        active=new_mission(
            "Corrigir Radar",
            next_action="Validar produção.",
            created_at="2026-09-24T20:00:00+00:00",
        )
        done=new_mission(
            "Fechar Guardian",
            created_at="2026-09-24T19:00:00+00:00",
        )
        done=transition_mission(
            [done],done["mission_id"],"DONE",
            outcome="Guardian fechado.",
            changed_at="2026-09-24T19:30:00+00:00",
        )[0]
        active=transition_mission(
            [active],active["mission_id"],"IN_PROGRESS",
            changed_at="2026-09-24T20:05:00+00:00",
        )[0]
        handoff=build_session_handoff(
            [done,active],
            tasks=[],
            events=[],
            checkpoint_digest="abc123",
            created_at="2026-09-24T20:40:00+00:00",
        )
        self.assertEqual(handoff["current_focus"],"Corrigir Radar")
        self.assertIn("Fechar Guardian",handoff["completed"])
        self.assertEqual(handoff["next_steps"],["Validar produção."])
        self.assertFalse(handoff["executes_action"])

    def test_persisted_handoff_wins_over_synthesized_view(self):
        mission=new_mission(
            "Missão atual",
            next_action="Passo sintetizado",
            created_at="2026-09-24T20:00:00+00:00",
        )
        handoff=build_session_handoff(
            [mission],
            checkpoint_digest="abc",
            created_at="2026-09-24T20:10:00+00:00",
        )
        handoff["current_focus"]="Foco persistido"
        rows=append_handoff([],handoff)
        view=continuity_briefing([mission],rows)
        self.assertEqual(view["source"],"PERSISTED_HANDOFF")
        self.assertEqual(view["current_focus"],"Foco persistido")
        self.assertFalse(view["executes_action"])

    def test_summary_and_digest_change_with_mission_history(self):
        empty=continuity_digest([],[])
        mission=new_mission(
            "Missão",
            created_at="2026-09-24T20:00:00+00:00",
        )
        rows=normalize_missions([mission])
        changed=continuity_digest(rows,[])
        self.assertNotEqual(empty,changed)
        summary=continuity_summary(rows,[])
        self.assertEqual(summary["total_missions"],1)
        self.assertEqual(summary["active_missions"],1)
        self.assertEqual(summary["handoff_count"],0)
        self.assertFalse(summary["executes_action"])

    def test_blocked_mission_appears_in_handoff_without_auto_action(self):
        mission=new_mission(
            "Publicar produção",
            next_action="Conectar Render.",
            created_at="2026-09-24T20:00:00+00:00",
        )
        mission=transition_mission(
            [mission],
            mission["mission_id"],
            "BLOCKED",
            blocker="Render ainda não conectado.",
            changed_at="2026-09-24T20:05:00+00:00",
        )[0]
        handoff=build_session_handoff([mission],checkpoint_digest="abc")
        self.assertTrue(handoff["blockers"])
        self.assertIn("Render ainda não conectado",handoff["blockers"][0])
        self.assertFalse(handoff["executes_action"])


if __name__=="__main__":
    unittest.main()
