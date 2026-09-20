"""AtlasQuant market behavior shift detector.

Compares observable market-behavior statistics between a baseline and a recent
window. The output is a regime/research alert only; it does not infer hidden
institutional intent or identify where institutions "will enter".
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from math import isfinite

SCHEMA="ATLASQUANT_BEHAVIOR_SHIFT_V1"


@dataclass(frozen=True)
class BehaviorStats:
    sample_size: int
    london_expansion_pct: float
    new_york_expansion_pct: float
    sweep_followthrough_pct: float
    reversal_after_sweep_pct: float
    level_reaction_pct: float
    average_range: float


def _finite(name:str,value:float)->float:
    out=float(value)
    if not isfinite(out):
        raise ValueError(f"{name} deve ser finito")
    return out


def _validated(stats:BehaviorStats)->BehaviorStats:
    if int(stats.sample_size)<0:
        raise ValueError("sample_size não pode ser negativo")
    pct_fields=(
        "london_expansion_pct",
        "new_york_expansion_pct",
        "sweep_followthrough_pct",
        "reversal_after_sweep_pct",
        "level_reaction_pct",
    )
    values={}
    for name in pct_fields:
        v=_finite(name,getattr(stats,name))
        if not 0 <= v <= 100:
            raise ValueError(f"{name} deve estar entre 0 e 100")
        values[name]=v
    average_range=_finite("average_range",stats.average_range)
    if average_range<0:
        raise ValueError("average_range não pode ser negativo")
    return BehaviorStats(
        sample_size=int(stats.sample_size),
        average_range=average_range,
        **values,
    )


def detect_behavior_shift(
    baseline:BehaviorStats,
    recent:BehaviorStats,
    *,
    min_baseline_samples:int=50,
    min_recent_samples:int=20,
    pct_shift_threshold:float=15.0,
    range_relative_threshold:float=0.25,
)->dict[str,object]:
    base=_validated(baseline)
    cur=_validated(recent)
    enough=base.sample_size>=int(min_baseline_samples) and cur.sample_size>=int(min_recent_samples)
    changes=[]
    fields=(
        ("london_expansion_pct","London expansion"),
        ("new_york_expansion_pct","New York expansion"),
        ("sweep_followthrough_pct","sweep follow-through"),
        ("reversal_after_sweep_pct","reversal after sweep"),
        ("level_reaction_pct","reaction at mapped levels"),
    )
    for field,label in fields:
        delta=round(getattr(cur,field)-getattr(base,field),2)
        if enough and abs(delta)>=float(pct_shift_threshold):
            changes.append({
                "metric":field,
                "label":label,
                "baseline":getattr(base,field),
                "recent":getattr(cur,field),
                "delta":delta,
                "direction":"UP" if delta>0 else "DOWN",
            })

    range_delta=cur.average_range-base.average_range
    range_relative=None
    if base.average_range>0:
        range_relative=range_delta/base.average_range
        if enough and abs(range_relative)>=float(range_relative_threshold):
            changes.append({
                "metric":"average_range",
                "label":"average range",
                "baseline":base.average_range,
                "recent":cur.average_range,
                "delta":round(range_delta,6),
                "relative_change_pct":round(range_relative*100.0,2),
                "direction":"UP" if range_relative>0 else "DOWN",
            })

    if not enough:
        state="INSUFFICIENT_SAMPLE"
    elif len(changes)>=2:
        state="MEANINGFUL_SHIFT_REVIEW"
    elif len(changes)==1:
        state="SINGLE_METRIC_SHIFT"
    else:
        state="STABLE_WITHIN_THRESHOLDS"

    return {
        "schema":SCHEMA,
        "state":state,
        "sample_sufficient":enough,
        "baseline":asdict(base),
        "recent":asdict(cur),
        "changes":changes,
        "change_count":len(changes),
        "institutional_intent_inferred":False,
        "automatic_strategy_change":False,
        "interpretation":(
            "Mudanças refletem estatísticas observáveis da amostra. Elas podem sugerir "
            "mudança de regime/comportamento, mas não revelam intenção oculta de instituições."
        ),
    }


__all__=["SCHEMA","BehaviorStats","detect_behavior_shift"]
