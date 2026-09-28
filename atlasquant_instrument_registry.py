"""AtlasQuant canonical market universe.

P0 foundation: one deterministic source of truth for the 28 unique FX pairs
formed by USD, EUR, GBP, JPY, CHF, CAD, AUD and NZD.

This module does not fetch prices and does not create trading signals.
Provider-specific symbols belong in adapters, never in strategy code.
"""
from __future__ import annotations

from dataclasses import dataclass

FX_CURRENCIES: tuple[str, ...] = ("USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD")

# Conventional market orientation. Exactly C(8, 2) == 28 unique pairs.
FX_28: tuple[str, ...] = (
    "EURUSD", "GBPUSD", "AUDUSD", "NZDUSD", "USDJPY", "USDCHF", "USDCAD",
    "EURGBP", "EURJPY", "EURCHF", "EURCAD", "EURAUD", "EURNZD",
    "GBPJPY", "GBPCHF", "GBPCAD", "GBPAUD", "GBPNZD",
    "AUDJPY", "AUDCHF", "AUDCAD", "AUDNZD",
    "NZDJPY", "NZDCHF", "NZDCAD",
    "CADJPY", "CADCHF", "CHFJPY",
)

@dataclass(frozen=True)
class Instrument:
    canonical_id: str
    symbol: str
    market: str
    base: str
    quote: str

def _instrument(symbol: str) -> Instrument:
    if len(symbol) != 6:
        raise ValueError(f"Invalid FX symbol: {symbol!r}")
    base, quote = symbol[:3], symbol[3:]
    if base not in FX_CURRENCIES or quote not in FX_CURRENCIES or base == quote:
        raise ValueError(f"Invalid AtlasQuant FX pair: {symbol!r}")
    return Instrument(
        canonical_id=f"FX:{symbol}",
        symbol=symbol,
        market="FOREX",
        base=base,
        quote=quote,
    )

FX_INSTRUMENTS: tuple[Instrument, ...] = tuple(_instrument(s) for s in FX_28)
FX_BY_SYMBOL: dict[str, Instrument] = {i.symbol: i for i in FX_INSTRUMENTS}
FX_BY_ID: dict[str, Instrument] = {i.canonical_id: i for i in FX_INSTRUMENTS}

def normalize_fx_symbol(value: str) -> str:
    """Normalize EUR/USD, EUR-USD, eurusd and FX:EURUSD to EURUSD."""
    raw = str(value or "").strip().upper()
    if raw.startswith("FX:"):
        raw = raw[3:]
    for token in ("/", "-", "_", " "):
        raw = raw.replace(token, "")
    if raw not in FX_BY_SYMBOL:
        raise ValueError(f"Unsupported FX pair: {value!r}")
    return raw

def get_fx_instrument(value: str) -> Instrument:
    return FX_BY_SYMBOL[normalize_fx_symbol(value)]

def validate_registry() -> None:
    if len(FX_CURRENCIES) != 8:
        raise RuntimeError("AtlasQuant FX registry must contain exactly 8 currencies")
    if len(FX_28) != 28 or len(set(FX_28)) != 28:
        raise RuntimeError("AtlasQuant FX registry must contain exactly 28 unique pairs")
    unordered = {frozenset((i.base, i.quote)) for i in FX_INSTRUMENTS}
    if len(unordered) != 28:
        raise RuntimeError("Duplicate/inverse currency combination in FX registry")
    expected = len(FX_CURRENCIES) * (len(FX_CURRENCIES) - 1) // 2
    if len(unordered) != expected:
        raise RuntimeError(f"FX registry incomplete: expected {expected}, got {len(unordered)}")

validate_registry()
