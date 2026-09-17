"""AtlasQuant V11.3 — comparação descritiva Backtest × Paper Trading.

A camada é somente observacional. Ela não escolhe setup, não altera Gate,
não muda pesos e não envia ordens. Backtest histórico e Paper Trading
prospectivo são amostras diferentes; os números ficam lado a lado para auditoria.
"""
from __future__ import annotations

import base64
import io
import json
import os
from typing import Any, Mapping

import pandas as pd
import requests
import streamlit as st

from atlasquant_journal import summarize_trades
from atlasquant_runtime_store import resolve_runtime_branch

PAPER_CSV_PATH = "dados/paper_trades_v112.csv"


def paper_sample_state(trades: int) -> str:
    n = max(0, int(trades or 0))
    if n == 0:
        return "AGUARDANDO AMOSTRA"
    if n < 30:
        return "AMOSTRA PEQUENA"
    if n < 100:
        return "AMOSTRA EM FORMAÇÃO"
    return "AMOSTRA MAIS MADURA"


def paper_records_from_frame(trades: pd.DataFrame | None) -> list[dict[str, Any]]:
    if not isinstance(trades, pd.DataFrame) or trades.empty:
        return []
    df = trades.copy()
    if "status" in df.columns:
        df = df[df["status"].astype(str).str.upper().eq("CLOSED")]
    if df.empty or "realized_r" not in df.columns:
        return []

    rr = pd.to_numeric(df["realized_r"], errors="coerce")
    df = df.loc[rr.notna()].copy()
    rr = rr.loc[rr.notna()]
    records: list[dict[str, Any]] = []
    for idx, row in df.iterrows():
        value = float(rr.loc[idx])
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


def paper_metrics(trades: pd.DataFrame | None) -> dict[str, Any]:
    metrics = summarize_trades(paper_records_from_frame(trades))
    metrics = dict(metrics or {})
    metrics["sample_state"] = paper_sample_state(int(metrics.get("trades", 0) or 0))
    return metrics


def extract_backtest_evidence(snapshot: Mapping[str, Any] | None) -> pd.DataFrame:
    if not isinstance(snapshot, Mapping):
        return pd.DataFrame()
    try:
        rows = (((snapshot.get("evidence") or {}).get("bundle") or {}).get("evidence_summary") or [])
    except Exception:
        return pd.DataFrame()
    if not isinstance(rows, list):
        return pd.DataFrame()
    safe_rows = [dict(row) for row in rows if isinstance(row, Mapping)]
    if not safe_rows:
        return pd.DataFrame()
    return pd.DataFrame(safe_rows)


def comparison_frame(
    snapshot: Mapping[str, Any] | None,
    trades: pd.DataFrame | None,
) -> pd.DataFrame:
    columns = [
        "fonte", "operacional", "trades", "win_rate_pct", "expectancy_r",
        "net_r", "profit_factor", "max_drawdown_r", "amostra",
    ]
    rows: list[dict[str, Any]] = []
    bt = extract_backtest_evidence(snapshot)
    if not bt.empty:
        for _, row in bt.iterrows():
            rows.append({
                "fonte": "BACKTEST HISTÓRICO",
                "operacional": row.get("operacional", row.get("strategy", "N/D")),
                "trades": int(row.get("trades", 0) or 0),
                "win_rate_pct": row.get("win_rate_pct"),
                "expectancy_r": row.get("expectancy_r"),
                "net_r": row.get("net_r"),
                "profit_factor": row.get("profit_factor"),
                "max_drawdown_r": row.get("max_drawdown_r"),
                "amostra": str(row.get("sample_tier", "HISTÓRICA") or "HISTÓRICA"),
            })

    pm = paper_metrics(trades)
    rows.append({
        "fonte": "PAPER PROSPECTIVO",
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


def _cfg_value(name: str, default: str = "") -> str:
    value = os.getenv(name)
    if value is not None and str(value).strip():
        return str(value)
    try:
        return str(st.secrets.get(name, default))
    except Exception:
        return default


def _runtime_cfg() -> tuple[str, str, str]:
    token = _cfg_value("GITHUB_TOKEN_HISTORICO")
    repo = _cfg_value("GITHUB_REPO_HISTORICO")
    branch = resolve_runtime_branch(
        _cfg_value("GITHUB_DATA_BRANCH"),
        _cfg_value("GITHUB_BRANCH_HISTORICO"),
    )
    return token, repo, branch


@st.cache_data(ttl=60, show_spinner=False)
def _load_paper_runtime() -> tuple[pd.DataFrame, str]:
    token, repo, branch = _runtime_cfg()
    if not repo:
        return pd.DataFrame(), "Persistência GitHub não configurada."
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        response = requests.get(
            f"https://api.github.com/repos/{repo}/contents/{PAPER_CSV_PATH}",
            headers=headers,
            params={"ref": branch},
            timeout=15,
        )
        if response.status_code == 404:
            return pd.DataFrame(), "Diário Paper ainda não existe."
        response.raise_for_status()
        raw = base64.b64decode(response.json()["content"])
        if not raw.strip():
            return pd.DataFrame(), ""
        return pd.read_csv(io.BytesIO(raw)), ""
    except Exception as exc:
        return pd.DataFrame(), f"{type(exc).__name__}: {exc}"


def _uploaded_snapshot() -> dict[str, Any] | None:
    uploaded = st.file_uploader(
        "Snapshot de backtest (opcional)",
        type=["json"],
        key="atlasquant_forward_snapshot_upload_v113",
        help="Use somente se o snapshot não estiver mais nesta sessão do Backtest.",
    )
    if uploaded is None:
        return None
    try:
        from atlasquant_backtest_snapshot import load_snapshot_json
        return load_snapshot_json(uploaded.getvalue())
    except Exception as exc:
        st.warning(f"Snapshot rejeitado: {type(exc).__name__}: {exc}")
        return None


def render_forward_validation_v113() -> None:
    st.subheader("🔬 Backtest × Paper Trading — Forward Validation V11.3")
    st.caption(
        "Coloca o histórico e o teste prospectivo lado a lado. É uma comparação descritiva: "
        "não cria ranking, não autoriza entrada e não altera o motor do AtlasQuant."
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

    pm = paper_metrics(trades)
    a, b, c, d = st.columns(4)
    a.metric("Paper encerrados", int(pm.get("trades", 0) or 0))
    b.metric("Paper Win Rate", f"{float(pm.get('win_rate_pct', 0.0) or 0.0):.1f}%")
    c.metric("Paper Expectativa", f"{float(pm.get('expectancy_r', 0.0) or 0.0):+.2f}R")
    d.metric("Paper Net R", f"{float(pm.get('net_r', 0.0) or 0.0):+.2f}R")
    st.caption(f"Estado da amostra prospectiva: {pm.get('sample_state')}")

    if not isinstance(snapshot, Mapping):
        st.info(
            "O Paper já está conectado. Para preencher a parte histórica, rode um Backtest nesta mesma "
            "sessão ou carregue um snapshot JSON reproduzível."
        )
        return

    frame = comparison_frame(snapshot, trades)
    st.caption(f"Referência histórica: {source}.")
    view = frame.rename(columns={
        "fonte": "Fonte",
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

    bt_pair = str(st.session_state.get("atlasquant_latest_snapshot_pair", "") or "").strip()
    if bt_pair:
        st.caption(f"Par do snapshot histórico: {bt_pair}")

    st.info(
        "Leitura correta: o Backtest usa histórico e regras de replay; o Paper mede sinais que surgem "
        "daqui para frente com o checklist real. Diferenças entre eles são evidência para revisão, "
        "não prova de que um resultado futuro será igual ao passado."
    )
    st.caption(
        "Segurança: comparação somente observacional · sem ordem real · sem broker · sem mudança automática de Gate/pesos."
    )
