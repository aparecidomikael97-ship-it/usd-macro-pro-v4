import unittest
from datetime import datetime, timezone

from atlasquant_risk_guardian import (
    RiskLimits,
    RiskState,
    can_apply_limit_change,
    daily_gain_lock,
    evaluate_risk_guard,
    limits_are_tighter_or_equal,
    validate_limits,
)


def limits(**overrides):
    base=dict(
        bankroll=1000.0,
        max_daily_loss=30.0,
        max_loss_per_trade=10.0,
        max_trades_per_day=5,
        max_consecutive_losses=2,
        max_open_exposure=20.0,
        max_daily_gains=2,
    )
    base.update(overrides)
    return RiskLimits(**base)


class AtlasQuantRiskGuardianTests(unittest.TestCase):
    def test_daily_gain_lock_helper_is_fail_closed_at_two(self):
        self.assertEqual(daily_gain_lock(0),(False,""))
        self.assertEqual(daily_gain_lock(1),(False,""))
        locked,reason=daily_gain_lock(2)
        self.assertTrue(locked)
        self.assertIn("preservar capital",reason)
        self.assertTrue(daily_gain_lock(3)[0])

    def test_daily_gain_lock_helper_rejects_invalid_counts(self):
        for gains,limit in ((-1,2),(0,0),(True,2),(1,False)):
            with self.subTest(gains=gains,limit=limit):
                with self.assertRaises(ValueError):
                    daily_gain_lock(gains,limit)

    def test_default_two_gain_rule_locks_third_trade(self):
        out=evaluate_risk_guard(
            limits(),
            RiskState(daily_pnl=40.0,trades_today=2,gains_today=2),
            requested_trade_risk=5.0,
            requested_exposure=5.0,
        )
        self.assertTrue(out.locked)
        self.assertIn("meta de gains do dia atingida; preservar capital",out.reasons)

    def test_one_gain_does_not_trigger_gain_lock_by_itself(self):
        out=evaluate_risk_guard(
            limits(),
            RiskState(daily_pnl=20.0,trades_today=1,gains_today=1),
            requested_trade_risk=5.0,
            requested_exposure=5.0,
        )
        self.assertFalse(out.locked)

    def test_gain_lock_applies_even_when_more_trade_slots_exist(self):
        out=evaluate_risk_guard(
            limits(max_trades_per_day=10),
            RiskState(daily_pnl=35.0,trades_today=2,gains_today=2),
        )
        self.assertTrue(out.locked)
        self.assertEqual(out.remaining_trade_slots,8)

    def test_daily_gain_limit_must_be_positive(self):
        with self.assertRaises(ValueError):
            validate_limits(limits(max_daily_gains=0))

    def test_lower_gain_cap_is_tighter_and_can_apply_immediately(self):
        current=limits(max_daily_gains=3)
        proposed=limits(max_daily_gains=2)
        self.assertTrue(limits_are_tighter_or_equal(current,proposed))
        self.assertTrue(can_apply_limit_change(
            current,proposed,
            relaxation_requested_at=None,
            now=datetime.now(timezone.utc),
        ))

    def test_raising_gain_cap_is_relaxation_not_immediate(self):
        current=limits(max_daily_gains=2)
        proposed=limits(max_daily_gains=3)
        self.assertFalse(limits_are_tighter_or_equal(current,proposed))
        self.assertFalse(can_apply_limit_change(
            current,proposed,
            relaxation_requested_at=None,
            now=datetime.now(timezone.utc),
        ))


if __name__=="__main__":
    unittest.main()
