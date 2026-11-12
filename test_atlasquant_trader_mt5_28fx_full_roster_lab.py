"""Offline tests: full NY17 roster, no cherry-picking of good sessions."""
from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from zoneinfo import ZoneInfo

from atlasquant_fx_universe import OFFICIAL_PAIRS

from atlasquant_trader_mt5_28fx_full_roster_lab import (
    inspect_am12_ny17_full_roster_lab as audit,
    main,
)
from test_atlasquant_trader_mt5_28fx_archive_reader_lab import build

UTC = timezone.utc
NY = ZoneInfo("America/New_York")
EVALUATED = datetime(2026, 12, 11, tzinfo=UTC)


def ny(day: int, month: int = 11, year: int = 2026) -> datetime:
    return datetime(year, month, day, 17, tzinfo=NY).astimezone(UTC)


def fake_ok(**kwargs):
    return {
        "state": "LAB_AM12_LOCAL_M15_WINDOW_CHECKS_ONLY_NO_GO",
        "reason": "LOCAL",
        "batch_result": {
            "coverage_claim_complete_pairs": 28,
            "pair_results": {
                pair: {
                    "state": "LAB_MT5_M15_ARCHIVE_NY17_LOCAL_JOIN_NO_GO",
                    "price_movement_direction_documentary": "UP",
                    "price_open_to_close_bps_documentary": "10.0000",
                    "price_window_start_open_documentary": "1.0000",
                    "price_window_end_close_documentary": "1.0010",
                }
                for pair in OFFICIAL_PAIRS
            },
        },
    }


def fake_gap(**kwargs):
    return {
        "state": "LAB_AM12_LOCAL_M15_INCOMPLETE_OR_GAPS_NO_GO",
        "reason": "ONE_PAIR_GAP",
        "batch_result": {
            "coverage_claim_complete_pairs": 27,
            "pair_results": {
                pair: ({
                    "state": "LAB_MT5_M15_ARCHIVE_NY17_JOIN_BLOCKED",
                    "reason": "M15_MISSING_ONE_EPOCH",
                } if pair == "EUR/USD" else {
                    "state": "LAB_MT5_M15_ARCHIVE_NY17_LOCAL_JOIN_NO_GO",
                    "price_movement_direction_documentary": "UP",
                    "price_open_to_close_bps_documentary": "10.0000",
                    "price_window_start_open_documentary": "1.0000",
                    "price_window_end_close_documentary": "1.0010",
                })
                for pair in OFFICIAL_PAIRS
            },
        },
    }


def run(*, horizon="D1", start=None, end=None, root="/tmp/unused-am12",
        evaluated=EVALUATED):
    return audit(
        root=root, horizon=horizon,
        range_start_at_utc=ny(8) if start is None else start,
        range_end_at_utc=ny(13) if end is None else end,
        evaluated_at_utc=evaluated,
    )


class FullNy17RosterTests(unittest.TestCase):
    def safe(self, r):
        self.assertEqual(r["operational_bias"], "AGUARDAR")
        self.assertIsNone(r["directional_accuracy_validated"])
        self.assertIsNone(r["calibrated_direction_probability"])
        for flag in (
            "weekend_and_holiday_calendar_independently_attested",
            "historical_broker_price_provenance_verified",
            "source_capture_clock_independently_verified",
            "pair_outcomes_independently_verified",
            "precommitted_forecast_evidence_verified",
            "statistical_out_of_sample_validation_completed",
            "trade_authorized", "publishable", "can_feed_live_radar",
            "live_alert_allowed",
        ):
            self.assertFalse(r[flag], flag)
        self.assertTrue(r["research_only"])
        self.assertEqual(
            (r["mt5_connections"], r["http_requests"],
             r["output_files_written"], r["new_cost_brl"]),
            (0, 0, 0, 0),
        )

    def test_all_five_daily_candidates_in_week_included(self):
        with patch(
            "atlasquant_trader_mt5_28fx_full_roster_lab.inspect_local_am12_28fx_lab",
            side_effect=fake_ok,
        ) as reader:
            result = run()
        self.assertEqual(result["state"],
                         "LAB_AM12_NY17_FULL_ROSTER_LOCAL_CLAIMS_ONLY_NO_GO")
        self.assertEqual(result["nominal_window_count"], 5)
        self.assertEqual(result["complete_local_window_count"], 5)
        self.assertEqual(result["total_expected_pair_window_checks"], 140)
        self.assertEqual(result["local_pair_window_checks_complete"], 140)
        self.assertEqual(reader.call_count, 5)
        self.assertEqual(set(result["complete_window_counts_by_pair"]), set(OFFICIAL_PAIRS))
        self.assertEqual(set(result["unverifiable_window_counts_by_pair"]), set(OFFICIAL_PAIRS))
        self.assertTrue(all(v == 5 for v in result["complete_window_counts_by_pair"].values()))
        self.assertTrue(all(v == 0 for v in result["unverifiable_window_counts_by_pair"].values()))
        self.assertEqual(
            [x["start_utc"] for x in result["windows"]],
            [ny(day).isoformat() for day in (8, 9, 10, 11, 12)],
        )
        self.assertEqual(result["windows"][-1]["end_utc"], ny(13).isoformat())
        self.safe(result)

    def test_all_two_weeks_included_without_weekend_dummy_bars(self):
        with patch(
            "atlasquant_trader_mt5_28fx_full_roster_lab.inspect_local_am12_28fx_lab",
            side_effect=fake_ok,
        ) as reader:
            result = run(horizon="W1", end=ny(20))
        self.assertEqual(result["nominal_window_count"], 2)
        self.assertEqual(result["total_expected_pair_window_checks"], 56)
        self.assertEqual([x["start_utc"] for x in result["windows"]],
                         [ny(8).isoformat(), ny(15).isoformat()])
        self.assertEqual([x["end_utc"] for x in result["windows"]],
                         [ny(13).isoformat(), ny(20).isoformat()])
        self.assertEqual(reader.call_count, 2)
        self.safe(result)

    def test_single_missed_pair_window_counts_139_of_140_not_28_of_28(self):
        def mixed(**kwargs):
            return fake_gap() if kwargs["start_at_utc"] == ny(10) else fake_ok()
        with patch(
            "atlasquant_trader_mt5_28fx_full_roster_lab.inspect_local_am12_28fx_lab",
            side_effect=mixed,
        ):
            result = run()
        self.assertEqual(result["state"], "LAB_AM12_NY17_FULL_ROSTER_HAS_GAPS_NO_GO")
        self.assertEqual(result["nominal_window_count"], 5)
        self.assertEqual(result["complete_local_window_count"], 4)
        self.assertEqual(result["blocked_or_incomplete_window_count"], 1)
        self.assertEqual(result["local_pair_window_checks_complete"], 139)
        self.assertEqual(result["blocked_or_unverifiable_pair_window_checks"], 1)
        self.assertEqual(result["windows"][2]["blocked_pairs"], ["EUR/USD"])
        self.assertNotIn("EUR/USD", result["windows"][2]["price_movements_documentary_by_pair"])
        self.assertEqual(result["windows"][2]["price_movements_documentary_by_pair"]["GBP/USD"]["change_bps_documentary"], "10.0000")
        self.assertEqual(result["windows"][2]["unverifiable_pair_reasons"],
                         {"EUR/USD": "M15_MISSING_ONE_EPOCH"})
        self.assertEqual(result["unverifiable_window_counts_by_pair"]["EUR/USD"], 1)
        self.assertEqual(result["complete_window_counts_by_pair"]["EUR/USD"], 4)
        self.assertEqual(result["complete_window_counts_by_pair"]["GBP/USD"], 5)
        self.assertFalse(result["all_nominal_windows_locally_checked_complete"])
        self.safe(result)

    def test_missing_manifest_disables_all_pair_counts_no_silent_skip(self):
        with patch(
            "atlasquant_trader_mt5_28fx_full_roster_lab.inspect_local_am12_28fx_lab",
            return_value={
                "state": "LAB_AM12_READONLY_28FX_RUNNER_BLOCKED",
                "reason": "SEVEN_BATCH_MANIFESTS_REQUIRED",
                "batch_result": None,
            },
        ):
            result = run()
        self.assertEqual(result["local_pair_window_checks_complete"], 0)
        self.assertEqual(result["blocked_or_unverifiable_pair_window_checks"], 140)
        self.assertEqual(result["blocked_or_incomplete_window_count"], 5)
        self.assertEqual(set(result["windows"][0]["blocked_pairs"]), set(OFFICIAL_PAIRS))
        self.assertEqual(set(result["windows"][0]["unverifiable_pair_reasons"]),
                         set(OFFICIAL_PAIRS))
        self.assertTrue(all(v == 5 for v in result["unverifiable_window_counts_by_pair"].values()))
        self.assertTrue(all(v == 0 for v in result["complete_window_counts_by_pair"].values()))
        self.assertEqual(result["windows"][0]["local_archive_check_reason"],
                         "SEVEN_BATCH_MANIFESTS_REQUIRED")
        self.safe(result)

    def test_inconsistent_green_count_without_pair_level_proof_blocks(self):
        forged = fake_ok()
        forged["batch_result"] = {
            "coverage_claim_complete_pairs": 28, "pair_results": {}
        }
        with patch(
            "atlasquant_trader_mt5_28fx_full_roster_lab.inspect_local_am12_28fx_lab",
            return_value=forged,
        ):
            r = run()
        self.assertEqual(r["state"], "LAB_AM12_NY17_FULL_ROSTER_BLOCKED")
        self.assertEqual(r["reason"], "INCOMPLETE_PAIR_DIAGNOSTICS_FROM_BATCH")
        self.assertEqual(r["local_pair_window_checks_complete"], 0)
        self.safe(r)

    def test_claimed_28_cannot_override_27_complete_pair_rows(self):
        inconsistent = fake_gap()
        inconsistent["batch_result"]["coverage_claim_complete_pairs"] = 28
        inconsistent["state"] = "LAB_AM12_LOCAL_M15_WINDOW_CHECKS_ONLY_NO_GO"
        with patch(
            "atlasquant_trader_mt5_28fx_full_roster_lab.inspect_local_am12_28fx_lab",
            return_value=inconsistent,
        ):
            r = run()
        self.assertEqual(r["state"], "LAB_AM12_NY17_FULL_ROSTER_BLOCKED")
        self.assertEqual(r["reason"], "INCONSISTENT_BATCH_COUNTS")
        self.safe(r)

    def test_green_window_without_documentary_price_label_is_blocked(self):
        forged = fake_ok()
        forged["batch_result"]["pair_results"]["EUR/USD"].pop(
            "price_open_to_close_bps_documentary")
        with patch(
            "atlasquant_trader_mt5_28fx_full_roster_lab.inspect_local_am12_28fx_lab",
            return_value=forged,
        ):
            result = run()
        self.assertEqual(result["state"], "LAB_AM12_NY17_FULL_ROSTER_BLOCKED")
        self.assertEqual(result["reason"],
                         "COMPLETE_PAIR_MISSING_DOCUMENTARY_PRICE_LABEL")
        self.safe(result)

    def test_naive_or_subsecond_ny17_bounds_fail_before_reader(self):
        for start in (
            ny(8).replace(tzinfo=None),
            ny(8) + timedelta(minutes=1),
            ny(8) + timedelta(microseconds=1),
        ):
            with self.subTest(start=start), patch(
                "atlasquant_trader_mt5_28fx_full_roster_lab.inspect_local_am12_28fx_lab"
            ) as reader:
                result = run(start=start)
                self.assertEqual(result["state"], "LAB_AM12_NY17_FULL_ROSTER_BLOCKED")
                reader.assert_not_called()
                self.safe(result)

    def test_w1_range_must_end_friday_and_begin_sunday(self):
        for start, end in ((ny(9), ny(13)), (ny(8), ny(12))):
            with self.subTest(start=start, end=end):
                result = run(horizon="W1", start=start, end=end)
                self.assertEqual(result["reason"],
                                 "W1_RANGE_MUST_START_SUNDAY_AND_END_FRIDAY_NY17")
                self.safe(result)

    def test_range_does_not_accept_unbounded_or_wrong_horizon(self):
        for horizon, start, end in (
            ("MN1", ny(8), ny(13)),
            ("D1", ny(8), ny(13) + timedelta(days=61)),
            ("D1", ny(13), ny(14)),
            ("D1", ny(8), ny(8)),
        ):
            with self.subTest(horizon=horizon, start=start, end=end):
                result = run(horizon=horizon, start=start, end=end)
                self.assertEqual(result["state"], "LAB_AM12_NY17_FULL_ROSTER_BLOCKED")
                self.safe(result)

    def test_d1_weekend_excluded_but_calendar_is_not_attested(self):
        with patch(
            "atlasquant_trader_mt5_28fx_full_roster_lab.inspect_local_am12_28fx_lab",
            side_effect=fake_ok,
        ):
            result = run(start=ny(12), end=ny(16))
        self.assertEqual(result["nominal_window_count"], 2)
        self.assertEqual([x["start_utc"] for x in result["windows"]],
                         [ny(12).isoformat(), ny(15).isoformat()])
        self.assertFalse(result["weekend_and_holiday_calendar_independently_attested"])
        self.safe(result)

    def test_daylight_saving_boundaries_are_iana_not_fixed_utc(self):
        with patch(
            "atlasquant_trader_mt5_28fx_full_roster_lab.inspect_local_am12_28fx_lab",
            side_effect=fake_ok,
        ):
            spring = run(start=ny(8, 3), end=ny(13, 3))
            fall = run(start=ny(1), end=ny(6))
        self.assertEqual(spring["nominal_window_count"], 5)
        self.assertEqual(fall["nominal_window_count"], 5)
        self.assertEqual(ny(8, 3).hour, 21)
        self.assertEqual(ny(1).hour, 22)
        self.safe(spring)
        self.safe(fall)

    def test_single_real_reader_integration_uses_disposable_mock_archive(self):
        with TemporaryDirectory() as directory:
            path = Path(directory)
            build(path)
            before = {p.name for p in path.iterdir()}
            result = run(root=path, start=ny(8), end=ny(9))
            self.assertEqual(result["state"],
                             "LAB_AM12_NY17_FULL_ROSTER_LOCAL_CLAIMS_ONLY_NO_GO")
            self.assertEqual(result["nominal_window_count"], 1)
            self.assertEqual(result["local_pair_window_checks_complete"], 28)
            movement = result["windows"][0]["price_movements_documentary_by_pair"]["EUR/USD"]
            self.assertEqual(movement["direction_documentary"], "UP")
            self.assertEqual(movement["change_bps_documentary"], "10.0000")
            self.assertIsNone(result["directional_accuracy_validated"])
            self.assertEqual({p.name for p in path.iterdir()}, before)
            self.safe(result)

    def test_command_line_prints_json_but_does_not_write_report(self):
        args = [
            "--root", "/unused",
            "--horizon", "W1",
            "--start-utc", ny(8).isoformat(),
            "--end-utc", ny(13).isoformat(),
            "--as-of-utc", EVALUATED.isoformat(),
        ]
        with patch(
            "atlasquant_trader_mt5_28fx_full_roster_lab.inspect_local_am12_28fx_lab",
            side_effect=fake_ok,
        ), patch("builtins.print") as printed:
            self.assertEqual(main(args), 0)
        self.assertEqual(printed.call_count, 1)
        data = json.loads(printed.call_args.args[0])
        self.assertEqual(data["nominal_window_count"], 1)
        self.assertEqual(data["output_files_written"], 0)
        self.safe(data)


if __name__ == "__main__":
    unittest.main()
