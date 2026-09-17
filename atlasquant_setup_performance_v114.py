"""AtlasQuant V11.4 — painel prospectivo de setups/componentes.

Lê somente os artefatos de auditoria gerados pelo Autopilot. É observacional:
não cria ranking, não escolhe estratégia, não altera Gate/pesos e não envia ordens.
"""
from __future__ import annotations

import base64
import io
import json
import math
import os
from typing import Any

import pandas as pd
import requests
import streamlit as st

from atlasquant_runtime_store import resolve_runtime_branch

AUDIT_PATH = "dados/paper_setup_audit_v114.csv"
PERFORMANCE_PATH = "dados/paper_setup_performance_v114.csv"
SUMMARY_PATH = "dados/paper_setup_summary_v114.json"

COMPONENT_STATUS_COLUMNS = {
    "AMD": "amd_status",
    "FVG": "fvg_status",
    "CRT": "crt_status",
    "OTE": "ote_status",
    "DISPLACEMENT": "displacement_status",
    "MSS": "mss_status",
    "SMT": "smt_status",
    "DEALING_RANGE": "dealing_range_status",
    "LIQUIDITY": "liquidity_status",
    "SESSION": "session_status",
    "PD_ARRAY": "pd_array_status",
}


def _cfg_value(name: str, default: str = "") -> str:
    value = os.getenv(name)
    if value is not None and str(value).strip():
        return str(value)
    try:
        return str(st.secrets.get(name, default))
    except Exception:
        return default


def _cfg() -> tuple[str, str, str]:
    token = _cfg_value("GITHUB_TOKEN_HISTORICO")
    repo = _cfg_value("GITHUB_REPO_HISTORICO")
    branch = resolve_runtime_branch(
        _cfg_value("GITHUB_DATA_BRANCH"),
        _cfg_value("GITHUB_BRANCH_HISTORICO"),
    )
    return token, repo, branch


def _github_bytes(path: str) -> tuple[bytes | None, str]:
    token, repo, branch = _cfg()
    if not repo:
        return None, "Persistência GitHub não configurada."
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        response = requests.get(
            f"https://api.github.com/repos/{repo}/contents/{path}",
            headers=headers,
            params={"ref": branch},
            timeout=15,
        )
        if response.status_code == 404:
            return None, "Artefato V11.4 ainda não foi criado pelo Autopilot."
        response.raise_for_status()
        return base64.b64decode(response.json().get("content", "")), ""
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"


@st.cache_data(ttl=60, show_spinner=False)
def _load_csv(path: str, _cache_key: str) -> tuple[pd.DataFrame, str, bytes | None]:
    raw, err = _github_bytes(path)
    if raw is None:
        return pd.DataFrame(), err, None
    if not raw.strip():
        return pd.DataFrame(), "", raw
    try:
        return pd.read_csv(io.BytesIO(raw)), "", raw
    except Exception as exc:
        return pd.DataFrame(), f"CSV inválido: {type(exc).__name__}: {exc}", raw


@st.cache_data(ttl=60, show_spinner=False)
def _load_summary(_cache_key: str) -> tuple[dict[str, Any], str]:
    raw, err = _github_bytes(SUMMARY_PATH)
    if raw is None:
        return {}, err
    try:
        return json.loads(raw.decode("utf-8")), ""
    except Exception as exc:
        return {}, f"Resumo V11.4 inválido: {type(exc).__name__}: {exc}"


def _finite(value: Any) -> float | None:
    try:
        out = float(value)
        return out if math.isfinite(out) else None
    except Exception:
        return None


def _max_drawdown(values: list[float]) -> float:
    equity = peak = max_dd = 0.0
    for value in values:
        equity += float(value)
        peak = max(peak, equity)
        max_dd = max(max_dd, peak - equity)
    return max_dd


def sample_state(n: int) -> str:
    n = max(0, int(n or 0))
    if n == 0:
        return "AGUARDANDO AMOSTRA"
    if n < 30:
        return "AMOSTRA PEQUENA"
    if n < 100:
        return "AMOSTRA EM FORMAÇÃO"
    return "AMOSTRA MAIS MADURA"


def component_pair_frame(audit: pd.DataFrame | None, component: str) -> pd.DataFrame:
    """Quebra descritiva por par + estado do componente, apenas trades fechados."""
    columns = [
        "pair", "state", "trades_closed", "wins", "losses", "breakeven",
        "win_rate_pct", "net_r", "avg_r", "profit_factor_r", "max_drawdown_r",
        "sample_state",
    ]
    if not isinstance(audit, pd.DataFrame) or audit.empty:
        return pd.DataFrame(columns=columns)
    status_col = COMPONENT_STATUS_COLUMNS.get(str(component).upper())
    required = {"pair", "status", "realized_r"}
    if not status_col or status_col not in audit.columns or not required.issubset(audit.columns):
        return pd.DataFrame(columns=columns)

    d = audit[audit["status"].astype(str).str.upper().eq("CLOSED")].copy()
    if d.empty:
        return pd.DataFrame(columns=columns)
    d["_r"] = pd.to_numeric(d["realized_r"], errors="coerce")
    d = d[d["_r"].notna()].copy()
    if d.empty:
        return pd.DataFrame(columns=columns)
    d[status_col] = d[status_col].fillna("").astype(str).str.strip().replace("", "(SEM ESTADO)")
    d["_exit"] = pd.to_datetime(d.get("exit_time"), utc=True, errors="coerce")

    rows: list[dict[str, Any]] = []
    for (pair, state), group in d.groupby(["pair", status_col], dropna=False):
        g = group.sort_values(["_exit", "trade_id" if "trade_id" in group.columns else "pair"], na_position="last")
        values = [float(x) for x in g["_r"].tolist()]
        n = len(values)
        wins = sum(1 for x in values if x > 0)
        losses = sum(1 for x in values if x < 0)
        breakeven = sum(1 for x in values if x == 0)
        gross_profit = sum(x for x in values if x > 0)
        gross_loss = abs(sum(x for x in values if x < 0))
        pf = None if gross_loss <= 0 else gross_profit / gross_loss
        rows.append({
            "pair": str(pair),
            "state": str(state),
            "trades_closed": int(n),
            "wins": int(wins),
            "losses": int(losses),
            "breakeven": int(breakeven),
            "win_rate_pct": round(wins / n * 100.0, 2) if n else None,
            "net_r": round(sum(values), 4),
            "avg_r": round(sum(values) / n, 4) if n else None,
            "profit_factor_r": None if pf is None else round(pf, 4),
            "max_drawdown_r": round(_max_drawdown(values), 4),
            "sample_state": sample_state(n),
        })
    return pd.DataFrame(rows, columns=columns).sort_values(["pair", "state"]).reset_index(drop=True)


def _fmt_pf(value: Any) -> str:
    x = _finite(value)
    return "—" if x is None else f"{x:.2f}"


def render_setup_performance_v114() -> None:
    st.subheader("🧬 ICT/SMC — auditoria prospectiva por componente V11.4")
    st.caption(
        "Congela o estado de AMD, FVG, CRT, OTE e componentes institucionais quando o Paper Trading "
        "registra um sinal. Depois mede os desfechos sem reescrever o contexto original."
    )

    cache_key = "|".join(_cfg()[1:])
    summary, summary_err = _load_summary(cache_key)
    performance, perf_err, perf_raw = _load_csv(PERFORMANCE_PATH, cache_key)
    audit, audit_err, audit_raw = _load_csv(AUDIT_PATH, cache_key)

    if not summary:
        st.info("V11.4 instalado no painel. Aguardando a primeira rodada do Autopilot com Setup Audit.")
        if summary_err:
            st.caption(summary_err)
        return

    safety = dict(summary.get("safety", {}) or {})
    safe = (
        safety.get("real_orders") is False
        and safety.get("broker_connection") is False
        and safety.get("auto_strategy_selection") is False
        and safety.get("auto_gate_change") is False
    )
    if safe:
        st.success("🔒 AUDITORIA OBSERVACIONAL · sem ordens · sem broker · sem ajuste automático do modelo")
    else:
        st.warning("Não foi possível confirmar todos os marcadores de segurança da auditoria V11.4.")

    a, b, c, d = st.columns(4)
    a.metric("Trades auditados", int(summary.get("audited_trades", 0) or 0))
    b.metric("Trades fechados", int(summary.get("closed_trades", 0) or 0))
    c.metric("Estados medidos", int(summary.get("component_state_rows", 0) or 0))
    d.metric("Net R auditado", f"{float(summary.get('net_r', 0.0) or 0.0):+.2f} R")
    st.caption(f"Maturidade da amostra: {summary.get('sample_state', 'AGUARDANDO AMOSTRA')}")

    if performance.empty:
        st.info(
            "Ainda não há trades Paper encerrados para comparar setups. O AtlasQuant continuará "
            "congelando o contexto dos novos sinais válidos e preencherá esta área conforme eles encerrarem."
        )
        if perf_err:
            st.caption(perf_err)
    else:
        components = sorted(performance.get("component", pd.Series(dtype=str)).dropna().astype(str).unique().tolist())
        if components:
            selected = st.selectbox(
                "Componente para auditoria",
                components,
                key="atlasquant_setup_audit_component_v114",
            )
            view = performance[performance["component"].astype(str) == selected].copy()
            view = view.rename(columns={
                "state": "Estado observado",
                "trades_closed": "Trades fechados",
                "wins": "Wins",
                "losses": "Losses",
                "breakeven": "BE",
                "win_rate_pct": "Win rate %",
                "net_r": "Net R",
                "avg_r": "Média R",
                "profit_factor_r": "Profit Factor",
                "max_drawdown_r": "DD máx R",
                "sample_state": "Amostra",
            })
            keep = [
                col for col in [
                    "Estado observado", "Trades fechados", "Wins", "Losses", "BE",
                    "Win rate %", "Net R", "Média R", "Profit Factor", "DD máx R", "Amostra",
                ] if col in view.columns
            ]
            st.markdown("#### Estado do componente × resultado prospectivo")
            st.dataframe(view[keep], use_container_width=True, hide_index=True)

            pair_view = component_pair_frame(audit, selected)
            if not pair_view.empty:
                pair_view = pair_view.rename(columns={
                    "pair": "Par",
                    "state": "Estado observado",
                    "trades_closed": "Trades fechados",
                    "wins": "Wins",
                    "losses": "Losses",
                    "breakeven": "BE",
                    "win_rate_pct": "Win rate %",
                    "net_r": "Net R",
                    "avg_r": "Média R",
                    "profit_factor_r": "Profit Factor",
                    "max_drawdown_r": "DD máx R",
                    "sample_state": "Amostra",
                })
                st.markdown("#### Mesmo componente, separado por par")
                st.dataframe(pair_view, use_container_width=True, hide_index=True)

    st.info(
        "Como ler: cada linha é um estado realmente observado no momento em que o sinal Paper apareceu. "
        "A tabela não escolhe vencedor e não recomenda operação. Amostras pequenas podem variar muito."
    )

    with st.expander("O que fica congelado no sinal"):
        st.markdown(
            "- ICT: AMD, FVG, CRT e OTE (status + score).\n"
            "- Institucional: displacement, MSS, SMT, dealing range, liquidez, sessão e PD Array.\n"
            "- Contexto Paper: par, lado, score mestre, qualidade, H4/H1/M15, Gate, ADR e risco de evento.\n"
            "- Depois do congelamento, só o desfecho evolui: entrada, saída, WIN/LOSS/BE, R, MFE e MAE."
        )

    if audit_raw is not None:
        st.download_button(
            "⬇️ Baixar auditoria completa de setups (CSV)",
            data=audit_raw,
            file_name="AtlasQuant_Setup_Audit_V11_4.csv",
            mime="text/csv",
            use_container_width=True,
        )
    if perf_raw is not None:
        st.download_button(
            "⬇️ Baixar desempenho por componente (CSV)",
            data=perf_raw,
            file_name="AtlasQuant_Setup_Performance_V11_4.csv",
            mime="text/csv",
            use_container_width=True,
        )

    errors = [x for x in (audit_err, perf_err) if x]
    if errors:
        with st.expander("Diagnóstico da leitura V11.4"):
            for error in errors:
                st.caption(error)
