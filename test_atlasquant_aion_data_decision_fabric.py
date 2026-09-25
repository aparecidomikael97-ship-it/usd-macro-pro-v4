from __future__ import annotations

import unittest

from atlasquant_aion_data_decision_fabric import (
    active_fabric_events,
    data_decision_fabric_summary,
    default_data_decision_fabric,
    derive_checkpoint_fabric_events,
    detect_fabric_conflicts,
    evaluate_decision_case,
    merge_fabric_events,
    new_decision_case,
    new_fabric_event,
    record_decision_outcome,
)


class AtlasQuantAionDataDecisionFabricTests(unittest.TestCase):
    def test_confirmed_event_requires_provenance(self):
        event=new_fabric_event(
            "Sem fonte",
            domain="investments",
            event_type="EVIDENCE",
            truth_state="CONFIRMED",
            claim_key="asset.quality",
            value="good",
        )
        self.assertEqual(event["truth_state"],"UNKNOWN")
        self.assertFalse(event["action_authorized"])

    def test_sensitive_value_is_redacted_but_digest_is_kept(self):
        event=new_fabric_event(
            "Documento",
            truth_state="INFERENCE",
            source_ref="vault:doc-1",
            claim_key="document.amount",
            value="R$ 123,45",
            privacy_class="SENSITIVE",
        )
        self.assertEqual(event["value_summary"],"[REDACTED]")
        self.assertTrue(event["value_digest"])

    def test_confirmed_source_conflict_is_preserved_not_silently_resolved(self):
        a=new_fabric_event(
            "Fonte A",
            truth_state="CONFIRMED",
            source_ref="source:a",
            claim_key="macro.cpi",
            value="3.1",
            evidence_refs=["a:1"],
            observed_at="2026-09-25T20:00:00+00:00",
        )
        b=new_fabric_event(
            "Fonte B",
            truth_state="CONFIRMED",
            source_ref="source:b",
            claim_key="macro.cpi",
            value="3.4",
            evidence_refs=["b:1"],
            observed_at="2026-09-25T20:00:01+00:00",
        )
        conflicts=detect_fabric_conflicts([a,b])
        self.assertEqual(len(conflicts),1)
        self.assertFalse(conflicts[0]["automatic_resolution"])

    def test_event_id_collision_with_different_content_fails_closed(self):
        a=new_fabric_event(
            "A",event_id="FAB-FIXED",source_ref="s:a",
            truth_state="CONFIRMED",claim_key="x",value="1",
        )
        b=new_fabric_event(
            "B",event_id="FAB-FIXED",source_ref="s:b",
            truth_state="CONFIRMED",claim_key="x",value="2",
        )
        with self.assertRaises(ValueError):
            merge_fabric_events([a],[b])

    def test_high_stakes_decision_requires_confirmed_evidence_test_and_rollback(self):
        contextual=new_fabric_event(
            "Inferência",
            domain="trading",
            truth_state="INFERENCE",
            source_ref="research:1",
            claim_key="trade.direction",
            value="BUY",
            evidence_refs=["r:1"],
        )
        case=new_decision_case(
            "Avaliar entrada",
            domain="trading",
            hypothesis="Compra",
            required_claim_keys=["trade.direction"],
            evidence_event_ids=[contextual["event_id"]],
            risk_level="HIGH",
            impact="HIGH",
            sensitive_action=True,
            requires_test=True,
        )
        evaluated=evaluate_decision_case(case,[contextual])
        self.assertEqual(evaluated["state"],"RESEARCH_REQUIRED")
        self.assertIn("HIGH_STAKES_REQUIRES_CURRENT_CONFIRMED_EVIDENCE",evaluated["blockers"])
        self.assertFalse(evaluated["action_authorized"])
        self.assertFalse(evaluated["real_trading_enabled"])

    def test_complete_case_reaches_human_review_only(self):
        evidence=new_fabric_event(
            "Evidência",
            domain="development",
            truth_state="CONFIRMED",
            source_ref="ci:quality",
            claim_key="release.tests",
            value="PASS",
            evidence_refs=["run:123"],
        )
        case=new_decision_case(
            "Revisar candidato",
            domain="development",
            hypothesis="Candidato sem regressão",
            required_claim_keys=["release.tests"],
            evidence_event_ids=[evidence["event_id"]],
            test_refs=["ci:run:123"],
            risk_level="HIGH",
            impact="HIGH",
            rollback_plan="Reverter commit.",
            sensitive_action=True,
        )
        evaluated=evaluate_decision_case(case,[evidence])
        self.assertEqual(evaluated["state"],"HUMAN_REVIEW_CANDIDATE")
        self.assertFalse(evaluated["action_authorized"])
        self.assertFalse(evaluated["automatic_execution"])

    def test_confirmed_root_cause_requires_evidence(self):
        case=new_decision_case("Pós-análise",domain="trading",requires_test=False)
        with self.assertRaises(ValueError):
            record_decision_outcome(
                case,
                outcome_summary="Operação negativa",
                truth_state="CONFIRMED",
                evidence_refs=["trade:1"],
                root_cause="Erro de timing",
                root_cause_truth_state="CONFIRMED",
                root_cause_refs=[],
            )

    def test_derived_checkpoint_events_cover_multiple_domains_without_execution(self):
        checkpoint={
            "operating":{
                "tasks":[{
                    "task_id":"TASK-1","title":"Teste","domain":"development",
                    "status":"TODO","created_at":"2026-09-25T20:00:00+00:00",
                }],
                "task_digest":"tasks123",
            },
            "studio":{
                "projects":[{
                    "content_id":"CNT-1","title":"Vídeo","status":"IDEA",
                    "created_at":"2026-09-25T20:00:00+00:00",
                }],
                "digest":"studio123",
            },
            "learning":{
                "episodes":[{
                    "episode_id":"LEARN-1","state":"SETTLED","domain":"trading",
                    "subject":"Setup","actual_outcome":"LOSS",
                    "evidence_refs":["paper:1"],
                    "created_at":"2026-09-25T20:00:00+00:00",
                    "settled_at":"2026-09-25T21:00:00+00:00",
                }],
                "digest":"learn123",
            },
        }
        events=derive_checkpoint_fabric_events(checkpoint)
        domains={x["domain"] for x in events}
        self.assertIn("development",domains)
        self.assertIn("studio",domains)
        self.assertIn("trading",domains)
        self.assertTrue(all(not x["action_authorized"] for x in events))

    def test_default_summary_has_no_automatic_execution(self):
        state=default_data_decision_fabric()
        summary=data_decision_fabric_summary(state)
        self.assertEqual(summary["persisted_events"],0)
        self.assertEqual(summary["decisions"],0)
        self.assertFalse(summary["automatic_execution"])
        self.assertFalse(summary["real_trading_enabled"])


if __name__=="__main__":
    unittest.main()
