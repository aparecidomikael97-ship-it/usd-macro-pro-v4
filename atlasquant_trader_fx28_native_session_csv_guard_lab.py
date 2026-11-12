"""Validate a manual read-only MT5 native FX28 quote/trade session CSV.

No scraping accounts, no MT5 connection, no inferred UTC broker offset,
no historical calendar exemption, no file writes, no signals, no orders.
A native MQL5 session schedule reports the broker's *current* weekday
schedule metadata, not authenticated 2026-10-25/11-01 historical sessions.
The snapshot may have missing hidden-symbol metadata. A missing session
does NOT mean the market is certainly closed.
"""
from __future__ import annotations

import csv
from datetime import datetime, timedelta, timezone
from io import StringIO
from typing import Any

from atlasquant_instrument_registry import FX_28

SCHEMA = "ATLASQUANT_FX28_MT5_SESSION_METADATA_LAB_V1"
RESULT_SCHEMA = "ATLASQUANT_FX28_NATIVE_MT5_SESSION_RECEIPT_AUDIT_LAB_V1"
CSV_COLUMNS = (
    "schema", "observed_utc_os_clock_claim", "canonical_symbol",
    "server_weekday", "session_kind", "session_index", "status",
    "from_server_midnight_seconds", "to_server_midnight_seconds",
    "market_watch_visible", "mt5_last_error_code",
)
MAX_BYTES = 500_000
MAX_ROWS = 4_000
PAIR_DAYS_KINDS = 28 * 7 * 2
KINDS = ("QUOTE", "TRADE")
TERMINATORS = frozenset(("NO_SESSION_RETURNED", "END_OF_RETURNED_SESSIONS"))
MAX_SESSION_ROWS = 8


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": RESULT_SCHEMA, "state": "LAB_FX28_NATIVE_SESSION_RECEIPT_BLOCKED",
        "reason": reason, "expected_symbols": 28,
        "expected_pair_weekday_kinds": PAIR_DAYS_KINDS,
        "verified_metadata_keys": 0, "returned_native_session_rows": 0,
        "no_session_returned_count": 0,
        "symbols_with_no_session_returned": [],
        "hidden_symbols_in_snapshot": [],
        "local_native_session_inventory_structurally_complete": False,
        "session_claim_timestamp_utc": None,
        "observed_mql5_server_offset_not_independently_verified": True,
        "claim_only_not_historical_schedule_proof": True,
        "historical_session_schedule_authenticated": False,
        "historical_quote_session_authenticated": False,
        "broker_timezone_for_2026_10_and_11_verified": False,
        "provider_session_calendar_verified": False,
        "eligible_utc_m15_calendar_exemptions": [],
        "session_based_backfill_permitted": False,
        "live_trading_session_status_verified": False,
        "validated_accuracy": None, "calibrated_probability": None,
        "operational_bias": "AGUARDAR",
        "publishable": False, "trade_authorized": False,
        "worker_enabled": False, "scheduler_enabled": False,
        "files_written": 0, "broker_connections": 0,
        "orders_or_positions_accessed": False,
        "account_info_accessed": False, "research_only": True,
    }


def _bounded_integer(value: Any, *, maximum: int) -> int | None:
    if type(value) is not str or not value.isdecimal() or len(value) > 10:
        return None
    parsed = int(value)
    return parsed if 0 <= parsed <= maximum else None


def _snapshot_clock(value: Any) -> datetime | None:
    if type(value) is not str or len(value) != 20:
        return None
    try:
        v = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        return v if v.year == 2026 else None
    except ValueError:
        return None


def inspect_fx28_native_session_csv_lab(
    csv_raw: Any, *, evaluated_at_utc: Any,
) -> dict[str, Any]:
    """Validate schema/repetition/order only, never assert session legitimacy."""
    r = _blocked("INVALID_CSV_OR_AS_OF")
    if (type(csv_raw) is not bytes or not 1 <= len(csv_raw) <= MAX_BYTES
            or not isinstance(evaluated_at_utc, datetime)
            or evaluated_at_utc.tzinfo is None
            or evaluated_at_utc.utcoffset() is None):
        return r
    try:
        asof = evaluated_at_utc.astimezone(timezone.utc)
        raw_text = csv_raw.decode("utf-8-sig")
        reader = csv.DictReader(StringIO(raw_text, newline=""), delimiter=";")
        if reader.fieldnames != list(CSV_COLUMNS):
            r["reason"] = "NATIVE_CSV_HEADER_MISMATCH"
            return r
        by_key: dict[tuple[str, int, str], list[dict[str, str]]] = {}
        symbol_visibility: dict[str, str] = {}
        time_seen: datetime | None = None
        total_rows = 0
        for row in reader:
            total_rows += 1
            if total_rows > MAX_ROWS or None in row or set(row) != set(CSV_COLUMNS):
                r["reason"] = "NATIVE_CSV_ROW_COUNT_OR_WIDTH_INVALID"
                return r
            if any(type(v) is not str for v in row.values()):
                r["reason"] = "NATIVE_CSV_FIELD_NOT_STRING"
                return r
            if (row["schema"] != SCHEMA
                    or row["canonical_symbol"] not in FX_28
                    or row["session_kind"] not in KINDS
                    or row["market_watch_visible"] not in ("TRUE", "FALSE")):
                r["reason"] = "NATIVE_CSV_IDENTITY_OR_KIND_INVALID"
                return r
            weekday = _bounded_integer(row["server_weekday"], maximum=6)
            index = _bounded_integer(row["session_index"], maximum=MAX_SESSION_ROWS)
            err = _bounded_integer(row["mt5_last_error_code"], maximum=10_000_000)
            stamp = _snapshot_clock(row["observed_utc_os_clock_claim"])
            if (weekday is None or index is None or err is None or stamp is None
                    or stamp > asof or stamp < asof-timedelta(days=7)):
                r["reason"] = "NATIVE_CSV_CLOCK_INDEX_OR_ERROR_INVALID"
                return r
            if time_seen is None:
                time_seen = stamp
            elif time_seen != stamp:
                r["reason"] = "INCONSISTENT_SNAPSHOT_CLOCK"
                return r
            symbol = row["canonical_symbol"]
            if symbol in symbol_visibility:
                if symbol_visibility[symbol] != row["market_watch_visible"]:
                    r["reason"] = "MARKET_WATCH_VISIBILITY_CLAIM_MISMATCH"
                    return r
            else:
                symbol_visibility[symbol] = row["market_watch_visible"]
            key = (symbol, weekday, row["session_kind"])
            by_key.setdefault(key, []).append(row)

        if not total_rows or set(by_key) != {
            (symbol, weekday, kind)
            for symbol in FX_28 for weekday in range(7) for kind in KINDS
        }:
            r["reason"] = "EXPECTED_ALL_28_X_7_X_2_SESSION_KEYS"
            return r

        no_sessions = 0
        native_session_rows = 0
        no_session_symbols: set[str] = set()
        for (symbol, weekday, kind), rows in by_key.items():
            if not 1 <= len(rows) <= MAX_SESSION_ROWS + 1:
                r["reason"] = "SESSION_ROW_COUNT_EXCEEDED_OR_EMPTY"
                return r
            last = rows[-1]
            if last["status"] not in TERMINATORS:
                r["reason"] = "MISSING_DAY_KIND_END_MARKER_OR_TRUNCATED"
                return r
            sessions = rows[:-1]
            if len(sessions) > MAX_SESSION_ROWS:
                r["reason"] = "TOO_MANY_SESSIONS"
                return r
            if (last["status"] == "NO_SESSION_RETURNED") != (len(sessions) == 0):
                r["reason"] = "NO_SESSION_STATUS_INCONSISTENT_WITH_SESSIONS"
                return r
            expected_indices = [str(i) for i in range(len(sessions)+1)]
            if [row["session_index"] for row in rows] != expected_indices:
                r["reason"] = "NONCONTIGUOUS_OR_DUPLICATE_SESSION_INDEX"
                return r
            for row in sessions:
                if row["status"] != "SESSION_RETURNED":
                    r["reason"] = "SESSION_STATUS_OR_ORDER_INVALID"
                    return r
                start = _bounded_integer(
                    row["from_server_midnight_seconds"], maximum=172_800)
                end = _bounded_integer(
                    row["to_server_midnight_seconds"], maximum=172_800)
                if (start is None or end is None
                        or start == end or row["mt5_last_error_code"] != "0"):
                    r["reason"] = "NATIVE_SESSION_BOUNDS_OR_ERROR_INVALID"
                    return r
                native_session_rows += 1
            if (last["from_server_midnight_seconds"] != ""
                    or last["to_server_midnight_seconds"] != ""):
                r["reason"] = "SESSION_TERMINATOR_HAS_PRICE_OR_TIMES"
                return r
            if not sessions:
                no_sessions += 1
                no_session_symbols.add(symbol)

        r.update({
            "state": "LAB_FX28_NATIVE_MT5_SESSION_METADATA_CLAIM_ONLY_NO_GO",
            "reason": "CURRENT_TERMINAL_SCHEDULE_NOT_HISTORICAL_VINTAGE_OR_BROKER_ATTESTATION",
            "verified_metadata_keys": PAIR_DAYS_KINDS,
            "returned_native_session_rows": native_session_rows,
            "no_session_returned_count": no_sessions,
            "symbols_with_no_session_returned": [
                sym for sym in FX_28 if sym in no_session_symbols],
            "hidden_symbols_in_snapshot": [
                sym for sym in FX_28 if symbol_visibility[sym] == "FALSE"],
            "local_native_session_inventory_structurally_complete": True,
            "session_claim_timestamp_utc": time_seen.isoformat() if time_seen else None,
        })
        return r
    except (UnicodeError, ValueError, TypeError, OverflowError, csv.Error):
        r["reason"] = "NATIVE_CSV_DECODING_OR_PARSE_EXCEPTION"
        return r


__all__ = ("SCHEMA", "CSV_COLUMNS", "inspect_fx28_native_session_csv_lab")
