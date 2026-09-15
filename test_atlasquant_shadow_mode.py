import unittest

from atlasquant_shadow_mode import (
    normalize_snapshot, compare_shadow_sample, append_shadow_sample, summarize_shadow,
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


if __name__=="__main__":
    unittest.main()
