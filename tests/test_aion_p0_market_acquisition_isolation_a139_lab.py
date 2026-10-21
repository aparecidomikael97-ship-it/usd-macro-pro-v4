"""A139 P0: synthetic market acquisition must not require checkpoint write.

RED-first LAB tests: no external provider, GitHub, network, actual orders or Worker.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import atlasquant_market_boundary_a139 as m


class MarketCollectorAuthorityBoundaryA139LAB(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)/"checkout"
        self.output=Path(self.tmp.name)/"artifacts"
        self.root.mkdir()
        self.output.mkdir()
        self.feed=m.SyntheticMarketFeed({
            "EUR/USD":{"bid":1.1,"ask":1.1002},
            "USD/JPY":{"bid":150.0,"ask":150.02},
            "GBP/USD":{"bid":1.3,"ask":1.3003},
        })
        self.quota=m.MemoryOnlyReservationLedger(limit=3)
        self.run="labrun139"
        self.time="2026-10-21T23:00:00Z"

    def call(self,*,run_id=None,symbols=None,feed=None,quota=None,out=None,root=None,at=None):
        return m.collect_synthetic_market(
            run_id=self.run if run_id is None else run_id,
            symbols=("EUR/USD","USD/JPY") if symbols is None else symbols,
            feed=self.feed if feed is None else feed,
            quota=self.quota if quota is None else quota,
            output_dir=self.output if out is None else out,
            checkout_root=self.root if root is None else root,
            observed_at=self.time if at is None else at,
        )

    def test_01_success_has_explicit_synthetic_labels(self):
        result=self.call()
        self.assertEqual(result["status"],"SYNTHETIC_OUTPUT_NOT_LIVE")
        self.assertFalse(result["external_provider_called"])
        self.assertFalse(result["runtime_write_authorized"])
        self.assertFalse(result["independent_witness_enrolled"])
        self.assertEqual(result["market_files_written"],1)
        self.assertEqual(self.feed.calls,["EUR/USD","USD/JPY"])

    def test_02_no_github_or_provider_secret_needed(self):
        with patch.dict(os.environ,{"GITHUB_TOKEN_HISTORICO":"MUST_NOT_BE_READ",
                       "CHAVE_TWELVE_DATA":"MUST_NOT_BE_READ"}):
            result=self.call()
        self.assertNotIn("MUST_NOT_BE_READ",(self.output/result["filename"]).read_text())

    def test_03_reservation_occurs_before_first_feed_read(self):
        events=[]
        feed=m.SyntheticMarketFeed({"EUR/USD":{"bid":1.1,"ask":1.1002}},events=events)
        quota=m.MemoryOnlyReservationLedger(limit=1,events=events)
        self.call(symbols=("EUR/USD",),feed=feed,quota=quota)
        self.assertEqual(events[:2],["reserve:labrun139:1","read:EUR/USD"])

    def test_04_insufficient_budget_denies_before_feed(self):
        self.quota=m.MemoryOnlyReservationLedger(limit=1)
        result=self.call()
        self.assertEqual(result["status"],"BLOCKED_NO_PROVIDER_FETCH")
        self.assertEqual(self.feed.calls,[])
        self.assertEqual(self.quota.reserved_units,0)

    def test_05_duplicate_run_id_denies_before_second_fetch(self):
        self.call()
        before=list(self.feed.calls)
        second=self.call()
        self.assertEqual(second["status"],"BLOCKED_NO_PROVIDER_FETCH")
        self.assertEqual(self.feed.calls,before)
        self.assertEqual(self.quota.reserved_units,2)

    def test_06_provider_timeout_blocks_without_automatic_retry(self):
        feed=m.SyntheticMarketFeed({"EUR/USD":TimeoutError("synthetic timeout")})
        result=self.call(symbols=("EUR/USD",),feed=feed)
        self.assertEqual(result["status"],"UNCERTAIN_NO_AUTOMATIC_RETRY")
        self.assertEqual(feed.calls,["EUR/USD"])
        self.assertEqual(self.quota.reserved_units,1)
        self.assertEqual(list(self.output.iterdir()),[])

    def test_07_provider_exception_never_refunds_uncertain_reserved_unit(self):
        feed=m.SyntheticMarketFeed({"EUR/USD":RuntimeError("synthetic provider error")})
        result=self.call(symbols=("EUR/USD",),feed=feed)
        self.assertEqual(result["status"],"UNCERTAIN_NO_AUTOMATIC_RETRY")
        self.assertEqual(self.quota.reserved_units,1)

    def test_08_payload_missing_pair_denies_safely(self):
        feed=m.SyntheticMarketFeed({"EUR/USD":{"bid":1.1,"ask":1.1002}})
        result=self.call(feed=feed)
        self.assertNotEqual(result["status"],"SYNTHETIC_OUTPUT_NOT_LIVE")
        self.assertEqual(list(self.output.iterdir()),[])

    def test_09_inverted_spread_rejected(self):
        self.feed.quotes["EUR/USD"]={"bid":1.12,"ask":1.10}
        self.assertNotEqual(self.call()["status"],"SYNTHETIC_OUTPUT_NOT_LIVE")

    def test_10_nan_price_rejected(self):
        self.feed.quotes["EUR/USD"]={"bid":float("nan"),"ask":1.1}
        self.assertNotEqual(self.call()["status"],"SYNTHETIC_OUTPUT_NOT_LIVE")

    def test_11_boolean_price_rejected(self):
        self.feed.quotes["EUR/USD"]={"bid":True,"ask":1.1002}
        self.assertNotEqual(self.call()["status"],"SYNTHETIC_OUTPUT_NOT_LIVE")

    def test_12_secret_field_rejected(self):
        self.feed.quotes["EUR/USD"]={"bid":1.1,"ask":1.1002,"api_key":"SENSITIVE"}
        self.assertNotEqual(self.call()["status"],"SYNTHETIC_OUTPUT_NOT_LIVE")

    def test_13_duplicate_symbol_rejected_before_reservation(self):
        self.assertEqual(self.call(symbols=("EUR/USD","EUR/USD"))["status"],"BLOCKED_NO_PROVIDER_FETCH")
        self.assertEqual(self.quota.reserved_units,0)

    def test_14_unlisted_symbol_denied(self):
        self.assertEqual(self.call(symbols=("XAU/USD",))["status"],"BLOCKED_NO_PROVIDER_FETCH")
        self.assertEqual(self.feed.calls,[])

    def test_15_invalid_run_id_denied(self):
        self.assertEqual(self.call(run_id="../../aion")["status"],"BLOCKED_NO_PROVIDER_FETCH")
        self.assertEqual(self.quota.reserved_units,0)

    def test_16_output_inside_checkout_forbidden(self):
        self.assertEqual(self.call(out=self.root/"dados")["status"],"BLOCKED_NO_PROVIDER_FETCH")
        self.assertEqual(self.feed.calls,[])

    def test_17_output_parent_symlink_escape_denied(self):
        link=Path(self.tmp.name)/"shortcut"
        try: link.symlink_to(self.output,target_is_directory=True)
        except (OSError,NotImplementedError): self.skipTest("symlink forbidden")
        self.assertEqual(self.call(out=link)["status"],"BLOCKED_NO_PROVIDER_FETCH")

    def test_18_existing_output_filename_not_overwritten(self):
        name=m.output_name(self.run)
        file=self.output/name
        file.write_text("DO_NOT_TOUCH")
        self.assertEqual(self.call()["status"],"BLOCKED_NO_PROVIDER_FETCH")
        self.assertEqual(file.read_text(),"DO_NOT_TOUCH")

    def test_19_invalid_observed_at_denied_without_reservation(self):
        self.assertEqual(self.call(at="tomorrow")["status"],"BLOCKED_NO_PROVIDER_FETCH")
        self.assertEqual(self.quota.reserved_units,0)

    def test_20_manifest_hash_matches_quote_bytes(self):
        res=self.call()
        file=self.output/res["filename"]
        saved=json.loads(file.read_text(encoding="utf-8"))
        payload=saved["quote_payload"]
        encoded=m.canonical_json(payload)
        self.assertEqual(saved["payload_sha256"],hashlib.sha256(encoded).hexdigest())
        self.assertEqual(saved["source_authority"],"SYNTHETIC_FIXTURE_ONLY")
        self.assertEqual(saved["freshness_status"],"NOT_VERIFIED_NOT_LIVE")

    def test_21_source_files_and_checkpoint_never_written(self):
        self.call()
        self.assertFalse((self.root/"dados/aion/checkpoint_master.json").exists())
        self.assertEqual(list(self.root.iterdir()),[])

    def test_22_no_generic_live_reader_accepted(self):
        class Impostor:
            def read(self,symbol): raise AssertionError("SHOULD_NOT_EXECUTE")
        self.assertEqual(self.call(feed=Impostor())["status"],"BLOCKED_NO_PROVIDER_FETCH")

    def test_23_no_generic_mutable_quota_accepted(self):
        class Impostor:
            def reserve(self,*args): raise AssertionError("SHOULD_NOT_EXECUTE")
        self.assertEqual(self.call(quota=Impostor())["status"],"BLOCKED_NO_PROVIDER_FETCH")

    def test_24_no_zero_or_negative_ledger_limit(self):
        with self.assertRaises(ValueError): m.MemoryOnlyReservationLedger(limit=0)
        with self.assertRaises(ValueError): m.MemoryOnlyReservationLedger(limit=-1)

    def test_25_quota_max_exact_no_expansion(self):
        result=self.call(symbols=("EUR/USD","USD/JPY","GBP/USD"))
        self.assertEqual(result["status"],"SYNTHETIC_OUTPUT_NOT_LIVE")
        self.assertEqual(self.quota.reserved_units,3)
        self.assertEqual(self.call(run_id="other1391",symbols=("EUR/USD",))["status"],"BLOCKED_NO_PROVIDER_FETCH")

    def test_26_cannot_use_extra_data_fields(self):
        self.feed.quotes["EUR/USD"]={"bid":1.1,"ask":1.1002,"owner_approved":True}
        self.assertNotEqual(self.call()["status"],"SYNTHETIC_OUTPUT_NOT_LIVE")

    def test_27_clock_is_not_claimed_as_verified_provider_timestamp(self):
        res=self.call()
        obj=json.loads((self.output/res["filename"]).read_text())
        self.assertEqual(obj["observed_at"],self.time)
        self.assertFalse(obj["provider_fetch_performed"])
        self.assertFalse(obj["human_owner_verified"])

    def test_28_files_are_canonical_no_nan(self):
        res=self.call()
        content=(self.output/res["filename"]).read_text()
        self.assertNotIn("NaN",content)
        self.assertNotIn("Infinity",content)
        self.assertTrue(content.endswith("\n"))

    def test_29_reservation_unavailable_denies_without_fetch(self):
        ledger=m.MemoryOnlyReservationLedger(limit=3,available=False)
        self.assertEqual(self.call(quota=ledger)["status"],"BLOCKED_NO_PROVIDER_FETCH")
        self.assertEqual(self.feed.calls,[])

    def test_30_approved_true_env_flag_does_not_enable_external_provider(self):
        with patch.dict(os.environ,{"AION_INDEPENDENT_WITNESS_VERIFIED":"true","AION_OWNER_APPROVED":"true"}):
            res=self.call()
        self.assertFalse(res["external_provider_called"])
        self.assertFalse(res["runtime_write_authorized"])


if __name__=="__main__":
    unittest.main()
