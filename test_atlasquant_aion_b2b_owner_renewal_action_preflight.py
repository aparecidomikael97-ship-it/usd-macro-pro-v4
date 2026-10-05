from __future__ import annotations

import unittest

from atlasquant_aion_b2b_owner_renewal_action_preflight import (
    ACTION_FAMILY,
    ENVIRONMENT_SCHEMA,
    evaluate_owner_renewal_action_preflight,
)
from atlasquant_aion_b2b_owner_renewal_persistence_attestation import (
    SCHEMA as PERSISTENCE_SCHEMA,
)
from atlasquant_aion_b2b_owner_renewal_review import (
    SCHEMA as OWNER_REVIEW_SCHEMA,
)
from atlasquant_aion_b2b_owner_renewal_writer_attestation import (
    RESULT_SCHEMA as WRITER_SCHEMA,
)
from atlasquant_aion_b2b_value_bound_service_cycle import (
    SCHEMA as SERVICE_CYCLE_SCHEMA,
)

SCOPE = {
    "owner_id": "owner-a",
    "tenant_id": "tenant-a",
    "workspace_id": "workspace-a",
}
NOW = "2026-10-05T21:50:00Z"
CYCLE_DIGEST = "sha256:cycle-evidence"
REVIEW_DIGEST = "sha256:owner-review"
CONTRACT_DIGEST = "sha256:contract"
CONVERSION_DIGEST = "sha256:value-bound"
DECISION_RECORD_DIGEST = "sha256:decision-record"
RECEIPT_DIGEST = "sha256:persistence-receipt"
CHECKPOINT_DIGEST = "sha256:checkpoint-after"


def persistence(choice="RENEW_AS_IS_REVIEW", **overrides):
    row = {
        "schema": PERSISTENCE_SCHEMA,
        "state": "OWNER_RENEWAL_DECISION_PERSISTENCE_ATTESTED",
        "blockers": [],
        "requested_choice": choice,
        "scope": dict(SCOPE),
        **SCOPE,
        "customer_id": "customer-a",
        "pilot_id": "pilot-a",
        "package": "PROFISSIONAL",
        "review_type": "RENEWAL_REVIEW",
        "owner_review_packet_digest": REVIEW_DIGEST,
        "cycle_evidence_digest": CYCLE_DIGEST,
        "contract_digest": CONTRACT_DIGEST,
        "value_bound_conversion_digest": CONVERSION_DIGEST,
        "decision_request_digest": "sha256:decision-request",
        "signature_request_digest": "sha256:signature-request",
        "decision_record_digest": DECISION_RECORD_DIGEST,
        "checkpoint_revision": 1,
        "checkpoint_state_digest": "sha256:checkpoint-state",
        "before_checkpoint_digest": "sha256:checkpoint-before",
        "after_checkpoint_digest": CHECKPOINT_DIGEST,
        "receipt_digest": RECEIPT_DIGEST,
        "owner_decision_recorded": True,
        "decision_persisted": True,
        "persistence_attested": True,
        "receipt_consistency_verified": True,
        "writer_identity_verified": False,
        "eligible_for_action_preflight": True,
        "storage_write_performed": False,
        "network_called": False,
        "renewal_authorized": False,
        "expansion_authorized": False,
        "pause_authorized": False,
        "termination_authorized": False,
        "billing_authorized": False,
        "pricing_change_authorized": False,
        "quota_change_authorized": False,
        "role_change_authorized": False,
        "integration_change_authorized": False,
        "customer_contact_authorized": False,
        "provisioning_authorized": False,
        "deploy_authorized": False,
        "provider_called": False,
        "crm_write_authorized": False,
        "production_mutation_authorized": False,
        "external_action_executed": False,
        "executes_action": False,
    }
    row.update(overrides)
    return row


def writer(choice="RENEW_AS_IS_REVIEW", **overrides):
    row = {
        "schema": WRITER_SCHEMA,
        "state": "CHECKPOINT_WRITER_AUTHORITY_ATTESTED",
        "blockers": [],
        "customer_id": "customer-a",
        "pilot_id": "pilot-a",
        "requested_choice": choice,
        "receipt_digest": RECEIPT_DIGEST,
        "after_checkpoint_digest": CHECKPOINT_DIGEST,
        "decision_record_digest": DECISION_RECORD_DIGEST,
        "event_id": "event-001",
        "writer_ref": "writer:trusted",
        "writer_key_id": "writer-key",
        "writer_key_version": 1,
        "writer_public_key_fingerprint": "sha256:writer-key",
        "writer_request_digest": "sha256:writer-request",
        "writer_identity_verified": True,
        "writer_authority_verified": True,
        "receipt_binding_verified": True,
        "nonce_registered": True,
        "checkpoint_write_performed": False,
        "business_action_authorized": False,
        "renewal_authorized": False,
        "expansion_authorized": False,
        "pause_authorized": False,
        "termination_authorized": False,
        "billing_authorized": False,
        "pricing_change_authorized": False,
        "quota_change_authorized": False,
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


def review(choice="RENEW_AS_IS_REVIEW", **overrides):
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
        "cycle_evidence_digest": CYCLE_DIGEST,
        "contract_digest": CONTRACT_DIGEST,
        "value_bound_conversion_digest": CONVERSION_DIGEST,
        "evidence_digest": REVIEW_DIGEST,
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


def cycle(**overrides):
    row = {
        "schema": SERVICE_CYCLE_SCHEMA,
        "state": "HEALTHY",
        "decision": "RENEWAL_REVIEW_CANDIDATE",
        "scope": dict(SCOPE),
        **SCOPE,
        "customer_id": "customer-a",
        "pilot_id": "pilot-a",
        "package": "PROFISSIONAL",
        "health_score": 88.0,
        "observed_roi_pct": 60.0,
        "actual_service_cost_brl": 2200.0,
        "review_reasons": [],
        "incident_reasons": [],
        "blockers": [],
        "contract_digest": CONTRACT_DIGEST,
        "value_bound_conversion_digest": CONVERSION_DIGEST,
        "source_cycle_evidence_digest": "sha256:source-cycle",
        "evidence_digest": CYCLE_DIGEST,
        "owner_review_required": True,
        "customer_visible": False,
        "contains_internal_finops": True,
        "requires_customer_safe_projection": True,
        "automatic_renewal": False,
        "automatic_expansion": False,
        "automatic_package_change": False,
        "automatic_pause": False,
        "automatic_termination": False,
        "automatic_billing": False,
        "automatic_quota_increase": False,
        "automatic_role_change": False,
        "automatic_integration_change": False,
        "automatic_customer_contact": False,
        "automatic_provisioning": False,
        "automatic_deploy": False,
        "provider_called": False,
        "production_mutation": False,
        "executes_action": False,
    }
    row.update(overrides)
    return row


def environment(choice="RENEW_AS_IS_REVIEW", **overrides):
    all_preconditions = {
        "renewal_terms_confirmed": True,
        "no_material_change_requested": True,
        "change_scope_defined": True,
        "contract_change_review_ready": True,
        "offboarding_plan_ready": True,
        "data_retention_plan_ready": True,
        "remediation_plan_ready": True,
        "remediation_owner_identified": True,
        "capacity_plan_ready": True,
        "capacity_impact_assessed": True,
        "pricing_rationale_ready": True,
        "pricing_review_packet_ready": True,
        "incident_remediation_plan_ready": True,
        "incident_containment_ready": True,
        "pause_plan_ready": True,
        "customer_impact_assessed": True,
        "termination_plan_ready": True,
    }
    row = {
        "schema": ENVIRONMENT_SCHEMA,
        "state": "VERIFIED",
        **SCOPE,
        "customer_id": "customer-a",
        "pilot_id": "pilot-a",
        "package": "PROFISSIONAL",
        "checked_at": "2026-10-05T21:49:00Z",
        "tenant_isolation_ready": True,
        "audit_receipts_ready": True,
        "service_snapshot_fresh": True,
        "contract_snapshot_fresh": True,
        "support_state_known": True,
        "billing_state_known": True,
        "capacity_state_known": True,
        "customer_safe_projection_ready": True,
        "rollback_or_reversal_plan_ready": True,
        "security_incident": False,
        "privacy_incident": False,
        "scope_breach": False,
        "projected_monthly_infra_brl": 180.0,
        "evidence_refs": [
            "action:service",
            "action:contract",
            "action:support",
            "action:audit",
        ],
        "choice_preconditions": all_preconditions,
    }
    row.update(overrides)
    return row


def run(choice="RENEW_AS_IS_REVIEW", **overrides):
    data = {
        "trusted_scope": SCOPE,
        "persistence_attestation": persistence(choice),
        "writer_attestation": writer(choice),
        "owner_review_packet": review(choice),
        "service_cycle": cycle(),
        "action_environment": environment(choice),
        "now_ts": NOW,
    }
    data.update(overrides)
    return evaluate_owner_renewal_action_preflight(**data)


class OwnerRenewalActionPreflightTests(unittest.TestCase):
    def test_renew_as_is_is_ceremony_eligible_only(self):
        out = run()
        self.assertEqual(
            out["state"],
            "READY_FOR_BUSINESS_ACTION_AUTHORIZATION_CEREMONY",
        )
        self.assertEqual(out["action_family"], "RENEWAL")
        self.assertTrue(out["action_ceremony_eligible"])
        self.assertTrue(out["owner_action_signature_required"])
        self.assertFalse(out["action_request_issued"])
        self.assertFalse(out["owner_action_signature_verified"])
        self.assertFalse(out["business_action_authorized"])
        self.assertFalse(out["renewal_authorized"])
        self.assertFalse(out["executes_action"])

    def test_all_supported_choices_map_to_action_families(self):
        cases = {
            "RENEW_AS_IS_REVIEW": ("RENEWAL", "RENEWAL_REVIEW"),
            "RENEW_WITH_CHANGES_REVIEW": (
                "RENEWAL_WITH_CHANGES",
                "RENEWAL_REVIEW",
            ),
            "NON_RENEWAL_REVIEW": ("NON_RENEWAL", "RENEWAL_REVIEW"),
            "REMEDIATION_PLAN_REVIEW": (
                "REMEDIATION",
                "REMEDIATION_REVIEW",
            ),
            "RESCOPE_CAPACITY_REVIEW": (
                "CAPACITY_RESCOPE",
                "CAPACITY_REVIEW",
            ),
            "REPRICE_REVIEW": ("REPRICING", "CAPACITY_REVIEW"),
            "INCIDENT_REMEDIATION_REVIEW": (
                "INCIDENT_REMEDIATION",
                "INCIDENT_REVIEW",
            ),
            "PAUSE_SERVICE_REVIEW": (
                "SERVICE_PAUSE",
                "INCIDENT_REVIEW",
            ),
            "TERMINATION_REVIEW": (
                "SERVICE_TERMINATION",
                "INCIDENT_REVIEW",
            ),
        }
        cycle_by_review = {
            "RENEWAL_REVIEW": (
                "HEALTHY",
                "RENEWAL_REVIEW_CANDIDATE",
            ),
            "REMEDIATION_REVIEW": (
                "REMEDIATION",
                "REMEDIATE_REVIEW",
            ),
            "CAPACITY_REVIEW": (
                "CAPACITY_HOLD",
                "CAPACITY_REVIEW",
            ),
            "INCIDENT_REVIEW": (
                "INCIDENT_REVIEW",
                "INCIDENT_REVIEW",
            ),
        }
        choices_by_review = {
            "RENEWAL_REVIEW": [
                "RENEW_AS_IS_REVIEW",
                "RENEW_WITH_CHANGES_REVIEW",
                "NON_RENEWAL_REVIEW",
            ],
            "REMEDIATION_REVIEW": [
                "REMEDIATION_PLAN_REVIEW",
                "RENEW_WITH_CHANGES_REVIEW",
                "NON_RENEWAL_REVIEW",
            ],
            "CAPACITY_REVIEW": [
                "RESCOPE_CAPACITY_REVIEW",
                "REPRICE_REVIEW",
                "NON_RENEWAL_REVIEW",
            ],
            "INCIDENT_REVIEW": [
                "INCIDENT_REMEDIATION_REVIEW",
                "PAUSE_SERVICE_REVIEW",
                "TERMINATION_REVIEW",
            ],
        }
        for choice, (family, review_type) in cases.items():
            with self.subTest(choice=choice):
                state, decision = cycle_by_review[review_type]
                out = run(
                    choice,
                    persistence_attestation=persistence(
                        choice,
                        review_type=review_type,
                    ),
                    owner_review_packet=review(
                        choice,
                        review_type=review_type,
                        service_state=state,
                        service_decision=decision,
                        allowed_owner_choices=choices_by_review[review_type],
                    ),
                    service_cycle=cycle(
                        state=state,
                        decision=decision,
                    ),
                )
                self.assertEqual(
                    out["state"],
                    "READY_FOR_BUSINESS_ACTION_AUTHORIZATION_CEREMONY",
                )
                self.assertEqual(out["action_family"], family)
                self.assertEqual(ACTION_FAMILY[choice], family)

    def test_writer_must_bind_same_choice(self):
        out = run(
            writer_attestation=writer("NON_RENEWAL_REVIEW")
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("WRITER_CHOICE_MISMATCH", out["blockers"])

    def test_review_packet_digest_change_blocks(self):
        out = run(
            owner_review_packet=review(
                evidence_digest="sha256:different-review"
            )
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "OWNER_REVIEW_PACKET_DIGEST_MISMATCH",
            out["blockers"],
        )

    def test_service_cycle_change_blocks(self):
        out = run(
            service_cycle=cycle(
                evidence_digest="sha256:different-cycle"
            )
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "SERVICE_CYCLE_EVIDENCE_DIGEST_MISMATCH",
            out["blockers"],
        )

    def test_cross_customer_environment_blocks(self):
        out = run(
            action_environment=environment(
                customer_id="customer-other"
            )
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "ACTION_ENVIRONMENT_CUSTOMER_MISMATCH",
            out["blockers"],
        )

    def test_stale_environment_blocks(self):
        out = run(
            action_environment=environment(
                checked_at="2026-10-05T21:40:00Z"
            )
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("ACTION_ENVIRONMENT_STALE", out["blockers"])

    def test_security_or_privacy_incident_blocks(self):
        for key in ("security_incident", "privacy_incident", "scope_breach"):
            with self.subTest(key=key):
                env = environment()
                env[key] = True
                out = run(action_environment=env)
                self.assertEqual(out["state"], "BLOCKED")
                self.assertIn(
                    "ACTION_ENVIRONMENT_INCIDENT:" + key,
                    out["blockers"],
                )

    def test_global_infra_cap_is_enforced(self):
        out = run(
            action_environment=environment(
                projected_monthly_infra_brl=201.0
            )
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "ACTION_ENVIRONMENT_GLOBAL_INFRA_CAP_EXCEEDED",
            out["blockers"],
        )

    def test_choice_specific_precondition_is_mandatory(self):
        env = environment()
        env["choice_preconditions"] = dict(
            env["choice_preconditions"]
        )
        env["choice_preconditions"]["renewal_terms_confirmed"] = False
        out = run(action_environment=env)
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "ACTION_CHOICE_PRECONDITION_MISSING:renewal_terms_confirmed",
            out["blockers"],
        )

    def test_insufficient_evidence_blocks(self):
        out = run(
            action_environment=environment(
                evidence_refs=["one", "two", "three"]
            )
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "ACTION_ENVIRONMENT_EVIDENCE_INSUFFICIENT",
            out["blockers"],
        )

    def test_preflight_digest_is_deterministic(self):
        first = run()
        second = run()
        self.assertEqual(
            first["preflight_digest"],
            second["preflight_digest"],
        )
        self.assertEqual(
            first["environment_digest"],
            second["environment_digest"],
        )

    def test_preflight_never_grants_business_authority(self):
        out = run()
        for key in (
            "action_request_issued",
            "owner_action_signature_verified",
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
            self.assertFalse(out[key], key)


if __name__ == "__main__":
    unittest.main()
