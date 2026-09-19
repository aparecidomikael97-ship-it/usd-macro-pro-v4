import unittest

from atlasquant_release_candidate import (
    SourceReleaseCandidateEvidence,
    assess_source_release_candidate,
)


class AtlasQuantReleaseCandidateTests(unittest.TestCase):
    def base(self, **kw):
        data=dict(
            integration_gate_ok=True,
            source_checkpoint_ok=True,
            quality_tests_total=970,
            quality_tests_failed=0,
            pr_mergeable=True,
            candidate_based_on_current_main=True,
            secret_hygiene_ok=True,
            production_health_baseline_ok=True,
            runtime_source_parity_ok=True,
            integration_ui_smoke_ok=True,
            runtime_data_files=0,
            browser_smoke_baseline_ok=False,
            pr_draft=True,
        )
        data.update(kw)
        return SourceReleaseCandidateEvidence(**data)

    def test_clean_draft_candidate_is_reviewable_but_waits_for_manual_and_browser_check(self):
        out=assess_source_release_candidate(self.base())
        self.assertEqual(out["status"],"SOURCE_REVIEWABLE_PENDING_MANUAL")
        self.assertTrue(out["source_reviewable"])
        self.assertTrue(out["pending"])
        self.assertFalse(out["automatic_merge_allowed"])
        self.assertFalse(out["automatic_promotion_allowed"])
        self.assertFalse(out["runtime_data_copy_allowed"])
        self.assertTrue(out["post_deploy_health_required"])
        self.assertTrue(out["post_deploy_browser_smoke_required"])

    def test_fully_green_source_evidence_is_still_manual(self):
        out=assess_source_release_candidate(
            self.base(browser_smoke_baseline_ok=True,pr_draft=False)
        )
        self.assertEqual(out["status"],"SOURCE_REVIEWABLE")
        self.assertTrue(out["source_reviewable"])
        self.assertFalse(out["automatic_merge_allowed"])
        self.assertTrue(out["manual_review_required"])

    def test_runtime_source_parity_is_required_for_release_candidate(self):
        out=assess_source_release_candidate(self.base(runtime_source_parity_ok=False))
        self.assertEqual(out["status"],"BLOCKED")
        self.assertFalse(out["source_reviewable"])
        self.assertTrue(any("Runtime source" in x for x in out["hard_blocks"]))


    def test_integration_ui_smoke_is_required_for_release_candidate(self):
        out=assess_source_release_candidate(self.base(integration_ui_smoke_ok=False))
        self.assertEqual(out["status"],"BLOCKED")
        self.assertFalse(out["source_reviewable"])
        self.assertTrue(any("UI smoke" in x for x in out["hard_blocks"]))


    def test_any_runtime_data_in_source_candidate_blocks(self):
        out=assess_source_release_candidate(self.base(runtime_data_files=1))
        self.assertEqual(out["status"],"BLOCKED")
        self.assertFalse(out["source_reviewable"])
        self.assertTrue(any("runtime data" in x for x in out["hard_blocks"]))

    def test_failed_or_insufficient_quality_blocks(self):
        for total,failed in ((899,0),(970,1),(0,0)):
            with self.subTest(total=total,failed=failed):
                out=assess_source_release_candidate(
                    self.base(quality_tests_total=total,quality_tests_failed=failed)
                )
                self.assertEqual(out["status"],"BLOCKED")
                self.assertFalse(out["source_reviewable"])

    def test_core_source_evidence_is_fail_closed(self):
        fields=(
            "integration_gate_ok",
            "source_checkpoint_ok",
            "pr_mergeable",
            "candidate_based_on_current_main",
            "secret_hygiene_ok",
            "production_health_baseline_ok",
            "runtime_source_parity_ok",
        )
        for field in fields:
            with self.subTest(field=field):
                out=assess_source_release_candidate(self.base(**{field:False}))
                self.assertEqual(out["status"],"BLOCKED")

    def test_boolean_evidence_must_be_actual_boolean(self):
        fields=(
            "integration_gate_ok","source_checkpoint_ok","pr_mergeable",
            "candidate_based_on_current_main","secret_hygiene_ok",
            "production_health_baseline_ok","runtime_source_parity_ok","integration_ui_smoke_ok","browser_smoke_baseline_ok","pr_draft",
        )
        for field in fields:
            for bad in ("true",1,None):
                with self.subTest(field=field,bad=bad):
                    out=assess_source_release_candidate(self.base(**{field:bad}))
                    self.assertEqual(out["status"],"BLOCKED")
                    self.assertTrue(any("Invalid boolean" in x for x in out["hard_blocks"]))

    def test_counts_and_thresholds_fail_closed(self):
        for field in ("quality_tests_total","quality_tests_failed","runtime_data_files"):
            for bad in (-1,float("nan"),float("inf"),True):
                with self.subTest(field=field,bad=bad):
                    out=assess_source_release_candidate(self.base(**{field:bad}))
                    self.assertEqual(out["status"],"BLOCKED")
        for bad in (0,-1,float("nan"),True):
            with self.subTest(min_quality_tests=bad):
                out=assess_source_release_candidate(self.base(),min_quality_tests=bad)
                self.assertEqual(out["status"],"BLOCKED")


if __name__=="__main__":
    unittest.main()
