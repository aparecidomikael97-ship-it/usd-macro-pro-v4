import unittest
from datetime import datetime, timedelta

from atlasquant_investment_ecosystem import (
    CompoundProjectionInput,
    IncomeProjectionInput,
    dividend_quality_snapshot,
    growth_watch_snapshot,
    project_compound,
    project_income_asset,
    required_capital_for_monthly_income,
)
from atlasquant_risk_guardian import (
    RiskLimits,
    RiskState,
    can_apply_limit_change,
    evaluate_risk_guard,
)


class InvestmentEcosystemTests(unittest.TestCase):
    def test_zero_return_projection_separates_contribution(self):
        result = project_compound(
            CompoundProjectionInput(1000, 100, 0, 1)
        )
        self.assertEqual(result["total_contributed"], 2200.0)
        self.assertEqual(result["projected_value"], 2200.0)
        self.assertEqual(result["projected_gain"], 0.0)
        self.assertIn("não são garantidos", result["notice"])

    def test_reinvested_income_builds_larger_portfolio_than_cash_mode(self):
        common = dict(
            initial_amount=10000,
            monthly_contribution=200,
            annual_income_yield_pct=8,
            annual_price_growth_pct=3,
            years=5,
        )
        reinvest = project_income_asset(
            IncomeProjectionInput(**common, reinvest_income=True)
        )
        cash = project_income_asset(
            IncomeProjectionInput(**common, reinvest_income=False)
        )
        self.assertGreater(
            reinvest["projected_portfolio_value"],
            cash["projected_portfolio_value"],
        )
        self.assertGreater(cash["projected_cash_income_paid"], 0)

    def test_income_goal_is_illustrative_not_guaranteed(self):
        result = required_capital_for_monthly_income(2000, 12)
        self.assertEqual(result["illustrative_required_capital"], 200000.0)
        self.assertIn("Simulação educacional", result["notice"])

    def test_dividend_snapshot_exposes_risks_without_probability_claim(self):
        result = dividend_quality_snapshot(
            asset_type="ação",
            payment_consistency_pct=50,
            payout_ratio_pct=130,
            net_debt_to_ebitda=4.2,
            earnings_or_ffo_growth_pct=-8,
            free_cash_flow_positive=False,
        )
        self.assertLess(result["dividend_quality_index"], 50)
        self.assertGreaterEqual(len(result["risk_flags"]), 4)
        self.assertIn("não representa probabilidade de pagamento", result["interpretation"].lower())

    def test_growth_watch_is_monitoring_not_buy_signal(self):
        result = growth_watch_snapshot(
            revenue_growth_pct=25,
            earnings_growth_pct=22,
            free_cash_flow_margin_pct=14,
            net_debt_to_ebitda=0.8,
            share_dilution_pct=0,
        )
        self.assertGreaterEqual(result["growth_quality_index"], 90)
        self.assertIn("não é previsão de preço", result["interpretation"])


class RiskGuardianTests(unittest.TestCase):
    def setUp(self):
        self.limits = RiskLimits(
            bankroll=1000,
            max_daily_loss=200,
            max_loss_per_trade=50,
            max_trades_per_day=5,
            max_consecutive_losses=3,
            max_open_exposure=500,
        )

    def test_daily_loss_locks_new_risk(self):
        decision = evaluate_risk_guard(
            self.limits,
            RiskState(daily_pnl=-200, trades_today=2),
            requested_trade_risk=10,
        )
        self.assertTrue(decision.locked)
        self.assertIn("limite de perda diária atingido", decision.reasons)
        self.assertEqual(decision.remaining_daily_loss_budget, 0)

    def test_consecutive_losses_lock(self):
        decision = evaluate_risk_guard(
            self.limits,
            RiskState(consecutive_losses=3),
        )
        self.assertTrue(decision.locked)
        self.assertIn("limite de perdas consecutivas atingido", decision.reasons)

    def test_requested_trade_risk_cannot_bypass_per_trade_limit(self):
        decision = evaluate_risk_guard(
            self.limits,
            RiskState(daily_pnl=-20),
            requested_trade_risk=80,
        )
        self.assertTrue(decision.locked)
        self.assertIn("risco solicitado por operação acima do limite", decision.reasons)

    def test_tightening_is_immediate_but_relaxing_requires_cooldown(self):
        tighter = RiskLimits(1000, 150, 40, 4, 2, 400)
        now = datetime(2026, 9, 20, 17, 0)
        self.assertTrue(
            can_apply_limit_change(
                self.limits,
                tighter,
                relaxation_requested_at=None,
                now=now,
            )
        )
        relaxed = RiskLimits(1000, 250, 60, 6, 4, 600)
        self.assertFalse(
            can_apply_limit_change(
                self.limits,
                relaxed,
                relaxation_requested_at=None,
                now=now,
            )
        )
        self.assertTrue(
            can_apply_limit_change(
                self.limits,
                relaxed,
                relaxation_requested_at=now - timedelta(hours=25),
                now=now,
            )
        )


if __name__ == "__main__":
    unittest.main()
