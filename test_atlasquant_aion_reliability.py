import unittest

from atlasquant_aion_reliability import (
    cost_guardian_snapshot,
    data_guardian_snapshot,
    degraded_mode_snapshot,
    memory_protection_snapshot,
    reconcile_sources,
    reliability_snapshot,
    rollback_governance_snapshot,
)


class AtlasQuantAionReliabilityTests(unittest.TestCase):
    def test_conflicting_confirmed_sources_are_not_silently_resolved(self):
        out = reconcile_sources([
            {
                "source":"source-a","claim":"CPI","value":3.1,
                "truth_state":"CONFIRMED","available":True,"healthy":True,
                "criticality":"HIGH",
            },
            {
                "source":"source-b","claim":"CPI","value":3.2,
                "truth_state":"CONFIRMED","available":True,"healthy":True,
                "criticality":"HIGH",
            },
        ])
        self.assertTrue(out["has_conflict"])
        self.assertTrue(out["has_critical_conflict"])
        self.assertEqual(out["conflict_count"],1)
        self.assertFalse(out["executes_action"])

    def test_stale_source_degrades_without_becoming_conflict(self):
        out = data_guardian_snapshot([
            {
                "source":"calendar","claim":"PAYROLL","value":210,
                "truth_state":"CONFIRMED","available":True,"healthy":True,
                "age_minutes":70,"max_age_minutes":30,"criticality":"HIGH",
            }
        ])
        self.assertEqual(out["state"],"DEGRADED_SAFE")
        self.assertFalse(out["reconciliation"]["has_conflict"])
        self.assertFalse(out["allows_strong_claims"])

    def test_critical_conflict_fails_closed(self):
        out = data_guardian_snapshot([
            {
                "source":"a","claim":"rate","value":4.0,
                "truth_state":"CONFIRMED","available":True,"healthy":True,
                "criticality":"CRITICAL",
            },
            {
                "source":"b","claim":"rate","value":4.5,
                "truth_state":"CONFIRMED","available":True,"healthy":True,
                "criticality":"CRITICAL",
            },
        ])
        self.assertEqual(out["state"],"FAIL_CLOSED")
        self.assertFalse(out["allows_live_market_authorization"])

    def test_cost_guardian_preserves_zero_cost_default(self):
        out = cost_guardian_snapshot(
            {"allow_paid":False,"monthly_limit_usd":0,"spent_usd_estimate":0},
            {"state":"ZERO_COST_LOCAL"},
        )
        self.assertEqual(out["state"],"ZERO_COST")
        self.assertFalse(out["automatic_billing"])
        self.assertFalse(out["automatic_upgrade"])
        self.assertFalse(out["automatic_paid_fallback"])

    def test_cost_guardian_warns_near_limit(self):
        out = cost_guardian_snapshot(
            {"allow_paid":True,"monthly_limit_usd":100,"spent_usd_estimate":90},
            {"state":"EXTERNAL_READY"},
        )
        self.assertEqual(out["state"],"WARNING")
        self.assertEqual(out["used_pct"],90.0)

    def test_memory_protection_blocks_conflict_and_integrity_mismatch(self):
        conflict = memory_protection_snapshot(
            {
                "status":"CONFIRMED",
                "sha":"abc",
                "integrity":{"state":"CONFIRMED"},
            },
            checkpoint_conflict=True,
        )
        self.assertEqual(conflict["state"],"CONFLICT")
        self.assertFalse(conflict["write_safe_precondition"])

        mismatch = memory_protection_snapshot({
            "status":"CONFIRMED",
            "sha":"abc",
            "integrity":{"state":"MISMATCH"},
        })
        self.assertEqual(mismatch["state"],"INTEGRITY_MISMATCH")
        self.assertFalse(mismatch["write_safe_precondition"])

    def test_memory_protection_confirms_conditional_write_precondition(self):
        out = memory_protection_snapshot({
            "status":"CONFIRMED",
            "sha":"abc",
            "integrity":{"state":"CONFIRMED"},
        })
        self.assertEqual(out["state"],"PROTECTED")
        self.assertTrue(out["write_safe_precondition"])
        self.assertTrue(out["requires_explicit_save_approval"])

    def test_rollback_is_advisory_only(self):
        out = rollback_governance_snapshot(
            {
                "rollback_review_recommended":True,
                "has_critical":True,
                "rollback_reasons":["health check failed"],
            },
            {"can_claim_latest_main_live":False},
        )
        self.assertEqual(out["state"],"REVIEW_URGENT")
        self.assertTrue(out["requires_human_approval"])
        self.assertFalse(out["automatic_rollback"])
        self.assertFalse(out["automatic_deploy"])

    def test_degraded_mode_fails_closed_for_memory_mismatch(self):
        out = degraded_mode_snapshot(
            data_guardian={"state":"CONTROLLED"},
            memory_protection={
                "state":"INTEGRITY_MISMATCH",
                "write_safe_precondition":False,
            },
            incident_snapshot={"has_critical":False},
            critical_surfaces={"counts":{}},
            release_gate={"state":"COMPLETE","release_claim_allowed":True},
        )
        self.assertEqual(out["state"],"FAIL_CLOSED")
        self.assertFalse(out["can_save_checkpoint"])
        self.assertFalse(out["can_authorize_market_action"])
        self.assertFalse(out["real_orders_enabled"])

    def test_reliability_snapshot_is_read_only_and_uses_market_freshness(self):
        out = reliability_snapshot(
            system_context={
                "source_build":"build-a",
                "critical_surfaces":{"counts":{"OK":3}},
                "release_gate":{"state":"COMPLETE","release_claim_allowed":True},
                "publication_truth":{"can_claim_latest_main_live":True},
            },
            market_context={"fresh_confirmed":False,"summary":""},
            provider_status={"state":"ZERO_COST_LOCAL"},
            runtime_result={
                "status":"CONFIRMED",
                "sha":"abc",
                "integrity":{"state":"CONFIRMED"},
            },
            budget={"allow_paid":False,"monthly_limit_usd":0},
            incident_snapshot={"has_critical":False,"rollback_review_recommended":False},
        )
        self.assertEqual(out["degraded_mode"]["state"],"DEGRADED_SAFE")
        self.assertFalse(out["automatic_failover"])
        self.assertFalse(out["automatic_repair"])
        self.assertFalse(out["automatic_rollback"])
        self.assertFalse(out["real_orders_enabled"])


if __name__ == "__main__":
    unittest.main()
