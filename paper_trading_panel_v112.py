"""AtlasQuant V11.2 — painel do Paper Trading automático."""
from __future__ import annotations

import base64
import io
import json
import os
from typing import Any

import pandas as pd
import requests
import streamlit as st

from atlasquant_runtime_store import resolve_runtime_branch

SUMMARY_PATH = "dados/paper_trading_summary_v112.json"
TRADES_PATH = "dados/paper_trades_v112.csv"


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
        r = requests.get(
            f"https://api.github.com/repos/{repo}/contents/{path}",
            headers=headers,
            params={"ref": branch},
            timeout=15,
        )
        if r.status_code == 404:
            return None, "Paper Trading ainda não gerou histórico."
        r.raise_for_status()
        return base64.b64decode(r.json().get("content", "")), ""
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"


@st.cache_data(ttl=60, show_spinner=False)
def _load_summary(_cache_key: str) -> tuple[dict[str, Any], str]:
    raw, err = _github_bytes(SUMMARY_PATH)
    if raw is None:
        return {}, err
    try:
        return json.loads(raw.decode("utf-8")), ""
    except Exception as exc:
        return {}, f"Resumo inválido: {type(exc).__name__}: {exc}"


@st.cache_data(ttl=60, show_spinner=False)
def _load_trades(_cache_key: str) -> tuple[pd.DataFrame, str, bytes | None]:
    raw, err = _github_bytes(TRADES_PATH)
    if raw is None:
        return pd.DataFrame(), err, None
    try:
        return pd.read_csv(io.BytesIO(raw)), "", raw
    except Exception as exc:
        return pd.DataFrame(), f"CSV inválido: {type(exc).__name__}: {exc}", raw


def _pf_text(value: Any) -> str:
    if value in (None, "", "nan"):
        return "—"
    try:
        return f"{float(value):.2f}"
    except Exception:
        return str(value)


def _closed_trades(trades: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(trades, pd.DataFrame) or trades.empty or "status" not in trades.columns:
        return pd.DataFrame()
    d = trades[trades["status"].astype(str).str.upper() == "CLOSED"].copy()
    if d.empty:
        return d
    d["realized_r_num"] = pd.to_numeric(d.get("realized_r"), errors="coerce")
    d = d[d["realized_r_num"].notna()].copy()
    if "exit_time" in d.columns:
        d["exit_time_dt"] = pd.to_datetime(d["exit_time"], utc=True, errors="coerce")
        d = d.sort_values(["exit_time_dt", "trade_id" if "trade_id" in d.columns else "status"], na_position="last")
    return d.reset_index(drop=True)


def _paper_analytics(trades: pd.DataFrame) -> dict[str, Any]:
    closed = _closed_trades(trades)
    if closed.empty:
        return {
            "closed": 0,
            "expectancy_r": None,
            "max_drawdown_r": None,
            "avg_mfe_r": None,
            "avg_mae_r": None,
            "payoff_ratio": None,
            "best_r": None,
            "worst_r": None,
            "equity": pd.DataFrame(),
        }

    rr = closed["realized_r_num"].astype(float)
    wins = rr[rr > 0]
    losses = rr[rr < 0]
    equity = rr.cumsum()
    running_peak = equity.cummax().clip(lower=0.0)
    drawdown = running_peak - equity

    payoff = None
    if not wins.empty and not losses.empty:
        avg_win = float(wins.mean())
        avg_loss = abs(float(losses.mean()))
        if avg_loss > 0:
            payoff = avg_win / avg_loss

    avg_mfe = None
    if "mfe_r" in closed.columns:
        x = pd.to_numeric(closed["mfe_r"], errors="coerce").dropna()
        if not x.empty:
            avg_mfe = float(x.mean())

    avg_mae = None
    if "mae_r" in closed.columns:
        x = pd.to_numeric(closed["mae_r"], errors="coerce").dropna()
        if not x.empty:
            avg_mae = float(x.mean())

    curve = pd.DataFrame({
        "Trade": range(1, len(equity) + 1),
        "R acumulado": equity.values,
    }).set_index("Trade")

    return {
        "closed": int(len(closed)),
        "expectancy_r": float(rr.mean()),
        "max_drawdown_r": float(drawdown.max()) if not drawdown.empty else 0.0,
        "avg_mfe_r": avg_mfe,
        "avg_mae_r": avg_mae,
        "payoff_ratio": payoff,
        "best_r": float(rr.max()),
        "worst_r": float(rr.min()),
        "equity": curve,
    }


def _fmt_r(value: Any, signed: bool = False) -> str:
    if value is None:
        return "—"
    try:
        x = float(value)
        return f"{x:+.2f} R" if signed else f"{x:.2f} R"
    except Exception:
        return "—"


def render_paper_trading_v112() -> None:
    st.markdown("### 🧪 Paper Trading — validação automática")
    st.caption(
        "Simulação prospectiva: só registra entrada quando TODO o checklist operacional libera. "
        "Não envia ordem real e não possui conexão com corretora."
    )

    cache_key = "|".join(_cfg()[1:])
    summary, summary_err = _load_summary(cache_key)
    trades, trades_err, csv_raw = _load_trades(cache_key)

    if not summary:
        st.info(
            "Motor V11.2 instalado. O primeiro resumo aparecerá após uma rodada do Autopilot. "
            "Se a Twelve Data estiver sem cota, o checklist continuará bloqueando entradas por dados antigos."
        )
        if summary_err:
            st.caption(summary_err)
        return

    safety = dict(summary.get("safety", {}) or {})
    if safety.get("real_orders") is False and safety.get("broker_connection") is False:
        st.success("🔒 MODO SIMULADO CONFIRMADO · zero ordens reais · zero conexão com corretora")
    else:
        st.error("Configuração de segurança do Paper Trading não pôde ser confirmada.")

    a, b, c, d = st.columns(4)
    a.metric("Operações registradas", int(summary.get("trades_total", 0) or 0))
    b.metric("Em espera / abertas", f"{int(summary.get('pending_entries',0) or 0)} / {int(summary.get('open_positions',0) or 0)}")
    c.metric("Encerradas", int(summary.get("closed_trades", 0) or 0))
    d.metric("Win rate", f"{float(summary.get('win_rate_pct',0) or 0):.1f}%")

    e, f, g, h = st.columns(4)
    e.metric("Wins", int(summary.get("wins", 0) or 0))
    f.metric("Losses", int(summary.get("losses", 0) or 0))
    g.metric("Resultado líquido", f"{float(summary.get('net_r',0) or 0):+.2f} R")
    h.metric("Profit Factor", _pf_text(summary.get("profit_factor_r")))

    analytics = _paper_analytics(trades)
    if analytics["closed"]:
        st.markdown("#### 📊 Estatística prospectiva")
        p1, p2, p3, p4 = st.columns(4)
        p1.metric("Expectativa / trade", _fmt_r(analytics["expectancy_r"], signed=True))
        p2.metric("Drawdown máximo", _fmt_r(analytics["max_drawdown_r"]))
        p3.metric("Payoff médio", "—" if analytics["payoff_ratio"] is None else f"{analytics['payoff_ratio']:.2f}x")
        p4.metric("MFE médio", _fmt_r(analytics["avg_mfe_r"]))

        q1, q2, q3, q4 = st.columns(4)
        q1.metric("MAE médio", _fmt_r(analytics["avg_mae_r"]))
        q2.metric("Melhor trade", _fmt_r(analytics["best_r"], signed=True))
        q3.metric("Pior trade", _fmt_r(analytics["worst_r"], signed=True))
        q4.metric("Amostra fechada", int(analytics["closed"]))

        curve = analytics["equity"]
        if isinstance(curve, pd.DataFrame) and not curve.empty:
            st.markdown("##### Curva de resultado em R")
            st.line_chart(curve)
            st.caption(
                "A curva usa apenas trades encerrados do Paper Trading. Ela mede consistência da regra, "
                "não representa lucro real em dinheiro e não considera execução de corretora."
            )

    st.caption(
        "Regra inicial auditável: entrada no OPEN do primeiro M15 posterior ao sinal · "
        "Stop 1 ATR · alvo 2R · máximo 24h · se stop e alvo tocarem no mesmo candle, conta LOSS."
    )

    last_cycle = dict(summary.get("last_cycle", {}) or {})
    checklists = dict(last_cycle.get("checklists", {}) or {})
    if checklists:
        rows = []
        for pair, raw in checklists.items():
            x = dict(raw or {})
            hard = list(x.get("hard_blocks", []) or [])
            soft = list(x.get("soft_blocks", []) or [])
            rows.append({
                "Par": pair,
                "Lado": x.get("side", "WAIT"),
                "Checklist": "✅ LIBERADO" if x.get("passed") else "⛔ BLOQUEADO",
                "Estado": x.get("state", ""),
                "Bloqueios": " | ".join(hard + soft) if (hard or soft) else "—",
            })
        st.markdown("#### Checklist da última rodada")
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)

    by_pair = dict(summary.get("by_pair", {}) or {})
    if by_pair:
        perf = []
        for pair, raw in by_pair.items():
            x = dict(raw or {})
            perf.append({
                "Par": pair,
                "Trades": x.get("trades", 0),
                "Wins": x.get("wins", 0),
                "Losses": x.get("losses", 0),
                "Win rate %": x.get("win_rate_pct", 0),
                "Net R": x.get("net_r", 0),
                "Média R": x.get("avg_r", 0),
            })
        st.markdown("#### Desempenho por par")
        st.dataframe(pd.DataFrame(perf), width="stretch", hide_index=True)

    st.markdown("#### Diário automático")
    if trades.empty:
        st.info("Nenhuma operação simulada registrada ainda.")
        if trades_err:
            st.caption(trades_err)
    else:
        cols = [
            c for c in [
                "pair", "side", "status", "result", "signal_time", "entry_time",
                "entry_price", "stop_price", "target_price", "exit_time", "exit_price",
                "realized_r", "mfe_r", "mae_r", "bars_held", "exit_reason", "checklist_note",
            ] if c in trades.columns
        ]
        st.dataframe(trades[cols].tail(100).iloc[::-1], width="stretch", hide_index=True)
        if csv_raw is not None:
            st.download_button(
                "⬇️ Baixar diário Paper Trading (CSV)",
                data=csv_raw,
                file_name="AtlasQuant_Paper_Trading_V11_2.csv",
                mime="text/csv",
                width="stretch",
            )

    with st.expander("Como o teste funciona"):
        st.markdown(
            "- O sinal só é criado com Decision Integrity executável **e zero bloqueios**.\n"
            "- A entrada nunca usa o mesmo candle que gerou o sinal.\n"
            "- O preço de entrada, stop, alvo e resultado ficam congelados no diário.\n"
            "- MFE/MAE, expectativa, drawdown e curva em R são calculados somente com operações fechadas.\n"
            "- Nenhuma estatística do Paper Trading altera o Score Mestre.\n"
            "- Este módulo serve para medir consistência antes de qualquer uso real."
        )
