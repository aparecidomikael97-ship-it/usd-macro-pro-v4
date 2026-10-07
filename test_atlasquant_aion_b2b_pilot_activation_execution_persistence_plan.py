from __future__ import annotations

import hashlib
import json
import unittest

from atlasquant_aion_b2b_pilot_activation_execution_persistence_plan import (
    NAMESPACE,
    build_activation_execution_persistence_plan,
)
from atlasquant_aion_checkpoint_master import new_checkpoint_master


def digest(value):
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
        default=str,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def verified(decision="AUTHORIZE_ACTIVATION_EXECUTION", **overrides):
    authorize = decision == "AUTHORIZE_ACTIVATION_EXECUTION"
    deny = decision == "DENY_ACTIVATION_EXECUTION"
    record = {
        "schema": "ATLASQUANT_AION_B2B_PILOT_ACTIVATION_EXECUTION_VERIFICATION_V1",
        "decision": decision,
        "owner_id": "HUMAN_OWNER",
        "tenant_id": "atlasquant-owner",
        "workspace_id": "business",
        "candidate_id": "candidate-001",
        "proposal_id": "proposal-001",
        "pilot_id": "pilot-001",
        "execution_environment_digest": "sha256:" + "e" * 64,
        "execution_preflight_digest": "sha256:" + "f" * 64,
        "execution_request_digest": "sha256:" + "a" * 64,
        "execution_decision_verified": True,
        "execution_record_persisted": False,
        "activation_command_generated": False,
        "activation_command_executed": False,
        "pilot_activation_authorized": False,
        "pilot_activated": False,
        "execution_authorization_intent": authorize,
        "execution_denial_intent": deny,
    }
    row = {
        "schema": "ATLASQUANT_AION_B2B_PILOT_ACTIVATION_EXECUTION_VERIFICATION_V1",
        "state": (
            "ACTIVATION_EXECUTION_AUTHORIZATION_VERIFIED_PENDING_PERSISTENCE"
            if authorize
            else "ACTIVATION_EXECUTION_DENIAL_VERIFIED_PENDING_PERSISTENCE"
        ),
        "blockers": [],
        "owner_execution_identity_verified": True,
        "owner_execution_signature_verified": True,
        "execution_decision_verified": True,
        "execution_decision": decision,
        "execution_record": record,
        "execution_record_digest": digest(record),
        "execution_record_persisted": False,
        "execution_authorization_intent": authorize,
        "execution_denial_intent": deny,
        "requires_execution_record_persistence": True,
        "eligible_for_activation_command_planning_after_persistence": authorize,
        "activation_command_generated": False,
        "activation_command_executed": False,
        "pilot_activation_authorized": False,
        "pilot_activated": False,
        "customer_contact_authorized": False,
        "billing_authorized": False,
        "provisioning_authorized": False,
        "deploy_authorized": False,
        "production_mutation_authorized": False,
        "external_action_executed": False,
        "network_called": False,
        "executes_action": False,
        "generic_chat_instruction_accepted_as_execution": False,
    }
    row.update(overrides)
    return row


def checkpoint(revision=0):
    return new_checkpoint_master(
        {"status": "ready"},
        base_revision=revision,
        created_at="2026-10-05T19:40:00Z",
        source_refs=["test:pilot-execution"],
    )


class AionB2BPilotActivationExecutionPersistencePlanTests(unittest.TestCase):
    def test_authorize_prepares_patch_candidate_without_persisting_or_command(self):
        out = build_activation_execution_persistence_plan(
            verified(),
            checkpoint_master=checkpoint(),
        )
        self.assertEqual(
            out["state"],
            "READY_FOR_EXPLICIT_EXECUTION_RECORD_PERSISTENCE",
        )
        self.assertFalse(out["blockers"])
        patch = out["patch_candidate"]
        self.assertEqual(patch["state"], "PATCH_CANDIDATE")
        self.assertEqual(patch["expected_revision"], 0)
        self.assertIn(NAMESPACE, patch["patch"])
        record = patch["patch"][NAMESPACE]
        self.assertEqual(
            record["decision"],
            "AUTHORIZE_ACTIVATION_EXECUTION",
        )
        self.assertTrue(record["execution_authorization_intent"])
        self.assertFalse(record["execution_record_persisted"])
        self.assertFalse(record["activation_command_generated"])
        self.assertFalse(record["activation_command_executed"])
        self.assertFalse(record["pilot_activation_authorized"])
        self.assertFalse(record["pilot_activated"])
        self.assertTrue(
            record[
                "eligible_for_activation_command_planning_after_persistence"
            ]
        )
        self.assertTrue(out["requires_explicit_checkpoint_save"])
        self.assertTrue(out["requires_persistence_attestation"])
        self.assertFalse(out["checkpoint_saved"])
        self.assertFalse(out["automatic_checkpoint_write"])
        self.assertFalse(out["executes_action"])

    def test_deny_patch_is_not_command_planning_eligible(self):
        out = build_activation_execution_persistence_plan(
            verified("DENY_ACTIVATION_EXECUTION"),
            checkpoint_master=checkpoint(),
        )
        self.assertEqual(
            out["state"],
            "READY_FOR_EXPLICIT_EXECUTION_RECORD_PERSISTENCE",
        )
        record = out["patch_candidate"]["patch"][NAMESPACE]
        self.assertTrue(record["execution_denial_intent"])
        self.assertFalse(record["execution_authorization_intent"])
        self.assertFalse(
            record[
                "eligible_for_activation_command_planning_after_persistence"
            ]
        )
        self.assertFalse(record["activation_command_generated"])

    def test_expected_revision_comes_from_checkpoint(self):
        out = build_activation_execution_persistence_plan(
            verified(),
            checkpoint_master=checkpoint(revision=12),
        )
        self.assertEqual(out["patch_candidate"]["expected_revision"], 12)

    def test_event_id_and_patch_digest_are_deterministic(self):
        first = build_activation_execution_persistence_plan(
            verified(),
            checkpoint_master=checkpoint(),
        )
        second = build_activation_execution_persistence_plan(
            verified(),
            checkpoint_master=checkpoint(),
        )
        self.assertEqual(
            first["patch_candidate"]["recommended_event_id"],
            second["patch_candidate"]["recommended_event_id"],
        )
        self.assertEqual(
            first["patch_candidate"]["patch_digest"],
            second["patch_candidate"]["patch_digest"],
        )

    def test_tampered_execution_record_digest_blocks(self):
        row = verified()
        row["execution_record_digest"] = "sha256:" + "0" * 64
        out = build_activation_execution_persistence_plan(
            row,
            checkpoint_master=checkpoint(),
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "ACTIVATION_EXECUTION_RECORD_DIGEST_MISMATCH",
            out["blockers"],
        )
        self.assertIsNone(out["patch_candidate"])

    def test_authorize_flags_must_match_choice(self):
        row = verified(
            "AUTHORIZE_ACTIVATION_EXECUTION",
            execution_denial_intent=True,
        )
        out = build_activation_execution_persistence_plan(
            row,
            checkpoint_master=checkpoint(),
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "ACTIVATION_EXECUTION_AUTHORIZE_FLAGS_INVALID",
            out["blockers"],
        )

    def test_pre_generated_or_executed_command_blocks(self):
        for key in (
            "activation_command_generated",
            "activation_command_executed",
        ):
            with self.subTest(key=key):
                row = verified()
                row[key] = True
                out = build_activation_execution_persistence_plan(
                    row,
                    checkpoint_master=checkpoint(),
                )
                self.assertEqual(out["state"], "BLOCKED")

    def test_external_authority_flip_blocks(self):
        for key in (
            "customer_contact_authorized",
            "billing_authorized",
            "provisioning_authorized",
            "deploy_authorized",
            "production_mutation_authorized",
            "external_action_executed",
            "network_called",
            "executes_action",
        ):
            with self.subTest(key=key):
                row = verified()
                row[key] = True
                out = build_activation_execution_persistence_plan(
                    row,
                    checkpoint_master=checkpoint(),
                )
                self.assertEqual(out["state"], "BLOCKED")

    def test_already_persisted_record_blocks(self):
        row = verified(execution_record_persisted=True)
        out = build_activation_execution_persistence_plan(
            row,
            checkpoint_master=checkpoint(),
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "ACTIVATION_EXECUTION_RECORD_ALREADY_PERSISTED",
            out["blockers"],
        )

    def test_invalid_checkpoint_blocks(self):
        out = build_activation_execution_persistence_plan(
            verified(),
            checkpoint_master={"schema": "bad"},
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("CHECKPOINT_MASTER_INVALID", out["blockers"])

    def test_output_never_claims_persistence_command_or_activation(self):
        out = build_activation_execution_persistence_plan(
            verified(),
            checkpoint_master=checkpoint(),
        )
        for key in (
            "execution_record_persisted",
            "checkpoint_saved",
            "automatic_checkpoint_write",
            "activation_command_generated",
            "activation_command_executed",
            "pilot_activation_authorized",
            "pilot_activated",
            "external_action_executed",
            "network_called",
            "executes_action",
        ):
            self.assertFalse(out[key], key)


if __name__ == "__main__":
    unittest.main()
