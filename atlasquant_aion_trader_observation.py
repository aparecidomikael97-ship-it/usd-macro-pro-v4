"""A268: offline AION Trader observation view built from existing resident data.

No provider calls, network, brokerage, signals, order placement, new data
collection, spending, Worker, or external actions. In particular, a CURRENT
resident snapshot alone does not prove that its M15 technical series is fresh.
All 28 FX pairs are displayed, but '28/28 monitored' is only true when ALL
28 have individually fresh closed-M15 evidence. Strength is optional input
context, not independently verified data or trade advice.
"""
from __future__ import annotations

from datetime import datetime, timezone
import math
from typing import Any

from atlasquant_instrument_registry import FX_28, FX_CURRENCIES, FX_BY_SYMBOL
from atlasquant_risk_guardian import (
    RiskLimits, RiskState, evaluate_risk_guard,
)

SCHEMA = "ATLASQUANT_AION_A268_TRADER_READ_ONLY_OBSERVATION_V1"
M15_MAX_AGE_MINUTES = 70
STRENGTH_MAX_AGE_MINUTES = 70
CURRENT_M15_SOURCES = frozenset((
    "scanner/cache_v110/m15",
    "twelve_series_v1108 / closed M15",
))
TEMPORAL_LABELS = ("M5", "M15", "M30", "H1", "H4", "D1")
NO_SEND_MODES = {
    "trader": "READ_ONLY",
    "investimentos": "SCAFFOLD_ONLY",
    "negocios": "FROZEN_IN_THIS_READ_MODEL",
    "real_trading_enabled": False,
    "external_actions_enabled": False,
    "new_market_data_requests": False,
    "authorizes_send": False,
    "permits_deploy": False,
    "p0_homologated": 0,
}


def _timestamp(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        date = value
    elif type(value) is str:
        try:
            date = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if date.tzinfo is None or date.utcoffset() is None:
        return None
    return date.astimezone(timezone.utc)


def _age_minutes(value: Any, now: datetime) -> float | None:
    dt = _timestamp(value)
    if dt is None:
        return None
    delta = (now - dt).total_seconds() / 60.0
    # Future evidence is NEVER promoted, even inside a small tolerance.
    if delta < 0 or not math.isfinite(delta):
        return None
    return delta


def _finite_native_number(value: Any) -> bool:
    if type(value) not in (int, float):
        return False
    try:
        return math.isfinite(value)
    except (OverflowError, ValueError):
        # Python's isfinite may overflow when converting huge int to float.
        return False


def _closed_series(value: Any) -> bool:
    return (
        type(value) in (tuple, list)
        and len(value) >= 2
        and len(value) <= 1000
        and all(_finite_native_number(n) and n > 0 for n in value)
    )


def _canonical_asset(value: Any) -> str | None:
    if type(value) is not str:
        return None
    raw = value.strip().upper()
    if raw.startswith("FX:"):
        raw = raw[3:]
    for ch in ("/", "-", "_", " "):
        raw = raw.replace(ch, "")
    return raw if raw in FX_BY_SYMBOL else None


def _strength_context(raw: Any, *, now: datetime) -> dict[str, float] | None:
    if type(raw) is not dict or set(raw) != {"scores", "as_of", "source"}:
        return None
    if type(raw["source"]) is not str or not raw["source"].strip():
        return None
    age = _age_minutes(raw["as_of"], now)
    if age is None or age >= STRENGTH_MAX_AGE_MINUTES:
        return None
    scores = raw["scores"]
    if type(scores) is not dict or set(scores) != set(FX_CURRENCIES):
        return None
    if not all(
        _finite_native_number(n) and abs(n) <= 1_000_000
        for n in scores.values()
    ):
        return None
    return {currency: float(scores[currency]) for currency in FX_CURRENCIES}


def _risk_status(limits: Any, state: Any) -> dict[str, Any]:
    if not isinstance(limits, RiskLimits) or not isinstance(state, RiskState):
        return {"status": "UNVERIFIED_BLOCKED", "reasons": ["RISK_INPUT_MISSING"]}
    try:
        decision = evaluate_risk_guard(limits, state)
    except (TypeError, ValueError, OverflowError):
        return {"status": "UNVERIFIED_BLOCKED", "reasons": ["RISK_INPUT_INVALID"]}
    if decision.locked:
        return {"status": "LIMIT_REACHED_BLOCKED", "reasons": list(decision.reasons)}
    return {
        "status": "SIMULATION_BUDGET_NOT_LOCKED_STILL_NO_TRADING",
        "reasons": [],
    }


def trader_readonly_observation(
    resident: Any,
    *,
    now: datetime | None = None,
    currency_strength: Any = None,
    timeframe_evidence: Any = None,
    risk_limits: RiskLimits | None = None,
    risk_state: RiskState | None = None,
) -> dict[str, Any]:
    """Produce 28 observation rows, never BUY/SELL, alert or execution advice.

    `resident` is the already hydrated Trader presentation state. This function
    never invokes providers, caches, getters or other callbacks, and never
    treats a market-input score as independently authenticated.
    """
    if now is None:
        now = datetime.now(timezone.utc)
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("timezone-aware now required")
    now = now.astimezone(timezone.utc)
    source = resident if type(resident) is dict else {}
    raw_items = source.get("atlasquant_validated_market_items")
    raw_items = raw_items if type(raw_items) is list and len(raw_items) <= 1000 else []
    indexes: dict[str, dict] = {}
    duplicates: set[str] = set()
    unknown = 0
    for obj in raw_items:
        if type(obj) is not dict:
            unknown += 1
            continue
        symbol = _canonical_asset(obj.get("asset"))
        if symbol is None:
            unknown += 1
            continue
        if symbol in indexes:
            duplicates.add(symbol)
            continue
        indexes[symbol] = obj

    relative_scores = _strength_context(currency_strength, now=now)
    rows = []
    current_count = 0
    historical_count = 0
    for pair in FX_28:
        obs = indexes.get(pair)
        evidence = "MISSING"
        stamp = None
        if pair in duplicates:
            evidence = "DUPLICATE_AMBIGUOUS"
        elif obs is not None:
            stamp = obs.get("series_as_of") or obs.get("quote_as_of")
            age = _age_minutes(stamp, now)
            has_series = _closed_series(obs.get("series"))
            source_name = obs.get("series_source") or obs.get("quote_source")
            has_current_m15 = (
                obs.get("validated") is True
                and obs.get("presentation_state") == "CURRENT"
                and (
                    (obs.get("series_source") == "scanner/cache_v110/m15"
                     and obs.get("series_state") == "CURRENT")
                    or (obs.get("quote_source") ==
                        "twelve_series_v1108 / closed M15")
                )
                and "historical_series" not in obs
            )
            if (
                has_current_m15
                and has_series
                and source_name in CURRENT_M15_SOURCES
                and age is not None
                and age < M15_MAX_AGE_MINUTES
            ):
                evidence = "FRESH_CLOSED_M15"
                current_count += 1
            elif (
                obs.get("presentation_state") == "HISTORICAL_STALE"
                or obs.get("series_state") == "HISTORICAL_STALE"
                or (age is not None and age >= M15_MAX_AGE_MINUTES)
                or "historical_series" in obs
            ):
                evidence = "HISTORICAL_ONLY"
                historical_count += 1
            else:
                evidence = "INSUFFICIENT_OR_UNVERIFIED"

        instrument = FX_BY_SYMBOL[pair]
        rel = {"status": "NO_FRESH_8_CURRENCY_INPUT", "direction": "UNKNOWN"}
        if relative_scores is not None:
            spread = relative_scores[instrument.base] - relative_scores[instrument.quote]
            rel = {
                "status": "UNVERIFIED_INPUT_CONTEXT_ONLY",
                "direction": (
                    "BASE_STRONGER" if spread > 0
                    else "QUOTE_STRONGER" if spread < 0 else "TIED"
                ),
                "base": instrument.base,
                "quote": instrument.quote,
            }

        periods = {tf: "NO_SEPARATE_TIMEFRAME_EVIDENCE" for tf in TEMPORAL_LABELS}
        periods["M15"] = evidence
        row = {
            "asset": pair,
            "market_evidence": evidence,
            "timeframes": periods,
            "relative_currency": rel,
            "context_bias_not_signal": (
                obs.get("last_bias") if type(obs) is dict
                and type(obs.get("last_bias")) is str else None
            ),
            "recommendation": "NONE_READ_ONLY",
            "authorizes_order": False,
        }
        rows.append(row)

    board = {
        "schema": SCHEMA,
        "mode": dict(NO_SEND_MODES),
        "generated_at": now.isoformat(),
        "source": "RESIDENT_PRESENTATION_ALREADY_IN_MEMORY_NO_FETCH",
        "universe": "FX_28",
        "expected_pairs": 28,
        "fresh_m15_pairs": current_count,
        "historical_m15_pairs": historical_count,
        "all_28_fresh_closed_m15": (
            current_count == 28 and not duplicates
        ),
        "duplicate_pairs": sorted(duplicates),
        "unknown_or_invalid_rows": unknown,
        "relative_strength_status": (
            "FRESH_INPUT_NOT_INDEPENDENTLY_VERIFIED"
            if relative_scores is not None else "UNAVAILABLE_OR_STALE"
        ),
        "risk": _risk_status(risk_limits, risk_state),
        "rows": rows,
        "no_orders": True,
        "no_alerts": True,
        "no_new_data_calls": True,
    }
    # Explicit external-in-memory candle evidence is optional. If omitted,
    # A268 behavior and its M15-only compatibility stay unchanged. There is
    # no provider/client/aggregator anywhere in this read-only extension.
    if timeframe_evidence is not None:
        from atlasquant_aion_trader_timeframes import merge_mtf_readonly
        merge_mtf_readonly(
            board, evidence=timeframe_evidence, now=now,
            resident_rows=raw_items,
        )
    return board
