"""USD Macro Pro V10.4 — Produto, Navegação, Gráficos e Feedback.

Camada de produto/UX. NÃO altera Score Mestre, Gate, direção macro,
Market Map, scanner técnico nem histórico oficial de performance.
"""
from __future__ import annotations

from typing import Any, Callable
import hashlib
import math
import uuid

import pandas as pd
import streamlit as st

try:
    import altair as alt
except Exception:
    alt = None


HISTORY_MAP = {
    "CPI / IPC": ("CPIAUCSL", "pc1", "Inflação anual (%)", "monthly"),
    "PCE": ("PCEPI", "pc1", "PCE anual (%)", "monthly"),
    "Payroll / NFP": ("PAYEMS", "chg", "Variação mensal (mil)", "monthly"),
    "Desemprego": ("UNRATE", None, "Desemprego (%)", "monthly"),
    "PIB": ("GDPC1", "pc1", "PIB real anual (%)", "quarterly"),
    "Treasury 2Y": ("DGS2", None, "Treasury 2Y (%)", "daily"),
    "Fed Funds": ("DFF", None, "Fed Funds efetivo (%)", "daily"),
}

FAQ = {
    "O Índice Integrado é probabilidade de gain?":
        "Não. É um ranking operacional de confluência. Probabilidade real exige amostra histórica suficiente.",
    "Por que o app manda AGUARDAR mesmo com Score alto?":
        "Porque Score alto não substitui localização, evento, W1/D1, ADR, H4/H1/M15 e qualidade dos dados.",
    "CPI, PCE e Payroll são tempo real?":
        "Não. Mudam quando a instituição publica uma nova leitura. Preços FX e candles técnicos podem atualizar durante a sessão.",
    "O app funciona sem internet?":
        "A casca PWA pode abrir, mas Streamlit, FRED e Twelve Data precisam de internet para atualizar dados.",
    "Como funciona o Gate A+/A/B/WAIT?":
        "É um filtro de seletividade. Não representa taxa de acerto.",
    "Por que o scanner atualiza em lotes?":
        "Para respeitar o limite conservador da Twelve Data e reduzir erros por excesso de consultas.",
}

ROADMAP = pd.DataFrame([
    {"Prioridade": "P0", "Área": "Velocidade", "Melhoria": "Cache de histórico + reaproveitamento de CPI/PCE/PIB", "Estado": "✅ V10.4"},
    {"Prioridade": "P0", "Área": "Navegação", "Melhoria": "Dock móvel + atalhos + tela inicial simplificada", "Estado": "✅ V10.4"},
    {"Prioridade": "P1", "Área": "Gráficos", "Melhoria": "Linha / barra / área + tooltip + zoom + período", "Estado": "✅ V10.4"},
    {"Prioridade": "P1", "Área": "Atualização", "Melhoria": "Política 1h/6h + transparência de frescor", "Estado": "✅ V10.4"},
    {"Prioridade": "P1", "Área": "Feedback", "Melhoria": "Pesquisa + anexo opcional + FAQ", "Estado": "✅ V10.4"},
    {"Prioridade": "P2", "Área": "A/B", "Melhoria": "Comparar dock fixo vs navegação compacta", "Estado": "✅ Laboratório"},
    {"Prioridade": "P2", "Área": "Analytics", "Melhoria": "Telemetria externa com consentimento", "Estado": "🟡 Opcional"},
    {"Prioridade": "P2", "Área": "Push", "Melhoria": "Notificação com app fechado", "Estado": "🟡 Exige serviço externo"},
    {"Prioridade": "P0", "Área": "Acesso", "Melhoria": "Login privado com perfis USER / SALES / ADMIN", "Estado": "✅ Base segura integrada"},
    {"Prioridade": "P0", "Área": "Admin", "Melhoria": "Ciclo de conta não destrutivo + exportação revisável", "Estado": "✅ Integrado"},
    {"Prioridade": "P0", "Área": "Vendas", "Melhoria": "Portal comercial + onboarding + checklist de lançamento", "Estado": "✅ Integrado"},
    {"Prioridade": "P0", "Área": "Instalação", "Melhoria": "PWA Android/iOS/Windows/macOS/Linux", "Estado": "✅ Integrado"},
    {"Prioridade": "P1", "Área": "Academy", "Melhoria": "Vídeos macro/SMC/plataforma/corretoras", "Estado": "🟡 Planejado"},
    {"Prioridade": "P1", "Área": "Voz", "Melhoria": "Briefing diário/semanal e explicação do viés", "Estado": "🟡 Planejado"},
    {"Prioridade": "P2", "Área": "Institucional", "Melhoria": "COT/open interest/posicionamento institucional", "Estado": "🟡 Fase final"},
])

WIREFRAME_SVG = r"""<svg xmlns="http://www.w3.org/2000/svg" width="1100" height="700" viewBox="0 0 1100 700">
<rect width="1100" height="700" fill="#f4f7fb"/>
<rect x="40" y="30" width="1020" height="70" rx="18" fill="#15345d"/>
<text x="75" y="75" font-family="Arial" font-size="28" font-weight="700" fill="white">AtlasQuant — Início</text>
<rect x="40" y="125" width="1020" height="80" rx="18" fill="white" stroke="#cbd7e6"/>
<text x="70" y="160" font-family="Arial" font-size="18" font-weight="700" fill="#15345d">Resumo rápido</text>
<text x="70" y="188" font-family="Arial" font-size="15" fill="#56677b">USD Macro • Fed • Evento • Melhor oportunidade • Frescor dos dados</text>
<rect x="40" y="230" width="500" height="250" rx="18" fill="white" stroke="#cbd7e6"/>
<text x="70" y="270" font-family="Arial" font-size="20" font-weight="700" fill="#15345d">Inflação / CPI</text>
<polyline points="85,420 150,390 220,405 290,340 360,365 430,300 495,315" fill="none" stroke="#1565c0" stroke-width="5"/>
<circle cx="430" cy="300" r="8" fill="#1565c0"/>
<text x="70" y="455" font-family="Arial" font-size="14" fill="#64748b">Toque nos pontos • zoom • 3m / 6m / 1a / 5a</text>
<rect x="560" y="230" width="500" height="250" rx="18" fill="white" stroke="#cbd7e6"/>
<text x="590" y="270" font-family="Arial" font-size="20" font-weight="700" fill="#15345d">PIB / Atividade</text>
<rect x="610" y="350" width="55" height="80" fill="#2e7d32"/><rect x="690" y="320" width="55" height="110" fill="#2e7d32"/>
<rect x="770" y="285" width="55" height="145" fill="#2e7d32"/><rect x="850" y="305" width="55" height="125" fill="#2e7d32"/>
<rect x="930" y="260" width="55" height="170" fill="#2e7d32"/>
<rect x="40" y="505" width="1020" height="75" rx="18" fill="#e8f1fd" stroke="#b5cbe8"/>
<text x="70" y="550" font-family="Arial" font-size="20" font-weight="700" fill="#15345d">Meus Indicadores</text>
<rect x="40" y="610" width="1020" height="60" rx="22" fill="#0f1c30"/>
<text x="130" y="648" font-family="Arial" font-size="18" font-weight="700" fill="white">Indicadores</text>
<text x="430" y="648" font-family="Arial" font-size="18" font-weight="700" fill="white">Explicações</text>
<text x="760" y="648" font-family="Arial" font-size="18" font-weight="700" fill="white">Configurações</text>
</svg>"""


def choose_ab_variant(seed: str) -> str:
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    return "A" if int(digest[:8], 16) % 2 == 0 else "B"


def history_limit(period: str, frequency: str) -> int:
    if frequency == "daily":
        return {"3 meses": 100, "6 meses": 160, "1 ano": 280, "5 anos": 1300}.get(period, 280)
    if frequency == "quarterly":
        return {"3 meses": 2, "6 meses": 3, "1 ano": 5, "5 anos": 21}.get(period, 5)
    return {"3 meses": 4, "6 meses": 7, "1 ano": 13, "5 anos": 61}.get(period, 13)


def freshness_by_frequency(date_value: Any, frequency: str, now: Any = None) -> tuple[str, str, int | None]:
    try:
        dt = pd.Timestamp(date_value).tz_localize(None).normalize()
        today = pd.Timestamp(now).tz_localize(None).normalize() if now is not None else pd.Timestamp.now().normalize()
        age = int((today - dt).days)
        if age < 0:
            return "SEM DATA", "⚪", None
    except Exception:
        return "SEM DATA", "⚪", None
    if frequency == "daily":
        if age <= 1: return "ATUAL", "🟢", age
        if age <= 3: return "ATENÇÃO", "🟡", age
        return "DESATUALIZADO", "🔴", age
    if frequency == "quarterly":
        if age <= 100: return "ATUAL", "🟢", age
        if age <= 130: return "ATENÇÃO", "🟡", age
        return "DESATUALIZADO", "🔴", age
    if age <= 45: return "ATUAL", "🟢", age
    if age <= 60: return "ATENÇÃO", "🟡", age
    return "DESATUALIZADO", "🔴", age


def _interactive_chart(df: pd.DataFrame, ytitle: str, chart_type: str):
    if df is None or df.empty:
        st.info("Sem histórico disponível para este indicador.")
        return
    d = df.copy()
    d["date"] = pd.to_datetime(d["date"], errors="coerce")
    d["value"] = pd.to_numeric(d["value"], errors="coerce")
    d = d.dropna(subset=["date", "value"]).sort_values("date")
    if d.empty:
        st.info("Sem valores válidos para o gráfico.")
        return
    if alt is None:
        st.line_chart(d.set_index("date")["value"], width="stretch")
        return
    common = {
        "x": alt.X("date:T", title="Data"),
        "y": alt.Y("value:Q", title=ytitle, scale=alt.Scale(zero=False)),
        "tooltip": [alt.Tooltip("date:T", title="Data"), alt.Tooltip("value:Q", title=ytitle, format=".3f")],
    }
    if chart_type == "Barra":
        chart = alt.Chart(d).mark_bar().encode(**common)
    elif chart_type == "Área":
        chart = alt.Chart(d).mark_area(opacity=.30, line=True).encode(**common)
    else:
        chart = alt.Chart(d).mark_line(point=True).encode(**common)
    st.altair_chart(chart.properties(height=340).interactive(), width="stretch")
    st.caption("Passe o mouse/toque nos pontos para valores. Zoom e pan dependem do navegador/dispositivo.")


def _dock(variant: str):
    if variant != "A":
        st.caption("🧪 Variante B: navegação compacta sem barra inferior fixa.")
        return
    st.markdown("""
<style>
.ux104dock{position:fixed;z-index:9998;left:50%;transform:translateX(-50%);bottom:9px;
width:min(94vw,570px);display:flex;justify-content:space-around;background:rgba(15,28,48,.95);
border:1px solid rgba(255,255,255,.18);border-radius:18px;padding:8px 5px;
box-shadow:0 8px 28px rgba(0,0,0,.28);backdrop-filter:blur(12px)}
.ux104dock a{color:#fff;text-decoration:none;font-size:.78rem;font-weight:700;text-align:center;padding:5px 8px}
</style>
<div class="ux104dock">
<a href="#indicadores-v104">📊<br>Indicadores</a>
<a href="#explicacoes-v104">📚<br>Explicações</a>
<a href="#config-v104">⚙️<br>Configurações</a>
<a href="#ajuda-v104">❓<br>Ajuda</a>
</div>
""", unsafe_allow_html=True)


def render_v104_hub(
    history_fetcher: Callable[[str, int, str | None], pd.DataFrame] | None = None,
    feedback_saver: Callable[[dict[str, Any], bytes | None, str | None], tuple[bool, str]] | None = None,
    refresh_callback: Callable[[], tuple[bool, str]] | None = None,
    app_version: str = "",
):
    if "ux104_ab_seed" not in st.session_state:
        st.session_state["ux104_ab_seed"] = uuid.uuid4().hex
    auto_variant = choose_ab_variant(st.session_state["ux104_ab_seed"])

    st.subheader("🚀 Produto, Navegação & Suporte — V10.4")
    st.caption("Camada de produto. Não altera Score Mestre, Gate, direção, Market Map ou histórico oficial.")

    with st.sidebar.expander("⚙️ Configurações V10.4", expanded=False):
        language = st.selectbox("Idioma", ["Português", "English"], key="ux104_language",
                                help="A V10.4 traduz suas próprias telas; módulos legados continuam em PT-BR.")
        date_fmt = st.selectbox("Formato de data", ["DD/MM/AAAA", "MM/DD/AAAA"], key="ux104_date_fmt")
        alerts_on = st.toggle("Alertas visuais", value=True, key="ux104_alerts_enabled")
        refresh_policy = st.selectbox("Política de atualização",
                                      ["Manual", "Verificar a cada 1h", "Verificar a cada 6h"],
                                      key="ux104_refresh_policy")
        ab_mode = st.selectbox("Teste A/B de navegação",
                               ["Automático", "A — dock fixo", "B — compacto"],
                               key="ux104_ab_mode")

    variant = auto_variant if ab_mode == "Automático" else ("A" if ab_mode.startswith("A") else "B")
    _dock(variant)

    tabs = st.tabs(["🏠 Início", "📊 Indicadores", "🧪 A/B & Roadmap", "💬 Feedback", "❓ FAQ", "⚙️ Configurações"])

    with tabs[0]:
        st.markdown("### 🏠 Tela inicial proposta")
        st.html(WIREFRAME_SVG)
        st.download_button("⬇️ Baixar wireframe SVG", WIREFRAME_SVG.encode("utf-8"),
                           "wireframe_usd_macro_pro_v104.svg", "image/svg+xml")
        st.markdown("**Objetivo:** Resumo Macro → 2 gráficos principais → Meus Indicadores → navegação curta.")
        c1, c2, c3 = st.columns(3)
        if c1.button("🔄 Atualizar agora", width="stretch"):
            if refresh_callback:
                ok, msg = refresh_callback()
                (st.success if ok else st.warning)(msg)
            else:
                st.info("Atualização central indisponível nesta execução.")
        c2.link_button("📱 Abrir PWA", "https://aparecidomikael97-ship-it.github.io/usd-macro-pro-v4/",
                       width="stretch")
        c3.metric("Teste A/B", f"Grupo {variant}")
        st.info("A V10.4 usa cache do servidor + PWA para a casca visual. Dados vivos continuam exigindo internet.")

    with tabs[1]:
        st.markdown('<div id="indicadores-v104"></div>', unsafe_allow_html=True)
        st.markdown("### 📊 Indicadores detalhados")
        if history_fetcher is None:
            st.warning("Histórico interativo indisponível.")
        else:
            indicator = st.selectbox("Indicador", list(HISTORY_MAP), key="ux104_hist_indicator")
            p1, p2 = st.columns(2)
            with p1:
                period = st.radio("Período", ["3 meses", "6 meses", "1 ano", "5 anos"], index=2,
                                  horizontal=True, key="ux104_hist_period")
            with p2:
                chart_type = st.radio("Gráfico", ["Linha", "Barra", "Área"], horizontal=True, key="ux104_hist_type")
            sid, units, ytitle, freq = HISTORY_MAP[indicator]
            limit = history_limit(period, freq)
            with st.spinner("Carregando histórico..."):
                df = history_fetcher(sid, limit, units)
            _interactive_chart(df, ytitle, chart_type)
            if isinstance(df, pd.DataFrame) and not df.empty:
                last = df.sort_values("date").iloc[-1]
                label, dot, age = freshness_by_frequency(last["date"], freq)
                fmt = "%d/%m/%Y" if date_fmt == "DD/MM/AAAA" else "%m/%d/%Y"
                st.info(f"{dot} Última observação: {pd.Timestamp(last['date']).strftime(fmt)} · {label} · idade {age} dia(s).")
        with st.expander("⚡ Velocidade, pré-carga e cache"):
            st.markdown(
                "- CPI/PCE/PIB já são buscados pelo motor e históricos repetidos usam cache de 1 hora.\n"
                "- O app carrega série de 5 anos somente quando você pedir.\n"
                "- O PWA guarda a interface, não chaves ou dados sensíveis."
            )

    with tabs[2]:
        st.markdown("### 🧪 Testes A/B e planejamento")
        st.write(f"Variante desta sessão: **{variant}**")
        st.caption("A = dock fixo. B = navegação compacta. O feedback registra a variante.")
        st.dataframe(ROADMAP, hide_index=True, width="stretch")
        st.download_button("⬇️ Baixar roadmap CSV", ROADMAP.to_csv(index=False).encode("utf-8"),
                           "roadmap_v104.csv", "text/csv")
        st.warning("Google Optimize foi descontinuado; a V10.4 usa um laboratório A/B interno simples e auditável.")

    with tabs[3]:
        st.markdown('<div id="ajuda-v104"></div>', unsafe_allow_html=True)
        st.markdown("### 💬 Pesquisa de experiência — USD Macro Pro")
        st.caption("Nenhum feedback é salvo até você clicar em Enviar.")
        with st.form("ux104_feedback_form"):
            indicators = st.multiselect("1. Quais indicadores você acompanha regularmente?", list(HISTORY_MAP))
            missing = st.text_input("2. Sente falta de algum indicador? Qual?")
            nav = st.slider("3. Facilidade de navegação", 0, 10, 8)
            nav_text = st.text_input("4. O que pode melhorar na navegação?")
            charts = st.slider("5. Clareza dos gráficos", 0, 10, 8)
            viz = st.multiselect("6. Formas de visualização desejadas", ["Linha", "Barra", "Área", "Candles", "Comparação lado a lado"])
            notifications = st.text_input("7. Quais alertas/notificações seriam úteis?")
            slow = st.selectbox("8. Você sentiu lentidão?", ["Não", "Às vezes", "Sim"])
            interest = st.text_area("9. O que aumenta ou diminui seu interesse em usar o app?")
            score = st.slider("10. Nota geral do app", 0, 10, 9)
            extra = st.text_area("11. Sugestões adicionais")
            screenshot = st.file_uploader("Anexar print (opcional)", type=["png", "jpg", "jpeg", "webp"])
            consent = st.checkbox("Autorizo salvar este feedback no repositório de dados do app.")
            send = st.form_submit_button("📨 Enviar feedback", type="primary")
        if send:
            if not consent:
                st.warning("Marque a autorização antes de enviar.")
            elif feedback_saver is None:
                st.error("Persistência de feedback não configurada.")
            else:
                payload = {
                    "timestamp": pd.Timestamp.now(tz="UTC").isoformat(), "app_version": app_version,
                    "ab_variant": variant, "language": language, "date_format": date_fmt,
                    "indicators": " | ".join(indicators), "missing_indicator": missing,
                    "navigation_score": nav, "navigation_comment": nav_text, "charts_score": charts,
                    "visualizations": " | ".join(viz), "notifications": notifications,
                    "slowness": slow, "interest": interest, "overall_score": score, "extra": extra,
                }
                blob = screenshot.getvalue() if screenshot else None
                name = screenshot.name if screenshot else None
                ok, msg = feedback_saver(payload, blob, name)
                (st.success if ok else st.error)(msg)

    with tabs[4]:
        st.markdown('<div id="explicacoes-v104"></div>', unsafe_allow_html=True)
        st.markdown("### ❓ FAQ e ajuda rápida")
        for q, a in FAQ.items():
            with st.expander(q):
                st.write(a)
        st.markdown("### 🧑‍🔬 Roteiro para pesquisa com usuários")
        st.markdown(
            "1. Quais indicadores acompanha regularmente?\n"
            "2. Sente falta de algum?\n"
            "3. O app é fácil de navegar?\n"
            "4. O que pode melhorar na navegação?\n"
            "5. Os gráficos são claros?\n"
            "6. Gostaria de outras visualizações?\n"
            "7. Quais alertas seriam úteis?\n"
            "8. Sentiu lentidão?\n"
            "9. O que aumenta/diminui seu interesse?\n"
            "10. Nota geral de 0 a 10."
        )

    with tabs[5]:
        st.markdown('<div id="config-v104"></div>', unsafe_allow_html=True)
        st.markdown("### ⚙️ Configurações e atualização")
        st.write(f"**Idioma da V10.4:** {language}")
        st.write(f"**Formato de data:** {date_fmt}")
        st.write(f"**Alertas visuais:** {'Ativados' if alerts_on else 'Desativados'}")
        st.write(f"**Política escolhida:** {refresh_policy}")
        st.write(f"**Variante A/B:** {variant}")
        interval_h = 0 if refresh_policy == "Manual" else (1 if "1h" in refresh_policy else 6)
        last_key = "ux104_last_refresh_utc"
        last_raw = st.session_state.get(last_key)
        now = pd.Timestamp.now(tz="UTC")
        age_h = None
        if last_raw:
            try:
                last = pd.Timestamp(last_raw)
                if last.tzinfo is None: last = last.tz_localize("UTC")
                age_h = (now - last).total_seconds() / 3600
            except Exception:
                age_h = None
        if interval_h == 0:
            st.info("Modo manual: você decide quando atualizar.")
        elif age_h is None or age_h >= interval_h:
            st.warning(f"⏰ Atualização recomendada agora (política {interval_h}h).")
        else:
            st.success(f"✅ Dentro da janela. Última marca há {age_h:.1f}h.")
        if st.button("🔄 Marcar atualização agora", key="ux104_mark_refresh"):
            if refresh_callback:
                ok, msg = refresh_callback()
                if ok: st.session_state[last_key] = now.isoformat()
                (st.success if ok else st.warning)(msg)
            else:
                st.session_state[last_key] = now.isoformat()
                st.success("Horário registrado.")
        st.warning(
            "Streamlit não garante atualização em segundo plano com o app fechado. "
            "Para isso use GitHub Actions/serviço externo. Evitamos timer visual agressivo por estabilidade."
        )
        st.success("✅ Web responsiva + PWA Android/PC + Adicionar à Tela de Início no iPhone/iPad.")
        with st.expander("📈 Analytics, privacidade e monitoramento"):
            st.markdown(
                "Analytics externo não é ativado automaticamente. "
                "A V10.4 usa feedback explícito e consentido para medir navegação, gráficos, lentidão e nota geral."
            )
