"""All rate-path examples are synthetic; not quoted market data or accuracy tests."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import unittest

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS
from atlasquant_trader_policy_expectations_conflict_lab import (
    RateExpectationVintage, inspect_policy_expectation_contradictions_lab as inspect,
    inspect_policy_expectations_d1_w1_lab as inspect_both,
)

UTC = timezone.utc
ASOF = datetime(2026, 11, 8, 16, tzinfo=UTC)
OLD = datetime(2026, 11, 5, 16, tzinfo=UTC)
NEW = datetime(2026, 11, 7, 16, tzinfo=UTC)


def vintages(currency, *, old="300", new="300", target="2027-02", instrument=None):
    instrument = instrument or f"{currency}:OIS3M"
    return [RateExpectationVintage(currency, OLD, OLD + timedelta(minutes=5), target, 3,
                                   old, instrument,
                                   "IMPLIED_POLICY_RATE_3M_BPS_RESEARCH_CLAIM", "a"*64),
            RateExpectationVintage(currency, NEW, NEW + timedelta(minutes=5), target, 3,
                                   new, instrument,
                                   "IMPLIED_POLICY_RATE_3M_BPS_RESEARCH_CLAIM", "b"*64)]


def dataset():
    rates = {c: vintages(c) for c in CURRENCIES}
    rates["USD"] = vintages("USD", new="320")
    return rates


def pair(result, name):
    return next(x for x in result["pair_rows"] if x["pair"] == name)


class ExpectationContradictionsTests(unittest.TestCase):
    def run_case(self, changes=None, horizon="D1", at=ASOF, directions=None):
        return inspect(changes if changes is not None else dataset(),
                       horizon=horizon, as_of_utc=at,
                       candidate_directions=directions if directions is not None
                       else {"EUR/USD": "ALTA", "USD/JPY": "ALTA", "AUD/NZD": "BAIXA"})

    def assert_safe(self, result):
        self.assertEqual(result["operational_bias"], "AGUARDAR")
        for key in ("publishable", "trade_authorized", "live_alert_allowed",
                    "worker_enabled", "scheduler_enabled",
                    "market_implied_quotes_independently_authenticated",
                    "instrument_comparability_independently_verified",
                    "point_in_time_vintages_independently_verified",
                    "news_surprise_independently_authenticated",
                    "regime_state_independently_verified",
                    "historical_predictive_increment_validated"):
            self.assertFalse(result[key], key)
        for key in ("directional_accuracy_validated", "calibrated_direction_probability",
                    "fx_bias", "index_bias"):
            self.assertIsNone(result[key], key)
        self.assertEqual((result["http_requests"], result["file_writes"], result["new_cost_brl"]), (0, 0, 0))

    def test_all_28_pair_routes_same_8_economies(self):
        r = self.run_case()
        self.assertEqual(r["pair_count"], 28)
        self.assertEqual({p["pair"] for p in r["pair_rows"]}, set(OFFICIAL_PAIRS))
        self.assertEqual(set(r["currency_states"]), set(CURRENCIES))
        self.assertEqual(r["documentary_contradictions"], 1)
        self.assertEqual(r["documentary_alignments"], 1)
        self.assertEqual(r["pair_context_unavailable"], 0)
        self.assert_safe(r)

    def test_base_quote_sign_reverses_expected_differential(self):
        r = self.run_case()
        self.assertEqual(pair(r, "EUR/USD")["base_minus_quote_change_bps_documentary"], "-20")
        self.assertEqual(pair(r, "EUR/USD")["comparison"], "DOCUMENTARY_RATE_EXPECTATION_CONTRADICTION")
        self.assertTrue(pair(r, "EUR/USD")["contradiction_veto_for_research_only"])
        self.assertEqual(pair(r, "USD/JPY")["base_minus_quote_change_bps_documentary"], "20")
        self.assertEqual(pair(r, "USD/JPY")["comparison"], "DOCUMENTARY_RATE_EXPECTATION_ALIGNMENT_NOT_PROOF")
        self.assert_safe(r)

    def test_candidate_baixa_reverses_contradiction(self):
        r = self.run_case(directions={"EUR/USD": "BAIXA", "USD/JPY": "BAIXA"})
        self.assertEqual(pair(r, "EUR/USD")["comparison"], "DOCUMENTARY_RATE_EXPECTATION_ALIGNMENT_NOT_PROOF")
        self.assertEqual(pair(r, "USD/JPY")["comparison"], "DOCUMENTARY_RATE_EXPECTATION_CONTRADICTION")
        self.assert_safe(r)

    def test_weekly_and_daily_handled_separately(self):
        for h in ("D1", "W1"):
            with self.subTest(horizon=h):
                r = self.run_case(horizon=h)
                self.assertEqual(r["horizon"], h)
                self.assertEqual(pair(r, "EUR/USD")["comparison"], "DOCUMENTARY_RATE_EXPECTATION_CONTRADICTION")
                self.assert_safe(r)

    def test_neutral_or_absent_candidate_does_not_create_signal(self):
        r = self.run_case(directions={"EUR/USD": "NEUTRO"})
        self.assertEqual(pair(r, "EUR/USD")["comparison"], "NO_DIRECTIONAL_RESEARCH_CANDIDATE")
        self.assertIsNone(pair(r, "GBP/USD")["candidate_direction_claim"])
        self.assert_safe(r)

    def test_change_smaller_than_threshold_is_inconclusive(self):
        rates = dataset()
        rates["USD"] = vintages("USD", new="304")
        r = self.run_case(rates)
        self.assertEqual(pair(r, "EUR/USD")["comparison"], "DIFFERENTIAL_SHIFT_TOO_SMALL_RESEARCH_ONLY")
        self.assertEqual(r["documentary_contradictions"], 0)
        self.assert_safe(r)

    def test_exact_threshold_is_documentary_not_probability(self):
        rates = dataset()
        rates["USD"] = vintages("USD", new="305")
        r = self.run_case(rates)
        self.assertEqual(pair(r, "EUR/USD")["comparison"], "DOCUMENTARY_RATE_EXPECTATION_CONTRADICTION")
        self.assertIsNone(r["calibrated_direction_probability"])
        self.assert_safe(r)

    def test_missing_currency_only_blocks_affected_seven_pairs(self):
        rates = dataset()
        rates["USD"] = []
        r = self.run_case(rates)
        self.assertEqual(r["pair_context_unavailable"], 7)
        self.assertEqual(pair(r, "EUR/USD")["comparison"], "RATE_PATH_EVIDENCE_UNAVAILABLE")
        self.assertEqual(pair(r, "AUD/NZD")["comparison"], "DIFFERENTIAL_SHIFT_TOO_SMALL_RESEARCH_ONLY")
        self.assert_safe(r)

    def test_reject_wrong_currency_in_record(self):
        rates = dataset()
        rates["EUR"][1] = replace(rates["EUR"][1], currency="GBP")
        r = self.run_case(rates)
        self.assertEqual(pair(r, "EUR/USD")["comparison"], "RATE_PATH_EVIDENCE_UNAVAILABLE")
        self.assert_safe(r)

    def test_bogus_or_nonfinite_rate_not_used(self):
        for value in ("NaN", "Infinity", "1e999", "5001", True, 300.0, "N/A", ""):
            with self.subTest(value=value):
                rates = dataset()
                rates["USD"][1] = replace(rates["USD"][1], expected_policy_rate_bps=value)
                r = self.run_case(rates)
                self.assertEqual(pair(r, "EUR/USD")["comparison"], "RATE_PATH_EVIDENCE_UNAVAILABLE")
                self.assert_safe(r)

    def test_wrong_tenor_or_methodology_does_not_mix(self):
        for mutation in ({"tenor_months": 6}, {"tenor_months": True},
                         {"methodology_claim": "RAW_FUTURES_TICKS"},
                         {"instrument_id": "INVALID SPACES"}):
            rates = dataset()
            rates["USD"][1] = replace(rates["USD"][1], **mutation)
            r = self.run_case(rates)
            self.assertEqual(pair(r, "EUR/USD")["comparison"], "RATE_PATH_EVIDENCE_UNAVAILABLE")
            self.assert_safe(r)

    def test_rollover_or_target_month_mismatch_rejected(self):
        for mutation in ({"target_month": "2027-03"}, {"instrument_id": "USD:NEW-OIS"}):
            rates = dataset()
            rates["USD"][1] = replace(rates["USD"][1], **mutation)
            r = self.run_case(rates)
            self.assertEqual(pair(r, "EUR/USD")["comparison"], "RATE_PATH_EVIDENCE_UNAVAILABLE")
            self.assert_safe(r)

    def test_other_currency_target_month_mismatch_prevents_comparison(self):
        rates = dataset()
        rates["EUR"] = vintages("EUR", target="2027-03")
        r = self.run_case(rates)
        self.assertEqual(pair(r, "EUR/USD")["comparison"], "CURRENCY_QUOTE_WINDOWS_OR_TARGET_MONTH_INCOMPARABLE")
        self.assertIsNone(pair(r, "EUR/USD")["base_minus_quote_change_bps_documentary"])
        self.assert_safe(r)

    def test_skewed_currency_quote_snapshots_do_not_compare(self):
        rates = dataset()
        rates["EUR"] = [replace(x, observed_at=x.observed_at + timedelta(hours=7),
                                captured_at=x.captured_at + timedelta(hours=7)) for x in rates["EUR"]]
        r = self.run_case(rates)
        self.assertEqual(pair(r, "EUR/USD")["comparison"], "CURRENCY_QUOTE_WINDOWS_OR_TARGET_MONTH_INCOMPARABLE")
        self.assert_safe(r)

    def test_future_snapshots_never_enter_past_asof(self):
        rates = dataset()
        rates["USD"][1] = replace(rates["USD"][1], captured_at=ASOF+timedelta(minutes=1))
        r = self.run_case(rates)
        self.assertEqual(pair(r, "EUR/USD")["comparison"], "RATE_PATH_EVIDENCE_UNAVAILABLE")
        self.assert_safe(r)

    def test_observed_quote_after_capture_not_accepted(self):
        rates = dataset()
        rates["USD"][1] = replace(rates["USD"][1], observed_at=NEW+timedelta(hours=2))
        r = self.run_case(rates)
        self.assertEqual(pair(r, "EUR/USD")["comparison"], "RATE_PATH_EVIDENCE_UNAVAILABLE")
        self.assert_safe(r)

    def test_lagged_quote_and_stale_cutoffs_fail_closed(self):
        rates = dataset()
        rates["USD"][1] = replace(rates["USD"][1], captured_at=NEW+timedelta(hours=5))
        r = self.run_case(rates)
        self.assertEqual(pair(r, "EUR/USD")["comparison"], "RATE_PATH_EVIDENCE_UNAVAILABLE")
        self.assert_safe(r)
        rates = dataset()
        r = self.run_case(rates, at=ASOF + timedelta(days=7))
        self.assertEqual(pair(r, "EUR/USD")["comparison"], "RATE_PATH_EVIDENCE_UNAVAILABLE")
        self.assert_safe(r)

    def test_invalid_source_sha_or_reused_instrument_not_accepted(self):
        rates = dataset()
        rates["USD"][1] = replace(rates["USD"][1], source_sha256_claim="oops")
        r = self.run_case(rates)
        self.assertEqual(pair(r, "EUR/USD")["comparison"], "RATE_PATH_EVIDENCE_UNAVAILABLE")
        self.assert_safe(r)

    def test_invalid_input_rejected_without_partial_28_pair_report(self):
        for changes, horizon, at, candidates in (
            (None, "D1", ASOF, {}), ({}, "D1", ASOF, {}),
            (dataset(), "M15", ASOF, {}), (dataset(), "D1", ASOF.replace(tzinfo=None), {}),
            (dataset(), "D1", ASOF, {"EURUSD": "ALTA"}),
            (dataset(), "D1", ASOF, {"WIN": "ALTA"}),
            (dataset(), "D1", ASOF, {"EUR/USD": "COMPRA"}),
        ):
            with self.subTest(h=horizon, at=at, candidates=candidates):
                r = inspect(changes, horizon=horizon, as_of_utc=at,
                            candidate_directions=candidates)
                self.assertEqual(r["state"], "LAB_RATE_EXPECTATION_INPUT_BLOCKED")
                self.assertEqual(r["pair_count"], 0)
                self.assert_safe(r)

    def test_d1_and_w1_use_different_cutoffs_and_vintages(self):
        # Both horizons use different *explicit* fixtures, no borrowing of D1 current data in W1.
        w = {c: vintages(c, old="300", new="300") for c in CURRENCIES}
        for c in CURRENCIES:
            w[c] = [replace(x, observed_at=x.observed_at - timedelta(days=2),
                            captured_at=x.captured_at - timedelta(days=2)) for x in w[c]]
        d = dataset()
        both = inspect_both(
            snapshots_by_horizon={"D1": d, "W1": w},
            decision_at_by_horizon={"D1": ASOF, "W1": ASOF - timedelta(days=2)},
            candidate_directions_by_horizon={"D1": {"EUR/USD": "ALTA"},
                                             "W1": {"EUR/USD": "ALTA"}},
            as_of_utc=ASOF,
        )
        self.assertEqual(both["state"], "LAB_D1_W1_POLICY_EXPECTATION_REVIEW_NO_GO")
        self.assertEqual(both["pair_count"], 28)
        eurusd = pair(both, "EUR/USD")
        self.assertTrue(eurusd["research_contradiction_in_either_horizon"])
        self.assertEqual(eurusd["W1_comparison"], "DIFFERENTIAL_SHIFT_TOO_SMALL_RESEARCH_ONLY")
        self.assertEqual(eurusd["D1_comparison"], "DOCUMENTARY_RATE_EXPECTATION_CONTRADICTION")
        self.assert_safe(both)

    def test_d1_and_w1_reject_reusing_a_future_daily_capture_in_weekly(self):
        both = inspect_both(
            snapshots_by_horizon={"D1": dataset(), "W1": dataset()},
            decision_at_by_horizon={"D1": ASOF, "W1": ASOF - timedelta(days=2)},
            candidate_directions_by_horizon={"D1": {"EUR/USD": "ALTA"},
                                             "W1": {"EUR/USD": "ALTA"}},
            as_of_utc=ASOF,
        )
        self.assertEqual(both["state"], "LAB_D1_W1_POLICY_EXPECTATION_REVIEW_NO_GO")
        self.assertTrue(pair(both, "EUR/USD")["rate_data_unavailable_or_incomparable_in_either_horizon"])
        self.assertTrue(pair(both, "EUR/USD")["research_contradiction_in_either_horizon"])
        self.assertEqual(pair(both, "EUR/USD")["W1_comparison"], "RATE_PATH_EVIDENCE_UNAVAILABLE")
        self.assert_safe(both)

    def test_d1_w1_invalid_decision_order_abstains(self):
        both = inspect_both(
            snapshots_by_horizon={"D1": dataset(), "W1": dataset()},
            decision_at_by_horizon={"D1": ASOF - timedelta(days=2), "W1": ASOF},
            candidate_directions_by_horizon={"D1": {}, "W1": {}},
            as_of_utc=ASOF,
        )
        self.assertEqual(both["state"], "LAB_RATE_EXPECTATION_INPUT_BLOCKED")
        self.assert_safe(both)

    def test_reusing_same_hash_for_two_vintages_is_not_independent_update(self):
        rates = dataset()
        rates["USD"][1] = replace(rates["USD"][1], source_sha256_claim="a" * 64)
        r = self.run_case(rates)
        self.assertEqual(pair(r, "EUR/USD")["comparison"], "RATE_PATH_EVIDENCE_UNAVAILABLE")
        self.assert_safe(r)

    def test_unhashable_horizon_is_fail_closed_not_exception(self):
        r = inspect(dataset(), horizon=["D1"], as_of_utc=ASOF)
        self.assertEqual(r["state"], "LAB_RATE_EXPECTATION_INPUT_BLOCKED")
        self.assert_safe(r)

    def test_different_forward_target_month_and_bad_regime_do_not_claim_confirmations(self):
        r = self.run_case()
        self.assertFalse(r["regime_state_independently_verified"])
        self.assertFalse(r["news_surprise_independently_authenticated"])
        self.assertFalse(r["historical_predictive_increment_validated"])
        self.assert_safe(r)


if __name__ == "__main__":
    unittest.main()
