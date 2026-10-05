from __future__ import annotations

import hashlib
import json
import unittest

from atlasquant_aion_b2b_owner_renewal_action_execution_persistence_attestation import (
    build_owner_execution_checkpoint_receipt_body,
    verify_owner_execution_record_persistence,
)
from atlasquant_aion_b2b_owner_renewal_action_execution_persistence_plan import (
    EXECUTION_SCHEMA,
    NAMESPACE,
    PATCH_SCHEMA,
    SCHEMA as PLAN_SCHEMA,
)
from atlasquant_aion_checkpoint_master import (
    append_checkpoint_patch,
    new_checkpoint_master,
)


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
    "business_action_authorized","renewal_authorized","expansion_authorized",
    "non_renewal_authorized","remediation_authorized","pause_authorized",
    "termination_authorized","billing_authorized","pricing_change_authorized",
    "quota_change_authorized","package_change_authorized","role_change_authorized",
    "integration_change_authorized","customer_contact_authorized",
    "provisioning_authorized","deploy_authorized","provider_called",
    "crm_write_authorized","production_mutation_authorized",
    "external_action_executed","network_called","executes_action",
)


def prior():
    return new_checkpoint_master(
        {"status": "ready"},
        base_revision=0,
        created_at="2026-10-05T22:40:00Z",
        source_refs=["test:execution-attestation"],
    )


def plan(decision="AUTHORIZE_BUSINESS_ACTION_EXECUTION"):
    authorize = decision == "AUTHORIZE_BUSINESS_ACTION_EXECUTION"
    state = (
        "OWNER_BUSINESS_ACTION_EXECUTION_VERIFIED_AUTHORIZE_PENDING_PERSISTENCE"
        if authorize else
        "OWNER_BUSINESS_ACTION_EXECUTION_VERIFIED_DENY_PENDING_PERSISTENCE"
    )
    record = {
        "schema": EXECUTION_SCHEMA,
        "state": state,
        "execution_decision": decision,
        "owner_id": "owner-a","tenant_id": "tenant-a","workspace_id": "workspace-a",
        "customer_id": "customer-a","pilot_id": "pilot-a",
        "package": "PROFISSIONAL","review_type": "RENEWAL_REVIEW",
        "requested_choice": "RENEW_AS_IS_REVIEW","action_family": "RENEWAL",
        "action_record_digest": h("1"),
        "action_persistence_receipt_digest": h("2"),
        "action_checkpoint_digest": h("3"),
        "action_writer_request_digest": h("4"),
        "authorization_preflight_digest": h("5"),
        "action_parameters_digest": h("6"),
        "execution_environment_digest": h("7"),
        "execution_preflight_digest": h("8"),
        "execution_request_digest": h("9"),
        "execution_record_digest": h("a"),
        "owner_execution_signature_verified": True,
        "execution_decision_verified": True,
        "execution_authorization_intent": authorize,
        "execution_denial_intent": not authorize,
        "execution_record_persisted": False,
        "eligible_for_command_planning_after_persistence": authorize,
        "execution_command_generated": False,
        "execution_command_executed": False,
        **{key: False for key in AUTHORITY_FIELDS},
    }
    body={NAMESPACE:record}
    cp=prior()
    patch={
        "schema":PATCH_SCHEMA,"state":"PATCH_CANDIDATE",
        "expected_revision":0,"expected_state_digest":cp["state_digest"],
        "recommended_event_id":"aion-b2b-owner-renewal-action-execution-0123456789abcdef0123456789abcdef",
        "patch":body,"patch_digest":digest(body),
        "requires_explicit_checkpoint_save":True,
        "requires_persistence_attestation":True,
        "automatic_checkpoint_write":False,"checkpoint_saved":False,
        "execution_record_persisted":False,
        "execution_command_generated":False,"execution_command_executed":False,
        **{key: False for key in AUTHORITY_FIELDS},
    }
    return {
        "schema":PLAN_SCHEMA,"state":"READY_FOR_EXPLICIT_EXECUTION_RECORD_PERSISTENCE",
        "blockers":[],"execution_decision":decision,
        "requested_choice":"RENEW_AS_IS_REVIEW","action_family":"RENEWAL",
        "owner_id":"owner-a","tenant_id":"tenant-a","workspace_id":"workspace-a",
        "customer_id":"customer-a","pilot_id":"pilot-a",
        "package":"PROFISSIONAL","review_type":"RENEWAL_REVIEW",
        "execution_record_digest":h("a"),
        "checkpoint_revision":0,"checkpoint_state_digest":cp["state_digest"],
        "patch_candidate":patch,"execution_record_persisted":False,
        "checkpoint_saved":False,"automatic_checkpoint_write":False,
        "requires_explicit_checkpoint_save":True,
        "requires_persistence_attestation":True,
        "eligible_for_command_planning_after_persistence":False,
        "execution_command_generated":False,"execution_command_executed":False,
        **{key: False for key in AUTHORITY_FIELDS},
    }


def observed(p=None):
    p=p or plan()
    patch=p["patch_candidate"]
    return append_checkpoint_patch(
        prior(),
        event_id=patch["recommended_event_id"],
        patch=patch["patch"],
        expected_revision=patch["expected_revision"],
        created_at="2026-10-05T22:42:00Z",
        evidence_refs=[
            p["execution_record_digest"],p["customer_id"],p["pilot_id"],
            p["requested_choice"],p["action_family"],p["execution_decision"],
        ],
    )


def receipt(p=None,o=None,**overrides):
    p=p or plan(); o=o or observed(p)
    row=build_owner_execution_checkpoint_receipt_body(
        persistence_plan=p,prior_checkpoint_master=prior(),
        observed_checkpoint_master=o,persisted_at="2026-10-05T22:42:00Z",
        writer_ref="checkpoint-writer:execution-intent",
    )
    row.update(overrides)
    if overrides and "receipt_digest" not in overrides:
        row["receipt_digest"]=digest({k:v for k,v in row.items() if k!="receipt_digest"})
    return row


class OwnerExecutionPersistenceAttestationTests(unittest.TestCase):
    def test_exact_authorize_persistence_is_attested_only(self):
        p=plan(); o=observed(p)
        out=verify_owner_execution_record_persistence(
            persistence_plan=p,prior_checkpoint_master=prior(),
            observed_checkpoint_master=o,checkpoint_write_receipt=receipt(p,o),
            now_ts="2026-10-05T22:43:00Z",
        )
        self.assertEqual(
            out["state"],
            "OWNER_RENEWAL_ACTION_EXECUTION_RECORD_PERSISTENCE_ATTESTED",
        )
        self.assertTrue(out["execution_record_persisted"])
        self.assertTrue(out["persistence_attested"])
        self.assertTrue(out["eligible_for_command_planning"])
        self.assertFalse(out["writer_identity_verified"])
        self.assertFalse(out["execution_command_generated"])
        self.assertFalse(out["business_action_authorized"])
        self.assertFalse(out["executes_action"])

    def test_deny_is_never_command_planning_eligible(self):
        p=plan("DENY_BUSINESS_ACTION_EXECUTION"); o=observed(p)
        out=verify_owner_execution_record_persistence(
            persistence_plan=p,prior_checkpoint_master=prior(),
            observed_checkpoint_master=o,checkpoint_write_receipt=receipt(p,o),
            now_ts="2026-10-05T22:43:00Z",
        )
        self.assertTrue(out["execution_record_persisted"])
        self.assertFalse(out["eligible_for_command_planning"])

    def test_wrong_prior_revision_blocks(self):
        p=plan()
        bad=new_checkpoint_master(
            {"status":"ready"},base_revision=4,created_at="2026-10-05T22:40:00Z"
        )
        out=verify_owner_execution_record_persistence(
            persistence_plan=p,prior_checkpoint_master=bad,
            observed_checkpoint_master=observed(p),checkpoint_write_receipt=receipt(p),
            now_ts="2026-10-05T22:43:00Z",
        )
        self.assertEqual(out["state"],"BLOCKED")
        self.assertIn("PRIOR_CHECKPOINT_REVISION_MISMATCH",out["blockers"])

    def test_receipt_choice_mismatch_blocks(self):
        p=plan();o=observed(p)
        out=verify_owner_execution_record_persistence(
            persistence_plan=p,prior_checkpoint_master=prior(),
            observed_checkpoint_master=o,
            checkpoint_write_receipt=receipt(p,o,requested_choice="REPRICE_REVIEW"),
            now_ts="2026-10-05T22:43:00Z",
        )
        self.assertEqual(out["state"],"BLOCKED")
        self.assertIn("EXECUTION_RECEIPT_MISMATCH:requested_choice",out["blockers"])

    def test_stale_receipt_blocks(self):
        p=plan();o=observed(p)
        out=verify_owner_execution_record_persistence(
            persistence_plan=p,prior_checkpoint_master=prior(),
            observed_checkpoint_master=o,
            checkpoint_write_receipt=receipt(p,o,persisted_at="2026-10-05T22:30:00Z"),
            now_ts="2026-10-05T22:43:00Z",
        )
        self.assertEqual(out["state"],"BLOCKED")
        self.assertIn("EXECUTION_RECEIPT_TOO_OLD",out["blockers"])

    def test_receipt_cannot_preclaim_writer_or_command(self):
        p=plan();o=observed(p)
        bad=receipt(p,o,writer_identity_verified=True,execution_command_generated=True)
        out=verify_owner_execution_record_persistence(
            persistence_plan=p,prior_checkpoint_master=prior(),
            observed_checkpoint_master=o,checkpoint_write_receipt=bad,
            now_ts="2026-10-05T22:43:00Z",
        )
        self.assertEqual(out["state"],"BLOCKED")
        self.assertIn("EXECUTION_RECEIPT_UNSAFE_FIELD:writer_identity_verified",out["blockers"])
        self.assertIn("EXECUTION_RECEIPT_UNSAFE_FIELD:execution_command_generated",out["blockers"])

    def test_attestation_grants_no_execution_authority(self):
        p=plan();o=observed(p)
        out=verify_owner_execution_record_persistence(
            persistence_plan=p,prior_checkpoint_master=prior(),
            observed_checkpoint_master=o,checkpoint_write_receipt=receipt(p,o),
            now_ts="2026-10-05T22:43:00Z",
        )
        for key in (
            "storage_write_performed","execution_command_generated",
            "execution_command_executed",*AUTHORITY_FIELDS,
        ):
            self.assertFalse(out[key],key)


if __name__=="__main__":
    unittest.main()
