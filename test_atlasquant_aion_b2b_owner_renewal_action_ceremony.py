from __future__ import annotations

import base64
import tempfile
import unittest
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
)

from atlasquant_aion_b2b_owner_renewal_action_ceremony import (
    canonical_business_action_decision_bytes,
    build_owner_business_action_request,
    verify_owner_business_action_decision,
)
from atlasquant_aion_b2b_owner_renewal_action_preflight import (
    SCHEMA as PREFLIGHT_SCHEMA,
)
from atlasquant_aion_nonce_registry import PersistentNonceRegistry
from atlasquant_aion_trust_root import TrustRootRegistry

NOW = "2026-10-05T22:00:30Z"
ISSUED = "2026-10-05T22:00:00Z"
EXPIRES = "2026-10-05T22:02:00Z"


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
                    "key_id": "business-action-owner-key",
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


def preflight(**overrides):
    row = {
        "schema": PREFLIGHT_SCHEMA,
        "state": "READY_FOR_BUSINESS_ACTION_AUTHORIZATION_CEREMONY",
        "blockers": [],
        "scope": {
            "owner_id": "owner-a",
            "tenant_id": "tenant-a",
            "workspace_id": "workspace-a",
        },
        "owner_id": "owner-a",
        "tenant_id": "tenant-a",
        "workspace_id": "workspace-a",
        "customer_id": "customer-a",
        "pilot_id": "pilot-a",
        "package": "PROFISSIONAL",
        "review_type": "RENEWAL_REVIEW",
        "requested_choice": "RENEW_AS_IS_REVIEW",
        "action_family": "RENEWAL",
        "owner_review_packet_digest": "sha256:review",
        "cycle_evidence_digest": "sha256:cycle",
        "contract_digest": "sha256:contract",
        "value_bound_conversion_digest": "sha256:value-bound",
        "decision_record_digest": "sha256:decision-record",
        "persistence_receipt_digest": "sha256:receipt",
        "checkpoint_digest": "sha256:checkpoint",
        "writer_request_digest": "sha256:writer-request",
        "environment_digest": "sha256:environment",
        "preflight_digest": "sha256:preflight",
        "action_ceremony_eligible": True,
        "requires_fresh_recheck_before_ceremony": True,
        "action_request_issued": False,
        "owner_action_signature_required": True,
        "owner_action_signature_verified": False,
        "customer_visible": False,
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
    row.update(overrides)
    return row


def built(decision="AUTHORIZE_BUSINESS_ACTION", pf=None, **overrides):
    private, registry = trust_material()
    args = {
        "action_preflight": pf or preflight(),
        "owner_trust_roots": registry,
        "now_ts": NOW,
        "decision": decision,
        "ceremony_id": "business-action-ceremony-001",
        "nonce": "business-action-nonce-0001",
        "issued_at": ISSUED,
        "expires_at": EXPIRES,
        "key_id": "business-action-owner-key",
        "key_version": 1,
    }
    args.update(overrides)
    out = build_owner_business_action_request(**args)
    return private, registry, out, args["action_preflight"]


class OwnerRenewalActionCeremonyTests(unittest.TestCase):
    def test_authorize_builds_exact_external_signature_request(self):
        _, _, out, pf = built()
        self.assertEqual(
            out["state"],
            "READY_FOR_EXTERNAL_OWNER_ACTION_SIGNATURE",
        )
        self.assertEqual(
            out["request"]["requested_choice"],
            pf["requested_choice"],
        )
        self.assertEqual(out["request"]["action_family"], "RENEWAL")
        self.assertFalse(out["action_decision_verified"])
        self.assertFalse(out["business_action_authorized"])
        self.assertFalse(out["executes_action"])

    def test_valid_authorize_signature_is_pending_persistence_only(self):
        private, registry, built_out, pf = built()
        signature = b64url(
            private.sign(
                canonical_business_action_decision_bytes(
                    built_out["request"]
                )
            )
        )
        with tempfile.TemporaryDirectory() as td:
            result = verify_owner_business_action_decision(
                built_out["request"],
                action_signature_b64=signature,
                action_preflight=pf,
                owner_trust_roots=registry,
                nonce_registry=PersistentNonceRegistry(
                    Path(td) / "action-nonces.sqlite3"
                ),
                now_ts=NOW,
            )
        self.assertEqual(
            result["state"],
            "OWNER_BUSINESS_ACTION_DECISION_VERIFIED_AUTHORIZE_PENDING_PERSISTENCE",
        )
        self.assertTrue(result["owner_action_signature_verified"])
        self.assertTrue(result["action_decision_verified"])
        self.assertTrue(result["action_authorization_intent"])
        self.assertFalse(result["action_denial_intent"])
        self.assertFalse(result["action_record_persisted"])
        self.assertTrue(result["requires_action_record_persistence"])
        self.assertFalse(result["business_action_authorized"])
        self.assertFalse(result["renewal_authorized"])
        self.assertFalse(result["executes_action"])

    def test_valid_deny_signature_never_executes_action(self):
        private, registry, built_out, pf = built(
            "DENY_BUSINESS_ACTION"
        )
        signature = b64url(
            private.sign(
                canonical_business_action_decision_bytes(
                    built_out["request"]
                )
            )
        )
        with tempfile.TemporaryDirectory() as td:
            result = verify_owner_business_action_decision(
                built_out["request"],
                action_signature_b64=signature,
                action_preflight=pf,
                owner_trust_roots=registry,
                nonce_registry=PersistentNonceRegistry(
                    Path(td) / "action-nonces.sqlite3"
                ),
                now_ts=NOW,
            )
        self.assertEqual(
            result["state"],
            "OWNER_BUSINESS_ACTION_DECISION_VERIFIED_DENY_PENDING_PERSISTENCE",
        )
        self.assertTrue(result["action_denial_intent"])
        self.assertFalse(result["action_authorization_intent"])
        self.assertFalse(result["business_action_authorized"])
        self.assertFalse(result["customer_contact_authorized"])

    def test_generic_chat_text_is_not_an_authorization_decision(self):
        _, _, out, _ = built("vamos lá")
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "BUSINESS_ACTION_AUTHORIZATION_DECISION_INVALID",
            out["blockers"],
        )
        self.assertFalse(
            out["generic_chat_instruction_accepted_as_action_authorization"]
        )

    def test_invalid_signature_blocks(self):
        _, registry, built_out, pf = built()
        other = Ed25519PrivateKey.generate()
        signature = b64url(
            other.sign(
                canonical_business_action_decision_bytes(
                    built_out["request"]
                )
            )
        )
        with tempfile.TemporaryDirectory() as td:
            result = verify_owner_business_action_decision(
                built_out["request"],
                action_signature_b64=signature,
                action_preflight=pf,
                owner_trust_roots=registry,
                nonce_registry=PersistentNonceRegistry(
                    Path(td) / "action-nonces.sqlite3"
                ),
                now_ts=NOW,
            )
        self.assertEqual(result["state"], "BLOCKED")
        self.assertIn("OWNER_ACTION_SIGNATURE_INVALID", result["blockers"])

    def test_preflight_mutation_after_request_blocks_rebuild(self):
        private, registry, built_out, pf = built()
        signature = b64url(
            private.sign(
                canonical_business_action_decision_bytes(
                    built_out["request"]
                )
            )
        )
        mutated = dict(pf)
        mutated["preflight_digest"] = "sha256:mutated"
        with tempfile.TemporaryDirectory() as td:
            result = verify_owner_business_action_decision(
                built_out["request"],
                action_signature_b64=signature,
                action_preflight=mutated,
                owner_trust_roots=registry,
                nonce_registry=PersistentNonceRegistry(
                    Path(td) / "action-nonces.sqlite3"
                ),
                now_ts=NOW,
            )
        self.assertEqual(result["state"], "BLOCKED")
        self.assertIn(
            "BUSINESS_ACTION_REQUEST_REBUILD_MISMATCH",
            result["blockers"],
        )

    def test_unsafe_preflight_authority_blocks_request(self):
        _, _, out, _ = built(
            pf=preflight(renewal_authorized=True)
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "BUSINESS_ACTION_PREFLIGHT_UNSAFE_FIELD:renewal_authorized",
            out["blockers"],
        )

    def test_expired_request_blocks(self):
        _, _, out, _ = built(
            issued_at="2026-10-05T21:50:00Z",
            expires_at="2026-10-05T21:52:00Z",
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "BUSINESS_ACTION_REQUEST_EXPIRED",
            out["blockers"],
        )

    def test_replay_is_blocked_durably(self):
        private, registry, built_out, pf = built()
        signature = b64url(
            private.sign(
                canonical_business_action_decision_bytes(
                    built_out["request"]
                )
            )
        )
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "action-nonces.sqlite3"
            first = verify_owner_business_action_decision(
                built_out["request"],
                action_signature_b64=signature,
                action_preflight=pf,
                owner_trust_roots=registry,
                nonce_registry=PersistentNonceRegistry(path),
                now_ts=NOW,
            )
            second = verify_owner_business_action_decision(
                built_out["request"],
                action_signature_b64=signature,
                action_preflight=pf,
                owner_trust_roots=registry,
                nonce_registry=PersistentNonceRegistry(path),
                now_ts=NOW,
            )
        self.assertTrue(first["action_decision_verified"])
        self.assertEqual(second["state"], "BLOCKED")
        self.assertIn(
            "BUSINESS_ACTION_NONCE_REPLAYED",
            second["blockers"],
        )

    def test_revoked_owner_key_blocks_request(self):
        _, registry = trust_material(status="REVOKED")
        out = build_owner_business_action_request(
            action_preflight=preflight(),
            owner_trust_roots=registry,
            now_ts=NOW,
            decision="AUTHORIZE_BUSINESS_ACTION",
            ceremony_id="business-action-ceremony-001",
            nonce="business-action-nonce-0001",
            issued_at=ISSUED,
            expires_at=EXPIRES,
            key_id="business-action-owner-key",
            key_version=1,
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("OWNER_TRUST_KEY_REVOKED", out["blockers"])

    def test_verified_authorize_grants_no_external_authority(self):
        private, registry, built_out, pf = built()
        signature = b64url(
            private.sign(
                canonical_business_action_decision_bytes(
                    built_out["request"]
                )
            )
        )
        with tempfile.TemporaryDirectory() as td:
            result = verify_owner_business_action_decision(
                built_out["request"],
                action_signature_b64=signature,
                action_preflight=pf,
                owner_trust_roots=registry,
                nonce_registry=PersistentNonceRegistry(
                    Path(td) / "action-nonces.sqlite3"
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
