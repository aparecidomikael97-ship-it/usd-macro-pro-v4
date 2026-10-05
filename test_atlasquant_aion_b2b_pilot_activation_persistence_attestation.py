from __future__ import annotations

import unittest

from atlasquant_aion_b2b_pilot_activation_persistence_attestation import (
    NAMESPACE,
    build_activation_checkpoint_write_receipt_body,
    verify_pilot_activation_record_persistence,
)
from atlasquant_aion_checkpoint_master import (
    append_checkpoint_patch,
    new_checkpoint_master,
)


def persistence_plan(decision="AUTHORIZE_PILOT_ACTIVATION"):
    authorize = decision == "AUTHORIZE_PILOT_ACTIVATION"
    deny = decision == "DENY_PILOT_ACTIVATION"
    record = {
        "schema": "ATLASQUANT_AION_B2B_PILOT_ACTIVATION_VERIFICATION_V1",
        "state": (
            "ACTIVATION_AUTHORIZATION_VERIFIED_PENDING_PERSISTENCE"
            if authorize
            else "ACTIVATION_DENIAL_VERIFIED_PENDING_PERSISTENCE"
        ),
        "decision": decision,
        "owner_id": "HUMAN_OWNER",
        "tenant_id": "atlasquant-owner",
        "workspace_id": "business",
        "candidate_id": "candidate-001",
        "proposal_id": "proposal-001",
        "pilot_id": "pilot-001",
        "environment_digest": "sha256:" + "e" * 64,
        "preflight_digest": "sha256:" + "f" * 64,
        "activation_request_digest": "sha256:" + "a" * 64,
        "activation_record_digest": "sha256:" + "c" * 64,
        "activation_decision_verified": True,
        "activation_record_persisted": False,
        "activation_authorization_intent": authorize,
        "activation_denial_intent": deny,
        "pilot_activation_authorized": False,
        "pilot_activated": False,
        "eligible_for_activation_execution_after_persistence": authorize,
        "external_action_executed": False,
        "executes_action": False,
    }
    import hashlib
    import json
    patch = {NAMESPACE: record}

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

    return {
        "schema": "ATLASQUANT_AION_B2B_PILOT_ACTIVATION_PERSISTENCE_PLAN_V1",
        "state": "READY_FOR_EXPLICIT_ACTIVATION_RECORD_PERSISTENCE",
        "blockers": [],
        "activation_decision": decision,
        "pilot_id": "pilot-001",
        "activation_record_digest": record["activation_record_digest"],
        "patch_candidate": {
            "schema": "ATLASQUANT_AION_B2B_PILOT_ACTIVATION_CHECKPOINT_PATCH_V1",
            "state": "PATCH_CANDIDATE",
            "expected_revision": 0,
            "recommended_event_id": "aion-b2b-pilot-activation-0123456789abcdef",
            "patch": patch,
            "patch_digest": digest(patch),
            "requires_explicit_checkpoint_save": True,
            "requires_persistence_attestation": True,
            "automatic_checkpoint_write": False,
            "checkpoint_saved": False,
            "activation_record_persisted": False,
            "pilot_activation_authorized": False,
            "pilot_activated": False,
            "external_action_executed": False,
            "executes_action": False,
        },
        "activation_record_persisted": False,
        "checkpoint_saved": False,
        "automatic_checkpoint_write": False,
        "pilot_activation_authorized": False,
        "pilot_activated": False,
        "requires_explicit_checkpoint_save": True,
        "requires_persistence_attestation": True,
        "external_action_executed": False,
        "network_called": False,
        "executes_action": False,
    }


def prior_master():
    return new_checkpoint_master(
        {"status": "ready"},
        base_revision=0,
        created_at="2026-10-05T18:30:00Z",
        source_refs=["test:pilot-activation-persistence"],
    )


def observed_master(plan=None):
    plan = plan or persistence_plan()
    patch = plan["patch_candidate"]
    return append_checkpoint_patch(
        prior_master(),
        event_id=patch["recommended_event_id"],
        patch=patch["patch"],
        expected_revision=patch["expected_revision"],
        created_at="1970-01-01T00:00:00+00:00",
        evidence_refs=[
            plan["activation_record_digest"],
            plan["pilot_id"],
        ],
    )


def receipt(plan=None, observed=None, **overrides):
    plan = plan or persistence_plan()
    observed = observed or observed_master(plan)
    row = build_activation_checkpoint_write_receipt_body(
        persistence_plan=plan,
        prior_checkpoint_master=prior_master(),
        observed_checkpoint_master=observed,
        persisted_at="2026-10-05T18:32:00Z",
        writer_ref="checkpoint-writer:authorized-path",
    )
    if overrides:
        row.update(overrides)
        if "receipt_digest" not in overrides:
            import hashlib
            import json
            body = {
                k: v
                for k, v in row.items()
                if k != "receipt_digest"
            }
            raw = json.dumps(
                body,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
                default=str,
            ).encode("utf-8")
            row["receipt_digest"] = (
                "sha256:" + hashlib.sha256(raw).hexdigest()
            )
    return row


class AionB2BPilotActivationPersistenceAttestationTests(unittest.TestCase):
    def test_authorize_persistence_attested_without_activation_authority(self):
        plan = persistence_plan()
        observed = observed_master(plan)
        out = verify_pilot_activation_record_persistence(
            persistence_plan=plan,
            prior_checkpoint_master=prior_master(),
            observed_checkpoint_master=observed,
            checkpoint_write_receipt=receipt(plan, observed),
            now_ts="2026-10-05T18:33:00Z",
        )
        self.assertEqual(
            out["state"],
            "ACTIVATION_RECORD_PERSISTENCE_ATTESTED_AUTHORIZE",
        )
        self.assertTrue(out["activation_record_persisted"])
        self.assertTrue(out["persistence_attested"])
        self.assertTrue(out["receipt_consistency_verified"])
        self.assertTrue(out["activation_authorization_intent"])
        self.assertTrue(
            out["eligible_for_activation_execution_preflight"]
        )
        self.assertFalse(out["writer_identity_verified"])
        self.assertFalse(out["pilot_activation_authorized"])
        self.assertFalse(out["pilot_activated"])
        self.assertFalse(out["storage_write_performed"])
        self.assertFalse(out["executes_action"])
        self.assertEqual(
            out["scope"],
            {
                "owner_id": "HUMAN_OWNER",
                "tenant_id": "atlasquant-owner",
                "workspace_id": "business",
            },
        )
        self.assertEqual(out["candidate_id"], "candidate-001")
        self.assertEqual(out["proposal_id"], "proposal-001")

    def test_deny_persistence_is_not_execution_preflight_eligible(self):
        plan = persistence_plan("DENY_PILOT_ACTIVATION")
        observed = observed_master(plan)
        out = verify_pilot_activation_record_persistence(
            persistence_plan=plan,
            prior_checkpoint_master=prior_master(),
            observed_checkpoint_master=observed,
            checkpoint_write_receipt=receipt(plan, observed),
            now_ts="2026-10-05T18:33:00Z",
        )
        self.assertEqual(
            out["state"],
            "ACTIVATION_RECORD_PERSISTENCE_ATTESTED_DENY",
        )
        self.assertTrue(out["activation_denial_intent"])
        self.assertFalse(out["activation_authorization_intent"])
        self.assertFalse(
            out["eligible_for_activation_execution_preflight"]
        )
        self.assertFalse(out["pilot_activation_authorized"])

    def test_observed_snapshot_mismatch_blocks(self):
        plan = persistence_plan()
        observed = observed_master(plan)
        observed["journal"][-1]["patch"][NAMESPACE]["proposal_id"] = (
            "proposal-tampered"
        )
        out = verify_pilot_activation_record_persistence(
            persistence_plan=plan,
            prior_checkpoint_master=prior_master(),
            observed_checkpoint_master=observed,
            checkpoint_write_receipt=receipt(
                plan,
                observed_master(plan),
            ),
            now_ts="2026-10-05T18:33:00Z",
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertFalse(out["activation_record_persisted"])

    def test_wrong_event_id_blocks(self):
        plan = persistence_plan()
        observed = observed_master(plan)
        observed["journal"][-1]["event_id"] = "different-event-id"
        out = verify_pilot_activation_record_persistence(
            persistence_plan=plan,
            prior_checkpoint_master=prior_master(),
            observed_checkpoint_master=observed,
            checkpoint_write_receipt=receipt(
                plan,
                observed_master(plan),
            ),
            now_ts="2026-10-05T18:33:00Z",
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
        out = verify_pilot_activation_record_persistence(
            persistence_plan=plan,
            prior_checkpoint_master=prior_master(),
            observed_checkpoint_master=observed,
            checkpoint_write_receipt=bad,
            now_ts="2026-10-05T18:33:00Z",
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "ACTIVATION_CHECKPOINT_RECEIPT_PATCH_DIGEST_MISMATCH",
            out["blockers"],
        )

    def test_receipt_after_checkpoint_digest_mismatch_blocks(self):
        plan = persistence_plan()
        observed = observed_master(plan)
        bad = receipt(
            plan,
            observed,
            after_checkpoint_digest="sha256:" + "0" * 64,
        )
        out = verify_pilot_activation_record_persistence(
            persistence_plan=plan,
            prior_checkpoint_master=prior_master(),
            observed_checkpoint_master=observed,
            checkpoint_write_receipt=bad,
            now_ts="2026-10-05T18:33:00Z",
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "ACTIVATION_CHECKPOINT_RECEIPT_AFTER_DIGEST_MISMATCH",
            out["blockers"],
        )

    def test_missing_receipt_blocks(self):
        plan = persistence_plan()
        out = verify_pilot_activation_record_persistence(
            persistence_plan=plan,
            prior_checkpoint_master=prior_master(),
            observed_checkpoint_master=observed_master(plan),
            checkpoint_write_receipt=None,
            now_ts="2026-10-05T18:33:00Z",
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "ACTIVATION_CHECKPOINT_WRITE_RECEIPT_REQUIRED",
            out["blockers"],
        )

    def test_stale_receipt_blocks(self):
        plan = persistence_plan()
        observed = observed_master(plan)
        old = receipt(
            plan,
            observed,
            persisted_at="2026-10-05T17:00:00Z",
        )
        out = verify_pilot_activation_record_persistence(
            persistence_plan=plan,
            prior_checkpoint_master=prior_master(),
            observed_checkpoint_master=observed,
            checkpoint_write_receipt=old,
            now_ts="2026-10-05T18:33:00Z",
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "ACTIVATION_CHECKPOINT_RECEIPT_TOO_OLD",
            out["blockers"],
        )

    def test_receipt_cannot_claim_writer_identity(self):
        plan = persistence_plan()
        observed = observed_master(plan)
        claimed = receipt(
            plan,
            observed,
            writer_identity_verified=True,
        )
        out = verify_pilot_activation_record_persistence(
            persistence_plan=plan,
            prior_checkpoint_master=prior_master(),
            observed_checkpoint_master=observed,
            checkpoint_write_receipt=claimed,
            now_ts="2026-10-05T18:33:00Z",
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "ACTIVATION_CHECKPOINT_RECEIPT_WRITER_IDENTITY_UNSUPPORTED",
            out["blockers"],
        )

    def test_wrong_prior_revision_blocks(self):
        plan = persistence_plan()
        different_prior = new_checkpoint_master(
            {"status": "ready"},
            base_revision=5,
            created_at="2026-10-05T18:30:00Z",
        )
        out = verify_pilot_activation_record_persistence(
            persistence_plan=plan,
            prior_checkpoint_master=different_prior,
            observed_checkpoint_master=observed_master(plan),
            checkpoint_write_receipt=receipt(
                plan,
                observed_master(plan),
            ),
            now_ts="2026-10-05T18:33:00Z",
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "PRIOR_CHECKPOINT_REVISION_MISMATCH",
            out["blockers"],
        )

    def test_attestation_never_authorizes_external_actions(self):
        plan = persistence_plan()
        observed = observed_master(plan)
        out = verify_pilot_activation_record_persistence(
            persistence_plan=plan,
            prior_checkpoint_master=prior_master(),
            observed_checkpoint_master=observed,
            checkpoint_write_receipt=receipt(plan, observed),
            now_ts="2026-10-05T18:33:00Z",
        )
        for key in (
            "writer_identity_verified",
            "pilot_activation_authorized",
            "pilot_activated",
            "customer_contact_authorized",
            "billing_authorized",
            "provisioning_authorized",
            "deploy_authorized",
            "production_mutation_authorized",
            "storage_write_performed",
            "external_action_executed",
            "network_called",
            "executes_action",
        ):
            self.assertFalse(out[key], key)


if __name__ == "__main__":
    unittest.main()
