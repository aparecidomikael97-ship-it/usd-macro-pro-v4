"""Adversarial pre-event provenance tests; NO real HTML or provider requests."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest

from atlasquant_trader_us_dec2026_pre_event_consensus_custody_lab import (
    inspect_us_dec2026_pre_event_consensus_custody_lab as custody,
    _td_edition_in_capture_window,
)
from atlasquant_trader_us_dec2026_consensus_original_one_get_lab import (
    capture_dec2026_one_get_original_lab as capture,
    replay_dec2026_one_get_original_lab as replay,
)
from atlasquant_trader_us_dec2026_disk_to_semantics_bridge_lab import (
    replay_dec2026_archives_to_semantic_candidates_lab as bridge,
)
import test_atlasquant_trader_us_dec2026_pre_event_consensus_custody_lab as fx
import test_atlasquant_trader_us_dec2026_consensus_original_one_get_lab as one
import test_atlasquant_trader_us_dec2026_disk_to_semantics_bridge_lab as physical

UTC=timezone.utc
CPI="US_CPI_NOV2026"
PPI="US_PPI_NOV2026"
TD=fx.TD
TE=fx.TE
CPI_RELEASE=fx.RELEASE[CPI]
PPI_RELEASE=fx.RELEASE[PPI]


def stamp(dt):
    return format_datetime(dt.replace(microsecond=0),usegmt=True)


def inspect_one(s):
    return custody(snapshots=(s,), research_cutoff_utc=s.finished_at_utc)


def assert_locked(t, r):
    t.assertEqual(r["frozen_upcoming_economic_event_denominator"],2)
    t.assertEqual(r["validated_out_of_sample_trading_trials"],0)
    t.assertEqual(r["historically_independent_model_forecasts"],0)
    t.assertIsNone(r["validated_fx_accuracy"])
    t.assertIsNone(r["directional_fx_bias"])
    t.assertFalse(r["trade_authorized"])
    t.assertFalse(r["publishable"])
    t.assertFalse(r["original_672_fx28_campaign_slots_modified"])


class DecemberHttpDateAndTDEditionTests(unittest.TestCase):
    def accepted(self,s):
        r=inspect_one(s)
        assert_locked(self,r)
        self.assertEqual(r["state"],"LAB_DEC2026_PRE_EVENT_SOURCE_CUSTODY_ONLY_NO_GO")
        self.assertEqual(r["locally_sha_reconciled_pre_event_source_documents"],1)
        return r

    def denied(self,s):
        r=inspect_one(s)
        assert_locked(self,r)
        self.assertEqual(r["state"],"LAB_DEC2026_PRE_EVENT_SNAPSHOTS_BLOCKED_NO_GO")
        self.assertEqual(r["locally_sha_reconciled_pre_event_source_documents"],0)
        self.assertTrue(all(not row["archived_hashes_only"] for row in r["events"]))
        return r

    def test_01_td_dec8_edition_cpi_capture_dec8_allowed_documentary(self):
        self.accepted(fx.sample())

    def test_02_td_dec8_edition_ppi_capture_dec13_allowed_documentary(self):
        self.accepted(fx.sample(root=PPI))

    def test_03_td_dec8_edition_cpi_capture_dec7_rejected_future_dated(self):
        start=datetime(2026,12,7,10,0,tzinfo=UTC)
        self.denied(fx.sample(end=start+timedelta(seconds=2)))

    def test_04_td_dec8_edition_ppi_capture_dec8_early_allowed_if_after_window(self):
        start=datetime(2026,12,8,13,31,tzinfo=UTC)
        self.accepted(fx.sample(root=PPI,end=start+timedelta(seconds=2)))

    def test_05_td_dec1_old_week_cpi_rejected(self):
        s=fx.sample()
        stale=TD.replace("2026-12-08","2026-12-01")
        self.denied(replace(s,source_url=stale,final_url=stale))

    def test_06_td_dec1_old_week_ppi_rejected(self):
        s=fx.sample(root=PPI)
        stale=TD.replace("2026-12-08","2026-12-01")
        self.denied(replace(s,source_url=stale,final_url=stale))

    def test_07_td_dec12_future_edition_cpi_rejected_at_dec8(self):
        s=fx.sample()
        newer=TD.replace("2026-12-08","2026-12-12")
        self.denied(replace(s,source_url=newer,final_url=newer))

    def test_08_td_invalid_feb_31_edition_rejected(self):
        s=fx.sample()
        invalid=TD.replace("2026-12-08","2026-02-31")
        self.denied(replace(s,source_url=invalid,final_url=invalid))

    def test_09_td_edition_date_is_not_independent_first_seen_proof(self):
        r=self.accepted(fx.sample())
        self.assertFalse(r["publisher_first_seen_and_capture_clock_independently_authenticated"])
        self.assertFalse(r["events"][0]["source_first_seen_independently_verified"])
        self.assertFalse(r["events"][0]["consensus_for_fx_prediction_eligible"])

    def test_10_original_synthetic_te_cpi_response_date_aligned(self):
        self.accepted(fx.sample(provider="TRADING_ECONOMICS"))

    def test_11_http_date_one_minute_older_rejected_not_recent_capture(self):
        s=fx.sample(provider="TRADING_ECONOMICS")
        self.denied(replace(s,http_date_claim=stamp(s.started_at_utc-timedelta(minutes=1))))

    def test_12_http_date_two_hours_older_previous_gap_closed(self):
        s=fx.sample()
        self.denied(replace(s,http_date_claim=stamp(s.started_at_utc-timedelta(hours=2))))

    def test_13_http_date_one_minute_ahead_previous_gap_closed(self):
        s=fx.sample(provider="TRADING_ECONOMICS")
        self.denied(replace(s,http_date_claim=stamp(s.finished_at_utc+timedelta(minutes=1))))

    def test_14_http_date_three_seconds_after_completion_rejected(self):
        s=fx.sample()
        self.denied(replace(s,http_date_claim=stamp(s.finished_at_utc+timedelta(seconds=3))))

    def test_15_http_date_one_second_after_completion_allowed_clock_tolerance(self):
        s=fx.sample()
        self.accepted(replace(s,http_date_claim=stamp(s.finished_at_utc+timedelta(seconds=1))))

    def test_16_http_date_two_seconds_after_completion_allowed_if_before_freeze(self):
        s=fx.sample(provider="TRADING_ECONOMICS")
        self.accepted(replace(s,http_date_claim=stamp(s.finished_at_utc+timedelta(seconds=2))))

    def test_17_http_date_exact_thirty_seconds_before_start_accepted(self):
        s=fx.sample()
        self.accepted(replace(s,http_date_claim=stamp(s.started_at_utc-timedelta(seconds=30))))

    def test_18_http_date_thirty_one_seconds_before_start_rejected(self):
        s=fx.sample()
        self.denied(replace(s,http_date_claim=stamp(s.started_at_utc-timedelta(seconds=31))))

    def test_19_http_date_after_freeze_must_not_qualify_even_if_near_finish(self):
        s=fx.sample(end=CPI_RELEASE-timedelta(hours=1))
        self.denied(replace(s,http_date_claim=stamp(s.finished_at_utc+timedelta(seconds=1))))

    def test_20_server_date_exactly_at_freeze_allowed_only_documentary(self):
        s=fx.sample(end=CPI_RELEASE-timedelta(hours=1))
        self.accepted(replace(s,http_date_claim=stamp(s.finished_at_utc)))

    def test_21_utc_minus_four_local_receipts_and_server_date_same_instant(self):
        s=fx.sample()
        cuiaba=timezone(timedelta(hours=-4))
        converted=replace(
            s,started_at_utc=s.started_at_utc.astimezone(cuiaba),
            finished_at_utc=s.finished_at_utc.astimezone(cuiaba))
        self.assertEqual(inspect_one(s),inspect_one(converted))

    def test_22_two_sources_one_with_stale_date_block_all(self):
        good=fx.sample()
        other=fx.sample(provider="TRADING_ECONOMICS")
        corrupted=replace(other,http_date_claim=stamp(other.started_at_utc-timedelta(minutes=40)))
        r=custody(snapshots=(good,corrupted),
                  research_cutoff_utc=max(good.finished_at_utc,corrupted.finished_at_utc))
        self.assertEqual(r["state"],"LAB_DEC2026_PRE_EVENT_SNAPSHOTS_BLOCKED_NO_GO")
        self.assertEqual(r["locally_sha_reconciled_pre_event_source_documents"],0)
        assert_locked(self,r)

    def test_23_collector_rejects_future_td_edition_before_any_get(self):
        fake=one.FakeHTTP()
        with TemporaryDirectory() as td:
            old=one.MARK-timedelta(days=1)
            r=capture(
                allow_one_official_get=True,
                confirm_bls_schedule_reviewed=True,
                event_root=CPI,provider="TD_ECONOMICS",source_url=TD,
                output_root=td,open_url=fake,clock=one.ticks(old))
            self.assertEqual(fake.calls,[])
            self.assertEqual(r["reason"],"TD_WEEKLY_EDITION_POSTDATES_CAPTURE")
            self.assertFalse(r["original_replayed_from_disk"])
            self.assertEqual(list(Path(td).iterdir()),[])

    def test_24_collector_rejects_stale_http_date_no_source_files(self):
        fake=one.FakeHTTP(
            response=one.MockResponse(date=stamp(one.MARK-timedelta(minutes=40))))
        with TemporaryDirectory() as td:
            r=capture(
                allow_one_official_get=True,
                confirm_bls_schedule_reviewed=True,
                event_root=CPI,provider="TD_ECONOMICS",source_url=TD,
                output_root=td,open_url=fake,clock=one.ticks())
            self.assertEqual(len(fake.calls),1)
            self.assertEqual(r["reason"],"ORIGINAL_SOURCE_CUSTODY_GATE_REJECTED")
            self.assertEqual(list(Path(td).iterdir()),[])

    def test_25_collector_rejects_future_http_date_no_source_files(self):
        fake=one.FakeHTTP(
            response=one.MockResponse(date=stamp(one.MARK+timedelta(seconds=50))))
        with TemporaryDirectory() as td:
            r=capture(
                allow_one_official_get=True,
                confirm_bls_schedule_reviewed=True,
                event_root=CPI,provider="TD_ECONOMICS",source_url=TD,
                output_root=td,open_url=fake,clock=one.ticks())
            self.assertEqual(len(fake.calls),1)
            self.assertEqual(r["reason"],"ORIGINAL_SOURCE_CUSTODY_GATE_REJECTED")
            self.assertEqual(list(Path(td).iterdir()),[])

    def test_26_collector_success_one_get_with_aligned_date_stays_no_forecast(self):
        with TemporaryDirectory() as td:
            r,fake=one.DecOneGetOriginalTests().capture_one(td)
            self.assertTrue(r["original_replayed_from_disk"])
            self.assertEqual(len(fake.calls),1)
            self.assertFalse(r["numerical_consensus_semantics_authenticated"])
            self.assertFalse(r["trade_authorized"])

    def test_27_existing_disk_receipt_stale_date_replay_refused(self):
        with TemporaryDirectory() as td:
            s=physical.write_synthetic_original(Path(td),CPI)
            file=Path(td)/s.archive_basename/"receipt.json"
            receipt=json.loads(file.read_text("utf-8"))
            end=datetime.fromisoformat(receipt["started_at_utc"])
            receipt["http_date_claim"]=stamp(end-timedelta(minutes=40))
            file.write_text(json.dumps(receipt),encoding="utf-8")
            r=replay(output_root=td,archive_basename=s.archive_basename,
                     research_cutoff_utc=datetime(2026,12,20,tzinfo=UTC))
            self.assertFalse(r["original_replayed_from_disk"])
            self.assertFalse(r["trade_authorized"])

    def test_28_bridge_rejects_old_week_td_when_te_document_still_valid(self):
        with TemporaryDirectory() as td:
            selectors=physical.pair(Path(td),CPI)
            file=Path(td)/selectors[0].archive_basename/"receipt.json"
            receipt=json.loads(file.read_text("utf-8"))
            old=TD.replace("2026-12-08","2026-12-01")
            receipt["source_url"]=old
            receipt["final_url"]=old
            file.write_text(json.dumps(receipt),encoding="utf-8")
            r=bridge(archive_root=td,archives=selectors,
                     research_cutoff_utc=datetime(2026,12,20,tzinfo=UTC))
            self.assertEqual(r["state"],
                "LAB_DEC2026_DISK_TO_PROVISIONAL_SEMANTICS_BLOCKED_HARD_NO_GO")
            self.assertEqual(r["semantic_candidate_event_count"],0)
            self.assertIsNone(r["semantic_details_local_only"])
            self.assertEqual(r["independent_directional_predictions"],0)

    def test_29_both_events_with_td_weekly_archive_before_release_valid_synthetically(self):
        c=fx.sample()
        p=fx.sample(root=PPI)
        r=custody(snapshots=(c,p),research_cutoff_utc=datetime(2026,12,15,12,tzinfo=UTC))
        self.assertEqual(r["state"],"LAB_DEC2026_PRE_EVENT_SOURCE_CUSTODY_ONLY_NO_GO")
        self.assertEqual(r["locally_sha_reconciled_pre_event_source_documents"],2)
        self.assertEqual(r["event_roots_with_two_local_source_hashes"],0)
        self.assertEqual(r["validated_out_of_sample_trading_trials"],0)

    def test_30_no_prices_model_or_accuracy_from_extra_provenance_checks(self):
        r=self.accepted(fx.sample())
        self.assertEqual(r["historically_independent_model_forecasts"],0)
        self.assertIsNone(r["calibrated_probability"])
        self.assertFalse(r["consensus_numeric_semantic_parser_approved"])


if __name__=="__main__":
    unittest.main()
