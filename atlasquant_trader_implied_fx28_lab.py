"""LAB ONLY: seven observed USD legs -> 28 IMPLICIT FX contexts.

Seven USD returns determine all eight currency relative moves algebraically,
but DO NOT supply 21 independently observed crosses, FVG/OB candles, spread,
market execution prices or provider proof. No orders, network or runtime writes.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from math import isfinite
from typing import Any, Mapping

from atlasquant_instrument_registry import FX_28, FX_CURRENCIES
from atlasquant_trader_precision_lab import PairWindow
from atlasquant_trader_precision_cache_bridge_lab import _window_for_pair

USD_LEGS = tuple(p for p in FX_28 if "USD" in (p[:3], p[3:]))
IMPLIED_CROSSES = tuple(p for p in FX_28 if p not in USD_LEGS)
assert len(USD_LEGS) == 7 and len(IMPLIED_CROSSES) == 21


@dataclass(frozen=True)
class ImpliedFX28Context:
    status: str
    currency_scores: dict[str, float]
    pair_context: dict[str, float]
    origin_by_pair: dict[str, str]
    observed_pairs: tuple[str, ...]
    implied_pairs: tuple[str, ...]
    missing_or_invalid: tuple[str, ...]
    reason: str
    allows_trading: bool = False

    @property
    def research_only(self) -> bool:
        return self.status == "IMPLIED_28_CONTEXT_ONLY"


def _deny(reason: str, missing: tuple[str, ...] = ()) -> ImpliedFX28Context:
    return ImpliedFX28Context("WAIT_NO_CONTEXT", {}, {}, {}, (), (), missing, reason)


def implied_28_from_7_usd(
    windows: Mapping[str, PairWindow], *, now: datetime, max_age: timedelta
) -> ImpliedFX28Context:
    """Algebraic relative-price comparison, never an observed 28-pair signal."""
    if (not isinstance(now, datetime) or now.tzinfo is None or
            now.utcoffset() is None or type(max_age) is not timedelta or
            max_age <= timedelta(0)):
        return _deny("invalid_clock_or_age")
    if not isinstance(windows, Mapping):
        return _deny("invalid_usd_leg_mapping")
    missing = tuple(p for p in USD_LEGS if p not in windows)
    if missing:
        return _deny("seven_usd_legs_required", missing)
    if set(windows) != set(USD_LEGS):
        return _deny("unexpected_non_usd_leg_not_observed")
    reference = None
    relative: dict[str, float] = {"USD": 0.0}
    for pair in USD_LEGS:
        row = windows[pair]
        if not isinstance(row, PairWindow):
            return _deny("malformed_usd_leg", (pair,))
        r = row.log_return
        if type(r) not in (int, float) or not isfinite(r):
            return _deny("nonfinite_or_invalid_log_return", (pair,))
        if (not isinstance(row.start, datetime) or
                not isinstance(row.end, datetime) or
                row.start.tzinfo is None or row.end.tzinfo is None or
                row.start.utcoffset() is None or row.end.utcoffset() is None or
                row.start >= row.end):
            return _deny("invalid_leg_timestamps", (pair,))
        if type(row.feed) is not str or not row.feed.strip():
            return _deny("unidentified_leg_provenance", (pair,))
        signature = (row.start, row.end, row.feed)
        if reference is None:
            reference = signature
        if signature != reference:
            return _deny("unsynchronized_usd_legs", (pair,))
        if row.end > now or now - row.end > max_age:
            return _deny("future_or_stale_leg", (pair,))
        base, quote = pair[:3], pair[3:]
        other = quote if base == "USD" else base
        relative[other] = -r if base == "USD" else r
    if set(relative) != set(FX_CURRENCIES):
        return _deny("incomplete_currency_projection")
    center = sum(relative.values()) / len(FX_CURRENCIES)
    scores = {c: relative[c] - center for c in FX_CURRENCIES}
    contexts = {p: scores[p[:3]] - scores[p[3:]] for p in FX_28}
    return ImpliedFX28Context(
        "IMPLIED_28_CONTEXT_ONLY", scores, contexts,
        {p: ("OBSERVED_USD_LEG" if p in USD_LEGS else "IMPLIED_CROSS_NOT_QUOTED")
         for p in FX_28},
        USD_LEGS, IMPLIED_CROSSES, (),
        "seven_usd_legs_not_28_observed_prices_or_zone_candles",
    )


def implied_28_from_supplied_cache(
    state: Any, *, now: datetime, max_age: timedelta
) -> ImpliedFX28Context:
    """Offline only: consume seven cached M15 USD series, never fetch them."""
    if (not isinstance(now, datetime) or now.tzinfo is None or
            now.utcoffset() is None or type(max_age) is not timedelta or
            max_age <= timedelta(0)):
        return _deny("invalid_clock_or_age")
    if type(state) is not dict or type(state.get("series")) is not dict:
        return _deny("cache_not_supplied", USD_LEGS)
    series = state["series"]
    windows = {}
    bad = []
    for pair in USD_LEGS:
        slash = pair[:3] + "/" + pair[3:] + "|15min"
        compact = pair + "|15min"
        if slash in series and compact in series:
            bad.append(pair)
            continue
        key = slash if slash in series else compact
        if key not in series:
            bad.append(pair)
            continue
        window = _window_for_pair(
            series[key], now=now.astimezone(timezone.utc), max_age=max_age
        )
        if window is None:
            bad.append(pair)
        else:
            windows[pair] = window
    if bad:
        return _deny("missing_or_untrusted_usd_cache_legs", tuple(bad))
    return implied_28_from_7_usd(windows, now=now, max_age=max_age)
