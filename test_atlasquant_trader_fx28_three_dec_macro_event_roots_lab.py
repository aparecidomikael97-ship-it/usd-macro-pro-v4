"""No real HTTP data: three official schedule references and FX28 slots."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from zoneinfo import ZoneInfoNotFoundError
import unittest

from atlasquant_fx_universe import OFFICIAL_PAIRS, split_pair
from atlasquant_trader_fx28_ny17_prospective_campaign_lab import (
    FROZEN_START_UTC, FROZEN_END_UTC, _nominal_windows,
)
from atlasquant_trader_fx28_rbnz_dec9_event_window_overlay_lab import (
    inspect_rbnz_dec9_event_ny17_relevance_lab as rbnz_only,
)
from atlasquant_trader_fx28_three_dec_macro_event_roots_lab import (
    BOJ_ROOT, SNB_ROOT, SCHEDULE_REFERENCE_ONLY,
    inspect_three_dec2026_macro_event_roots_lab as inspect,
)

UTC=timezone.utc
NOW=datetime(2026,11,14,11,0,tzinfo=UTC)
RBNZ=datetime(2026,12,9,1,0,tzinfo=UTC)
BOJ=datetime(2026,12,9,23,50,tzinfo=UTC)
SNB=datetime(2026,12,10,8,30,tzinfo=UTC)


class ThreeOfficialDecemberEventsTests(unittest.TestCase):
    def audit(self,now=NOW):
        return inspect(inspected_at_utc=now)

    def safe(self,r):
        self.assertEqual(r["operational_bias"],"AGUARDAR")
        self.assertTrue(r["source_schedules_are_public_page_references_not_original_bytes"])
        self.assertFalse(r["source_schedules_independently_first_seen_witnessed"])
        self.assertFalse(r["calendar_last_revision_independently_authenticated"])
        self.assertFalse(r["event_results_independently_authenticated"])
        self.assertFalse(r["pre_event_consensus_available_and_authenticated"])
        self.assertTrue(r["scheduled_not_same_as_announcement_released"])
        self.assertTrue(r["boj_cgpi_not_boj_policy_rate_decision"])
        self.assertTrue(r["rbnz_snb_policy_decisions_do_not_imply_rate_change"])
        self.assertTrue(r["no_outside_pairs_proved_immune_to_spillover"])
        self.assertIsNone(r["model_direction"])
        self.assertIsNone(r["calibrated_probability"])
        self.assertIsNone(r["out_of_sample_accuracy"])
        self.assertEqual(r["expected_pair_horizon_slots"],672)
        for key in ("trade_authorized","publishable","live_alert_allowed",
                    "worker_enabled","scheduler_enabled"):
            self.assertFalse(r[key],key)
        self.assertEqual((r["http_requests"],r["file_writes"],
                          r["new_cost_brl"]),(0,0,0))

    def complete(self,r):
        self.safe(r)
        self.assertEqual(r["state"],
                         "LAB_FX28_THREE_DEC_EVENTS_RECONCILED_PUBLIC_SCHEDULE_NO_GO")
        self.assertTrue(r["all_672_campaign_slots_unchanged"])
        self.assertEqual(r["event_root_count"],3)
        self.assertEqual(r["root_to_pair_horizon_associations"],42)
        self.assertEqual(r["unique_pair_horizon_slots_exposed"],38)
        self.assertEqual(r["cross_event_duplicate_slot_associations"],4)
        self.assertEqual(r["multi_root_slot_count"],4)
        self.assertEqual(len(r["events"]),3)
        self.assertEqual(len(r["distinct_slot_exposures"]),38)
        self.assertEqual(
            len(set(x["slot_id"] for x in r["distinct_slot_exposures"])),38)
        self.assertEqual(
            sum(len(s["event_roots"]) for s in r["distinct_slot_exposures"]),42)
        for e in r["events"]:
            self.assertFalse(e["source_is_captured_original"])
            self.assertFalse(e["first_seen_issuer_timestamp_authenticated"])
            self.assertFalse(e["actual_release_observed"])
            self.assertFalse(e["result_or_rate_change_known"])
            self.assertIsNone(e["pre_event_consensus"])
            self.assertIsNone(e["signed_fx_effect"])
            self.assertTrue(e["one_root_not_fourteen_independent_events"])
            self.assertEqual(e["direct_pair_horizon_associations"],14)
        for s in r["distinct_slot_exposures"]:
            self.assertFalse(s["independently_witnessed"])
            self.assertFalse(s["trade_authorized"])
            self.assertIsNone(s["event_direction"])

    def test_01_three_release_times_use_local_iana_zones(self):
        r=self.audit()
        self.complete(r)
        events={e["currency"]:e for e in r["events"]}
        for currency,utc_stamp,cuiaba in (
            ("NZD","2026-12-09T01:00:00+00:00","2026-12-08T21:00:00-04:00"),
            ("JPY","2026-12-09T23:50:00+00:00","2026-12-09T19:50:00-04:00"),
            ("CHF","2026-12-10T08:30:00+00:00","2026-12-10T04:30:00-04:00"),
        ):
            self.assertEqual(events[currency]["scheduled_at_utc_interpreted"],utc_stamp)
            self.assertEqual(events[currency]["scheduled_at_cuiaba_interpreted"],cuiaba)

    def test_02_d1_and_w1_intersections_not_invented(self):
        r=self.audit()
        self.complete(r)
        by={e["currency"]:e for e in r["events"]}
        window=lambda code,h: next(x for x in by[code]["horizon_windows"]
                                    if x["horizon"]==h)
        self.assertEqual(window("NZD","D1")["start_utc"],
                         "2026-12-08T22:00:00+00:00")
        self.assertEqual(window("JPY","D1")["start_utc"],
                         "2026-12-09T22:00:00+00:00")
        self.assertEqual(window("CHF","D1")["start_utc"],
                         "2026-12-09T22:00:00+00:00")
        for c in ("NZD","JPY","CHF"):
            self.assertEqual(window(c,"W1")["start_utc"],
                             "2026-12-06T22:00:00+00:00")
            self.assertEqual(window(c,"W1")["end_utc"],
                             "2026-12-11T22:00:00+00:00")

    def test_03_every_root_has_seven_direct_fx_pairs_twice(self):
        r=self.audit()
        self.complete(r)
        for event in r["events"]:
            direct={p for p in OFFICIAL_PAIRS
                    if event["currency"] in split_pair(p)}
            self.assertEqual(len(direct),7)
            for h in ("D1","W1"):
                window=next(x for x in event["horizon_windows"] if x["horizon"]==h)
                roots={slot["pair"] for slot in r["distinct_slot_exposures"]
                       if slot["horizon"]==h
                       and slot["window_start_utc"]==window["start_utc"]
                       and event["event_root_id"] in slot["event_roots"]}
                self.assertEqual(roots,direct)

    def test_04_three_roots_not_fortytwo_independent_events(self):
        r=self.audit()
        self.complete(r)
        roots={e["event_root_id"] for e in r["events"]}
        self.assertEqual(roots,
                         {SCHEDULE_REFERENCE_ONLY[0][0],BOJ_ROOT,SNB_ROOT})
        self.assertEqual(len(roots),3)

    def test_05_four_overlaps_are_at_correct_fx_horizon(self):
        r=self.audit()
        self.complete(r)
        mult=[s for s in r["distinct_slot_exposures"]
              if len(s["event_roots"])>1]
        self.assertEqual(len(mult),4)
        observed={(s["horizon"],frozenset(split_pair(s["pair"])))
                  for s in mult}
        expected={
            ("D1",frozenset(("CHF","JPY"))),
            ("W1",frozenset(("CHF","JPY"))),
            ("W1",frozenset(("CHF","NZD"))),
            ("W1",frozenset(("JPY","NZD"))),
        }
        self.assertEqual(observed,expected)

    def test_06_boj_cgpi_not_monetary_policy_meeting(self):
        r=self.audit()
        self.complete(r)
        japan=next(e for e in r["events"] if e["currency"]=="JPY")
        self.assertEqual(japan["metric_type"],
                         "BOJ_NOV2026_CORPORATE_GOODS_PRICE_INDEX")
        self.assertIn("/about/calendar/index.htm",
                      japan["schedule_reference_url"])
        self.assertNotIn("POLICY_DECISION",japan["metric_type"])

    def test_07_snb_and_rbnz_policy_meetings_are_not_known_outcomes(self):
        r=self.audit()
        self.complete(r)
        for e in r["events"]:
            if e["currency"] in ("CHF","NZD"):
                self.assertIn("POLICY",e["metric_type"])
                self.assertFalse(e["result_or_rate_change_known"])
                self.assertIsNone(e["signed_fx_effect"])

    def test_08_future_before_all_events_not_forecast_witness(self):
        r=self.audit()
        self.complete(r)
        self.assertTrue(all(e["schedule_status_at_inspection"]==
                            "UPCOMING_UNATTESTED_PUBLIC_REFERENCE"
                            for e in r["events"]))
        self.assertFalse(r["source_schedules_independently_first_seen_witnessed"])

    def test_09_rbnz_second_before_and_at_schedule(self):
        before=self.audit(RBNZ-timedelta(seconds=1))
        at=self.audit(RBNZ)
        self.complete(before)
        self.complete(at)
        nzd=lambda r:next(e for e in r["events"] if e["currency"]=="NZD")
        self.assertEqual(nzd(before)["schedule_status_at_inspection"],
                         "UPCOMING_UNATTESTED_PUBLIC_REFERENCE")
        self.assertEqual(nzd(at)["schedule_status_at_inspection"],
                         "ELAPSED_SCHEDULE_NOT_BACKFILLABLE_FORECAST")
        self.assertFalse(nzd(at)["actual_release_observed"])

    def test_10_boj_second_before_and_snb_moment(self):
        a=self.audit(BOJ-timedelta(seconds=1))
        b=self.audit(SNB)
        self.complete(a)
        self.complete(b)
        ev=lambda r,c:next(e for e in r["events"] if e["currency"]==c)
        self.assertEqual(ev(a,"JPY")["schedule_status_at_inspection"],
                         "UPCOMING_UNATTESTED_PUBLIC_REFERENCE")
        self.assertEqual(ev(b,"CHF")["schedule_status_at_inspection"],
                         "ELAPSED_SCHEDULE_NOT_BACKFILLABLE_FORECAST")

    def test_11_after_campaign_does_not_reconstruct_forecast(self):
        r=self.audit(FROZEN_END_UTC+timedelta(days=1))
        self.complete(r)
        self.assertTrue(all(e["schedule_status_at_inspection"]==
                            "ELAPSED_SCHEDULE_NOT_BACKFILLABLE_FORECAST"
                            for e in r["events"]))

    def test_12_invalid_clock_fails_closed(self):
        for now in (None,"2026-11-14T11:00:00Z",
                    NOW.replace(tzinfo=None),
                    NOW+timedelta(microseconds=1)):
            with self.subTest(now=now):
                r=self.audit(now)
                self.safe(r)
                self.assertEqual(r["state"],
                                 "LAB_FX28_THREE_DEC_EVENT_OVERLAY_BLOCKED_NO_GO")
                self.assertEqual(r["unique_pair_horizon_slots_exposed"],0)

    def test_13_missing_iana_zoneinfo_fails_closed(self):
        with patch("atlasquant_trader_fx28_three_dec_macro_event_roots_lab.ZoneInfo",
                   side_effect=ZoneInfoNotFoundError("synthetic unavailable")):
            r=self.audit()
        self.safe(r)
        self.assertEqual(r["reason"],"REQUIRED_IANA_TIMEZONE_DATA_UNAVAILABLE")

    def test_14_no_frozen_calendar_mutations(self):
        r=self.audit()
        self.complete(r)
        self.assertEqual((len(_nominal_windows("D1")),
                          len(_nominal_windows("W1"))),(20,4))
        self.assertEqual(_nominal_windows("D1")[0][0],FROZEN_START_UTC)
        self.assertEqual(_nominal_windows("W1")[-1][1],FROZEN_END_UTC)
        self.assertEqual(len(OFFICIAL_PAIRS),28)

    def test_15_original_rbnz_single_event_overlay_remains_consistent(self):
        all_events=self.audit()
        single=rbnz_only(inspected_at_utc=NOW)
        self.complete(all_events)
        self.assertEqual(single["direct_pair_horizon_slots_intersecting_event"],14)
        rbnz_set={s["slot_id"] for s in single["direct_pair_horizon_slot_ids"]}
        merged_set={s["slot_id"] for s in all_events["distinct_slot_exposures"]
                    if SCHEDULE_REFERENCE_ONLY[0][0] in s["event_roots"]}
        self.assertEqual(rbnz_set,merged_set)

    def test_16_single_research_schedule_root_not_price_or_consensus(self):
        r=self.audit()
        self.complete(r)
        for e in r["events"]:
            self.assertNotIn("price",e)
            self.assertNotIn("bid",e)
            self.assertNotIn("ask",e)
            self.assertNotIn("consensus_pct",e)
            self.assertIsNone(e["pre_event_consensus"])


if __name__=="__main__":
    unittest.main()
