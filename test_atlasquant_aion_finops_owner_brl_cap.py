"""Adversarial tests for the owner-wide BRL envelope (no external I/O)."""
import unittest

from atlasquant_aion_finops_owner_brl_cap import (
    MONTHLY_CAP_CENTS, evaluate_owner_brl_cap,
)


def evidence(**changes):
    record = {
        "state": "VERIFIED",
        "scope": "OWNER_ALL_ENVIRONMENTS",
        "month": "2026-10",
        "currency": "BRL",
        "coverage_complete": True,
        "fx_reconciled": True,
        "non_overlapping_categories": True,
        "snapshot_age_minutes": 0,
        "settled_brl_cents": 1000,
        "committed_brl_cents": 2000,
        "reserved_brl_cents": 1000,
        "unbilled_estimate_brl_cents": 1000,
    }
    record.update(changes)
    return record


def request(**changes):
    record = {"month": "2026-10", "estimated_brl_cents": 50, "mode": "PAID"}
    record.update(changes)
    return record


class OwnerBrlCapTests(unittest.TestCase):
    def evaluate(self, ev=None, req=None):
        return evaluate_owner_brl_cap(
            evidence() if ev is None else ev,
            request() if req is None else req,
        )

    def test_cap_is_200_brl_exactly(self):
        self.assertEqual(MONTHLY_CAP_CENTS, 20000)

    def test_small_paid_quote_passes_as_precheck_only(self):
        result = self.evaluate()
        self.assertEqual(result["state"], "ALLOW_PRECHECK")
        self.assertFalse(result["grants_spending_authority"])
        self.assertFalse(result["executes_action"])

    def test_warning_at_70_percent(self):
        result = self.evaluate(
            evidence(settled_brl_cents=10000),
            request(estimated_brl_cents=0),
        )
        self.assertEqual(result["state"], "ALLOW_WITH_WARNING")

    def test_degrade_at_85_percent(self):
        result = self.evaluate(
            evidence(settled_brl_cents=13000),
            request(estimated_brl_cents=0),
        )
        self.assertEqual(result["state"], "DEGRADE_PAID")
        self.assertIn("LOW_COST_LOCAL_FIRST", result["warnings"])

    def test_exact_cap_blocks_new_paid_quote(self):
        result = self.evaluate(
            evidence(settled_brl_cents=15000),
            request(estimated_brl_cents=0),
        )
        self.assertEqual(result["state"], "BLOCK_PAID")

    def test_overspend_blocks(self):
        self.assertEqual(
            self.evaluate(request(estimated_brl_cents=25000))["state"],
            "BLOCK_PAID",
        )

    def test_unknown_provider_cost_blocks(self):
        result = self.evaluate(req=request(estimated_brl_cents=None))
        self.assertIn("REQUEST_COST_UNKNOWN_OR_INVALID", result["reasons"])

    def test_float_and_bool_money_block(self):
        for value in (True, 1.25, -1, "50", float("inf")):
            with self.subTest(value=value):
                self.assertEqual(
                    self.evaluate(req=request(estimated_brl_cents=value))["state"],
                    "BLOCK_PAID",
                )

    def test_provider_reconciliation_unknown_blocks(self):
        for changes in (
            {"coverage_complete": False},
            {"fx_reconciled": False},
            {"currency": "USD"},
            {"non_overlapping_categories": False},
            {"state": "DRAFT"},
            {"scope": "TENANT_ONLY"},
            {"snapshot_age_minutes": 61},
            {"snapshot_age_minutes": True},
            {"reserved_brl_cents": None},
            {"unbilled_estimate_brl_cents": -1},
        ):
            with self.subTest(changes=changes):
                self.assertEqual(self.evaluate(ev=evidence(**changes))["state"], "BLOCK_PAID")

    def test_monthly_boundary_fails_closed(self):
        self.assertIn(
            "MONTH_MISMATCH",
            self.evaluate(req=request(month="2026-11"))["reasons"],
        )
        self.assertEqual(
            self.evaluate(req=request(month="2026-13"))["state"], "BLOCK_PAID",
        )

    def test_local_zero_vendor_charge_does_not_need_paid_ledger(self):
        result = self.evaluate(
            ev={},
            req=request(mode="LOCAL_ZERO_VENDOR_CHARGE", estimated_brl_cents=0),
        )
        self.assertEqual(result["state"], "ALLOW_LOCAL_ONLY")
        self.assertFalse(result["grants_spending_authority"])

    def test_local_mode_cannot_hide_vendor_spend(self):
        result = self.evaluate(
            ev={},
            req=request(mode="LOCAL_ZERO_VENDOR_CHARGE", estimated_brl_cents=1),
        )
        self.assertEqual(result["state"], "BLOCK_PAID")

    def test_forged_owner_approval_does_not_override_cap(self):
        result = self.evaluate(
            ev=evidence(settled_brl_cents=15000, owner_approved=True),
            req=request(estimated_brl_cents=1, owner_approved=True),
        )
        self.assertEqual(result["state"], "BLOCK_PAID")

    def test_missing_snapshot_blocks(self):
        self.assertEqual(self.evaluate(ev={})["state"], "BLOCK_PAID")

    def test_no_auto_payment_or_provider_switch(self):
        for state in (
            self.evaluate(),
            self.evaluate(req=request(estimated_brl_cents=25000)),
        ):
            self.assertFalse(state["automatic_charge"])
            self.assertFalse(state["automatic_model_switch"])
            self.assertFalse(state["automatic_budget_change"])

    def test_input_is_not_mutated(self):
        ev = evidence()
        req = request()
        original_ev, original_req = ev.copy(), req.copy()
        self.evaluate(ev=ev, req=req)
        self.assertEqual(ev, original_ev)
        self.assertEqual(req, original_req)


if __name__ == "__main__":
    unittest.main()
