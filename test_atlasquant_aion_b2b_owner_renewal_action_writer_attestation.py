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

from atlasquant_aion_b2b_owner_renewal_action_persistence_attestation import (
    RECEIPT_SCHEMA,
)
from atlasquant_aion_b2b_owner_renewal_action_persistence_plan import NAMESPACE
from atlasquant_aion_b2b_owner_renewal_action_writer_attestation import (
    build_owner_renewal_action_writer_attestation_request,
    canonical_owner_renewal_action_writer_bytes,
    verify_owner_renewal_action_writer_attestation,
)
from atlasquant_aion_nonce_registry import PersistentNonceRegistry
from atlasquant_aion_trust_root import TrustRootRegistry

NOW = "2026-10-05T22:20:30Z"
ISSUED = "2026-10-05T22:20:00Z"
EXPIRES = "2026-10-05T22:22:00Z"


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


def h(char):
    return "sha256:" + char * 64


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
                    "key_id": "renewal-action-writer-key",
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


def receipt(
    decision="AUTHORIZE_BUSINESS_ACTION",
    **overrides,
):
    body = {
        "schema": RECEIPT_SCHEMA,
        "status": "CONFIRMED",
        "storage_target": "CHECKPOINT_MASTER",
        "write_mode": "EXPLICIT_AUTHORIZED_APPEND",
        "namespace": NAMESPACE,
        "event_id": "aion-b2b-owner-renewal-action-0123456789abcdef0123456789abcdef",
        "base_revision": 2,
        "revision": 3,
        "patch_digest": h("1"),
        "before_checkpoint_digest": h("2"),
        "after_checkpoint_digest": h("3"),
        "action_record_digest": h("4"),
        "customer_id": "customer-a",
        "pilot_id": "pilot-a",
        "requested_choice": "RENEW_AS_IS_REVIEW",
        "action_family": "RENEWAL",
        "authorization_decision": decision,
        "persisted_at": "2026-10-05T22:19:30Z",
        "writer_ref": "checkpoint-writer:recurring-action",
        "writer_identity_verified": False,
        "business_action_authorized": False,
        "external_action_executed": False,
    }
    body.update(overrides)
    raw = {k: v for k, v in body.items() if k != "receipt_digest"}
    body["receipt_digest"] = digest(raw)
    return body


def built(raw_receipt=None, **overrides):
    private, registry = trust_material()
    raw_receipt = raw_receipt or receipt()
    args = {
        "checkpoint_write_receipt": raw_receipt,
        "writer_trust_roots": registry,
        "now_ts": NOW,
        "ceremony_id": "renewal-action-writer-ceremony-001",
        "nonce": "renewal-action-writer-nonce-0001",
        "issued_at": ISSUED,
        "expires_at": EXPIRES,
        "key_id": "renewal-action-writer-key",
        "key_version": 1,
    }
    args.update(overrides)
    out = build_owner_renewal_action_writer_attestation_request(**args)
    return private, registry, out, raw_receipt


class OwnerRenewalActionWriterAttestationTests(unittest.TestCase):
    def test_receipt_builds_external_writer_signature_request(self):
        _, _, out, raw_receipt = built()
        self.assertEqual(
            out["state"],
            "READY_FOR_EXTERNAL_ACTION_WRITER_SIGNATURE",
        )
        self.assertEqual(
            out["request"]["receipt_digest"],
            raw_receipt["receipt_digest"],
        )
        self.assertFalse(out["writer_identity_verified"])
        self.assertFalse(out["business_action_authorized"])
        self.assertFalse(out["executes_action"])

    def test_valid_signature_attests_writer_without_business_authority(self):
        private, registry, built_out, raw_receipt = built()
        signature = b64url(
            private.sign(
                canonical_owner_renewal_action_writer_bytes(
                    built_out["request"]
                )
            )
        )
        with tempfile.TemporaryDirectory() as td:
            result = verify_owner_renewal_action_writer_attestation(
                built_out["request"],
                writer_signature_b64=signature,
                checkpoint_write_receipt=raw_receipt,
                writer_trust_roots=registry,
                nonce_registry=PersistentNonceRegistry(
                    Path(td) / "renewal-action-writer.sqlite3"
                ),
                now_ts=NOW,
            )
        self.assertEqual(
            result["state"],
            "ACTION_CHECKPOINT_WRITER_AUTHORITY_ATTESTED",
        )
        self.assertTrue(result["writer_identity_verified"])
        self.assertTrue(result["writer_authority_verified"])
        self.assertTrue(result["receipt_binding_verified"])
        self.assertTrue(result["nonce_registered"])
        self.assertTrue(result["eligible_for_action_execution_preflight"])
        self.assertFalse(result["checkpoint_write_performed"])
        self.assertFalse(result["business_action_authorized"])
        self.assertFalse(result["renewal_authorized"])
        self.assertFalse(result["executes_action"])

    def test_deny_receipt_never_becomes_execution_eligible(self):
        raw_receipt = receipt(decision="DENY_BUSINESS_ACTION")
        private, registry, built_out, raw_receipt = built(raw_receipt)
        signature = b64url(
            private.sign(
                canonical_owner_renewal_action_writer_bytes(
                    built_out["request"]
                )
            )
        )
        with tempfile.TemporaryDirectory() as td:
            result = verify_owner_renewal_action_writer_attestation(
                built_out["request"],
                writer_signature_b64=signature,
                checkpoint_write_receipt=raw_receipt,
                writer_trust_roots=registry,
                nonce_registry=PersistentNonceRegistry(
                    Path(td) / "renewal-action-writer.sqlite3"
                ),
                now_ts=NOW,
            )
        self.assertTrue(result["writer_authority_verified"])
        self.assertFalse(result["eligible_for_action_execution_preflight"])
        self.assertFalse(result["business_action_authorized"])

    def test_invalid_signature_blocks(self):
        _, registry, built_out, raw_receipt = built()
        other = Ed25519PrivateKey.generate()
        signature = b64url(
            other.sign(
                canonical_owner_renewal_action_writer_bytes(
                    built_out["request"]
                )
            )
        )
        with tempfile.TemporaryDirectory() as td:
            result = verify_owner_renewal_action_writer_attestation(
                built_out["request"],
                writer_signature_b64=signature,
                checkpoint_write_receipt=raw_receipt,
                writer_trust_roots=registry,
                nonce_registry=PersistentNonceRegistry(
                    Path(td) / "renewal-action-writer.sqlite3"
                ),
                now_ts=NOW,
            )
        self.assertEqual(result["state"], "BLOCKED")
        self.assertIn("ACTION_WRITER_SIGNATURE_INVALID", result["blockers"])

    def test_receipt_mutation_after_request_blocks_rebuild(self):
        private, registry, built_out, raw_receipt = built()
        signature = b64url(
            private.sign(
                canonical_owner_renewal_action_writer_bytes(
                    built_out["request"]
                )
            )
        )
        mutated = dict(raw_receipt)
        mutated["requested_choice"] = "NON_RENEWAL_REVIEW"
        body = {k: v for k, v in mutated.items() if k != "receipt_digest"}
        mutated["receipt_digest"] = digest(body)
        with tempfile.TemporaryDirectory() as td:
            result = verify_owner_renewal_action_writer_attestation(
                built_out["request"],
                writer_signature_b64=signature,
                checkpoint_write_receipt=mutated,
                writer_trust_roots=registry,
                nonce_registry=PersistentNonceRegistry(
                    Path(td) / "renewal-action-writer.sqlite3"
                ),
                now_ts=NOW,
            )
        self.assertEqual(result["state"], "BLOCKED")
        self.assertIn(
            "ACTION_WRITER_REQUEST_REBUILD_MISMATCH",
            result["blockers"],
        )

    def test_replay_is_blocked(self):
        private, registry, built_out, raw_receipt = built()
        signature = b64url(
            private.sign(
                canonical_owner_renewal_action_writer_bytes(
                    built_out["request"]
                )
            )
        )
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "renewal-action-writer.sqlite3"
            first = verify_owner_renewal_action_writer_attestation(
                built_out["request"],
                writer_signature_b64=signature,
                checkpoint_write_receipt=raw_receipt,
                writer_trust_roots=registry,
                nonce_registry=PersistentNonceRegistry(path),
                now_ts=NOW,
            )
            second = verify_owner_renewal_action_writer_attestation(
                built_out["request"],
                writer_signature_b64=signature,
                checkpoint_write_receipt=raw_receipt,
                writer_trust_roots=registry,
                nonce_registry=PersistentNonceRegistry(path),
                now_ts=NOW,
            )
        self.assertTrue(first["writer_authority_verified"])
        self.assertEqual(second["state"], "BLOCKED")
        self.assertIn("ACTION_WRITER_NONCE_REPLAYED", second["blockers"])

    def test_revoked_writer_key_blocks_request(self):
        _, registry = trust_material(status="REVOKED")
        out = build_owner_renewal_action_writer_attestation_request(
            checkpoint_write_receipt=receipt(),
            writer_trust_roots=registry,
            now_ts=NOW,
            ceremony_id="renewal-action-writer-ceremony-001",
            nonce="renewal-action-writer-nonce-0001",
            issued_at=ISSUED,
            expires_at=EXPIRES,
            key_id="renewal-action-writer-key",
            key_version=1,
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("WRITER_TRUST_KEY_REVOKED", out["blockers"])

    def test_success_never_grants_external_authority(self):
        private, registry, built_out, raw_receipt = built()
        signature = b64url(
            private.sign(
                canonical_owner_renewal_action_writer_bytes(
                    built_out["request"]
                )
            )
        )
        with tempfile.TemporaryDirectory() as td:
            result = verify_owner_renewal_action_writer_attestation(
                built_out["request"],
                writer_signature_b64=signature,
                checkpoint_write_receipt=raw_receipt,
                writer_trust_roots=registry,
                nonce_registry=PersistentNonceRegistry(
                    Path(td) / "renewal-action-writer.sqlite3"
                ),
                now_ts=NOW,
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
            self.assertFalse(result[key], key)


if __name__ == "__main__":
    unittest.main()
