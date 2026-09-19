import unittest

from atlasquant_quota_shadow import (
    build_quota_shadow_sample,
    append_quota_shadow_sample,
    summarize_quota_shadow,
)


GOOD_PLAN={
    "estimated_daily_calls":309,
    "usable_cap":400,
    "within_usable_cap":True,
    "active_pairs":3,
    "background_pairs":25,
}


def status(ts, *, blocked=False, market=True, ok=True, calls=4):
    return {
        "last_run":ts,
        "forex_market_open":market,
        "twelve_calls_this_run":calls,
        "twelve_calls_requested_internal":calls,
        "twelve_daily_blocked":blocked,
        "twelve_block_type":"COTA_DIARIA" if blocked else "",
        "app_headless_ok":ok,
        "scanner_fresh":7,
        "market_map_fresh":7,
        "twelve_budget":{"used":100,"remaining":380},
    }


class AtlasQuantQuotaShadowTests(unittest.TestCase):
    def test_sample_contains_projection_and_actual_usage(self):
        s=build_quota_shadow_sample(status("2026-09-16T01:00:00Z"),plan=GOOD_PLAN)
        self.assertEqual(s["actual_http_calls"],4)
        self.assertEqual(s["adaptive_estimated_daily_calls"],309)
        self.assertTrue(s["adaptive_within_usable_cap"])
        self.assertTrue(s["sample_id"])

    def test_duplicate_sample_is_ignored(self):
        s=build_quota_shadow_sample(status("2026-09-16T01:00:00Z"),plan=GOOD_PLAN)
        rows,added=append_quota_shadow_sample([],s)
        self.assertTrue(added)
        rows2,added2=append_quota_shadow_sample(rows,s)
        self.assertFalse(added2)
        self.assertEqual(len(rows2),1)

    def test_closed_market_runs_do_not_satisfy_minimum(self):
        rows=[
            build_quota_shadow_sample(status(f"2026-09-16T0{i}:00:00Z",market=False),plan=GOOD_PLAN)
            for i in range(3)
        ]
        r=summarize_quota_shadow(rows,min_market_runs=2)
        self.assertFalse(r["minimum_met"])

    def test_enough_clean_market_runs_become_reviewable(self):
        rows=[
            build_quota_shadow_sample(status(f"2026-09-16T0{i}:00:00Z"),plan=GOOD_PLAN)
            for i in range(3)
        ]
        r=summarize_quota_shadow(rows,min_market_runs=3)
        self.assertTrue(r["quota_shadow_validated"])
        self.assertTrue(r["eligible_for_manual_review"])
        self.assertFalse(r["automatic_expansion_allowed"])

    def test_any_provider_block_prevents_validation(self):
        rows=[
            build_quota_shadow_sample(status("2026-09-16T01:00:00Z"),plan=GOOD_PLAN),
            build_quota_shadow_sample(status("2026-09-16T02:00:00Z",blocked=True),plan=GOOD_PLAN),
        ]
        r=summarize_quota_shadow(rows,min_market_runs=2)
        self.assertFalse(r["quota_shadow_validated"])
        self.assertEqual(r["provider_blocked_runs"],1)

    def test_headless_failure_prevents_validation(self):
        rows=[
            build_quota_shadow_sample(status("2026-09-16T01:00:00Z",ok=False),plan=GOOD_PLAN),
        ]
        r=summarize_quota_shadow(rows,min_market_runs=1)
        self.assertFalse(r["quota_shadow_validated"])

    def test_plan_over_budget_prevents_validation(self):
        bad=dict(GOOD_PLAN); bad["within_usable_cap"]=False
        rows=[build_quota_shadow_sample(status("2026-09-16T01:00:00Z"),plan=bad)]
        r=summarize_quota_shadow(rows,min_market_runs=1)
        self.assertFalse(r["quota_shadow_validated"])


    def test_exactly_twenty_clean_market_runs_validate_but_never_auto_expand(self):
        rows=[
            build_quota_shadow_sample(status(f"2026-09-{16+i//10:02d}T{i%10:02d}:00:00Z"),plan=GOOD_PLAN)
            for i in range(20)
        ]
        r=summarize_quota_shadow(rows,min_market_runs=20)
        self.assertEqual(r["market_open_runs"],20)
        self.assertTrue(r["quota_shadow_validated"])
        self.assertTrue(r["eligible_for_manual_review"])
        self.assertFalse(r["automatic_expansion_allowed"])
        self.assertTrue(r["manual_review_required"])

    def test_invalid_minimum_threshold_fails_closed_to_default(self):
        rows=[build_quota_shadow_sample(status("2026-09-16T01:00:00Z"),plan=GOOD_PLAN)]
        for bad in (0,-1,True,"bad"):
            with self.subTest(value=bad):
                r=summarize_quota_shadow(rows,min_market_runs=bad)
                self.assertEqual(r["min_market_runs"],20)
                self.assertFalse(r["quota_shadow_validated"])



    def test_summary_ignores_malformed_non_mapping_samples(self):
        valid=build_quota_shadow_sample(
            {"last_run":"2026-09-19T18:00:00+00:00","forex_market_open":True,"app_headless_ok":True},
            plan={"within_usable_cap":True},
        )
        summary=summarize_quota_shadow([None,"bad",42,valid],min_market_runs=1)
        self.assertEqual(summary["samples"],1)
        self.assertEqual(summary["market_open_runs"],1)
        self.assertTrue(summary["eligible_for_manual_review"])


if __name__=="__main__":
    unittest.main()
