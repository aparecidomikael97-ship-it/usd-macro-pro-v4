from __future__ import annotations

import base64
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
)

from atlasquant_aion_b2b_owner_renewal_persistence_attestation import (
    RECEIPT_SCHEMA,
)
from atlasquant_aion_b2b_owner_renewal_persistence_plan import NAMESPACE
from atlasquant_aion_b2b_owner_renewal_writer_attestation import (
    canonical_owner_renewal_writer_bytes,
    build_owner_renewal_writer_attestation_request,
    verify_owner_renewal_writer_attestation,
)
from atlasquant_aion_nonce_registry import PersistentNonceRegistry
from atlasquant_aion_trust_root import TrustRootRegistry

NOW = "2026-10-05T21:40:30Z"
ISSUED = "2026-10-05T21:40:00Z"
EXPIRES = "2026-10-05T21:42:00Z"


def b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


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
                    "key_id": "checkpoint-writer-key",
                    "key_version": 1,
                    "algorithm": "Ed25519",
                    "public_key_b64": b64url(public),
                    "status": status,
                    "not_before": "2026-10-05T20:00:00Z",
                    "not_after": "2027-10-05T00:00:00Z",
                }
            ],
            "revoked_key_ids": [],
        }
    )
    return private, registry


def receipt(**overrides):
    body = {
        "schema": RECEIPT_SCHEMA,
        "status": "CONFIRMED",
        "storage_target": "CHECKPOINT_MASTER",
        "write_mode": "EXPLICIT_AUTHORIZED_APPEND",
        "namespace": NAMESPACE,
        "event_id": (
            "aion-b2b-owner-renewal-decision-"
            "0123456789abcdef0123456789abcdef"
        ),
        "base_revision": 0,
        "revision": 1,
        "patch_digest": "sha256:" + "1" * 64,
        "before_checkpoint_digest": "sha256:" + "2" * 64,
        "after_checkpoint_digest": "sha256:" + "3" * 64,
        "decision_record_digest": "sha256:" + "4" * 64,
        "customer_id": "customer-a",
        "pilot_id": "pilot-a",
        "requested_choice": "RENEW_AS_IS_REVIEW",
        "persisted_at": "2026-10-05T21:39:30Z",
        "writer_ref": "checkpoint-writer:authorized-path",
        "writer_identity_verified": False,
        "business_action_authorized": False,
        "external_action_executed": False,
    }
    body.update(overrides)
    no_digest = {
        key: value
        for key, value in body.items()
        if key != "receipt_digest"
    }
    body["receipt_digest"] = digest(no_digest)
    return body


def built_request(receipt_value=None, **overrides):
    private, registry = trust_material()
    args = {
        "checkpoint_write_receipt": receipt_value or receipt(),
        "writer_trust_roots": registry,
        "now_ts": NOW,
        "ceremony_id": "renewal-writer-ceremony-001",
        "nonce": "renewal-writer-nonce-0001",
        "issued_at": ISSUED,
        "expires_at": EXPIRES,
        "key_id": "checkpoint-writer-key",
        "key_version": 1,
    }
    args.update(overrides)
    built = build_owner_renewal_writer_attestation_request(**args)
    return private, registry, built, args["checkpoint_write_receipt"]


class OwnerRenewalWriterAttestationTests(unittest.TestCase):
    def test_valid_receipt_builds_signature_request(self):
        _, _, built, raw = built_request()
        self.assertEqual(
            built["state"],
            "READY_FOR_EXTERNAL_CHECKPOINT_WRITER_SIGNATURE",
        )
        self.assertEqual(
            built["request"]["receipt_digest"],
            raw["receipt_digest"],
        )
        self.assertEqual(
            built["request"]["requested_choice"],
            "RENEW_AS_IS_REVIEW",
        )
        self.assertFalse(built["writer_identity_verified"])
        self.assertFalse(built["business_action_authorized"])

    def test_valid_signature_attests_writer_only(self):
        private, registry, built, raw = built_request()
        signature = b64url(
            private.sign(
                canonical_owner_renewal_writer_bytes(
                    built["request"]
                )
            )
        )
        with tempfile.TemporaryDirectory() as td:
            result = verify_owner_renewal_writer_attestation(
                built["request"],
                writer_signature_b64=signature,
                checkpoint_write_receipt=raw,
                writer_trust_roots=registry,
                nonce_registry=PersistentNonceRegistry(
                    Path(td) / "writer-nonces.sqlite3"
                ),
                now_ts=NOW,
            )
        self.assertEqual(
            result["state"],
            "CHECKPOINT_WRITER_AUTHORITY_ATTESTED",
        )
        self.assertTrue(result["writer_identity_verified"])
        self.assertTrue(result["writer_authority_verified"])
        self.assertTrue(result["receipt_binding_verified"])
        self.assertTrue(result["nonce_registered"])
        self.assertEqual(result["customer_id"], "customer-a")
        self.assertEqual(result["pilot_id"], "pilot-a")
        self.assertFalse(result["checkpoint_write_performed"])
        self.assertFalse(result["renewal_authorized"])
        self.assertFalse(result["executes_action"])

    def test_invalid_signature_blocks(self):
        _, registry, built, raw = built_request()
        other = Ed25519PrivateKey.generate()
        signature = b64url(
            other.sign(
                canonical_owner_renewal_writer_bytes(
                    built["request"]
                )
            )
        )
        with tempfile.TemporaryDirectory() as td:
            result = verify_owner_renewal_writer_attestation(
                built["request"],
                writer_signature_b64=signature,
                checkpoint_write_receipt=raw,
                writer_trust_roots=registry,
                nonce_registry=PersistentNonceRegistry(
                    Path(td) / "writer-nonces.sqlite3"
                ),
                now_ts=NOW,
            )
        self.assertEqual(result["state"], "BLOCKED")
        self.assertIn(
            "CHECKPOINT_WRITER_SIGNATURE_INVALID",
            result["blockers"],
        )

    def test_receipt_mutation_after_request_blocks(self):
        private, registry, built, raw = built_request()
        signature = b64url(
            private.sign(
                canonical_owner_renewal_writer_bytes(
                    built["request"]
                )
            )
        )
        mutated = receipt(
            requested_choice="NON_RENEWAL_REVIEW"
        )
        with tempfile.TemporaryDirectory() as td:
            result = verify_owner_renewal_writer_attestation(
                built["request"],
                writer_signature_b64=signature,
                checkpoint_write_receipt=mutated,
                writer_trust_roots=registry,
                nonce_registry=PersistentNonceRegistry(
                    Path(td) / "writer-nonces.sqlite3"
                ),
                now_ts=NOW,
            )
        self.assertEqual(result["state"], "BLOCKED")
        self.assertIn(
            "CHECKPOINT_WRITER_REQUEST_REBUILD_MISMATCH",
            result["blockers"],
        )

    def test_receipt_cannot_arrive_preverified(self):
        _, registry = trust_material()
        raw = receipt(writer_identity_verified=True)
        built = build_owner_renewal_writer_attestation_request(
            checkpoint_write_receipt=raw,
            writer_trust_roots=registry,
            now_ts=NOW,
            ceremony_id="renewal-writer-ceremony-001",
            nonce="renewal-writer-nonce-0001",
            issued_at=ISSUED,
            expires_at=EXPIRES,
            key_id="checkpoint-writer-key",
            key_version=1,
        )
        self.assertEqual(built["state"], "BLOCKED")
        self.assertIn(
            "CHECKPOINT_RECEIPT_PREVERIFIED_WRITER_FORBIDDEN",
            built["blockers"],
        )

    def test_receipt_cannot_claim_business_authority(self):
        _, registry = trust_material()
        raw = receipt(business_action_authorized=True)
        built = build_owner_renewal_writer_attestation_request(
            checkpoint_write_receipt=raw,
            writer_trust_roots=registry,
            now_ts=NOW,
            ceremony_id="renewal-writer-ceremony-001",
            nonce="renewal-writer-nonce-0001",
            issued_at=ISSUED,
            expires_at=EXPIRES,
            key_id="checkpoint-writer-key",
            key_version=1,
        )
        self.assertEqual(built["state"], "BLOCKED")
        self.assertIn(
            "CHECKPOINT_RECEIPT_ACTION_AUTHORITY_UNSAFE",
            built["blockers"],
        )

    def test_expired_request_blocks(self):
        _, _, built, _ = built_request(
            issued_at="2026-10-05T21:30:00Z",
            expires_at="2026-10-05T21:32:00Z",
        )
        self.assertEqual(built["state"], "BLOCKED")
        self.assertIn(
            "CHECKPOINT_WRITER_REQUEST_EXPIRED",
            built["blockers"],
        )

    def test_window_over_three_minutes_blocks(self):
        _, _, built, _ = built_request(
            expires_at="2026-10-05T21:50:00Z",
        )
        self.assertEqual(built["state"], "BLOCKED")
        self.assertIn(
            "CHECKPOINT_WRITER_WINDOW_TOO_LONG",
            built["blockers"],
        )

    def test_replay_blocks(self):
        private, registry, built, raw = built_request()
        signature = b64url(
            private.sign(
                canonical_owner_renewal_writer_bytes(
                    built["request"]
                )
            )
        )
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "writer-nonces.sqlite3"
            first = verify_owner_renewal_writer_attestation(
                built["request"],
                writer_signature_b64=signature,
                checkpoint_write_receipt=raw,
                writer_trust_roots=registry,
                nonce_registry=PersistentNonceRegistry(path),
                now_ts=NOW,
            )
            second = verify_owner_renewal_writer_attestation(
                built["request"],
                writer_signature_b64=signature,
                checkpoint_write_receipt=raw,
                writer_trust_roots=registry,
                nonce_registry=PersistentNonceRegistry(path),
                now_ts=NOW,
            )
        self.assertTrue(first["writer_authority_verified"])
        self.assertEqual(second["state"], "BLOCKED")
        self.assertIn(
            "CHECKPOINT_WRITER_NONCE_REPLAYED",
            second["blockers"],
        )

    def test_revoked_key_blocks_request(self):
        _, registry = trust_material(status="REVOKED")
        built = build_owner_renewal_writer_attestation_request(
            checkpoint_write_receipt=receipt(),
            writer_trust_roots=registry,
            now_ts=NOW,
            ceremony_id="renewal-writer-ceremony-001",
            nonce="renewal-writer-nonce-0001",
            issued_at=ISSUED,
            expires_at=EXPIRES,
            key_id="checkpoint-writer-key",
            key_version=1,
        )
        self.assertEqual(built["state"], "BLOCKED")
        self.assertIn("WRITER_TRUST_KEY_REVOKED", built["blockers"])

    def test_writer_attestation_never_authorizes_business_actions(self):
        private, registry, built, raw = built_request()
        signature = b64url(
            private.sign(
                canonical_owner_renewal_writer_bytes(
                    built["request"]
                )
            )
        )
        with tempfile.TemporaryDirectory() as td:
            result = verify_owner_renewal_writer_attestation(
                built["request"],
                writer_signature_b64=signature,
                checkpoint_write_receipt=raw,
                writer_trust_roots=registry,
                nonce_registry=PersistentNonceRegistry(
                    Path(td) / "writer-nonces.sqlite3"
                ),
                now_ts=NOW,
            )
        for key in (
            "checkpoint_write_performed",
            "business_action_authorized",
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
            "network_called",
            "executes_action",
        ):
            self.assertFalse(result[key], key)


if __name__ == "__main__":
    unittest.main()
