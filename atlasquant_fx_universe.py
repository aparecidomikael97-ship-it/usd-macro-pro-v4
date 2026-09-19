"""AtlasQuant FX universe.

Pure helpers for the G8 currency universe and its 28 unique spot-FX crosses.
This module deliberately separates relative-strength arithmetic from execution
logic. A directional score is an internal ranking score, not a probability of
profit.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Iterable
import math

CURRENCIES = ("USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD")

# Conventional market orientation. Every unordered G8 currency pair appears once.
OFFICIAL_PAIRS = (
    "EUR/USD", "GBP/USD", "AUD/USD", "NZD/USD", "USD/JPY", "USD/CHF", "USD/CAD",
    "EUR/GBP", "EUR/JPY", "EUR/CHF", "EUR/CAD", "EUR/AUD", "EUR/NZD",
    "GBP/JPY", "GBP/CHF", "GBP/CAD", "GBP/AUD", "GBP/NZD",
    "AUD/JPY", "AUD/CHF", "AUD/CAD", "AUD/NZD",
    "NZD/JPY", "NZD/CHF", "NZD/CAD",
    "CAD/JPY", "CAD/CHF", "CHF/JPY",
)


@dataclass(frozen=True)
class PairView:
    pair: str
    base: str
    quote: str
    base_strength: float
    quote_strength: float
    differential: float
    side: str
    directional_score: float


def split_pair(pair: str) -> tuple[str, str]:
    text = str(pair).strip().upper().replace("-", "/")
    parts = text.split("/")
    if len(parts) != 2 or parts[0] not in CURRENCIES or parts[1] not in CURRENCIES or parts[0] == parts[1]:
        raise ValueError(f"Par FX G8 inválido: {pair!r}")
    return parts[0], parts[1]


def invert_pair(pair: str) -> str:
    base, quote = split_pair(pair)
    return f"{quote}/{base}"


def validate_strengths(strengths: Mapping[str, float]) -> dict[str, float]:
    out: dict[str, float] = {}
    missing = [c for c in CURRENCIES if c not in strengths]
    if missing:
        raise ValueError(f"Força ausente para: {', '.join(missing)}")
    for currency in CURRENCIES:
        try:
            value = float(strengths[currency])
        except Exception as exc:
            raise ValueError(f"Força inválida para {currency}") from exc
        if not math.isfinite(value) or not (0.0 <= value <= 100.0):
            raise ValueError(f"Força de {currency} deve estar entre 0 e 100")
        out[currency] = value
    return out


def pair_differential(pair: str, strengths: Mapping[str, float]) -> float:
    s = validate_strengths(strengths)
    base, quote = split_pair(pair)
    return s[base] - s[quote]


def classify_side(differential: float, neutral_band: float = 5.0) -> str:
    d = float(differential)
    band = max(0.0, float(neutral_band))
    if d > band:
        return "BUY"
    if d < -band:
        return "SELL"
    return "NEUTRAL"


def directional_score(differential: float, full_scale_diff: float = 40.0) -> float:
    """Convert absolute strength imbalance into 0..100 ranking intensity.

    It is intentionally *not* named confidence/probability; calibration against
    forward results belongs to the Performance Lab.
    """
    scale = max(1e-9, float(full_scale_diff))
    return round(min(100.0, abs(float(differential)) / scale * 100.0), 2)


def evaluate_pair(pair: str, strengths: Mapping[str, float], neutral_band: float = 5.0) -> PairView:
    s = validate_strengths(strengths)
    base, quote = split_pair(pair)
    diff = s[base] - s[quote]
    return PairView(
        pair=f"{base}/{quote}", base=base, quote=quote,
        base_strength=s[base], quote_strength=s[quote],
        differential=round(diff, 4), side=classify_side(diff, neutral_band),
        directional_score=directional_score(diff),
    )


def rank_pairs(strengths: Mapping[str, float], neutral_band: float = 5.0,
               pairs: Iterable[str] = OFFICIAL_PAIRS) -> list[PairView]:
    rows = [evaluate_pair(p, strengths, neutral_band) for p in pairs]
    return sorted(rows, key=lambda r: (r.directional_score, abs(r.differential)), reverse=True)


def universe_integrity() -> dict[str, object]:
    unordered = {frozenset(split_pair(p)) for p in OFFICIAL_PAIRS}
    return {
        "currency_count": len(CURRENCIES),
        "pair_count": len(OFFICIAL_PAIRS),
        "unique_unordered_pairs": len(unordered),
        "valid": len(CURRENCIES) == 8 and len(OFFICIAL_PAIRS) == 28 and len(unordered) == 28,
    }
