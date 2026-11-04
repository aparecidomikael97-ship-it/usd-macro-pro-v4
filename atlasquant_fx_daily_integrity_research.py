"""Offline FX G8 daily snapshot integrity and relative currency strength.

Research only. No provider calls, no live quote publishing, no order capability.
Pairs use the canonical 28 spot-FX quote orientations; signs are not reversed.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from math import isfinite, log
from typing import Any, Mapping

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS, split_pair

SCHEMA = "ATLASQUANT_FX_28_QUOTE_RESEARCH_V1"
OUTPUT_SCHEMA = "ATLASQUANT_FX_28_STRENGTH_RESEARCH_V1"
MAX_SNAPSHOT_AGE = timedelta(minutes=15)
MAX_CROSS_LAG = timedelta(seconds=90)
MAX_REFERENCE_AGE = timedelta(days=5)
MAX_SPREAD_PCT = 0.5
MAX_MOVE_PCT = 15.0
MAX_RESIDUAL_LOG_PP = 0.30


def _stamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        return None
    return stamp.astimezone(timezone.utc)


def _positive(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        number = float(value)
    except (OverflowError, TypeError, ValueError):
        return None
    return number if isfinite(number) and number > 0 else None


def analyze_fx_daily_snapshot(payload: Any, *, now: datetime | None = None) -> dict[str, Any]:
    """Strict and atomic: a bad/missing cross invalidates the *whole* ranking.

    Source identity is reported, never cryptographically authenticated here.
    Even a passing snapshot is RESEARCH_ONLY, not validated for the live UI.
    """
    out: dict[str, Any] = {
        "schema": OUTPUT_SCHEMA, "state": "BLOCKED", "reason": "INVALID_CONTRACT",
        "complete_pairs": 0, "total_pairs": len(OFFICIAL_PAIRS),
        "currencies": {}, "pair_returns_pct": {}, "top10": [],
        "source_claim": "", "as_of": "",
        "publishable": False, "provider_authenticated": False,
        "trade_authorized": False, "accuracy_verified": False,
        "max_consistency_residual_log_pp": None,
    }
    if not isinstance(payload, Mapping) or payload.get("schema") != SCHEMA:
        return out
    if payload.get("state") != "OFFLINE_RESEARCH":
        return out
    source = payload.get("source")
    if not isinstance(source, str) or not source.strip() or len(source) > 150:
        return out
    current = now if now is not None else datetime.now(timezone.utc)
    if current.tzinfo is None or current.utcoffset() is None:
        raise ValueError("now must have timezone")
    current = current.astimezone(timezone.utc)
    as_of = _stamp(payload.get("as_of"))
    if as_of is None or not timedelta(0) <= current - as_of <= MAX_SNAPSHOT_AGE:
        out["reason"] = "STALE_OR_FUTURE_SNAPSHOT"
        return out
    raw = payload.get("pairs")
    if not isinstance(raw, Mapping) or set(raw) != set(OFFICIAL_PAIRS):
        out["reason"] = "INCOMPLETE_28_PAIR_UNIVERSE"
        return out
    reference_clock: datetime | None = None
    min_quote: datetime | None = None
    max_quote: datetime | None = None
    returns: dict[str, float] = {}
    log_returns: dict[str, float] = {}
    for pair in OFFICIAL_PAIRS:
        quote = raw[pair]
        if not isinstance(quote, Mapping) or quote.get("source") != source:
            out["reason"] = "QUOTE_OR_SOURCE_INVALID"
            return out
        bid = _positive(quote.get("bid"))
        ask = _positive(quote.get("ask"))
        previous = _positive(quote.get("previous_close"))
        observed = _stamp(quote.get("observed_at"))
        reference = _stamp(quote.get("reference_at"))
        if None in (bid, ask, previous, observed, reference):
            out["reason"] = "QUOTE_FIELDS_INVALID"
            return out
        assert bid is not None and ask is not None and previous is not None
        assert observed is not None and reference is not None
        if ask < bid:
            out["reason"] = "BID_ASK_INVERTED"
            return out
        mid = (bid + ask) / 2
        if not isfinite(mid) or (ask - bid) / mid * 100 > MAX_SPREAD_PCT:
            out["reason"] = "SPREAD_TOO_WIDE"
            return out
        if (not reference < observed <= as_of or
                current - observed > MAX_SNAPSHOT_AGE or
                as_of - observed > timedelta(minutes=3)):
            out["reason"] = "QUOTE_TIME_INVALID"
            return out
        if not timedelta(minutes=30) <= observed - reference <= MAX_REFERENCE_AGE:
            out["reason"] = "REFERENCE_STALE_OR_FUTURE"
            return out
        if reference_clock is None:
            reference_clock = reference
        elif reference_clock != reference:
            out["reason"] = "MIXED_REFERENCE_SESSION"
            return out
        min_quote = observed if min_quote is None else min(min_quote, observed)
        max_quote = observed if max_quote is None else max(max_quote, observed)
        simple_pct = (mid / previous - 1) * 100
        if not isfinite(simple_pct) or abs(simple_pct) > MAX_MOVE_PCT:
            out["reason"] = "IMPLAUSIBLE_DAILY_MOVE"
            return out
        returns[pair] = simple_pct
        log_returns[pair] = 100 * log(mid / previous)
    assert min_quote is not None and max_quote is not None
    if max_quote - min_quote > MAX_CROSS_LAG:
        out["reason"] = "MIXED_QUOTE_TIMES"
        return out
    # Each G8 currency participates in seven unique edges in the 28-pair graph.
    # Summed signed log returns remove the arbitrary numeraire and center to zero.
    net = dict.fromkeys(CURRENCIES, 0.0)
    for pair, value in log_returns.items():
        base, counter = split_pair(pair)
        net[base] += value
        net[counter] -= value
    strength = {ccy: net[ccy] / len(CURRENCIES) for ccy in CURRENCIES}
    # For coherent FX crosses, a pair's log-return equals base - quote strength.
    # Residuals detect stale/crossed feeds, not directional predictability.
    residuals = {}
    for pair, observed_log in log_returns.items():
        base, counter = split_pair(pair)
        residuals[pair] = abs(observed_log - (strength[base] - strength[counter]))
    maximum = max(residuals.values())
    if maximum > MAX_RESIDUAL_LOG_PP:
        out["reason"] = "CROSS_RATE_INCONSISTENCY"
        out["max_consistency_residual_log_pp"] = round(maximum, 6)
        return out
    currency_sorted = sorted(strength.items(), key=lambda p: (-p[1], p[0]))
    sorted_pairs = sorted(returns.items(), key=lambda p: (-p[1], p[0]))
    out.update({
        "state": "RESEARCH_ONLY", "reason": "PROVIDER_NOT_AUTHENTICATED",
        "complete_pairs": 28, "source_claim": source.strip(),
        "as_of": as_of.isoformat(),
        "reference_at": reference_clock.isoformat() if reference_clock else "",
        "currencies": {ccy: round(strength[ccy], 6) for ccy in CURRENCIES},
        "currency_order": [ccy for ccy, _ in currency_sorted],
        "pair_returns_pct": {pair: round(returns[pair], 6) for pair in OFFICIAL_PAIRS},
        "top10": [{"pair": pair, "change_pct": round(v, 6)}
                  for pair, v in sorted_pairs[:10]],
        "max_consistency_residual_log_pp": round(maximum, 6),
        "method": "G8_MEAN_SIGNED_LOG_RETURN_V1",
        "notice": "Força relativa e variação diária não são probabilidade de acerto.",
    })
    return out


__all__ = ["SCHEMA", "OUTPUT_SCHEMA", "analyze_fx_daily_snapshot"]
