from __future__ import annotations

import unittest

from atlasquant_aion_b2b_pilot_activation_execution_persistence_attestation import (
    NAMESPACE,
    build_execution_checkpoint_write_receipt_body,
    verify_activation_execution_record_persistence,
)
from atlasquant_aion_checkpoint_master import (
    append_checkpoint_patch,
    new_checkpoint_master,
)


def persistence_plan(decision="AUTHORIZE_ACTIVATION_EXECUTION"):
    authorize = decision == "AUTHORIZE_ACTIVATION_EXECUTION"
    deny = decision == "DENY_ACTIVATION_EXECUTION"
    record = {
        "schema": "ATLASQUANT_AION_B2B_PILOT_ACTIVATION_EXECUTION_VERIFICATION_V1",
        "state": (
            "ACTIVATION_EXECUTION_AUTHORIZATION_VERIFIED_PENDING_PERSISTENCE"
            if authorize
            else "ACTIVATION_EXECUTION_DENIAL_VERIFIED_PENDING_PERSISTENCE"
        ),
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
        "execution_record_digest": "sha256:" + "c" * 64,
        "execution_decision_verified": True,
        "execution_record_persisted": False,
        "execution_authorization_intent": authorize,
        "execution_denial_intent": deny,
        "activation_command_generated": False,
        "activation_command_executed": False,
        "pilot_activation_authorized": False,
        "pilot_activated": False,
        "eligible_for_activation_command_planning_after_persistence": authorize,
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
        "schema": "ATLASQUANT_AION_B2B_PILOT_ACTIVATION_EXECUTION_PERSISTENCE_PLAN_V1",
        "state": "READY_FOR_EXPLICIT_EXECUTION_RECORD_PERSISTENCE",
        "blockers": [],
        "execution_decision": decision,
        "pilot_id": "pilot-001",
        "execution_record_digest": record["execution_record_digest"],
        "patch_candidate": {
            "schema": "ATLASQUANT_AION_B2B_PILOT_ACTIVATION_EXECUTION_CHECKPOINT_PATCH_V1",
            "state": "PATCH_CANDIDATE",
            "expected_revision": 0,
            "recommended_event_id": "aion-b2b-pilot-activation-execution-0123456789abcdef",
            "patch": patch,
            "patch_digest": digest(patch),
            "requires_explicit_checkpoint_save": True,
            "requires_persistence_attestation": True,
            "automatic_checkpoint_write": False,
            "checkpoint_saved": False,
            "execution_record_persisted": False,
            "activation_command_generated": False,
            "activation_command_executed": False,
            "pilot_activation_authorized": False,
            "pilot_activated": False,
            "external_action_executed": False,
            "executes_action": False,
        },
        "execution_record_persisted": False,
        "checkpoint_saved": False,
        "automatic_checkpoint_write": False,
        "activation_command_generated": False,
        "activation_command_executed": False,
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
        created_at="2026-10-05T19:40:00Z",
        source_refs=["test:pilot-execution-persistence"],
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
            plan["execution_record_digest"],
            plan["pilot_id"],
        ],
    )


def receipt(plan=None, observed=None, **overrides):
    plan = plan or persistence_plan()
    observed = observed or observed_master(plan)
    row = build_execution_checkpoint_write_receipt_body(
        persistence_plan=plan,
        prior_checkpoint_master=prior_master(),
        observed_checkpoint_master=observed,
        persisted_at="2026-10-05T19:42:00Z",
        writer_ref="checkpoint-writer:execution-path",
    )
    if overrides:
        row.update(overrides)
        if "receipt_digest" not in overrides:
            import hashlib
            import json
            body = {k: v for k, v in row.items() if k != "receipt_digest"}
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


class AionB2BPilotActivationExecutionPersistenceAttestationTests(unittest.TestCase):
    def test_authorize_persistence_attested_without_command_or_activation(self):
        plan = persistence_plan()
        observed = observed_master(plan)
        out = verify_activation_execution_record_persistence(
            persistence_plan=plan,
            prior_checkpoint_master=prior_master(),
            observed_checkpoint_master=observed,
            checkpoint_write_receipt=receipt(plan, observed),
            now_ts="2026-10-05T19:43:00Z",
        )
        self.assertEqual(
            out["state"],
            "EXECUTION_RECORD_PERSISTENCE_ATTESTED_AUTHORIZE",
        )
        self.assertTrue(out["execution_record_persisted"])
        self.assertTrue(out["persistence_attested"])
        self.assertTrue(out["receipt_consistency_verified"])
        self.assertTrue(out["execution_authorization_intent"])
        self.assertTrue(out["eligible_for_activation_command_planning"])
        self.assertFalse(out["writer_identity_verified"])
        self.assertFalse(out["activation_command_generated"])
        self.assertFalse(out["activation_command_executed"])
        self.assertFalse(out["pilot_activation_authorized"])
        self.assertFalse(out["pilot_activated"])
        self.assertFalse(out["storage_write_performed"])
        self.assertFalse(out["executes_action"])

    def test_deny_persistence_is_not_command_planning_eligible(self):
        plan = persistence_plan("DENY_ACTIVATION_EXECUTION")
        observed = observed_master(plan)
        out = verify_activation_execution_record_persistence(
            persistence_plan=plan,
            prior_checkpoint_master=prior_master(),
            observed_checkpoint_master=observed,
            checkpoint_write_receipt=receipt(plan, observed),
            now_ts="2026-10-05T19:43:00Z",
        )
        self.assertEqual(
            out["state"],
            "EXECUTION_RECORD_PERSISTENCE_ATTESTED_DENY",
        )
        self.assertTrue(out["execution_denial_intent"])
        self.assertFalse(out["execution_authorization_intent"])
        self.assertFalse(out["eligible_for_activation_command_planning"])
        self.assertFalse(out["activation_command_generated"])

    def test_observed_snapshot_mismatch_blocks(self):
        plan = persistence_plan()
        observed = observed_master(plan)
        observed["journal"][-1]["patch"][NAMESPACE]["proposal_id"] = (
            "proposal-tampered"
        )
        out = verify_activation_execution_record_persistence(
            persistence_plan=plan,
            prior_checkpoint_master=prior_master(),
            observed_checkpoint_master=observed,
            checkpoint_write_receipt=receipt(
                plan,
                observed_master(plan),
            ),
            now_ts="2026-10-05T19:43:00Z",
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertFalse(out["execution_record_persisted"])

    def test_wrong_event_id_blocks(self):
        plan = persistence_plan()
        observed = observed_master(plan)
        observed["journal"][-1]["event_id"] = "different-event-id"
        out = verify_activation_execution_record_persistence(
            persistence_plan=plan,
            prior_checkpoint_master=prior_master(),
            observed_checkpoint_master=observed,
            checkpoint_write_receipt=receipt(
                plan,
                observed_master(plan),
            ),
            now_ts="2026-10-05T19:43:00Z",
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
        out = verify_activation_execution_record_persistence(
            persistence_plan=plan,
            prior_checkpoint_master=prior_master(),
            observed_checkpoint_master=observed,
            checkpoint_write_receipt=bad,
            now_ts="2026-10-05T19:43:00Z",
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "EXECUTION_CHECKPOINT_RECEIPT_PATCH_DIGEST_MISMATCH",
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
        out = verify_activation_execution_record_persistence(
            persistence_plan=plan,
            prior_checkpoint_master=prior_master(),
            observed_checkpoint_master=observed,
            checkpoint_write_receipt=bad,
            now_ts="2026-10-05T19:43:00Z",
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "EXECUTION_CHECKPOINT_RECEIPT_AFTER_DIGEST_MISMATCH",
            out["blockers"],
        )

    def test_missing_receipt_blocks(self):
        plan = persistence_plan()
        out = verify_activation_execution_record_persistence(
            persistence_plan=plan,
            prior_checkpoint_master=prior_master(),
            observed_checkpoint_master=observed_master(plan),
            checkpoint_write_receipt=None,
            now_ts="2026-10-05T19:43:00Z",
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "EXECUTION_CHECKPOINT_WRITE_RECEIPT_REQUIRED",
            out["blockers"],
        )

    def test_stale_receipt_blocks(self):
        plan = persistence_plan()
        observed = observed_master(plan)
        old = receipt(
            plan,
            observed,
            persisted_at="2026-10-05T19:30:00Z",
        )
        out = verify_activation_execution_record_persistence(
            persistence_plan=plan,
            prior_checkpoint_master=prior_master(),
            observed_checkpoint_master=observed,
            checkpoint_write_receipt=old,
            now_ts="2026-10-05T19:43:00Z",
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "EXECUTION_CHECKPOINT_RECEIPT_TOO_OLD",
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
        out = verify_activation_execution_record_persistence(
            persistence_plan=plan,
            prior_checkpoint_master=prior_master(),
            observed_checkpoint_master=observed,
            checkpoint_write_receipt=claimed,
            now_ts="2026-10-05T19:43:00Z",
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "EXECUTION_CHECKPOINT_RECEIPT_WRITER_IDENTITY_UNSUPPORTED",
            out["blockers"],
        )

    def test_wrong_prior_revision_blocks(self):
        plan = persistence_plan()
        different_prior = new_checkpoint_master(
            {"status": "ready"},
            base_revision=5,
            created_at="2026-10-05T19:40:00Z",
        )
        out = verify_activation_execution_record_persistence(
            persistence_plan=plan,
            prior_checkpoint_master=different_prior,
            observed_checkpoint_master=observed_master(plan),
            checkpoint_write_receipt=receipt(
                plan,
                observed_master(plan),
            ),
            now_ts="2026-10-05T19:43:00Z",
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "PRIOR_CHECKPOINT_REVISION_MISMATCH",
            out["blockers"],
        )

    def test_attestation_never_generates_or_executes_command(self):
        plan = persistence_plan()
        observed = observed_master(plan)
        out = verify_activation_execution_record_persistence(
            persistence_plan=plan,
            prior_checkpoint_master=prior_master(),
            observed_checkpoint_master=observed,
            checkpoint_write_receipt=receipt(plan, observed),
            now_ts="2026-10-05T19:43:00Z",
        )
        for key in (
            "writer_identity_verified",
            "activation_command_generated",
            "activation_command_executed",
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
