import ast
import copy
import hashlib
import json
import unittest
from datetime import datetime, timezone
from pathlib import Path

from atlasquant_aion_business_revenue_live_economics_binding import (
    bind_revenue_opportunity_to_live_economics,
    derive_opportunity_monthly_cost,
    live_economics_policy,
    rank_live_economics_opportunities,
)
from atlasquant_aion_finops_live_cost_ledger import (
    build_hash_chained_ledger,
    normalize_cost_observations,
    provider_cost_attestation,
)


NOW = datetime(2026, 9, 30, 18, 0, tzinfo=timezone.utc)


def _provider(provider):
    return provider_cost_attestation(
        provider_ref=provider,
        connection_ref=f"connector://{provider}/readonly",
        authentication_verified=True,
        read_only_scope_verified=True,
        write_scope_present=False,
        credential_value_present=False,
        observed_at="2026-09-30T17:50:00+00:00",
    )


def _ledger():
    snapshot = normalize_cost_observations(
        [
            {
                "entry_id": "ai-month",
                "provider_ref": "provider-ai",
                "source_ref": "usage://ai/month",
                "category": "AI_PROVIDER",
                "tenant_id": "",
                "shared_cost": True,
                "amount_brl": 60.0,
                "recurring": True,
                "period_start": "2026-09-01T00:00:00+00:00",
                "period_end": "2026-09-30T23:59:59+00:00",
                "observed_at": "2026-09-30T17:45:00+00:00",
            },
            {
                "entry_id": "hosting-month",
                "provider_ref": "provider-host",
                "source_ref": "usage://hosting/month",
                "category": "HOSTING",
                "tenant_id": "",
                "shared_cost": True,
                "amount_brl": 40.0,
                "recurring": True,
                "period_start": "2026-09-01T00:00:00+00:00",
                "period_end": "2026-09-30T23:59:59+00:00",
                "observed_at": "2026-09-30T17:45:00+00:00",
            },
        ],
        attestations=[_provider("provider-ai"), _provider("provider-host")],
        now=NOW,
    )
    return build_hash_chained_ledger(snapshot)


def _capacity(ready=True):
    return {
        "schema": "ATLASQUANT_AION_BUSINESS_CAPACITY_LIVE_METRICS_BINDING_V1",
        "version": "1",
        "state": "LIVE_CAPACITY_REVIEW_READY" if ready else "LIVE_CAPACITY_REVIEW_BLOCKED",
        "live_snapshot_digest": "c" * 64,
        "capacity_plan": {
            "state": "CAPACITY_SCALE_ADMISSION_READY" if ready else "CAPACITY_SCALE_ADMISSION_BLOCKED",
            "plan_digest": "d" * 64 if ready else "",
        },
        "safe_additional_tenants": 2 if ready else 0,
        "automatic_customer_admission": False,
        "customer_admission_authorized": False,
        "automatic_budget_increase": False,
        "automatic_quota_change": False,
        "billing_authorized": False,
        "executes_action": False,
    }


def _opportunity(name="opp-a", price=300.0):
    return {
        "opportunity_id": name,
        "label": f"Opportunity {name}",
        "opportunity_type": "B2B_AUTOMATION",
        "startup_cost_brl": 20.0,
        "available_startup_budget_brl": 100.0,
        "monthly_price_brl": price,
        "implementation_days": 7,
        "minimum_margin_pct": 40.0,
        "repeatability_pct": 90.0,
        "evidence_readiness_pct": 80.0,
        "support_load_pct": 20.0,
        "implementation_complexity_pct": 30.0,
    }


class RevenueLiveEconomicsBindingTests(unittest.TestCase):
    def test_policy_replaces_cost_and_capacity_only(self):
        row = live_economics_policy()
        self.assertEqual(
            row["monthly_cost_source"],
            "VERIFIED_FINOPS_LEDGER_ALLOCATIONS",
        )
        self.assertEqual(row["capacity_source"], "LIVE_CAPACITY_REVIEW")
        self.assertEqual(row["commercial_price_source"], "ADMIN_INPUT")
        self.assertFalse(row["automatic_sale"])

    def test_cost_is_derived_from_verified_ledger_allocations(self):
        row = derive_opportunity_monthly_cost(
            _ledger(),
            [
                {"entry_id": "ai-month", "allocation_pct": 50},
                {"entry_id": "hosting-month", "allocation_pct": 25},
            ],
        )
        self.assertEqual(row["state"], "OPPORTUNITY_MONTHLY_COST_DERIVED")
        self.assertEqual(row["derived_monthly_cost_brl"], 40.0)
        self.assertFalse(row["ledger_modified"])

    def test_missing_entry_blocks_cost_binding(self):
        row = derive_opportunity_monthly_cost(
            _ledger(),
            [{"entry_id": "does-not-exist", "allocation_pct": 50}],
        )
        self.assertEqual(row["state"], "OPPORTUNITY_MONTHLY_COST_BLOCKED")
        self.assertTrue(any("ledger_entry_not_found" in x for x in row["blockers"]))

    def test_tampered_ledger_blocks_cost_binding(self):
        ledger = copy.deepcopy(_ledger())
        ledger["entries"][0]["amount_brl"] = 9999.0
        row = derive_opportunity_monthly_cost(
            ledger,
            [{"entry_id": "ai-month", "allocation_pct": 50}],
        )
        self.assertEqual(row["state"], "OPPORTUNITY_MONTHLY_COST_BLOCKED")
        self.assertIn("FINOPS_LEDGER_NOT_VERIFIED", row["blockers"])

    def test_live_binding_injects_real_cost_and_capacity(self):
        row = bind_revenue_opportunity_to_live_economics(
            _opportunity(),
            ledger=_ledger(),
            cost_allocations=[
                {"entry_id": "ai-month", "allocation_pct": 50},
                {"entry_id": "hosting-month", "allocation_pct": 25},
            ],
            live_capacity_review=_capacity(True),
        )
        self.assertEqual(
            row["state"],
            "LIVE_ECONOMICS_REVENUE_OPPORTUNITY_ELIGIBLE",
        )
        self.assertEqual(row["derived_monthly_cost_brl"], 40.0)
        self.assertEqual(row["safe_additional_tenants"], 2)
        self.assertEqual(
            row["opportunity"]["estimated_monthly_cost_brl"],
            40.0,
        )
        self.assertTrue(row["opportunity"]["capacity_ready"])
        self.assertFalse(row["automatic_sale"])

    def test_capacity_block_prevents_eligibility(self):
        row = bind_revenue_opportunity_to_live_economics(
            _opportunity(),
            ledger=_ledger(),
            cost_allocations=[{"entry_id": "ai-month", "allocation_pct": 50}],
            live_capacity_review=_capacity(False),
        )
        self.assertEqual(
            row["state"],
            "LIVE_ECONOMICS_REVENUE_OPPORTUNITY_BLOCKED",
        )
        self.assertIn("LIVE_CAPACITY_NOT_READY", row["blockers"])

    def test_low_price_still_obeys_existing_margin_gate(self):
        row = bind_revenue_opportunity_to_live_economics(
            _opportunity(price=50.0),
            ledger=_ledger(),
            cost_allocations=[
                {"entry_id": "ai-month", "allocation_pct": 100},
                {"entry_id": "hosting-month", "allocation_pct": 100},
            ],
            live_capacity_review=_capacity(True),
        )
        self.assertEqual(
            row["state"],
            "LIVE_ECONOMICS_REVENUE_OPPORTUNITY_BLOCKED",
        )
        self.assertIn("MARGIN_BELOW_ADMIN_FLOOR", row["blockers"])

    def test_portfolio_ranking_remains_nonautomatic(self):
        first = bind_revenue_opportunity_to_live_economics(
            _opportunity("a", 300.0),
            ledger=_ledger(),
            cost_allocations=[{"entry_id": "ai-month", "allocation_pct": 50}],
            live_capacity_review=_capacity(True),
        )
        second = bind_revenue_opportunity_to_live_economics(
            _opportunity("b", 400.0),
            ledger=_ledger(),
            cost_allocations=[{"entry_id": "ai-month", "allocation_pct": 50}],
            live_capacity_review=_capacity(True),
        )
        row = rank_live_economics_opportunities([first, second])
        self.assertEqual(
            row["state"],
            "READY_FOR_ADMIN_LIVE_REVENUE_PRIORITY_REVIEW",
        )
        self.assertEqual(len(row["ranked"]), 2)
        self.assertFalse(row["score_is_probability"])
        self.assertFalse(row["top_is_automatic_decision"])
        self.assertFalse(row["automatic_sale"])

    def test_admin_exposes_live_revenue_economics_view(self):
        source = Path("atlasquant_aion_admin.py").read_text(encoding="utf-8")
        self.assertIn("36 · Receita · Economia Real", source)
        self.assertIn("business_live_economics_policy", source)

    def test_module_has_no_network_or_executor_imports(self):
        source = Path(
            "atlasquant_aion_business_revenue_live_economics_binding.py"
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
