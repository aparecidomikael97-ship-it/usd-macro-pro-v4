"""Independent offline budget negatives: no real FX, AWS or cloud billing."""
import ast
from pathlib import Path
import unittest
from atlasquant_aion_external_witness_cost_capacity_reference_v1 import (
    CAP_BRL, PLAN_FIELDS, QUOTE_FIELDS, NO_AUTHORITY, model_witness_cost,
)

def plan(tenants=1):
    return {
        "tenant_count": tenants,
        "reads_per_tenant_per_day": 12,
        "writes_per_tenant_per_day": 4,
        "do_requests_per_read": 2,
        "do_requests_per_write": 4,
        "do_rows_read_per_request": 2,
        "do_rows_written_per_write": 3,
        "do_duration_gb_s_per_request": "0.005",
        "do_storage_gb": "0.1",
        "s3_receipt_bytes": 2048,
        "s3_retention_days": 90,
    }

def hypothetical_quote():
    # Invented prices for arithmetic testing, NEVER a vendor quotation.
    return {
        "fx_brl_per_usd": "5.00",
        "existing_infra_brl_month": "50",
        "s3_storage_usd_per_gb_month": "0.10",
        "s3_put_usd_per_1000": "10.00",
        "s3_get_usd_per_1000": "1.00",
        "s3_list_usd_per_1000": "1.00",
        "s3_egress_usd_month": "5.00",
        "kms_usd_month": "2.00",
        "monitoring_usd_month": "2.00",
        "tax_percent": "10",
        "reserve_percent": "20",
    }

class WitnessBudgetReferenceTests(unittest.TestCase):
    def no_go(self, result):
        for k in NO_AUTHORITY:
            self.assertIs(result[k],False,k)
        self.assertIs(result["budget_certified"],False)
        self.assertIs(result["full_stack_monthly_cost_brl"],None)
        self.assertIs(result["cloudflare_free_account_usage_verified"],False)
        self.assertIs(result["workers_caller_quota_verified"],False)
        self.assertIs(result["aws_billing_verified"],False)

    def test_small_workload_free_capacity_only_not_quote(self):
        result=model_witness_cost(plan())
        self.assertEqual(result["status"],"COST_NOT_QUOTED")
        self.assertEqual(result["do_requests_per_day"],40)
        self.assertEqual(result["do_rows_read_per_day"],80)
        self.assertEqual(result["do_rows_written_per_day"],12)
        self.assertEqual(result["s3_put_per_month"],120)
        self.assertEqual(result["s3_get_per_month"],360)
        self.assertEqual(result["s3_versions_retained_steady_state"],360)
        self.no_go(result)

    def test_growth_to_hundred_tenants_still_requires_external_cost_quote(self):
        result=model_witness_cost(plan(tenants=100))
        self.assertEqual(result["do_requests_per_day"],4000)
        self.assertEqual(result["do_rows_written_per_day"],1200)
        self.assertEqual(result["status"],"COST_NOT_QUOTED")
        self.no_go(result)

    def test_hundred_tenants_writes_quota_is_not_extrapolated_to_one_thousand(self):
        result=model_witness_cost(plan(tenants=1000))
        self.assertEqual(result["do_requests_per_day"],40000)
        self.assertEqual(result["do_rows_written_per_day"],12000)
        self.assertEqual(result["status"],"COST_NOT_QUOTED")
        self.no_go(result)
        bigger=plan(tenants=1000)
        bigger["writes_per_tenant_per_day"]=80
        r=model_witness_cost(bigger)
        self.assertEqual(r["status"],"FREE_CAPACITY_EXCEEDED")
        self.assertIn("CF_FREE_DO_ROWS_WRITTEN_PER_DAY_EXCEEDED",r["blockers"])
        self.no_go(r)

    def test_daily_request_quota_separate_from_storage_write_quota(self):
        p=plan(tenants=1000)
        p["reads_per_tenant_per_day"]=100
        p["writes_per_tenant_per_day"]=1
        r=model_witness_cost(p)
        self.assertEqual(r["status"],"FREE_CAPACITY_EXCEEDED")
        self.assertIn("CF_FREE_DO_REQUESTS_PER_DAY_EXCEEDED",r["blockers"])
        self.no_go(r)

    def test_duration_or_storage_over_limit_refuses_free_fit(self):
        p=plan()
        p["do_duration_gb_s_per_request"]="1000"
        r=model_witness_cost(p)
        self.assertIn("CF_FREE_DURATION_EXCEEDED",r["blockers"])
        p=plan()
        p["do_storage_gb"]="5.01"
        r=model_witness_cost(p)
        self.assertIn("CF_FREE_STORAGE_EXCEEDED",r["blockers"])
        self.no_go(r)

    def test_missing_vendor_quotes_cannot_compute_full_cost(self):
        for quote in (None,{},{"fx_brl_per_usd":"5"},"approved",1,[]):
            with self.subTest(quote=quote):
                r=model_witness_cost(plan(),quote)
                self.assertEqual(r["status"],"COST_NOT_QUOTED")
                self.no_go(r)

    def test_hypothetical_complete_quote_is_math_only(self):
        r=model_witness_cost(plan(),hypothetical_quote())
        self.assertEqual(r["status"],"PARTIAL_MATH_NOT_CERTIFIED")
        self.assertIsInstance(r["quoted_partial_brl"],str)
        self.assertIn("PROVIDER_QUOTE_NOT_AUTHENTICATED",r["blockers"])
        self.assertIn("UNQUOTED_CF_CALLER_AND_ACCOUNT_WIDE_USAGE",r["blockers"])
        self.assertFalse(r["quoted_partial_over_cap_math_only"])
        self.no_go(r)

    def test_hypothetical_over_cap_is_not_capped_or_approved(self):
        q=hypothetical_quote()
        q["existing_infra_brl_month"]="220"
        r=model_witness_cost(plan(),q)
        self.assertTrue(r["quoted_partial_over_cap_math_only"])
        self.no_go(r)

    def test_invalid_fx_negative_nan_inf_zero_or_tax_blocks_quote(self):
        for name,bad in (
            ("fx_brl_per_usd","0"),("fx_brl_per_usd","NaN"),
            ("fx_brl_per_usd","Infinity"),("existing_infra_brl_month","-1"),
            ("tax_percent","101"),("reserve_percent","250"),
            ("fx_brl_per_usd",0),("s3_storage_usd_per_gb_month",None),
        ):
            with self.subTest(name=name,bad=bad):
                q=hypothetical_quote()
                q[name]=bad
                r=model_witness_cost(plan(),q)
                self.assertEqual(r["status"],"COST_NOT_QUOTED")
                self.no_go(r)

    def test_missing_or_invalid_plan_and_booleans_never_enable(self):
        for p in (None,[],{},{"tenant_count":1},"approved"):
            with self.subTest(value=p):
                self.no_go(model_witness_cost(p))
        for k,v in (
            ("tenant_count",True),("tenant_count",0),
            ("s3_receipt_bytes",True),("s3_retention_days",-1),
            ("reads_per_tenant_per_day",-1),
            ("do_duration_gb_s_per_request","NaN"),
        ):
            with self.subTest(k=k):
                p=plan()
                p[k]=v
                self.assertEqual(model_witness_cost(p)["status"],"INVALID_PLAN")
                self.no_go(model_witness_cost(p))

    def test_no_traffic_must_not_appear_free_or_billable(self):
        p=plan()
        p["reads_per_tenant_per_day"]=0
        p["writes_per_tenant_per_day"]=0
        r=model_witness_cost(p)
        self.assertEqual(r["status"],"INVALID_PLAN")
        self.no_go(r)

    def test_cost_reference_does_not_import_runtime_or_external_clients(self):
        root=Path(__file__).resolve().parent
        source=(root/"atlasquant_aion_external_witness_cost_capacity_reference_v1.py").read_text("utf-8")
        imports=set()
        for n in ast.walk(ast.parse(source)):
            if isinstance(n,ast.Import):
                imports.update(x.name.split(".")[0] for x in n.names)
            if isinstance(n,ast.ImportFrom) and n.module:
                imports.add(n.module.split(".")[0])
        self.assertFalse(imports & {
            "requests","boto3","botocore","httpx","socket","urllib",
            "os","subprocess","streamlit","cloudflare",
        })
        for name in ("atlasquant_aion_global_worker.py",
                     "atlasquant_aion_global_worker_source_gate_v1.py",
                     "atlasquant_aion_global_worker_readiness.py"):
            text=(root/name).read_text("utf-8")
            self.assertNotIn("model_witness_cost",text)

if __name__=="__main__":
    unittest.main()
