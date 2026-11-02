"""Synthetic-only paired macro-veto study; zero claims about real accuracy."""
import copy
import unittest
from datetime import datetime, timedelta, timezone
from math import exp

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS
from atlasquant_trader_bias_daily_freeze_lab import (
    freeze_daily_bias_observation_lab, VETO_POLICY_ID,
)
from atlasquant_trader_bias_forecast_bridge_lab import FIXED_METHOD, SCHEMA as BRIDGE
from atlasquant_trader_bias_macro_ablation_lab import (
    MACRO_METHOD, compare_frozen_macro_veto_lab,
)

SPLIT = datetime(2026, 8, 1, 0, tzinfo=timezone.utc)
NOW = datetime(2026, 11, 2, 15, tzinfo=timezone.utc)
TRAIN = ("2026-06-01", "2026-06-05", "2026-06-10")
TEST = ("2026-09-02", "2026-09-04", "2026-09-07", "2026-09-09")
LENGTHS = {"D1": 1, "W1": 7, "MN1": 30}
USDJPY = "USD/JPY"


def observation(day, veto=False):
    issued = datetime.fromisoformat(day + "T11:00:00+00:00")
    key = "bias-" + day.replace("-", "")
    forecasts = [
        {"forecast_id": f"{key}-{h}-{pair.replace('/', '')}",
         "state": "LAB_SYNTHETIC_BIAS", "pair": pair, "horizon": h,
         "bias": "ALTA", "method_id": FIXED_METHOD,
         "issued_at_utc": issued.isoformat(),
         "evidence_at_utc": (issued - timedelta(minutes=30)).isoformat(),
         "trade_authorized": False}
        for pair in OFFICIAL_PAIRS for h in LENGTHS
    ]
    evidence = [
        {"state": "LAB_SYNTHETIC_EVIDENCE", "evidence_id": "g8-ref",
         "kind": "G8_STRENGTH_REFERENCE", "source": "Sintetico-lab",
         "data_as_of_utc": (issued - timedelta(hours=2)).isoformat(),
         "captured_at_utc": (issued - timedelta(minutes=60)).isoformat(),
         "currencies": list(CURRENCIES)},
        {"state": "LAB_SYNTHETIC_EVIDENCE", "evidence_id": "usd-cpi-release",
         "kind": "MACRO_ACTUAL_RELEASED", "source": "Sintetico-lab",
         "currency": "USD", "actual": 2.0,
         "released_at_utc": (issued - timedelta(minutes=90)).isoformat(),
         "data_as_of_utc": (issued - timedelta(minutes=90)).isoformat(),
         "captured_at_utc": (issued - timedelta(minutes=55)).isoformat()},
        {"state": "LAB_SYNTHETIC_EVIDENCE", "evidence_id": "scheduled-usd",
         "kind": "MACRO_SCHEDULE_ONLY", "source": "Sintetico-lab",
         "released_at_utc": (issued + timedelta(hours=2)).isoformat(),
         "data_as_of_utc": (issued - timedelta(minutes=90)).isoformat(),
         "captured_at_utc": (issued - timedelta(minutes=75)).isoformat()},
    ]
    session = {
        "batch": {"schema": BRIDGE, "state": "LAB_SYNTHETIC_ISSUED",
                  "batch_key": key, "issued_at_utc": issued.isoformat(),
                  "method_id": FIXED_METHOD, "forecasts": forecasts},
        "evidences": evidence,
        "macro_vetoes": [{
            "state": "LAB_SYNTHETIC_MACRO_VETO",
            "policy_id": VETO_POLICY_ID,
            "forecast_id": f"{key}-D1-USDJPY",
            "decided_at_utc": issued.isoformat(),
            "evidence_ids": ["usd-cpi-release"],
            "rationale": "Hipotese macro contraria o lado de USD/JPY",
            "trade_authorized": False,
        }] if veto else [],
    }
    seal(session)
    return session


def seal(session):
    issue = datetime.fromisoformat(session["batch"]["issued_at_utc"])
    output = freeze_daily_bias_observation_lab(
        session["batch"], session["evidences"], checked_at=issue,
        macro_vetoes=session["macro_vetoes"],
    )
    if output["state"] != "LAB_FROZEN_SYNTHETIC_OBSERVATION":
        raise AssertionError("Fixture precommit failed: " + output["reason"])
    session["precommitted_observation_digest"] = output["frozen_observation_digest"]
    return session


def settlement(row, bearish=False):
    issue = datetime.fromisoformat(row["issued_at_utc"])
    entry = issue + timedelta(days=1)
    exit_at = entry + timedelta(days=LENGTHS[row["horizon"]])
    move = -30 if bearish else 20
    return {
        "forecast_id": row["forecast_id"],
        "state": "LAB_SYNTHETIC_SPOT_OUTCOME",
        "pair": row["pair"], "entry_at_utc": entry.isoformat(),
        "exit_at_utc": exit_at.isoformat(), "entry_price": 100.0,
        "exit_price": 100.0 * exp(move / 10000),
    }


def fixture():
    sessions = [
        observation(day, veto=(day == TEST[0])) for day in TRAIN + TEST
    ]
    outcomes = [
        settlement(row, bearish=(
            session["batch"]["issued_at_utc"].startswith(TEST[0])
            and row["pair"] == USDJPY and row["horizon"] == "D1"
        ))
        for session in sessions for row in session["batch"]["forecasts"]
    ]
    return sessions, outcomes


def evaluate(sessions, outcomes, **kwargs):
    return compare_frozen_macro_veto_lab(
        sessions, outcomes, split_at=SPLIT, evaluated_at=NOW,
        min_train=3, min_test=3, min_test_days=3, **kwargs,
    )


class MacroVetoAblationTests(unittest.TestCase):
    def test_exact_future_outcomes_and_oos_reused_on_two_methods(self):
        sessions, outcomes = fixture()
        result = evaluate(sessions, outcomes)
        self.assertEqual(result["state"], "LAB_SYNTHETIC_PAIRED_ABLATION")
        self.assertEqual(result["observed_sessions"], 7)
        self.assertEqual(result["baseline_predictions"], 588)
        self.assertEqual(result["macro_vetoed_all_periods"], 1)
        self.assertEqual(result["baseline_oos"]["holdout_rows"],
                         result["macro_gate_oos"]["holdout_rows"])
        self.assertEqual(result["baseline_oos"]["fixed_method_id"], FIXED_METHOD)
        self.assertEqual(result["macro_gate_oos"]["fixed_method_id"], MACRO_METHOD)

    def test_macro_veto_selects_but_does_not_improve_matched_direction(self):
        sessions, outcomes = fixture()
        result = evaluate(sessions, outcomes)
        base = result["baseline_oos"]["pair_metrics"][USDJPY]["D1"]
        gated = result["macro_gate_oos"]["pair_metrics"][USDJPY]["D1"]
        pair = result["paired_holdout"]["D1"][USDJPY]
        self.assertEqual(base["directional_hit_rate_pct"], 75.0)
        self.assertEqual(gated["directional_hit_rate_pct"], 100.0)
        self.assertEqual(pair["macro_gate_directional"], 3)
        self.assertEqual(pair["macro_vetoed_test_rows"], 1)
        self.assertEqual(pair["test_coverage_change_pp"], -25.0)
        self.assertEqual(pair["matched_retained_hit_rate_pct"], 100.0)
        self.assertEqual(pair["baseline_on_exact_retained_sample_pct"], 100.0)
        self.assertFalse(result["accuracy_improvement_proven"])
        self.assertTrue(result["macro_vetoes_bound_to_frozen_digest"])
        self.assertFalse(result["independent_custody_verified"])
        self.assertFalse(pair["statistical_uplift_proven"])

    def test_no_veto_means_same_forecasts_no_fake_macro_effect(self):
        sessions, outcomes = fixture()
        for session in sessions:
            session["macro_vetoes"] = []
            seal(session)  # Construct a distinct synthetic precommitted experiment.
        result = evaluate(sessions, outcomes)
        self.assertEqual(result["macro_vetoed_all_periods"], 0)
        self.assertEqual(result["baseline_oos"]["metrics"]["D1"],
                         result["macro_gate_oos"]["metrics"]["D1"])

    def test_unrelated_pairs_and_long_horizons_remain_unmodified(self):
        sessions, outcomes = fixture()
        result = evaluate(sessions, outcomes)
        self.assertEqual(result["paired_holdout"]["W1"][USDJPY]["macro_vetoed_test_rows"], 0)
        self.assertEqual(result["paired_holdout"]["MN1"][USDJPY]["macro_vetoed_test_rows"], 0)
        self.assertEqual(result["paired_holdout"]["D1"]["EUR/USD"]["macro_vetoed_test_rows"], 0)
        self.assertEqual(result["paired_holdout"]["D1"][USDJPY]["macro_direction_flips"], 0)

    def test_never_assert_real_macro_market_or_profitability_evidence(self):
        sessions, outcomes = fixture()
        result = evaluate(sessions, outcomes)
        for flag in ("real_point_in_time_proven", "actual_macro_effect_proven",
                     "accuracy_improvement_proven", "profitability_proven",
                     "trade_authorized", "worker_enabled", "scheduler_enabled"):
            self.assertFalse(result[flag], flag)
        self.assertFalse(result["baseline_oos"]["oos_proven"])
        self.assertFalse(result["macro_gate_oos"]["historical_data_verified"])

    def test_changing_precommitted_veto_after_issue_is_refused(self):
        sessions, outcomes = fixture()
        sessions[3]["macro_vetoes"] = []
        result = evaluate(sessions, outcomes)
        self.assertEqual(result["state"], "LAB_REJECTED_ABLATION")
        self.assertIn("predeclared", result["reason"])

    def test_rewriting_macro_release_after_precommit_is_refused(self):
        sessions, outcomes = fixture()
        sessions[3]["evidences"][1]["actual"] = 5.0
        result = evaluate(sessions, outcomes)
        self.assertEqual(result["state"], "LAB_REJECTED_ABLATION")
        self.assertIn("predeclared", result["reason"])

    def test_veto_policy_id_must_be_fixed_in_original_frozen_plan(self):
        sessions, outcomes = fixture()
        sessions[3]["macro_vetoes"][0]["policy_id"] = "POST_HOC_POLICY_V2"
        self.assertEqual(evaluate(sessions, outcomes)["state"], "LAB_REJECTED_ABLATION")

    def test_forged_content_hash_does_not_match_frozen_plan(self):
        sessions, outcomes = fixture()
        sessions[3]["precommitted_observation_digest"] = "0" * 64
        result = evaluate(sessions, outcomes)
        self.assertEqual(result["state"], "LAB_REJECTED_ABLATION")
        self.assertIn("predeclared", result["reason"])

    def test_missing_precommit_digest_refuses_comparison(self):
        sessions, outcomes = fixture()
        del sessions[3]["precommitted_observation_digest"]
        result = evaluate(sessions, outcomes)
        self.assertEqual(result["state"], "LAB_REJECTED_ABLATION")
        self.assertIn("predeclared", result["reason"])

    def test_precommitted_plan_does_not_create_trusted_timestamp(self):
        sessions, outcomes = fixture()
        result = evaluate(sessions, outcomes)
        self.assertEqual(result["predeclared_veto_policy_lab"], VETO_POLICY_ID)
        self.assertTrue(result["macro_vetoes_bound_to_frozen_digest"])
        self.assertFalse(result["real_point_in_time_proven"])
        self.assertFalse(result["independent_custody_verified"])
        self.assertFalse(result["actual_macro_effect_proven"])

    def test_veto_cannot_reference_future_scheduled_actual(self):
        sessions, outcomes = fixture()
        veto = sessions[3]["macro_vetoes"][0]
        veto["evidence_ids"] = ["scheduled-usd"]
        result = evaluate(sessions, outcomes)
        self.assertEqual(result["state"], "LAB_REJECTED_ABLATION")

    def test_veto_requires_related_currency_from_released_event(self):
        sessions, outcomes = fixture()
        sessions[3]["evidences"][1]["currency"] = "CHF"
        self.assertEqual(evaluate(sessions, outcomes)["state"], "LAB_REJECTED_ABLATION")

    def test_veto_requires_sourced_macro_not_g8_strength(self):
        sessions, outcomes = fixture()
        sessions[3]["macro_vetoes"][0]["evidence_ids"] = ["g8-ref"]
        self.assertEqual(evaluate(sessions, outcomes)["state"], "LAB_REJECTED_ABLATION")

    def test_veto_rejects_postcutoff_event_capture(self):
        sessions, outcomes = fixture()
        issued = datetime.fromisoformat(sessions[3]["batch"]["issued_at_utc"])
        sessions[3]["evidences"][1]["captured_at_utc"] = (
            issued + timedelta(seconds=1)).isoformat()
        self.assertEqual(evaluate(sessions, outcomes)["state"], "LAB_REJECTED_ABLATION")

    def test_veto_precommit_timestamp_must_equal_baseline_cutoff(self):
        sessions, outcomes = fixture()
        veto = sessions[3]["macro_vetoes"][0]
        veto["decided_at_utc"] = (
            datetime.fromisoformat(veto["decided_at_utc"]) + timedelta(minutes=1)
        ).isoformat()
        self.assertEqual(evaluate(sessions, outcomes)["state"], "LAB_REJECTED_ABLATION")

    def test_veto_can_never_inject_after_outcome_direction(self):
        sessions, outcomes = fixture()
        sessions[3]["macro_vetoes"][0]["new_bias"] = "BAIXA"
        self.assertEqual(evaluate(sessions, outcomes)["state"], "LAB_REJECTED_ABLATION")

    def test_veto_cannot_change_weekly_or_monthly_bias(self):
        sessions, outcomes = fixture()
        veto = sessions[3]["macro_vetoes"][0]
        veto["forecast_id"] = veto["forecast_id"].replace("-D1-", "-W1-")
        self.assertEqual(evaluate(sessions, outcomes)["state"], "LAB_REJECTED_ABLATION")

    def test_veto_does_not_apply_to_neutral_baseline(self):
        sessions, outcomes = fixture()
        row = next(x for x in sessions[3]["batch"]["forecasts"]
                   if x["forecast_id"].endswith("-D1-USDJPY"))
        row["bias"] = "NEUTRO"
        self.assertEqual(evaluate(sessions, outcomes)["state"], "LAB_REJECTED_ABLATION")

    def test_duplicate_veto_rejected_without_cherry_pick(self):
        sessions, outcomes = fixture()
        sessions[3]["macro_vetoes"].append(copy.deepcopy(sessions[3]["macro_vetoes"][0]))
        self.assertEqual(evaluate(sessions, outcomes)["state"], "LAB_REJECTED_ABLATION")

    def test_missing_outcome_rejects_both_evaluations(self):
        sessions, outcomes = fixture()
        outcomes.pop()
        result = evaluate(sessions, outcomes)
        self.assertEqual(result["state"], "LAB_REJECTED_ABLATION")
        self.assertIsNone(result["baseline_oos"])
        self.assertIsNone(result["macro_gate_oos"])

    def test_future_outcome_rejected_for_both_methods(self):
        sessions, outcomes = fixture()
        outcomes[0]["exit_at_utc"] = "2026-11-10T00:00:00+00:00"
        self.assertEqual(evaluate(sessions, outcomes)["state"], "LAB_REJECTED_ABLATION")

    def test_out_of_order_or_repeated_sessions_refused(self):
        sessions, outcomes = fixture()
        self.assertEqual(evaluate(list(reversed(sessions)), outcomes)["state"],
                         "LAB_REJECTED_ABLATION")
        duplicated = sessions + [copy.deepcopy(sessions[-1])]
        self.assertEqual(evaluate(duplicated, outcomes)["state"],
                         "LAB_REJECTED_ABLATION")

    def test_bad_research_freeze_or_missing_source_refused(self):
        sessions, outcomes = fixture()
        sessions[3]["evidences"] = sessions[3]["evidences"][1:]
        self.assertEqual(evaluate(sessions, outcomes)["state"], "LAB_REJECTED_ABLATION")
        sessions, outcomes = fixture()
        sessions[3]["batch"]["forecasts"].pop()
        self.assertEqual(evaluate(sessions, outcomes)["state"], "LAB_REJECTED_ABLATION")

    def test_insufficient_sample_must_not_show_paired_hit_rate(self):
        sessions, outcomes = fixture()
        result = compare_frozen_macro_veto_lab(
            sessions, outcomes, split_at=SPLIT, evaluated_at=NOW,
            min_train=3, min_test=10, min_test_days=3)
        self.assertEqual(result["state"], "LAB_SYNTHETIC_PAIRED_ABLATION")
        pair = result["paired_holdout"]["D1"][USDJPY]
        self.assertIsNone(pair["matched_retained_hit_rate_pct"])
        self.assertIsNone(pair["baseline_on_exact_retained_sample_pct"])

    def test_bad_timezone_rejected_without_implicit_utc(self):
        sessions, outcomes = fixture()
        with self.assertRaises(ValueError):
            compare_frozen_macro_veto_lab(
                sessions, outcomes, split_at=datetime(2026, 8, 1),
                evaluated_at=NOW)

    def test_nonfinite_macro_observation_cannot_influence_veto(self):
        sessions, outcomes = fixture()
        sessions[3]["evidences"][1]["actual"] = float("nan")
        self.assertEqual(evaluate(sessions, outcomes)["state"], "LAB_REJECTED_ABLATION")


if __name__ == "__main__":
    unittest.main()
