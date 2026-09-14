"""USD Macro Pro V10.5 — Centro de Melhorias e Execução.

Implementa dentro do app o plano solicitado:
1) Interatividade dos dados
2) Contextualização e educação
3) Personalização e alertas
4) Design e usabilidade
5) Atualização e performance
6) Feedback e suporte
+ Plano de execução em 7 fases

Esta camada NÃO altera o motor de trading.
"""
from __future__ import annotations

from typing import Any, Callable
import json
import math

import pandas as pd
import streamlit as st

try:
    import altair as alt
except Exception:
    alt = None

try:
    from experience_v103 import INDICATOR_GUIDE
except Exception:
    INDICATOR_GUIDE = {}

try:
    from product_v104 import HISTORY_MAP, history_limit, freshness_by_frequency
except Exception:
    HISTORY_MAP = {}
    def history_limit(period: str, frequency: str) -> int:
        return 24
    def freshness_by_frequency(date_value: Any, frequency: str, now: Any = None):
        return ("SEM DATA", "⚪", None)


# Adiciona Saldo Comercial à área interativa solicitada.
HISTORY_V105 = dict(HISTORY_MAP)
HISTORY_V105.setdefault(
    "Saldo comercial",
    ("BOPGSTB", None, "Saldo comercial (milhões USD)", "monthly")
)

EDU_EXTRA = {
    "PIB": {
        "o_que_e": "Produto Interno Bruto: soma dos bens e serviços produzidos no país.",
        "impacto": "PIB forte sinaliza atividade resistente; pode sustentar juros mais altos e favorecer a moeda.",
    },
    "Inflação": {
        "o_que_e": "Aumento geral dos preços ao longo do tempo.",
        "impacto": "Inflação acima do esperado pode pressionar o banco central a manter juros altos.",
    },
    "Taxa de juros": {
        "o_que_e": "É o custo básico do dinheiro e influencia crédito, consumo, investimento e câmbio.",
        "impacto": "Juros relativamente mais altos tendem a aumentar a atratividade da moeda.",
    },
    "Desemprego": {
        "o_que_e": "Percentual da força de trabalho sem emprego e procurando trabalho.",
        "impacto": "Alta persistente pode indicar enfraquecimento econômico e aumentar expectativa de cortes de juros.",
    },
    "Saldo comercial": {
        "o_que_e": "Diferença entre exportações e importações de bens e serviços.",
        "impacto": "Mudanças persistentes podem afetar demanda pela moeda e percepção sobre a economia.",
    },
}

EXECUTION_PLAN = pd.DataFrame([
    {
        "Fase": "1. Diagnóstico e Planejamento",
        "Prazo de referência": "1–2 semanas",
        "Objetivo": "Coletar feedback e priorizar esforço x benefício",
        "Dentro do app": "Pesquisa, roadmap, A/B, notas de usabilidade",
        "Status": "✅ Implementado"
    },
    {
        "Fase": "2. Interatividade dos Gráficos",
        "Prazo de referência": "3–4 semanas",
        "Objetivo": "Zoom, toque, período e comparação",
        "Dentro do app": "Linha/barra/área + 1m/3m/6m/1a/5a + comparação normalizada",
        "Status": "✅ Implementado"
    },
    {
        "Fase": "3. Contextualização e Educação",
        "Prazo de referência": "2–3 semanas",
        "Objetivo": "Explicações simples de indicadores e impacto",
        "Dentro do app": "Modo explicativo + glossário + impacto no Forex",
        "Status": "✅ Implementado"
    },
    {
        "Fase": "4. Personalização",
        "Prazo de referência": "3–4 semanas",
        "Objetivo": "Indicadores favoritos e alertas configuráveis",
        "Dentro do app": "Meu painel + exportar/importar preferências + regras de alerta",
        "Status": "✅ Implementado"
    },
    {
        "Fase": "5. Design e Usabilidade",
        "Prazo de referência": "2–3 semanas",
        "Objetivo": "Responsividade, estética e navegação",
        "Dentro do app": "Temas, contraste, fonte, mobile, PWA, densidade visual",
        "Status": "✅ Implementado"
    },
    {
        "Fase": "6. Atualização e Performance",
        "Prazo de referência": "1–2 semanas",
        "Objetivo": "Dados frescos e carregamento rápido",
        "Dentro do app": "Cache 1h, frescor por cadência, atualização manual/1h/6h",
        "Status": "✅ Implementado"
    },
    {
        "Fase": "7. Feedback e Suporte",
        "Prazo de referência": "1–2 semanas",
        "Objetivo": "Canal de feedback e FAQ",
        "Dentro do app": "Formulário, anexo de print, FAQ e ajuda",
        "Status": "✅ Implementado"
    },
    {
        "Fase": "Pós-implementação",
        "Prazo de referência": "Contínuo",
        "Objetivo": "Monitorar uso, erros, A/B e satisfação",
        "Dentro do app": "Roadmap + feedback + histórico de performance + revisão periódica",
        "Status": "🟢 Contínuo"
    },
])


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        x = float(value)
        return x if math.isfinite(x) else float(default)
    except Exception:
        return float(default)


def _period_options() -> list[str]:
    return ["1 mês", "3 meses", "6 meses", "1 ano", "5 anos"]


def _limit_for_period(period: str, frequency: str) -> int:
    if period == "1 mês":
        if frequency == "daily":
            return 35
        if frequency == "quarterly":
            return 2
        return 2
    return history_limit(period, frequency)


def _normalize_series(df: pd.DataFrame, name: str) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=["date", "value", "normalized", "indicator"])
    d = df.copy()
    d["date"] = pd.to_datetime(d["date"], errors="coerce")
    d["value"] = pd.to_numeric(d["value"], errors="coerce")
    d = d.dropna(subset=["date", "value"]).sort_values("date")
    if d.empty:
        return pd.DataFrame(columns=["date", "value", "normalized", "indicator"])
    base = float(d["value"].iloc[0])
    if abs(base) < 1e-12:
        # Evita divisão por zero: usa mudança acumulada em pontos.
        d["normalized"] = 100.0 + (d["value"] - base)
    else:
        d["normalized"] = (d["value"] / base) * 100.0
    d["indicator"] = str(name)
    return d[["date", "value", "normalized", "indicator"]]


def _compare_chart(long_df: pd.DataFrame):
    if long_df is None or long_df.empty:
        st.info("Sem dados suficientes para comparação.")
        return
    if alt is None:
        pivot = long_df.pivot_table(index="date", columns="indicator", values="normalized", aggfunc="last")
        st.line_chart(pivot, use_container_width=True)
        return
    chart = (
        alt.Chart(long_df)
        .mark_line(point=True)
        .encode(
            x=alt.X("date:T", title="Data"),
            y=alt.Y("normalized:Q", title="Índice base 100", scale=alt.Scale(zero=False)),
            color=alt.Color("indicator:N", title="Indicador"),
            tooltip=[
                alt.Tooltip("indicator:N", title="Indicador"),
                alt.Tooltip("date:T", title="Data"),
                alt.Tooltip("value:Q", title="Valor original", format=".3f"),
                alt.Tooltip("normalized:Q", title="Base 100", format=".2f"),
            ],
        )
        .properties(height=380)
        .interactive()
    )
    st.altair_chart(chart, use_container_width=True)


def _single_chart(df: pd.DataFrame, label: str, chart_type: str = "Linha"):
    if df is None or df.empty:
        st.info("Sem dados.")
        return
    d = df.copy()
    d["date"] = pd.to_datetime(d["date"], errors="coerce")
    d["value"] = pd.to_numeric(d["value"], errors="coerce")
    d = d.dropna(subset=["date", "value"]).sort_values("date")
    if d.empty:
        st.info("Sem valores válidos.")
        return
    if alt is None:
        st.line_chart(d.set_index("date")["value"], use_container_width=True)
        return
    enc = {
        "x": alt.X("date:T", title="Data"),
        "y": alt.Y("value:Q", title=label, scale=alt.Scale(zero=False)),
        "tooltip": [
            alt.Tooltip("date:T", title="Data"),
            alt.Tooltip("value:Q", title=label, format=".3f"),
        ],
    }
    if chart_type == "Barra":
        chart = alt.Chart(d).mark_bar().encode(**enc)
    elif chart_type == "Área":
        chart = alt.Chart(d).mark_area(opacity=.30, line=True).encode(**enc)
    else:
        chart = alt.Chart(d).mark_line(point=True).encode(**enc)
    st.altair_chart(chart.properties(height=280).interactive(), use_container_width=True)


def _guide_for(indicator: str) -> dict[str, str]:
    if indicator in INDICATOR_GUIDE:
        raw = INDICATOR_GUIDE[indicator]
        return {
            "o_que_e": str(raw.get("o_que_e", "")),
            "impacto": str(raw.get("por_que_importa", raw.get("cadeia", ""))),
        }
    # Tenta aproximar nomes.
    aliases = {
        "CPI / IPC": "CPI / IPC",
        "PCE": "PCE",
        "Payroll / NFP": "Payroll / NFP",
        "Desemprego": "Desemprego",
        "PIB": "PIB",
        "Treasury 2Y": "Treasury 2Y",
        "Fed Funds": "Taxa de juros",
        "Saldo comercial": "Saldo comercial",
    }
    return EDU_EXTRA.get(aliases.get(indicator, indicator), {
        "o_que_e": "Indicador econômico usado para acompanhar o estado da economia.",
        "impacto": "Seu impacto depende do resultado versus consenso e do contexto de juros e crescimento.",
    })


def _export_preferences(prefs: dict[str, Any]) -> bytes:
    return json.dumps(prefs, ensure_ascii=False, indent=2).encode("utf-8")


def _load_preferences(raw: bytes) -> tuple[bool, dict[str, Any] | str]:
    try:
        obj = json.loads(raw.decode("utf-8"))
        if not isinstance(obj, dict):
            return False, "O arquivo precisa conter um objeto JSON."
        return True, obj
    except Exception as exc:
        return False, f"Arquivo inválido: {type(exc).__name__}"


def _latest_value(history_fetcher, indicator: str) -> dict[str, Any]:
    sid, units, label, freq = HISTORY_V105[indicator]
    df = history_fetcher(sid, 5, units)
    if df is None or df.empty:
        return {"indicator": indicator, "value": None, "date": None, "label": label, "frequency": freq}
    d = df.sort_values("date").iloc[-1]
    return {
        "indicator": indicator,
        "value": _safe_float(d["value"], float("nan")),
        "date": pd.Timestamp(d["date"]),
        "label": label,
        "frequency": freq,
    }


def _evaluate_alert(value: float, condition: str, limit: float) -> bool:
    if not math.isfinite(float(value)):
        return False
    if condition == "Acima de":
        return float(value) > float(limit)
    if condition == "Abaixo de":
        return float(value) < float(limit)
    if condition == "Maior ou igual":
        return float(value) >= float(limit)
    if condition == "Menor ou igual":
        return float(value) <= float(limit)
    return False


def render_v105_center(
    history_fetcher: Callable[[str, int, str | None], pd.DataFrame] | None = None,
    refresh_callback: Callable[[], tuple[bool, str]] | None = None,
    app_version: str = "",
):
    st.subheader("🧭 Centro de Melhorias — V10.5")
    st.caption(
        "Tudo que você pediu reunido dentro do app. "
        "Esta camada melhora experiência, análise e organização; não altera o motor de trading."
    )

    cards = st.columns(3)
    cards[0].metric("Interatividade", "✅ ATIVA", "comparação + zoom")
    cards[1].metric("Educação", "✅ ATIVA", "modo explicativo")
    cards[2].metric("Personalização", "✅ ATIVA", "preferências + alertas")
    cards2 = st.columns(3)
    cards2[0].metric("Design", "✅ RESPONSIVO", "web + PWA")
    cards2[1].metric("Atualização", "✅ MONITORADA", "frescor + cache")
    cards2[2].metric("Suporte", "✅ NO APP", "FAQ + feedback")

    tabs = st.tabs([
        "📊 Interatividade",
        "📚 Educação",
        "⭐ Personalização",
        "🎨 Design",
        "🕒 Atualização",
        "💬 Suporte",
        "🗺️ Plano de Execução",
    ])

    # --------------------------------------------------------
    # 1) Interatividade
    # --------------------------------------------------------
    with tabs[0]:
        st.markdown("### 📊 Interatividade dos dados")
        st.caption("Selecione período, tipo de gráfico e compare indicadores lado a lado.")

        if history_fetcher is None:
            st.warning("Histórico FRED indisponível nesta execução.")
        else:
            mode = st.radio(
                "Modo de análise",
                ["Um indicador", "Comparar indicadores"],
                horizontal=True,
                key="v105_chart_mode",
            )
            period = st.radio(
                "Intervalo",
                _period_options(),
                index=3,
                horizontal=True,
                key="v105_period",
            )

            if mode == "Um indicador":
                indicator = st.selectbox("Indicador", list(HISTORY_V105), key="v105_single_indicator")
                chart_type = st.radio(
                    "Tipo de gráfico",
                    ["Linha", "Barra", "Área"],
                    horizontal=True,
                    key="v105_single_chart_type",
                )
                sid, units, label, freq = HISTORY_V105[indicator]
                df = history_fetcher(sid, _limit_for_period(period, freq), units)
                _single_chart(df, label, chart_type)

                guide = _guide_for(indicator)
                st.info(f"ℹ️ **{indicator}:** {guide['o_que_e']}")
                st.caption(f"Impacto prático: {guide['impacto']}")

                if isinstance(df, pd.DataFrame) and not df.empty:
                    last = df.sort_values("date").iloc[-1]
                    fresh, dot, age = freshness_by_frequency(last["date"], freq)
                    st.success(
                        f"{dot} Última observação: {pd.Timestamp(last['date']).strftime('%d/%m/%Y')} "
                        f"· {fresh} · idade {age} dia(s)"
                    )
            else:
                selected = st.multiselect(
                    "Compare de 2 a 4 indicadores",
                    list(HISTORY_V105),
                    default=["CPI / IPC", "PCE"],
                    max_selections=4,
                    key="v105_compare_indicators",
                )
                if len(selected) < 2:
                    st.info("Escolha pelo menos 2 indicadores.")
                else:
                    frames = []
                    latest_rows = []
                    for indicator in selected:
                        sid, units, label, freq = HISTORY_V105[indicator]
                        df = history_fetcher(sid, _limit_for_period(period, freq), units)
                        frames.append(_normalize_series(df, indicator))
                        if isinstance(df, pd.DataFrame) and not df.empty:
                            last = df.sort_values("date").iloc[-1]
                            latest_rows.append({
                                "Indicador": indicator,
                                "Último valor": float(last["value"]),
                                "Data": pd.Timestamp(last["date"]).strftime("%d/%m/%Y"),
                            })
                    long_df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
                    st.markdown("#### Comparação normalizada · base 100")
                    st.caption(
                        "Como os indicadores usam unidades diferentes, a comparação usa base 100 "
                        "para comparar direção/tendência sem misturar escalas."
                    )
                    _compare_chart(long_df)
                    if latest_rows:
                        st.dataframe(pd.DataFrame(latest_rows), hide_index=True, use_container_width=True)

                    st.markdown("#### Lado a lado")
                    cols = st.columns(min(2, len(selected)))
                    for i, indicator in enumerate(selected):
                        with cols[i % len(cols)]:
                            sid, units, label, freq = HISTORY_V105[indicator]
                            df = history_fetcher(sid, _limit_for_period(period, freq), units)
                            st.markdown(f"**{indicator}**")
                            _single_chart(df, label, "Linha")

    # --------------------------------------------------------
    # 2) Educação
    # --------------------------------------------------------
    with tabs[1]:
        st.markdown("### 📚 Modo explicativo")
        st.info(
            "Ative esta área quando quiser entender o dado antes de usar no Forex. "
            "A leitura continua simples: dado → economia → Fed → juros → USD → par."
        )
        indicator = st.selectbox(
            "O que você quer aprender?",
            list(HISTORY_V105),
            key="v105_edu_indicator",
        )
        guide = _guide_for(indicator)
        st.markdown(
            f"""
<div style="padding:1rem;border:1px solid rgba(120,140,160,.35);border-radius:14px">
<b>{indicator}</b><br><br>
<b>O que é:</b> {guide['o_que_e']}<br><br>
<b>Por que importa:</b> {guide['impacto']}
</div>
""",
            unsafe_allow_html=True,
        )
        st.markdown("#### 🧠 Cadeia prática")
        st.markdown(
            "**Indicador → surpresa versus consenso → atividade/inflação/emprego → Fed → juros → USD → par cambial.**"
        )
        st.warning("Um indicador isolado não é sinal de entrada. O contexto e a confirmação técnica continuam obrigatórios.")

    # --------------------------------------------------------
    # 3) Personalização + alertas
    # --------------------------------------------------------
    with tabs[2]:
        st.markdown("### ⭐ Meu painel e preferências")
        tracked = st.multiselect(
            "Indicadores favoritos",
            list(HISTORY_V105),
            default=st.session_state.get("v105_tracked", ["CPI / IPC", "PCE", "Payroll / NFP", "Fed Funds"]),
            key="v105_tracked",
        )
        layout = st.radio(
            "Layout preferido",
            ["Compacto", "Confortável", "Detalhado"],
            horizontal=True,
            key="v105_layout_pref",
        )
        explain_mode = st.toggle(
            "Mostrar explicações junto aos indicadores",
            value=bool(st.session_state.get("v105_explain_mode", True)),
            key="v105_explain_mode",
        )
        prefs = {
            "indicadores": tracked,
            "layout": layout,
            "modo_explicativo": explain_mode,
        }
        st.download_button(
            "⬇️ Exportar minhas preferências",
            _export_preferences(prefs),
            "usd_macro_preferencias.json",
            "application/json",
            use_container_width=True,
        )

        uploaded = st.file_uploader("Importar preferências (.json)", type=["json"], key="v105_pref_upload")
        if uploaded is not None and st.button("📥 Aplicar preferências importadas", key="v105_apply_prefs"):
            ok, obj = _load_preferences(uploaded.getvalue())
            if ok:
                st.session_state["v105_imported_prefs"] = obj
                st.success(
                    "Preferências lidas. Por segurança do Streamlit, aplique manualmente os campos desejados nesta tela."
                )
                st.json(obj)
            else:
                st.error(str(obj))

        st.markdown("### 🔔 Alertas configuráveis dentro do app")
        st.caption(
            "Estes alertas são verificados quando o app está aberto/atualizado. "
            "Push com o app fechado exige serviço externo e não é prometido nesta versão."
        )

        if history_fetcher is None:
            st.warning("Fonte histórica indisponível para verificar alertas.")
        else:
            defaults = pd.DataFrame([
                {"Ativo": True, "Indicador": "CPI / IPC", "Condição": "Acima de", "Limite": 3.0, "Frequência": "Imediata"},
                {"Ativo": True, "Indicador": "Desemprego", "Condição": "Acima de", "Limite": 4.5, "Frequência": "Diária"},
                {"Ativo": False, "Indicador": "Treasury 2Y", "Condição": "Acima de", "Limite": 5.0, "Frequência": "Imediata"},
            ])
            rules = st.data_editor(
                st.session_state.get("v105_alert_rules", defaults),
                num_rows="dynamic",
                use_container_width=True,
                key="v105_alert_editor",
                column_config={
                    "Ativo": st.column_config.CheckboxColumn("Ativo"),
                    "Indicador": st.column_config.SelectboxColumn("Indicador", options=list(HISTORY_V105)),
                    "Condição": st.column_config.SelectboxColumn(
                        "Condição", options=["Acima de", "Abaixo de", "Maior ou igual", "Menor ou igual"]
                    ),
                    "Limite": st.column_config.NumberColumn("Limite", format="%.3f"),
                    "Frequência": st.column_config.SelectboxColumn(
                        "Frequência", options=["Imediata", "Diária", "Semanal"]
                    ),
                },
            )
            st.session_state["v105_alert_rules"] = rules

            if st.button("🔎 Verificar alertas agora", type="primary", key="v105_check_alerts"):
                hits = []
                checked = []
                for _, row in rules.iterrows():
                    if not bool(row.get("Ativo", False)):
                        continue
                    indicator = str(row.get("Indicador", ""))
                    if indicator not in HISTORY_V105:
                        continue
                    latest = _latest_value(history_fetcher, indicator)
                    value = latest.get("value")
                    if value is None or not math.isfinite(float(value)):
                        continue
                    condition = str(row.get("Condição", "Acima de"))
                    limit = _safe_float(row.get("Limite", 0.0))
                    triggered = _evaluate_alert(float(value), condition, limit)
                    checked.append({
                        "Indicador": indicator,
                        "Valor atual": float(value),
                        "Condição": condition,
                        "Limite": limit,
                        "Disparou": "SIM" if triggered else "não",
                    })
                    if triggered:
                        hits.append((indicator, float(value), condition, limit))

                if checked:
                    st.dataframe(pd.DataFrame(checked), hide_index=True, use_container_width=True)
                if hits:
                    for indicator, value, condition, limit in hits:
                        st.warning(f"🔔 {indicator}: {value:.3f} está {condition.lower()} {limit:.3f}.")
                else:
                    st.success("Nenhum alerta configurado foi disparado nesta verificação.")

    # --------------------------------------------------------
    # 4) Design
    # --------------------------------------------------------
    with tabs[3]:
        st.markdown("### 🎨 Design e usabilidade")
        st.markdown(
            "- ✅ Layout responsivo para celular, tablet e desktop\n"
            "- ✅ PWA instalável no Android/PC e tela inicial no iPhone\n"
            "- ✅ Tema claro, escuro e alto contraste\n"
            "- ✅ Fonte normal, grande e muito grande\n"
            "- ✅ Botões grandes para toque\n"
            "- ✅ Abas roláveis em telas pequenas\n"
            "- ✅ Painel Mestre sem depender de texto truncado para decisão"
        )
        density = st.radio(
            "Densidade visual desta sessão",
            ["Compacta", "Normal", "Espaçosa"],
            horizontal=True,
            key="v105_density",
        )
        if density == "Compacta":
            st.markdown(
                "<style>.block-container{padding-top:.6rem!important}.stMarkdown p{margin-bottom:.35rem!important}</style>",
                unsafe_allow_html=True,
            )
        elif density == "Espaçosa":
            st.markdown(
                "<style>.block-container{padding-top:1.5rem!important}.stMarkdown p{margin-bottom:.9rem!important}</style>",
                unsafe_allow_html=True,
            )
        st.info("As opções globais de tema, tamanho do texto e acessibilidade continuam na barra lateral.")

    # --------------------------------------------------------
    # 5) Atualização e Performance
    # --------------------------------------------------------
    with tabs[4]:
        st.markdown("### 🕒 Atualização e performance")
        st.caption("Dados econômicos são atualizados conforme a cadência da fonte; nem todo indicador é tempo real.")
        if history_fetcher is None:
            st.warning("Fonte histórica indisponível.")
        else:
            popular = ["CPI / IPC", "PCE", "Payroll / NFP", "PIB", "Treasury 2Y", "Fed Funds"]
            rows = []
            for indicator in popular:
                latest = _latest_value(history_fetcher, indicator)
                if latest["date"] is None:
                    rows.append({
                        "Indicador": indicator, "Último valor": "—", "Data": "—",
                        "Frescor": "⚪ SEM DADO", "Cadência": latest["frequency"]
                    })
                    continue
                fresh, dot, age = freshness_by_frequency(latest["date"], latest["frequency"])
                rows.append({
                    "Indicador": indicator,
                    "Último valor": round(float(latest["value"]), 3),
                    "Data": pd.Timestamp(latest["date"]).strftime("%d/%m/%Y"),
                    "Frescor": f"{dot} {fresh} ({age}d)",
                    "Cadência": latest["frequency"],
                })
            st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)

        u1, u2 = st.columns(2)
        u1.metric("Cache histórico", "1 hora")
        u2.metric("Atualizado na tela", pd.Timestamp.now(tz="UTC").strftime("%H:%M UTC"))
        if st.button("🔄 Forçar renovação do histórico", key="v105_refresh_history"):
            if refresh_callback:
                ok, msg = refresh_callback()
                (st.success if ok else st.warning)(msg)
            else:
                st.info("Atualização central indisponível nesta execução.")

        st.warning(
            "Atualização garantida em segundo plano com o app fechado não é função confiável do Streamlit. "
            "Para tarefas de background, use GitHub Actions/serviço externo. O app mostra frescor para evitar falsa sensação de tempo real."
        )

    # --------------------------------------------------------
    # 6) Feedback e Suporte
    # --------------------------------------------------------
    with tabs[5]:
        st.markdown("### 💬 Feedback e suporte")
        st.success("O app já possui formulário de feedback, anexo de print e FAQ na aba Produto.")
        st.markdown(
            "#### Perguntas rápidas\n"
            "**O app garante lucro?** Não. Ele organiza confluência e filtros.\n\n"
            "**Por que um dado pode estar antigo?** Porque CPI, PIB, PCE e Payroll seguem calendário de publicação.\n\n"
            "**Por que não recebo push com o app fechado?** Push real exige infraestrutura externa.\n\n"
            "**Onde reporto problema?** Use Produto → Feedback e anexe um print."
        )
        st.markdown(
            "#### Roteiro de pesquisa com usuários\n"
            "1. Quais indicadores você acompanha regularmente?\n"
            "2. Sente falta de algum indicador?\n"
            "3. A navegação está clara?\n"
            "4. O que pode melhorar?\n"
            "5. Os gráficos são fáceis de interpretar?\n"
            "6. Gostaria de outras visualizações?\n"
            "7. Quais alertas seriam úteis?\n"
            "8. Sentiu lentidão?\n"
            "9. O que aumenta/diminui seu interesse?\n"
            "10. Nota geral de 0 a 10."
        )

    # --------------------------------------------------------
    # 7) Plano de Execução
    # --------------------------------------------------------
    with tabs[6]:
        st.markdown("### 🗺️ Plano de execução dentro do app")
        st.dataframe(EXECUTION_PLAN, hide_index=True, use_container_width=True)
        implemented = EXECUTION_PLAN["Status"].astype(str).str.contains("✅|🟢", regex=True).sum()
        progress = implemented / len(EXECUTION_PLAN)
        st.progress(progress)
        st.caption(f"{implemented}/{len(EXECUTION_PLAN)} fases estão implementadas ou em operação contínua.")
        st.download_button(
            "⬇️ Baixar plano em CSV",
            EXECUTION_PLAN.to_csv(index=False).encode("utf-8"),
            "plano_execucao_v105.csv",
            "text/csv",
            use_container_width=True,
        )
        st.info(
            "O plano aparece no app para acompanhamento. As melhorias futuras devem ser promovidas para o motor "
            "somente quando houver evidência de que aumentam qualidade sem introduzir instabilidade."
        )
