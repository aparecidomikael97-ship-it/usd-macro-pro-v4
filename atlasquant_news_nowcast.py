"""AtlasQuant pre-news empirical nowcast foundation.

The module estimates whether an economic release may print ABOVE / INLINE /
BELOW consensus from pre-release evidence and historical analogs.

Important:
- it predicts the DATA RELEASE, not the market reaction;
- it uses only observations timestamped before the forecast;
- it returns no distribution when the historical sample is insufficient;
- its percentages are empirical research estimates, never profit probabilities.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from math import isfinite
from typing import Any, Iterable, Mapping, Sequence

SCHEMA="ATLASQUANT_NEWS_NOWCAST_V1"
OUTCOMES=("BELOW","INLINE","ABOVE")


def _utc(value:datetime)->datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _finite(name:str,value:Any)->float:
    out=float(value)
    if not isfinite(out):
        raise ValueError(f"{name} deve ser finito")
    return out


@dataclass(frozen=True)
class LeadingSignal:
    name:str
    observed_at:datetime
    direction_score:float
    weight:float=1.0
    source:str=""
    detail:str=""


@dataclass(frozen=True)
class HistoricalRelease:
    indicator:str
    scheduled_at:datetime
    captured_at:datetime
    consensus:float
    actual:float
    signal_score:float
    tolerance:float=0.0
    unit:str=""


def classify_surprise(actual:Any,consensus:Any,tolerance:Any=0.0)->str:
    a=_finite("actual",actual)
    c=_finite("consensus",consensus)
    tol=_finite("tolerance",tolerance)
    if tol<0:
        raise ValueError("tolerance não pode ser negativo")
    delta=a-c
    if abs(delta)<=tol:
        return "INLINE"
    return "ABOVE" if delta>0 else "BELOW"


def validate_historical_release(release:HistoricalRelease)->HistoricalRelease:
    indicator=str(release.indicator or "").strip()
    if not indicator:
        raise ValueError("indicator histórico é obrigatório")
    scheduled=_utc(release.scheduled_at)
    captured=_utc(release.captured_at)
    if captured>=scheduled:
        raise ValueError("captured_at histórico deve ser anterior ao scheduled_at")
    consensus=_finite("consensus",release.consensus)
    actual=_finite("actual",release.actual)
    score=_finite("signal_score",release.signal_score)
    tolerance=_finite("tolerance",release.tolerance)
    if not -1<=score<=1:
        raise ValueError("signal_score deve estar entre -1 e 1")
    if tolerance<0:
        raise ValueError("tolerance não pode ser negativo")
    return HistoricalRelease(
        indicator=indicator,
        scheduled_at=scheduled,
        captured_at=captured,
        consensus=consensus,
        actual=actual,
        signal_score=score,
        tolerance=tolerance,
        unit=str(release.unit or ""),
    )


def combine_leading_signals(
    signals:Sequence[LeadingSignal]|None,
    *,
    captured_at:datetime,
)->dict[str,Any]:
    capture=_utc(captured_at)
    valid=[]
    total_weight=0.0
    weighted=0.0
    for raw in list(signals or []):
        observed=_utc(raw.observed_at)
        if observed>capture:
            raise ValueError(
                f"sinal antecedente {raw.name!r} foi observado depois do snapshot pré-release"
            )
        score=_finite("direction_score",raw.direction_score)
        weight=_finite("weight",raw.weight)
        if not -1<=score<=1:
            raise ValueError("direction_score deve estar entre -1 e 1")
        if weight<=0:
            raise ValueError("weight deve ser positivo")
        total_weight+=weight
        weighted+=score*weight
        valid.append({
            **asdict(raw),
            "observed_at":observed.isoformat(),
            "direction_score":score,
            "weight":weight,
        })
    if not valid or total_weight<=0:
        return {
            "state":"INSUFFICIENT_SIGNALS",
            "signal_score":None,
            "signals":[],
            "captured_at":capture.isoformat(),
            "lookahead_used":False,
        }
    return {
        "state":"READY",
        "signal_score":round(weighted/total_weight,6),
        "signals":valid,
        "captured_at":capture.isoformat(),
        "lookahead_used":False,
    }


def _history_before(
    history:Iterable[HistoricalRelease]|None,
    *,
    indicator:str,
    captured_at:datetime,
)->list[HistoricalRelease]:
    capture=_utc(captured_at)
    target=str(indicator or "").strip().casefold()
    rows=[]
    for raw in history or []:
        item=validate_historical_release(raw)
        if str(item.indicator).strip().casefold()!=target:
            continue
        # The release itself must already have happened before this forecast was captured.
        if item.scheduled_at>=capture:
            continue
        rows.append(item)
    return sorted(rows,key=lambda x:x.scheduled_at)


def _smoothed_probabilities(
    rows:Sequence[HistoricalRelease],
    *,
    alpha:float,
)->dict[str,float]:
    if alpha<0:
        raise ValueError("alpha não pode ser negativo")
    counts={name:0 for name in OUTCOMES}
    for row in rows:
        counts[classify_surprise(row.actual,row.consensus,row.tolerance)]+=1
    denom=len(rows)+alpha*len(OUTCOMES)
    if denom<=0:
        return {}
    return {
        key:round((counts[key]+alpha)/denom,6)
        for key in OUTCOMES
    }


def build_empirical_nowcast_from_score(
    *,
    indicator:str,
    consensus:Any,
    captured_at:datetime,
    signal_score:Any,
    history:Iterable[HistoricalRelease]|None,
    min_history:int=40,
    min_analogs:int=20,
    bandwidth:float=0.25,
    alpha:float=1.0,
)->dict[str,Any]:
    capture=_utc(captured_at)
    consensus_value=_finite("consensus",consensus)
    score=_finite("signal_score",signal_score)
    if not -1<=score<=1:
        raise ValueError("signal_score deve estar entre -1 e 1")
    min_history=max(1,int(min_history))
    min_analogs=max(1,int(min_analogs))
    bandwidth=_finite("bandwidth",bandwidth)
    if bandwidth<0:
        raise ValueError("bandwidth não pode ser negativo")

    eligible=_history_before(history,indicator=indicator,captured_at=capture)
    if len(eligible)<min_history:
        return {
            "schema":SCHEMA,
            "indicator":str(indicator),
            "state":"INSUFFICIENT_HISTORY",
            "captured_at":capture.isoformat(),
            "consensus":consensus_value,
            "signal_score":score,
            "historical_samples":len(eligible),
            "analog_samples":0,
            "probabilities":None,
            "estimate":None,
            "calibrated":False,
            "lookahead_used":False,
            "automatic_execution":False,
            "interpretation":(
                "Amostra histórica insuficiente. O AtlasQuant não fabrica percentuais "
                "nem estimativa pré-notícia sem evidência mínima."
            ),
        }

    within=[
        row for row in eligible
        if abs(row.signal_score-score)<=bandwidth
    ]
    analog_method="BAND"
    if len(within)<min_analogs:
        analog_method="NEAREST"
        within=sorted(
            eligible,
            key=lambda row:(abs(row.signal_score-score),row.scheduled_at),
        )[:min(min_analogs,len(eligible))]

    probabilities=_smoothed_probabilities(within,alpha=alpha)
    surprises=[row.actual-row.consensus for row in within]
    mean_surprise=sum(surprises)/len(surprises) if surprises else 0.0
    estimate=consensus_value+mean_surprise
    max_p=max(probabilities.values()) if probabilities else 0.0
    leaders=[k for k,v in probabilities.items() if abs(v-max_p)<1e-12]
    top_class=leaders[0] if len(leaders)==1 else "TIE"

    return {
        "schema":SCHEMA,
        "indicator":str(indicator),
        "state":"RESEARCH_ESTIMATE",
        "captured_at":capture.isoformat(),
        "consensus":consensus_value,
        "signal_score":round(score,6),
        "historical_samples":len(eligible),
        "analog_samples":len(within),
        "analog_method":analog_method,
        "bandwidth":bandwidth,
        "probabilities":probabilities,
        "top_class":top_class,
        "estimate":round(float(estimate),6),
        "mean_historical_surprise":round(float(mean_surprise),6),
        "calibrated":False,
        "profit_probability":None,
        "market_reaction_predicted":False,
        "lookahead_used":False,
        "automatic_execution":False,
        "interpretation":(
            "Percentuais = frequência empírica suavizada de ABOVE/INLINE/BELOW em "
            "análogos históricos pré-release. Não são probabilidade de lucro nem "
            "garantia da reação do mercado."
        ),
    }


def build_empirical_nowcast(
    *,
    indicator:str,
    consensus:Any,
    captured_at:datetime,
    signals:Sequence[LeadingSignal]|None,
    history:Iterable[HistoricalRelease]|None,
    min_history:int=40,
    min_analogs:int=20,
    bandwidth:float=0.25,
    alpha:float=1.0,
)->dict[str,Any]:
    combined=combine_leading_signals(signals,captured_at=captured_at)
    if combined["state"]!="READY":
        return {
            "schema":SCHEMA,
            "indicator":str(indicator),
            "state":"INSUFFICIENT_SIGNALS",
            "captured_at":_utc(captured_at).isoformat(),
            "consensus":_finite("consensus",consensus),
            "probabilities":None,
            "estimate":None,
            "calibrated":False,
            "profit_probability":None,
            "market_reaction_predicted":False,
            "lookahead_used":False,
            "automatic_execution":False,
            "leading_signals":combined,
        }
    out=build_empirical_nowcast_from_score(
        indicator=indicator,
        consensus=consensus,
        captured_at=captured_at,
        signal_score=combined["signal_score"],
        history=history,
        min_history=min_history,
        min_analogs=min_analogs,
        bandwidth=bandwidth,
        alpha=alpha,
    )
    out["leading_signals"]=combined
    return out


__all__=[
    "SCHEMA","OUTCOMES","LeadingSignal","HistoricalRelease",
    "classify_surprise","validate_historical_release","combine_leading_signals",
    "build_empirical_nowcast_from_score","build_empirical_nowcast",
]
