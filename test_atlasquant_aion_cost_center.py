import unittest

from atlasquant_aion_cost_center import (
    build_cost_center,
    compact_cost_summary,
    normalize_cost_evidence,
)


class AionCostCenterTests(unittest.TestCase):
    def item(
        self,
        *,
        category="ai_api",
        truth_state="CONFIRMED",
        amount=10,
        source="invoice",
        currency="USD",
        period="MONTHLY",
        label="Item",
    ):
        return {
            "id": "cost-1",
            "label": label,
            "category": category,
            "truth_state": truth_state,
            "amount": amount,
            "source": source,
            "currency": currency,
            "period": period,
            "observed_at": "2026-09-29T00:20:00+00:00",
        }

    def test_confirmed_cost_requires_source(self):
        row = normalize_cost_evidence(self.item(source=""))
        self.assertFalse(row["usable"])
        self.assertIn("CONFIRMED_SOURCE_REQUIRED", row["reasons"])
        self.assertIsNone(row["amount_usd_monthly"])

    def test_estimate_stays_separate_from_confirmed_spend(self):
        center = build_cost_center([
            self.item(amount=20, truth_state="CONFIRMED"),
            self.item(amount=5, truth_state="ESTIMATED", source="pricing-page"),
        ])
        self.assertEqual(center["state"], "PARTIAL")
        self.assertEqual(center["confirmed_monthly_usd"], 20.0)
        self.assertEqual(center["estimated_monthly_usd"], 5.0)
        self.assertEqual(center["projected_monthly_usd"], 25.0)
        self.assertTrue(center["estimate_is_not_spend"])


    def test_zero_valued_estimate_still_keeps_state_partial(self):
        center = build_cost_center([
            self.item(amount=0, truth_state="ESTIMATED", source="pricing-page"),
        ])
        self.assertEqual(center["state"], "PARTIAL")
        self.assertEqual(center["estimated_items"], 1)
        self.assertEqual(center["estimated_monthly_usd"], 0.0)

    def test_all_confirmed_usd_monthly_evidence_can_be_confirmed(self):
        center = build_cost_center([
            self.item(category="infrastructure", amount=12),
            self.item(category="market_data", amount=0),
        ])
        self.assertEqual(center["state"], "CONFIRMED")
        self.assertEqual(center["confirmed_monthly_usd"], 12.0)
        self.assertEqual(center["estimated_monthly_usd"], 0.0)

    def test_unknown_truth_is_rejected(self):
        row = normalize_cost_evidence(self.item(truth_state="UNKNOWN"))
        self.assertFalse(row["usable"])
        self.assertIn("TRUTH_UNKNOWN", row["reasons"])

    def test_negative_nan_inf_bool_and_text_amounts_are_rejected(self):
        for amount in (-1, float("nan"), float("inf"), True, "bad"):
            with self.subTest(amount=amount):
                row = normalize_cost_evidence(self.item(amount=amount))
                self.assertFalse(row["usable"])
                self.assertIn("INVALID_AMOUNT", row["reasons"])

    def test_unsupported_currency_is_not_silently_converted(self):
        row = normalize_cost_evidence(self.item(currency="BRL"))
        self.assertFalse(row["usable"])
        self.assertIn("UNSUPPORTED_CURRENCY", row["reasons"])
        self.assertEqual(row["currency"], "BRL")
        self.assertIsNone(row["amount_usd_monthly"])

    def test_unsupported_period_is_not_silently_annualized(self):
        row = normalize_cost_evidence(self.item(period="ANNUAL"))
        self.assertFalse(row["usable"])
        self.assertIn("UNSUPPORTED_PERIOD", row["reasons"])

    def test_empty_center_is_unknown(self):
        center = build_cost_center([])
        self.assertEqual(center["state"], "UNKNOWN")
        self.assertEqual(center["confirmed_monthly_usd"], 0.0)
        self.assertFalse(center["executes_action"])

    def test_cost_per_user_requires_confirmed_positive_user_count(self):
        evidence = [self.item(amount=20)]
        missing = build_cost_center(
            evidence,
            active_users=2,
            active_users_confirmed=False,
        )
        self.assertIsNone(missing["confirmed_cost_per_user_usd"])

        zero = build_cost_center(
            evidence,
            active_users=0,
            active_users_confirmed=True,
        )
        self.assertIsNone(zero["confirmed_cost_per_user_usd"])

        confirmed = build_cost_center(
            evidence,
            active_users=2,
            active_users_confirmed=True,
        )
        self.assertEqual(confirmed["confirmed_cost_per_user_usd"], 10.0)

    def test_category_totals_keep_confirmed_and_estimated_separate(self):
        center = build_cost_center([
            self.item(category="voice_tts", amount=8, truth_state="CONFIRMED"),
            self.item(category="voice_tts", amount=3, truth_state="ESTIMATED"),
        ])
        bucket = center["by_category"]["voice_tts"]
        self.assertEqual(bucket["confirmed_usd"], 8.0)
        self.assertEqual(bucket["estimated_usd"], 3.0)
        self.assertEqual(bucket["usable_items"], 2)

    def test_rejected_item_makes_center_partial_when_other_evidence_is_valid(self):
        center = build_cost_center([
            self.item(amount=10),
            self.item(amount=-5, label="broken"),
        ])
        self.assertEqual(center["state"], "PARTIAL")
        self.assertEqual(center["rejected_items"], 1)
        self.assertEqual(center["confirmed_monthly_usd"], 10.0)

    def test_compact_summary_never_claims_billing_verification(self):
        center = build_cost_center([self.item(amount=15)])
        summary = compact_cost_summary(center)
        self.assertEqual(summary["state"], "CONFIRMED")
        self.assertEqual(summary["confirmed_monthly_usd"], 15.0)
        self.assertFalse(summary["billing_verified"])
        self.assertFalse(summary["executes_action"])

    def test_no_automatic_financial_or_trading_action(self):
        center = build_cost_center([self.item(amount=1)])
        self.assertFalse(center["automatic_charge"])
        self.assertFalse(center["automatic_subscription"])
        self.assertFalse(center["automatic_upgrade"])
        self.assertFalse(center["automatic_paid_fallback"])
        self.assertFalse(center["real_trading_enabled"])


if __name__ == "__main__":
    unittest.main()
