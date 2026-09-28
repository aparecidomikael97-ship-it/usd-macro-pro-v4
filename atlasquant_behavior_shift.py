"""AtlasQuant market behavior shift detector.

Compares observable statistics between a baseline window and a recent window.
The result is a research/regime description. It does not emit an order, infer
why a market changed, or authorize a strategy change.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from math import isfinite

SCHEMA = "ATLASQUANT_BEHAVIOR_SHIFT_V1"
_PCT_FIELDS = (
    "london_expansion_pct",
    "new_york_expansion_pct",
    "sweep_followthrough_pct",
    "reversal_after_sweep_pct",
    "level_reaction_pct",
)


def _exact_count(name: str, value: object, *, minimum: int) -> int:
    if type(value) is not int or value < minimum:
        raise ValueError(f"{name} deve ser int exato >= {minimum}")
    return value


def _finite_number(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} deve ser número finito")
    number = float(value)
    if not isfinite(number):
        raise ValueError(f"{name} deve ser número finito")
    return number


def _check_percent(name: str, value: object) -> float:
    number = _finite_number(name, value)
    if number < 0 or number > 100:
        raise ValueError(f"{name} deve estar entre 0 e 100")
    return number


@dataclass(frozen=True)
class BehaviorStats:
    sample_size: int
    london_expansion_pct: float
    new_york_expansion_pct: float
    sweep_followthrough_pct: float
    reversal_after_sweep_pct: float
    level_reaction_pct: float
    average_range: float

    def __post_init__(self) -> None:
        _exact_count("sample_size", self.sample_size, minimum=0)
        for name in _PCT_FIELDS:
            _check_percent(name, getattr(self, name))
        average_range = _finite_number("average_range", self.average_range)
        if average_range < 0:
            raise ValueError("average_range não pode ser negativo")


def _validated(stats: BehaviorStats) -> BehaviorStats:
    if not isinstance(stats, BehaviorStats):
        raise ValueError("baseline e recent devem ser BehaviorStats")
    return BehaviorStats(
        sample_size=stats.sample_size,
        london_expansion_pct=_check_percent("london_expansion_pct", stats.london_expansion_pct),
        new_york_expansion_pct=_check_percent("new_york_expansion_pct", stats.new_york_expansion_pct),
        sweep_followthrough_pct=_check_percent("sweep_followthrough_pct", stats.sweep_followthrough_pct),
        reversal_after_sweep_pct=_check_percent("reversal_after_sweep_pct", stats.reversal_after_sweep_pct),
        level_reaction_pct=_check_percent("level_reaction_pct", stats.level_reaction_pct),
        average_range=_finite_number("average_range", stats.average_range),
    )


def _require_thresholds(
    min_baseline_samples: object,
    min_recent_samples: object,
    pct_shift_threshold: object,
    range_relative_threshold: object,
) -> tuple[int, int, float, float]:
    baseline = _exact_count("min_baseline_samples", min_baseline_samples, minimum=1)
    recent = _exact_count("min_recent_samples", min_recent_samples, minimum=1)
    pct_threshold = _finite_number("pct_shift_threshold", pct_shift_threshold)
    if pct_threshold < 0 or pct_threshold > 100:
        raise ValueError("pct_shift_threshold deve estar entre 0 e 100")
    range_threshold = _finite_number("range_relative_threshold", range_relative_threshold)
    if range_threshold < 0:
        raise ValueError("range_relative_threshold não pode ser negativo")
    return baseline, recent, pct_threshold, range_threshold


def detect_behavior_shift(
    baseline: BehaviorStats,
    recent: BehaviorStats,
    *,
    min_baseline_samples: int = 50,
    min_recent_samples: int = 20,
    pct_shift_threshold: float = 15.0,
    range_relative_threshold: float = 0.25,
) -> dict[str, object]:
    """Compare two observed windows. Direction here is the metric delta, not an order."""
    min_baseline, min_recent, pct_threshold, range_threshold = _require_thresholds(
        min_baseline_samples,
        min_recent_samples,
        pct_shift_threshold,
        range_relative_threshold,
    )
    base = _validated(baseline)
    cur = _validated(recent)
    enough = base.sample_size >= min_baseline and cur.sample_size >= min_recent
    changes: list[dict[str, object]] = []
    fields = (
        ("london_expansion_pct", "London expansion"),
        ("new_york_expansion_pct", "New York expansion"),
        ("sweep_followthrough_pct", "sweep follow-through"),
        ("reversal_after_sweep_pct", "reversal after sweep"),
        ("level_reaction_pct", "reaction at mapped levels"),
    )
    for field, label in fields:
        delta = round(getattr(cur, field) - getattr(base, field), 2)
        if enough and abs(delta) >= pct_threshold:
            changes.append({
                "metric": field,
                "label": label,
                "baseline": getattr(base, field),
                "recent": getattr(cur, field),
                "delta": delta,
                "direction": "UP" if delta > 0 else "DOWN",
            })

    range_relative_calculable = base.average_range > 0
    range_relative_change_pct = None
    if range_relative_calculable:
        range_relative = (cur.average_range - base.average_range) / base.average_range
        range_relative_change_pct = round(range_relative * 100.0, 2)
        if enough and abs(range_relative) >= range_threshold:
            changes.append({
                "metric": "average_range",
                "label": "average range",
                "baseline": base.average_range,
                "recent": cur.average_range,
                "delta": round(cur.average_range - base.average_range, 6),
                "relative_change_pct": range_relative_change_pct,
                "direction": "UP" if range_relative > 0 else "DOWN",
            })

    if not enough:
        state = "INSUFFICIENT_SAMPLE"
    elif len(changes) >= 2:
        state = "MEANINGFUL_SHIFT_REVIEW"
    elif len(changes) == 1:
        state = "SINGLE_METRIC_SHIFT"
    else:
        state = "STABLE_WITHIN_THRESHOLDS"

    return {
        "schema": SCHEMA,
        "state": state,
        "sample_sufficient": enough,
        "baseline_sample_size": base.sample_size,
        "recent_sample_size": cur.sample_size,
        "thresholds": {
            "min_baseline_samples": min_baseline,
            "min_recent_samples": min_recent,
            "pct_shift_threshold": pct_threshold,
            "range_relative_threshold": range_threshold,
        },
        "baseline": asdict(base),
        "recent": asdict(cur),
        "changes": changes,
        "change_count": len(changes),
        "range_relative_calculable": range_relative_calculable,
        "range_relative_change_pct": range_relative_change_pct,
        "institutional_intent_inferred": False,
        "automatic_strategy_change": False,
        "automatic_promotion": False,
        "execution_authorized": False,
        "real_trading_enabled": False,
        "interpretation": (
            "Mudanças refletem estatísticas observáveis da amostra. Elas podem sugerir "
            "mudança de regime/comportamento, mas não revelam intenção oculta de instituições. "
            "Isto não é sinal operacional e não autoriza execução."
        ),
    }


__all__ = ["SCHEMA", "BehaviorStats", "detect_behavior_shift"]
