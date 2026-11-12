"""Synthetic PPI seven-FX price breadth: NOT independent predictive trials."""
from copy import deepcopy
from decimal import Decimal
import unittest

from atlasquant_trader_ppi_fx_breadth_lab import (
    BLOCKED, DOCUMENTARY, METRICS,
    summarize_ppi_7fx_breadth_lab as summarize,
)
from atlasquant_trader_ppi_usd_fx_forward_reaction_lab import USD_FX


def fixture():
    rows = {}
    for i, sym in enumerate(USD_FX, 1):
        rows[sym] = {
            "M15": f"{i}.00",
            "H1": "-1.00" if i == 1 else f"{i}.00",
            "H4": "-3.00" if i == 1 else "1.00",
        }
    return {
        "state": "LAB_PPI_FX_7PAIR_FORWARD_REACTION_DOCUMENTARY_NO_GO",
        "independent_economic_event_sample_count": 1,
        "source_broker_independently_authenticated": False,
        "prediction_precommitted_and_validated": False,
        "price_reactions_usd_normalized_bps": rows,
    }


class PpiBreadthTests(unittest.TestCase):
    def run_lab(self, report=None):
        result = summarize(price_reaction_report=fixture() if report is None else report)
        self.assertEqual(result["operational_bias"], "AGUARDAR")
        self.assertFalse(result["trade_authorized"])
        self.assertFalse(result["publishable"])
        self.assertFalse(result["live_alert_allowed"])
        self.assertFalse(result["broker_candles_independently_authenticated"])
        self.assertFalse(result["source_price_bytes_revalidated_by_this_helper"])
        self.assertFalse(result["pre_event_directional_forecast_registered"])
        self.assertTrue(result["seven_correlated_pairs_not_seven_independent_trials"])
        self.assertTrue(result["cross_pair_price_moves_do_not_estimate_usd_causality"])
        self.assertEqual(result["economic_event_count_documentary"], 1)
        self.assertEqual(result["independent_prediction_trials_verified"], 0)
        self.assertEqual(result["validated_prediction_count"], 0)
        self.assertIsNone(result["validated_directional_accuracy"])
        self.assertIsNone(result["calibrated_direction_probability"])
        self.assertIsNone(result["market_bias"])
        self.assertEqual((result["http_requests"], result["file_writes"],
                          result["new_cost_brl"]), (0, 0, 0))
        return result

    def test_complete_sample_counts_and_median_are_descriptive(self):
        x = self.run_lab()
        self.assertEqual(x["state"], DOCUMENTARY)
        self.assertEqual(x["fx_pair_count_documentary"], 7)
        rows = x["cross_pair_breadth_by_horizon"]
        self.assertEqual(set(rows), set(METRICS))
        self.assertEqual(rows["M15"]["positive_usd_normalized_move_count"], 7)
        self.assertEqual(rows["M15"]["negative_usd_normalized_move_count"], 0)
        self.assertEqual(rows["M15"]["rounded_zero_usd_normalized_move_count"], 0)
        self.assertEqual(rows["M15"]["median_of_seven_normalized_bps_documentary"], "4.00")
        self.assertEqual(rows["M15"]["max_minus_min_bps_descriptive"], "6.00")
        self.assertEqual(rows["M15"]["sign_pattern_documentary_not_predictive"],
                         "SEVEN_POSITIVE_USD_NORMALIZED_PRICE_MOVES")

    def test_opposite_sign_on_one_pair_is_visible_not_majority_certainty(self):
        x = self.run_lab()
        h4 = x["cross_pair_breadth_by_horizon"]["H4"]
        self.assertEqual(h4["negative_pair_symbols"], ["EURUSD"])
        self.assertEqual(h4["positive_usd_normalized_move_count"], 6)
        self.assertEqual(h4["sign_pattern_documentary_not_predictive"],
                         "MIXED_POSITIVE_NEGATIVE_SPOT_REACTIONS")
        self.assertEqual(x["cross_horizon_m15_to_h4_sign_reversals"], ["EURUSD"])

    def test_all_negative_h4_price_movements_are_not_a_short_signal(self):
        v = fixture()
        for sym in USD_FX:
            v["price_reactions_usd_normalized_bps"][sym]["H4"] = "-1.10"
        x = self.run_lab(v)
        self.assertEqual(x["cross_pair_breadth_by_horizon"]["H4"]["negative_usd_normalized_move_count"], 7)
        self.assertEqual(x["cross_pair_breadth_by_horizon"]["H4"]["sign_pattern_documentary_not_predictive"],
                         "SEVEN_NEGATIVE_USD_NORMALIZED_PRICE_MOVES")
        self.assertIsNone(x["market_bias"])

    def test_all_rounded_zero_does_not_prove_no_intrabar_move(self):
        v = fixture()
        for sym in USD_FX:
            v["price_reactions_usd_normalized_bps"][sym]["M15"] = "0.00"
        x = self.run_lab(v)
        self.assertEqual(x["cross_pair_breadth_by_horizon"]["M15"]["rounded_zero_usd_normalized_move_count"], 7)
        self.assertEqual(x["cross_pair_breadth_by_horizon"]["M15"]["sign_pattern_documentary_not_predictive"],
                         "SEVEN_ROUNDED_ZERO_PRICE_MOVES")
        self.assertTrue(x["rounded_zero_bps_can_mask_tiny_price_moves"])
        self.assertEqual(x["cross_horizon_m15_to_h4_sign_reversals"], [])

    def test_mixed_with_zero_still_descriptive_not_7_votes(self):
        v = fixture()
        v["price_reactions_usd_normalized_bps"]["EURUSD"]["M15"] = "-0.00"
        x = self.run_lab(v)
        r = x["cross_pair_breadth_by_horizon"]["M15"]
        self.assertEqual(r["rounded_zero_usd_normalized_move_count"], 1)
        self.assertEqual(r["sign_pattern_documentary_not_predictive"],
                         "PARTIAL_SIGN_WITH_ROUNDED_ZERO_REACTIONS")
        self.assertEqual(r["rounded_zero_pair_symbols"], ["EURUSD"])

    def test_missing_pair_and_extra_pair_block(self):
        for add in (False, True):
            with self.subTest(extra=add):
                v = fixture()
                if add:
                    v["price_reactions_usd_normalized_bps"]["EURGBP"] = dict(
                        v["price_reactions_usd_normalized_bps"]["EURUSD"])
                else:
                    del v["price_reactions_usd_normalized_bps"]["USDJPY"]
                out = self.run_lab(v)
                self.assertEqual(out["state"], BLOCKED)
                self.assertIsNone(out["cross_pair_breadth_by_horizon"])

    def test_wrong_horizons_or_missing_value_block(self):
        for key in ("M15", "H1", "H4"):
            with self.subTest(missing=key):
                v = fixture()
                del v["price_reactions_usd_normalized_bps"]["EURUSD"][key]
                out = self.run_lab(v)
                self.assertEqual(out["state"], BLOCKED)
        v = fixture()
        v["price_reactions_usd_normalized_bps"]["USDJPY"]["H4_EXTRA"] = "1.00"
        self.assertEqual(self.run_lab(v)["state"], BLOCKED)

    def test_noncanonical_bps_rejected_not_silently_cast(self):
        for wrong in ("NaN", "Inf", "+1.00", "0.1", "1e2", " 1.00",
                      "", "1,00", "10000000000000.00", 1.0, None):
            with self.subTest(wrong=wrong):
                v = fixture()
                v["price_reactions_usd_normalized_bps"]["USDCHF"]["H1"] = wrong
                out = self.run_lab(v)
                self.assertEqual(out["state"], BLOCKED)

    def test_claimed_seven_independent_events_rejected(self):
        v = fixture()
        v["independent_economic_event_sample_count"] = 7
        out = self.run_lab(v)
        self.assertEqual(out["state"], BLOCKED)
        self.assertEqual(out["independent_prediction_trials_verified"], 0)

    def test_claimed_broker_authentication_or_precommitted_prediction_rejected(self):
        for field in ("source_broker_independently_authenticated",
                      "prediction_precommitted_and_validated"):
            with self.subTest(field=field):
                v = fixture()
                v[field] = True
                out = self.run_lab(v)
                self.assertEqual(out["state"], BLOCKED)

    def test_input_not_mutated(self):
        v = fixture()
        copy = deepcopy(v)
        x = self.run_lab(v)
        self.assertEqual(v, copy)
        self.assertEqual(x["state"], DOCUMENTARY)

    def test_wrong_envelope_blocked(self):
        for wrong in (None, [], "price", {}, {"state": "LAB_NOT_READY"}):
            with self.subTest(wrong=wrong):
                out = self.run_lab(wrong)
                self.assertEqual(out["state"], BLOCKED)


if __name__ == "__main__":
    unittest.main()
