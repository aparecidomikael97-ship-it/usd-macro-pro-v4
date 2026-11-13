"""Offline tests for real-pattern session/W1 context; all fixtures synthetic."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone, timedelta
import unittest

from atlasquant_instrument_registry import FX_28
from atlasquant_trader_fx28_mt5_ny17_w1_gap_attribution_lab import (
    _empty as week_empty, W1_WINDOWS_UTC,
)
from atlasquant_trader_fx28_native_session_w1_context_lab import (
    reconcile_fx28_current_sessions_and_past_w1_lab as reconcile,
)
from test_atlasquant_trader_fx28_native_session_csv_guard_lab import (
    native_rows, encode,
)

NOW = datetime(2026, 11, 13, 0, 10, tzinfo=timezone.utc)
SYNTHETIC_NO_BROKER_HISTORY = True


def mock_csv_rows():
    """Synthetic analog of observed 15x00:01, 13x00:05 native schedule."""
    rows = native_rows()
    late = set(FX_28[15:])
    for row in rows:
        if row["status"] in ("NO_SESSION_RETURNED",
                             "END_OF_RETURNED_SESSIONS"):
            row["mt5_last_error_code"] = "4307"
        if (row["status"] == "SESSION_RETURNED"
                and row["server_weekday"] == "1"
                and row["canonical_symbol"] in late):
            row["from_server_midnight_seconds"] = "300"
        if row["status"] == "SESSION_RETURNED" and row["server_weekday"] == "5":
            row["to_server_midnight_seconds"] = "86100"
    return rows


def mock_w1_reports():
    weeks = []
    for day, shared, pair_specific in (
        ("2026-10-25", 12, {"GBPNZD": 9, "CHFJPY": 10, "AUDNZD": 1}),
        ("2026-11-01", 8, {"GBPNZD": 9, "CHFJPY": 10, "EURNZD": 11}),
    ):
        week = week_empty("MISSING_M15_SLOTS_NO_CALENDAR_EXEMPTION_OR_FILL")
        week.update({
            "state": "LAB_FX28_W1_NY17_SHARED_AND_PAIR_GAPS_NO_GO",
            "reference_sunday_ny": day,
            "window_start_utc": W1_WINDOWS_UTC[day][0],
            "window_end_utc_exclusive": W1_WINDOWS_UTC[day][1],
            "pair_count_attempted": 28,
            "complete_480_pairs": 0,
            "all_pairs_timeseries_structurally_valid": True,
            "all_expected_weekly_m15_slots_present": False,
            "shared_missing_utc_slot_count": shared,
            "shared_missing_pair_slots_total": 28 * shared,
            "pair_specific_missing_by_symbol": {
                sym: pair_specific.get(sym, 0) for sym in FX_28},
            "pair_specific_missing_slots_total": sum(pair_specific.values()),
            "missing_slots_total": 28 * shared + sum(pair_specific.values()),
        })
        weeks.append(week)
    return weeks


class NativeW1ContextTests(unittest.TestCase):
    def run_join(self, *, rows=None, weeks=None, now=NOW):
        return reconcile(
            native_csv_bytes=encode(mock_csv_rows() if rows is None else rows),
            historic_w1_reports=(mock_w1_reports() if weeks is None else weeks),
            evaluated_at_utc=now,
        )

    def safe(self, report):
        self.assertEqual(report["operational_bias"], "AGUARDAR")
        self.assertFalse(report["trade_authorized"])
        self.assertFalse(report["publishable"])
        self.assertFalse(report["scheduler_enabled"])
        self.assertFalse(report["worker_enabled"])
        self.assertFalse(report["live_alert_allowed"])
        self.assertFalse(report["native_current_schedule_applies_to_past_weeks_verified"])
        self.assertFalse(report["broker_server_utc_offset_now_independently_verified"])
        self.assertFalse(report["market_closed_for_missing_slots_verified"])
        self.assertFalse(report["historical_calendar_exemptions"])
        self.assertFalse(report["candles_synthesized_or_backfilled"])
        self.assertFalse(report["outcome_labels_authorized"])
        self.assertIsNone(report["historical_forecast_accuracy"])
        self.assertIsNone(report["calibrated_probability"])
        self.assertIsNone(report["directional_bias"])
        self.assertIsNone(report["broker_server_utc_offset_at_history"])
        self.assertFalse(report["mt5_account_accessed"])
        self.assertFalse(report["orders_or_positions_accessed"])
        self.assertEqual(report["files_written"], 0)
        self.assertEqual(report["external_calls"], 0)

    def test_synthetic_reconciliation_reports_15_13_and_two_past_weeks(self):
        r = self.run_join()
        self.safe(r)
        self.assertEqual(r["state"], "LAB_FX28_NATIVE_CURRENT_VS_PAST_W1_RECONCILED_NO_GO")
        self.assertEqual(r["native_schedule_claim_count"], 392)
        self.assertEqual(r["native_session_terminator_4307_count"], 392)
        self.assertEqual(r["native_quote_trade_weekday_disagreements"], 0)
        self.assertEqual(r["current_monday_quote_start_by_server_minute"]["00:01"],
                         list(FX_28[:15]))
        self.assertEqual(r["current_monday_quote_start_by_server_minute"]["00:05"],
                         list(FX_28[15:]))
        self.assertEqual(r["current_friday_quote_end_by_server_minute"]["23:55"],
                         list(FX_28))
        self.assertEqual(r["historical_weeks_reconciled"], 2)
        oct_week = r["historical_weekly_gap_context"]["2026-10-25"]
        nov_week = r["historical_weekly_gap_context"]["2026-11-01"]
        self.assertEqual(oct_week["total_missing_slots"], 356)
        self.assertEqual(nov_week["total_missing_slots"], 254)
        self.assertEqual(oct_week["shared_pair_slots_without_candles"], 336)
        self.assertEqual(nov_week["shared_pair_slots_without_candles"], 224)
        self.assertEqual(nov_week["pair_specific_CHFJPY"], 10)
        self.assertFalse(nov_week["calendar_closure_or_feed_failure_inferred"])

    def test_changed_native_4307_marker_blocks_no_market_closed_inference(self):
        for state in ("0", "4302", "4301"):
            rows = mock_csv_rows()
            marker = next(x for x in rows if x["status"] == "NO_SESSION_RETURNED")
            marker["mt5_last_error_code"] = state
            r = self.run_join(rows=rows)
            self.safe(r)
            self.assertEqual(r["reason"],
                             "NATIVE_SESSION_END_MARKER_OR_WEEKDAY_SHAPE_INVALID")

    def test_missing_day_native_receipt_blocks(self):
        rows = [r for r in mock_csv_rows() if not (
            r["canonical_symbol"] == "GBPNZD" and
            r["server_weekday"] == "1")]
        r = self.run_join(rows=rows)
        self.safe(r)
        self.assertEqual(r["reason"], "NATIVE_SESSION_RECEIPT_NOT_STRUCTURALLY_ACCEPTED")

    def test_quote_trade_conflict_flags_reject_current_schedule_equality(self):
        rows = mock_csv_rows()
        row = next(r for r in rows if r["canonical_symbol"] == "GBPUSD"
                   and r["server_weekday"] == "3"
                   and r["session_kind"] == "TRADE"
                   and r["status"] == "SESSION_RETURNED")
        row["from_server_midnight_seconds"] = "120"
        r = self.run_join(rows=rows)
        self.safe(r)
        self.assertEqual(r["reason"],
                         "QUOTE_TRADE_WEEKDAY_SCHEDULES_DIFFER_CURRENTLY")

    def test_multiple_weekday_sessions_require_review_not_silent_single_open(self):
        rows = mock_csv_rows()
        row = next(r for r in rows if r["canonical_symbol"] == "EURUSD"
                   and r["server_weekday"] == "1"
                   and r["session_kind"] == "QUOTE"
                   and r["status"] == "END_OF_RETURNED_SESSIONS")
        row["session_index"] = "2"
        rows.insert(rows.index(row), {
            **row, "session_index": "1", "status": "SESSION_RETURNED",
            "from_server_midnight_seconds": "120",
            "to_server_midnight_seconds": "180",
            "mt5_last_error_code": "0",
        })
        r = self.run_join(rows=rows)
        self.safe(r)
        self.assertEqual(r["reason"], "NATIVE_SESSION_END_MARKER_OR_WEEKDAY_SHAPE_INVALID")

    def test_missing_or_duplicate_past_w1_cannot_count_two_economic_weeks(self):
        for weeks in (
            [mock_w1_reports()[0]],
            [mock_w1_reports()[0], mock_w1_reports()[0]],
        ):
            with self.subTest(weeks=weeks):
                r = self.run_join(weeks=weeks)
                self.safe(r)
                self.assertEqual(r["state"], "LAB_FX28_CURRENT_SESSION_W1_CONTEXT_BLOCKED")

    def test_malformed_total_or_pair_roster_invalid(self):
        for field in ("missing_slots_total", "shared_missing_pair_slots_total",
                      "pair_specific_missing_slots_total"):
            with self.subTest(field=field):
                weeks = mock_w1_reports()
                weeks[0][field] += 1
                r = self.run_join(weeks=weeks)
                self.safe(r)
                self.assertEqual(r["reason"],
                                 "HISTORICAL_W1_GAP_ARITHMETIC_OR_PAIR_ROSTER_INVALID")

    def test_metadata_today_does_not_establish_historical_session_timezone(self):
        r = self.run_join()
        self.safe(r)
        self.assertEqual(r["reason"],
                         "CONTEMPORARY_SERVER_HOURS_CANNOT_ATTEST_HISTORIC_UTC_SESSION_OR_EXEMPT_GAPS")
        self.assertIsNone(r["broker_server_utc_offset_at_history"])
        self.assertFalse(r["market_closed_for_missing_slots_verified"])
        self.assertEqual(r["historical_calendar_exemptions"], [])

    def test_fake_historical_authentication_never_promotes_results(self):
        for flag in (
            "source_feed_independently_verified",
            "reference_market_schedule_independently_authenticated",
            "trade_authorized",
        ):
            with self.subTest(flag=flag):
                weeks = mock_w1_reports()
                weeks[1][flag] = True
                r = self.run_join(weeks=weeks)
                self.safe(r)
                self.assertEqual(r["reason"],
                                 "HISTORICAL_W1_REPORT_OR_SAFETY_CLAIM_INVALID")

    def test_unverified_malformed_pair_count_and_historical_state_block(self):
        weeks = mock_w1_reports()
        weeks[1]["pair_count_attempted"] = 27
        r = self.run_join(weeks=weeks)
        self.safe(r)
        self.assertEqual(r["state"], "LAB_FX28_CURRENT_SESSION_W1_CONTEXT_BLOCKED")
        weeks = mock_w1_reports()
        weeks[0]["state"] = "ALLEGED_GO"
        self.assertEqual(self.run_join(weeks=weeks)["state"],
                         "LAB_FX28_CURRENT_SESSION_W1_CONTEXT_BLOCKED")


if __name__ == "__main__":
    unittest.main()
