from __future__ import annotations

import unittest

from atlasquant_aion_b2b_pilot_operating_contract import (
    MAX_MONTHLY_INFRA_BRL,
    build_pilot_operating_contract,
    evaluate_pilot_checkpoint,
)

SCOPE = {"owner_id": "owner-a", "tenant_id": "tenant-a", "workspace_id": "ws-a"}


def readiness(**overrides):
    row = {
        "decision": "PILOT_REVIEW_CANDIDATE",
        "state": "READY_FOR_OWNER_REVIEW",
        "human_owner_decision_required": True,
        "blockers": [],
        "evidence_digest": "sha256:pilot-readiness",
        "automatic_acceptance": False,
        "production_mutation": False,
    }
    row.update(overrides)
    return row


def spec(**overrides):
    row = {
        **SCOPE,
        "pilot_id": "pilot-001",
        "candidate_id": "candidate-001",
        "duration_days": 14,
        "max_monthly_infra_brl": 150.0,
        "objectives": [
            "Reduce repetitive commercial administration without reducing control.",
            "Measure service response and follow-up quality.",
        ],
        "quick_wins": [
            "Normalize lead intake and next-action ownership.",
            "Prepare bounded follow-up drafts with human review.",
        ],
        "kpis": [
            {
                "metric_id": "response_minutes",
                "label": "Tempo medio de primeira resposta",
                "unit": "minutes",
                "direction": "LOWER",
                "baseline": 30.0,
                "target": 15.0,
                "source_ref": "baseline:crm-export",
            },
            {
                "metric_id": "followup_completion_pct",
                "label": "Follow-ups concluidos no prazo",
                "unit": "percent",
                "direction": "HIGHER",
                "baseline": 60.0,
                "target": 85.0,
                "source_ref": "baseline:crm-export",
            },
            {
                "metric_id": "admin_minutes_per_case",
                "label": "Tempo administrativo por caso",
                "unit": "minutes",
                "direction": "LOWER",
                "baseline": 20.0,
                "target": 12.0,
                "source_ref": "baseline:time-study",
            },
        ],
        "stop_conditions": [
            "Any privacy breach.",
            "Any cross-tenant scope breach.",
            "Budget cap exceeded without owner approval.",
        ],
        "rollback_steps": [
            "Disable pilot-only workflow routing.",
            "Restore last owner-approved manual operating path.",
        ],
        "evidence_refs": [
            "diagnostic:v1",
            "baseline:v1",
            "scope:v1",
        ],
    }
    row.update(overrides)
    return row


class AionB2BPilotOperatingContractTests(unittest.TestCase):
    def test_valid_spec_builds_draft_for_owner_approval_only(self):
        out = build_pilot_operating_contract(
            trusted_scope=SCOPE,
            readiness=readiness(),
            spec=spec(),
        )
        self.assertEqual(out["state"], "DRAFT_FOR_OWNER_APPROVAL")
        self.assertEqual(out["activation_state"], "BLOCKED_UNTIL_OWNER_APPROVAL")
        self.assertFalse(out["blockers"])
        self.assertTrue(out["human_owner_approval_required"])
        self.assertFalse(out["automatic_activation"])
        self.assertFalse(out["executes_action"])

    def test_readiness_candidate_is_mandatory(self):
        out = build_pilot_operating_contract(
            trusted_scope=SCOPE,
            readiness=readiness(decision="REVIEW"),
            spec=spec(),
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("READINESS_NOT_PILOT_REVIEW_CANDIDATE", out["blockers"])

    def test_scope_mismatch_blocks(self):
        out = build_pilot_operating_contract(
            trusted_scope=SCOPE,
            readiness=readiness(),
            spec=spec(tenant_id="tenant-b"),
        )
        self.assertIn("PILOT_SCOPE_MISMATCH", out["blockers"])

    def test_duration_is_bounded(self):
        for days in (0, 6, 31, 90):
            with self.subTest(days=days):
                out = build_pilot_operating_contract(
                    trusted_scope=SCOPE,
                    readiness=readiness(),
                    spec=spec(duration_days=days),
                )
                self.assertIn("PILOT_DURATION_OUT_OF_RANGE", out["blockers"])

    def test_monthly_infra_cap_blocks(self):
        out = build_pilot_operating_contract(
            trusted_scope=SCOPE,
            readiness=readiness(),
            spec=spec(max_monthly_infra_brl=MAX_MONTHLY_INFRA_BRL + 1),
        )
        self.assertIn("PILOT_INFRA_BUDGET_EXCEEDS_CAP", out["blockers"])

    def test_kpis_require_improvement_direction_and_evidence(self):
        bad = spec()
        bad["kpis"] = [
            {
                "metric_id": "bad",
                "label": "Bad KPI",
                "unit": "minutes",
                "direction": "LOWER",
                "baseline": 10,
                "target": 20,
                "source_ref": "",
            },
            bad["kpis"][1],
            bad["kpis"][2],
        ]
        out = build_pilot_operating_contract(
            trusted_scope=SCOPE,
            readiness=readiness(),
            spec=bad,
        )
        self.assertTrue(any(x.startswith("KPI_TARGET_NOT_IMPROVEMENT:bad") for x in out["blockers"]))
        self.assertTrue(any(x.startswith("KPI_METADATA_INCOMPLETE:bad") for x in out["blockers"]))

    def test_stop_and_rollback_are_explicit_requirements(self):
        out = build_pilot_operating_contract(
            trusted_scope=SCOPE,
            readiness=readiness(),
            spec=spec(stop_conditions=["one"], rollback_steps=["one"]),
        )
        self.assertIn("STOP_CONDITIONS_INSUFFICIENT", out["blockers"])
        self.assertIn("ROLLBACK_PLAN_INSUFFICIENT", out["blockers"])

    def test_checkpoint_on_track_requires_measured_evidence(self):
        contract = build_pilot_operating_contract(
            trusted_scope=SCOPE,
            readiness=readiness(),
            spec=spec(),
        )
        out = evaluate_pilot_checkpoint(
            contract,
            measurements=[
                {"metric_id": "response_minutes", "current": 12.0, "source_ref": "week1:crm"},
                {"metric_id": "followup_completion_pct", "current": 90.0, "source_ref": "week1:crm"},
                {"metric_id": "admin_minutes_per_case", "current": 11.0, "source_ref": "week1:time"},
            ],
        )
        self.assertEqual(out["state"], "ON_TRACK")
        self.assertEqual(out["kpi_completion_pct"], 100.0)
        self.assertEqual(out["kpi_target_hit_pct"], 100.0)

    def test_missing_measurement_stays_evidence_incomplete(self):
        contract = build_pilot_operating_contract(
            trusted_scope=SCOPE,
            readiness=readiness(),
            spec=spec(),
        )
        out = evaluate_pilot_checkpoint(
            contract,
            measurements=[
                {"metric_id": "response_minutes", "current": 12.0, "source_ref": "week1:crm"},
            ],
        )
        self.assertEqual(out["state"], "EVIDENCE_INCOMPLETE")
        self.assertLess(out["kpi_completion_pct"], 100.0)

    def test_hard_stop_signals_require_stop_review_but_do_not_stop_automatically(self):
        contract = build_pilot_operating_contract(
            trusted_scope=SCOPE,
            readiness=readiness(),
            spec=spec(),
        )
        out = evaluate_pilot_checkpoint(
            contract,
            measurements=[],
            privacy_breach=True,
            scope_breach=True,
        )
        self.assertEqual(out["state"], "STOP_REVIEW")
        self.assertIn("PRIVACY_BREACH", out["hard_stop_reasons"])
        self.assertIn("SCOPE_BREACH", out["hard_stop_reasons"])
        self.assertFalse(out["automatic_stop"])
        self.assertTrue(out["owner_review_required"])

    def test_at_risk_when_all_evidence_exists_but_targets_miss(self):
        contract = build_pilot_operating_contract(
            trusted_scope=SCOPE,
            readiness=readiness(),
            spec=spec(),
        )
        out = evaluate_pilot_checkpoint(
            contract,
            measurements=[
                {"metric_id": "response_minutes", "current": 25.0, "source_ref": "week1:crm"},
                {"metric_id": "followup_completion_pct", "current": 70.0, "source_ref": "week1:crm"},
                {"metric_id": "admin_minutes_per_case", "current": 18.0, "source_ref": "week1:time"},
            ],
        )
        self.assertEqual(out["state"], "AT_RISK")
        self.assertEqual(out["kpi_completion_pct"], 100.0)
        self.assertEqual(out["kpi_target_hit_pct"], 0.0)

    def test_contract_and_checkpoint_never_grant_external_authority(self):
        contract = build_pilot_operating_contract(
            trusted_scope=SCOPE,
            readiness=readiness(),
            spec=spec(),
        )
        for key in (
            "automatic_activation",
            "automatic_contract_signature",
            "automatic_customer_contact",
            "automatic_billing",
            "automatic_spend",
            "automatic_deploy",
            "provider_called",
            "production_mutation",
            "executes_action",
        ):
            self.assertFalse(contract[key], key)

        checkpoint = evaluate_pilot_checkpoint(contract, measurements=[])
        for key in (
            "automatic_stop",
            "automatic_expand_scope",
            "automatic_contract_change",
            "automatic_billing",
            "automatic_deploy",
            "provider_called",
            "production_mutation",
            "executes_action",
        ):
            self.assertFalse(checkpoint[key], key)


if __name__ == "__main__":
    unittest.main()
