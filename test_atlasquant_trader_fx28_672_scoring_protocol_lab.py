"""Only fabricated 672-slot outcomes/forecasts, never source authenticity."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import unittest

from atlasquant_fx_universe import OFFICIAL_PAIRS
from atlasquant_trader_fx28_ny17_prospective_campaign_lab import (
    _nominal_windows, FROZEN_END_UTC, FROZEN_START_UTC,
)
from atlasquant_trader_fx_ny17_forecast_outcome_join_lab import (
    SCHEMA as JOIN_SCHEMA,
)
from atlasquant_trader_fx28_672_scoring_protocol_lab import (
    SCHEMA, precommit_fx28_672_scoring_rules_lab as inspect,
    inspect_fx28_672_two_axis_coverage_lab as coverage,
)

BEFORE = datetime(2026,11,13,18,tzinfo=timezone.utc)
AFTER = FROZEN_END_UTC + timedelta(seconds=1)


def fake_join(horizon, *, forecast="UP", actual="UP"):
    rows=[]
    counter={"SAME_DIRECTION_CLAIM_ONLY":0,
             "OPPOSITE_DIRECTION_CLAIM_ONLY":0,
             "FLAT_OUTCOME_NOT_A_HIT":0,
             "ABSTENTION_NOT_A_HIT":0}
    windows=_nominal_windows(horizon)
    for ix,(start,end) in enumerate(windows):
        for pair in OFFICIAL_PAIRS:
            comparison=("ABSTENTION_NOT_A_HIT" if forecast=="ABSTAIN"
                        else "FLAT_OUTCOME_NOT_A_HIT" if actual=="FLAT"
                        else "SAME_DIRECTION_CLAIM_ONLY" if forecast==actual
                        else "OPPOSITE_DIRECTION_CLAIM_ONLY")
            counter[comparison]+=1
            rows.append({
                "opportunity_id":f"TEST_{horizon}_{ix}_{pair.replace('/','')}",
                "pair":pair, "horizon":horizon,
                "window_start_utc":start.isoformat(),
                "window_end_utc":end.isoformat(),
                "direction_claim_unattested":forecast,
                "abstain_reason":"LOW_CONFIDENCE" if forecast=="ABSTAIN" else None,
                "observed_price_direction_documentary":actual,
                "observed_price_move_bps_documentary":"0.0000",
                "comparison_documentary_only":comparison,
                "external_precommit_verified":False,
                "broker_price_source_verified":False,
            })
    n=len(rows)
    return {
        "schema":JOIN_SCHEMA,
        "state":"LAB_NY17_COMPLETE_FORECAST_PRICE_CLAIMS_ONLY_NO_GO",
        "horizon":horizon,
        "declared_window_count":len(windows),
        "expected_opportunities":n,
        "received_forecasts":n,
        "declared_abstentions":counter["ABSTENTION_NOT_A_HIT"],
        "directional_claims":n-counter["ABSTENTION_NOT_A_HIT"],
        "documentary_same_direction_count":counter["SAME_DIRECTION_CLAIM_ONLY"],
        "documentary_opposite_direction_count":counter["OPPOSITE_DIRECTION_CLAIM_ONLY"],
        "documentary_flat_outcomes_count":counter["FLAT_OUTCOME_NOT_A_HIT"],
        "full_28fx_all_window_manifest_reconciled":True,
        "nominal_window_census_recomputed_locally":True,
        "forecast_pre_event_witness_independently_authenticated":False,
        "price_archive_source_independently_authenticated":False,
        "trade_authorized":False,
        "publishable":False,
        "rows_documentary":rows,
    }


class Fx28ScoringProtocolTests(unittest.TestCase):
    def run_it(self, *, at=AFTER, daily=None, weekly=None):
        return inspect(
            as_of_utc=at,
            d1_documentary_join=daily,
            w1_documentary_join=weekly,
        )

    def safe(self,r):
        self.assertEqual(r["schema"],SCHEMA)
        self.assertEqual(r["expected_pair_horizon_slots"],672)
        self.assertEqual(r["expected_d1_slots"],560)
        self.assertEqual(r["expected_w1_slots"],112)
        self.assertEqual(r["operational_bias"],"AGUARDAR")
        self.assertFalse(r["trade_authorized"])
        self.assertFalse(r["publishable"])
        self.assertFalse(r["worker_enabled"])
        self.assertFalse(r["live_alert_allowed"])
        self.assertFalse(r["pre_event_publication_independently_authenticated"])
        self.assertFalse(r["broker_prices_independently_authenticated"])
        self.assertFalse(r["macro_vintages_independently_authenticated"])
        self.assertFalse(r["model_configuration_independently_attested"])
        self.assertIsNone(r["out_of_sample_accuracy_percent"])
        self.assertIsNone(r["validated_hit_rate_percent"])
        self.assertIsNone(r["calibrated_probability"])
        self.assertIsNone(r["confidence_interval_percent"])
        self.assertIsNone(r["expected_independent_trials"])
        self.assertTrue(r["composite_accuracy_not_allowed"])
        self.assertTrue(r["twenty_d1_and_four_w1_sessions_overlap"])
        self.assertTrue(r["fx28_pairs_share_eight_currency_legs"])
        self.assertTrue(r["cluster_aware_uncertainty_required"])
        self.assertTrue(r["no_iid_binomial_interval"])
        self.assertEqual(r["http_requests"],0)
        self.assertEqual(r["file_writes"],0)
        self.assertEqual(r["new_cost_brl"],0)

    def blocked(self,**kwargs):
        r=self.run_it(**kwargs)
        self.safe(r)
        self.assertEqual(r["state"],"LAB_FX28_672_PRECOMMITTED_SCORING_BLOCKED")
        self.assertEqual(r["total_documentary_reconciled_slots"],0)
        self.assertEqual(r["per_horizon_documentary_counts"],{})
        return r

    def test_01_preopen_protocol_frozen_before_forecasts(self):
        r=self.run_it(at=BEFORE)
        self.safe(r)
        self.assertEqual(r["state"],
                         "LAB_FX28_672_SCORING_PROTOCOL_FROZEN_AWAIT_RESULTS_NO_GO")
        self.assertEqual(r["reason"],"NO_FORECAST_OR_PRICE_MEASUREMENT_YET")
        self.assertEqual(r["primary_metric_definition"],
                         "AUTHENTICATED_CORRECT_UP_DOWN / AUTHENTICATED_NON_ABSTAIN_UP_DOWN")
        self.assertEqual(r["secondary_coverage_definition"],
                         "AUTHENTICATED_NON_ABSTAIN_UP_DOWN / 672")
        self.assertEqual(r["abstention"],
                         "NOT_A_HIT_AND_EXCLUDED_FROM_DIRECTIONAL_HIT_RATE")

    def test_02_study_not_finished_but_rows_claimed_is_not_accepted(self):
        r=self.blocked(at=FROZEN_END_UTC-timedelta(seconds=1),
                       daily=fake_join("D1"),weekly=fake_join("W1"))
        self.assertEqual(r["reason"],
                         "HINDSIGHT_SCORE_REQUESTED_BEFORE_ALL_WINDOWS_FINISH")

    def test_03_missing_one_horizon_never_reports_partial_hit_rate(self):
        r=self.blocked(daily=fake_join("D1"))
        self.assertEqual(r["reason"],
                         "BOTH_HORIZON_JOINS_MANDATORY_NO_PARTIAL_WIN_RATE")

    def test_04_all_right_synthetic_rows_still_no_real_accuracy(self):
        r=self.run_it(daily=fake_join("D1"),weekly=fake_join("W1"))
        self.safe(r)
        self.assertEqual(r["state"],"LAB_FX28_672_DOCUMENTARY_ROLLUP_ONLY_NO_GO")
        self.assertEqual(r["total_documentary_reconciled_slots"],672)
        self.assertEqual(r["total_documentary_same_direction"],672)
        self.assertEqual(r["total_documentary_wrong_or_flat"],0)
        self.assertEqual(r["total_documentary_abstentions"],0)
        self.assertEqual(r["per_horizon_documentary_counts"]["D1"]["expected_slots"],560)
        self.assertEqual(r["per_horizon_documentary_counts"]["W1"]["expected_slots"],112)

    def test_05_all_wrong_is_zero_agreement_not_mathematical_error(self):
        r=self.run_it(daily=fake_join("D1",actual="DOWN"),
                      weekly=fake_join("W1",actual="DOWN"))
        self.safe(r)
        self.assertEqual(r["total_documentary_same_direction"],0)
        self.assertEqual(r["total_documentary_wrong_or_flat"],672)

    def test_06_all_flat_predictions_not_wins(self):
        r=self.run_it(daily=fake_join("D1",actual="FLAT"),
                      weekly=fake_join("W1",actual="FLAT"))
        self.safe(r)
        self.assertEqual(r["total_documentary_same_direction"],0)
        self.assertEqual(r["total_documentary_wrong_or_flat"],672)

    def test_07_all_abstain_no_direction_coverage_and_not_672_wins(self):
        r=self.run_it(daily=fake_join("D1",forecast="ABSTAIN"),
                      weekly=fake_join("W1",forecast="ABSTAIN"))
        self.safe(r)
        self.assertEqual(r["total_documentary_abstentions"],672)
        self.assertEqual(r["total_documentary_directional_claims"],0)
        self.assertEqual(r["total_documentary_same_direction"],0)
        self.assertEqual(r["total_documentary_wrong_or_flat"],0)

    def test_08_one_abstention_cannot_be_silently_promoted_to_hit(self):
        d,w=fake_join("D1"),fake_join("W1")
        d["rows_documentary"][0]["direction_claim_unattested"]="ABSTAIN"
        # The row still has "SAME" but should be abstention.
        self.assertIn("COMPARISON",self.blocked(
            daily=d,weekly=w)["reason"])

    def test_09_fake_correct_flag_without_actual_matching_direction_blocks(self):
        d=fake_join("D1")
        d["rows_documentary"][0]["observed_price_direction_documentary"]="DOWN"
        r=self.blocked(daily=d,weekly=fake_join("W1"))
        self.assertEqual(r["reason"],
                         "D1_COMPARISON_INCONSISTENT_WITH_DIRECTIONS")

    def test_10_forge_560_hits_to_559_or_561_blocks_not_accuracy(self):
        for count in (559,561,True):
            with self.subTest(count=count):
                d=fake_join("D1")
                d["documentary_same_direction_count"]=count
                r=self.blocked(daily=d,weekly=fake_join("W1"))
                self.assertEqual(r["reason"],
                                 "D1_DOCUMENTARY_SUMMARY_COUNTS_TAMPERED")

    def test_11_duplicate_or_missing_pair_row_blocks_672(self):
        for mode in ("duplicate","missing","swapped"):
            with self.subTest(mode=mode):
                d=fake_join("D1")
                if mode=="duplicate":
                    d["rows_documentary"][1]["opportunity_id"] = (
                        d["rows_documentary"][0]["opportunity_id"])
                elif mode=="missing":
                    d["rows_documentary"].pop()
                else:
                    d["rows_documentary"][0],d["rows_documentary"][1] = (
                        d["rows_documentary"][1],d["rows_documentary"][0])
                r=self.blocked(daily=d,weekly=fake_join("W1"))
                self.assertTrue(r["reason"].startswith("D1_"))

    def test_12_fake_external_provenance_flags_cannot_be_accepted_as_verified(self):
        for flag in ("forecast_pre_event_witness_independently_authenticated",
                     "price_archive_source_independently_authenticated"):
            with self.subTest(flag=flag):
                d=fake_join("D1")
                d[flag]=True
                r=self.blocked(daily=d,weekly=fake_join("W1"))
                self.assertEqual(r["reason"],
                                 "D1_DOCUMENTARY_JOIN_SCHEMA_OR_STATE_INVALID")
        d=fake_join("D1")
        d["rows_documentary"][0]["external_precommit_verified"]=True
        r=self.blocked(daily=d,weekly=fake_join("W1"))
        self.assertEqual(r["reason"],"D1_UNTRUSTED_OR_NONCANONICAL_ROW")

    def test_13_wrong_time_or_wrong_pair_or_invalid_type_blocks(self):
        for field,val in (
            ("window_start_utc","2026-11-15T21:59:59+00:00"),
            ("window_end_utc","2026-11-20T22:00:00+00:00"),
            ("pair","XAU/USD"),("direction_claim_unattested",42),
            ("comparison_documentary_only","HIT_100%"),
        ):
            with self.subTest(field=field):
                d=fake_join("D1");d["rows_documentary"][0][field]=val
                r=self.blocked(daily=d,weekly=fake_join("W1"))
                self.assertEqual(r["reason"],"D1_UNTRUSTED_OR_NONCANONICAL_ROW")

    def test_14_clock_after_end_in_mato_grosso_is_same_utc(self):
        local=timezone(timedelta(hours=-4))
        t=AFTER.astimezone(local)
        r=self.run_it(at=t,daily=fake_join("D1"),weekly=fake_join("W1"))
        self.safe(r)
        self.assertEqual(r["total_documentary_reconciled_slots"],672)

    def test_15_invalid_clocks_fail_with_zero_evidence(self):
        for bad in (None,AFTER.replace(tzinfo=None),
                    AFTER.replace(microsecond=1),0,
                    "2026-12-12T10:00:00Z"):
            with self.subTest(bad=bad):
                r=self.blocked(at=bad)
                self.assertEqual(r["reason"],
                                 "INVALID_AS_OF_UTC_OR_CAMPAIGN_CONTRACT")

    def test_16_post_close_claim_rosters_are_not_witness_proof(self):
        d,w=fake_join("D1"),fake_join("W1")
        dcopy,wcopy=deepcopy(d),deepcopy(w)
        r=self.run_it(daily=d,weekly=w)
        self.safe(r)
        self.assertEqual(d,dcopy)
        self.assertEqual(w,wcopy)
        self.assertFalse(r["pre_event_publication_independently_authenticated"])
        self.assertIsNone(r["validated_hit_rate_percent"])
        self.assertTrue(r["research_only"])


class Fx28TwoAxisCoverageTests(unittest.TestCase):
    @staticmethod
    def sid(*, horizon="D1", window=0, pair="EUR/USD"):
        start=_nominal_windows(horizon)[window][0]
        return f"FX28_NY17_{start.strftime('%Y%m%dT%H%MZ')}_{horizon}_{pair}"

    def one(self, *, horizon="D1", window=0, pair="EUR/USD",
            fc="DIRECTIONAL_CLAIM_ONLY", price=None):
        return {
            "slot_id":self.sid(horizon=horizon,window=window,pair=pair),
            "forecast_status_claim":fc,
            "price_status_claim":price,
        }

    def safe(self, r):
        self.assertFalse(r["trade_authorized"])
        self.assertFalse(r["publishable"])
        self.assertEqual(r["operational_bias"],"AGUARDAR")
        self.assertIsNone(r["validated_hit_rate_percent"])
        self.assertIsNone(r["calibrated_probability"])
        self.assertTrue(r["source_claims_not_issuer_or_broker_attestation"])
        self.assertTrue(r["absence_of_supplied_claim_is_not_proof_of_nonissuance"])
        self.assertTrue(r["price_gap_cannot_be_a_hit_or_abstention"])
        self.assertEqual((r["http_requests"],r["file_writes"],r["new_cost_brl"]),(0,0,0))

    def test_17_preflight_first_56_future_no_forecast_absence_inferred(self):
        pre=datetime(2026,11,15,10,tzinfo=timezone.utc)
        r=coverage(as_of_utc=pre)
        self.safe(r)
        self.assertTrue(r["all_slots_accounted"])
        self.assertEqual(r["per_horizon"]["D1"]["slots"],560)
        self.assertEqual(r["per_horizon"]["W1"]["slots"],112)
        self.assertEqual(sum(v["forecast_unknown_no_supplied_evidence"]
                             for v in r["per_horizon"].values()),672)
        self.assertEqual(sum(v["price_not_yet_labelable_by_clock"]
                             for v in r["per_horizon"].values()),672)

    def test_18_after_first_d1_close_price_gap_never_abstention_or_hit(self):
        after=datetime(2026,11,16,22,tzinfo=timezone.utc)
        records=[
            self.one(price="UNLABELABLE_M15_GAP_CLAIM_ONLY"),
            self.one(pair="GBP/USD",fc="ABSTAIN_CLAIM_ONLY",
                     price="COMPLETE_M15_CLAIM_ONLY"),
            self.one(pair="AUD/USD",fc="NOT_ISSUED_CLAIM_ONLY",
                     price="UNAVAILABLE_PRICE_CLAIM_ONLY"),
            self.one(pair="NZD/USD",price="COMPLETE_M15_CLAIM_ONLY"),
        ]
        r=coverage(as_of_utc=after,supplied_slot_claims=records)
        self.safe(r)
        self.assertEqual(r["state"],"LAB_FX28_672_TWO_AXIS_COVERAGE_CLAIM_ONLY_NO_GO")
        self.assertEqual(r["per_horizon"]["D1"]["window_closed"],28)
        self.assertEqual(r["per_horizon"]["D1"]["price_unlabelable_m15_gap_claim_only"],1)
        self.assertEqual(r["per_horizon"]["D1"]["forecast_abstain_claim_only"],1)
        self.assertEqual(r["per_horizon"]["D1"]["forecast_not_issued_claim_only"],1)
        self.assertEqual(r["per_horizon"]["D1"]["directional_with_price_complete_claim_only"],1)
        self.assertEqual(r["per_horizon"]["W1"]["window_closed"],0)

    def test_19_price_from_future_or_current_window_is_rejected(self):
        for at in (datetime(2026,11,15,10,tzinfo=timezone.utc),
                   datetime(2026,11,16,21,59,tzinfo=timezone.utc)):
            r=coverage(as_of_utc=at,supplied_slot_claims=[
                self.one(price="COMPLETE_M15_CLAIM_ONLY")])
            self.safe(r)
            self.assertEqual(r["reason"],"PRICE_CLAIM_BEFORE_NOMINAL_WINDOW_CLOSE")
            self.assertFalse(r["all_slots_accounted"])

    def test_20_unknown_duplicate_wrong_record_types_do_not_inflate_slots(self):
        at=datetime(2026,11,16,22,tzinfo=timezone.utc)
        valid=self.one(price="UNLABELABLE_M15_GAP_CLAIM_ONLY")
        cases=[
            [valid,dict(valid)],
            [{**valid,"slot_id":"FX28_NOT_AN_ACTUAL_SLOT"}],
            [{**valid,"forecast_status_claim":["DIRECTIONAL_CLAIM_ONLY"]}],
            [{**valid,"price_status_claim":{"adversarial":"value"}}],
            [{**valid,"untrusted_extra":True}],
        ]
        for c in cases:
            with self.subTest(c=c):
                r=coverage(as_of_utc=at,supplied_slot_claims=c)
                self.safe(r)
                self.assertEqual(r["state"],"LAB_FX28_672_COVERAGE_BLOCKED_NO_GO")
                self.assertFalse(r["all_slots_accounted"])

    def test_21_672_nominal_slots_remain_even_without_any_supplied_price(self):
        at=FROZEN_END_UTC+timedelta(seconds=1)
        r=coverage(as_of_utc=at,supplied_slot_claims=())
        self.safe(r)
        self.assertTrue(r["all_slots_accounted"])
        self.assertEqual(sum(v["window_closed"] for v in r["per_horizon"].values()),672)
        self.assertEqual(sum(v["price_unknown_no_supplied_evidence"]
                             for v in r["per_horizon"].values()),672)
        self.assertEqual(sum(v["forecast_not_issued_claim_only"]
                             for v in r["per_horizon"].values()),0)

if __name__=="__main__":
    unittest.main()
