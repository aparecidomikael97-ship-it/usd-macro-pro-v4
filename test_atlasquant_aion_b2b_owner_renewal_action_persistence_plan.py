from __future__ import annotations

import hashlib
import json
import unittest

from atlasquant_aion_b2b_owner_renewal_action_ceremony import RESULT_SCHEMA
from atlasquant_aion_b2b_owner_renewal_action_persistence_plan import (
    NAMESPACE,
    build_owner_renewal_action_persistence_plan,
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


def h(char):
    return "sha256:" + char * 64


def verified(
    decision="AUTHORIZE_BUSINESS_ACTION",
    choice="RENEW_AS_IS_REVIEW",
    family="RENEWAL",
    **overrides,
):
    authorize = decision == "AUTHORIZE_BUSINESS_ACTION"
    state = (
        "OWNER_BUSINESS_ACTION_DECISION_VERIFIED_AUTHORIZE_PENDING_PERSISTENCE"
        if authorize
        else "OWNER_BUSINESS_ACTION_DECISION_VERIFIED_DENY_PENDING_PERSISTENCE"
    )
    record = {
        "schema": RESULT_SCHEMA,
        "state": state,
        "authorization_decision": decision,
        "owner_id": "owner-a",
        "tenant_id": "tenant-a",
        "workspace_id": "workspace-a",
        "customer_id": "customer-a",
        "pilot_id": "pilot-a",
        "package": "PROFISSIONAL",
        "review_type": "RENEWAL_REVIEW",
        "requested_choice": choice,
        "action_family": family,
        "owner_review_packet_digest": h("1"),
        "cycle_evidence_digest": h("2"),
        "contract_digest": h("3"),
        "value_bound_conversion_digest": h("4"),
        "decision_record_digest": h("5"),
        "persistence_receipt_digest": h("6"),
        "checkpoint_digest": h("7"),
        "writer_request_digest": h("8"),
        "environment_digest": h("9"),
        "preflight_digest": h("a"),
        "authorization_request_digest": h("b"),
        "owner_action_signature_verified": True,
        "action_decision_verified": True,
        "action_authorization_intent": authorize,
        "action_denial_intent": not authorize,
        "action_record_persisted": False,
        "business_action_authorized": False,
        "external_action_executed": False,
        "executes_action": False,
    }
    row = {
        "schema": RESULT_SCHEMA,
        "state": state,
        "blockers": [],
        "authorization_decision": decision,
        "requested_choice": choice,
        "action_family": family,
        "owner_action_identity_verified": True,
        "owner_action_signature_verified": True,
        "action_decision_verified": True,
        "action_authorization_intent": authorize,
        "action_denial_intent": not authorize,
        "action_record": record,
        "action_record_digest": digest(record),
        "action_record_persisted": False,
        "requires_action_record_persistence": True,
        "generic_chat_instruction_accepted_as_action_authorization": False,
        "business_action_authorized": False,
        "renewal_authorized": False,
        "expansion_authorized": False,
        "non_renewal_authorized": False,
        "remediation_authorized": False,
        "pause_authorized": False,
        "termination_authorized": False,
        "billing_authorized": False,
        "pricing_change_authorized": False,
        "quota_change_authorized": False,
        "package_change_authorized": False,
        "role_change_authorized": False,
        "integration_change_authorized": False,
        "customer_contact_authorized": False,
        "provisioning_authorized": False,
        "deploy_authorized": False,
        "provider_called": False,
        "crm_write_authorized": False,
        "production_mutation_authorized": False,
        "external_action_executed": False,
        "network_called": False,
        "executes_action": False,
    }
    row.update(overrides)
    return row


def checkpoint(revision=0):
    return new_checkpoint_master(
        {"status": "ready"},
        base_revision=revision,
        created_at="2026-10-05T22:10:00Z",
        source_refs=["test:owner-renewal-action"],
    )


class OwnerRenewalActionPersistencePlanTests(unittest.TestCase):
    def test_verified_authorization_prepares_patch_only(self):
        out = build_owner_renewal_action_persistence_plan(
            verified(),
            checkpoint_master=checkpoint(),
        )
        self.assertEqual(
            out["state"],
            "READY_FOR_EXPLICIT_ACTION_RECORD_PERSISTENCE",
        )
        patch = out["patch_candidate"]
        self.assertEqual(patch["state"], "PATCH_CANDIDATE")
        self.assertIn(NAMESPACE, patch["patch"])
        record = patch["patch"][NAMESPACE]
        self.assertTrue(record["action_authorization_intent"])
        self.assertFalse(record["action_record_persisted"])
        self.assertFalse(record["business_action_authorized"])
        self.assertTrue(
            record[
                "eligible_for_action_execution_preflight_after_persistence"
            ]
        )
        self.assertFalse(
            out[
                "eligible_for_action_execution_preflight_after_persistence"
            ]
        )
        self.assertFalse(out["checkpoint_saved"])
        self.assertFalse(out["automatic_checkpoint_write"])
        self.assertFalse(out["renewal_authorized"])
        self.assertFalse(out["executes_action"])

    def test_denial_persists_intent_without_execution_eligibility(self):
        out = build_owner_renewal_action_persistence_plan(
            verified(decision="DENY_BUSINESS_ACTION"),
            checkpoint_master=checkpoint(),
        )
        record = out["patch_candidate"]["patch"][NAMESPACE]
        self.assertTrue(record["action_denial_intent"])
        self.assertFalse(record["action_authorization_intent"])
        self.assertFalse(
            record[
                "eligible_for_action_execution_preflight_after_persistence"
            ]
        )
        self.assertFalse(out["business_action_authorized"])

    def test_checkpoint_revision_and_state_are_pinned(self):
        out = build_owner_renewal_action_persistence_plan(
            verified(),
            checkpoint_master=checkpoint(9),
        )
        self.assertEqual(out["checkpoint_revision"], 9)
        self.assertEqual(
            out["patch_candidate"]["expected_revision"],
            9,
        )
        self.assertEqual(
            out["patch_candidate"]["expected_state_digest"],
            out["checkpoint_state_digest"],
        )

    def test_patch_and_event_are_deterministic(self):
        first = build_owner_renewal_action_persistence_plan(
            verified(),
            checkpoint_master=checkpoint(),
        )
        second = build_owner_renewal_action_persistence_plan(
            verified(),
            checkpoint_master=checkpoint(),
        )
        self.assertEqual(
            first["patch_candidate"]["patch_digest"],
            second["patch_candidate"]["patch_digest"],
        )
        self.assertEqual(
            first["patch_candidate"]["recommended_event_id"],
            second["patch_candidate"]["recommended_event_id"],
        )

    def test_record_digest_tampering_blocks(self):
        row = verified()
        row["action_record_digest"] = h("f")
        out = build_owner_renewal_action_persistence_plan(
            row,
            checkpoint_master=checkpoint(),
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "BUSINESS_ACTION_RECORD_DIGEST_MISMATCH",
            out["blockers"],
        )

    def test_record_choice_mismatch_blocks(self):
        row = verified()
        row["action_record"] = dict(row["action_record"])
        row["action_record"]["requested_choice"] = "NON_RENEWAL_REVIEW"
        row["action_record_digest"] = digest(row["action_record"])
        out = build_owner_renewal_action_persistence_plan(
            row,
            checkpoint_master=checkpoint(),
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "BUSINESS_ACTION_RECORD_CHOICE_MISMATCH",
            out["blockers"],
        )

    def test_invalid_lineage_digest_blocks(self):
        row = verified()
        row["action_record"] = dict(row["action_record"])
        row["action_record"]["contract_digest"] = "sha256:not-valid"
        row["action_record_digest"] = digest(row["action_record"])
        out = build_owner_renewal_action_persistence_plan(
            row,
            checkpoint_master=checkpoint(),
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "BUSINESS_ACTION_RECORD_DIGEST_FIELD_INVALID:contract_digest",
            out["blockers"],
        )

    def test_already_persisted_blocks(self):
        out = build_owner_renewal_action_persistence_plan(
            verified(action_record_persisted=True),
            checkpoint_master=checkpoint(),
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "BUSINESS_ACTION_RECORD_ALREADY_PERSISTED",
            out["blockers"],
        )

    def test_authority_flip_blocks(self):
        out = build_owner_renewal_action_persistence_plan(
            verified(billing_authorized=True),
            checkpoint_master=checkpoint(),
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "BUSINESS_ACTION_DECISION_UNSAFE_FIELD:billing_authorized",
            out["blockers"],
        )

    def test_invalid_checkpoint_blocks(self):
        out = build_owner_renewal_action_persistence_plan(
            verified(),
            checkpoint_master={"schema": "bad"},
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("CHECKPOINT_MASTER_INVALID", out["blockers"])

    def test_plan_never_grants_action_authority(self):
        out = build_owner_renewal_action_persistence_plan(
            verified(),
            checkpoint_master=checkpoint(),
        )
        for key in (
            "business_action_authorized",
            "renewal_authorized",
            "expansion_authorized",
            "non_renewal_authorized",
            "remediation_authorized",
            "pause_authorized",
            "termination_authorized",
            "billing_authorized",
            "pricing_change_authorized",
            "quota_change_authorized",
            "package_change_authorized",
            "role_change_authorized",
            "integration_change_authorized",
            "customer_contact_authorized",
            "provisioning_authorized",
            "deploy_authorized",
            "provider_called",
            "crm_write_authorized",
            "production_mutation_authorized",
            "external_action_executed",
            "network_called",
            "executes_action",
        ):
            self.assertFalse(out[key], key)


if __name__ == "__main__":
    unittest.main()
