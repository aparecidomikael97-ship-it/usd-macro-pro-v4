"""Offline tests of provisional growth review: no payment, bill or deploy."""
import copy
import unittest

from atlasquant_aion_owner_provisional_cap_growth_policy_v1 import (
    SCHEMA, OWNER_FUNDED_INITIAL_CAP_CENTS, MIN_PAID_MONTHS,
    evaluate_owner_cap_growth_review,
)

CUSTOMER_A = "a" * 64
CUSTOMER_B = "b" * 64


def period(month, *, collected=30_000, cost=15_000, customers=None):
    return {
        "month": month,
        "customer_payment_received_cents": collected,
        "fully_loaded_costs_and_taxes_cents": cost,
        "payments_reconciled": True,
        "costs_and_taxes_reconciled": True,
        "paying_customer_keys": [CUSTOMER_A] if customers is None else customers,
    }


def example(**changes):
    defaults = dict(
        as_of="2026-10-08",
        paid_months=[period("2026-08"), period("2026-09")],
        declared_current_cap_cents=20_000,
        proposed_cap_cents=40_000,
        available_working_capital_cents=60_000,
    )
    defaults.update(changes)
    return evaluate_owner_cap_growth_review(**defaults)


class ProvisionalCapGrowthV1Tests(unittest.TestCase):
    def assert_blocked(self, result, code):
        self.assertEqual(result["status"], "NOT_ELIGIBLE_FOR_REVIEW", result)
        self.assertTrue(any(code in c for c in result["blockers"]), result)
        self.assertFalse(result["budget_increase_approved"])
        self.assertFalse(result["executes_action"])

    def test_two_paid_closed_months_can_propose_not_approve(self):
        r = example()
        self.assertEqual(r["schema"], SCHEMA)
        self.assertEqual(r["status"], "ELIGIBLE_FOR_OWNER_REVIEW_ONLY")
        self.assertEqual(r["blockers"], [])
        self.assertEqual(r["consecutive_paid_months_required"], 2)
        self.assertEqual(r["declared_positive_net_result_brl_cents"], 30_000)
        self.assertEqual(r["owner_funded_initial_cap_brl_cents"], 20_000)
        for key in (
            "budget_increase_approved", "paid_api_call_authorized",
            "subscription_purchase_authorized", "automatic_cap_escalation_enabled",
            "current_production_cap_changed", "executes_action",
            "receipts_and_costs_independently_verified",
            "customer_identity_independently_verified",
        ):
            self.assertFalse(r[key], key)
        self.assertTrue(r["requires_explicit_human_owner_approval"])
        self.assertTrue(r["requires_independent_reconciliation"])

    def test_current_owner_funded_cap_is_kept(self):
        self.assertEqual(OWNER_FUNDED_INITIAL_CAP_CENTS, 20_000)
        self.assertEqual(MIN_PAID_MONTHS, 2)
        self.assertEqual(example()["owner_funded_initial_cap_brl_cents"], 20_000)

    def test_no_clients_or_zero_months_does_not_qualify(self):
        self.assert_blocked(example(paid_months=[]), "EXACTLY_TWO_PAID_MONTHS_REQUIRED")

    def test_one_month_does_not_qualify(self):
        self.assert_blocked(example(paid_months=[period("2026-09")]),
                            "EXACTLY_TWO_PAID_MONTHS_REQUIRED")

    def test_three_months_are_not_an_implicit_whitelist(self):
        rows = [period("2026-07"), period("2026-08"), period("2026-09")]
        self.assert_blocked(example(paid_months=rows), "EXACTLY_TWO_PAID_MONTHS_REQUIRED")

    def test_unpaid_client_not_counted_as_income(self):
        rows = [period("2026-08", collected=0), period("2026-09")]
        self.assert_blocked(example(paid_months=rows), "SETTLED_RECEIPTS_REQUIRED")

    def test_future_or_current_open_month_is_not_accepted(self):
        self.assert_blocked(example(paid_months=[period("2026-09"), period("2026-10")]),
                            "TWO_MOST_RECENT_CLOSED_MONTHS_REQUIRED")

    def test_stale_months_do_not_qualify(self):
        self.assert_blocked(example(paid_months=[period("2026-06"), period("2026-07")]),
                            "TWO_MOST_RECENT_CLOSED_MONTHS_REQUIRED")

    def test_months_must_be_consecutive(self):
        self.assert_blocked(example(paid_months=[period("2026-07"), period("2026-09")]),
                            "PAID_MONTHS_MUST_BE_CONSECUTIVE")

    def test_duplicate_months_rejected(self):
        self.assert_blocked(example(paid_months=[period("2026-09"), period("2026-09")]),
                            "DUPLICATE_ACCOUNTING_MONTH")

    def test_negative_profit_not_sustainable(self):
        self.assert_blocked(example(paid_months=[period("2026-08", cost=40_000), period("2026-09")]),
                            "NONPOSITIVE_MONTHLY_NET_RESULT")

    def test_break_even_month_not_sustainable(self):
        self.assert_blocked(example(paid_months=[period("2026-08", cost=30_000), period("2026-09")]),
                            "NONPOSITIVE_MONTHLY_NET_RESULT")

    def test_taxes_and_full_costs_must_be_reviewed(self):
        rows = [period("2026-08"), period("2026-09")]
        rows[0]["costs_and_taxes_reconciled"] = False
        self.assert_blocked(example(paid_months=rows),
                            "PAYMENT_AND_COST_RECONCILIATION_REQUIRED")

    def test_unreconciled_receipts_block(self):
        rows = [period("2026-08"), period("2026-09")]
        rows[1]["payments_reconciled"] = False
        self.assert_blocked(example(paid_months=rows),
                            "PAYMENT_AND_COST_RECONCILIATION_REQUIRED")

    def test_different_clients_each_month_does_not_prove_retention(self):
        rows = [period("2026-08", customers=[CUSTOMER_A]),
                period("2026-09", customers=[CUSTOMER_B])]
        self.assert_blocked(example(paid_months=rows),
                            "NO_CONTINUING_PAYING_CUSTOMER")

    def test_opaque_customer_id_required(self):
        rows = [period("2026-08", customers=["Customer Name"]), period("2026-09")]
        self.assert_blocked(example(paid_months=rows),
                            "OPAQUE_PAYING_CUSTOMERS_REQUIRED")

    def test_duplicate_customer_records_rejected(self):
        rows = [period("2026-08", customers=[CUSTOMER_A,CUSTOMER_A]),period("2026-09")]
        self.assert_blocked(example(paid_months=rows), "DUPLICATE_PAYING_CUSTOMER")

    def test_cash_not_established(self):
        self.assert_blocked(example(available_working_capital_cents=None),
                            "WORKING_CAPITAL_UNVERIFIED")

    def test_cash_reserve_not_enough(self):
        self.assert_blocked(example(available_working_capital_cents=39_999),
                            "WORKING_CAPITAL_BELOW_PROPOSED_MONTHLY_CAP")

    def test_increment_above_one_step_needs_separate_review(self):
        self.assert_blocked(example(proposed_cap_cents=40_001), "PROPOSAL_STEP_TOO_LARGE")

    def test_no_automatic_decrease_or_equal_cap(self):
        self.assert_blocked(example(proposed_cap_cents=20_000),
                            "INCREASE_REQUIRED_FOR_GROWTH_REVIEW")

    def test_boolean_amounts_not_accepted_as_cents(self):
        self.assert_blocked(example(proposed_cap_cents=True), "PROPOSED_CAP_INVALID")

    def test_negative_or_missing_expenses_block(self):
        rows = [period("2026-08", cost=-1), period("2026-09")]
        self.assert_blocked(example(paid_months=rows), "FULL_COSTS_INVALID")

    def test_invalid_date_fail_closed(self):
        self.assert_blocked(example(as_of="2026-02-30"), "REVIEW_DATE_INVALID")

    def test_malformed_input_fail_closed(self):
        self.assert_blocked(example(paid_months=[{"month":"2026-08"}, period("2026-09")]),
                            "MONTH_EXACT_FIELDS_REQUIRED")

    def test_unknown_fields_are_rejected(self):
        rows = [period("2026-08"), period("2026-09")]
        rows[0]["secret"] = "do not transmit"
        self.assert_blocked(example(paid_months=rows), "MONTH_EXACT_FIELDS_REQUIRED")

    def test_non_integer_current_cap_fails_closed(self):
        self.assert_blocked(example(declared_current_cap_cents="R$ 200"),
                            "DECLARED_CURRENT_CAP_INVALID")

    def test_growing_again_remains_only_a_proposal(self):
        result = example(declared_current_cap_cents=40_000,
                         proposed_cap_cents=60_000)
        self.assertEqual(result["status"], "ELIGIBLE_FOR_OWNER_REVIEW_ONLY")
        self.assertFalse(result["current_production_cap_changed"])
        self.assertFalse(result["budget_increase_approved"])

    def test_no_customer_identity_disclosed_in_result(self):
        r = example()
        self.assertNotIn(CUSTOMER_A, repr(r))
        self.assertNotIn(CUSTOMER_B, repr(r))


if __name__ == "__main__":
    unittest.main()
