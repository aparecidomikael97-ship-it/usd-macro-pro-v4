from __future__ import annotations

import unittest

from atlasquant_aion_b2b_multi_company_admission import (
    evaluate_multi_company_admission,
)

SCOPE = {
    "owner_id": "owner-a",
    "tenant_id": "atlasquant-owner",
    "workspace_id": "business",
}


def value_result(**overrides):
    row = {
        "schema": "ATLASQUANT_AION_B2B_PILOT_VALUE_REALIZATION_V1",
        "state": "STRONG_VALUE",
        "recommendation": "EXPANSION_REVIEW_CANDIDATE",
        "pilot_id": "pilot-001",
        "scope": dict(SCOPE),
        "low_value_alert": False,
        "owner_review_required": True,
        "blockers": [],
        "evidence_digest": "sha256:" + "1" * 64,
        "automatic_renewal": False,
        "automatic_expansion": False,
        "automatic_pause": False,
        "automatic_termination": False,
        "automatic_scope_change": False,
        "automatic_contract_change": False,
        "automatic_billing": False,
        "automatic_customer_contact": False,
        "automatic_provisioning": False,
        "automatic_deploy": False,
        "crm_write": False,
        "provider_called": False,
        "production_mutation": False,
        "executes_action": False,
    }
    row.update(overrides)
    return row


def conversion(**overrides):
    row = {
        "schema": "ATLASQUANT_AION_B2B_CONVERSION_CAPACITY_V1",
        "state": "REVIEWABLE",
        "decision": "COMMERCIAL_REVIEW_CANDIDATE",
        "customer_id": "customer-001",
        "recommended_package": "PROFISSIONAL",
        "review_reasons": [],
        "blockers": [],
        "evidence_digest": "sha256:" + "2" * 64,
        "owner_commercial_approval_required": True,
        "automatic_conversion": False,
        "automatic_package_change": False,
        "automatic_pricing_change": False,
        "automatic_contract": False,
        "automatic_billing": False,
        "automatic_provisioning": False,
        "automatic_customer_contact": False,
        "automatic_deploy": False,
        "production_mutation": False,
        "executes_action": False,
    }
    row.update(overrides)
    return row


def policy(**overrides):
    row = {
        "schema": "ATLASQUANT_AION_B2B_MULTI_COMPANY_POLICY_V1",
        "state": "VERIFIED",
        **SCOPE,
        "max_active_tenants": 10,
        "max_total_capacity_units": 300,
        "max_total_calls_per_cycle": 10000,
        "max_total_tokens_per_cycle": 10000000,
        "max_total_support_tickets_per_cycle": 200,
        "min_portfolio_reserve_pct": 15.0,
        "max_single_tenant_share_pct": 30.0,
        "max_tenant_utilization_pct": 85.0,
        "max_channels_per_tenant": 4,
        "max_integrations_per_tenant": 5,
        "evidence_refs": [
            "policy:capacity",
            "policy:concentration",
            "policy:noisy-neighbor",
            "policy:channels",
        ],
    }
    row.update(overrides)
    return row


def active_tenant(
    tenant_id,
    customer_id,
    *,
    capacity_units=40,
    calls_per_cycle=1000,
    tokens_per_cycle=1000000,
    support_tickets_per_cycle=20,
    utilization=60.0,
):
    return {
        "service_tenant_id": tenant_id,
        "customer_id": customer_id,
        "package": "PROFISSIONAL",
        "quotas": {
            "capacity_units": capacity_units,
            "calls_per_cycle": calls_per_cycle,
            "tokens_per_cycle": tokens_per_cycle,
            "support_tickets_per_cycle": support_tickets_per_cycle,
        },
        "utilization_pct": {
            "capacity_units": utilization,
            "calls_per_cycle": utilization,
            "tokens_per_cycle": utilization,
            "support_tickets_per_cycle": utilization,
        },
    }


def portfolio(**overrides):
    row = {
        "schema": "ATLASQUANT_AION_B2B_MULTI_COMPANY_PORTFOLIO_V1",
        "state": "VERIFIED",
        **SCOPE,
        "active_tenants": [
            active_tenant("tenant-alpha-001", "customer-alpha"),
            active_tenant("tenant-beta-001", "customer-beta"),
        ],
        "evidence_refs": [
            "portfolio:tenants",
            "portfolio:quotas",
            "portfolio:usage",
            "portfolio:audit",
        ],
    }
    row.update(overrides)
    return row


def request(**overrides):
    row = {
        **SCOPE,
        "customer_id": "customer-001",
        "service_tenant_id": "customer-001-prod",
        "package": "PROFISSIONAL",
        "requested_quotas": {
            "capacity_units": 40,
            "calls_per_cycle": 1000,
            "tokens_per_cycle": 1000000,
            "support_tickets_per_cycle": 20,
        },
        "channel_count": 3,
        "integration_count": 4,
        "expected_peak_utilization_pct": 75.0,
        "evidence_refs": [
            "admission:scope",
            "admission:quota",
            "admission:package",
        ],
    }
    row.update(overrides)
    return row


def evaluate(**overrides):
    args = {
        "trusted_scope": SCOPE,
        "value_realization": value_result(),
        "conversion_capacity": conversion(),
        "admission_request": request(),
        "portfolio_state": portfolio(),
        "policy": policy(),
    }
    args.update(overrides)
    return evaluate_multi_company_admission(**args)


class AionB2BMultiCompanyAdmissionTests(unittest.TestCase):
    def test_capacity_fit_becomes_owner_admission_review_candidate_only(self):
        out = evaluate()
        self.assertEqual(out["state"], "REVIEWABLE")
        self.assertEqual(
            out["decision"],
            "TENANT_ADMISSION_REVIEW_CANDIDATE",
        )
        self.assertEqual(out["service_tenant_id"], "customer-001-prod")
        self.assertEqual(out["package"], "PROFISSIONAL")
        self.assertEqual(out["projected_active_tenants"], 3)
        self.assertEqual(
            out["projected_portfolio"]["capacity_units"][
                "projected_allocated"
            ],
            120,
        )
        self.assertTrue(out["owner_admission_approval_required"])
        self.assertFalse(out["tenant_creation_authorized"])
        self.assertFalse(out["quota_change_authorized"])
        self.assertFalse(out["automatic_tenant_creation"])
        self.assertFalse(out["executes_action"])

    def test_duplicate_service_tenant_id_is_isolation_hold(self):
        out = evaluate(
            admission_request=request(
                service_tenant_id="tenant-alpha-001"
            )
        )
        self.assertEqual(out["state"], "ISOLATION_HOLD")
        self.assertEqual(out["decision"], "ISOLATION_REVIEW")
        self.assertIn(
            "SERVICE_TENANT_ID_ALREADY_EXISTS",
            out["isolation_reasons"],
        )

    def test_existing_customer_is_isolation_hold(self):
        out = evaluate(
            admission_request=request(customer_id="customer-alpha"),
            conversion_capacity=conversion(customer_id="customer-alpha"),
        )
        self.assertEqual(out["state"], "ISOLATION_HOLD")
        self.assertIn(
            "CUSTOMER_ALREADY_ADMITTED",
            out["isolation_reasons"],
        )

    def test_hard_portfolio_quota_exceed_is_capacity_hold(self):
        req = request()
        req["requested_quotas"] = dict(
            req["requested_quotas"],
            capacity_units=250,
        )
        out = evaluate(admission_request=req)
        self.assertEqual(out["state"], "CAPACITY_HOLD")
        self.assertEqual(out["decision"], "CAPACITY_REVIEW")
        self.assertIn(
            "PORTFOLIO_QUOTA_EXCEEDED:capacity_units",
            out["capacity_reasons"],
        )

    def test_minimum_reserve_is_enforced_before_hard_limit(self):
        req = request()
        req["requested_quotas"] = dict(
            req["requested_quotas"],
            capacity_units=180,
        )
        out = evaluate(admission_request=req)
        self.assertEqual(out["state"], "CAPACITY_HOLD")
        self.assertIn(
            "PORTFOLIO_RESERVE_BELOW_POLICY:capacity_units",
            out["capacity_reasons"],
        )
        self.assertLessEqual(
            out["projected_portfolio"]["capacity_units"][
                "projected_allocated"
            ],
            300,
        )

    def test_single_tenant_concentration_is_bounded(self):
        req = request()
        req["requested_quotas"] = dict(
            req["requested_quotas"],
            tokens_per_cycle=4000000,
        )
        out = evaluate(admission_request=req)
        self.assertEqual(out["state"], "CAPACITY_HOLD")
        self.assertIn(
            "SINGLE_TENANT_CONCENTRATION_EXCEEDED:tokens_per_cycle",
            out["capacity_reasons"],
        )

    def test_existing_noisy_neighbor_holds_new_admission(self):
        noisy = portfolio(
            active_tenants=[
                active_tenant(
                    "tenant-alpha-001",
                    "customer-alpha",
                    utilization=92.0,
                ),
                active_tenant(
                    "tenant-beta-001",
                    "customer-beta",
                    utilization=60.0,
                ),
            ]
        )
        out = evaluate(portfolio_state=noisy)
        self.assertEqual(out["state"], "CAPACITY_HOLD")
        self.assertTrue(
            any(
                reason.startswith(
                    "NOISY_NEIGHBOR_UTILIZATION_PRESENT:"
                )
                for reason in out["capacity_reasons"]
            )
        )

    def test_requested_peak_utilization_above_policy_is_hold(self):
        out = evaluate(
            admission_request=request(
                expected_peak_utilization_pct=90.0
            )
        )
        self.assertEqual(out["state"], "CAPACITY_HOLD")
        self.assertIn(
            "REQUESTED_TENANT_PEAK_UTILIZATION_TOO_HIGH",
            out["capacity_reasons"],
        )

    def test_channel_and_integration_limits_are_enforced(self):
        out = evaluate(
            admission_request=request(
                channel_count=5,
                integration_count=6,
            )
        )
        self.assertEqual(out["state"], "CAPACITY_HOLD")
        self.assertIn(
            "TENANT_CHANNEL_LIMIT_EXCEEDED",
            out["capacity_reasons"],
        )
        self.assertIn(
            "TENANT_INTEGRATION_LIMIT_EXCEEDED",
            out["capacity_reasons"],
        )

    def test_active_tenant_limit_is_enforced(self):
        tenants = [
            active_tenant(f"tenant-{i:03d}-x", f"customer-{i:03d}")
            for i in range(10)
        ]
        out = evaluate(
            portfolio_state=portfolio(active_tenants=tenants)
        )
        self.assertEqual(out["state"], "CAPACITY_HOLD")
        self.assertIn(
            "ACTIVE_TENANT_LIMIT_EXCEEDED",
            out["capacity_reasons"],
        )

    def test_cross_scope_admission_request_blocks(self):
        out = evaluate(
            admission_request=request(tenant_id="other-owner-tenant")
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "ADMISSION_REQUEST_SCOPE_MISMATCH",
            out["blockers"],
        )

    def test_package_must_match_commercial_conversion(self):
        out = evaluate(
            admission_request=request(package="COMPLETO")
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "ADMISSION_PACKAGE_CONVERSION_MISMATCH",
            out["blockers"],
        )

    def test_low_value_pilot_cannot_enter_admission(self):
        out = evaluate(
            value_realization=value_result(
                state="VALUE_AT_RISK",
                recommendation="REMEDIATE_REVIEW_CANDIDATE",
                low_value_alert=True,
            )
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "VALUE_REALIZATION_NOT_CONVERSION_READY",
            out["blockers"],
        )
        self.assertIn(
            "VALUE_REALIZATION_LOW_VALUE_ALERT",
            out["blockers"],
        )

    def test_conversion_must_be_clean_and_reviewable(self):
        out = evaluate(
            conversion_capacity=conversion(
                state="CAPACITY_HOLD",
                decision="CAPACITY_REVIEW",
                review_reasons=["CAPACITY_UNITS_EXCEEDED"],
            )
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "CONVERSION_NOT_REVIEWABLE",
            out["blockers"],
        )
        self.assertIn(
            "CONVERSION_HAS_REVIEW_REASONS",
            out["blockers"],
        )

    def test_policy_and_portfolio_evidence_are_required(self):
        out = evaluate(
            policy=policy(evidence_refs=["one"]),
            portfolio_state=portfolio(evidence_refs=["one"]),
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "MULTI_COMPANY_POLICY_EVIDENCE_INSUFFICIENT",
            out["blockers"],
        )
        self.assertIn(
            "MULTI_COMPANY_PORTFOLIO_EVIDENCE_INSUFFICIENT",
            out["blockers"],
        )

    def test_duplicate_active_tenant_identity_blocks_portfolio(self):
        duplicate = portfolio(
            active_tenants=[
                active_tenant(
                    "tenant-alpha-001",
                    "customer-alpha",
                ),
                active_tenant(
                    "tenant-alpha-001",
                    "customer-other",
                ),
            ]
        )
        out = evaluate(portfolio_state=duplicate)
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "ACTIVE_TENANT_IDENTITY_INVALID_OR_DUPLICATE",
            out["blockers"],
        )

    def test_no_tenant_or_quota_authority_is_granted(self):
        out = evaluate()
        for key in (
            "tenant_creation_authorized",
            "quota_change_authorized",
            "admission_token_issued",
            "automatic_tenant_creation",
            "automatic_quota_change",
            "automatic_package_change",
            "automatic_pricing_change",
            "automatic_contract_change",
            "automatic_billing",
            "automatic_provisioning",
            "automatic_customer_contact",
            "automatic_deploy",
            "crm_write",
            "provider_called",
            "production_mutation",
            "executes_action",
        ):
            self.assertFalse(out[key], key)


if __name__ == "__main__":
    unittest.main()
