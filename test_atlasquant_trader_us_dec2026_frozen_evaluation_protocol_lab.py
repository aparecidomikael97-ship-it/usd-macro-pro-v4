"""Deterministic protocol pin, source-custody and no-hindsight tests only."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from unittest.mock import patch
from dataclasses import replace
import unittest

import atlasquant_trader_us_dec2026_frozen_evaluation_protocol_lab as protocol
from atlasquant_trader_us_dec2026_pre_event_consensus_custody_lab import EVENTS
import test_atlasquant_trader_us_dec2026_pre_event_consensus_custody_lab as fixture

UTC=timezone.utc
BEFORE=datetime(2026,11,16,3,15,tzinfo=UTC)
CPI=EVENTS[0][3]
PPI=EVENTS[1][3]


def review(now=BEFORE, *, snapshots=(), submitted=None):
    return protocol.inspect_frozen_dec2026_evaluation_protocol_lab(
        inspected_at_utc=now,
        source_snapshots=snapshots,
        submitted_plan=submitted,
    )


class FrozenDecemberEvaluationTests(unittest.TestCase):
    def safe(self,out):
        self.assertEqual(out["schema"],protocol.SCHEMA)
        self.assertEqual(out["frozen_economic_event_denominator"],2)
        self.assertEqual(out["frozen_event_roots"],["US_CPI_NOV2026","US_PPI_NOV2026"])
        self.assertEqual([e["event_root"] for e in out["events"]],
                         ["US_CPI_NOV2026","US_PPI_NOV2026"])
        self.assertTrue(out["descriptive_correlated_fx_observations_not_independent_predictions"])
        self.assertTrue(out["incomplete_economic_events_retained_in_denominator"])
        self.assertFalse(out["overlap_or_confounders_independently_ruled_out"])
        self.assertFalse(out["pre_event_commitment_git_timestamp_independently_authenticated"])
        self.assertFalse(out["publisher_first_seen_independently_authenticated"])
        self.assertFalse(out["broker_prices_spreads_and_slippage_authenticated"])
        self.assertFalse(out["directional_model_calibrated_and_locked"])
        self.assertFalse(out["trade_authorized"])
        self.assertFalse(out["publishable"])
        self.assertFalse(out["fx28_672_campaign_slots_modified"])
        self.assertEqual(out["operational_bias"],"AGUARDAR")
        self.assertIsNone(out["forecast_accuracy"])
        self.assertIsNone(out["forecast_probability"])
        self.assertIsNone(out["usd_direction"])
        self.assertIsNone(out["forex_trade_signal"])
        self.assertEqual(out["prospective_directional_forecasts_registered"],0)
        self.assertEqual(out["independent_economic_prediction_trials_verified"],0)
        self.assertEqual(out["independent_testable_out_of_sample_trials"],0)
        self.assertEqual((out["http_requests"],out["file_writes"],out["mt5_calls"]),(0,0,0))
        self.assertEqual(out["new_trading_cost_brl"],0)
        for e in out["events"]:
            self.assertEqual(e["pre_event_directional_research_decision"],"ABSTAIN")
            self.assertFalse(e["price_window_results_verified"])
            self.assertFalse(e["forecast_direction_verified"])
            self.assertFalse(e["scoreable_prediction"])

    def accepted(self,*args,**kwargs):
        out=review(*args,**kwargs)
        self.safe(out)
        self.assertEqual(out["state"],"LAB_DEC2026_FROZEN_DESCRIPTIVE_PROTOCOL_RECONCILED_NO_GO")
        self.assertEqual(out["frozen_plan_sha256"],protocol.PINNED_PLAN_SHA256)
        return out

    def blocked(self,*args,**kwargs):
        out=review(*args,**kwargs)
        self.safe(out)
        self.assertEqual(out["state"],"LAB_DEC2026_FROZEN_EVALUATION_PROTOCOL_BLOCKED_NO_GO")
        self.assertIsNone(out["frozen_plan_sha256"])
        self.assertEqual(out["locally_replayed_source_snapshots"],0)
        return out

    def test_01_sha256_is_exactly_pinned_before_any_event(self):
        blob=protocol.canonical_frozen_plan_bytes_lab(protocol.FROZEN_PLAN)
        self.assertEqual(sha256(blob).hexdigest(),protocol.PINNED_PLAN_SHA256)
        self.accepted()

    def test_02_two_events_and_zero_registered_predictions_before_cpi(self):
        out=self.accepted()
        self.assertEqual([x["status"] for x in out["events"]],
                         ["PRE_RELEASE_FROZEN_ABSTENTION"]*2)
        self.assertEqual(out["locally_replayed_source_snapshots"],0)

    def test_03_explicit_identical_submitted_plan_accepted(self):
        self.accepted(submitted=deepcopy(protocol.FROZEN_PLAN))

    def test_04_any_changed_forecast_direction_rejected(self):
        forged=deepcopy(protocol.FROZEN_PLAN)
        forged["event_roots"][0]["forecast_direction"]="USD_UP"
        self.blocked(submitted=forged)

    def test_05_fake_model_version_added_after_the_event_rejected(self):
        forged=deepcopy(protocol.FROZEN_PLAN)
        forged["validated_model_version"]="v100_percent"
        self.blocked(submitted=forged)

    def test_06_accuracy_claim_mutation_blocked(self):
        forged=deepcopy(protocol.FROZEN_PLAN)
        forged["accuracy_claim_allowed"]=True
        self.blocked(submitted=forged)

    def test_07_added_100_percent_win_rate_field_rejected(self):
        forged=deepcopy(protocol.FROZEN_PLAN)
        forged["reported_fx_accuracy"]="100%"
        self.blocked(submitted=forged)

    def test_08_missing_event_to_hide_failure_rejected(self):
        forged=deepcopy(protocol.FROZEN_PLAN)
        forged["event_roots"].pop()
        self.blocked(submitted=forged)

    def test_09_relabelled_september_cpi_into_december_rejected(self):
        forged=deepcopy(protocol.FROZEN_PLAN)
        forged["event_roots"][0]["root_id"]="US_CPI_SEP2026"
        self.blocked(submitted=forged)

    def test_10_cherry_pick_best_horizon_after_news_rejected(self):
        forged=deepcopy(protocol.FROZEN_PLAN)
        forged["primary_descriptive_horizon"]="M15"
        self.blocked(submitted=forged)

    def test_11_cherry_pick_one_winning_pair_rejected(self):
        forged=deepcopy(protocol.FROZEN_PLAN)
        forged["usd_fx_crosses"]=["EURUSD"]
        self.blocked(submitted=forged)

    def test_12_swapped_m15_and_h4_endpoints_rejected(self):
        forged=deepcopy(protocol.FROZEN_PLAN)
        forged["analysis_windows_minutes"]["H4"]=15
        self.blocked(submitted=forged)

    def test_13_in_place_mutation_is_caught_by_literal_sha(self):
        for field,value in (
            ("issuer","UNVERIFIED"),
            ("registered_forecasts",2),
            ("publication_or_trade_allowed",True),
            ("news_confounder_policy","ASSUME_NO_OTHER_NEWS"),
        ):
            with self.subTest(field=field):
                with patch.dict(protocol.FROZEN_PLAN,{field:value}):
                    result=self.blocked()
                self.assertEqual(result["reason"],"FROZEN_CODE_POLICY_SHA_MISMATCH")

    def test_14_naive_timestamp_cannot_pass_pre_event_validation(self):
        out=self.blocked(datetime(2026,12,9))
        self.assertEqual(out["reason"],"INVALID_RESEARCH_CUTOFF")

    def test_15_string_datetime_and_none_cannot_pass(self):
        for at in (None,"2026-12-09T10:00:00Z",123):
            with self.subTest(at=at):
                self.blocked(at)

    def test_16_cpi_already_released_ppi_still_future_no_invented_win(self):
        out=self.accepted(CPI+timedelta(hours=1))
        self.assertEqual([e["status"] for e in out["events"]],
            ["POST_RELEASE_DESCRIPTIVE_ONLY_NO_FORECAST",
             "PRE_RELEASE_FROZEN_ABSTENTION"])

    def test_17_after_both_releases_still_zero_forecasts(self):
        out=self.accepted(PPI+timedelta(days=1))
        self.assertEqual([e["status"] for e in out["events"]],
            ["POST_RELEASE_DESCRIPTIVE_ONLY_NO_FORECAST"]*2)
        self.assertEqual(out["independent_testable_out_of_sample_trials"],0)

    def test_18_cpi_two_mock_source_hashes_are_one_event(self):
        a=fixture.sample()
        b=fixture.sample(provider="TRADING_ECONOMICS")
        out=self.accepted(CPI-timedelta(hours=2),snapshots=(a,b))
        self.assertEqual(out["locally_replayed_source_snapshots"],2)
        self.assertEqual(out["events"][0]["source_snapshot_hash_count_locally_claimed_only"],2)
        self.assertEqual(out["independent_economic_prediction_trials_verified"],0)

    def test_19_ppi_two_mock_source_hashes_are_one_event(self):
        a=fixture.sample(root="US_PPI_NOV2026")
        b=fixture.sample(root="US_PPI_NOV2026",provider="TRADING_ECONOMICS")
        out=self.accepted(PPI-timedelta(hours=2),snapshots=(a,b))
        self.assertEqual(out["locally_replayed_source_snapshots"],2)
        self.assertEqual(out["events"][1]["source_snapshot_hash_count_locally_claimed_only"],2)

    def test_20_four_mock_snapshots_are_two_not_four_event_roots(self):
        docs=tuple(
            fixture.sample(root,provider)
            for root in ("US_CPI_NOV2026","US_PPI_NOV2026")
            for provider in ("TD_ECONOMICS","TRADING_ECONOMICS")
        )
        out=self.accepted(PPI-timedelta(hours=2),snapshots=docs)
        self.assertEqual(out["locally_replayed_source_snapshots"],4)
        self.assertEqual(out["frozen_economic_event_denominator"],2)
        self.assertEqual(out["independent_economic_prediction_trials_verified"],0)

    def test_21_future_document_is_invisible_at_past_cutoff(self):
        source=fixture.sample()
        out=self.accepted(source.finished_at_utc-timedelta(microseconds=1),
                          snapshots=(source,))
        self.assertEqual(out["locally_replayed_source_snapshots"],0)
        self.assertEqual(out["events"][0]["source_snapshot_hash_count_locally_claimed_only"],0)

    def test_22_bogus_past_timestamp_and_wrong_sha_blocks_whole_protocol(self):
        source=fixture.sample()
        bad=replace(source,original_sha256_claim="0"*64)
        out=self.blocked(source.finished_at_utc,snapshots=(bad,))
        self.assertEqual(out["reason"],"SOURCE_ARCHIVE_FAILED_CUSTODY_NO_PARTIAL_FORECAST")

    def test_23_one_good_one_corrupt_source_fails_all_not_partial(self):
        one=fixture.sample()
        two=fixture.sample(provider="TRADING_ECONOMICS")
        bad=replace(two,original_sha256_claim="f"*64)
        out=self.blocked(CPI-timedelta(hours=2),snapshots=(one,bad))
        self.assertEqual(out["locally_replayed_source_snapshots"],0)

    def test_24_future_source_without_numeric_consensus_never_a_forecast(self):
        one=fixture.sample()
        out=self.accepted(CPI-timedelta(hours=2),snapshots=(one,))
        self.assertEqual(out["events"][0]["source_snapshot_hash_count_locally_claimed_only"],1)
        self.assertIsNone(out["usd_direction"])
        self.assertIsNone(out["forecast_probability"])
        self.assertEqual(out["prospective_directional_forecasts_registered"],0)

    def test_25_after_event_new_source_not_backdated_into_prediction(self):
        late=fixture.sample(end=CPI+timedelta(minutes=2))
        out=self.blocked(CPI+timedelta(hours=1),snapshots=(late,))
        self.assertEqual(out["reason"],"SOURCE_ARCHIVE_FAILED_CUSTODY_NO_PARTIAL_FORECAST")

    def test_26_same_second_temporal_visibility_exact_no_round_down(self):
        one=fixture.sample(end=CPI-timedelta(days=2,microseconds=1433))
        prior=self.accepted(one.finished_at_utc-timedelta(microseconds=1),
                            snapshots=(one,))
        at=self.accepted(one.finished_at_utc,snapshots=(one,))
        self.assertEqual(prior["locally_replayed_source_snapshots"],0)
        self.assertEqual(at["locally_replayed_source_snapshots"],1)

    def test_27_absence_of_any_source_keeps_two_cpi_ppi_releases(self):
        out=self.accepted(PPI+timedelta(days=1),snapshots=())
        self.assertEqual([e["source_snapshot_hash_count_locally_claimed_only"]
                          for e in out["events"]],[0,0])
        self.assertEqual(out["frozen_economic_event_denominator"],2)

    def test_28_pre_release_freeze_is_one_hour_for_both(self):
        for i,(root,_,_,t) in enumerate(EVENTS):
            with self.subTest(root=root):
                e=protocol.FROZEN_PLAN["event_roots"][i]
                self.assertEqual(e["release_utc"],t.isoformat())
                self.assertEqual(e["latest_pre_event_freeze_utc"],
                                 (t-timedelta(hours=1)).isoformat())

    def test_29_correlation_and_cost_checks_are_never_fabricated(self):
        out=self.accepted(PPI+timedelta(days=7))
        self.assertFalse(out["broker_prices_spreads_and_slippage_authenticated"])
        self.assertFalse(out["overlap_or_confounders_independently_ruled_out"])
        self.assertIsNone(out["forecast_accuracy"])
        self.assertEqual(out["independent_testable_out_of_sample_trials"],0)


if __name__ == "__main__":
    unittest.main()
