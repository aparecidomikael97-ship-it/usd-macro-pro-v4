"""A276 LAB: bounded, offline, historical CSV OHLC intake.

Historical research only. Caller text is untrusted, even when it resembles
TradingView exports. No filesystem, provider, broker, order, live evidence,
strategy activation, or external trust claim. Fail closed without partial rows.
"""
from __future__ import annotations

import csv
from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
import math
from typing import Any

from atlasquant_instrument_registry import FX_28
from atlasquant_aion_trader_nonfx import SYMBOLS as NONFX_SYMBOLS, FUTURE_ROOTS
from atlasquant_aion_trader_timeframes import PERIOD_MINUTES

SCHEMA = "ATLASQUANT_AION_HISTORICAL_CSV_LAB_V1"
MAX_CSV_BYTES = 1_000_000
MAX_CANDLES = 10_000
MIN_CANDLES = 2
ALLOWED_SYMBOLS = frozenset(FX_28) | frozenset(NONFX_SYMBOLS)
TIME_COLUMNS = frozenset(("time", "datetime", "closed_at"))
OHLC = ("open", "high", "low", "close")


def _base(symbol: Any, timeframe: Any, timestamp_basis: Any) -> dict:
    return {
        "schema": SCHEMA,
        "symbol": symbol if type(symbol) is str and symbol in ALLOWED_SYMBOLS else None,
        "timeframe": timeframe if type(timeframe) is str and timeframe in PERIOD_MINUTES else None,
        "timestamp_basis": timestamp_basis if type(timestamp_basis) is str
                           and timestamp_basis in ("OPEN", "CLOSE") else None,
        "status": "INVALID_UNVERIFIED_HISTORICAL_CSV",
        "valid": False,
        "error": "INVALID_INPUT",
        "candles": [],
        "candle_count": 0,
        "first_closed_at": None,
        "last_closed_at": None,
        "raw_csv_sha256": None,
        "normalized_candles_sha256": None,
        "historical_only": True,
        "source_is_externally_attested": False,
        "provider_mapping_verified": False,
        "contract_expiry_verified": False,
        "backtest_results_generated": False,
        "no_live_gate_effect": True,
        "no_orders": True,
        "no_alerts": True,
        "no_new_data_calls": True,
        "authorizes_send": False,
        "p0_homologated": 0,
    }


def _decimal(raw: Any, *, allow_zero: bool = False) -> float | None:
    if type(raw) is not str or not raw or not raw.strip():
        return None
    try:
        n = float(raw)
    except (ValueError, OverflowError):
        return None
    if not math.isfinite(n) or (n < 0 if allow_zero else n <= 0):
        return None
    return n


def _date(raw: Any) -> datetime | None:
    if type(raw) is not str or not raw.strip():
        return None
    try:
        value = datetime.fromisoformat(raw.strip().replace("Z", "+00:00"))
        if value.tzinfo is None or value.utcoffset() is None:
            return None
        return value.astimezone(timezone.utc)
    except (ValueError, OverflowError):
        return None


def import_historical_csv(
    csv_text: Any, *, symbol: Any, timeframe: Any,
    timestamp_basis: Any, now: Any,
) -> dict:
    """Parse one asset/TF CSV, with explicit OPEN/CLOSE timestamp semantics.

    Headers: time|datetime|closed_at,open,high,low,close[,volume].
    Every time must be timezone-aware ISO 8601. Timestamp basis OPEN means
    adding exactly one chart period to obtain the closed-candle timestamp.
    Gaps are allowed (market closure); duplicates and reverse order are not.
    """
    result = _base(symbol, timeframe, timestamp_basis)
    if (result["symbol"] is None or result["timeframe"] is None
            or result["timestamp_basis"] is None):
        result["error"] = "UNKNOWN_SYMBOL_TIMEFRAME_OR_BASIS"
        return result
    if type(now) is not datetime or now.tzinfo is None or now.utcoffset() is None:
        result["error"] = "INVALID_NOW"
        return result
    now_utc = now.astimezone(timezone.utc)
    if type(csv_text) is not str or "\x00" in csv_text:
        result["error"] = "NON_TEXT_OR_NUL_INPUT"
        return result
    try:
        raw = csv_text.encode("utf-8", errors="strict")
    except UnicodeEncodeError:
        result["error"] = "NON_UTF8_TEXT"
        return result
    if len(raw) > MAX_CSV_BYTES or not raw:
        result["error"] = "CSV_SIZE_LIMIT"
        return result

    reader = csv.reader(io.StringIO(csv_text.lstrip("\ufeff"), newline=""), strict=True)
    records = []
    previous = None
    try:
        header = next(reader, None)
        if header is None or len(header) not in (5, 6):
            result["error"] = "INVALID_HEADER"
            return result
        time_fields = [field for field in header if field in TIME_COLUMNS]
        expected = set(OHLC) | set(time_fields)
        if len(header) == 6:
            expected.add("volume")
        if (len(time_fields) != 1 or len(set(header)) != len(header)
                or set(header) != expected):
            result["error"] = "INVALID_HEADER"
            return result
        time_key = time_fields[0]
        offset = timedelta(minutes=PERIOD_MINUTES[timeframe]) if timestamp_basis == "OPEN" else timedelta()
        for values in reader:
            if len(records) >= MAX_CANDLES:
                result["error"] = "CANDLE_COUNT_LIMIT"
                return result
            if len(values) != len(header):
                result["error"] = "INVALID_ROW_WIDTH"
                return result
            entry = dict(zip(header, values))
            moment = _date(entry[time_key])
            if moment is None:
                result["error"] = "INVALID_TIMESTAMP"
                return result
            try:
                closed_at = moment + offset
            except OverflowError:
                result["error"] = "INVALID_TIMESTAMP"
                return result
            if closed_at > now_utc:
                result["error"] = "FUTURE_CANDLE"
                return result
            if previous is not None and closed_at - previous < timedelta(minutes=PERIOD_MINUTES[timeframe]):
                result["error"] = "NON_MONOTONIC_OR_TOO_CLOSE"
                return result
            nums = {key: _decimal(entry[key]) for key in OHLC}
            if any(value is None for value in nums.values()):
                result["error"] = "INVALID_OHLC"
                return result
            if (nums["high"] < max(nums["open"], nums["low"], nums["close"])
                    or nums["low"] > min(nums["open"], nums["high"], nums["close"])):
                result["error"] = "INVALID_OHLC_GEOMETRY"
                return result
            candle = {"datetime": closed_at.isoformat(), **nums}
            if "volume" in entry:
                vol = _decimal(entry["volume"], allow_zero=True)
                if vol is None:
                    result["error"] = "INVALID_VOLUME"
                    return result
                candle["volume"] = vol
            records.append(candle)
            previous = closed_at
    except csv.Error:
        result["error"] = "MALFORMED_CSV"
        return result

    if len(records) < MIN_CANDLES:
        result["error"] = "INSUFFICIENT_CANDLES"
        return result
    normalized = json.dumps(records, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    result.update({
        "status": "HISTORICAL_ONLY_UNATTESTED",
        "valid": True,
        "error": None,
        "candles": records,
        "candle_count": len(records),
        "first_closed_at": records[0]["datetime"],
        "last_closed_at": records[-1]["datetime"],
        "raw_csv_sha256": hashlib.sha256(raw).hexdigest(),
        "normalized_candles_sha256": hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
        "asset_class": ("FOREX" if symbol in FX_28 else
                        "UNRESOLVED_FUTURE_ROOT" if symbol in FUTURE_ROOTS else
                        "INDEX_REFERENCE"),
    })
    return result


__all__ = ["SCHEMA", "ALLOWED_SYMBOLS", "MAX_CSV_BYTES", "MAX_CANDLES",
           "import_historical_csv"]
