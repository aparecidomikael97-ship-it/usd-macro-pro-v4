"""AtlasQuant V11.6 — painel de fricção do Paper Trading.

Camada somente observacional. Exibe resultado bruto, custos conservadores de
spread/slippage e resultado líquido sem alterar sinais, Gate, pesos ou
classificação WIN/LOSS.
"""
from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from paper_trading_panel_v112 import _cfg, _load_summary, _load_trades


def friction_snapshot(summary: dict[str, Any] | None, trades: pd.DataFrame | None) -> dict[str, Any]:
    summary = dict(summary or {})
    friction = dict(summary.get("friction_v116", {}) or {})

    gross = friction.get("gross_r", summary.get("gross_r_before_friction", 0.0))
    costs = friction.get("friction_r", summary.get("friction_r", 0.0))
    net = friction.get("net_r", summary.get("net_r_after_friction", 0.0))
    pf_net = friction.get("profit_factor_net_r")
    closed = int(friction.get("closed_costed", 0) or 0)
    version = friction.get("version", "V11.6_PAPER_FRICTION")

    if isinstance(trades, pd.DataFrame) and not trades.empty:
        d = trades.copy()
        if "status" in d.columns:
            d = d[d["status"].astype(str).str.upper().eq("CLOSED")]
        if not d.empty:
            gross_col = pd.to_numeric(d.get("gross_r"), errors="coerce") if "gross_r" in d.columns else pd.Series(dtype=float)
            net_col = pd.to_numeric(d.get("net_r"), errors="coerce") if "net_r" in d.columns else pd.Series(dtype=float)
            cost_col = pd.to_numeric(d.get("total_friction_r"), errors="coerce") if "total_friction_r" in d.columns else pd.Series(dtype=float)
            if closed == 0 and not net_col.dropna().empty:
                closed = int(net_col.notna().sum())
            if float(gross or 0.0) == 0.0 and not gross_col.dropna().empty:
                gross = float(gross_col.dropna().sum())
            if float(costs or 0.0) == 0.0 and not cost_col.dropna().empty:
                costs = float(cost_col.dropna().sum())
            if float(net or 0.0) == 0.0 and not net_col.dropna().empty:
                net = float(net_col.dropna().sum())

    return {
        "version": str(version),
        "closed_costed": closed,
        "gross_r": float(gross or 0.0),
        "friction_r": float(costs or 0.0),
        "net_r": float(net or 0.0),
        "profit_factor_net_r": pf_net,
        "safety_confirmed": bool(
            (summary.get("safety", {}) or {}).get("real_orders") is False
            and (summary.get("safety", {}) or {}).get("broker_connection") is False
        ),
    }


def _fmt_pf(value: Any) -> str:
    if value in (None, "", "nan"):
        return "—"
    try:
        return f"{float(value):.2f}"
    except Exception:
        return "—"


def render_paper_friction_v116() -> None:
    st.subheader("💸 Paper Trading — custos e resultado líquido V11.6")
    st.caption(
        "Mostra o impacto conservador de spread e slippage sobre o Paper Trading. "
        "O resultado bruto permanece preservado para auditoria."
    )

    cache_key = "|".join(_cfg()[1:])
    summary, summary_err = _load_summary(cache_key)
    trades, trades_err, _ = _load_trades(cache_key)

    if not summary:
        st.info("Aguardando o primeiro resumo V11.6 do Autopilot.")
        if summary_err:
            st.caption(summary_err)
        return

    snap = friction_snapshot(summary, trades)
    if snap["safety_confirmed"]:
        st.success("🔒 Fricção analítica confirmada · sem ordens reais · sem conexão com corretora")
    else:
        st.warning("Não foi possível confirmar todos os campos de segurança do resumo atual.")

    a, b, c, d = st.columns(4)
    a.metric("R bruto", f"{snap['gross_r']:+.2f} R")
    b.metric("Spread + slippage", f"-{snap['friction_r']:.2f} R")
    c.metric("R líquido após custos", f"{snap['net_r']:+.2f} R")
    d.metric("Profit Factor líquido", _fmt_pf(snap["profit_factor_net_r"]))

    st.caption(
        f"Modelo: {snap['version']} · trades fechados com custo: {snap['closed_costed']} · "
        "premissa padrão atual: 0,04R de spread + 0,02R de slippage por trade fechado."
    )

    if isinstance(trades, pd.DataFrame) and not trades.empty:
        cols = [c for c in [
            "pair", "side", "result", "exit_time", "realized_r", "gross_r",
            "spread_cost_r", "slippage_cost_r", "total_friction_r", "net_r",
        ] if c in trades.columns]
        if cols and "net_r" in cols:
            d = trades.copy()
            if "status" in d.columns:
                d = d[d["status"].astype(str).str.upper().eq("CLOSED")]
            if not d.empty:
                st.markdown("#### Auditoria por operação")
                st.dataframe(d[cols].tail(100).iloc[::-1], width="stretch", hide_index=True)
    elif trades_err:
        st.caption(trades_err)

    st.info(
        "Esta camada não altera WIN/LOSS, sinal, Gate ou estratégia. Ela serve para impedir que a "
        "avaliação prospectiva pareça melhor por ignorar custos de execução."
    )
