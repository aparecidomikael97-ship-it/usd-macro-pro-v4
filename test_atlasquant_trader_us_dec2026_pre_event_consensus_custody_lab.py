"""CPI/PPI December pre-event archival gate: 25 strictly synthetic tests."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from hashlib import sha256
import unittest

from atlasquant_trader_us_dec2026_pre_event_consensus_custody_lab import (
    EVENTS,OriginalPreEventSourceClaim,
    inspect_us_dec2026_pre_event_consensus_custody_lab as inspect,
)
UTC=timezone.utc
RELEASE={root:time for root,_,_,time in EVENTS}
TD="https://economics.td.com/domains/economics.td.com/documents/reports/bottom-line/tables/2026-12-08/upcoming.htm"
TE="https://tradingeconomics.com/united-states/calendar"


def sample(root="US_CPI_NOV2026",provider="TD_ECONOMICS",*,end=None,text=None):
    release=RELEASE[root]
    end = end or (release-timedelta(days=2))
    raw=(text if text is not None else
         f"<html><body>RESEARCH SYNTHETIC DOCUMENT {root} {provider} "
         +("CONSENSUS FIELD MUST NOT BE PARSED 0.7% " * 7)
         +"</body></html>").encode("utf-8")
    start=end-timedelta(seconds=2)
    return OriginalPreEventSourceClaim(
        event_root=root,provider=provider,
        source_url=TD if provider=="TD_ECONOMICS" else TE,
        final_url=TD if provider=="TD_ECONOMICS" else TE,
        html_original_bytes=raw,
        original_sha256_claim=sha256(raw).hexdigest(),
        http_status=200,
        http_content_type="text/html; charset=utf-8",
        http_date_claim=format_datetime(start,usegmt=True),
        started_at_utc=start,finished_at_utc=end,
    )


def audit(items=(),*,as_of=None):
    return inspect(snapshots=items,
        research_cutoff_utc=as_of or datetime(2026,12,12,tzinfo=UTC))


class DecemberPreEventCustodyTests(unittest.TestCase):
    def guarded(self,v):
        self.assertEqual(v["schema"],
            "ATLASQUANT_MOTOR_A_US_DEC2026_PROSPECTIVE_CONSENSUS_CUSTODY_LAB_V1")
        self.assertEqual(v["frozen_upcoming_economic_event_denominator"],2)
        self.assertEqual([x["root_id"] for x in v["events"]],
                         ["US_CPI_NOV2026","US_PPI_NOV2026"])
        self.assertEqual(v["historically_independent_model_forecasts"],0)
        self.assertEqual(v["validated_out_of_sample_trading_trials"],0)
        self.assertEqual(v["scoreable_research_events"],0)
        self.assertEqual(v["economically_validated_pre_event_consensus_events"],0)
        self.assertFalse(v["consensus_numeric_semantic_parser_approved"])
        self.assertFalse(v["publisher_first_seen_and_capture_clock_independently_authenticated"])
        self.assertIsNone(v["posterior_economic_actual_values"])
        self.assertIsNone(v["directional_fx_bias"])
        self.assertIsNone(v["validated_fx_accuracy"])
        self.assertIsNone(v["calibrated_probability"])
        self.assertFalse(v["trade_authorized"])
        self.assertFalse(v["publishable"])
        self.assertFalse(v["worker_enabled"])
        self.assertFalse(v["scheduler_enabled"])
        self.assertFalse(v["original_672_fx28_campaign_slots_modified"])
        self.assertEqual((v["http_requests"],v["file_writes"],v["mt5_calls"]),(0,0,0))
        self.assertEqual(v["new_cost_brl"],0)
        self.assertEqual(v["operational_bias"],"AGUARDAR")
        for e in v["events"]:
            self.assertFalse(e["source_first_seen_independently_verified"])
            self.assertFalse(e["consensus_for_fx_prediction_eligible"])
            self.assertFalse(e["pre_event_forecast_committed"])
            self.assertIsNone(e["numeric_consensus_parsed_from_source"])

    def bad(self,items,*,at=None):
        v=audit(items,as_of=at or datetime(2026,12,20,tzinfo=UTC))
        self.guarded(v)
        self.assertEqual(v["state"],"LAB_DEC2026_PRE_EVENT_SNAPSHOTS_BLOCKED_NO_GO")
        self.assertEqual(v["locally_sha_reconciled_pre_event_source_documents"],0)
        return v

    def test_01_no_sources_two_events_never_silent_zero_denominator(self):
        v=audit()
        self.guarded(v)
        self.assertEqual(v["state"],"LAB_DEC2026_PRE_EVENT_SOURCE_CUSTODY_ONLY_NO_GO")
        self.assertEqual(v["locally_sha_reconciled_pre_event_source_documents"],0)
        self.assertEqual(v["event_roots_with_two_local_source_hashes"],0)

    def test_02_pinned_bls_schedule_utc_dates_with_brazil_local_clock(self):
        self.assertEqual(RELEASE["US_CPI_NOV2026"].isoformat(),"2026-12-10T13:30:00+00:00")
        self.assertEqual(RELEASE["US_PPI_NOV2026"].isoformat(),"2026-12-15T13:30:00+00:00")
        cuiaba=timezone(timedelta(hours=-4))
        self.assertEqual(RELEASE["US_CPI_NOV2026"].astimezone(cuiaba).hour,9)
        self.assertEqual(RELEASE["US_PPI_NOV2026"].astimezone(cuiaba).minute,30)

    def test_03_cpi_two_sources_locally_sha_checked_not_numeric_consensus(self):
        arr=[sample(),sample(provider="TRADING_ECONOMICS")]
        v=audit(arr,as_of=datetime(2026,12,10,10,tzinfo=UTC))
        self.guarded(v)
        self.assertEqual(v["locally_sha_reconciled_pre_event_source_documents"],2)
        self.assertEqual(v["event_roots_with_two_local_source_hashes"],1)
        self.assertEqual(v["events"][0]["locally_reconciled_source_count"],2)
        self.assertTrue(v["events"][0]["locally_reconciled_two_sources"])

    def test_04_four_distinct_raw_sources_are_two_events_not_four_trades(self):
        arr=[sample(root,provider) for root in RELEASE
             for provider in ("TD_ECONOMICS","TRADING_ECONOMICS")]
        v=audit(arr,as_of=datetime(2026,12,15,11,tzinfo=UTC))
        self.guarded(v)
        self.assertEqual(v["locally_sha_reconciled_pre_event_source_documents"],4)
        self.assertEqual(v["event_roots_with_two_local_source_hashes"],2)
        self.assertEqual(v["validated_out_of_sample_trading_trials"],0)

    def test_05_future_raw_html_hidden_until_local_capture_finished(self):
        original=sample()
        before=original.finished_at_utc-timedelta(microseconds=1)
        v=audit([original],as_of=before)
        self.guarded(v)
        self.assertEqual(v["locally_sha_reconciled_pre_event_source_documents"],0)
        self.assertEqual(v["events"][0]["archived_hashes_only"],{})

    def test_06_future_wrong_hash_does_not_leak_in_past_but_blocks_later(self):
        a=replace(sample(),original_sha256_claim="f"*64)
        early=audit([a],as_of=a.finished_at_utc-timedelta(seconds=1))
        self.guarded(early)
        self.assertEqual(early["locally_sha_reconciled_pre_event_source_documents"],0)
        self.bad([a],at=a.finished_at_utc)

    def test_07_capture_visible_exactly_at_microsecond_end(self):
        a=sample(end=RELEASE["US_CPI_NOV2026"]-timedelta(days=1,microseconds=12345))
        v=audit([a],as_of=a.finished_at_utc)
        self.guarded(v)
        self.assertEqual(v["locally_sha_reconciled_pre_event_source_documents"],1)
        self.assertEqual(v["events"][0]["archived_hashes_only"]["TD_ECONOMICS"]["last_local_capture_utc_claim"],
                         a.finished_at_utc.isoformat())

    def test_08_capture_within_one_hour_of_release_not_freezable(self):
        a=sample(end=RELEASE["US_CPI_NOV2026"]-timedelta(minutes=59))
        self.bad([a])

    def test_09_capture_after_event_banned_not_backdated(self):
        a=sample(end=RELEASE["US_PPI_NOV2026"]+timedelta(minutes=1),
                 root="US_PPI_NOV2026")
        self.bad([a])

    def test_10_too_old_economic_preview_outside_seven_day_window(self):
        a=sample(end=RELEASE["US_CPI_NOV2026"]-timedelta(days=9))
        self.bad([a])

    def test_11_pre_release_capture_exact_freeze_deadline_allowed(self):
        a=sample(end=RELEASE["US_CPI_NOV2026"]-timedelta(hours=1))
        v=audit([a],as_of=a.finished_at_utc)
        self.guarded(v)
        self.assertEqual(v["locally_sha_reconciled_pre_event_source_documents"],1)

    def test_12_redirect_or_mismatched_final_url_fails(self):
        self.bad([replace(sample(),final_url="https://example.org/changed")])

    def test_13_td_redirect_or_wrong_website_fails(self):
        self.bad([replace(sample(),source_url="https://td.example.invalid/calendar",
                          final_url="https://td.example.invalid/calendar")])

    def test_14_te_source_url_requires_pinned_path(self):
        self.bad([replace(sample(provider="TRADING_ECONOMICS"),
                          source_url="https://tradingeconomics.com/united-states/calendar?cookie=1",
                          final_url="https://tradingeconomics.com/united-states/calendar?cookie=1")])

    def test_15_wrong_digest_never_accepts_values_even_if_string_0_7(self):
        self.bad([replace(sample(),original_sha256_claim="0"*64)])

    def test_16_reuse_one_source_as_second_provider_denied(self):
        a=sample()
        b=replace(a,provider="TRADING_ECONOMICS",source_url=TE,final_url=TE)
        self.bad([a,b])

    def test_17_duplicate_same_source_event_pair_denied(self):
        a=sample()
        self.bad([a,a])

    def test_18_bad_http_status_or_bool_true_both_fail(self):
        for status in (True,301,403):
            with self.subTest(status=status):
                self.bad([replace(sample(),http_status=status)])

    def test_19_wrong_content_type_banned(self):
        self.bad([replace(sample(),http_content_type="application/json")])

    def test_20_wrong_http_date_future_or_stale_does_not_claim_first_seen(self):
        a=sample()
        for date in (a.finished_at_utc+timedelta(hours=1),
                     a.started_at_utc-timedelta(hours=3)):
            with self.subTest(date=date):
                self.bad([replace(a,http_date_claim=format_datetime(date,usegmt=True))])

    def test_21_invalid_capture_chronology_blocks(self):
        a=sample()
        self.bad([replace(a,started_at_utc=a.finished_at_utc+timedelta(seconds=1))])

    def test_22_non_utc_cuiaba_clocks_compare_same_instants(self):
        a=sample()
        offset=timezone(timedelta(hours=-4))
        loc=replace(a,started_at_utc=a.started_at_utc.astimezone(offset),
                    finished_at_utc=a.finished_at_utc.astimezone(offset))
        self.assertEqual(audit([a]),audit([loc]))

    def test_23_forecast_fabricated_dictionary_not_a_raw_source(self):
        self.bad([{"provider":"TD_ECONOMICS","consensus":"0.7",
                   "release":"2026-12-10T13:30:00Z"}])

    def test_24_fifth_snapshot_never_changes_denominator(self):
        a=sample()
        v=self.bad([a,a,a,a,a])
        self.assertEqual(v["frozen_upcoming_economic_event_denominator"],2)

    def test_25_nan_time_invalid_date_or_bytes_not_a_vintage(self):
        a=sample()
        self.bad([replace(a,finished_at_utc=datetime(2026,12,9,9,0))])
        self.bad([replace(a,html_original_bytes="consensus 0.7")])
        self.bad([replace(a,http_date_claim="not-a-date")])

    def test_26_missing_provider_cannot_be_claimed_pair(self):
        v=audit([sample()])
        self.guarded(v)
        self.assertEqual(v["event_roots_with_two_local_source_hashes"],0)
        self.assertFalse(v["events"][0]["locally_reconciled_two_sources"])

    def test_27_source_documents_are_not_automatically_consensus(self):
        blob="<html>"+"Consensus 99.9% tradingeconomics estimate "*20+"</html>"
        a=sample(provider="TRADING_ECONOMICS",text=blob)
        v=audit([a])
        self.guarded(v)
        self.assertIsNone(v["events"][0]["numeric_consensus_parsed_from_source"])
        self.assertEqual(v["historically_independent_model_forecasts"],0)

    def test_28_future_source_is_not_validated_just_by_valid_sha(self):
        a=sample(root="US_PPI_NOV2026")
        early=audit([a],as_of=a.finished_at_utc-timedelta(seconds=2))
        late=audit([a],as_of=a.finished_at_utc)
        self.guarded(early)
        self.guarded(late)
        self.assertEqual(early["locally_sha_reconciled_pre_event_source_documents"],0)
        self.assertEqual(late["locally_sha_reconciled_pre_event_source_documents"],1)


if __name__ == "__main__":
    unittest.main()
