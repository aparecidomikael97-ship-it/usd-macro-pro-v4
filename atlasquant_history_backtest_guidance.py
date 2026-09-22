"""AtlasQuant History + Backtest didactic helpers.

Presentation/research-only. No provider calls, no signal creation, no gate changes,
no strategy promotion and no real execution.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence
import math

import pandas as pd
import streamlit as st

HISTORY_REQUIRED_COLUMNS=("Código","Pontuação_Final","data")

BACKTEST_GUIDE_STEPS=(
    ("1 · Escolha o contexto","Defina o timeframe e o tipo de operacional que você quer validar."),
    ("2 · Traga os candles","Importe candles OHLC exportados do TradingView; a aba não busca mercado por conta própria."),
    ("3 · Defina o que será testado","Use sinais explícitos ou um replay objetivo dos modelos suportados."),
    ("4 · Inclua fricção real","Considere spread/custos e slippage. Resultado sem custo pode parecer melhor do que seria na prática."),
    ("5 · Leia o resultado","Olhe operações, gain/loss, taxa de acerto, resultado e expectativa em R, drawdown, MFE/MAE e estabilidade."),
    ("6 · Valide a robustez","Compare períodos, sessões, ativos, walk-forward e sensibilidade antes de confiar no operacional."),
)

BACKTEST_THREE_QUESTIONS=(
    "O que exatamente está sendo testado?",
    "Como cada entrada, stop, alvo, custo e saída são simulados?",
    "A amostra é grande e estável o suficiente para justificar confiança?",
)

BACKTEST_VIDEO_SCRIPT=(
    "Nesta aba você valida um operacional em dados históricos. Primeiro escolha o timeframe. "
    "Depois importe candles do TradingView. Você pode fornecer sinais com entrada, stop e alvo "
    "ou usar os replays objetivos disponíveis. O AtlasQuant começa a simulação sem olhar o futuro, "
    "considera custos e slippage quando informados e trata stop e alvo no mesmo candle de forma conservadora. "
    "No resultado, não olhe só a taxa de acerto: confira expectativa em R, resultado líquido em R, "
    "drawdown, profit factor, MFE e MAE, quantidade de trades e estabilidade em outros períodos. "
    "Uma amostra pequena ou um resultado histórico bom não garante resultado futuro e não promove estratégia automaticamente."
)


def _finite(value:Any)->float|None:
    try:
        x=float(value)
        return x if math.isfinite(x) else None
    except Exception:
        return None


def prepare_history(frame:pd.DataFrame|None)->pd.DataFrame:
    if not isinstance(frame,pd.DataFrame) or frame.empty:
        return pd.DataFrame(columns=list(HISTORY_REQUIRED_COLUMNS))
    if not set(HISTORY_REQUIRED_COLUMNS).issubset(frame.columns):
        return pd.DataFrame(columns=list(HISTORY_REQUIRED_COLUMNS))
    out=frame.copy()
    out["Código"]=out["Código"].astype(str).str.upper().str.strip()
    out["data"]=pd.to_datetime(out["data"],errors="coerce")
    out["Pontuação_Final"]=pd.to_numeric(out["Pontuação_Final"],errors="coerce")
    out=out.dropna(subset=["Código","data","Pontuação_Final"])
    out=out[out["Pontuação_Final"].map(lambda x:_finite(x) is not None)]
    return out.sort_values(["data","Código"]).reset_index(drop=True)


def history_change_summary(frame:pd.DataFrame|None)->pd.DataFrame:
    data=prepare_history(frame)
    columns=("Moeda","Atual","Anterior","Mudança","Leitura","Data atual","Data anterior")
    if data.empty:
        return pd.DataFrame(columns=columns)
    rows=[]
    for code,group in data.groupby("Código",sort=True):
        ordered=group.sort_values("data")
        latest=ordered.iloc[-1]
        previous=ordered.iloc[-2] if len(ordered)>=2 else None
        current=float(latest["Pontuação_Final"])
        previous_score=None if previous is None else float(previous["Pontuação_Final"])
        delta=None if previous_score is None else current-previous_score
        if delta is None:
            reading="SEM COMPARAÇÃO"
        elif delta>0.5:
            reading="FORTALECEU"
        elif delta<-0.5:
            reading="ENFRAQUECEU"
        else:
            reading="ESTÁVEL"
        rows.append({
            "Moeda":str(code),
            "Atual":round(current,1),
            "Anterior":None if previous_score is None else round(previous_score,1),
            "Mudança":None if delta is None else round(delta,1),
            "Leitura":reading,
            "Data atual":pd.Timestamp(latest["data"]),
            "Data anterior":None if previous is None else pd.Timestamp(previous["data"]),
        })
    return pd.DataFrame(rows,columns=columns).sort_values(
        ["Mudança","Moeda"],ascending=[False,True],na_position="last"
    ).reset_index(drop=True)


def history_chart_frame(
    frame:pd.DataFrame|None,
    *,
    currencies:Sequence[str]|None=None,
    days:int|None=None,
)->pd.DataFrame:
    data=prepare_history(frame)
    if data.empty:
        return pd.DataFrame(columns=["data","Código","Pontuação_Final"])
    if currencies:
        wanted={str(x).upper().strip() for x in currencies}
        data=data[data["Código"].isin(wanted)]
    if days is not None:
        try:
            window=int(days)
        except Exception:
            window=0
        if window>0 and not data.empty:
            latest=data["data"].max()
            data=data[data["data"]>=latest-pd.Timedelta(days=window)]
    return data[["data","Código","Pontuação_Final"]].copy()


def history_help_model()->dict[str,Any]:
    return {
        "title":"Histórico de Força e Direção",
        "purpose":"Acompanhar como a força das moedas mudou ao longo do tempo.",
        "not_this":"Não é Backtest e não mede se uma estratégia teria dado gain ou loss.",
        "questions":(
            "Qual moeda ganhou ou perdeu força?",
            "Quando a mudança começou?",
            "A mudança foi pequena, forte ou persistente?",
        ),
        "trading_side_effects":False,
    }


def render_history_workspace(frame:pd.DataFrame|None)->dict[str,Any]:
    model=history_help_model()
    st.subheader("🗂️ Histórico de Força e Direção")
    st.info(
        "Esta aba mostra como a força das moedas foi mudando com o tempo. "
        "**Ela não é Backtest.** Backtest testa um operacional; Histórico acompanha a evolução das leituras."
    )
    with st.expander("❓ Como funciona esta aba?",expanded=False):
        st.markdown(
            "**Use assim:** veja o que mudou desde o registro anterior, escolha uma moeda e observe a linha do tempo. "
            "Se a força sobe repetidamente, há persistência; se oscila muito, a leitura está instável."
        )
        for question in model["questions"]:
            st.markdown(f"- {question}")
        st.caption(
            "Vídeo desta aba: roteiro didático preparado; mídia final será incorporada na etapa educacional. "
            "Nenhuma linha do Histórico é uma ordem de compra ou venda."
        )

    data=prepare_history(frame)
    if data.empty:
        st.warning(
            "Ainda não há histórico suficiente para comparação. "
            "Quando os snapshots de força forem registrados, eles aparecerão aqui automaticamente."
        )
        return {"ready":False,"rows":0,"changes":0,**model}

    summary=history_change_summary(data)
    st.markdown("### O que mudou desde o registro anterior?")
    st.dataframe(summary,width="stretch",hide_index=True)

    currencies=sorted(data["Código"].unique().tolist())
    c1,c2=st.columns(2)
    with c1:
        selected=st.multiselect(
            "Moedas no gráfico",
            currencies,
            default=currencies,
            key="aq_history_currencies",
        )
    with c2:
        period=st.selectbox(
            "Período",
            ["7 dias","30 dias","90 dias","Todo o histórico"],
            index=1,
            key="aq_history_period",
        )
    days={"7 dias":7,"30 dias":30,"90 dias":90,"Todo o histórico":None}[period]
    chart=history_chart_frame(data,currencies=selected,days=days)
    if chart.empty:
        st.info("Nenhum registro dentro deste filtro.")
    else:
        pivot=chart.pivot_table(
            index="data",columns="Código",values="Pontuação_Final",aggfunc="last"
        ).sort_index()
        st.markdown("### Evolução da força")
        st.line_chart(pivot)

    with st.expander("Ver registros brutos",expanded=False):
        st.dataframe(data.sort_values("data",ascending=False),width="stretch",hide_index=True)

    st.caption(
        "Fonte desta aba: snapshots históricos do AtlasQuant. Se a persistência externa não estiver configurada, "
        "o histórico local pode ser perdido em um novo deploy."
    )
    return {
        "ready":True,
        "rows":len(data),
        "changes":len(summary),
        "currencies":currencies,
        **model,
    }


def backtest_help_model()->dict[str,Any]:
    return {
        "title":"Backtest — validação histórica do operacional",
        "steps":BACKTEST_GUIDE_STEPS,
        "questions":BACKTEST_THREE_QUESTIONS,
        "video_script":BACKTEST_VIDEO_SCRIPT,
        "warnings":(
            "Taxa de acerto sozinha não mede qualidade.",
            "Amostra pequena não é evidência suficiente.",
            "Resultado histórico não garante resultado futuro.",
            "Backtest não promove estratégia nem habilita ordens automaticamente.",
        ),
        "trading_side_effects":False,
        "automatic_promotion":False,
    }


def render_backtest_intro()->dict[str,Any]:
    model=backtest_help_model()
    st.subheader("🧪 Backtest — como validar uma estratégia")
    st.info(
        "Backtest responde: **'Se eu tivesse aplicado estas regras no passado, o que teria acontecido?'** "
        "Ele não prevê o futuro e não transforma resultado histórico em autorização de operação."
    )
    with st.expander("▶️ Comece aqui — passo a passo",expanded=True):
        for title,text in model["steps"]:
            st.markdown(f"**{title}** — {text}")
        st.markdown("#### As três perguntas que você precisa conseguir responder")
        for question in model["questions"]:
            st.markdown(f"- {question}")

    with st.expander("🎬 Como funciona esta aba? · roteiro do vídeo",expanded=False):
        st.write(model["video_script"])
        st.caption(
            "Esse é o roteiro do vídeo didático desta aba. O vídeo final ainda será produzido/publicado "
            "na etapa educacional; o texto já serve como guia de uso agora."
        )

    with st.expander("📌 Como interpretar os resultados",expanded=False):
        st.markdown(
            "**Operações** = quantidade realmente simulada.  
"
            "**Taxa de acerto** = proporção de gains, mas não basta sozinha.  
"
            "**Expectativa em R** = resultado médio por operação medido em unidades de risco.  
"
            "**Drawdown** = queda acumulada a partir de um pico.  
"
            "**MFE/MAE** = quanto o preço andou a favor/contra durante a operação.  
"
            "**Profit Factor** = ganhos brutos divididos pelas perdas brutas, quando definido.  
"
            "**Custos/Slippage** = fricção que aproxima a simulação do mercado real."
        )
        for warning in model["warnings"]:
            st.warning(warning)
    return model


__all__=[
    "HISTORY_REQUIRED_COLUMNS","BACKTEST_GUIDE_STEPS","BACKTEST_THREE_QUESTIONS",
    "BACKTEST_VIDEO_SCRIPT","prepare_history","history_change_summary",
    "history_chart_frame","history_help_model","render_history_workspace",
    "backtest_help_model","render_backtest_intro",
]
