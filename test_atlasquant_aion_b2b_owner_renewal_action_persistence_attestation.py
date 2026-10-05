from __future__ import annotations

import hashlib
import json
import unittest

from atlasquant_aion_b2b_owner_renewal_action_persistence_attestation import (
    build_owner_renewal_action_checkpoint_receipt_body,
    verify_owner_renewal_action_persistence,
)
from atlasquant_aion_b2b_owner_renewal_action_persistence_plan import (
    ACTION_SCHEMA,
    NAMESPACE,
    PATCH_SCHEMA,
    SCHEMA as PLAN_SCHEMA,
)
from atlasquant_aion_checkpoint_master import (
    append_checkpoint_patch,
    new_checkpoint_master,
)


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


def prior_master():
    return new_checkpoint_master(
        {"status": "ready"},
        base_revision=0,
        created_at="2026-10-05T22:10:00Z",
        source_refs=["test:action-persistence"],
    )


def persistence_plan(
    decision="AUTHORIZE_BUSINESS_ACTION",
    choice="RENEW_AS_IS_REVIEW",
    family="RENEWAL",
):
    authorize = decision == "AUTHORIZE_BUSINESS_ACTION"
    state = (
        "OWNER_BUSINESS_ACTION_DECISION_VERIFIED_AUTHORIZE_PENDING_PERSISTENCE"
        if authorize
        else "OWNER_BUSINESS_ACTION_DECISION_VERIFIED_DENY_PENDING_PERSISTENCE"
    )
    record = {
        "schema": ACTION_SCHEMA,
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
        "action_record_digest": h("c"),
        "owner_action_signature_verified": True,
        "action_decision_verified": True,
        "action_authorization_intent": authorize,
        "action_denial_intent": not authorize,
        "action_record_persisted": False,
        "business_action_authorized": False,
        "eligible_for_action_execution_preflight_after_persistence": authorize,
        "external_action_executed": False,
        "executes_action": False,
    }
    cp = prior_master()
    patch_body = {NAMESPACE: record}
    patch = {
        "schema": PATCH_SCHEMA,
        "state": "PATCH_CANDIDATE",
        "expected_revision": 0,
        "expected_state_digest": cp["state_digest"],
        "recommended_event_id": "aion-b2b-owner-renewal-action-0123456789abcdef0123456789abcdef",
        "patch": patch_body,
        "patch_digest": digest(patch_body),
        "requires_explicit_checkpoint_save": True,
        "requires_persistence_attestation": True,
        "automatic_checkpoint_write": False,
        "checkpoint_saved": False,
        "action_record_persisted": False,
        "business_action_authorized": False,
        "external_action_executed": False,
        "executes_action": False,
    }
    return {
        "schema": PLAN_SCHEMA,
        "state": "READY_FOR_EXPLICIT_ACTION_RECORD_PERSISTENCE",
        "blockers": [],
        "authorization_decision": decision,
        "requested_choice": choice,
        "action_family": family,
        "owner_id": "owner-a",
        "tenant_id": "tenant-a",
        "workspace_id": "workspace-a",
        "customer_id": "customer-a",
        "pilot_id": "pilot-a",
        "package": "PROFISSIONAL",
        "review_type": "RENEWAL_REVIEW",
        "action_record_digest": record["action_record_digest"],
        "checkpoint_revision": 0,
        "checkpoint_state_digest": cp["state_digest"],
        "patch_candidate": patch,
        "action_record_persisted": False,
        "checkpoint_saved": False,
        "automatic_checkpoint_write": False,
        "requires_explicit_checkpoint_save": True,
        "requires_persistence_attestation": True,
        "eligible_for_action_execution_preflight_after_persistence": False,
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


def observed_master(plan=None):
    plan = plan or persistence_plan()
    patch = plan["patch_candidate"]
    return append_checkpoint_patch(
        prior_master(),
        event_id=patch["recommended_event_id"],
        patch=patch["patch"],
        expected_revision=patch["expected_revision"],
        created_at="2026-10-05T22:12:00Z",
        evidence_refs=[
            plan["action_record_digest"],
            plan["customer_id"],
            plan["pilot_id"],
            plan["requested_choice"],
            plan["action_family"],
            plan["authorization_decision"],
        ],
    )


def receipt(plan=None, observed=None, **overrides):
    plan = plan or persistence_plan()
    observed = observed or observed_master(plan)
    row = build_owner_renewal_action_checkpoint_receipt_body(
        persistence_plan=plan,
        prior_checkpoint_master=prior_master(),
        observed_checkpoint_master=observed,
        persisted_at="2026-10-05T22:12:00Z",
        writer_ref="checkpoint-writer:recurring-action",
    )
    if overrides:
        row.update(overrides)
        if "receipt_digest" not in overrides:
            body = {k: v for k, v in row.items() if k != "receipt_digest"}
            row["receipt_digest"] = digest(body)
    return row


class OwnerRenewalActionPersistenceAttestationTests(unittest.TestCase):
    def test_exact_authorization_persistence_is_attested_only(self):
        plan = persistence_plan()
        observed = observed_master(plan)
        out = verify_owner_renewal_action_persistence(
            persistence_plan=plan,
            prior_checkpoint_master=prior_master(),
            observed_checkpoint_master=observed,
            checkpoint_write_receipt=receipt(plan, observed),
            now_ts="2026-10-05T22:13:00Z",
        )
        self.assertEqual(
            out["state"],
            "OWNER_RENEWAL_ACTION_RECORD_PERSISTENCE_ATTESTED",
        )
        self.assertTrue(out["action_record_persisted"])
        self.assertTrue(out["persistence_attested"])
        self.assertTrue(out["receipt_consistency_verified"])
        self.assertTrue(out["eligible_for_action_execution_preflight"])
        self.assertFalse(out["writer_identity_verified"])
        self.assertFalse(out["business_action_authorized"])
        self.assertFalse(out["renewal_authorized"])
        self.assertFalse(out["storage_write_performed"])
        self.assertFalse(out["executes_action"])

    def test_denial_persistence_never_becomes_execution_eligible(self):
        plan = persistence_plan(decision="DENY_BUSINESS_ACTION")
        observed = observed_master(plan)
        out = verify_owner_renewal_action_persistence(
            persistence_plan=plan,
            prior_checkpoint_master=prior_master(),
            observed_checkpoint_master=observed,
            checkpoint_write_receipt=receipt(plan, observed),
            now_ts="2026-10-05T22:13:00Z",
        )
        self.assertTrue(out["action_record_persisted"])
        self.assertFalse(out["eligible_for_action_execution_preflight"])
        self.assertFalse(out["business_action_authorized"])

    def test_wrong_prior_revision_blocks(self):
        bad_prior = new_checkpoint_master(
            {"status": "ready"},
            base_revision=4,
            created_at="2026-10-05T22:10:00Z",
        )
        plan = persistence_plan()
        out = verify_owner_renewal_action_persistence(
            persistence_plan=plan,
            prior_checkpoint_master=bad_prior,
            observed_checkpoint_master=observed_master(plan),
            checkpoint_write_receipt=receipt(plan),
            now_ts="2026-10-05T22:13:00Z",
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "PRIOR_CHECKPOINT_REVISION_MISMATCH",
            out["blockers"],
        )

    def test_receipt_patch_digest_mismatch_blocks(self):
        plan = persistence_plan()
        observed = observed_master(plan)
        bad = receipt(plan, observed, patch_digest=h("f"))
        out = verify_owner_renewal_action_persistence(
            persistence_plan=plan,
            prior_checkpoint_master=prior_master(),
            observed_checkpoint_master=observed,
            checkpoint_write_receipt=bad,
            now_ts="2026-10-05T22:13:00Z",
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "ACTION_RECEIPT_PATCH_DIGEST_MISMATCH",
            out["blockers"],
        )

    def test_receipt_choice_mismatch_blocks(self):
        plan = persistence_plan()
        observed = observed_master(plan)
        bad = receipt(
            plan,
            observed,
            requested_choice="NON_RENEWAL_REVIEW",
        )
        out = verify_owner_renewal_action_persistence(
            persistence_plan=plan,
            prior_checkpoint_master=prior_master(),
            observed_checkpoint_master=observed,
            checkpoint_write_receipt=bad,
            now_ts="2026-10-05T22:13:00Z",
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("ACTION_RECEIPT_CHOICE_MISMATCH", out["blockers"])

    def test_stale_receipt_blocks(self):
        plan = persistence_plan()
        observed = observed_master(plan)
        bad = receipt(
            plan,
            observed,
            persisted_at="2026-10-05T21:00:00Z",
        )
        out = verify_owner_renewal_action_persistence(
            persistence_plan=plan,
            prior_checkpoint_master=prior_master(),
            observed_checkpoint_master=observed,
            checkpoint_write_receipt=bad,
            now_ts="2026-10-05T22:13:00Z",
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("ACTION_RECEIPT_TOO_OLD", out["blockers"])

    def test_receipt_cannot_preclaim_writer_identity(self):
        plan = persistence_plan()
        observed = observed_master(plan)
        bad = receipt(
            plan,
            observed,
            writer_identity_verified=True,
        )
        out = verify_owner_renewal_action_persistence(
            persistence_plan=plan,
            prior_checkpoint_master=prior_master(),
            observed_checkpoint_master=observed,
            checkpoint_write_receipt=bad,
            now_ts="2026-10-05T22:13:00Z",
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "ACTION_RECEIPT_PREVERIFIED_WRITER_FORBIDDEN",
            out["blockers"],
        )

    def test_output_never_grants_business_authority(self):
        plan = persistence_plan()
        observed = observed_master(plan)
        out = verify_owner_renewal_action_persistence(
            persistence_plan=plan,
            prior_checkpoint_master=prior_master(),
            observed_checkpoint_master=observed,
            checkpoint_write_receipt=receipt(plan, observed),
            now_ts="2026-10-05T22:13:00Z",
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
