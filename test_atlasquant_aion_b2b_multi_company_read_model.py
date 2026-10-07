from __future__ import annotations

import unittest

from atlasquant_aion_b2b_multi_company_read_model import (
    build_multi_company_admission_read_model,
)

SCOPE = {
    "owner_id": "owner-a",
    "tenant_id": "atlasquant-owner",
    "workspace_id": "business",
}


def admission(**overrides):
    row = {
        "schema": "ATLASQUANT_AION_B2B_MULTI_COMPANY_ADMISSION_V1",
        "state": "REVIEWABLE",
        "decision": "TENANT_ADMISSION_REVIEW_CANDIDATE",
        "customer_id": "customer-secret-001",
        "service_tenant_id": "customer-001-prod",
        "package": "PROFISSIONAL",
        "proposed_quotas": {
            "capacity_units": 40,
            "calls_per_cycle": 1000,
            "tokens_per_cycle": 1000000,
            "support_tickets_per_cycle": 20,
        },
        "projected_active_tenants": 3,
        "projected_portfolio": {
            "capacity_units": {
                "current_allocated": 80,
                "requested": 40,
                "projected_allocated": 120,
                "portfolio_limit": 300,
                "reserve_pct": 60.0,
                "single_tenant_share_pct": 13.33,
            },
            "calls_per_cycle": {
                "current_allocated": 2000,
                "requested": 1000,
                "projected_allocated": 3000,
                "portfolio_limit": 10000,
                "reserve_pct": 70.0,
                "single_tenant_share_pct": 10.0,
            },
            "tokens_per_cycle": {
                "current_allocated": 2000000,
                "requested": 1000000,
                "projected_allocated": 3000000,
                "portfolio_limit": 10000000,
                "reserve_pct": 70.0,
                "single_tenant_share_pct": 10.0,
            },
            "support_tickets_per_cycle": {
                "current_allocated": 40,
                "requested": 20,
                "projected_allocated": 60,
                "portfolio_limit": 200,
                "reserve_pct": 70.0,
                "single_tenant_share_pct": 10.0,
            },
        },
        "review_reasons": [],
        "isolation_reasons": [],
        "capacity_reasons": [],
        "blockers": [],
        "evidence_digest": "sha256:" + "1" * 64,
        "owner_admission_approval_required": True,
        "tenant_creation_authorized": False,
        "quota_change_authorized": False,
        "admission_token_issued": False,
        "automatic_tenant_creation": False,
        "automatic_quota_change": False,
        "automatic_package_change": False,
        "automatic_pricing_change": False,
        "automatic_contract_change": False,
        "automatic_billing": False,
        "automatic_provisioning": False,
        "automatic_customer_contact": False,
        "automatic_deploy": False,
        "crm_write": False,
        "provider_called": False,
        "production_mutation": False,
        "executes_action": False,
    }
    row.update(overrides)
    return row


class AionB2BMultiCompanyReadModelTests(unittest.TestCase):
    def test_reviewable_admission_projects_aggregate_capacity_only(self):
        out = build_multi_company_admission_read_model(
            admission(),
            trusted_scope=SCOPE,
        )
        self.assertEqual(out["state"], "READY")
        self.assertEqual(out["admission_state"], "REVIEWABLE")
        self.assertEqual(
            out["admission_decision"],
            "TENANT_ADMISSION_REVIEW_CANDIDATE",
        )
        self.assertEqual(out["service_tenant_id"], "customer-001-prod")
        self.assertEqual(out["package"], "PROFISSIONAL")
        self.assertEqual(out["projected_active_tenants"], 3)
        self.assertEqual(out["minimum_portfolio_reserve_pct"], 60.0)
        self.assertEqual(out["maximum_single_tenant_share_pct"], 13.33)
        self.assertTrue(out["read_only"])
        self.assertFalse(out["other_tenant_identity_exposed"])
        self.assertFalse(out["customer_identity_exposed"])
        self.assertFalse(out["tenant_creation_control_exposed"])
        self.assertFalse(out["quota_control_exposed"])
        self.assertFalse(out["executes_action"])

    def test_source_customer_identity_is_not_projected(self):
        out = build_multi_company_admission_read_model(
            admission(),
            trusted_scope=SCOPE,
        )
        self.assertNotIn("customer_id", out)
        self.assertNotIn("customer-secret-001", str(out))
        self.assertFalse(out["customer_identity_exposed"])

    def test_capacity_hold_is_presentable_without_action(self):
        out = build_multi_company_admission_read_model(
            admission(
                state="CAPACITY_HOLD",
                decision="CAPACITY_REVIEW",
                capacity_reasons=[
                    "PORTFOLIO_RESERVE_BELOW_POLICY:capacity_units"
                ],
                review_reasons=[
                    "PORTFOLIO_RESERVE_BELOW_POLICY:capacity_units"
                ],
            ),
            trusted_scope=SCOPE,
        )
        self.assertEqual(out["state"], "READY")
        self.assertEqual(out["admission_state"], "CAPACITY_HOLD")
        self.assertEqual(out["capacity_reason_count"], 1)
        self.assertFalse(out["tenant_creation_control_exposed"])

    def test_isolation_hold_is_presentable_without_other_identity(self):
        out = build_multi_company_admission_read_model(
            admission(
                state="ISOLATION_HOLD",
                decision="ISOLATION_REVIEW",
                isolation_reasons=[
                    "SERVICE_TENANT_ID_ALREADY_EXISTS"
                ],
                review_reasons=[
                    "SERVICE_TENANT_ID_ALREADY_EXISTS"
                ],
            ),
            trusted_scope=SCOPE,
        )
        self.assertEqual(out["state"], "READY")
        self.assertEqual(out["isolation_reason_count"], 1)
        self.assertFalse(out["other_tenant_identity_exposed"])

    def test_blocked_source_is_not_presentable(self):
        out = build_multi_company_admission_read_model(
            admission(
                state="BLOCKED",
                decision="BLOCKED",
                blockers=["ADMISSION_REQUEST_SCOPE_MISMATCH"],
            ),
            trusted_scope=SCOPE,
        )
        self.assertEqual(out["state"], "BLOCKED")

    def test_missing_quota_projection_blocks(self):
        broken = admission()
        broken["projected_portfolio"] = {
            "capacity_units": broken["projected_portfolio"][
                "capacity_units"
            ]
        }
        out = build_multi_company_admission_read_model(
            broken,
            trusted_scope=SCOPE,
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertTrue(
            any(
                item.startswith("PROJECTED_QUOTA_MISSING:")
                for item in out["blockers"]
            )
        )

    def test_any_authority_flip_blocks_read_model(self):
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
            with self.subTest(key=key):
                out = build_multi_company_admission_read_model(
                    admission(**{key: True}),
                    trusted_scope=SCOPE,
                )
                self.assertEqual(out["state"], "BLOCKED")


if __name__ == "__main__":
    unittest.main()
