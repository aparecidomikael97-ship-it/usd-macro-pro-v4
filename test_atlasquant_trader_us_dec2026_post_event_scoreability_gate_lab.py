"""All research evidence synthetic; deliberately no validated FX forecast."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import unittest

from atlasquant_trader_us_dec2026_post_event_scoreability_gate_lab import (
    UntrustedAftermathArchiveClaim as Claim,
    audit_dec2026_scoreability_readiness_lab as audit,
)
from atlasquant_trader_us_dec2026_frozen_evaluation_protocol_lab import FROZEN_PLAN
from atlasquant_trader_us_dec2026_pre_event_consensus_custody_lab import EVENTS
from atlasquant_trader_ppi_usd_fx_forward_reaction_lab import USD_FX, WINDOWS
import test_atlasquant_trader_us_dec2026_pre_event_consensus_custody_lab as source_fixture

UTC = timezone.utc
CPI=EVENTS[0][3]
PPI=EVENTS[1][3]
BEFORE=datetime(2026,11,16,3,25,tzinfo=UTC)
LATER=datetime(2026,12,20,13,30,tzinfo=UTC)


def claim(root="US_CPI_NOV2026", *, price_delay_hours=5, actual_delay_hours=1,
          actual_sha=None, price_sha=None):
    release=CPI if root=="US_CPI_NOV2026" else PPI
    one=(actual_sha or ("a"*64 if root=="US_CPI_NOV2026" else "c"*64))
    two=(price_sha or ("b"*64 if root=="US_CPI_NOV2026" else "d"*64))
    return Claim(
        event_root=root,
        actual_original_sha256_claim=one,
        actual_locally_captured_at_utc=release+timedelta(hours=actual_delay_hours),
        price_original_sha256_claim=two,
        price_locally_captured_at_utc=release+timedelta(hours=price_delay_hours),
        price_pairs=tuple(USD_FX),
        horizons=tuple(k for k,_ in WINDOWS),
    )


def inspect(*, at=BEFORE, claims=(), sources=(), submitted=None):
    return audit(
        inspected_at_utc=at, aftermath_archive_claims=claims,
        pre_event_source_snapshots=sources, submitted_frozen_plan=submitted,
    )


class ScoreabilityReadinessTests(unittest.TestCase):
    def safety(self,r):
        self.assertEqual(r["schema"],
            "ATLASQUANT_US_DEC2026_POST_EVENT_SCOREABILITY_READINESS_LAB_V1")
        self.assertEqual(r["frozen_dec2026_economic_event_denominator"],2)
        self.assertEqual([row["event_root_id"] for row in r["event_rows"]],
                         ["US_CPI_NOV2026","US_PPI_NOV2026"])
        self.assertTrue(r["seven_correlated_crosses_are_not_seven_macro_trials"])
        self.assertTrue(r["three_price_horizons_are_not_three_independent_macro_trials"])
        self.assertTrue(r["missing_events_retained_and_no_outcome_based_selection"])
        self.assertFalse(r["source_first_seen_independently_attested"])
        self.assertFalse(r["github_witness_timestamp_independently_verified"])
        self.assertFalse(r["bls_first_print_independently_attested"])
        self.assertFalse(r["broker_prices_bid_ask_and_slippage_independently_attested"])
        self.assertFalse(r["causal_fx_reaction_identified"])
        self.assertFalse(r["publishable"])
        self.assertFalse(r["trade_authorized"])
        self.assertFalse(r["fx28_original_672_slots_changed"])
        self.assertEqual(r["operational_bias"],"AGUARDAR")
        self.assertEqual(r["pre_registered_directional_predictions"],0)
        self.assertEqual(r["independent_forecast_trials_verified"],0)
        self.assertEqual(r["out_of_sample_trials_scoreable"],0)
        self.assertIsNone(r["winner_count"])
        self.assertIsNone(r["loser_count"])
        self.assertIsNone(r["win_rate"])
        self.assertIsNone(r["calibrated_fx_probability"])
        self.assertIsNone(r["directional_usd_bias"])
        self.assertEqual((r["http_requests"],r["file_writes"],r["mt5_calls"]),(0,0,0))
        self.assertEqual(r["new_cost_brl"],0)
        for row in r["event_rows"]:
            self.assertFalse(row["forecast_precommitted_before_news"])
            self.assertFalse(row["independent_scoreable_prediction"])
            self.assertFalse(row["spreads_originals_independently_attested"])
            self.assertFalse(row["competing_news_independently_ruled_out"])

    def good(self,**kwargs):
        r=inspect(**kwargs)
        self.safety(r)
        self.assertEqual(r["state"],"LAB_DEC2026_TWO_EVENT_AFTER_EVIDENCE_RECONCILED_HARD_NO_GO")
        return r

    def blocked(self,**kwargs):
        r=inspect(**kwargs)
        self.safety(r)
        self.assertEqual(r["state"],"LAB_DEC2026_SCOREABILITY_GATE_BLOCKED_HARD_NO_GO")
        self.assertEqual(r["post_event_archive_claims_visible_count"],0)
        self.assertIsNone(r["pre_registered_plan_sha256"])
        return r

    def test_01_no_december_actuals_november_pre_event(self):
        r=self.good(at=BEFORE)
        self.assertEqual([e["status"] for e in r["event_rows"]],
            ["FUTURE_BLS_RELEASE_NO_ACTUAL_OR_PRICE_AVAILABLE"]*2)
        self.assertEqual(r["post_event_archive_claims_visible_count"],0)

    def test_02_after_both_releases_missing_archives_still_two_events(self):
        r=self.good(at=LATER)
        self.assertEqual([e["status"] for e in r["event_rows"]],
            ["NO_POST_RELEASE_ORIGINALS_SUBMITTED"]*2)
        self.assertEqual(r["frozen_dec2026_economic_event_denominator"],2)

    def test_03_one_valid_cpi_archive_claim_is_not_forecast(self):
        r=self.good(at=CPI+timedelta(hours=6), claims=(claim(),))
        self.assertEqual(r["post_event_archive_claims_visible_count"],1)
        self.assertTrue(r["event_rows"][0]["post_event_archive_claim_visible"])
        self.assertFalse(r["event_rows"][1]["post_event_archive_claim_visible"])
        self.assertEqual(r["event_rows"][0]["price_pairs_observed_claim_only"],7)
        self.assertEqual(r["event_rows"][0]["horizons_observed_claim_only"],["M15","H1","H4"])
        self.assertEqual(r["out_of_sample_trials_scoreable"],0)

    def test_04_both_realistic_archive_claims_only_two_release_roots(self):
        r=self.good(at=LATER,claims=(claim(),claim("US_PPI_NOV2026")))
        self.assertEqual(r["post_event_archive_claims_visible_count"],2)
        self.assertEqual(r["independent_forecast_trials_verified"],0)
        self.assertEqual(r["frozen_dec2026_economic_event_denominator"],2)

    def test_05_after_cpi_before_ppi_only_cpi_can_show(self):
        r=self.good(at=CPI+timedelta(days=1),claims=(
            claim(),claim("US_PPI_NOV2026"),
        ))
        self.assertEqual(r["post_event_archive_claims_visible_count"],1)
        self.assertEqual(r["event_rows"][1]["status"],
            "FUTURE_BLS_RELEASE_NO_ACTUAL_OR_PRICE_AVAILABLE")
        self.assertIsNone(r["event_rows"][1]["actual_original_sha256_local_claim"])

    def test_06_future_payload_bad_digest_does_not_leak_until_visible(self):
        c=replace(claim(),actual_original_sha256_claim="not a hash",
                  actual_locally_captured_at_utc=CPI+timedelta(hours=7))
        prior=self.good(at=BEFORE,claims=(c,))
        self.assertEqual(prior["post_event_archive_claims_visible_count"],0)
        self.assertIsNone(prior["event_rows"][0]["actual_original_sha256_local_claim"])

    def test_07_one_future_price_receipt_blocks_claim_without_hash_disclosure(self):
        c=claim()
        r=self.good(at=CPI+timedelta(hours=4),claims=(c,))
        self.assertEqual(r["event_rows"][0]["status"],
            "POST_RELEASE_ARCHIVE_NOT_YET_VISIBLE_AT_CUTOFF")
        self.assertIsNone(r["event_rows"][0]["price_archive_sha256_local_claim"])

    def test_08_exact_capture_completion_visibility_boundary(self):
        c=claim()
        early=self.good(at=c.price_locally_captured_at_utc-timedelta(microseconds=1),
                        claims=(c,))
        at=self.good(at=c.price_locally_captured_at_utc,claims=(c,))
        self.assertEqual(early["post_event_archive_claims_visible_count"],0)
        self.assertEqual(at["post_event_archive_claims_visible_count"],1)

    def test_09_actual_before_official_release_is_rejected_once_visible(self):
        c=claim(actual_delay_hours=-1)
        r=self.blocked(at=CPI+timedelta(hours=6),claims=(c,))
        self.assertEqual(r["reason"],"CLAIMED_ORIGINAL_RECEIPTS_PRICE_COHORT_OR_CLOCK_INVALID")

    def test_10_price_archive_captured_before_h4_endpoint_is_invalid(self):
        c=claim(price_delay_hours=3)
        self.blocked(at=CPI+timedelta(hours=6),claims=(c,))

    def test_11_faked_forecast_not_in_dataclass_is_injection(self):
        self.blocked(at=LATER,claims=({"forecast":"USD_UP","accuracy":100},))

    def test_12_duplicate_root_cannot_be_counted_twice(self):
        c=claim()
        self.blocked(at=LATER,claims=(c,c))

    def test_13_foreign_third_root_does_not_join_december_research(self):
        c=replace(claim(),event_root="US_CPI_SEP2026")
        self.blocked(at=LATER,claims=(c,))

    def test_14_more_than_two_claims_blocks_whole_cohort(self):
        c=claim()
        self.blocked(at=LATER,claims=(c,c,c))

    def test_15_reused_actual_original_sha_across_cpi_ppi_refused(self):
        a=claim()
        b=claim("US_PPI_NOV2026",actual_sha=a.actual_original_sha256_claim)
        self.blocked(at=LATER,claims=(a,b))

    def test_16_reused_price_sha_across_two_releases_refused(self):
        a=claim()
        b=claim("US_PPI_NOV2026",price_sha=a.price_original_sha256_claim)
        self.blocked(at=LATER,claims=(a,b))

    def test_17_actual_and_price_same_sha_is_not_two_sources(self):
        c=claim(price_sha="a"*64)
        self.blocked(at=CPI+timedelta(hours=7),claims=(c,))

    def test_18_forged_uppercase_or_short_sha_rejected(self):
        for bad in ("A"*64, "abc", "", "0"*63):
            with self.subTest(digest=bad):
                self.blocked(at=LATER,claims=(replace(claim(),
                    price_original_sha256_claim=bad),))

    def test_19_missing_fx_pairs_not_a_complete_seven_cross_archive(self):
        c=replace(claim(),price_pairs=tuple(USD_FX)[:-1])
        self.blocked(at=LATER,claims=(c,))

    def test_20_reorder_prices_does_not_silently_change_model_universe(self):
        c=claim()
        c=replace(c,price_pairs=tuple(reversed(c.price_pairs)))
        self.blocked(at=LATER,claims=(c,))

    def test_21_missing_h4_cannot_be_promoted_to_full_cohort(self):
        c=replace(claim(),horizons=("M15","H1"))
        self.blocked(at=LATER,claims=(c,))

    def test_22_duplicate_h1_horizon_and_out_of_order_fail(self):
        for horizons in (("M15","H1","H1"),("H4","H1","M15")):
            with self.subTest(horizons=horizons):
                self.blocked(at=LATER,claims=(replace(claim(),horizons=horizons),))

    def test_23_unknown_price_archive_kind_refused(self):
        c=replace(claim(),price_archive_kind="CRYPTO_FAKE_TICK_FORECAST")
        self.blocked(at=LATER,claims=(c,))

    def test_24_unknown_issuer_type_refused(self):
        c=replace(claim(),actual_archive_kind="CONSENSUS_NOT_OFFICIAL_BLS")
        self.blocked(at=LATER,claims=(c,))

    def test_25_naive_or_text_capture_datetime_not_valid(self):
        for time in (datetime(2026,12,10,14,30), "2026-12-10T14:30Z",None):
            with self.subTest(clock=time):
                self.blocked(at=LATER,claims=(replace(claim(),
                    actual_locally_captured_at_utc=time),))

    def test_26_explicit_brazil_timezone_must_convert_correctly(self):
        c=claim()
        tz=timezone(timedelta(hours=-4))
        local=replace(c,
            actual_locally_captured_at_utc=c.actual_locally_captured_at_utc.astimezone(tz),
            price_locally_captured_at_utc=c.price_locally_captured_at_utc.astimezone(tz))
        a=self.good(at=LATER,claims=(c,))
        b=self.good(at=LATER,claims=(local,))
        self.assertEqual(a,b)

    def test_27_true_spread_and_calendar_booleans_still_not_attestation(self):
        c=replace(claim(),spread_rows_present_claim_only=True,
                  competing_news_review_claim_only=True)
        r=self.good(at=LATER,claims=(c,))
        self.assertTrue(r["event_rows"][0]["post_event_archive_claim_visible"])
        self.assertFalse(r["event_rows"][0]["spreads_originals_independently_attested"])
        self.assertFalse(r["event_rows"][0]["competing_news_independently_ruled_out"])

    def test_28_bool_spread_claim_as_string_does_not_pass(self):
        c=replace(claim(),spread_rows_present_claim_only="yes")
        self.blocked(at=LATER,claims=(c,))

    def test_29_tamper_frozen_protocol_direction_blocks_every_archive(self):
        frozen=deepcopy(FROZEN_PLAN)
        frozen["event_roots"][0]["forecast_direction"]="USD_UP"
        r=self.blocked(at=LATER,claims=(claim(),),submitted=frozen)
        self.assertEqual(r["reason"],"FROZEN_PROTOCOL_OR_PRE_EVENT_CUSTODY_INVALID")

    def test_30_tamper_frozen_protocol_primary_horizon_blocks(self):
        frozen=deepcopy(FROZEN_PLAN)
        frozen["primary_descriptive_horizon"]="M15"
        self.blocked(at=LATER,claims=(claim(),),submitted=frozen)

    def test_31_untrusted_cpi_source_consensus_cannot_be_forecast(self):
        src=source_fixture.sample()
        r=self.good(at=CPI-timedelta(hours=2),sources=(src,))
        self.assertEqual(r["local_source_snapshots_visible_count"],1)
        self.assertEqual(r["post_event_archive_claims_visible_count"],0)
        self.assertEqual(r["independent_forecast_trials_verified"],0)

    def test_32_bad_source_hash_blocks_all_later_price_archive_claims(self):
        src=source_fixture.sample()
        src=replace(src,original_sha256_claim="f"*64)
        self.blocked(at=LATER,claims=(claim(),),sources=(src,))

    def test_33_all_missing_consent_price_and_model_is_not_a_loss_either(self):
        r=self.good(at=LATER)
        self.assertIsNone(r["loser_count"])
        self.assertIsNone(r["winner_count"])
        self.assertIsNone(r["win_rate"])

    def test_34_after_market_moves_cannot_promote_abstain_to_hit(self):
        r=self.good(at=PPI+timedelta(days=10),claims=(
            claim(),claim("US_PPI_NOV2026"),
        ))
        self.assertIsNone(r["directional_usd_bias"])
        self.assertFalse(r["trade_authorized"])
        self.assertEqual(r["independent_forecast_trials_verified"],0)

    def test_35_seven_pairs_times_three_horizons_remains_zero_trials(self):
        r=self.good(at=LATER,claims=(claim(),claim("US_PPI_NOV2026")))
        self.assertEqual(r["event_rows"][0]["price_pairs_observed_claim_only"],7)
        self.assertEqual(len(r["event_rows"][0]["horizons_observed_claim_only"]),3)
        self.assertEqual(r["out_of_sample_trials_scoreable"],0)

    def test_36_corrupted_evidence_at_second_event_rejects_first_too(self):
        a=claim()
        b=replace(claim("US_PPI_NOV2026"),horizons=("M15","H4"))
        r=self.blocked(at=LATER,claims=(a,b))
        self.assertIsNone(r["event_rows"][0]["actual_original_sha256_local_claim"])

    def test_37_original_plan_without_evidence_verification_fails_on_naive_cutoff(self):
        self.blocked(at=datetime(2026,12,20))

    def test_38_no_protocol_mutation_from_audit(self):
        frozen=deepcopy(FROZEN_PLAN)
        r=self.good(at=BEFORE)
        self.assertEqual(frozen,FROZEN_PLAN)
        self.assertEqual(r["frozen_dec2026_economic_event_denominator"],2)


if __name__ == "__main__":
    unittest.main()
