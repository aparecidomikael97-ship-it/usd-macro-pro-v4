"""Synthetic numpy-shaped MT5 raw tick/rate arrays. NO real MT5 or price I/O."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone, timedelta
from types import SimpleNamespace
import unittest

from atlasquant_fx_universe import OFFICIAL_PAIRS
from atlasquant_trader_fx28_sunday_mt5_raw_time_adapter_lab import (
    SuppliedMT5RawPairRows as Raw,
    inspect_supplied_fx28_sunday_mt5_raw_time_lab as inspect,
    MAX_RAW_TICK_ROWS, MAX_RAW_M15_ROWS,
)

UTC=timezone.utc
SUN=datetime(2026,12,13,22,tzinfo=UTC)
ASOF=SUN+timedelta(hours=5,minutes=20)
FIRST=int(SUN.timestamp())
BAR_OPEN=FIRST+2*3600


class IntLike:
    def __init__(self,value):
        self.value=value
    def item(self):
        return self.value


class NumpyLikeRow:
    dtype=SimpleNamespace(names=("time","time_msc","bid","ask","open","high","low","close"))
    def __init__(self,time, time_msc=None,price=1.00001):
        self.vals={"time":IntLike(time),"time_msc":IntLike(time_msc),
                   "bid":price,"ask":price,"open":price,
                   "high":price,"low":price,"close":price}
    def __getitem__(self,key):
        return self.vals[key]


class NumpyLikeArray:
    dtype=SimpleNamespace(names=("time","time_msc","open","bid","ask"))
    def __init__(self,rows):
        self.rows=rows
    def __len__(self):
        return len(self.rows)
    def __iter__(self):
        return iter(self.rows)


def sample_tick(epoch,ms=420):
    return {"time":epoch,"time_msc":epoch*1000+ms,"bid":1.11111,
            "ask":1.11112,"account":"PRIVATE_NOT_READ"}


def cohort(*, bars=None, ticks=None, first=SUN):
    if bars is None:
        bars=[{"time":int(first.timestamp())+7200,"open":1.0}]
    if ticks is None:
        t=int(first.timestamp())+7210
        ticks=[sample_tick(t)]
    return [Raw(
        pair=pair,m15_rows=list(bars),tick_rows=list(ticks),
        m15_request_start_utc=first,
        m15_request_end_inclusive_utc=first+timedelta(hours=4,minutes=45),
        tick_request_start_utc=first,
        tick_request_end_exclusive_utc=first+timedelta(hours=5,minutes=15),
    ) for pair in OFFICIAL_PAIRS]


class MT5RawTimeAdapterTests(unittest.TestCase):
    def check(self, rows=None,*,nominal=SUN,now=ASOF):
        return inspect(
            separate_sunday_start_utc=nominal,
            inspected_at_utc=now,
            pair_raw_rows=cohort(first=nominal) if rows is None else rows)

    def safe(self,result):
        for flag in ("broker_source_authenticated","observed_at_point_in_time_authenticated",
                     "actual_market_open_authenticated","server_clock_offset_applied",
                     "historical_20261115_campaign_replayed",
                     "frozen_campaign_672_slots_modified",
                     "publishable","trade_authorized","scheduler_enabled"):
            self.assertFalse(result[flag],flag)
        self.assertTrue(result["raw_prices_never_inspected_or_returned"])
        self.assertTrue(result["raw_api_outputs_supplied_by_caller_not_authenticated"])
        self.assertTrue(result["first_tick_per_quarterhour_bucket_not_full_tick_coverage"])
        self.assertIsNone(result["validated_accuracy"])
        self.assertEqual(result["operational_bias"],"AGUARDAR")
        self.assertEqual((result["mt5_calls"],result["http_requests"],
                          result["file_writes"],result["new_cost_brl"]),(0,0,0,0))

    def test_01_valid_28_from_dict_records_same_m15_bucket(self):
        r=self.check()
        self.safe(r)
        self.assertEqual(r["state"],
            "LAB_FX28_SUNDAY_RAW_MT5_TIME_ONLY_CLAIMS_NORMALIZED_NO_GO")
        self.assertEqual(r["normalized_pair_count"],28)
        self.assertEqual(r["m15_rows_structurally_read"],28)
        self.assertEqual(r["tick_rows_structurally_read"],28)
        self.assertEqual(r["m15_bucket_samples_retained"],28)
        self.assertEqual(r["guard_classification_summary"][
            "same_utc_m15_bucket_tick_claim_only"],28)
        self.assertEqual(len(r["normalized_pair_claims"]),28)
        self.assertFalse(any(hasattr(x,"bid") or hasattr(x,"ask")
                             for x in r["normalized_pair_claims"]))

    def test_02_valid_numpy_like_named_fields_and_integer_scalars(self):
        rows=cohort()
        for i,row in enumerate(rows):
            rows[i]=replace(row,
                m15_rows=NumpyLikeArray([NumpyLikeRow(BAR_OPEN)]),
                tick_rows=NumpyLikeArray([NumpyLikeRow(BAR_OPEN+10,
                                             (BAR_OPEN+10)*1000+123)]))
        r=self.check(rows)
        self.safe(r)
        self.assertEqual(r["normalized_pair_count"],28)
        self.assertEqual(r["guard_classification_summary"][
            "same_utc_m15_bucket_tick_claim_only"],28)

    def test_03_equal_time_msc_legal_but_one_bucket_sample(self):
        t=sample_tick(BAR_OPEN+12,123)
        r=self.check(cohort(ticks=[t,dict(t)]))
        self.safe(r)
        self.assertEqual(r["tick_rows_structurally_read"],56)
        self.assertEqual(r["m15_bucket_samples_retained"],28)
        self.assertEqual(r["guard_classification_summary"][
            "same_utc_m15_bucket_tick_claim_only"],28)

    def test_04_detect_minus_2_hour_shift_suspicious_not_correction(self):
        r=self.check(cohort(ticks=[sample_tick(FIRST+10)]))
        self.safe(r)
        self.assertEqual(r["guard_classification_summary"][
            "possible_2h_3h_offset_unproven"],28)
        self.assertEqual(r["normalized_pair_claims"][0].
                         first_m15_open_seconds_utc_epoch,BAR_OPEN)

    def test_05_no_bars_and_no_ticks_yields_unknown(self):
        r=self.check(cohort(bars=[],ticks=[]))
        self.safe(r)
        self.assertEqual(r["raw_m15_empty_pairs"],28)
        self.assertEqual(r["raw_tick_empty_pairs"],28)
        self.assertEqual(r["guard_classification_summary"][
            "no_m15_for_comparison_claim_only"],28)

    def test_06_no_bar_but_ticks_not_synthetic_bar(self):
        r=self.check(cohort(bars=[]))
        self.safe(r)
        self.assertEqual(r["m15_rows_structurally_read"],0)
        self.assertEqual(r["tick_rows_structurally_read"],28)
        self.assertEqual(r["guard_classification_summary"][
            "no_m15_for_comparison_claim_only"],28)

    def test_07_six_ticks_two_buckets_only_two_samples_per_pair(self):
        ts=[sample_tick(BAR_OPEN+i) for i in range(4)]
        ts.extend([sample_tick(BAR_OPEN+900+j) for j in range(2)])
        r=self.check(cohort(ticks=ts))
        self.safe(r)
        self.assertEqual(r["tick_rows_structurally_read"],28*6)
        self.assertEqual(r["m15_bucket_samples_retained"],28*2)

    def test_08_at_most_21_distinct_quarterhour_buckets(self):
        ts=[sample_tick(FIRST+900*i) for i in range(21)]
        r=self.check(cohort(ticks=ts))
        self.safe(r)
        self.assertEqual(r["m15_bucket_samples_retained"],28*21)
        self.assertEqual(len(r["normalized_pair_claims"][0].tick_samples),21)

    def test_09_summer_2027_21utc_after_dst_switch_accepted(self):
        summer=datetime(2027,3,14,21,tzinfo=UTC)
        r=self.check(nominal=summer,
            now=summer+timedelta(hours=5,minutes=20))
        self.safe(r)
        self.assertEqual(r["normalized_pair_count"],28)

    def test_10_summer_wrong_22utc_rejected(self):
        summer=datetime(2027,3,14,22,tzinfo=UTC)
        r=self.check(nominal=summer,
            now=summer+timedelta(hours=5,minutes=20))
        self.assertEqual(r["reason"],"INVALID_TIME_OR_RESEARCH_WINDOW")

    def test_11_pre_campaign_sunday_not_allowed(self):
        old=datetime(2026,11,15,22,tzinfo=UTC)
        r=self.check(nominal=old,now=old+timedelta(hours=5,minutes=20))
        self.safe(r)
        self.assertEqual(r["normalized_pair_count"],0)

    def test_12_naive_and_microsecond_dates_block(self):
        for nominal in (datetime(2026,12,13,22),
                        SUN+timedelta(microseconds=1)):
            with self.subTest(nominal=nominal):
                self.assertEqual(self.check(nominal=nominal)["state"],
                    "LAB_FX28_SUNDAY_RAW_MT5_TIME_NORMALIZATION_BLOCKED_NO_GO")

    def test_13_before_all_bars_close_time_rejected(self):
        self.assertEqual(
            self.check(now=SUN+timedelta(hours=5))["normalized_pair_count"],0)

    def test_14_more_than_one_hour_after_data_close_block(self):
        self.assertEqual(
            self.check(now=SUN+timedelta(hours=6,minutes=1))["normalized_pair_count"],0)

    def test_15_none_m15_api_error_not_empty(self):
        p=cohort()
        p[0]=replace(p[0],m15_rows=None)
        r=self.check(p)
        self.safe(r)
        self.assertEqual(r["reason"],"MT5_RETURNED_NONE_MALFORMED_OR_OVERSIZED_RAW_ROWS")

    def test_16_none_tick_api_error_not_empty(self):
        p=cohort()
        p[0]=replace(p[0],tick_rows=None)
        r=self.check(p)
        self.safe(r)
        self.assertEqual(r["reason"],"MT5_RETURNED_NONE_MALFORMED_OR_OVERSIZED_RAW_ROWS")

    def test_17_27_or_duplicate_fx28_rejected(self):
        p=cohort()
        self.assertEqual(self.check(p[:27])["reason"],"INCOMPLETE_28_PAIR_RAW_ROSTER")
        p[-1]=replace(p[-1],pair=p[0].pair)
        self.assertEqual(self.check(p)["reason"],"RAW_PAIR_OR_QUERY_TIMEFRAME_CLOCK_DRIFT")

    def test_18_XAUUSD_not_in_fx28_roster(self):
        p=cohort()
        p[-1]=replace(p[-1],pair="XAUUSD")
        self.assertEqual(self.check(p)["reason"],"RAW_PAIR_OR_QUERY_TIMEFRAME_CLOCK_DRIFT")

    def test_19_wrong_terminal_timeframe_or_tick_flags(self):
        for change in ({"terminal_path_claim":"OTHER_BROKER"},
                       {"m15_timeframe_claim":"H1"},
                       {"tick_flags_claim":"COPY_TICKS_TRADE"}):
            p=cohort()
            p[0]=replace(p[0],**change)
            with self.subTest(change=change):
                self.assertEqual(self.check(p)["reason"],
                                 "RAW_PAIR_OR_QUERY_TIMEFRAME_CLOCK_DRIFT")

    def test_20_changed_raw_history_request_bounds(self):
        for change in (
            {"m15_request_start_utc":SUN+timedelta(minutes=15)},
            {"m15_request_end_inclusive_utc":SUN+timedelta(hours=5)},
            {"tick_request_start_utc":SUN+timedelta(minutes=15)},
            {"tick_request_end_exclusive_utc":SUN+timedelta(hours=5)}):
            p=cohort()
            p[0]=replace(p[0],**change)
            with self.subTest(change=change):
                self.assertEqual(self.check(p)["reason"],
                                 "RAW_PAIR_OR_QUERY_TIMEFRAME_CLOCK_DRIFT")

    def test_21_bad_m15_epoch_outside_grid_or_not_sorted(self):
        for bars in (
            [{"time":FIRST+1}],
            [{"time":FIRST-900}],
            [{"time":FIRST+5*3600}],
            [{"time":BAR_OPEN+900},{"time":BAR_OPEN}],
            [{"time":BAR_OPEN},{"time":BAR_OPEN}]):
            with self.subTest(bars=bars):
                self.assertEqual(self.check(cohort(bars=bars))["reason"],
                    "M15_RAW_TIME_NOT_STRICTLY_ASCENDING_ON_UTC_GRID")

    def test_22_m15_time_float_or_bool_rejected(self):
        for value in (float(BAR_OPEN), True):
            self.assertEqual(self.check(cohort(bars=[{"time":value}]))["reason"],
                "M15_RAW_TIME_NOT_STRICTLY_ASCENDING_ON_UTC_GRID")

    def test_23_missing_tick_time_msc_rejected(self):
        self.assertEqual(self.check(cohort(ticks=[{"time":BAR_OPEN+10}]))["reason"],
            "RAW_TICK_SECONDS_MSC_OR_SORTING_INVALID")

    def test_24_float_time_msc_or_time_not_rounded(self):
        t=sample_tick(BAR_OPEN+10)
        for k in ("time","time_msc"):
            bad=dict(t)
            bad[k]=float(bad[k])
            self.assertEqual(self.check(cohort(ticks=[bad]))["reason"],
                "RAW_TICK_SECONDS_MSC_OR_SORTING_INVALID")

    def test_25_conflicting_seconds_msc_or_reverse_order(self):
        t=sample_tick(BAR_OPEN+10)
        wrong=dict(t)
        wrong["time_msc"]+=1000
        self.assertEqual(self.check(cohort(ticks=[wrong]))["reason"],
            "RAW_TICK_SECONDS_MSC_OR_SORTING_INVALID")
        self.assertEqual(self.check(cohort(ticks=[
            sample_tick(BAR_OPEN+11),t]))["reason"],
            "RAW_TICK_SECONDS_MSC_OR_SORTING_INVALID")

    def test_26_tick_epoch_before_start_or_after_end(self):
        for bad in (FIRST-1,FIRST+5*3600+900):
            with self.subTest(bad=bad):
                self.assertEqual(self.check(cohort(ticks=[sample_tick(bad)]))["reason"],
                    "RAW_TICK_SECONDS_MSC_OR_SORTING_INVALID")

    def test_27_more_than_20_bars_blocks(self):
        bad=[{"time":FIRST+900*i} for i in range(21)]
        self.assertEqual(self.check(cohort(bars=bad))["reason"],
            "MT5_RETURNED_NONE_MALFORMED_OR_OVERSIZED_RAW_ROWS")

    def test_28_more_than_120000_tick_rows_blocks_without_scan(self):
        class Huge:
            dtype=SimpleNamespace(names=("time","time_msc"))
            def __len__(self):
                return MAX_RAW_TICK_ROWS+1
            def __iter__(self):
                raise AssertionError("SHOULD_NOT_ITERATE_OVERSIZED")
        p=cohort()
        p[0]=replace(p[0],tick_rows=Huge())
        self.assertEqual(self.check(p)["reason"],
            "MT5_RETURNED_NONE_MALFORMED_OR_OVERSIZED_RAW_ROWS")

    def test_29_structured_array_missing_time_msc_field_blocks(self):
        class TimeOnlyRow:
            dtype=SimpleNamespace(names=("time",))
            def __getitem__(self,key):
                return IntLike(BAR_OPEN+10)
        p=cohort()
        p[0]=replace(p[0],tick_rows=NumpyLikeArray([TimeOnlyRow()]))
        self.assertEqual(self.check(p)["reason"],
            "RAW_TICK_SECONDS_MSC_OR_SORTING_INVALID")

    def test_30_price_bid_ask_not_read_or_exposed(self):
        class PrivatePrice:
            def __float__(self):
                raise AssertionError("PRICE MUST NOT BE ACCESSED")
            def __str__(self):
                raise AssertionError("PRICE MUST NOT BE EXPOSED")
        row={"time":BAR_OPEN+10,"time_msc":(BAR_OPEN+10)*1000+420,
             "bid":PrivatePrice(),"ask":PrivatePrice()}
        r=self.check(cohort(ticks=[row]))
        self.safe(r)
        self.assertEqual(r["tick_rows_structurally_read"],28)

    def test_31_structured_numpy_missing_time_field_rejected(self):
        p=cohort()
        p[0]=replace(p[0],m15_rows=["NOT_A_ROW"])
        self.assertEqual(self.check(p)["reason"],
            "M15_RAW_TIME_NOT_STRICTLY_ASCENDING_ON_UTC_GRID")


if __name__=="__main__":
    unittest.main(verbosity=2)
