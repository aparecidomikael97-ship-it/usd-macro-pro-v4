from __future__ import annotations
import unittest

from atlasquant_aion_evaluation_lab import (
    default_core_suite, default_evaluation_lab, evaluate_run,
    evaluation_lab_summary, new_eval_run, normalize_evaluation_lab,
)


def full_case_results(suite, *, regress_critical=False, improve_one=True):
    rows=[]
    for index,case in enumerate(suite["cases"]):
        candidate=True
        baseline=True
        if improve_one and index==len(suite["cases"])-1:
            baseline=False
        if regress_critical and case["criticality"]=="CRITICAL":
            candidate=False
            baseline=True
            regress_critical=False
        rows.append({
            "case_id":case["case_id"],
            "baseline_pass":baseline,
            "candidate_pass":candidate,
            "evidence_refs":[f"ci:{case['case_id']}"],
        })
    return rows


def baseline_metrics():
    return {
        "task_success_pct":90,
        "hallucination_rate_pct":1,
        "safety_violation_count":0,
        "critical_regression_count":0,
        "p95_latency_ms":500,
        "estimated_cost_usd_per_100_tasks":1.0,
    }


def candidate_metrics():
    return {
        "task_success_pct":92,
        "hallucination_rate_pct":0.8,
        "safety_violation_count":0,
        "critical_regression_count":0,
        "p95_latency_ms":480,
        "estimated_cost_usd_per_100_tasks":0.9,
    }


class AtlasQuantAionEvaluationLabTests(unittest.TestCase):
    def test_default_suite_is_deterministic_across_calls(self):
        a=default_core_suite()
        b=default_core_suite()
        self.assertEqual(a["suite_id"],b["suite_id"])
        self.assertEqual(a["created_at"],b["created_at"])
        self.assertEqual(default_evaluation_lab()["digest"],default_evaluation_lab()["digest"])

    def test_default_lab_never_auto_promotes(self):
        summary=evaluation_lab_summary(default_evaluation_lab())
        self.assertGreaterEqual(summary["suites"],1)
        self.assertFalse(summary["automatic_promotion"])
        self.assertFalse(summary["production_change_allowed"])

    def test_candidate_with_evidence_and_nonregression_reaches_human_review_only(self):
        suite=default_core_suite()
        run=new_eval_run(
            suite,baseline_version="AION-1",candidate_version="AION-2",
            case_results=full_case_results(suite),
            baseline_metrics=baseline_metrics(),
            candidate_metrics=candidate_metrics(),
            evidence_refs=["ci:run-1"],
            created_at="2026-09-25T17:00:00+00:00",
        )
        out=evaluate_run(suite,run,evaluated_at="2026-09-25T17:10:00+00:00")
        self.assertEqual(out["state"],"HUMAN_REVIEW_CANDIDATE")
        self.assertFalse(out["automatic_promotion"])
        self.assertFalse(out["production_change_allowed"])
        self.assertTrue(out["requires_human_review"])

    def test_critical_case_regression_rejects_candidate(self):
        suite=default_core_suite()
        run=new_eval_run(
            suite,baseline_version="AION-1",candidate_version="AION-2",
            case_results=full_case_results(suite,regress_critical=True),
            baseline_metrics=baseline_metrics(),candidate_metrics=candidate_metrics(),
            evidence_refs=["ci:critical-case-regression"],
        )
        out=evaluate_run(suite,run)
        self.assertEqual(out["state"],"REJECTED_FOR_NOW")
        self.assertTrue(out["evaluation"]["critical_regressions"])

    def test_safety_metric_nonzero_rejects_candidate(self):
        suite=default_core_suite()
        metrics=candidate_metrics()
        metrics["safety_violation_count"]=1
        run=new_eval_run(
            suite,baseline_version="AION-1",candidate_version="AION-2",
            case_results=full_case_results(suite),
            baseline_metrics=baseline_metrics(),candidate_metrics=metrics,
            evidence_refs=["ci:safety-metric-regression"],
        )
        out=evaluate_run(suite,run)
        self.assertEqual(out["state"],"REJECTED_FOR_NOW")
        self.assertIn("METRIC:safety_violation_count",out["evaluation"]["critical_regressions"])

    def test_missing_baseline_case_result_needs_more_evidence(self):
        suite=default_core_suite()
        rows=full_case_results(suite)
        rows[0]["baseline_pass"]=None
        run=new_eval_run(
            suite,baseline_version="AION-1",candidate_version="AION-2",
            case_results=rows,baseline_metrics=baseline_metrics(),
            candidate_metrics=candidate_metrics(),
            evidence_refs=["ci:run-baseline"],
        )
        out=evaluate_run(suite,run)
        self.assertEqual(out["state"],"NEED_MORE_EVIDENCE")
        self.assertIn(suite["cases"][0]["case_id"],out["evaluation"]["missing_case_ids"])

    def test_metrics_without_run_evidence_never_reach_human_review(self):
        suite=default_core_suite()
        run=new_eval_run(
            suite,baseline_version="AION-1",candidate_version="AION-2",
            case_results=full_case_results(suite),
            baseline_metrics=baseline_metrics(),candidate_metrics=candidate_metrics(),
            evidence_refs=[],
        )
        out=evaluate_run(suite,run)
        self.assertEqual(out["state"],"NEED_MORE_EVIDENCE")
        self.assertTrue(out["evaluation"]["metric_evidence_missing"])

    def test_persisted_fake_candidate_is_recomputed_fail_closed(self):
        suite=default_core_suite()
        fake=new_eval_run(
            suite,baseline_version="AION-1",candidate_version="AION-2",
            case_results=[],baseline_metrics={},candidate_metrics={},
            evidence_refs=[],
            created_at="2026-09-25T17:00:00+00:00",
        )
        fake["state"]="HUMAN_REVIEW_CANDIDATE"
        fake["evaluation"]={"state":"HUMAN_REVIEW_CANDIDATE"}
        fake["evaluated_at"]="2026-09-25T17:10:00+00:00"
        lab=normalize_evaluation_lab({"suites":[suite],"runs":[fake]})
        self.assertEqual(lab["runs"][0]["state"],"NEED_MORE_EVIDENCE")
        self.assertFalse(lab["runs"][0]["production_change_allowed"])

    def test_missing_case_evidence_needs_more_evidence(self):
        suite=default_core_suite()
        rows=full_case_results(suite)
        rows[0]["evidence_refs"]=[]
        run=new_eval_run(
            suite,baseline_version="AION-1",candidate_version="AION-2",
            case_results=rows,baseline_metrics=baseline_metrics(),
            candidate_metrics=candidate_metrics(),
        )
        out=evaluate_run(suite,run)
        self.assertEqual(out["state"],"NEED_MORE_EVIDENCE")
        self.assertIn(suite["cases"][0]["case_id"],out["evaluation"]["missing_case_ids"])

    def test_no_measured_improvement_is_not_enough_for_promotion_candidate(self):
        suite=default_core_suite()
        run=new_eval_run(
            suite,baseline_version="AION-1",candidate_version="AION-2",
            case_results=full_case_results(suite,improve_one=False),
            baseline_metrics=baseline_metrics(),candidate_metrics=baseline_metrics(),
        )
        out=evaluate_run(suite,run)
        self.assertEqual(out["state"],"NEED_MORE_EVIDENCE")
        self.assertEqual(out["evaluation"]["improvement_signals"],0)


if __name__=="__main__":
    unittest.main()
