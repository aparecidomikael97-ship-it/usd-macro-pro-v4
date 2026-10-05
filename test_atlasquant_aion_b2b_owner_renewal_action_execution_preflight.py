from __future__ import annotations

import unittest

from atlasquant_aion_b2b_owner_renewal_action_execution_preflight import (
    ACTION_REQUIRED_PRECONDITIONS,
    ENVIRONMENT_SCHEMA,
    evaluate_owner_renewal_action_execution_preflight,
)
from atlasquant_aion_b2b_owner_renewal_action_persistence_attestation import (
    SCHEMA as PERSISTENCE_SCHEMA,
)
from atlasquant_aion_b2b_owner_renewal_action_preflight import (
    SCHEMA as AUTHORIZATION_PREFLIGHT_SCHEMA,
)
from atlasquant_aion_b2b_owner_renewal_action_writer_attestation import (
    RESULT_SCHEMA as WRITER_SCHEMA,
)

SCOPE = {
    "owner_id": "owner-a",
    "tenant_id": "tenant-a",
    "workspace_id": "workspace-a",
}
NOW = "2026-10-05T22:30:00Z"


def h(char):
    return "sha256:" + char * 64


def persistence(
    *,
    decision="AUTHORIZE_BUSINESS_ACTION",
    choice="RENEW_AS_IS_REVIEW",
    family="RENEWAL",
    review_type="RENEWAL_REVIEW",
    **overrides,
):
    row = {
        "schema": PERSISTENCE_SCHEMA,
        "state": "OWNER_RENEWAL_ACTION_RECORD_PERSISTENCE_ATTESTED",
        "blockers": [],
        "authorization_decision": decision,
        "requested_choice": choice,
        "action_family": family,
        "scope": dict(SCOPE),
        **SCOPE,
        "customer_id": "customer-a",
        "pilot_id": "pilot-a",
        "package": "PROFISSIONAL",
        "review_type": review_type,
        "owner_review_packet_digest": "sha256:review",
        "cycle_evidence_digest": "sha256:cycle",
        "contract_digest": "sha256:contract",
        "value_bound_conversion_digest": "sha256:value-bound",
        "decision_record_digest": "sha256:decision",
        "prior_persistence_receipt_digest": "sha256:prior-receipt",
        "prior_checkpoint_digest": "sha256:prior-checkpoint",
        "prior_writer_request_digest": "sha256:prior-writer",
        "authorization_environment_digest": "sha256:auth-environment",
        "authorization_preflight_digest": h("a"),
        "authorization_request_digest": "sha256:auth-request",
        "action_record_digest": h("b"),
        "checkpoint_revision": 4,
        "checkpoint_state_digest": h("c"),
        "before_checkpoint_digest": h("d"),
        "after_checkpoint_digest": h("e"),
        "receipt_digest": h("f"),
        "action_record_persisted": True,
        "persistence_attested": True,
        "receipt_consistency_verified": True,
        "writer_identity_verified": False,
        "eligible_for_action_execution_preflight": (
            decision == "AUTHORIZE_BUSINESS_ACTION"
        ),
        "storage_write_performed": False,
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


def writer(
    *,
    decision="AUTHORIZE_BUSINESS_ACTION",
    choice="RENEW_AS_IS_REVIEW",
    family="RENEWAL",
    **overrides,
):
    row = {
        "schema": WRITER_SCHEMA,
        "state": "ACTION_CHECKPOINT_WRITER_AUTHORITY_ATTESTED",
        "blockers": [],
        "customer_id": "customer-a",
        "pilot_id": "pilot-a",
        "requested_choice": choice,
        "action_family": family,
        "authorization_decision": decision,
        "receipt_digest": h("f"),
        "after_checkpoint_digest": h("e"),
        "action_record_digest": h("b"),
        "event_id": "aion-b2b-owner-renewal-action-001",
        "writer_ref": "checkpoint-writer:recurring-action",
        "writer_key_id": "action-writer-key",
        "writer_key_version": 1,
        "writer_public_key_fingerprint": h("1"),
        "writer_request_digest": h("2"),
        "writer_identity_verified": True,
        "writer_authority_verified": True,
        "receipt_binding_verified": True,
        "nonce_registered": True,
        "checkpoint_write_performed": False,
        "eligible_for_action_execution_preflight": (
            decision == "AUTHORIZE_BUSINESS_ACTION"
        ),
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


def authorization_preflight(
    *,
    choice="RENEW_AS_IS_REVIEW",
    family="RENEWAL",
    review_type="RENEWAL_REVIEW",
    **overrides,
):
    row = {
        "schema": AUTHORIZATION_PREFLIGHT_SCHEMA,
        "state": "READY_FOR_BUSINESS_ACTION_AUTHORIZATION_CEREMONY",
        "blockers": [],
        "scope": dict(SCOPE),
        **SCOPE,
        "customer_id": "customer-a",
        "pilot_id": "pilot-a",
        "package": "PROFISSIONAL",
        "review_type": review_type,
        "requested_choice": choice,
        "action_family": family,
        "owner_review_packet_digest": "sha256:review",
        "cycle_evidence_digest": "sha256:cycle",
        "contract_digest": "sha256:contract",
        "value_bound_conversion_digest": "sha256:value-bound",
        "decision_record_digest": "sha256:decision",
        "persistence_receipt_digest": "sha256:prior-receipt",
        "checkpoint_digest": "sha256:prior-checkpoint",
        "writer_request_digest": "sha256:prior-writer",
        "environment_digest": "sha256:auth-environment",
        "preflight_digest": h("a"),
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


def environment(
    *,
    choice="RENEW_AS_IS_REVIEW",
    family="RENEWAL",
    review_type="RENEWAL_REVIEW",
    service_state="HEALTHY",
    **overrides,
):
    all_preconditions = {
        key: True
        for keys in ACTION_REQUIRED_PRECONDITIONS.values()
        for key in keys
    }
    row = {
        "schema": ENVIRONMENT_SCHEMA,
        "state": "VERIFIED",
        **SCOPE,
        "customer_id": "customer-a",
        "pilot_id": "pilot-a",
        "package": "PROFISSIONAL",
        "review_type": review_type,
        "requested_choice": choice,
        "action_family": family,
        "service_state": service_state,
        "execution_mode": "CONTROLLED_MANAGED_SERVICE_ACTION",
        "checked_at": "2026-10-05T22:29:00Z",
        "action_window_reserved": True,
        "production_scope_expansion_allowed": False,
        "contract_digest": "sha256:contract",
        "cycle_evidence_digest": "sha256:cycle",
        "tenant_isolation_ready": True,
        "contract_snapshot_fresh": True,
        "service_health_fresh": True,
        "sla_state_fresh": True,
        "finops_state_fresh": True,
        "capacity_state_fresh": True,
        "support_state_fresh": True,
        "rollback_or_reversal_ready": True,
        "audit_receipts_ready": True,
        "idempotency_key_ready": True,
        "single_action_lock_ready": True,
        "customer_safe_projection_ready": True,
        "kill_switch_ready": True,
        "dry_run_validation_pass": True,
        "security_incident": False,
        "privacy_incident": False,
        "scope_breach": False,
        "provider_degraded": False,
        "rollback_degraded": False,
        "contract_conflict": False,
        "unresolved_billing_dispute": False,
        "action_parameters_digest": h("3"),
        "service_health_digest": h("4"),
        "sla_digest": h("5"),
        "finops_digest": h("6"),
        "capacity_digest": h("7"),
        "support_digest": h("8"),
        "security_digest": h("9"),
        "customer_safe_projection_digest": h("0"),
        "action_preconditions": all_preconditions,
        "reserved_capacity_units": 10,
        "available_capacity_units": 100,
        "planned_monthly_infra_brl": 180.0,
        "evidence_refs": [
            "exec:tenant",
            "exec:contract",
            "exec:health",
            "exec:sla",
            "exec:finops",
            "exec:capacity",
            "exec:support",
            "exec:security",
        ],
    }
    row.update(overrides)
    return row


def run(**overrides):
    args = {
        "trusted_scope": SCOPE,
        "action_persistence_attestation": persistence(),
        "action_writer_attestation": writer(),
        "authorization_preflight": authorization_preflight(),
        "execution_environment": environment(),
        "now_ts": NOW,
    }
    args.update(overrides)
    return evaluate_owner_renewal_action_execution_preflight(**args)


class OwnerRenewalActionExecutionPreflightTests(unittest.TestCase):
    def test_valid_chain_is_execution_ceremony_eligible_only(self):
        out = run()
        self.assertEqual(
            out["state"],
            "READY_FOR_BUSINESS_ACTION_EXECUTION_CEREMONY",
        )
        self.assertFalse(out["blockers"])
        self.assertTrue(out["business_action_execution_ceremony_eligible"])
        self.assertTrue(out["human_execution_confirmation_required"])
        self.assertFalse(out["execution_request_issued"])
        self.assertFalse(out["owner_execution_signature_verified"])
        self.assertFalse(out["execution_command_generated"])
        self.assertFalse(out["execution_command_executed"])
        self.assertFalse(out["business_action_authorized"])
        self.assertFalse(out["renewal_authorized"])
        self.assertFalse(out["executes_action"])

    def test_persisted_denial_blocks(self):
        out = run(
            action_persistence_attestation=persistence(
                decision="DENY_BUSINESS_ACTION",
            ),
            action_writer_attestation=writer(
                decision="DENY_BUSINESS_ACTION",
            ),
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("BUSINESS_ACTION_DENIED", out["blockers"])

    def test_writer_receipt_must_match_persistence(self):
        out = run(
            action_writer_attestation=writer(
                receipt_digest=h("9")
            )
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "ACTION_WRITER_BINDING_MISMATCH:receipt_digest",
            out["blockers"],
        )

    def test_original_authorization_preflight_digest_must_match(self):
        out = run(
            authorization_preflight=authorization_preflight(
                preflight_digest=h("9")
            )
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "ORIGINAL_AUTHORIZATION_PREFLIGHT_DIGEST_MISMATCH",
            out["blockers"],
        )

    def test_execution_environment_is_customer_bound(self):
        out = run(
            execution_environment=environment(
                customer_id="customer-other"
            )
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "EXECUTION_ENVIRONMENT_CUSTOMER_MISMATCH",
            out["blockers"],
        )

    def test_execution_environment_must_be_fresh(self):
        out = run(
            execution_environment=environment(
                checked_at="2026-10-05T22:20:00Z"
            )
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("EXECUTION_ENVIRONMENT_STALE", out["blockers"])

    def test_security_or_contract_problem_blocks(self):
        for key in (
            "security_incident",
            "privacy_incident",
            "scope_breach",
            "provider_degraded",
            "rollback_degraded",
            "contract_conflict",
            "unresolved_billing_dispute",
        ):
            with self.subTest(key=key):
                env = environment()
                env[key] = True
                out = run(execution_environment=env)
                self.assertEqual(out["state"], "BLOCKED")
                self.assertIn(
                    "EXECUTION_ENVIRONMENT_BLOCKED:" + key,
                    out["blockers"],
                )

    def test_service_state_must_match_review_lineage(self):
        out = run(
            execution_environment=environment(
                service_state="REMEDIATION"
            )
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "EXECUTION_SERVICE_STATE_MISMATCH",
            out["blockers"],
        )

    def test_contract_and_cycle_lineage_are_immutable(self):
        for key, blocker in (
            ("contract_digest", "EXECUTION_CONTRACT_DIGEST_MISMATCH"),
            ("cycle_evidence_digest", "EXECUTION_CYCLE_DIGEST_MISMATCH"),
        ):
            with self.subTest(key=key):
                env = environment()
                env[key] = "sha256:changed"
                out = run(execution_environment=env)
                self.assertEqual(out["state"], "BLOCKED")
                self.assertIn(blocker, out["blockers"])

    def test_capacity_must_fit(self):
        out = run(
            execution_environment=environment(
                reserved_capacity_units=101,
                available_capacity_units=100,
            )
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("EXECUTION_CAPACITY_INSUFFICIENT", out["blockers"])

    def test_global_infra_cap_is_enforced(self):
        out = run(
            execution_environment=environment(
                planned_monthly_infra_brl=200.01
            )
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "EXECUTION_MONTHLY_INFRA_CAP_EXCEEDED",
            out["blockers"],
        )

    def test_action_parameters_digest_is_required(self):
        out = run(
            execution_environment=environment(
                action_parameters_digest="sha256:not-valid"
            )
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "EXECUTION_ENVIRONMENT_DIGEST_INVALID:action_parameters_digest",
            out["blockers"],
        )

    def test_each_action_family_has_specific_fresh_preconditions(self):
        cases = (
            ("RENEWAL", "RENEWAL_REVIEW", "HEALTHY"),
            ("RENEWAL_WITH_CHANGES", "REMEDIATION_REVIEW", "REMEDIATION"),
            ("NON_RENEWAL", "CAPACITY_REVIEW", "CAPACITY_HOLD"),
            ("REMEDIATION", "REMEDIATION_REVIEW", "REMEDIATION"),
            ("CAPACITY_RESCOPE", "CAPACITY_REVIEW", "CAPACITY_HOLD"),
            ("REPRICING", "CAPACITY_REVIEW", "CAPACITY_HOLD"),
            ("INCIDENT_REMEDIATION", "INCIDENT_REVIEW", "INCIDENT_REVIEW"),
            ("SERVICE_PAUSE", "INCIDENT_REVIEW", "INCIDENT_REVIEW"),
            ("SERVICE_TERMINATION", "INCIDENT_REVIEW", "INCIDENT_REVIEW"),
        )
        for family, review_type, service_state in cases:
            with self.subTest(family=family):
                choice = family + "_CHOICE"
                persisted = persistence(
                    choice=choice,
                    family=family,
                    review_type=review_type,
                )
                wr = writer(choice=choice, family=family)
                original = authorization_preflight(
                    choice=choice,
                    family=family,
                    review_type=review_type,
                )
                env = environment(
                    choice=choice,
                    family=family,
                    review_type=review_type,
                    service_state=service_state,
                )
                out = run(
                    action_persistence_attestation=persisted,
                    action_writer_attestation=wr,
                    authorization_preflight=original,
                    execution_environment=env,
                )
                self.assertEqual(
                    out["state"],
                    "READY_FOR_BUSINESS_ACTION_EXECUTION_CEREMONY",
                )

    def test_missing_family_specific_precondition_blocks(self):
        env = environment()
        env["action_preconditions"] = dict(
            env["action_preconditions"]
        )
        env["action_preconditions"]["renewal_terms_snapshot_ready"] = False
        out = run(execution_environment=env)
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "EXECUTION_ACTION_PRECONDITION_MISSING:renewal_terms_snapshot_ready",
            out["blockers"],
        )

    def test_execution_evidence_requires_eight_refs(self):
        out = run(
            execution_environment=environment(
                evidence_refs=["1", "2", "3", "4", "5", "6", "7"]
            )
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "EXECUTION_ENVIRONMENT_EVIDENCE_INSUFFICIENT",
            out["blockers"],
        )

    def test_preflight_never_generates_or_executes_command(self):
        out = run()
        for key in (
            "execution_request_issued",
            "owner_execution_signature_verified",
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
            self.assertFalse(out[key], key)

    def test_preflight_digest_is_deterministic(self):
        first = run()
        second = run()
        self.assertEqual(
            first["execution_preflight_digest"],
            second["execution_preflight_digest"],
        )
        self.assertEqual(
            first["execution_environment_digest"],
            second["execution_environment_digest"],
        )


if __name__ == "__main__":
    unittest.main()
