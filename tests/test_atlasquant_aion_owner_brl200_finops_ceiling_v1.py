"""AION BRL 200 monthly ceiling contract regression tests — no real billing."""
import copy
import unittest
from atlasquant_aion_owner_brl200_finops_ceiling_v1 import (
    SCHEMA, HARD_CAP_CENTS, SOFT_CAP_CENTS, CRITICAL_CAP_CENTS,
    build_owner_monthly_budget, preflight_owner_paid_request,
    minimum_customer_monthly_margin, owner_budget_policy,
)

OWNER = "HUMAN_OWNER_FIXTURE"
MONTH = "2026-10"
AS_OF = "2026-10-08"
FX = {"rate_brl_per_usd": "5.000000",
      "observed_date": "2026-10-07", "source": "OWNER_QUOTE"}

def row(entry_id="hosting", cost=9000, *, category="hosting",
        currency="BRL", usd=None, evidence="CONFIRMED",
        status="COMMITTED", owner=OWNER, month=MONTH):
    return {
        "entry_id": entry_id, "owner_id": owner, "month": month,
        "category": category, "status": status, "evidence": evidence,
        "currency": currency, "brl_cents": cost if currency == "BRL" else None,
        "usd_micros": usd if currency == "USD" else None,
    }

def snapshot(entries=None, **kwargs):
    return build_owner_monthly_budget(
        [row()] if entries is None else entries,
        expected_month=kwargs.pop("month", MONTH),
        trusted_owner_id=kwargs.pop("owner", OWNER),
        as_of=kwargs.pop("as_of", AS_OF),
        fx_snapshot=kwargs.pop("fx", FX),
        **kwargs,
    )

def quote(cost=100, cost_type="PAID_EXTERNAL", currency="BRL", usd=None):
    return {"cost_type":cost_type, "currency":currency,
            "brl_cents":cost if currency=="BRL" else None,
            "usd_micros":usd if currency=="USD" else None}

def admission(b=None, q=None, **kwargs):
    return preflight_owner_paid_request(snapshot() if b is None else b,
        quote=quote() if q is None else q, fx_snapshot=kwargs.pop("fx", FX),
        as_of=kwargs.pop("as_of", AS_OF), **kwargs)

class OwnerBRL200FinOpsCeilingV1Tests(unittest.TestCase):
    def assert_block(self, r, fragment=None):
        self.assertEqual(r["state"],"BLOCKED",r)
        if fragment: self.assertTrue(any(fragment in x for x in r["blockers"]),r)

    def test_approved_goal_is_fixed_two_hundred_reais(self):
        policy=owner_budget_policy()
        self.assertEqual(HARD_CAP_CENTS,20000)
        self.assertEqual(SOFT_CAP_CENTS,14000)
        self.assertEqual(CRITICAL_CAP_CENTS,18000)
        self.assertEqual(policy["currency"],"BRL")
        self.assertTrue(policy["monthly_owner_operating_costs_only"])

    def test_monthly_projection_inside_target_is_provisional_only(self):
        r=snapshot()
        self.assertEqual(r["state"],"WITHIN_TARGET_PROVISIONAL")
        self.assertEqual(r["forecast_brl_cents"],9000)
        self.assertEqual(r["headroom_brl_cents"],11000)
        self.assertFalse(r["cap_is_real_payment_enforcement"])
        self.assertFalse(r["input_costs_independently_reconciled"])

    def test_soft_limit_degrades_before_hard_cap(self):
        self.assertEqual(snapshot([row(cost=14000)])["state"],"DEGRADE")

    def test_critical_limit_warns_before_hard_cap(self):
        self.assertEqual(snapshot([row(cost=18000)])["state"],"CRITICAL")

    def test_exact_hard_cap_does_not_authorize_more_paid_spend(self):
        b=snapshot([row(cost=20000)])
        self.assertEqual(b["state"],"CRITICAL")
        self.assertEqual(b["headroom_brl_cents"],0)
        self.assertEqual(admission(b)["decision"],"BLOCK_PAID")

    def test_above_hard_cap_blocks(self):
        self.assert_block(snapshot([row(cost=20001)]),"OWNER_MONTHLY_CAP_EXCEEDED")

    def test_multiple_categories_count_together(self):
        r=snapshot([
            row(cost=8000),
            row("api",5000,category="ai_api",status="RESERVED",evidence="ESTIMATED"),
            row("db",3000,category="database",status="SETTLED"),
        ])
        self.assertEqual(r["forecast_brl_cents"],16000)
        self.assertEqual(r["state"],"DEGRADE")
        self.assertEqual(r["entries_count"],3)

    def test_exact_duplicate_id_counts_once(self):
        r=snapshot([row(),row()])
        self.assertEqual(r["forecast_brl_cents"],9000)
        self.assertEqual(r["entries_count"],1)

    def test_conflicting_duplicate_id_fails_closed(self):
        self.assert_block(snapshot([row(),row(cost=8000)]),"CONFLICTING_OBLIGATION_ID")

    def test_cross_owner_record_rejected(self):
        self.assert_block(snapshot([row(owner="OTHER_OWNER")]),"OWNER_SCOPE_MISMATCH")

    def test_cross_month_record_rejected(self):
        self.assert_block(snapshot([row(month="2026-11")]),"ENTRY_MONTH_MISMATCH")

    def test_invalid_accounting_month_rejected(self):
        self.assert_block(snapshot(month="2026-13"),"MONTH_INVALID")

    def test_as_of_from_other_month_rejected(self):
        self.assert_block(snapshot(as_of="2026-09-30"),"ACCOUNTING_MONTH_MISMATCH")

    def test_invalid_calendar_date_rejected(self):
        self.assert_block(snapshot(as_of="2026-10-35"),"AS_OF_DATE_INVALID")

    def test_blank_owner_rejected(self):
        self.assert_block(snapshot(owner=""),"OWNER_ID_REQUIRED")

    def test_missing_amount_evidence_does_not_mean_zero(self):
        self.assert_block(snapshot([row(evidence="UNKNOWN")]),"AMOUNT_EVIDENCE_MISSING")

    def test_unrecognized_category_rejected(self):
        self.assert_block(snapshot([row(category="missing_external_provider")]),"ENTRY_CATEGORY_UNRECOGNIZED")

    def test_invalid_commitment_state_rejected(self):
        self.assert_block(snapshot([row(status="CANCELED_BUT_BILLED")]),"ENTRY_STATUS_UNKNOWN")

    def test_negative_amount_rejected(self):
        self.assert_block(snapshot([row(cost=-1)]),"BRL_AMOUNT_INVALID")

    def test_fractional_amount_not_accepted(self):
        self.assert_block(snapshot([row(cost=7.25)]),"BRL_AMOUNT_INVALID")

    def test_bool_amount_not_accepted(self):
        self.assert_block(snapshot([row(cost=True)]),"BRL_AMOUNT_INVALID")

    def test_brl_entry_cannot_carry_usd_amount(self):
        r=row()
        r["usd_micros"]=2
        self.assert_block(snapshot([r]),"BRL_AMOUNT_INVALID")

    def test_extra_scope_or_approval_field_rejected(self):
        r=row()
        r["auto_approve"]=True
        self.assert_block(snapshot([r]),"ENTRY_EXACT_FIELDS_REQUIRED")

    def test_missing_required_row_field_rejected(self):
        r=row()
        del r["owner_id"]
        self.assert_block(snapshot([r]),"ENTRY_EXACT_FIELDS_REQUIRED")

    def test_usd_cost_converts_to_brl_with_10_pct_buffer_and_roundup(self):
        r=snapshot([row("api",currency="USD",usd=1_000_000,category="ai_api")])
        self.assertEqual(r["forecast_brl_cents"],550)
        self.assertEqual(r["state"],"WITHIN_TARGET_PROVISIONAL")

    def test_usd_microcent_rounds_up_to_a_cent(self):
        r=snapshot([row("micro",currency="USD",usd=1,category="ai_api")])
        self.assertEqual(r["forecast_brl_cents"],1)

    def test_usd_quote_needs_fx_evidence(self):
        r=snapshot([row("api",currency="USD",usd=100_000,category="ai_api")],fx=None)
        self.assert_block(r,"USD_FX_SNAPSHOT_REQUIRED")

    def test_stale_fx_blocks(self):
        fx=dict(FX,observed_date="2026-10-01")
        self.assert_block(snapshot([row("api",currency="USD",usd=1_000_000,category="ai_api")],fx=fx),"FX_RATE_STALE_OR_FUTURE")

    def test_future_fx_blocks(self):
        fx=dict(FX,observed_date="2026-10-09")
        self.assert_block(snapshot([row("api",currency="USD",usd=1_000_000,category="ai_api")],fx=fx),"FX_RATE_STALE_OR_FUTURE")

    def test_fx_invalid_rate_blocks(self):
        fx=dict(FX,rate_brl_per_usd="NaN")
        self.assert_block(snapshot([row("api",currency="USD",usd=1_000_000,category="ai_api")],fx=fx),"FX_RATE_INVALID")

    def test_fx_source_cannot_be_claimed_live_unverified(self):
        fx=dict(FX,source="VERIFIED_LIVE")
        self.assert_block(snapshot([row("api",currency="USD",usd=1_000_000,category="ai_api")],fx=fx),"FX_SOURCE_NOT_ESTABLISHED")

    def test_fx_snapshot_extra_fields_block(self):
        fx=dict(FX,automatically_trusted=True)
        self.assert_block(snapshot([row("api",currency="USD",usd=1_000_000,category="ai_api")],fx=fx),"FX_SNAPSHOT_EXACT_FIELDS_REQUIRED")

    def test_valid_paid_quote_inside_cap_requires_separate_approval(self):
        r=admission()
        self.assertEqual(r["decision"],"REQUIRES_SEPARATE_OWNER_APPROVAL")
        self.assertFalse(r["external_call_authorized"])
        self.assertEqual(r["approved_paid_spend_brl_cents"],0)

    def test_paid_quote_over_cap_blocked(self):
        b=snapshot([row(cost=19900)])
        r=admission(b,quote(200))
        self.assertEqual(r["decision"],"BLOCK_PAID")
        self.assertIn("PROJECTED_OWNER_CAP_EXCEEDED",r["blockers"])

    def test_local_zero_marginal_work_does_not_get_paid_authority(self):
        r=admission(q=quote(0,"LOCAL_ZERO_MARGINAL"))
        self.assertEqual(r["decision"],"LOCAL_ONLY_ADVISORY")
        self.assertFalse(r["external_call_authorized"])

    def test_fake_free_work_with_cost_cannot_bypass(self):
        r=admission(q=quote(10,"LOCAL_ZERO_MARGINAL"))
        self.assertEqual(r["decision"],"BLOCK_PAID")
        self.assertIn("LOCAL_ZERO_QUOTE_MUST_BE_ZERO",r["blockers"])

    def test_usd_paid_quote_exactly_bridges_cap(self):
        b=snapshot([row(cost=19450)])
        r=admission(b,quote(currency="USD",usd=1_000_000),fx=FX)
        self.assertEqual(r["decision"],"REQUIRES_SEPARATE_OWNER_APPROVAL")

    def test_usd_paid_quote_exceeds_cap(self):
        b=snapshot([row(cost=19500)])
        r=admission(b,quote(currency="USD",usd=1_000_000),fx=FX)
        self.assertEqual(r["decision"],"BLOCK_PAID")

    def test_unknown_quote_has_no_approval(self):
        r=admission(q={"cost_type":"PAID_EXTERNAL","currency":"USD",
                       "brl_cents":None,"usd_micros":None})
        self.assertEqual(r["decision"],"BLOCK_PAID")

    def test_extra_quote_field_cannot_self_authorize(self):
        r=admission(q=dict(quote(), owner_approved=True))
        self.assertEqual(r["decision"],"BLOCK_PAID")

    def test_invalid_or_foreign_budget_does_not_grant_paid_work(self):
        for b in ({},dict(snapshot(),state="BLOCKED"),
                  dict(snapshot(),hard_cap_brl_cents=10**8)):
            with self.subTest(b=b):
                self.assertEqual(admission(b)["decision"],"BLOCK_PAID")

    def test_paid_call_denied_when_budget_total_tampered(self):
        b=dict(snapshot(),forecast_brl_cents=0)
        a=admission(b)
        self.assertEqual(a["decision"],"BLOCK_PAID")
        self.assertIn("BUDGET_SNAPSHOT_TAMPERED",a["blockers"])

    def test_paid_call_denied_when_snapshot_hash_missing(self):
        b=dict(snapshot())
        del b["forecast_snapshot_digest"]
        a=admission(b)
        self.assertEqual(a["decision"],"BLOCK_PAID")
        self.assertIn("BUDGET_SNAPSHOT_TAMPERED",a["blockers"])

    def test_malicious_unhashable_status_category_and_evidence_fail_closed(self):
        for field in ("status","category","evidence"):
            item=row()
            item[field]=["forged"]
            r=snapshot([item])
            self.assertEqual(r["state"],"BLOCKED",field)

    def test_paid_quote_unhashable_cost_type_fails_closed(self):
        q=quote()
        q["cost_type"]=["PAID_EXTERNAL"]
        self.assertEqual(admission(q=q)["decision"],"BLOCK_PAID")

    def test_customer_positive_margin_is_estimate_not_proof(self):
        r=minimum_customer_monthly_margin(revenue_brl_cents=10000,operating_cost_brl_cents=7500)
        self.assertEqual(r["state"],"ESTIMATED_POSITIVE_MARGIN")
        self.assertEqual(r["gross_margin_brl_cents"],2500)
        self.assertFalse(r["customer_payment_received"])

    def test_customer_nonpositive_margin_warns(self):
        r=minimum_customer_monthly_margin(revenue_brl_cents=3000,operating_cost_brl_cents=5000)
        self.assertEqual(r["state"],"ESTIMATED_NONPOSITIVE_MARGIN")

    def test_customer_unknown_cost_blocks(self):
        r=minimum_customer_monthly_margin(revenue_brl_cents=3000,operating_cost_brl_cents=None)
        self.assertEqual(r["state"],"BLOCKED")

    def test_client_margin_does_not_offset_owner_budget(self):
        result=snapshot([row(cost=20100)])
        profit=minimum_customer_monthly_margin(revenue_brl_cents=1_000_000,operating_cost_brl_cents=1000)
        self.assertEqual(profit["state"],"ESTIMATED_POSITIVE_MARGIN")
        self.assertEqual(result["state"],"BLOCKED")

    def test_module_policy_explicitly_not_real_payment_guard(self):
        p=owner_budget_policy()
        for f in ("production_enforcement_active","real_billing_sources_connected",
                  "automatic_provider_purchase","automatic_paid_fallback",
                  "automatic_customer_charge","merges_or_deploys"):
            self.assertIs(p[f],False,f)

if __name__=="__main__":
    unittest.main()
