"""Streamlit Admin Voice panel.

ADMIN-only UI. Uses browser speech synthesis as a zero-cost DEV fallback while
the original AtlasQuant PT-BR production voice provider is not yet connected.
"""
from __future__ import annotations
from typing import Any,Mapping,Sequence
import os
import base64
import streamlit as st
import streamlit.components.v1 as components
from atlasquant_admin_voice_briefing import build_admin_voice_briefing
from atlasquant_aion_orchestrator import answer_aion
from atlasquant_aion_memory import append_memory,memory_context
from atlasquant_aion_action_approval import approve_pending_action

SESSION_SPOKEN_KEY="atlasquant_admin_voice_spoken"
SESSION_MEMORY_KEY="atlasquant_aion_memory"
SESSION_PENDING_ACTION_KEY="atlasquant_aion_pending_action"
SESSION_APPROVED_ACTION_KEY="atlasquant_aion_approved_action"

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
                                 important_alerts:Sequence[Any]|None=None,paper_summary:Mapping[str,Any]|None=None,
                                 timezone_name:str|None=None,connections:Mapping[str,Any]|None=None,
                                 general_ai_adapter:Any=None,web_research_adapter:Any=None)->dict[str,Any]|None:
    if not _is_admin(access):
        return None
    tz_name=str(timezone_name or os.getenv("ATLASQUANT_TIMEZONE","America/Sao_Paulo") or "America/Sao_Paulo")
    briefing=build_admin_voice_briefing(dict(admin_state or {}),user_name=user_name,timezone_name=tz_name,
        changes_since_last_login=changes_since_last_login,macro_summary=macro_summary,
        opportunities=opportunities,important_alerts=important_alerts)
    st.markdown("### 🗣️ AION · Assistente Inteligente do Administrador")
    st.caption("AION · Assistente de Voz Inteligente do Atlas Code · Português do Brasil")
    st.info(briefing["spoken_text"])
    already=bool(st.session_state.get(SESSION_SPOKEN_KEY,False))
    components.html(_speech_html(briefing["spoken_text"],autoplay=not already),height=52)
    if not already:st.session_state[SESSION_SPOKEN_KEY]=True

    with st.expander("💬 Conversar com o AION",expanded=False):
        st.caption(
            "Pergunte sobre o AtlasQuant, mercado ou assuntos gerais. "
            "Perguntas atuais usam pesquisa quando o adaptador estiver conectado."
        )
        q=st.text_input(
            "Pergunte qualquer coisa",
            key="atlasquant_admin_voice_question",
            placeholder="Ex.: Como está o AtlasQuant? Ou: pesquise uma notícia atual para mim.",
        )
        if q:
            history=list(st.session_state.get(SESSION_MEMORY_KEY,[]) or [])
            try:
                history=append_memory(history,role="user",text=q,metadata={"surface":"ADMIN_VOICE"})
            except Exception:
                history=list(history)[-20:]
            reply=answer_aion(
                q,
                admin_state=admin_state,
                changes=changes_since_last_login,
                macro_summary=macro_summary,
                opportunities=opportunities,
                paper_summary=paper_summary,
                memory=memory_context(history),
                connections=connections,
                general_ai_adapter=general_ai_adapter,
                web_research_adapter=web_research_adapter,
            )
            answer=str(reply.get("answer") or "Não consegui responder com segurança.")
            try:
                history=append_memory(
                    history,role="assistant",text=answer,
                    metadata={"route":reply.get("route"),"source_of_truth":reply.get("source_of_truth")},
                )
            except Exception:
                pass
            st.session_state[SESSION_MEMORY_KEY]=history
            st.write(answer)
            components.html(_speech_html(answer,autoplay=False),height=52)

            sources=list(reply.get("sources",[]) or [])
            if sources:
                st.markdown("**Fontes consultadas**")
                for source in sources[:8]:
                    title=str(source.get("title") or source.get("url") or "Fonte")
                    url=str(source.get("url") or "")
                    if url.startswith(("https://","http://")):
                        st.markdown(f"- [{title}]({url})")

            pending=reply.get("pending_action")
            if isinstance(pending,dict):
                st.session_state[SESSION_PENDING_ACTION_KEY]=pending
                st.warning(
                    "Ação externa preparada, mas ainda não executada. "
                    "Confirme somente se quiser autorizar exatamente esta ação."
                )
                c1,c2=st.columns(2)
                if c1.button("✅ Confirmar ação externa",key="atlasquant_aion_confirm_external"):
                    try:
                        approved=approve_pending_action(
                            pending,
                            approved_by=str(user_name or "Administrador"),
                        )
                    except Exception as exc:
                        st.error(f"Não foi possível aprovar: {type(exc).__name__}.")
                    else:
                        st.session_state[SESSION_APPROVED_ACTION_KEY]=approved
                        st.session_state.pop(SESSION_PENDING_ACTION_KEY,None)
                        st.success(
                            "Ação aprovada para o adaptador da plataforma. "
                            "Nenhuma execução foi simulada ou presumida."
                        )
                if c2.button("Cancelar",key="atlasquant_aion_cancel_external"):
                    st.session_state.pop(SESSION_PENDING_ACTION_KEY,None)
                    st.info("Ação cancelada.")

    st.caption("DEV: reprodução usa a voz PT-BR disponível no navegador. A voz original AION será conectada pelo adaptador TTS oficial.")
    return briefing
