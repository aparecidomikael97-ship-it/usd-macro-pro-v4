"""All synthetic CSV/receipts; no real broker prices, quotes or MT5 calls."""
from __future__ import annotations

import csv
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from atlasquant_trader_us_macro_mt5_bidask_anchor_archive_lab import (
    ANCHORS, EVENTS, PAIR_ORDER, SOURCE_KIND, LocalMT5BidAskAnchorReceipt,
    inspect_local_mt5_7fx_bidask_anchor_archive_lab as inspect,
)

UTC=timezone.utc
CUIABA=timezone(timedelta(hours=-4))
PPI="US_PPI_OCT2026"
CPI_DEC="US_CPI_NOV2026"
PPI_DEC="US_PPI_NOV2026"
NOW=datetime(2026,11,16,10,0,tzinfo=UTC)
HEAD=("anchor","anchor_epoch_msc","tick_time_msc","bid","ask")
OFFSETS=(-15,15,60,240)
GOOD="LAB_US_MACRO_7FX_TICK_BIDASK_ARCHIVE_DOCUMENTARY_ONLY_NO_GO"
BAD="LAB_US_MACRO_7FX_TICK_BIDASK_ARCHIVE_BLOCKED_HARD_NO_GO"


def rows(event=PPI,pair="EURUSD"):
    release=EVENTS[event]
    p=PAIR_ORDER.index(pair)
    mid=100.0 if pair=="USDJPY" else 1.10000+p*0.00017
    return [{
        "anchor":ANCHORS[i],
        "anchor_epoch_msc":str(int(
            (release+timedelta(minutes=off)).timestamp())*1000),
        "tick_time_msc":str(int(
            (release+timedelta(minutes=off)).timestamp())*1000-1000),
        "bid":f"{mid:.5f}",
        "ask":f"{mid+0.00020:.5f}",
    } for i,off in enumerate(OFFSETS)]


class TickFixture:
    def __init__(self,root,event=PPI):
        self.root=Path(root)
        self.event=event
        self.folder=self.root/event
        self.folder.mkdir()
        self.samples={p:rows(event,p) for p in PAIR_ORDER}
        self.receipt=self.write()

    def write(self):
        hashes={}
        for p,rs in self.samples.items():
            file=self.folder/f"{p}_BIDASK_ANCHORS.csv"
            with file.open("w",newline="",encoding="utf-8") as stream:
                writer=csv.DictWriter(stream,fieldnames=HEAD,lineterminator="\n")
                writer.writeheader()
                writer.writerows(rs)
            hashes[p]=sha256(file.read_bytes()).hexdigest()
        release=EVENTS[self.event]
        return LocalMT5BidAskAnchorReceipt(
            event_root=self.event,source_kind=SOURCE_KIND,
            captured_at_utc=release+timedelta(hours=5),
            sha256_by_pair=hashes,
            broker_company_label_claim="Pepperstone (LOCAL LABEL NOT VERIFIED)",
        )


class ReadOnlyMT5TickArchiveTests(unittest.TestCase):
    def safe(self,result,event=PPI):
        self.assertEqual(result["schema"],
            "ATLASQUANT_US_MACRO_MT5_7FX_TICK_BIDASK_ANCHOR_ARCHIVE_LAB_V1")
        self.assertEqual(result["event_root"],event)
        self.assertEqual(result["expected_pair_count"],7)
        self.assertEqual(result["expected_quote_rows"],28)
        self.assertTrue(result["missing_pair_means_whole_study_abstains"])
        self.assertTrue(result["prices_are_historical_receipt_claims_only"])
        for key in (
            "mt5_broker_identity_independently_authenticated",
            "quote_bid_ask_source_first_seen_independently_authenticated",
            "tick_stream_complete_and_latest_quote_independently_verified",
            "bidask_at_execution_venue_independently_verified",
            "slippage_commission_and_order_fill_verified",
            "actual_trading_cost_verified",
            "net_return_or_pnl_calculated",
            "forecast_precommitted_and_verified",
            "publishable","trade_authorized","worker_enabled",
            "scheduler_enabled","fx28_original_672_slots_changed",
        ):
            self.assertFalse(result[key],key)
        self.assertEqual(result["independent_fx_directional_trials"],0)
        self.assertIsNone(result["historical_forex_accuracy"])
        self.assertIsNone(result["calibrated_probability"])
        self.assertEqual(result["operational_bias"],"AGUARDAR")
        self.assertEqual((result["mt5_calls"],result["http_requests"],
                          result["file_writes"],result["new_cost_brl"]),(0,0,0))

    def allowed(self,fixture,at=NOW,receipt=None):
        r=inspect(archive_root=fixture.root,receipt=receipt or fixture.receipt,
                  inspected_at_utc=at)
        self.safe(r,fixture.event)
        self.assertEqual(r["state"],GOOD,r["reason"])
        self.assertEqual(r["replayed_pair_count"],7)
        self.assertEqual(r["replayed_bidask_anchor_rows"],28)
        self.assertEqual(set(r["local_quote_spread_samples_bps_by_pair"]),set(PAIR_ORDER))
        return r

    def blocked(self,fixture,at=NOW,receipt=None):
        r=inspect(archive_root=fixture.root,receipt=receipt or fixture.receipt,
                  inspected_at_utc=at)
        self.safe(r,fixture.event)
        self.assertEqual(r["state"],BAD)
        self.assertEqual(r["replayed_pair_count"],0)
        self.assertEqual(r["replayed_bidask_anchor_rows"],0)
        self.assertIsNone(r["local_quote_spread_samples_bps_by_pair"])
        return r

    def test_01_7pairs_4quotes_each_documentary_only(self):
        with TemporaryDirectory() as d:
            r=self.allowed(TickFixture(d))
            row=r["local_quote_spread_samples_bps_by_pair"]["EURUSD"]
            self.assertEqual([v["anchor"] for v in row],list(ANCHORS))
            self.assertEqual(row[0]["tick_age_milliseconds_local_claim"],1000)
            self.assertTrue(row[0]["historical_quote_not_executable_spread_or_fill"])

    def test_02_ppi_historical_event_clock_is_nov13_1330utc(self):
        self.assertEqual(EVENTS[PPI],
                         datetime(2026,11,13,13,30,tzinfo=UTC))

    def test_03_future_december_cpi_denied_as_of_november(self):
        with TemporaryDirectory() as d:
            f=TickFixture(d,CPI_DEC)
            r=self.blocked(f)
            self.assertEqual(r["reason"],
                "FUTURE_EVENT_OR_FOUR_HOUR_REACTION_WINDOW_NOT_CLOSED")

    def test_04_future_december_ppi_denied_as_of_november(self):
        with TemporaryDirectory() as d:
            f=TickFixture(d,PPI_DEC)
            r=self.blocked(f)
            self.assertEqual(r["reason"],
                "FUTURE_EVENT_OR_FOUR_HOUR_REACTION_WINDOW_NOT_CLOSED")

    def test_05_future_cpi_after_h4_close_does_not_become_a_forecast(self):
        with TemporaryDirectory() as d:
            f=TickFixture(d,CPI_DEC)
            self.allowed(f,at=f.receipt.captured_at_utc)

    def test_06_future_ppi_after_h4_close_does_not_become_a_forecast(self):
        with TemporaryDirectory() as d:
            f=TickFixture(d,PPI_DEC)
            self.allowed(f,at=f.receipt.captured_at_utc)

    def test_07_asof_one_microsecond_before_h4_close_denied(self):
        with TemporaryDirectory() as d:
            f=TickFixture(d)
            at=EVENTS[PPI]+timedelta(hours=4)-timedelta(microseconds=1)
            self.blocked(f,at=at)

    def test_08_receipt_capture_before_h4_close_denied(self):
        with TemporaryDirectory() as d:
            f=TickFixture(d)
            r=replace(f.receipt,
                      captured_at_utc=EVENTS[PPI]+timedelta(hours=3))
            self.blocked(f,receipt=r)

    def test_09_receipt_capture_after_research_cutoff_denied(self):
        with TemporaryDirectory() as d:
            f=TickFixture(d)
            self.blocked(f,at=f.receipt.captured_at_utc-timedelta(microseconds=1))

    def test_10_cuiaba_time_offset_is_same_utc_instant(self):
        with TemporaryDirectory() as d:
            f=TickFixture(d)
            alt=replace(f.receipt,
                captured_at_utc=f.receipt.captured_at_utc.astimezone(CUIABA))
            a=self.allowed(f)
            b=self.allowed(f,receipt=alt,at=NOW.astimezone(CUIABA))
            self.assertEqual(a,b)

    def test_11_naive_research_clock_fail_closed(self):
        with TemporaryDirectory() as d:
            f=TickFixture(d)
            self.blocked(f,at=datetime(2026,11,16,10))

    def test_12_naive_capture_clock_fail_closed(self):
        with TemporaryDirectory() as d:
            f=TickFixture(d)
            self.blocked(f,receipt=replace(
                f.receipt,captured_at_utc=datetime(2026,11,13,18,30)))

    def test_13_one_missing_csv_blocks_whole_7pair_result(self):
        with TemporaryDirectory() as d:
            f=TickFixture(d)
            (f.folder/"GBPUSD_BIDASK_ANCHORS.csv").unlink()
            self.blocked(f)

    def test_14_tamper_one_quote_byte_fails_sha_gate(self):
        with TemporaryDirectory() as d:
            f=TickFixture(d)
            file=f.folder/"EURUSD_BIDASK_ANCHORS.csv"
            file.write_bytes(file.read_bytes()+b"BAD")
            self.blocked(f)

    def test_15_one_wrong_digest_claim_refused(self):
        with TemporaryDirectory() as d:
            f=TickFixture(d)
            hashes={**f.receipt.sha256_by_pair,"EURUSD":"f"*64}
            self.blocked(f,receipt=replace(f.receipt,sha256_by_pair=hashes))

    def test_16_missing_digest_for_one_pair_refused(self):
        with TemporaryDirectory() as d:
            f=TickFixture(d)
            hashes={k:v for k,v in f.receipt.sha256_by_pair.items() if k!="EURUSD"}
            self.blocked(f,receipt=replace(f.receipt,sha256_by_pair=hashes))

    def test_17_reused_digest_for_two_pairs_refused(self):
        with TemporaryDirectory() as d:
            f=TickFixture(d)
            hashes={**f.receipt.sha256_by_pair}
            hashes["GBPUSD"]=hashes["EURUSD"]
            self.blocked(f,receipt=replace(f.receipt,sha256_by_pair=hashes))

    def test_18_same_pair_bad_anchor_time_not_cherry_pick(self):
        with TemporaryDirectory() as d:
            f=TickFixture(d)
            f.samples["EURUSD"][1]["anchor_epoch_msc"]=str(
                int(f.samples["EURUSD"][1]["anchor_epoch_msc"])+1000)
            f.receipt=f.write()
            self.blocked(f)

    def test_19_tick_after_fixed_anchor_is_lookahead(self):
        with TemporaryDirectory() as d:
            f=TickFixture(d)
            f.samples["EURUSD"][0]["tick_time_msc"]=str(
                int(f.samples["EURUSD"][0]["anchor_epoch_msc"])+1)
            f.receipt=f.write()
            self.blocked(f)

    def test_20_exact_five_seconds_staleness_is_maximum(self):
        with TemporaryDirectory() as d:
            f=TickFixture(d)
            item=f.samples["EURUSD"][0]
            item["tick_time_msc"]=str(int(item["anchor_epoch_msc"])-5000)
            f.receipt=f.write()
            r=self.allowed(f)
            self.assertEqual(r["local_quote_spread_samples_bps_by_pair"]["EURUSD"][0]
                             ["tick_age_milliseconds_local_claim"],5000)

    def test_21_five_seconds_plus_one_ms_stale_rejected(self):
        with TemporaryDirectory() as d:
            f=TickFixture(d)
            item=f.samples["EURUSD"][0]
            item["tick_time_msc"]=str(int(item["anchor_epoch_msc"])-5001)
            f.receipt=f.write()
            self.blocked(f)

    def test_22_crossed_bid_ask_quote_refused(self):
        with TemporaryDirectory() as d:
            f=TickFixture(d)
            item=f.samples["USDJPY"][2]
            item["ask"]=str(float(item["bid"])-0.001)
            f.receipt=f.write()
            self.blocked(f)

    def test_23_zero_spread_is_not_execution_free(self):
        with TemporaryDirectory() as d:
            f=TickFixture(d)
            item=f.samples["EURUSD"][0]
            item["ask"]=item["bid"]
            f.receipt=f.write()
            self.blocked(f)

    def test_24_negative_or_nan_bid_refused(self):
        for bad in ("-1","NaN","Inf","1e200","not_a_quote"):
            with self.subTest(bad=bad),TemporaryDirectory() as d:
                f=TickFixture(d)
                f.samples["EURUSD"][0]["bid"]=bad
                f.receipt=f.write()
                self.blocked(f)

    def test_25_one_duplicate_anchor_never_four_valid_quotes(self):
        with TemporaryDirectory() as d:
            f=TickFixture(d)
            f.samples["EURUSD"][1]["anchor"]=f.samples["EURUSD"][0]["anchor"]
            f.receipt=f.write()
            self.blocked(f)

    def test_26_one_missing_row_refused_not_partial_three_anchors(self):
        with TemporaryDirectory() as d:
            f=TickFixture(d)
            f.samples["EURUSD"].pop()
            f.receipt=f.write()
            self.blocked(f)

    def test_27_symlinked_csv_refused(self):
        with TemporaryDirectory() as d:
            f=TickFixture(d)
            p=f.folder/"EURUSD_BIDASK_ANCHORS.csv"
            dst=f.folder/"outside_quote.csv"
            p.rename(dst)
            p.symlink_to(dst)
            self.blocked(f)

    def test_28_wrong_receipt_source_kind_refused(self):
        with TemporaryDirectory() as d:
            f=TickFixture(d)
            self.blocked(f,receipt=replace(f.receipt,source_kind="OHLC_BAR_SPREAD_NOT_TICKS"))

    def test_29_unknown_event_root_rejected_before_csv(self):
        with TemporaryDirectory() as d:
            f=TickFixture(d)
            r=inspect(archive_root=f.root,receipt=replace(
                f.receipt,event_root="US_FED_MAY2010"),
                inspected_at_utc=NOW)
            self.assertEqual(r["state"],BAD)
            self.assertIsNone(r["event_root"])
            self.assertFalse(r["trade_authorized"])

    def test_30_company_label_is_not_authenticated_broker_identity(self):
        with TemporaryDirectory() as d:
            f=TickFixture(d)
            fake=replace(f.receipt,broker_company_label_claim="FAKE BROKER NAME")
            r=self.allowed(f,receipt=fake)
            self.assertFalse(r["mt5_broker_identity_independently_authenticated"])
            self.assertFalse(r["bidask_at_execution_venue_independently_verified"])

    def test_31_integer_millisecond_timestamp_not_naive_seconds(self):
        with TemporaryDirectory() as d:
            f=TickFixture(d)
            f.samples["EURUSD"][0]["tick_time_msc"]="1794575700"
            f.receipt=f.write()
            self.blocked(f)

    def test_32_m15_bar_spread_does_not_masquerade_as_tick_bidask(self):
        with TemporaryDirectory() as d:
            f=TickFixture(d)
            f.samples["EURUSD"][0]["ask"]="11pts"
            f.receipt=f.write()
            self.blocked(f)

    def test_33_one_wrong_column_name_does_not_coerce_consensus(self):
        with TemporaryDirectory() as d:
            f=TickFixture(d)
            p=f.folder/"EURUSD_BIDASK_ANCHORS.csv"
            raw=p.read_text("utf-8")
            p.write_text(raw.replace("tick_time_msc","bar_spread",1),encoding="utf-8")
            hashes={**f.receipt.sha256_by_pair,"EURUSD":sha256(p.read_bytes()).hexdigest()}
            self.blocked(f,receipt=replace(f.receipt,sha256_by_pair=hashes))


if __name__=="__main__":
    unittest.main()
