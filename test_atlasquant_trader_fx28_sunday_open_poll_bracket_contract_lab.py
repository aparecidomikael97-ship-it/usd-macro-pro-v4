"""Synthetic 28+28 local MT5 poll claims. Zero I/O, price or live session."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
import unittest

from atlasquant_fx_universe import OFFICIAL_PAIRS
from atlasquant_trader_fx28_sunday_open_poll_bracket_contract_lab import (
    LocalM15PollClaim, EXPECTED_TERMINAL, SOURCE, BAR, EMPTY, ERROR,
    inspect_fx28_sunday_open_two_poll_bracket_lab as inspect,
)

UTC=timezone.utc
NOMINAL=datetime(2026,12,13,22,tzinfo=UTC)
NOW=datetime(2026,12,14,0,tzinfo=UTC)


def poll(first: bool, *, start=NOMINAL, mode=EMPTY, bar=None):
    when=start+timedelta(minutes=30 if first else 45)
    return [LocalM15PollClaim(
        pair=pair,
        started_at_utc=when-timedelta(seconds=5),
        finished_at_utc=when,
        api_result_kind=mode,
        first_closed_bar_open_utc=bar,
    ) for pair in OFFICIAL_PAIRS]


class SundayFirstAvailabilityBracketTests(unittest.TestCase):
    def check(self, before=None, after=None, *, nominal=NOMINAL, now=NOW):
        if before is None:
            before=poll(True,start=nominal)
        if after is None:
            after=poll(False,start=nominal,mode=BAR,
                       bar=nominal+timedelta(minutes=15))
        return inspect(
            research_sunday_start_utc=nominal,
            prior_cohort=before, later_cohort=after,
            inspected_at_utc=now)

    def safe(self, r):
        self.assertFalse(r["mt5_terminal_path_not_broker_identity_proof"] is False)
        for name in (
            "first_seen_time_independently_attested",
            "broker_session_open_time_authenticated",
            "actual_market_open_inferred",
            "price_origin_independently_authenticated",
            "first_bar_20261115_backfilled",
            "original_672_slots_modified",
            "scheduler_enabled","can_run_market_probe",
            "trade_authorized","publishable",
        ):
            self.assertFalse(r[name],name)
        self.assertIsNone(r["out_of_sample_accuracy"])
        self.assertIsNone(r["calibrated_direction_probability"])
        self.assertEqual((r["mt5_calls"],r["http_requests"],
                          r["file_writes"],r["new_cost_brl"]),(0,0,0,0))
        self.assertEqual(r["operational_bias"],"AGUARDAR")

    def test_01_28_late_availability_after_prior_candle_already_closed(self):
        r=self.check()
        self.safe(r)
        self.assertEqual(r["state"],
            "LAB_FX28_SUNDAY_OPEN_28_PAIR_TWO_POLL_DOCUMENTARY_ONLY_NO_GO")
        self.assertEqual(r["before_cohort_count"],28)
        self.assertEqual(r["after_cohort_count"],28)
        self.assertEqual(r["claimed_first_closed_candle_appeared_between_polls"],28)
        self.assertEqual(r["claimed_not_returned_after_prior_close"],28)
        self.assertEqual(r["previous_poll_before_candle_close"],0)
        self.assertEqual(r["still_empty_in_both_polls"],0)
        self.assertEqual(len(r["rows"]),28)
        self.assertEqual(set(x["pair"] for x in r["rows"]),set(OFFICIAL_PAIRS))
        self.assertFalse(any(x["local_first_seen_time_authenticated"]
                             or x["broker_first_open_authenticated"]
                             for x in r["rows"]))

    def test_02_if_first_candle_closed_during_poll_gap_do_not_claim_delay(self):
        r=self.check(after=poll(False,mode=BAR,
                                bar=NOMINAL+timedelta(minutes=30)))
        self.safe(r)
        self.assertEqual(r["previous_poll_before_candle_close"],28)
        self.assertEqual(r["claimed_not_returned_after_prior_close"],0)
        self.assertTrue(all(x["poll_comparison_class"] ==
            "M15_CLOSED_BETWEEN_POLLS_NO_SOURCE_LATENCY_INFERRED"
            for x in r["rows"]))

    def test_03_no_bar_in_both_polls_not_zero_prices_attested(self):
        r=self.check(after=poll(False))
        self.safe(r)
        self.assertEqual(r["still_empty_in_both_polls"],28)
        self.assertEqual(r["claimed_first_closed_candle_appeared_between_polls"],0)
        self.assertTrue(all(x["first_closed_bar_open_at_utc_claim"] is None
                            for x in r["rows"]))

    def test_04_same_first_closed_candle_in_both_polls(self):
        before=poll(True,mode=BAR,bar=NOMINAL+timedelta(minutes=15))
        after=poll(False,mode=BAR,bar=NOMINAL+timedelta(minutes=15))
        r=self.check(before=before,after=after)
        self.safe(r)
        self.assertEqual(r["claimed_first_closed_candle_appeared_between_polls"],0)
        self.assertTrue(all(x["poll_comparison_class"] ==
            "SAME_FIRST_CLOSED_M15_IN_BOTH_POLLS_CLAIM_ONLY"
            for x in r["rows"]))

    def test_05_earlier_present_but_later_missing_rejected(self):
        b=poll(True,mode=BAR,bar=NOMINAL+timedelta(minutes=15))
        r=self.check(before=b,after=poll(False))
        self.assertEqual(r["reason"],"EARLIER_CLOSED_BAR_DISAPPEARED_OR_CHANGED")

    def test_06_first_bar_changed_between_polls_rejected(self):
        b=poll(True,mode=BAR,bar=NOMINAL+timedelta(minutes=15))
        a=poll(False,mode=BAR,bar=NOMINAL+timedelta(minutes=30))
        self.assertEqual(self.check(b,a)["reason"],
                         "EARLIER_CLOSED_BAR_DISAPPEARED_OR_CHANGED")

    def test_07_api_none_not_equated_with_empty(self):
        before=poll(True)
        before[0]=replace(before[0],api_result_kind=ERROR)
        r=self.check(before=before)
        self.safe(r)
        self.assertEqual(r["reason"],
                         "INVALID_28_PAIR_POLL_COHORT_OR_MT5_RETURNED_NONE")

    def test_08_not_all_28_pairs_rejected(self):
        self.assertEqual(self.check(before=poll(True)[:27])["state"],
                         "LAB_FX28_SUNDAY_OPEN_TWO_POLL_BLOCKED_NO_GO")

    def test_09_duplicate_pair_rejected(self):
        before=poll(True)
        before[-1]=replace(before[-1],pair=before[0].pair)
        self.assertEqual(self.check(before=before)["reason"],
                         "INVALID_28_PAIR_POLL_COHORT_OR_MT5_RETURNED_NONE")

    def test_10_unknown_pair_rejected(self):
        after=poll(False,mode=BAR,bar=NOMINAL+timedelta(minutes=15))
        after[-1]=replace(after[-1],pair="XAUUSD")
        self.assertEqual(self.check(after=after)["state"],
                         "LAB_FX28_SUNDAY_OPEN_TWO_POLL_BLOCKED_NO_GO")

    def test_11_wrong_terminal_path_rejected(self):
        before=poll(True)
        before[0]=replace(before[0],
            mt5_terminal_path_claim=r"C:\Program Files\OtherBroker\terminal64.exe")
        self.assertEqual(self.check(before=before)["reason"],
                         "INVALID_28_PAIR_POLL_COHORT_OR_MT5_RETURNED_NONE")

    def test_12_wrong_source_identity_claim_rejected(self):
        before=poll(True)
        before[0]=replace(before[0],source_kind_claim="BROKER_ATTESTED")
        self.assertEqual(self.check(before=before)["reason"],
                         "INVALID_28_PAIR_POLL_COHORT_OR_MT5_RETURNED_NONE")

    def test_13_disconnected_terminal_or_hidden_symbol_rejected(self):
        for field in ("terminal_connected_claim","market_watch_visible_claim"):
            b=poll(True)
            b[0]=replace(b[0],**{field:False})
            with self.subTest(field=field):
                self.assertEqual(self.check(before=b)["reason"],
                    "INVALID_28_PAIR_POLL_COHORT_OR_MT5_RETURNED_NONE")

    def test_14_m15_cannot_be_claimed_before_candle_close(self):
        after=poll(False,mode=BAR,bar=NOMINAL+timedelta(minutes=45))
        self.assertEqual(self.check(after=after)["reason"],
                         "INVALID_28_PAIR_POLL_COHORT_OR_MT5_RETURNED_NONE")

    def test_15_empty_cannot_claim_bar_timestamp(self):
        before=poll(True)
        before[0]=replace(before[0],
            first_closed_bar_open_utc=NOMINAL+timedelta(minutes=15))
        self.assertEqual(self.check(before=before)["state"],
                         "LAB_FX28_SUNDAY_OPEN_TWO_POLL_BLOCKED_NO_GO")

    def test_16_returned_bar_needs_actual_open_timestamp_claim(self):
        after=poll(False,mode=BAR,bar=None)
        self.assertEqual(self.check(after=after)["state"],
                         "LAB_FX28_SUNDAY_OPEN_TWO_POLL_BLOCKED_NO_GO")

    def test_17_more_than_30_min_gap_rejected(self):
        a=poll(False,mode=BAR,bar=NOMINAL+timedelta(minutes=15))
        a=[replace(x,started_at_utc=x.started_at_utc+timedelta(minutes=40),
                   finished_at_utc=x.finished_at_utc+timedelta(minutes=40))
           for x in a]
        self.assertEqual(self.check(after=a)["reason"],
                         "POLL_COHORT_ORDER_GAP_TOO_LARGE_OR_OVERLAPPED")

    def test_18_overlap_of_two_cohorts_rejected(self):
        a=poll(False,mode=BAR,bar=NOMINAL+timedelta(minutes=15))
        a=[replace(x,started_at_utc=x.started_at_utc-timedelta(minutes=16),
                   finished_at_utc=x.finished_at_utc-timedelta(minutes=16))
           for x in a]
        self.assertEqual(self.check(after=a)["reason"],
                         "POLL_COHORT_ORDER_GAP_TOO_LARGE_OR_OVERLAPPED")

    def test_19_cannot_spread_28_pair_query_across_an_hour(self):
        b=poll(True)
        b[-1]=replace(b[-1],
            started_at_utc=b[-1].started_at_utc+timedelta(minutes=12),
            finished_at_utc=b[-1].finished_at_utc+timedelta(minutes=12))
        self.assertEqual(self.check(before=b)["reason"],
                         "INVALID_28_PAIR_POLL_COHORT_OR_MT5_RETURNED_NONE")

    def test_20_a_single_pair_api_call_cannot_take_30_seconds(self):
        b=poll(True)
        b[0]=replace(b[0],
            started_at_utc=b[0].finished_at_utc-timedelta(seconds=30))
        self.assertEqual(self.check(before=b)["reason"],
                         "INVALID_28_PAIR_POLL_COHORT_OR_MT5_RETURNED_NONE")

    def test_21_cannot_poll_still_frozen_campaign_20261115(self):
        nominal=datetime(2026,11,15,22,tzinfo=UTC)
        r=self.check(nominal=nominal)
        self.safe(r)
        self.assertEqual(r["state"],
                         "LAB_FX28_SUNDAY_OPEN_TWO_POLL_BLOCKED_NO_GO")

    def test_22_sunday_in_winter_ny17_22utc_allowed(self):
        self.assertEqual(self.check()["before_cohort_count"],28)

    def test_23_sunday_summer_ny17_21utc_allowed(self):
        nominal=datetime(2027,3,14,21,tzinfo=UTC)
        r=self.check(nominal=nominal,now=nominal+timedelta(hours=2))
        self.safe(r)
        self.assertEqual(r["before_cohort_count"],28)

    def test_24_summer_sunday_wrong_22utc_rejected(self):
        nominal=datetime(2027,3,14,22,tzinfo=UTC)
        r=self.check(nominal=nominal,now=nominal+timedelta(hours=2))
        self.safe(r)
        self.assertEqual(r["state"],
                         "LAB_FX28_SUNDAY_OPEN_TWO_POLL_BLOCKED_NO_GO")

    def test_25_naive_or_microsecond_timestamps_rejected(self):
        b=poll(True)
        b[0]=replace(b[0],finished_at_utc=b[0].finished_at_utc.replace(tzinfo=None))
        self.assertEqual(self.check(before=b)["state"],
                         "LAB_FX28_SUNDAY_OPEN_TWO_POLL_BLOCKED_NO_GO")
        a=poll(False,mode=BAR,bar=NOMINAL+timedelta(minutes=15))
        a[0]=replace(a[0],first_closed_bar_open_utc=
                       NOMINAL+timedelta(minutes=15,microseconds=1))
        self.assertEqual(self.check(after=a)["state"],
                         "LAB_FX28_SUNDAY_OPEN_TWO_POLL_BLOCKED_NO_GO")

    def test_26_poll_past_five_hour_history_scope_rejected(self):
        a=poll(False,mode=BAR,bar=NOMINAL+timedelta(minutes=15))
        a=[replace(x,started_at_utc=NOMINAL+timedelta(hours=5,minutes=20),
                   finished_at_utc=NOMINAL+timedelta(hours=5,minutes=20,seconds=5))
           for x in a]
        r=self.check(after=a,now=NOMINAL+timedelta(hours=6))
        self.assertEqual(r["state"],
                         "LAB_FX28_SUNDAY_OPEN_TWO_POLL_BLOCKED_NO_GO")

    def test_27_future_inspection_clock_cannot_precede_poll_receipt(self):
        r=self.check(now=NOMINAL+timedelta(minutes=40))
        self.assertEqual(r["reason"],
                         "INVALID_28_PAIR_POLL_COHORT_OR_MT5_RETURNED_NONE")


if __name__=="__main__":
    unittest.main(verbosity=2)
