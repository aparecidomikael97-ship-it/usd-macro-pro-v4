import unittest

from atlasquant_adaptive_coverage import adaptive_coverage_plan, adaptive_readiness


class AtlasQuantAdaptiveCoverageTests(unittest.TestCase):
    def test_default_28_pair_plan_fits_reserved_budget(self):
        p=adaptive_coverage_plan()
        self.assertEqual(p["pair_count"],28)
        self.assertTrue(p["within_usable_cap"])
        self.assertLessEqual(p["estimated_daily_calls"],p["usable_cap"])

    def test_only_active_set_is_execution_grade(self):
        p=adaptive_coverage_plan(active_pairs=3)
        self.assertTrue(p["execution_grade_only_for_active_set"])
        self.assertTrue(p["background_pairs_must_not_be_executable_when_stale"])

    def test_plan_requires_m15_resampling(self):
        p=adaptive_coverage_plan()
        self.assertTrue(p["derive_h1_h4_from_m15_required"])
        self.assertGreaterEqual(p["required_m15_history_bars"],1000)

    def test_no_live_or_automatic_expansion(self):
        p=adaptive_coverage_plan()
        self.assertFalse(p["live_change_allowed"])
        self.assertFalse(p["automatic_expansion_allowed"])

    def test_tight_budget_fails_closed(self):
        p=adaptive_coverage_plan(daily_cap=200,reserved_calls=50)
        self.assertFalse(p["within_usable_cap"])
        self.assertGreater(p["excess_calls"],0)

    def test_readiness_building_until_all_validation_done(self):
        p=adaptive_coverage_plan()
        r=adaptive_readiness(p)
        self.assertEqual(r["status"],"BUILDING")
        self.assertEqual(len(r["blockers"]),3)
        self.assertFalse(r["automatic_expansion_allowed"])

    def test_readiness_can_become_reviewable_but_not_auto_expand(self):
        p=adaptive_coverage_plan()
        r=adaptive_readiness(
            p,
            m15_resampling_validated=True,
            freshness_gate_validated=True,
            quota_shadow_validated=True,
        )
        self.assertEqual(r["status"],"REVIEWABLE")
        self.assertFalse(r["automatic_expansion_allowed"])

    def test_active_count_is_bounded_by_pair_count(self):
        p=adaptive_coverage_plan(pair_count=2,active_pairs=9)
        self.assertEqual(p["active_pairs"],2)
        self.assertEqual(p["background_pairs"],0)


    def test_invalid_numeric_inputs_fail_closed_without_crashing(self):
        for bad in (float("nan"),float("inf"),float("-inf"),"bad"):
            with self.subTest(value=bad):
                p=adaptive_coverage_plan(active_m15_min=bad)
                self.assertFalse(p["inputs_valid"])
                self.assertFalse(p["within_usable_cap"])
                self.assertFalse(p["automatic_expansion_allowed"])

    def test_zero_or_negative_cadence_is_not_quota_safe(self):
        for bad in (0,-1):
            with self.subTest(cadence=bad):
                p=adaptive_coverage_plan(background_m15_min=bad)
                self.assertFalse(p["within_usable_cap"])
                self.assertEqual(p["background_m15_calls_per_pair"],0)


if __name__=="__main__":
    unittest.main()
