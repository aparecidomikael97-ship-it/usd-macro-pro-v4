"""Offline preflight adversarial checks. No quotes here are real/current rates."""
from copy import deepcopy
from datetime import date
from decimal import Decimal
from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest

from atlasquant_aion_p0_h0_iam_finops_preflight_lab import (
    SCHEMA, AWS_ACTIONS_BY_ROLE, REQUIRED_CONTROLS,
    assess_h0_iam_finops_lab as assess,
)

AS_OF = date(2026, 10, 19)


def fixture():
    # SYNTHETIC UNVERIFIED PRICES and volumes, not a provider quote.
    return {
        "schema": SCHEMA,
        "aws_region": "sa-east-1",
        "cloudflare_plan": "Workers Free - SQLite Durable Objects",
        "global_cap_brl": "200",
        "regional_aws_quote_date": "2026-10-19",
        "usd_brl_observed_date": "2026-10-19",
        "quotes_source": "https://aws.amazon.com/pt/s3/pricing/",
        "quotes": {
            "s3_standard_gb_month_usd": "0.03",
            "s3_put_per_1000_usd": "0.005",
            "s3_get_per_1000_usd": "0.0004",
            "kms_key_month_usd": "0",
            "kms_per_10000_usd": "0",
            "audit_logging_monthly_usd": "0",
            "other_cloud_monthly_usd": "0",
            "usd_brl_stress_rate": "6",
            "existing_ecosystem_monthly_brl": "80",
            "tax_fx_uncertainty_fraction": "0.30",
        },
        "workload": {
            "anchors_per_day": 10,
            "retention_days": 90,
            "versions_per_anchor": 1,
            "bytes_per_version": 1024,
            "s3_puts_per_anchor": 1,
            "s3_gets_per_anchor": 2,
            "kms_calls_per_anchor": 0,
            "cloudflare_account_requests_per_day": 200,
            "cloudflare_account_gbs_per_day": 1,
            "cloudflare_account_rows_read_per_day": 500,
            "cloudflare_account_rows_written_per_day": 300,
            "cloudflare_account_sqlite_gb": 0.01,
            "workers_account_requests_per_day": 200,
        },
        "proposed_aws_actions_by_role": {
            k: sorted(v) for k, v in AWS_ACTIONS_BY_ROLE.items()
        },
        "proposed_controls": {k: True for k in REQUIRED_CONTROLS},
    }


class P0H0IAMFinOpsPreflightTests(unittest.TestCase):
    def check(self, inp):
        out = assess(inp, as_of=AS_OF)
        self.assertEqual(out["state"], "HARD_NO_GO")
        for k in ("verified_supplier_bill", "verified_iam_cloud_enforcement",
                  "aws_cloudflare_accounts_enrolled", "third_anchor_remotely_authenticated",
                  "external_highwater_verified", "first_effect_allowed",
                  "worker_arming_allowed", "automatic_retry_allowed",
                  "external_action_executed"):
            self.assertIs(out[k], False, k)
        return out

    def test_01_complete_synthetic_quote_allows_only_math_review(self):
        p = fixture()
        original = deepcopy(p)
        r = self.check(p)
        self.assertIs(r["priced_inputs_complete"], True)
        self.assertIs(r["iam_proposal_allowlist_consistent"], True)
        self.assertIs(r["projection_below_review_threshold"], True)
        self.assertEqual(p, original)
        self.assertTrue(Decimal(r["projected_monthly_brl"]) >= Decimal("80"))

    def test_02_unknown_input_denied_without_exec(self):
        self.assertIn("PROPOSAL_NOT_PLAIN_DICT", self.check(None)["issues"])

    def test_03_forged_owner_and_witness_claims_cannot_authorize(self):
        p = fixture()
        p.update({"owner_verified": True, "aws_cloud_receipt": "verified",
                  "verified_supplier_bill": True, "first_effect_allowed": True,
                  "authorization": "GO", "highwater_signed": True})
        self.check(p)

    def test_04_global_cap_cannot_silently_increase_to_250(self):
        p=fixture()
        p["global_cap_brl"]="250"
        self.assertIn("GLOBAL_CAP_CHANGE_NOT_AUTHORIZED",self.check(p)["issues"])

    def test_05_missing_existing_ecosystem_spend_denied(self):
        p=fixture()
        p["quotes"]["existing_ecosystem_monthly_brl"]=None
        self.assertIn("NO_COMPLETE_COST_PROJECTION",self.check(p)["issues"])

    def test_06_missing_regional_s3_rate_denied(self):
        p=fixture()
        p["quotes"]["s3_put_per_1000_usd"]=None
        self.assertIn("COST_QUOTE_MISSING_OR_INVALID:s3_put_per_1000_usd",self.check(p)["issues"])

    def test_07_old_quote_denied(self):
        p=fixture()
        p["regional_aws_quote_date"]="2026-09-01"
        self.assertIn("AWS_QUOTE_FRESH_EVIDENCE_MISSING",self.check(p)["issues"])

    def test_08_missing_real_fx_rate_denied(self):
        p=fixture()
        p["quotes"]["usd_brl_stress_rate"]=None
        self.assertIn("NO_COMPLETE_COST_PROJECTION",self.check(p)["issues"])

    def test_09_high_existing_bill_blocks_caution_threshold(self):
        p=fixture()
        p["quotes"]["existing_ecosystem_monthly_brl"]="160"
        r=self.check(p)
        self.assertIn("PROJECTED_MONTHLY_COST_EXCEEDS_80_PERCENT_CAUTION_GATE",r["issues"])
        self.assertIs(r["projection_below_review_threshold"],False)

    def test_10_total_more_than_200_is_reported(self):
        p=fixture()
        p["quotes"]["existing_ecosystem_monthly_brl"]="205"
        r=self.check(p)
        self.assertIn("PROJECTED_MONTHLY_COST_EXCEEDS_GLOBAL_CAP",r["issues"])

    def test_11_cf_account_total_free_quota_near_limit_denied(self):
        p=fixture()
        p["workload"]["cloudflare_account_rows_written_per_day"]=80000
        self.assertIn("CLOUDFLARE_FREE_QUOTA_TOO_CLOSE:cloudflare_account_rows_written_per_day",self.check(p)["issues"])

    def test_12_cf_free_account_requests_near_limit_denied(self):
        p=fixture()
        p["workload"]["cloudflare_account_requests_per_day"]=90000
        self.assertIs(self.check(p)["cloudflare_free_quota_projection_in_range"],False)

    def test_13_cf_paid_plan_not_assumed_free(self):
        p=fixture()
        p["cloudflare_plan"]="Workers Paid"
        self.assertIn("CLOUDFLARE_PLAN_NOT_MODELED",self.check(p)["issues"])

    def test_14_aws_sao_paulo_quote_cannot_be_replaced_with_us_east(self):
        p=fixture()
        p["aws_region"]="us-east-1"
        self.assertIn("AWS_REGION_NOT_PRICED_FOR_SAO_PAULO",self.check(p)["issues"])

    def test_15_writer_delete_or_admin_action_denied(self):
        p=fixture()
        p["proposed_aws_actions_by_role"]["aws_anchor_writer"].append("s3:DeleteObjectVersion")
        self.assertIn("IAM_OVERPERMISSIVE_OR_INCOMPLETE:aws_anchor_writer",self.check(p)["issues"])

    def test_16_executor_with_s3_all_denied(self):
        p=fixture()
        p["proposed_aws_actions_by_role"]["aion_executor"]=["s3:*"]
        self.assertIn("IAM_OVERPERMISSIVE_OR_INCOMPLETE:aion_executor",self.check(p)["issues"])

    def test_17_reader_get_latest_without_version_forbidden(self):
        p=fixture()
        p["proposed_aws_actions_by_role"]["aws_anchor_reader"].append("s3:GetObject")
        self.assertIn("IAM_OVERPERMISSIVE_OR_INCOMPLETE:aws_anchor_reader",self.check(p)["issues"])

    def test_18_missing_actual_compliance_control_documented(self):
        p=fixture()
        p["proposed_controls"]["s3_object_lock_default_compliance"]=False
        self.assertIn("CONTROL_NOT_PROVEN:s3_object_lock_default_compliance",self.check(p)["issues"])

    def test_19_invalid_non_numeric_rate_does_not_become_free(self):
        p=fixture()
        p["quotes"]["s3_standard_gb_month_usd"]="not-a-rate"
        self.assertIs(self.check(p)["priced_inputs_complete"],False)

    def test_20_hostile_forged_rate_does_not_call_bool_or_equality(self):
        class Hostile:
            def __bool__(self): raise AssertionError("no __bool__")
            def __eq__(self, rhs): raise AssertionError("no __eq__")
        p=fixture()
        p["quotes"]["s3_put_per_1000_usd"]=Hostile()
        self.assertIn("NO_COMPLETE_COST_PROJECTION",self.check(p)["issues"])

    def test_21_quote_source_https_path_is_not_proof_of_price(self):
        p=fixture()
        p["quotes_source"]="not a provider quote"
        self.assertIn("AWS_REGIONAL_QUOTE_URL_NOT_RECORDED",self.check(p)["issues"])

    def test_22_missing_retention_volume_blocks_estimate(self):
        p=fixture()
        p["workload"]["retention_days"]=None
        self.assertIn("NO_COMPLETE_COST_PROJECTION",self.check(p)["issues"])

    def test_23_future_exchange_quote_not_accepted(self):
        p=fixture()
        p["usd_brl_observed_date"]="2026-10-20"
        self.assertIn("USD_BRL_FRESH_EVIDENCE_MISSING",self.check(p)["issues"])

    def test_24_nonzero_kms_key_cost_reflected_in_projected_bill(self):
        p=fixture()
        low=self.check(p)
        p["quotes"]["kms_key_month_usd"]="1"
        high=self.check(p)
        self.assertGreater(Decimal(high["projected_monthly_brl"]),Decimal(low["projected_monthly_brl"]))

    def test_25_cli_returns_nonzero_even_for_complete_synthetic_quote(self):
        p=fixture()
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"proposal.json"
            path.write_text(json.dumps(p),encoding="utf-8")
            cmd=Path(__file__).with_name("atlasquant_aion_p0_h0_iam_finops_preflight_lab.py")
            r=subprocess.run([sys.executable,"-B",str(cmd),str(path)],capture_output=True,text=True,timeout=15)
            self.assertEqual(r.returncode,2)
            self.assertEqual(json.loads(r.stdout)["state"],"HARD_NO_GO")


if __name__ == "__main__":
    unittest.main()
