from __future__ import annotations

import hashlib
import json
import unittest

from atlasquant_aion_b2b_owner_renewal_persistence_plan import (
    NAMESPACE,
    build_owner_renewal_persistence_plan,
)
from atlasquant_aion_b2b_owner_renewal_signature import RESULT_SCHEMA
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


def verified(**overrides):
    record = {
        "schema": RESULT_SCHEMA,
        "requested_choice": "RENEW_AS_IS_REVIEW",
        "owner_id": "owner-a",
        "tenant_id": "tenant-a",
        "workspace_id": "workspace-a",
        "customer_id": "customer-a",
        "pilot_id": "pilot-a",
        "package": "PROFISSIONAL",
        "review_type": "RENEWAL_REVIEW",
        "owner_review_packet_digest": "sha256:review",
        "cycle_evidence_digest": "sha256:cycle",
        "contract_digest": "sha256:contract",
        "value_bound_conversion_digest": "sha256:value-bound",
        "decision_request_digest": "sha256:decision-request",
        "signature_request_digest": "sha256:signature-request",
        "owner_signature_verified": True,
        "owner_decision_verified": True,
        "owner_decision_recorded": False,
        "decision_persisted": False,
    }
    row = {
        "schema": RESULT_SCHEMA,
        "state": "OWNER_RENEWAL_DECISION_VERIFIED_PENDING_PERSISTENCE",
        "blockers": [],
        "owner_identity_signature_verified": True,
        "owner_decision_signature_verified": True,
        "owner_decision_verified": True,
        "owner_decision_recorded": False,
        "decision_persisted": False,
        "requested_choice": "RENEW_AS_IS_REVIEW",
        "decision_record": record,
        "decision_record_digest": digest(record),
        "requires_decision_persistence": True,
        "signature_capture_performed": False,
        "generic_chat_instruction_accepted_as_decision": False,
        "renewal_authorized": False,
        "expansion_authorized": False,
        "pause_authorized": False,
        "termination_authorized": False,
        "billing_authorized": False,
        "pricing_change_authorized": False,
        "quota_change_authorized": False,
        "role_change_authorized": False,
        "integration_change_authorized": False,
        "customer_contact_authorized": False,
        "provisioning_authorized": False,
        "deploy_authorized": False,
        "provider_called": False,
        "crm_write_authorized": False,
        "production_mutation_authorized": False,
        "external_action_executed": False,
        "executes_action": False,
    }
    row.update(overrides)
    return row


def checkpoint(revision=0):
    return new_checkpoint_master(
        {"status": "ready"},
        base_revision=revision,
        created_at="2026-10-05T21:30:00Z",
        source_refs=["test:owner-renewal-decision"],
    )


class OwnerRenewalPersistencePlanTests(unittest.TestCase):
    def test_verified_decision_prepares_patch_only(self):
        out = build_owner_renewal_persistence_plan(
            verified(),
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
        self.assertEqual(
            record["requested_choice"],
            "RENEW_AS_IS_REVIEW",
        )
        self.assertTrue(record["owner_decision_verified"])
        self.assertFalse(record["owner_decision_recorded"])
        self.assertFalse(record["decision_persisted"])
        self.assertFalse(record["business_action_authorized"])
        self.assertFalse(out["checkpoint_saved"])
        self.assertFalse(out["automatic_checkpoint_write"])
        self.assertFalse(out["renewal_authorized"])
        self.assertFalse(out["executes_action"])

    def test_checkpoint_revision_and_state_digest_are_pinned(self):
        cp = checkpoint(revision=7)
        out = build_owner_renewal_persistence_plan(
            verified(),
            checkpoint_master=cp,
        )
        self.assertEqual(out["checkpoint_revision"], 7)
        self.assertEqual(
            out["patch_candidate"]["expected_revision"],
            7,
        )
        self.assertEqual(
            out["patch_candidate"]["expected_state_digest"],
            out["checkpoint_state_digest"],
        )

    def test_event_id_and_patch_digest_are_deterministic(self):
        first = build_owner_renewal_persistence_plan(
            verified(),
            checkpoint_master=checkpoint(),
        )
        second = build_owner_renewal_persistence_plan(
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

    def test_tampered_record_digest_blocks(self):
        row = verified()
        row["decision_record_digest"] = "sha256:tampered"
        out = build_owner_renewal_persistence_plan(
            row,
            checkpoint_master=checkpoint(),
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "OWNER_RENEWAL_RECORD_DIGEST_MISMATCH",
            out["blockers"],
        )
        self.assertIsNone(out["patch_candidate"])

    def test_record_choice_mismatch_blocks(self):
        row = verified()
        row["decision_record"] = dict(row["decision_record"])
        row["decision_record"]["requested_choice"] = "NON_RENEWAL_REVIEW"
        row["decision_record_digest"] = digest(row["decision_record"])
        out = build_owner_renewal_persistence_plan(
            row,
            checkpoint_master=checkpoint(),
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "OWNER_RENEWAL_RECORD_CHOICE_MISMATCH",
            out["blockers"],
        )

    def test_already_persisted_decision_blocks(self):
        out = build_owner_renewal_persistence_plan(
            verified(decision_persisted=True),
            checkpoint_master=checkpoint(),
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "OWNER_RENEWAL_DECISION_ALREADY_PERSISTED",
            out["blockers"],
        )

    def test_authority_flip_blocks(self):
        out = build_owner_renewal_persistence_plan(
            verified(renewal_authorized=True),
            checkpoint_master=checkpoint(),
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "OWNER_RENEWAL_DECISION_UNSAFE_FIELD:renewal_authorized",
            out["blockers"],
        )

    def test_invalid_checkpoint_blocks(self):
        out = build_owner_renewal_persistence_plan(
            verified(),
            checkpoint_master={"schema": "bad"},
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("CHECKPOINT_MASTER_INVALID", out["blockers"])

    def test_non_renewal_choice_still_grants_no_termination_authority(self):
        row = verified(requested_choice="NON_RENEWAL_REVIEW")
        row["decision_record"] = dict(row["decision_record"])
        row["decision_record"]["requested_choice"] = "NON_RENEWAL_REVIEW"
        row["decision_record_digest"] = digest(row["decision_record"])
        out = build_owner_renewal_persistence_plan(
            row,
            checkpoint_master=checkpoint(),
        )
        self.assertEqual(
            out["state"],
            "READY_FOR_EXPLICIT_CHECKPOINT_PERSISTENCE",
        )
        self.assertFalse(out["termination_authorized"])
        self.assertFalse(out["customer_contact_authorized"])

    def test_output_never_claims_persistence_or_execution(self):
        out = build_owner_renewal_persistence_plan(
            verified(),
            checkpoint_master=checkpoint(),
        )
        for key in (
            "owner_decision_recorded",
            "decision_persisted",
            "checkpoint_saved",
            "automatic_checkpoint_write",
            "renewal_authorized",
            "expansion_authorized",
            "pause_authorized",
            "termination_authorized",
            "billing_authorized",
            "pricing_change_authorized",
            "quota_change_authorized",
            "role_change_authorized",
            "integration_change_authorized",
            "customer_contact_authorized",
            "provisioning_authorized",
            "deploy_authorized",
            "provider_called",
            "crm_write_authorized",
            "production_mutation_authorized",
            "external_action_executed",
            "executes_action",
        ):
            self.assertFalse(out[key], key)


if __name__ == "__main__":
    unittest.main()
