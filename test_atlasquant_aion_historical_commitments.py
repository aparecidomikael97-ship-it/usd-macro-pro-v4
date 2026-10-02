import copy
import unittest
from pathlib import Path

import atlasquant_aion_historical_commitments as history


ROOT = Path(__file__).resolve().parent


class HistoricalCommitmentsTests(unittest.TestCase):
    def test_repository_registry_is_valid(self):
        report = history.validate_repository(ROOT)
        self.assertEqual(report["errors"], [], "\n".join(report["errors"]))
        self.assertTrue(report["ok"])
        self.assertGreaterEqual(report["count"], 108)
        self.assertEqual(report["daily_coverage_count"], 18)
        self.assertEqual(report["unresolved_days"], [])

    def test_snapshot_is_read_only_and_fail_closed(self):
        snapshot = history.historical_commitments_snapshot(ROOT)
        self.assertFalse(snapshot["execution_authority"])
        self.assertFalse(snapshot["automatic_activation"])
        self.assertFalse(snapshot["real_trading_enabled"])
        self.assertFalse(snapshot["external_action_executed"])
        self.assertIn("D-2026-09-30-CLT-INDEPENDENCE-INDEX", snapshot["pending_ids"])
        self.assertEqual(len(snapshot["daily_coverage"]), 18)
        self.assertEqual(snapshot["unresolved_days"], [])
        self.assertEqual(len(snapshot["inherited_gaps"]), 8)
        self.assertTrue(all(row["state"] == "COVERED_WITH_EVIDENCE" for row in snapshot["daily_coverage"]))
        self.assertTrue(all(row["closed"] is False for row in snapshot["daily_coverage"]))
    def test_pending_commitment_cannot_claim_implementation(self):
        manifest = history.load_manifest(ROOT)
        item = copy.deepcopy(manifest["commitments"][0])
        item["implemented"] = True
        errors = history.validate_commitment(item, set())
        self.assertTrue(any("pending commitment" in error for error in errors))

    def test_day_cannot_close_while_commitments_are_non_terminal(self):
        manifest = history.load_manifest(ROOT)
        day = next(row for row in manifest["daily_coverage"] if row["date"] == "2026-09-23")
        self.assertFalse(day["closed"])
        mutated = copy.deepcopy(manifest)
        target = next(row for row in mutated["daily_coverage"] if row["date"] == "2026-09-23")
        target["closed"] = True
        target["closure_evidence"] = ["docs/continuidade/AION_FOUNDATION_2026-09-23.md"]
        original = history.load_manifest
        try:
            history.load_manifest = lambda root=None: mutated
            report = history.validate_repository(ROOT)
        finally:
            history.load_manifest = original
        self.assertTrue(
            any("closed day still has non-terminal commitments" in error for error in report["errors"])
        )

    def test_required_recovered_topics_are_present(self):
        ids = {item["id"] for item in history.load_manifest(ROOT)["commitments"]}
        required = {
            "D-2026-09-25-CYBER-IMMUNE-SYSTEM",
            "D-2026-09-25-DIGITAL-TWIN-PREEXEC-PROOF",
            "D-2026-09-25-PORTABLE-CORE-EVERYWHERE",
            "D-2026-09-25-AION-VAULT-OFFICIAL-ACCESS",
            "D-2026-09-26-TREASURY-GROWTH-ENGINE",
            "D-2026-09-30-BUSINESS-CLIENT-PORTAL-TENANT",
            "D-2026-09-30-BUSINESS-RBAC-LGPD-FINOPS",
            "D-2026-09-30-FUTURE-BIOMETRIC-CRITICAL-DECISION",
            "D-2026-09-30-LIBRARY-OFFICIAL-KNOWLEDGE-FLOW",
            "D-2026-09-25-FORTRESS-LAYER",
            "D-2026-09-25-SOVEREIGNTY-KERNEL",
            "D-2026-09-25-AUTONOMY-BUDGET",
            "D-2026-09-25-FALSIFICATION-ENGINE",
            "D-2026-09-29-PRIME-SHADOW-SENTINEL",
            "D-2026-09-29-SUPPLY-CHAIN-SECURITY",
            "D-2026-09-29-EXECUTABLE-CONSTITUTION-HUMAN-CONTROL",
            "D-2026-09-23-NOTIFICATION-CENTER",
            "D-2026-09-23-OPENING-TRADE-WIN-WDO-CORRELATES",
            "D-2026-09-24-BUSINESS-MARKETPLACE-IN-ECOSYSTEM",
            "D-2026-09-24-DIGITAL-INCOME-AREA",
            "D-2026-09-24-REALTIME-EVENT-ALERTS",
            "D-AION-SINGLE-NUCLEUS",
            "D-2026-09-18-ACADEMY-AFTER-UI-STABLE",
            "D-2026-09-18-COT-FINAL-PHASE",
            "D-2026-09-20-OPERATE-INVEST-BOTH",
            "D-2026-09-21-FIXED-NEURAL-VOICE",
            "D-2026-09-22-RADAR-MAIN-NAVIGATION",
            "D-2026-10-02-AION-EIGHT-INTERNAL-ROLES",
            "D-2026-09-17-AUTOPILOT-PAPER-V116",
            "D-2026-09-17-TWELVE-DATA-PROD-SMOKE-BLOCK",
            "D-2026-09-28-FOREX28-RADAR-LAB-FOUNDATION",
            "D-2026-09-28-AION-ADMIN-REPLAY-HEALTH-GOVERNANCE",
            "D-2026-10-01-NIGHTSHIFT-V1-RECOVERY",
            "D-2026-10-01-LIBRARY-FOUNDATION-INDEX-PDF",
            "D-2026-10-01-LIBRARY-IDENTITY-ACL-DR-BLOCKERS",
            "D-2026-10-02-DAILY-HISTORICAL-SWEEP",
            "D-2026-10-02-PHASE2-60-20-20",
            "D-2026-10-02-DECEMBER-90-PLANNING-TARGET",
        }
        self.assertTrue(required.issubset(ids))


if __name__ == "__main__":
    unittest.main()
