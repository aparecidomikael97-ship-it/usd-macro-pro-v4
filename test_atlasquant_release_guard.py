import unittest

from atlasquant_release_guard import ReleaseEvidence, assess_release, should_rollback


class ReleaseGuardTests(unittest.TestCase):
    def test_small_shadow_sample_never_auto_promotes_core_change(self):
        ev = ReleaseEvidence(
            tests_total=700,
            tests_failed=0,
            critical_regressions=0,
            compile_ok=True,
            health_check_ok=True,
            shadow_samples=20,
            shadow_critical_mismatches=0,
        )
        report = assess_release(ev, core_model_change=True, min_shadow_samples_for_core=100)
        self.assertTrue(report["staging_ok"])
        self.assertFalse(report["eligible_for_manual_promotion"])
        self.assertFalse(report["automatic_core_promotion"])
        self.assertTrue(report["pending"])

    def test_large_shadow_sample_still_requires_manual_promotion(self):
        ev = ReleaseEvidence(
            tests_total=700,
            tests_failed=0,
            critical_regressions=0,
            compile_ok=True,
            health_check_ok=True,
            shadow_samples=500,
            shadow_critical_mismatches=0,
        )
        report = assess_release(ev, core_model_change=True, min_shadow_samples_for_core=100)
        self.assertTrue(report["eligible_for_manual_promotion"])
        self.assertFalse(report["automatic_core_promotion"])

    def test_failed_health_or_data_integrity_blocks_release(self):
        ev = ReleaseEvidence(
            tests_total=700,
            tests_failed=0,
            critical_regressions=0,
            compile_ok=True,
            health_check_ok=False,
            data_migrations_ok=False,
        )
        report = assess_release(ev)
        self.assertFalse(report["staging_ok"])
        self.assertFalse(report["eligible_for_manual_promotion"])
        self.assertGreaterEqual(len(report["hard_blocks"]), 2)

    def test_shadow_mismatch_blocks_release(self):
        ev = ReleaseEvidence(
            tests_total=700,
            tests_failed=0,
            critical_regressions=0,
            compile_ok=True,
            health_check_ok=True,
            shadow_samples=500,
            shadow_critical_mismatches=1,
        )
        report = assess_release(ev, core_model_change=True)
        self.assertFalse(report["staging_ok"])
        self.assertFalse(report["eligible_for_manual_promotion"])

    def test_integrity_breach_forces_rollback(self):
        report = should_rollback(
            app_boot_ok=True,
            health_check_ok=True,
            data_integrity_breach=True,
        )
        self.assertTrue(report["rollback"])
        self.assertTrue(report["reasons"])


if __name__ == "__main__":
    unittest.main()
