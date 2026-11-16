"""Strict manual-export integration tests with a FAKE MT5 client and CSVs.

No MT5 package, actual broker quote, external network, trading, or actual
future December event data are ever used. The frozen future UTC clocks in
tests are simulated; dates and numeric quotes are synthetic.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import json
import unittest

from atlasquant_trader_us_macro_mt5_bidask_manual_export_lab import (
    export_manual_mt5_7fx_bidask_anchors_lab as export,
    load_manual_mt5_bidask_receipt_lab as load,
)
from atlasquant_trader_us_macro_mt5_bidask_anchor_archive_lab import (
    EVENTS,PAIR_ORDER,
    inspect_local_mt5_7fx_bidask_anchor_archive_lab as replay,
)

UTC=timezone.utc
CUIABA=timezone(timedelta(hours=-4))
PPI="US_PPI_OCT2026"
CPI_DEC="US_CPI_NOV2026"
PPI_DEC="US_PPI_NOV2026"
NOW=datetime(2026,11,16,14,30,tzinfo=UTC)
GOOD="LAB_MT5_7FX_LOCAL_BIDASK_ORIGINALS_EXPORTED_NO_TRADING"
BAD="LAB_MT5_7FX_MANUAL_TICK_EXPORT_BLOCKED_NO_GO"


class FakeReadOnlyMT5:
    COPY_TICKS_INFO=2
    def __init__(self,mode=None,trigger_pair="EURUSD",trigger_anchor=0):
        self.mode=mode
        self.trigger_pair=trigger_pair
        self.trigger_anchor=trigger_anchor
        self.calls=[]
        self.info_calls=[]
        self.terminal_calls=0
        self.visible=True
        self.company="Pepperstone LOCAL COMPANY LABEL NOT VERIFIED"

    def terminal_info(self):
        self.terminal_calls+=1
        if self.mode=="disconnected":
            return SimpleNamespace(company=self.company,connected=False)
        return SimpleNamespace(company=self.company,connected=True)

    def symbol_info(self,pair):
        self.info_calls.append(pair)
        if self.mode=="symbol_missing" and pair==self.trigger_pair:
            return None
        digits=3 if pair.endswith("JPY") else 5
        if self.mode=="wrong_digits" and pair==self.trigger_pair:
            digits=1
        visible=(not self.visible
                 if self.mode=="visibility_flip"
                 and pair==self.trigger_pair and self.info_calls.count(pair)>1
                 else self.visible)
        return SimpleNamespace(
            name=pair,currency_base=pair[:3],
            currency_profit=pair[3:],visible=visible,
            digits=digits,point=10**(-digits),
        )

    def copy_ticks_range(self,pair,start,end,flags):
        assert start.tzinfo is not None and start.utcoffset()==timedelta(0)
        assert end.tzinfo is not None and end.utcoffset()==timedelta(0)
        assert (end-start)==timedelta(seconds=5)
        assert flags==self.COPY_TICKS_INFO
        ordinal=sum(x[0]==pair for x in self.calls)
        self.calls.append((pair,start,end,flags))
        active=pair==self.trigger_pair and ordinal==self.trigger_anchor
        if active and self.mode=="raise_read":
            raise RuntimeError("SYNTHETIC_QUERY_EXCEPTION")
        if active and self.mode=="missing":
            return []
        anchor=int(end.timestamp())*1000
        secs=[anchor-3000,anchor-1000]
        if active and self.mode=="stale":
            secs[-1]=anchor-5001
        if active and self.mode=="future":
            secs[-1]=anchor+1
        if active and self.mode=="out_of_order":
            secs=list(reversed(secs))
        if active and self.mode=="boundary":
            secs[-1]=anchor-5000
            secs[0]=anchor-5000
        if active and self.mode=="at_anchor":
            secs[-1]=anchor
        if active and self.mode=="duplicate_ms":
            secs[-1]=secs[0]
        base=149.231 if pair.endswith("JPY") else 1.12534
        spread=0.002 if pair.endswith("JPY") else 0.00020
        result=[]
        for ms in secs:
            row=dict(time=ms//1000,time_msc=ms,bid=base,ask=base+spread)
            if active and self.mode=="zero_spread":
                row["ask"]=row["bid"]
            if active and self.mode=="non_grid":
                row["bid"]=1.123456789
            if active and self.mode=="negative_bid":
                row["bid"]=-1.0
            if active and self.mode=="time_seconds_mismatch":
                row["time"]+=1
            if active and self.mode=="missing_bid":
                row.pop("bid")
            result.append(row)
        return result

    def initialize(self,*args,**kwargs):
        raise AssertionError("initialize must NEVER be called by manual exporter")

    def account_info(self,*args,**kwargs):
        raise AssertionError("account_info must NEVER be called")

    def symbol_select(self,*args,**kwargs):
        raise AssertionError("symbol_select must NEVER be called")

    def order_send(self,*args,**kwargs):
        raise AssertionError("order_send must NEVER be called")


class ManualSevenPairBidAskExportTests(unittest.TestCase):
    def setUp(self):
        temp=TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root=Path(temp.name)/"AtlasQuant"/"LAB"/"MT5_7FX_BIDASK_ANCHORS"

    def call(self,api=None,*,event=PPI,at=NOW,approve=True,root=None,clock=None):
        api=api or FakeReadOnlyMT5()
        result=export(api,event_root=event,
                      output_root=self.root if root is None else root,
                      allow_explicit_manual_export=approve,
                      clock=(lambda: at) if clock is None else clock)
        self.assertEqual(result["schema"],
                         "ATLASQUANT_MT5_7FX_MANUAL_BIDASK_TICK_EXPORT_LAB_V1")
        self.assertEqual(result["event_root"],event if event in EVENTS else None)
        self.assertEqual(result["operational_bias"],"AGUARDAR")
        self.assertFalse(result["trade_authorized"])
        self.assertFalse(result["publishable"])
        self.assertFalse(result["orders_or_positions_accessed"])
        self.assertFalse(result["terminal_visibility_changed_by_script"])
        self.assertFalse(result["broker_login_performed"])
        self.assertFalse(result["new_workers_or_cron_enabled"])
        self.assertFalse(result["fx28_original_672_slots_changed"])
        self.assertFalse(result["quote_completeness_or_executability_authenticated"])
        self.assertFalse(result["historical_data_first_seen_independently_authenticated"])
        self.assertFalse(result["terminal_company_identity_independently_authenticated"])
        self.assertEqual(result["out_of_sample_directional_trials"],0)
        self.assertIsNone(result["forex_accuracy"])
        self.assertIsNone(result["calibrated_probability"])
        self.assertEqual(result["http_requests"],0)
        self.assertEqual(result["new_cost_brl"],0)
        return result,api

    def denied(self,api=None,**kwargs):
        result,api=self.call(api,**kwargs)
        self.assertEqual(result["state"],BAD)
        self.assertEqual(result["tick_snapshots_selected"],0)
        self.assertEqual(result["local_files_written"],0)
        self.assertIsNone(result["private_event_directory"])
        return result,api

    def allowed(self,api=None,**kwargs):
        result,api=self.call(api,**kwargs)
        self.assertEqual(result["state"],GOOD,result["reason"])
        self.assertEqual(result["tick_snapshots_selected"],28)
        self.assertEqual(result["local_files_written"],8)
        self.assertEqual(len(result["bidask_original_sha256_by_pair_local_claim"]),7)
        self.assertEqual(result["historical_tick_read_calls"],28)
        self.assertTrue(result["archive_replayed_by_independent_offline_validator"])
        return result,api

    def test_01_no_explicit_opt_in_means_zero_terminal_calls_or_writes(self):
        api=FakeReadOnlyMT5()
        result,_=self.denied(api,approve=False)
        self.assertEqual(api.terminal_calls,0)
        self.assertEqual(api.calls,[])
        self.assertFalse(self.root.exists())

    def test_02_wrong_root_location_blocks_without_terminal_contact(self):
        api=FakeReadOnlyMT5()
        self.denied(api,root=self.root.parent)
        self.assertEqual(api.terminal_calls,0)
        self.assertFalse(self.root.exists())

    def test_03_unlisted_event_blocked_before_terminal_contact(self):
        api=FakeReadOnlyMT5()
        self.denied(api,event="US_CPI_JAN2027")
        self.assertEqual(api.terminal_calls,0)

    def test_04_december_cpi_future_not_fabricated_in_november(self):
        api=FakeReadOnlyMT5()
        self.denied(api,event=CPI_DEC)
        self.assertEqual(api.terminal_calls,0)

    def test_05_december_ppi_future_not_fabricated_in_november(self):
        api=FakeReadOnlyMT5()
        self.denied(api,event=PPI_DEC)
        self.assertEqual(api.terminal_calls,0)

    def test_06_disconnected_terminal_blocked_without_any_query(self):
        api=FakeReadOnlyMT5(mode="disconnected")
        self.denied(api)
        self.assertEqual(len(api.calls),0)
        self.assertFalse(self.root.exists())

    def test_07_complete_mock_ppi_replay_7pairs_4anchors_and_manifest(self):
        result,api=self.allowed()
        self.assertEqual(len(api.calls),28)
        folder=self.root/PPI
        self.assertEqual(len(list(folder.iterdir())),8)
        self.assertTrue((folder/"receipt.json").exists())
        receipt=load(archive_root=self.root,event_root=PPI,inspected_at_utc=NOW)
        self.assertEqual(receipt.sha256_by_pair,
                         result["bidask_original_sha256_by_pair_local_claim"])
        reread=replay(archive_root=self.root,receipt=receipt,inspected_at_utc=NOW)
        self.assertEqual(reread["replayed_bidask_anchor_rows"],28)
        row=reread["local_quote_spread_samples_bps_by_pair"]["EURUSD"]
        self.assertEqual(row[0]["tick_age_milliseconds_local_claim"],1000)

    def test_08_cpi_future_clock_simulated_not_real_december_quotes(self):
        t=EVENTS[CPI_DEC]+timedelta(hours=5)
        self.allowed(event=CPI_DEC,at=t)

    def test_09_ppi_future_clock_simulated_not_real_december_quotes(self):
        t=EVENTS[PPI_DEC]+timedelta(hours=5)
        self.allowed(event=PPI_DEC,at=t)

    def test_10_no_existing_archive_can_be_overwritten(self):
        self.allowed()
        api=FakeReadOnlyMT5()
        r,_=self.denied(api)
        self.assertEqual(r["reason"],"ORIGINAL_EVENT_ARCHIVE_ALREADY_EXISTS_NO_OVERWRITE")
        self.assertEqual(api.calls,[])

    def test_11_tick_missing_on_any_pair_aborts_all_without_archive(self):
        api=FakeReadOnlyMT5(mode="missing")
        r,_=self.denied(api)
        self.assertGreater(r["historical_tick_read_calls"],0)
        self.assertFalse(self.root.exists())

    def test_12_tick_after_fixed_anchor_rejected_as_lookahead(self):
        self.denied(FakeReadOnlyMT5(mode="future"))
        self.assertFalse(self.root.exists())

    def test_13_tick_older_than_five_seconds_not_interpolated(self):
        self.denied(FakeReadOnlyMT5(mode="stale"))
        self.assertFalse(self.root.exists())

    def test_14_tick_exactly_on_anchor_allowed_in_mock(self):
        self.allowed(FakeReadOnlyMT5(mode="at_anchor"))

    def test_15_tick_at_five_seconds_boundary_allowed(self):
        result,_=self.allowed(FakeReadOnlyMT5(mode="boundary"))
        receipt=load(archive_root=self.root,event_root=PPI,inspected_at_utc=NOW)
        r=replay(archive_root=self.root,receipt=receipt,inspected_at_utc=NOW)
        self.assertEqual(r["local_quote_spread_samples_bps_by_pair"]["EURUSD"][0]
                         ["tick_age_milliseconds_local_claim"],5000)

    def test_16_out_of_order_ticks_are_not_silently_sorted(self):
        self.denied(FakeReadOnlyMT5(mode="out_of_order"))

    def test_17_duplicate_millisecond_ticks_do_not_create_extra_anchor(self):
        self.allowed(FakeReadOnlyMT5(mode="duplicate_ms"))

    def test_18_missing_bid_field_rejected(self):
        self.denied(FakeReadOnlyMT5(mode="missing_bid"))

    def test_19_seconds_and_milliseconds_must_describe_same_instant(self):
        self.denied(FakeReadOnlyMT5(mode="time_seconds_mismatch"))

    def test_20_crossed_or_zero_bidask_is_not_valid_quote(self):
        self.denied(FakeReadOnlyMT5(mode="zero_spread"))

    def test_21_negative_bid_rejected(self):
        self.denied(FakeReadOnlyMT5(mode="negative_bid"))

    def test_22_off_tick_quote_not_arbitrarily_rounded(self):
        self.denied(FakeReadOnlyMT5(mode="non_grid"))

    def test_23_missing_symbol_metadata_does_not_turn_into_six_pair_export(self):
        self.denied(FakeReadOnlyMT5(mode="symbol_missing"))
        self.assertFalse(self.root.exists())

    def test_24_invalid_symbol_quote_grid_rejected(self):
        self.denied(FakeReadOnlyMT5(mode="wrong_digits"))

    def test_25_market_watch_visibility_change_rejected_without_writing(self):
        self.denied(FakeReadOnlyMT5(mode="visibility_flip"))
        self.assertFalse(self.root.exists())

    def test_26_query_exception_fail_closed_and_counted(self):
        api=FakeReadOnlyMT5(mode="raise_read")
        result,_=self.denied(api)
        self.assertEqual(result["historical_tick_read_calls"],1)
        self.assertEqual(len(api.calls),1)
        self.assertFalse(self.root.exists())

    def test_27_UTC_minus_four_clock_same_instant_and_hashes(self):
        result,_=self.allowed(at=NOW.astimezone(CUIABA))
        self.assertEqual(result["tick_snapshots_selected"],28)

    def test_28_manifest_cannot_add_duplicate_JSON_keys(self):
        self.allowed()
        file=self.root/PPI/"receipt.json"
        original=file.read_text("utf-8")
        file.write_text(original.replace('"schema":','"schema":"MALICIOUS","schema":',1),
                        encoding="utf-8")
        with self.assertRaises(ValueError):
            load(archive_root=self.root,event_root=PPI,inspected_at_utc=NOW)

    def test_29_manifest_cannot_change_claimed_event_root(self):
        self.allowed()
        file=self.root/PPI/"receipt.json"
        m=json.loads(file.read_text("utf-8"))
        m["event_root"]=CPI_DEC
        file.write_text(json.dumps(m),encoding="utf-8")
        with self.assertRaises(ValueError):
            load(archive_root=self.root,event_root=PPI,inspected_at_utc=NOW)

    def test_30_replay_catches_archive_tamper_after_capture(self):
        self.allowed()
        file=self.root/PPI/"EURUSD_BIDASK_ANCHORS.csv"
        file.write_bytes(file.read_bytes()+b"\n")
        with self.assertRaises(ValueError):
            load(archive_root=self.root,event_root=PPI,inspected_at_utc=NOW)

    def test_31_replay_before_manifest_capture_time_not_visible(self):
        self.allowed()
        with self.assertRaises(ValueError):
            load(archive_root=self.root,event_root=PPI,
                 inspected_at_utc=EVENTS[PPI]+timedelta(hours=4))

    def test_32_root_symlink_cannot_redirect_local_export(self):
        with TemporaryDirectory() as d:
            target=Path(d)/"outside"
            target.mkdir()
            parent=self.root.parent
            parent.mkdir(parents=True)
            self.root.symlink_to(target,target_is_directory=True)
            api=FakeReadOnlyMT5()
            self.denied(api)
            self.assertEqual(api.terminal_calls,0)

    def test_33_reader_does_not_call_initialize_or_order_send(self):
        _,api=self.allowed()
        self.assertEqual(api.terminal_calls,1)
        self.assertEqual(len(api.info_calls),14)
        self.assertEqual(len(api.calls),28)


if __name__=="__main__":
    unittest.main()
