import ast
import copy
import unittest
from datetime import datetime, timezone
from pathlib import Path

from atlasquant_aion_finops_ledger_persistence_reconciliation import (
    build_ledger_version_manifest,
    invoice_attestation,
    persistence_and_reconciliation_review_packet,
    persistence_policy,
    reconcile_invoice_to_ledger,
    verify_version_manifest_chain,
)
from atlasquant_aion_finops_live_cost_ledger import (
    build_hash_chained_ledger,
    normalize_cost_observations,
    provider_cost_attestation,
)


NOW = datetime(2026, 9, 30, 18, 0, tzinfo=timezone.utc)


def _provider_attestation():
    return provider_cost_attestation(
        provider_ref="provider-ai",
        connection_ref="connector://provider-ai/readonly",
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
                "entry_id": "ai-cost-01",
                "provider_ref": "provider-ai",
                "source_ref": "usage://ai-01",
                "category": "AI_PROVIDER",
                "tenant_id": "tenant-a",
                "shared_cost": False,
                "amount_brl": 20.0,
                "recurring": True,
                "period_start": "2026-09-01T00:00:00+00:00",
                "period_end": "2026-09-30T23:59:59+00:00",
                "observed_at": "2026-09-30T17:45:00+00:00",
            },
            {
                "entry_id": "ai-cost-02",
                "provider_ref": "provider-ai",
                "source_ref": "usage://ai-02",
                "category": "AI_PROVIDER",
                "tenant_id": "tenant-b",
                "shared_cost": False,
                "amount_brl": 15.0,
                "recurring": True,
                "period_start": "2026-09-01T00:00:00+00:00",
                "period_end": "2026-09-30T23:59:59+00:00",
                "observed_at": "2026-09-30T17:45:00+00:00",
            },
        ],
        attestations=[_provider_attestation()],
        now=NOW,
    )
    return build_hash_chained_ledger(snapshot)


def _invoice(total=35.0):
    return invoice_attestation(
        provider_ref="provider-ai",
        invoice_ref="invoice-ai-2026-09",
        source_ref="invoice://provider-ai/2026-09",
        period_start="2026-09-01T00:00:00+00:00",
        period_end="2026-09-30T23:59:59+00:00",
        total_brl=total,
        currency="BRL",
        authentication_verified=True,
        read_only_scope_verified=True,
        signature_or_source_integrity_verified=True,
        observed_at="2026-09-30T17:55:00+00:00",
    )


class FinOpsLedgerPersistenceReconciliationTests(unittest.TestCase):
    def test_policy_keeps_physical_actions_outside(self):
        row = persistence_policy()
        self.assertEqual(row["storage_model"], "IMMUTABLE_VERSION_MANIFEST_CHAIN")
        self.assertFalse(row["physical_persistence_executed_here"])
        self.assertFalse(row["invoice_paid_here"])
        self.assertFalse(row["automatic_reconciliation_writeback"])

    def test_first_version_must_bind_genesis(self):
        ledger = _ledger()
        row = build_ledger_version_manifest(
            ledger,
            version_number=1,
            previous_version_manifest_digest="0" * 64,
            storage_ref="storage://finops/v1",
            created_at="2026-09-30T18:00:00+00:00",
            created_by="mikael",
        )
        self.assertEqual(row["state"], "LEDGER_VERSION_MANIFEST_READY")
        self.assertFalse(row["physical_persistence_confirmed"])
        self.assertFalse(row["persistence_authorized"])

    def test_version_chain_detects_gap_and_replay(self):
        ledger = _ledger()
        v1 = build_ledger_version_manifest(
            ledger,
            version_number=1,
            previous_version_manifest_digest="0" * 64,
            storage_ref="storage://finops/v1",
            created_at="2026-09-30T18:00:00+00:00",
            created_by="mikael",
        )
        v2 = build_ledger_version_manifest(
            ledger,
            version_number=2,
            previous_version_manifest_digest=v1["version_manifest_digest"],
            storage_ref="storage://finops/v2",
            created_at="2026-09-30T18:10:00+00:00",
            created_by="mikael",
        )
        ok = verify_version_manifest_chain([v1, v2])
        self.assertEqual(ok["state"], "LEDGER_VERSION_CHAIN_VERIFIED")
        self.assertTrue(ok["valid"])

        gap = copy.deepcopy(v2)
        gap["version_number"] = 3
        bad = verify_version_manifest_chain([v1, gap])
        self.assertFalse(bad["valid"])
        self.assertEqual(bad["reason"], "VERSION_GAP_OR_REORDER")

        replay = verify_version_manifest_chain([v1, v1])
        self.assertFalse(replay["valid"])

    def test_invoice_attestation_is_read_only(self):
        row = _invoice()
        self.assertEqual(row["state"], "INVOICE_ATTESTATION_READY")
        self.assertFalse(row["invoice_paid"])
        self.assertFalse(row["automatic_payment"])

    def test_invoice_reconciles_exact_total(self):
        result = reconcile_invoice_to_ledger(
            _invoice(35.0),
            _ledger(),
            tolerance_brl=0.01,
        )
        self.assertEqual(result["state"], "INVOICE_LEDGER_RECONCILED")
        self.assertEqual(result["matched_entry_count"], 2)
        self.assertEqual(result["ledger_total_brl"], 35.0)
        self.assertEqual(result["difference_brl"], 0.0)
        self.assertFalse(result["payment_authorized"])

    def test_invoice_total_mismatch_blocks(self):
        result = reconcile_invoice_to_ledger(
            _invoice(45.0),
            _ledger(),
            tolerance_brl=0.01,
        )
        self.assertEqual(
            result["state"],
            "INVOICE_LEDGER_RECONCILIATION_BLOCKED",
        )
        self.assertIn("INVOICE_LEDGER_TOTAL_MISMATCH", result["blockers"])

    def test_review_packet_never_persists_or_pays(self):
        ledger = _ledger()
        v1 = build_ledger_version_manifest(
            ledger,
            version_number=1,
            previous_version_manifest_digest="0" * 64,
            storage_ref="storage://finops/v1",
            created_at="2026-09-30T18:00:00+00:00",
            created_by="mikael",
        )
        recon = reconcile_invoice_to_ledger(_invoice(), ledger)
        row = persistence_and_reconciliation_review_packet(
            [v1],
            recon,
            requested_by="mikael",
        )
        self.assertEqual(
            row["state"],
            "READY_FOR_ADMIN_PERSISTENCE_RECONCILIATION_REVIEW",
        )
        self.assertFalse(row["physical_persistence_authorized"])
        self.assertFalse(row["invoice_payment_authorized"])
        self.assertFalse(row["subscription_change_authorized"])

    def test_admin_exposes_persistence_reconciliation_view(self):
        source = Path("atlasquant_aion_admin.py").read_text(encoding="utf-8")
        self.assertIn("33 · FinOps · Persistencia & Reconciliacao", source)
        self.assertIn("aion_finops_persistence_policy", source)

    def test_module_has_no_network_or_executor_imports(self):
        source = Path(
            "atlasquant_aion_finops_ledger_persistence_reconciliation.py"
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
