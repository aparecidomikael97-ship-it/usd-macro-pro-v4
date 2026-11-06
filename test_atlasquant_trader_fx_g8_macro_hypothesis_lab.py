"""All macro inputs here are FICTIONAL; zero evidence of real predictive edge."""
from hashlib import sha256
import json
import unittest

from atlasquant_fx_universe import OFFICIAL_PAIRS, CURRENCIES
from atlasquant_trader_fx_g8_macro_hypothesis_lab import (
    INPUT, SCHEMA, FACTORS, WEIGHTS, NEUTRAL_DIFF_POINTS,
    inspect_g8_synthetic_macro_hypothesis_lab as inspect,
)


def mock_input(*, horizon="D1"):
    return {
        "schema": INPUT,
        "data_kind": "SYNTHETIC_RESEARCH_ONLY",
        "horizon": horizon,
        "research_at_utc": "2026-11-06T14:00:00Z",
        "currency_factors": {
            c: {f: 0 for f in FACTORS} for c in CURRENCIES
        },
    }


def raw(obj):
    return (json.dumps(obj, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def eval_mock(obj=None):
    return inspect(raw(mock_input() if obj is None else obj))


class HypothesisModelTests(unittest.TestCase):
    def assert_no_go(self, result):
        for field in (
            "input_factors_are_verified_official_statistics",
            "monetary_surprise_from_market_consensus_verified",
            "economic_surprises_from_pre_release_consensus_verified",
            "geopolitical_risk_model_implemented",
            "broker_m15_execution_prices_verified",
            "weights_empirically_calibrated",
            "macro_bias_predictive_accuracy_verified",
            "can_feed_live_radar", "trade_authorized",
            "worker_enabled", "scheduler_enabled", "publishable",
        ):
            self.assertIs(result[field], False, field)
        self.assertEqual(result["source_kind"], "SYNTHETIC_RESEARCH_ONLY")
        self.assertEqual(result["validated_prediction_count"], 0)
        self.assertIsNone(result["validated_accuracy"])
        self.assertIsNone(result["fx_bias"])
        self.assertEqual(result["operational_bias"], "AGUARDAR")
        self.assertEqual((result["http_requests"], result["new_cost_brl"]), (0, 0))

    def test_fixed_hypothesis_weights_total_100_each_period(self):
        self.assertEqual(set(WEIGHTS), {"D1", "W1"})
        for horizon, row in WEIGHTS.items():
            self.assertEqual(tuple(row), FACTORS)
            self.assertEqual(sum(row.values()), 100)
            self.assertTrue(all(type(x) is int and 0 < x < 100 for x in row.values()))
        self.assertEqual(NEUTRAL_DIFF_POINTS, 40)

    def test_zero_synthetic_impulses_are_28_neutral_comparisons(self):
        obj = mock_input()
        out = eval_mock(obj)
        self.assertEqual(out["schema"], SCHEMA)
        self.assertEqual(out["state"], "LAB_SYNTHETIC_MACRO_RANKING_ONLY_NOT_A_FORECAST")
        self.assertEqual((out["currency_count"], out["pair_count"]), (8, 28))
        self.assertEqual(out["neutral_pair_count"], 28)
        self.assertEqual(out["highest_abs_pair_score"], 0)
        self.assertEqual(out["input_sha256"], sha256(raw(obj)).hexdigest())
        self.assertEqual({r["pair"] for r in out["synthetic_pair_rank"]}, set(OFFICIAL_PAIRS))
        self.assert_no_go(out)

    def test_one_hawkish_currency_relative_monetary_impulse(self):
        obj = mock_input()
        obj["currency_factors"]["EUR"]["policy_repricing"] = 2
        out = eval_mock(obj)
        self.assertEqual(out["highest_abs_pair_score"], 80)
        by_pair = {r["pair"]: r for r in out["synthetic_pair_rank"]}
        self.assertEqual(by_pair["EUR/USD"]["synthetic_relative_points"], 80)
        self.assertEqual(by_pair["EUR/USD"]["synthetic_relation"], "BASE_RELATIVELY_FORTE")
        self.assertEqual(by_pair["EUR/GBP"]["synthetic_relative_points"], 80)
        self.assertEqual(by_pair["EUR/JPY"]["synthetic_relative_points"], 80)
        self.assertEqual(by_pair["USD/JPY"]["synthetic_relative_points"], 0)
        self.assert_no_go(out)

    def test_quote_hawkish_impulse_reverses_pair_relation(self):
        obj = mock_input()
        obj["currency_factors"]["USD"]["policy_repricing"] = 2
        out = eval_mock(obj)
        pair = next(r for r in out["synthetic_pair_rank"] if r["pair"] == "EUR/USD")
        self.assertEqual(pair["synthetic_relative_points"], -80)
        self.assertEqual(pair["synthetic_relation"], "COTACAO_RELATIVAMENTE_FORTE")
        self.assert_no_go(out)

    def test_weekly_policy_weight_differs_from_daily_by_frozen_design(self):
        d = mock_input(horizon="D1")
        w = mock_input(horizon="W1")
        d["currency_factors"]["EUR"]["policy_repricing"] = 2
        w["currency_factors"]["EUR"]["policy_repricing"] = 2
        daily, weekly = eval_mock(d), eval_mock(w)
        self.assertEqual(daily["highest_abs_pair_score"], 80)
        self.assertEqual(weekly["highest_abs_pair_score"], 90)
        self.assertEqual(weekly["horizon"], "W1")
        self.assert_no_go(daily)
        self.assert_no_go(weekly)

    def test_valid_impulses_cancel_when_equal_across_currencies(self):
        obj = mock_input()
        for c in CURRENCIES:
            obj["currency_factors"][c].update({
                "policy_repricing": 2, "inflation_repricing": -1,
                "growth_surprise": 1, "labor_surprise": -2,
            })
        out = eval_mock(obj)
        self.assertEqual(out["neutral_pair_count"], 28)
        self.assertEqual(out["highest_abs_pair_score"], 0)
        self.assert_no_go(out)

    def test_28_crosses_arise_from_only_8_currency_scores(self):
        obj = mock_input()
        for index, cur in enumerate(CURRENCIES):
            obj["currency_factors"][cur]["policy_repricing"] = index % 5 - 2
            obj["currency_factors"][cur]["growth_surprise"] = 2 - index % 5
        out = eval_mock(obj)
        points = {r["currency"]: r["synthetic_points"]
                  for r in out["synthetic_currency_rank"]}
        self.assertEqual(len(out["synthetic_pair_rank"]), 28)
        for row in out["synthetic_pair_rank"]:
            self.assertEqual(row["synthetic_relative_points"],
                             points[row["base"]] - points[row["quote"]])
        self.assert_no_go(out)

    def test_pair_inverse_arithmetic_avoids_inconsistent_triangle(self):
        obj = mock_input()
        obj["currency_factors"]["USD"]["policy_repricing"] = -2
        obj["currency_factors"]["EUR"]["growth_surprise"] = 2
        obj["currency_factors"]["JPY"]["labor_surprise"] = 1
        out = eval_mock(obj)
        by_pair = {r["pair"]: r["synthetic_relative_points"]
                   for r in out["synthetic_pair_rank"]}
        # USD/JPY + EUR/USD == EUR/JPY: mathematical transitivity.
        self.assertEqual(by_pair["USD/JPY"] + by_pair["EUR/USD"],
                         by_pair["EUR/JPY"])
        self.assert_no_go(out)

    def test_stable_tie_break_is_alphabetical_pair_identity(self):
        out = eval_mock()
        self.assertEqual([r["pair"] for r in out["synthetic_pair_rank"]],
                         sorted(OFFICIAL_PAIRS))

    def test_fixed_40_point_neutral_zone_has_strict_boundary(self):
        obj = mock_input()
        obj["currency_factors"]["EUR"]["policy_repricing"] = 1
        out = eval_mock(obj)
        rel = next(r for r in out["synthetic_pair_rank"] if r["pair"] == "EUR/USD")
        self.assertEqual(rel["synthetic_relative_points"], 40)
        self.assertEqual(rel["synthetic_relation"], "INDEFINIDO_HIPOTESE")
        self.assert_no_go(out)

    def test_missing_macro_factor_cannot_be_automatically_zero_filled(self):
        obj = mock_input()
        del obj["currency_factors"]["EUR"]["inflation_repricing"]
        out = eval_mock(obj)
        self.assertEqual(out["state"], "LAB_BLOCKED")
        self.assertEqual(out["reason"], "MACRO_FACTOR_MISSING_OR_UNKNOWN")
        self.assert_no_go(out)

    def test_extra_macro_factor_rejected(self):
        obj = mock_input()
        obj["currency_factors"]["EUR"]["geopolitics"] = 2
        self.assertEqual(eval_mock(obj)["state"], "LAB_BLOCKED")

    def test_missing_or_ninth_currency_never_accepted(self):
        for mode in ("missing", "extra"):
            obj = mock_input()
            if mode == "missing":
                del obj["currency_factors"]["CHF"]
            else:
                obj["currency_factors"]["BRL"] = {f: 0 for f in FACTORS}
            out = eval_mock(obj)
            self.assertEqual(out["reason"], "G8_UNIVERSE_MISSING_OR_UNKNOWN_CURRENCY")
            self.assert_no_go(out)

    def test_only_strict_signed_integer_shocks_allowed(self):
        for bad in (-3, 3, 1.0, True, False, "2", None, [], {}, float("nan")):
            obj = mock_input()
            obj["currency_factors"]["USD"]["growth_surprise"] = bad
            result = eval_mock(obj)
            self.assertEqual(result["state"], "LAB_BLOCKED", str(bad))
            self.assert_no_go(result)

    def test_maximum_and_minimum_points_cannot_exceed_fixed_range(self):
        obj = mock_input()
        for f in FACTORS:
            obj["currency_factors"]["USD"][f] = 2
            obj["currency_factors"]["EUR"][f] = -2
        out = eval_mock(obj)
        by_pair = {r["pair"]: r for r in out["synthetic_pair_rank"]}
        self.assertEqual(by_pair["EUR/USD"]["synthetic_relative_points"], -400)
        self.assertEqual(out["highest_abs_pair_score"], 400)
        self.assertTrue(all(abs(r["synthetic_relative_points"]) <= 400
                            for r in out["synthetic_pair_rank"]))
        self.assert_no_go(out)

    def test_wrong_source_kind_must_not_masquerade_as_official_data(self):
        for wrong in ("OFFICIAL_ECB", "VERIFIED_BROKER_DATA", "LIVE_MARKET", None):
            obj = mock_input()
            obj["data_kind"] = wrong
            out = eval_mock(obj)
            self.assertEqual(out["state"], "LAB_BLOCKED")
            self.assert_no_go(out)

    def test_unknown_horizon_blocked_instead_of_guessing(self):
        for wrong in ("M15", "D2", "MONTHLY", "", None, 1):
            obj = mock_input()
            obj["horizon"] = wrong
            self.assertEqual(eval_mock(obj)["state"], "LAB_BLOCKED")

    def test_malformed_and_duplicate_json_rejected(self):
        valid = raw(mock_input())
        for invalid in (
            b"", b"[]", b"null", b"{", b"\xff", b"not json",
            valid[:-2] + b',"schema":"override"}',
            b"x" * 7001,
        ):
            result = inspect(invalid)
            self.assertEqual(result["state"], "LAB_BLOCKED")
            self.assert_no_go(result)

    def test_timestamp_bad_format_bad_date_and_missing_fields(self):
        for when in ("2026-11-06 14:00:00", "2026-11-06T14:00:00-04:00",
                     "2026-02-30T14:00:00Z", "2025-11-06T14:00:00Z",
                     "", None):
            obj = mock_input()
            obj["research_at_utc"] = when
            self.assertEqual(eval_mock(obj)["state"], "LAB_BLOCKED", str(when))
        obj = mock_input()
        obj["probability"] = 0.99
        self.assertEqual(eval_mock(obj)["state"], "LAB_BLOCKED")

    def test_invalid_currency_factor_structure_rejected(self):
        for invalid in (None, [], "not factors", 0):
            obj = mock_input()
            obj["currency_factors"]["EUR"] = invalid
            self.assertEqual(eval_mock(obj)["state"], "LAB_BLOCKED")

    def test_all_outputs_persist_no_operational_bias_even_full_extremes(self):
        for horizon in ("D1", "W1"):
            obj = mock_input(horizon=horizon)
            for i, c in enumerate(CURRENCIES):
                for f in FACTORS:
                    obj["currency_factors"][c][f] = -2 if i % 2 else 2
            result = eval_mock(obj)
            self.assertEqual(result["pair_count"], 28)
            self.assertEqual(result["state"],
                             "LAB_SYNTHETIC_MACRO_RANKING_ONLY_NOT_A_FORECAST")
            self.assert_no_go(result)


if __name__ == "__main__":
    unittest.main()
