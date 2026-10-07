from __future__ import annotations

import hashlib
import json
import unittest

from atlasquant_aion_b2b_pilot_owner_decision_persistence_plan import (
    NAMESPACE,
    build_pilot_owner_decision_persistence_plan,
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


def verified(decision="APPROVE_PILOT", **overrides):
    approved = decision == "APPROVE_PILOT"
    denied = decision == "DENY_PILOT"
    record = {
        "schema": "ATLASQUANT_AION_B2B_PILOT_OWNER_DECISION_VERIFICATION_V1",
        "decision": decision,
        "owner_id": "HUMAN_OWNER",
        "tenant_id": "atlasquant-owner",
        "workspace_id": "business",
        "candidate_id": "candidate-001",
        "proposal_id": "proposal-001",
        "pilot_id": "pilot-001",
        "packet_digest": "sha256:" + "a" * 64,
        "decision_request_digest": "sha256:" + "b" * 64,
        "owner_decision_verified": True,
        "owner_decision_recorded": False,
        "decision_record_persisted": False,
        "pilot_approved": approved,
        "pilot_denied": denied,
        "pilot_activation_authorized": False,
        "pilot_activated": False,
    }
    row = {
        "schema": "ATLASQUANT_AION_B2B_PILOT_OWNER_DECISION_VERIFICATION_V1",
        "state": (
            "OWNER_DECISION_VERIFIED_APPROVE_PENDING_PERSISTENCE"
            if approved
            else "OWNER_DECISION_VERIFIED_DENY_PENDING_PERSISTENCE"
        ),
        "blockers": [],
        "owner_identity_signature_verified": True,
        "owner_decision_signature_verified": True,
        "owner_decision_verified": True,
        "owner_decision": decision,
        "owner_decision_recorded": False,
        "decision_record_persisted": False,
        "decision_record": record,
        "decision_record_digest": digest(record),
        "pilot_approved": approved,
        "pilot_denied": denied,
        "pilot_activation_authorized": False,
        "pilot_activated": False,
        "requires_decision_record_persistence": True,
        "eligible_for_activation_ceremony_after_persistence": approved,
        "signature_capture_performed": False,
        "customer_contact_authorized": False,
        "contract_signature_authorized": False,
        "billing_authorized": False,
        "spend_authorized": False,
        "deploy_authorized": False,
        "crm_write_authorized": False,
        "production_mutation_authorized": False,
        "external_action_executed": False,
        "network_called": False,
        "executes_action": False,
        "generic_chat_instruction_accepted_as_decision": False,
    }
    row.update(overrides)
    return row


def checkpoint(revision=0):
    return new_checkpoint_master(
        {"status": "ready"},
        base_revision=revision,
        created_at="2026-10-05T18:00:00Z",
        source_refs=["test:pilot-owner-decision"],
    )


class AionB2BPilotOwnerDecisionPersistencePlanTests(unittest.TestCase):
    def test_approve_prepares_patch_candidate_without_persisting(self):
        out = build_pilot_owner_decision_persistence_plan(
            verified("APPROVE_PILOT"),
            checkpoint_master=checkpoint(),
        )
        self.assertEqual(
            out["state"],
            "READY_FOR_EXPLICIT_CHECKPOINT_PERSISTENCE",
        )
        self.assertFalse(out["blockers"])
        patch = out["patch_candidate"]
        self.assertEqual(patch["state"], "PATCH_CANDIDATE")
        self.assertEqual(patch["expected_revision"], 0)
        self.assertIn(NAMESPACE, patch["patch"])
        record = patch["patch"][NAMESPACE]
        self.assertEqual(record["decision"], "APPROVE_PILOT")
        self.assertTrue(record["pilot_approved"])
        self.assertFalse(record["pilot_activation_authorized"])
        self.assertFalse(record["decision_record_persisted"])
        self.assertTrue(out["requires_explicit_checkpoint_save"])
        self.assertTrue(out["requires_persistence_attestation"])
        self.assertFalse(out["checkpoint_saved"])
        self.assertFalse(out["automatic_checkpoint_write"])
        self.assertFalse(out["executes_action"])

    def test_deny_patch_remains_activation_ineligible(self):
        out = build_pilot_owner_decision_persistence_plan(
            verified("DENY_PILOT"),
            checkpoint_master=checkpoint(),
        )
        self.assertEqual(
            out["state"],
            "READY_FOR_EXPLICIT_CHECKPOINT_PERSISTENCE",
        )
        record = out["patch_candidate"]["patch"][NAMESPACE]
        self.assertTrue(record["pilot_denied"])
        self.assertFalse(record["pilot_approved"])
        self.assertFalse(
            record["eligible_for_activation_ceremony_after_persistence"]
        )
        self.assertFalse(record["pilot_activation_authorized"])
        self.assertFalse(out["pilot_activation_authorized"])

    def test_expected_revision_comes_from_current_checkpoint(self):
        out = build_pilot_owner_decision_persistence_plan(
            verified(),
            checkpoint_master=checkpoint(revision=7),
        )
        self.assertEqual(
            out["patch_candidate"]["expected_revision"],
            7,
        )

    def test_event_id_and_patch_digest_are_deterministic(self):
        first = build_pilot_owner_decision_persistence_plan(
            verified(),
            checkpoint_master=checkpoint(),
        )
        second = build_pilot_owner_decision_persistence_plan(
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

    def test_tampered_decision_record_digest_blocks(self):
        row = verified()
        row["decision_record_digest"] = "sha256:" + "0" * 64
        out = build_pilot_owner_decision_persistence_plan(
            row,
            checkpoint_master=checkpoint(),
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "PILOT_OWNER_DECISION_RECORD_DIGEST_MISMATCH",
            out["blockers"],
        )
        self.assertIsNone(out["patch_candidate"])

    def test_choice_and_boolean_flags_must_be_consistent(self):
        row = verified("APPROVE_PILOT", pilot_denied=True)
        out = build_pilot_owner_decision_persistence_plan(
            row,
            checkpoint_master=checkpoint(),
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "PILOT_OWNER_DECISION_APPROVE_FLAGS_INVALID",
            out["blockers"],
        )

    def test_activation_flag_flip_blocks(self):
        row = verified(pilot_activation_authorized=True)
        out = build_pilot_owner_decision_persistence_plan(
            row,
            checkpoint_master=checkpoint(),
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "PILOT_OWNER_DECISION_ACTIVATION_UNSAFE",
            out["blockers"],
        )

    def test_external_authority_flip_blocks(self):
        for key in (
            "customer_contact_authorized",
            "contract_signature_authorized",
            "billing_authorized",
            "spend_authorized",
            "deploy_authorized",
            "crm_write_authorized",
            "production_mutation_authorized",
            "external_action_executed",
            "network_called",
            "executes_action",
        ):
            with self.subTest(key=key):
                row = verified()
                row[key] = True
                out = build_pilot_owner_decision_persistence_plan(
                    row,
                    checkpoint_master=checkpoint(),
                )
                self.assertEqual(out["state"], "BLOCKED")

    def test_already_persisted_decision_blocks(self):
        row = verified(decision_record_persisted=True)
        out = build_pilot_owner_decision_persistence_plan(
            row,
            checkpoint_master=checkpoint(),
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "PILOT_OWNER_DECISION_ALREADY_PERSISTED",
            out["blockers"],
        )

    def test_invalid_checkpoint_blocks(self):
        out = build_pilot_owner_decision_persistence_plan(
            verified(),
            checkpoint_master={"schema": "bad"},
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("CHECKPOINT_MASTER_INVALID", out["blockers"])

    def test_output_never_claims_persistence_or_activation(self):
        out = build_pilot_owner_decision_persistence_plan(
            verified(),
            checkpoint_master=checkpoint(),
        )
        for key in (
            "decision_record_persisted",
            "checkpoint_saved",
            "automatic_checkpoint_write",
            "pilot_activation_authorized",
            "pilot_activated",
            "external_action_executed",
            "network_called",
            "executes_action",
        ):
            self.assertFalse(out[key], key)


if __name__ == "__main__":
    unittest.main()
