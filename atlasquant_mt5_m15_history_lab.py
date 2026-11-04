"""Offline MT5-shaped M15 historical bars for backtest research only.

This module never imports MetaTrader5, attaches to a terminal, authenticates,
downloads data, places orders, or certifies executable bid/ask prices.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from math import isfinite
from typing import Any, Mapping

from atlasquant_fx_universe import OFFICIAL_PAIRS

SCHEMA = "ATLASQUANT_MT5_28_M15_HISTORY_IMPORT_LAB_V1"
OUTPUT_SCHEMA = "ATLASQUANT_MT5_28_M15_HISTORY_RESEARCH_LAB_V1"
INTERVAL = timedelta(minutes=15)
MAX_BARS = 2000
MAX_CLAIM_LENGTH = 150


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": OUTPUT_SCHEMA, "state": "BLOCKED", "reason": reason,
        "complete_pairs": 0, "bars_per_pair": 0,
        "last_close": {}, "last_tick_volume": {}, "last_spread_points": {},
        "total_history_gaps": 0,
        "provider_authenticated": False, "historical_bid_ask_verified": False,
        "spread_cost_verified": False, "display_authorized": False,
        "price_accuracy_verified": False, "publishable": False,
        "trade_authorized": False, "backtest_performance_verified": False,
        "market_feed_connected": False,
    }


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        v = float(value)
    except (ValueError, OverflowError, TypeError):
        return None
    return v if isfinite(v) and v > 0 else None


def _bar(value: Any) -> tuple[datetime, float, int, int] | None:
    if not isinstance(value, Mapping):
        return None
    seconds = value.get("time")
    if isinstance(seconds, bool) or not isinstance(seconds, int):
        return None
    try:
        stamp = datetime.fromtimestamp(seconds, timezone.utc)
    except (ValueError, OverflowError, OSError):
        return None
    if stamp.minute % 15 or stamp.second or stamp.microsecond:
        return None
    prices = {key: _number(value.get(key)) for key in ("open", "high", "low", "close")}
    if any(v is None for v in prices.values()):
        return None
    assert all(v is not None for v in prices.values())
    if prices["high"] < max(prices["open"], prices["close"], prices["low"]):
        return None
    if prices["low"] > min(prices["open"], prices["close"], prices["high"]):
        return None
    tick = value.get("tick_volume")
    spread = value.get("spread")
    if (type(tick) is not int or tick < 0 or
            type(spread) is not int or spread < 0):
        return None
    real = value.get("real_volume")
    if real is not None and (type(real) is not int or real < 0):
        return None
    return stamp, prices["close"], tick, spread


def analyze_mt5_m15_history(payload: Any, *, now: datetime | None = None) -> dict[str, Any]:
    """Validate 28 canonical, time-aligned M15 bar histories atomically.

    Historical session gaps (e.g., weekends) are counted, not filled.
    Spread is unverified *points*, never converted into executable costs.
    """
    if not isinstance(payload, Mapping) or payload.get("schema") != SCHEMA:
        return _blocked("INVALID_CONTRACT")
    if payload.get("state") != "OFFLINE_RESEARCH" or payload.get("timeframe") != "M15":
        return _blocked("INVALID_CONTRACT")
    if any(key in payload for key in ("token", "api_key", "password", "authorization", "access_token")):
        return _blocked("SENSITIVE_FIELD_NOT_ALLOWED")
    claim = payload.get("terminal_claim")
    if not isinstance(claim, str) or not claim.strip() or len(claim) > MAX_CLAIM_LENGTH:
        return _blocked("TERMINAL_CLAIM_INVALID")
    current = now if now is not None else datetime.now(timezone.utc)
    if current.tzinfo is None or current.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    current = current.astimezone(timezone.utc)
    raw = payload.get("pairs")
    if not isinstance(raw, Mapping) or set(raw) != set(OFFICIAL_PAIRS):
        return _blocked("INCOMPLETE_28_PAIR_UNIVERSE")

    common_last: datetime | None = None
    common_first: datetime | None = None
    common_timeline: tuple[datetime, ...] | None = None
    expected_count: int | None = None
    closes: dict[str, float] = {}
    ticks: dict[str, int] = {}
    spreads: dict[str, int] = {}
    gaps = 0
    for symbol in OFFICIAL_PAIRS:
        bars = raw[symbol]
        if not isinstance(bars, list) or not 3 <= len(bars) <= MAX_BARS:
            return _blocked("BAR_HISTORY_LENGTH_INVALID")
        first: datetime | None = None
        previous: datetime | None = None
        last_data: tuple[datetime, float, int, int] | None = None
        timeline: list[datetime] = []
        for raw_bar in bars:
            bar = _bar(raw_bar)
            if bar is None:
                return _blocked("MT5_OHLC_OR_FIELDS_INVALID")
            when = bar[0]
            if when + INTERVAL > current:
                return _blocked("FUTURE_OR_OPEN_HISTORY_BAR")
            if previous is not None:
                distance = when - previous
                if distance < INTERVAL or distance.total_seconds() % 900:
                    return _blocked("DUPLICATE_OR_OUT_OF_ORDER_BAR")
                if distance > INTERVAL:
                    gaps += 1
            if first is None:
                first = when
            previous = when
            last_data = bar
            timeline.append(when)
        assert first is not None and previous is not None and last_data is not None
        if common_timeline is None:
            common_first, common_last, expected_count = first, previous, len(bars)
            common_timeline = tuple(timeline)
        elif tuple(timeline) != common_timeline:
            return _blocked("MIXED_28_PAIR_HISTORY_WINDOWS")
        closes[symbol] = round(last_data[1], 8)
        ticks[symbol] = last_data[2]
        spreads[symbol] = last_data[3]

    assert common_last is not None and common_first is not None
    out = _blocked("UNAUTHENTICATED_MT5_HISTORY_RESEARCH_ONLY")
    out.update({
        "state": "RESEARCH_ONLY", "complete_pairs": 28,
        "bars_per_pair": expected_count,
        "terminal_claim": claim.strip(),
        "first_bar_start_utc": common_first.isoformat(),
        "last_bar_start_utc": common_last.isoformat(),
        "last_bar_end_utc": (common_last + INTERVAL).isoformat(),
        "last_bar_age_minutes": (current - (common_last + INTERVAL)).total_seconds() / 60,
        "last_close": closes,
        "last_tick_volume": ticks,
        "last_spread_points": spreads,
        "total_history_gaps": gaps,
        "volume_kind": "BROKER_TICK_COUNT_NOT_CENTRALIZED_FOREX_VOLUME",
        "notice": (
            "MT5-shaped OHLC history only; no authenticated prices, bid/ask "
            "execution, volume confirmation, or spread-cost calibration."
        ),
    })
    return out


__all__ = ["SCHEMA", "OUTPUT_SCHEMA", "analyze_mt5_m15_history"]
