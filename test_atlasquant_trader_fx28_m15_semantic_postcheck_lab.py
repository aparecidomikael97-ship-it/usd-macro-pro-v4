"""Portable offline FX28 M15 semantic post-check regression.
All candles are SYNTHETIC FakeMT5 responses; temporary files auto-deleted.
Do not interpret any test as broker evidence or a trading forecast.
"""
from __future__ import annotations
import csv,hashlib,json
from datetime import datetime,timezone
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from atlasquant_trader_fx28_ny17_m15_writeonce_capture_lab import collect_window_lab
from atlasquant_trader_fx28_m15_semantic_postcheck_lab import assert_semantics
UTC=timezone.utc
START=datetime(2026,11,15,22,0,tzinfo=UTC)
AFTER=datetime(2026,11,15,22,20,tzinfo=UTC)
EPOCH=int(START.timestamp())
CAMPAIGN="CAMPAIGN_FIRST_M15_20261115"
TERMINAL=r"C:\Program Files\Pepperstone MetaTrader 5\terminal64.exe"
class FakeMT5:
    TIMEFRAME_M15=15
    def __init__(self,empty=False):
        self.empty=empty
        self.calls=[]
    def initialize(self,**kw):
        self.calls.append("initialize")
        return True
    def terminal_info(self):
        self.calls.append("terminal_info")
        return SimpleNamespace(connected=True)
    def symbol_info(self,symbol):
        self.calls.append("symbol_info")
        digits=3 if symbol.endswith("JPY") else 5
        return SimpleNamespace(name=symbol,currency_base=symbol[:3],
          currency_profit=symbol[3:],digits=digits,
          point=10**(-digits),visible=True)
    def copy_rates_range(self,*args):
        self.calls.append("copy_rates_range")
        if self.empty:
            return []
        return [{"time":EPOCH,"open":1.200,"high":1.210,"low":1.190,
                 "close":1.205,"tick_volume":10,"spread":1,"real_volume":0}]
    def shutdown(self):
        self.calls.append("shutdown")
class SemanticPostcheck(unittest.TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory(prefix="aq_fx28_m15_semantic_ci_")
        self.addCleanup(self.tmp.cleanup)
        fake=FakeMT5()
        res=collect_window_lab(fake,window=CAMPAIGN,
            terminal_path=TERMINAL,output_root=Path(self.tmp.name),
            clock=lambda:AFTER)
        self.assertEqual(res["captured_symbols"],28)
        self.assertEqual(fake.calls.count("shutdown"),1)
        self.folder=Path(res["archive_dir"])
        self.csvpath=self.folder/"EURUSD_M15.csv"
        self.manpath=self.folder/"manifest.json"
    def mutate(self,fn,*,update_hash=True,change_claim=None):
        raw=self.csvpath.read_bytes().decode("utf-8")
        table=list(csv.reader(StringIO(raw)))
        fn(table)
        out=StringIO(newline="")
        writer=csv.writer(out,lineterminator="\n")
        writer.writerows(table)
        self.csvpath.write_bytes(out.getvalue().encode("utf-8"))
        if update_hash:
            manifest=json.loads(self.manpath.read_text(encoding="utf-8"))
            rec=manifest["files"]["EURUSD"]
            rec["sha256"]=hashlib.sha256(self.csvpath.read_bytes()).hexdigest()
            if change_claim is not None:
                change_claim(rec)
            self.manpath.write_bytes((json.dumps(manifest,sort_keys=True,indent=2)+"\n").encode())
    def blocked(self,reason):
        with self.assertRaisesRegex(ValueError,reason):
            assert_semantics(self.folder)
    def test_valid_first_bar_28_pairs(self):
        got=assert_semantics(self.folder)
        self.assertEqual(got["symbols_structurally_verified"],28)
        self.assertEqual(got["m15_rows_semantically_checked"],28)
        self.assertFalse(got["trading_authorized"])
        self.assertFalse(got["independent_broker_authentication"])
    def test_valid_empty_first_bar_28_gaps(self):
        with TemporaryDirectory(prefix="aq_fx28_m15_empty_") as tmp:
            out=collect_window_lab(FakeMT5(empty=True),window=CAMPAIGN,
               terminal_path=TERMINAL,output_root=Path(tmp),clock=lambda:AFTER)
            got=assert_semantics(Path(out["archive_dir"]))
            self.assertEqual(got["m15_rows_semantically_checked"],0)
            self.assertEqual(got["m15_gaps_from_base_verifier"],28)
    def test_invalid_header_fails_even_with_rehashed_manifest(self):
        self.mutate(lambda rows:rows[0].__setitem__(1,"MALICIOUS"))
        self.blocked("INVALID_CSV_HEADER")
    def test_bad_ohlc_fails_even_with_rehashed_manifest(self):
        self.mutate(lambda rows:rows[1].__setitem__(3,"9.99"))
        self.blocked("IMPOSSIBLE_OHLC_RANGE")
    def test_off_quote_grid_fails(self):
        self.mutate(lambda rows:rows[1].__setitem__(4,"1.205001"))
        self.blocked("INVALID_CSV_PRICE_GRID")
    def test_negative_price_fails(self):
        self.mutate(lambda rows:rows[1].__setitem__(4,"-1"))
        self.blocked("INVALID_CSV_PRICE")
    def test_zero_tick_volume_fails(self):
        self.mutate(lambda rows:rows[1].__setitem__(5,"0"))
        self.blocked("INVALID_VOLUME_OR_SPREAD")
    def test_negative_spread_fails(self):
        self.mutate(lambda rows:rows[1].__setitem__(6,"-1"))
        self.blocked("INVALID_VOLUME_OR_SPREAD")
    def test_extra_csv_field_fails(self):
        self.mutate(lambda rows:rows[1].append("EXTRA"))
        self.blocked("MALFORMED_CSV_ROW")
    def test_untouched_hash_detects_single_byte_change(self):
        self.mutate(lambda rows:rows[1].__setitem__(4,"1.204"),update_hash=False)
        self.blocked("CSV_SHA256_MISMATCH")
    def test_bad_quote_precision_claim_fails(self):
        self.mutate(lambda rows:None,change_claim=lambda rec:rec.update(price_digits_claim=1))
        self.blocked("INVALID_QUOTE_DIGITS")
    def test_noncanonical_epoch_plus_prefix_fails(self):
        self.mutate(lambda rows:rows[1].__setitem__(0,"+"+str(EPOCH)))
        self.blocked("NONCANONICAL_M15_EPOCH")
    def test_noncanonical_epoch_whitespace_fails(self):
        self.mutate(lambda rows:rows[1].__setitem__(0," "+str(EPOCH)))
        self.blocked("NONCANONICAL_M15_EPOCH")
    def test_manifest_endpoint_flag_lie_fails(self):
        self.mutate(lambda rows:None,change_claim=lambda rec:rec.update(first_expected_open_present=False))
        self.blocked("MANIFEST_CSV_GAP_DISAGREEMENT")
if __name__=="__main__": unittest.main(verbosity=2)
