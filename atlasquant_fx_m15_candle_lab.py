"""Offline 28-pair M15 market-candle contract (LAB ONLY).

No HTTP, credentials, broker operations, quote publishing, or AION integration.
Validating payload shape does not authenticate its source or execution prices.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from math import expm1, isfinite, log
from typing import Any, Mapping

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS, split_pair

SCHEMA = "ATLASQUANT_FX_28_M15_CANDLE_IMPORT_LAB_V1"
OUTPUT_SCHEMA = "ATLASQUANT_FX_28_M15_CANDLE_RESEARCH_LAB_V1"
M15 = timedelta(minutes=15)
MAX_CAPTURE_AGE = timedelta(minutes=5)
MAX_COMPLETED_CANDLE_AGE = timedelta(minutes=45)
MAX_SPREAD_PCT = 0.75
MAX_M15_MOVE_PCT = 15.0
MAX_CROSS_RESIDUAL_LOG_PP = 0.30


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": OUTPUT_SCHEMA, "state": "BLOCKED", "reason": reason,
        "complete_pairs": 0, "total_pairs": 28, "pair_changes_pct": {},
        "spreads_pct": {}, "currency_strength_log_pp": {}, "top10": [],
        "publishable": False, "provider_authenticated": False,
        "trade_authorized": False, "accuracy_verified": False,
        "independent_observations_verified": False,
        "has_executable_bid_ask": False,
        "candle_bid_ask_is_historical": True,
    }


def _time(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        return None
    return stamp.astimezone(timezone.utc)


def _price(value: Any) -> float | None:
    # Broker JSON prices are often strings. Never accept booleans or NaN/Inf.
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        return None
    if isinstance(value, str) and (not value.strip() or len(value) > 40):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if isfinite(number) and number > 0 else None


def _ohlc(value: Any) -> dict[str, float] | None:
    if not isinstance(value, Mapping) or set(value) != {"o", "h", "l", "c"}:
        return None
    parts = {key: _price(value[key]) for key in ("o", "h", "l", "c")}
    if any(v is None for v in parts.values()):
        return None
    assert all(v is not None for v in parts.values())
    if parts["h"] < max(parts["o"], parts["c"], parts["l"]):
        return None
    if parts["l"] > min(parts["o"], parts["c"], parts["h"]):
        return None
    return parts  # type: ignore[return-value]


def _candle(value: Any) -> tuple[datetime, float, float, float] | None:
    if not isinstance(value, Mapping) or value.get("complete") is not True:
        return None
    stamp = _time(value.get("time"))
    bid, ask = _ohlc(value.get("bid")), _ohlc(value.get("ask"))
    if stamp is None or bid is None or ask is None:
        return None
    if stamp.minute % 15 or stamp.second or stamp.microsecond:
        return None
    if bid["c"] > ask["c"]:
        return None
    mid = (bid["c"] + ask["c"]) / 2.0
    spread = (ask["c"] - bid["c"]) / mid * 100 if isfinite(mid) and mid > 0 else float("inf")
    if not isfinite(spread) or spread > MAX_SPREAD_PCT:
        return None
    return stamp, mid, bid["c"], ask["c"]


def analyze_m15_candle_export(payload: Any, *, now: datetime | None = None) -> dict[str, Any]:
    """Inspect the two latest *completed* M15 candles for all 28 pairs.

    A future broker adapter must extract those candles into this contract.
    The output is never promoted to the Radar's VALIDATED_DAILY contract.
    """
    if not isinstance(payload, Mapping) or payload.get("schema") != SCHEMA:
        return _blocked("INVALID_CONTRACT")
    if payload.get("state") != "OFFLINE_RESEARCH" or payload.get("kind") != "MARKET_CANDLE_EXPORT":
        return _blocked("INVALID_CONTRACT")
    if any(key in payload for key in ("api_key", "access_token", "authorization", "token")):
        return _blocked("SENSITIVE_FIELD_NOT_ALLOWED")
    source = payload.get("source_claim")
    if not isinstance(source, str) or not source.strip() or len(source) > 150:
        return _blocked("SOURCE_CLAIM_INVALID")
    current = now if now is not None else datetime.now(timezone.utc)
    if current.tzinfo is None or current.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    current = current.astimezone(timezone.utc)
    captured = _time(payload.get("captured_at"))
    if captured is None or not timedelta(0) <= current - captured <= MAX_CAPTURE_AGE:
        return _blocked("STALE_OR_FUTURE_CAPTURE")
    raw = payload.get("pairs")
    if not isinstance(raw, Mapping) or set(raw) != set(OFFICIAL_PAIRS):
        return _blocked("INCOMPLETE_28_PAIR_UNIVERSE")

    common_times: tuple[datetime, datetime] | None = None
    mids: dict[str, tuple[float, float]] = {}
    spreads: dict[str, float] = {}
    for symbol in OFFICIAL_PAIRS:
        record = raw[symbol]
        if not isinstance(record, Mapping) or record.get("source_claim") != source:
            return _blocked("CANDLE_SOURCE_MISMATCH")
        if record.get("granularity") != "M15":
            return _blocked("WRONG_TIMEFRAME")
        candles = record.get("candles")
        if not isinstance(candles, list) or len(candles) != 2:
            return _blocked("REQUIRE_TWO_COMPLETED_CANDLES")
        old, latest = (_candle(candles[0]), _candle(candles[1]))
        if old is None or latest is None:
            return _blocked("INVALID_OHLC_OR_INCOMPLETE_CANDLE")
        if latest[0] - old[0] != M15:
            return _blocked("M15_CANDLE_GAP_OR_ORDER")
        if latest[0] + M15 > captured or captured - (latest[0] + M15) > MAX_COMPLETED_CANDLE_AGE:
            return _blocked("STALE_OR_FUTURE_M15_CANDLE")
        window = (old[0], latest[0])
        if common_times is None:
            common_times = window
        elif common_times != window:
            return _blocked("MIXED_CANDLE_WINDOWS")
        if latest[1] <= 0 or old[1] <= 0 or not isfinite(latest[1] + old[1]):
            return _blocked("NUMERIC_RANGE_INVALID")
        mids[symbol] = (old[1], latest[1])
        spreads[symbol] = (latest[3] - latest[2]) / latest[1] * 100

    returns: dict[str, float] = {}
    log_returns: dict[str, float] = {}
    for symbol, (old, latest) in mids.items():
        log_change = log(latest) - log(old)
        try:
            change = expm1(log_change) * 100
        except OverflowError:
            return _blocked("NUMERIC_RANGE_INVALID")
        if not isfinite(change) or abs(change) > MAX_M15_MOVE_PCT:
            return _blocked("IMPLAUSIBLE_M15_MOVE")
        returns[symbol], log_returns[symbol] = change, log_change * 100

    net = dict.fromkeys(CURRENCIES, 0.0)
    for symbol, change in log_returns.items():
        base, quote = split_pair(symbol)
        net[base] += change
        net[quote] -= change
    strength = {ccy: net[ccy] / 8 for ccy in CURRENCIES}
    residual = max(
        abs(log_returns[s] - (strength[split_pair(s)[0]] - strength[split_pair(s)[1]]))
        for s in OFFICIAL_PAIRS
    )
    if not isfinite(residual) or residual > MAX_CROSS_RESIDUAL_LOG_PP:
        return _blocked("M15_CROSS_RATE_INCONSISTENCY")
    assert common_times is not None
    result = _blocked("PROVIDER_NOT_AUTHENTICATED")
    ordered = sorted(returns.items(), key=lambda row: (-row[1], row[0]))
    result.update({
        "state": "RESEARCH_ONLY", "complete_pairs": 28,
        "source_claim": source.strip(),
        "captured_at": captured.isoformat(),
        "granularity": "M15",
        "previous_candle_start": common_times[0].isoformat(),
        "latest_candle_start": common_times[1].isoformat(),
        "latest_candle_end": (common_times[1] + M15).isoformat(),
        "pair_changes_pct": {s: round(returns[s], 6) for s in OFFICIAL_PAIRS},
        "spreads_pct": {s: round(spreads[s], 6) for s in OFFICIAL_PAIRS},
        "currency_strength_log_pp": {c: round(strength[c], 6) for c in CURRENCIES},
        "currency_order": sorted(CURRENCIES, key=lambda c: (-strength[c], c)),
        "top10": [{"pair": s, "change_pct": round(v, 6)} for s, v in ordered[:10]],
        "max_consistency_residual_log_pp": round(residual, 6),
        "notice": "Offline M15 candle research; source, execution prices, and prediction unverified.",
    })
    return result


__all__ = ["SCHEMA", "OUTPUT_SCHEMA", "analyze_m15_candle_export"]
