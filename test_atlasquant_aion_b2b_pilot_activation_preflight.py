from __future__ import annotations

import unittest

from atlasquant_aion_b2b_pilot_activation_preflight import (
    evaluate_pilot_activation_preflight,
)

SCOPE = {
    "owner_id": "HUMAN_OWNER",
    "tenant_id": "atlasquant-owner",
    "workspace_id": "business",
}


def persistence(**overrides):
    row = {
        "schema": "ATLASQUANT_AION_B2B_PILOT_OWNER_DECISION_PERSISTENCE_ATTESTATION_V1",
        "state": "DECISION_RECORD_PERSISTENCE_ATTESTED_APPROVE",
        "blockers": [],
        "decision": "APPROVE_PILOT",
        "scope": dict(SCOPE),
        "candidate_id": "candidate-001",
        "proposal_id": "proposal-001",
        "packet_digest": "sha256:" + "a" * 64,
        "decision_request_digest": "sha256:" + "b" * 64,
        "pilot_id": "pilot-001",
        "decision_record_digest": "sha256:" + "c" * 64,
        "checkpoint_revision": 1,
        "checkpoint_state_digest": "sha256:" + "d" * 64,
        "checkpoint_master_digest": "sha256:" + "e" * 64,
        "receipt_digest": "sha256:" + "f" * 64,
        "attestation_digest": "sha256:" + "1" * 64,
        "owner_decision_recorded": True,
        "decision_record_persisted": True,
        "persistence_attested": True,
        "receipt_consistency_verified": True,
        "writer_identity_verified": False,
        "pilot_approved": True,
        "pilot_denied": False,
        "eligible_for_activation_ceremony": True,
        "pilot_activation_authorized": False,
        "pilot_activated": False,
        "customer_contact_authorized": False,
        "contract_signature_authorized": False,
        "billing_authorized": False,
        "spend_authorized": False,
        "deploy_authorized": False,
        "crm_write_authorized": False,
        "production_mutation_authorized": False,
        "storage_write_performed": False,
        "external_action_executed": False,
        "network_called": False,
        "executes_action": False,
    }
    row.update(overrides)
    return row


def writer(**overrides):
    row = {
        "schema": "ATLASQUANT_AION_B2B_PILOT_CHECKPOINT_WRITER_VERIFICATION_V1",
        "state": "CHECKPOINT_WRITER_AUTHORITY_ATTESTED",
        "blockers": [],
        "pilot_id": "pilot-001",
        "receipt_digest": "sha256:" + "f" * 64,
        "after_checkpoint_digest": "sha256:" + "e" * 64,
        "decision_record_digest": "sha256:" + "c" * 64,
        "event_id": "aion-b2b-pilot-owner-decision-0123456789abcdef",
        "writer_ref": "checkpoint-writer:authorized-path",
        "writer_key_id": "checkpoint-writer-key",
        "writer_key_version": 1,
        "writer_public_key_fingerprint": "sha256:" + "2" * 64,
        "writer_request_digest": "sha256:" + "3" * 64,
        "writer_identity_verified": True,
        "writer_authority_verified": True,
        "receipt_binding_verified": True,
        "nonce_registered": True,
        "pilot_activation_authorized": False,
        "pilot_activated": False,
        "checkpoint_write_performed": False,
        "customer_contact_authorized": False,
        "billing_authorized": False,
        "deploy_authorized": False,
        "production_mutation_authorized": False,
        "external_action_executed": False,
        "network_called": False,
        "executes_action": False,
    }
    row.update(overrides)
    return row


def packet(**overrides):
    row = {
        "schema": "ATLASQUANT_AION_B2B_PILOT_OWNER_REVIEW_PACKET_V1",
        "state": "READY_FOR_OWNER_REVIEW",
        "scope": dict(SCOPE),
        "candidate_id": "candidate-001",
        "summary": {
            "proposal": {
                "proposal_id": "proposal-001",
                "company_label": "Empresa Exemplo",
                "package": "PROFISSIONAL",
                "pricing_mode": "TBD",
                "pricing_binding": False,
                "non_binding": True,
            },
            "readiness": {
                "decision": "PILOT_REVIEW_CANDIDATE",
            },
            "pilot": {
                "pilot_id": "pilot-001",
                "duration_days": 14,
                "max_monthly_infra_brl": 150.0,
                "scope_items": ["Estruturação de CRM"],
                "kpis": [],
                "stop_conditions": ["privacy", "scope", "budget"],
                "rollback_steps": ["disable", "restore"],
                "activation_state": "BLOCKED_UNTIL_OWNER_APPROVAL",
            },
            "evidence": {
                "proposal_digest": "sha256:" + "4" * 64,
                "readiness_evidence_digest": "sha256:" + "5" * 64,
                "pilot_handoff_digest": "sha256:" + "6" * 64,
                "operating_contract_digest": "sha256:" + "7" * 64,
            },
        },
        "checklist": {},
        "blockers": [],
        "packet_digest": "sha256:" + "a" * 64,
        "owner_decision": "UNDECIDED",
        "owner_decision_recorded": False,
        "owner_approval_recorded": False,
        "human_owner_decision_required": True,
        "pilot_activation_authorized": False,
        "automatic_activation": False,
        "automatic_customer_contact": False,
        "automatic_contract_signature": False,
        "automatic_billing": False,
        "automatic_spend": False,
        "automatic_deploy": False,
        "crm_write": False,
        "provider_called": False,
        "production_mutation": False,
        "grants_authority": False,
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
        "pilot_scope_items": ["Estruturação de CRM"],
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
                "quick_wins": ["Organizar follow-up"],
                "kpis": [],
                "stop_conditions": ["privacy", "scope", "budget"],
                "rollback_steps": ["disable", "restore"],
                "evidence_refs": [],
            },
            "blockers": [],
            "contract_digest": "sha256:" + "7" * 64,
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
        "handoff_digest": "sha256:" + "6" * 64,
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


def environment(**overrides):
    row = {
        "schema": "ATLASQUANT_AION_B2B_PILOT_ACTIVATION_ENVIRONMENT_V1",
        "state": "VERIFIED",
        **SCOPE,
        "pilot_id": "pilot-001",
        "checked_at": "2026-10-05T18:20:00Z",
        "tenant_isolation_ready": True,
        "secrets_vault_ready": True,
        "rollback_ready": True,
        "monitoring_ready": True,
        "audit_receipts_ready": True,
        "sandbox_validation_pass": True,
        "integration_health_ready": True,
        "kill_switch_ready": True,
        "security_incident": False,
        "privacy_incident": False,
        "scope_breach": False,
        "reserved_capacity_units": 10,
        "available_capacity_units": 100,
        "planned_monthly_infra_brl": 150.0,
        "evidence_refs": [
            "env:tenant",
            "env:vault",
            "env:rollback",
            "env:monitoring",
        ],
    }
    row.update(overrides)
    return row


def run(**kwargs):
    data = {
        "trusted_scope": SCOPE,
        "persistence_attestation": persistence(),
        "writer_attestation": writer(),
        "owner_review_packet": packet(),
        "pilot_handoff": handoff(),
        "environment_evidence": environment(),
        "now_ts": "2026-10-05T18:21:00Z",
    }
    data.update(kwargs)
    return evaluate_pilot_activation_preflight(**data)


class AionB2BPilotActivationPreflightTests(unittest.TestCase):
    def test_valid_chain_is_ready_for_ceremony_not_activation(self):
        out = run()
        self.assertEqual(out["state"], "READY_FOR_ACTIVATION_CEREMONY")
        self.assertFalse(out["blockers"])
        self.assertTrue(out["activation_ceremony_eligible"])
        self.assertTrue(out["owner_activation_signature_required"])
        self.assertFalse(out["activation_request_issued"])
        self.assertFalse(out["owner_activation_signature_verified"])
        self.assertFalse(out["pilot_activation_authorized"])
        self.assertFalse(out["pilot_activated"])
        self.assertFalse(out["executes_action"])

    def test_persisted_deny_blocks(self):
        denied = persistence(
            state="DECISION_RECORD_PERSISTENCE_ATTESTED_DENY",
            decision="DENY_PILOT",
            pilot_approved=False,
            pilot_denied=True,
            eligible_for_activation_ceremony=False,
        )
        out = run(persistence_attestation=denied)
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("PILOT_DECISION_DENIED", out["blockers"])

    def test_writer_authority_is_mandatory(self):
        out = run(
            writer_attestation=writer(
                writer_authority_verified=False
            )
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("WRITER_AUTHORITY_NOT_VERIFIED", out["blockers"])

    def test_writer_receipt_digest_must_match_persistence(self):
        out = run(
            writer_attestation=writer(
                receipt_digest="sha256:" + "9" * 64
            )
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("WRITER_RECEIPT_DIGEST_MISMATCH", out["blockers"])

    def test_writer_checkpoint_digest_must_match_persistence(self):
        out = run(
            writer_attestation=writer(
                after_checkpoint_digest="sha256:" + "9" * 64
            )
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "WRITER_CHECKPOINT_DIGEST_MISMATCH",
            out["blockers"],
        )

    def test_cross_tenant_packet_blocks(self):
        bad = packet()
        bad["scope"] = {
            "owner_id": "HUMAN_OWNER",
            "tenant_id": "other-tenant",
            "workspace_id": "business",
        }
        out = run(owner_review_packet=bad)
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "OWNER_REVIEW_PACKET_SCOPE_MISMATCH",
            out["blockers"],
        )

    def test_operating_contract_digest_change_blocks(self):
        bad = handoff()
        bad["operating_contract"] = dict(bad["operating_contract"])
        bad["operating_contract"]["contract_digest"] = (
            "sha256:" + "9" * 64
        )
        out = run(pilot_handoff=bad)
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "OPERATING_CONTRACT_DIGEST_MISMATCH",
            out["blockers"],
        )

    def test_environment_must_be_fresh(self):
        out = run(
            environment_evidence=environment(
                checked_at="2026-10-05T18:00:00Z"
            )
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "ACTIVATION_ENVIRONMENT_STALE",
            out["blockers"],
        )

    def test_environment_incident_blocks(self):
        for key in (
            "security_incident",
            "privacy_incident",
            "scope_breach",
        ):
            with self.subTest(key=key):
                env = environment()
                env[key] = True
                out = run(environment_evidence=env)
                self.assertEqual(out["state"], "BLOCKED")

    def test_all_safety_capabilities_are_required(self):
        keys = (
            "tenant_isolation_ready",
            "secrets_vault_ready",
            "rollback_ready",
            "monitoring_ready",
            "audit_receipts_ready",
            "sandbox_validation_pass",
            "integration_health_ready",
            "kill_switch_ready",
        )
        for key in keys:
            with self.subTest(key=key):
                env = environment()
                env[key] = False
                out = run(environment_evidence=env)
                self.assertEqual(out["state"], "BLOCKED")
                self.assertTrue(
                    any(key.upper() in item for item in out["blockers"])
                )

    def test_capacity_must_be_reserved_within_available_units(self):
        out = run(
            environment_evidence=environment(
                reserved_capacity_units=101,
                available_capacity_units=100,
            )
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "ACTIVATION_CAPACITY_INSUFFICIENT",
            out["blockers"],
        )

    def test_monthly_infra_must_respect_contract_and_global_caps(self):
        contract_cap = run(
            environment_evidence=environment(
                planned_monthly_infra_brl=151.0
            )
        )
        global_cap_env = environment(
            planned_monthly_infra_brl=201.0
        )
        global_cap = run(environment_evidence=global_cap_env)
        self.assertIn(
            "ACTIVATION_MONTHLY_INFRA_CONTRACT_CAP_EXCEEDED",
            contract_cap["blockers"],
        )
        self.assertIn(
            "ACTIVATION_MONTHLY_INFRA_GLOBAL_CAP_EXCEEDED",
            global_cap["blockers"],
        )

    def test_environment_requires_evidence_refs(self):
        out = run(
            environment_evidence=environment(
                evidence_refs=["one", "two", "three"]
            )
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "ACTIVATION_ENVIRONMENT_EVIDENCE_INSUFFICIENT",
            out["blockers"],
        )

    def test_preflight_never_grants_external_authority(self):
        out = run()
        for key in (
            "activation_request_issued",
            "owner_activation_signature_verified",
            "pilot_activation_authorized",
            "pilot_activated",
            "customer_contact_authorized",
            "contract_signature_authorized",
            "billing_authorized",
            "spend_authorized",
            "provisioning_authorized",
            "deploy_authorized",
            "crm_write_authorized",
            "provider_called",
            "production_mutation_authorized",
            "external_action_executed",
            "network_called",
            "executes_action",
        ):
            self.assertFalse(out[key], key)

    def test_preflight_digest_is_deterministic(self):
        first = run()
        second = run()
        self.assertEqual(first["preflight_digest"], second["preflight_digest"])
        self.assertEqual(
            first["environment_digest"],
            second["environment_digest"],
        )


if __name__ == "__main__":
    unittest.main()
