"""AtlasQuant Data Confidence Center / Golden Record helpers."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from statistics import median
from typing import Iterable
import math


@dataclass(frozen=True)
class Observation:
    source: str
    value: float
    observed_at: datetime
    revision: str | None = None


def _utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def reconcile_numeric(observations: Iterable[Observation], *, now: datetime | None = None,
                      max_age_minutes: float = 120.0, absolute_tolerance: float = 0.0,
                      relative_tolerance: float = 0.0025, min_sources: int = 2) -> dict[str, object]:
    ref = _utc(now or datetime.now(timezone.utc))
    valid: list[tuple[Observation, float]] = []
    rejected: list[str] = []
    for obs in observations:
        try:
            value = float(obs.value)
            age = (ref - _utc(obs.observed_at)).total_seconds() / 60.0
        except Exception:
            rejected.append(str(getattr(obs, "source", "?")))
            continue
        if not math.isfinite(value) or age < -1 or age > float(max_age_minutes):
            rejected.append(obs.source)
            continue
        valid.append((obs, age))

    if len(valid) < int(min_sources):
        return {
            "confirmed": False, "golden_value": None, "quality": 0.0,
            "reason": "Fontes válidas insuficientes", "valid_sources": [o.source for o, _ in valid],
            "rejected_sources": rejected,
        }

    values = [float(o.value) for o, _ in valid]
    center = float(median(values))
    tol = max(float(absolute_tolerance), abs(center) * float(relative_tolerance))
    spread = max(values) - min(values)
    confirmed = spread <= tol + 1e-12
    freshness_penalty = min(35.0, max(age for _, age in valid) / max(float(max_age_minutes), 1.0) * 35.0)
    disagreement_penalty = 0.0 if confirmed else min(60.0, spread / max(tol, 1e-12) * 20.0)
    source_bonus = min(10.0, (len(valid) - int(min_sources)) * 5.0)
    quality = max(0.0, min(100.0, 100.0 - freshness_penalty - disagreement_penalty + source_bonus))
    return {
        "confirmed": confirmed,
        "golden_value": center if confirmed else None,
        "candidate_value": center,
        "spread": spread,
        "tolerance": tol,
        "quality": round(quality, 2),
        "reason": "Fontes confirmadas" if confirmed else "Divergência entre fontes acima da tolerância",
        "valid_sources": [o.source for o, _ in valid],
        "rejected_sources": rejected,
    }
