"""Streamlit Admin Voice panel.

ADMIN-only UI. Uses browser speech synthesis as a zero-cost DEV fallback while
the original AtlasQuant PT-BR production voice provider is not yet connected.
"""
from __future__ import annotations
from typing import Any,Mapping,Sequence
import base64
import streamlit as st
import streamlit.components.v1 as components
from atlasquant_admin_voice_briefing import build_admin_voice_briefing
from atlasquant_admin_voice_qa import answer_admin_question

SESSION_SPOKEN_KEY="atlasquant_admin_voice_spoken"

def _is_admin(access:Mapping[str,Any]|None)->bool:
    a=dict(access or {})
    return bool(a.get("allowed")) and str(a.get("role","")).upper()=="ADMIN"

def _speech_html(text:str,autoplay:bool)->str:
    payload=base64.b64encode(str(text).encode("utf-8")).decode("ascii")
    auto="true" if autoplay else "false"
    return f"""<!doctype html><html><body style="margin:0;background:transparent">
<button id="aqSpeak" style="font:600 14px system-ui;padding:8px 12px;border-radius:9px;border:1px solid #789;background:#10243b;color:#eef">🔊 Ouvir atualização</button>
<script>
const text=new TextDecoder().decode(Uint8Array.from(atob('{payload}'), c => c.charCodeAt(0))); const auto={auto};
function speak(){{
  if(!('speechSynthesis' in window)) return;
  window.speechSynthesis.cancel();
  const u=new SpeechSynthesisUtterance(text);
  u.lang='pt-BR'; u.rate=0.98; u.pitch=0.95;
  const voices=window.speechSynthesis.getVoices();
  const preferred=voices.find(v => (v.lang||'').toLowerCase()==='pt-br') || voices.find(v => (v.lang||'').toLowerCase().startsWith('pt'));
  if(preferred) u.voice=preferred;
  window.speechSynthesis.speak(u);
}}
document.getElementById('aqSpeak').onclick=speak;
if(auto) setTimeout(speak,350);
</script></body></html>"""

def render_admin_voice_assistant(access:Mapping[str,Any]|None,admin_state:Mapping[str,Any]|None, *,
                                 user_name:str="Mikael",changes_since_last_login:Sequence[Any]|None=None,
                                 macro_summary:Sequence[Any]|None=None,opportunities:Sequence[Mapping[str,Any]]|None=None,
                                 important_alerts:Sequence[Any]|None=None,paper_summary:Mapping[str,Any]|None=None)->dict[str,Any]|None:
    if not _is_admin(access):
        return None
    briefing=build_admin_voice_briefing(dict(admin_state or {}),user_name=user_name,
        changes_since_last_login=changes_since_last_login,macro_summary=macro_summary,
        opportunities=opportunities,important_alerts=important_alerts)
    st.markdown("### 🗣️ Assistente do Administrador")
    st.caption("AtlasQuant Voice · Português do Brasil · identidade oficial em preparação")
    st.info(briefing["spoken_text"])
    already=bool(st.session_state.get(SESSION_SPOKEN_KEY,False))
    components.html(_speech_html(briefing["spoken_text"],autoplay=not already),height=52)
    if not already:st.session_state[SESSION_SPOKEN_KEY]=True

    with st.expander("💬 Conversar com o assistente",expanded=False):
        q=st.text_input(
            "Pergunte sobre sistema, mudanças, macro, Radar, Paper ou release",
            key="atlasquant_admin_voice_question",
            placeholder="Ex.: O que mudou desde meu último acesso?",
        )
        if q:
            reply=answer_admin_question(
                q,
                admin_state=admin_state,
                changes=changes_since_last_login,
                macro_summary=macro_summary,
                opportunities=opportunities,
                paper_summary=paper_summary,
            )
            st.write(reply["answer"])
            components.html(_speech_html(reply["answer"],autoplay=False),height=52)

    st.caption("DEV: reprodução usa a voz PT-BR disponível no navegador. A voz original AtlasQuant será conectada pelo adaptador TTS oficial.")
    return briefing
