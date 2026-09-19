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
    try:
        max_age=float(max_age_minutes); abs_tol=float(absolute_tolerance); rel_tol=float(relative_tolerance)
        min_src=int(min_sources)
        params_valid=(math.isfinite(max_age) and max_age>=0 and math.isfinite(abs_tol) and abs_tol>=0 and math.isfinite(rel_tol) and rel_tol>=0 and min_src>=1 and not isinstance(min_sources,bool))
    except Exception:
        params_valid=False; max_age=abs_tol=rel_tol=0.0; min_src=1
    if not params_valid:
        return {"confirmed":False,"golden_value":None,"quality":0.0,"reason":"Parâmetros de reconciliação inválidos","valid_sources":[],"rejected_sources":[]}
    valid: list[tuple[Observation, float]] = []
    rejected: list[str] = []
    seen_sources: set[str] = set()
    for obs in observations:
        try:
            value = float(obs.value)
            age = (ref - _utc(obs.observed_at)).total_seconds() / 60.0
        except Exception:
            rejected.append(str(getattr(obs, "source", "?")))
            continue
        source=str(obs.source or "").strip()
        if not source or source in seen_sources or not math.isfinite(value) or age < 0 or age >= max_age:
            rejected.append(source or "?")
            continue
        seen_sources.add(source)
        valid.append((obs, age))

    if len(valid) < min_src:
        return {
            "confirmed": False, "golden_value": None, "quality": 0.0,
            "reason": "Fontes válidas insuficientes", "valid_sources": [o.source for o, _ in valid],
            "rejected_sources": rejected,
        }

    values = [float(o.value) for o, _ in valid]
    center = float(median(values))
    tol = max(abs_tol, abs(center) * rel_tol)
    spread = max(values) - min(values)
    confirmed = spread <= tol + 1e-12
    freshness_penalty = min(35.0, max(age for _, age in valid) / max(max_age, 1.0) * 35.0)
    disagreement_penalty = 0.0 if confirmed else min(60.0, spread / max(tol, 1e-12) * 20.0)
    source_bonus = min(10.0, (len(valid) - min_src) * 5.0)
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
