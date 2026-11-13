"""Prospective 672-slot Sunday preflight tests; synthetic, no real forecasts."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from contextlib import redirect_stdout
from unittest.mock import patch
from copy import deepcopy
import io
import json
import unittest

from atlasquant_trader_fx28_28pair_source_readiness_manual_lab import (
    SCHEMA as READINESS_SCHEMA,
)
from atlasquant_trader_fx28_sunday_launch_preflight_lab import (
    SCHEMA, inspect_fx28_sunday_opening_preflight_lab as inspect, main,
)

UTC = timezone.utc
BEFORE = datetime(2026, 11, 13, 17, tzinfo=UTC)
START = datetime(2026, 11, 15, 22, tzinfo=UTC)
LAST = datetime(2026, 12, 11, 22, tzinfo=UTC)


def local_source_claim(codes=()):
    codes = sorted(codes)
    return {
        "schema": READINESS_SCHEMA,
        "state": "LAB_FX28_28PAIR_MANUAL_SOURCE_READINESS_NO_GO",
        "operational_bias": "AGUARDAR",
        "trade_authorized": False,
        "publishable": False,
        "pairs_explained": 28,
        "pre_event_forecasts_independently_witnessed": False,
        "first_seen_pit_authenticated": False,
        "bilateral_cpi_yoy_authenticated": False,
        "local_policy_sources_checked_codes": codes,
        "local_policy_sources_checked_count": len(codes),
        "pairs_with_two_policy_sources_locally_checked":
            len(codes)*(len(codes)-1)//2,
    }


class SundayCampaignOpeningTests(unittest.TestCase):
    def safe(self, x):
        self.assertEqual(x["schema"], SCHEMA)
        self.assertEqual(x["operational_bias"], "AGUARDAR")
        self.assertIsNone(x["directional_bias"])
        self.assertIsNone(x["calibrated_probability"])
        self.assertEqual(x["independently_authenticated_pre_event_forecasts"], 0)
        self.assertFalse(x["sufficient_verified_macro_to_issue_direction"])
        self.assertFalse(x["broker_ny17_m15_verified"])
        self.assertFalse(x["policy_readiness_report_is_authenticated_source"])
        self.assertFalse(x["first_d1_forecast_roster_independently_witnessed"])
        self.assertFalse(x["first_w1_forecast_roster_independently_witnessed"])
        self.assertFalse(x["pre_event_roster_can_be_backfilled_after_start"])
        for key in ("trade_authorized", "publishable", "live_alert_allowed",
                    "worker_enabled", "scheduler_enabled"):
            self.assertFalse(x[key])
        self.assertEqual(x["http_requests"], 0)
        self.assertEqual(x["file_writes"], 0)
        self.assertEqual(x["new_cost_brl"], 0)

    def ok(self, **kwargs):
        x = inspect(inspected_at_utc=BEFORE, **kwargs)
        self.safe(x)
        self.assertEqual(x["state"], "LAB_FX28_CAMPAIGN_OPENING_RESEARCH_ONLY_NO_GO")
        self.assertEqual(x["expected_pair_horizon_opportunities"], 672)
        self.assertEqual(x["expected_d1_opportunities"], 560)
        self.assertEqual(x["expected_w1_opportunities"], 112)
        self.assertTrue(x["not_independent_bernoulli_trials"])
        self.assertEqual(x["window_roster_length"], 24)
        self.assertEqual(len(x["required_actions"]), 8)
        return x

    def blocked(self, **kwargs):
        x = inspect(inspected_at_utc=BEFORE, **kwargs)
        self.safe(x)
        self.assertEqual(x["state"], "LAB_FX28_CAMPAIGN_OPENING_PREFLIGHT_BLOCKED")
        self.assertEqual(x["window_roster_length"], 0)
        return x

    def test_01_first_d1_w1_starts_frozen_same_utc_and_two_ends(self):
        x=self.ok()
        self.assertEqual(x["campaign_begin_utc"], "2026-11-15T22:00:00Z")
        self.assertEqual(x["first_d1_end_utc"], "2026-11-16T22:00:00Z")
        self.assertEqual(x["first_w1_end_utc"], "2026-11-20T22:00:00Z")
        self.assertEqual(x["future_nominal_pair_horizon_slots"],672)
        self.assertEqual(x["due_nominal_pair_horizon_slots"],0)
        self.assertEqual(x["seconds_until_first_nominal_open"],53*60*60)
        self.assertEqual(x["next_nominal_window_starts_utc"],
                         "2026-11-15T22:00:00Z")
        self.assertFalse(x["first_nominal_open_already_due"])

    def test_02_timezone_offset_same_utc_countdown(self):
        mt=timezone(timedelta(hours=-4))
        at=datetime(2026,11,13,13,tzinfo=mt)
        x=inspect(inspected_at_utc=at)
        self.safe(x)
        self.assertEqual(x["checked_clock_utc"],"2026-11-13T17:00:00Z")
        self.assertEqual(x["seconds_until_first_nominal_open"],53*60*60)

    def test_03_exact_open_debits_both_initial_horizons_no_hindsight(self):
        x=inspect(inspected_at_utc=START)
        self.safe(x)
        self.assertEqual(x["state"],"LAB_FX28_CAMPAIGN_OPENING_RESEARCH_ONLY_NO_GO")
        self.assertEqual(x["reason"],"OPENED_NO_RETROACTIVE_FORECAST")
        self.assertEqual(x["due_nominal_pair_horizon_slots"],56)
        self.assertEqual(x["future_nominal_pair_horizon_slots"],616)
        self.assertEqual(x["next_nominal_window_starts_utc"],
                         "2026-11-16T22:00:00Z")
        self.assertTrue(x["first_nominal_open_already_due"])

    def test_04_one_second_before_start_is_still_future(self):
        x=inspect(inspected_at_utc=START-timedelta(seconds=1))
        self.safe(x)
        self.assertEqual(x["seconds_until_first_nominal_open"],1)
        self.assertEqual(x["due_nominal_pair_horizon_slots"],0)

    def test_05_after_second_d1_open_has_84_due_including_first_week(self):
        x=inspect(inspected_at_utc=START+timedelta(days=1))
        self.safe(x)
        self.assertEqual(x["due_nominal_pair_horizon_slots"],84)
        self.assertEqual(x["future_nominal_pair_horizon_slots"],588)

    def test_06_exact_end_all_672_due_no_backfill(self):
        x=inspect(inspected_at_utc=LAST)
        self.safe(x)
        self.assertEqual(x["reason"],"CAMPAIGN_CLOSED_NO_RETROACTIVE_FORECAST")
        self.assertEqual(x["future_nominal_pair_horizon_slots"],0)
        self.assertEqual(x["due_nominal_pair_horizon_slots"],672)
        self.assertIsNone(x["next_nominal_window_starts_utc"])

    def test_07_unknown_local_archive_is_unknown_not_zero_sources(self):
        x=self.ok()
        self.assertIsNone(x["local_bank_policy_currency_count"])
        self.assertIsNone(x["local_bank_policy_pair_coverage_count"])
        self.assertEqual(x["local_bank_policy_currency_codes_checked"],[])

    def test_08_synthetic_three_and_eight_bank_source_claim_no_go(self):
        for codes in (("USD","EUR","CAD"),
                      ("USD","EUR","GBP","JPY","CHF","CAD","AUD","NZD")):
            with self.subTest(codes=codes):
                x=self.ok(local_policy_readiness=local_source_claim(codes))
                self.assertEqual(x["local_bank_policy_currency_count"],len(codes))
                self.assertEqual(
                    x["local_bank_policy_pair_coverage_count"],
                    len(codes)*(len(codes)-1)//2)
                self.assertIsNone(x["directional_bias"])

    def test_09_fake_source_direction_or_false_pit_blocks(self):
        for k,val in (("state","LIVE"),("trade_authorized",True),
                      ("publishable",True),("first_seen_pit_authenticated",True),
                      ("bilateral_cpi_yoy_authenticated",True),
                      ("pre_event_forecasts_independently_witnessed",True)):
            with self.subTest(k=k):
                rep=local_source_claim(("EUR","USD"))
                rep[k]=val
                x=self.blocked(local_policy_readiness=rep)
                self.assertEqual(x["reason"],"POLICY_SOURCE_READINESS_REPORT_INADMISSIBLE")

    def test_10_currency_duplicates_and_fake_pair_count_block(self):
        for k,val in (("local_policy_sources_checked_codes",["USD","USD"]),
                      ("local_policy_sources_checked_codes",["NOK"]),
                      ("local_policy_sources_checked_count", 8),
                      ("pairs_with_two_policy_sources_locally_checked",28)):
            with self.subTest(k=k):
                rep=local_source_claim(("USD","EUR"))
                rep[k]=val
                x=self.blocked(local_policy_readiness=rep)
                self.assertEqual(x["reason"],"POLICY_SOURCE_READINESS_COVERAGE_INCOHERENT")

    def test_11_empty_explicit_witness_snapshot_is_not_evidence_of_filled_roster(self):
        x=self.ok(window_witness_claims=[])
        self.assertTrue(x["witness_snapshot_was_supplied"])
        self.assertEqual(x["claimed_window_anchors_checked"],0)
        self.assertEqual(x["independently_authenticated_pre_event_forecasts"],0)

    def test_12_malformed_witness_claim_list_blocked(self):
        for bad in (42,{},[None],["fake future price"]):
            with self.subTest(bad=bad):
                x=self.blocked(window_witness_claims=bad)
                self.assertEqual(x["reason"],
                                 "WITNESS_SNAPSHOT_INADMISSIBLE_OR_CLOCK_TOO_EARLY")

    def test_13_clock_rejects_naive_microseconds_and_not_datetime(self):
        for bad in (None, "2026-11-13T17:00:00Z",
                    BEFORE.replace(tzinfo=None),
                    BEFORE.replace(microsecond=1)):
            with self.subTest(bad=bad):
                x=inspect(inspected_at_utc=bad)
                self.safe(x)
                self.assertEqual(x["state"],
                                 "LAB_FX28_CAMPAIGN_OPENING_PREFLIGHT_BLOCKED")
                self.assertEqual(x["reason"],
                                 "INVALID_CLOCK_OR_FROZEN_CAMPAIGN")

    def test_14_readiness_input_not_mutated_by_preflight(self):
        src=local_source_claim(("EUR","USD","CAD"))
        before=deepcopy(src)
        self.ok(local_policy_readiness=src)
        self.assertEqual(src,before)

    def test_15_without_explicit_cli_flag_no_source_audit(self):
        with patch("atlasquant_trader_fx28_sunday_launch_preflight_lab.inspect_28pair_source_readiness_once_lab") as audit:
            out=io.StringIO()
            with redirect_stdout(out):
                status=main([])
            self.assertEqual(status,2)
            self.assertEqual(json.loads(out.getvalue())["reason"],
                             "EXPLICIT_PREFLIGHT_REQUIRED")
            audit.assert_not_called()

    def test_16_cli_preflight_is_read_only_and_claim_unwitnessed(self):
        source=local_source_claim(("EUR","USD","CAD"))
        with patch("atlasquant_trader_fx28_sunday_launch_preflight_lab.inspect_28pair_source_readiness_once_lab",
                   return_value=source) as audit:
            out=io.StringIO()
            with redirect_stdout(out):
                code=main(["--preflight"])
            self.assertEqual(code,2)
            audit.assert_called_once()
            self.assertEqual(audit.call_args.kwargs["mode"],"audit")
            parsed=json.loads(out.getvalue())
            self.safe(parsed)
            self.assertEqual(parsed["local_bank_policy_currency_count"],3)
            self.assertFalse(parsed["witness_snapshot_was_supplied"])

    def test_17_cli_missing_archive_does_not_invent_zero_local_sources(self):
        with patch("atlasquant_trader_fx28_sunday_launch_preflight_lab.inspect_28pair_source_readiness_once_lab",
                   return_value={"state":"LAB_FX28_28PAIR_READINESS_BLOCKED"}) as audit:
            out=io.StringIO()
            with redirect_stdout(out):
                code=main(["--preflight"])
            self.assertEqual(code,2)
            parsed=json.loads(out.getvalue())
            self.safe(parsed)
            self.assertIsNone(parsed["local_bank_policy_currency_count"])
            audit.assert_called_once()


if __name__=="__main__":
    unittest.main()
