"""A284 LAB: strict offline MT5 native Bars TSV -> A276 canonical CSV bridge.

Native MetaTrader 5 bar exports commonly have nine tab-separated columns
with date and time as separate broker/server wall-clock labels. The server
UTC offset is NOT known to this module and MUST be declared. One constant
offset cannot establish historic DST transitions. All metadata and quoted
market data remain untrusted; no terminal, broker, network, Worker or orders.
"""
from __future__ import annotations

import csv
from datetime import datetime, timedelta, timezone
import hashlib
import io
import re
from typing import Any

from atlasquant_aion_historical_csv import (
    MAX_CANDLES, MAX_CSV_BYTES, import_historical_csv,
)
from atlasquant_aion_csv_readiness_lab import (
    preflight_historical_csv, compare_if_preflight_ready_csv,
)

SCHEMA = "ATLASQUANT_AION_MT5_BARS_TSV_OFFLINE_BRIDGE_LAB_V1"
VERSION = "A284_MT5_BARS_FIXED_DECLARED_OFFSET_V1"
MAX_MT5_BYTES = 1_600_000
EXPECTED_HEADER = (
    "<DATE>", "<TIME>", "<OPEN>", "<HIGH>", "<LOW>", "<CLOSE>",
    "<TICKVOL>", "<VOL>", "<SPREAD>",
)
DAY_PATTERN = re.compile(r"[0-9]{4}\.[0-9]{2}\.[0-9]{2}\Z")
CLOCK_PATTERN = re.compile(r"[0-9]{2}:[0-9]{2}:[0-9]{2}\Z")
METADATA_PATTERN = re.compile(r"[0-9]{1,16}\Z")
SPEC = {
    "version": VERSION,
    "input_native_header": list(EXPECTED_HEADER),
    "delimiter": "TAB_EXACT",
    "source_bar_timestamp": "OPEN_TIME_WALL_CLOCK_AS_DECLARED",
    "explicit_fixed_server_utc_offset_minutes_required": True,
    "source_timezone_independently_verified": False,
    "historic_dst_transitions_verified": False,
    "tick_volume_used_as_real_volume": False,
    "spread_used_as_verified_transaction_cost": False,
    "output": "A276_CLOSED_UTC_OHLC_CSV",
    "no_automatic_data_download": True,
}


def _base() -> dict:
    return {
        "schema": SCHEMA, "version": VERSION,
        "valid": False, "error": "INVALID_INPUT",
        "status": "INVALID_MT5_OFFLINE_EXPORT",
        "canonical_closed_csv": None,
        "canonical_timestamp_basis": None,
        "source_mt5_sha256": None, "canonical_csv_sha256": None,
        "normalized_candles_sha256": None,
        "candle_count": 0, "preflight": None, "comparison": None,
        "historical_only": True, "research_only": True,
        "source_export_is_externally_attested": False,
        "broker_utc_offset_is_verified": False,
        "dst_transitions_verified": False,
        "volume_represents_real_traded_volume": False,
        "spread_represents_verified_execution_cost": False,
        "broker_symbol_to_research_id_verified": False,
        "futures_contract_expiry_verified": False,
        "no_data_download": True, "no_new_data_calls": True,
        "no_orders": True, "no_alerts": True,
        "authorizes_send": False, "p0_homologated": 0,
    }


def _metadata_nonnegative(value: str) -> bool:
    return bool(METADATA_PATTERN.fullmatch(value))


def normalize_mt5_bars_tsv(
    mt5_tsv: Any, *, symbol: Any, timeframe: Any, now: Any,
    server_utc_offset_minutes: Any,
) -> dict:
    """Normalize a bounded native 9-column MT5 Bars export; fail closed.

    The offset is a human-declared fixed UTC offset of the source wall clock,
    not a timezone guessed from the user's device or a broker attestation.
    E.g. server UTC+2 -> +120 (convert server time to UTC by subtracting 2h).
    This does not support a DST-changing time span safely by itself.
    """
    result = _base()
    offset = server_utc_offset_minutes
    if (type(offset) is not int or abs(offset) > 14 * 60
            or offset % 15 != 0):
        result["error"] = "EXPLICIT_SERVER_UTC_OFFSET_REQUIRED"
        return result
    if type(mt5_tsv) is not str or "\x00" in mt5_tsv:
        result["error"] = "NON_TEXT_OR_NUL_EXPORT"
        return result
    try:
        raw = mt5_tsv.encode("utf-8", "strict")
    except UnicodeEncodeError:
        result["error"] = "NON_UTF8_EXPORT"
        return result
    if not raw or len(raw) > MAX_MT5_BYTES:
        result["error"] = "MT5_SOURCE_SIZE_LIMIT"
        return result
    try:
        reader = csv.reader(
            io.StringIO(mt5_tsv.lstrip("\ufeff"), newline=""),
            delimiter="\t", strict=True,
        )
        header = next(reader, None)
        if tuple(header or ()) != EXPECTED_HEADER:
            result["error"] = "NOT_NATIVE_MT5_NINE_COLUMN_TSV"
            return result
        interpreted = []
        zone = timezone(timedelta(minutes=offset))
        for columns in reader:
            if len(interpreted) >= MAX_CANDLES:
                result["error"] = "MT5_CANDLE_COUNT_LIMIT"
                return result
            if len(columns) != len(EXPECTED_HEADER):
                result["error"] = "INVALID_MT5_ROW_WIDTH"
                return result
            day, hour, op, hi, lo, close, ticks, vol, spread = columns
            if not DAY_PATTERN.fullmatch(day) or not CLOCK_PATTERN.fullmatch(hour):
                result["error"] = "INVALID_MT5_WALL_CLOCK_FORMAT"
                return result
            if not all(_metadata_nonnegative(x)
                       for x in (ticks, vol, spread)):
                result["error"] = "INVALID_MT5_QUOTE_METADATA"
                return result
            try:
                wall = datetime.strptime(
                    day + " " + hour, "%Y.%m.%d %H:%M:%S",
                ).replace(tzinfo=zone)
                at_utc = wall.astimezone(timezone.utc).isoformat()
            except (ValueError, OverflowError):
                result["error"] = "INVALID_MT5_WALL_CLOCK_DATE"
                return result
            interpreted.append((at_utc, op, hi, lo, close))
    except (csv.Error, UnicodeError):
        result["error"] = "MALFORMED_MT5_TSV"
        return result
    if not interpreted:
        result["error"] = "MT5_EXPORT_HAS_NO_CANDLES"
        return result

    # The exported native label is OPEN time. A276 must compute the
    # CLOSED timestamp and enforce order, geometry, symbol and now.
    opening_csv = "closed_at,open,high,low,close\n" + "".join(
        ",".join(row) + "\n" for row in interpreted
    )
    imported = import_historical_csv(
        opening_csv, symbol=symbol, timeframe=timeframe,
        timestamp_basis="OPEN", now=now,
    )
    if not imported["valid"]:
        result["error"] = "INVALID_A276_OPEN_BARS:" + imported["error"]
        return result
    closed_csv = "closed_at,open,high,low,close\n" + "".join(
        f'{row["datetime"]},{row["open"]},{row["high"]},'
        f'{row["low"]},{row["close"]}\n'
        for row in imported["candles"]
    )
    # Round-trip: the canonical output must pass the same A276 contract,
    # without a second OPEN shift (avoid a one-candle time error).
    checked = import_historical_csv(
        closed_csv, symbol=symbol, timeframe=timeframe,
        timestamp_basis="CLOSE", now=now,
    )
    if (not checked["valid"]
            or imported["normalized_candles_sha256"] !=
                checked["normalized_candles_sha256"]):
        result["error"] = "CLOSED_CSV_CANONICAL_ROUNDTRIP_FAILED"
        return result
    result.update({
        "valid": True, "error": None,
        "status": "MT5_BARS_NORMALIZED_UNATTESTED_HISTORICAL_ONLY",
        "symbol": symbol, "timeframe": timeframe,
        "declared_server_utc_offset_minutes": offset,
        "fixed_offset_does_not_handle_dst_transition": True,
        "canonical_timestamp_basis": "CLOSE",
        "canonical_closed_csv": closed_csv,
        "source_mt5_sha256": hashlib.sha256(raw).hexdigest(),
        "canonical_csv_sha256": checked["raw_csv_sha256"],
        "normalized_candles_sha256": checked["normalized_candles_sha256"],
        "first_closed_at": checked["first_closed_at"],
        "last_closed_at": checked["last_closed_at"],
        "candle_count": checked["candle_count"],
        "mt5_tick_volume_and_real_volume_not_preserved": True,
        "source_spread_not_used_to_set_backtest_friction": True,
    })
    return result


def preflight_mt5_bars_tsv(
    mt5_tsv: Any, *, symbol: Any, timeframe: Any, now: Any,
    server_utc_offset_minutes: Any, validation_start: Any,
) -> dict:
    """Normalize first; then A283 checks historical split, still no attestation."""
    result = _base()
    normalized = normalize_mt5_bars_tsv(
        mt5_tsv, symbol=symbol, timeframe=timeframe,
        now=now, server_utc_offset_minutes=server_utc_offset_minutes,
    )
    if not normalized["valid"]:
        result["error"] = normalized["error"]
        return result
    preflight = preflight_historical_csv(
        normalized["canonical_closed_csv"], symbol=symbol,
        timeframe=timeframe, timestamp_basis="CLOSE", now=now,
        validation_start=validation_start,
    )
    if (not preflight["valid"]
            or preflight.get("raw_csv_sha256") !=
                normalized["canonical_csv_sha256"]
            or preflight.get("normalized_candles_sha256") !=
                normalized["normalized_candles_sha256"]):
        result["error"] = "A283_PREFLIGHT_OR_DIGEST_FAILURE:" + str(
            preflight["error"])
        return result
    result.update({
        **{k: normalized[k] for k in (
            "source_mt5_sha256", "canonical_csv_sha256",
            "normalized_candles_sha256", "candle_count",
        )},
        "valid": True, "error": None,
        "status": ("MT5_OFFLINE_PREFLIGHT_READY_UNATTESTED"
                   if preflight["ready_for_offline_research"]
                   else "MT5_OFFLINE_PREFLIGHT_INSUFFICIENT"),
        "preflight": preflight,
        "canonical_timestamp_basis": "CLOSE",
        "server_utc_offset_minutes_declared": server_utc_offset_minutes,
        "ready_for_offline_research": preflight["ready_for_offline_research"],
    })
    return result


def research_mt5_bars_tsv(
    mt5_tsv: Any, *, symbol: Any, timeframe: Any, now: Any,
    server_utc_offset_minutes: Any, validation_start: Any,
    cost_r: Any, slippage_r: Any,
    max_wait_bars: Any = 8, max_hold_bars: Any = 96,
) -> dict:
    """Offline A283 + A282 only if native MT5 CSV and data preflight pass."""
    result = _base()
    converted = normalize_mt5_bars_tsv(
        mt5_tsv, symbol=symbol, timeframe=timeframe, now=now,
        server_utc_offset_minutes=server_utc_offset_minutes,
    )
    if not converted["valid"]:
        result["error"] = converted["error"]
        return result
    evaluated = compare_if_preflight_ready_csv(
        converted["canonical_closed_csv"],
        symbol=symbol, timeframe=timeframe,
        timestamp_basis="CLOSE", now=now,
        validation_start=validation_start,
        cost_r=cost_r, slippage_r=slippage_r,
        max_wait_bars=max_wait_bars, max_hold_bars=max_hold_bars,
    )
    if (not evaluated["valid"] or not evaluated["ready_for_offline_research"]):
        result["error"] = "A283_OR_A282:" + str(evaluated["error"])
        return result
    checked = evaluated["preflights"][0]
    if (checked["raw_csv_sha256"] != converted["canonical_csv_sha256"]
            or checked["normalized_candles_sha256"] !=
                converted["normalized_candles_sha256"]
            or evaluated["comparison"]["authorizes_send"] is not False
            or evaluated["comparison"]["p0_homologated"] != 0):
        result["error"] = "MT5_A283_A282_DIGEST_OR_AUTHORITY_MISMATCH"
        return result
    result.update({
        "valid": True, "error": None,
        "status": "MT5_OFFLINE_A283_A282_RESEARCH_ONLY_UNATTESTED",
        "source_mt5_sha256": converted["source_mt5_sha256"],
        "canonical_csv_sha256": converted["canonical_csv_sha256"],
        "normalized_candles_sha256": converted["normalized_candles_sha256"],
        "server_utc_offset_minutes_declared": server_utc_offset_minutes,
        "candle_count": converted["candle_count"],
        "canonical_timestamp_basis": "CLOSE",
        "preflight": checked,
        "comparison": evaluated["comparison"],
    })
    return result


__all__ = [
    "SCHEMA", "SPEC", "VERSION", "EXPECTED_HEADER",
    "normalize_mt5_bars_tsv", "preflight_mt5_bars_tsv",
    "research_mt5_bars_tsv",
]
