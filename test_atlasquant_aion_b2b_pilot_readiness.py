from __future__ import annotations

import unittest

from atlasquant_aion_b2b_pilot_readiness import (
    MAX_MONTHLY_INFRA_BRL,
    assess_b2b_pilot_candidate,
    normalize_candidate,
)

SCOPE = {"owner_id": "owner-a", "tenant_id": "tenant-a", "workspace_id": "ws-a"}


def candidate(**overrides):
    row = {
        **SCOPE,
        "candidate_id": "pilot-001",
        "company_label": "Empresa Ficticia A",
        "problem_fit": 5,
        "process_repeatability": 4,
        "data_readiness": 4,
        "owner_sponsorship": 5,
        "integration_feasibility": 4,
        "expected_value": 5,
        "scope_clarity": 5,
        "privacy_risk": 1,
        "operational_risk": 1,
        "planned_monthly_infra_brl": 120.0,
        "pilot_duration_days": 14,
        "evidence_refs": ["diagnostic:v1", "process-map:v1", "roi-hypothesis:v1"],
    }
    row.update(overrides)
    return row


def platform(**overrides):
    row = {
        "state": "PASS",
        "pilot_recommendation": "HUMAN_REVIEW_CANDIDATE",
        "total_tasks": 1000,
        "company_count": 3,
        "classification_error_count": 0,
        "unsafe_escape_count": 0,
        "deny_escape_count": 0,
        "evidence_digest": "sha256:managed-ops-reference",
    }
    row.update(overrides)
    return row


def hardening(**overrides):
    row = {
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
    row.update(overrides)
    return row


class AionB2BPilotReadinessTests(unittest.TestCase):
    def test_strong_candidate_reaches_owner_review_only(self):
        out = assess_b2b_pilot_candidate(
            trusted_scope=SCOPE,
            candidate=candidate(),
            platform_evidence=platform(),
            hardening_evidence=hardening(),
        )
        self.assertEqual(out["decision"], "PILOT_REVIEW_CANDIDATE")
        self.assertEqual(out["state"], "READY_FOR_OWNER_REVIEW")
        self.assertGreaterEqual(out["priority_score"], 75)
        self.assertTrue(out["human_owner_decision_required"])
        self.assertFalse(out["automatic_acceptance"])
        self.assertFalse(out["executes_action"])

    def test_scope_mismatch_fails_closed(self):
        normalized = normalize_candidate(candidate(tenant_id="tenant-b"), trusted_scope=SCOPE)
        self.assertIn("CANDIDATE_SCOPE_MISMATCH", normalized["normalization_blockers"])

    def test_monthly_infra_cap_is_hard_block(self):
        out = assess_b2b_pilot_candidate(
            trusted_scope=SCOPE,
            candidate=candidate(planned_monthly_infra_brl=MAX_MONTHLY_INFRA_BRL + 0.01),
            platform_evidence=platform(),
            hardening_evidence=hardening(),
        )
        self.assertEqual(out["decision"], "BLOCKED")
        self.assertIn("MONTHLY_INFRA_CAP_EXCEEDED", out["blockers"])

    def test_high_privacy_risk_blocks(self):
        out = assess_b2b_pilot_candidate(
            trusted_scope=SCOPE,
            candidate=candidate(privacy_risk=4),
            platform_evidence=platform(),
            hardening_evidence=hardening(),
        )
        self.assertEqual(out["decision"], "BLOCKED")
        self.assertIn("PRIVACY_RISK_TOO_HIGH", out["blockers"])

    def test_high_operational_risk_blocks(self):
        out = assess_b2b_pilot_candidate(
            trusted_scope=SCOPE,
            candidate=candidate(operational_risk=5),
            platform_evidence=platform(),
            hardening_evidence=hardening(),
        )
        self.assertIn("OPERATIONAL_RISK_TOO_HIGH", out["blockers"])

    def test_reference_simulation_must_be_clean(self):
        for key, value, expected in (
            ("state", "BLOCKED", "MANAGED_OPERATIONS_SIM_NOT_PASS"),
            ("pilot_recommendation", "HOLD", "MANAGED_OPERATIONS_NOT_REVIEW_CANDIDATE"),
            ("classification_error_count", 1, "REFERENCE_CLASSIFICATION_ERRORS"),
            ("unsafe_escape_count", 1, "REFERENCE_UNSAFE_ESCAPE"),
            ("deny_escape_count", 1, "REFERENCE_DENY_ESCAPE"),
        ):
            with self.subTest(key=key):
                out = assess_b2b_pilot_candidate(
                    trusted_scope=SCOPE,
                    candidate=candidate(),
                    platform_evidence=platform(**{key: value}),
                    hardening_evidence=hardening(),
                )
                self.assertEqual(out["decision"], "BLOCKED")
                self.assertIn(expected, out["blockers"])

    def test_reference_scale_is_mandatory(self):
        out = assess_b2b_pilot_candidate(
            trusted_scope=SCOPE,
            candidate=candidate(),
            platform_evidence=platform(total_tasks=999, company_count=2),
            hardening_evidence=hardening(),
        )
        self.assertIn("REFERENCE_TASK_VOLUME_INSUFFICIENT", out["blockers"])
        self.assertIn("REFERENCE_COMPANY_COVERAGE_INSUFFICIENT", out["blockers"])

    def test_each_hardening_contract_is_required(self):
        fields = (
            "tenant_isolation_pass",
            "vault_backend_pass",
            "chaos_campaign_pass",
            "mission_control_ready",
            "approval_gate_ready",
            "audit_receipts_ready",
            "rollback_ready",
        )
        for field in fields:
            with self.subTest(field=field):
                out = assess_b2b_pilot_candidate(
                    trusted_scope=SCOPE,
                    candidate=candidate(),
                    platform_evidence=platform(),
                    hardening_evidence=hardening(**{field: False}),
                )
                self.assertEqual(out["decision"], "BLOCKED")
                self.assertTrue(any(field.upper() in x for x in out["blockers"]))

    def test_drift_and_security_must_be_clean(self):
        drift = assess_b2b_pilot_candidate(
            trusted_scope=SCOPE,
            candidate=candidate(),
            platform_evidence=platform(),
            hardening_evidence=hardening(drift_state="DEGRADED"),
        )
        security = assess_b2b_pilot_candidate(
            trusted_scope=SCOPE,
            candidate=candidate(),
            platform_evidence=platform(),
            hardening_evidence=hardening(security_gate_state="BLOCKED"),
        )
        self.assertIn("DRIFT_NOT_STABLE", drift["blockers"])
        self.assertIn("SECURITY_GATE_NOT_PASS", security["blockers"])

    def test_low_priority_candidate_is_declined_without_external_effect(self):
        out = assess_b2b_pilot_candidate(
            trusted_scope=SCOPE,
            candidate=candidate(
                problem_fit=1,
                process_repeatability=1,
                data_readiness=2,
                owner_sponsorship=1,
                integration_feasibility=2,
                expected_value=1,
                scope_clarity=2,
                privacy_risk=2,
                operational_risk=2,
            ),
            platform_evidence=platform(),
            hardening_evidence=hardening(),
        )
        self.assertEqual(out["decision"], "DECLINE")
        self.assertFalse(out["automatic_rejection_external_effect"])
        self.assertTrue(out["human_owner_decision_required"])

    def test_invalid_score_or_insufficient_evidence_blocks(self):
        out = assess_b2b_pilot_candidate(
            trusted_scope=SCOPE,
            candidate=candidate(problem_fit=6, evidence_refs=["one"]),
            platform_evidence=platform(),
            hardening_evidence=hardening(),
        )
        self.assertEqual(out["decision"], "BLOCKED")
        self.assertIn("PROBLEM_FIT_SCORE_INVALID", out["blockers"])
        self.assertIn("CANDIDATE_EVIDENCE_INSUFFICIENT", out["blockers"])

    def test_no_external_or_production_authority_is_granted(self):
        out = assess_b2b_pilot_candidate(
            trusted_scope=SCOPE,
            candidate=candidate(),
            platform_evidence=platform(),
            hardening_evidence=hardening(),
        )
        for key in (
            "automatic_acceptance",
            "automatic_rejection_external_effect",
            "automatic_contract",
            "automatic_billing",
            "automatic_provisioning",
            "automatic_deploy",
            "provider_called",
            "customer_data_mutated",
            "production_mutation",
            "executes_action",
        ):
            self.assertFalse(out[key], key)


if __name__ == "__main__":
    unittest.main()
