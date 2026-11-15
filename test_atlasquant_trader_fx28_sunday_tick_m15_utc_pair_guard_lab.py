"""28-pair synthetic-only UTC second/millisecond M15-tick clock guards."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone, timedelta
import unittest

from atlasquant_fx_universe import OFFICIAL_PAIRS
from atlasquant_trader_fx28_sunday_tick_m15_utc_pair_guard_lab import (
    LocalTickM15PairClaim as Pair,
    LocalTickTimeClaim as Tick,
    inspect_fx28_sunday_tick_m15_utc_pair_lab as inspect,
    PRESENT, EMPTY, ERROR, TICKS_PRESENT, TICKS_EMPTY,
)

UTC = timezone.utc
SUN = datetime(2026,12,13,22,tzinfo=UTC)
NOW = SUN+timedelta(hours=5,minutes=20)
BASE = int(SUN.timestamp())
OPEN = BASE+2*3600


def tick(tsec: int, ms=250):
    return Tick(time_seconds_utc_epoch=tsec,time_msc_utc_epoch=tsec*1000+ms)


def cohort(*, kind=PRESENT, op=OPEN, ticks=None):
    if ticks is None:
        ticks=(tick(op+12),)
    status=TICKS_PRESENT if ticks else TICKS_EMPTY
    if kind==EMPTY:
        op=None
    return [Pair(
        pair=pair,m15_result_kind=kind,
        first_m15_open_seconds_utc_epoch=op,
        tick_result_kind=status,tick_samples=tuple(ticks),
    ) for pair in OFFICIAL_PAIRS]


class TickVsM15UtcGuardTests(unittest.TestCase):
    def check(self, pairs=None, *, nominal=SUN, now=NOW):
        return inspect(separate_sunday_start_utc=nominal,
                       inspected_at_utc=now,
                       pair_claims=cohort() if pairs is None else pairs)

    def safe(self,r):
        for key in (
            "pepperstone_broker_source_authenticated",
            "first_tick_at_actual_market_open_authenticated",
            "broker_open_time_authenticated",
            "historical_20261115_start_bar_reconstructed",
            "frozen_campaign_672_slots_modified",
            "clock_rewrite_allowed",
            "publishable","trade_authorized","scheduler_enabled"):
            self.assertFalse(r[key],key)
        self.assertTrue(r["mt5_local_tick_and_bar_records_are_not_independent"])
        self.assertTrue(r["sparse_tick_sample_does_not_prove_absence"])
        self.assertTrue(r["time_msc_does_not_independently_attest_timestamp"])
        self.assertTrue(r["broker_server_offset_not_applied_to_data"])
        self.assertIsNone(r["validated_accuracy"])
        self.assertIsNone(r["calibrated_direction_probability"])
        self.assertEqual((r["mt5_calls"],r["http_requests"],
                          r["file_writes"],r["new_cost_brl"]),(0,0,0,0))
        self.assertEqual(r["operational_bias"],"AGUARDAR")

    def test_01_all_28_same_utc_candle_bucket_including_ms(self):
        r=self.check()
        self.safe(r)
        self.assertEqual(r["state"],"LAB_FX28_SUNDAY_TICK_M15_UTC_CLOCK_CLAIMS_ONLY_NO_GO")
        self.assertEqual(r["roster_pairs_verified_claim_only"],28)
        self.assertEqual(r["pairs_with_m15"],28)
        self.assertEqual(r["pairs_with_tick_samples"],28)
        self.assertEqual(r["pairs_with_same_m15_bucket_tick"],28)
        self.assertEqual(r["pairs_with_possible_2h_3h_shift_but_no_same_bucket_tick"],0)
        self.assertEqual(len(r["comparison_rows"]),28)
        self.assertTrue(all(row["classification"] ==
            "SAME_UTC_M15_BUCKET_TICK_SAMPLED_CLAIM_ONLY"
            for row in r["comparison_rows"]))

    def test_02_28_offset_minus_2h_only_suspicion_no_clock_rewrite(self):
        pairs=cohort(ticks=(tick(BASE+10),))
        r=self.check(pairs)
        self.safe(r)
        self.assertEqual(r["pairs_with_same_m15_bucket_tick"],0)
        self.assertEqual(r["pairs_with_possible_2h_3h_shift_but_no_same_bucket_tick"],28)
        self.assertTrue(all(x["candidate_offset_hours_no_timestamp_rewrite"]==[-2]
                            for x in r["comparison_rows"]))
        self.assertEqual(r["comparison_rows"][0]["m15_open_epoch_claim"],OPEN)

    def test_03_28_offset_minus_3h_summer_ny17_clock(self):
        summer=datetime(2027,3,14,21,tzinfo=UTC)
        base=int(summer.timestamp())
        pairs=cohort(op=base+3*3600,ticks=(tick(base+8),))
        r=self.check(pairs,nominal=summer,
                     now=summer+timedelta(hours=5,minutes=20))
        self.safe(r)
        self.assertEqual(r["pairs_with_possible_2h_3h_shift_but_no_same_bucket_tick"],28)
        self.assertEqual(r["comparison_rows"][0]["candidate_offset_hours_no_timestamp_rewrite"],[-3])

    def test_04_tick_far_away_not_proof_market_closed(self):
        r=self.check(cohort(ticks=(tick(BASE+1000),)))
        self.safe(r)
        self.assertEqual(r["pairs_with_insufficient_overlap_sample"],28)
        self.assertEqual(r["pairs_with_possible_2h_3h_shift_but_no_same_bucket_tick"],0)

    def test_05_m15_empty_with_empty_ticks_not_fabricated_bar(self):
        r=self.check(cohort(kind=EMPTY,ticks=()))
        self.safe(r)
        self.assertEqual(r["pairs_with_no_m15_to_compare"],28)
        self.assertEqual(r["pairs_with_empty_m15"],28)
        self.assertEqual(r["pairs_with_tick_samples"],0)
        self.assertEqual(r["pairs_with_same_m15_bucket_tick"],0)

    def test_06_m15_missing_but_sampled_ticks_still_unlabelled(self):
        r=self.check(cohort(kind=EMPTY,ticks=(tick(BASE+18),)))
        self.safe(r)
        self.assertEqual(r["pairs_with_no_m15_to_compare"],28)
        self.assertEqual(r["pairs_with_tick_samples"],28)

    def test_07_mixed_roster_10_same_8_shift_6_sparse_4_missing(self):
        p=cohort()
        for i in range(10,18):
            p[i]=replace(p[i],tick_samples=(tick(BASE+10),))
        for i in range(18,24):
            p[i]=replace(p[i],tick_samples=(),tick_result_kind=TICKS_EMPTY)
        for i in range(24,28):
            p[i]=replace(p[i],m15_result_kind=EMPTY,
                         first_m15_open_seconds_utc_epoch=None)
        r=self.check(p)
        self.safe(r)
        self.assertEqual((r["pairs_with_same_m15_bucket_tick"],
                          r["pairs_with_possible_2h_3h_shift_but_no_same_bucket_tick"],
                          r["pairs_with_insufficient_overlap_sample"],
                          r["pairs_with_no_m15_to_compare"]), (10,8,6,4))

    def test_08_mt5_none_on_m15_is_error_not_empty(self):
        p=cohort()
        p[0]=replace(p[0],m15_result_kind=ERROR,
                     first_m15_open_seconds_utc_epoch=None)
        r=self.check(p)
        self.safe(r)
        self.assertEqual(r["reason"],"INVALID_PAIR_SOURCE_OR_NONE_MISCLASSIFIED_AS_EMPTY")

    def test_09_mt5_none_ticks_is_error_not_no_ticks(self):
        p=cohort()
        p[0]=replace(p[0],tick_result_kind=ERROR,tick_samples=())
        r=self.check(p)
        self.safe(r)
        self.assertEqual(r["reason"],"INVALID_PAIR_SOURCE_OR_NONE_MISCLASSIFIED_AS_EMPTY")

    def test_10_time_and_time_msc_are_1s_apart_fails(self):
        p=cohort()
        wrong=tick(OPEN+12)
        p[0]=replace(p[0],tick_samples=(
            replace(wrong,time_msc_utc_epoch=wrong.time_msc_utc_epoch+1000),))
        r=self.check(p)
        self.safe(r)
        self.assertEqual(r["reason"],"TICK_TIME_SECONDS_MILLISECONDS_OR_ORDER_CONFLICT")

    def test_11_tick_millisecond_rounding_boundary_999_allowed(self):
        r=self.check(cohort(ticks=(tick(OPEN+899,999),)))
        self.safe(r)
        self.assertEqual(r["pairs_with_same_m15_bucket_tick"],28)

    def test_12_tick_at_next_bar_open_not_first_bar_match(self):
        r=self.check(cohort(ticks=(tick(OPEN+900),)))
        self.safe(r)
        self.assertEqual(r["pairs_with_same_m15_bucket_tick"],0)
        self.assertEqual(r["pairs_with_insufficient_overlap_sample"],28)

    def test_13_tick_time_msc_less_than_nominal_is_blocked(self):
        p=cohort(ticks=(tick(BASE-1),))
        self.assertEqual(self.check(p)["reason"],
                         "TICK_TIME_SECONDS_MILLISECONDS_OR_ORDER_CONFLICT")

    def test_14_tick_after_history_end_plus_closed_m15_is_blocked(self):
        p=cohort(ticks=(tick(BASE+5*3600+900),))
        self.assertEqual(self.check(p)["reason"],
                         "TICK_TIME_SECONDS_MILLISECONDS_OR_ORDER_CONFLICT")

    def test_15_unsorted_or_equal_tick_milliseconds_blocked(self):
        for ticks in ((tick(OPEN+12),tick(OPEN+11)),
                      (tick(OPEN+12),tick(OPEN+12))):
            with self.subTest(ticks=ticks):
                self.assertEqual(
                    self.check(cohort(ticks=ticks))["reason"],
                    "TICK_TIME_SECONDS_MILLISECONDS_OR_ORDER_CONFLICT")

    def test_16_over_16_tick_samples_rejected(self):
        samples=tuple(tick(OPEN+i) for i in range(17))
        self.assertEqual(self.check(cohort(ticks=samples))["reason"],
                         "INVALID_PAIR_SOURCE_OR_NONE_MISCLASSIFIED_AS_EMPTY")

    def test_17_27_pairs_or_duplicate_pair_blocked(self):
        p=cohort()
        self.assertEqual(self.check(p[:27])["reason"],"INCOMPLETE_28_PAIR_COHORT")
        p[-1]=replace(p[-1],pair=p[0].pair)
        self.assertEqual(self.check(p)["reason"],
                         "INVALID_PAIR_SOURCE_OR_NONE_MISCLASSIFIED_AS_EMPTY")

    def test_18_nonroster_XAUUSD_rejected_from_fx28_scope(self):
        p=cohort()
        p[-1]=replace(p[-1],pair="XAUUSD")
        self.assertEqual(self.check(p)["reason"],
                         "INVALID_PAIR_SOURCE_OR_NONE_MISCLASSIFIED_AS_EMPTY")

    def test_19_wrong_terminal_or_m15_timeframe_rejected(self):
        for edit in ({"mt5_terminal_path_claim":"WRONG"},
                     {"timeframe_claim":"H1"},
                     {"tick_source_claim":"BROKER_ATTESTED"}):
            with self.subTest(edit=edit):
                p=cohort()
                p[0]=replace(p[0],**edit)
                self.assertEqual(self.check(p)["reason"],
                    "INVALID_PAIR_SOURCE_OR_NONE_MISCLASSIFIED_AS_EMPTY")

    def test_20_bad_open_epoch_not_on_m15_grid(self):
        p=cohort()
        p[0]=replace(p[0],first_m15_open_seconds_utc_epoch=OPEN+5)
        self.assertEqual(self.check(p)["reason"],
                         "BAD_M15_OPEN_UTC_EPOCH_GRID")

    def test_21_bar_open_epoch_before_nominal_or_after_5h_rejected(self):
        for opening in (BASE-900,BASE+5*3600):
            p=cohort()
            p[0]=replace(p[0],first_m15_open_seconds_utc_epoch=opening)
            with self.subTest(opening=opening):
                self.assertEqual(self.check(p)["reason"],
                                 "BAD_M15_OPEN_UTC_EPOCH_GRID")

    def test_22_float_bool_epoch_not_int(self):
        for opening in (float(OPEN),True):
            p=cohort()
            p[0]=replace(p[0],first_m15_open_seconds_utc_epoch=opening)
            self.assertEqual(self.check(p)["reason"],"BAD_M15_OPEN_UTC_EPOCH_GRID")

    def test_23_empty_kind_with_nonempty_ticks_inconsistent(self):
        p=cohort()
        p[0]=replace(p[0],tick_result_kind=TICKS_EMPTY)
        self.assertEqual(self.check(p)["reason"],
                         "INVALID_PAIR_SOURCE_OR_NONE_MISCLASSIFIED_AS_EMPTY")

    def test_24_before_campaign_research_is_forbidden(self):
        old=datetime(2026,11,15,22,tzinfo=UTC)
        r=self.check(nominal=old,now=old+timedelta(hours=5,minutes=20))
        self.safe(r)
        self.assertEqual(r["state"],
                         "LAB_FX28_SUNDAY_TICK_M15_UTC_PAIR_BLOCKED_NO_GO")

    def test_25_wrong_dst_wallclock_hour_rejected(self):
        summer=datetime(2027,3,14,22,tzinfo=UTC)
        self.assertEqual(self.check(nominal=summer,now=summer+timedelta(hours=5,minutes=20))["state"],
                         "LAB_FX28_SUNDAY_TICK_M15_UTC_PAIR_BLOCKED_NO_GO")

    def test_26_naive_or_microsecond_nominal_rejected(self):
        for nominal in (datetime(2026,12,13,22),
                        SUN+timedelta(microseconds=1)):
            self.assertEqual(
                self.check(nominal=nominal)["state"],
                "LAB_FX28_SUNDAY_TICK_M15_UTC_PAIR_BLOCKED_NO_GO")

    def test_27_asof_before_all_five_hour_candles_closed_rejected(self):
        self.assertEqual(self.check(now=SUN+timedelta(hours=5))["reason"],
                         "INVALID_SEPARATE_SUNDAY_OR_INSPECTION_CLOCK")

    def test_28_asof_more_than_six_hours_later_rejected(self):
        self.assertEqual(self.check(now=SUN+timedelta(hours=6,minutes=1))["reason"],
                         "INVALID_SEPARATE_SUNDAY_OR_INSPECTION_CLOCK")

    def test_29_result_never_reports_adjusted_epoch_as_broker_truth(self):
        r=self.check(cohort(ticks=(tick(BASE+10),)))
        self.safe(r)
        self.assertFalse(r["pepperstone_broker_source_authenticated"])
        self.assertFalse(r["clock_rewrite_allowed"])
        self.assertFalse(r["first_tick_at_actual_market_open_authenticated"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
