from __future__ import annotations

import base64
import tempfile
import unittest
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
)

from atlasquant_aion_b2b_pilot_activation_ceremony import (
    build_pilot_activation_request,
    canonical_activation_decision_bytes,
    verify_pilot_activation_decision,
)
from atlasquant_aion_nonce_registry import PersistentNonceRegistry
from atlasquant_aion_trust_root import TrustRootRegistry

NOW = "2026-10-05T18:30:30Z"
ISSUED = "2026-10-05T18:30:00Z"
EXPIRES = "2026-10-05T18:32:00Z"


def b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def trust_material():
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
                    "key_id": "pilot-activation-owner-key",
                    "key_version": 1,
                    "algorithm": "Ed25519",
                    "public_key_b64": b64url(public),
                    "status": "ACTIVE",
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
        "schema": "ATLASQUANT_AION_B2B_PILOT_ACTIVATION_PREFLIGHT_V1",
        "state": "READY_FOR_ACTIVATION_CEREMONY",
        "scope": {
            "owner_id": "HUMAN_OWNER",
            "tenant_id": "atlasquant-owner",
            "workspace_id": "business",
        },
        "candidate_id": "candidate-001",
        "proposal_id": "proposal-001",
        "pilot_id": "pilot-001",
        "blockers": [],
        "environment_digest": "sha256:" + "e" * 64,
        "preflight_digest": "sha256:" + "f" * 64,
        "activation_ceremony_eligible": True,
        "activation_request_issued": False,
        "owner_activation_signature_required": True,
        "owner_activation_signature_verified": False,
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


def built_request(decision="AUTHORIZE_PILOT_ACTIVATION", **overrides):
    private, registry = trust_material()
    args = {
        "activation_preflight": preflight(),
        "owner_trust_roots": registry,
        "now_ts": NOW,
        "decision": decision,
        "ceremony_id": "pilot-activation-ceremony-001",
        "nonce": "pilot-activation-nonce-0001",
        "issued_at": ISSUED,
        "expires_at": EXPIRES,
        "key_id": "pilot-activation-owner-key",
        "key_version": 1,
    }
    args.update(overrides)
    built = build_pilot_activation_request(**args)
    return private, registry, built, args["activation_preflight"]


class AionB2BPilotActivationCeremonyTests(unittest.TestCase):
    def test_valid_authorize_request_is_signature_ready_but_not_authorized(self):
        _, _, built, _ = built_request()
        self.assertEqual(
            built["state"],
            "READY_FOR_EXTERNAL_OWNER_ACTIVATION_SIGNATURE",
        )
        self.assertFalse(built["blockers"])
        self.assertEqual(built["activation_decision"], "UNDECIDED")
        self.assertFalse(built["activation_decision_verified"])
        self.assertFalse(built["activation_record_persisted"])
        self.assertFalse(built["pilot_activation_authorized"])
        self.assertFalse(built["pilot_activated"])
        self.assertFalse(built["executes_action"])
        self.assertEqual(
            built["request"]["decision"],
            "AUTHORIZE_PILOT_ACTIVATION",
        )
        self.assertEqual(
            built["request"]["preflight_digest"],
            "sha256:" + "f" * 64,
        )

    def test_generic_chat_instruction_is_not_activation_authorization(self):
        _, _, built, _ = built_request("vamos lá")
        self.assertEqual(built["state"], "BLOCKED")
        self.assertIn(
            "PILOT_ACTIVATION_DECISION_INVALID",
            built["blockers"],
        )

    def test_only_canonical_activation_choices_are_accepted(self):
        for decision in (
            "approve",
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
                    "PILOT_ACTIVATION_DECISION_INVALID",
                    built["blockers"],
                )

    def test_preflight_must_be_ready_and_authority_free(self):
        for key, value in (
            ("state", "BLOCKED"),
            ("activation_ceremony_eligible", False),
            ("activation_request_issued", True),
            ("owner_activation_signature_verified", True),
            ("pilot_activation_authorized", True),
            ("pilot_activated", True),
            ("billing_authorized", True),
            ("provisioning_authorized", True),
            ("deploy_authorized", True),
            ("production_mutation_authorized", True),
            ("executes_action", True),
        ):
            with self.subTest(key=key):
                bad = preflight(**{key: value})
                _, registry = trust_material()
                built = build_pilot_activation_request(
                    activation_preflight=bad,
                    owner_trust_roots=registry,
                    now_ts=NOW,
                    decision="AUTHORIZE_PILOT_ACTIVATION",
                    ceremony_id="pilot-activation-ceremony-001",
                    nonce="pilot-activation-nonce-0001",
                    issued_at=ISSUED,
                    expires_at=EXPIRES,
                    key_id="pilot-activation-owner-key",
                    key_version=1,
                )
                self.assertEqual(built["state"], "BLOCKED")

    def test_window_is_bounded_to_three_minutes(self):
        _, _, built, _ = built_request(
            expires_at="2026-10-05T18:40:00Z",
        )
        self.assertEqual(built["state"], "BLOCKED")
        self.assertIn(
            "PILOT_ACTIVATION_WINDOW_TOO_LONG",
            built["blockers"],
        )

    def test_expired_request_blocks(self):
        _, _, built, _ = built_request(
            issued_at="2026-10-05T18:20:00Z",
            expires_at="2026-10-05T18:22:00Z",
        )
        self.assertEqual(built["state"], "BLOCKED")
        self.assertIn(
            "PILOT_ACTIVATION_REQUEST_EXPIRED",
            built["blockers"],
        )

    def test_valid_authorize_signature_stays_pending_persistence(self):
        private, registry, built, pf = built_request()
        signature = b64url(
            private.sign(
                canonical_activation_decision_bytes(
                    built["request"]
                )
            )
        )
        with tempfile.TemporaryDirectory() as td:
            result = verify_pilot_activation_decision(
                built["request"],
                activation_signature_b64=signature,
                activation_preflight=pf,
                owner_trust_roots=registry,
                nonce_registry=PersistentNonceRegistry(
                    Path(td) / "activation-nonces.sqlite3"
                ),
                now_ts=NOW,
            )
        self.assertEqual(
            result["state"],
            "ACTIVATION_AUTHORIZATION_VERIFIED_PENDING_PERSISTENCE",
        )
        self.assertTrue(result["owner_activation_identity_verified"])
        self.assertTrue(result["owner_activation_signature_verified"])
        self.assertTrue(result["activation_decision_verified"])
        self.assertTrue(result["activation_authorization_intent"])
        self.assertFalse(result["activation_denial_intent"])
        self.assertTrue(result["requires_activation_record_persistence"])
        self.assertTrue(
            result["eligible_for_activation_execution_after_persistence"]
        )
        self.assertFalse(result["activation_record_persisted"])
        self.assertFalse(result["pilot_activation_authorized"])
        self.assertFalse(result["pilot_activated"])
        self.assertFalse(result["executes_action"])
        self.assertFalse(
            result["generic_chat_instruction_accepted_as_activation"]
        )

    def test_valid_deny_signature_is_not_execution_eligible(self):
        private, registry, built, pf = built_request(
            "DENY_PILOT_ACTIVATION"
        )
        signature = b64url(
            private.sign(
                canonical_activation_decision_bytes(
                    built["request"]
                )
            )
        )
        with tempfile.TemporaryDirectory() as td:
            result = verify_pilot_activation_decision(
                built["request"],
                activation_signature_b64=signature,
                activation_preflight=pf,
                owner_trust_roots=registry,
                nonce_registry=PersistentNonceRegistry(
                    Path(td) / "activation-nonces.sqlite3"
                ),
                now_ts=NOW,
            )
        self.assertEqual(
            result["state"],
            "ACTIVATION_DENIAL_VERIFIED_PENDING_PERSISTENCE",
        )
        self.assertFalse(result["activation_authorization_intent"])
        self.assertTrue(result["activation_denial_intent"])
        self.assertFalse(
            result["eligible_for_activation_execution_after_persistence"]
        )
        self.assertFalse(result["pilot_activation_authorized"])
        self.assertFalse(result["executes_action"])

    def test_invalid_signature_blocks(self):
        _, registry, built, pf = built_request()
        other = Ed25519PrivateKey.generate()
        signature = b64url(
            other.sign(
                canonical_activation_decision_bytes(
                    built["request"]
                )
            )
        )
        with tempfile.TemporaryDirectory() as td:
            result = verify_pilot_activation_decision(
                built["request"],
                activation_signature_b64=signature,
                activation_preflight=pf,
                owner_trust_roots=registry,
                nonce_registry=PersistentNonceRegistry(
                    Path(td) / "activation-nonces.sqlite3"
                ),
                now_ts=NOW,
            )
        self.assertEqual(result["state"], "BLOCKED")
        self.assertIn(
            "PILOT_ACTIVATION_SIGNATURE_INVALID",
            result["blockers"],
        )

    def test_preflight_mutation_after_request_blocks_rebuild(self):
        private, registry, built, pf = built_request()
        signature = b64url(
            private.sign(
                canonical_activation_decision_bytes(
                    built["request"]
                )
            )
        )
        mutated = dict(pf)
        mutated["preflight_digest"] = "sha256:" + "9" * 64
        with tempfile.TemporaryDirectory() as td:
            result = verify_pilot_activation_decision(
                built["request"],
                activation_signature_b64=signature,
                activation_preflight=mutated,
                owner_trust_roots=registry,
                nonce_registry=PersistentNonceRegistry(
                    Path(td) / "activation-nonces.sqlite3"
                ),
                now_ts=NOW,
            )
        self.assertEqual(result["state"], "BLOCKED")
        self.assertIn(
            "PILOT_ACTIVATION_REQUEST_REBUILD_MISMATCH",
            result["blockers"],
        )

    def test_replay_is_blocked_durably(self):
        private, registry, built, pf = built_request()
        signature = b64url(
            private.sign(
                canonical_activation_decision_bytes(
                    built["request"]
                )
            )
        )
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "activation-nonces.sqlite3"
            first = verify_pilot_activation_decision(
                built["request"],
                activation_signature_b64=signature,
                activation_preflight=pf,
                owner_trust_roots=registry,
                nonce_registry=PersistentNonceRegistry(path),
                now_ts=NOW,
            )
            second = verify_pilot_activation_decision(
                built["request"],
                activation_signature_b64=signature,
                activation_preflight=pf,
                owner_trust_roots=registry,
                nonce_registry=PersistentNonceRegistry(path),
                now_ts=NOW,
            )
        self.assertTrue(first["activation_decision_verified"])
        self.assertEqual(second["state"], "BLOCKED")
        self.assertIn(
            "PILOT_ACTIVATION_NONCE_REPLAYED",
            second["blockers"],
        )

    def test_verified_authorization_never_executes_external_actions(self):
        private, registry, built, pf = built_request()
        signature = b64url(
            private.sign(
                canonical_activation_decision_bytes(
                    built["request"]
                )
            )
        )
        with tempfile.TemporaryDirectory() as td:
            result = verify_pilot_activation_decision(
                built["request"],
                activation_signature_b64=signature,
                activation_preflight=pf,
                owner_trust_roots=registry,
                nonce_registry=PersistentNonceRegistry(
                    Path(td) / "activation-nonces.sqlite3"
                ),
                now_ts=NOW,
            )
        for key in (
            "activation_record_persisted",
            "pilot_activation_authorized",
            "pilot_activated",
            "customer_contact_authorized",
            "contract_signature_authorized",
            "billing_authorized",
            "spend_authorized",
            "provisioning_authorized",
            "deploy_authorized",
            "crm_write_authorized",
            "provider_called",
            "production_mutation_authorized",
            "external_action_executed",
            "network_called",
            "executes_action",
        ):
            self.assertFalse(result[key], key)


if __name__ == "__main__":
    unittest.main()
