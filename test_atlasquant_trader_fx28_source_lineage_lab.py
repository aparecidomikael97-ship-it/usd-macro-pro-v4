"""Source-byte SHA lineage integration with actual eight-bank/PPI replay.

All original source bytes are SYNTHETIC test fixtures; network PPI transport
is mocked. No authentic issuer data, no MT5, no forecast, no trade.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock
import unittest

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS
from atlasquant_trader_fx28_source_lineage_lab import (
    SCHEMA, extract_checked_policy_source_lineage_lab as extract,
    build_pair_source_lineage_lab as pair_digest,
)
from atlasquant_trader_fx28_policy_local_archive_replay_lab import (
    inspect_fx28_official_policy_archive_replay_lab as source_reader,
)
from atlasquant_trader_fx28_28pair_source_readiness_manual_lab import (
    inspect_28pair_source_readiness_once_lab as policy_reader,
)
from atlasquant_trader_fx28_policy_ppi_unified_readiness_lab import (
    inspect_fx28_policy_ppi_readiness_lab as unified,
)
from atlasquant_trader_fx28_pre_window_source_gate_lab import (
    inspect_fx28_pre_window_source_gate_lab as prewindow,
)
from atlasquant_trader_fx28_ny17_prospective_campaign_lab import (
    FROZEN_START_UTC,
)
from atlasquant_trader_us_ppi_oct2026_original_capture_lab import (
    capture_oct2026_bls_original_once_lab as capture,
)
from test_atlasquant_trader_us_ppi_oct2026_original_capture_lab import (
    MockResponse, START, FINISH,
)
from test_atlasquant_trader_us_ppi_oct2026_actual_table_guard_lab import raw
from test_atlasquant_trader_fx28_policy_local_archive_replay_lab import (
    archive_dir, save_fixture,
)
from test_atlasquant_trader_fx28_eight_policy_raw_source_join_lab import (
    synthetic_packets,
)

UTC=timezone.utc
NOW=datetime(2026,11,13,14,5,tzinfo=UTC)
PRE=FROZEN_START_UTC-timedelta(minutes=30)


class LocalSourceLineageIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sources=synthetic_packets()

    def setUp(self):
        self.tmp=TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def banks(self, codes=()):
        folder=archive_dir(self.tmp.name)
        for c in codes:
            save_fixture(folder,c,self.sources[c])
        return folder

    def ppi(self):
        transport=Mock(return_value=MockResponse(
            body=raw(head="0.3",core="0.3",extra="0.5")))
        times=Mock(side_effect=[START,FINISH])
        result=capture(allow_one_get=True,
                       local_appdata=self.tmp.name,
                       open_url=transport,clock=times)
        self.assertTrue(result["raw_bytes_and_receipt_replayed"])
        transport.assert_called_once()
        return result["archive_directory_basename"]

    def archive(self,at=NOW):
        return source_reader(local_appdata=self.tmp.name,decision_at_utc=at)

    def policy(self,at=NOW):
        return policy_reader(mode="audit",local_appdata=self.tmp.name,
                             decision_clock=lambda:at)

    def combined(self,ppi=None,at=NOW):
        return unified(local_appdata=self.tmp.name,decision_at_utc=at,
                       ppi_archive_basename=ppi)

    def ensure_no_go(self,result):
        self.assertEqual(result["operational_bias"],"AGUARDAR")
        self.assertFalse(result["trade_authorized"])
        self.assertFalse(result["publishable"])

    def test_01_all_eight_real_issuer_validators_reconstruct_eight_hash_claims(self):
        self.banks(CURRENCIES)
        report=self.archive()
        ledger=extract(archive_report=report,inspected_at_utc=NOW)
        self.assertEqual(set(ledger),set(CURRENCIES))
        self.assertEqual(len(ledger),8)
        for row in ledger.values():
            self.assertEqual(len(row["source_original_sha256_local_claim"]),64)
            self.assertEqual(row["origin_pit_authenticated"],"false")
            self.assertTrue(row["selected_capture_utc_local_claim"].endswith("Z"))
        source=self.policy()
        self.ensure_no_go(source)
        self.assertEqual(source["local_policy_source_lineage_by_currency"],ledger)
        self.assertEqual(source["local_policy_sources_with_reproducible_byte_hashes"],8)
        self.assertEqual(source["pairs_with_two_original_source_hashes"],28)
        self.assertTrue(all(x["complete_policy_pair_source_digest_local_only"]
                            for x in source["per_pair"]))

    def test_02_only_three_valid_bank_receipts_make_three_complete_pair_hashes(self):
        self.banks(("USD","EUR","CAD"))
        source=self.policy()
        self.ensure_no_go(source)
        self.assertEqual(source["local_policy_sources_with_reproducible_byte_hashes"],3)
        self.assertEqual(source["pairs_with_two_original_source_hashes"],3)
        found={x["pair"] for x in source["per_pair"]
               if x["complete_policy_pair_source_digest_local_only"]}
        self.assertEqual(found,{"EUR/USD","EUR/CAD","USD/CAD"})

    def test_03_policy_digest_is_repeatable_and_pair_specific(self):
        self.banks(CURRENCIES)
        left=self.policy()
        right=self.policy()
        self.assertEqual(left["local_policy_source_lineage_by_currency"],
                         right["local_policy_source_lineage_by_currency"])
        hashes=[x["complete_policy_pair_source_digest_local_only"]
                for x in left["per_pair"]]
        self.assertEqual(len(set(hashes)),28)
        self.assertEqual(hashes,[
            x["complete_policy_pair_source_digest_local_only"]
            for x in right["per_pair"]])
        self.assertEqual(left["operational_bias"],"AGUARDAR")

    def test_04_corrupted_usd_original_drops_usd_sha_and_all_seven_pair_hashes(self):
        folder=self.banks(CURRENCIES)
        file=[p for p in folder.glob("USD_FED_BOARD_TARGET_RANGE_*.html")]
        self.assertEqual(len(file),1)
        file[0].write_bytes(file[0].read_bytes()+b"unsafe extra")
        result=self.policy()
        self.ensure_no_go(result)
        self.assertEqual(result["local_policy_sources_with_reproducible_byte_hashes"],7)
        self.assertEqual(result["pairs_with_two_original_source_hashes"],21)
        self.assertNotIn("USD",result["local_policy_source_lineage_by_currency"])
        self.assertTrue(all(not row["complete_policy_pair_source_digest_local_only"]
                            for row in result["per_pair"] if "USD" in row["pair"]))

    def test_05_missing_policy_leg_cannot_be_replaced_by_ppi_document(self):
        self.banks(("EUR",))
        ppi=self.ppi()
        result=self.combined(ppi=ppi)
        self.ensure_no_go(result)
        self.assertEqual(result["policy_source_documents_locally_checked"],1)
        self.assertEqual(result["policy_pairs_with_two_source_digest_claims"],0)
        self.assertEqual(result["ppi_documentary_series_count"],3)
        self.assertEqual(result["ppi_direct_usd_leg_pairs_with_source_replayed"],7)
        self.assertTrue(all(
            not row["pair_full_document_bundle_sha256_local_claim"]
            for row in result["per_pair"]))
        self.assertTrue(all(not row["both_original_policy_sha256_claims_present"]
                            for row in result["per_pair"]))

    def test_06_ppi_one_sha_shared_across_seven_usd_legs_but_unique_bundles(self):
        self.banks(CURRENCIES)
        ppi=self.ppi()
        result=self.combined(ppi=ppi)
        self.ensure_no_go(result)
        self.assertEqual(result["ppi_documentary_series_count"],3)
        rows=result["per_pair"]
        usd=[r for r in rows if "USD" in r["pair"]]
        other=[r for r in rows if "USD" not in r["pair"]]
        self.assertEqual(len(usd),7)
        self.assertEqual(len(other),21)
        self.assertEqual({r["ppi_single_document_sha256_in_bundle_if_usd"]
                          for r in usd},{result["ppi_source_raw_sha256"]})
        self.assertTrue(all(r["ppi_single_document_sha256_in_bundle_if_usd"]
                            is None for r in other))
        self.assertEqual(len({r["pair_full_document_bundle_sha256_local_claim"]
                              for r in usd}),7)
        self.assertEqual(result["policy_pairs_with_two_source_digest_claims"],28)
        self.assertTrue(result["ppi_is_one_shared_catalyst_not_seven_independent_news"])

    def test_07_adding_ppi_changes_usd_bundle_only_not_policy_digests(self):
        self.banks(CURRENCIES)
        before=self.combined()
        ppi=self.ppi()
        after=self.combined(ppi=ppi)
        self.ensure_no_go(after)
        for a,b in zip(before["per_pair"],after["per_pair"]):
            self.assertEqual(a["pair"],b["pair"])
            self.assertEqual(a["policy_pair_evidence_sha256_local_claim"],
                             b["policy_pair_evidence_sha256_local_claim"])
            if "USD" in a["pair"]:
                self.assertNotEqual(
                    a["pair_full_document_bundle_sha256_local_claim"],
                    b["pair_full_document_bundle_sha256_local_claim"])
            else:
                self.assertEqual(
                    a["pair_full_document_bundle_sha256_local_claim"],
                    b["pair_full_document_bundle_sha256_local_claim"])
        self.assertIsNone(after["usd_strength_score"])

    def test_08_policy_digest_can_be_historically_valid_but_not_recent(self):
        self.banks(CURRENCIES)
        result=self.combined(at=NOW+timedelta(days=2))
        self.ensure_no_go(result)
        self.assertEqual(result["policy_source_documents_locally_checked"],8)
        self.assertEqual(result["policy_source_originals_with_reproducible_sha_claims"],8)
        self.assertEqual(result["policy_source_recent_local_receipt_claims"],0)
        self.assertEqual(result["policy_pairs_with_two_source_digest_claims"],28)
        self.assertEqual(result["policy_pairs_with_two_recent_local_receipt_claims"],0)
        self.assertFalse(result["model_calibrated_for_fx28"])

    def test_09_ppi_receipt_tamper_preserves_bank_sha_but_erases_usd_addition(self):
        self.banks(CURRENCIES)
        ppi=self.ppi()
        path=Path(self.tmp.name)/"AtlasQuant"/"LAB"/"official_macro_receipts"/ppi/"receipt.json"
        data=json.loads(path.read_text())
        data["raw_sha256"]="f"*64
        path.write_text(json.dumps(data))
        result=self.combined(ppi=ppi)
        self.ensure_no_go(result)
        self.assertEqual(result["policy_pairs_with_two_source_digest_claims"],28)
        self.assertEqual(result["ppi_documentary_series_count"],0)
        self.assertTrue(all(
            r["ppi_single_document_sha256_in_bundle_if_usd"] is None
            for r in result["per_pair"]))

    def test_10_future_stamped_bank_is_never_a_predecision_hash(self):
        folder=self.banks(("EUR","CAD"))
        info=deepcopy(self.sources["USD"])
        receipt=dict(info["receipt"])
        receipt["started_at_utc"]="2026-11-13T18:00:00Z"
        receipt["finished_at_utc"]="2026-11-13T18:00:02Z"
        save_fixture(folder,"USD",info,
                     override_receipt=receipt,
                     override_stamp="2026-11-13T18:00:02Z")
        source=self.policy()
        self.ensure_no_go(source)
        self.assertNotIn("USD",source["local_policy_source_lineage_by_currency"])
        self.assertEqual(source["pairs_with_two_original_source_hashes"],1)
        self.assertEqual(source["local_policy_sources_with_reproducible_byte_hashes"],2)

    def test_11_invalid_sha_and_claimed_clock_fail_closed_in_pure_builder(self):
        valid={"USD":{
            "source_original_sha256_local_claim":"a"*64,
            "selected_capture_utc_local_claim":"2026-11-13T14:00:00Z",
            "origin_pit_authenticated":"false",
        },"EUR":{
            "source_original_sha256_local_claim":"b"*64,
            "selected_capture_utc_local_claim":"2026-11-13T14:00:00Z",
            "origin_pit_authenticated":"false",
        }}
        ok=pair_digest(pair="EUR/USD",policy_ledger=valid)
        self.assertEqual(ok["schema"],SCHEMA)
        self.assertTrue(ok["both_policy_original_hashes_available"])
        self.assertEqual(len(ok["complete_policy_pair_source_digest_local_only"]),64)
        for currency,key,value in (
            ("USD","source_original_sha256_local_claim","A"*64),
            ("USD","source_original_sha256_local_claim","0"*64),
            ("EUR","selected_capture_utc_local_claim","not-time"),
            ("EUR","origin_pit_authenticated","true"),
        ):
            with self.subTest(change=(currency,key,value)):
                changed=deepcopy(valid)
                changed[currency][key]=value
                bad=pair_digest(pair="EUR/USD",policy_ledger=changed)
                self.assertIsNone(bad["complete_policy_pair_source_digest_local_only"])
                self.assertFalse(bad["both_policy_original_hashes_available"])
                self.assertIsNone(bad["calibrated_probability"])

    def test_12_archive_report_fake_attestation_true_prevents_any_source_fingerprint(self):
        self.banks(CURRENCIES)
        original=self.archive()
        modified=deepcopy(original)
        modified["true_first_seen_time_independently_attested"]=True
        ledger=extract(archive_report=modified,inspected_at_utc=NOW)
        self.assertEqual(ledger,{})
        future=extract(archive_report=original,
                       inspected_at_utc=NOW-timedelta(days=10))
        self.assertEqual(future,{})

    def test_13_preflight_propagates_pair_bundle_hash_but_not_a_forecast(self):
        self.banks(CURRENCIES)
        ppi=self.ppi()
        result=prewindow(local_appdata=self.tmp.name,inspected_at_utc=PRE,
                         ppi_archive_basename=ppi)
        self.ensure_no_go(result)
        self.assertEqual(result["state"],
                         "LAB_FX28_PREWINDOW_28_SOURCE_VETOES_NO_GO")
        self.assertEqual(result["nominal_windows_in_active_preflight"],2)
        self.assertEqual(result["policy_originals_with_reproducible_source_hash_claims"],8)
        first,second=result["next_nominal_windows"]
        self.assertEqual(len(first["pairs"]),28)
        self.assertEqual(len(second["pairs"]),28)
        for a,b in zip(first["pairs"],second["pairs"]):
            self.assertEqual(a["pair"],b["pair"])
            self.assertEqual(a["pair_document_bundle_sha256_local_claim"],
                             b["pair_document_bundle_sha256_local_claim"])
            self.assertEqual(len(a["pair_document_bundle_sha256_local_claim"]),64)
            self.assertTrue(a["source_digest_is_not_a_registered_forecast"])
            self.assertFalse(a["forecast_issued"])
            self.assertFalse(a["trade_authorized"])
            self.assertFalse(a["forecast_authorized"])
        self.assertFalse(result["pre_event_28_forecast_rosters_generated"])

    def test_14_missing_evidence_means_no_fingerprint_not_fake_prediction(self):
        self.banks(())
        result=self.policy()
        self.ensure_no_go(result)
        self.assertEqual(result["local_policy_source_lineage_by_currency"],{})
        self.assertEqual(result["pairs_with_two_original_source_hashes"],0)
        self.assertTrue(all(
            x["complete_policy_pair_source_digest_local_only"] is None
            for x in result["per_pair"]))
        self.assertFalse(result["pre_event_forecasts_independently_witnessed"])


if __name__=="__main__":
    unittest.main()
