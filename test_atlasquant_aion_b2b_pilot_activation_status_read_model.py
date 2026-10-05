from __future__ import annotations

import unittest

from atlasquant_aion_b2b_pilot_activation_status_read_model import (
    build_pilot_activation_status_read_model,
)

SCOPE = {
    "owner_id": "HUMAN_OWNER",
    "tenant_id": "atlasquant-owner",
    "workspace_id": "business",
}


def preflight(**overrides):
    row = {
        "schema": "ATLASQUANT_AION_B2B_PILOT_ACTIVATION_EXECUTION_PREFLIGHT_V1",
        "state": "READY_FOR_ACTIVATION_EXECUTION_CEREMONY",
        "scope": dict(SCOPE),
        "candidate_id": "candidate-secret-001",
        "proposal_id": "proposal-001",
        "pilot_id": "pilot-001",
        "blockers": [],
        "execution_environment_digest": "sha256:" + "1" * 64,
        "execution_preflight_digest": "sha256:" + "2" * 64,
        "activation_execution_ceremony_eligible": True,
        "human_execution_confirmation_required": True,
        "execution_request_issued": False,
        "owner_execution_signature_verified": False,
        "activation_command_generated": False,
        "activation_command_executed": False,
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


class AionB2BPilotActivationStatusReadModelTests(unittest.TestCase):
    def test_ready_preflight_becomes_read_only_governance_summary(self):
        out = build_pilot_activation_status_read_model(
            preflight(),
            trusted_scope=SCOPE,
        )
        self.assertEqual(out["state"], "READY")
        self.assertEqual(out["pilot_id"], "pilot-001")
        self.assertEqual(
            out["governance_state"],
            "WAITING_HUMAN_EXECUTION_CONFIRMATION",
        )
        self.assertEqual(out["activation_writer_state"], "ATTESTED")
        self.assertEqual(out["execution_environment_state"], "VERIFIED")
        self.assertTrue(out["human_execution_confirmation_required"])
        self.assertTrue(out["read_only"])
        self.assertFalse(out["activation_control_exposed"])
        self.assertFalse(out["activation_command_exposed"])
        self.assertFalse(out["executes_action"])

    def test_candidate_identity_and_digests_are_not_exposed(self):
        out = build_pilot_activation_status_read_model(
            preflight(),
            trusted_scope=SCOPE,
        )
        flat = str(out)
        self.assertNotIn("candidate-secret-001", flat)
        self.assertNotIn("execution_preflight_digest", out)
        self.assertNotIn("execution_environment_digest", out)
        self.assertFalse(out["candidate_identity_exposed"])
        self.assertFalse(out["cryptographic_digest_exposed"])
        self.assertFalse(out["writer_identity_exposed"])
        self.assertFalse(out["raw_evidence_exposed"])

    def test_cross_tenant_preflight_blocks(self):
        bad = preflight()
        bad["scope"] = {
            "owner_id": "HUMAN_OWNER",
            "tenant_id": "other-tenant",
            "workspace_id": "business",
        }
        out = build_pilot_activation_status_read_model(
            bad,
            trusted_scope=SCOPE,
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "ACTIVATION_EXECUTION_PREFLIGHT_SCOPE_MISMATCH",
            out["blockers"],
        )

    def test_non_ready_preflight_blocks(self):
        out = build_pilot_activation_status_read_model(
            preflight(state="BLOCKED"),
            trusted_scope=SCOPE,
        )
        self.assertEqual(out["state"], "BLOCKED")

    def test_any_authority_or_execution_flip_blocks(self):
        for key in (
            "execution_request_issued",
            "owner_execution_signature_verified",
            "activation_command_generated",
            "activation_command_executed",
            "pilot_activation_authorized",
            "pilot_activated",
            "customer_contact_authorized",
            "billing_authorized",
            "provisioning_authorized",
            "deploy_authorized",
            "crm_write_authorized",
            "provider_called",
            "production_mutation_authorized",
            "external_action_executed",
            "network_called",
            "executes_action",
        ):
            with self.subTest(key=key):
                bad = preflight()
                bad[key] = True
                out = build_pilot_activation_status_read_model(
                    bad,
                    trusted_scope=SCOPE,
                )
                self.assertEqual(out["state"], "BLOCKED")

    def test_blocked_model_never_grants_authority(self):
        out = build_pilot_activation_status_read_model(
            {},
            trusted_scope=SCOPE,
        )
        for key in (
            "activation_control_exposed",
            "activation_command_exposed",
            "raw_evidence_exposed",
            "candidate_identity_exposed",
            "cryptographic_digest_exposed",
            "writer_identity_exposed",
            "grants_authority",
            "executes_action",
        ):
            self.assertFalse(out[key], key)


if __name__ == "__main__":
    unittest.main()
