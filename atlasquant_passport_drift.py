"""AtlasQuant Operational Passport drift monitor.

Compares consecutive persisted research snapshots for the same strategy.
Thresholds are descriptive review triggers, not trading rules. No strategy,
weight, Gate or execution setting is changed automatically.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Any, Iterable, Mapping

SCHEMA="ATLASQUANT_PASSPORT_DRIFT_V1"


@dataclass(frozen=True)
class DriftThresholds:
    expectancy_drop_r:float=0.15
    profit_factor_drop:float=0.25
    drawdown_increase_r:float=3.0
    data_quality_drop_pct:float=15.0
    paper_gap_abs_increase_r:float=0.15


def _finite(value:Any)->float|None:
    try:
        out=float(value)
        return out if isfinite(out) else None
    except Exception:
        return None


def passport_metric_snapshot(record:Mapping[str,Any]|None)->dict[str,Any]:
    row=dict(record or {})
    passport=dict(row.get("passport",{}) or {})
    observed=dict(passport.get("observed_metrics",{}) or {})
    evidence=dict(row.get("evidence",{}) or {})
    ladder=dict(evidence.get("evidence_ladder",{}) or {})
    comparison=dict(ladder.get("backtest_paper_comparison",{}) or {})
    return {
        "record_id":str(row.get("record_id") or ""),
        "strategy":str(row.get("strategy") or passport.get("strategy") or ""),
        "captured_at":str(row.get("captured_at") or ""),
        "source":str(row.get("source") or ""),
        "expectancy_r":_finite(observed.get("expectancy_r")),
        "profit_factor":_finite(observed.get("profit_factor")),
        "max_drawdown_r":_finite(observed.get("max_drawdown_r")),
        "trades":_finite(observed.get("trades")),
        "data_quality_pct":_finite(passport.get("data_quality_pct")),
        "paper_gap_r":_finite(comparison.get("expectancy_gap_r")),
        "evidence_state":str(ladder.get("state") or ""),
        "evidence_coverage_pct":_finite(ladder.get("evidence_coverage_pct")),
    }


def compare_passport_records(
    previous:Mapping[str,Any],
    current:Mapping[str,Any],
    *,
    thresholds:DriftThresholds|None=None,
)->dict[str,Any]:
    t=thresholds or DriftThresholds()
    before=passport_metric_snapshot(previous)
    after=passport_metric_snapshot(current)
    if not before["strategy"] or before["strategy"]!=after["strategy"]:
        raise ValueError("records must belong to the same strategy")

    deltas={}
    for field in (
        "expectancy_r","profit_factor","max_drawdown_r","data_quality_pct",
        "evidence_coverage_pct",
    ):
        a=before.get(field); b=after.get(field)
        deltas[field]=None if a is None or b is None else round(float(b)-float(a),4)

    if before["paper_gap_r"] is None or after["paper_gap_r"] is None:
        paper_gap_abs_change=None
    else:
        paper_gap_abs_change=round(
            abs(float(after["paper_gap_r"]))-abs(float(before["paper_gap_r"])),
            4,
        )

    alerts=[]
    exp_delta=deltas["expectancy_r"]
    if exp_delta is not None and exp_delta<=-abs(float(t.expectancy_drop_r)):
        alerts.append({
            "code":"EXPECTANCY_DROP",
            "detail":f"expectativa observada caiu {abs(exp_delta):.2f}R",
        })
    pf_delta=deltas["profit_factor"]
    if pf_delta is not None and pf_delta<=-abs(float(t.profit_factor_drop)):
        alerts.append({
            "code":"PROFIT_FACTOR_DROP",
            "detail":f"profit factor observado caiu {abs(pf_delta):.2f}",
        })
    dd_delta=deltas["max_drawdown_r"]
    if dd_delta is not None and dd_delta>=abs(float(t.drawdown_increase_r)):
        alerts.append({
            "code":"DRAWDOWN_INCREASE",
            "detail":f"drawdown observado aumentou {dd_delta:.2f}R",
        })
    quality_delta=deltas["data_quality_pct"]
    if quality_delta is not None and quality_delta<=-abs(float(t.data_quality_drop_pct)):
        alerts.append({
            "code":"DATA_QUALITY_DROP",
            "detail":f"qualidade de dados caiu {abs(quality_delta):.1f} pontos",
        })
    if (
        paper_gap_abs_change is not None
        and paper_gap_abs_change>=abs(float(t.paper_gap_abs_increase_r))
    ):
        alerts.append({
            "code":"PAPER_GAP_WIDENED",
            "detail":f"|gap Backtest×Paper| aumentou {paper_gap_abs_change:.2f}R",
        })
    if (
        before["evidence_state"]=="HUMAN_REVIEW_CANDIDATE"
        and after["evidence_state"]
        and after["evidence_state"]!="HUMAN_REVIEW_CANDIDATE"
    ):
        alerts.append({
            "code":"EVIDENCE_STATE_REGRESSED",
            "detail":(
                "estado de evidência saiu de HUMAN_REVIEW_CANDIDATE para "
                +str(after["evidence_state"])
            ),
        })

    return {
        "schema":SCHEMA,
        "strategy":after["strategy"],
        "previous":before,
        "current":after,
        "deltas":deltas,
        "paper_gap_abs_change_r":paper_gap_abs_change,
        "alerts":alerts,
        "review_required":bool(alerts),
        "automatic_strategy_change":False,
        "automatic_weight_change":False,
        "automatic_gate_change":False,
        "real_orders_enabled":False,
        "interpretation":(
            "Alertas indicam mudança observada entre snapshots de pesquisa. "
            "Eles não provam mudança institucional e não autorizam reotimização automática."
        ),
    }


def latest_passport_drift(
    records:Iterable[Mapping[str,Any]]|None,
    *,
    thresholds:DriftThresholds|None=None,
)->list[dict[str,Any]]:
    groups={}
    for raw in records or []:
        row=dict(raw)
        strategy=str(row.get("strategy") or "").strip()
        if strategy:
            groups.setdefault(strategy,[]).append(row)
    out=[]
    for strategy,rows in groups.items():
        ordered=sorted(
            rows,
            key=lambda x:(str(x.get("captured_at") or ""),str(x.get("record_id") or "")),
        )
        if len(ordered)<2:
            continue
        out.append(compare_passport_records(
            ordered[-2],
            ordered[-1],
            thresholds=thresholds,
        ))
    return sorted(out,key=lambda x:str(x.get("strategy") or ""))


def passport_drift_rows(
    records:Iterable[Mapping[str,Any]]|None,
)->list[dict[str,Any]]:
    rows=[]
    for drift in latest_passport_drift(records):
        rows.append({
            "strategy":drift["strategy"],
            "review_required":drift["review_required"],
            "expectancy_delta_r":drift["deltas"].get("expectancy_r"),
            "profit_factor_delta":drift["deltas"].get("profit_factor"),
            "drawdown_delta_r":drift["deltas"].get("max_drawdown_r"),
            "data_quality_delta_pct":drift["deltas"].get("data_quality_pct"),
            "paper_gap_abs_change_r":drift.get("paper_gap_abs_change_r"),
            "alerts":" · ".join(x["code"] for x in drift.get("alerts",[])),
        })
    return rows


__all__=[
    "SCHEMA",
    "DriftThresholds",
    "passport_metric_snapshot",
    "compare_passport_records",
    "latest_passport_drift",
    "passport_drift_rows",
]
