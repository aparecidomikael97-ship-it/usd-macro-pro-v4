"""Synthetic-only firewall tests; all campaigns are temp directories.

None of these tests connects to broker or network. The fake perfect
672/672 result is an adversarial documentary claim, NOT trading accuracy.
"""
from __future__ import annotations

from datetime import datetime,timedelta,timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from copy import deepcopy
import unittest

from atlasquant_trader_fx28_672_temporal_scoring_firewall_lab import (
    inspect_fx28_672_temporal_scoring_ingress_lab as audit,
)
from atlasquant_trader_fx28_first_m15_atomic_claim_lab import (
    claim_once_lab,CLAIM_NAME,WINDOW,
)
from atlasquant_trader_fx28_ny17_m15_writeonce_capture_lab import (
    collect_window_lab,
)
from test_atlasquant_trader_fx28_first_m15_no_duplicate_precheck_lab import (
    StrictMock,CLOSED,TERMINAL,
)
from test_atlasquant_trader_fx28_first_m15_archive_census_readonly_lab import (
    OneCandleMock,
)
from test_atlasquant_trader_fx28_sunday_open_research_protocol_lab import (
    historical_fixture,
)
from atlasquant_trader_fx28_ny17_prospective_campaign_lab import (
    FROZEN_END_UTC,
)

UTC=timezone.utc
ASOF=datetime(2026,11,15,23,45,tzinfo=UTC)
SUCCESS="LAB_FX28_672_FIRST56_AND_SERVER_CLOCK_P0_SCORING_QUARANTINE_NO_GO"


class ScoringTemporalIngressFirewallTests(unittest.TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory(prefix="AQ_FX28_TEMPORAL_NO_LIVE_MT5_")
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)/"FX28_NY17_M15"
        self.root.mkdir()

    def capture_mock(self,api=None):
        mock=StrictMock([]) if api is None else api
        claim=claim_once_lab(archive_root=self.root,clock=lambda:CLOSED)
        self.assertTrue(claim["exclusive_claim_created"])
        captured=collect_window_lab(
            mock,window=WINDOW,terminal_path=TERMINAL,
            output_root=self.root,clock=lambda:CLOSED)
        return mock,captured

    def check(self,*,history=None,when=ASOF,claims=(),
              proposed=None):
        return audit(
            archive_root=self.root,inspected_at_utc=when,
            historical_sunday_summaries=(
                historical_fixture() if history is None else history),
            window_claims=claims,
            proposed_documentary_scoring_report=proposed)

    def safe(self,r):
        self.assertEqual(r["frozen_total_slots"],672)
        self.assertFalse(r["source_first_seen_broker_authenticated"])
        self.assertFalse(r["market_server_utc_mapping_independently_attested"])
        self.assertFalse(r["historical_3_week_clocks_independently_attested"])
        self.assertFalse(r["pre_event_forecasts_independently_authenticated"])
        self.assertFalse(r["scoring_ingress_allowed"])
        self.assertFalse(r["documentary_perfect_score_claim_can_unlock_ingress"])
        self.assertFalse(r["directional_accuracy_validated"])
        self.assertFalse(r["frozen_campaign_slots_modified"])
        self.assertFalse(r["trade_authorized"])
        self.assertFalse(r["publishable"])
        self.assertFalse(r["scheduler_enabled"])
        self.assertIsNone(r["validated_accuracy"])
        self.assertIsNone(r["calibrated_probability"])
        self.assertEqual(r["documentary_score_count_released"],0)
        self.assertEqual((r["mt5_calls"],r["http_requests"],
                          r["file_writes"],r["new_cost_brl"]),(0,0,0,0))
        self.assertEqual((r["source_bars_backfilled"],r["historical_rows_retimed"]),(0,0))
        self.assertEqual(r["operational_bias"],"AGUARDAR")

    def test_01_live_like_synthetic_first_28_missing_56_d1w1_quarantined(self):
        mock,arch=self.capture_mock()
        self.assertEqual(arch["missing_m15_total"],28)
        calls=list(mock.calls)
        r=self.check()
        self.safe(r)
        self.assertEqual(mock.calls,calls)
        self.assertEqual(r["state"],SUCCESS)
        self.assertEqual(r["first_nominal_window_slots_quarantined"],56)
        self.assertEqual(r["first_nominal_window_distinct_m15_prices_missing"],28)
        self.assertEqual(r["remaining_original_slots_unevaluated"],616)
        self.assertEqual(r["first_window_horizons"],{"D1":28,"W1":28})
        self.assertEqual(r["sunday_weekly_history_samples"],3)
        self.assertEqual(r["matching_server_offset_weekly_minima"],3)
        self.assertFalse(r["source_price_window_complete"])

    def test_02_adversarial_posthoc_672_of_672_perfect_rollup_cannot_unlock(self):
        self.capture_mock()
        fake={"schema":"FAKE_SCORING_RESULTS",
              "total_documentary_reconciled_slots":672,
              "total_documentary_same_direction":672,
              "out_of_sample_accuracy_percent":100.0,
              "trade_authorized":True}
        r=self.check(proposed=fake)
        self.safe(r)
        self.assertEqual(r["state"],SUCCESS)
        self.assertEqual(r["documentary_score_count_released"],0)

    def test_03_missing_archive_not_inferred_as_missing_28_price_bars(self):
        r=self.check()
        self.safe(r)
        self.assertEqual(r["first_nominal_window_slots_quarantined"],0)
        self.assertEqual(r["reason"],"REAL_FIRST_M15_ARCHIVE_OR_672_LEDGER_NOT_CONFIRMED")

    def test_04_sealed_28_realistic_fake_bars_reject_56_missing_claim(self):
        _,arch=self.capture_mock(OneCandleMock())
        self.assertEqual(arch["captured_m15_total"],28)
        r=self.check()
        self.safe(r)
        self.assertEqual(r["reason"],"REAL_FIRST_M15_ARCHIVE_OR_672_LEDGER_NOT_CONFIRMED")

    def test_05_partial_27_present_1_missing_never_claim_56_quarantine(self):
        _,arch=self.capture_mock(OneCandleMock(empty_symbol="EURUSD"))
        self.assertEqual(arch["missing_m15_total"],1)
        r=self.check()
        self.safe(r)
        self.assertEqual(r["first_nominal_window_slots_quarantined"],0)

    def test_06_mt5_none_failure_does_not_count_28_missing(self):
        _,arch=self.capture_mock(StrictMock(None))
        self.assertEqual(arch["reason"],"MT5_HISTORY_QUERY_FAILED_NONE_EURUSD")
        r=self.check()
        self.safe(r)
        self.assertEqual(r["first_nominal_window_slots_quarantined"],0)

    def test_07_csv_or_manifest_tamper_cannot_pass(self):
        _,arch=self.capture_mock()
        folder=Path(arch["archive_dir"])
        file=folder/"EURUSD_M15.csv"
        with file.open("ab") as f:f.write(b"TAMPER")
        r=self.check()
        self.safe(r)
        self.assertEqual(r["first_nominal_window_slots_quarantined"],0)

    def test_08_extra_archive_duplicate_blocks_no_rescans(self):
        self.capture_mock()
        (self.root/(WINDOW+"_DUPLICATE")).mkdir()
        self.assertEqual(self.check()["first_nominal_window_slots_quarantined"],0)

    def test_09_missing_atomic_claim_blocks(self):
        self.capture_mock()
        (self.root/CLAIM_NAME).unlink()
        self.assertEqual(self.check()["first_nominal_window_slots_quarantined"],0)

    def test_10_invalid_historical_2h_or_3h_record_blocks_release(self):
        self.capture_mock()
        fake=historical_fixture()
        fake[0]["mt5_api_none_count"]=1
        r=self.check(history=fake)
        self.safe(r)
        self.assertEqual(r["first_nominal_window_slots_quarantined"],56)
        self.assertEqual(r["matching_server_offset_weekly_minima"],0)
        self.assertEqual(r["reason"],
            "SUNDAY_CLOCK_SOURCE_UNRESOLVED_OR_HISTORICAL_CLAIMS_INVALID")

    def test_11_mixed_offset_history_no_silent_retiming(self):
        self.capture_mock()
        fake=historical_fixture()
        dist=fake[1]["first_actual_m15_lag_minute_distribution"]
        dist["135"]+=dist.pop("120")
        fake[1]["min_observed_lag_min"]=135
        r=self.check(history=fake)
        self.safe(r)
        self.assertEqual(r["first_nominal_window_slots_quarantined"],56)
        self.assertEqual(r["historical_rows_retimed"],0)
        self.assertEqual(r["reason"],
            "SUNDAY_CLOCK_SOURCE_UNRESOLVED_OR_HISTORICAL_CLAIMS_INVALID")

    def test_12_clock_before_sunday_first_m15_cannot_pretend_started(self):
        self.capture_mock()
        r=self.check(when=datetime(2026,11,15,21,0,tzinfo=UTC))
        self.safe(r)
        self.assertEqual(r["first_nominal_window_slots_quarantined"],0)

    def test_13_naive_clock_rejected(self):
        r=self.check(when=datetime(2026,11,15,23,45))
        self.safe(r)
        self.assertEqual(r["reason"],
            "INVALID_ARCHIVE_CLOCK_OR_FORECAST_CLAIM_INPUT")

    def test_14_post_campaign_still_blocks_fake_accuracy(self):
        self.capture_mock()
        now=FROZEN_END_UTC+timedelta(seconds=1)
        fake={"out_of_sample_accuracy_percent":100.0,
              "total_documentary_same_direction":672}
        r=self.check(when=now,proposed=fake)
        self.safe(r)
        self.assertEqual(r["state"],SUCCESS)
        self.assertEqual(r["documentary_score_count_released"],0)

    def test_15_malicious_window_claim_cannot_claim_independent_precommit(self):
        self.capture_mock()
        r=self.check(claims=[object()])
        self.safe(r)
        self.assertEqual(r["first_nominal_window_slots_quarantined"],0)

    def test_16_invalid_proposed_documentary_score_input(self):
        self.capture_mock()
        r=self.check(proposed="100%")
        self.safe(r)
        self.assertEqual(r["reason"],
            "INVALID_ARCHIVE_CLOCK_OR_FORECAST_CLAIM_INPUT")


if __name__=="__main__":
    unittest.main(verbosity=2)
