import unittest
from atlasquant_release_guard import ReleaseEvidence, assess_release, should_rollback

class ReleaseGuardTests(unittest.TestCase):
    def base(self, **kw):
        data=dict(tests_total=769,tests_failed=0,critical_regressions=0,compile_ok=True,health_check_ok=True,shadow_samples=120,shadow_critical_mismatches=0,data_migrations_ok=True)
        data.update(kw); return ReleaseEvidence(**data)

    def test_clean_evidence_is_staging_eligible_but_never_auto_promotes_core(self):
        out=assess_release(self.base(),core_model_change=True,min_shadow_samples_for_core=100)
        self.assertTrue(out["staging_ok"])
        self.assertTrue(out["eligible_for_manual_promotion"])
        self.assertFalse(out["automatic_core_promotion"])

    def test_invalid_counts_fail_closed(self):
        fields=("tests_total","tests_failed","critical_regressions","shadow_samples","shadow_critical_mismatches")
        for field in fields:
            for bad in (float("nan"),float("inf"),float("-inf"),-1,True):
                with self.subTest(field=field,bad=bad):
                    out=assess_release(self.base(**{field:bad}),core_model_change=True)
                    self.assertFalse(out["staging_ok"])
                    self.assertFalse(out["eligible_for_manual_promotion"])

    def test_invalid_thresholds_fail_closed(self):
        for bad in (0,-1,float("nan"),float("inf")):
            with self.subTest(min_tests=bad):
                self.assertFalse(assess_release(self.base(),min_tests=bad)["staging_ok"])
        for bad in (-1,float("nan"),float("inf")):
            with self.subTest(shadow=bad):
                self.assertFalse(assess_release(self.base(),core_model_change=True,min_shadow_samples_for_core=bad)["staging_ok"])


    def test_private_release_requires_valid_access_configuration(self):
        blocked=assess_release(self.base(private_access_required=True,access_config_ok=False))
        self.assertFalse(blocked["staging_ok"])
        self.assertTrue(any("Acesso privado obrigatório" in x for x in blocked["hard_blocks"]))
        ok=assess_release(self.base(private_access_required=True,access_config_ok=True))
        self.assertTrue(ok["staging_ok"])

    def test_boolean_release_evidence_must_be_actual_bool(self):
        for field in ("compile_ok","health_check_ok","data_migrations_ok","private_access_required","access_config_ok"):
            for bad in ("true",1,None):
                with self.subTest(field=field,bad=bad):
                    out=assess_release(self.base(**{field:bad}))
                    self.assertFalse(out["staging_ok"])
                    self.assertTrue(any("Flags de release inválidas" in x for x in out["hard_blocks"]))

    def test_invalid_error_rates_force_rollback(self):
        for bad in (float("nan"),float("inf"),float("-inf"),-1,"bad"):
            with self.subTest(rate=bad):
                out=should_rollback(app_boot_ok=True,health_check_ok=True,error_rate_pct=bad)
                self.assertTrue(out["rollback"])

    def test_error_rate_above_limit_rolls_back(self):
        self.assertTrue(should_rollback(app_boot_ok=True,health_check_ok=True,error_rate_pct=5.1,max_error_rate_pct=5.0)["rollback"])

if __name__=="__main__":
    unittest.main()
