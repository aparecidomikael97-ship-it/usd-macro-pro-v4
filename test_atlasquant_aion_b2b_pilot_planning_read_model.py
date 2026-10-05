from __future__ import annotations

import unittest

from atlasquant_aion_b2b_pilot_planning_read_model import (
    build_pilot_planning_read_model,
)

SCOPE = {
    "owner_id": "owner-a",
    "tenant_id": "tenant-a",
    "workspace_id": "business",
}


def handoff(**overrides):
    row = {
        "schema": "ATLASQUANT_AION_B2B_PILOT_PLANNING_HANDOFF_V1",
        "state": "PLANNED_FOR_OWNER_REVIEW",
        "scope": dict(SCOPE),
        "proposal_id": "proposal-001",
        "candidate_id": "candidate-secret",
        "pilot_id": "pilot-001",
        "pilot_scope_items": [
            "Estruturação de CRM",
            "Acompanhamento de indicadores",
        ],
        "planning_spec": {
            "evidence_refs": ["secret:evidence"],
        },
        "operating_contract": {
            "schema": "ATLASQUANT_AION_B2B_PILOT_OPERATING_CONTRACT_V1",
            "state": "DRAFT_FOR_OWNER_APPROVAL",
            "activation_state": "BLOCKED_UNTIL_OWNER_APPROVAL",
            "contract": {
                **SCOPE,
                "pilot_id": "pilot-001",
                "candidate_id": "candidate-secret",
                "duration_days": 14,
                "max_monthly_infra_brl": 150.0,
                "objectives": ["Reduzir tempo de resposta"],
                "quick_wins": ["Organizar follow-up e CRM"],
                "kpis": [
                    {
                        "metric_id": "response_minutes",
                        "source_ref": "secret:kpi-source",
                    },
                    {
                        "metric_id": "followup_completion_pct",
                        "source_ref": "secret:kpi-source-2",
                    },
                    {
                        "metric_id": "admin_minutes_per_case",
                        "source_ref": "secret:kpi-source-3",
                    },
                ],
                "stop_conditions": ["one", "two", "three"],
                "rollback_steps": ["one", "two"],
                "evidence_refs": ["secret:evidence"],
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


class AionB2BPilotPlanningReadModelTests(unittest.TestCase):
    def test_valid_handoff_projects_aggregate_planning_metadata(self):
        out = build_pilot_planning_read_model(
            handoff(),
            trusted_scope=SCOPE,
        )
        self.assertEqual(out["state"], "READY")
        self.assertEqual(out["pilot_id"], "pilot-001")
        self.assertEqual(out["proposal_id"], "proposal-001")
        self.assertEqual(out["duration_days"], 14)
        self.assertEqual(out["max_monthly_infra_brl"], 150.0)
        self.assertEqual(out["pilot_scope_item_count"], 2)
        self.assertEqual(out["kpi_count"], 3)
        self.assertEqual(out["stop_condition_count"], 3)
        self.assertEqual(out["rollback_step_count"], 2)
        self.assertEqual(
            out["activation_state"],
            "BLOCKED_UNTIL_OWNER_APPROVAL",
        )
        self.assertTrue(out["read_only"])
        self.assertFalse(out["executes_action"])

    def test_candidate_and_raw_evidence_are_not_projected(self):
        out = build_pilot_planning_read_model(
            handoff(),
            trusted_scope=SCOPE,
        )
        flat = str(out)
        self.assertNotIn("candidate-secret", flat)
        self.assertNotIn("secret:evidence", flat)
        self.assertNotIn("secret:kpi-source", flat)
        self.assertFalse(out["candidate_identity_exposed"])
        self.assertFalse(out["raw_evidence_exposed"])

    def test_cross_tenant_handoff_blocks(self):
        bad = handoff()
        bad["scope"] = {
            "owner_id": "owner-a",
            "tenant_id": "tenant-b",
            "workspace_id": "business",
        }
        out = build_pilot_planning_read_model(
            bad,
            trusted_scope=SCOPE,
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("PILOT_HANDOFF_SCOPE_MISMATCH", out["blockers"])

    def test_unsafe_handoff_action_flag_blocks(self):
        for key in (
            "automatic_activation",
            "automatic_customer_contact",
            "automatic_billing",
            "automatic_deploy",
            "crm_write",
            "provider_called",
            "production_mutation",
            "executes_action",
        ):
            with self.subTest(key=key):
                bad = handoff()
                bad[key] = True
                out = build_pilot_planning_read_model(
                    bad,
                    trusted_scope=SCOPE,
                )
                self.assertEqual(out["state"], "BLOCKED")
                self.assertTrue(
                    any(key.upper() in item for item in out["blockers"])
                )

    def test_activation_state_must_remain_blocked(self):
        bad = handoff(
            activation_state="ACTIVE"
        )
        out = build_pilot_planning_read_model(
            bad,
            trusted_scope=SCOPE,
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "PILOT_ACTIVATION_BOUNDARY_INVALID",
            out["blockers"],
        )

    def test_nested_contract_must_remain_owner_approval_draft(self):
        bad = handoff()
        bad["operating_contract"] = dict(bad["operating_contract"])
        bad["operating_contract"]["state"] = "ACTIVE"
        out = build_pilot_planning_read_model(
            bad,
            trusted_scope=SCOPE,
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("OPERATING_CONTRACT_STATE_INVALID", out["blockers"])

    def test_nested_contract_auto_activation_blocks(self):
        bad = handoff()
        bad["operating_contract"] = dict(bad["operating_contract"])
        bad["operating_contract"]["automatic_activation"] = True
        out = build_pilot_planning_read_model(
            bad,
            trusted_scope=SCOPE,
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "OPERATING_CONTRACT_AUTOMATIC_ACTIVATION_UNSAFE",
            out["blockers"],
        )

    def test_pilot_id_mismatch_blocks(self):
        bad = handoff(pilot_id="pilot-999")
        out = build_pilot_planning_read_model(
            bad,
            trusted_scope=SCOPE,
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("PILOT_ID_MISMATCH", out["blockers"])

    def test_missing_handoff_digest_blocks(self):
        out = build_pilot_planning_read_model(
            handoff(handoff_digest=""),
            trusted_scope=SCOPE,
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("PILOT_HANDOFF_DIGEST_REQUIRED", out["blockers"])

    def test_read_model_never_exposes_activation_control(self):
        out = build_pilot_planning_read_model(
            handoff(),
            trusted_scope=SCOPE,
        )
        self.assertFalse(out["activation_control_exposed"])
        self.assertFalse(out["automatic_activation"])
        self.assertFalse(out["automatic_customer_contact"])
        self.assertFalse(out["automatic_billing"])
        self.assertFalse(out["automatic_deploy"])
        self.assertFalse(out["grants_authority"])
        self.assertFalse(out["executes_action"])


if __name__ == "__main__":
    unittest.main()
