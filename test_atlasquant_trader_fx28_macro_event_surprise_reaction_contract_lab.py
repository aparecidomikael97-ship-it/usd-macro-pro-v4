"""Pure synthetic contract QA. NOT real November PPI consensus or FX prices."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import unittest

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS, split_pair
from atlasquant_trader_fx28_macro_event_surprise_reaction_contract_lab import (
    SCHEMA, MetricIdentity, PreEventConsensus, OfficialActual,
    LocalPriceReaction, inspect_macro_event_surprise_reaction_lab as inspect,
)

UTC=timezone.utc
RELEASE=datetime(2026,11,13,13,30,tzinfo=UTC)
NOW=datetime(2026,11,13,17,45,tzinfo=UTC)
METRIC=MetricIdentity(
    "USD","US_PPI_FINAL_DEMAND","2026-10","MOM","SA","PERCENT",
)
CONSENSUS=PreEventConsensus(
    METRIC,"0.2","https://www.tradingeconomics.com/united-states/producer-prices",
    sha256(b"PRE-EVENT SYNTHETIC CONSENSUS").hexdigest(),
    RELEASE-timedelta(hours=2),RELEASE-timedelta(hours=1),
)
ACTUAL=OfficialActual(
    METRIC,"0.3","https://www.bls.gov/news.release/ppi.toc.htm",
    sha256(b"POST-RELEASE SYNTHETIC ACTUAL").hexdigest(),
    RELEASE,RELEASE,RELEASE+timedelta(minutes=3),"FIRST_PRINT_CLAIM_ONLY",
)
ROOT="US_PPI_OCT2026_TEST_ONLY"


def prices(*,horizon="M15"):
    mins={"M15":15,"H1":60,"H4":240}[horizon]
    return [
        LocalPriceReaction(
            pair,horizon,"1.2500","1.2525",
            RELEASE-timedelta(minutes=15),
            RELEASE+timedelta(minutes=mins),
            sha256(f"SYNTHETIC PRICE {pair} {horizon}".encode()).hexdigest(),
        )
        for pair in OFFICIAL_PAIRS if "USD" in split_pair(pair)
    ]


class GenericMacroSurpriseEventTests(unittest.TestCase):
    def run_event(self,**kw):
        values=dict(event_root_id=ROOT,consensus=CONSENSUS,
                    actual=ACTUAL,inspected_at_utc=NOW)
        values.update(kw)
        return inspect(**values)

    def safety(self,r):
        self.assertEqual(r["schema"],SCHEMA)
        self.assertEqual(r["operational_bias"],"AGUARDAR")
        self.assertIsNone(r["calibrated_probability"])
        self.assertIsNone(r["historical_out_of_sample_accuracy"])
        self.assertIsNone(r["predicted_currency_direction"])
        self.assertFalse(r["trade_authorized"])
        self.assertFalse(r["publishable"])
        self.assertFalse(r["live_alert_allowed"])
        self.assertFalse(r["scheduler_enabled"])
        self.assertFalse(r["issuer_first_seen_independently_authenticated"])
        self.assertFalse(r["broker_price_and_bid_ask_independently_authenticated"])
        self.assertTrue(r["seven_pair_outcomes_are_not_independent_events"])
        self.assertEqual((r["http_calls"],r["mt5_calls"],r["file_writes"]),(0,0,0))
        self.assertEqual(r["new_cost_brl"],0)
        return r

    def blocked(self,**kw):
        r=self.safety(self.run_event(**kw))
        self.assertEqual(r["state"],"LAB_FX28_MACRO_EVENT_STUDY_BLOCKED_NO_GO")
        self.assertEqual(r["single_independent_economic_event_count"],0)
        self.assertIsNone(r["actual_minus_consensus_metric_units"])
        self.assertEqual(r["fx_pair_outcome_claim_count"],0)
        return r

    def test_01_same_metric_arithmetic_without_prices(self):
        r=self.safety(self.run_event())
        self.assertEqual(r["state"],
            "LAB_FX28_SINGLE_EVENT_SURPRISE_DOCUMENTARY_ONLY_NO_GO")
        self.assertEqual(r["single_independent_economic_event_count"],1)
        self.assertEqual(r["actual_minus_consensus_metric_units"],"0.1")
        self.assertEqual(r["economic_surprise_label_documentary_only"],"ABOVE_CONSENSUS")
        self.assertEqual(r["metric_identity"]["seasonal_adjustment"],"SA")
        self.assertEqual(r["fx_pair_outcome_claim_count"],0)

    def test_02_complete_seven_pairs_one_event_not_seven_forecasts(self):
        r=self.safety(self.run_event(price_claims=prices()))
        self.assertEqual(r["state"],
            "LAB_FX28_SINGLE_EVENT_AND_7FX_REACTIONS_DOCUMENTARY_ONLY_NO_GO")
        self.assertEqual(r["single_independent_economic_event_count"],1)
        self.assertEqual(r["fx_pair_outcome_claim_count"],7)
        self.assertTrue(r["full_seven_pair_cohort_documentary"])
        self.assertEqual([p["pair"] for p in r["fx_reaction_claims"]],
            [pair for pair in OFFICIAL_PAIRS if "USD" in split_pair(pair)])
        self.assertTrue(all(p["locally_claimed_change_bps"]=="20.0000"
                            for p in r["fx_reaction_claims"]))

    def test_03_same_event_h1_and_h4_not_convert_to_skill(self):
        for horizon in ("H1","H4"):
            with self.subTest(horizon=horizon):
                r=self.safety(self.run_event(price_claims=prices(horizon=horizon)))
                self.assertEqual(r["fx_pair_outcome_claim_count"],7)
                self.assertEqual(r["single_independent_economic_event_count"],1)
                self.assertIsNone(r["predicted_currency_direction"])

    def test_04_below_zero_and_equal_consensus_are_descriptive(self):
        for numeric,label,diff in (
            ("0.1","BELOW_CONSENSUS","-0.1"),
            ("0.2","IN_LINE_WITH_CONSENSUS","0.0"),
        ):
            with self.subTest(numeric=numeric):
                actual=replace(ACTUAL,numeric_value=numeric)
                r=self.safety(self.run_event(actual=actual))
                self.assertEqual(r["economic_surprise_label_documentary_only"],label)
                self.assertEqual(r["actual_minus_consensus_metric_units"],diff)

    def test_05_early_read_before_actual_release_rejected(self):
        self.blocked(inspected_at_utc=RELEASE-timedelta(seconds=1))

    def test_06_consensus_local_capture_after_release_rejected(self):
        consensus=replace(CONSENSUS,locally_captured_at_utc=RELEASE)
        r=self.blocked(consensus=consensus)
        self.assertEqual(r["reason"],"CONSENSUS_NOT_PRE_EVENT_OR_ACTUAL_NOT_POST_RELEASE")

    def test_07_pre_event_snapshot_claim_published_after_capture_rejected(self):
        consensus=replace(CONSENSUS,published_at_utc=RELEASE-timedelta(minutes=30))
        self.blocked(consensus=consensus)

    def test_08_original_actual_published_future_rejected(self):
        actual=replace(ACTUAL,published_at_utc=NOW+timedelta(seconds=1))
        self.blocked(actual=actual)

    def test_09_wrong_first_print_vintage_rejected(self):
        actual=replace(ACTUAL,first_print_vintage_claim="LATEST_REVISED")
        self.blocked(actual=actual)

    def test_10_issuer_domain_spoof_rejected(self):
        actual=replace(ACTUAL,
            official_source_url="https://www.bls.gov.attacker.invalid/news.release/ppi.toc.htm")
        r=self.blocked(actual=actual)
        self.assertEqual(r["reason"],"UNTRUSTED_OR_ISSUER_COLLIDING_CONSENSUS_OR_OFFICIAL_URL")

    def test_11_sources_same_domain_not_independent_consensus(self):
        consensus=replace(CONSENSUS,
            source_url="https://www.bls.gov/news.release/ppi.toc.htm")
        self.blocked(consensus=consensus)

    def test_12_wrong_https_or_embedded_credentials_rejected(self):
        for bad in ("http://www.bls.gov/news.release/ppi.toc.htm",
                    "https://username:pass@www.bls.gov/news.release/ppi.toc.htm",
                    "https://www.bls.gov/news.release/ppi.toc.htm#fragment"):
            with self.subTest(url=bad):
                self.blocked(actual=replace(ACTUAL,official_source_url=bad))

    def test_13_missing_or_malformed_sha_rejected(self):
        self.blocked(consensus=replace(CONSENSUS,original_sha256_claim="0"*63))
        self.blocked(actual=replace(ACTUAL,original_sha256_claim="A"*64))

    def test_14_never_mix_sa_mom_with_nsa_or_yoy(self):
        for transformation,adjustment in (
            ("YOY","SA"), ("MOM","NSA"), ("LEVEL","SA")
        ):
            with self.subTest(transform=transformation,sa=adjustment):
                altered=replace(METRIC,transformation=transformation,
                                seasonal_adjustment=adjustment)
                self.blocked(actual=replace(ACTUAL,metric=altered))

    def test_15_never_mix_period_or_series_even_same_values(self):
        for updated in (replace(METRIC,reference_period="2026-09"),
                        replace(METRIC,series_id="US_CPI_U_MOM")):
            self.blocked(actual=replace(ACTUAL,metric=updated))

    def test_16_unknown_metric_units_or_series_rejected(self):
        bad=replace(METRIC,unit="USD")
        self.blocked(consensus=replace(CONSENSUS,metric=bad),
                     actual=replace(ACTUAL,metric=bad))
        bad=replace(METRIC,series_id="../THIS")
        self.blocked(consensus=replace(CONSENSUS,metric=bad),
                     actual=replace(ACTUAL,metric=bad))

    def test_17_non_numeric_nan_float_or_infinite_refused(self):
        for val in ("NaN","Infinity","1e99","not_a_number",0.3,True):
            with self.subTest(val=val):
                self.blocked(actual=replace(ACTUAL,numeric_value=val))

    def test_18_one_missing_or_duplicated_cross_pair_blocks_whole_study(self):
        pp=prices()
        self.blocked(price_claims=pp[:-1])
        self.blocked(price_claims=pp[:-1]+[pp[0]])

    def test_19_mixed_horizon_in_single_event_not_same_outcome(self):
        pp=prices()
        pp[1]=replace(pp[1],horizon="H1")
        self.blocked(price_claims=pp)

    def test_20_negative_zero_or_future_price_not_admitted(self):
        pp=prices()
        for val in ("0.0","-1.0","NaN",1.25):
            with self.subTest(price=val):
                bad=list(pp);bad[0]=replace(bad[0],baseline_price=val)
                self.blocked(price_claims=bad)
        bad=list(pp)
        bad[0]=replace(bad[0],endpoint_at_utc=NOW+timedelta(minutes=1))
        self.blocked(price_claims=bad)

    def test_21_before_horizon_close_is_not_closed_broker_bar(self):
        pp=prices(horizon="H4")
        pp[0]=replace(pp[0],endpoint_at_utc=RELEASE+timedelta(minutes=239))
        self.blocked(price_claims=pp)

    def test_22a_mixed_price_baseline_clocks_block_entire_cohort(self):
        pp=prices()
        pp[0]=replace(pp[0],baseline_at_utc=RELEASE-timedelta(minutes=14))
        r=self.blocked(price_claims=pp)
        self.assertEqual(r["reason"],
            "SEVEN_FX_REACTIONS_HAVE_DIFFERENT_PRICE_WINDOWS")

    def test_22b_mixed_endpoint_clocks_block_even_inside_tolerance(self):
        pp=prices()
        pp[0]=replace(pp[0],endpoint_at_utc=RELEASE+timedelta(minutes=16))
        r=self.blocked(price_claims=pp)
        self.assertEqual(r["reason"],
            "SEVEN_FX_REACTIONS_HAVE_DIFFERENT_PRICE_WINDOWS")

    def test_22c_all_m15_endpoints_hours_late_are_not_m15(self):
        pp=[replace(row,endpoint_at_utc=RELEASE+timedelta(hours=3))
            for row in prices()]
        r=self.blocked(price_claims=pp)
        self.assertEqual(r["reason"],
            "FX_PRICE_CLAIM_NUMERIC_TIME_OR_SOURCE_HASH_INVALID")

    def test_22d_one_synchronized_endpoint_within_alignment_tolerance(self):
        pp=[replace(row,endpoint_at_utc=RELEASE+timedelta(minutes=16))
            for row in prices()]
        r=self.safety(self.run_event(price_claims=pp))
        self.assertTrue(
            r["all_seven_pairs_share_identical_baseline_and_endpoint_clocks"])
        self.assertEqual(r["shared_price_baseline_utc_claim"],
                         (RELEASE-timedelta(minutes=15)).isoformat())
        self.assertEqual(r["shared_price_endpoint_utc_claim"],
                         (RELEASE+timedelta(minutes=16)).isoformat())
        self.assertEqual(r["fx_pair_outcome_claim_count"],7)
        self.assertFalse(r["broker_price_and_bid_ask_independently_authenticated"])

    def test_22_timezone_equivalence_is_reproducible(self):
        mt=timezone(timedelta(hours=-4))
        consensus=replace(CONSENSUS,
            published_at_utc=CONSENSUS.published_at_utc.astimezone(mt),
            locally_captured_at_utc=CONSENSUS.locally_captured_at_utc.astimezone(mt))
        actual=replace(ACTUAL,
            scheduled_release_at_utc=ACTUAL.scheduled_release_at_utc.astimezone(mt),
            published_at_utc=ACTUAL.published_at_utc.astimezone(mt),
            locally_captured_at_utc=ACTUAL.locally_captured_at_utc.astimezone(mt))
        r1=self.run_event()
        r2=self.run_event(consensus=consensus,actual=actual,
                          inspected_at_utc=NOW.astimezone(mt))
        self.assertEqual(r1,r2)

    def test_23_not_a_causal_event_study_or_oos_probability(self):
        result=self.safety(self.run_event(price_claims=prices()))
        self.assertTrue(result["observed_correlation_not_causing_currency_direction"])
        self.assertFalse(result["pre_event_consensus_independently_authenticated"])
        self.assertFalse(result["first_print_actual_independently_authenticated"])
        self.assertTrue(result["source_digest_authenticates_only_claimed_local_bytes"])
        self.assertTrue(all(not p["broker_price_source_independently_verified"]
                            for p in result["fx_reaction_claims"]))

    def test_24_empty_or_naive_asof_blocks(self):
        self.blocked(inspected_at_utc=None)
        self.blocked(inspected_at_utc=NOW.replace(tzinfo=None))

    def test_26_identical_pre_and_post_original_digest_not_independent(self):
        actual=replace(ACTUAL,
                       original_sha256_claim=CONSENSUS.original_sha256_claim)
        r=self.blocked(actual=actual)
        self.assertEqual(r["reason"],
            "PRE_EVENT_CONSENSUS_AND_POST_EVENT_ACTUAL_SAME_BYTES")

    def test_27_explicit_default_https_port_443_remains_same_issuer(self):
        actual=replace(ACTUAL,official_source_url=
                       "https://www.bls.gov:443/news.release/ppi.toc.htm")
        r=self.safety(self.run_event(actual=actual))
        self.assertEqual(r["state"],
            "LAB_FX28_SINGLE_EVENT_SURPRISE_DOCUMENTARY_ONLY_NO_GO")

    def test_25_all_8_currency_rosters_have_7_crosses_each(self):
        for c in CURRENCIES:
            self.assertEqual(
                sum(c in split_pair(pair) for pair in OFFICIAL_PAIRS),7)

if __name__=="__main__":
    unittest.main(verbosity=2)
