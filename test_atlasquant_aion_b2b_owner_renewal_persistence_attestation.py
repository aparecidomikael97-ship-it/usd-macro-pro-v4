from __future__ import annotations

import hashlib
import json
import unittest

from atlasquant_aion_b2b_owner_renewal_persistence_attestation import (
    build_owner_renewal_checkpoint_receipt_body,
    verify_owner_renewal_decision_persistence,
)
from atlasquant_aion_b2b_owner_renewal_persistence_plan import (
    DECISION_SCHEMA,
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


def prior_master():
    return new_checkpoint_master(
        {"status": "ready"},
        base_revision=0,
        created_at="2026-10-05T21:30:00Z",
        source_refs=["test:owner-renewal-persistence"],
    )


def persistence_plan(choice="RENEW_AS_IS_REVIEW"):
    record = {
        "schema": DECISION_SCHEMA,
        "state": "OWNER_RENEWAL_DECISION_VERIFIED_PENDING_PERSISTENCE",
        "requested_choice": choice,
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
        "decision_record_digest": "sha256:" + "a" * 64,
        "owner_signature_verified": True,
        "owner_decision_verified": True,
        "owner_decision_recorded": False,
        "decision_persisted": False,
        "business_action_authorized": False,
        "external_action_executed": False,
        "executes_action": False,
    }
    patch_body = {NAMESPACE: record}
    cp = prior_master()
    cp_state_digest = cp["state_digest"]
    patch = {
        "schema": PATCH_SCHEMA,
        "state": "PATCH_CANDIDATE",
        "expected_revision": 0,
        "expected_state_digest": cp_state_digest,
        "recommended_event_id": (
            "aion-b2b-owner-renewal-decision-0123456789abcdef0123456789abcdef"
        ),
        "patch": patch_body,
        "patch_digest": digest(patch_body),
        "requires_explicit_checkpoint_save": True,
        "requires_persistence_attestation": True,
        "automatic_checkpoint_write": False,
        "checkpoint_saved": False,
        "owner_decision_recorded": False,
        "decision_persisted": False,
        "business_action_authorized": False,
        "external_action_executed": False,
        "executes_action": False,
    }
    return {
        "schema": PLAN_SCHEMA,
        "state": "READY_FOR_EXPLICIT_CHECKPOINT_PERSISTENCE",
        "blockers": [],
        "requested_choice": choice,
        "customer_id": "customer-a",
        "pilot_id": "pilot-a",
        "decision_record_digest": record["decision_record_digest"],
        "checkpoint_revision": 0,
        "checkpoint_state_digest": cp_state_digest,
        "patch_candidate": patch,
        "owner_decision_recorded": False,
        "decision_persisted": False,
        "checkpoint_saved": False,
        "automatic_checkpoint_write": False,
        "requires_explicit_checkpoint_save": True,
        "requires_persistence_attestation": True,
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


def observed_master(plan=None):
    plan = plan or persistence_plan()
    patch = plan["patch_candidate"]
    return append_checkpoint_patch(
        prior_master(),
        event_id=patch["recommended_event_id"],
        patch=patch["patch"],
        expected_revision=patch["expected_revision"],
        created_at="2026-10-05T21:32:00Z",
        evidence_refs=[
            plan["decision_record_digest"],
            plan["customer_id"],
            plan["pilot_id"],
            plan["requested_choice"],
        ],
    )


def receipt(plan=None, observed=None, **overrides):
    plan = plan or persistence_plan()
    observed = observed or observed_master(plan)
    row = build_owner_renewal_checkpoint_receipt_body(
        persistence_plan=plan,
        prior_checkpoint_master=prior_master(),
        observed_checkpoint_master=observed,
        persisted_at="2026-10-05T21:32:00Z",
        writer_ref="checkpoint-writer:authorized-path",
    )
    if overrides:
        row.update(overrides)
        if "receipt_digest" not in overrides:
            body = {
                key: value
                for key, value in row.items()
                if key != "receipt_digest"
            }
            row["receipt_digest"] = digest(body)
    return row


class OwnerRenewalPersistenceAttestationTests(unittest.TestCase):
    def test_exact_persistence_is_attested_without_action_authority(self):
        plan = persistence_plan()
        observed = observed_master(plan)
        out = verify_owner_renewal_decision_persistence(
            persistence_plan=plan,
            prior_checkpoint_master=prior_master(),
            observed_checkpoint_master=observed,
            checkpoint_write_receipt=receipt(plan, observed),
            now_ts="2026-10-05T21:33:00Z",
        )
        self.assertEqual(
            out["state"],
            "OWNER_RENEWAL_DECISION_PERSISTENCE_ATTESTED",
        )
        self.assertTrue(out["owner_decision_recorded"])
        self.assertTrue(out["decision_persisted"])
        self.assertTrue(out["persistence_attested"])
        self.assertTrue(out["receipt_consistency_verified"])
        self.assertTrue(out["eligible_for_action_preflight"])
        self.assertFalse(out["writer_identity_verified"])
        self.assertFalse(out["storage_write_performed"])
        self.assertFalse(out["renewal_authorized"])
        self.assertFalse(out["executes_action"])

    def test_non_renewal_persistence_does_not_authorize_termination(self):
        plan = persistence_plan("NON_RENEWAL_REVIEW")
        observed = observed_master(plan)
        out = verify_owner_renewal_decision_persistence(
            persistence_plan=plan,
            prior_checkpoint_master=prior_master(),
            observed_checkpoint_master=observed,
            checkpoint_write_receipt=receipt(plan, observed),
            now_ts="2026-10-05T21:33:00Z",
        )
        self.assertTrue(out["decision_persisted"])
        self.assertEqual(out["requested_choice"], "NON_RENEWAL_REVIEW")
        self.assertFalse(out["termination_authorized"])
        self.assertFalse(out["customer_contact_authorized"])

    def test_wrong_prior_revision_blocks(self):
        different = new_checkpoint_master(
            {"status": "ready"},
            base_revision=4,
            created_at="2026-10-05T21:30:00Z",
        )
        plan = persistence_plan()
        out = verify_owner_renewal_decision_persistence(
            persistence_plan=plan,
            prior_checkpoint_master=different,
            observed_checkpoint_master=observed_master(plan),
            checkpoint_write_receipt=receipt(plan),
            now_ts="2026-10-05T21:33:00Z",
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "PRIOR_CHECKPOINT_REVISION_MISMATCH",
            out["blockers"],
        )

    def test_observed_event_mismatch_blocks(self):
        plan = persistence_plan()
        observed = observed_master(plan)
        observed["journal"][-1]["event_id"] = "tampered-event-id"
        out = verify_owner_renewal_decision_persistence(
            persistence_plan=plan,
            prior_checkpoint_master=prior_master(),
            observed_checkpoint_master=observed,
            checkpoint_write_receipt=receipt(
                plan,
                observed_master(plan),
            ),
            now_ts="2026-10-05T21:33:00Z",
        )
        self.assertEqual(out["state"], "BLOCKED")

    def test_receipt_patch_digest_mismatch_blocks(self):
        plan = persistence_plan()
        observed = observed_master(plan)
        bad = receipt(
            plan,
            observed,
            patch_digest="sha256:" + "0" * 64,
        )
        out = verify_owner_renewal_decision_persistence(
            persistence_plan=plan,
            prior_checkpoint_master=prior_master(),
            observed_checkpoint_master=observed,
            checkpoint_write_receipt=bad,
            now_ts="2026-10-05T21:33:00Z",
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "CHECKPOINT_RECEIPT_PATCH_DIGEST_MISMATCH",
            out["blockers"],
        )

    def test_receipt_after_digest_mismatch_blocks(self):
        plan = persistence_plan()
        observed = observed_master(plan)
        bad = receipt(
            plan,
            observed,
            after_checkpoint_digest="sha256:" + "0" * 64,
        )
        out = verify_owner_renewal_decision_persistence(
            persistence_plan=plan,
            prior_checkpoint_master=prior_master(),
            observed_checkpoint_master=observed,
            checkpoint_write_receipt=bad,
            now_ts="2026-10-05T21:33:00Z",
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "CHECKPOINT_RECEIPT_AFTER_DIGEST_MISMATCH",
            out["blockers"],
        )

    def test_stale_receipt_blocks(self):
        plan = persistence_plan()
        observed = observed_master(plan)
        old = receipt(
            plan,
            observed,
            persisted_at="2026-10-05T20:00:00Z",
        )
        out = verify_owner_renewal_decision_persistence(
            persistence_plan=plan,
            prior_checkpoint_master=prior_master(),
            observed_checkpoint_master=observed,
            checkpoint_write_receipt=old,
            now_ts="2026-10-05T21:33:00Z",
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("CHECKPOINT_RECEIPT_TOO_OLD", out["blockers"])

    def test_receipt_cannot_claim_writer_identity_verified(self):
        plan = persistence_plan()
        observed = observed_master(plan)
        claimed = receipt(
            plan,
            observed,
            writer_identity_verified=True,
        )
        out = verify_owner_renewal_decision_persistence(
            persistence_plan=plan,
            prior_checkpoint_master=prior_master(),
            observed_checkpoint_master=observed,
            checkpoint_write_receipt=claimed,
            now_ts="2026-10-05T21:33:00Z",
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "CHECKPOINT_RECEIPT_WRITER_IDENTITY_CLAIM_UNSUPPORTED",
            out["blockers"],
        )

    def test_missing_receipt_blocks(self):
        plan = persistence_plan()
        out = verify_owner_renewal_decision_persistence(
            persistence_plan=plan,
            prior_checkpoint_master=prior_master(),
            observed_checkpoint_master=observed_master(plan),
            checkpoint_write_receipt=None,
            now_ts="2026-10-05T21:33:00Z",
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "CHECKPOINT_WRITE_RECEIPT_REQUIRED",
            out["blockers"],
        )

    def test_attestation_never_authorizes_external_actions(self):
        plan = persistence_plan()
        observed = observed_master(plan)
        out = verify_owner_renewal_decision_persistence(
            persistence_plan=plan,
            prior_checkpoint_master=prior_master(),
            observed_checkpoint_master=observed,
            checkpoint_write_receipt=receipt(plan, observed),
            now_ts="2026-10-05T21:33:00Z",
        )
        for key in (
            "writer_identity_verified",
            "storage_write_performed",
            "network_called",
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
