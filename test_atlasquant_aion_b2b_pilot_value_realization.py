from __future__ import annotations

import unittest

from atlasquant_aion_b2b_pilot_value_realization import (
    evaluate_pilot_value_realization,
)

SCOPE = {
    "owner_id": "owner-a",
    "tenant_id": "tenant-a",
    "workspace_id": "ws-a",
}

QUICK_WINS = [
    "Normalize lead intake and next-action ownership.",
    "Prepare bounded follow-up drafts with human review.",
]


def contract(**overrides):
    core = {
        **SCOPE,
        "pilot_id": "pilot-001",
        "candidate_id": "candidate-001",
        "duration_days": 14,
        "max_monthly_infra_brl": 150.0,
        "objectives": ["Reduce repetitive administration."],
        "quick_wins": list(QUICK_WINS),
        "kpis": [
            {
                "metric_id": "response_minutes",
                "label": "Tempo medio de resposta",
                "unit": "minutes",
                "direction": "LOWER",
                "baseline": 30.0,
                "target": 15.0,
                "source_ref": "baseline:crm",
            },
            {
                "metric_id": "followup_completion_pct",
                "label": "Follow-up no prazo",
                "unit": "percent",
                "direction": "HIGHER",
                "baseline": 60.0,
                "target": 85.0,
                "source_ref": "baseline:crm",
            },
            {
                "metric_id": "admin_minutes_per_case",
                "label": "Tempo administrativo",
                "unit": "minutes",
                "direction": "LOWER",
                "baseline": 20.0,
                "target": 12.0,
                "source_ref": "baseline:time",
            },
        ],
        "stop_conditions": ["privacy", "scope", "budget"],
        "rollback_steps": ["disable routing", "restore manual path"],
        "evidence_refs": ["diagnostic:v1", "baseline:v1", "scope:v1"],
        "readiness_evidence_digest": "sha256:" + "1" * 64,
    }
    core.update(overrides.pop("contract", {}))
    row = {
        "schema": "ATLASQUANT_AION_B2B_PILOT_OPERATING_CONTRACT_V1",
        "state": "DRAFT_FOR_OWNER_APPROVAL",
        "activation_state": "BLOCKED_UNTIL_OWNER_APPROVAL",
        "contract": core,
        "blockers": [],
        "contract_digest": "sha256:" + "2" * 64,
        "human_owner_approval_required": True,
        "automatic_activation": False,
        "automatic_contract_signature": False,
        "automatic_customer_contact": False,
        "automatic_billing": False,
        "automatic_spend": False,
        "automatic_deploy": False,
        "provider_called": False,
        "production_mutation": False,
        "executes_action": False,
    }
    row.update(overrides)
    return row


def outcome(**overrides):
    row = {
        "schema": "ATLASQUANT_AION_B2B_PILOT_OUTCOME_HEALTH_V1",
        "state": "HEALTHY",
        "decision": "CONTINUE_REVIEW_CANDIDATE",
        "pilot_id": "pilot-001",
        "health_score": 90.0,
        "kpi_completion_pct": 100.0,
        "kpi_target_hit_pct": 100.0,
        "progress": {},
        "manual_baseline_cost_brl": 6000.0,
        "observed_operating_cost_brl": 3000.0,
        "observed_savings_brl": 3000.0,
        "observed_roi_pct": 100.0,
        "observed_monthly_infra_brl": 100.0,
        "hard_stop_reasons": [],
        "blockers": [],
        "evidence_digest": "sha256:" + "3" * 64,
        "owner_review_required": True,
        "automatic_renewal": False,
        "automatic_pause": False,
        "automatic_termination": False,
        "automatic_scope_expansion": False,
        "automatic_contract_change": False,
        "automatic_billing": False,
        "automatic_customer_contact": False,
        "automatic_deploy": False,
        "provider_called": False,
        "production_mutation": False,
        "executes_action": False,
    }
    row.update(overrides)
    return row


def quick_wins(hit=True):
    return [
        {
            "quick_win": QUICK_WINS[0],
            "achieved": hit,
            "realized_value_brl": 800.0 if hit else 0.0,
            "source_ref": "pilot:qwin:1",
        },
        {
            "quick_win": QUICK_WINS[1],
            "achieved": hit,
            "realized_value_brl": 700.0 if hit else 0.0,
            "source_ref": "pilot:qwin:2",
        },
    ]


def checkpoints(trend="IMPROVING"):
    if trend == "IMPROVING":
        return [
            {
                "period_id": "week-1",
                "sequence": 1,
                "observed_savings_brl": 1200.0,
                "observed_roi_pct": 20.0,
                "health_score": 80.0,
                "source_ref": "value:w1",
            },
            {
                "period_id": "week-2",
                "sequence": 2,
                "observed_savings_brl": 3000.0,
                "observed_roi_pct": 100.0,
                "health_score": 90.0,
                "source_ref": "value:w2",
            },
        ]
    if trend == "DECLINING":
        return [
            {
                "period_id": "week-1",
                "sequence": 1,
                "observed_savings_brl": 3000.0,
                "observed_roi_pct": 100.0,
                "health_score": 85.0,
                "source_ref": "value:w1",
            },
            {
                "period_id": "week-2",
                "sequence": 2,
                "observed_savings_brl": 1500.0,
                "observed_roi_pct": 10.0,
                "health_score": 72.0,
                "source_ref": "value:w2",
            },
        ]
    return [
        {
            "period_id": "week-1",
            "sequence": 1,
            "observed_savings_brl": 2800.0,
            "observed_roi_pct": 90.0,
            "health_score": 88.0,
            "source_ref": "value:w1",
        },
        {
            "period_id": "week-2",
            "sequence": 2,
            "observed_savings_brl": 2900.0,
            "observed_roi_pct": 95.0,
            "health_score": 89.0,
            "source_ref": "value:w2",
        },
    ]


def commercial(**overrides):
    row = {
        **SCOPE,
        "pilot_id": "pilot-001",
        "customer_fee_brl": 1500.0,
        "recognized_service_revenue_brl": 2000.0,
        "delivery_labor_cost_brl": 700.0,
        "support_cost_brl": 100.0,
        "external_cost_brl": 100.0,
        "infra_cost_brl": 100.0,
        "evidence_refs": [
            "finance:invoice",
            "finance:labor",
            "finance:support",
            "finance:infra",
        ],
    }
    row.update(overrides)
    return row


def evaluate(**overrides):
    args = {
        "trusted_scope": SCOPE,
        "contract_result": contract(),
        "outcome_health": outcome(),
        "quick_win_observations": quick_wins(),
        "value_checkpoints": checkpoints(),
        "commercial_evidence": commercial(),
    }
    args.update(overrides)
    return evaluate_pilot_value_realization(**args)


class AionB2BPilotValueRealizationTests(unittest.TestCase):
    def test_strong_value_becomes_expansion_review_candidate_only(self):
        out = evaluate()
        self.assertEqual(out["state"], "STRONG_VALUE")
        self.assertEqual(
            out["recommendation"],
            "EXPANSION_REVIEW_CANDIDATE",
        )
        self.assertEqual(out["quick_win_completion_pct"], 100.0)
        self.assertEqual(out["quick_win_achieved_pct"], 100.0)
        self.assertEqual(out["value_trend"], "IMPROVING")
        self.assertEqual(out["customer_value_to_fee_ratio"], 2.0)
        self.assertEqual(out["customer_net_value_brl"], 1500.0)
        self.assertTrue(out["customer_payback_covered"])
        self.assertEqual(out["provider_delivery_cost_brl"], 1000.0)
        self.assertEqual(out["provider_gross_margin_brl"], 1000.0)
        self.assertEqual(out["provider_gross_margin_pct"], 50.0)
        self.assertEqual(out["retention_risk"], "LOW")
        self.assertFalse(out["low_value_alert"])
        self.assertTrue(out["owner_review_required"])
        self.assertFalse(out["automatic_expansion"])

    def test_healthy_stable_value_becomes_continue_review_candidate(self):
        out = evaluate(value_checkpoints=checkpoints("STABLE"))
        self.assertEqual(out["state"], "VALUE_CONFIRMED")
        self.assertEqual(
            out["recommendation"],
            "CONTINUE_REVIEW_CANDIDATE",
        )
        self.assertEqual(out["value_trend"], "STABLE")

    def test_declining_value_becomes_remediation_review(self):
        out = evaluate(value_checkpoints=checkpoints("DECLINING"))
        self.assertEqual(out["state"], "VALUE_AT_RISK")
        self.assertEqual(
            out["recommendation"],
            "REMEDIATE_REVIEW_CANDIDATE",
        )
        self.assertTrue(out["low_value_alert"])
        self.assertIn(
            "VALUE_TREND_DECLINING",
            out["low_value_reasons"],
        )

    def test_negative_customer_value_can_be_exit_candidate(self):
        out = evaluate(
            outcome_health=outcome(
                state="UNHEALTHY",
                decision="EXIT_REVIEW_CANDIDATE",
                health_score=35.0,
                observed_savings_brl=-1000.0,
                observed_roi_pct=-25.0,
            ),
            quick_win_observations=quick_wins(hit=False),
            value_checkpoints=checkpoints("DECLINING"),
            commercial_evidence=commercial(
                customer_fee_brl=2000.0,
                recognized_service_revenue_brl=1000.0,
                delivery_labor_cost_brl=1200.0,
                support_cost_brl=300.0,
                external_cost_brl=100.0,
                infra_cost_brl=150.0,
            ),
        )
        self.assertEqual(out["state"], "LOW_VALUE")
        self.assertEqual(
            out["recommendation"],
            "EXIT_REVIEW_CANDIDATE",
        )
        self.assertTrue(out["low_value_alert"])
        self.assertEqual(out["retention_risk"], "HIGH")
        self.assertLess(out["customer_net_value_brl"], 0)
        self.assertLess(out["provider_gross_margin_brl"], 0)

    def test_stop_review_remains_stop_review(self):
        out = evaluate(
            outcome_health=outcome(
                state="STOP_REVIEW",
                decision="STOP_REVIEW",
                health_score=None,
                hard_stop_reasons=["SECURITY_INCIDENT_PRESENT"],
            )
        )
        self.assertEqual(out["state"], "STOP_REVIEW")
        self.assertEqual(out["recommendation"], "STOP_REVIEW")
        self.assertEqual(out["retention_risk_score"], 100.0)

    def test_missing_quick_win_observation_keeps_evidence_incomplete(self):
        out = evaluate(
            quick_win_observations=quick_wins()[:1],
        )
        self.assertEqual(out["state"], "EVIDENCE_INCOMPLETE")
        self.assertEqual(
            out["recommendation"],
            "VALUE_EVIDENCE_REVIEW",
        )
        self.assertLess(out["quick_win_completion_pct"], 100.0)

    def test_unknown_quick_win_is_rejected(self):
        rows = quick_wins()
        rows.append(
            {
                "quick_win": "Uncontracted growth experiment",
                "achieved": True,
                "source_ref": "pilot:unknown",
            }
        )
        out = evaluate(quick_win_observations=rows)
        self.assertEqual(out["state"], "BLOCKED")
        self.assertTrue(
            any(
                item.startswith("QUICK_WIN_NOT_IN_CONTRACT:")
                for item in out["blockers"]
            )
        )

    def test_value_checkpoint_sequence_is_deterministic(self):
        rows = list(reversed(checkpoints("IMPROVING")))
        out = evaluate(value_checkpoints=rows)
        self.assertEqual(out["value_trend"], "IMPROVING")
        self.assertEqual(out["value_checkpoints"][0]["sequence"], 1)
        self.assertEqual(out["value_checkpoints"][-1]["sequence"], 2)

    def test_duplicate_checkpoint_sequence_blocks(self):
        rows = checkpoints()
        rows[1] = dict(rows[1], sequence=1)
        out = evaluate(value_checkpoints=rows)
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "VALUE_CHECKPOINT_SEQUENCE_DUPLICATE",
            out["blockers"],
        )

    def test_one_checkpoint_is_evidence_incomplete_not_invented_trend(self):
        out = evaluate(value_checkpoints=checkpoints()[:1])
        self.assertEqual(out["state"], "EVIDENCE_INCOMPLETE")
        self.assertEqual(out["value_trend"], "INSUFFICIENT")

    def test_cross_tenant_commercial_evidence_blocks(self):
        out = evaluate(
            commercial_evidence=commercial(tenant_id="tenant-b"),
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "COMMERCIAL_EVIDENCE_SCOPE_MISMATCH",
            out["blockers"],
        )

    def test_global_infra_cap_is_enforced_in_commercial_evidence(self):
        out = evaluate(
            commercial_evidence=commercial(infra_cost_brl=200.01),
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "COMMERCIAL_INFRA_CAP_EXCEEDED",
            out["blockers"],
        )

    def test_commercial_evidence_requires_four_refs(self):
        out = evaluate(
            commercial_evidence=commercial(
                evidence_refs=["finance:1", "finance:2", "finance:3"]
            )
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "COMMERCIAL_EVIDENCE_INSUFFICIENT",
            out["blockers"],
        )

    def test_outcome_health_must_preserve_no_action_boundary(self):
        for key in (
            "automatic_renewal",
            "automatic_pause",
            "automatic_termination",
            "automatic_scope_expansion",
            "automatic_contract_change",
            "automatic_billing",
            "automatic_customer_contact",
            "automatic_deploy",
            "provider_called",
            "production_mutation",
            "executes_action",
        ):
            with self.subTest(key=key):
                out = evaluate(outcome_health=outcome(**{key: True}))
                self.assertEqual(out["state"], "BLOCKED")

    def test_review_packet_contains_only_decision_support(self):
        out = evaluate()
        packet = out["review_packet"]
        self.assertEqual(packet["pilot_id"], "pilot-001")
        self.assertEqual(packet["state"], "STRONG_VALUE")
        self.assertEqual(packet["retention_risk"], "LOW")
        self.assertIn("review_reasons", packet)
        self.assertNotIn("customer_contact", packet)
        self.assertNotIn("execute", packet)

    def test_no_business_action_is_granted(self):
        out = evaluate()
        for key in (
            "automatic_renewal",
            "automatic_expansion",
            "automatic_pause",
            "automatic_termination",
            "automatic_scope_change",
            "automatic_contract_change",
            "automatic_billing",
            "automatic_customer_contact",
            "automatic_provisioning",
            "automatic_deploy",
            "crm_write",
            "provider_called",
            "production_mutation",
            "executes_action",
        ):
            self.assertFalse(out[key], key)


if __name__ == "__main__":
    unittest.main()
