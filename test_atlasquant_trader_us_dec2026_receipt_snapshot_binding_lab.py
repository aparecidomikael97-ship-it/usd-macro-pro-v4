"""Adversarial TOCTOU checks for locally replayed December CPI/PPI receipts.

All HTML, dates, data and provider receipts in this test are SYNTHETIC.
Changes between the two disk reads are deterministic mock injections;
not a claim of real activity, data, first-seen or forecast accuracy.
"""
from __future__ import annotations

from datetime import timedelta
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import json
import unittest

import atlasquant_trader_us_dec2026_disk_to_semantics_bridge_lab as bridge
from atlasquant_trader_us_dec2026_consensus_original_one_get_lab import (
    replay_dec2026_one_get_original_lab as replay,
)
import test_atlasquant_trader_us_dec2026_disk_to_semantics_bridge_lab as fixture

CPI=fixture.CPI
PPI=fixture.PPI
POST=fixture.POST
BAD="LAB_DEC2026_DISK_TO_PROVISIONAL_SEMANTICS_BLOCKED_HARD_NO_GO"
GOOD="LAB_DEC2026_PHYSICAL_ORIGINALS_TO_PROVISIONAL_COLUMNS_NO_GO"
CHANGED="REOPENED_ORIGINAL_OR_RECEIPT_CHANGED_AFTER_REPLAY"


def assert_no_fx_signal(test, report):
    test.assertFalse(report["trade_authorized"])
    test.assertFalse(report["publishable"])
    test.assertFalse(report["source_originals_independently_first_seen_attested"])
    test.assertFalse(report["source_layout_semantics_validated_against_real_december_html"])
    test.assertFalse(report["synthetic_fixture_is_real_consensus_evidence"])
    test.assertIsNone(report["win_rate"])
    test.assertIsNone(report["usd_direction"])
    test.assertIsNone(report["probability"])
    test.assertEqual(report["scoreable_out_of_sample_fx_trials"],0)
    test.assertEqual(report["independent_directional_predictions"],0)
    test.assertEqual(report["economic_events_frozen_denominator"],2)
    test.assertEqual(report["operational_bias"],"AGUARDAR")
    test.assertFalse(report["original_fx28_672_slots_modified"])
    test.assertEqual(
        (report["http_requests"],report["file_writes"],report["mt5_calls"]),(0,0,0))


def replay_with_mutation(root, archive_refs, *, mutate, target_index=0, when=POST):
    target=archive_refs[target_index].archive_basename
    mutations=[]
    def after_original_replay(**kwargs):
        proof=replay(**kwargs)
        if (kwargs["archive_basename"]==target
                and proof["original_replayed_from_disk"] is True):
            receipt=Path(root)/target/"receipt.json"
            original=Path(root)/target/"original.html"
            mutate(receipt,original)
            mutations.append(target)
        return proof
    with patch.object(bridge,"replay_dec2026_one_get_original_lab",
                      side_effect=after_original_replay):
        result=bridge.replay_dec2026_archives_to_semantic_candidates_lab(
            archive_root=root, archives=archive_refs, research_cutoff_utc=when)
    return result,mutations


class PhysicalReceiptSnapshotBindingTests(unittest.TestCase):
    def rejected(self,r,reason=CHANGED):
        assert_no_fx_signal(self,r)
        self.assertEqual(r["state"],BAD)
        self.assertEqual(r["reason"],reason)
        self.assertEqual(r["original_archives_replayed_visible"],0)
        self.assertEqual(r["semantic_candidate_event_count"],0)
        self.assertIsNone(r["semantic_details_local_only"])

    def test_01_one_cpi_td_receipt_sha_matches_exact_original_bytes(self):
        with TemporaryDirectory() as d:
            s=fixture.write_synthetic_original(Path(d),CPI)
            proof=replay(output_root=d,archive_basename=s.archive_basename,
                         research_cutoff_utc=POST)
            self.assertTrue(proof["original_replayed_from_disk"])
            self.assertEqual(
                proof["source_receipt_sha256"],
                sha256((Path(d)/s.archive_basename/"receipt.json").read_bytes()).hexdigest())
            self.assertEqual(len(proof["source_receipt_sha256"]),64)
            self.assertFalse(proof["trade_authorized"])

    def test_02_one_ppi_te_receipt_sha_matches_exact_original_bytes(self):
        with TemporaryDirectory() as d:
            s=fixture.write_synthetic_original(Path(d),PPI,
                                                provider="TRADING_ECONOMICS")
            proof=replay(output_root=d,archive_basename=s.archive_basename,
                         research_cutoff_utc=POST)
            self.assertTrue(proof["original_replayed_from_disk"])
            self.assertEqual(
                proof["source_receipt_sha256"],
                sha256((Path(d)/s.archive_basename/"receipt.json").read_bytes()).hexdigest())

    def test_03_invalid_receipt_never_has_validated_receipt_digest(self):
        with TemporaryDirectory() as d:
            s=fixture.write_synthetic_original(Path(d),CPI)
            path=Path(d)/s.archive_basename/"receipt.json"
            content=json.loads(path.read_text("utf-8"))
            content["manual_bls_schedule_review_claim_only"]=False
            path.write_text(json.dumps(content),encoding="utf-8")
            proof=replay(output_root=d,archive_basename=s.archive_basename,
                         research_cutoff_utc=POST)
            self.assertFalse(proof["original_replayed_from_disk"])
            self.assertIsNone(proof["source_receipt_sha256"])

    def test_04_healthy_pair_still_yields_documentary_candidate_only(self):
        with TemporaryDirectory() as d:
            refs=fixture.pair(Path(d),CPI)
            r=bridge.replay_dec2026_archives_to_semantic_candidates_lab(
                archive_root=d,archives=refs,research_cutoff_utc=POST)
            assert_no_fx_signal(self,r)
            self.assertEqual(r["state"],GOOD)
            self.assertEqual(r["semantic_candidate_event_count"],1)

    def test_05_healthy_four_sources_are_two_economic_events_only(self):
        with TemporaryDirectory() as d:
            refs=fixture.pair(Path(d),CPI)+fixture.pair(Path(d),PPI)
            r=bridge.replay_dec2026_archives_to_semantic_candidates_lab(
                archive_root=d,archives=refs,research_cutoff_utc=POST)
            assert_no_fx_signal(self,r)
            self.assertEqual(r["state"],GOOD)
            self.assertEqual(r["semantic_candidate_event_count"],2)

    def test_06_receipt_manual_bls_review_switched_off_after_replay(self):
        with TemporaryDirectory() as d:
            refs=fixture.pair(Path(d),CPI)
            def mutate(receipt,unused_html):
                obj=json.loads(receipt.read_text("utf-8"))
                obj["manual_bls_schedule_review_claim_only"]=False
                receipt.write_text(json.dumps(obj),encoding="utf-8")
            r,seen=replay_with_mutation(d,refs,mutate=mutate)
            self.assertEqual(seen,[refs[0].archive_basename])
            self.rejected(r)

    def test_07_receipt_semantic_authenticated_falsely_switched_on(self):
        with TemporaryDirectory() as d:
            refs=fixture.pair(Path(d),PPI)
            def mutate(receipt,unused_html):
                obj=json.loads(receipt.read_text("utf-8"))
                obj["numerical_consensus_semantics_authenticated"]=True
                receipt.write_text(json.dumps(obj),encoding="utf-8")
            r,seen=replay_with_mutation(d,refs,mutate=mutate)
            self.assertEqual(len(seen),1)
            self.rejected(r)

    def test_08_receipt_html_digest_valid_but_http_date_changed(self):
        with TemporaryDirectory() as d:
            refs=fixture.pair(Path(d),CPI)
            def mutate(receipt,unused_html):
                obj=json.loads(receipt.read_text("utf-8"))
                obj["http_date_claim"]="Tue, 08 Dec 2026 10:00:01 GMT"
                receipt.write_text(json.dumps(obj),encoding="utf-8")
            r,seen=replay_with_mutation(d,refs,mutate=mutate)
            self.assertEqual(len(seen),1)
            self.rejected(r)

    def test_09_merely_pretty_printing_json_after_replay_changes_raw_receipt(self):
        with TemporaryDirectory() as d:
            refs=fixture.pair(Path(d),CPI)
            def mutate(receipt,unused_html):
                obj=json.loads(receipt.read_text("utf-8"))
                receipt.write_text(json.dumps(obj,indent=2),encoding="utf-8")
            r,seen=replay_with_mutation(d,refs,mutate=mutate)
            self.assertEqual(len(seen),1)
            self.rejected(r)

    def test_10_keys_reordered_after_replay_not_same_archival_receipt(self):
        with TemporaryDirectory() as d:
            refs=fixture.pair(Path(d),PPI)
            def mutate(receipt,unused_html):
                obj=json.loads(receipt.read_text("utf-8"))
                receipt.write_text(json.dumps(dict(reversed(list(obj.items())))),
                                   encoding="utf-8")
            r,seen=replay_with_mutation(d,refs,mutate=mutate)
            self.assertEqual(len(seen),1)
            self.rejected(r)

    def test_11_second_te_receipt_changed_blocks_entire_cpi_pair(self):
        with TemporaryDirectory() as d:
            refs=fixture.pair(Path(d),CPI)
            def mutate(receipt,unused_html):
                obj=json.loads(receipt.read_text("utf-8"))
                obj["manual_bls_schedule_review_claim_only"]=False
                receipt.write_text(json.dumps(obj),encoding="utf-8")
            r,seen=replay_with_mutation(d,refs,mutate=mutate,target_index=1)
            self.assertEqual(seen,[refs[1].archive_basename])
            self.rejected(r)

    def test_12_ppi_receipt_changed_blocks_healthy_cpi_as_well(self):
        with TemporaryDirectory() as d:
            refs=fixture.pair(Path(d),CPI)+fixture.pair(Path(d),PPI)
            def mutate(receipt,unused_html):
                obj=json.loads(receipt.read_text("utf-8"))
                obj["content_type"]="text/plain"
                receipt.write_text(json.dumps(obj),encoding="utf-8")
            r,seen=replay_with_mutation(d,refs,mutate=mutate,target_index=2)
            self.assertEqual(len(seen),1)
            self.rejected(r)

    def test_13_html_changed_during_replay_also_denied(self):
        with TemporaryDirectory() as d:
            refs=fixture.pair(Path(d),CPI)
            def mutate(unused_receipt,html):
                html.write_bytes(html.read_bytes()+b"POST_REPLAY_UNTRUSTED")
            r,seen=replay_with_mutation(d,refs,mutate=mutate)
            self.assertEqual(len(seen),1)
            self.rejected(r)

    def test_14_no_second_source_no_numeric_consensus_and_no_trade(self):
        with TemporaryDirectory() as d:
            s=fixture.write_synthetic_original(Path(d),CPI)
            r=bridge.replay_dec2026_archives_to_semantic_candidates_lab(
                archive_root=d,archives=(s,),research_cutoff_utc=POST)
            assert_no_fx_signal(self,r)
            self.assertEqual(r["state"],GOOD)
            self.assertEqual(r["semantic_candidate_event_count"],0)

    def test_15_future_receipt_must_not_be_opened_or_mutated_early(self):
        with TemporaryDirectory() as d:
            refs=fixture.pair(Path(d),CPI)
            finish=fixture.example.source_fixture.sample(root=CPI).finished_at_utc
            def mutate(unused_receipt,unused_html):
                raise AssertionError("future receipt unexpectedly opened")
            r,seen=replay_with_mutation(
                d,refs,mutate=mutate,when=finish-timedelta(microseconds=1))
            assert_no_fx_signal(self,r)
            self.assertEqual(r["state"],GOOD)
            self.assertEqual(seen,[])
            self.assertEqual(r["original_archives_future_hidden"],2)

    def test_16_missing_digest_in_replay_result_fails_closed(self):
        with TemporaryDirectory() as d:
            refs=fixture.pair(Path(d),CPI)
            def lost_digest(**kwargs):
                proof=replay(**kwargs)
                if proof["original_replayed_from_disk"]:
                    proof.pop("source_receipt_sha256")
                return proof
            with patch.object(bridge,"replay_dec2026_one_get_original_lab",
                              side_effect=lost_digest):
                r=bridge.replay_dec2026_archives_to_semantic_candidates_lab(
                    archive_root=d,archives=refs,research_cutoff_utc=POST)
            self.rejected(r,reason="RECEIPT_OR_ARCHIVED_ORIGINAL_READ_FAILED")


if __name__=="__main__":
    unittest.main()
