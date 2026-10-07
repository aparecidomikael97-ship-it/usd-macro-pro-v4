from __future__ import annotations

import base64
import tempfile
import unittest
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
)

from atlasquant_aion_b2b_owner_renewal_action_execution_ceremony import (
    build_owner_business_action_execution_request,
    canonical_owner_business_action_execution_bytes,
    verify_owner_business_action_execution_decision,
)
from atlasquant_aion_b2b_owner_renewal_action_execution_preflight import (
    SCHEMA as PREFLIGHT_SCHEMA,
)
from atlasquant_aion_nonce_registry import PersistentNonceRegistry
from atlasquant_aion_trust_root import TrustRootRegistry

NOW = "2026-10-05T22:35:30Z"
ISSUED = "2026-10-05T22:35:00Z"
EXPIRES = "2026-10-05T22:36:30Z"


def h(char):
    return "sha256:" + char * 64


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
                    "key_id": "recurring-execution-owner-key",
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
        "state": "READY_FOR_BUSINESS_ACTION_EXECUTION_CEREMONY",
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
        "action_record_digest": h("1"),
        "action_persistence_receipt_digest": h("2"),
        "action_checkpoint_digest": h("3"),
        "action_writer_request_digest": h("4"),
        "authorization_preflight_digest": h("5"),
        "action_parameters_digest": h("6"),
        "execution_environment_digest": h("7"),
        "execution_preflight_digest": h("8"),
        "business_action_execution_ceremony_eligible": True,
        "human_execution_confirmation_required": True,
        "execution_request_issued": False,
        "owner_execution_signature_verified": False,
        "execution_command_generated": False,
        "execution_command_executed": False,
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


def built(decision="AUTHORIZE_BUSINESS_ACTION_EXECUTION", pf=None, **overrides):
    private, registry = trust_material()
    args = {
        "execution_preflight": pf or preflight(),
        "owner_trust_roots": registry,
        "now_ts": NOW,
        "decision": decision,
        "ceremony_id": "recurring-execution-ceremony-001",
        "nonce": "recurring-execution-nonce-0001",
        "issued_at": ISSUED,
        "expires_at": EXPIRES,
        "key_id": "recurring-execution-owner-key",
        "key_version": 1,
    }
    args.update(overrides)
    out = build_owner_business_action_execution_request(**args)
    return private, registry, out, args["execution_preflight"]


class OwnerRenewalActionExecutionCeremonyTests(unittest.TestCase):
    def test_valid_request_is_signature_ready_without_command(self):
        _, _, out, pf = built()
        self.assertEqual(
            out["state"],
            "READY_FOR_EXTERNAL_OWNER_BUSINESS_ACTION_EXECUTION_SIGNATURE",
        )
        self.assertEqual(
            out["request"]["action_parameters_digest"],
            pf["action_parameters_digest"],
        )
        self.assertFalse(out["execution_decision_verified"])
        self.assertFalse(out["execution_command_generated"])
        self.assertFalse(out["business_action_authorized"])
        self.assertFalse(out["executes_action"])

    def test_generic_chat_instruction_is_not_execution_authorization(self):
        _, _, out, _ = built("vamos lá")
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "BUSINESS_ACTION_EXECUTION_DECISION_INVALID",
            out["blockers"],
        )
        self.assertFalse(
            out["generic_chat_instruction_accepted_as_execution"]
        )

    def test_only_canonical_execution_choices_are_accepted(self):
        for decision in (
            "approve",
            "execute",
            "renew",
            "YES",
            "AUTHORIZE",
            True,
            1,
            "",
            None,
        ):
            with self.subTest(decision=decision):
                _, _, out, _ = built(decision)
                self.assertEqual(out["state"], "BLOCKED")
                self.assertIn(
                    "BUSINESS_ACTION_EXECUTION_DECISION_INVALID",
                    out["blockers"],
                )

    def test_preflight_must_remain_authority_free(self):
        for key in (
            "execution_request_issued",
            "owner_execution_signature_verified",
            "execution_command_generated",
            "execution_command_executed",
            "business_action_authorized",
            "renewal_authorized",
            "termination_authorized",
            "billing_authorized",
            "customer_contact_authorized",
            "production_mutation_authorized",
            "executes_action",
        ):
            with self.subTest(key=key):
                _, _, out, _ = built(pf=preflight(**{key: True}))
                self.assertEqual(out["state"], "BLOCKED")

    def test_window_is_bounded_to_two_minutes(self):
        _, _, out, _ = built(
            expires_at="2026-10-05T22:38:30Z"
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "BUSINESS_ACTION_EXECUTION_WINDOW_TOO_LONG",
            out["blockers"],
        )

    def test_expired_request_blocks(self):
        _, _, out, _ = built(
            issued_at="2026-10-05T22:30:00Z",
            expires_at="2026-10-05T22:31:00Z",
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "BUSINESS_ACTION_EXECUTION_REQUEST_EXPIRED",
            out["blockers"],
        )

    def test_valid_authorize_signature_stays_pending_persistence(self):
        private, registry, built_out, pf = built()
        signature = b64url(
            private.sign(
                canonical_owner_business_action_execution_bytes(
                    built_out["request"]
                )
            )
        )
        with tempfile.TemporaryDirectory() as td:
            result = verify_owner_business_action_execution_decision(
                built_out["request"],
                execution_signature_b64=signature,
                execution_preflight=pf,
                owner_trust_roots=registry,
                nonce_registry=PersistentNonceRegistry(
                    Path(td) / "recurring-execution.sqlite3"
                ),
                now_ts=NOW,
            )
        self.assertEqual(
            result["state"],
            "OWNER_BUSINESS_ACTION_EXECUTION_VERIFIED_AUTHORIZE_PENDING_PERSISTENCE",
        )
        self.assertTrue(result["owner_execution_identity_verified"])
        self.assertTrue(result["owner_execution_signature_verified"])
        self.assertTrue(result["execution_decision_verified"])
        self.assertTrue(result["execution_authorization_intent"])
        self.assertFalse(result["execution_denial_intent"])
        self.assertTrue(result["requires_execution_record_persistence"])
        self.assertTrue(
            result["eligible_for_command_planning_after_persistence"]
        )
        self.assertFalse(result["execution_record_persisted"])
        self.assertFalse(result["execution_command_generated"])
        self.assertFalse(result["execution_command_executed"])
        self.assertFalse(result["business_action_authorized"])
        self.assertFalse(result["renewal_authorized"])
        self.assertFalse(result["executes_action"])

    def test_valid_deny_signature_is_not_planning_eligible(self):
        private, registry, built_out, pf = built(
            "DENY_BUSINESS_ACTION_EXECUTION"
        )
        signature = b64url(
            private.sign(
                canonical_owner_business_action_execution_bytes(
                    built_out["request"]
                )
            )
        )
        with tempfile.TemporaryDirectory() as td:
            result = verify_owner_business_action_execution_decision(
                built_out["request"],
                execution_signature_b64=signature,
                execution_preflight=pf,
                owner_trust_roots=registry,
                nonce_registry=PersistentNonceRegistry(
                    Path(td) / "recurring-execution.sqlite3"
                ),
                now_ts=NOW,
            )
        self.assertEqual(
            result["state"],
            "OWNER_BUSINESS_ACTION_EXECUTION_VERIFIED_DENY_PENDING_PERSISTENCE",
        )
        self.assertFalse(result["execution_authorization_intent"])
        self.assertTrue(result["execution_denial_intent"])
        self.assertFalse(
            result["eligible_for_command_planning_after_persistence"]
        )
        self.assertFalse(result["business_action_authorized"])

    def test_invalid_signature_blocks(self):
        _, registry, built_out, pf = built()
        other = Ed25519PrivateKey.generate()
        signature = b64url(
            other.sign(
                canonical_owner_business_action_execution_bytes(
                    built_out["request"]
                )
            )
        )
        with tempfile.TemporaryDirectory() as td:
            result = verify_owner_business_action_execution_decision(
                built_out["request"],
                execution_signature_b64=signature,
                execution_preflight=pf,
                owner_trust_roots=registry,
                nonce_registry=PersistentNonceRegistry(
                    Path(td) / "recurring-execution.sqlite3"
                ),
                now_ts=NOW,
            )
        self.assertEqual(result["state"], "BLOCKED")
        self.assertIn(
            "BUSINESS_ACTION_EXECUTION_SIGNATURE_INVALID",
            result["blockers"],
        )

    def test_preflight_mutation_after_request_blocks_rebuild(self):
        private, registry, built_out, pf = built()
        signature = b64url(
            private.sign(
                canonical_owner_business_action_execution_bytes(
                    built_out["request"]
                )
            )
        )
        mutated = dict(pf)
        mutated["execution_preflight_digest"] = h("9")
        with tempfile.TemporaryDirectory() as td:
            result = verify_owner_business_action_execution_decision(
                built_out["request"],
                execution_signature_b64=signature,
                execution_preflight=mutated,
                owner_trust_roots=registry,
                nonce_registry=PersistentNonceRegistry(
                    Path(td) / "recurring-execution.sqlite3"
                ),
                now_ts=NOW,
            )
        self.assertEqual(result["state"], "BLOCKED")
        self.assertIn(
            "BUSINESS_ACTION_EXECUTION_REQUEST_REBUILD_MISMATCH",
            result["blockers"],
        )

    def test_replay_is_blocked_durably(self):
        private, registry, built_out, pf = built()
        signature = b64url(
            private.sign(
                canonical_owner_business_action_execution_bytes(
                    built_out["request"]
                )
            )
        )
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "recurring-execution.sqlite3"
            first = verify_owner_business_action_execution_decision(
                built_out["request"],
                execution_signature_b64=signature,
                execution_preflight=pf,
                owner_trust_roots=registry,
                nonce_registry=PersistentNonceRegistry(path),
                now_ts=NOW,
            )
            second = verify_owner_business_action_execution_decision(
                built_out["request"],
                execution_signature_b64=signature,
                execution_preflight=pf,
                owner_trust_roots=registry,
                nonce_registry=PersistentNonceRegistry(path),
                now_ts=NOW,
            )
        self.assertTrue(first["execution_decision_verified"])
        self.assertEqual(second["state"], "BLOCKED")
        self.assertIn(
            "BUSINESS_ACTION_EXECUTION_NONCE_REPLAYED",
            second["blockers"],
        )

    def test_revoked_owner_key_blocks_request(self):
        _, registry = trust_material(status="REVOKED")
        out = build_owner_business_action_execution_request(
            execution_preflight=preflight(),
            owner_trust_roots=registry,
            now_ts=NOW,
            decision="AUTHORIZE_BUSINESS_ACTION_EXECUTION",
            ceremony_id="recurring-execution-ceremony-001",
            nonce="recurring-execution-nonce-0001",
            issued_at=ISSUED,
            expires_at=EXPIRES,
            key_id="recurring-execution-owner-key",
            key_version=1,
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("OWNER_TRUST_KEY_REVOKED", out["blockers"])

    def test_verified_execution_never_generates_or_runs_command(self):
        private, registry, built_out, pf = built()
        signature = b64url(
            private.sign(
                canonical_owner_business_action_execution_bytes(
                    built_out["request"]
                )
            )
        )
        with tempfile.TemporaryDirectory() as td:
            result = verify_owner_business_action_execution_decision(
                built_out["request"],
                execution_signature_b64=signature,
                execution_preflight=pf,
                owner_trust_roots=registry,
                nonce_registry=PersistentNonceRegistry(
                    Path(td) / "recurring-execution.sqlite3"
                ),
                now_ts=NOW,
            )
        for key in (
            "execution_record_persisted",
            "execution_command_generated",
            "execution_command_executed",
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
