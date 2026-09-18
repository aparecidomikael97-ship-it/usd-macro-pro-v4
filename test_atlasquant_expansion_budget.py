import unittest

from atlasquant_expansion_budget import (
    estimate_daily_calls, max_supported_pairs, expansion_plan,
)


class AtlasQuantExpansionBudgetTests(unittest.TestCase):
    def test_zero_pairs_zero_calls(self):
        e=estimate_daily_calls(pair_count=0)
        self.assertEqual(e["estimated_daily_calls"],0)
        self.assertTrue(e["within_cap"])

    def test_priority_never_exceeds_pair_count(self):
        e=estimate_daily_calls(pair_count=2,priority_count=3)
        self.assertEqual(e["priority_count"],2)
        self.assertEqual(e["normal_count"],0)

    def test_current_seven_fit_default_cap(self):
        e=estimate_daily_calls(pair_count=7,priority_count=3)
        self.assertTrue(e["within_cap"])
        self.assertLessEqual(e["estimated_daily_calls"],480)

    def test_twenty_eight_exceed_default_cap(self):
        e=estimate_daily_calls(pair_count=28,priority_count=3)
        self.assertFalse(e["within_cap"])
        self.assertGreater(e["estimated_daily_calls"],480)

    def test_expansion_plan_requires_change(self):
        p=expansion_plan(7,28,priority_count=3,daily_cap=480)
        self.assertTrue(p["target_requires_change"])
        self.assertGreater(p["estimated_multiplier"],2.0)

    def test_max_supported_pairs_is_below_28(self):
        m=max_supported_pairs(priority_count=3,daily_cap=480)
        self.assertLess(m,28)
        self.assertGreaterEqual(m,7)

    def test_larger_cap_can_support_more_pairs(self):
        a=max_supported_pairs(priority_count=3,daily_cap=480)
        b=max_supported_pairs(priority_count=3,daily_cap=2000)
        self.assertGreater(b,a)

    def test_higher_cadence_interval_reduces_calls(self):
        fast=estimate_daily_calls(pair_count=7,normal_m15_min=55)
        slow=estimate_daily_calls(pair_count=7,normal_m15_min=110)
        self.assertLess(slow["estimated_daily_calls"],fast["estimated_daily_calls"])


    def test_invalid_planner_inputs_fail_closed(self):
        for bad in (float("nan"),float("inf"),float("-inf"),-1,True,"bad"):
            with self.subTest(bad=bad):
                out=estimate_daily_calls(pair_count=7,daily_cap=bad)
                self.assertFalse(out["inputs_valid"])
                self.assertFalse(out["within_cap"])

    def test_invalid_cadence_never_looks_within_cap(self):
        for bad in (0,-1,float("nan"),float("inf")):
            with self.subTest(bad=bad):
                out=estimate_daily_calls(pair_count=7,normal_m15_min=bad)
                self.assertFalse(out["within_cap"])


if __name__=="__main__":
    unittest.main()
