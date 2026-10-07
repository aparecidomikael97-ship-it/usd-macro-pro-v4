from __future__ import annotations

import unittest

from atlasquant_aion_managed_operations_simulation import (
    AUTONOMY_CLASSES,
    build_simulated_workload,
    classify_task,
    evaluate_managed_operations,
    run_reference_simulation,
)


class AionManagedOperationsSimulationTests(unittest.TestCase):
    def test_reference_workload_has_exact_scale_and_company_split(self):
        rows = build_simulated_workload(1000)
        self.assertEqual(len(rows), 1000)
        counts = {}
        for row in rows:
            counts[row["company_id"]] = counts.get(row["company_id"], 0) + 1
        self.assertEqual(sorted(counts.values()), [333, 333, 334])

    def test_reference_simulation_is_deterministic_and_passes(self):
        first = run_reference_simulation()
        second = run_reference_simulation()
        self.assertEqual(first["state"], "PASS")
        self.assertEqual(first["pilot_recommendation"], "HUMAN_REVIEW_CANDIDATE")
        self.assertEqual(first["evidence_digest"], second["evidence_digest"])
        self.assertEqual(first["total_tasks"], 1000)
        self.assertEqual(first["company_count"], 3)
        self.assertFalse(first["blockers"])

    def test_all_autonomy_classes_are_exercised(self):
        out = run_reference_simulation()
        self.assertEqual(set(out["class_counts"]), set(AUTONOMY_CLASSES))
        for name in AUTONOMY_CLASSES:
            self.assertGreater(out["class_counts"][name], 0)

    def test_reference_policy_has_zero_classification_and_unsafe_escape_errors(self):
        out = run_reference_simulation()
        self.assertEqual(out["classification_error_count"], 0)
        self.assertEqual(out["classification_error_rate_pct"], 0.0)
        self.assertEqual(out["unsafe_escape_count"], 0)
        self.assertEqual(out["deny_escape_count"], 0)

    def test_simulation_reports_cost_savings_and_work_completed_cost(self):
        out = run_reference_simulation()
        self.assertGreater(out["manual_baseline_cost_brl"], out["modeled_operating_cost_brl"])
        self.assertGreater(out["modeled_savings_brl"], 0)
        self.assertGreater(out["modeled_roi_pct"], 0)
        self.assertGreater(out["manual_cost_per_task_brl"], out["modeled_cost_per_task_brl"])
        self.assertGreater(out["human_minutes_saved"], 0)

    def test_automation_and_assistance_metrics_are_separate(self):
        out = run_reference_simulation()
        self.assertGreater(out["assisted_or_auto_rate_pct"], out["auto_safe_rate_pct"])
        self.assertGreater(out["human_touch_rate_pct"], 0)
        self.assertLess(out["auto_safe_rate_pct"], 100)

    def test_deny_and_human_only_fail_closed(self):
        self.assertEqual(
            classify_task(
                {
                    "task_type": "unknown",
                    "risk": "CRITICAL",
                    "sensitivity": "CRITICAL",
                    "attempts_policy_bypass": True,
                }
            ),
            "DENY",
        )
        self.assertEqual(
            classify_task(
                {
                    "task_type": "sensitive_exception",
                    "risk": "HIGH",
                    "sensitivity": "HIGH",
                    "requires_owner_judgment": True,
                }
            ),
            "HUMAN_ONLY",
        )

    def test_binding_commitment_requires_approval(self):
        self.assertEqual(
            classify_task(
                {
                    "task_type": "contract_or_price_commitment",
                    "risk": "HIGH",
                    "sensitivity": "MEDIUM",
                    "requires_binding_commitment": True,
                }
            ),
            "REQUIRE_APPROVAL",
        )

    def test_injected_misclassification_blocks_candidate(self):
        rows = build_simulated_workload(20)
        rows[0]["expected_class"] = "DENY"
        out = evaluate_managed_operations(rows, expected_total=20, expected_company_count=3)
        self.assertEqual(out["state"], "BLOCKED")
        self.assertEqual(out["pilot_recommendation"], "HOLD")
        self.assertIn("CLASSIFICATION_ERROR_PRESENT", out["blockers"])

    def test_count_mismatch_blocks(self):
        rows = build_simulated_workload(999)
        out = evaluate_managed_operations(rows, expected_total=1000, expected_company_count=3)
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("TASK_COUNT_MISMATCH", out["blockers"])

    def test_simulation_has_no_external_side_effect_authority(self):
        out = run_reference_simulation()
        for key in (
            "customer_data_used",
            "provider_called",
            "external_tool_called",
            "production_mutation",
            "payment_executed",
            "trading_executed",
            "automatic_customer_commitment",
            "merge_authorized",
            "deploy_authorized",
            "executes_action",
        ):
            self.assertFalse(out[key], key)


if __name__ == "__main__":
    unittest.main()
