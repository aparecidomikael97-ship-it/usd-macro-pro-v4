"""Synthetic-only rare-bias policy experiments; no claimed market edge."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import unittest

from atlasquant_trader_selective_bias_gate_lab import (
    BiasObservation, HoldoutWindow, LastAlert, SelectiveAuditClaims,
    assess_selective_bias_lab as assess,
)


UTC = timezone.utc
NOW = datetime(2026, 11, 9, 12, tzinfo=UTC)
EVAL = NOW - timedelta(minutes=5)
ALL_CLAIMED = SelectiveAuditClaims(True, True, True, True, True, True)
HASH = "a" * 64


def observation(*, asset="EUR/USD", horizon="D1", when=EVAL,
                side="ALTA", weekly=None, score=8.0, marker=HASH):
    return BiasObservation(
        asset=asset, horizon=horizon, evaluated_at=when,
        weekly=side if weekly is None else weekly, daily=side,
        grade_0_to_10=score,
        macro_captured_at=when - timedelta(hours=1),
        snapshot_sha256=marker,
    )


def holdout(*, hits=38, count=40, asset="EUR/USD", horizon="D1", direction="ALTA"):
    return [
        HoldoutWindow(asset, horizon, direction,
                      datetime(2024, 1 + 2 * i, 1, tzinfo=UTC),
                      datetime(2024, 2 + 2 * i, 15, tzinfo=UTC),
                      count, hits)
        for i in range(3)
    ]


def confirm(candidate=None):
    candidate = candidate or observation()
    return [replace(candidate, evaluated_at=EVAL - timedelta(minutes=30),
                    macro_captured_at=EVAL - timedelta(hours=1),
                    snapshot_sha256="b" * 64)]


def reversed_confirm(candidate):
    return [
        replace(candidate, evaluated_at=EVAL - timedelta(minutes=60),
                macro_captured_at=EVAL - timedelta(hours=2),
                snapshot_sha256="c" * 64),
        replace(candidate, evaluated_at=EVAL - timedelta(minutes=30),
                macro_captured_at=EVAL - timedelta(hours=1),
                snapshot_sha256="b" * 64),
    ]


class RareBiasGateTests(unittest.TestCase):
    def case(self, candidate=None, previous=None, windows=None,
             claims=ALL_CLAIMED, **opts):
        candidate = candidate or observation()
        return assess(candidate, confirm(candidate) if previous is None else previous,
                      holdout(asset=candidate.asset, horizon=candidate.horizon,
                              direction=candidate.daily) if windows is None else windows,
                      claims, now=NOW, **opts)

    def never_operational(self, result):
        self.assertEqual(result["operational_bias"], "AGUARDAR")
        self.assertFalse(result["grade_is_probability"])
        self.assertFalse(result["score_0_to_10_certified"])
        self.assertIsNone(result["calibrated_direction_probability"])
        self.assertFalse(result["source_and_trial_claims_independently_verified_by_this_module"])
        self.assertFalse(result["live_alert_allowed"])
        self.assertFalse(result["publishable"])
        self.assertFalse(result["trade_authorized"])
        self.assertTrue(result["research_only"])
        self.assertFalse(result["scheduler_enabled"])
        self.assertFalse(result["worker_enabled"])
        self.assertEqual(result["new_cost_brl"], 0)

    def test_two_separate_confirmations_and_high_synthetic_oos_remain_research(self):
        result = self.case()
        self.assertEqual(result["state"], "LAB_INTERNAL_RESEARCH_CANDIDATE_NOT_LIVE")
        self.assertEqual(result["research_candidate_direction"], "ALTA")
        self.assertGreaterEqual(result["observed_holdout_wilson95_lower"], 0.8)
        self.assertEqual(result["history_samples"], 120)
        self.never_operational(result)

    def test_10_out_of_10_grade_does_not_replace_missing_provenance(self):
        claims = replace(ALL_CLAIMED, macro_originals_and_pair_comparison_witnessed=False)
        result = self.case(candidate=observation(score=10), claims=claims)
        self.assertEqual(result["reason"], "INDEPENDENT_MACRO_OOS_OR_RIGHTS_PROOF_MISSING")
        self.assertIsNone(result["research_candidate_direction"])
        self.never_operational(result)

    def test_score_below_6_is_abstention(self):
        result = self.case(candidate=observation(score=5.9))
        self.assertEqual(result["reason"], "GRADE_BELOW_RESEARCH_SELECTION_THRESHOLD")
        self.never_operational(result)

    def test_weekly_daily_disagreement_and_neutral_abstain(self):
        for candidate, reason in ((observation(weekly="BAIXA"), "W1_D1_CONFLICT"),
                                  (observation(side="NEUTRO"), "NO_W1_D1_DIRECTION")):
            with self.subTest(reason=reason):
                result = self.case(candidate=candidate)
                self.assertEqual(result["reason"], reason)
                self.never_operational(result)

    def test_future_or_stale_observation_fails(self):
        for time in (NOW + timedelta(seconds=1), NOW - timedelta(hours=7)):
            result = self.case(candidate=observation(when=time))
            self.assertEqual(result["reason"], "INVALID_STALE_OR_FUTURE_CANDIDATE")

    def test_macro_capture_after_evaluation_fails_even_with_good_grade(self):
        candidate = replace(observation(), macro_captured_at=NOW)
        self.assertEqual(self.case(candidate=candidate)["reason"],
                         "INVALID_STALE_OR_FUTURE_CANDIDATE")

    def test_only_known_forex_and_index_futures_names(self):
        for asset in ("WIN", "WDO", "US500", "NAS100", "US30", "GBP/JPY"):
            with self.subTest(asset=asset):
                candidate = observation(asset=asset)
                result = self.case(candidate=candidate)
                self.assertEqual(result["state"], "LAB_INTERNAL_RESEARCH_CANDIDATE_NOT_LIVE")
                self.never_operational(result)
        for asset in ("", "BTC/USDT", "EURUSD", "UNKNOWN"):
            self.assertEqual(self.case(candidate=observation(asset=asset))["state"], "LAB_ABSTAIN")

    def test_high_impact_event_blackout_before_and_after_release(self):
        for minutes in (-20, 10, 30):
            with self.subTest(minutes=minutes):
                result = self.case(high_impact_events=[NOW + timedelta(minutes=minutes)])
                self.assertEqual(result["reason"], "HIGH_IMPACT_NEWS_BLACKOUT")
                self.never_operational(result)

    def test_official_event_actual_pending_blocks_even_after_blackout(self):
        result = self.case(unverified_event_actual_pending=True)
        self.assertEqual(result["reason"], "EVENT_ACTUAL_NOT_VERIFIED")

    def test_macro_snapshot_before_just_released_event_is_not_reused(self):
        event = NOW - timedelta(minutes=45)
        result = self.case(high_impact_events=[event])
        self.assertEqual(result["reason"], "MACRO_CONTEXT_PREDATES_HIGH_IMPACT_RELEASE")
        self.never_operational(result)

    def test_one_confirmation_not_enough_when_reversing_previous_alert(self):
        last = LastAlert("EUR/USD", "D1", NOW - timedelta(hours=5), "BAIXA")
        result = self.case(last_alert=last, reversal_catalyst_claimed=True)
        self.assertEqual(result["reason"], "INSUFFICIENT_DISTINCT_CONFIRMATIONS")

    def test_reversal_requires_catalyst_and_more_separate_confirmations(self):
        candidate = observation()
        last = LastAlert("EUR/USD", "D1", NOW - timedelta(hours=5), "BAIXA")
        result = self.case(candidate=candidate, previous=reversed_confirm(candidate),
                           last_alert=last)
        self.assertEqual(result["reason"], "REVERSAL_WITHOUT_MACRO_CATALYST")
        permitted_research = self.case(
            candidate=candidate, previous=reversed_confirm(candidate),
            last_alert=last, reversal_catalyst_claimed=True)
        self.assertEqual(permitted_research["state"], "LAB_INTERNAL_RESEARCH_CANDIDATE_NOT_LIVE")
        self.never_operational(permitted_research)

    def test_reversal_cooldown_is_not_a_micro_noise_flip(self):
        last = LastAlert("EUR/USD", "D1", NOW - timedelta(hours=1), "BAIXA")
        result = self.case(last_alert=last, reversal_catalyst_claimed=True)
        self.assertEqual(result["reason"], "REVERSAL_COOLDOWN")

    def test_identical_direction_not_alerted_repeatedly(self):
        last = LastAlert("EUR/USD", "D1", NOW - timedelta(hours=10), "ALTA")
        result = self.case(last_alert=last)
        self.assertEqual(result["reason"], "REPEATED_DIRECTION_ALREADY_PUBLISHED")

    def test_alert_for_other_asset_cannot_be_reused(self):
        last = LastAlert("GBP/USD", "D1", NOW - timedelta(hours=10), "ALTA")
        result = self.case(last_alert=last)
        self.assertEqual(result["reason"], "INVALID_LAST_ALERT")

    def test_same_snapshot_hash_is_not_independent_confirmation(self):
        candidate = observation()
        copied = replace(candidate, evaluated_at=EVAL - timedelta(minutes=30))
        result = self.case(candidate=candidate, previous=[copied])
        self.assertEqual(result["reason"], "CONFLICTING_OR_REUSED_CONFIRMATION")

    def test_simultaneous_or_too_close_confirmations_rejected(self):
        candidate = observation()
        prior = replace(candidate, evaluated_at=EVAL - timedelta(minutes=1),
                        snapshot_sha256="b" * 64)
        result = self.case(candidate=candidate, previous=[prior])
        self.assertEqual(result["reason"], "CONFIRMATIONS_NOT_SEPARATED_IN_TIME")

    def test_low_oos_wilson_lower_bound_abstains_even_if_hit_rate_80(self):
        result = self.case(windows=holdout(hits=32))
        self.assertEqual(result["reason"], "OOS_LOWER_BOUND_BELOW_RESEARCH_GOAL")
        self.assertAlmostEqual(result["observed_holdout_hit_rate"], 0.8)
        self.assertLess(result["observed_holdout_wilson95_lower"], 0.8)
        self.never_operational(result)

    def test_oos_fewer_than_three_windows_or_100_samples_abstains(self):
        self.assertEqual(self.case(windows=holdout()[:2])["reason"], "INSUFFICIENT_OOS_WINDOWS")
        self.assertEqual(self.case(windows=holdout(count=30, hits=29))["reason"],
                         "INSUFFICIENT_OOS_SAMPLE")

    def test_overlapping_oos_windows_rejected(self):
        windows = holdout()
        windows[1] = replace(windows[1], start_at=windows[0].end_at)
        self.assertEqual(self.case(windows=windows)["reason"], "INVALID_OR_LEAKING_OOS_WINDOW")

    def test_training_on_future_outcomes_rejected(self):
        windows = holdout()
        windows[2] = replace(windows[2], end_at=NOW + timedelta(days=1))
        self.assertEqual(self.case(windows=windows)["reason"], "INVALID_OR_LEAKING_OOS_WINDOW")

    def test_wrong_oos_target_is_not_directional_validation(self):
        windows = holdout()
        windows[2] = replace(windows[2], label="CPI_SURPRISE_SIGN")
        self.assertEqual(self.case(windows=windows)["reason"], "INVALID_OR_LEAKING_OOS_WINDOW")

    def test_oos_cannot_pool_other_assets_horizons_or_direction(self):
        for mutation in ({"asset": "GBP/USD"}, {"horizon": "W1"}, {"direction": "BAIXA"}):
            with self.subTest(mutation=mutation):
                windows = holdout()
                windows[2] = replace(windows[2], **mutation)
                result = self.case(windows=windows)
                self.assertEqual(result["reason"], "INVALID_OR_LEAKING_OOS_WINDOW")
                self.never_operational(result)

    def test_boolean_counts_or_invalid_score_fail_closed(self):
        windows = holdout()
        windows[0] = replace(windows[0], resolved_predictions=True)
        self.assertEqual(self.case(windows=windows)["reason"], "INVALID_OR_LEAKING_OOS_WINDOW")
        for score in (float("nan"), float("inf"), True, 11, -1):
            self.assertEqual(self.case(candidate=observation(score=score))["reason"],
                             "INVALID_STALE_OR_FUTURE_CANDIDATE")

    def test_invalid_evidence_flag_type_or_timezone_fails(self):
        wrong = replace(ALL_CLAIMED, geopol_macro_risk_reviewed="true")
        self.assertEqual(self.case(claims=wrong)["reason"], "INVALID_AUDIT_CLAIMS")
        bad = replace(observation(), evaluated_at=EVAL.replace(tzinfo=None))
        self.assertEqual(self.case(candidate=bad)["reason"], "INVALID_STALE_OR_FUTURE_CANDIDATE")

    def test_unhashable_user_evidence_fails_closed(self):
        for mutation in ({"weekly": []}, {"daily": []}, {"horizon": []}):
            with self.subTest(mutation=mutation):
                result = self.case(candidate=replace(observation(), **mutation))
                self.assertEqual(result["reason"], "INVALID_STALE_OR_FUTURE_CANDIDATE")
        self.assertEqual(self.case(last_alert=LastAlert("EUR/USD", "D1",
                         NOW - timedelta(hours=5), []))["reason"], "INVALID_LAST_ALERT")

    def test_no_hidden_unverified_data_can_turn_into_live_probability(self):
        result = self.case()
        self.assertTrue(result["oos_numbers_are_caller_claimed_not_authenticated"])
        self.assertTrue(result["oos_wilson_not_validated_for_dependent_market_outcomes"])
        self.assertIsNone(result["calibrated_direction_probability"])
        self.never_operational(result)


if __name__ == "__main__":
    unittest.main()
