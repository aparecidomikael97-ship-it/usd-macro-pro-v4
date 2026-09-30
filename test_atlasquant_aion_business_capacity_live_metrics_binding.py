import ast
import hashlib
import json
import unittest
from datetime import datetime, timezone
from pathlib import Path

from atlasquant_aion_business_capacity_live_metrics_binding import (
    evaluate_capacity_from_live_metrics,
    live_capacity_policy,
    metrics_source_attestation,
    normalize_live_capacity_snapshot,
)
from atlasquant_aion_business_capacity_scale_manager import (
    evaluate_capacity_scale,
)


NOW = datetime(2026, 9, 30, 18, 0, tzinfo=timezone.utc)


def _attestation(source):
    return metrics_source_attestation(
        source_type=source,
        source_ref=f"connector://{source.lower()}/readonly",
        authentication_verified=True,
        read_only_scope_verified=True,
        write_scope_present=False,
        observed_at="2026-09-30T17:50:00+00:00",
    )


def _capacity_review():
    quota_rows = [{"tenant_id": "tenant-a"}]
    payload = {
        "ledger_digest": "9" * 64,
        "minimum_margin_pct": 20.0,
        "reserve_capacity_pct": 10.0,
        "quota_rows": quota_rows,
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
        "ledger_digest": payload["ledger_digest"],
        "tenant_ids": ["tenant-a"],
        "minimum_margin_pct": 20.0,
        "reserve_capacity_pct": 10.0,
        "quota_rows": quota_rows,
        "quota_application_authorized": False,
        "billing_authorized": False,
        "automatic_expansion_allowed": False,
        "client_actions_authorized": False,
        "executes_action": False,
    }


def _snapshot():
    return normalize_live_capacity_snapshot(
        tenant_metrics=[{
            "tenant_id": "tenant-a",
            "current_month_cost_brl": 30.0,
            "max_utilization_pct": 45.0,
            "active_high_severity_incidents": 0,
            "observed_at": "2026-09-30T17:45:00+00:00",
            "finops_cost_digest": "a" * 64,
        }],
        platform_metrics={
            "shared_platform_cost_brl": 20.0,
            "available_support_hours": 20.0,
            "infra_headroom_pct": 60.0,
            "observed_at": "2026-09-30T17:45:00+00:00",
        },
        source_attestations=[
            _attestation("FINOPS"),
            _attestation("SUPPORT"),
            _attestation("INFRA"),
            _attestation("INCIDENTS"),
        ],
        now=NOW,
    )


class BusinessCapacityLiveMetricsBindingTests(unittest.TestCase):
    def test_policy_remains_read_only(self):
        row = live_capacity_policy()
        self.assertFalse(row["external_probe_executed_here"])
        self.assertFalse(row["automatic_customer_admission"])
        self.assertFalse(row["automatic_budget_increase"])

    def test_source_attestation_rejects_write_scope(self):
        good = _attestation("FINOPS")
        self.assertEqual(good["state"], "METRICS_SOURCE_ATTESTATION_READY")
        bad = metrics_source_attestation(
            source_type="FINOPS",
            source_ref="connector://finops",
            authentication_verified=True,
            read_only_scope_verified=True,
            write_scope_present=True,
            observed_at="2026-09-30T17:50:00+00:00",
        )
        self.assertEqual(bad["state"], "METRICS_SOURCE_ATTESTATION_BLOCKED")

    def test_live_snapshot_requires_all_four_sources(self):
        row = _snapshot()
        self.assertEqual(row["state"], "CAPACITY_LIVE_METRICS_SNAPSHOT_READY")
        self.assertEqual(row["tenant_count"], 1)
        self.assertEqual(
            row["truth_state"],
            "EXTERNALLY_ATTESTED_READ_ONLY_INPUT",
        )

        blocked = normalize_live_capacity_snapshot(
            tenant_metrics=[{
                "tenant_id": "tenant-a",
                "current_month_cost_brl": 30.0,
                "max_utilization_pct": 45.0,
                "active_high_severity_incidents": 0,
                "observed_at": "2026-09-30T17:45:00+00:00",
                "finops_cost_digest": "a" * 64,
            }],
            platform_metrics={
                "shared_platform_cost_brl": 20.0,
                "available_support_hours": 20.0,
                "infra_headroom_pct": 60.0,
                "observed_at": "2026-09-30T17:45:00+00:00",
            },
            source_attestations=[_attestation("FINOPS")],
            now=NOW,
        )
        self.assertEqual(
            blocked["state"],
            "CAPACITY_LIVE_METRICS_SNAPSHOT_BLOCKED",
        )

    def test_stale_tenant_metric_is_blocked(self):
        row = normalize_live_capacity_snapshot(
            tenant_metrics=[{
                "tenant_id": "tenant-a",
                "current_month_cost_brl": 30.0,
                "max_utilization_pct": 45.0,
                "active_high_severity_incidents": 0,
                "observed_at": "2026-09-20T17:45:00+00:00",
                "finops_cost_digest": "a" * 64,
            }],
            platform_metrics={
                "shared_platform_cost_brl": 20.0,
                "available_support_hours": 20.0,
                "infra_headroom_pct": 60.0,
                "observed_at": "2026-09-30T17:45:00+00:00",
            },
            source_attestations=[
                _attestation("FINOPS"),
                _attestation("SUPPORT"),
                _attestation("INFRA"),
                _attestation("INCIDENTS"),
            ],
            now=NOW,
        )
        self.assertEqual(
            row["state"],
            "CAPACITY_LIVE_METRICS_SNAPSHOT_BLOCKED",
        )
        self.assertTrue(any(x.endswith("_stale") for x in row["blockers"]))

    def test_live_snapshot_feeds_existing_capacity_manager(self):
        row = evaluate_capacity_from_live_metrics(
            _capacity_review(),
            _snapshot(),
            approved_monthly_budget_cap_brl=200.0,
            support_hours_per_new_tenant=2.0,
            infra_load_pct_per_new_tenant=5.0,
            estimated_new_tenant_cost_brl=20.0,
            expected_new_tenant_revenue_brl=300.0,
        )
        self.assertEqual(row["state"], "LIVE_CAPACITY_REVIEW_READY")
        self.assertGreater(row["safe_additional_tenants"], 0)
        self.assertFalse(row["automatic_customer_admission"])
        self.assertFalse(row["customer_admission_authorized"])

    def test_high_incident_count_blocks_existing_capacity_manager(self):
        snap = _snapshot()
        snap["tenant_metrics"][0]["active_high_severity_incidents"] = 1
        # Rebuild through normalizer to preserve contract.
        blocked_snap = normalize_live_capacity_snapshot(
            tenant_metrics=snap["tenant_metrics"],
            platform_metrics=snap["platform_metrics"],
            source_attestations=[
                _attestation("FINOPS"),
                _attestation("SUPPORT"),
                _attestation("INFRA"),
                _attestation("INCIDENTS"),
            ],
            now=NOW,
        )
        row = evaluate_capacity_from_live_metrics(
            _capacity_review(),
            blocked_snap,
            approved_monthly_budget_cap_brl=200.0,
            support_hours_per_new_tenant=2.0,
            infra_load_pct_per_new_tenant=5.0,
            estimated_new_tenant_cost_brl=20.0,
            expected_new_tenant_revenue_brl=300.0,
        )
        self.assertEqual(row["state"], "LIVE_CAPACITY_REVIEW_BLOCKED")
        self.assertEqual(row["safe_additional_tenants"], 0)

    def test_admin_exposes_live_capacity_view(self):
        source = Path("atlasquant_aion_admin.py").read_text(encoding="utf-8")
        self.assertIn("35 · Capacidade · Metricas Reais", source)
        self.assertIn("business_live_capacity_policy", source)

    def test_module_has_no_network_or_executor_imports(self):
        source = Path(
            "atlasquant_aion_business_capacity_live_metrics_binding.py"
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
