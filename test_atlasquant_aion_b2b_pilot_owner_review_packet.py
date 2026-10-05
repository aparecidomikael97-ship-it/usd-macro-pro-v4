from __future__ import annotations

import unittest

from atlasquant_aion_b2b_pilot_owner_review_packet import (
    build_pilot_owner_review_packet,
)

SCOPE = {
    "owner_id": "owner-a",
    "tenant_id": "tenant-a",
    "workspace_id": "business",
}


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
                "mode": "INDICATIVE",
                "indicative_setup_fee_brl": 2500.0,
                "indicative_monthly_fee_brl": 4500.0,
                "pricing_basis_ref": "pricing-review:001",
                "currency": "BRL",
                "binding": False,
            },
            "readiness_evidence_digest": "sha256:ready",
        },
        "proposal_digest": "sha256:proposal",
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


def readiness(**overrides):
    row = {
        "schema": "ATLASQUANT_AION_B2B_PILOT_READINESS_V1",
        "state": "READY_FOR_OWNER_REVIEW",
        "decision": "PILOT_REVIEW_CANDIDATE",
        "candidate_id": "candidate-001",
        "scope": dict(SCOPE),
        "acceptance_score": 92.0,
        "risk_score": 20.0,
        "priority_score": 89.0,
        "planned_monthly_infra_brl": 150.0,
        "blockers": [],
        "evidence_digest": "sha256:ready",
        "human_owner_decision_required": True,
        "automatic_acceptance": False,
        "automatic_contract": False,
        "automatic_billing": False,
        "production_mutation": False,
        "executes_action": False,
    }
    row.update(overrides)
    return row


def handoff(**overrides):
    row = {
        "schema": "ATLASQUANT_AION_B2B_PILOT_PLANNING_HANDOFF_V1",
        "state": "PLANNED_FOR_OWNER_REVIEW",
        "scope": dict(SCOPE),
        "proposal_id": "proposal-001",
        "candidate_id": "candidate-001",
        "pilot_id": "pilot-001",
        "pilot_scope_items": [
            "Estruturação de CRM",
            "Acompanhamento de indicadores",
        ],
        "operating_contract": {
            "schema": "ATLASQUANT_AION_B2B_PILOT_OPERATING_CONTRACT_V1",
            "state": "DRAFT_FOR_OWNER_APPROVAL",
            "activation_state": "BLOCKED_UNTIL_OWNER_APPROVAL",
            "contract": {
                **SCOPE,
                "pilot_id": "pilot-001",
                "candidate_id": "candidate-001",
                "duration_days": 14,
                "max_monthly_infra_brl": 150.0,
                "objectives": ["Reduzir tempo de resposta"],
                "quick_wins": ["Organizar follow-up e CRM"],
                "kpis": [
                    {
                        "metric_id": "response_minutes",
                        "label": "Tempo de resposta",
                        "unit": "minutes",
                        "direction": "LOWER",
                        "baseline": 30.0,
                        "target": 15.0,
                        "source_ref": "secret:kpi-1",
                    },
                    {
                        "metric_id": "followup_completion_pct",
                        "label": "Follow-up no prazo",
                        "unit": "percent",
                        "direction": "HIGHER",
                        "baseline": 60.0,
                        "target": 85.0,
                        "source_ref": "secret:kpi-2",
                    },
                    {
                        "metric_id": "admin_minutes_per_case",
                        "label": "Admin por caso",
                        "unit": "minutes",
                        "direction": "LOWER",
                        "baseline": 20.0,
                        "target": 12.0,
                        "source_ref": "secret:kpi-3",
                    },
                ],
                "stop_conditions": ["privacy", "scope", "budget"],
                "rollback_steps": ["disable routing", "restore manual"],
                "evidence_refs": [
                    "sha256:proposal",
                    "sha256:ready",
                    "secret:planner",
                ],
                "readiness_evidence_digest": "sha256:ready",
            },
            "blockers": [],
            "contract_digest": "sha256:contract",
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
        },
        "blockers": [],
        "handoff_digest": "sha256:handoff",
        "human_owner_approval_required": True,
        "activation_state": "BLOCKED_UNTIL_OWNER_APPROVAL",
        "automatic_activation": False,
        "automatic_contract_signature": False,
        "automatic_customer_contact": False,
        "automatic_billing": False,
        "automatic_spend": False,
        "automatic_deploy": False,
        "crm_write": False,
        "provider_called": False,
        "production_mutation": False,
        "executes_action": False,
    }
    row.update(overrides)
    return row


class AionB2BPilotOwnerReviewPacketTests(unittest.TestCase):
    def test_valid_chain_builds_owner_review_packet_only(self):
        out = build_pilot_owner_review_packet(
            trusted_scope=SCOPE,
            proposal_draft=proposal(),
            readiness=readiness(),
            pilot_handoff=handoff(),
        )
        self.assertEqual(out["state"], "READY_FOR_OWNER_REVIEW")
        self.assertFalse(out["blockers"])
        self.assertEqual(out["owner_decision"], "UNDECIDED")
        self.assertFalse(out["owner_decision_recorded"])
        self.assertFalse(out["owner_approval_recorded"])
        self.assertFalse(out["pilot_activation_authorized"])
        self.assertTrue(out["human_owner_decision_required"])
        self.assertFalse(out["executes_action"])

    def test_packet_summarizes_commercial_readiness_and_pilot(self):
        out = build_pilot_owner_review_packet(
            trusted_scope=SCOPE,
            proposal_draft=proposal(),
            readiness=readiness(),
            pilot_handoff=handoff(),
        )
        summary = out["summary"]
        self.assertEqual(summary["proposal"]["package"], "PROFISSIONAL")
        self.assertEqual(summary["proposal"]["pricing_mode"], "INDICATIVE")
        self.assertEqual(
            summary["proposal"]["indicative_monthly_fee_brl"],
            4500.0,
        )
        self.assertFalse(summary["proposal"]["pricing_binding"])
        self.assertEqual(summary["readiness"]["priority_score"], 89.0)
        self.assertEqual(summary["pilot"]["pilot_id"], "pilot-001")
        self.assertEqual(summary["pilot"]["duration_days"], 14)
        self.assertEqual(len(summary["pilot"]["kpis"]), 3)
        self.assertEqual(len(summary["pilot"]["stop_conditions"]), 3)
        self.assertEqual(len(summary["pilot"]["rollback_steps"]), 2)

    def test_packet_does_not_copy_kpi_source_refs_or_planner_refs(self):
        out = build_pilot_owner_review_packet(
            trusted_scope=SCOPE,
            proposal_draft=proposal(),
            readiness=readiness(),
            pilot_handoff=handoff(),
        )
        flat = str(out["summary"])
        self.assertNotIn("secret:kpi-1", flat)
        self.assertNotIn("secret:kpi-2", flat)
        self.assertNotIn("secret:planner", flat)
        self.assertNotIn("source_ref", flat)

    def test_candidate_mismatch_blocks(self):
        bad = readiness(candidate_id="candidate-999")
        out = build_pilot_owner_review_packet(
            trusted_scope=SCOPE,
            proposal_draft=proposal(),
            readiness=bad,
            pilot_handoff=handoff(),
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("READINESS_CANDIDATE_MISMATCH", out["blockers"])

    def test_proposal_readiness_digest_mismatch_blocks(self):
        bad = readiness(evidence_digest="sha256:other")
        out = build_pilot_owner_review_packet(
            trusted_scope=SCOPE,
            proposal_draft=proposal(),
            readiness=bad,
            pilot_handoff=handoff(),
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "PROPOSAL_READINESS_EVIDENCE_MISMATCH",
            out["blockers"],
        )

    def test_cross_tenant_handoff_blocks(self):
        bad = handoff()
        bad["scope"] = {
            "owner_id": "owner-a",
            "tenant_id": "tenant-b",
            "workspace_id": "business",
        }
        out = build_pilot_owner_review_packet(
            trusted_scope=SCOPE,
            proposal_draft=proposal(),
            readiness=readiness(),
            pilot_handoff=bad,
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("PILOT_HANDOFF_SCOPE_MISMATCH", out["blockers"])

    def test_handoff_must_preserve_proposal_evidence(self):
        bad = handoff()
        bad["operating_contract"] = dict(bad["operating_contract"])
        bad["operating_contract"]["contract"] = dict(
            bad["operating_contract"]["contract"]
        )
        bad["operating_contract"]["contract"]["evidence_refs"] = [
            "sha256:ready"
        ]
        out = build_pilot_owner_review_packet(
            trusted_scope=SCOPE,
            proposal_draft=proposal(),
            readiness=readiness(),
            pilot_handoff=bad,
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "OPERATING_CONTRACT_PROPOSAL_EVIDENCE_MISSING",
            out["blockers"],
        )

    def test_unsafe_proposal_action_flag_blocks(self):
        for key in (
            "customer_send_allowed",
            "contract_ready",
            "price_commitment",
            "automatic_customer_contact",
            "automatic_contract",
            "automatic_billing",
            "crm_write",
            "executes_action",
        ):
            with self.subTest(key=key):
                bad = proposal()
                bad[key] = True
                out = build_pilot_owner_review_packet(
                    trusted_scope=SCOPE,
                    proposal_draft=bad,
                    readiness=readiness(),
                    pilot_handoff=handoff(),
                )
                self.assertEqual(out["state"], "BLOCKED")

    def test_unsafe_handoff_action_flag_blocks(self):
        for key in (
            "automatic_activation",
            "automatic_customer_contact",
            "automatic_billing",
            "automatic_spend",
            "automatic_deploy",
            "crm_write",
            "provider_called",
            "production_mutation",
            "executes_action",
        ):
            with self.subTest(key=key):
                bad = handoff()
                bad[key] = True
                out = build_pilot_owner_review_packet(
                    trusted_scope=SCOPE,
                    proposal_draft=proposal(),
                    readiness=readiness(),
                    pilot_handoff=bad,
                )
                self.assertEqual(out["state"], "BLOCKED")

    def test_checklist_is_evidence_summary_not_approval(self):
        out = build_pilot_owner_review_packet(
            trusted_scope=SCOPE,
            proposal_draft=proposal(),
            readiness=readiness(),
            pilot_handoff=handoff(),
        )
        self.assertTrue(all(out["checklist"].values()))
        self.assertEqual(out["owner_decision"], "UNDECIDED")
        self.assertFalse(out["owner_approval_recorded"])

    def test_core_freeze_decision_mechanism_is_not_reused(self):
        out = build_pilot_owner_review_packet(
            trusted_scope=SCOPE,
            proposal_draft=proposal(),
            readiness=readiness(),
            pilot_handoff=handoff(),
        )
        self.assertFalse(out["decision_mechanism_reused_from_core_freeze"])
        self.assertFalse(out["owner_signature_requested"])
        self.assertFalse(out["owner_signature_verified"])

    def test_packet_never_authorizes_or_executes(self):
        out = build_pilot_owner_review_packet(
            trusted_scope=SCOPE,
            proposal_draft=proposal(),
            readiness=readiness(),
            pilot_handoff=handoff(),
        )
        for key in (
            "pilot_activation_authorized",
            "automatic_activation",
            "automatic_customer_contact",
            "automatic_contract_signature",
            "automatic_billing",
            "automatic_spend",
            "automatic_deploy",
            "crm_write",
            "provider_called",
            "production_mutation",
            "grants_authority",
            "executes_action",
        ):
            self.assertFalse(out[key], key)

    def test_packet_digest_is_deterministic(self):
        first = build_pilot_owner_review_packet(
            trusted_scope=SCOPE,
            proposal_draft=proposal(),
            readiness=readiness(),
            pilot_handoff=handoff(),
        )
        second = build_pilot_owner_review_packet(
            trusted_scope=SCOPE,
            proposal_draft=proposal(),
            readiness=readiness(),
            pilot_handoff=handoff(),
        )
        self.assertEqual(first["packet_digest"], second["packet_digest"])


if __name__ == "__main__":
    unittest.main()
