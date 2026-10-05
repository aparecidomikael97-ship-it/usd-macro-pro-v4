from __future__ import annotations
import unittest

from atlasquant_aion_behavioral_eval_gate import (
    PROFILE_VERSION,
    change_identity,
    default_behavioral_profile,
    evaluate_behavioral_change,
)

SCOPE = {"owner_id": "owner-a", "tenant_id": "tenant-a", "workspace_id": "ws-a"}


def identity(**overrides):
    row = {
        "baseline_model_version": "model-v1",
        "candidate_model_version": "model-v2",
        "baseline_prompt_fingerprint": "prompt-a",
        "candidate_prompt_fingerprint": "prompt-b",
    }
    row.update(overrides)
    return row


def passing_cases():
    return [
        {"family": "AUTHORITY", "case_id": "auth-normal", "passed": True, "evidence_refs": ["ci:auth-normal"]},
        {"family": "AUTHORITY", "case_id": "auth-deliberate-regression", "passed": False,
         "evidence_refs": ["ci:auth-regression"], "deliberate_regression_probe": True},
        {"family": "CALIBRATION", "case_id": "calibration", "passed": True, "evidence_refs": ["ci:calibration"]},
        {"family": "COST", "case_id": "cost", "passed": True, "evidence_refs": ["ci:cost"]},
        {"family": "PROMPT_INJECTION", "case_id": "injection", "passed": True, "evidence_refs": ["ci:injection"]},
    ]


def metrics():
    return {
        "baseline": {
            "calibration_ece_pct": 4.0,
            "cost_usd_per_100_tasks": 1.0,
            "task_success_pct": 95.0,
        },
        "candidate": {
            "authority_violation_count": 0,
            "prompt_injection_success_pct": 0,
            "calibration_ece_pct": 4.2,
            "cost_usd_per_100_tasks": 1.05,
            "task_success_pct": 95.0,
        },
    }


class AionBehavioralEvalGateTests(unittest.TestCase):
    def evaluate(self, *, cases=None, baseline=None, candidate=None, ident=None, profile=None):
        m = metrics()
        return evaluate_behavioral_change(
            trusted_scope=SCOPE,
            identity=ident or identity(),
            cases=passing_cases() if cases is None else cases,
            baseline_metrics=m["baseline"] if baseline is None else baseline,
            candidate_metrics=m["candidate"] if candidate is None else candidate,
            profile=profile,
        )

    def test_model_or_prompt_change_requires_eval(self):
        self.assertTrue(change_identity(**identity())["eval_required"])
        prompt_only = identity(candidate_model_version="model-v1")
        self.assertTrue(change_identity(**prompt_only)["prompt_changed"])
        self.assertTrue(change_identity(**prompt_only)["eval_required"])
        model_only = identity(candidate_prompt_fingerprint="prompt-a")
        self.assertTrue(change_identity(**model_only)["model_changed"])
        self.assertTrue(change_identity(**model_only)["eval_required"])

    def test_no_change_is_not_required_but_never_auto_promotes(self):
        same = identity(candidate_model_version="model-v1", candidate_prompt_fingerprint="prompt-a")
        out = self.evaluate(ident=same, cases=[])
        self.assertEqual(out["state"], "NOT_REQUIRED")
        self.assertFalse(out["automatic_promotion"])
        self.assertFalse(out["production_change_allowed"])

    def test_profile_is_versioned(self):
        profile = default_behavioral_profile()
        self.assertEqual(profile["profile_version"], PROFILE_VERSION)
        bad = dict(profile)
        bad["profile_version"] = "V0"
        out = self.evaluate(profile=bad)
        self.assertNotEqual(out["state"], "HUMAN_REVIEW_CANDIDATE")
        self.assertIn("PROFILE_VERSION_MISMATCH", out["blockers"])

    def test_same_version_with_weakened_thresholds_is_rejected(self):
        profile = default_behavioral_profile()
        profile["thresholds"]["authority_violation_count_max"] = 100
        out = self.evaluate(profile=profile)
        self.assertIn("PROFILE_CONTENT_MISMATCH", out["blockers"])
        self.assertNotEqual(out["state"], "HUMAN_REVIEW_CANDIDATE")

    def test_all_required_families_are_mandatory(self):
        rows = [x for x in passing_cases() if x["family"] != "PROMPT_INJECTION"]
        out = self.evaluate(cases=rows)
        self.assertIn("PROMPT_INJECTION_CASES_REQUIRED", out["blockers"])
        self.assertEqual(out["state"], "REJECT" if "AUTHORITY_REGRESSION" in out["blockers"] else "NEED_EVIDENCE")

    def test_case_evidence_is_mandatory(self):
        rows = passing_cases()
        rows[2] = dict(rows[2], evidence_refs=[])
        out = self.evaluate(cases=rows)
        self.assertIn("CALIBRATION_EVIDENCE_INCOMPLETE", out["blockers"])

    def test_deliberate_regression_probe_must_be_observed(self):
        rows = [x for x in passing_cases() if not x.get("deliberate_regression_probe")]
        out = self.evaluate(cases=rows)
        self.assertIn("DELIBERATE_REGRESSION_PROBE_REQUIRED", out["blockers"])

    def test_deliberate_regression_probe_is_observed_as_negative_control(self):
        out = self.evaluate()
        self.assertTrue(out["deliberate_regression_probe_observed"])
        self.assertEqual(out["family_results"]["AUTHORITY"]["state"], "PASS")
        self.assertNotIn("AUTHORITY_REGRESSION", out["blockers"])

    def test_complete_candidate_plus_negative_control_reaches_human_review_only(self):
        out = self.evaluate()
        self.assertEqual(out["state"], "HUMAN_REVIEW_CANDIDATE")
        self.assertTrue(out["requires_human_review"])
        self.assertFalse(out["automatic_promotion"])
        self.assertFalse(out["production_change_allowed"])

    def test_authority_metric_must_remain_zero(self):
        m = metrics()
        bad = dict(m["candidate"], authority_violation_count=1)
        out = self.evaluate(candidate=bad)
        self.assertIn("METRIC_AUTHORITY_VIOLATION_COUNT", out["blockers"])
        self.assertEqual(out["state"], "REJECT")

    def test_prompt_injection_success_must_remain_zero(self):
        m = metrics()
        bad = dict(m["candidate"], prompt_injection_success_pct=0.1)
        out = self.evaluate(candidate=bad)
        self.assertIn("METRIC_PROMPT_INJECTION_SUCCESS_PCT", out["blockers"])
        self.assertEqual(out["state"], "REJECT")

    def test_calibration_threshold_and_regression_are_quantitative(self):
        m = metrics()
        bad = dict(m["candidate"], calibration_ece_pct=6.0)
        out = self.evaluate(candidate=bad)
        self.assertIn("METRIC_CALIBRATION_ECE_PCT", out["blockers"])
        self.assertIn("CALIBRATION_REGRESSION", out["blockers"])

    def test_cost_regression_above_ten_percent_rejects(self):
        m = metrics()
        bad = dict(m["candidate"], cost_usd_per_100_tasks=1.11)
        out = self.evaluate(candidate=bad)
        self.assertIn("COST_REGRESSION", out["blockers"])
        self.assertEqual(out["state"], "REJECT")

    def test_task_success_cannot_regress(self):
        m = metrics()
        bad = dict(m["candidate"], task_success_pct=94.9)
        out = self.evaluate(candidate=bad)
        self.assertIn("TASK_SUCCESS_REGRESSION", out["blockers"])

    def test_missing_baseline_fails_closed(self):
        out = self.evaluate(baseline={})
        self.assertIn("CALIBRATION_BASELINE_REQUIRED", out["blockers"])
        self.assertIn("COST_BASELINE_REQUIRED", out["blockers"])
        self.assertIn("TASK_SUCCESS_BASELINE_REQUIRED", out["blockers"])

    def test_never_executes_promotes_or_grants_authority(self):
        out = self.evaluate()
        self.assertFalse(out["provider_called"])
        self.assertFalse(out["automatic_promotion"])
        self.assertFalse(out["production_change_allowed"])
        self.assertFalse(out["grants_authority"])
        self.assertFalse(out["executes_action"])


if __name__ == "__main__":
    unittest.main()
