from __future__ import annotations

import unittest

from atlasquant_aion_b2b_diagnostic_intake import (
    build_diagnostic_intake,
    build_pilot_scoring_input,
)
from atlasquant_aion_b2b_pilot_readiness import assess_b2b_pilot_candidate
from atlasquant_aion_b2b_proposal_draft import build_b2b_proposal_draft

SCOPE = {
    "owner_id": "owner-a",
    "tenant_id": "tenant-a",
    "workspace_id": "business",
}


def metric(metric_id):
    return {
        "metric_id": metric_id,
        "label": metric_id,
        "unit": "count",
        "value": 10,
        "source_ref": f"source:{metric_id}",
    }


def area(name, *, baseline=True):
    return {
        "current_process": f"Processo de {name}",
        "pain_points": [f"Gargalo de {name}"],
        "systems": [f"system-{name}"],
        "baseline_metrics": [metric(f"{name}_baseline")] if baseline else [],
        "evidence_refs": [f"evidence:{name}"],
    }


def diagnostic_raw():
    return {
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
        "constraints": ["Sem automação irreversível"],
        "quick_win_candidates": ["Organizar follow-up e CRM"],
        "integration_candidates": ["crm", "email"],
        "evidence_refs": ["diag:01", "diag:02", "diag:03"],
    }


def assessment():
    return {
        "human_assessed": True,
        "assessor_ref": "owner-review:001",
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
        "evidence_refs": ["assessment:01", "assessment:02"],
    }


def platform():
    return {
        "state": "PASS",
        "pilot_recommendation": "HUMAN_REVIEW_CANDIDATE",
        "total_tasks": 1000,
        "company_count": 3,
        "classification_error_count": 0,
        "unsafe_escape_count": 0,
        "deny_escape_count": 0,
        "evidence_digest": "sha256:managed-ops-reference",
    }


def hardening():
    return {
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


def chain():
    diagnostic = build_diagnostic_intake(
        diagnostic_raw(),
        trusted_scope=SCOPE,
    )
    scoring = build_pilot_scoring_input(
        diagnostic,
        human_assessment=assessment(),
    )
    readiness = assess_b2b_pilot_candidate(
        trusted_scope=SCOPE,
        candidate=scoring["candidate"],
        platform_evidence=platform(),
        hardening_evidence=hardening(),
    )
    return diagnostic, readiness


def terms(**overrides):
    row = {
        "proposal_id": "proposal-001",
        "human_commercial_author_ref": "commercial-owner:001",
        "human_terms_confirmed": True,
        "non_binding": True,
        "package": "PROFISSIONAL",
        "pricing_mode": "TBD",
        "indicative_setup_fee_brl": None,
        "indicative_monthly_fee_brl": None,
        "pricing_basis_ref": "",
        "scope_items": [
            "Diagnóstico operacional",
            "Estruturação de CRM",
            "Acompanhamento de indicadores",
        ],
        "exclusions": [
            "Sem compromisso automático de preço",
            "Sem deploy sem aprovação",
        ],
        "implementation_phases": [
            "Diagnóstico e baseline",
            "Piloto controlado",
            "Revisão humana",
        ],
        "assumptions": [
            "Acesso a dados autorizados",
            "Responsável do cliente disponível",
        ],
        "validity_days": 15,
        "evidence_refs": ["commercial:scope", "commercial:terms"],
    }
    row.update(overrides)
    return row


class AionB2BProposalDraftTests(unittest.TestCase):
    def test_tbd_proposal_is_non_binding_human_review_draft(self):
        diagnostic, readiness = chain()
        out = build_b2b_proposal_draft(
            trusted_scope=SCOPE,
            diagnostic=diagnostic,
            readiness=readiness,
            commercial_terms=terms(),
        )
        self.assertEqual(out["state"], "DRAFT_FOR_HUMAN_REVIEW")
        self.assertFalse(out["blockers"])
        self.assertEqual(out["proposal"]["candidate_id"], "candidate-001")
        self.assertEqual(out["proposal"]["package"], "PROFISSIONAL")
        self.assertEqual(out["proposal"]["pricing"]["mode"], "TBD")
        self.assertIsNone(out["proposal"]["pricing"]["indicative_monthly_fee_brl"])
        self.assertFalse(out["proposal"]["pricing"]["binding"])
        self.assertTrue(out["owner_review_required"])
        self.assertFalse(out["customer_send_allowed"])

    def test_proposal_binds_diagnostic_and_readiness_evidence(self):
        diagnostic, readiness = chain()
        out = build_b2b_proposal_draft(
            trusted_scope=SCOPE,
            diagnostic=diagnostic,
            readiness=readiness,
            commercial_terms=terms(),
        )
        self.assertEqual(
            out["proposal"]["diagnostic_digest"],
            diagnostic["diagnostic_digest"],
        )
        self.assertEqual(
            out["proposal"]["readiness_evidence_digest"],
            readiness["evidence_digest"],
        )
        self.assertEqual(readiness["candidate_id"], "candidate-001")
        self.assertEqual(readiness["scope"], SCOPE)

    def test_candidate_mismatch_blocks(self):
        diagnostic, readiness = chain()
        readiness = dict(readiness)
        readiness["candidate_id"] = "other-candidate"
        out = build_b2b_proposal_draft(
            trusted_scope=SCOPE,
            diagnostic=diagnostic,
            readiness=readiness,
            commercial_terms=terms(),
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("READINESS_CANDIDATE_MISMATCH", out["blockers"])

    def test_cross_tenant_readiness_blocks(self):
        diagnostic, readiness = chain()
        readiness = dict(readiness)
        readiness["scope"] = {
            "owner_id": "owner-a",
            "tenant_id": "tenant-b",
            "workspace_id": "business",
        }
        out = build_b2b_proposal_draft(
            trusted_scope=SCOPE,
            diagnostic=diagnostic,
            readiness=readiness,
            commercial_terms=terms(),
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("READINESS_SCOPE_MISMATCH", out["blockers"])

    def test_readiness_must_be_positive_owner_review_candidate(self):
        diagnostic, readiness = chain()
        readiness = dict(readiness)
        readiness["state"] = "REVIEW"
        readiness["decision"] = "REVIEW"
        out = build_b2b_proposal_draft(
            trusted_scope=SCOPE,
            diagnostic=diagnostic,
            readiness=readiness,
            commercial_terms=terms(),
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("READINESS_STATE_INVALID", out["blockers"])
        self.assertIn("READINESS_NOT_PILOT_REVIEW_CANDIDATE", out["blockers"])

    def test_truthy_human_terms_string_does_not_count(self):
        diagnostic, readiness = chain()
        out = build_b2b_proposal_draft(
            trusted_scope=SCOPE,
            diagnostic=diagnostic,
            readiness=readiness,
            commercial_terms=terms(human_terms_confirmed="true"),
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("EXPLICIT_HUMAN_COMMERCIAL_TERMS_REQUIRED", out["blockers"])

    def test_non_binding_must_be_explicit_true(self):
        diagnostic, readiness = chain()
        out = build_b2b_proposal_draft(
            trusted_scope=SCOPE,
            diagnostic=diagnostic,
            readiness=readiness,
            commercial_terms=terms(non_binding=False),
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("NON_BINDING_DRAFT_REQUIRED", out["blockers"])

    def test_package_is_closed_list(self):
        diagnostic, readiness = chain()
        out = build_b2b_proposal_draft(
            trusted_scope=SCOPE,
            diagnostic=diagnostic,
            readiness=readiness,
            commercial_terms=terms(package="ULTRA"),
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("PACKAGE_INVALID", out["blockers"])

    def test_indicative_pricing_requires_values_and_basis(self):
        diagnostic, readiness = chain()
        out = build_b2b_proposal_draft(
            trusted_scope=SCOPE,
            diagnostic=diagnostic,
            readiness=readiness,
            commercial_terms=terms(pricing_mode="INDICATIVE"),
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("INDICATIVE_SETUP_FEE_INVALID", out["blockers"])
        self.assertIn("INDICATIVE_MONTHLY_FEE_INVALID", out["blockers"])
        self.assertIn("PRICING_BASIS_REF_REQUIRED", out["blockers"])

    def test_valid_indicative_price_remains_non_binding(self):
        diagnostic, readiness = chain()
        out = build_b2b_proposal_draft(
            trusted_scope=SCOPE,
            diagnostic=diagnostic,
            readiness=readiness,
            commercial_terms=terms(
                pricing_mode="INDICATIVE",
                indicative_setup_fee_brl=2500,
                indicative_monthly_fee_brl=4500,
                pricing_basis_ref="pricing-review:001",
            ),
        )
        self.assertEqual(out["state"], "DRAFT_FOR_HUMAN_REVIEW")
        self.assertEqual(
            out["proposal"]["pricing"]["indicative_monthly_fee_brl"],
            4500.0,
        )
        self.assertFalse(out["proposal"]["pricing"]["binding"])
        self.assertFalse(out["price_commitment"])
        self.assertFalse(out["automatic_pricing"])

    def test_tbd_mode_rejects_hidden_numeric_price(self):
        diagnostic, readiness = chain()
        out = build_b2b_proposal_draft(
            trusted_scope=SCOPE,
            diagnostic=diagnostic,
            readiness=readiness,
            commercial_terms=terms(
                pricing_mode="TBD",
                indicative_monthly_fee_brl=4500,
            ),
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("TBD_MONTHLY_FEE_MUST_BE_EMPTY", out["blockers"])

    def test_scope_exclusions_phases_assumptions_and_evidence_are_required(self):
        diagnostic, readiness = chain()
        out = build_b2b_proposal_draft(
            trusted_scope=SCOPE,
            diagnostic=diagnostic,
            readiness=readiness,
            commercial_terms=terms(
                scope_items=["one"],
                exclusions=[],
                implementation_phases=["one"],
                assumptions=[],
                evidence_refs=[],
            ),
        )
        self.assertEqual(out["state"], "BLOCKED")
        for expected in (
            "PROPOSAL_SCOPE_INSUFFICIENT",
            "PROPOSAL_EXCLUSIONS_INSUFFICIENT",
            "IMPLEMENTATION_PHASES_INSUFFICIENT",
            "PROPOSAL_ASSUMPTIONS_INSUFFICIENT",
            "PROPOSAL_EVIDENCE_INSUFFICIENT",
        ):
            self.assertIn(expected, out["blockers"])

    def test_proposal_does_not_copy_lead_or_contact_identity(self):
        diagnostic, readiness = chain()
        out = build_b2b_proposal_draft(
            trusted_scope=SCOPE,
            diagnostic=diagnostic,
            readiness=readiness,
            commercial_terms=terms(),
        )
        flat = str(out["proposal"])
        self.assertNotIn("lead-001", flat)
        self.assertNotIn("assessor_context_ref", flat)
        self.assertNotIn("contact", flat.lower())

    def test_draft_never_grants_send_contract_billing_or_production_authority(self):
        diagnostic, readiness = chain()
        out = build_b2b_proposal_draft(
            trusted_scope=SCOPE,
            diagnostic=diagnostic,
            readiness=readiness,
            commercial_terms=terms(),
        )
        for key in (
            "customer_send_allowed",
            "contract_ready",
            "price_commitment",
            "automatic_proposal_generation",
            "automatic_pricing",
            "automatic_customer_contact",
            "automatic_contract",
            "automatic_billing",
            "automatic_provisioning",
            "crm_write",
            "provider_called",
            "production_mutation",
            "executes_action",
        ):
            self.assertFalse(out[key], key)

    def test_proposal_digest_is_deterministic(self):
        diagnostic, readiness = chain()
        first = build_b2b_proposal_draft(
            trusted_scope=SCOPE,
            diagnostic=diagnostic,
            readiness=readiness,
            commercial_terms=terms(),
        )
        second = build_b2b_proposal_draft(
            trusted_scope=SCOPE,
            diagnostic=diagnostic,
            readiness=readiness,
            commercial_terms=terms(),
        )
        self.assertEqual(first["proposal_digest"], second["proposal_digest"])


if __name__ == "__main__":
    unittest.main()
