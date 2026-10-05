from __future__ import annotations

import hashlib
import json
import unittest

from atlasquant_aion_b2b_owner_renewal_action_execution_ceremony import (
    RESULT_SCHEMA,
)
from atlasquant_aion_b2b_owner_renewal_action_execution_persistence_plan import (
    NAMESPACE,
    build_owner_renewal_action_execution_persistence_plan,
)
from atlasquant_aion_checkpoint_master import new_checkpoint_master


def h(char):
    return "sha256:" + char * 64


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


AUTHORITY_FIELDS = (
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
)


def verified(
    decision="AUTHORIZE_BUSINESS_ACTION_EXECUTION",
    **overrides,
):
    authorize = decision == "AUTHORIZE_BUSINESS_ACTION_EXECUTION"
    state = (
        "OWNER_BUSINESS_ACTION_EXECUTION_VERIFIED_AUTHORIZE_PENDING_PERSISTENCE"
        if authorize
        else "OWNER_BUSINESS_ACTION_EXECUTION_VERIFIED_DENY_PENDING_PERSISTENCE"
    )
    record = {
        "schema": RESULT_SCHEMA,
        "state": state,
        "execution_decision": decision,
        "owner_id": "owner-a",
        "tenant_id": "tenant-a",
        "workspace_id": "workspace-a",
        "customer_id": "customer-a",
        "pilot_id": "pilot-a",
        "package": "PROFISSIONAL",
        "review_type": "RENEWAL_REVIEW",
        "requested_choice": "RENEW_AS_IS_REVIEW",
        "action_family": "RENEWAL",
        "action_record_digest": h("1"),
        "action_persistence_receipt_digest": h("2"),
        "action_checkpoint_digest": h("3"),
        "action_writer_request_digest": h("4"),
        "authorization_preflight_digest": h("5"),
        "action_parameters_digest": h("6"),
        "execution_environment_digest": h("7"),
        "execution_preflight_digest": h("8"),
        "execution_request_digest": h("9"),
        "owner_execution_signature_verified": True,
        "execution_decision_verified": True,
        "execution_authorization_intent": authorize,
        "execution_denial_intent": not authorize,
        "execution_record_persisted": False,
        "execution_command_generated": False,
        "execution_command_executed": False,
        **{key: False for key in AUTHORITY_FIELDS},
    }
    row = {
        "schema": RESULT_SCHEMA,
        "state": state,
        "blockers": [],
        "execution_decision": decision,
        "requested_choice": "RENEW_AS_IS_REVIEW",
        "action_family": "RENEWAL",
        "owner_execution_identity_verified": True,
        "owner_execution_signature_verified": True,
        "execution_decision_verified": True,
        "execution_authorization_intent": authorize,
        "execution_denial_intent": not authorize,
        "execution_record": record,
        "execution_record_digest": digest(record),
        "execution_record_persisted": False,
        "requires_execution_record_persistence": True,
        "eligible_for_command_planning_after_persistence": authorize,
        "execution_command_generated": False,
        "execution_command_executed": False,
        "generic_chat_instruction_accepted_as_execution": False,
        **{key: False for key in AUTHORITY_FIELDS},
    }
    row.update(overrides)
    return row


def checkpoint(revision=0):
    return new_checkpoint_master(
        {"status": "ready"},
        base_revision=revision,
        created_at="2026-10-05T22:40:00Z",
        source_refs=["test:recurring-execution-persistence"],
    )


class OwnerRenewalActionExecutionPersistencePlanTests(unittest.TestCase):
    def test_authorize_prepares_patch_only(self):
        out = build_owner_renewal_action_execution_persistence_plan(
            verified(),
            checkpoint_master=checkpoint(),
        )
        self.assertEqual(
            out["state"],
            "READY_FOR_EXPLICIT_EXECUTION_RECORD_PERSISTENCE",
        )
        record = out["patch_candidate"]["patch"][NAMESPACE]
        self.assertTrue(record["execution_authorization_intent"])
        self.assertTrue(
            record["eligible_for_command_planning_after_persistence"]
        )
        self.assertFalse(out["eligible_for_command_planning_after_persistence"])
        self.assertFalse(out["execution_record_persisted"])
        self.assertFalse(out["execution_command_generated"])
        self.assertFalse(out["execution_command_executed"])
        self.assertFalse(out["business_action_authorized"])
        self.assertFalse(out["executes_action"])

    def test_deny_never_becomes_command_planning_eligible(self):
        out = build_owner_renewal_action_execution_persistence_plan(
            verified("DENY_BUSINESS_ACTION_EXECUTION"),
            checkpoint_master=checkpoint(),
        )
        record = out["patch_candidate"]["patch"][NAMESPACE]
        self.assertTrue(record["execution_denial_intent"])
        self.assertFalse(
            record["eligible_for_command_planning_after_persistence"]
        )

    def test_checkpoint_revision_and_state_are_pinned(self):
        out = build_owner_renewal_action_execution_persistence_plan(
            verified(),
            checkpoint_master=checkpoint(11),
        )
        self.assertEqual(out["checkpoint_revision"], 11)
        self.assertEqual(
            out["patch_candidate"]["expected_revision"],
            11,
        )
        self.assertEqual(
            out["patch_candidate"]["expected_state_digest"],
            out["checkpoint_state_digest"],
        )

    def test_record_digest_tampering_blocks(self):
        row = verified()
        row["execution_record_digest"] = h("f")
        out = build_owner_renewal_action_execution_persistence_plan(
            row,
            checkpoint_master=checkpoint(),
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "EXECUTION_RECORD_DIGEST_MISMATCH",
            out["blockers"],
        )

    def test_invalid_lineage_digest_blocks(self):
        row = verified()
        record = dict(row["execution_record"])
        record["action_parameters_digest"] = "sha256:not-valid"
        row["execution_record"] = record
        row["execution_record_digest"] = digest(record)
        out = build_owner_renewal_action_execution_persistence_plan(
            row,
            checkpoint_master=checkpoint(),
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "EXECUTION_RECORD_DIGEST_FIELD_INVALID:action_parameters_digest",
            out["blockers"],
        )

    def test_command_or_authority_flip_blocks(self):
        for key in (
            "execution_command_generated",
            "execution_command_executed",
            "billing_authorized",
            "termination_authorized",
        ):
            with self.subTest(key=key):
                out = build_owner_renewal_action_execution_persistence_plan(
                    verified(**{key: True}),
                    checkpoint_master=checkpoint(),
                )
                self.assertEqual(out["state"], "BLOCKED")

    def test_invalid_checkpoint_blocks(self):
        out = build_owner_renewal_action_execution_persistence_plan(
            verified(),
            checkpoint_master={"schema": "bad"},
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("CHECKPOINT_MASTER_INVALID", out["blockers"])

    def test_plan_grants_no_execution_authority(self):
        out = build_owner_renewal_action_execution_persistence_plan(
            verified(),
            checkpoint_master=checkpoint(),
        )
        for key in (
            "execution_record_persisted",
            "checkpoint_saved",
            "automatic_checkpoint_write",
            "eligible_for_command_planning_after_persistence",
            "execution_command_generated",
            "execution_command_executed",
            *AUTHORITY_FIELDS,
        ):
            self.assertFalse(out[key], key)


if __name__ == "__main__":
    unittest.main()
