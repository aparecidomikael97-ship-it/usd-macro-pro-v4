import ast
import copy
import unittest
from datetime import datetime, timezone
from pathlib import Path

from atlasquant_aion_finops_live_cost_ledger import (
    GENESIS_DIGEST,
    build_hash_chained_ledger,
    live_cost_policy,
    monthly_budget_from_live_ledger,
    normalize_cost_observations,
    provider_cost_attestation,
    tenant_cost_summary,
    verify_hash_chained_ledger,
)


NOW = datetime(2026, 9, 30, 18, 0, tzinfo=timezone.utc)


def _attestation(provider="provider-ai"):
    return provider_cost_attestation(
        provider_ref=provider,
        connection_ref=f"connector://{provider}/readonly",
        authentication_verified=True,
        read_only_scope_verified=True,
        write_scope_present=False,
        credential_value_present=False,
        observed_at="2026-09-30T17:50:00+00:00",
    )


def _snapshot():
    return normalize_cost_observations(
        [
            {
                "entry_id": "cost-001",
                "provider_ref": "provider-ai",
                "source_ref": "invoice://ai-2026-09",
                "category": "AI_PROVIDER",
                "tenant_id": "tenant-a",
                "shared_cost": False,
                "amount_brl": 35.0,
                "recurring": True,
                "period_start": "2026-09-01T00:00:00+00:00",
                "period_end": "2026-09-30T23:59:59+00:00",
                "observed_at": "2026-09-30T17:45:00+00:00",
            },
            {
                "entry_id": "cost-002",
                "provider_ref": "provider-host",
                "source_ref": "invoice://host-2026-09",
                "category": "HOSTING",
                "tenant_id": "",
                "shared_cost": True,
                "amount_brl": 50.0,
                "recurring": True,
                "period_start": "2026-09-01T00:00:00+00:00",
                "period_end": "2026-09-30T23:59:59+00:00",
                "observed_at": "2026-09-30T17:40:00+00:00",
            },
        ],
        attestations=[_attestation("provider-ai"), _attestation("provider-host")],
        now=NOW,
    )


def _ledger():
    return build_hash_chained_ledger(_snapshot())


class AionFinopsLiveCostLedgerTests(unittest.TestCase):
    def test_policy_is_nonexecuting_and_ledger_is_append_only_contract(self):
        row = live_cost_policy()
        self.assertEqual(row["ledger_model"], "APPEND_ONLY_HASH_CHAIN")
        self.assertEqual(row["genesis_digest"], GENESIS_DIGEST)
        self.assertFalse(row["provider_connector_executes_here"])
        self.assertFalse(row["ledger_persisted_here"])
        self.assertFalse(row["automatic_payment"])

    def test_provider_attestation_requires_read_only(self):
        good = _attestation()
        self.assertEqual(good["state"], "PROVIDER_COST_ATTESTATION_READY")
        self.assertFalse(good["write_scope_present"])

        bad = provider_cost_attestation(
            provider_ref="provider-ai",
            connection_ref="connector://provider-ai",
            authentication_verified=True,
            read_only_scope_verified=True,
            write_scope_present=True,
            credential_value_present=False,
            observed_at="2026-09-30T17:50:00+00:00",
        )
        self.assertEqual(bad["state"], "PROVIDER_COST_ATTESTATION_BLOCKED")

    def test_live_cost_snapshot_accepts_direct_and_shared_costs(self):
        row = _snapshot()
        self.assertEqual(row["state"], "LIVE_COST_SNAPSHOT_READY")
        self.assertEqual(row["entry_count"], 2)
        self.assertEqual(row["truth_state"], "EXTERNALLY_ATTESTED_COST_INPUT")

    def test_direct_cost_requires_tenant(self):
        row = normalize_cost_observations(
            [{
                "entry_id": "cost-x",
                "provider_ref": "provider-ai",
                "source_ref": "invoice://x",
                "category": "AI_PROVIDER",
                "shared_cost": False,
                "tenant_id": "",
                "amount_brl": 10.0,
                "period_start": "2026-09-01T00:00:00+00:00",
                "period_end": "2026-09-30T23:59:59+00:00",
                "observed_at": "2026-09-30T17:45:00+00:00",
            }],
            attestations=[_attestation("provider-ai")],
            now=NOW,
        )
        self.assertEqual(row["state"], "LIVE_COST_SNAPSHOT_BLOCKED")
        self.assertTrue(any("tenant_required" in x for x in row["blockers"]))

    def test_hash_chained_ledger_verifies(self):
        ledger = _ledger()
        self.assertEqual(ledger["state"], "FINOPS_LEDGER_READY_FOR_PERSISTENCE_REVIEW")
        self.assertEqual(ledger["entry_count"], 2)
        self.assertFalse(ledger["ledger_persisted"])
        verified = verify_hash_chained_ledger(ledger)
        self.assertEqual(verified["state"], "FINOPS_LEDGER_VERIFIED")
        self.assertTrue(verified["valid"])

    def test_tampering_breaks_hash_chain(self):
        ledger = copy.deepcopy(_ledger())
        ledger["entries"][0]["amount_brl"] = 9999.0
        verified = verify_hash_chained_ledger(ledger)
        self.assertEqual(verified["state"], "FINOPS_LEDGER_INVALID")
        self.assertFalse(verified["valid"])
        self.assertEqual(verified["reason"], "ENTRY_DIGEST_MISMATCH")

    def test_monthly_budget_uses_verified_ledger(self):
        row = monthly_budget_from_live_ledger(
            _ledger(),
            planned_new_commitment_brl=20.0,
        )
        self.assertEqual(row["state"], "LIVE_BUDGET_REVIEW_READY")
        self.assertEqual(row["budget"]["current_monthly_cost_brl"], 85.0)
        self.assertEqual(row["budget"]["projected_monthly_cost_brl"], 105.0)
        self.assertFalse(row["automatic_spending"])

    def test_tenant_cost_summary_allocates_admin_defined_shared_cost(self):
        row = tenant_cost_summary(
            _ledger(),
            tenant_id="tenant-a",
            shared_cost_allocation_pct=50,
        )
        self.assertEqual(row["state"], "TENANT_COST_SUMMARY_READY")
        self.assertEqual(row["direct_cost_brl"], 35.0)
        self.assertEqual(row["allocated_shared_cost_brl"], 25.0)
        self.assertEqual(row["estimated_total_cost_brl"], 60.0)
        self.assertTrue(row["allocation_is_admin_input"])
        self.assertFalse(row["automatic_price_change"])

    def test_admin_exposes_live_finops_ledger_view(self):
        source = Path("atlasquant_aion_admin.py").read_text(encoding="utf-8")
        self.assertIn("32 · FinOps · Custos Reais & Ledger", source)
        self.assertIn("aion_live_cost_policy", source)

    def test_module_has_no_network_or_executor_imports(self):
        source = Path("atlasquant_aion_finops_live_cost_ledger.py").read_text(
            encoding="utf-8"
        )
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
