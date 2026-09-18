"""Streamlit presentation layer for AtlasQuant Macro Briefing.

No data collection or trading decision is performed here.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence
import streamlit as st

from atlasquant_macro_briefing import build_macro_briefing


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
    st.caption(brief["disclaimer"])
    return brief
