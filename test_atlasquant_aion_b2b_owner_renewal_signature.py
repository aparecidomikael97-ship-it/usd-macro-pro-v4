from __future__ import annotations

import base64
import tempfile
import unittest
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
)

from atlasquant_aion_b2b_owner_renewal_decision_request import (
    build_owner_renewal_decision_request,
)
from atlasquant_aion_b2b_owner_renewal_review import (
    SCHEMA as OWNER_REVIEW_SCHEMA,
)
from atlasquant_aion_b2b_owner_renewal_signature import (
    RESULT_SCHEMA,
    canonical_owner_renewal_signature_bytes,
    prepare_owner_renewal_signature_request,
    verify_owner_renewal_decision_signature,
)
from atlasquant_aion_nonce_registry import PersistentNonceRegistry
from atlasquant_aion_trust_root import TrustRootRegistry

SCOPE = {
    "owner_id": "owner-a",
    "tenant_id": "tenant-a",
    "workspace_id": "workspace-a",
}
ISSUED = "2026-10-05T21:00:00Z"
NOW = "2026-10-05T21:01:00Z"
EXPIRES = "2026-10-05T21:03:00Z"


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def packet(**overrides):
    row = {
        "schema": OWNER_REVIEW_SCHEMA,
        "state": "REVIEWABLE",
        "decision": "OWNER_REVIEW_REQUIRED",
        "review_type": "RENEWAL_REVIEW",
        "scope": dict(SCOPE),
        **SCOPE,
        "customer_id": "customer-a",
        "pilot_id": "pilot-a",
        "package": "PROFISSIONAL",
        "service_state": "HEALTHY",
        "service_decision": "RENEWAL_REVIEW_CANDIDATE",
        "health_score": 88.0,
        "observed_roi_pct": 60.0,
        "actual_service_cost_brl": 2200.0,
        "review_reasons": [],
        "incident_reasons": [],
        "allowed_owner_choices": [
            "RENEW_AS_IS_REVIEW",
            "RENEW_WITH_CHANGES_REVIEW",
            "NON_RENEWAL_REVIEW",
        ],
        "source_value_decision": "EXPANSION_REVIEW_CANDIDATE",
        "source_conversion_decision": (
            "EXPANSION_COMMERCIAL_REVIEW_CANDIDATE"
        ),
        "expansion_review_candidate": True,
        "continuation_review_candidate": False,
        "cycle_evidence_digest": "sha256:cycle",
        "contract_digest": "sha256:contract",
        "value_bound_conversion_digest": "sha256:value-bound",
        "evidence_digest": "sha256:owner-review",
        "blockers": [],
        "owner_decision_required": True,
        "owner_only": True,
        "customer_visible": False,
        "automatic_owner_choice": False,
        "automatic_renewal": False,
        "automatic_expansion": False,
        "automatic_package_change": False,
        "automatic_pause": False,
        "automatic_termination": False,
        "automatic_billing": False,
        "automatic_pricing_change": False,
        "automatic_quota_increase": False,
        "automatic_role_change": False,
        "automatic_integration_change": False,
        "automatic_customer_contact": False,
        "automatic_provisioning": False,
        "automatic_deploy": False,
        "provider_called": False,
        "crm_write": False,
        "production_mutation": False,
        "executes_action": False,
    }
    row.update(overrides)
    return row


def decision_request(review=None, choice="RENEW_AS_IS_REVIEW"):
    return build_owner_renewal_decision_request(
        trusted_scope=SCOPE,
        owner_review_packet=review or packet(),
        requested_choice=choice,
        ceremony_id="renewal-decision-ceremony-001",
        nonce="renewal-decision-nonce-0001",
        issued_at=ISSUED,
        expires_at=EXPIRES,
    )


def trust_material():
    private = Ed25519PrivateKey.generate()
    public_raw = private.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    registry = TrustRootRegistry.from_mapping(
        {
            "schema": "ATLASQUANT_AION_TRUST_ROOT_V1",
            "roots": [
                {
                    "key_id": "renewal-owner-key",
                    "key_version": 1,
                    "algorithm": "Ed25519",
                    "public_key_b64": _b64url(public_raw),
                    "status": "ACTIVE",
                    "not_before": "2026-10-05T20:00:00Z",
                    "not_after": "2026-10-05T23:00:00Z",
                }
            ],
            "revoked_key_ids": [],
        }
    )
    return private, registry


def prepared(review=None, choice="RENEW_AS_IS_REVIEW"):
    review = review or packet()
    base = decision_request(review, choice)
    private, registry = trust_material()
    signable = prepare_owner_renewal_signature_request(
        decision_request_result=base,
        owner_review_packet=review,
        owner_trust_roots=registry,
        now_ts=NOW,
        key_id="renewal-owner-key",
        key_version=1,
    )
    return private, registry, base, review, signable


class OwnerRenewalSignatureTests(unittest.TestCase):
    def test_prepare_binds_exact_decision_request_and_owner_key(self):
        _, _, base, _, signable = prepared()
        self.assertEqual(
            signable["state"],
            "READY_FOR_EXTERNAL_OWNER_SIGNATURE",
        )
        self.assertEqual(
            signable["request"]["requested_choice"],
            "RENEW_AS_IS_REVIEW",
        )
        self.assertEqual(
            signable["request"]["decision_request_digest"],
            base["request_digest"],
        )
        self.assertEqual(
            signable["request"]["key_id"],
            "renewal-owner-key",
        )
        self.assertFalse(signable["owner_decision_verified"])
        self.assertFalse(signable["renewal_authorized"])
        self.assertFalse(signable["executes_action"])

    def test_valid_signature_verifies_decision_only(self):
        private, registry, base, review, signable = prepared()
        signature = _b64url(
            private.sign(
                canonical_owner_renewal_signature_bytes(
                    signable["request"]
                )
            )
        )
        with tempfile.TemporaryDirectory() as td:
            result = verify_owner_renewal_decision_signature(
                signable["request"],
                decision_signature_b64=signature,
                decision_request_result=base,
                owner_review_packet=review,
                owner_trust_roots=registry,
                decision_nonce_registry=PersistentNonceRegistry(
                    Path(td) / "nonces.sqlite3"
                ),
                now_ts=NOW,
            )
        self.assertEqual(result["schema"], RESULT_SCHEMA)
        self.assertEqual(
            result["state"],
            "OWNER_RENEWAL_DECISION_VERIFIED_PENDING_PERSISTENCE",
        )
        self.assertTrue(result["owner_decision_verified"])
        self.assertEqual(
            result["requested_choice"],
            "RENEW_AS_IS_REVIEW",
        )
        self.assertFalse(result["owner_decision_recorded"])
        self.assertFalse(result["decision_persisted"])
        self.assertTrue(result["requires_decision_persistence"])
        self.assertFalse(result["renewal_authorized"])
        self.assertFalse(result["customer_contact_authorized"])
        self.assertFalse(result["executes_action"])

    def test_non_renewal_signature_still_does_not_terminate(self):
        private, registry, base, review, signable = prepared(
            choice="NON_RENEWAL_REVIEW"
        )
        signature = _b64url(
            private.sign(
                canonical_owner_renewal_signature_bytes(
                    signable["request"]
                )
            )
        )
        with tempfile.TemporaryDirectory() as td:
            result = verify_owner_renewal_decision_signature(
                signable["request"],
                decision_signature_b64=signature,
                decision_request_result=base,
                owner_review_packet=review,
                owner_trust_roots=registry,
                decision_nonce_registry=PersistentNonceRegistry(
                    Path(td) / "nonces.sqlite3"
                ),
                now_ts=NOW,
            )
        self.assertTrue(result["owner_decision_verified"])
        self.assertEqual(
            result["requested_choice"],
            "NON_RENEWAL_REVIEW",
        )
        self.assertFalse(result["termination_authorized"])
        self.assertFalse(result["pause_authorized"])

    def test_invalid_signature_blocks(self):
        _, registry, base, review, signable = prepared()
        other = Ed25519PrivateKey.generate()
        signature = _b64url(
            other.sign(
                canonical_owner_renewal_signature_bytes(
                    signable["request"]
                )
            )
        )
        with tempfile.TemporaryDirectory() as td:
            result = verify_owner_renewal_decision_signature(
                signable["request"],
                decision_signature_b64=signature,
                decision_request_result=base,
                owner_review_packet=review,
                owner_trust_roots=registry,
                decision_nonce_registry=PersistentNonceRegistry(
                    Path(td) / "nonces.sqlite3"
                ),
                now_ts=NOW,
            )
        self.assertEqual(result["state"], "BLOCKED")
        self.assertIn(
            "OWNER_RENEWAL_SIGNATURE_INVALID",
            result["blockers"],
        )

    def test_nonce_replay_is_blocked_durably(self):
        private, registry, base, review, signable = prepared()
        signature = _b64url(
            private.sign(
                canonical_owner_renewal_signature_bytes(
                    signable["request"]
                )
            )
        )
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "nonces.sqlite3"
            first = verify_owner_renewal_decision_signature(
                signable["request"],
                decision_signature_b64=signature,
                decision_request_result=base,
                owner_review_packet=review,
                owner_trust_roots=registry,
                decision_nonce_registry=PersistentNonceRegistry(path),
                now_ts=NOW,
            )
            second = verify_owner_renewal_decision_signature(
                signable["request"],
                decision_signature_b64=signature,
                decision_request_result=base,
                owner_review_packet=review,
                owner_trust_roots=registry,
                decision_nonce_registry=PersistentNonceRegistry(path),
                now_ts=NOW,
            )
        self.assertTrue(first["owner_decision_verified"])
        self.assertEqual(second["state"], "BLOCKED")
        self.assertIn("OWNER_RENEWAL_NONCE_REPLAYED", second["blockers"])

    def test_packet_mutation_after_request_blocks_rebuild(self):
        _, registry, base, review, _ = prepared()
        mutated = dict(review)
        mutated["evidence_digest"] = "sha256:mutated"
        out = prepare_owner_renewal_signature_request(
            decision_request_result=base,
            owner_review_packet=mutated,
            owner_trust_roots=registry,
            now_ts=NOW,
            key_id="renewal-owner-key",
            key_version=1,
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertTrue(
            any(
                item.startswith("OWNER_RENEWAL_REQUEST_REBUILD")
                for item in out["blockers"]
            )
        )

    def test_tampered_prepared_request_digest_blocks(self):
        _, registry, base, review, _ = prepared()
        bad = dict(base)
        bad["request_digest"] = "sha256:tampered"
        out = prepare_owner_renewal_signature_request(
            decision_request_result=bad,
            owner_review_packet=review,
            owner_trust_roots=registry,
            now_ts=NOW,
            key_id="renewal-owner-key",
            key_version=1,
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "OWNER_RENEWAL_REQUEST_DIGEST_MISMATCH",
            out["blockers"],
        )

    def test_expired_request_blocks(self):
        _, registry, base, review, _ = prepared()
        out = prepare_owner_renewal_signature_request(
            decision_request_result=base,
            owner_review_packet=review,
            owner_trust_roots=registry,
            now_ts="2026-10-05T21:04:00Z",
            key_id="renewal-owner-key",
            key_version=1,
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "OWNER_RENEWAL_DECISION_EXPIRED",
            out["blockers"],
        )

    def test_authority_flip_in_signed_request_blocks(self):
        private, registry, base, review, signable = prepared()
        tampered = dict(signable["request"])
        tampered["renewal_authorized"] = True
        signature = _b64url(
            private.sign(
                canonical_owner_renewal_signature_bytes(tampered)
            )
        )
        with tempfile.TemporaryDirectory() as td:
            result = verify_owner_renewal_decision_signature(
                tampered,
                decision_signature_b64=signature,
                decision_request_result=base,
                owner_review_packet=review,
                owner_trust_roots=registry,
                decision_nonce_registry=PersistentNonceRegistry(
                    Path(td) / "nonces.sqlite3"
                ),
                now_ts=NOW,
            )
        self.assertEqual(result["state"], "BLOCKED")
        self.assertIn(
            "OWNER_RENEWAL_SIGNATURE_UNSAFE_FIELD:renewal_authorized",
            result["blockers"],
        )

    def test_generic_chat_cannot_reach_signature_request(self):
        review = packet()
        bad = decision_request(review, choice="vamos lá")
        _, registry = trust_material()
        out = prepare_owner_renewal_signature_request(
            decision_request_result=bad,
            owner_review_packet=review,
            owner_trust_roots=registry,
            now_ts=NOW,
            key_id="renewal-owner-key",
            key_version=1,
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "OWNER_RENEWAL_REQUEST_NOT_READY",
            out["blockers"],
        )

    def test_verified_signature_grants_no_external_authority(self):
        private, registry, base, review, signable = prepared()
        signature = _b64url(
            private.sign(
                canonical_owner_renewal_signature_bytes(
                    signable["request"]
                )
            )
        )
        with tempfile.TemporaryDirectory() as td:
            result = verify_owner_renewal_decision_signature(
                signable["request"],
                decision_signature_b64=signature,
                decision_request_result=base,
                owner_review_packet=review,
                owner_trust_roots=registry,
                decision_nonce_registry=PersistentNonceRegistry(
                    Path(td) / "nonces.sqlite3"
                ),
                now_ts=NOW,
            )
        for key in (
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
            self.assertFalse(result[key], key)


if __name__ == "__main__":
    unittest.main()
