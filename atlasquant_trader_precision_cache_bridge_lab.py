"""LAB-only offline bridge: historical shared cache -> complete 28-FX strength.

Consumes an already-supplied cache dictionary. NEVER loads disk, calls API,
imports the cache network loader, mutates runtime, emits signals or sends orders.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from math import isfinite, log
from typing import Any, Mapping

from atlasquant_instrument_registry import FX_28
from atlasquant_trader_precision_lab import (
    PairWindow, StrengthResult, assess_28_pair_strength,
)

INTERVAL = timedelta(minutes=15)
CACHE_FEED = "twelve_series_v1108/15min/offline"
_CACHE_SUFFIX = "|15min"


@dataclass(frozen=True)
class OfflineFX28CacheAudit:
    status: str
    missing_pairs: tuple[str, ...]
    invalid_pairs: tuple[str, ...]
    reason: str
    strength: StrengthResult | None

    @property
    def ready_for_research(self) -> bool:
        return self.status == "COMPLETE_RESEARCH_ONLY" and self.strength is not None


def _timestamp(value: Any) -> datetime | None:
    if type(value) is not str or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)


def _valid_candle(record: Any) -> tuple[datetime, float] | None:
    if type(record) is not dict:
        return None
    ts = _timestamp(record.get("datetime"))
    if ts is None:
        return None
    nums = []
    for field in ("open", "high", "low", "close"):
        x = record.get(field)
        if type(x) not in (float, int) or not isfinite(x) or x <= 0:
            return None
        nums.append(float(x))
    op, hi, lo, cl = nums
    if hi < max(op, lo, cl) or lo > min(op, hi, cl):
        return None
    return ts, cl


def _window_for_pair(
    raw: Any, *, now: datetime, max_age: timedelta
) -> PairWindow | None:
    if type(raw) is not dict:
        return None
    fetched = _timestamp(raw.get("fetched_at"))
    if fetched is None or fetched > now or now - fetched > max_age:
        return None
    records = raw.get("records")
    if type(records) is not list or len(records) < 2:
        return None
    closed: list[tuple[datetime, float]] = []
    seen = set()
    for record in records:
        value = _valid_candle(record)
        if value is None or value[0] in seen:
            return None
        seen.add(value[0])
        # A collector may include a still-open last M15 candle: ignore it.
        if value[0] + INTERVAL <= now:
            closed.append(value)
    closed.sort(key=lambda row: row[0])
    if len(closed) < 2:
        return None
    (t0, c0), (t1, c1) = closed[-2:]
    if t1 - t0 != INTERVAL or fetched < t1 + INTERVAL:
        return None
    if now - (t1 + INTERVAL) > max_age:
        return None
    return PairWindow(
        log_return=log(c1) - log(c0),
        start=t0 + INTERVAL,
        end=t1 + INTERVAL,
        feed=CACHE_FEED,
    )


def assess_existing_fx28_cache_offline(
    supplied_state: Any, *, now: datetime, max_age: timedelta
) -> OfflineFX28CacheAudit:
    """Inspect the existing raw twelve_series_v1108 shape without side effects.

    Expected keys are EUR/USD|15min etc. A bare alias is tolerated only if the
    slashed key is absent. Neither duplicates nor missing pair rows are imputed.
    Any failed pair denies all-currency strength to prevent partial ranking.
    """
    if (not isinstance(now, datetime) or now.tzinfo is None or
            now.utcoffset() is None or type(max_age) is not timedelta or
            max_age <= timedelta(0)):
        return OfflineFX28CacheAudit("WAIT_NO_CONTEXT", (), (),
                                     "invalid_now_or_age", None)
    if type(supplied_state) is not dict or type(supplied_state.get("series")) is not dict:
        return OfflineFX28CacheAudit("WAIT_NO_CONTEXT", tuple(FX_28), (),
                                     "cache_not_supplied", None)
    series = supplied_state["series"]
    missing: list[str] = []
    invalid: list[str] = []
    windows: dict[str, PairWindow] = {}
    for pair in FX_28:
        conventional = pair[:3] + "/" + pair[3:] + _CACHE_SUFFIX
        compact = pair + _CACHE_SUFFIX
        if conventional in series and compact in series:
            invalid.append(pair)
            continue
        key = conventional if conventional in series else compact
        if key not in series:
            missing.append(pair)
            continue
        value = _window_for_pair(
            series[key], now=now.astimezone(timezone.utc), max_age=max_age
        )
        if value is None:
            invalid.append(pair)
            continue
        windows[pair] = value
    if missing or invalid:
        return OfflineFX28CacheAudit("WAIT_NO_CONTEXT", tuple(missing), tuple(invalid),
                                     "missing_or_invalid_read_only_cache_rows", None)
    assessment = assess_28_pair_strength(windows, now=now, max_age=max_age)
    if not assessment.ready_for_research:
        return OfflineFX28CacheAudit("WAIT_NO_CONTEXT", (), (),
                                     assessment.reason, assessment)
    return OfflineFX28CacheAudit("COMPLETE_RESEARCH_ONLY", (), (),
                                 "no_trade_or_live_gate", assessment)
