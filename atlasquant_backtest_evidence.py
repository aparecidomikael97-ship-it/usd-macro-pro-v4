"""AtlasQuant consolidated Backtest evidence report.

Combines already-computed descriptive diagnostics for the five research
strategies into one neutral evidence view. It does not rank, recommend, forecast
or change any live decision gate.
"""
from __future__ import annotations

from typing import Any, Mapping
import json
import math

import pandas as pd

from atlasquant_strategy_comparator import STRATEGY_ORDER, STRATEGY_LABELS


def _value(row: Mapping[str, Any] | None, key: str, default: Any=None) -> Any:
    if not row:
        return default
    value=row.get(key,default)
    try:
        if pd.isna(value):
            return default
    except Exception:
        pass
    return value


def _row_for(df: pd.DataFrame | None, strategy: str) -> dict[str, Any]:
    if not isinstance(df,pd.DataFrame) or df.empty or "strategy" not in df.columns:
        return {}
    match=df[df["strategy"]==strategy]
    if match.empty:
        return {}
    return dict(match.iloc[0])


def _status_available(status: Any) -> bool:
    value=str(status or "").strip().upper()
    return bool(value and value not in {"INSUFFICIENT","NOT_RUN","N/D","NONE"})


def consolidated_evidence_frame(
    comparison: pd.DataFrame,
    stability_summary: pd.DataFrame,
    walkforward_summary: pd.DataFrame,
    friction_summary: pd.DataFrame,
    parameter_summary: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Build one neutral evidence row per strategy.

    Coverage means only whether each diagnostic had sufficient information to
    produce a non-INSUFFICIENT status. It is NOT a performance score.
    """
    rows=[]
    parameter_ran=isinstance(parameter_summary,pd.DataFrame) and not parameter_summary.empty

    for strategy in STRATEGY_ORDER:
        comp=_row_for(comparison,strategy)
        stab=_row_for(stability_summary,strategy)
        wf=_row_for(walkforward_summary,strategy)
        friction=_row_for(friction_summary,strategy)
        param=_row_for(parameter_summary,strategy) if parameter_ran else {}

        temporal_status=str(_value(stab,"stability_status","INSUFFICIENT"))
        walk_status=str(_value(wf,"walk_forward_status","INSUFFICIENT"))
        friction_status=str(_value(friction,"sensitivity_status","INSUFFICIENT"))
        parameter_status=(
            str(_value(param,"parameter_robustness_status","INSUFFICIENT"))
            if parameter_ran else "NOT_RUN"
        )

        statuses={
            "temporal":temporal_status,
            "walk_forward":walk_status,
            "friction":friction_status,
            "parameter":parameter_status,
        }
        available=sum(1 for x in statuses.values() if _status_available(x))
        total=len(statuses)

        if available==total:
            coverage="COMPLETE"
        elif available>0:
            coverage="PARTIAL"
        else:
            coverage="INSUFFICIENT"

        missing=[
            name for name,status in statuses.items()
            if not _status_available(status)
        ]

        rows.append({
            "strategy":strategy,
            "operacional":_value(comp,"operacional",STRATEGY_LABELS[strategy]),
            "trades":int(_value(comp,"trades",0) or 0),
            "win_rate_pct":_value(comp,"win_rate_pct"),
            "expectancy_r":_value(comp,"expectancy_r"),
            "net_r":_value(comp,"net_r"),
            "profit_factor":_value(comp,"profit_factor"),
            "max_drawdown_r":_value(comp,"max_drawdown_r"),
            "max_loss_streak":int(_value(comp,"max_loss_streak",0) or 0),
            "sample_tier":str(_value(comp,"sample_tier","N/D")),
            "temporal_status":temporal_status,
            "temporal_positive_fold_pct":_value(stab,"positive_fold_pct"),
            "walk_forward_status":walk_status,
            "oos_positive_pct":_value(wf,"positive_test_pct"),
            "avg_oos_expectancy_r":_value(wf,"avg_test_expectancy_r"),
            "avg_oos_delta_r":_value(wf,"avg_expectancy_delta_r"),
            "friction_status":friction_status,
            "friction_positive_scenario_pct":_value(friction,"positive_scenario_pct"),
            "first_nonpositive_friction_r":_value(friction,"first_nonpositive_total_friction_r"),
            "parameter_status":parameter_status,
            "parameter_positive_variant_pct":_value(param,"positive_variant_pct"),
            "evidence_diagnostics_available":available,
            "evidence_diagnostics_total":total,
            "evidence_coverage":coverage,
            "evidence_missing":",".join(missing),
        })

    return pd.DataFrame(rows)


def _json_safe(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value,pd.Timestamp):
        return value.isoformat()
    if isinstance(value,(bool,str,int)):
        return value
    if isinstance(value,float):
        return value if math.isfinite(value) else None
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass
    if hasattr(value,"item"):
        try:
            return _json_safe(value.item())
        except Exception:
            pass
    return str(value)


def dataframe_records(df: pd.DataFrame | None) -> list[dict[str, Any]]:
    if not isinstance(df,pd.DataFrame) or df.empty:
        return []
    return [
        {str(k):_json_safe(v) for k,v in row.items()}
        for row in df.to_dict(orient="records")
    ]


def build_evidence_bundle(
    *,
    pair: str,
    evidence: pd.DataFrame,
    comparison: pd.DataFrame,
    stability_summary: pd.DataFrame,
    stability_folds: pd.DataFrame,
    walkforward_summary: pd.DataFrame,
    walkforward_windows: pd.DataFrame,
    friction_summary: pd.DataFrame,
    friction_scenarios: pd.DataFrame,
    friction_breakdown: pd.DataFrame,
    parameter_summary: pd.DataFrame | None = None,
    parameter_variants: pd.DataFrame | None = None,
    settings: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a JSON-safe evidence package for audit/export."""
    return {
        "schema":"ATLASQUANT_BACKTEST_EVIDENCE_V1",
        "pair":str(pair or "").strip().upper(),
        "research_only":True,
        "no_live_gate_effect":True,
        "no_profit_probability":True,
        "settings":{str(k):_json_safe(v) for k,v in dict(settings or {}).items()},
        "evidence_summary":dataframe_records(evidence),
        "comparison":dataframe_records(comparison),
        "temporal_stability":{
            "summary":dataframe_records(stability_summary),
            "folds":dataframe_records(stability_folds),
        },
        "walk_forward":{
            "summary":dataframe_records(walkforward_summary),
            "windows":dataframe_records(walkforward_windows),
        },
        "friction":{
            "summary":dataframe_records(friction_summary),
            "scenarios":dataframe_records(friction_scenarios),
            "breakdown":dataframe_records(friction_breakdown),
        },
        "parameter_robustness":{
            "ran":bool(isinstance(parameter_summary,pd.DataFrame) and not parameter_summary.empty),
            "summary":dataframe_records(parameter_summary),
            "variants":dataframe_records(parameter_variants),
        },
    }


def evidence_bundle_json(bundle: Mapping[str, Any]) -> str:
    return json.dumps(dict(bundle),ensure_ascii=False,indent=2,sort_keys=True)


def evidence_markdown(
    evidence: pd.DataFrame,
    *,
    pair: str,
    settings: Mapping[str, Any] | None = None,
) -> str:
    """Create a compact human-readable research evidence report."""
    pair_name=str(pair or "").strip().upper() or "N/D"
    lines=[
        "# AtlasQuant — Relatório consolidado de evidências",
        "",
        f"Par: **{pair_name}**",
        "",
        "> Pesquisa histórica. Não é previsão, probabilidade de lucro ou autorização para operar.",
        "",
    ]
    if settings:
        lines.append("## Configuração")
        for key,value in dict(settings).items():
            lines.append(f"- {key}: {value}")
        lines.append("")

    lines.append("## Operacionais")
    if not isinstance(evidence,pd.DataFrame) or evidence.empty:
        lines.append("- Sem evidências consolidadas.")
        return "\n".join(lines)+"\n"

    for _,row in evidence.iterrows():
        lines.extend([
            "",
            f"### {row.get('operacional','N/D')}",
            f"- Trades: {row.get('trades',0)}",
            f"- Expectativa observada: {row.get('expectancy_r','N/D')} R",
            f"- Net R: {row.get('net_r','N/D')}",
            f"- Drawdown máximo: {row.get('max_drawdown_r','N/D')} R",
            f"- Estabilidade temporal: {row.get('temporal_status','N/D')}",
            f"- Walk-forward OOS: {row.get('walk_forward_status','N/D')}",
            f"- Custos/slippage: {row.get('friction_status','N/D')}",
            f"- Robustez de parâmetros: {row.get('parameter_status','N/D')}",
            f"- Cobertura dos diagnósticos: {row.get('evidence_diagnostics_available',0)}/{row.get('evidence_diagnostics_total',4)} ({row.get('evidence_coverage','N/D')})",
        ])
        missing=str(row.get("evidence_missing","") or "")
        if missing:
            lines.append(f"- Diagnósticos ausentes/insuficientes: {missing}")

    lines.extend([
        "",
        "## Limites",
        "- Resultados são históricos e dependem da amostra e das regras do replay.",
        "- Slippage é modelado como drag adverso em R, não como execução tick a tick.",
        "- O relatório não escolhe setup, não otimiza parâmetros e não altera o Gate.",
        "",
    ])
    return "\n".join(lines)
