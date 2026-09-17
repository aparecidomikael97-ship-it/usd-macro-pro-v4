"""AtlasQuant V11.6 — Forward Validation com custos do Paper Trading.

Compara evidência histórica com Paper prospectivo usando R líquido pós-fricção
quando disponível. Mantém resultado bruto visível e não cria ranking, vencedor,
Gate, peso ou qualquer ação de corretora.
"""
from __future__ import annotations

from typing import Any, Mapping

import pandas as pd
import streamlit as st

from atlasquant_forward_validation_v113 import (
    _load_paper_runtime,
    _uploaded_snapshot,
    extract_backtest_evidence,
    paper_sample_state,
)
from atlasquant_journal import summarize_trades


def paper_records_after_friction(trades: pd.DataFrame | None) -> list[dict[str, Any]]:
    if not isinstance(trades, pd.DataFrame) or trades.empty:
        return []
    df = trades.copy()
    if "status" in df.columns:
        df = df[df["status"].astype(str).str.upper().eq("CLOSED")]
    if df.empty:
        return []

    gross = pd.to_numeric(df.get("realized_r"), errors="coerce") if "realized_r" in df.columns else pd.Series(index=df.index, dtype=float)
    net = pd.to_numeric(df.get("net_r"), errors="coerce") if "net_r" in df.columns else pd.Series(index=df.index, dtype=float)
    effective = net.where(net.notna(), gross)
    df = df.loc[effective.notna()].copy()
    effective = effective.loc[effective.notna()]

    records: list[dict[str, Any]] = []
    for idx, row in df.iterrows():
        value = float(effective.loc[idx])
        result = str(row.get("result", "") or "").strip().upper()
        if result not in {"WIN", "LOSS", "BREAKEVEN"}:
            result = "WIN" if value > 0 else "LOSS" if value < 0 else "BREAKEVEN"
        records.append({
            "result": result,
            "net_r": value,
            "pair": str(row.get("pair", "") or ""),
            "closed_at": row.get("exit_time"),
        })
    return records


def paper_metrics_after_friction(trades: pd.DataFrame | None) -> dict[str, Any]:
    metrics = dict(summarize_trades(paper_records_after_friction(trades)) or {})
    metrics["sample_state"] = paper_sample_state(int(metrics.get("trades", 0) or 0))

    gross_r = 0.0
    friction_r = 0.0
    if isinstance(trades, pd.DataFrame) and not trades.empty:
        d = trades.copy()
        if "status" in d.columns:
            d = d[d["status"].astype(str).str.upper().eq("CLOSED")]
        if "realized_r" in d.columns:
            gross_r = float(pd.to_numeric(d["realized_r"], errors="coerce").dropna().sum())
        if "total_friction_r" in d.columns:
            friction_r = float(pd.to_numeric(d["total_friction_r"], errors="coerce").dropna().sum())
    metrics["gross_r_before_friction"] = round(gross_r, 4)
    metrics["friction_r"] = round(friction_r, 4)
    metrics["uses_net_r_when_available"] = True
    return metrics


def comparison_frame_v116(snapshot: Mapping[str, Any] | None, trades: pd.DataFrame | None) -> pd.DataFrame:
    columns = [
        "fonte", "base_resultado", "operacional", "trades", "win_rate_pct",
        "expectancy_r", "net_r", "profit_factor", "max_drawdown_r", "amostra",
    ]
    rows: list[dict[str, Any]] = []
    bt = extract_backtest_evidence(snapshot)
    if not bt.empty:
        for _, row in bt.iterrows():
            rows.append({
                "fonte": "BACKTEST HISTÓRICO",
                "base_resultado": "snapshot histórico",
                "operacional": row.get("operacional", row.get("strategy", "N/D")),
                "trades": int(row.get("trades", 0) or 0),
                "win_rate_pct": row.get("win_rate_pct"),
                "expectancy_r": row.get("expectancy_r"),
                "net_r": row.get("net_r"),
                "profit_factor": row.get("profit_factor"),
                "max_drawdown_r": row.get("max_drawdown_r"),
                "amostra": str(row.get("sample_tier", "HISTÓRICA") or "HISTÓRICA"),
            })

    pm = paper_metrics_after_friction(trades)
    rows.append({
        "fonte": "PAPER PROSPECTIVO",
        "base_resultado": "R líquido pós-fricção quando disponível",
        "operacional": "AtlasQuant — checklist completo",
        "trades": int(pm.get("trades", 0) or 0),
        "win_rate_pct": pm.get("win_rate_pct"),
        "expectancy_r": pm.get("expectancy_r"),
        "net_r": pm.get("net_r"),
        "profit_factor": pm.get("profit_factor"),
        "max_drawdown_r": pm.get("max_drawdown_r"),
        "amostra": pm.get("sample_state"),
    })
    return pd.DataFrame(rows, columns=columns)


def render_forward_validation_v116() -> None:
    st.subheader("🔬 Backtest × Paper — Forward Validation V11.6")
    st.caption(
        "Compara histórico e amostra prospectiva. No Paper, usa R líquido após spread/slippage "
        "quando esses campos já foram persistidos. A comparação continua somente descritiva."
    )

    trades, paper_err = _load_paper_runtime()
    if paper_err:
        st.caption(f"Paper Trading: {paper_err}")

    snapshot = st.session_state.get("atlasquant_latest_snapshot")
    source = "último Backtest desta sessão" if isinstance(snapshot, Mapping) else ""
    if not isinstance(snapshot, Mapping):
        uploaded = _uploaded_snapshot()
        if isinstance(uploaded, Mapping):
            snapshot = uploaded
            source = "snapshot carregado"

    pm = paper_metrics_after_friction(trades)
    a, b, c, d = st.columns(4)
    a.metric("Paper encerrados", int(pm.get("trades", 0) or 0))
    b.metric("R bruto", f"{float(pm.get('gross_r_before_friction', 0.0) or 0.0):+.2f}R")
    c.metric("Custos acumulados", f"-{float(pm.get('friction_r', 0.0) or 0.0):.2f}R")
    d.metric("Paper R líquido", f"{float(pm.get('net_r', 0.0) or 0.0):+.2f}R")
    st.caption(
        f"Win Rate: {float(pm.get('win_rate_pct', 0.0) or 0.0):.1f}% · "
        f"Expectativa líquida: {float(pm.get('expectancy_r', 0.0) or 0.0):+.2f}R · "
        f"Amostra: {pm.get('sample_state')}"
    )

    if not isinstance(snapshot, Mapping):
        st.info(
            "O Paper líquido já está conectado. Para preencher a parte histórica, rode um Backtest "
            "nesta sessão ou carregue um snapshot JSON reproduzível."
        )
        return

    frame = comparison_frame_v116(snapshot, trades)
    st.caption(f"Referência histórica: {source}.")
    view = frame.rename(columns={
        "fonte": "Fonte",
        "base_resultado": "Base do resultado",
        "operacional": "Operacional",
        "trades": "Trades",
        "win_rate_pct": "Win Rate %",
        "expectancy_r": "Expectativa R",
        "net_r": "Net R",
        "profit_factor": "Profit Factor",
        "max_drawdown_r": "DD Máx R",
        "amostra": "Amostra",
    })
    st.dataframe(view, width="stretch", hide_index=True)

    st.info(
        "Backtest e Paper são amostras diferentes. Custos e metodologia podem não ser idênticos entre "
        "as duas fontes; por isso a coluna 'Base do resultado' fica explícita. Diferenças são evidência "
        "para revisão, não previsão de desempenho futuro."
    )
    st.caption(
        "Segurança: observacional · sem ranking/vencedor · sem ordem real · sem broker · sem mudança automática de Gate/pesos."
    )
