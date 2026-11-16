"""Synthetic-only two-provider capture-time co-vintage audit for CPI/PPI.

A pair of HTML snapshots may each pass raw SHA/PIT and carry IDENTICAL
consensus numbers, but cannot be combined if captured hours or days apart.
A <=30m gap is only a LOCAL documentary precondition, not authenticated
publisher-first-seen, underlying polling equality, an FX bias or a forecast.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import test_atlasquant_trader_us_dec2026_consensus_semantic_candidate_lab as source
import test_atlasquant_trader_us_dec2026_disk_to_semantics_bridge_lab as disk
from atlasquant_trader_us_dec2026_consensus_semantic_candidate_lab import (
    inspect_dec2026_consensus_semantic_candidate_lab as inspect,
)
from atlasquant_trader_us_dec2026_disk_to_semantics_bridge_lab import (
    replay_dec2026_archives_to_semantic_candidates_lab as replay_disk,
)
from atlasquant_trader_us_dec2026_pre_event_consensus_custody_lab import (
    inspect_us_dec2026_pre_event_consensus_custody_lab as inspect_custody,
)

CPI=source.CPI
PPI=source.PPI
UTC=timezone.utc
POST=source.POST
GOOD="LAB_DEC2026_TWO_SOURCE_PROVISIONAL_SEMANTICS_ONLY_HARD_NO_GO"
BAD="LAB_DEC2026_CONSENSUS_SEMANTICS_BLOCKED_HARD_NO_GO"


def moved(snapshot,delta):
    started=snapshot.started_at_utc+delta
    finished=snapshot.finished_at_utc+delta
    # HTTP-Date is a local server claim, independently validated by custody.
    return replace(snapshot,started_at_utc=started,finished_at_utc=finished,
                   http_date_claim=format_datetime(
                       started.astimezone(UTC).replace(microsecond=0),
                       usegmt=True))


def pair(root=CPI,*,te_shift=timedelta(0),td_shift=timedelta(0)):
    td,te=source.pair(root)
    return moved(td,td_shift),moved(te,te_shift)


def candidate(docs,now=POST):
    return inspect(source_snapshots=docs,inspected_at_utc=now)


def physical_pair(root:Path,event=CPI,*,te_shift=timedelta(0)):
    end=source.source_fixture.sample(root=event).finished_at_utc
    return (
        disk.write_synthetic_original(root,event,"TD_ECONOMICS",end=end),
        disk.write_synthetic_original(
            root,event,"TRADING_ECONOMICS",end=end+te_shift),
    )


class TwoProviderCaptureCoherenceTests(unittest.TestCase):
    def base_guard(self,r):
        self.assertEqual(r["frozen_economic_event_denominator"],2)
        self.assertEqual([e["event_root"] for e in r["events"]],[CPI,PPI])
        self.assertFalse(r["trade_authorized"])
        self.assertFalse(r["publishable"])
        self.assertFalse(r["fx28_original_672_slots_modified"])
        self.assertEqual(r["registered_directional_fx_predictions"],0)
        self.assertEqual(r["independent_fx_oos_trials"],0)
        self.assertEqual(r["economic_consensus_pre_event_independently_authenticated"],0)
        self.assertIsNone(r["win_rate"])
        self.assertIsNone(r["fx_bias"])
        self.assertIsNone(r["calibrated_probability"])
        self.assertEqual((r["http_requests"],r["file_writes"],r["mt5_calls"]),(0,0,0))
        for row in r["events"]:
            self.assertFalse(row["source_semantic_schema_approved_on_real_december_html"])
            self.assertFalse(row["publisher_first_seen_independently_authenticated"])
            self.assertFalse(row["capture_times_independently_attested"])
            self.assertFalse(row["consensus_eligible_for_fx_prediction"])
            self.assertFalse(row["independent_validated_fx_forecast"])

    def rejected(self,docs,now=POST):
        r=candidate(docs,now)
        self.base_guard(r)
        self.assertEqual(r["state"],BAD)
        self.assertEqual(r["local_two_source_candidate_event_count"],0)
        self.assertTrue(all(e["provisional_consensus_headline_mom_sa_pct"] is None
                            for e in r["events"]))
        self.assertTrue(all(e["two_provider_local_capture_gap_seconds_claim"] is None
                            for e in r["events"]))
        return r

    def provisional(self,docs,root=CPI,now=POST):
        r=candidate(docs,now)
        self.base_guard(r)
        self.assertEqual(r["state"],GOOD)
        self.assertEqual(r["local_two_source_candidate_event_count"],1)
        i=0 if root==CPI else 1
        self.assertEqual(r["events"][i]["provisional_consensus_headline_mom_sa_pct"],"0.4")
        self.assertEqual(r["events"][i]["provisional_consensus_core_mom_sa_pct"],"0.3")
        return r["events"][i]

    def test_01_equal_capture_finish_cpi_gives_local_gap_zero_only(self):
        e=self.provisional(pair())
        self.assertEqual(e["two_provider_local_capture_gap_seconds_claim"],0)

    def test_02_equal_capture_finish_ppi_gives_local_gap_zero_only(self):
        e=self.provisional(pair(PPI),root=PPI)
        self.assertEqual(e["two_provider_local_capture_gap_seconds_claim"],0)

    def test_03_one_minute_apart_cpi_allowed_provisionally(self):
        e=self.provisional(pair(te_shift=timedelta(minutes=1)))
        self.assertEqual(e["two_provider_local_capture_gap_seconds_claim"],60)

    def test_04_twenty_nine_minutes_ppi_allowed_provisionally(self):
        e=self.provisional(pair(PPI,te_shift=timedelta(minutes=29)),root=PPI)
        self.assertEqual(e["two_provider_local_capture_gap_seconds_claim"],1740)

    def test_05_exact_thirty_minutes_cpi_boundary_inclusive(self):
        e=self.provisional(pair(te_shift=timedelta(minutes=30)))
        self.assertEqual(e["two_provider_local_capture_gap_seconds_claim"],1800)

    def test_06_exact_thirty_minutes_ppi_boundary_inclusive(self):
        e=self.provisional(pair(PPI,te_shift=timedelta(minutes=30)),root=PPI)
        self.assertEqual(e["two_provider_local_capture_gap_seconds_claim"],1800)

    def test_07_thirty_minutes_plus_one_microsecond_cpi_blocks_all(self):
        r=self.rejected(pair(te_shift=timedelta(minutes=30,microseconds=1)))
        self.assertEqual(r["reason"],"TWO_PROVIDER_CAPTURE_VINTAGES_TOO_FAR_APART")

    def test_08_thirty_minutes_plus_one_second_ppi_blocks_all(self):
        r=self.rejected(pair(PPI,te_shift=timedelta(minutes=30,seconds=1)))
        self.assertEqual(r["reason"],"TWO_PROVIDER_CAPTURE_VINTAGES_TOO_FAR_APART")

    def test_09_same_numbers_but_hour_apart_are_not_one_survey(self):
        docs=pair(te_shift=timedelta(hours=1))
        prior=inspect_custody(snapshots=docs,
                              research_cutoff_utc=POST)
        self.assertEqual(prior["locally_sha_reconciled_pre_event_source_documents"],2)
        r=self.rejected(docs)
        self.assertEqual(r["reason"],"TWO_PROVIDER_CAPTURE_VINTAGES_TOO_FAR_APART")

    def test_10_same_numbers_but_day_apart_cpi_blocks(self):
        docs=pair(te_shift=timedelta(days=1))
        self.rejected(docs)

    def test_11_same_numbers_but_two_days_apart_ppi_blocks(self):
        docs=pair(PPI,te_shift=timedelta(days=2))
        prior=inspect_custody(snapshots=docs,research_cutoff_utc=POST)
        self.assertEqual(prior["locally_sha_reconciled_pre_event_source_documents"],2)
        self.rejected(docs)

    def test_12_early_te_vs_late_td_cpi_also_blocks(self):
        docs=pair(te_shift=timedelta(hours=-12))
        self.rejected(docs)

    def test_13_early_te_vs_late_td_ppi_also_blocks(self):
        docs=pair(PPI,te_shift=timedelta(days=-1))
        self.rejected(docs)

    def test_14_microseconds_above_boundary_cuiaba_offset_comparison(self):
        td,te=pair(te_shift=timedelta(minutes=30,microseconds=1))
        cuiaba=timezone(timedelta(hours=-4))
        te=replace(te,
            started_at_utc=te.started_at_utc.astimezone(cuiaba),
            finished_at_utc=te.finished_at_utc.astimezone(cuiaba))
        self.rejected((td,te))

    def test_15_future_te_not_visible_must_not_evaluate_pair(self):
        td,te=pair(te_shift=timedelta(minutes=40))
        r=candidate((td,te),now=td.finished_at_utc+timedelta(minutes=10))
        self.base_guard(r)
        self.assertEqual(r["state"],GOOD)
        self.assertEqual(r["local_two_source_candidate_event_count"],0)
        self.assertTrue(all(e["two_provider_local_capture_gap_seconds_claim"] is None
                            for e in r["events"]))

    def test_16_only_one_provider_is_not_fabricated_double_source(self):
        td,_=pair()
        r=candidate((td,))
        self.base_guard(r)
        self.assertEqual(r["state"],GOOD)
        self.assertEqual(r["local_two_source_candidate_event_count"],0)

    def test_17_when_second_event_skewed_first_does_not_leak(self):
        docs=pair(CPI)+pair(PPI,te_shift=timedelta(hours=2))
        r=self.rejected(docs)
        self.assertTrue(all(e["td_html_sha256_local_claim"] is None
                            for e in r["events"]))

    def test_18_two_good_event_pairs_still_no_fx_predictions(self):
        docs=pair(CPI)+pair(PPI,te_shift=timedelta(minutes=20))
        r=candidate(docs)
        self.base_guard(r)
        self.assertEqual(r["state"],GOOD)
        self.assertEqual(r["local_two_source_candidate_event_count"],2)
        self.assertEqual(r["events"][1]["two_provider_local_capture_gap_seconds_claim"],1200)
        self.assertEqual(r["independent_fx_oos_trials"],0)

    def test_19_same_capture_time_not_independent_publication_proof(self):
        e=self.provisional(pair())
        self.assertFalse(e["capture_times_independently_attested"])
        self.assertFalse(e["source_semantic_schema_approved_on_real_december_html"])
        self.assertFalse(e["consensus_eligible_for_fx_prediction"])

    def test_20_disk_bridge_two_sources_exact_same_time_is_provisional(self):
        with TemporaryDirectory() as d:
            docs=physical_pair(Path(d))
            r=replay_disk(archive_root=d,archives=docs,research_cutoff_utc=POST)
            self.assertEqual(r["state"],
                "LAB_DEC2026_PHYSICAL_ORIGINALS_TO_PROVISIONAL_COLUMNS_NO_GO")
            self.assertEqual(r["semantic_candidate_event_count"],1)
            self.assertEqual(r["semantic_details_local_only"]["events"][0]
                             ["two_provider_local_capture_gap_seconds_claim"],0)
            self.assertFalse(r["trade_authorized"])

    def test_21_disk_bridge_td_and_te_hour_apart_blocks_whole_census(self):
        with TemporaryDirectory() as d:
            docs=physical_pair(Path(d),te_shift=timedelta(hours=1))
            r=replay_disk(archive_root=d,archives=docs,research_cutoff_utc=POST)
            self.assertEqual(r["state"],
                "LAB_DEC2026_DISK_TO_PROVISIONAL_SEMANTICS_BLOCKED_HARD_NO_GO")
            self.assertEqual(r["semantic_candidate_event_count"],0)
            self.assertIsNone(r["semantic_details_local_only"])
            self.assertEqual(r["independent_directional_predictions"],0)

    def test_22_disk_bridge_exact_thirty_minutes_accepted_as_local_only(self):
        with TemporaryDirectory() as d:
            docs=physical_pair(Path(d),te_shift=timedelta(minutes=30))
            r=replay_disk(archive_root=d,archives=docs,research_cutoff_utc=POST)
            self.assertEqual(r["state"],
                "LAB_DEC2026_PHYSICAL_ORIGINALS_TO_PROVISIONAL_COLUMNS_NO_GO")
            self.assertEqual(r["semantic_candidate_event_count"],1)
            self.assertFalse(r["source_originals_independently_first_seen_attested"])

    def test_23_disk_bridge_thirty_minute_plus_microsecond_rejected(self):
        with TemporaryDirectory() as d:
            docs=physical_pair(Path(d),te_shift=timedelta(minutes=30,microseconds=1))
            r=replay_disk(archive_root=d,archives=docs,research_cutoff_utc=POST)
            self.assertEqual(r["state"],
                "LAB_DEC2026_DISK_TO_PROVISIONAL_SEMANTICS_BLOCKED_HARD_NO_GO")
            self.assertEqual(r["semantic_candidate_event_count"],0)
            self.assertFalse(r["trade_authorized"])

    def test_24_disk_bridge_future_price_claim_does_not_open_html_early(self):
        with TemporaryDirectory() as d:
            docs=physical_pair(Path(d),te_shift=timedelta(minutes=20))
            cut=source.source_fixture.sample(root=CPI).finished_at_utc
            r=replay_disk(archive_root=d,archives=docs,research_cutoff_utc=cut)
            self.assertEqual(r["state"],
                "LAB_DEC2026_PHYSICAL_ORIGINALS_TO_PROVISIONAL_COLUMNS_NO_GO")
            self.assertEqual(r["semantic_candidate_event_count"],0)
            self.assertEqual(r["original_archives_future_hidden"],1)
            self.assertFalse(r["trade_authorized"])


if __name__=="__main__":
    unittest.main()
