from __future__ import annotations

import unittest

from atlasquant_aion_b2b_pilot_outcome_health import evaluate_pilot_outcome

SCOPE = {"owner_id": "owner-a", "tenant_id": "tenant-a", "workspace_id": "ws-a"}


def contract(**overrides):
    core = {
        **SCOPE,
        "pilot_id": "pilot-001",
        "candidate_id": "candidate-001",
        "duration_days": 14,
        "max_monthly_infra_brl": 150.0,
        "kpis": [
            {"metric_id": "response_minutes", "direction": "LOWER", "target": 15.0},
            {"metric_id": "followup_completion_pct", "direction": "HIGHER", "target": 85.0},
            {"metric_id": "admin_minutes_per_case", "direction": "LOWER", "target": 12.0},
        ],
    }
    core.update(overrides.pop("contract", {}))
    row = {
        "state": "DRAFT_FOR_OWNER_APPROVAL",
        "activation_state": "BLOCKED_UNTIL_OWNER_APPROVAL",
        "human_owner_approval_required": True,
        "blockers": [],
        "contract_digest": "sha256:contract",
        "contract": core,
    }
    row.update(overrides)
    return row


def owner(**overrides):
    row = {
        **SCOPE,
        "state": "CONFIRMED",
        "approved_by_owner": True,
        "pilot_id": "pilot-001",
        "approval_ref": "owner-approval:001",
    }
    row.update(overrides)
    return row


def measurements(hit=True):
    if hit:
        return [
            {"metric_id": "response_minutes", "current": 12.0, "source_ref": "week2:crm"},
            {"metric_id": "followup_completion_pct", "current": 90.0, "source_ref": "week2:crm"},
            {"metric_id": "admin_minutes_per_case", "current": 10.0, "source_ref": "week2:time"},
        ]
    return [
        {"metric_id": "response_minutes", "current": 25.0, "source_ref": "week2:crm"},
        {"metric_id": "followup_completion_pct", "current": 70.0, "source_ref": "week2:crm"},
        {"metric_id": "admin_minutes_per_case", "current": 18.0, "source_ref": "week2:time"},
    ]


def observed(**overrides):
    row = {
        **SCOPE,
        "pilot_id": "pilot-001",
        "adoption_pct": 90.0,
        "sla_met_pct": 95.0,
        "automation_reliability_pct": 98.0,
        "evidence_coverage_pct": 100.0,
        "manual_baseline_cost_brl": 5000.0,
        "observed_operating_cost_brl": 2500.0,
        "observed_monthly_infra_brl": 120.0,
        "critical_incident_count": 0,
        "security_incident_count": 0,
        "privacy_incident_count": 0,
        "scope_breach_count": 0,
        "evidence_refs": ["crm:w2", "time:w2", "sla:w2", "finops:w2"],
    }
    row.update(overrides)
    return row


class AionB2BPilotOutcomeHealthTests(unittest.TestCase):
    def test_healthy_pilot_becomes_continue_review_candidate_only(self):
        out = evaluate_pilot_outcome(
            trusted_scope=SCOPE,
            contract_result=contract(),
            owner_activation_attestation=owner(),
            measurements=measurements(),
            observed=observed(),
        )
        self.assertEqual(out["state"], "HEALTHY")
        self.assertEqual(out["decision"], "CONTINUE_REVIEW_CANDIDATE")
        self.assertEqual(out["kpi_completion_pct"], 100.0)
        self.assertEqual(out["kpi_target_hit_pct"], 100.0)
        self.assertGreaterEqual(out["health_score"], 80.0)
        self.assertEqual(out["observed_savings_brl"], 2500.0)
        self.assertEqual(out["observed_roi_pct"], 100.0)
        self.assertTrue(out["owner_review_required"])
        self.assertFalse(out["automatic_renewal"])

    def test_owner_activation_attestation_is_mandatory(self):
        out = evaluate_pilot_outcome(
            trusted_scope=SCOPE,
            contract_result=contract(),
            owner_activation_attestation=owner(state="PENDING", approved_by_owner=False),
            measurements=measurements(),
            observed=observed(),
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("OWNER_PILOT_APPROVAL_NOT_CONFIRMED", out["blockers"])
        self.assertIn("OWNER_PILOT_APPROVAL_REQUIRED", out["blockers"])

    def test_scope_mismatch_fails_closed(self):
        out = evaluate_pilot_outcome(
            trusted_scope=SCOPE,
            contract_result=contract(),
            owner_activation_attestation=owner(),
            measurements=measurements(),
            observed=observed(tenant_id="tenant-b"),
        )
        self.assertEqual(out["decision"], "BLOCKED")
        self.assertIn("OBSERVED_SCOPE_MISMATCH", out["blockers"])

    def test_missing_kpi_evidence_stays_incomplete(self):
        out = evaluate_pilot_outcome(
            trusted_scope=SCOPE,
            contract_result=contract(),
            owner_activation_attestation=owner(),
            measurements=measurements()[:1],
            observed=observed(),
        )
        self.assertEqual(out["state"], "EVIDENCE_INCOMPLETE")
        self.assertEqual(out["decision"], "EVIDENCE_REVIEW")
        self.assertLess(out["kpi_completion_pct"], 100.0)

    def test_contract_budget_is_enforced_even_below_global_cap(self):
        out = evaluate_pilot_outcome(
            trusted_scope=SCOPE,
            contract_result=contract(contract={"max_monthly_infra_brl": 100.0}),
            owner_activation_attestation=owner(),
            measurements=measurements(),
            observed=observed(observed_monthly_infra_brl=120.0),
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("OBSERVED_CONTRACT_BUDGET_EXCEEDED", out["blockers"])

    def test_global_monthly_infra_cap_is_hard_block(self):
        out = evaluate_pilot_outcome(
            trusted_scope=SCOPE,
            contract_result=contract(contract={"max_monthly_infra_brl": 200.0}),
            owner_activation_attestation=owner(),
            measurements=measurements(),
            observed=observed(observed_monthly_infra_brl=201.0),
        )
        self.assertIn("OBSERVED_MONTHLY_INFRA_CAP_EXCEEDED", out["blockers"])

    def test_security_privacy_scope_or_critical_incident_forces_stop_review(self):
        cases = (
            ("critical_incident_count", "CRITICAL_INCIDENT_PRESENT"),
            ("security_incident_count", "SECURITY_INCIDENT_PRESENT"),
            ("privacy_incident_count", "PRIVACY_INCIDENT_PRESENT"),
            ("scope_breach_count", "SCOPE_BREACH_PRESENT"),
        )
        for field, reason in cases:
            with self.subTest(field=field):
                out = evaluate_pilot_outcome(
                    trusted_scope=SCOPE,
                    contract_result=contract(),
                    owner_activation_attestation=owner(),
                    measurements=measurements(),
                    observed=observed(**{field: 1}),
                )
                self.assertEqual(out["state"], "STOP_REVIEW")
                self.assertEqual(out["decision"], "STOP_REVIEW")
                self.assertIn(reason, out["hard_stop_reasons"])
                self.assertFalse(out["automatic_pause"])
                self.assertFalse(out["automatic_termination"])

    def test_watch_state_recommends_pause_or_remediation_review(self):
        out = evaluate_pilot_outcome(
            trusted_scope=SCOPE,
            contract_result=contract(),
            owner_activation_attestation=owner(),
            measurements=[
                {"metric_id": "response_minutes", "current": 12.0, "source_ref": "w2:crm"},
                {"metric_id": "followup_completion_pct", "current": 70.0, "source_ref": "w2:crm"},
                {"metric_id": "admin_minutes_per_case", "current": 10.0, "source_ref": "w2:time"},
            ],
            observed=observed(
                adoption_pct=60.0,
                sla_met_pct=70.0,
                automation_reliability_pct=80.0,
            ),
        )
        self.assertEqual(out["state"], "WATCH")
        self.assertEqual(out["decision"], "PAUSE_OR_REMEDIATE_REVIEW")

    def test_unhealthy_pilot_becomes_exit_review_candidate_not_auto_termination(self):
        out = evaluate_pilot_outcome(
            trusted_scope=SCOPE,
            contract_result=contract(),
            owner_activation_attestation=owner(),
            measurements=measurements(hit=False),
            observed=observed(
                adoption_pct=20.0,
                sla_met_pct=40.0,
                automation_reliability_pct=50.0,
                evidence_coverage_pct=60.0,
                manual_baseline_cost_brl=2000.0,
                observed_operating_cost_brl=3000.0,
            ),
        )
        self.assertEqual(out["state"], "UNHEALTHY")
        self.assertEqual(out["decision"], "EXIT_REVIEW_CANDIDATE")
        self.assertLess(out["observed_roi_pct"], 0)
        self.assertFalse(out["automatic_termination"])

    def test_insufficient_observed_evidence_blocks(self):
        out = evaluate_pilot_outcome(
            trusted_scope=SCOPE,
            contract_result=contract(),
            owner_activation_attestation=owner(),
            measurements=measurements(),
            observed=observed(evidence_refs=["one", "two"]),
        )
        self.assertIn("OBSERVED_EVIDENCE_INSUFFICIENT", out["blockers"])

    def test_no_external_authority_is_granted(self):
        out = evaluate_pilot_outcome(
            trusted_scope=SCOPE,
            contract_result=contract(),
            owner_activation_attestation=owner(),
            measurements=measurements(),
            observed=observed(),
        )
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
            self.assertFalse(out[key], key)


if __name__ == "__main__":
    unittest.main()
