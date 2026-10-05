from __future__ import annotations

import base64
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from atlasquant_aion_b2b_pilot_activation_writer_attestation import (
    build_activation_writer_attestation_request,
    canonical_activation_writer_bytes,
    verify_activation_writer_attestation,
)
from atlasquant_aion_nonce_registry import PersistentNonceRegistry
from atlasquant_aion_trust_root import TrustRootRegistry

NOW = "2026-10-05T19:10:30Z"
ISSUED = "2026-10-05T19:10:00Z"
EXPIRES = "2026-10-05T19:12:00Z"


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
                    "key_id": "activation-writer-key",
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


def receipt(**overrides):
    body = {
        "schema": "ATLASQUANT_AION_B2B_PILOT_ACTIVATION_CHECKPOINT_RECEIPT_V1",
        "status": "CONFIRMED",
        "storage_target": "CHECKPOINT_MASTER",
        "write_mode": "EXPLICIT_AUTHORIZED_APPEND",
        "namespace": "aion_b2b_pilot_activation_authorization",
        "event_id": "aion-b2b-pilot-activation-0123456789abcdef",
        "base_revision": 1,
        "revision": 2,
        "patch_digest": "sha256:" + "1" * 64,
        "before_checkpoint_digest": "sha256:" + "2" * 64,
        "after_checkpoint_digest": "sha256:" + "3" * 64,
        "activation_record_digest": "sha256:" + "4" * 64,
        "pilot_id": "pilot-001",
        "persisted_at": "2026-10-05T19:09:30Z",
        "writer_ref": "checkpoint-writer:activation-path",
        "writer_identity_verified": False,
        "pilot_activation_authorized": False,
        "pilot_activated": False,
        "external_action_executed": False,
    }
    body.update(overrides)
    raw = {k: v for k, v in body.items() if k != "receipt_digest"}
    body["receipt_digest"] = digest(raw)
    return body


def built_request(receipt_value=None, **overrides):
    private, registry = trust_material()
    args = {
        "checkpoint_write_receipt": receipt_value or receipt(),
        "writer_trust_roots": registry,
        "now_ts": NOW,
        "ceremony_id": "activation-writer-ceremony-001",
        "nonce": "activation-writer-nonce-0001",
        "issued_at": ISSUED,
        "expires_at": EXPIRES,
        "key_id": "activation-writer-key",
        "key_version": 1,
    }
    args.update(overrides)
    built = build_activation_writer_attestation_request(**args)
    return private, registry, built, args["checkpoint_write_receipt"]


class AionB2BPilotActivationWriterAttestationTests(unittest.TestCase):
    def test_valid_receipt_builds_external_signature_request(self):
        _, _, built, raw_receipt = built_request()
        self.assertEqual(
            built["state"],
            "READY_FOR_EXTERNAL_ACTIVATION_WRITER_SIGNATURE",
        )
        self.assertEqual(
            built["request"]["receipt_digest"],
            raw_receipt["receipt_digest"],
        )
        self.assertFalse(built["writer_identity_verified"])
        self.assertFalse(built["pilot_activation_authorized"])
        self.assertFalse(built["executes_action"])

    def test_valid_signature_attests_writer_without_activation(self):
        private, registry, built, raw_receipt = built_request()
        signature = b64url(
            private.sign(canonical_activation_writer_bytes(built["request"]))
        )
        with tempfile.TemporaryDirectory() as td:
            result = verify_activation_writer_attestation(
                built["request"],
                writer_signature_b64=signature,
                checkpoint_write_receipt=raw_receipt,
                writer_trust_roots=registry,
                nonce_registry=PersistentNonceRegistry(
                    Path(td) / "activation-writer.sqlite3"
                ),
                now_ts=NOW,
            )
        self.assertEqual(
            result["state"],
            "ACTIVATION_CHECKPOINT_WRITER_AUTHORITY_ATTESTED",
        )
        self.assertTrue(result["writer_identity_verified"])
        self.assertTrue(result["writer_authority_verified"])
        self.assertTrue(result["receipt_binding_verified"])
        self.assertTrue(result["nonce_registered"])
        self.assertFalse(result["pilot_activation_authorized"])
        self.assertFalse(result["pilot_activated"])
        self.assertFalse(result["checkpoint_write_performed"])
        self.assertFalse(result["executes_action"])

    def test_invalid_signature_blocks(self):
        _, registry, built, raw_receipt = built_request()
        other = Ed25519PrivateKey.generate()
        signature = b64url(
            other.sign(canonical_activation_writer_bytes(built["request"]))
        )
        with tempfile.TemporaryDirectory() as td:
            result = verify_activation_writer_attestation(
                built["request"],
                writer_signature_b64=signature,
                checkpoint_write_receipt=raw_receipt,
                writer_trust_roots=registry,
                nonce_registry=PersistentNonceRegistry(
                    Path(td) / "activation-writer.sqlite3"
                ),
                now_ts=NOW,
            )
        self.assertEqual(result["state"], "BLOCKED")
        self.assertIn("ACTIVATION_WRITER_SIGNATURE_INVALID", result["blockers"])

    def test_receipt_mutation_after_request_blocks(self):
        private, registry, built, raw_receipt = built_request()
        signature = b64url(
            private.sign(canonical_activation_writer_bytes(built["request"]))
        )
        mutated = receipt(
            activation_record_digest="sha256:" + "9" * 64
        )
        with tempfile.TemporaryDirectory() as td:
            result = verify_activation_writer_attestation(
                built["request"],
                writer_signature_b64=signature,
                checkpoint_write_receipt=mutated,
                writer_trust_roots=registry,
                nonce_registry=PersistentNonceRegistry(
                    Path(td) / "activation-writer.sqlite3"
                ),
                now_ts=NOW,
            )
        self.assertEqual(result["state"], "BLOCKED")
        self.assertIn(
            "ACTIVATION_WRITER_REQUEST_REBUILD_MISMATCH",
            result["blockers"],
        )

    def test_preverified_receipt_is_rejected(self):
        _, registry = trust_material()
        built = build_activation_writer_attestation_request(
            checkpoint_write_receipt=receipt(
                writer_identity_verified=True
            ),
            writer_trust_roots=registry,
            now_ts=NOW,
            ceremony_id="activation-writer-ceremony-001",
            nonce="activation-writer-nonce-0001",
            issued_at=ISSUED,
            expires_at=EXPIRES,
            key_id="activation-writer-key",
            key_version=1,
        )
        self.assertEqual(built["state"], "BLOCKED")
        self.assertIn(
            "ACTIVATION_RECEIPT_PREVERIFIED_WRITER_FORBIDDEN",
            built["blockers"],
        )

    def test_expired_request_blocks(self):
        _, _, built, _ = built_request(
            issued_at="2026-10-05T19:00:00Z",
            expires_at="2026-10-05T19:02:00Z",
        )
        self.assertEqual(built["state"], "BLOCKED")
        self.assertIn(
            "ACTIVATION_WRITER_REQUEST_EXPIRED",
            built["blockers"],
        )

    def test_replay_is_blocked_durably(self):
        private, registry, built, raw_receipt = built_request()
        signature = b64url(
            private.sign(canonical_activation_writer_bytes(built["request"]))
        )
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "activation-writer.sqlite3"
            first = verify_activation_writer_attestation(
                built["request"],
                writer_signature_b64=signature,
                checkpoint_write_receipt=raw_receipt,
                writer_trust_roots=registry,
                nonce_registry=PersistentNonceRegistry(path),
                now_ts=NOW,
            )
            second = verify_activation_writer_attestation(
                built["request"],
                writer_signature_b64=signature,
                checkpoint_write_receipt=raw_receipt,
                writer_trust_roots=registry,
                nonce_registry=PersistentNonceRegistry(path),
                now_ts=NOW,
            )
        self.assertTrue(first["writer_authority_verified"])
        self.assertEqual(second["state"], "BLOCKED")
        self.assertIn("ACTIVATION_WRITER_NONCE_REPLAYED", second["blockers"])

    def test_revoked_writer_key_blocks(self):
        _, registry = trust_material(status="REVOKED")
        built = build_activation_writer_attestation_request(
            checkpoint_write_receipt=receipt(),
            writer_trust_roots=registry,
            now_ts=NOW,
            ceremony_id="activation-writer-ceremony-001",
            nonce="activation-writer-nonce-0001",
            issued_at=ISSUED,
            expires_at=EXPIRES,
            key_id="activation-writer-key",
            key_version=1,
        )
        self.assertEqual(built["state"], "BLOCKED")
        self.assertIn("WRITER_TRUST_KEY_REVOKED", built["blockers"])

    def test_success_never_authorizes_external_actions(self):
        private, registry, built, raw_receipt = built_request()
        signature = b64url(
            private.sign(canonical_activation_writer_bytes(built["request"]))
        )
        with tempfile.TemporaryDirectory() as td:
            result = verify_activation_writer_attestation(
                built["request"],
                writer_signature_b64=signature,
                checkpoint_write_receipt=raw_receipt,
                writer_trust_roots=registry,
                nonce_registry=PersistentNonceRegistry(
                    Path(td) / "activation-writer.sqlite3"
                ),
                now_ts=NOW,
            )
        for key in (
            "pilot_activation_authorized",
            "pilot_activated",
            "checkpoint_write_performed",
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
