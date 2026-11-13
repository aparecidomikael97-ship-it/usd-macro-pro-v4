"""Compare CURRENT native MT5 Forex sessions with past W1 M15 coverage.

This is evidence CONTEXT, not a reconstructed broker session calendar:
- Native sessions are from a CURRENT terminal snapshot and expressed as
  seconds from BROKER SERVER midnight, with no authenticated UTC offset.
- W1 2026-10-25 and 2026-11-01 are two past terminal-history claims.
- No caller, parameter or outcome can grant exclusions, backfill, bias,
  probability, alerts, trade permission, or historical market-close labels.
- All inputs are pure data; no MT5, file, internet or account actions.
"""
from __future__ import annotations

import csv
from datetime import datetime, timezone
from io import StringIO
from typing import Any

from atlasquant_instrument_registry import FX_28
from atlasquant_trader_fx28_native_session_csv_guard_lab import (
    inspect_fx28_native_session_csv_lab, RESULT_SCHEMA as RECEIPT_SCHEMA,
)
from atlasquant_trader_fx28_mt5_ny17_w1_gap_attribution_lab import (
    SCHEMA as WEEK_SCHEMA, W1_WINDOWS_UTC, W1_M15_COUNT,
)

SCHEMA = "ATLASQUANT_TRADER_FX28_NATIVE_SESSION_W1_CONTEXT_LAB_V1"
RECEIPT_SUCCESS = "LAB_FX28_NATIVE_MT5_SESSION_METADATA_CLAIM_ONLY_NO_GO"
WEEK_SUCCESS = "LAB_FX28_W1_NY17_SHARED_AND_PAIR_GAPS_NO_GO"


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_FX28_CURRENT_SESSION_W1_CONTEXT_BLOCKED",
        "reason": reason, "current_session_snapshot_utc_claim": None,
        "native_schedule_claim_count": 0, "native_quote_trade_weekday_disagreements": None,
        "current_monday_quote_start_by_server_minute": None,
        "current_friday_quote_end_by_server_minute": None,
        "native_quote_trade_session_matches_currently": False,
        "native_session_terminator_4307_count": None,
        "historical_weeks_reconciled": 0, "historical_weekly_gap_context": None,
        "broker_server_utc_offset_at_history": None,
        "broker_server_utc_offset_now_independently_verified": False,
        "native_current_schedule_applies_to_past_weeks_verified": False,
        "broker_current_session_metadata_independently_attested": False,
        "market_closed_for_missing_slots_verified": False,
        "historical_calendar_exemptions": [],
        "candles_synthesized_or_backfilled": False,
        "outcome_labels_authorized": False,
        "historical_forecast_accuracy": None,
        "calibrated_probability": None,
        "directional_bias": None, "operational_bias": "AGUARDAR",
        "publishable": False, "live_alert_allowed": False,
        "trade_authorized": False, "scheduler_enabled": False,
        "worker_enabled": False, "files_written": 0,
        "external_calls": 0, "mt5_account_accessed": False,
        "orders_or_positions_accessed": False, "new_cost_brl": 0,
        "research_only": True,
    }


def _nonneg_int(value: Any, limit: int) -> int | None:
    return value if type(value) is int and 0 <= value <= limit else None


def _clock(value: Any) -> datetime | None:
    if (not isinstance(value, datetime) or value.tzinfo is None
            or value.utcoffset() is None):
        return None
    return value.astimezone(timezone.utc)


def _minute_label(second: int) -> str | None:
    if second < 0 or second >= 86400 or second % 60 != 0:
        return None
    return f"{second // 3600:02d}:{(second % 3600) // 60:02d}"


def _current_session_aggregates(csv_bytes: bytes) -> dict[str, Any] | None:
    # Parent parser has already validated CSV identity, all 392 keys,
    # indices, rows, and timestamp. No private/price fields are present.
    try:
        rows = list(csv.DictReader(
            StringIO(csv_bytes.decode("utf-8-sig"), newline=""),
            delimiter=";"))
    except (UnicodeError, ValueError, csv.Error):
        return None
    group: dict[tuple[str, int, str], list[dict[str, str]]] = {}
    sentinel4307 = 0
    for row in rows:
        key = (row["canonical_symbol"], int(row["server_weekday"]),
               row["session_kind"])
        group.setdefault(key, []).append(row)
        if row["status"] in ("NO_SESSION_RETURNED", "END_OF_RETURNED_SESSIONS"):
            if row["mt5_last_error_code"] != "4307":
                return None
            sentinel4307 += 1
    if len(group) != len(FX_28) * 7 * 2:
        return None

    monday: dict[str, list[str]] = {}
    friday: dict[str, list[str]] = {}
    discrepancies = 0
    for sym in FX_28:
        for weekday in range(7):
            quote = [r for r in group[(sym, weekday, "QUOTE")]
                     if r["status"] == "SESSION_RETURNED"]
            trade = [r for r in group[(sym, weekday, "TRADE")]
                     if r["status"] == "SESSION_RETURNED"]
            quote_spans = [(r["from_server_midnight_seconds"],
                            r["to_server_midnight_seconds"]) for r in quote]
            trade_spans = [(r["from_server_midnight_seconds"],
                            r["to_server_midnight_seconds"]) for r in trade]
            if quote_spans != trade_spans:
                discrepancies += 1
            # For the two weekdays summarized, require exactly one
            # quote + one trade interval, and do not hide multi-session
            # schedules behind a single inferred open or close.
            if weekday in (1, 5):
                if len(quote) != 1 or len(trade) != 1:
                    return None
                start = _minute_label(int(quote[0]["from_server_midnight_seconds"]))
                end = _minute_label(int(quote[0]["to_server_midnight_seconds"]))
                if start is None or end is None:
                    return None
                if weekday == 1:
                    monday.setdefault(start, []).append(sym)
                else:
                    friday.setdefault(end, []).append(sym)
    return {
        "monday": dict(sorted(monday.items())),
        "friday": dict(sorted(friday.items())),
        "quote_trade_disagreements": discrepancies,
        "terminators_4307": sentinel4307,
    }


def reconcile_fx28_current_sessions_and_past_w1_lab(
    *, native_csv_bytes: Any, historic_w1_reports: Any, evaluated_at_utc: Any,
) -> dict[str, Any]:
    result = _blocked("INVALID_OR_MISSING_NATIVE_RECEIPT_OR_WEEKLY_REPORTS")
    asof = _clock(evaluated_at_utc)
    if (asof is None or type(native_csv_bytes) is not bytes
            or type(historic_w1_reports) not in (tuple, list)
            or len(historic_w1_reports) != 2):
        return result

    receipt = inspect_fx28_native_session_csv_lab(
        native_csv_bytes, evaluated_at_utc=asof)
    if (receipt.get("schema") != RECEIPT_SCHEMA
            or receipt.get("state") != RECEIPT_SUCCESS
            or receipt.get("verified_metadata_keys") != 392
            or receipt.get("historical_session_schedule_authenticated") is not False
            or receipt.get("eligible_utc_m15_calendar_exemptions") != []
            or receipt.get("trade_authorized") is not False):
        result["reason"] = "NATIVE_SESSION_RECEIPT_NOT_STRUCTURALLY_ACCEPTED"
        return result

    native = _current_session_aggregates(native_csv_bytes)
    if native is None:
        result["reason"] = "NATIVE_SESSION_END_MARKER_OR_WEEKDAY_SHAPE_INVALID"
        return result
    if native["quote_trade_disagreements"]:
        result["reason"] = "QUOTE_TRADE_WEEKDAY_SCHEDULES_DIFFER_CURRENTLY"
        return result
    if (sum(map(len, native["monday"].values())) != 28
            or sum(map(len, native["friday"].values())) != 28):
        result["reason"] = "CURRENT_WEEKDAY_MONDAY_OR_FRIDAY_ROSTER_INCOMPLETE"
        return result

    historical_summaries: dict[str, dict[str, Any]] = {}
    expected_days = set(W1_WINDOWS_UTC)
    if {r.get("reference_sunday_ny") for r in historic_w1_reports
            if type(r) is dict} != expected_days:
        result["reason"] = "HISTORICAL_WEEKS_NOT_EXACTLY_EXPECTED_TWO"
        return result
    for report in historic_w1_reports:
        if type(report) is not dict:
            result["reason"] = "HISTORIC_WEEK_REPORT_NOT_A_DOCUMENT"
            return result
        day = report["reference_sunday_ny"]
        expected_lo, expected_hi = W1_WINDOWS_UTC[day]
        if (report.get("schema") != WEEK_SCHEMA
                or report.get("state") != WEEK_SUCCESS
                or report.get("window_start_utc") != expected_lo
                or report.get("window_end_utc_exclusive") != expected_hi
                or report.get("pair_count_attempted") != 28
                or report.get("complete_480_pairs") != 0
                or report.get("all_pairs_timeseries_structurally_valid") is not True
                or report.get("all_expected_weekly_m15_slots_present") is not False
                or report.get("reference_market_schedule_independently_authenticated") is not False
                or report.get("source_feed_independently_verified") is not False
                or report.get("no_candles_interpolated_or_forward_filled") is not True
                or report.get("trade_authorized") is not False
                or report.get("operational_bias") != "AGUARDAR"):
            result["reason"] = "HISTORICAL_W1_REPORT_OR_SAFETY_CLAIM_INVALID"
            return result
        shared_n = _nonneg_int(report.get("shared_missing_utc_slot_count"), W1_M15_COUNT)
        shared_pair = _nonneg_int(
            report.get("shared_missing_pair_slots_total"), 28*W1_M15_COUNT)
        residual_n = _nonneg_int(
            report.get("pair_specific_missing_slots_total"), 28*W1_M15_COUNT)
        total_n = _nonneg_int(report.get("missing_slots_total"), 28*W1_M15_COUNT)
        residual = report.get("pair_specific_missing_by_symbol")
        if (any(n is None for n in (shared_n,shared_pair,residual_n,total_n))
                or type(residual) is not dict or set(residual) != set(FX_28)
                or any(_nonneg_int(n, W1_M15_COUNT) is None
                       for n in residual.values())
                or shared_n == 0 or shared_n * 28 != shared_pair
                or sum(residual.values()) != residual_n
                or shared_pair + residual_n != total_n):
            result["reason"] = "HISTORICAL_W1_GAP_ARITHMETIC_OR_PAIR_ROSTER_INVALID"
            return result
        historical_summaries[day] = {
            "timeframe": "W1",
            "fixed_utc_window": [expected_lo, expected_hi],
            "theoretical_15min_slots": W1_M15_COUNT*28,
            "shared_utc_times_without_candles": shared_n,
            "shared_pair_slots_without_candles": shared_pair,
            "pair_specific_missing_slots": residual_n,
            "total_missing_slots": total_n,
            "pair_specific_GBPNZD": residual["GBPNZD"],
            "pair_specific_CHFJPY": residual["CHFJPY"],
            "calendar_closure_or_feed_failure_inferred": False,
        }

    result.update({
        "state": "LAB_FX28_NATIVE_CURRENT_VS_PAST_W1_RECONCILED_NO_GO",
        "reason": "CONTEMPORARY_SERVER_HOURS_CANNOT_ATTEST_HISTORIC_UTC_SESSION_OR_EXEMPT_GAPS",
        "current_session_snapshot_utc_claim": receipt["session_claim_timestamp_utc"],
        "native_schedule_claim_count": receipt["verified_metadata_keys"],
        "native_quote_trade_weekday_disagreements": 0,
        "native_quote_trade_session_matches_currently": True,
        "native_session_terminator_4307_count": native["terminators_4307"],
        "current_monday_quote_start_by_server_minute": native["monday"],
        "current_friday_quote_end_by_server_minute": native["friday"],
        "historical_weeks_reconciled": 2,
        "historical_weekly_gap_context": historical_summaries,
    })
    return result


__all__ = ("SCHEMA", "reconcile_fx28_current_sessions_and_past_w1_lab")
