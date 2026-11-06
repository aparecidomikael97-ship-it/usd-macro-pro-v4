"""Fail-closed LAB gate for self-exported MT5-shaped Forex M15 OHLC bars.

Only reads offline JSON bytes normalized from MetaTrader5.copy_rates_range.
The caller's broker, clock and price series are UNAUTHENTICATED. Even a
structurally complete event window cannot be called executable, independent,
point-in-time witnessed or suitable for a historical accuracy score.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
import re
from typing import Any

SCHEMA = "ATLASQUANT_TRADER_FX_M15_OFFLINE_PRICE_WINDOW_LAB_V1"
EXPORT_SCHEMA = "ATLASQUANT_MT5_M15_OFFLINE_EXPORT_V1"
SOURCE_ID = "MT5_COPY_RATES_RANGE_OFFLINE_EXPORT"
SOURCE_DOC = "https://www.mql5.com/en/docs/python_metatrader5/mt5copyratesrange_py"
CURRENCIES = frozenset(("EUR", "USD", "GBP", "JPY", "CHF", "AUD", "NZD", "CAD"))
FIELDS = frozenset(("time", "open", "high", "low", "close", "tick_volume",
                    "spread", "real_volume"))
MAX_BYTES = 900_000
MAX_BARS = 5_000
BAR_SECONDS = 900
WINDOW_BARS_PER_SIDE = 4


def _deny(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_BLOCKED", "reason": reason,
        "source_id": SOURCE_ID, "source_doc": SOURCE_DOC,
        "symbol": None, "timeframe": "M15", "bar_seconds": BAR_SECONDS,
        "raw_sha256": None, "raw_bytes": None, "captured_at_utc": None,
        "event_at_utc": None, "first_bar_open_utc": None,
        "last_bar_open_utc": None, "total_bars": None,
        "pre_event_closed_bars": None, "post_event_closed_bars": None,
        "excluded_event_straddling_bar": None,
        "price_side_broker_attested": False,
        "broker_identity_independently_verified": False,
        "timestamp_origin_independently_verified": False,
        "independent_execution_prices_verified": False,
        "historical_point_in_time_eligible": False,
        "historical_backtest_accuracy_verified": False,
        "m15_trade_ready": False, "fx_bias": None,
        "operational_bias": "AGUARDAR", "trade_authorized": False,
        "can_feed_live_radar": False, "publishable": False,
        "worker_enabled": False, "scheduler_enabled": False,
        "new_cost_brl": 0,
    }


def _utc(value: Any) -> datetime | None:
    if (not isinstance(value, datetime) or value.tzinfo is None
            or value.utcoffset() is None):
        return None
    return value.astimezone(timezone.utc)


def _unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _price(value: Any) -> Decimal:
    # Decimal strings, rather than JSON floats, prevent an unnoticed float
    # conversion in a reproducible OHLC evidence document.
    if (not isinstance(value, str)
            or not re.fullmatch(r"(?:0|[1-9]\d{0,2})(?:\.\d{1,8})?", value)):
        raise ValueError("invalid decimal price")
    try:
        result = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError("non-finite price") from exc
    if not Decimal("0.0001") <= result <= Decimal("1000"):
        raise ValueError("out of range FX price")
    return result


def _int(value: Any, *, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise ValueError("invalid integer")
    return value


def _iso_epoch(epoch: int) -> str:
    return datetime.fromtimestamp(epoch, timezone.utc).isoformat()


def inspect_fx_m15_event_window_lab(
    raw: Any, *, expected_symbol: str, captured_at_utc: datetime,
    as_of_utc: datetime, event_at_utc: datetime,
) -> dict[str, Any]:
    """Require 4 completed M15 bars either side, excluding event-straddler.

    Returns no price, direction, hit rate, spread, slippage or signal. A buyer
    must separately prove the data provider's identity, vintage, quote side,
    calendar timestamp and licensing before any statistical backtest.
    """
    out = _deny("INVALID_INPUT_OR_CLOCK")
    capture, as_of, event = (_utc(captured_at_utc), _utc(as_of_utc),
                             _utc(event_at_utc))
    if (capture is None or as_of is None or event is None
            or capture > as_of or event > as_of
            or not isinstance(raw, bytes) or not 100 <= len(raw) <= MAX_BYTES
            or not isinstance(expected_symbol, str)
            or not re.fullmatch(r"[A-Z]{6}", expected_symbol)
            or expected_symbol[:3] not in CURRENCIES
            or expected_symbol[3:] not in CURRENCIES
            or expected_symbol[:3] == expected_symbol[3:]):
        return out
    try:
        obj = json.loads(raw.decode("utf-8", errors="strict"),
                         object_pairs_hook=_unique_pairs,
                         parse_constant=lambda _: (_ for _ in ()).throw(ValueError("constant")))
        if (not isinstance(obj, dict)
                or set(obj) != {"schema", "source_id", "symbol", "timeframe",
                                "timestamp_unit", "price_basis", "bars"}
                or obj.get("schema") != EXPORT_SCHEMA
                or obj.get("source_id") != SOURCE_ID
                or obj.get("symbol") != expected_symbol
                or obj.get("timeframe") != "M15"
                or obj.get("timestamp_unit") != "unix_seconds_utc"
                or obj.get("price_basis") != "BROKER_REPORTED_UNVERIFIED"):
            out["reason"] = "UNSUPPORTED_EXPORT_CONTRACT"
            return out
        bars = obj["bars"]
        if not isinstance(bars, list) or not 8 <= len(bars) <= MAX_BARS:
            out["reason"] = "INSUFFICIENT_OR_EXCESSIVE_BARS"
            return out
        observed: list[int] = []
        previous: int | None = None
        for bar in bars:
            if not isinstance(bar, dict) or set(bar) != FIELDS:
                raise ValueError("row schema drift")
            ts = _int(bar["time"], minimum=946684800, maximum=4102444800)
            if ts % BAR_SECONDS != 0 or previous is not None and ts <= previous:
                raise ValueError("non-UTC, duplicate or unsorted bar")
            previous = ts
            if ts + BAR_SECONDS > int(capture.timestamp()):
                raise ValueError("open or future bar at capture")
            o, h, l, c = (_price(bar[k]) for k in ("open", "high", "low", "close"))
            if not l <= min(o, c) <= max(o, c) <= h:
                raise ValueError("invalid OHLC range")
            _int(bar["tick_volume"], minimum=1, maximum=10**9)
            _int(bar["spread"], minimum=0, maximum=10**6)
            _int(bar["real_volume"], minimum=0, maximum=10**12)
            observed.append(ts)

        event_ts = event.timestamp()
        before = [ts for ts in observed if ts + BAR_SECONDS <= event_ts]
        after = [ts for ts in observed if ts >= event_ts]
        if len(before) < WINDOW_BARS_PER_SIDE or len(after) < WINDOW_BARS_PER_SIDE:
            out["reason"] = "M15_EVENT_WINDOW_INSUFFICIENT"
            return out
        pre = before[-WINDOW_BARS_PER_SIDE:]
        post = after[:WINDOW_BARS_PER_SIDE]
        straddlers = [ts for ts in observed if ts < event_ts < ts + BAR_SECONDS]
        if len(straddlers) > 1:
            raise ValueError("multiple crossing bars")
        combined = pre + straddlers + post
        if (len(combined) != 8 + (1 if event_ts % BAR_SECONDS else 0)
                or any(b - a != BAR_SECONDS for a, b in zip(combined, combined[1:]))
                or pre[-1] + BAR_SECONDS > event_ts
                or post[0] < event_ts
                or (event_ts % BAR_SECONDS == 0 and (pre[-1] + BAR_SECONDS != event_ts
                                                    or post[0] != event_ts))):
            out["reason"] = "M15_WINDOW_GAPS_OR_AMBIGUOUS_EVENT_BAR"
            return out
        out.update({
            "state": "LAB_M15_EVENT_WINDOW_STRUCTURALLY_COMPLETE_UNVERIFIED",
            "reason": "BROKER_ORIGIN_SPREAD_EXECUTION_AND_HISTORICAL_VINTAGE_NOT_VERIFIED",
            "symbol": expected_symbol, "raw_sha256": sha256(raw).hexdigest(),
            "raw_bytes": len(raw), "captured_at_utc": capture.isoformat(),
            "event_at_utc": event.isoformat(),
            "first_bar_open_utc": _iso_epoch(observed[0]),
            "last_bar_open_utc": _iso_epoch(observed[-1]),
            "total_bars": len(observed),
            "pre_event_closed_bars": len(pre),
            "post_event_closed_bars": len(post),
            "excluded_event_straddling_bar": bool(straddlers),
        })
        return out
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError, TypeError,
            OverflowError, OSError):
        out["reason"] = "PRICE_EXPORT_SCHEMA_OR_VALUES_REJECTED"
        return out


__all__ = ["SCHEMA", "EXPORT_SCHEMA", "SOURCE_ID",
           "inspect_fx_m15_event_window_lab"]
