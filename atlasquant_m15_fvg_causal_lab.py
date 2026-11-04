"""Causal three-candle FVG zone lifecycle for offline M15 research only.

No broker, signals, orders, higher-timeframe trend, or profitability claims.
Zone formation is timestamped only AFTER the third candle has closed.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from math import isfinite
from typing import Any, Mapping

from atlasquant_fx_universe import OFFICIAL_PAIRS

SCHEMA = "ATLASQUANT_M15_FVG_CAUSAL_IMPORT_LAB_V1"
OUTPUT_SCHEMA = "ATLASQUANT_M15_FVG_CAUSAL_RESEARCH_LAB_V1"
M15 = timedelta(minutes=15)


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": OUTPUT_SCHEMA, "state": "BLOCKED", "reason": reason,
        "zone_count": 0, "zones": [], "events": [],
        "source_authenticated": False, "trend_verified": False,
        "setup_accuracy_verified": False, "profitability_verified": False,
        "publishable": False, "trade_authorized": False,
    }


def _number(value: Any, *, zero_ok: bool = False) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if not isfinite(result) or (result < 0 if zero_ok else result <= 0):
        return None
    return result


def _time(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        t = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if t.tzinfo is None or t.utcoffset() is None:
        return None
    t = t.astimezone(timezone.utc)
    if t.minute % 15 or t.second or t.microsecond or not 1970 <= t.year <= 2100:
        return None
    return t


def _bar(raw: Any) -> tuple[datetime, float, float, float, float] | None:
    if not isinstance(raw, Mapping) or raw.get("complete") is not True:
        return None
    stamp = _time(raw.get("time"))
    values = [_number(raw.get(key)) for key in ("open", "high", "low", "close")]
    if stamp is None or any(x is None for x in values):
        return None
    opening, high, low, close = values
    assert opening is not None and high is not None and low is not None and close is not None
    if high < max(opening, close, low) or low > min(opening, close, high):
        return None
    return stamp, opening, high, low, close


def scan_m15_fvg(payload: Any, *, now: datetime | None = None) -> dict[str, Any]:
    """Detect completed 3-bar imbalances, then replay later mitigation only.

    No future candle is used to create or resize a zone. Body and minimum-gap
    thresholds are explicit experimental filters, not calibrated performance.
    """
    if not isinstance(payload, Mapping) or payload.get("schema") != SCHEMA:
        return _blocked("INVALID_CONTRACT")
    if payload.get("state") != "OFFLINE_RESEARCH" or payload.get("timeframe") != "M15":
        return _blocked("INVALID_CONTRACT")
    if payload.get("pair") not in OFFICIAL_PAIRS:
        return _blocked("INVALID_PAIR")
    if any(k in payload for k in ("token", "api_key", "authorization", "access_token")):
        return _blocked("SENSITIVE_FIELD_NOT_ALLOWED")
    point = _number(payload.get("point_size"))
    min_points = _number(payload.get("minimum_gap_points"), zero_ok=True)
    middle_body_min = _number(payload.get("middle_body_min_fraction"), zero_ok=True)
    if (point is None or min_points is None or middle_body_min is None
            or middle_body_min > 1):
        return _blocked("INVALID_FVG_FILTERS")
    current = now if now is not None else datetime.now(timezone.utc)
    if current.tzinfo is None or current.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    current = current.astimezone(timezone.utc)
    raw = payload.get("bars")
    if not isinstance(raw, list) or not 3 <= len(raw) <= 500:
        return _blocked("BAR_COUNT_INVALID")
    bars: list[tuple[datetime, float, float, float, float]] = []
    gaps = 0
    for item in raw:
        b = _bar(item)
        if b is None:
            return _blocked("OPEN_OR_INVALID_OHLC")
        if b[0] + M15 > current:
            return _blocked("FUTURE_OR_UNCLOSED_BAR")
        if bars:
            delta = b[0] - bars[-1][0]
            if delta < M15 or delta.total_seconds() % 900:
                return _blocked("DUPLICATE_OR_MISALIGNED_TIME")
            if delta != M15:
                gaps += 1
        bars.append(b)

    zones: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    for i in range(2, len(bars)):
        first, middle, third = bars[i-2], bars[i-1], bars[i]
        # Existing zones may react to bar i. A zone created by bar i cannot.
        for zone in zones:
            if zone["status"] == "INVALIDATED_CLOSE":
                continue
            lower, upper = zone["lower"], zone["upper"]
            if zone["direction"] == "BULLISH":
                invalidated = third[4] < lower
                filled = third[3] <= lower and third[2] >= lower
                touched = third[3] <= upper and third[2] >= lower
            else:
                invalidated = third[4] > upper
                filled = third[2] >= upper and third[3] <= upper
                touched = third[2] >= lower and third[3] <= upper
            new_status = (
                "INVALIDATED_CLOSE" if invalidated else
                "FULLY_FILLED" if filled else
                "TOUCHED" if touched else zone["status"]
            )
            order = {"ACTIVE": 0, "TOUCHED": 1, "FULLY_FILLED": 2, "INVALIDATED_CLOSE": 3}
            if order[new_status] > order[zone["status"]]:
                zone["status"] = new_status
                zone["last_change_at"] = (third[0] + M15).isoformat()
                events.append({
                    "id": zone["id"], "event": new_status,
                    "observed_at": zone["last_change_at"],
                })

        # A three-candle FVG requires truly consecutive candles. Overnight or
        # weekend gaps are NOT themselves categorized as price imbalances.
        if middle[0] - first[0] != M15 or third[0] - middle[0] != M15:
            continue
        body = abs(middle[4] - middle[1])
        candle_range = middle[2] - middle[3]
        if candle_range <= 0 or body / candle_range < middle_body_min:
            continue
        bullish = third[3] > first[2] and middle[4] > middle[1]
        bearish = third[2] < first[3] and middle[4] < middle[1]
        if not bullish and not bearish:
            continue
        lower, upper = (first[2], third[3]) if bullish else (third[2], first[3])
        if (upper - lower) / point < min_points:
            continue
        direction = "BULLISH" if bullish else "BEARISH"
        created = (third[0] + M15).isoformat()
        ident = f"M15:{direction}:{created}"
        zone = {
            "id": ident, "direction": direction,
            "lower": lower, "upper": upper,
            "created_at": created, "status": "ACTIVE",
            "last_change_at": created,
        }
        zones.append(zone)
        events.append({"id": ident, "event": "CREATED", "observed_at": created})

    out = _blocked("UNAUTHENTICATED_CAUSAL_FVG_RESEARCH_ONLY")
    out.update({
        "state": "RESEARCH_ONLY", "pair": payload["pair"],
        "timeframe": "M15", "zone_count": len(zones),
        "zone_created_after_third_close": True,
        "historical_session_gaps": gaps,
        "zones": [
            {**z, "lower": round(z["lower"], 8), "upper": round(z["upper"], 8)}
            for z in zones
        ],
        "events": events,
        "as_of": (bars[-1][0] + M15).isoformat(),
        "notice": "Experimental FVG map; no trend, entry, execution or accuracy validation.",
    })
    return out


__all__ = ["SCHEMA", "OUTPUT_SCHEMA", "scan_m15_fvg"]
