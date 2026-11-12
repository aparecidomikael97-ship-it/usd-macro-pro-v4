"""Synthetic M15 market reaction tests only: ZERO real broker/event performance."""
from dataclasses import replace
from datetime import datetime, timezone, timedelta
from hashlib import sha256
from decimal import Decimal
from pathlib import Path
import csv
import tempfile
import unittest

from atlasquant_trader_ppi_usd_fx_forward_reaction_lab import (
    EVENT_UTC, BASELINE_OPEN_UTC, LAST_REQUIRED_CLOSE_UTC, USD_FX,
    FIELDS, ClaimedLocalPriceArchive, inspect_ppi_fx_m15_forward_reaction_lab as inspect,
)

NOW = LAST_REQUIRED_CLOSE_UTC + timedelta(minutes=15)

class EventResponseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.values = {}
        for sym in USD_FX:
            rows = []
            for i in range(17):
                p = Decimal("1.0") + Decimal(i) * Decimal("0.001") if sym.startswith("USD") else Decimal("1.0") - Decimal(i) * Decimal("0.001")
                rows.append({
                    "time_utc_epoch":str(int(BASELINE_OPEN_UTC.timestamp())+900*i),
                    "open":str(p),"high":str(p+Decimal("0.002")),"low":str(p-Decimal("0.002")),
                    "close":str(p),"tick_volume":"70","spread":"11","real_volume":"0",
                })
            self.values[sym] = rows
        self.receipt = self.save_all()

    def save_all(self):
        hashes={}
        for sym,rows in self.values.items():
            path=self.root / f"{sym}_PPI_20261113_M15.csv"
            with path.open('w',newline='',encoding='utf-8') as f:
                writer=csv.DictWriter(f,fieldnames=FIELDS,lineterminator='\n')
                writer.writeheader();writer.writerows(rows)
            hashes[sym]=sha256(path.read_bytes()).hexdigest()
        return ClaimedLocalPriceArchive(NOW,hashes)

    def run_lab(self, *, root=None, rec=None, now=NOW):
        return inspect(archive_root=self.root if root is None else root,
                       receipt=self.receipt if rec is None else rec, as_of_utc=now)

    def safe(self,r):
        self.assertEqual(r['operational_bias'],'AGUARDAR')
        self.assertFalse(r['publishable'])
        self.assertFalse(r['trade_authorized'])
        self.assertFalse(r['worker_enabled'])
        self.assertFalse(r['scheduler_enabled'])
        self.assertFalse(r['source_broker_independently_authenticated'])
        self.assertFalse(r['statistical_causal_impact_identified'])
        self.assertIsNone(r['directional_forecast'])
        self.assertIsNone(r['calibrated_probability'])
        self.assertIsNone(r['historical_out_of_sample_accuracy'])
        self.assertEqual(r['new_cost_brl'],0)

    def test_complete_seven_pair_documentary_reaction(self):
        r=self.run_lab()
        self.assertEqual(r['state'],'LAB_PPI_FX_7PAIR_FORWARD_REACTION_DOCUMENTARY_NO_GO')
        self.assertEqual(set(r['price_reactions_usd_normalized_bps']),set(USD_FX))
        for sym,results in r['price_reactions_usd_normalized_bps'].items():
            self.assertEqual(set(results),{'M15','H1','H4'})
            self.assertGreater(float(results['H4']),0)  # intentionally fictional positive USD direction
        self.assertEqual(r['independent_economic_event_sample_count'],1)
        self.safe(r)

    def test_not_seven_independent_events(self):
        r=self.run_lab();self.assertEqual(r['independent_economic_event_sample_count'],1)
        self.safe(r)

    def test_before_release_or_four_hour_end_wait(self):
        for at in (EVENT_UTC-timedelta(seconds=1),EVENT_UTC,
                   LAST_REQUIRED_CLOSE_UTC-timedelta(seconds=1)):
            with self.subTest(at=at):
                r=self.run_lab(now=at)
                self.assertEqual(r['state'],'LAB_WAIT_PPI_FX_FORWARD_WINDOW')
                self.assertIsNone(r['price_reactions_usd_normalized_bps'])
                self.safe(r)

    def test_no_archive_after_release_still_blocks(self):
        r=inspect(archive_root=self.root,receipt=None,as_of_utc=NOW)
        self.assertEqual(r['reason'],'PRICE_ARCHIVE_NOT_SUPPLIED');self.safe(r)

    def test_expected_cohort_is_exactly_seven_usd_fx_pairs(self):
        self.assertEqual(USD_FX,('EURUSD','GBPUSD','AUDUSD','NZDUSD','USDJPY','USDCHF','USDCAD'))

    def test_missing_one_symbol_cannot_report_six_as_seven(self):
        (self.root/'GBPUSD_PPI_20261113_M15.csv').unlink()
        r=self.run_lab();self.assertEqual(r['failed_symbol'],'GBPUSD')
        self.assertIsNone(r['price_reactions_usd_normalized_bps']);self.safe(r)

    def test_missing_hash_in_manifest_blocks(self):
        hashes=self.receipt.sha256_by_symbol.copy();del hashes['EURUSD']
        r=self.run_lab(rec=replace(self.receipt,sha256_by_symbol=hashes))
        self.assertEqual(r['reason'],'INVALID_OR_INCOMPLETE_SEVEN_PAIR_RECEIPT');self.safe(r)

    def test_extra_symbol_in_manifest_blocks(self):
        hashes=self.receipt.sha256_by_symbol.copy();hashes['EURGBP']='a'*64
        r=self.run_lab(rec=replace(self.receipt,sha256_by_symbol=hashes))
        self.assertEqual(r['reason'],'INVALID_OR_INCOMPLETE_SEVEN_PAIR_RECEIPT');self.safe(r)

    def test_changed_csv_after_receipt_detected(self):
        p=self.root/'EURUSD_PPI_20261113_M15.csv';p.write_bytes(p.read_bytes()+b'\n')
        r=self.run_lab();self.assertEqual(r['series_failure'],'ARCHIVE_RAW_SHA256_MISMATCH');self.safe(r)

    def test_missing_bar_no_cherry_picked_windows(self):
        del self.values['USDJPY'][5];self.receipt=self.save_all()
        r=self.run_lab();self.assertEqual(r['series_failure'],'ALL_17_CONTIGUOUS_M15_BARS_REQUIRED');self.safe(r)

    def test_inserted_bar_no_cherry_picked_windows(self):
        self.values['USDJPY'].append(self.values['USDJPY'][-1]);self.receipt=self.save_all()
        r=self.run_lab();self.assertEqual(r['series_failure'],'ALL_17_CONTIGUOUS_M15_BARS_REQUIRED');self.safe(r)

    def test_duplicate_or_wrong_event_epoch_rejected(self):
        self.values['EURUSD'][1]['time_utc_epoch']=self.values['EURUSD'][0]['time_utc_epoch'];self.receipt=self.save_all()
        r=self.run_lab();self.assertEqual(r['series_failure'],'M15_GAP_DUPLICATE_OR_WRONG_EVENT_WINDOW');self.safe(r)

    def test_bad_OHLC_range_rejected(self):
        self.values['EURUSD'][3]['high']='0.1';self.receipt=self.save_all()
        r=self.run_lab();self.assertEqual(r['series_failure'],'OHLC_RANGE_INCONSISTENT');self.safe(r)

    def test_zero_tick_volume_requires_review(self):
        self.values['EURUSD'][3]['tick_volume']='0';self.receipt=self.save_all()
        r=self.run_lab();self.assertEqual(r['series_failure'],'ZERO_TICK_VOLUME_NEEDS_BROKER_REVIEW');self.safe(r)

    def test_nonnumeric_price_not_converted(self):
        self.values['EURUSD'][3]['close']='=42';self.receipt=self.save_all()
        r=self.run_lab();self.assertEqual(r['series_failure'],'INVALID_OHLC_PRICE');self.safe(r)

    def test_negative_spread_not_accepted(self):
        self.values['EURUSD'][3]['spread']='-1';self.receipt=self.save_all()
        r=self.run_lab();self.assertEqual(r['series_failure'],'INVALID_M15_VOLUME_OR_SPREAD');self.safe(r)

    def test_pre_close_claimed_archive_not_allowed(self):
        r=self.run_lab(rec=replace(self.receipt,captured_at_utc=EVENT_UTC+timedelta(hours=1)))
        self.assertEqual(r['reason'],'INVALID_OR_INCOMPLETE_SEVEN_PAIR_RECEIPT');self.safe(r)

    def test_future_archive_and_invalid_clock_rejected(self):
        r=self.run_lab(rec=replace(self.receipt,captured_at_utc=NOW+timedelta(seconds=1)))
        self.assertEqual(r['reason'],'INVALID_OR_INCOMPLETE_SEVEN_PAIR_RECEIPT');self.safe(r)
        r=self.run_lab(now=NOW.replace(tzinfo=None))
        self.assertEqual(r['reason'],'INVALID_AS_OF_CLOCK');self.safe(r)

    def test_non_MT5_source_kind_not_trusted(self):
        r=self.run_lab(rec=replace(self.receipt,source_kind='BROKER_VERIFIED'))
        self.assertEqual(r['reason'],'INVALID_OR_INCOMPLETE_SEVEN_PAIR_RECEIPT');self.safe(r)

    def test_orientations_invert_quote_usd_exactly(self):
        r=self.run_lab()
        # EURUSD falls from 1 to 0.984 -> positive USD bps, USDJPY rises -> positive USD bps.
        self.assertNotEqual(r['price_reactions_usd_normalized_bps']['EURUSD']['H4'],
                            r['price_reactions_usd_normalized_bps']['USDJPY']['H4'])
        self.assertTrue(all(float(r['price_reactions_usd_normalized_bps'][s]['H4']) > 0 for s in USD_FX))
        self.safe(r)

    def test_entry_is_not_a_market_order_and_costs_not_verified(self):
        r=self.run_lab()
        self.assertFalse(r['execution_bid_ask_and_slippage_verified'])
        self.assertFalse(r['prediction_precommitted_and_validated'])
        self.safe(r)

if __name__ == '__main__':
    unittest.main()