"""AtlasQuant Trader precision research: full FX cross-section and zone deduplication.

LAB ONLY. No market feed, signal, win-rate claim, execution, Worker or SEND.
All scores are descriptive/heuristic until independently walk-forward calibrated.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from itertools import combinations
from math import isfinite
from typing import Mapping

CURRENCIES = ("AUD", "CAD", "CHF", "EUR", "GBP", "JPY", "NZD", "USD")
PAIRS = (
    "EURUSD", "GBPUSD", "AUDUSD", "NZDUSD", "USDCAD", "USDCHF", "USDJPY",
    "EURGBP", "EURAUD", "EURNZD", "EURCAD", "EURCHF", "EURJPY",
    "GBPAUD", "GBPNZD", "GBPCAD", "GBPCHF", "GBPJPY",
    "AUDNZD", "AUDCAD", "AUDCHF", "AUDJPY",
    "NZDCAD", "NZDCHF", "NZDJPY", "CADCHF", "CADJPY", "CHFJPY",
)
assert len(PAIRS) == 28
assert {frozenset((p[:3], p[3:])) for p in PAIRS} == {
    frozenset(x) for x in combinations(CURRENCIES, 2)
}
assert len(set(PAIRS)) == len(PAIRS)


@dataclass(frozen=True)
class PairWindow:
    """Log return ln(close/end divided by close/start), same feed and window."""
    log_return: float
    start: datetime
    end: datetime
    feed: str


@dataclass(frozen=True)
class StrengthResult:
    status: str
    currency_scores: dict[str, float]
    pair_context: dict[str, float]
    residual_by_pair: dict[str, float]
    max_abs_residual: float
    reason: str

    @property
    def ready_for_research(self) -> bool:
        return self.status == "COMPLETE_CONTEXT_ONLY"


def _wait(reason: str) -> StrengthResult:
    return StrengthResult("WAIT_NO_CONTEXT", {}, {}, {}, 0.0, reason)


def _aware(value: object) -> bool:
    return isinstance(value, datetime) and value.tzinfo is not None and value.utcoffset() is not None


def assess_28_pair_strength(
    windows: Mapping[str, PairWindow], *, now: datetime, max_age: timedelta
) -> StrengthResult:
    """Project all 28 synchronized log returns onto zero-sum eight-currency strength.

    For a complete 8-currency graph the least-squares estimate is
    s[c] = sum(signed pair log returns incident to c) / 8.
    Missing/stale/inconsistent windows are WAIT, never imputed. Residuals
    expose cross-rate disagreement, rather than hiding it as confidence.
    """
    if not _aware(now) or type(max_age) is not timedelta or max_age <= timedelta(0):
        return _wait("invalid_clock_or_freshness_contract")
    if not isinstance(windows, Mapping) or set(windows) != set(PAIRS):
        return _wait("requires_exactly_all_28_unique_pairs")
    reference = None
    totals = {currency: 0.0 for currency in CURRENCIES}
    for pair in PAIRS:
        item = windows[pair]
        if not isinstance(item, PairWindow):
            return _wait("malformed_pair_window")
        r = item.log_return
        if type(r) not in (int, float) or not isfinite(r):
            return _wait("nonfinite_or_non_numeric_return")
        if not _aware(item.start) or not _aware(item.end) or item.start >= item.end:
            return _wait("invalid_window_timestamps")
        if type(item.feed) is not str or not item.feed.strip():
            return _wait("missing_feed_provenance")
        current = (item.start, item.end, item.feed)
        if reference is None:
            reference = current
        if current != reference:
            return _wait("different_time_windows_or_feeds")
        if item.end > now or now - item.end > max_age:
            return _wait("future_or_stale_observation")
        base, quote = pair[:3], pair[3:]
        totals[base] += r
        totals[quote] -= r
    scores = {c: totals[c] / len(CURRENCIES) for c in CURRENCIES}
    contexts = {p: scores[p[:3]] - scores[p[3:]] for p in PAIRS}
    residuals = {p: windows[p].log_return - contexts[p] for p in PAIRS}
    return StrengthResult(
        "COMPLETE_CONTEXT_ONLY", scores, contexts, residuals,
        max(abs(r) for r in residuals.values()),
        "relative_strength_not_entry_signal",
    )


@dataclass(frozen=True)
class Zone:
    origin_id: str
    pair: str
    timeframe: str
    side: str
    kind: str
    low: float
    high: float
    detector_quality_score: float
    formed_at_epoch: int
    invalidated: bool = False


@dataclass(frozen=True)
class ZoneResolution:
    selected: tuple[Zone, ...]
    suppressed_by: tuple[tuple[str, str], ...]
    invalidated_ids: tuple[str, ...]


def _zone_rank(zone: Zone) -> tuple[float, int, int, str]:
    # Data-backed detector score first; FVG only wins a true score tie.
    return (-zone.detector_quality_score, 0 if zone.kind == "FVG" else 1,
            -zone.formed_at_epoch, zone.origin_id)


def _gap(a: Zone, b: Zone) -> float:
    return max(0.0, max(a.low, b.low) - min(a.high, b.high))


def resolve_near_fvg_ob(
    zones: list[Zone] | tuple[Zone, ...],
    atr_by_pair_timeframe: Mapping[tuple[str, str], float],
    *, max_gap_atr: float = 0.15,
) -> ZoneResolution:
    """Suppress competing *same-side* nearby zones, without issuing a trade.

    Different pairs, directions and timeframes never compete. Higher validated
    detector quality wins; an FVG wins a tie. Inputs are mandatory research
    evidence, not an estimated probability of profit.
    """
    if type(max_gap_atr) not in (int, float) or not isfinite(max_gap_atr) or max_gap_atr < 0:
        raise ValueError("invalid proximity threshold")
    if not isinstance(zones, (list, tuple)) or not isinstance(atr_by_pair_timeframe, Mapping):
        raise ValueError("invalid zone batch or ATR map")
    ids = set()
    for zone in zones:
        if not isinstance(zone, Zone) or type(zone.origin_id) is not str or not zone.origin_id:
            raise ValueError("malformed origin identity")
        if zone.origin_id in ids:
            raise ValueError("duplicate origin identity")
        ids.add(zone.origin_id)
        if (zone.pair not in PAIRS or not zone.timeframe or
                zone.side not in ("BUY", "SELL") or zone.kind not in ("FVG", "OB")):
            raise ValueError("invalid zone metadata")
        if (type(zone.low) not in (int, float) or type(zone.high) not in (int, float)
                or not isfinite(zone.low) or not isfinite(zone.high) or
                zone.low <= 0 or zone.high <= zone.low):
            raise ValueError("invalid zone bounds")
        score = zone.detector_quality_score
        if type(score) not in (int, float) or not isfinite(score) or not 0 <= score <= 1:
            raise ValueError("invalid detector score")
        if type(zone.formed_at_epoch) is not int or type(zone.invalidated) is not bool:
            raise ValueError("invalid formation/invalidation state")
        atr = atr_by_pair_timeframe.get((zone.pair, zone.timeframe))
        if type(atr) not in (int, float) or not isfinite(atr) or atr <= 0:
            raise ValueError("missing or invalid ATR for zone")
    selected: list[Zone] = []
    suppressed: list[tuple[str, str]] = []
    active = [z for z in zones if not z.invalidated]
    for zone in sorted(active, key=_zone_rank):
        near_winner = next(
            (winner for winner in selected
             if zone.pair == winner.pair and zone.timeframe == winner.timeframe
             and zone.side == winner.side
             and _gap(zone, winner) <= max_gap_atr *
             atr_by_pair_timeframe[(zone.pair, zone.timeframe)]),
            None,
        )
        if near_winner is None:
            selected.append(zone)
        else:
            suppressed.append((zone.origin_id, near_winner.origin_id))
    return ZoneResolution(
        tuple(sorted(selected, key=lambda z: z.origin_id)),
        tuple(sorted(suppressed)),
        tuple(sorted(z.origin_id for z in zones if z.invalidated)),
    )
