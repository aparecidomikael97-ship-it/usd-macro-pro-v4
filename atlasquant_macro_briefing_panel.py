"""Streamlit presentation layer for AtlasQuant Macro Briefing.

No data collection or trading decision is performed here.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence
import streamlit as st

from atlasquant_macro_briefing import build_macro_briefing
from atlasquant_neural_voice_ui import render_neural_voice_player
from atlasquant_voice_profile import VOICE_PROFILE_ID



def briefing_status(brief: Mapping[str,Any] | None) -> dict[str,str]:
    b=dict(brief or {})
    if not bool(b.get("data_sufficient",False)):
        return {"label":"DADOS INSUFICIENTES","detail":"Narrativa bloqueada até os dados serem válidos"}
    bias=str(b.get("context_bias","neutro") or "neutro")
    if bias=="divergência macro":
        return {"label":"DIVERGÊNCIA MACRO","detail":"Há separação relevante entre moedas; não é sinal de trade"}
    return {"label":"CONTEXTO NEUTRO","detail":"Sem divergência macro relevante no estado atual"}


def render_macro_briefing_panel(currency_rows: Sequence[Mapping[str, Any]] | None, events: Sequence[Mapping[str, Any]] | None = None, central_banks: Sequence[Mapping[str, Any]] | None = None) -> dict[str, Any]:
    st.subheader("🎙️ Macro Briefing")
    st.caption("Panorama informativo gerado somente a partir do estado macro disponível no AtlasQuant.")
    mode = st.radio("Horizonte", ["Hoje", "Semana"], horizontal=True, key="aq_macro_brief_horizon")
    horizon = "today" if mode == "Hoje" else "week"
    brief = build_macro_briefing(currency_rows, events, central_banks, horizon=horizon)
    ui_status=briefing_status(brief)
    st.markdown(
        f"""<div style="padding:11px 13px;border:1px solid rgba(137,170,210,.18);border-radius:12px;margin:4px 0 13px">
        <strong>{ui_status['label']}</strong><br><span style="opacity:.74;font-size:.78rem">{ui_status['detail']}</span>
        </div>""", unsafe_allow_html=True,
    )
    if not brief["data_sufficient"]:
        st.warning(brief["summary"])
        st.caption("O AtlasQuant não cria narrativa quando os dados necessários não estão válidos.")
        return brief
    st.info(brief["summary"])
    bias = str(brief.get("context_bias", "neutro"))
    if bias == "divergência macro":
        st.metric("Contexto entre moedas", "Divergência macro")
        st.caption("Há separação relevante entre os scores válidos; isto não é sinal de compra ou venda.")
    else:
        st.metric("Contexto entre moedas", "Neutro")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("#### 🏦 Bancos centrais")
        if brief["central_banks"]:
            for line in brief["central_banks"]:
                st.write("• " + line)
        else:
            st.caption("Sem leitura validada de bancos centrais neste estado.")
    with c2:
        st.markdown("#### 📅 Eventos relevantes")
        if brief["events"]:
            for line in brief["events"]:
                st.write("• " + line)
        else:
            st.caption("Sem evento validado para destacar.")
    st.markdown("#### 🔊 Texto da apresentação")
    st.write(brief["speech_text"])
    st.caption("A camada de voz deve ler exatamente este texto; ela não pode gerar sinal ou alterar o diagnóstico.")
    st.markdown("#### 🎧 Voz")
    st.caption(
        "A narração usa somente a voz neural oficial do AtlasQuant. "
        "A voz do Google/aparelho não é usada como fallback."
    )
    voice_status=render_neural_voice_player(
        brief["speech_text"],
        button_label="🔊 Ouvir briefing com a voz AtlasQuant",
        key=f"macro_brief_{horizon}",
    )
    st.session_state["aq_macro_brief_voice_request"] = {
        "transcript": brief["speech_text"],
        "voice_profile_id": VOICE_PROFILE_ID,
        "delivery_mode": "server_neural_tts",
        "configured": bool(voice_status.get("configured")),
    }

    st.download_button(
        "Baixar roteiro da narração",
        data=brief["speech_text"],
        file_name=f"atlasquant_macro_briefing_{horizon}.txt",
        mime="text/plain",
        key=f"aq_macro_brief_script_{horizon}",
    )
    st.caption(brief["disclaimer"])
    return brief