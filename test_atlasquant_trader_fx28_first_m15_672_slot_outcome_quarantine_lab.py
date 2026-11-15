"""Synthetic-only regressions. Never read a real campaign archive or MT5."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from atlasquant_trader_fx28_first_m15_672_slot_outcome_quarantine_lab import (
    inspect_first_m15_672_slot_outcome_quarantine_lab as quarantine,
    STATUS,
)
from atlasquant_trader_fx28_first_m15_atomic_claim_lab import (
    claim_once_lab, CLAIM_NAME, WINDOW,
)
from atlasquant_trader_fx28_ny17_m15_writeonce_capture_lab import collect_window_lab
from test_atlasquant_trader_fx28_first_m15_no_duplicate_precheck_lab import (
    StrictMock, CLOSED, TERMINAL,
)
from test_atlasquant_trader_fx28_first_m15_archive_census_readonly_lab import (
    OneCandleMock,
)

UTC=timezone.utc
NOW=datetime(2026,11,15,22,30,tzinfo=UTC)
START=datetime(2026,11,15,22,0,tzinfo=UTC)


class FirstM15QuarantineTests(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory(prefix="AQ_M15_672_JOIN_NO_MT5_")
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/"FX28_NY17_M15"
        self.root.mkdir()

    def inspect(self, *, now=NOW, claims=()):
        return quarantine(
            archive_root=self.root, window_claims=claims,
            inspected_at_utc=now)

    def prepare(self, fake=None):
        fake=StrictMock([]) if fake is None else fake
        claim=claim_once_lab(archive_root=self.root,clock=lambda:CLOSED)
        self.assertTrue(claim["exclusive_claim_created"])
        res=collect_window_lab(
            fake,window=WINDOW,terminal_path=TERMINAL,
            output_root=self.root,clock=lambda:CLOSED)
        return fake,res

    def test_01_28_missing_prices_quarantine_56_not_56_losing_trades(self):
        fake,archive=self.prepare()
        self.assertEqual(archive["missing_m15_total"],28)
        before=list(fake.calls)
        result=self.inspect()
        self.assertEqual(fake.calls,before)
        self.assertEqual(result["state"],
            "LAB_FX28_FIRST_M15_56_OUTCOMES_QUARANTINED_NO_GO")
        self.assertEqual(result["ledger_slots_accounted"],672)
        self.assertEqual(result["first_window_pair_horizon_slots"],56)
        self.assertEqual(result["first_window_d1_slots"],28)
        self.assertEqual(result["first_window_w1_slots"],28)
        self.assertEqual(result["missing_distinct_nominal_m15_start_prices"],28)
        self.assertEqual(result["quarantined_first_window_slots"],56)
        self.assertEqual(result["other_frozen_slots_not_assessed"],616)
        self.assertEqual(result["claimed_issuance_summary"][
            "not_issued_before_window_slots_in_caller_input"],56)
        self.assertEqual(result["claimed_issuance_summary"][
            "not_yet_due_slots"],616)
        self.assertEqual(len(result["first_window_rows"]),56)
        self.assertEqual(len(set(x["slot_id"]
                                 for x in result["first_window_rows"])),56)
        for horizon in ("D1","W1"):
            cohort=[r for r in result["first_window_rows"]
                    if r["horizon"]==horizon]
            self.assertEqual(len(cohort),28)
            self.assertEqual(len(set(r["pair"] for r in cohort)),28)
        for slot in result["first_window_rows"]:
            self.assertEqual(slot["nominal_start_price_status"],STATUS)
            self.assertEqual(slot["nominal_window_start_utc"],START.isoformat())
            self.assertFalse(slot["scored_as_hit"])
            self.assertFalse(slot["scored_as_miss"])
            self.assertFalse(slot["scored_as_trade"])
            self.assertFalse(slot["broker_price_authenticated"])
        self.assertIsNone(result["validated_accuracy"])
        self.assertIsNone(result["calibrated_probability"])
        self.assertFalse(result["github_witness_absence_independently_verified"])
        self.assertFalse(result["trade_authorized"])
        self.assertFalse(result["publishable"])
        self.assertEqual((result["mt5_calls"],result["file_writes"],
                          result["http_requests"]),(0,0,0))

    def test_02_no_archived_attempt_is_not_28_missing_bars(self):
        r=self.inspect()
        self.assertEqual(r["reason"],
            "ARCHIVE_NOT_CONFIRMED_ALL_28_NOMINAL_M15_ABSENT")
        self.assertEqual(r["first_window_pair_horizon_slots"],0)
        self.assertIsNone(r["missing_distinct_nominal_m15_start_prices"])

    def test_03_claim_without_archive_is_not_a_price_gap(self):
        self.assertTrue(claim_once_lab(
            archive_root=self.root,clock=lambda:CLOSED)["exclusive_claim_created"])
        r=self.inspect()
        self.assertEqual(r["reason"],
            "ARCHIVE_NOT_CONFIRMED_ALL_28_NOMINAL_M15_ABSENT")
        self.assertEqual(r["quarantined_first_window_slots"],0)

    def test_04_one_missing_of_28_does_not_guess_56_slot_membership(self):
        _,archive=self.prepare(OneCandleMock(empty_symbol="EURUSD"))
        self.assertEqual(archive["missing_m15_total"],1)
        r=self.inspect()
        self.assertEqual(r["reason"],
            "ARCHIVE_NOT_CONFIRMED_ALL_28_NOMINAL_M15_ABSENT")
        self.assertEqual(r["quarantined_first_window_slots"],0)

    def test_05_all_28_valid_prices_do_not_quarantine_outcomes(self):
        _,archive=self.prepare(OneCandleMock())
        self.assertEqual(archive["captured_m15_total"],28)
        r=self.inspect()
        self.assertEqual(r["reason"],
            "ARCHIVE_NOT_CONFIRMED_ALL_28_NOMINAL_M15_ABSENT")

    def test_06_api_none_failed_before_archive_does_not_invent_gap(self):
        _,archive=self.prepare(StrictMock(None))
        self.assertEqual(archive["reason"],
            "MT5_HISTORY_QUERY_FAILED_NONE_EURUSD")
        r=self.inspect()
        self.assertEqual(r["reason"],
            "ARCHIVE_NOT_CONFIRMED_ALL_28_NOMINAL_M15_ABSENT")

    def test_07_duplicate_archive_blocks_link(self):
        self.prepare()
        (self.root/(WINDOW+"_second")).mkdir()
        r=self.inspect()
        self.assertEqual(r["reason"],
            "ARCHIVE_NOT_CONFIRMED_ALL_28_NOMINAL_M15_ABSENT")
        self.assertEqual(r["ledger_slots_accounted"],0)

    def test_08_corrupt_claim_blocks_no_quarantine(self):
        self.prepare()
        (self.root/CLAIM_NAME).write_text("CORRUPT",encoding="utf-8")
        r=self.inspect()
        self.assertEqual(r["reason"],
            "ARCHIVE_NOT_CONFIRMED_ALL_28_NOMINAL_M15_ABSENT")
        self.assertEqual(r["quarantined_first_window_slots"],0)

    def test_09_tampered_csv_blocks_no_quarantine(self):
        _,archive=self.prepare()
        folder=Path(archive["archive_dir"])
        with (folder/"EURUSD_M15.csv").open("ab") as handle:
            handle.write(b"tamper")
        r=self.inspect()
        self.assertEqual(r["reason"],
            "ARCHIVE_NOT_CONFIRMED_ALL_28_NOMINAL_M15_ABSENT")

    def test_10_clock_before_campaign_does_not_count_slots(self):
        r=self.inspect(now=START-timedelta(seconds=1))
        self.assertEqual(r["reason"],"FROZEN_FIRST_WINDOW_NOT_STARTED")
        self.assertEqual(r["ledger_slots_accounted"],0)

    def test_11_clock_microsecond_or_naive_rejected(self):
        for now in (NOW+timedelta(microseconds=1),
                    datetime(2026,11,15,22,30)):
            with self.subTest(now=str(now)):
                r=self.inspect(now=now)
                self.assertEqual(r["reason"],
                    "INVALID_CLOCK_ARCHIVE_ROOT_OR_LEDGER_INPUT")

    def test_12_invalid_forecast_claim_blocks_no_autofill(self):
        self.prepare()
        r=self.inspect(claims=(object(),))
        self.assertEqual(r["reason"],
            "FROZEN_672_SLOT_LEDGER_INCOMPLETE_OR_UNVERIFIED")
        self.assertEqual(r["quarantined_first_window_slots"],0)


if __name__=="__main__":
    unittest.main(verbosity=2)
