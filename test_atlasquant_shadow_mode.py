import unittest

from atlasquant_shadow_mode import (
    normalize_snapshot, compare_shadow_sample, append_shadow_sample, summarize_shadow, shadow_pair_breakdown, DEFAULT_SHADOW_PAIRS,
)


class AtlasQuantShadowModeTests(unittest.TestCase):
    def snap(self, side="BUY", executable=False, score=80, version="v1"):
        return {
            "pair":"EUR/USD","side":side,"state":"WAIT","score":score,
            "data_quality":90,"executable":executable,"version":version,
            "timestamp":"2026-09-15T12:00:00Z",
        }

    def test_invalid_side_becomes_neutral(self):
        self.assertEqual(normalize_snapshot({"side":"X"},role="CHAMPION")["side"],"NEUTRAL")

    def test_equal_snapshots_agree(self):
        s=compare_shadow_sample(self.snap(),self.snap(version="v2"))
        self.assertTrue(s["side_match"])
        self.assertTrue(s["execution_match"])
        self.assertFalse(s["critical_mismatch"])

    def test_opposite_direction_is_critical(self):
        s=compare_shadow_sample(self.snap("BUY"),self.snap("SELL",version="v2"))
        self.assertTrue(s["opposite_direction"])
        self.assertTrue(s["critical_mismatch"])

    def test_execution_disagreement_is_critical(self):
        s=compare_shadow_sample(self.snap(executable=False),self.snap(executable=True,version="v2"))
        self.assertTrue(s["critical_mismatch"])
        self.assertFalse(s["execution_match"])

    def test_pair_mismatch_is_critical(self):
        a=self.snap(); b=self.snap(version="v2"); b["pair"]="GBP/USD"
        self.assertTrue(compare_shadow_sample(a,b)["critical_mismatch"])

    def test_append_deduplicates_sample(self):
        s=compare_shadow_sample(self.snap(),self.snap(version="v2"))
        rows,added=append_shadow_sample([],s)
        self.assertTrue(added)
        rows2,added2=append_shadow_sample(rows,s)
        self.assertFalse(added2)
        self.assertEqual(len(rows2),1)

    def test_sample_id_changes_across_timestamped_observations(self):
        a=self.snap(); b=self.snap(version="v2")
        s1=compare_shadow_sample(a,b)
        a2=dict(a); b2=dict(b)
        a2["timestamp"]="2026-09-15T12:15:00Z"
        b2["timestamp"]="2026-09-15T12:15:00Z"
        s2=compare_shadow_sample(a2,b2)
        self.assertNotEqual(s1["sample_id"],s2["sample_id"])

    def test_nonfinite_scores_do_not_poison_summary(self):
        a=self.snap(score=float("nan"))
        b=self.snap(score=float("inf"),version="v2")
        s=compare_shadow_sample(a,b)
        self.assertIsNone(s["score_delta"])
        summary=summarize_shadow([s],min_samples=1)
        self.assertIsNone(summary["mean_abs_score_delta"])

    def test_expected_pair_coverage_requires_every_pair(self):
        s=compare_shadow_sample(self.snap(),self.snap(version="v2"))
        summary=summarize_shadow(
            [s],min_samples=1,
            expected_pairs=("EUR/USD","GBP/USD","USD/JPY"),
            min_pair_samples=1,
        )
        self.assertEqual(summary["pairs_meeting_minimum"],1)
        self.assertEqual(set(summary["missing_pairs"]),{"GBP/USD","USD/JPY"})
        self.assertFalse(summary["eligible_for_manual_review"])

    def test_summary_never_allows_auto_promotion(self):
        s=compare_shadow_sample(self.snap(),self.snap(version="v2"))
        summary=summarize_shadow([s],min_samples=1)
        self.assertTrue(summary["eligible_for_manual_review"])
        self.assertFalse(summary["auto_promotion_allowed"])

    def test_critical_mismatch_blocks_manual_review(self):
        s=compare_shadow_sample(self.snap("BUY"),self.snap("SELL",version="v2"))
        summary=summarize_shadow([s],min_samples=1)
        self.assertFalse(summary["eligible_for_manual_review"])

    def test_minimum_sample_gate(self):
        s=compare_shadow_sample(self.snap(),self.snap(version="v2"))
        summary=summarize_shadow([s],min_samples=2)
        self.assertFalse(summary["minimum_met"])
        self.assertFalse(summary["eligible_for_manual_review"])

    def test_pair_breakdown_exposes_concentration(self):
        s=compare_shadow_sample(self.snap(),self.snap(version="v2"))
        rows=shadow_pair_breakdown(
            [s],
            expected_pairs=("EUR/USD","GBP/USD"),
            min_pair_samples=1,
        )
        by_pair={x["pair"]:x for x in rows}
        self.assertEqual(by_pair["EUR/USD"]["samples"],1)
        self.assertEqual(by_pair["GBP/USD"]["samples"],0)
        self.assertFalse(by_pair["GBP/USD"]["minimum_met"])

    def test_balanced_coverage_required_when_expected_pairs_supplied(self):
        s=compare_shadow_sample(self.snap(),self.snap(version="v2"))
        summary=summarize_shadow(
            [s],
            min_samples=1,
            expected_pairs=("EUR/USD","GBP/USD"),
            min_pair_samples=1,
        )
        self.assertTrue(summary["minimum_met"])
        self.assertFalse(summary["coverage_balanced"])
        self.assertFalse(summary["eligible_for_manual_review"])
        self.assertIn("GBP/USD",summary["missing_pairs"])

    def test_balanced_coverage_can_be_reviewable(self):
        a=self.snap()
        b=self.snap(version="v2")
        s1=compare_shadow_sample(a,b)
        c=self.snap(); c["pair"]="GBP/USD"; c["timestamp"]="2026-09-15T12:01:00Z"
        d=dict(c); d["version"]="v2"
        s2=compare_shadow_sample(c,d)
        summary=summarize_shadow(
            [s1,s2],
            min_samples=2,
            expected_pairs=("EUR/USD","GBP/USD"),
            min_pair_samples=1,
        )
        self.assertTrue(summary["coverage_balanced"])
        self.assertTrue(summary["eligible_for_manual_review"])


    def test_invalid_review_thresholds_fail_closed(self):
        samples=[]
        for i in range(120):
            pair=DEFAULT_SHADOW_PAIRS[i % len(DEFAULT_SHADOW_PAIRS)]
            samples.append(compare_shadow_sample(
                {"pair":pair,"side":"BUY","state":"OK","score":70,"quality":90,"executable":True,"version":"c","timestamp":str(i)},
                {"pair":pair,"side":"BUY","state":"OK","score":70,"quality":90,"executable":True,"version":"x","timestamp":str(i)},
            ))
        for bad in (0,-1,float("nan"),float("inf"),True,"bad"):
            with self.subTest(min_samples=bad):
                s=summarize_shadow(samples,min_samples=bad,expected_pairs=DEFAULT_SHADOW_PAIRS,min_pair_samples=1)
                self.assertFalse(s["thresholds_valid"])
                self.assertFalse(s["eligible_for_manual_review"])
            with self.subTest(min_pair=bad):
                s=summarize_shadow(samples,min_samples=1,expected_pairs=DEFAULT_SHADOW_PAIRS,min_pair_samples=bad)
                self.assertFalse(s["thresholds_valid"])
                self.assertFalse(s["eligible_for_manual_review"])


if __name__=="__main__":
    unittest.main()
