"""Synthetic-only paired coverage/accuracy accounting; NO real price data."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import unittest

from atlasquant_fx_universe import OFFICIAL_PAIRS
from atlasquant_trader_regime_increment_benchmark_lab import (
    DirectionalCase, PredeclaredWindow, evaluate_regime_increment_lab as evaluate,
)

UTC = timezone.utc
NOW = datetime(2026, 11, 8, 22, tzinfo=UTC)
ANCHORS_D1 = (datetime(2024, 1, 1, tzinfo=UTC),
              datetime(2024, 4, 1, tzinfo=UTC),
              datetime(2024, 7, 1, tzinfo=UTC))
ANCHORS_W1 = (datetime(2022, 1, 3, tzinfo=UTC),
              datetime(2023, 1, 2, tzinfo=UTC),
              datetime(2024, 1, 1, tzinfo=UTC))


def make_cohort(*, asset="EUR/USD", horizon="D1", windows_count=3, per_window=40,
                keep_mod=3, correct_fn=None):
    anchors = (ANCHORS_D1 if horizon == "D1" else ANCHORS_W1)[:windows_count]
    period = timedelta(days=1 if horizon == "D1" else 7)
    windows = [PredeclaredWindow(x, x + (timedelta(days=60) if horizon == "D1"
                                            else timedelta(days=300))) for x in anchors]
    cases = []
    for w_i, anchor in enumerate(anchors):
        for i in range(per_window):
            t = anchor + i * period
            correct = (i % 3 != 0) if correct_fn is None else correct_fn(w_i, i)
            start = 100 + i / 10
            end = start + (1 if correct else -1)
            cases.append(DirectionalCase(
                opportunity_id=f"TEST_{horizon}_{w_i:02}_{i:03}",
                asset=asset, horizon=horizon, candidate_direction="ALTA",
                decided_at=t+timedelta(hours=12),
                regime_observed_at=t+timedelta(hours=11),
                target_open_at=t+period, target_close_at=t+period*2,
                actual_observed_at=t+period*2+timedelta(seconds=3),
                start_price=str(start), end_price=str(end),
                baseline_eligible=True, regime_veto=(i % keep_mod == 0),
                decision_sha256_claim="a" * 64,
                regime_source_sha256_claim="b" * 64,
                price_source_sha256_claim="c" * 64,
            ))
    return cases, [c.opportunity_id for c in cases], windows


def call(cases=None, ids=None, windows=None, *, now=NOW):
    sample = make_cohort()
    return evaluate(sample[0] if cases is None else cases,
                    expected_opportunity_ids=sample[1] if ids is None else ids,
                    predeclared_windows=sample[2] if windows is None else windows,
                    as_of_utc=now)


def eval_cohort(cohort):
    return evaluate(cohort[0], expected_opportunity_ids=cohort[1],
                    predeclared_windows=cohort[2], as_of_utc=NOW)


class RegimeIncrementTests(unittest.TestCase):
    def no_live(self, r):
        self.assertEqual(r["operational_bias"], "AGUARDAR")
        self.assertFalse(r["publishable"])
        self.assertFalse(r["trade_authorized"])
        self.assertFalse(r["live_alert_allowed"])
        self.assertFalse(r["worker_enabled"])
        self.assertFalse(r["scheduler_enabled"])
        self.assertFalse(r["point_in_time_price_vintage_authenticated"])
        self.assertFalse(r["manifest_externally_precommitted"])
        self.assertFalse(r["direction_precommitted_externally"])
        self.assertFalse(r["regime_rule_precommitted_externally"])
        self.assertFalse(r["selection_bias_ruled_out"])
        self.assertFalse(r["market_outcome_independence_verified"])
        self.assertFalse(r["multiple_testing_adjusted"])
        self.assertFalse(r["broker_calendar_verified"])
        self.assertFalse(r["costs_spread_slippage_included"])
        self.assertFalse(r["incremental_accuracy_validated"])
        self.assertFalse(r["real_market_data_loaded"])
        self.assertIsNone(r["validated_directional_accuracy"])
        self.assertIsNone(r["calibrated_direction_probability"])
        self.assertIsNone(r["fx_bias"])
        self.assertIsNone(r["index_bias"])
        self.assertTrue(r["research_only"])
        self.assertEqual((r["http_requests"], r["file_writes"], r["new_cost_brl"]), (0, 0, 0))

    def test_paired_selection_counts_matched_manifest_and_denominators(self):
        r = call()
        self.assertEqual(r["state"], "LAB_PAIRED_COMPARISON_DESCRIPTIVE_UNATTESTED_NO_GO")
        self.assertEqual(r["manifest_total"], 120)
        self.assertEqual(r["count_observed"], 120)
        self.assertEqual((r["baseline_issued"], r["filtered_issued"],
                          r["filtered_rejected"]), (120, 78, 42))
        self.assertEqual((r["baseline_correct"], r["filtered_correct"],
                          r["rejected_correct"]), (78, 78, 0))
        self.assertEqual(r["baseline_hit_rate_documentary"], 65.0)
        self.assertEqual(r["filtered_hit_rate_documentary"], 100.0)
        self.assertEqual(r["rejected_hit_rate_documentary"], 0.0)
        self.assertEqual(r["filtered_coverage_vs_baseline_documentary"], 65.0)
        self.assertEqual(r["hit_rate_delta_percentage_points_documentary"], 35.0)
        self.assertTrue(r["complete_declared_manifest_checked"])
        self.assertEqual(len(r["windows"]), 3)
        self.no_live(r)

    def test_reversing_outcome_does_not_rewrite_baseline_or_filter(self):
        cohort = make_cohort(correct_fn=lambda w, i: (i % 3 == 0))
        r = eval_cohort(cohort)
        self.assertEqual((r["baseline_correct"], r["filtered_correct"],
                          r["rejected_correct"]), (42, 0, 42))
        self.assertEqual(r["hit_rate_delta_percentage_points_documentary"], -35.0)
        self.no_live(r)

    def test_flat_candles_count_as_misses_for_buy_and_sell(self):
        cohort = make_cohort()
        cases = list(cohort[0])
        cases[1] = replace(cases[1], end_price=cases[1].start_price)
        cases[2] = replace(cases[2], end_price=cases[2].start_price,
                           candidate_direction="BAIXA")
        r = eval_cohort((cases, cohort[1], cohort[2]))
        self.assertEqual((r["baseline_flat"], r["filtered_flat"]), (2, 2))
        self.assertEqual(r["baseline_correct"], 76)
        self.assertEqual(r["filtered_correct"], 76)
        self.no_live(r)

    def test_baseline_abstention_is_not_mistaken_for_regime_rejection(self):
        cohort = make_cohort()
        cases = [replace(c, baseline_eligible=False) if c.opportunity_id.endswith("_000")
                 else c for c in cohort[0]]
        r = eval_cohort((cases, cohort[1], cohort[2]))
        self.assertEqual(r["baseline_abstained"], 3)
        self.assertEqual(r["baseline_issued"], 117)
        self.assertEqual(r["filtered_rejected"], 39)
        self.assertEqual(r["filtered_issued"], 78)
        self.no_live(r)

    def test_no_filter_rejections_does_not_invent_improvement(self):
        cohort = make_cohort()
        cases = [replace(c, regime_veto=False) for c in cohort[0]]
        r = eval_cohort((cases, cohort[1], cohort[2]))
        self.assertEqual(r["filtered_rejected"], 0)
        self.assertIsNone(r["rejected_hit_rate_documentary"])
        self.assertEqual(r["hit_rate_delta_percentage_points_documentary"], 0.0)
        self.no_live(r)

    def test_full_veto_has_no_filtered_accuracy(self):
        cohort = make_cohort()
        cases = [replace(c, regime_veto=True) for c in cohort[0]]
        r = eval_cohort((cases, cohort[1], cohort[2]))
        self.assertEqual(r["state"], "LAB_SAMPLE_INSUFFICIENT_FOR_DESCRIPTIVE_COMPARISON")
        self.assertIsNone(r["filtered_hit_rate_documentary"])
        self.assertIsNone(r["hit_rate_delta_percentage_points_documentary"])
        self.no_live(r)

    def test_small_sample_suppresses_headline_rates(self):
        cohort = make_cohort(per_window=8)
        r = eval_cohort(cohort)
        self.assertEqual(r["state"], "LAB_SAMPLE_INSUFFICIENT_FOR_DESCRIPTIVE_COMPARISON")
        self.assertEqual(r["manifest_total"], 24)
        self.assertIsNone(r["baseline_hit_rate_documentary"])
        self.assertTrue(all(x["baseline_hit_rate_documentary"] is None
                            for x in r["windows"]))
        self.no_live(r)

    def test_low_filtered_coverage_per_window_suppresses_headline(self):
        cohort = make_cohort(keep_mod=1)
        cases = list(cohort[0]);cases[0] = replace(cases[0], regime_veto=False)
        r = eval_cohort((cases, cohort[1], cohort[2]))
        self.assertEqual(r["state"], "LAB_SAMPLE_INSUFFICIENT_FOR_DESCRIPTIVE_COMPARISON")
        self.assertIsNone(r["filtered_hit_rate_documentary"])
        self.no_live(r)

    def test_all_28_pair_ids_are_independently_admissible_no_cross_pooling(self):
        self.assertEqual(len(OFFICIAL_PAIRS), 28)
        for pair in OFFICIAL_PAIRS:
            with self.subTest(pair=pair):
                cohort = make_cohort(asset=pair)
                r = eval_cohort(cohort)
                self.assertEqual(r["asset"], pair)
                self.assertEqual(r["horizon"], "D1")
                self.no_live(r)

    def test_weekly_cadence_is_distinct_from_daily(self):
        cohort = make_cohort(horizon="W1")
        r = eval_cohort(cohort)
        self.assertEqual(r["horizon"], "W1")
        self.assertEqual(r["state"], "LAB_PAIRED_COMPARISON_DESCRIPTIVE_UNATTESTED_NO_GO")
        self.no_live(r)

    def test_missing_trial_in_declared_manifest_blocks_comparison(self):
        cohort = make_cohort()
        r = eval_cohort((cohort[0][:-1], cohort[1], cohort[2]))
        self.assertEqual(r["reason"], "MANIFEST_DOES_NOT_MATCH_ALL_CASES_NO_SILENT_OMISSION")
        self.no_live(r)

    def test_manifest_cannot_duplicate_ids(self):
        cohort = make_cohort()
        ids = list(cohort[1]);ids[-1] = ids[0]
        self.assertEqual(eval_cohort((cohort[0], ids, cohort[2]))["reason"],
                         "INVALID_OR_DUPLICATED_OPPORTUNITY_MANIFEST")

    def test_relabel_same_target_under_new_id_blocks(self):
        cohort = make_cohort()
        cases = list(cohort[0]);cases[1] = replace(cases[1],
             decided_at=cases[0].decided_at,
             regime_observed_at=cases[0].regime_observed_at,
             target_open_at=cases[0].target_open_at,
             target_close_at=cases[0].target_close_at,
             actual_observed_at=cases[0].actual_observed_at)
        self.assertEqual(eval_cohort((cases, cohort[1], cohort[2]))["reason"],
                         "DUPLICATE_TARGET_CANDLE_UNDER_DIFFERENT_ID")

    def test_duplicate_case_id_blocks(self):
        cohort = make_cohort()
        cases = list(cohort[0]);cases[1] = replace(cases[1], opportunity_id=cases[0].opportunity_id)
        self.assertEqual(eval_cohort((cases, cohort[1], cohort[2]))["reason"],
                         "DUPLICATED_OPPORTUNITY_ID")

    def test_horizons_and_assets_cannot_be_mixed(self):
        cohort = make_cohort()
        for kw in ({"asset": "GBP/USD"}, {"horizon": "W1"}, {"asset": "WIN"}):
            with self.subTest(kw=kw):
                cases=list(cohort[0]);cases[0]=replace(cases[0],**kw)
                self.assertEqual(eval_cohort((cases,cohort[1],cohort[2]))["reason"],
                                 "MIXED_PAIR_OR_HORIZON_CANNOT_POOL_RESULTS")

    def test_indices_and_inverted_noncanonical_pairs_do_not_get_forex_accuracy(self):
        for pair in ("WIN", "EURUSD", "JPY/USD"):
            with self.subTest(pair=pair):
                r=eval_cohort(make_cohort(asset=pair))
                self.assertEqual(r["reason"], "OUTSIDE_28_FX_OR_NON_D1_W1")
                self.no_live(r)

    def test_decision_after_target_open_is_a_lookahead(self):
        cohort=make_cohort();cases=list(cohort[0]);cases[0]=replace(cases[0],
                  decided_at=cases[0].target_open_at)
        self.assertEqual(eval_cohort((cases,cohort[1],cohort[2]))["reason"],
                         "POST_EVENT_OR_LOOKAHEAD_OR_INVALID_TARGET_WINDOW")

    def test_regime_observed_after_decision_is_a_lookahead(self):
        cohort=make_cohort();cases=list(cohort[0]);cases[0]=replace(cases[0],
                  regime_observed_at=cases[0].decided_at+timedelta(seconds=1))
        self.assertEqual(eval_cohort((cases,cohort[1],cohort[2]))["reason"],
                         "POST_EVENT_OR_LOOKAHEAD_OR_INVALID_TARGET_WINDOW")

    def test_actual_observed_before_close_is_a_lookahead(self):
        cohort=make_cohort();cases=list(cohort[0]);cases[0]=replace(cases[0],
                  actual_observed_at=cases[0].target_close_at-timedelta(seconds=1))
        self.assertEqual(eval_cohort((cases,cohort[1],cohort[2]))["reason"],
                         "POST_EVENT_OR_LOOKAHEAD_OR_INVALID_TARGET_WINDOW")

    def test_future_actual_at_asof_is_invalid(self):
        cohort=make_cohort();cases=list(cohort[0]);cases[0]=replace(cases[0],
                  actual_observed_at=NOW+timedelta(seconds=1))
        self.assertEqual(eval_cohort((cases,cohort[1],cohort[2]))["reason"],
                         "POST_EVENT_OR_LOOKAHEAD_OR_INVALID_TARGET_WINDOW")

    def test_naive_clock_and_invalid_cadence_fail_closed(self):
        cohort=make_cohort();cases=list(cohort[0]);cases[0]=replace(cases[0],
                  decided_at=cases[0].decided_at.replace(tzinfo=None))
        self.assertEqual(eval_cohort((cases,cohort[1],cohort[2]))["reason"],
                         "INVALID_PAIR_HORIZON_SIDE_OR_CLOCK")
        cases=list(cohort[0]);cases[0]=replace(cases[0],
                  target_close_at=cases[0].target_close_at+timedelta(days=1))
        self.assertEqual(eval_cohort((cases,cohort[1],cohort[2]))["reason"],
                         "POST_EVENT_OR_LOOKAHEAD_OR_INVALID_TARGET_WINDOW")

    def test_wrong_hash_does_not_count_as_authentic(self):
        cohort=make_cohort();cases=list(cohort[0]);cases[0]=replace(cases[0],
                  price_source_sha256_claim="notsha")
        self.assertEqual(eval_cohort((cases,cohort[1],cohort[2]))["reason"],
                         "INVALID_SOURCE_HASH_CLAIMS")

    def test_bad_prices_nan_negative_or_nonstrings_are_rejected(self):
        cohort=make_cohort()
        for val in ("NaN","Infinity","0","-1","1e1000",True,3.5,None):
            with self.subTest(val=val):
                cases=list(cohort[0]);cases[0]=replace(cases[0],end_price=val)
                self.assertEqual(eval_cohort((cases,cohort[1],cohort[2]))["reason"],
                                 "INVALID_PRICE_OR_NONFINITE_OUTCOME")

    def test_target_outside_predeclared_window_fails(self):
        cohort=make_cohort();cases=list(cohort[0]);cases[0]=replace(cases[0],
                  decided_at=datetime(2025,1,1,12,tzinfo=UTC),
                  regime_observed_at=datetime(2025,1,1,11,tzinfo=UTC),
                  target_open_at=datetime(2025,1,2,tzinfo=UTC),
                  target_close_at=datetime(2025,1,3,tzinfo=UTC),
                  actual_observed_at=datetime(2025,1,3,1,tzinfo=UTC))
        self.assertEqual(eval_cohort((cases,cohort[1],cohort[2]))["reason"],
                         "OPPORTUNITY_OUTSIDE_PREDECLARED_WINDOW")

    def test_windows_must_be_predeclared_nonoverlapping_sorted(self):
        cohort=make_cohort();win=list(cohort[2]);win[1]=PredeclaredWindow(win[0].start_at+timedelta(days=1),win[1].end_at)
        self.assertEqual(eval_cohort((cohort[0],cohort[1],win))["reason"],
                         "INVALID_OR_OVERLAPPING_OOS_WINDOWS")

    def test_no_one_or_two_windows_for_oos_comparison(self):
        cohort=make_cohort(windows_count=2)
        self.assertEqual(eval_cohort(cohort)["reason"],"INVALID_INPUT_SCHEMA_OR_CLOCK")

    def test_invalid_nonbool_veto_and_baseline_rejected(self):
        cohort=make_cohort()
        for param in ("regime_veto", "baseline_eligible"):
            with self.subTest(param=param):
                cases=list(cohort[0]);cases[0]=replace(cases[0],**{param:1})
                self.assertEqual(eval_cohort((cases,cohort[1],cohort[2]))["reason"],
                                 "INVALID_PAIR_HORIZON_SIDE_OR_CLOCK")

    def test_all_sell_hypotheses_correct_when_target_prices_fall(self):
        cohort = make_cohort(correct_fn=lambda w, i: False)
        cases = [replace(c, candidate_direction="BAIXA") for c in cohort[0]]
        r = eval_cohort((cases, cohort[1], cohort[2]))
        self.assertEqual(r["baseline_hit_rate_documentary"], 100.0)
        self.assertEqual(r["filtered_hit_rate_documentary"], 100.0)
        self.assertEqual(r["hit_rate_delta_percentage_points_documentary"], 0.0)
        self.no_live(r)

    def test_neutral_direction_is_not_relabelled_as_a_hit(self):
        cohort = make_cohort()
        cases = list(cohort[0]);cases[0] = replace(cases[0], candidate_direction="NEUTRO")
        self.assertEqual(eval_cohort((cases,cohort[1],cohort[2]))["reason"],
                         "INVALID_PAIR_HORIZON_SIDE_OR_CLOCK")

    def test_missing_filter_result_is_not_assumed_no_veto(self):
        cohort = make_cohort()
        cases = list(cohort[0]);cases[0] = replace(cases[0], regime_veto=None)
        self.assertEqual(eval_cohort((cases,cohort[1],cohort[2]))["reason"],
                         "INVALID_PAIR_HORIZON_SIDE_OR_CLOCK")

    def test_empty_and_oversize_cohorts_fail_closed(self):
        cohort=make_cohort()
        self.assertEqual(eval_cohort(([],[],cohort[2]))["reason"],
                         "INVALID_OR_DUPLICATED_OPPORTUNITY_MANIFEST")
        self.assertEqual(eval_cohort((cohort[0],cohort[1]*25,cohort[2]))["reason"],
                         "INVALID_INPUT_SCHEMA_OR_CLOCK")


    def test_weekly_dst_boundary_cannot_enter_paired_accuracy(self):
        cohort = make_cohort(horizon="W1")
        cases = list(cohort[0])
        opened = datetime(2024, 3, 3, 22, tzinfo=UTC)
        cases[0] = replace(cases[0],
                           target_open_at=opened,
                           target_close_at=opened+timedelta(days=7),
                           actual_observed_at=opened+timedelta(days=7, seconds=2))
        result = eval_cohort((cases, cohort[1], cohort[2]))
        self.assertEqual(result["reason"],
                         "W1_NY17_DST_CLOSE_REQUIRES_BROKER_VERIFICATION")
        self.assertIsNone(result["validated_directional_accuracy"])
        self.no_live(result)


if __name__ == "__main__":
    unittest.main()
