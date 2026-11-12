"""AtlasQuant Trader: M15 quote-cost and already-moved-price veto (offline LAB).

Consumes caller-supplied closed bars and a bid/ask quote. Does not connect to
MetaTrader, validate broker provenance, prove liquidity, predict direction, or
publish signals. Thresholds are fixed *research hypotheses*, not fit/calibrated.
A non-vetoed research context is NOT authorization to issue a bias or trade.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from statistics import median
import re
from typing import Any

from atlasquant_fx_universe import OFFICIAL_PAIRS

SCHEMA = "ATLASQUANT_TRADER_FX_M15_PRICE_COST_VETO_LAB_V1"
PERIOD = timedelta(minutes=15)
REQUIRED_BARS = 21
ATR_BARS = 14
MAX_QUOTE_AGE = timedelta(seconds=90)
MAX_QUOTE_TRANSPORT = timedelta(seconds=20)
MAX_LAST_BAR_AGE = timedelta(minutes=16)
# Hypotheses ONLY. Cross-pair/regime thresholds need prospective calibration.
MAX_SPREAD_BPS = Decimal("8")
MAX_SPREAD_TO_ATR = Decimal("0.15")
MAX_FAVORABLE_1H_MOVE_ATR = Decimal("2.50")
MAX_LATEST_TRUE_RANGE_MULTIPLIER = Decimal("3.00")
SHA = re.compile(r"[0-9a-f]{64}\Z")
PRICE_TEXT = re.compile(r"[0-9]{1,5}(?:\.[0-9]{1,10})?\Z")
SIDES = frozenset(("ALTA", "BAIXA"))


@dataclass(frozen=True)
class ClosedM15Bar:
    opened_at_utc: datetime
    closed_at_utc: datetime
    received_at_utc: datetime
    open: str
    high: str
    low: str
    close: str
    tick_volume: int
    batch_sha256_claim: str


@dataclass(frozen=True)
class IndicativeBidAskQuote:
    asset: str
    observed_at_utc: datetime
    received_at_utc: datetime
    bid: str
    ask: str
    quote_sha256_claim: str


def _utc(v: Any) -> datetime | None:
    if not isinstance(v, datetime) or v.tzinfo is None or v.utcoffset() is None:
        return None
    return v.astimezone(timezone.utc)


def _price(v: Any) -> Decimal | None:
    if not isinstance(v, str) or PRICE_TEXT.fullmatch(v) is None:
        return None
    try:
        n = Decimal(v)
        return n if n.is_finite() and Decimal("0.000001") <= n <= 10000 else None
    except (InvalidOperation, ValueError):
        return None


def _out(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_PRICE_COST_VETO_BLOCKED",
        "reason": reason, "asset": None, "research_side": None,
        "closed_m15_bars_checked": 0, "quote_age_seconds_documentary": None,
        "spread_bps_documentary": None, "spread_to_atr_documentary": None,
        "favorable_1h_move_atr_documentary": None,
        "latest_true_range_multiplier_documentary": None,
        "research_veto": True,
        "m15_quote_and_bars_source_independently_attested": False,
        "bid_ask_quote_is_executable": False,
        "full_liquidity_and_depth_verified": False,
        "fees_slippage_and_swap_included": False,
        "cost_thresholds_empirically_calibrated": False,
        "price_extension_threshold_empirically_calibrated": False,
        "out_of_sample_incremental_edge_verified": False,
        "directional_accuracy_validated": None,
        "calibrated_direction_probability": None,
        "fx_bias": None, "operational_bias": "AGUARDAR",
        "publishable": False, "live_alert_allowed": False,
        "trade_authorized": False, "worker_enabled": False,
        "scheduler_enabled": False, "new_cost_brl": 0,
    }


def inspect_fx_m15_price_cost_veto_lab(
    *, asset: Any, research_side: Any, closed_bars: Any,
    quote: Any, decision_at_utc: Any, as_of_utc: Any,
) -> dict[str, Any]:
    """Reject stale, expensive, extended or volatile hypothetical M15 context.

    A caller-provided 'spread' number on an OHLC candle is *not* accepted as
    a contemporaneous bid/ask quote. This reader requires an explicit snapshot.
    """
    out = _out("INVALID_ASSET_OR_DECISION")
    decision, now = _utc(decision_at_utc), _utc(as_of_utc)
    if (not isinstance(asset, str) or asset not in OFFICIAL_PAIRS
            or research_side not in SIDES or decision is None or now is None
            or now < decision or not isinstance(closed_bars, (tuple, list))
            or len(closed_bars) != REQUIRED_BARS
            or not isinstance(quote, IndicativeBidAskQuote)
            or quote.asset != asset):
        return out
    quoted, received = _utc(quote.observed_at_utc), _utc(quote.received_at_utc)
    if (quoted is None or received is None or received < quoted
            or received > decision or quoted > decision
            or received - quoted > MAX_QUOTE_TRANSPORT
            or decision - quoted > MAX_QUOTE_AGE
            or not isinstance(quote.quote_sha256_claim, str)
            or SHA.fullmatch(quote.quote_sha256_claim) is None):
        out["reason"] = "STALE_UNAVAILABLE_OR_UNTRACKED_BID_ASK_QUOTE"
        return out
    bid, ask = _price(quote.bid), _price(quote.ask)
    if bid is None or ask is None or bid >= ask:
        out["reason"] = "INVALID_CROSSED_OR_ZERO_SPREAD_BID_ASK"
        return out
    mid = (bid + ask) / 2

    previous_closed = None
    previous_opened = None
    closes: list[Decimal] = []
    ranges: list[Decimal] = []
    declared_batch = None
    for i, bar in enumerate(closed_bars):
        if not isinstance(bar, ClosedM15Bar):
            out["reason"] = "M15_ROW_INVALID"
            return out
        opened, closed, captured = (_utc(bar.opened_at_utc),
                                    _utc(bar.closed_at_utc),
                                    _utc(bar.received_at_utc))
        if (opened is None or closed is None or captured is None
                or opened.timestamp() % 900 != 0
                or closed - opened != PERIOD
                or not closed <= captured <= decision
                or type(bar.tick_volume) is not int or bar.tick_volume <= 0
                or not isinstance(bar.batch_sha256_claim, str)
                or SHA.fullmatch(bar.batch_sha256_claim) is None):
            out["reason"] = "M15_CLOCK_VOLUME_OR_PROVENANCE_CLAIM_INVALID"
            return out
        if i and (opened != previous_opened + PERIOD
                  or opened != previous_closed):
            out["reason"] = "M15_MISSING_DUPLICATED_OR_NONCONTIGUOUS_BAR"
            return out
        if declared_batch is not None and declared_batch != bar.batch_sha256_claim:
            out["reason"] = "M15_BATCH_SOURCE_CLAIMS_INCONSISTENT"
            return out
        declared_batch = bar.batch_sha256_claim
        o, h, low, c = (_price(v) for v in (bar.open, bar.high, bar.low, bar.close))
        if (o is None or h is None or low is None or c is None
                or not low <= min(o, c) <= max(o, c) <= h):
            out["reason"] = "M15_OHLC_CLAIMS_INVALID"
            return out
        ranges.append(max(h - low, abs(h - closes[-1]), abs(low - closes[-1]))
                      if closes else h - low)
        closes.append(c)
        previous_opened, previous_closed = opened, closed
    if (decision - previous_closed > MAX_LAST_BAR_AGE
            or previous_closed > quoted):
        out["reason"] = "QUOTE_AND_LAST_CLOSED_BAR_NOT_SYNCHRONIZED"
        return out
    reference = median(ranges[-ATR_BARS-1:-1])
    if reference <= 0:
        out["reason"] = "NO_POSITIVE_PRIOR_VOLATILITY_REFERENCE"
        return out
    spread = ask - bid
    spread_bps = spread / mid * Decimal("10000")
    relative_cost = spread / reference
    # Four closed M15 candles plus the current quote: an hour-ish price move.
    favorable_move = ((mid - closes[-5]) if research_side == "ALTA"
                      else (closes[-5] - mid)) / reference
    shock = ranges[-1] / reference
    out.update({
        "asset": asset, "research_side": research_side,
        "closed_m15_bars_checked": len(closed_bars),
        "quote_age_seconds_documentary": int((decision - quoted).total_seconds()),
        "spread_bps_documentary": str(spread_bps.quantize(Decimal("0.001"))),
        "spread_to_atr_documentary": str(relative_cost.quantize(Decimal("0.001"))),
        "favorable_1h_move_atr_documentary": str(favorable_move.quantize(Decimal("0.001"))),
        "latest_true_range_multiplier_documentary": str(shock.quantize(Decimal("0.001"))),
    })
    if spread_bps > MAX_SPREAD_BPS:
        out.update(state="LAB_SPREAD_TOO_WIDE_VETO", reason="SPREAD_BPS_RESEARCH_LIMIT_EXCEEDED")
    elif relative_cost > MAX_SPREAD_TO_ATR:
        out.update(state="LAB_SPREAD_TOO_WIDE_VETO", reason="SPREAD_RELATIVE_TO_RECENT_RANGE_TOO_HIGH")
    elif favorable_move > MAX_FAVORABLE_1H_MOVE_ATR:
        out.update(state="LAB_PRICE_ALREADY_EXTENDED_VETO", reason="ONE_HOUR_FAVORABLE_MOVE_RELATIVE_TO_RANGE_TOO_LARGE")
    elif shock > MAX_LATEST_TRUE_RANGE_MULTIPLIER:
        out.update(state="LAB_VOLATILITY_SHOCK_VETO", reason="LATEST_CLOSED_BAR_VOLATILITY_SHOCK")
    else:
        out.update(state="LAB_PRICE_COST_CONTEXT_NOT_VETOED_UNATTESTED",
                   reason="COST_AND_EXTENSION_HYPOTHESES_ONLY_NOT_LIVE_PERMISSION",
                   research_veto=False)
    return out


__all__ = (
    "ClosedM15Bar", "IndicativeBidAskQuote",
    "inspect_fx_m15_price_cost_veto_lab",
)