from __future__ import annotations

import base64
import tempfile
import unittest
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
)

from atlasquant_aion_b2b_pilot_owner_decision import (
    build_pilot_owner_decision_request,
    canonical_pilot_owner_decision_bytes,
    verify_pilot_owner_decision,
)
from atlasquant_aion_nonce_registry import PersistentNonceRegistry
from atlasquant_aion_trust_root import TrustRootRegistry

NOW = "2026-10-05T18:00:30Z"
ISSUED = "2026-10-05T18:00:00Z"
EXPIRES = "2026-10-05T18:02:00Z"


def _b64url(raw: bytes) -> str:
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
                    "key_id": "pilot-owner-key",
                    "key_version": 1,
                    "algorithm": "Ed25519",
                    "public_key_b64": _b64url(public),
                    "status": "ACTIVE",
                    "not_before": "2026-10-05T00:00:00Z",
                    "not_after": "2027-10-05T00:00:00Z",
                }
            ],
            "revoked_key_ids": [],
        }
    )
    return private, registry


def packet(**overrides):
    row = {
        "schema": "ATLASQUANT_AION_B2B_PILOT_OWNER_REVIEW_PACKET_V1",
        "state": "READY_FOR_OWNER_REVIEW",
        "scope": {
            "owner_id": "HUMAN_OWNER",
            "tenant_id": "atlasquant-owner",
            "workspace_id": "business",
        },
        "candidate_id": "candidate-001",
        "summary": {
            "proposal": {
                "proposal_id": "proposal-001",
                "company_label": "Empresa Exemplo",
                "package": "PROFISSIONAL",
                "pricing_mode": "TBD",
                "indicative_setup_fee_brl": None,
                "indicative_monthly_fee_brl": None,
                "pricing_binding": False,
                "non_binding": True,
            },
            "readiness": {
                "decision": "PILOT_REVIEW_CANDIDATE",
                "acceptance_score": 90.0,
                "risk_score": 20.0,
                "priority_score": 87.5,
                "planned_monthly_infra_brl": 150.0,
            },
            "pilot": {
                "pilot_id": "pilot-001",
                "duration_days": 14,
                "max_monthly_infra_brl": 150.0,
                "scope_items": ["Estruturação de CRM"],
                "kpis": [],
                "stop_conditions": ["privacy", "scope", "budget"],
                "rollback_steps": ["disable", "restore"],
                "activation_state": "BLOCKED_UNTIL_OWNER_APPROVAL",
            },
            "evidence": {
                "proposal_digest": "sha256:" + "1" * 64,
                "readiness_evidence_digest": "sha256:" + "2" * 64,
                "pilot_handoff_digest": "sha256:" + "3" * 64,
                "operating_contract_digest": "sha256:" + "4" * 64,
            },
        },
        "checklist": {
            "scope_bound": True,
            "candidate_bound": True,
            "proposal_non_binding": True,
            "readiness_positive": True,
            "activation_blocked": True,
            "stop_conditions_present": True,
            "rollback_present": True,
            "kpis_present": True,
        },
        "blockers": [],
        "packet_digest": "sha256:" + "a" * 64,
        "owner_decision": "UNDECIDED",
        "owner_decision_recorded": False,
        "owner_approval_recorded": False,
        "owner_signature_requested": False,
        "owner_signature_verified": False,
        "decision_mechanism_reused_from_core_freeze": False,
        "human_owner_decision_required": True,
        "pilot_activation_authorized": False,
        "automatic_activation": False,
        "automatic_customer_contact": False,
        "automatic_contract_signature": False,
        "automatic_billing": False,
        "automatic_spend": False,
        "automatic_deploy": False,
        "crm_write": False,
        "provider_called": False,
        "production_mutation": False,
        "grants_authority": False,
        "executes_action": False,
    }
    row.update(overrides)
    return row


def request_for(decision="APPROVE_PILOT", **overrides):
    private, registry = trust_material()
    args = {
        "review_packet": packet(),
        "owner_trust_roots": registry,
        "now_ts": NOW,
        "decision": decision,
        "ceremony_id": "pilot-decision-ceremony-001",
        "nonce": "pilot-decision-nonce-0001",
        "issued_at": ISSUED,
        "expires_at": EXPIRES,
        "key_id": "pilot-owner-key",
        "key_version": 1,
    }
    args.update(overrides)
    built = build_pilot_owner_decision_request(**args)
    return private, registry, built, args["review_packet"]


class AionB2BPilotOwnerDecisionTests(unittest.TestCase):
    def test_valid_approve_request_is_signature_ready_but_undecided(self):
        _, _, built, _ = request_for("APPROVE_PILOT")
        self.assertEqual(
            built["state"],
            "READY_FOR_EXTERNAL_OWNER_DECISION_SIGNATURE",
        )
        self.assertFalse(built["blockers"])
        self.assertEqual(built["owner_decision"], "UNDECIDED")
        self.assertFalse(built["owner_decision_verified"])
        self.assertFalse(built["pilot_approved"])
        self.assertFalse(built["pilot_activation_authorized"])
        self.assertFalse(built["executes_action"])
        self.assertEqual(
            built["request"]["decision"],
            "APPROVE_PILOT",
        )
        self.assertEqual(
            built["request"]["packet_digest"],
            "sha256:" + "a" * 64,
        )

    def test_generic_chat_instruction_is_not_a_decision(self):
        _, _, built, _ = request_for("vamos lá")
        self.assertEqual(built["state"], "BLOCKED")
        self.assertIn(
            "PILOT_OWNER_DECISION_CHOICE_INVALID",
            built["blockers"],
        )

    def test_only_two_canonical_choices_are_accepted(self):
        for decision in (
            "approve",
            "YES",
            "APPROVE",
            True,
            1,
            "",
            None,
        ):
            with self.subTest(decision=decision):
                _, _, built, _ = request_for(decision)
                self.assertEqual(built["state"], "BLOCKED")
                self.assertIn(
                    "PILOT_OWNER_DECISION_CHOICE_INVALID",
                    built["blockers"],
                )

    def test_window_is_bounded_to_three_minutes(self):
        _, _, built, _ = request_for(
            "APPROVE_PILOT",
            expires_at="2026-10-05T18:10:00Z",
        )
        self.assertEqual(built["state"], "BLOCKED")
        self.assertIn(
            "PILOT_OWNER_DECISION_WINDOW_TOO_LONG",
            built["blockers"],
        )

    def test_expired_request_blocks(self):
        _, _, built, _ = request_for(
            "APPROVE_PILOT",
            issued_at="2026-10-05T17:55:00Z",
            expires_at="2026-10-05T17:57:00Z",
        )
        self.assertEqual(built["state"], "BLOCKED")
        self.assertIn(
            "PILOT_OWNER_DECISION_EXPIRED",
            built["blockers"],
        )

    def test_packet_must_remain_undecided_and_authority_free(self):
        bad = packet(owner_decision="APPROVE_PILOT")
        _, registry = trust_material()
        built = build_pilot_owner_decision_request(
            review_packet=bad,
            owner_trust_roots=registry,
            now_ts=NOW,
            decision="APPROVE_PILOT",
            ceremony_id="pilot-decision-ceremony-001",
            nonce="pilot-decision-nonce-0001",
            issued_at=ISSUED,
            expires_at=EXPIRES,
            key_id="pilot-owner-key",
            key_version=1,
        )
        self.assertEqual(built["state"], "BLOCKED")
        self.assertIn(
            "PILOT_REVIEW_PACKET_ALREADY_DECIDED",
            built["blockers"],
        )

    def test_approve_signature_verifies_but_stays_pending_persistence(self):
        private, registry, built, review_packet = request_for(
            "APPROVE_PILOT"
        )
        signature = _b64url(
            private.sign(
                canonical_pilot_owner_decision_bytes(
                    built["request"]
                )
            )
        )
        with tempfile.TemporaryDirectory() as td:
            nonce_registry = PersistentNonceRegistry(
                Path(td) / "nonces.sqlite3"
            )
            result = verify_pilot_owner_decision(
                built["request"],
                decision_signature_b64=signature,
                review_packet=review_packet,
                owner_trust_roots=registry,
                decision_nonce_registry=nonce_registry,
                now_ts=NOW,
            )
        self.assertEqual(
            result["state"],
            "OWNER_DECISION_VERIFIED_APPROVE_PENDING_PERSISTENCE",
        )
        self.assertTrue(result["owner_decision_verified"])
        self.assertEqual(result["owner_decision"], "APPROVE_PILOT")
        self.assertTrue(result["pilot_approved"])
        self.assertFalse(result["pilot_denied"])
        self.assertFalse(result["owner_decision_recorded"])
        self.assertFalse(result["decision_record_persisted"])
        self.assertTrue(result["requires_decision_record_persistence"])
        self.assertTrue(
            result["eligible_for_activation_ceremony_after_persistence"]
        )
        self.assertFalse(result["pilot_activation_authorized"])
        self.assertFalse(result["pilot_activated"])
        self.assertFalse(result["executes_action"])
        self.assertFalse(
            result["generic_chat_instruction_accepted_as_decision"]
        )

    def test_deny_signature_verifies_and_never_becomes_activation_eligible(self):
        private, registry, built, review_packet = request_for(
            "DENY_PILOT"
        )
        signature = _b64url(
            private.sign(
                canonical_pilot_owner_decision_bytes(
                    built["request"]
                )
            )
        )
        with tempfile.TemporaryDirectory() as td:
            result = verify_pilot_owner_decision(
                built["request"],
                decision_signature_b64=signature,
                review_packet=review_packet,
                owner_trust_roots=registry,
                decision_nonce_registry=PersistentNonceRegistry(
                    Path(td) / "nonces.sqlite3"
                ),
                now_ts=NOW,
            )
        self.assertEqual(
            result["state"],
            "OWNER_DECISION_VERIFIED_DENY_PENDING_PERSISTENCE",
        )
        self.assertFalse(result["pilot_approved"])
        self.assertTrue(result["pilot_denied"])
        self.assertFalse(
            result["eligible_for_activation_ceremony_after_persistence"]
        )
        self.assertFalse(result["pilot_activation_authorized"])
        self.assertFalse(result["executes_action"])

    def test_invalid_signature_blocks(self):
        _, registry, built, review_packet = request_for(
            "APPROVE_PILOT"
        )
        other_private = Ed25519PrivateKey.generate()
        signature = _b64url(
            other_private.sign(
                canonical_pilot_owner_decision_bytes(
                    built["request"]
                )
            )
        )
        with tempfile.TemporaryDirectory() as td:
            result = verify_pilot_owner_decision(
                built["request"],
                decision_signature_b64=signature,
                review_packet=review_packet,
                owner_trust_roots=registry,
                decision_nonce_registry=PersistentNonceRegistry(
                    Path(td) / "nonces.sqlite3"
                ),
                now_ts=NOW,
            )
        self.assertEqual(result["state"], "BLOCKED")
        self.assertIn(
            "PILOT_OWNER_DECISION_SIGNATURE_INVALID",
            result["blockers"],
        )

    def test_replay_is_blocked_durably(self):
        private, registry, built, review_packet = request_for(
            "APPROVE_PILOT"
        )
        signature = _b64url(
            private.sign(
                canonical_pilot_owner_decision_bytes(
                    built["request"]
                )
            )
        )
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "nonces.sqlite3"
            registry_one = PersistentNonceRegistry(path)
            first = verify_pilot_owner_decision(
                built["request"],
                decision_signature_b64=signature,
                review_packet=review_packet,
                owner_trust_roots=registry,
                decision_nonce_registry=registry_one,
                now_ts=NOW,
            )
            registry_two = PersistentNonceRegistry(path)
            second = verify_pilot_owner_decision(
                built["request"],
                decision_signature_b64=signature,
                review_packet=review_packet,
                owner_trust_roots=registry,
                decision_nonce_registry=registry_two,
                now_ts=NOW,
            )
        self.assertTrue(first["owner_decision_verified"])
        self.assertEqual(second["state"], "BLOCKED")
        self.assertIn(
            "PILOT_OWNER_DECISION_NONCE_REPLAYED",
            second["blockers"],
        )

    def test_packet_mutation_after_request_blocks_rebuild(self):
        private, registry, built, review_packet = request_for(
            "APPROVE_PILOT"
        )
        signature = _b64url(
            private.sign(
                canonical_pilot_owner_decision_bytes(
                    built["request"]
                )
            )
        )
        mutated = dict(review_packet)
        mutated["packet_digest"] = "sha256:" + "b" * 64
        with tempfile.TemporaryDirectory() as td:
            result = verify_pilot_owner_decision(
                built["request"],
                decision_signature_b64=signature,
                review_packet=mutated,
                owner_trust_roots=registry,
                decision_nonce_registry=PersistentNonceRegistry(
                    Path(td) / "nonces.sqlite3"
                ),
                now_ts=NOW,
            )
        self.assertEqual(result["state"], "BLOCKED")
        self.assertIn(
            "PILOT_OWNER_DECISION_REQUEST_REBUILD_MISMATCH",
            result["blockers"],
        )

    def test_verified_approve_never_authorizes_external_actions(self):
        private, registry, built, review_packet = request_for(
            "APPROVE_PILOT"
        )
        signature = _b64url(
            private.sign(
                canonical_pilot_owner_decision_bytes(
                    built["request"]
                )
            )
        )
        with tempfile.TemporaryDirectory() as td:
            result = verify_pilot_owner_decision(
                built["request"],
                decision_signature_b64=signature,
                review_packet=review_packet,
                owner_trust_roots=registry,
                decision_nonce_registry=PersistentNonceRegistry(
                    Path(td) / "nonces.sqlite3"
                ),
                now_ts=NOW,
            )
        for key in (
            "pilot_activation_authorized",
            "pilot_activated",
            "customer_contact_authorized",
            "contract_signature_authorized",
            "billing_authorized",
            "spend_authorized",
            "deploy_authorized",
            "crm_write_authorized",
            "production_mutation_authorized",
            "external_action_executed",
            "network_called",
            "executes_action",
        ):
            self.assertFalse(result[key], key)


if __name__ == "__main__":
    unittest.main()
