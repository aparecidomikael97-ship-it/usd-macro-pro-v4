from __future__ import annotations
import unittest

from atlasquant_aion_dev_fusion import (
    new_dev_fusion_pipeline, record_stage, dev_fusion_summary,
)


class AtlasQuantAionDevFusionTests(unittest.TestCase):
    def _pipeline(self):
        return new_dev_fusion_pipeline(
            "AION feature",
            twin_id="TWIN-1",
            baseline_ref="main@a",
            candidate_ref="branch@b",
            created_at="2026-09-25T18:00:00+00:00",
        )

    def test_reviewer_must_be_independent_from_builder(self):
        p=self._pipeline()
        p=record_stage(p,"BUILD",state="PASS",actor_ref="agent-builder",evidence_refs=["commit:1"])
        with self.assertRaises(ValueError):
            record_stage(p,"REVIEW",state="PASS",actor_ref="agent-builder",evidence_refs=["review:1"])

    def test_breaker_must_be_independent(self):
        p=self._pipeline()
        p=record_stage(p,"BUILD",state="PASS",actor_ref="builder",evidence_refs=["commit:1"])
        p=record_stage(p,"REVIEW",state="PASS",actor_ref="reviewer",evidence_refs=["review:1"])
        with self.assertRaises(ValueError):
            record_stage(p,"BREAK",state="PASS",actor_ref="reviewer",evidence_refs=["redteam:1"])

    def test_pipeline_reaches_human_review_not_deploy(self):
        p=self._pipeline()
        p=record_stage(p,"PLAN",state="PASS",actor_ref="planner",evidence_refs=["plan:1"])
        p=record_stage(p,"BUILD",state="PASS",actor_ref="builder",evidence_refs=["commit:1"])
        p=record_stage(p,"REVIEW",state="PASS",actor_ref="reviewer",evidence_refs=["review:1"])
        p=record_stage(p,"BREAK",state="PASS",actor_ref="breaker",evidence_refs=["redteam:1"])
        p=record_stage(
            p,"EVALUATE",state="PASS",actor_ref="evaluator",
            evidence_refs=["eval:1"],evaluation_run_id="EVAL-1",
        )
        self.assertEqual(p["state"],"HUMAN_REVIEW_CANDIDATE")
        self.assertFalse(p["automatic_merge"])
        self.assertFalse(p["automatic_deploy"])
        self.assertFalse(p["production_change_allowed"])
        self.assertEqual(dev_fusion_summary([p])["human_review_candidates"],1)

    def test_malformed_critical_findings_fail_safe_to_zero_not_crash(self):
        p=self._pipeline()
        p["stages"][1]["critical_findings"]="bad"
        from atlasquant_aion_dev_fusion import normalize_pipeline
        out=normalize_pipeline(p)
        self.assertEqual(out["stages"][1]["critical_findings"],0)

    def test_critical_finding_blocks_pipeline(self):
        p=self._pipeline()
        p=record_stage(
            p,"BUILD",state="PASS",actor_ref="builder",
            evidence_refs=["commit:1"],critical_findings=1,
        )
        self.assertEqual(p["state"],"BLOCKED")


if __name__=="__main__":
    unittest.main()
