"""Experiência, acessibilidade, educação e personalização — USD Macro Pro V10.3.

Esta camada NÃO altera Score Mestre, Gate, direção macro ou histórico oficial.
Ela melhora apresentação, compreensão, preferências, alertas visuais e transparência
sobre a atualização das fontes.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping
import math

import pandas as pd
import streamlit as st

try:
    import altair as alt
except Exception:  # fallback: o app continua sem gráfico Altair
    alt = None


INDICATOR_GUIDE = {
    "Taxa de juros": {
        "sigla": "Fed Funds / taxa do BC",
        "o_que_e": "É o custo básico do dinheiro definido pelo banco central.",
        "por_que_importa": "Juros relativamente mais altos tendem a aumentar a atratividade da moeda.",
        "cadeia": "Juros ↑ → rendimento relativo ↑ → moeda tende a ganhar força.",
        "frequencia": "Decisões periódicas do banco central; não muda a cada tick.",
    },
    "CPI / IPC": {
        "sigla": "CPI",
        "o_que_e": "Mede a variação de preços ao consumidor.",
        "por_que_importa": "Inflação acima do esperado pode pressionar o Fed a manter juros altos.",
        "cadeia": "CPI ↑ acima do consenso → Fed mais hawkish → USD tende a fortalecer.",
        "frequencia": "Mensal.",
    },
    "Core CPI": {
        "sigla": "Core CPI",
        "o_que_e": "Inflação ao consumidor excluindo itens mais voláteis, como alimentos e energia.",
        "por_que_importa": "Ajuda a enxergar a persistência da inflação.",
        "cadeia": "Core CPI persistente → cortes de juros menos prováveis → suporte ao USD.",
        "frequencia": "Mensal.",
    },
    "PCE": {
        "sigla": "PCE",
        "o_que_e": "Índice de preços de consumo acompanhado de perto pelo Federal Reserve.",
        "por_que_importa": "É uma das principais referências de inflação para a política monetária dos EUA.",
        "cadeia": "PCE forte → expectativa de juros mais altos por mais tempo → USD tende a ganhar força.",
        "frequencia": "Mensal.",
    },
    "Payroll / NFP": {
        "sigla": "NFP",
        "o_que_e": "Variação mensal do emprego não agrícola nos Estados Unidos.",
        "por_que_importa": "Mostra a força do mercado de trabalho e pode alterar expectativas para o Fed.",
        "cadeia": "Payroll forte + salários fortes → economia resistente → Fed menos dovish.",
        "frequencia": "Mensal.",
    },
    "Desemprego": {
        "sigla": "Unemployment Rate",
        "o_que_e": "Percentual da força de trabalho que está desempregada e procurando emprego.",
        "por_que_importa": "Uma alta persistente pode sinalizar enfraquecimento econômico.",
        "cadeia": "Desemprego ↑ → crescimento esfria → cortes de juros ficam mais prováveis.",
        "frequencia": "Mensal.",
    },
    "PIB": {
        "sigla": "GDP / PIB",
        "o_que_e": "Mede a produção total da economia.",
        "por_que_importa": "Ajuda a identificar expansão, desaceleração ou recessão.",
        "cadeia": "PIB forte → atividade forte → juros podem permanecer altos → moeda recebe suporte.",
        "frequencia": "Trimestral, com revisões.",
    },
    "ISM / PMI": {
        "sigla": "ISM / PMI",
        "o_que_e": "Pesquisas de atividade empresarial. Acima de 50 geralmente indica expansão.",
        "por_que_importa": "São dados rápidos sobre a direção da economia.",
        "cadeia": "PMI ↑ → atividade ↑ → inflação/juros podem permanecer firmes → impacto na moeda.",
        "frequencia": "Mensal.",
    },
    "Treasury 2Y": {
        "sigla": "US 2Y",
        "o_que_e": "Rendimento do título do Tesouro americano de 2 anos.",
        "por_que_importa": "É muito sensível às expectativas de juros do Fed.",
        "cadeia": "2Y ↑ → mercado precifica juros maiores → tende a favorecer o USD.",
        "frequencia": "Mercado: varia durante a sessão.",
    },
    "Fed": {
        "sigla": "Federal Reserve",
        "o_que_e": "Banco central dos Estados Unidos.",
        "por_que_importa": "Sua política monetária influencia o dólar e ativos no mundo todo.",
        "cadeia": "Hawkish → juros altos por mais tempo → USD tende a fortalecer; dovish → efeito contrário.",
        "frequencia": "Reuniões, atas, discursos e comunicados.",
    },
    "ADR14": {
        "sigla": "ADR14",
        "o_que_e": "Média do range diário dos últimos 14 pregões.",
        "por_que_importa": "Ajuda a saber se o preço já percorreu grande parte do movimento diário típico.",
        "cadeia": "ADR consumido muito alto → maior risco de perseguir um movimento esticado.",
        "frequencia": "Atualizado com os candles diários.",
    },
    "W1 / D1": {
        "sigla": "Weekly / Daily",
        "o_que_e": "Leitura de estrutura e tendência dos gráficos semanal e diário.",
        "por_que_importa": "Evita executar contra a estrutura de prazo maior.",
        "cadeia": "Macro + W1 + D1 alinhados → contexto mais limpo para buscar execução.",
        "frequencia": "Atualiza conforme novos candles e estrutura.",
    },
    "BSL / SSL": {
        "sigla": "Buy-side / Sell-side Liquidity",
        "o_que_e": "Referências de liquidez acima das máximas e abaixo das mínimas.",
        "por_que_importa": "Ajudam a mapear onde o preço pode buscar ordens antes de expandir ou rejeitar.",
        "cadeia": "Sweep de liquidez + contexto macro + estrutura → possível confirmação adicional.",
        "frequencia": "Intraday / conforme o preço negocia os níveis.",
    },
    "Killzones": {
        "sigla": "ICT Killzones",
        "o_que_e": "Janelas horárias de maior interesse operacional, como Londres e Nova York.",
        "por_que_importa": "Organizam o timing; não determinam direção sozinhas.",
        "cadeia": "Viés definido → liquidez mapeada → killzone → H4/H1 → gatilho M15.",
        "frequencia": "Janelas horárias diárias.",
    },
    "Quarterly Theory": {
        "sigla": "Quarterly",
        "o_que_e": "Moldura temporal heurística que divide ciclos em quatro partes.",
        "por_que_importa": "Ajuda a organizar expectativa temporal de acumulação, manipulação e expansão.",
        "cadeia": "É contexto de timing; nunca deve substituir macro, estrutura ou gestão de risco.",
        "frequencia": "Depende da escala escolhida.",
    },
}

DEFAULT_TRACKED = ["Taxa de juros", "CPI / IPC", "PCE", "Payroll / NFP", "ISM / PMI", "Fed", "Treasury 2Y"]


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        n = float(value)
        return n if math.isfinite(n) else float(default)
    except Exception:
        return float(default)


def inflation_projection(amount: float, annual_rate_pct: float, years: float) -> dict[str, float]:
    amount = max(0.0, _safe_float(amount))
    rate = _safe_float(annual_rate_pct) / 100.0
    years = max(0.0, _safe_float(years))
    future_cost = amount * ((1.0 + rate) ** years) if rate > -1 else 0.0
    purchasing_power = amount / ((1.0 + rate) ** years) if rate > -1 else 0.0
    return {
        "future_cost": float(future_cost),
        "purchasing_power": float(purchasing_power),
        "loss_pct": float(max(0.0, (1.0 - purchasing_power / amount) * 100.0)) if amount > 0 else 0.0,
    }


def select_alert_hits(
    matrix: pd.DataFrame,
    min_score: float = 85.0,
    min_quality: float = 75.0,
    allowed_pairs: list[str] | None = None,
) -> list[dict[str, Any]]:
    if matrix is None or matrix.empty:
        return []
    allowed = set(allowed_pairs or [])
    hits: list[dict[str, Any]] = []
    for _, row in matrix.iterrows():
        pair = str(row.get("Par", ""))
        if allowed and pair not in allowed:
            continue
        direction = str(row.get("Direção", row.get("Direcao", "")))
        score = _safe_float(row.get("Score final", row.get("Score", 0.0)))
        quality = _safe_float(row.get("Qualidade", 0.0))
        if direction.startswith(("COMPRA", "VENDA")) and score >= min_score and quality >= min_quality:
            hits.append({
                "Par": pair,
                "Direção": direction,
                "Score": score,
                "Qualidade": quality,
            })
    return sorted(hits, key=lambda x: (x["Score"], x["Qualidade"]), reverse=True)


def _theme_css(theme: str, font_scale: str, reduced_motion: bool) -> str:
    scale = {"Normal": 1.0, "Grande": 1.10, "Muito grande": 1.20}.get(font_scale, 1.0)

    if theme == "Escuro":
        bg, card, text, muted, border, accent = "#0b1220", "#111c2e", "#eef5ff", "#a8b4c7", "#263955", "#4ea1ff"
    elif theme == "Alto contraste":
        bg, card, text, muted, border, accent = "#000000", "#080808", "#ffffff", "#ffffff", "#ffffff", "#00e5ff"
    else:
        bg, card, text, muted, border, accent = "#f5f8fc", "#ffffff", "#132238", "#5f6f82", "#dbe4ee", "#1565c0"

    motion = "*, *::before, *::after {animation: none !important; transition: none !important; scroll-behavior: auto !important;}" if reduced_motion else ""

    return f"""
    <style>
      :root {{
        --ux-bg:{bg}; --ux-card:{card}; --ux-text:{text}; --ux-muted:{muted};
        --ux-border:{border}; --ux-accent:{accent}; --ux-scale:{scale};
      }}
      .stApp {{
        background: var(--ux-bg);
        color: var(--ux-text);
        font-size: calc(1rem * var(--ux-scale));
      }}
      [data-testid="stSidebar"] {{
        background: color-mix(in srgb, var(--ux-card) 94%, var(--ux-bg));
        border-right: 1px solid var(--ux-border);
      }}
      [data-testid="stMetric"] {{
        background: var(--ux-card);
        border: 1px solid var(--ux-border);
        border-radius: 16px;
        padding: .85rem .9rem;
        box-shadow: 0 6px 18px rgba(10, 30, 60, .06);
      }}
      [data-testid="stMetricLabel"], .stCaption, [data-testid="stCaptionContainer"] {{
        color: var(--ux-muted) !important;
      }}
      .stButton > button, [data-testid="stDownloadButton"] button {{
        min-height: 44px;
        border-radius: 12px;
        font-weight: 650;
      }}
      [data-baseweb="tab-list"] {{
        gap: .25rem;
        overflow-x: auto;
        scrollbar-width: thin;
      }}
      [data-baseweb="tab"] {{
        min-height: 46px;
        white-space: nowrap;
      }}
      div[data-testid="stDataFrame"] {{
        border: 1px solid var(--ux-border);
        border-radius: 14px;
        overflow: hidden;
      }}
      .ux-card {{
        background: var(--ux-card);
        color: var(--ux-text);
        border: 1px solid var(--ux-border);
        border-radius: 16px;
        padding: 1rem 1.05rem;
        margin: .35rem 0 .75rem;
        box-shadow: 0 8px 22px rgba(10, 30, 60, .06);
      }}
      .ux-badge {{
        display:inline-block; padding:.25rem .55rem; margin:.12rem;
        border:1px solid var(--ux-border); border-radius:999px;
        background:var(--ux-card); color:var(--ux-text); font-size:.88rem;
      }}
      .ux-accent {{ color: var(--ux-accent); font-weight: 700; }}
      @media (max-width: 780px) {{
        .block-container {{
          padding: .75rem .6rem 4.5rem !important;
          max-width: 100% !important;
        }}
        h1 {{ font-size: 1.65rem !important; line-height:1.18 !important; }}
        h2 {{ font-size: 1.35rem !important; }}
        h3 {{ font-size: 1.16rem !important; }}
        [data-testid="stHorizontalBlock"] {{
          flex-wrap: wrap !important;
          gap: .55rem !important;
        }}
        [data-testid="column"] {{
          min-width: min(100%, 215px) !important;
          flex: 1 1 215px !important;
        }}
        [data-testid="stMetric"] {{
          min-width: 0 !important;
          padding: .72rem .72rem !important;
        }}
        [data-testid="stMetricValue"] {{
          font-size: 1.55rem !important;
          white-space: normal !important;
          overflow-wrap: anywhere !important;
        }}
        button {{
          white-space: normal !important;
          line-height:1.15 !important;
        }}
      }}
      {motion}
    </style>
    """



def experience_theme_summary(theme: str, font_scale: str, reduced_motion: bool) -> dict[str,Any]:
    allowed={"Claro","Escuro","Alto contraste"}
    safe_theme=theme if theme in allowed else "Claro"
    safe_font=font_scale if font_scale in {"Normal","Grande","Muito grande"} else "Normal"
    return {"theme":safe_theme,"font_scale":safe_font,"reduced_motion":bool(reduced_motion),"responsive":True}


def render_experience_controls() -> dict[str, Any]:
    with st.sidebar.expander("🎨 Aparência & acessibilidade", expanded=False):
        theme = st.selectbox(
            "Tema do aplicativo",
            ["Claro", "Escuro", "Alto contraste"],
            index=["Claro", "Escuro", "Alto contraste"].index(st.session_state.get("ux103_theme", "Claro"))
            if st.session_state.get("ux103_theme", "Claro") in ["Claro", "Escuro", "Alto contraste"] else 0,
            key="ux103_theme",
            help="Muda apenas a apresentação. Não altera cálculos ou sinais.",
        )
        font_scale = st.selectbox(
            "Tamanho do texto",
            ["Normal", "Grande", "Muito grande"],
            key="ux103_font_scale",
        )
        reduced_motion = st.toggle(
            "Reduzir animações",
            value=bool(st.session_state.get("ux103_reduce_motion", False)),
            key="ux103_reduce_motion",
            help="Útil para conforto visual e acessibilidade.",
        )
        st.caption("O layout responsivo também foi reforçado para celular e tablet.")

    prefs=experience_theme_summary(theme,font_scale,reduced_motion)
    st.markdown(_theme_css(prefs["theme"], prefs["font_scale"], prefs["reduced_motion"]), unsafe_allow_html=True)
    st.sidebar.caption(f"Interface: {prefs['theme']} · Texto {prefs['font_scale']} · Mobile responsivo")
    return prefs


def _currency_chart(ranking: pd.DataFrame):
    if ranking is None or ranking.empty:
        st.info("Ranking ainda indisponível.")
        return
    value_col = "Pontuação_Final" if "Pontuação_Final" in ranking.columns else "Pontuação Macro"
    code_col = "Código" if "Código" in ranking.columns else "Moeda"
    if value_col not in ranking.columns or code_col not in ranking.columns:
        st.info("Colunas do ranking não disponíveis para o gráfico.")
        return
    df = ranking[[code_col, value_col]].copy()
    df[value_col] = pd.to_numeric(df[value_col], errors="coerce")
    df = df.dropna()
    if alt is None:
        st.bar_chart(df.set_index(code_col)[value_col], width="stretch")
        return
    chart = (
        alt.Chart(df)
        .mark_bar(cornerRadiusTopLeft=5, cornerRadiusTopRight=5)
        .encode(
            x=alt.X(f"{code_col}:N", title="Moeda", sort="-y"),
            y=alt.Y(f"{value_col}:Q", title="Força / score"),
            tooltip=[alt.Tooltip(f"{code_col}:N", title="Moeda"), alt.Tooltip(f"{value_col}:Q", title="Score", format=".1f")],
        )
        .properties(height=300)
        .interactive()
    )
    st.altair_chart(chart, width="stretch")


def render_experience_hub(
    ranking: pd.DataFrame,
    matrix: pd.DataFrame,
    macro_context: Mapping[str, Any] | None = None,
    source_status: Mapping[str, Any] | None = None,
    app_version: str = "",
) -> None:
    macro = dict(macro_context or {})
    sources = dict(source_status or {})

    st.subheader("✨ Experiência, Aprendizado & Personalização — V10.3")
    st.caption(
        "Camada educacional e de interface. Não altera Score Mestre, Gate, direção, "
        "Market Map ou histórico oficial."
    )

    t1, t2, t3, t4, t5 = st.tabs([
        "⭐ Meu painel",
        "📚 Aprenda",
        "🔔 Alertas",
        "🕒 Dados & fontes",
        "🧮 Simulador",
    ])

    with t1:
        st.markdown("### ⭐ Meus indicadores")
        tracked = st.multiselect(
            "Escolha o que você quer acompanhar",
            list(INDICATOR_GUIDE.keys()),
            default=st.session_state.get("ux103_tracked", DEFAULT_TRACKED),
            key="ux103_tracked",
            help="A seleção personaliza esta sessão do aplicativo.",
        )
        available_pairs = matrix["Par"].astype(str).tolist() if matrix is not None and not matrix.empty and "Par" in matrix.columns else []
        favorites = st.multiselect(
            "Pares favoritos",
            available_pairs,
            default=[p for p in st.session_state.get("ux103_favorite_pairs", ["EUR/USD", "USD/CHF"]) if p in available_pairs],
            key="ux103_favorite_pairs",
        )

        st.markdown(
            '<div class="ux-card"><span class="ux-accent">Seu painel rápido</span><br>'
            'Os itens escolhidos ficam destacados nesta sessão. '
            'Nenhuma preferência altera o motor de decisão.</div>',
            unsafe_allow_html=True,
        )

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("USD macro", f"{_safe_float(macro.get('usd_score', 50)):.0f}/100")
        m2.metric("Qualidade USD", f"{_safe_float(macro.get('usd_quality', 0)):.0f}%")
        m3.metric("Fed", str(macro.get("fed_tone", "Neutro")))
        m4.metric("Surpresa macro", f"{_safe_float(macro.get('surprise_adjustment', 0)):+.1f}")

        if tracked:
            st.markdown("**Acompanhar:** " + " ".join(f'<span class="ux-badge">{x}</span>' for x in tracked), unsafe_allow_html=True)
        if favorites:
            st.markdown("**Favoritos:** " + " ".join(f'<span class="ux-badge">{x}</span>' for x in favorites), unsafe_allow_html=True)

        st.markdown("### 📊 Força das moedas — gráfico interativo")
        st.caption("Passe o mouse ou toque no gráfico para explorar os valores.")
        _currency_chart(ranking)

    with t2:
        st.markdown("### 📚 Aprenda no próprio app")
        indicator = st.selectbox("Escolha um conceito", list(INDICATOR_GUIDE.keys()), key="ux103_learn_indicator")
        info = INDICATOR_GUIDE[indicator]
        st.markdown(f"""
<div class="ux-card">
  <div class="ux-accent">ℹ️ {indicator} · {info['sigla']}</div>
  <p><b>O que é:</b> {info['o_que_e']}</p>
  <p><b>Por que importa:</b> {info['por_que_importa']}</p>
  <p><b>Cadeia prática:</b> {info['cadeia']}</p>
  <p><b>Atualização:</b> {info['frequencia']}</p>
</div>
""", unsafe_allow_html=True)

        with st.expander("🧠 Cadeia macro que usamos no Forex", expanded=True):
            st.markdown(
                "**Dados → Economia → Inflação/Emprego → Fed → Juros → USD → Par cambial → "
                "W1/D1 → Liquidez → Killzone → H4/H1 → M15.**"
            )
            st.caption("Nenhum elo isolado garante uma operação. O sistema procura concordância e motivos para não entrar.")

        with st.expander("🗂️ Glossário rápido"):
            for name, item in INDICATOR_GUIDE.items():
                st.markdown(f"**{name}:** {item['o_que_e']}")

    with t3:
        st.markdown("### 🔔 Alertas visuais configuráveis")
        st.info(
            "Nesta versão os alertas são VISUAIS dentro do app enquanto ele está aberto. "
            "Notificação push em segundo plano exige um serviço externo específico e ainda não está ativada."
        )
        min_score = st.slider("Avisar quando Score ≥", 50, 100, int(st.session_state.get("ux103_alert_score", 85)), 1, key="ux103_alert_score")
        min_quality = st.slider("E Qualidade ≥", 0, 100, int(st.session_state.get("ux103_alert_quality", 75)), 1, key="ux103_alert_quality")
        pair_options = matrix["Par"].astype(str).tolist() if matrix is not None and not matrix.empty and "Par" in matrix.columns else []
        watch_pairs = st.multiselect(
            "Pares monitorados",
            pair_options,
            default=st.session_state.get("ux103_alert_pairs", pair_options),
            key="ux103_alert_pairs",
        )
        hits = select_alert_hits(matrix, min_score, min_quality, watch_pairs)
        if hits:
            st.success(f"🔔 {len(hits)} contexto(s) atendem seus filtros agora.")
            st.dataframe(pd.DataFrame(hits), hide_index=True, width="stretch")
        else:
            st.warning("Nenhum par atende aos limites configurados neste momento.")

        with st.expander("Exemplos de alertas úteis"):
            st.markdown(
                "- Score alto + qualidade alta\n"
                "- Evento principal próximo\n"
                "- Scanner técnico ficou atual\n"
                "- Gate A/A+ e M15 confirmado\n"
                "- ADR muito consumido para evitar perseguir preço"
            )

    with t4:
        st.markdown("### 🕒 Transparência de atualização")
        now = pd.Timestamp.now(tz="UTC")
        c1, c2, c3 = st.columns(3)
        c1.metric("Consulta da tela", now.strftime("%H:%M UTC"))
        c2.metric("Versão", app_version.split(" — ")[0] if app_version else "V10.3")
        c3.metric("Modo de dados", "AUTO + FRESCOR")

        st.markdown(
            '<div class="ux-card"><b>Importante:</b> CPI, PCE, Payroll e PIB não possuem '
            '"tick em tempo real". Eles mudam quando a instituição publica uma nova leitura. '
            'Preços FX, Treasury e candles técnicos podem atualizar durante a sessão. '
            'O app mostra idade/frescor para não misturar dado novo com dado antigo.</div>',
            unsafe_allow_html=True,
        )

        source_rows = []
        for name, value in sources.items():
            source_rows.append({"Fonte / bloco": str(name), "Estado": str(value)})
        if source_rows:
            st.dataframe(pd.DataFrame(source_rows), hide_index=True, width="stretch")
        else:
            st.caption("Os estados detalhados das fontes continuam disponíveis nas abas operacionais.")

        st.markdown("#### 📱 Multiplataforma")
        st.success("✅ Web responsiva + PWA instalável no Android/PC + Adicionar à Tela de Início no iPhone/iPad.")
        st.caption("É uma PWA instalada a partir da web, não um APK nativo da Play Store.")

    with t5:
        st.markdown("### 🧮 Simulador simples de inflação")
        amount = st.number_input("Valor hoje", min_value=0.0, value=1000.0, step=100.0, key="ux103_sim_amount")
        rate = st.number_input("Inflação anual (%)", value=4.0, step=0.1, key="ux103_sim_rate")
        years = st.slider("Anos", 1, 30, 5, key="ux103_sim_years")
        sim = inflation_projection(amount, rate, years)
        s1, s2, s3 = st.columns(3)
        s1.metric("Mesmo bem no futuro", f"{sim['future_cost']:,.2f}")
        s2.metric("Poder de compra", f"{sim['purchasing_power']:,.2f}")
        s3.metric("Perda acumulada", f"{sim['loss_pct']:.1f}%")
        st.caption("Simulação matemática educativa; não é previsão de inflação futura.")
