"""Walk-forward backtest for AtlasQuant economic-release nowcasts.

Every forecast is reconstructed at the target release's captured_at timestamp
using only releases that had already occurred. This prevents future releases
from leaking into the historical estimate.
"""
from __future__ import annotations

from math import isfinite, log
from typing import Any, Iterable, Sequence

from atlasquant_news_nowcast import (
    OUTCOMES,
    HistoricalRelease,
    build_empirical_nowcast_from_score,
    classify_surprise,
    validate_historical_release,
)

SCHEMA="ATLASQUANT_NEWS_BACKTEST_V1"


def _finite(value:Any)->float|None:
    try:
        out=float(value)
        return out if isfinite(out) else None
    except Exception:
        return None


def _top_class(probabilities:dict[str,float]|None)->str:
    p=dict(probabilities or {})
    if not p:
        return "NONE"
    high=max(p.values())
    winners=[name for name in OUTCOMES if abs(float(p.get(name,0))-high)<1e-12]
    return winners[0] if len(winners)==1 else "TIE"


def multiclass_brier(
    probabilities:dict[str,float],
    actual_class:str,
)->float:
    if actual_class not in OUTCOMES:
        raise ValueError("actual_class inválido")
    values=[]
    for label in OUTCOMES:
        p=float(probabilities.get(label,0.0))
        if not 0<=p<=1:
            raise ValueError("probabilidades devem ficar entre 0 e 1")
        y=1.0 if label==actual_class else 0.0
        values.append((p-y)**2)
    # Mean across classes -> 0 perfect, bounded in [0,1].
    return sum(values)/len(values)


def _summarize_forecasts(rows:Sequence[dict[str,Any]])->dict[str,Any]:
    if not rows:
        return {
            "forecast_samples":0,
            "class_hits":0,
            "class_accuracy_pct":None,
            "average_brier":None,
            "average_top_confidence_pct":None,
            "calibration_gap_abs_pct":None,
            "numeric_mae":None,
        }
    hits=sum(1 for row in rows if row.get("class_hit"))
    briers=[float(row["brier"]) for row in rows if _finite(row.get("brier")) is not None]
    confidences=[
        float(row["top_confidence"])
        for row in rows
        if _finite(row.get("top_confidence")) is not None
    ]
    errors=[
        abs(float(row["estimate_error"]))
        for row in rows
        if _finite(row.get("estimate_error")) is not None
    ]
    accuracy=100.0*hits/len(rows)
    avg_conf=(100.0*sum(confidences)/len(confidences)) if confidences else None
    return {
        "forecast_samples":len(rows),
        "class_hits":hits,
        "class_accuracy_pct":round(accuracy,2),
        "average_brier":None if not briers else round(sum(briers)/len(briers),6),
        "average_top_confidence_pct":None if avg_conf is None else round(avg_conf,2),
        "calibration_gap_abs_pct":(
            None if avg_conf is None else round(abs(accuracy-avg_conf),2)
        ),
        "numeric_mae":None if not errors else round(sum(errors)/len(errors),6),
    }


def walk_forward_news_backtest(
    releases:Iterable[HistoricalRelease]|None,
    *,
    min_history:int=40,
    min_analogs:int=20,
    bandwidth:float=0.25,
    alpha:float=1.0,
)->dict[str,Any]:
    validated=[validate_historical_release(row) for row in releases or []]
    validated.sort(key=lambda row:row.scheduled_at)
    forecasts=[]
    skipped=[]

    for target in validated:
        nowcast=build_empirical_nowcast_from_score(
            indicator=target.indicator,
            consensus=target.consensus,
            captured_at=target.captured_at,
            signal_score=target.signal_score,
            history=validated,
            min_history=min_history,
            min_analogs=min_analogs,
            bandwidth=bandwidth,
            alpha=alpha,
        )
        if nowcast.get("state")!="RESEARCH_ESTIMATE":
            skipped.append({
                "indicator":target.indicator,
                "scheduled_at":target.scheduled_at.isoformat(),
                "reason":nowcast.get("state"),
                "historical_samples":nowcast.get("historical_samples",0),
            })
            continue

        actual_class=classify_surprise(
            target.actual,target.consensus,target.tolerance
        )
        probabilities=dict(nowcast["probabilities"] or {})
        predicted=_top_class(probabilities)
        top_conf=max(probabilities.values()) if probabilities else None
        estimate=_finite(nowcast.get("estimate"))
        estimate_error=(
            None if estimate is None else float(target.actual)-estimate
        )
        forecasts.append({
            "indicator":target.indicator,
            "scheduled_at":target.scheduled_at.isoformat(),
            "captured_at":target.captured_at.isoformat(),
            "consensus":target.consensus,
            "actual":target.actual,
            "tolerance":target.tolerance,
            "signal_score":target.signal_score,
            "predicted_class":predicted,
            "actual_class":actual_class,
            "class_hit":predicted==actual_class,
            "top_confidence":top_conf,
            "p_below":probabilities.get("BELOW"),
            "p_inline":probabilities.get("INLINE"),
            "p_above":probabilities.get("ABOVE"),
            "estimate":estimate,
            "estimate_error":estimate_error,
            "brier":multiclass_brier(probabilities,actual_class),
            "training_samples":nowcast.get("historical_samples"),
            "analog_samples":nowcast.get("analog_samples"),
            "analog_method":nowcast.get("analog_method"),
            "lookahead_used":False,
        })

    overall=_summarize_forecasts(forecasts)
    per_indicator={}
    for indicator in sorted({row["indicator"] for row in forecasts}):
        group=[row for row in forecasts if row["indicator"]==indicator]
        per_indicator[indicator]=_summarize_forecasts(group)

    return {
        "schema":SCHEMA,
        "releases":len(validated),
        "forecast_samples":overall["forecast_samples"],
        "skipped_samples":len(skipped),
        "overall":overall,
        "per_indicator":per_indicator,
        "forecasts":forecasts,
        "skipped":skipped,
        "lookahead_used":False,
        "market_reaction_scored":False,
        "profit_probability":None,
        "automatic_execution":False,
        "interpretation":(
            "O backtest mede previsão do dado ABOVE/INLINE/BELOW e erro numérico. "
            "A reação do preço é uma tarefa separada; acerto do dado não implica "
            "acerto do mercado ou lucro."
        ),
    }


def monthly_news_scores(backtest:dict[str,Any])->list[dict[str,Any]]:
    """Group walk-forward forecasts by release month ('8 of 10' style)."""
    groups={}
    for raw in list(backtest.get("forecasts",[]) or []):
        row=dict(raw)
        stamp=str(row.get("scheduled_at") or "")
        month=stamp[:7] if len(stamp)>=7 else "UNKNOWN"
        groups.setdefault(month,[]).append(row)
    out=[]
    for month in sorted(groups):
        rows=groups[month]
        summary=_summarize_forecasts(rows)
        out.append({
            "month":month,
            "samples":summary["forecast_samples"],
            "hits":summary["class_hits"],
            "score_text":f"{summary['class_hits']} de {summary['forecast_samples']}",
            "class_accuracy_pct":summary["class_accuracy_pct"],
            "average_brier":summary["average_brier"],
            "average_top_confidence_pct":summary["average_top_confidence_pct"],
            "calibration_gap_abs_pct":summary["calibration_gap_abs_pct"],
            "interpretation":"Acerto da classe do dado; não é taxa de gain.",
        })
    return out


def simple_month_score(backtest:dict[str,Any])->dict[str,Any]:
    """Human-readable '8 of 10' score without converting it into a trade claim."""
    overall=dict(backtest.get("overall",{}) or {})
    samples=int(overall.get("forecast_samples",0) or 0)
    hits=int(overall.get("class_hits",0) or 0)
    return {
        "hits":hits,
        "samples":samples,
        "text":f"{hits} de {samples}" if samples else "sem amostra",
        "accuracy_pct":overall.get("class_accuracy_pct"),
        "interpretation":"Taxa de classificação do dado; não é taxa de gain.",
    }


__all__=[
    "SCHEMA","multiclass_brier","walk_forward_news_backtest",
    "monthly_news_scores","simple_month_score",
]
