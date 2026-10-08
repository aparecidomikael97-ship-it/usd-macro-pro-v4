"""AION FinOps synthetic inventory, invoice and paid-provider dry-run checks.

All declared obligations, invoices and providers are fictitious. This suite
writes only the GitHub Actions RUNNER_TEMP SQLite file via upstream #1071.
No API credentials, billing accounts, payment providers or AION owner PC.
"""
import os
import sqlite3
import tempfile
from pathlib import Path
import unittest

from atlasquant_aion_owner_brl200_finops_ceiling_v1 import build_owner_monthly_budget
from atlasquant_aion_finops_ephemeral_sqlite_reservation_cas_v1 import EphemeralFinOpsReservationStore
from atlasquant_aion_finops_ci_inventory_reconciliation_provider_boundary_v1 import (
    SCHEMA, INVENTORY_READY, RECONCILED, DRY_READY, BLOCKED,
    build_declared_owner_inventory, reconcile_claimed_owner_invoices,
    dry_run_ci_provider_execution_boundary, boundary_policy,
    _safe_digest,
)

OWNER, MONTH, AS_OF = "owner-ci-example", "2026-10", "2026-10-08"

def subscription(oid="cloud-sub",provider="cloud-ci",amount=10000,cadence="MONTHLY",status="COMMITTED",source="OWNER_DECLARED"):
    return {
        "obligation_id":oid, "provider_id":provider, "owner_id":OWNER,
        "month":MONTH, "category":"hosting" if cadence!="FREE" else "other",
        "cadence":cadence, "declared_charge_brl_cents":amount,
        "evidence":source, "status":status,
    }

def invoice(row,amount=None):
    return {
        "invoice_id":"invoice-"+row["obligation_id"],
        "obligation_id":row["obligation_id"],"provider_id":row["provider_id"],
        "owner_id":row["owner_id"],"month":row["month"],
        "claimed_charge_brl_cents":row["declared_charge_brl_cents"] if amount is None else amount,
        "evidence":"USER_IMPORTED",
    }

def budget(amount=10000):
    return build_owner_monthly_budget([{
        "entry_id":"cost-ci","owner_id":OWNER,"month":MONTH,
        "category":"hosting","status":"COMMITTED","evidence":"ESTIMATED",
        "currency":"BRL","brl_cents":amount,"usd_micros":None,
    }],expected_month=MONTH,trusted_owner_id=OWNER,as_of=AS_OF)

class FinOpsInventoryReconciliationAndBoundaryV1Tests(unittest.TestCase):
    def setUp(self):
        self.entries=[subscription()]
        self.inv=self.inventory()
        self.rec=self.reconcile()
        self.tmp=tempfile.TemporaryDirectory(prefix="aion-finops-ci-boundary-",dir=os.environ["RUNNER_TEMP"])
        self.addCleanup(self.tmp.cleanup)
        self.store=EphemeralFinOpsReservationStore(
            str(Path(self.tmp.name)/"aion-finops-ci-provider-boundary.sqlite3")
        )
        self.budget=budget()
        self.start=self.store.initialize_month(self.budget)
        self.quote={
            "cost_type":"PAID_EXTERNAL","currency":"BRL",
            "brl_cents":1500,"usd_micros":None,
        }
        self.reservation=self.store.reserve(
            self.budget,reservation_id="ci-finops-call001",
            tenant_id="tenant-ci",provider_id="cloud-ci",quote=self.quote,
            fx_snapshot=None,as_of=AS_OF
        )
        self.request={
            "reservation_id":"ci-finops-call001","owner_id":OWNER,"month":MONTH,
            "tenant_id":"tenant-ci","provider_id":"cloud-ci",
            "quoted_brl_cents":1500,
            "inventory_digest":self.inv["inventory_digest"],
            "reconciliation_digest":self.rec["claimed_invoices_digest"],
            "budget_digest":self.budget["forecast_snapshot_digest"],
        }

    def inventory(self,obligations=None,providers=None,owner=OWNER,month=MONTH):
        return build_declared_owner_inventory(
            self.entries if obligations is None else obligations,
            expected_owner_id=owner,expected_month=month,
            expected_provider_ids=["cloud-ci"] if providers is None else providers,
        )

    def reconcile(self,inventory=None,invoices=None):
        return reconcile_claimed_owner_invoices(
            self.inv if inventory is None else inventory,
            [invoice(x) for x in self.entries] if invoices is None else invoices,
            expected_owner_id=OWNER,expected_month=MONTH,
        )

    def gate(self,request=None,inventory=None,reconciliation=None,store=None):
        return dry_run_ci_provider_execution_boundary(
            self.store if store is None else store,
            self.inv if inventory is None else inventory,
            self.rec if reconciliation is None else reconciliation,
            self.request if request is None else request,
        )

    def blocked(self,out,reason=None):
        self.assertEqual(out["state"],BLOCKED,out)
        if reason:
            self.assertIn(reason,out["blockers"],out)

    def test_positive_chain_only_simulates_no_paid_execution(self):
        self.assertEqual(self.inv["state"],INVENTORY_READY,self.inv)
        self.assertEqual(self.rec["state"],RECONCILED,self.rec)
        self.assertEqual(self.start["state"],"CI_MONTH_INITIALIZED_UNTRUSTED",self.start)
        self.assertEqual(self.reservation["state"],"CI_RESERVATION_RECORDED_UNTRUSTED",self.reservation)
        out=self.gate()
        self.assertEqual(out["state"],DRY_READY,out)
        self.assertTrue(out["request_digest"])
        self.assertFalse(out["paid_provider_call_authorized"])
        self.assertFalse(out["paid_call_executed"])

    def test_declared_monthly_total_is_100_reais(self):
        self.assertEqual(self.inv["monthly_total_brl_cents"],10000)
        self.assertEqual(self.inv["expected_provider_ids"],["cloud-ci"])

    def test_annual_120_reais_prorates_to_10_reais_monthly(self):
        inv=self.inventory([subscription(amount=12000,cadence="ANNUAL")])
        self.assertEqual(inv["state"],INVENTORY_READY)
        self.assertEqual(inv["monthly_total_brl_cents"],1000)

    def test_annual_1_cent_rounds_up_one_cent_monthly(self):
        inv=self.inventory([subscription(amount=1,cadence="ANNUAL")])
        self.assertEqual(inv["monthly_total_brl_cents"],1)

    def test_declared_more_than_200_reais_blocks(self):
        self.blocked(self.inventory([subscription(amount=20001)]),
                     "DECLARED_OWNER_HARD_CAP_EXCEEDED")

    def test_exactly_200_reais_is_allowed_as_unverified_inventory(self):
        self.assertEqual(self.inventory([subscription(amount=20000)])["state"],INVENTORY_READY)

    def test_no_obligations_cannot_fake_zero_cost(self):
        self.blocked(self.inventory([],providers=[]),"NO_DECLARED_OBLIGATIONS")

    def test_missing_provider_in_expected_set_blocks(self):
        self.blocked(self.inventory(providers=[]),"UNLISTED_PROVIDER:cloud-ci")

    def test_unlisted_extra_provider_blocks(self):
        self.blocked(self.inventory(providers=["cloud-ci","other-ci"]),
                     "DECLARED_PROVIDER_COVERAGE_INCOMPLETE")

    def test_duplicate_obligation_id_blocks_even_with_equal_content(self):
        self.blocked(self.inventory([self.entries[0],dict(self.entries[0])]),
                     "DUPLICATE_OBLIGATION_ID:cloud-sub")

    def test_missing_or_unknown_cost_blocks(self):
        for val in (None,-1,1.1,True):
            with self.subTest(value=val):
                self.blocked(self.inventory([subscription(amount=val)]),
                             "CHARGE_AMOUNT_UNKNOWN_OR_INVALID:0")

    def test_free_cadence_cannot_hide_paid_cost(self):
        self.blocked(self.inventory([subscription(amount=10,cadence="FREE")]),
                     "FREE_CADENCE_REQUIRES_ZERO:0")

    def test_nonfree_zero_requires_explicit_free_tier(self):
        self.blocked(self.inventory([subscription(amount=0,cadence="MONTHLY")]),
                     "PAID_CADENCE_REQUIRES_POSITIVE:0")

    def test_declared_free_tier_stays_unverified(self):
        inv=self.inventory([subscription(amount=0,cadence="FREE")])
        self.assertEqual(inv["state"],INVENTORY_READY)
        self.assertFalse(inv["all_real_providers_independently_discovered"])

    def test_wrong_owner_or_month_scope_blocks(self):
        self.blocked(self.inventory([dict(self.entries[0],owner_id="other-ci")]),
                     "OBLIGATION_SCOPE_MISMATCH:0")
        self.blocked(self.inventory([dict(self.entries[0],month="2026-11")]),
                     "OBLIGATION_SCOPE_MISMATCH:0")

    def test_unknown_category_evidence_and_status_blocks(self):
        for field,value in (
            ("category","unknown"),("evidence","INVOICE_VERIFIED"),
            ("status","PAID_AND_APPROVED"),
        ):
            with self.subTest(field=field):
                self.blocked(self.inventory([dict(self.entries[0],**{field:value})]))

    def test_injected_paid_approval_field_blocked(self):
        self.blocked(self.inventory([dict(self.entries[0],owner_approved=True)]),
                     "OBLIGATION_EXACT_FIELDS_REQUIRED:0")

    def test_malicious_unhashable_fields_fail_closed(self):
        for field in ("category","cadence","evidence","status","provider_id"):
            with self.subTest(field=field):
                self.blocked(self.inventory([dict(self.entries[0],**{field:["fake"]})]))

    def test_invoice_happy_path_is_still_untrusted(self):
        self.assertEqual(self.rec["state"],RECONCILED,self.rec)
        self.assertEqual(self.rec["claimed_total_raw_brl_cents"],10000)
        self.assertFalse(self.rec["real_provider_invoice_authenticated"])

    def test_missing_invoice_blocks(self):
        self.blocked(self.reconcile(invoices=[]),"INVOICE_COVERAGE_INCOMPLETE")

    def test_extra_invoice_blocks(self):
        rows=[invoice(self.entries[0]),dict(invoice(self.entries[0]),invoice_id="extra-invoice",obligation_id="other-ci")]
        self.blocked(self.reconcile(invoices=rows))

    def test_invoice_provider_substitution_blocks(self):
        inv=dict(invoice(self.entries[0]),provider_id="other-ci")
        self.blocked(self.reconcile(invoices=[inv]),"INVOICE_PROVIDER_MISMATCH:0")

    def test_invoice_dollar_amount_under_or_over_expected_blocks(self):
        for amount in (9000,10001):
            with self.subTest(value=amount):
                self.blocked(self.reconcile(invoices=[invoice(self.entries[0],amount)]),
                             "CLAIMED_INVOICE_VS_DECLARED_COST_DIVERGENCE:0")

    def test_invoice_scope_cross_owner_or_month_blocks(self):
        for k,v in (("owner_id","other-ci"),("month","2026-09")):
            with self.subTest(k=k):
                self.blocked(self.reconcile(invoices=[dict(invoice(self.entries[0]),**{k:v})]),
                             "INVOICE_SCOPE_INVALID:0")

    def test_invoice_duplicate_claims_block(self):
        self.blocked(self.reconcile(invoices=[
            invoice(self.entries[0]),invoice(self.entries[0])
        ]),"INVOICE_DUPLICATE_ID_OR_OBLIGATION:1")

    def test_fake_invoice_authenticity_claim_blocked(self):
        self.blocked(self.reconcile(invoices=[
            dict(invoice(self.entries[0]),bank_verified=True)
        ]),"INVOICE_EXACT_FIELDS_REQUIRED:0")

    def test_unknown_invoice_amount_does_not_mean_zero(self):
        self.blocked(self.reconcile(invoices=[
            dict(invoice(self.entries[0]),claimed_charge_brl_cents=None)
        ]),"INVOICE_AMOUNT_INVALID:0")

    def test_forged_invoice_document_source_does_not_gain_trust(self):
        self.blocked(self.reconcile(invoices=[
            dict(invoice(self.entries[0]),evidence="INDEPENDENTLY_VERIFIED")
        ]),"INVOICE_EVIDENCE_UNKNOWN:0")

    def test_inventory_hash_modification_detected_in_reconcile(self):
        inv=dict(self.inv,monthly_total_brl_cents=0)
        self.blocked(self.reconcile(inventory=inv),"INVENTORY_DIGEST_MISMATCH")

    def test_gate_missing_reservation_blocked(self):
        req=dict(self.request,reservation_id="ci-finops-nonexistent")
        self.blocked(self.gate(request=req),"ATOMIC_RESERVATION_MISSING_OR_MISMATCHED")

    def test_gate_wrong_tenant_provider_or_price_blocked(self):
        for k,v in (("tenant_id","tenant-other"),("provider_id","other-ci"),
                    ("quoted_brl_cents",1700)):
            with self.subTest(field=k):
                self.blocked(self.gate(request=dict(self.request,**{k:v})))

    def test_gate_wrong_owner_and_month_blocked(self):
        for k,v in (("owner_id","other-ci"),("month","2026-11")):
            with self.subTest(k=k):
                self.blocked(self.gate(request=dict(self.request,**{k:v})))

    def test_gate_budget_digest_mismatch_blocked(self):
        self.blocked(self.gate(request=dict(self.request,budget_digest="0"*64)),
                     "BOUNDARY_BUDGET_INVENTORY_BASELINE_MISMATCH")

    def test_gate_inventory_digest_mismatch_blocked(self):
        self.blocked(self.gate(request=dict(self.request,inventory_digest="0"*64)),
                     "BOUNDARY_INVENTORY_INVALID")

    def test_gate_reconciliation_digest_mismatch_blocked(self):
        self.blocked(self.gate(request=dict(self.request,reconciliation_digest="0"*64)),
                     "BOUNDARY_CLAIMED_RECON_INVALID")

    def test_gate_injected_owner_approval_is_forbidden(self):
        self.blocked(self.gate(request=dict(self.request,approve_paid_spend=True)),
                     "BOUNDARY_EXACT_FIELDS_REQUIRED")

    def test_gate_fake_verified_real_invoice_flag_blocks(self):
        rec=dict(self.rec,real_provider_invoice_authenticated=True)
        self.blocked(self.gate(reconciliation=rec),
                     "FALSE_EXTERNAL_FINANCIAL_TRUST_REQUIRED:real_provider_invoice_authenticated")

    def test_gate_inventory_monthly_baseline_mismatch_blocks(self):
        inv=self.inventory([subscription(amount=8000)])
        rec=self.reconcile(inventory=inv,invoices=[invoice(subscription(amount=8000))])
        self.assertEqual(rec["state"],RECONCILED,rec)
        req=dict(self.request,inventory_digest=inv["inventory_digest"],
                 reconciliation_digest=rec["claimed_invoices_digest"])
        self.blocked(self.gate(request=req,inventory=inv,reconciliation=rec),
                     "BOUNDARY_BUDGET_INVENTORY_BASELINE_MISMATCH")

    def test_gate_settled_reservation_does_not_simulate_unspent_call(self):
        result=self.store.settle(owner_id=OWNER,month=MONTH,
            reservation_id="ci-finops-call001",measured_actual_cents=1000)
        self.assertEqual(result["state"],"CI_SETTLEMENT_RECORDED_NO_BUDGET_RELEASE")
        self.blocked(self.gate(),"ATOMIC_RESERVATION_MISSING_OR_MISMATCHED")

    def test_gate_db_tamper_blocks(self):
        with sqlite3.connect(self.store.path) as conn:
            conn.execute("UPDATE month_state SET total_reserved_cents=0")
        self.blocked(self.gate(),"CI_STORE_ACCOUNTING_OR_SCOPE_ERROR")

    def test_gate_hostile_types_fail_closed(self):
        for key in ("reservation_id","tenant_id","provider_id","quoted_brl_cents"):
            with self.subTest(key=key):
                self.blocked(self.gate(request=dict(self.request,**{key:["spoof"]})))

    def test_gate_missing_evidence_document_blocks(self):
        self.blocked(self.gate(reconciliation=dict(self.rec,state=BLOCKED)),
                     "BOUNDARY_CLAIMED_RECON_INVALID")

    def test_policy_never_claims_real_invoices_or_calls(self):
        p=boundary_policy()
        self.assertTrue(p["synthetic_ci_inventory_only"])
        self.assertTrue(p["sqlite_ci_readback_only"])
        for key in (
            "all_provider_bills_discovered","real_invoices_authenticated",
            "real_subscription_inventory_complete",
            "real_provider_boundary_enforcing",
            "real_owner_approval_consumed",
            "production_payment_or_provider_call_allowed",
            "production_deploy_enabled","worker_activated",
        ):
            self.assertIs(p[key],False,key)

if __name__=="__main__":
    unittest.main()
