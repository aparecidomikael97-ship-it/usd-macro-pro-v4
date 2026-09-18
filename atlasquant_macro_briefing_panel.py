"""Streamlit presentation layer for AtlasQuant Macro Briefing.

No data collection or trading decision is performed here.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence
import streamlit as st

from atlasquant_macro_briefing import build_macro_briefing
from atlasquant_macro_briefing_voice import VoiceRequest


def render_macro_briefing_panel(currency_rows: Sequence[Mapping[str, Any]] | None, events: Sequence[Mapping[str, Any]] | None = None, central_banks: Sequence[Mapping[str, Any]] | None = None) -> dict[str, Any]:
    st.subheader("🎙️ Macro Briefing")
    st.caption("Panorama informativo gerado somente a partir do estado macro disponível no AtlasQuant.")
    mode = st.radio("Horizonte", ["Hoje", "Semana"], horizontal=True, key="aq_macro_brief_horizon")
    horizon = "today" if mode == "Hoje" else "week"
    brief = build_macro_briefing(currency_rows, events, central_banks, horizon=horizon)
    if not brief["data_sufficient"]:
        st.warning(brief["summary"])
        st.caption("O AtlasQuant não cria narrativa quando os dados necessários não estão válidos.")
        return brief
    st.info(brief["summary"])
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
        "Narração preparada para TTS neural. O áudio é opcional e deve consumir somente "
        "o speech_text acima; nenhum provedor de voz é chamado automaticamente ao abrir a tela."
    )
    voice_style = st.selectbox(
        "Estilo da voz",
        ["deep", "clear", "normal", "crisp", "fancy", "delicate"],
        index=0,
        key="aq_macro_brief_voice_style",
    )
    voice_request = VoiceRequest(brief["speech_text"], voice_style).validated()
    st.session_state["aq_macro_brief_voice_request"] = {
        "transcript": voice_request.transcript,
        "voice": voice_request.voice,
    }
    st.caption("O pedido de áudio só fica preparado; a geração exige ação explícita e provedor TTS configurado.")
    if st.button("🎙️ Gerar narração", key=f"aq_macro_brief_generate_{horizon}"):
        st.session_state["aq_macro_brief_voice_generate_requested"] = True
        st.info(
            "Pedido de narração registrado. O player só será exibido quando um provedor TTS "
            "configurado devolver áudio válido."
        )
    audio_bytes = st.session_state.get("aq_macro_brief_audio_bytes")
    if isinstance(audio_bytes, (bytes, bytearray)) and audio_bytes:
        st.audio(bytes(audio_bytes), format="audio/mp3")
        st.download_button(
            "Baixar áudio",
            data=bytes(audio_bytes),
            file_name=f"atlasquant_macro_briefing_{horizon}.mp3",
            mime="audio/mpeg",
            key=f"aq_macro_brief_audio_download_{horizon}",
        )

    st.download_button(
        "Baixar roteiro da narração",
        data=brief["speech_text"],
        file_name=f"atlasquant_macro_briefing_{horizon}.txt",
        mime="text/plain",
        key=f"aq_macro_brief_script_{horizon}",
    )
    st.caption(brief["disclaimer"])
    return brief
