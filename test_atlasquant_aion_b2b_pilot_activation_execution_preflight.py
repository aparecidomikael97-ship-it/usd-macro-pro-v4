from __future__ import annotations

import unittest

from atlasquant_aion_b2b_pilot_activation_execution_preflight import (
    evaluate_activation_execution_preflight,
)

SCOPE = {
    "owner_id": "HUMAN_OWNER",
    "tenant_id": "atlasquant-owner",
    "workspace_id": "business",
}


def persistence(**overrides):
    row = {
        "schema": "ATLASQUANT_AION_B2B_PILOT_ACTIVATION_PERSISTENCE_ATTESTATION_V1",
        "state": "ACTIVATION_RECORD_PERSISTENCE_ATTESTED_AUTHORIZE",
        "blockers": [],
        "decision": "AUTHORIZE_PILOT_ACTIVATION",
        "scope": dict(SCOPE),
        "candidate_id": "candidate-001",
        "proposal_id": "proposal-001",
        "pilot_id": "pilot-001",
        "environment_digest": "sha256:" + "e" * 64,
        "preflight_digest": "sha256:" + "f" * 64,
        "activation_request_digest": "sha256:" + "a" * 64,
        "activation_record_digest": "sha256:" + "c" * 64,
        "checkpoint_revision": 2,
        "checkpoint_state_digest": "sha256:" + "d" * 64,
        "checkpoint_master_digest": "sha256:" + "3" * 64,
        "receipt_digest": "sha256:" + "4" * 64,
        "attestation_digest": "sha256:" + "5" * 64,
        "activation_record_persisted": True,
        "persistence_attested": True,
        "receipt_consistency_verified": True,
        "writer_identity_verified": False,
        "activation_authorization_intent": True,
        "activation_denial_intent": False,
        "eligible_for_activation_execution_preflight": True,
        "pilot_activation_authorized": False,
        "pilot_activated": False,
        "customer_contact_authorized": False,
        "billing_authorized": False,
        "provisioning_authorized": False,
        "deploy_authorized": False,
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
        "schema": "ATLASQUANT_AION_B2B_PILOT_ACTIVATION_WRITER_VERIFICATION_V1",
        "state": "ACTIVATION_CHECKPOINT_WRITER_AUTHORITY_ATTESTED",
        "blockers": [],
        "pilot_id": "pilot-001",
        "receipt_digest": "sha256:" + "4" * 64,
        "after_checkpoint_digest": "sha256:" + "3" * 64,
        "activation_record_digest": "sha256:" + "c" * 64,
        "event_id": "aion-b2b-pilot-activation-0123456789abcdef",
        "writer_ref": "checkpoint-writer:activation-path",
        "writer_key_id": "activation-writer-key",
        "writer_key_version": 1,
        "writer_public_key_fingerprint": "sha256:" + "6" * 64,
        "writer_request_digest": "sha256:" + "7" * 64,
        "writer_identity_verified": True,
        "writer_authority_verified": True,
        "receipt_binding_verified": True,
        "nonce_registered": True,
        "pilot_activation_authorized": False,
        "pilot_activated": False,
        "checkpoint_write_performed": False,
        "customer_contact_authorized": False,
        "billing_authorized": False,
        "provisioning_authorized": False,
        "deploy_authorized": False,
        "production_mutation_authorized": False,
        "external_action_executed": False,
        "network_called": False,
        "executes_action": False,
    }
    row.update(overrides)
    return row


def original_preflight(**overrides):
    row = {
        "schema": "ATLASQUANT_AION_B2B_PILOT_ACTIVATION_PREFLIGHT_V1",
        "state": "READY_FOR_ACTIVATION_CEREMONY",
        "scope": dict(SCOPE),
        "candidate_id": "candidate-001",
        "proposal_id": "proposal-001",
        "pilot_id": "pilot-001",
        "blockers": [],
        "environment_digest": "sha256:" + "e" * 64,
        "preflight_digest": "sha256:" + "f" * 64,
        "activation_ceremony_eligible": True,
        "activation_request_issued": False,
        "owner_activation_signature_required": True,
        "owner_activation_signature_verified": False,
        "pilot_activation_authorized": False,
        "pilot_activated": False,
        "customer_contact_authorized": False,
        "contract_signature_authorized": False,
        "billing_authorized": False,
        "spend_authorized": False,
        "provisioning_authorized": False,
        "deploy_authorized": False,
        "crm_write_authorized": False,
        "provider_called": False,
        "production_mutation_authorized": False,
        "external_action_executed": False,
        "network_called": False,
        "executes_action": False,
    }
    row.update(overrides)
    return row


def environment(**overrides):
    row = {
        "schema": "ATLASQUANT_AION_B2B_PILOT_ACTIVATION_EXECUTION_ENVIRONMENT_V1",
        "state": "VERIFIED",
        **SCOPE,
        "pilot_id": "pilot-001",
        "execution_mode": "CONTROLLED_PILOT",
        "checked_at": "2026-10-05T19:20:00Z",
        "activation_slot_reserved": True,
        "production_scope_expansion_allowed": False,
        "tenant_isolation_ready": True,
        "secrets_vault_ready": True,
        "rollback_ready": True,
        "monitoring_ready": True,
        "audit_receipts_ready": True,
        "integration_health_ready": True,
        "kill_switch_ready": True,
        "idempotency_key_ready": True,
        "single_pilot_lock_ready": True,
        "dry_run_validation_pass": True,
        "security_incident": False,
        "privacy_incident": False,
        "scope_breach": False,
        "provider_degraded": False,
        "rollback_degraded": False,
        "reserved_capacity_units": 10,
        "available_capacity_units": 100,
        "planned_monthly_infra_brl": 150.0,
        "evidence_refs": [
            "exec:tenant",
            "exec:vault",
            "exec:rollback",
            "exec:monitoring",
            "exec:idempotency",
            "exec:lock",
        ],
    }
    row.update(overrides)
    return row


def run(**overrides):
    args = {
        "trusted_scope": SCOPE,
        "activation_persistence_attestation": persistence(),
        "activation_writer_attestation": writer(),
        "activation_preflight": original_preflight(),
        "execution_environment": environment(),
        "now_ts": "2026-10-05T19:21:00Z",
    }
    args.update(overrides)
    return evaluate_activation_execution_preflight(**args)


class AionB2BPilotActivationExecutionPreflightTests(unittest.TestCase):
    def test_valid_chain_is_ready_for_execution_ceremony_only(self):
        out = run()
        self.assertEqual(
            out["state"],
            "READY_FOR_ACTIVATION_EXECUTION_CEREMONY",
        )
        self.assertFalse(out["blockers"])
        self.assertTrue(out["activation_execution_ceremony_eligible"])
        self.assertTrue(out["human_execution_confirmation_required"])
        self.assertFalse(out["execution_request_issued"])
        self.assertFalse(out["owner_execution_signature_verified"])
        self.assertFalse(out["activation_command_generated"])
        self.assertFalse(out["activation_command_executed"])
        self.assertFalse(out["pilot_activation_authorized"])
        self.assertFalse(out["pilot_activated"])
        self.assertFalse(out["executes_action"])

    def test_persisted_denial_blocks(self):
        denied = persistence(
            state="ACTIVATION_RECORD_PERSISTENCE_ATTESTED_DENY",
            decision="DENY_PILOT_ACTIVATION",
            activation_authorization_intent=False,
            activation_denial_intent=True,
            eligible_for_activation_execution_preflight=False,
        )
        out = run(activation_persistence_attestation=denied)
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("PILOT_ACTIVATION_DENIED", out["blockers"])

    def test_second_writer_attestation_is_mandatory(self):
        out = run(
            activation_writer_attestation=writer(
                writer_authority_verified=False
            )
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "ACTIVATION_WRITER_AUTHORITY_NOT_VERIFIED",
            out["blockers"],
        )

    def test_second_writer_receipt_digest_must_match(self):
        out = run(
            activation_writer_attestation=writer(
                receipt_digest="sha256:" + "9" * 64
            )
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "ACTIVATION_WRITER_RECEIPT_DIGEST_MISMATCH",
            out["blockers"],
        )

    def test_second_writer_checkpoint_digest_must_match(self):
        out = run(
            activation_writer_attestation=writer(
                after_checkpoint_digest="sha256:" + "9" * 64
            )
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "ACTIVATION_WRITER_CHECKPOINT_DIGEST_MISMATCH",
            out["blockers"],
        )

    def test_original_preflight_digest_must_match_persisted_record(self):
        out = run(
            activation_preflight=original_preflight(
                preflight_digest="sha256:" + "9" * 64
            )
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "ORIGINAL_ACTIVATION_PREFLIGHT_DIGEST_MISMATCH",
            out["blockers"],
        )

    def test_cross_tenant_execution_environment_blocks(self):
        env = environment()
        env["tenant_id"] = "other-tenant"
        out = run(execution_environment=env)
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "EXECUTION_ENVIRONMENT_SCOPE_MISMATCH",
            out["blockers"],
        )

    def test_execution_environment_must_be_fresh(self):
        out = run(
            execution_environment=environment(
                checked_at="2026-10-05T19:18:00Z"
            )
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("EXECUTION_ENVIRONMENT_STALE", out["blockers"])

    def test_execution_requires_reserved_slot(self):
        out = run(
            execution_environment=environment(
                activation_slot_reserved=False
            )
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("ACTIVATION_SLOT_NOT_RESERVED", out["blockers"])

    def test_execution_forbids_scope_expansion(self):
        out = run(
            execution_environment=environment(
                production_scope_expansion_allowed=True
            )
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "PRODUCTION_SCOPE_EXPANSION_FORBIDDEN",
            out["blockers"],
        )

    def test_all_execution_safety_capabilities_are_required(self):
        keys = (
            "tenant_isolation_ready",
            "secrets_vault_ready",
            "rollback_ready",
            "monitoring_ready",
            "audit_receipts_ready",
            "integration_health_ready",
            "kill_switch_ready",
            "idempotency_key_ready",
            "single_pilot_lock_ready",
            "dry_run_validation_pass",
        )
        for key in keys:
            with self.subTest(key=key):
                env = environment()
                env[key] = False
                out = run(execution_environment=env)
                self.assertEqual(out["state"], "BLOCKED")

    def test_incident_or_degradation_blocks(self):
        for key in (
            "security_incident",
            "privacy_incident",
            "scope_breach",
            "provider_degraded",
            "rollback_degraded",
        ):
            with self.subTest(key=key):
                env = environment()
                env[key] = True
                out = run(execution_environment=env)
                self.assertEqual(out["state"], "BLOCKED")

    def test_capacity_must_fit(self):
        out = run(
            execution_environment=environment(
                reserved_capacity_units=101,
                available_capacity_units=100,
            )
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("EXECUTION_CAPACITY_INSUFFICIENT", out["blockers"])

    def test_infra_cap_is_enforced(self):
        out = run(
            execution_environment=environment(
                planned_monthly_infra_brl=200.01
            )
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "EXECUTION_MONTHLY_INFRA_CAP_EXCEEDED",
            out["blockers"],
        )

    def test_execution_evidence_requires_six_refs(self):
        out = run(
            execution_environment=environment(
                evidence_refs=["1", "2", "3", "4", "5"]
            )
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "EXECUTION_ENVIRONMENT_EVIDENCE_INSUFFICIENT",
            out["blockers"],
        )

    def test_preflight_never_generates_or_executes_activation_command(self):
        out = run()
        for key in (
            "execution_request_issued",
            "owner_execution_signature_verified",
            "activation_command_generated",
            "activation_command_executed",
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
        self.assertEqual(
            first["execution_preflight_digest"],
            second["execution_preflight_digest"],
        )
        self.assertEqual(
            first["execution_environment_digest"],
            second["execution_environment_digest"],
        )


if __name__ == "__main__":
    unittest.main()
