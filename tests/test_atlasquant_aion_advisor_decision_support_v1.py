import copy
import unittest

from atlasquant_aion_advisor_decision_support_v1 import (
    build_advisory_assessment,
    verify_advisory_assessment,
    advisor_policy,
)
from atlasquant_aion_data_decision_fabric import (
    new_decision_case,
    new_fabric_event,
)


NOW = "2026-10-08T10:00:00+00:00"


class AionAdvisorDecisionSupportV1Tests(unittest.TestCase):
    def events(self):
        first = new_fabric_event(
            "CRM follow-up evidence",
            domain="business",
            event_type="EVIDENCE",
            truth_state="CONFIRMED",
            source_ref="source://crm/audit-1",
            claim_key="followup_gap",
            value="high",
            value_summary="Follow-up gap confirmed",
            observed_at=NOW,
        )
        second = new_fabric_event(
            "Pilot conversion evidence",
            domain="business",
            event_type="EVIDENCE",
            truth_state="CONFIRMED",
            source_ref="source://pilot/metrics-1",
            claim_key="pilot_conversion",
            value="positive",
            value_summary="Pilot conversion improved",
            observed_at=NOW,
        )
        return [first, second]

    def decision_case(self, events=None, **changes):
        events = events or self.events()
        raw = new_decision_case(
            "Choose rollout approach for AION follow-up automation",
            domain="business",
            hypothesis="A staged rollout reduces implementation risk.",
            required_claim_keys=["followup_gap", "pilot_conversion"],
            evidence_event_ids=[row["event_id"] for row in events],
            test_refs=["test://pilot/clinic-v1"],
            risk_level="MEDIUM",
            impact="MEDIUM",
            reversible=True,
            rollback_plan="rollback://disable-followup-automation",
            requires_test=True,
            sensitive_action=False,
            created_by="AION",
            created_at=NOW,
        )
        raw.update(changes)
        return raw

    def options(self):
        return [
            {
                "option_id": "staged",
                "title": "Staged rollout",
                "summary": "Roll out to a synthetic/pilot cohort before expansion.",
                "pros": ["Lower operational risk", "Provides measurable learning"],
                "cons": ["Slower full rollout"],
                "evidence_refs": [
                    "source://crm/audit-1",
                    "source://pilot/metrics-1",
                ],
                "assumption_refs": ["assumption://capacity/pilot"],
                "dependency_refs": ["dependency://sandbox-ready"],
                "reversible": True,
                "rollback_ref": "rollback://disable-followup-automation",
                "cost_band": "LOW",
                "time_band": "SHORT",
            },
            {
                "option_id": "full",
                "title": "Full rollout",
                "summary": "Enable the planned feature for the full intended cohort.",
                "pros": ["Faster coverage"],
                "cons": ["Higher operational exposure", "Harder failure isolation"],
                "evidence_refs": ["source://crm/audit-1"],
                "assumption_refs": ["assumption://capacity/full"],
                "dependency_refs": ["dependency://all-integrations-ready"],
                "reversible": True,
                "rollback_ref": "rollback://disable-followup-automation",
                "cost_band": "MEDIUM",
                "time_band": "SHORT",
            },
        ]

    def assessment(self, **changes):
        kwargs = {
            "decision_case": self.decision_case(),
            "fabric_events": self.events(),
            "advisory_domain": "BUSINESS",
            "question": "Qual abordagem reduz risco sem perder velocidade?",
            "options": self.options(),
            "risks": [
                {
                    "risk_id": "ops-1",
                    "category": "OPERATIONS",
                    "severity": "MEDIUM",
                    "statement": "Rollout integral increases blast radius.",
                    "mitigation": "Start with a bounded cohort.",
                    "evidence_refs": ["source://pilot/metrics-1"],
                }
            ],
            "recommended_option_id": "staged",
            "recommendation_rationale": (
                "The staged option preserves rollback and is supported by "
                "the current pilot evidence."
            ),
            "probability_estimate": {"state": "NOT_ESTIMATED"},
            "now": NOW,
        }
        kwargs.update(changes)
        return build_advisory_assessment(**kwargs)

    def test_evidence_supported_advice_is_human_review_only(self):
        result = self.assessment()
        self.assertEqual(result["state"], "READY_FOR_HUMAN_REVIEW")
        self.assertEqual(result["decision_state"], "HUMAN_REVIEW_CANDIDATE")
        self.assertEqual(result["confidence_posture"], "EVIDENCE_SUPPORTED")
        self.assertEqual(result["evidence_coverage_pct"], 100.0)
        self.assertTrue(result["recommendation_ready"])
        self.assertEqual(result["recommended_option_id"], "staged")
        self.assertTrue(result["owner_decision_required"])
        self.assertFalse(result["recommendation_is_approval"])
        self.assertFalse(result["approval_is_execution"])
        self.assertFalse(result["action_authorized"])
        self.assertFalse(result["automatic_execution"])
        self.assertFalse(result["external_action_executed"])
        self.assertTrue(verify_advisory_assessment(result)["valid"])

    def test_missing_required_evidence_blocks_recommendation(self):
        events = self.events()[:1]
        case = self.decision_case(
            events=self.events(),
            evidence_event_ids=[events[0]["event_id"]],
        )
        result = self.assessment(
            decision_case=case,
            fabric_events=events,
        )
        self.assertEqual(result["state"], "RESEARCH_REQUIRED")
        self.assertEqual(result["decision_state"], "RESEARCH_REQUIRED")
        self.assertFalse(result["recommendation_ready"])
        self.assertEqual(result["recommended_option_id"], "")
        self.assertIn(
            "DECISION_GATE:REQUIRED_EVIDENCE_MISSING",
            result["blockers"],
        )

    def test_conflicting_confirmed_evidence_blocks_advice(self):
        events = self.events()
        conflict = new_fabric_event(
            "Conflicting pilot result",
            domain="business",
            event_type="EVIDENCE",
            truth_state="CONFIRMED",
            source_ref="source://independent/audit-2",
            claim_key="pilot_conversion",
            value="negative",
            value_summary="Independent audit found no improvement",
            observed_at=NOW,
        )
        all_events = [*events, conflict]
        case = self.decision_case(
            events=all_events,
            evidence_event_ids=[row["event_id"] for row in all_events],
        )
        result = self.assessment(
            decision_case=case,
            fabric_events=all_events,
        )
        self.assertEqual(result["state"], "BLOCKED")
        self.assertEqual(result["confidence_posture"], "CONFLICTED_EVIDENCE")
        self.assertFalse(result["recommendation_ready"])
        self.assertIn("DECISION_GATE:EVIDENCE_CONFLICT", result["blockers"])

    def test_critical_risk_forces_risk_review(self):
        result = self.assessment(
            risks=[
                {
                    "risk_id": "security-1",
                    "category": "SECURITY",
                    "severity": "CRITICAL",
                    "statement": "A compromised credential could expose the tenant.",
                    "mitigation": "Require credential rotation and isolation.",
                    "evidence_refs": ["evidence://security/finding-1"],
                }
            ]
        )
        self.assertEqual(result["state"], "RISK_REVIEW_REQUIRED")
        self.assertEqual(result["critical_risk_count"], 1)
        self.assertFalse(result["recommendation_ready"])
        self.assertEqual(result["recommended_option_id"], "")
        self.assertFalse(result["action_authorized"])

    def test_contract_risk_is_flag_not_legal_conclusion(self):
        result = self.assessment(
            advisory_domain="CONTRACT",
            risks=[
                {
                    "risk_id": "clause-1",
                    "category": "LEGAL_CONTRACT",
                    "severity": "HIGH",
                    "statement": (
                        "The termination clause may create asymmetric exposure."
                    ),
                    "mitigation": "Request specialist legal review before signing.",
                    "evidence_refs": ["evidence://contract/review-note-1"],
                    "clause_ref": "contract://proposal/clause-12",
                }
            ],
        )
        self.assertEqual(result["state"], "READY_FOR_HUMAN_REVIEW")
        self.assertFalse(result["legal_conclusion_issued"])
        risk = result["risks"][0]
        self.assertFalse(risk["legal_conclusion"])
        self.assertTrue(risk["professional_review_recommended"])
        self.assertFalse(result["contract_signed"])

    def test_high_contract_risk_requires_clause_ref(self):
        result = self.assessment(
            advisory_domain="CONTRACT",
            risks=[
                {
                    "risk_id": "clause-2",
                    "category": "LEGAL_CONTRACT",
                    "severity": "HIGH",
                    "statement": "Potentially asymmetric indemnity.",
                    "mitigation": "Seek specialist review.",
                    "evidence_refs": ["evidence://contract/review-note-2"],
                }
            ],
        )
        self.assertEqual(result["state"], "BLOCKED")
        self.assertIn(
            "CONTRACT_CLAUSE_REF_REQUIRED:clause-2",
            result["blockers"],
        )
        self.assertFalse(result["recommendation_ready"])

    def test_probability_requires_calibrated_range_not_false_precision(self):
        precise = self.assessment(
            probability_estimate={
                "state": "EVIDENCE_SUPPORTED_RANGE",
                "min_pct": 71,
                "max_pct": 74,
                "method_ref": "method://pilot/outcomes-v1",
                "calibration_ref": "calibration://pilot/v1",
                "evidence_refs": ["evidence://pilot/outcomes"],
            }
        )
        self.assertEqual(precise["state"], "BLOCKED")
        self.assertIn(
            "PROBABILITY_RANGE_TOO_PRECISE",
            precise["blockers"],
        )
        self.assertFalse(precise["single_point_success_probability_used"])
        self.assertFalse(precise["false_precision_allowed"])

        ranged = self.assessment(
            probability_estimate={
                "state": "EVIDENCE_SUPPORTED_RANGE",
                "min_pct": 55,
                "max_pct": 75,
                "method_ref": "method://pilot/outcomes-v1",
                "calibration_ref": "calibration://pilot/v1",
                "evidence_refs": ["evidence://pilot/outcomes"],
            }
        )
        self.assertEqual(ranged["state"], "READY_FOR_HUMAN_REVIEW")
        self.assertTrue(ranged["probability_is_calibrated_claim"])
        self.assertEqual(
            ranged["probability_estimate"]["state"],
            "EVIDENCE_SUPPORTED_RANGE",
        )
        self.assertEqual(ranged["probability_estimate"]["min_pct"], 55.0)
        self.assertEqual(ranged["probability_estimate"]["max_pct"], 75.0)
        self.assertFalse(
            ranged["probability_estimate"]["single_point_probability_used"]
        )

    def test_assessment_digest_detects_tampering(self):
        result = self.assessment()
        self.assertTrue(verify_advisory_assessment(result)["valid"])

        tampered = copy.deepcopy(result)
        tampered["recommendation_rationale"] = "Changed after assessment."
        verified = verify_advisory_assessment(tampered)
        self.assertFalse(verified["valid"])
        self.assertIn("ASSESSMENT_DIGEST_MISMATCH", verified["blockers"])

    def test_advisor_policy_preserves_advice_execution_separation(self):
        policy = advisor_policy()
        self.assertTrue(policy["reuses_data_decision_fabric"])
        self.assertFalse(policy["creates_second_decision_engine"])
        self.assertTrue(policy["recommendation_requires_evidence_gate"])
        self.assertTrue(
            policy["recommendation_requires_human_review_candidate"]
        )
        self.assertFalse(policy["recommendation_is_approval"])
        self.assertFalse(policy["approval_is_execution"])
        self.assertTrue(policy["owner_decision_required"])
        self.assertFalse(policy["confidence_is_success_probability"])
        self.assertFalse(policy["single_point_success_probability_allowed"])
        self.assertTrue(policy["probability_requires_range"])
        self.assertTrue(policy["probability_requires_method_ref"])
        self.assertTrue(policy["probability_requires_calibration_ref"])
        self.assertTrue(policy["probability_requires_evidence_refs"])
        self.assertTrue(policy["legal_contract_risk_flags_supported"])
        self.assertFalse(policy["legal_conclusion_authority"])
        self.assertTrue(
            policy["high_contract_risk_professional_review_recommended"]
        )
        self.assertFalse(policy["critical_risk_can_be_auto_approved"])
        self.assertFalse(policy["memory_can_grant_authority"])
        self.assertFalse(policy["action_authorized"])
        self.assertFalse(policy["automatic_execution"])
        self.assertFalse(policy["trading_order_authorized"])
        self.assertFalse(policy["payment_authorized"])
        self.assertFalse(policy["contract_signed"])
        self.assertFalse(policy["message_sent"])
        self.assertFalse(policy["provider_called"])
        self.assertFalse(policy["network_called"])
        self.assertFalse(policy["memory_written"])
        self.assertFalse(policy["worker_armed"])
        self.assertFalse(policy["deploy_executed"])
        self.assertFalse(policy["core_checkpoint_write"])
        self.assertFalse(policy["external_action_executed"])
        self.assertFalse(policy["executes_action"])


if __name__ == "__main__":
    unittest.main()
