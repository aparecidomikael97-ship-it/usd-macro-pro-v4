from __future__ import annotations

import base64
import tempfile
import unittest
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from atlasquant_aion_b2b_pilot_activation_execution_ceremony import (
    build_activation_execution_request,
    canonical_execution_decision_bytes,
    verify_activation_execution_decision,
)
from atlasquant_aion_nonce_registry import PersistentNonceRegistry
from atlasquant_aion_trust_root import TrustRootRegistry

NOW = "2026-10-05T19:40:30Z"
ISSUED = "2026-10-05T19:40:00Z"
EXPIRES = "2026-10-05T19:41:30Z"


def b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def trust_material(status="ACTIVE"):
    private = Ed25519PrivateKey.generate()
    public = private.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    registry = TrustRootRegistry.from_mapping(
        {
            "schema": "ATLASQUANT_AION_TRUST_ROOT_V1",
            "roots": [
                {
                    "key_id": "pilot-execution-owner-key",
                    "key_version": 1,
                    "algorithm": "Ed25519",
                    "public_key_b64": b64url(public),
                    "status": status,
                    "not_before": "2026-10-05T00:00:00Z",
                    "not_after": "2027-10-05T00:00:00Z",
                }
            ],
            "revoked_key_ids": [],
        }
    )
    return private, registry


def preflight(**overrides):
    row = {
        "schema": "ATLASQUANT_AION_B2B_PILOT_ACTIVATION_EXECUTION_PREFLIGHT_V1",
        "state": "READY_FOR_ACTIVATION_EXECUTION_CEREMONY",
        "scope": {
            "owner_id": "HUMAN_OWNER",
            "tenant_id": "atlasquant-owner",
            "workspace_id": "business",
        },
        "candidate_id": "candidate-001",
        "proposal_id": "proposal-001",
        "pilot_id": "pilot-001",
        "blockers": [],
        "execution_environment_digest": "sha256:" + "e" * 64,
        "execution_preflight_digest": "sha256:" + "f" * 64,
        "activation_execution_ceremony_eligible": True,
        "human_execution_confirmation_required": True,
        "execution_request_issued": False,
        "owner_execution_signature_verified": False,
        "activation_command_generated": False,
        "activation_command_executed": False,
        "pilot_activation_authorized": False,
        "pilot_activated": False,
        "customer_contact_authorized": False,
        "contract_signature_authorized": False,
        "billing_authorized": False,
        "spend_authorized": False,
        "provisioning_authorized": False,
        "deploy_authorized": False,
        "crm_write_authorized": False,
        "provider_called": False,
        "production_mutation_authorized": False,
        "external_action_executed": False,
        "network_called": False,
        "executes_action": False,
    }
    row.update(overrides)
    return row


def built_request(decision="AUTHORIZE_ACTIVATION_EXECUTION", **overrides):
    private, registry = trust_material()
    args = {
        "execution_preflight": preflight(),
        "owner_trust_roots": registry,
        "now_ts": NOW,
        "decision": decision,
        "ceremony_id": "pilot-execution-ceremony-001",
        "nonce": "pilot-execution-nonce-0001",
        "issued_at": ISSUED,
        "expires_at": EXPIRES,
        "key_id": "pilot-execution-owner-key",
        "key_version": 1,
    }
    args.update(overrides)
    built = build_activation_execution_request(**args)
    return private, registry, built, args["execution_preflight"]


class AionB2BPilotActivationExecutionCeremonyTests(unittest.TestCase):
    def test_valid_authorize_request_is_signature_ready_without_command(self):
        _, _, built, _ = built_request()
        self.assertEqual(
            built["state"],
            "READY_FOR_EXTERNAL_OWNER_EXECUTION_SIGNATURE",
        )
        self.assertFalse(built["blockers"])
        self.assertEqual(built["execution_decision"], "UNDECIDED")
        self.assertFalse(built["execution_decision_verified"])
        self.assertFalse(built["execution_record_persisted"])
        self.assertFalse(built["activation_command_generated"])
        self.assertFalse(built["activation_command_executed"])
        self.assertFalse(built["pilot_activation_authorized"])
        self.assertFalse(built["pilot_activated"])
        self.assertFalse(built["executes_action"])

    def test_generic_chat_instruction_is_not_execution_authorization(self):
        _, _, built, _ = built_request("vamos lá")
        self.assertEqual(built["state"], "BLOCKED")
        self.assertIn(
            "ACTIVATION_EXECUTION_DECISION_INVALID",
            built["blockers"],
        )

    def test_only_canonical_execution_choices_are_accepted(self):
        for decision in (
            "approve",
            "execute",
            "activate",
            "YES",
            "AUTHORIZE",
            True,
            1,
            "",
            None,
        ):
            with self.subTest(decision=decision):
                _, _, built, _ = built_request(decision)
                self.assertEqual(built["state"], "BLOCKED")
                self.assertIn(
                    "ACTIVATION_EXECUTION_DECISION_INVALID",
                    built["blockers"],
                )

    def test_preflight_must_remain_authority_free(self):
        for key in (
            "execution_request_issued",
            "owner_execution_signature_verified",
            "activation_command_generated",
            "activation_command_executed",
            "pilot_activation_authorized",
            "pilot_activated",
            "billing_authorized",
            "provisioning_authorized",
            "deploy_authorized",
            "production_mutation_authorized",
            "executes_action",
        ):
            with self.subTest(key=key):
                bad = preflight(**{key: True})
                _, registry = trust_material()
                built = build_activation_execution_request(
                    execution_preflight=bad,
                    owner_trust_roots=registry,
                    now_ts=NOW,
                    decision="AUTHORIZE_ACTIVATION_EXECUTION",
                    ceremony_id="pilot-execution-ceremony-001",
                    nonce="pilot-execution-nonce-0001",
                    issued_at=ISSUED,
                    expires_at=EXPIRES,
                    key_id="pilot-execution-owner-key",
                    key_version=1,
                )
                self.assertEqual(built["state"], "BLOCKED")

    def test_window_is_bounded_to_two_minutes(self):
        _, _, built, _ = built_request(
            expires_at="2026-10-05T19:45:00Z",
        )
        self.assertEqual(built["state"], "BLOCKED")
        self.assertIn(
            "ACTIVATION_EXECUTION_WINDOW_TOO_LONG",
            built["blockers"],
        )

    def test_expired_request_blocks(self):
        _, _, built, _ = built_request(
            issued_at="2026-10-05T19:30:00Z",
            expires_at="2026-10-05T19:31:00Z",
        )
        self.assertEqual(built["state"], "BLOCKED")
        self.assertIn(
            "ACTIVATION_EXECUTION_REQUEST_EXPIRED",
            built["blockers"],
        )

    def test_valid_authorize_signature_stays_pending_persistence(self):
        private, registry, built, pf = built_request()
        signature = b64url(
            private.sign(canonical_execution_decision_bytes(built["request"]))
        )
        with tempfile.TemporaryDirectory() as td:
            result = verify_activation_execution_decision(
                built["request"],
                execution_signature_b64=signature,
                execution_preflight=pf,
                owner_trust_roots=registry,
                nonce_registry=PersistentNonceRegistry(
                    Path(td) / "execution-nonces.sqlite3"
                ),
                now_ts=NOW,
            )
        self.assertEqual(
            result["state"],
            "ACTIVATION_EXECUTION_AUTHORIZATION_VERIFIED_PENDING_PERSISTENCE",
        )
        self.assertTrue(result["owner_execution_identity_verified"])
        self.assertTrue(result["owner_execution_signature_verified"])
        self.assertTrue(result["execution_decision_verified"])
        self.assertTrue(result["execution_authorization_intent"])
        self.assertFalse(result["execution_denial_intent"])
        self.assertTrue(result["requires_execution_record_persistence"])
        self.assertTrue(
            result["eligible_for_activation_command_planning_after_persistence"]
        )
        self.assertFalse(result["execution_record_persisted"])
        self.assertFalse(result["activation_command_generated"])
        self.assertFalse(result["activation_command_executed"])
        self.assertFalse(result["pilot_activation_authorized"])
        self.assertFalse(result["pilot_activated"])
        self.assertFalse(result["executes_action"])
        self.assertFalse(
            result["generic_chat_instruction_accepted_as_execution"]
        )

    def test_valid_deny_signature_is_not_command_planning_eligible(self):
        private, registry, built, pf = built_request(
            "DENY_ACTIVATION_EXECUTION"
        )
        signature = b64url(
            private.sign(canonical_execution_decision_bytes(built["request"]))
        )
        with tempfile.TemporaryDirectory() as td:
            result = verify_activation_execution_decision(
                built["request"],
                execution_signature_b64=signature,
                execution_preflight=pf,
                owner_trust_roots=registry,
                nonce_registry=PersistentNonceRegistry(
                    Path(td) / "execution-nonces.sqlite3"
                ),
                now_ts=NOW,
            )
        self.assertEqual(
            result["state"],
            "ACTIVATION_EXECUTION_DENIAL_VERIFIED_PENDING_PERSISTENCE",
        )
        self.assertFalse(result["execution_authorization_intent"])
        self.assertTrue(result["execution_denial_intent"])
        self.assertFalse(
            result["eligible_for_activation_command_planning_after_persistence"]
        )
        self.assertFalse(result["activation_command_generated"])
        self.assertFalse(result["executes_action"])

    def test_invalid_signature_blocks(self):
        _, registry, built, pf = built_request()
        other = Ed25519PrivateKey.generate()
        signature = b64url(
            other.sign(canonical_execution_decision_bytes(built["request"]))
        )
        with tempfile.TemporaryDirectory() as td:
            result = verify_activation_execution_decision(
                built["request"],
                execution_signature_b64=signature,
                execution_preflight=pf,
                owner_trust_roots=registry,
                nonce_registry=PersistentNonceRegistry(
                    Path(td) / "execution-nonces.sqlite3"
                ),
                now_ts=NOW,
            )
        self.assertEqual(result["state"], "BLOCKED")
        self.assertIn(
            "ACTIVATION_EXECUTION_SIGNATURE_INVALID",
            result["blockers"],
        )

    def test_preflight_mutation_after_request_blocks_rebuild(self):
        private, registry, built, pf = built_request()
        signature = b64url(
            private.sign(canonical_execution_decision_bytes(built["request"]))
        )
        mutated = dict(pf)
        mutated["execution_preflight_digest"] = "sha256:" + "9" * 64
        with tempfile.TemporaryDirectory() as td:
            result = verify_activation_execution_decision(
                built["request"],
                execution_signature_b64=signature,
                execution_preflight=mutated,
                owner_trust_roots=registry,
                nonce_registry=PersistentNonceRegistry(
                    Path(td) / "execution-nonces.sqlite3"
                ),
                now_ts=NOW,
            )
        self.assertEqual(result["state"], "BLOCKED")
        self.assertIn(
            "ACTIVATION_EXECUTION_REQUEST_REBUILD_MISMATCH",
            result["blockers"],
        )

    def test_replay_is_blocked_durably(self):
        private, registry, built, pf = built_request()
        signature = b64url(
            private.sign(canonical_execution_decision_bytes(built["request"]))
        )
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "execution-nonces.sqlite3"
            first = verify_activation_execution_decision(
                built["request"],
                execution_signature_b64=signature,
                execution_preflight=pf,
                owner_trust_roots=registry,
                nonce_registry=PersistentNonceRegistry(path),
                now_ts=NOW,
            )
            second = verify_activation_execution_decision(
                built["request"],
                execution_signature_b64=signature,
                execution_preflight=pf,
                owner_trust_roots=registry,
                nonce_registry=PersistentNonceRegistry(path),
                now_ts=NOW,
            )
        self.assertTrue(first["execution_decision_verified"])
        self.assertEqual(second["state"], "BLOCKED")
        self.assertIn(
            "ACTIVATION_EXECUTION_NONCE_REPLAYED",
            second["blockers"],
        )

    def test_revoked_owner_key_blocks_request(self):
        _, registry = trust_material(status="REVOKED")
        built = build_activation_execution_request(
            execution_preflight=preflight(),
            owner_trust_roots=registry,
            now_ts=NOW,
            decision="AUTHORIZE_ACTIVATION_EXECUTION",
            ceremony_id="pilot-execution-ceremony-001",
            nonce="pilot-execution-nonce-0001",
            issued_at=ISSUED,
            expires_at=EXPIRES,
            key_id="pilot-execution-owner-key",
            key_version=1,
        )
        self.assertEqual(built["state"], "BLOCKED")
        self.assertIn("OWNER_TRUST_KEY_REVOKED", built["blockers"])

    def test_verified_execution_never_generates_or_runs_command(self):
        private, registry, built, pf = built_request()
        signature = b64url(
            private.sign(canonical_execution_decision_bytes(built["request"]))
        )
        with tempfile.TemporaryDirectory() as td:
            result = verify_activation_execution_decision(
                built["request"],
                execution_signature_b64=signature,
                execution_preflight=pf,
                owner_trust_roots=registry,
                nonce_registry=PersistentNonceRegistry(
                    Path(td) / "execution-nonces.sqlite3"
                ),
                now_ts=NOW,
            )
        for key in (
            "execution_record_persisted",
            "activation_command_generated",
            "activation_command_executed",
            "pilot_activation_authorized",
            "pilot_activated",
            "customer_contact_authorized",
            "billing_authorized",
            "provisioning_authorized",
            "deploy_authorized",
            "production_mutation_authorized",
            "external_action_executed",
            "network_called",
            "executes_action",
        ):
            self.assertFalse(result[key], key)


if __name__ == "__main__":
    unittest.main()
