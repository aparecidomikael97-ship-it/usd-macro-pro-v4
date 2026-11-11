"""Synthetic D1/W1 bilateral agreement tests. Never measure market accuracy."""
from dataclasses import replace
from datetime import timedelta
import unittest

from atlasquant_fx_universe import OFFICIAL_PAIRS, split_pair
from atlasquant_trader_fx28_bilateral_symmetry_guard_lab import (
    CurrencyScoreClaim, PairRelativeClaim, NEUTRAL_BAND,
)
from atlasquant_trader_fx28_d1w1_consensus_guard_lab import inspect_fx28_d1w1_agreement_lab as evaluate
from test_atlasquant_trader_fx28_bilateral_symmetry_guard_lab import inputs, SCORES, DECISION

WEEK = DECISION - timedelta(days=2)
NOW = DECISION + timedelta(minutes=15)


def w_inputs(*, override=None, stale=None, waiting=()):
    values = SCORES.copy()
    values.update(override or {})
    scores = [CurrencyScoreClaim(
        name, values[name], WEEK - (timedelta(days=4) if stale == name else timedelta(hours=1)),
        f"{i+1:064x}",
    ) for i, name in enumerate(SCORES)]
    # SCORES iteration contains exactly G8 currencies though order need not match.
    blocked = set(waiting)
    if stale:
        blocked.update(p for p in OFFICIAL_PAIRS if stale in split_pair(p))
    pair_rows = []
    for p in OFFICIAL_PAIRS:
        base, quote = split_pair(p)
        delta = values[base] - values[quote]
        label = ("BASE_RELATIVE" if delta > NEUTRAL_BAND else
                 "QUOTE_RELATIVE" if delta < -NEUTRAL_BAND else "NEUTRAL")
        pair_rows.append(PairRelativeClaim(p, None if p in blocked else delta,
                                           "AGUARDAR" if p in blocked else label))
    return scores, pair_rows


def run(*, daily=None, weekly=None, week=WEEK, day=DECISION, now=NOW):
    ds, dp = inputs() if daily is None else daily
    ws, wp = w_inputs() if weekly is None else weekly
    return evaluate(
        daily_currency_scores=ds, daily_pair_claims=dp,
        weekly_currency_scores=ws, weekly_pair_claims=wp,
        daily_decision_at_utc=day, weekly_decision_at_utc=week,
        inspected_at_utc=now,
    )


class D1W1BilateralTests(unittest.TestCase):
    def safe(self, out):
        self.assertEqual(out["operational_bias"], "AGUARDAR")
        self.assertFalse(out["trade_authorized"])
        self.assertFalse(out["publishable"])
        self.assertFalse(out["live_alert_allowed"])
        self.assertFalse(out["source_authenticity_verified"])
        self.assertFalse(out["independent_historical_pit_verified"])
        self.assertFalse(out["weights_and_accuracy_empirically_validated"])
        self.assertIsNone(out["calibrated_direction_probability"])
        self.assertIsNone(out["market_bias"])

    def test_28_concordant_synthetic_matrices_never_tradable(self):
        out = run()
        self.assertEqual(out["state"], "LAB_D1W1_BILATERAL_CONSISTENCY_CLASSIFIED_NO_GO")
        self.assertEqual((out["pair_count"], out["concordant_hypothesis_count"]), (28, 18))
        self.assertEqual(out["neutral_hypothesis_count"], 10)
        self.assertEqual(out["opposing_hypothesis_count"], 0)
        self.assertTrue(out["D1_matrix_claim_consistency_verified_locally"])
        self.safe(out)

    def test_seven_crosses_stale_daily_usd_wait(self):
        d = inputs(stale_currency="USD")
        out = run(daily=d)
        self.assertEqual(out["abstained_pair_count"], 7)
        self.assertEqual(out["daily_ready_pair_count"], 21)
        self.assertEqual(out["weekly_ready_pair_count"], 28)
        for p in OFFICIAL_PAIRS:
            self.assertEqual(out["pairs"][p]["state"] == "AGUARDAR_DADOS", "USD" in split_pair(p))
        self.safe(out)

    def test_seven_crosses_stale_weekly_usd_wait(self):
        out = run(weekly=w_inputs(stale="USD"))
        self.assertEqual(out["abstained_pair_count"], 7)
        self.assertEqual(out["weekly_ready_pair_count"], 21)
        self.safe(out)

    def test_opposing_daily_and_weekly_never_promoted(self):
        out = run(weekly=w_inputs(override={"USD": -200}))
        self.assertGreater(out["opposing_hypothesis_count"], 0)
        self.assertEqual(out["pairs"]["USD/JPY"]["state"], "CONFLITO_D1_W1")
        self.assertEqual(out["pairs"]["USD/JPY"]["operational_bias"], "AGUARDAR")
        self.safe(out)

    def test_neutral_in_weekly_blocks_directional_alignment(self):
        out = run(weekly=w_inputs(override={"USD": SCORES["JPY"]}))
        self.assertEqual(out["pairs"]["USD/JPY"]["state"], "NEUTRO_EM_UM_HORIZONTE")
        self.safe(out)

    def test_weekly_time_after_daily_rejected(self):
        out = run(week=DECISION+timedelta(seconds=1))
        self.assertEqual(out["reason"], "D1_W1_CUTOFF_ORDER_OR_CLOCK_INVALID")
        self.safe(out)

    def test_naive_or_late_inspection_rejected(self):
        for vals in ({"day": DECISION.replace(tzinfo=None)},
                     {"week": WEEK.replace(tzinfo=None)},
                     {"now": DECISION-timedelta(seconds=1)}):
            with self.subTest(vals=vals):
                out = run(**vals)
                self.assertEqual(out["state"], "LAB_D1W1_BILATERAL_JOIN_BLOCKED")
                self.safe(out)

    def test_mismatched_weekly_claim_fails_whole_census(self):
        ws, wp = w_inputs()
        wp[0] = replace(wp[0], relative_points=999)
        out = run(weekly=(ws, wp))
        self.assertTrue(out["reason"].startswith("WEEKLY_MATRIX_INCOHERENT_OR_INCOMPLETE"))
        self.assertEqual(out["pair_count"], 0)
        self.safe(out)

    def test_mismatched_daily_claim_fails_whole_census(self):
        ds, dp = inputs()
        dp[0] = replace(dp[0], relative_label="AGUARDAR")
        out = run(daily=(ds, dp))
        self.assertTrue(out["reason"].startswith("DAILY_MATRIX_INCOHERENT_OR_INCOMPLETE"))
        self.safe(out)

    def test_one_pair_voluntary_wait_does_not_promote(self):
        out = run(daily=inputs(waiting=["EUR/USD"]))
        self.assertEqual(out["pairs"]["EUR/USD"]["state"], "AGUARDAR_DADOS")
        self.assertEqual(out["abstained_pair_count"], 1)
        self.safe(out)

    def test_missing_weekly_pair_fails_all(self):
        ws, wp = w_inputs()
        out = run(weekly=(ws, wp[:-1]))
        self.assertEqual(out["state"], "LAB_D1W1_BILATERAL_JOIN_BLOCKED")
        self.safe(out)

    def test_never_interprets_synthetic_points_as_probabilities(self):
        out = run()
        self.assertEqual(out["new_cost_brl"], 0)
        self.assertEqual(out["http_requests"], 0)
        self.assertTrue(all(p["operational_bias"] == "AGUARDAR" for p in out["pairs"].values()))
        self.assertTrue(all(p["calibrated_probability"] is None for p in out["pairs"].values()))
        self.safe(out)

if __name__ == "__main__":
    unittest.main()