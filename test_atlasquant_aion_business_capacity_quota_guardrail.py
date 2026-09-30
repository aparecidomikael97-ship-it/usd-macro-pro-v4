import ast
import unittest
from pathlib import Path

from atlasquant_aion_business_capacity_quota_guardrail import (
    build_capacity_quota_review,
    capacity_policy_requirements,
    quota_application_review_packet,
)


def _audit(tenants=None):
    if tenants is None:
        tenants = ["tenant-001", "tenant-002"]
    return {
        "schema": "ATLASQUANT_AION_BUSINESS_EXPANSION_CYCLE_AUDIT_LEDGER_V1",
        "version": "1",
        "state": "LEDGER_INTEGRITY_VERIFIED",
        "integrity_verified": True,
        "entry_count": 2,
        "ledger_digest": "a" * 64,
        "last_verified_scope": "pilot",
        "last_verified_tenant_ids": tenants,
        "blockers": [],
        "automatic_expansion_allowed": False,
        "scope_expansion_authorized": False,
        "expansion_execution_authorized": False,
        "client_actions_authorized": False,
        "billing_authorized": False,
        "executes_action": False,
    }


def _quotas():
    base = {
        "max_ai_requests": 10000,
        "max_integration_calls": 20000,
        "max_workflow_runs": 5000,
        "max_storage_mb": 5000,
        "ai_cost_budget": 100.0,
        "integration_cost_budget": 50.0,
        "support_cost_budget": 100.0,
        "infra_cost_budget": 50.0,
        "expected_revenue": 1000.0,
    }
    return [
        {"tenant_id": "tenant-001", **base},
        {"tenant_id": "tenant-002", **base},
    ]


class BusinessCapacityQuotaGuardrailTests(unittest.TestCase):
    def test_policy_never_applies_quota(self):
        row = capacity_policy_requirements()
        self.assertEqual(row["state"], "CAPACITY_POLICY_REQUIRED")
        self.assertFalse(row["quota_application_authorized"])
        self.assertFalse(row["billing_authorized"])
        self.assertFalse(row["executes_action"])

    def test_matching_tenants_and_margin_can_reach_review(self):
        row = build_capacity_quota_review(
            _audit(),
            quota_rows=_quotas(),
            minimum_margin_pct=20,
            reserve_capacity_pct=10,
        )
        self.assertEqual(row["state"], "CAPACITY_QUOTA_REVIEW_READY")
        self.assertEqual(row["blockers"], [])
        self.assertEqual(len(row["review_digest"]), 64)
        self.assertEqual(row["tenant_ids"], ["tenant-001", "tenant-002"])
        self.assertFalse(row["quota_application_authorized"])

    def test_missing_or_extra_tenant_blocks(self):
        quotas = _quotas()[:1]
        row = build_capacity_quota_review(
            _audit(),
            quota_rows=quotas,
            minimum_margin_pct=20,
            reserve_capacity_pct=10,
        )
        self.assertEqual(row["state"], "CAPACITY_QUOTA_REVIEW_BLOCKED")
        self.assertIn("quota_tenant_set_must_match_ledger", row["blockers"])

    def test_margin_floor_is_enforced_after_reserve(self):
        quotas = _quotas()
        for item in quotas:
            item["ai_cost_budget"] = 500.0
            item["integration_cost_budget"] = 200.0
            item["support_cost_budget"] = 200.0
            item["infra_cost_budget"] = 50.0
        row = build_capacity_quota_review(
            _audit(),
            quota_rows=quotas,
            minimum_margin_pct=20,
            reserve_capacity_pct=10,
        )
        self.assertEqual(row["state"], "CAPACITY_QUOTA_REVIEW_BLOCKED")
        self.assertTrue(
            any("minimum_margin_not_met" in item for item in row["blockers"])
        )

    def test_invalid_usage_quota_blocks(self):
        quotas = _quotas()
        quotas[0]["max_ai_requests"] = 0
        row = build_capacity_quota_review(
            _audit(),
            quota_rows=quotas,
            minimum_margin_pct=20,
            reserve_capacity_pct=10,
        )
        self.assertEqual(row["state"], "CAPACITY_QUOTA_REVIEW_BLOCKED")
        self.assertIn("row_1_max_ai_requests_invalid", row["blockers"])

    def test_unverified_ledger_blocks(self):
        audit = _audit()
        audit["integrity_verified"] = False
        audit["state"] = "LEDGER_INTEGRITY_BLOCKED"
        row = build_capacity_quota_review(
            audit,
            quota_rows=_quotas(),
            minimum_margin_pct=20,
            reserve_capacity_pct=10,
        )
        self.assertEqual(row["state"], "CAPACITY_QUOTA_REVIEW_BLOCKED")
        self.assertIn("verified_ledger_required", row["blockers"])

    def test_review_packet_remains_non_executing(self):
        review = build_capacity_quota_review(
            _audit(),
            quota_rows=_quotas(),
            minimum_margin_pct=20,
            reserve_capacity_pct=10,
        )
        packet = quota_application_review_packet(review)
        self.assertEqual(packet["state"], "QUOTA_APPLICATION_DECISION_REQUIRED")
        self.assertFalse(packet["quota_application_authorized"])
        self.assertFalse(packet["billing_authorized"])
        self.assertFalse(packet["automatic_expansion_allowed"])
        self.assertFalse(packet["executes_action"])

    def test_forged_tenant_set_cannot_reach_application_review(self):
        review = build_capacity_quota_review(
            _audit(),
            quota_rows=_quotas(),
            minimum_margin_pct=20,
            reserve_capacity_pct=10,
        )
        review["tenant_ids"] = ["tenant-001"]
        packet = quota_application_review_packet(review)
        self.assertEqual(packet["state"], "NOT_READY")
        self.assertFalse(packet["quota_application_authorized"])

    def test_admin_exposes_twenty_first_view(self):
        source = Path("atlasquant_aion_admin.py").read_text(encoding="utf-8")
        self.assertIn("21 · Capacidade & quotas por tenant", source)
        self.assertIn("business_capacity_policy_requirements", source)

    def test_module_has_no_network_git_process_or_runtime_executor(self):
        source = Path(
            "atlasquant_aion_business_capacity_quota_guardrail.py"
        ).read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported = []
        for node in tree.body:
            if isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.append(node.module or "")
        for banned in (
            "requests",
            "urllib",
            "httpx",
            "socket",
            "subprocess",
            "github",
            "paramiko",
            "docker",
            "kubernetes",
        ):
            self.assertNotIn(banned, imported)


if __name__ == "__main__":
    unittest.main()
