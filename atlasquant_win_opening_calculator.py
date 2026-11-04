"""Pure WIN opening research calculator. No quotes, orders or provider calls.

Signed % changes: iron + oil - vix. Experimental thresholds, never a signal.
"""
from __future__ import annotations
from math import isfinite
from typing import Any


def _percentage(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, str):
        text = value.strip().replace("%", "").replace(",", ".")
        if not text:
            return None
        value = text
    try:
        number = float(value)
    except (ValueError, TypeError, OverflowError):
        return None
    return number if isfinite(number) and abs(number) <= 100 else None


def calculate_win_opening(*, vix_pct: Any, iron_pct: Any, oil_pct: Any) -> dict | None:
    """Return a preliminary filter, or None for malformed/absent inputs."""
    vix = _percentage(vix_pct)
    iron = _percentage(iron_pct)
    oil = _percentage(oil_pct)
    if vix is None or iron is None or oil is None:
        return None
    score = round(iron + oil - vix, 4)
    magnitude = abs(score)
    intensity = ("Indefinido" if magnitude < 1.5 else
                 "Fraco" if magnitude < 2.5 else
                 "Moderado" if magnitude <= 4.5 else "Forte")
    side = ("Neutro" if magnitude < 1.5 else
            "Alta" if score > 0 else "Baixa")
    return {
        "vix": vix, "iron": iron, "oil": oil,
        "score": score, "level": intensity, "side": side,
        "kind": "PRELIMINARY_RESEARCH_ONLY",
        "trade_signal": False, "accuracy_verified": False,
    }


__all__ = ["calculate_win_opening"]
