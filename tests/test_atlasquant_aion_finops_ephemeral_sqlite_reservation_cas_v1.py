"""Adversarial ephemeral SQLite owner BRL200 reservation contract tests.

This test fixture writes only inside GitHub-hosted RUNNER_TEMP on pull_request.
It does not use a REAL billing provider, real owner approval or production DB.
"""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from atlasquant_aion_finops_ephemeral_sqlite_reservation_cas_v1 import (
    SCHEMA, EphemeralFinOpsReservationStore, _check_ci_path,
    ephemeral_finops_policy,
)
from atlasquant_aion_owner_brl200_finops_ceiling_v1 import (
    build_owner_monthly_budget,
)

OWNER = "owner-ci-fixture"
MONTH = "2026-10"
AS_OF = "2026-10-08"
FX = {"rate_brl_per_usd":"5.000000",
      "observed_date":"2026-10-07","source":"OWNER_QUOTE"}

def entry(amount=12000, *, id="hosting-ci", owner=OWNER, month=MONTH):
    return {
        "entry_id":id, "owner_id":owner, "month":month,
        "category":"hosting", "status":"COMMITTED", "evidence":"ESTIMATED",
        "currency":"BRL", "brl_cents":amount, "usd_micros":None,
    }

def budget(amount=12000):
    return build_owner_monthly_budget(
        [entry(amount)],expected_month=MONTH,trusted_owner_id=OWNER,as_of=AS_OF,
    )

def brl_quote(amount):
    return {"cost_type":"PAID_EXTERNAL","currency":"BRL",
            "brl_cents":amount,"usd_micros":None}

def usd_quote(usd_micros):
    return {"cost_type":"PAID_EXTERNAL","currency":"USD",
            "brl_cents":None,"usd_micros":usd_micros}

class AIONFinOpsEphemeralSQLiteReservationsV1Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(
            prefix="aion-finops-ci-suite-",dir=os.environ["RUNNER_TEMP"]
        )
        self.addCleanup(self.temp.cleanup)
        self.path = str(Path(self.temp.name)/"aion-finops-ci-ledger.sqlite3")
        self.store = EphemeralFinOpsReservationStore(self.path)
        self.b = budget()

    def start(self, b=None):
        return self.store.initialize_month(self.b if b is None else b)

    def reserve(self, rid="ci-finops-req001", amount=1000, b=None,
                tenant_id="tenant-ci", provider_id="provider-ci", quote=None,
                fx=FX, as_of=AS_OF):
        return self.store.reserve(
            self.b if b is None else b, reservation_id=rid,
            tenant_id=tenant_id, provider_id=provider_id,
            quote=brl_quote(amount) if quote is None else quote,
            fx_snapshot=fx, as_of=as_of,
        )

    def report(self):
        return self.store.report(owner_id=OWNER,month=MONTH)

    def assert_block(self, response, reason=None):
        self.assertEqual(response["state"],"BLOCKED",response)
        if reason:
            self.assertIn(reason,response["blockers"])
        self.assertFalse(response["paid_call_authorized"])
        self.assertFalse(response["executes_action"])

    def test_ci_scratch_path_lies_within_runner_temp(self):
        self.assertTrue(str(Path(self.path).resolve()).startswith(
            str(Path(os.environ["RUNNER_TEMP"]).resolve())
        ))

    def test_guard_requires_explicit_ephemeral_flag(self):
        with patch.dict(os.environ, {"AION_FINOPS_CI_EPHEMERAL":"0"}):
            with self.assertRaises(PermissionError):
                EphemeralFinOpsReservationStore(self.path)

    def test_guard_requires_pull_request(self):
        with patch.dict(os.environ, {"GITHUB_EVENT_NAME":"push"}):
            with self.assertRaises(PermissionError):
                EphemeralFinOpsReservationStore(self.path)

    def test_guard_requires_github_actions(self):
        with patch.dict(os.environ, {"GITHUB_ACTIONS":"false"}):
            with self.assertRaises(PermissionError):
                EphemeralFinOpsReservationStore(self.path)

    def test_guard_rejects_path_outside_runner_temp(self):
        with self.assertRaises(PermissionError):
            _check_ci_path(str(Path(tempfile.gettempdir())/"outside.sqlite3"))

    def test_guard_rejects_filename_without_allowlisted_prefix(self):
        with self.assertRaises(PermissionError):
            _check_ci_path(str(Path(self.temp.name)/"untrusted.sqlite3"))

    def test_month_bootstrap_is_idempotent(self):
        a = self.start()
        c = self.start()
        self.assertEqual(a["state"],"CI_MONTH_INITIALIZED_UNTRUSTED")
        self.assertEqual(c["state"],"CI_MONTH_ALREADY_INITIALIZED")
        self.assertEqual(self.report()["baseline_cents"],12000)
        self.assertEqual(self.report()["revision"],1)

    def test_month_requires_authenticated_external_costs_before_production(self):
        self.start()
        p=self.report()
        self.assertEqual(p["remaining_cents"],8000)
        self.assertFalse(p["production_enforcement_active"])

    def test_month_budget_tamper_is_rejected(self):
        b=dict(self.b,forecast_brl_cents=0)
        self.assert_block(self.start(b),"BUDGET_SNAPSHOT_DIGEST_INVALID")

    def test_month_budget_unknown_invoices_are_not_zero(self):
        b=dict(self.b,unknown_other_bills_possible=False)
        self.assert_block(self.start(b),"BUDGET_UNKNOWN_BILLS_MUST_REMAIN_VISIBLE")

    def test_month_budget_fake_payment_enforcement_denied(self):
        b=dict(self.b,cap_is_real_payment_enforcement=True)
        self.assert_block(self.start(b),"UNTRUSTED_BUDGET_AUTHORITY:cap_is_real_payment_enforcement")

    def test_month_budget_is_frozen_no_silent_lowering(self):
        self.start()
        smaller=budget(1000)
        self.assert_block(self.start(smaller),"FROZEN_MONTH_BASELINE_MISMATCH")
        self.assertEqual(self.report()["baseline_cents"],12000)

    def test_paid_quote_cannot_reserve_without_month_init(self):
        self.assert_block(self.reserve(),"MONTH_NOT_INITIALIZED")

    def test_small_reservation_uses_sqlite_transaction(self):
        self.start()
        r=self.reserve()
        self.assertEqual(r["state"],"CI_RESERVATION_RECORDED_UNTRUSTED",r)
        self.assertFalse(r["paid_call_authorized"])
        snap=self.report()
        self.assertEqual(snap["baseline_cents"],12000)
        self.assertEqual(snap["reserved_cents"],1000)
        self.assertEqual(snap["remaining_cents"],7000)
        self.assertEqual(snap["revision"],2)

    def test_duplicate_identical_request_is_idempotent(self):
        self.start()
        self.reserve()
        again=self.reserve()
        self.assertEqual(again["state"],"CI_RESERVATION_REPLAY_IDENTICAL_UNTRUSTED")
        self.assertEqual(self.report()["reservation_count"],1)
        self.assertEqual(self.report()["reserved_cents"],1000)

    def test_duplicate_changed_price_is_denied(self):
        self.start()
        self.reserve()
        self.assert_block(self.reserve(amount=1200),"RESERVATION_ID_REUSE_OR_SCOPE_CONFLICT")

    def test_duplicate_cross_tenant_is_denied(self):
        self.start()
        self.reserve()
        self.assert_block(self.reserve(tenant_id="tenant-other"),"RESERVATION_ID_REUSE_OR_SCOPE_CONFLICT")

    def test_duplicate_cross_provider_is_denied(self):
        self.start()
        self.reserve()
        self.assert_block(self.reserve(provider_id="provider-other"),"RESERVATION_ID_REUSE_OR_SCOPE_CONFLICT")

    def test_reservation_baseline_mismatch_rejected(self):
        self.start()
        self.assert_block(self.reserve(b=budget(4000)),"FROZEN_MONTH_BASELINE_MISMATCH")

    def test_exact_remaining_balance_is_allowed_in_ci_only(self):
        self.start()
        result=self.reserve(amount=8000)
        self.assertEqual(result["state"],"CI_RESERVATION_RECORDED_UNTRUSTED")
        self.assertEqual(self.report()["remaining_cents"],0)

    def test_above_remaining_balance_rejected(self):
        self.start()
        self.assert_block(self.reserve(amount=8001),"ATOMIC_OWNER_HARD_CAP_EXCEEDED")
        self.assertEqual(self.report()["reserved_cents"],0)

    def test_two_serial_reservations_no_double_spend(self):
        self.start()
        self.reserve("ci-finops-req001",6000)
        self.assert_block(self.reserve("ci-finops-req002",4000),"ATOMIC_OWNER_HARD_CAP_EXCEEDED")
        self.assertEqual(self.report()["reserved_cents"],6000)

    def test_two_concurrent_reservations_only_one_can_win(self):
        self.start()
        def candidate(i):
            return self.reserve(rid=f"ci-finops-race{i:03}",amount=5000)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(candidate,(1,2)))
        self.assertEqual(sum(x["state"]=="CI_RESERVATION_RECORDED_UNTRUSTED"
                             for x in results),1,results)
        self.assertEqual(sum(x["state"]=="BLOCKED" for x in results),1)
        self.assertEqual(self.report()["reserved_cents"],5000)
        self.assertEqual(self.report()["remaining_cents"],3000)

    def test_five_concurrent_reservations_cannot_exceed_cap(self):
        self.start()
        with ThreadPoolExecutor(max_workers=5) as pool:
            results=list(pool.map(
                lambda i:self.reserve(rid=f"ci-finops-concurrent{i:03}",amount=3000),
                range(5)
            ))
        self.assertEqual(sum(x["state"]=="CI_RESERVATION_RECORDED_UNTRUSTED"
                             for x in results),2,results)
        self.assertEqual(self.report()["reserved_cents"],6000)
        self.assertGreaterEqual(self.report()["remaining_cents"],0)

    def test_reopen_sqlite_database_readback_same_reservation(self):
        self.start()
        self.reserve()
        fresh=EphemeralFinOpsReservationStore(self.path)
        self.assertEqual(fresh.report(owner_id=OWNER,month=MONTH)["reserved_cents"],1000)
        self.assertEqual(fresh.reserve(self.b,reservation_id="ci-finops-req001",
                        tenant_id="tenant-ci",provider_id="provider-ci",
                        quote=brl_quote(1000),fx_snapshot=FX,as_of=AS_OF)["state"],
                         "CI_RESERVATION_REPLAY_IDENTICAL_UNTRUSTED")

    def test_missing_reservation_cannot_be_settled(self):
        self.start()
        self.assert_block(self.store.settle(owner_id=OWNER,month=MONTH,
            reservation_id="ci-finops-nope",measured_actual_cents=5),
            "RESERVATION_SCOPE_OR_ID_INVALID")

    def test_settle_preserves_entire_liability_even_if_actual_lower(self):
        self.start()
        self.reserve()
        r=self.store.settle(owner_id=OWNER,month=MONTH,
                            reservation_id="ci-finops-req001",
                            measured_actual_cents=200)
        self.assertEqual(r["state"],"CI_SETTLEMENT_RECORDED_NO_BUDGET_RELEASE")
        self.assertEqual(self.report()["reserved_cents"],1000)
        self.assertEqual(self.report()["remaining_cents"],7000)

    def test_settle_identical_replay_and_conflicting_replay(self):
        self.start()
        self.reserve()
        self.store.settle(owner_id=OWNER,month=MONTH,
                          reservation_id="ci-finops-req001",measured_actual_cents=100)
        r=self.store.settle(owner_id=OWNER,month=MONTH,
                            reservation_id="ci-finops-req001",measured_actual_cents=100)
        self.assertEqual(r["state"],"CI_SETTLEMENT_REPLAY_IDENTICAL_UNTRUSTED")
        self.assert_block(self.store.settle(owner_id=OWNER,month=MONTH,
            reservation_id="ci-finops-req001",measured_actual_cents=101),
            "CONFLICTING_SETTLEMENT_REPLAY")

    def test_overage_settlement_rejected_without_reclaim(self):
        self.start()
        self.reserve()
        self.assert_block(self.store.settle(owner_id=OWNER,month=MONTH,
            reservation_id="ci-finops-req001",measured_actual_cents=1001),
            "ACTUAL_COST_EXCEEDS_RESERVED")
        self.assertEqual(self.report()["reserved_cents"],1000)

    def test_settlement_wrong_owner_rejected(self):
        self.start()
        self.reserve()
        self.assert_block(self.store.settle(owner_id="someone-else",month=MONTH,
            reservation_id="ci-finops-req001",measured_actual_cents=20),
            "MONTH_NOT_INITIALIZED")

    def test_database_liability_counter_tamper_blocks_reuse(self):
        self.start()
        self.reserve()
        with sqlite3.connect(self.path) as conn:
            conn.execute("UPDATE month_state SET total_reserved_cents=0")
        self.assert_block(self.reserve(rid="ci-finops-req002"),
                          "CI_DATABASE_OR_ACCOUNTING_ERROR")
        self.assert_block(self.report(),"CI_DATABASE_OR_ACCOUNTING_ERROR")

    def test_sqlite_database_corrupted_file_fails_closed(self):
        self.start()
        Path(self.path).write_bytes(b"invalid sqlite file")
        self.assert_block(self.report(),"CI_DATABASE_OR_ACCOUNTING_ERROR")

    def test_out_of_scope_and_bad_reservation_ids_denied(self):
        self.start()
        for rid in ("../escape","req","ci-finops-",""):
            with self.subTest(rid=rid):
                self.assert_block(self.reserve(rid=rid),"RESERVATION_ID_INVALID")

    def test_zero_or_unknown_paid_cost_denied(self):
        self.start()
        self.assert_block(self.reserve(amount=0),"RESERVATION_AMOUNT_INVALID")
        self.assert_block(self.reserve(quote={
            "cost_type":"PAID_EXTERNAL","currency":"BRL",
            "brl_cents":None,"usd_micros":None
        }),"PAID_PREFLIGHT_NOT_ELIGIBLE")

    def test_USD_quote_requires_fx_and_uses_buffer(self):
        self.start()
        r=self.reserve(rid="ci-finops-usd001",quote=usd_quote(1_000_000))
        self.assertEqual(r["state"],"CI_RESERVATION_RECORDED_UNTRUSTED",r)
        self.assertEqual(r["amount_cents"],550)
        self.assertEqual(self.report()["reserved_cents"],550)

    def test_USD_quote_stale_fx_denied(self):
        self.start()
        stale=dict(FX,observed_date="2026-09-10")
        self.assert_block(self.reserve(quote=usd_quote(1_000_000),fx=stale),
                          "PAID_PREFLIGHT_NOT_ELIGIBLE")

    def test_pure_zero_cost_work_does_not_get_paid_reservation(self):
        self.start()
        self.assert_block(self.reserve(quote={
            "cost_type":"LOCAL_ZERO_MARGINAL","currency":"BRL",
            "brl_cents":0,"usd_micros":None
        }),"PAID_PREFLIGHT_NOT_ELIGIBLE")

    def test_no_production_approval_in_policy_and_receipts(self):
        p=ephemeral_finops_policy()
        self.assertTrue(p["scratch_sqlite_written_on_ci_runner"])
        self.assertTrue(p["ephemeral_github_ci_only"])
        self.assertTrue(p["atomic_sqlite_begin_immediate"])
        for k in ("real_owner_billing_sources_authenticated",
                  "real_provider_integration_live",
                  "human_owner_approval_consumed","production_payment_enforcement",
                  "production_ledger_deployed","refund_or_released_funds_authorized",
                  "real_provider_bill_paid","automatic_paid_fallback",
                  "owner_workstation_accessed","worker_activated",
                  "deploy_executed"):
            self.assertIs(p[k],False,k)

if __name__=="__main__":
    unittest.main()
