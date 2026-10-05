from __future__ import annotations

import unittest

from atlasquant_aion_b2b_owner_renewal_decision_request import (
    SCHEMA,
    build_owner_renewal_decision_request,
)
from atlasquant_aion_b2b_owner_renewal_review import (
    SCHEMA as OWNER_REVIEW_SCHEMA,
)

SCOPE = {
    "owner_id": "owner-a",
    "tenant_id": "tenant-a",
    "workspace_id": "workspace-a",
}


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


def build(choice="RENEW_AS_IS_REVIEW", **overrides):
    args = {
        "trusted_scope": SCOPE,
        "owner_review_packet": packet(),
        "requested_choice": choice,
        "ceremony_id": "renewal-decision-ceremony-001",
        "nonce": "renewal-decision-nonce-0001",
        "issued_at": "2026-10-05T21:00:00Z",
        "expires_at": "2026-10-05T21:03:00Z",
    }
    args.update(overrides)
    return build_owner_renewal_decision_request(**args)


class OwnerRenewalDecisionRequestTests(unittest.TestCase):
    def test_allowed_choice_builds_signature_request_only(self):
        out = build()
        self.assertEqual(out["schema"], SCHEMA)
        self.assertEqual(out["state"], "READY_FOR_EXPLICIT_OWNER_SIGNATURE")
        self.assertEqual(
            out["request"]["requested_choice"],
            "RENEW_AS_IS_REVIEW",
        )
        self.assertTrue(out["request_digest"].startswith("sha256:"))
        self.assertTrue(out["owner_signature_required"])
        self.assertFalse(out["owner_signature_verified"])
        self.assertFalse(out["owner_decision_verified"])
        self.assertFalse(out["owner_decision_recorded"])
        self.assertFalse(out["decision_persisted"])
        self.assertFalse(out["renewal_authorized"])
        self.assertFalse(out["executes_action"])

    def test_non_renewal_choice_does_not_terminate_or_change_service(self):
        out = build("NON_RENEWAL_REVIEW")
        self.assertEqual(out["state"], "READY_FOR_EXPLICIT_OWNER_SIGNATURE")
        self.assertFalse(out["termination_authorized"])
        self.assertFalse(out["pause_authorized"])
        self.assertFalse(out["customer_contact_authorized"])
        self.assertFalse(out["billing_authorized"])

    def test_generic_chat_instruction_is_not_a_decision(self):
        for choice in ("vamos lá", "ok", "sim", "aprovado"):
            with self.subTest(choice=choice):
                out = build(choice)
                self.assertEqual(out["state"], "BLOCKED")
                self.assertIn(
                    "GENERIC_CHAT_INSTRUCTION_NOT_ACCEPTED_AS_DECISION",
                    out["blockers"],
                )
                self.assertFalse(
                    out["generic_chat_instruction_accepted_as_decision"]
                )

    def test_choice_must_exist_in_exact_review_packet(self):
        out = build("EXPAND_NOW")
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "OWNER_RENEWAL_CHOICE_NOT_ALLOWED_BY_PACKET",
            out["blockers"],
        )

    def test_scope_mismatch_fails_closed(self):
        bad = packet()
        bad["scope"] = {**SCOPE, "tenant_id": "tenant-other"}
        out = build(owner_review_packet=bad)
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("OWNER_REVIEW_PACKET_SCOPE_MISMATCH", out["blockers"])

    def test_packet_with_blocker_fails_closed(self):
        out = build(owner_review_packet=packet(blockers=["SOMETHING"]))
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("OWNER_REVIEW_PACKET_HAS_BLOCKERS", out["blockers"])

    def test_unsafe_packet_authority_fails_closed(self):
        out = build(
            owner_review_packet=packet(automatic_renewal=True),
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "OWNER_REVIEW_PACKET_UNSAFE_FIELD:automatic_renewal",
            out["blockers"],
        )

    def test_request_binds_customer_pilot_and_value_lineage_digests(self):
        out = build()
        request = out["request"]
        self.assertEqual(request["customer_id"], "customer-a")
        self.assertEqual(request["pilot_id"], "pilot-a")
        self.assertEqual(request["package"], "PROFISSIONAL")
        self.assertEqual(
            request["owner_review_packet_digest"],
            "sha256:owner-review",
        )
        self.assertEqual(request["cycle_evidence_digest"], "sha256:cycle")
        self.assertEqual(request["contract_digest"], "sha256:contract")
        self.assertEqual(
            request["value_bound_conversion_digest"],
            "sha256:value-bound",
        )

    def test_request_digest_is_deterministic(self):
        first = build()
        second = build()
        self.assertEqual(first["request_digest"], second["request_digest"])

    def test_short_nonce_blocks(self):
        out = build(nonce="short")
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("NONCE_INVALID", out["blockers"])

    def test_no_external_authority_is_granted(self):
        out = build()
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
            self.assertFalse(out[key], key)


if __name__ == "__main__":
    unittest.main()
