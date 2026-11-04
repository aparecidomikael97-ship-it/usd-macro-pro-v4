"""Pure offline OANDA v20-shaped M15 export adapter (no network or token).

Input is a caller-supplied list of instrument candle responses. Even when
structurally valid, it is NOT proof of an authenticated OANDA account/feed.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping

from atlasquant_fx_universe import OFFICIAL_PAIRS
from atlasquant_fx_m15_candle_lab import (
    SCHEMA as M15_SCHEMA, _blocked as _refuse, analyze_m15_candle_export,
)

ADAPTER = "ATLASQUANT_OANDA_V20_M15_EXPORT_OFFLINE_LAB_V1"
SOURCE_CLAIM = "OANDA_V20_FORMAT_UNVERIFIED_OFFLINE"
SENSITIVE_KEYS = frozenset({"token", "api_key", "access_token", "authorization", "password"})
ALLOWED_PAIRS = frozenset(OFFICIAL_PAIRS)


def analyze_oanda_m15_export(
    responses: Any, *, captured_at: str, now: datetime | None = None,
) -> dict[str, Any]:
    """Normalize 28 OANDA-shaped candle responses into the M15 LAB gate.

    The caller must supply responses from separate authorized, read-only GETs.
    This function never makes those calls and never reads credentials.
    A single trailing incomplete candle may be discarded; older incomplete
    candles, missing bid/ask or pairs, and wrong symbol orientation are refused.
    """
    if not isinstance(responses, (list, tuple)) or len(responses) != 28:
        return _refuse("OANDA_EXPORT_REQUIRES_28_RESPONSES")
    pairs: dict[str, dict[str, Any]] = {}
    for response in responses:
        if not isinstance(response, Mapping):
            return _refuse("OANDA_RESPONSE_INVALID")
        if SENSITIVE_KEYS.intersection(str(key).lower() for key in response):
            return _refuse("OANDA_SENSITIVE_FIELD_REJECTED")
        instrument = response.get("instrument")
        if not isinstance(instrument, str) or not instrument.isascii():
            return _refuse("OANDA_INSTRUMENT_INVALID")
        symbol = instrument.replace("_", "/")
        if symbol not in ALLOWED_PAIRS or instrument != symbol.replace("/", "_"):
            return _refuse("OANDA_INSTRUMENT_INVALID")
        if symbol in pairs:
            return _refuse("OANDA_DUPLICATE_INSTRUMENT")
        if response.get("granularity") != "M15":
            return _refuse("OANDA_GRANULARITY_INVALID")
        candles = response.get("candles")
        if not isinstance(candles, list) or not 2 <= len(candles) <= 5000:
            return _refuse("OANDA_CANDLE_HISTORY_INVALID")
        if any(
            not isinstance(c, Mapping) or
            SENSITIVE_KEYS.intersection(str(key).lower() for key in c)
            for c in candles
        ):
            return _refuse("OANDA_SENSITIVE_OR_INVALID_CANDLE")
        # OANDA may include its current open bar at the end. Discard only
        # that last bar; never turn an incomplete candle into a closed one.
        closed = candles[:-1] if isinstance(candles[-1], Mapping) and candles[-1].get("complete") is False else candles
        if len(closed) < 2 or any(
            not isinstance(c, Mapping) or c.get("complete") is not True
            for c in closed
        ):
            return _refuse("OANDA_INCOMPLETE_OR_MISSING_CLOSED_CANDLES")
        last_two = closed[-2:]
        # Strip all unneeded fields (including volume and midpoint), and
        # preserve source string prices for downstream numeric checks.
        pairs[symbol] = {
            "source_claim": SOURCE_CLAIM,
            "granularity": "M15",
            "candles": [
                {
                    "time": c.get("time"),
                    "complete": c.get("complete"),
                    "bid": c.get("bid"),
                    "ask": c.get("ask"),
                }
                for c in last_two
            ],
        }
    payload = {
        "schema": M15_SCHEMA, "state": "OFFLINE_RESEARCH",
        "kind": "MARKET_CANDLE_EXPORT", "source_claim": SOURCE_CLAIM,
        "captured_at": captured_at, "pairs": pairs,
    }
    out = analyze_m15_candle_export(payload, now=now)
    out["offline_adapter"] = ADAPTER
    return out


__all__ = ["ADAPTER", "SOURCE_CLAIM", "analyze_oanda_m15_export"]
