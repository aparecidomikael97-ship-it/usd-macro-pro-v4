from __future__ import annotations

import unittest

from atlasquant_aion_b2b_diagnostic_intake import (
    build_diagnostic_intake,
    build_pilot_scoring_input,
)
from atlasquant_aion_b2b_pilot_readiness import assess_b2b_pilot_candidate

SCOPE = {
    "owner_id": "owner-a",
    "tenant_id": "tenant-a",
    "workspace_id": "business",
}


def metric(metric_id, value, unit="count"):
    return {
        "metric_id": metric_id,
        "label": metric_id.replace("_", " ").title(),
        "unit": unit,
        "value": value,
        "source_ref": f"source:{metric_id}",
    }


def area(name, *, baseline=True):
    row = {
        "current_process": f"Processo atual de {name}",
        "pain_points": [f"Gargalo de {name}"],
        "systems": [f"system-{name}"],
        "evidence_refs": [f"evidence:{name}"],
        "baseline_metrics": [],
    }
    if baseline:
        row["baseline_metrics"] = [metric(f"{name}_baseline", 10)]
    return row


def diagnostic_raw(**overrides):
    row = {
        **SCOPE,
        "candidate_id": "candidate-001",
        "lead_id": "lead-001",
        "company_key": "company-001",
        "company_label": "Empresa Exemplo",
        "assessor_context_ref": "diagnostic-session:001",
        "areas": {
            "sales": area("sales"),
            "customer_service": area("customer_service"),
            "billing": area("billing"),
            "team": area("team", baseline=False),
            "systems": area("systems", baseline=False),
            "bottlenecks": area("bottlenecks", baseline=False),
        },
        "objectives": ["Reduzir tempo de resposta", "Melhorar conversão"],
        "constraints": ["Sem mutação automática de produção"],
        "quick_win_candidates": ["Organizar follow-up e CRM"],
        "integration_candidates": ["crm", "email", "calendar"],
        "evidence_refs": ["diag:01", "diag:02", "diag:03"],
    }
    row.update(overrides)
    return row


def human_assessment(**overrides):
    row = {
        "human_assessed": True,
        "assessor_ref": "owner-review:001",
        "problem_fit": 4.5,
        "process_repeatability": 4.0,
        "data_readiness": 4.0,
        "owner_sponsorship": 5.0,
        "integration_feasibility": 4.0,
        "expected_value": 4.5,
        "scope_clarity": 4.0,
        "privacy_risk": 1.0,
        "operational_risk": 1.0,
        "planned_monthly_infra_brl": 150.0,
        "pilot_duration_days": 14,
        "evidence_refs": ["assessment:01", "assessment:02"],
    }
    row.update(overrides)
    return row


class AionB2BDiagnosticIntakeTests(unittest.TestCase):
    def test_complete_diagnostic_is_ready_for_human_scoring(self):
        out = build_diagnostic_intake(
            diagnostic_raw(),
            trusted_scope=SCOPE,
        )
        self.assertEqual(out["state"], "READY_FOR_HUMAN_SCORING")
        self.assertEqual(out["dossier"]["completeness_pct"], 100.0)
        self.assertEqual(set(out["dossier"]["areas"]), {
            "sales",
            "customer_service",
            "billing",
            "team",
            "systems",
            "bottlenecks",
        })
        self.assertFalse(out["automatic_score_generation"])
        self.assertFalse(out["executes_action"])

    def test_sales_service_and_billing_require_baseline_metrics(self):
        raw = diagnostic_raw()
        raw["areas"]["sales"]["baseline_metrics"] = []
        raw["areas"]["customer_service"]["baseline_metrics"] = []
        raw["areas"]["billing"]["baseline_metrics"] = []
        out = build_diagnostic_intake(raw, trusted_scope=SCOPE)
        self.assertEqual(out["state"], "INCOMPLETE")
        self.assertIn("SALES_BASELINE_REQUIRED", out["blockers"])
        self.assertIn("CUSTOMER_SERVICE_BASELINE_REQUIRED", out["blockers"])
        self.assertIn("BILLING_BASELINE_REQUIRED", out["blockers"])
        self.assertLess(out["dossier"]["completeness_pct"], 100.0)

    def test_each_area_requires_process_pain_and_evidence(self):
        raw = diagnostic_raw()
        raw["areas"]["team"] = {
            "current_process": "",
            "pain_points": [],
            "systems": [],
            "baseline_metrics": [],
            "evidence_refs": [],
        }
        out = build_diagnostic_intake(raw, trusted_scope=SCOPE)
        self.assertEqual(out["state"], "INCOMPLETE")
        self.assertIn("TEAM_CURRENT_PROCESS_REQUIRED", out["blockers"])
        self.assertIn("TEAM_PAIN_POINTS_REQUIRED", out["blockers"])
        self.assertIn("TEAM_EVIDENCE_REQUIRED", out["blockers"])

    def test_cross_tenant_diagnostic_blocks(self):
        raw = diagnostic_raw()
        raw["tenant_id"] = "tenant-b"
        out = build_diagnostic_intake(raw, trusted_scope=SCOPE)
        self.assertEqual(out["state"], "INCOMPLETE")
        self.assertIn("DIAGNOSTIC_SCOPE_MISMATCH", out["blockers"])

    def test_global_evidence_objectives_constraints_and_quick_win_are_required(self):
        out = build_diagnostic_intake(
            diagnostic_raw(
                evidence_refs=[],
                objectives=[],
                constraints=[],
                quick_win_candidates=[],
            ),
            trusted_scope=SCOPE,
        )
        self.assertEqual(out["state"], "INCOMPLETE")
        self.assertIn("DIAGNOSTIC_EVIDENCE_INSUFFICIENT", out["blockers"])
        self.assertIn("DIAGNOSTIC_OBJECTIVES_REQUIRED", out["blockers"])
        self.assertIn("DIAGNOSTIC_CONSTRAINTS_REQUIRED", out["blockers"])
        self.assertIn("QUICK_WIN_CANDIDATE_REQUIRED", out["blockers"])

    def test_scoring_input_binds_only_explicit_human_scores(self):
        diagnostic = build_diagnostic_intake(
            diagnostic_raw(),
            trusted_scope=SCOPE,
        )
        out = build_pilot_scoring_input(
            diagnostic,
            human_assessment=human_assessment(),
        )
        self.assertEqual(out["state"], "READY_FOR_PILOT_READINESS")
        self.assertTrue(out["human_assessment_bound"])
        self.assertEqual(out["candidate"]["problem_fit"], 4.5)
        self.assertEqual(out["candidate"]["privacy_risk"], 1.0)
        self.assertEqual(out["candidate"]["planned_monthly_infra_brl"], 150.0)
        self.assertIn(diagnostic["diagnostic_digest"], out["candidate"]["evidence_refs"])
        self.assertIn("owner-review:001", out["candidate"]["evidence_refs"])
        self.assertFalse(out["automatic_score_generation"])
        self.assertFalse(out["calls_pilot_readiness"])
        self.assertFalse(out["executes_action"])

    def test_truthy_human_assessed_string_does_not_count(self):
        diagnostic = build_diagnostic_intake(
            diagnostic_raw(),
            trusted_scope=SCOPE,
        )
        out = build_pilot_scoring_input(
            diagnostic,
            human_assessment=human_assessment(human_assessed="true"),
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("EXPLICIT_HUMAN_ASSESSMENT_REQUIRED", out["blockers"])

    def test_missing_assessor_reference_blocks_scoring_input(self):
        diagnostic = build_diagnostic_intake(
            diagnostic_raw(),
            trusted_scope=SCOPE,
        )
        out = build_pilot_scoring_input(
            diagnostic,
            human_assessment=human_assessment(assessor_ref=""),
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("ASSESSOR_REF_REQUIRED", out["blockers"])

    def test_invalid_score_is_not_inferred_or_clamped(self):
        diagnostic = build_diagnostic_intake(
            diagnostic_raw(),
            trusted_scope=SCOPE,
        )
        out = build_pilot_scoring_input(
            diagnostic,
            human_assessment=human_assessment(problem_fit=8),
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("PROBLEM_FIT_SCORE_INVALID", out["blockers"])
        self.assertIsNone(out["candidate"]["problem_fit"])

    def test_incomplete_diagnostic_cannot_be_scored(self):
        diagnostic = build_diagnostic_intake(
            diagnostic_raw(objectives=[]),
            trusted_scope=SCOPE,
        )
        out = build_pilot_scoring_input(
            diagnostic,
            human_assessment=human_assessment(),
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("DIAGNOSTIC_NOT_READY_FOR_SCORING", out["blockers"])

    def test_assessment_evidence_is_required(self):
        diagnostic = build_diagnostic_intake(
            diagnostic_raw(),
            trusted_scope=SCOPE,
        )
        out = build_pilot_scoring_input(
            diagnostic,
            human_assessment=human_assessment(evidence_refs=["one"]),
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("ASSESSMENT_EVIDENCE_INSUFFICIENT", out["blockers"])

    def test_diagnostic_never_generates_proposal_or_pricing(self):
        out = build_diagnostic_intake(
            diagnostic_raw(),
            trusted_scope=SCOPE,
        )
        for key in (
            "automatic_score_generation",
            "automatic_acceptance",
            "automatic_rejection_external_effect",
            "automatic_outreach",
            "automatic_proposal",
            "automatic_pricing",
            "automatic_contract",
            "crm_write",
            "provider_called",
            "production_mutation",
            "executes_action",
        ):
            self.assertFalse(out[key], key)

    def test_diagnostic_flows_into_existing_pilot_readiness_gate(self):
        diagnostic = build_diagnostic_intake(
            diagnostic_raw(),
            trusted_scope=SCOPE,
        )
        scoring = build_pilot_scoring_input(
            diagnostic,
            human_assessment=human_assessment(),
        )
        self.assertEqual(scoring["state"], "READY_FOR_PILOT_READINESS")

        platform = {
            "state": "PASS",
            "pilot_recommendation": "HUMAN_REVIEW_CANDIDATE",
            "total_tasks": 1000,
            "company_count": 3,
            "classification_error_count": 0,
            "unsafe_escape_count": 0,
            "deny_escape_count": 0,
            "evidence_digest": "sha256:managed-ops-reference",
        }
        hardening = {
            "tenant_isolation_pass": True,
            "vault_backend_pass": True,
            "chaos_campaign_pass": True,
            "mission_control_ready": True,
            "approval_gate_ready": True,
            "audit_receipts_ready": True,
            "rollback_ready": True,
            "drift_state": "STABLE",
            "security_gate_state": "PASS",
        }
        decision = assess_b2b_pilot_candidate(
            trusted_scope=SCOPE,
            candidate=scoring["candidate"],
            platform_evidence=platform,
            hardening_evidence=hardening,
        )
        self.assertEqual(decision["decision"], "PILOT_REVIEW_CANDIDATE")
        self.assertEqual(decision["state"], "READY_FOR_OWNER_REVIEW")
        self.assertTrue(decision["human_owner_decision_required"])
        self.assertFalse(decision["automatic_acceptance"])
        self.assertFalse(decision["executes_action"])

    def test_scoring_binding_is_deterministic_for_same_inputs(self):
        diagnostic = build_diagnostic_intake(
            diagnostic_raw(),
            trusted_scope=SCOPE,
        )
        first = build_pilot_scoring_input(
            diagnostic,
            human_assessment=human_assessment(),
        )
        second = build_pilot_scoring_input(
            diagnostic,
            human_assessment=human_assessment(),
        )
        self.assertEqual(first["binding_digest"], second["binding_digest"])


if __name__ == "__main__":
    unittest.main()
