"""AtlasQuant Investir — presentation layer for long-term planning.

The panel consumes the isolated investment foundations. It is educational and
scenario-based: it does not place orders, recommend assets or promise returns.
"""
from __future__ import annotations

from typing import Iterable

import pandas as pd
import streamlit as st

from atlasquant_investment_ecosystem import (
    CompoundProjectionInput,
    IncomeProjectionInput,
    SIMULATION_NOTICE,
    dividend_quality_snapshot,
    growth_watch_snapshot,
    project_compound,
    project_income_asset,
    required_capital_for_monthly_income,
)

PANEL_VERSION = "1.0"


def _mode(value: object) -> str:
    raw = str(value or "").strip().casefold()
    return "Avançado" if raw.startswith("avan") or raw in {"pro", "advanced"} else "Iniciante"


def investment_sections(experience_mode: object = "Iniciante") -> tuple[str, ...]:
    base = ("Planejador", "Renda", "Comece com pouco")
    if _mode(experience_mode) == "Avançado":
        return base + ("Qualidade da renda", "Radar de crescimento")
    return base


def format_brl(value: float | int) -> str:
    number = float(value)
    text = f"{number:,.2f}"
    return "R$ " + text.replace(",", "X").replace(".", ",").replace("X", ".")


def small_contribution_scenarios(
    monthly_values: Iterable[float] = (50.0, 100.0, 200.0),
    *,
    years: int = 10,
    annual_return_pct: float = 8.0,
) -> list[dict[str, float]]:
    rows: list[dict[str, float]] = []
    for monthly in monthly_values:
        result = project_compound(
            CompoundProjectionInput(
                initial_amount=0.0,
                monthly_contribution=float(monthly),
                annual_return_pct=float(annual_return_pct),
                years=int(years),
            )
        )
        rows.append(
            {
                "Aporte mensal": round(float(monthly), 2),
                "Total aportado": float(result["total_contributed"]),
                "Valor projetado": float(result["projected_value"]),
                "Ganho projetado": float(result["projected_gain"]),
            }
        )
    return rows


def _projection_frame(result: dict[str, object], value_key: str) -> pd.DataFrame:
    checkpoints = list(result.get("yearly_checkpoints", []) or [])
    if not checkpoints:
        return pd.DataFrame()
    frame = pd.DataFrame(checkpoints)
    rename = {
        "year": "Ano",
        "contributed": "Aportado",
        value_key: "Valor projetado",
        "projected_gain": "Ganho projetado",
        "income_generated": "Renda gerada",
        "cash_income_paid": "Renda recebida",
    }
    return frame.rename(columns={k: v for k, v in rename.items() if k in frame.columns})


def _render_planner() -> dict[str, object]:
    st.markdown("### 🧮 Planejador de patrimônio")
    st.caption(
        "Simule aportes e uma taxa anual hipotética. O resultado é cenário, não previsão."
    )
    c1, c2, c3, c4 = st.columns(4)
    initial = c1.number_input(
        "Valor inicial",
        min_value=0.0,
        value=1000.0,
        step=100.0,
        key="aq_invest_initial",
    )
    monthly = c2.number_input(
        "Aporte mensal",
        min_value=0.0,
        value=300.0,
        step=50.0,
        key="aq_invest_monthly",
    )
    annual_return = c3.number_input(
        "Cenário anual (%)",
        min_value=-50.0,
        max_value=100.0,
        value=8.0,
        step=0.5,
        key="aq_invest_return",
        help="Hipótese usada apenas para a simulação.",
    )
    years = c4.selectbox(
        "Prazo",
        [1, 3, 5, 10, 20, 30],
        index=3,
        key="aq_invest_years",
    )
    result = project_compound(
        CompoundProjectionInput(
            initial_amount=float(initial),
            monthly_contribution=float(monthly),
            annual_return_pct=float(annual_return),
            years=int(years),
        )
    )
    m1, m2, m3 = st.columns(3)
    m1.metric("Total aportado", format_brl(result["total_contributed"]))
    m2.metric("Valor projetado", format_brl(result["projected_value"]))
    m3.metric("Ganho projetado", format_brl(result["projected_gain"]))

    frame = _projection_frame(result, "projected_value")
    if not frame.empty:
        st.line_chart(
            frame.set_index("Ano")[["Aportado", "Valor projetado"]],
            use_container_width=True,
        )
        with st.expander("Ver evolução ano a ano"):
            st.dataframe(frame, hide_index=True, use_container_width=True)
    st.info(SIMULATION_NOTICE)
    return result


def _render_income() -> dict[str, object]:
    st.markdown("### 💵 Planejador de renda")
    st.caption(
        "Compare um cenário de renda distribuída com reinvestimento ou recebimento em caixa."
    )
    c1, c2, c3 = st.columns(3)
    initial = c1.number_input(
        "Capital inicial",
        min_value=0.0,
        value=10000.0,
        step=500.0,
        key="aq_income_initial",
    )
    monthly = c2.number_input(
        "Aporte mensal",
        min_value=0.0,
        value=500.0,
        step=50.0,
        key="aq_income_monthly",
    )
    years = c3.selectbox(
        "Prazo da renda",
        [1, 3, 5, 10, 20, 30],
        index=3,
        key="aq_income_years",
    )
    c4, c5, c6 = st.columns(3)
    income_yield = c4.number_input(
        "Renda anual hipotética (%)",
        min_value=0.01,
        max_value=50.0,
        value=8.0,
        step=0.5,
        key="aq_income_yield",
    )
    growth = c5.number_input(
        "Valorização anual hipotética (%)",
        min_value=-50.0,
        max_value=100.0,
        value=2.0,
        step=0.5,
        key="aq_income_growth",
    )
    reinvest = c6.toggle(
        "Reinvestir a renda",
        value=True,
        key="aq_income_reinvest",
    )
    result = project_income_asset(
        IncomeProjectionInput(
            initial_amount=float(initial),
            monthly_contribution=float(monthly),
            annual_income_yield_pct=float(income_yield),
            annual_price_growth_pct=float(growth),
            years=int(years),
            reinvest_income=bool(reinvest),
        )
    )

    m1, m2, m3 = st.columns(3)
    m1.metric("Total aportado", format_brl(result["total_contributed"]))
    m2.metric("Patrimônio projetado", format_brl(result["projected_portfolio_value"]))
    m3.metric("Renda gerada no período", format_brl(result["projected_income_generated"]))

    if not reinvest:
        st.metric("Renda projetada recebida em caixa", format_brl(result["projected_cash_income_paid"]))

    target = st.number_input(
        "Meta de renda mensal para simular",
        min_value=0.0,
        value=2000.0,
        step=100.0,
        key="aq_income_target",
    )
    if target > 0 and income_yield > 0:
        goal = required_capital_for_monthly_income(float(target), float(income_yield))
        st.caption(
            "Capital ilustrativo para essa meta, mantendo a hipótese informada: "
            + format_brl(goal["illustrative_required_capital"])
        )

    frame = _projection_frame(result, "portfolio_value")
    if not frame.empty:
        columns = [c for c in ("Aportado", "Valor projetado", "Renda gerada", "Renda recebida") if c in frame.columns]
        if columns:
            st.line_chart(frame.set_index("Ano")[columns], use_container_width=True)
    st.info(SIMULATION_NOTICE)
    return result


def _render_small_start() -> list[dict[str, float]]:
    st.markdown("### 🌱 Comece com pouco")
    years = st.selectbox(
        "Prazo para comparar",
        [5, 10, 20, 30],
        index=1,
        key="aq_small_years",
    )
    annual_return = st.number_input(
        "Cenário anual da comparação (%)",
        min_value=-50.0,
        max_value=100.0,
        value=8.0,
        step=0.5,
        key="aq_small_return",
    )
    rows = small_contribution_scenarios(
        (50.0, 100.0, 200.0),
        years=int(years),
        annual_return_pct=float(annual_return),
    )
    display = pd.DataFrame(rows)
    for col in ("Aporte mensal", "Total aportado", "Valor projetado", "Ganho projetado"):
        display[col] = display[col].map(format_brl)
    st.dataframe(display, hide_index=True, use_container_width=True)
    st.caption(
        "A comparação serve para mostrar o efeito de constância + tempo. "
        "A taxa é apenas uma hipótese editável."
    )
    st.info(SIMULATION_NOTICE)
    return rows


def _render_income_quality_lab() -> dict[str, object]:
    st.markdown("### 🧾 Qualidade da renda · laboratório")
    st.caption(
        "Insira dados observados de um ativo para organizar a análise. "
        "O índice não é probabilidade de pagamento nem recomendação."
    )
    c1, c2, c3 = st.columns(3)
    asset_type = c1.selectbox(
        "Tipo",
        ["ação", "FII"],
        key="aq_quality_type",
    )
    consistency = c2.slider(
        "Consistência de pagamentos (%)",
        0.0,
        100.0,
        80.0,
        1.0,
        key="aq_quality_consistency",
    )
    payout = c3.number_input(
        "Payout (%)",
        min_value=0.0,
        max_value=500.0,
        value=75.0,
        step=1.0,
        key="aq_quality_payout",
    )
    c4, c5, c6 = st.columns(3)
    debt = c4.number_input(
        "Dívida líquida / EBITDA",
        min_value=-10.0,
        max_value=30.0,
        value=2.0,
        step=0.1,
        key="aq_quality_debt",
    )
    growth = c5.number_input(
        "Crescimento lucro/FFO (%)",
        min_value=-100.0,
        max_value=300.0,
        value=5.0,
        step=1.0,
        key="aq_quality_growth",
    )
    fcf = c6.selectbox(
        "Fluxo de caixa livre",
        ["Positivo", "Negativo", "Não informado"],
        key="aq_quality_fcf",
    )
    vacancy = None
    if asset_type == "FII":
        vacancy = st.number_input(
            "Vacância (%)",
            min_value=0.0,
            max_value=100.0,
            value=8.0,
            step=0.5,
            key="aq_quality_vacancy",
        )
    fcf_value = True if fcf == "Positivo" else False if fcf == "Negativo" else None
    snapshot = dividend_quality_snapshot(
        asset_type=asset_type,
        payment_consistency_pct=float(consistency),
        payout_ratio_pct=float(payout),
        net_debt_to_ebitda=float(debt),
        earnings_or_ffo_growth_pct=float(growth),
        free_cash_flow_positive=fcf_value,
        vacancy_pct=None if vacancy is None else float(vacancy),
    )
    st.metric("Índice descritivo de qualidade", f"{snapshot['dividend_quality_index']:.0f}/100")
    if snapshot["positive_factors"]:
        st.success("Pontos favoráveis: " + " · ".join(snapshot["positive_factors"]))
    if snapshot["risk_flags"]:
        st.warning("Pontos para investigar: " + " · ".join(snapshot["risk_flags"]))
    st.caption(snapshot["interpretation"])
    return snapshot


def _render_growth_lab() -> dict[str, object]:
    st.markdown("### 🚀 Radar de crescimento · laboratório")
    st.caption(
        "Ferramenta para priorizar estudo de longo prazo; não prevê preço e não gera compra."
    )
    c1, c2, c3 = st.columns(3)
    revenue = c1.number_input(
        "Crescimento da receita (%)",
        min_value=-100.0,
        max_value=500.0,
        value=15.0,
        step=1.0,
        key="aq_growth_revenue",
    )
    earnings = c2.number_input(
        "Crescimento do lucro (%)",
        min_value=-100.0,
        max_value=500.0,
        value=15.0,
        step=1.0,
        key="aq_growth_earnings",
    )
    fcf = c3.number_input(
        "Margem de FCF (%)",
        min_value=-100.0,
        max_value=100.0,
        value=10.0,
        step=1.0,
        key="aq_growth_fcf",
    )
    c4, c5 = st.columns(2)
    debt = c4.number_input(
        "Dívida líquida / EBITDA",
        min_value=-10.0,
        max_value=30.0,
        value=1.5,
        step=0.1,
        key="aq_growth_debt",
    )
    dilution = c5.number_input(
        "Diluição de ações (%)",
        min_value=-100.0,
        max_value=300.0,
        value=0.0,
        step=0.5,
        key="aq_growth_dilution",
    )
    snapshot = growth_watch_snapshot(
        revenue_growth_pct=float(revenue),
        earnings_growth_pct=float(earnings),
        free_cash_flow_margin_pct=float(fcf),
        net_debt_to_ebitda=float(debt),
        share_dilution_pct=float(dilution),
    )
    st.metric("Índice descritivo de crescimento", f"{snapshot['growth_quality_index']:.0f}/100")
    if snapshot["reasons_to_monitor"]:
        st.success("Motivos para acompanhar: " + " · ".join(snapshot["reasons_to_monitor"]))
    if snapshot["risk_flags"]:
        st.warning("Riscos/pontos de atenção: " + " · ".join(snapshot["risk_flags"]))
    st.caption(snapshot["interpretation"])
    return snapshot


def render_investment_center(experience_mode: object = "Iniciante") -> dict[str, object]:
    mode = _mode(experience_mode)
    st.markdown("## 💰 Investir")
    st.write(
        "Planejamento de patrimônio e renda dentro do AtlasQuant, separado da área de operação."
    )
    st.caption(
        "Renda fixa e renda variável ficam separadas. FIIs, ações e ativos de crescimento "
        "não são tratados como renda fixa nem como aplicações sem risco."
    )

    st.markdown("#### Trilhas")
    a, b, c, d = st.columns(4)
    a.info("🏦 **Renda fixa**\n\nCDB, Tesouro, LCI/LCA · liquidez, prazo, risco e impostos.")
    b.info("🏢 **FIIs**\n\nRenda variável · distribuição, vacância, contratos e risco de mercado.")
    c.info("💸 **Dividendos**\n\nConsistência, payout, dívida, caixa e sustentabilidade.")
    d.info("🚀 **Crescimento**\n\nReceita, lucro, caixa, dívida, diluição e oportunidade de mercado.")

    sections = investment_sections(mode)
    selected = st.radio(
        "Ferramenta",
        sections,
        horizontal=True,
        key="aq_investment_tool",
    )

    result: dict[str, object] = {"mode": mode, "section": selected, "automatic_orders": False}
    if selected == "Planejador":
        result["projection"] = _render_planner()
    elif selected == "Renda":
        result["income"] = _render_income()
    elif selected == "Comece com pouco":
        result["small_start"] = _render_small_start()
    elif selected == "Qualidade da renda":
        result["quality"] = _render_income_quality_lab()
    elif selected == "Radar de crescimento":
        result["growth"] = _render_growth_lab()

    if mode == "Iniciante":
        st.info(
            "No modo Avançado aparecem também os laboratórios de Qualidade da Renda "
            "e Radar de Crescimento, com os critérios abertos para conferência."
        )

    st.warning(
        "O AtlasQuant não promete rentabilidade. Antes de investir, compare risco, "
        "liquidez, custos, impostos e se o produto combina com seu objetivo e prazo."
    )
    return result


__all__ = [
    "PANEL_VERSION",
    "format_brl",
    "investment_sections",
    "small_contribution_scenarios",
    "render_investment_center",
]
