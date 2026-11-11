"""Synthetic invariants: eight anchors, 28 pairs, no false bias or accuracy."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
import unittest

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS, split_pair
from atlasquant_trader_fx28_bilateral_symmetry_guard_lab import (
    CurrencyScoreClaim, PairRelativeClaim, NEUTRAL_BAND,
    inspect_fx28_bilateral_symmetry_lab as audit,
)

UTC = timezone.utc
DECISION = datetime(2026, 11, 11, 12, tzinfo=UTC)
SCORES = {"USD": 100, "EUR": 30, "GBP": 20, "JPY": -100,
          "CHF": 0, "CAD": 10, "AUD": -20, "NZD": -90}


def inputs(*, stale_currency=None, waiting=()):
    anchors = [CurrencyScoreClaim(
        c, SCORES[c], DECISION - (timedelta(hours=15)
                                   if stale_currency == c else timedelta(hours=1)),
        f"{i+1:064x}",
    ) for i, c in enumerate(CURRENCIES)]
    waits = set(waiting)
    if stale_currency:
        waits |= {p for p in OFFICIAL_PAIRS if stale_currency in split_pair(p)}
    pairs = []
    for p in OFFICIAL_PAIRS:
        a, b = split_pair(p)
        v = SCORES[a] - SCORES[b]
        label = ("BASE_RELATIVE" if v > NEUTRAL_BAND else
                 "QUOTE_RELATIVE" if v < -NEUTRAL_BAND else "NEUTRAL")
        pairs.append(PairRelativeClaim(p, None if p in waits else v,
                                       "AGUARDAR" if p in waits else label))
    return anchors, pairs


def run(anchors=None, pairs=None, *, horizon="D1", decision=DECISION,
        inspected=DECISION + timedelta(minutes=1)):
    a, b = inputs()
    return audit(currency_scores=a if anchors is None else anchors,
                 pair_claims=b if pairs is None else pairs,
                 horizon=horizon, decision_at_utc=decision,
                 inspected_at_utc=inspected)


class BilateralTests(unittest.TestCase):
    def safe(self, r):
        self.assertEqual(r["operational_bias"], "AGUARDAR")
        self.assertFalse(r["trade_authorized"])
        self.assertFalse(r["publishable"])
        self.assertFalse(r["live_alert_allowed"])
        self.assertFalse(r["worker_enabled"])
        self.assertFalse(r["scheduler_enabled"])
        self.assertFalse(r["independent_macro_sources_authenticated"])
        self.assertFalse(r["historical_point_in_time_proven"])
        self.assertFalse(r["model_scores_are_calibrated_probabilities"])
        self.assertIsNone(r["validated_accuracy"])
        self.assertIsNone(r["fx_bias"])
        self.assertEqual(r["new_cost_brl"], 0)

    def test_all_28_inverse_and_56_triangles_consistent(self):
        r = run()
        self.assertEqual(r["state"], "LAB_FX28_BILATERAL_COHERENT_CLAIMS_NO_GO")
        self.assertEqual((r["currency_count"], r["pair_count"]), (8, 28))
        self.assertEqual((r["inverse_checks"], r["triangle_checks"]), (28, 56))
        self.assertEqual(r["abstained_pair_count"], 0)
        self.safe(r)

    def test_eur_usd_oriented_correctly(self):
        anchors, pairs = inputs()
        row = next(x for x in pairs if x.pair == "EUR/USD")
        self.assertEqual((row.relative_points, row.relative_label), (-70, "QUOTE_RELATIVE"))
        row = next(x for x in pairs if x.pair == "USD/JPY")
        self.assertEqual((row.relative_points, row.relative_label), (200, "BASE_RELATIVE"))
        self.safe(run(anchors, pairs))

    def test_stale_single_currency_abstains_seven_crosses(self):
        a, p = inputs(stale_currency="USD")
        r = run(a, p)
        self.assertEqual(r["state"], "LAB_FX28_BILATERAL_COHERENT_CLAIMS_NO_GO")
        self.assertEqual(r["stale_currencies"], ["USD"])
        self.assertEqual((r["ready_pair_count"], r["abstained_pair_count"]), (21, 7))
        self.assertEqual(r["triangle_checks"], 35)
        self.safe(r)

    def test_stale_currency_must_not_emit_relative_label(self):
        a, p = inputs(stale_currency="USD")
        i = next(i for i, x in enumerate(p) if "USD" in x.pair)
        p[i] = replace(p[i], relative_label="BASE_RELATIVE", relative_points=120)
        r = run(a, p)
        self.assertEqual(r["reason"], "STALE_ANCHOR_USED_AS_DIRECTIONAL_PAIR")
        self.safe(r)

    def test_wrong_pair_orientation_rejected(self):
        a, p = inputs()
        i = next(i for i, x in enumerate(p) if x.pair == "EUR/USD")
        p[i] = replace(p[i], relative_label="BASE_RELATIVE")
        r = run(a, p)
        self.assertEqual(r["reason"], "PAIR_DIFFERENTIAL_OR_SIGN_CONTRADICTS_BILATERAL_ANCHORS")
        self.safe(r)

    def test_one_lying_score_rejected_even_correct_label(self):
        a, p = inputs()
        p[0] = replace(p[0], relative_points=p[0].relative_points + 1)
        r = run(a, p)
        self.assertEqual(r["reason"], "PAIR_DIFFERENTIAL_OR_SIGN_CONTRADICTS_BILATERAL_ANCHORS")
        self.safe(r)

    def test_optional_wait_valid_but_no_numeric_signal(self):
        a, p = inputs(waiting=["EUR/USD"])
        r = run(a, p)
        self.assertEqual((r["ready_pair_count"], r["abstained_pair_count"]), (27, 1))
        self.assertEqual(r["triangle_checks"], 50)  # six triangles include EUR/USD
        self.safe(r)
        i = next(i for i, x in enumerate(p) if x.pair == "EUR/USD")
        p[i] = replace(p[i], relative_points=-70)
        self.assertEqual(run(a, p)["reason"], "WAIT_PAIR_MUST_NOT_CLAIM_RELATIVE_POINTS")

    def test_missing_or_extra_pair_blocks(self):
        a, p = inputs()
        self.assertEqual(run(a, p[:-1])["state"], "LAB_BILATERAL_COHERENCE_BLOCKED")
        p[-1] = replace(p[-1], pair="EUR/USD")
        self.assertEqual(run(a, p)["reason"], "PAIR_UNIVERSE_OR_LABEL_INVALID")

    def test_reverse_noncanonical_pair_blocks(self):
        a, p = inputs()
        p[0] = replace(p[0], pair="USD/EUR")
        self.assertEqual(run(a, p)["reason"], "PAIR_UNIVERSE_OR_LABEL_INVALID")

    def test_missing_currency_blocks(self):
        a, p = inputs()
        self.assertEqual(run(a[:-1], p)["state"], "LAB_BILATERAL_COHERENCE_BLOCKED")
        a[-1] = replace(a[-1], currency="USD")
        self.assertEqual(run(a, p)["reason"], "DUPLICATE_MISSING_OR_INVALID_CURRENCY_SCORE")

    def test_boolean_float_and_outside_bounds_are_rejected(self):
        for value in (True, 1.0, -201, 201, float("nan"), float("inf")):
            with self.subTest(value=value):
                a, p = inputs()
                a[0] = replace(a[0], synthetic_points=value)
                self.assertEqual(run(a, p)["reason"], "DUPLICATE_MISSING_OR_INVALID_CURRENCY_SCORE")

    def test_future_source_capture_blocks(self):
        a, p = inputs()
        a[0] = replace(a[0], score_captured_at=DECISION + timedelta(seconds=1))
        self.assertEqual(run(a, p)["reason"], "FUTURE_OR_INVALID_SCORE_CAPTURE")

    def test_naive_clock_or_future_decision_blocks(self):
        for kw in ({"decision": DECISION.replace(tzinfo=None)},
                   {"inspected": DECISION - timedelta(seconds=1)},
                   {"horizon": "M1"}):
            with self.subTest(kw=kw):
                self.assertEqual(run(**kw)["state"], "LAB_BILATERAL_COHERENCE_BLOCKED")

    def test_horizon_specific_freshness(self):
        a, p = inputs(stale_currency="USD")
        r = run(a, p, horizon="W1")
        # On W1 the 15-hour-old anchor is fresh; 7 WAIT pairs are valid voluntary abstentions.
        self.assertEqual((r["ready_pair_count"], r["abstained_pair_count"]), (21, 7))
        self.assertEqual(r["stale_currencies"], [])
        self.safe(r)

    def test_invalid_hash_source_claim_blocks(self):
        a, p = inputs()
        a[0] = replace(a[0], source_sha256_claim="not-a-real-digest")
        self.assertEqual(run(a, p)["reason"], "DUPLICATE_MISSING_OR_INVALID_CURRENCY_SCORE")


if __name__ == "__main__":
    unittest.main()