from __future__ import annotations

import unittest

from atlasquant_aion_b2b_pilot_planning_handoff import (
    build_pilot_planning_handoff,
)

SCOPE = {
    "owner_id": "owner-a",
    "tenant_id": "tenant-a",
    "workspace_id": "business",
}


def readiness(**overrides):
    row = {
        "schema": "ATLASQUANT_AION_B2B_PILOT_READINESS_V1",
        "state": "READY_FOR_OWNER_REVIEW",
        "decision": "PILOT_REVIEW_CANDIDATE",
        "candidate_id": "candidate-001",
        "scope": dict(SCOPE),
        "acceptance_score": 90.0,
        "risk_score": 20.0,
        "priority_score": 87.5,
        "pilot_duration_days": 14,
        "blockers": [],
        "evidence_digest": "sha256:readiness-001",
        "human_owner_decision_required": True,
        "automatic_acceptance": False,
        "automatic_contract": False,
        "automatic_billing": False,
        "production_mutation": False,
        "executes_action": False,
    }
    row.update(overrides)
    return row


def proposal(**overrides):
    row = {
        "schema": "ATLASQUANT_AION_B2B_PROPOSAL_DRAFT_V1",
        "state": "DRAFT_FOR_HUMAN_REVIEW",
        "proposal": {
            **SCOPE,
            "proposal_id": "proposal-001",
            "candidate_id": "candidate-001",
            "company_label": "Empresa Exemplo",
            "package": "PROFISSIONAL",
            "pricing": {
                "mode": "TBD",
                "indicative_setup_fee_brl": None,
                "indicative_monthly_fee_brl": None,
                "pricing_basis_ref": "",
                "currency": "BRL",
                "binding": False,
            },
            "scope_items": [
                "Diagnóstico operacional",
                "Estruturação de CRM",
                "Acompanhamento de indicadores",
            ],
            "exclusions": [
                "Sem deploy sem aprovação",
                "Sem compromisso automático",
            ],
            "implementation_phases": [
                "Diagnóstico e baseline",
                "Piloto controlado",
                "Revisão humana",
            ],
            "assumptions": ["Dados autorizados", "Responsável disponível"],
            "objectives": [
                "Reduzir tempo de resposta",
                "Melhorar conversão",
            ],
            "quick_win_candidates": [
                "Organizar follow-up e CRM",
                "Padronizar próxima ação",
            ],
            "diagnostic_constraints": [
                "Sem automação irreversível",
            ],
            "pilot_duration_days": 14,
            "validity_days": 15,
            "diagnostic_digest": "sha256:diag-001",
            "readiness_evidence_digest": "sha256:readiness-001",
            "human_commercial_author_ref": "commercial-owner:001",
            "evidence_refs": ["commercial:scope", "commercial:terms"],
        },
        "proposal_digest": "sha256:proposal-001",
        "non_binding": True,
        "owner_review_required": True,
        "customer_send_allowed": False,
        "contract_ready": False,
        "price_commitment": False,
        "automatic_proposal_generation": False,
        "automatic_pricing": False,
        "automatic_customer_contact": False,
        "automatic_contract": False,
        "automatic_billing": False,
        "automatic_provisioning": False,
        "crm_write": False,
        "provider_called": False,
        "production_mutation": False,
        "executes_action": False,
    }
    row.update(overrides)
    return row


def planning(**overrides):
    row = {
        "human_planning_confirmed": True,
        "human_pilot_planner_ref": "pilot-planner:001",
        "pilot_id": "pilot-001",
        "duration_days": 14,
        "max_monthly_infra_brl": 150.0,
        "pilot_scope_items": [
            "Estruturação de CRM",
            "Acompanhamento de indicadores",
        ],
        "objectives": [
            "Reduzir tempo de resposta",
            "Melhorar conversão",
        ],
        "quick_wins": [
            "Organizar follow-up e CRM",
        ],
        "kpis": [
            {
                "metric_id": "response_minutes",
                "label": "Tempo médio de primeira resposta",
                "unit": "minutes",
                "direction": "LOWER",
                "baseline": 30.0,
                "target": 15.0,
                "source_ref": "baseline:crm",
            },
            {
                "metric_id": "followup_completion_pct",
                "label": "Follow-ups no prazo",
                "unit": "percent",
                "direction": "HIGHER",
                "baseline": 60.0,
                "target": 85.0,
                "source_ref": "baseline:crm",
            },
            {
                "metric_id": "admin_minutes_per_case",
                "label": "Tempo administrativo por caso",
                "unit": "minutes",
                "direction": "LOWER",
                "baseline": 20.0,
                "target": 12.0,
                "source_ref": "baseline:time",
            },
        ],
        "stop_conditions": [
            "Qualquer incidente de privacidade",
            "Qualquer violação de tenant",
            "Orçamento excedido sem aprovação",
        ],
        "rollback_steps": [
            "Desabilitar roteamento do piloto",
            "Restaurar processo manual aprovado",
        ],
        "evidence_refs": [
            "pilot-plan:scope",
            "pilot-plan:kpis",
        ],
    }
    row.update(overrides)
    return row


class AionB2BPilotPlanningHandoffTests(unittest.TestCase):
    def test_valid_proposal_plans_existing_operating_contract_only(self):
        out = build_pilot_planning_handoff(
            trusted_scope=SCOPE,
            proposal_draft=proposal(),
            readiness=readiness(),
            planning_terms=planning(),
        )
        self.assertEqual(out["state"], "PLANNED_FOR_OWNER_REVIEW")
        self.assertEqual(out["activation_state"], "BLOCKED_UNTIL_OWNER_APPROVAL")
        self.assertFalse(out["blockers"])
        self.assertTrue(out["human_owner_approval_required"])
        contract = out["operating_contract"]
        self.assertEqual(contract["state"], "DRAFT_FOR_OWNER_APPROVAL")
        self.assertEqual(
            contract["activation_state"],
            "BLOCKED_UNTIL_OWNER_APPROVAL",
        )
        self.assertFalse(contract["automatic_activation"])
        self.assertFalse(out["automatic_activation"])
        self.assertFalse(out["executes_action"])

    def test_existing_operating_contract_receives_proposal_evidence(self):
        out = build_pilot_planning_handoff(
            trusted_scope=SCOPE,
            proposal_draft=proposal(),
            readiness=readiness(),
            planning_terms=planning(),
        )
        refs = out["operating_contract"]["contract"]["evidence_refs"]
        self.assertIn("sha256:proposal-001", refs)
        self.assertIn("sha256:readiness-001", refs)
        self.assertIn("pilot-planner:001", refs)

    def test_candidate_mismatch_blocks_before_contract(self):
        bad_readiness = readiness(candidate_id="other-candidate")
        out = build_pilot_planning_handoff(
            trusted_scope=SCOPE,
            proposal_draft=proposal(),
            readiness=bad_readiness,
            planning_terms=planning(),
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("READINESS_CANDIDATE_MISMATCH", out["blockers"])
        self.assertIsNone(out["operating_contract"])

    def test_cross_tenant_proposal_blocks(self):
        bad = proposal()
        bad["proposal"] = dict(bad["proposal"])
        bad["proposal"]["tenant_id"] = "tenant-b"
        out = build_pilot_planning_handoff(
            trusted_scope=SCOPE,
            proposal_draft=bad,
            readiness=readiness(),
            planning_terms=planning(),
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("PROPOSAL_SCOPE_MISMATCH", out["blockers"])

    def test_cross_tenant_readiness_blocks(self):
        bad = readiness(
            scope={
                "owner_id": "owner-a",
                "tenant_id": "tenant-b",
                "workspace_id": "business",
            }
        )
        out = build_pilot_planning_handoff(
            trusted_scope=SCOPE,
            proposal_draft=proposal(),
            readiness=bad,
            planning_terms=planning(),
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("READINESS_SCOPE_MISMATCH", out["blockers"])

    def test_proposal_and_readiness_digest_mismatch_blocks(self):
        bad = readiness(evidence_digest="sha256:other-readiness")
        out = build_pilot_planning_handoff(
            trusted_scope=SCOPE,
            proposal_draft=proposal(),
            readiness=bad,
            planning_terms=planning(),
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "PROPOSAL_READINESS_EVIDENCE_MISMATCH",
            out["blockers"],
        )

    def test_proposal_must_remain_non_binding_and_unsent(self):
        for key, value, expected in (
            ("non_binding", False, "PROPOSAL_MUST_REMAIN_NON_BINDING"),
            ("customer_send_allowed", True, "PROPOSAL_CUSTOMER_SEND_ALLOWED_UNSAFE"),
            ("contract_ready", True, "PROPOSAL_CONTRACT_READY_UNSAFE"),
            ("price_commitment", True, "PROPOSAL_PRICE_COMMITMENT_UNSAFE"),
        ):
            with self.subTest(key=key):
                bad = proposal(**{key: value})
                out = build_pilot_planning_handoff(
                    trusted_scope=SCOPE,
                    proposal_draft=bad,
                    readiness=readiness(),
                    planning_terms=planning(),
                )
                self.assertEqual(out["state"], "BLOCKED")
                self.assertIn(expected, out["blockers"])

    def test_truthy_human_planning_string_does_not_count(self):
        out = build_pilot_planning_handoff(
            trusted_scope=SCOPE,
            proposal_draft=proposal(),
            readiness=readiness(),
            planning_terms=planning(human_planning_confirmed="true"),
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "EXPLICIT_HUMAN_PILOT_PLANNING_REQUIRED",
            out["blockers"],
        )

    def test_pilot_scope_cannot_expand_beyond_proposal(self):
        out = build_pilot_planning_handoff(
            trusted_scope=SCOPE,
            proposal_draft=proposal(),
            readiness=readiness(),
            planning_terms=planning(
                pilot_scope_items=[
                    "Estruturação de CRM",
                    "Implantar ERP completo",
                ]
            ),
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("PILOT_SCOPE_EXPANDS_PROPOSAL", out["blockers"])

    def test_objectives_and_quick_wins_cannot_silently_expand(self):
        objective = build_pilot_planning_handoff(
            trusted_scope=SCOPE,
            proposal_draft=proposal(),
            readiness=readiness(),
            planning_terms=planning(
                objectives=["Objetivo novo fora da proposta"]
            ),
        )
        quick_win = build_pilot_planning_handoff(
            trusted_scope=SCOPE,
            proposal_draft=proposal(),
            readiness=readiness(),
            planning_terms=planning(
                quick_wins=["Automatizar tudo sem revisão"]
            ),
        )
        self.assertIn("PILOT_OBJECTIVE_NOT_IN_PROPOSAL", objective["blockers"])
        self.assertIn("PILOT_QUICK_WIN_NOT_IN_PROPOSAL", quick_win["blockers"])

    def test_existing_contract_keeps_duration_budget_kpi_and_rollback_rules(self):
        duration = build_pilot_planning_handoff(
            trusted_scope=SCOPE,
            proposal_draft=proposal(),
            readiness=readiness(),
            planning_terms=planning(duration_days=31),
        )
        budget = build_pilot_planning_handoff(
            trusted_scope=SCOPE,
            proposal_draft=proposal(),
            readiness=readiness(),
            planning_terms=planning(max_monthly_infra_brl=201.0),
        )
        stop = build_pilot_planning_handoff(
            trusted_scope=SCOPE,
            proposal_draft=proposal(),
            readiness=readiness(),
            planning_terms=planning(stop_conditions=["only one"]),
        )
        self.assertEqual(duration["state"], "BLOCKED")
        self.assertTrue(
            any(
                "PILOT_DURATION_OUT_OF_RANGE" in x
                for x in duration["blockers"]
            )
        )
        self.assertTrue(
            any(
                "PILOT_INFRA_BUDGET_EXCEEDS_CAP" in x
                for x in budget["blockers"]
            )
        )
        self.assertTrue(
            any(
                "STOP_CONDITIONS_INSUFFICIENT" in x
                for x in stop["blockers"]
            )
        )

    def test_handoff_is_deterministic_for_same_inputs(self):
        first = build_pilot_planning_handoff(
            trusted_scope=SCOPE,
            proposal_draft=proposal(),
            readiness=readiness(),
            planning_terms=planning(),
        )
        second = build_pilot_planning_handoff(
            trusted_scope=SCOPE,
            proposal_draft=proposal(),
            readiness=readiness(),
            planning_terms=planning(),
        )
        self.assertEqual(first["handoff_digest"], second["handoff_digest"])
        self.assertEqual(
            first["operating_contract"]["contract_digest"],
            second["operating_contract"]["contract_digest"],
        )

    def test_handoff_never_activates_contacts_bills_or_mutates(self):
        out = build_pilot_planning_handoff(
            trusted_scope=SCOPE,
            proposal_draft=proposal(),
            readiness=readiness(),
            planning_terms=planning(),
        )
        for key in (
            "automatic_activation",
            "automatic_contract_signature",
            "automatic_customer_contact",
            "automatic_billing",
            "automatic_spend",
            "automatic_deploy",
            "crm_write",
            "provider_called",
            "production_mutation",
            "executes_action",
        ):
            self.assertFalse(out[key], key)


if __name__ == "__main__":
    unittest.main()
