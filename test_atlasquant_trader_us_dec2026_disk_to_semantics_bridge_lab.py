"""Synthetic-only on-disk original+receipt test fixtures; 0 external GETs."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest

from atlasquant_trader_us_dec2026_disk_to_semantics_bridge_lab import (
    ArchivedOriginalSelector, replay_dec2026_archives_to_semantic_candidates_lab as audit,
)
from atlasquant_trader_us_dec2026_consensus_original_one_get_lab import RECEIPT_SCHEMA
from atlasquant_trader_us_dec2026_pre_event_consensus_custody_lab import EVENTS
import test_atlasquant_trader_us_dec2026_consensus_semantic_candidate_lab as example

UTC=timezone.utc
CPI="US_CPI_NOV2026"
PPI="US_PPI_NOV2026"
POST=datetime(2026,12,20,tzinfo=UTC)


def write_synthetic_original(root:Path,event=CPI,provider="TD_ECONOMICS",*,html=None,
                             end=None):
    source=example.source_fixture.sample(root=event,provider=provider,end=end)
    body=html if html is not None else (
        example.td_html(event) if provider=="TD_ECONOMICS"
        else example.te_html(event))
    digest=sha256(body).hexdigest()
    finish=source.finished_at_utc
    receipt={
        "schema":RECEIPT_SCHEMA,
        "event_root":event, "provider":provider,
        "source_url":source.source_url,"final_url":source.final_url,
        "started_at_utc":source.started_at_utc.isoformat(),
        "finished_at_utc":finish.isoformat(),
        "http_status":200,"content_type":"text/html; charset=utf-8",
        "http_date_claim":source.http_date_claim,
        "original_html_bytes":len(body),"original_html_sha256":digest,
        "manual_bls_schedule_review_claim_only":True,
        "numerical_consensus_semantics_authenticated":False,
    }
    name=("US_DEC2026_"+event+"_"+provider+"_"
          +finish.strftime("%Y%m%dT%H%M%S%fZ")+"_"+digest[:12])
    folder=root/name
    folder.mkdir()
    (folder/"original.html").write_bytes(body)
    (folder/"receipt.json").write_text(
        json.dumps(receipt,sort_keys=True),encoding="utf-8")
    return ArchivedOriginalSelector(event,provider,name)


def pair(root,root_event=CPI,*,td=None,te=None):
    return (
        write_synthetic_original(root,root_event,"TD_ECONOMICS",html=td),
        write_synthetic_original(root,root_event,"TRADING_ECONOMICS",html=te),
    )


class DiskReplaySemanticBridgeTests(unittest.TestCase):
    def safety(self,out):
        self.assertEqual(out["schema"],
            "ATLASQUANT_US_DEC2026_DISK_SOURCE_TO_PROVISIONAL_SEMANTICS_LAB_V1")
        self.assertEqual(out["economic_events_frozen_denominator"],2)
        self.assertEqual([r["event_root"] for r in out["events"]],[CPI,PPI])
        self.assertFalse(out["source_originals_independently_first_seen_attested"])
        self.assertFalse(out["source_layout_semantics_validated_against_real_december_html"])
        self.assertFalse(out["synthetic_fixture_is_real_consensus_evidence"])
        self.assertEqual(out["independent_directional_predictions"],0)
        self.assertEqual(out["scoreable_out_of_sample_fx_trials"],0)
        self.assertIsNone(out["win_rate"])
        self.assertIsNone(out["usd_direction"])
        self.assertIsNone(out["probability"])
        self.assertFalse(out["trade_authorized"])
        self.assertFalse(out["publishable"])
        self.assertFalse(out["scheduler_enabled"])
        self.assertFalse(out["worker_enabled"])
        self.assertFalse(out["original_fx28_672_slots_modified"])
        self.assertEqual((out["http_requests"],out["file_writes"],out["mt5_calls"]),(0,0,0))
        self.assertEqual(out["new_cost_brl"],0)
        self.assertEqual(out["operational_bias"],"AGUARDAR")
        for row in out["events"]:
            self.assertFalse(row["consensus_eligible_for_fx"])

    def good(self,root,refs=(),now=POST):
        out=audit(archive_root=root,archives=refs,research_cutoff_utc=now)
        self.safety(out)
        self.assertEqual(out["state"],
            "LAB_DEC2026_PHYSICAL_ORIGINALS_TO_PROVISIONAL_COLUMNS_NO_GO")
        return out

    def blocked(self,root,refs=(),now=POST):
        out=audit(archive_root=root,archives=refs,research_cutoff_utc=now)
        self.safety(out)
        self.assertEqual(out["state"],
            "LAB_DEC2026_DISK_TO_PROVISIONAL_SEMANTICS_BLOCKED_HARD_NO_GO")
        self.assertEqual(out["original_archives_replayed_visible"],0)
        self.assertEqual(out["semantic_candidate_event_count"],0)
        self.assertIsNone(out["semantic_details_local_only"])
        return out

    def test_01_empty_directory_retains_two_events_zero_consensus(self):
        with TemporaryDirectory() as td:
            r=self.good(td)
            self.assertEqual((r["original_archives_replayed_visible"],
                              r["semantic_candidate_event_count"]),(0,0))
            self.assertEqual(list(Path(td).iterdir()),[])

    def test_02_single_real_file_replay_without_two_source_candidate(self):
        with TemporaryDirectory() as td:
            s=write_synthetic_original(Path(td))
            r=self.good(td,(s,))
            self.assertEqual(r["original_archives_replayed_visible"],1)
            self.assertEqual(r["semantic_candidate_event_count"],0)

    def test_03_two_cpi_on_disk_originals_replay_and_candidate(self):
        with TemporaryDirectory() as td:
            refs=pair(Path(td))
            r=self.good(td,refs)
            self.assertEqual(r["original_archives_replayed_visible"],2)
            self.assertEqual(r["semantic_candidate_event_count"],1)
            self.assertTrue(r["events"][0]["provisional_semantic_candidate"])
            self.assertFalse(r["events"][1]["provisional_semantic_candidate"])
            candidate=r["semantic_details_local_only"]["events"][0]
            self.assertEqual(candidate["provisional_consensus_headline_mom_sa_pct"],"0.4")
            self.assertEqual(candidate["td_previous_headline_mom_pct"],"0.2")
            self.assertEqual(candidate["te_provider_forecast_headline_mom_pct"],"0.5")
            self.assertFalse(candidate["consensus_eligible_for_fx_prediction"])

    def test_04_two_ppi_on_disk_originals_replay_not_doubled(self):
        with TemporaryDirectory() as td:
            r=self.good(td,pair(Path(td),PPI))
            self.assertEqual(r["semantic_candidate_event_count"],1)
            self.assertTrue(r["events"][1]["provisional_semantic_candidate"])
            self.assertFalse(r["events"][0]["provisional_semantic_candidate"])

    def test_05_four_cpi_ppi_source_documents_are_two_macro_events(self):
        with TemporaryDirectory() as td:
            refs=pair(Path(td),CPI)+pair(Path(td),PPI)
            r=self.good(td,refs)
            self.assertEqual(r["original_archives_replayed_visible"],4)
            self.assertEqual(r["semantic_candidate_event_count"],2)
            self.assertEqual(r["independent_directional_predictions"],0)
            self.assertEqual(r["scoreable_out_of_sample_fx_trials"],0)

    def test_06_historical_cutoff_prior_to_both_sources_opens_no_original(self):
        with TemporaryDirectory() as td:
            refs=pair(Path(td),CPI)
            finish=example.source_fixture.sample(root=CPI).finished_at_utc
            r=self.good(td,refs,finish-timedelta(microseconds=1))
            self.assertEqual(r["original_archives_replayed_visible"],0)
            self.assertEqual(r["original_archives_future_hidden"],2)
            self.assertEqual(r["semantic_candidate_event_count"],0)

    def test_07_exact_capture_last_microsecond_not_backdated(self):
        with TemporaryDirectory() as td:
            refs=pair(Path(td),CPI)
            end=example.source_fixture.sample(root=CPI).finished_at_utc
            prior=self.good(td,refs,end-timedelta(microseconds=1))
            at=self.good(td,refs,end)
            self.assertEqual(prior["original_archives_replayed_visible"],0)
            self.assertEqual(at["original_archives_replayed_visible"],2)

    def test_08_future_corrupt_file_must_not_leak_before_cutoff(self):
        with TemporaryDirectory() as td:
            refs=pair(Path(td))
            f=Path(td)/refs[0].archive_basename/"original.html"
            f.write_bytes(f.read_bytes()+b"corruption")
            t=example.source_fixture.sample(root=CPI).finished_at_utc
            early=self.good(td,refs,t-timedelta(seconds=1))
            self.assertEqual(early["original_archives_replayed_visible"],0)
            self.blocked(td,refs,t)

    def test_09_corrupt_raw_html_blocks_all_replayed_partials(self):
        with TemporaryDirectory() as td:
            refs=pair(Path(td),CPI)
            f=Path(td)/refs[1].archive_basename/"original.html"
            f.write_bytes(f.read_bytes()+b"AFTER_THE_FACT")
            r=self.blocked(td,refs)
            self.assertEqual(r["reason"],"PHYSICAL_ORIGINAL_SHA_RECEIPT_REPLAY_REJECTED")

    def test_10_forged_sha256_receipt_is_not_real_source(self):
        with TemporaryDirectory() as td:
            refs=pair(Path(td))
            f=Path(td)/refs[0].archive_basename/"receipt.json"
            doc=json.loads(f.read_text("utf-8"))
            doc["original_html_sha256"]="e"*64
            f.write_text(json.dumps(doc),encoding="utf-8")
            self.blocked(td,refs)

    def test_11_receipt_changed_event_root_is_mismatched(self):
        with TemporaryDirectory() as td:
            refs=pair(Path(td))
            f=Path(td)/refs[0].archive_basename/"receipt.json"
            doc=json.loads(f.read_text("utf-8"))
            doc["event_root"]=PPI
            f.write_text(json.dumps(doc),encoding="utf-8")
            self.blocked(td,refs)

    def test_12_duplicate_json_receipt_key_cannot_override_hash(self):
        with TemporaryDirectory() as td:
            refs=pair(Path(td))
            f=Path(td)/refs[0].archive_basename/"receipt.json"
            doc=f.read_text("utf-8").replace(
                '"schema":','"schema":"HINDSIGHT_OVERRIDE","schema":')
            f.write_text(doc,encoding="utf-8")
            self.blocked(td,refs)

    def test_13_selector_name_must_match_event_and_provider(self):
        with TemporaryDirectory() as td:
            refs=pair(Path(td))
            bad=replace(refs[0],provider="TRADING_ECONOMICS")
            self.blocked(td,(bad,refs[1]))

    def test_14_selector_duplicate_event_provider_not_two_documents(self):
        with TemporaryDirectory() as td:
            refs=pair(Path(td))
            self.blocked(td,(refs[0],refs[0]))

    def test_15_foreign_event_root_rejected_before_any_file_open(self):
        with TemporaryDirectory() as td:
            r=self.blocked(td,(ArchivedOriginalSelector(
                "US_CPI_SEP2026","TD_ECONOMICS","bad"),))
            self.assertEqual(r["reason"],"UNKNOWN_EVENT_PROVIDER_OR_SELECTOR_TYPE")

    def test_16_nonexistent_named_physical_archive_is_not_consensus(self):
        with TemporaryDirectory() as td:
            refs=pair(Path(td))
            (Path(td)/refs[0].archive_basename/"original.html").unlink()
            self.blocked(td,refs)

    def test_17_symlinked_original_html_is_blocked(self):
        with TemporaryDirectory() as td:
            refs=pair(Path(td))
            src=Path(td)/refs[0].archive_basename/"original.html"
            outside=Path(td)/"elsewhere.html"
            outside.write_bytes(src.read_bytes())
            src.unlink()
            src.symlink_to(outside)
            self.blocked(td,refs)

    def test_18_changed_td_url_edition_refused_during_physical_replay(self):
        with TemporaryDirectory() as td:
            refs=pair(Path(td))
            f=Path(td)/refs[0].archive_basename/"receipt.json"
            doc=json.loads(f.read_text("utf-8"))
            url=doc["source_url"].replace("2026-12-08","2025-12-08")
            doc["source_url"]=url
            doc["final_url"]=url
            f.write_text(json.dumps(doc),encoding="utf-8")
            self.blocked(td,refs)

    def test_19_source_semantic_mismatch_blocks_every_documentary_value(self):
        with TemporaryDirectory() as td:
            refs=pair(Path(td),CPI,te=example.te_html(CPI,head="0.6%"))
            out=self.blocked(td,refs)
            self.assertEqual(out["reason"],
                "ORIGINAL_BYTES_SEMANTICS_FAILED_NO_PARTIAL_CANDIDATE")

    def test_20_invalid_cpi_reference_month_from_disk_no_go(self):
        with TemporaryDirectory() as td:
            refs=pair(Path(td),CPI,td=example.td_html(CPI,period="Oct"))
            self.blocked(td,refs)

    def test_21_synthetic_html_has_no_permission_to_become_fx_forecast(self):
        with TemporaryDirectory() as td:
            r=self.good(td,pair(Path(td)))
            self.assertIsNone(r["usd_direction"])
            self.assertIsNone(r["win_rate"])
            self.assertEqual(r["independent_directional_predictions"],0)
            self.assertFalse(r["semantic_details_local_only"]["events"][0]
                             ["source_semantic_schema_approved_on_real_december_html"])

    def test_22_only_cpi_visible_before_ppi_source_capture(self):
        with TemporaryDirectory() as td:
            refs=pair(Path(td),CPI)+pair(Path(td),PPI)
            cutoff=example.source_fixture.sample(root=PPI).finished_at_utc-timedelta(seconds=1)
            r=self.good(td,refs,cutoff)
            self.assertEqual(r["original_archives_replayed_visible"],2)
            self.assertEqual(r["original_archives_future_hidden"],2)
            self.assertEqual(r["semantic_candidate_event_count"],1)

    def test_23_empty_archive_refs_cannot_produce_100_percent_accuracy(self):
        with TemporaryDirectory() as td:
            out=self.good(td)
            self.assertEqual(out["semantic_candidate_event_count"],0)
            self.assertIsNone(out["probability"])

    def test_24_unsupported_selector_dataclass_not_forgivable(self):
        with TemporaryDirectory() as td:
            self.blocked(td,({"event_root":CPI,"consensus":0.4},))

    def test_25_fifth_document_never_expands_denominator(self):
        with TemporaryDirectory() as td:
            refs=pair(Path(td),CPI)+pair(Path(td),PPI)
            self.blocked(td,refs+(refs[0],))

    def test_26_naive_clock_blocks_all_copies(self):
        with TemporaryDirectory() as td:
            refs=pair(Path(td),CPI)
            self.blocked(td,refs,datetime(2026,12,20))

    def test_27_wrong_root_directory_blocks_without_network(self):
        r=self.blocked("/this-folder-is-not-a-real-atlasquant-lab",())
        self.assertEqual(r["reason"],"INVALID_ARCHIVE_ROSTER_ROOT_OR_CUTOFF")

    def test_28_missing_receipt_blocks_even_if_valid_html_exists(self):
        with TemporaryDirectory() as td:
            refs=pair(Path(td))
            (Path(td)/refs[0].archive_basename/"receipt.json").unlink()
            self.blocked(td,refs)

    def test_29_http_403_claim_does_not_count_as_saved_original(self):
        with TemporaryDirectory() as td:
            refs=pair(Path(td))
            f=Path(td)/refs[1].archive_basename/"receipt.json"
            data=json.loads(f.read_text("utf-8"))
            data["http_status"]=403
            f.write_text(json.dumps(data),encoding="utf-8")
            self.blocked(td,refs)

    def test_30_future_archive_selector_missing_folder_is_not_opened_early(self):
        with TemporaryDirectory() as td:
            refs=pair(Path(td))
            src=Path(td)/refs[0].archive_basename
            for entry in src.iterdir():
                entry.unlink()
            src.rmdir()
            future=example.source_fixture.sample(root=CPI).finished_at_utc
            r=self.good(td,refs,future-timedelta(seconds=1))
            self.assertEqual(r["original_archives_future_hidden"],2)
            self.assertEqual(r["original_archives_replayed_visible"],0)
            self.blocked(td,refs,future)

if __name__=="__main__":
    unittest.main()
