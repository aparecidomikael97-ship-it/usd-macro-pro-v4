"""Workers Free inbound/CPU, burst and DO capacity separation, offline only."""
import unittest

from atlasquant_aion_external_witness_cost_capacity_reference_v1 import (
    model_witness_cost, NO_AUTHORITY,
)
from test_atlasquant_aion_external_witness_cost_capacity_reference_v1 import (
    plan, hypothetical_quote,
)

def profile(*, read=1, write=1, other=0, cpu="5", peak="1"):
    return {
        "requests_per_read": read,
        "requests_per_write": write,
        "other_account_requests_per_day": other,
        "cpu_ms_per_invocation": cpu,
        "peak_day_multiplier": peak,
    }

class WitnessWorkersFreePeakCapacityTests(unittest.TestCase):
    def assert_never_authority(self, x):
        for k in NO_AUTHORITY:
            self.assertIs(x[k], False, k)
        self.assertIs(x["full_stack_monthly_cost_brl"], None)
        self.assertIs(x["workers_caller_quota_verified"], False)

    def test_no_worker_profile_is_not_a_free_capacity_certification(self):
        x = model_witness_cost(plan())
        self.assertEqual(x["status"], "COST_NOT_QUOTED")
        self.assertIn("WORKERS_FREE_USAGE_AND_PEAK_NOT_MODELED", x["blockers"])
        self.assertFalse(x["workers_profile_included"])
        self.assertIsNone(x["workers_requests_per_day_modeled"])
        self.assert_never_authority(x)

    def test_small_synthetic_worker_profile_is_still_not_measured(self):
        x = model_witness_cost(plan(), worker_profile=profile())
        self.assertEqual(x["status"], "COST_NOT_QUOTED")
        self.assertEqual(x["workers_requests_per_day_modeled"],16)
        self.assertEqual(x["workers_total_peak_requests_per_day_modeled"],16)
        self.assertEqual(x["do_peak_requests_per_day"],40)
        self.assertTrue(x["workers_profile_included"])
        self.assertIn("WORKERS_FREE_AND_OTHER_ACCOUNT_ONLY_SELF_DECLARED",x["blockers"])
        self.assert_never_authority(x)

    def test_worker_inbound_can_breach_even_when_do_within_free(self):
        # 1000 tenants x (12 reads,4 writes) x inbound fanout >100k/day,
        # while DO capacity is only 40k RPC/day.
        x = model_witness_cost(plan(1000),
             worker_profile=profile(read=6,write=8))
        self.assertEqual(x["do_requests_per_day"],40000)
        self.assertEqual(x["workers_total_peak_requests_per_day_modeled"],104000)
        self.assertIn("CF_WORKERS_FREE_INBOUND_REQUESTS_EXCEEDED",x["blockers"])
        self.assertEqual(x["status"],"FREE_CAPACITY_EXCEEDED")
        self.assert_never_authority(x)

    def test_shared_free_worker_account_quota_already_used(self):
        x = model_witness_cost(plan(),worker_profile=profile(other=99990))
        self.assertEqual(x["workers_total_peak_requests_per_day_modeled"],100006)
        self.assertIn("CF_WORKERS_FREE_INBOUND_REQUESTS_EXCEEDED",x["blockers"])
        self.assert_never_authority(x)

    def test_per_invocation_cpu_over_10ms_free_is_separate(self):
        x=model_witness_cost(plan(),worker_profile=profile(cpu="10.01"))
        self.assertIn("CF_WORKERS_FREE_CPU_PER_INVOCATION_EXCEEDED",x["blockers"])
        self.assertEqual(x["status"],"FREE_CAPACITY_EXCEEDED")
        self.assert_never_authority(x)
        y=model_witness_cost(plan(),worker_profile=profile(cpu="10"))
        self.assertNotIn("CF_WORKERS_FREE_CPU_PER_INVOCATION_EXCEEDED",y["blockers"])
        self.assert_never_authority(y)

    def test_burst_peak_breaks_do_requests_even_under_mean_quota(self):
        x=model_witness_cost(plan(1000),worker_profile=profile(peak="3"))
        self.assertEqual(x["do_requests_per_day"],40000)
        self.assertEqual(x["do_peak_requests_per_day"],120000)
        self.assertIn("CF_DO_PEAK_REQUESTS_EXCEEDED",x["blockers"])
        self.assertEqual(x["status"],"FREE_CAPACITY_EXCEEDED")
        self.assert_never_authority(x)

    def test_burst_can_break_worker_limit_without_breaking_do(self):
        x=model_witness_cost(plan(1000),worker_profile=profile(read=4,write=4,peak="2"))
        self.assertEqual(x["do_peak_requests_per_day"],80000)
        self.assertEqual(x["workers_total_peak_requests_per_day_modeled"],128000)
        self.assertIn("CF_WORKERS_FREE_INBOUND_REQUESTS_EXCEEDED",x["blockers"])
        self.assertNotIn("CF_DO_PEAK_REQUESTS_EXCEEDED",x["blockers"])
        self.assert_never_authority(x)

    def test_do_rows_written_peak_fails_while_average_passes(self):
        p=plan(1000)
        p["writes_per_tenant_per_day"]=30
        x=model_witness_cost(p,worker_profile=profile(peak="2"))
        self.assertEqual(x["do_rows_written_per_day"],90000)
        self.assertEqual(x["do_peak_rows_written_per_day"],180000)
        self.assertIn("CF_DO_PEAK_ROWS_WRITTEN_EXCEEDED",x["blockers"])
        self.assert_never_authority(x)

    def test_invalid_and_incomplete_worker_profile_is_not_defaulted_positive(self):
        for invalid in ([],{},{"requests_per_read":1},"VERIFIED"):
            with self.subTest(invalid=invalid):
                x=model_witness_cost(plan(),worker_profile=invalid)
                self.assertEqual(x["status"],"WORKER_PROFILE_INVALID")
                self.assert_never_authority(x)
        for k,v in (
            ("requests_per_read",True),("requests_per_read",-1),
            ("other_account_requests_per_day","0"),
            ("cpu_ms_per_invocation","NaN"),("cpu_ms_per_invocation","inf"),
            ("peak_day_multiplier","0"),("peak_day_multiplier","101"),
            ("peak_day_multiplier",1),("requests_per_write",None)
        ):
            with self.subTest(k=k,v=v):
                p=profile()
                p[k]=v
                x=model_witness_cost(plan(),worker_profile=p)
                self.assertEqual(x["status"],"WORKER_PROFILE_INVALID")
                self.assert_never_authority(x)

    def test_zero_inbound_requests_is_not_a_valid_profile(self):
        x=model_witness_cost(plan(),worker_profile=profile(read=0,write=0))
        self.assertEqual(x["status"],"WORKER_PROFILE_INVALID")
        self.assert_never_authority(x)

    def test_hypothetical_low_partial_cost_never_trumps_free_quota_breach(self):
        x=model_witness_cost(plan(1000),hypothetical_quote(),
             worker_profile=profile(read=6,write=8))
        self.assertEqual(x["status"],"FREE_CAPACITY_EXCEEDED")
        self.assertIn("CF_WORKERS_FREE_INBOUND_REQUESTS_EXCEEDED",x["blockers"])
        self.assertIn("quoted_partial_brl",x)
        self.assert_never_authority(x)

    def test_synthetic_budget_below_cap_not_deploy_approval(self):
        x=model_witness_cost(plan(),hypothetical_quote(),worker_profile=profile())
        self.assertEqual(x["status"],"PARTIAL_MATH_NOT_CERTIFIED")
        self.assertFalse(x["quoted_partial_over_cap_math_only"])
        self.assertIs(x["budget_certified"],False)
        self.assertIs(x["spending_approved"],False)
        self.assertIs(x["worker_authorized"],False)

if __name__=="__main__":
    unittest.main()
