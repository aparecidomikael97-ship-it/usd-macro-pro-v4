import ast
import hashlib
import json
import unittest
from pathlib import Path

from atlasquant_aion_business_capacity_scale_manager import (
    INITIAL_BUDGET_CAP_BRL,
    capacity_scale_policy,
    evaluate_capacity_scale,
    prepare_customer_admission_review,
)


def _capacity_review(tenants=None):
    if tenants is None:
        tenants = ["client-a", "client-b"]
    quota_rows = [{"tenant_id": tenant} for tenant in tenants]
    ledger_digest = "9" * 64
    payload = {
        "ledger_digest": ledger_digest,
        "minimum_margin_pct": 20.0,
        "reserve_capacity_pct": 10.0,
        "quota_rows": sorted(quota_rows, key=lambda item: item["tenant_id"]),
    }
    digest = hashlib.sha256(
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
    ).hexdigest()
    return {
        "schema": "ATLASQUANT_AION_BUSINESS_CAPACITY_QUOTA_GUARDRAIL_V1",
        "version": "1",
        "state": "CAPACITY_QUOTA_REVIEW_READY",
        "review_digest": digest,
        "ledger_digest": ledger_digest,
        "tenant_ids": tenants,
        "minimum_margin_pct": 20.0,
        "reserve_capacity_pct": 10.0,
        "quota_rows": quota_rows,
        "quota_application_authorized": False,
        "billing_authorized": False,
        "automatic_expansion_allowed": False,
        "client_actions_authorized": False,
        "executes_action": False,
    }


def _usage():
    return [
        {
            "tenant_id": "client-a",
            "current_month_cost_brl": 25.0,
            "max_utilization_pct": 40.0,
            "active_high_severity_incidents": 0,
        },
        {
            "tenant_id": "client-b",
            "current_month_cost_brl": 25.0,
            "max_utilization_pct": 50.0,
            "active_high_severity_incidents": 0,
        },
    ]


def _plan(**overrides):
    kwargs = {
        "usage_rows": _usage(),
        "measurement_ref": "metrics://2026-09-30",
        "approved_monthly_budget_cap_brl": 200.0,
        "shared_platform_cost_brl": 25.0,
        "available_support_hours": 20.0,
        "support_hours_per_new_tenant": 2.0,
        "infra_headroom_pct": 60.0,
        "infra_load_pct_per_new_tenant": 5.0,
        "estimated_new_tenant_cost_brl": 25.0,
        "expected_new_tenant_revenue_brl": 250.0,
    }
    kwargs.update(overrides)
    return evaluate_capacity_scale(_capacity_review(), **kwargs)


class BusinessCapacityScaleManagerTests(unittest.TestCase):
    def test_policy_keeps_customer_admission_manual(self):
        row = capacity_scale_policy()
        self.assertEqual(row["initial_budget_cap_brl"], INITIAL_BUDGET_CAP_BRL)
        self.assertFalse(row["automatic_customer_admission"])
        self.assertFalse(row["automatic_budget_increase"])
        self.assertFalse(row["billing_authorized"])
        self.assertFalse(row["executes_action"])

    def test_safe_capacity_is_minimum_of_all_resources(self):
        row = _plan()
        self.assertEqual(row["state"], "CAPACITY_SCALE_ADMISSION_READY")
        self.assertEqual(row["current_tenant_count"], 2)
        self.assertEqual(row["tenant_month_cost_brl"], 50.0)
        self.assertEqual(row["shared_platform_cost_brl"], 25.0)
        self.assertEqual(row["remaining_budget_brl"], 125.0)
        self.assertEqual(row["budget_slots"], 5)
        self.assertEqual(row["support_slots"], 10)
        self.assertEqual(row["infra_slots"], 8)
        self.assertEqual(row["tenant_slots"], 8)
        self.assertEqual(row["safe_additional_tenants"], 5)
        self.assertFalse(row["automatic_customer_admission"])

    def test_tampered_capacity_review_is_blocked(self):
        review = _capacity_review()
        review["minimum_margin_pct"] = 5.0
        row = evaluate_capacity_scale(
            review,
            usage_rows=_usage(),
            measurement_ref="metrics://2026-09-30",
            approved_monthly_budget_cap_brl=200.0,
            shared_platform_cost_brl=25.0,
            available_support_hours=20.0,
            support_hours_per_new_tenant=2.0,
            infra_headroom_pct=60.0,
            infra_load_pct_per_new_tenant=5.0,
            estimated_new_tenant_cost_brl=25.0,
            expected_new_tenant_revenue_brl=250.0,
        )
        self.assertEqual(row["state"], "CAPACITY_SCALE_ADMISSION_BLOCKED")
        self.assertIn("capacity_review_valid", row["blockers"])

    def test_budget_above_current_200_cap_is_blocked(self):
        row = _plan(approved_monthly_budget_cap_brl=201.0)
        self.assertEqual(row["state"], "CAPACITY_SCALE_ADMISSION_BLOCKED")
        self.assertIn("policy_values_valid", row["blockers"])
        self.assertEqual(row["safe_additional_tenants"], 0)

    def test_current_high_utilization_blocks_growth(self):
        usage = _usage()
        usage[0]["max_utilization_pct"] = 90.0
        row = _plan(usage_rows=usage)
        self.assertEqual(row["state"], "CAPACITY_SCALE_ADMISSION_BLOCKED")
        self.assertIn("current_tenants_healthy", row["blockers"])

    def test_high_severity_incident_blocks_growth(self):
        usage = _usage()
        usage[1]["active_high_severity_incidents"] = 1
        row = _plan(usage_rows=usage)
        self.assertEqual(row["state"], "CAPACITY_SCALE_ADMISSION_BLOCKED")
        self.assertIn("current_tenants_healthy", row["blockers"])

    def test_low_margin_blocks_growth(self):
        row = _plan(
            estimated_new_tenant_cost_brl=220.0,
            expected_new_tenant_revenue_brl=250.0,
        )
        self.assertEqual(row["state"], "CAPACITY_SCALE_ADMISSION_BLOCKED")
        self.assertIn("new_tenant_margin_meets_floor", row["blockers"])

    def test_usage_tenant_set_must_match_review(self):
        usage = _usage()[:1]
        row = _plan(usage_rows=usage)
        self.assertEqual(row["state"], "CAPACITY_SCALE_ADMISSION_BLOCKED")
        self.assertIn("usage_tenant_set_matches_review", row["blockers"])

    def test_admission_review_never_auto_accepts(self):
        plan = _plan()
        packet = prepare_customer_admission_review(
            plan,
            requested_new_tenants=2,
            candidate_refs=["lead-001", "lead-002"],
        )
        self.assertEqual(
            packet["state"],
            "EXPLICIT_CUSTOMER_ADMISSION_DECISION_REQUIRED",
        )
        self.assertFalse(packet["customer_admission_authorized"])
        self.assertFalse(packet["automatic_customer_admission"])
        self.assertFalse(packet["billing_authorized"])
        self.assertFalse(packet["executes_action"])

    def test_request_above_safe_capacity_is_blocked(self):
        plan = _plan()
        packet = prepare_customer_admission_review(
            plan,
            requested_new_tenants=7,
            candidate_refs=[f"lead-{i}" for i in range(7)],
        )
        self.assertEqual(packet["state"], "NOT_READY")

    def test_admin_exposes_capacity_scale_view(self):
        source = Path("atlasquant_aion_admin.py").read_text(encoding="utf-8")
        self.assertIn("24 · Gestor de Capacidade & Escala", source)
        self.assertIn("business_capacity_scale_policy", source)

    def test_module_has_no_network_or_executor_imports(self):
        source = Path(
            "atlasquant_aion_business_capacity_scale_manager.py"
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
