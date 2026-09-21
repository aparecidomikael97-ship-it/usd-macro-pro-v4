"""AtlasQuant Home Radar — decision-first private dashboard.

This module turns already-computed pair intelligence into a simple home screen.
It never creates orders, bypasses Safety Core, turns scores into probabilities,
or calls market-data providers. Voice playback uses the fixed server-side neural TTS identity only after an
explicit user click; browser/device TTS is never used as fallback.
"""
from __future__ import annotations

from html import escape
import json
import math
from typing import Any, Mapping, Sequence

import pandas as pd
import streamlit as st

from atlasquant_voice_assistant import render_contextual_voice_assistant
from atlasquant_neural_voice_ui import render_neural_voice_player
from atlasquant_session_profiles import (
    SESSION_PROFILES,
    SESSION_LABELS,
    extract_session_bucket,
    prioritize_rows_for_session,
    session_profile_summary,
)

SCHEMA="ATLASQUANT_HOME_RADAR_V1"


def _safe(value:Any, default:float=0.0)->float:
    try:
        x=float(value)
        return x if math.isfinite(x) else float(default)
    except Exception:
        return float(default)


def _bias(direction:object)->str:
    raw=str(direction or "").upper()
    if "COMPRA" in raw or "BUY" in raw:
        return "COMPRA"
    if "VENDA" in raw or "SELL" in raw:
        return "VENDA"
    return "NEUTRO"


def _blocked(pack:Mapping[str,Any])->bool:
    data=dict(pack.get("data_ready",{}) or {})
    state=str(pack.get("state","")).upper()
    gate=str(pack.get("gate","")).upper()
    if not bool(data.get("sufficient",False)):
        return True
    if any(x in state for x in ("NÃO OPERAR","NAO OPERAR","AGUARDAR","BLOCK","BLOQUE")):
        return True
    if gate in {"WAIT","BLOCKED","BLOQUEADO","N/D","—",""}:
        return True
    return False


def _adr_label(value:Any)->str:
    if value is None:
        return "N/D"
    x=_safe(value,-1)
    if x < 0:
        return "N/D"
    if x >= 100:
        return f"ESTICADO · ADR {x:.0f}%"
    if x >= 80:
        return f"ALTO · ADR {x:.0f}%"
    if x >= 45:
        return f"MODERADO · ADR {x:.0f}%"
    return f"BAIXO · ADR {x:.0f}%"


def home_rows_from_packs(packs:Sequence[Mapping[str,Any]]|None)->list[dict[str,Any]]:
    rows=[]
    for raw in list(packs or []):
        p=dict(raw or {})
        pair=str(p.get("pair") or "—")
        bias=_bias(p.get("direction",p.get("side")))
        blocked=_blocked(p)
        action="NÃO OPERAR" if blocked or bias=="NEUTRO" else bias
        data=dict(p.get("data_ready",{}) or {})
        strength=dict(p.get("strength",{}) or {})
        blockers=[str(x) for x in list(p.get("blockers",[]) or []) if str(x).strip()]
        session_bucket=extract_session_bucket(p)
        rows.append({
            "pair":pair,
            "session_bucket":session_bucket,
            "session_label":SESSION_LABELS.get(session_bucket,SESSION_LABELS["UNKNOWN"]),
            "bias":bias,
            "action":action,
            "priority":max(0.0,min(100.0,_safe(p.get("priority",p.get("unified",0))))),
            "quality":max(0.0,min(100.0,_safe(p.get("quality",0)))),
            "data_score":max(0.0,min(100.0,_safe(data.get("score",0)))),
            "data_ready":bool(data.get("sufficient",False)),
            "state":str(p.get("state") or "AGUARDAR"),
            "reason":str(p.get("reason") or "Sem motivo dominante disponível."),
            "next_action":str(p.get("next_action") or "Aguardar confirmação válida."),
            "base_score":_safe(strength.get("base_score",p.get("base_score",50)),50),
            "quote_score":_safe(strength.get("quote_score",p.get("quote_score",50)),50),
            "strength_diff":_safe(strength.get("difference",p.get("macro_diff",0)),0),
            "h4":str(p.get("h4") or "—"),
            "h1":str(p.get("h1") or "—"),
            "m15":str(p.get("m15") or "—"),
            "gate":str(p.get("gate") or "—"),
            "event":str(p.get("event") or "NORMAL"),
            "news":str(p.get("news_align") or "—"),
            "movement":_adr_label(p.get("adr")),
            "blockers":blockers,
            "target":str(p.get("target") or "—"),
            "w1":str(p.get("w1") or "—"),
            "d1":str(p.get("d1") or "—"),
            "pd_zone":str(p.get("pd_zone") or "—"),
            "sweep_type":str(p.get("sweep_type") or "—"),
            "sweep_level":str(p.get("sweep_level") or "—"),
            "ict_read":_safe(p.get("ict_read",0)),
            "inst_read":_safe(p.get("inst_read",0)),
            "up":[str(x) for x in list(p.get("up",[]) or []) if str(x).strip()],
            "down":[str(x) for x in list(p.get("down",[]) or []) if str(x).strip()],
            "positives":[str(x) for x in list(p.get("positives",[]) or []) if str(x).strip()],
            "hard_blocks":[str(x) for x in list(p.get("hard_blocks",[]) or []) if str(x).strip()],
            "soft_blocks":[str(x) for x in list(p.get("soft_blocks",[]) or []) if str(x).strip()],
        })
    rows.sort(key=lambda x:(x["action"]!="NÃO OPERAR",x["priority"],x["data_score"]),reverse=True)
    return rows


def home_summary(rows:Sequence[Mapping[str,Any]]|None)->dict[str,Any]:
    data=list(rows or [])
    actionable=[r for r in data if str(r.get("action")) in ("COMPRA","VENDA")]
    blocked=[r for r in data if str(r.get("action"))=="NÃO OPERAR"]
    best=actionable[0] if actionable else (data[0] if data else None)
    return {
        "total":len(data),
        "actionable":len(actionable),
        "blocked":len(blocked),
        "best_pair":str((best or {}).get("pair") or "—"),
        "best_action":str((best or {}).get("action") or "NÃO OPERAR"),
    }


def voice_script_for_row(row:Mapping[str,Any])->str:
    r=dict(row or {})
    pair=str(r.get("pair") or "este ativo")
    bias=str(r.get("bias") or "NEUTRO")
    action=str(r.get("action") or "NÃO OPERAR")
    priority=_safe(r.get("priority",0))
    quality=_safe(r.get("quality",0))
    data_score=_safe(r.get("data_score",0))
    reason=str(r.get("reason") or "não há motivo dominante suficiente")
    next_action=str(r.get("next_action") or "aguardar confirmação válida")
    h4=str(r.get("h4") or "sem dado")
    h1=str(r.get("h1") or "sem dado")
    m15=str(r.get("m15") or "sem dado")
    event=str(r.get("event") or "normal")
    session=str(r.get("session_label") or "sessão não informada")
    blockers=[str(x) for x in list(r.get("blockers",[]) or []) if str(x).strip()]
    blocker_text=(" Principais bloqueios: "+"; ".join(blockers[:3])+".") if blockers else ""
    return (
        f"Análise do {pair}. "
        f"O viés atual é {bias}. A orientação da tela é {action}. "
        f"A prioridade interna está em {priority:.0f} de 100, com qualidade {quality:.0f} de 100 "
        f"e prontidão dos dados {data_score:.0f} de 100. "
        f"O principal motivo é: {reason}. "
        f"No técnico, H4 está {h4}, H1 está {h1} e M15 está {m15}. "
        f"A janela de sessão identificada é {session}. "
        f"O risco de evento está classificado como {event}. "
        f"Próximo passo: {next_action}."
        f"{blocker_text} "
        "Esta leitura é probabilística e educacional; não é garantia de resultado nem ordem para corretora."
    )


def _card_html(row:Mapping[str,Any])->str:
    r=dict(row or {})
    action=str(r.get("action") or "NÃO OPERAR")
    tone="buy" if action=="COMPRA" else "sell" if action=="VENDA" else "wait"
    icon="🟢" if action=="COMPRA" else "🔴" if action=="VENDA" else "⚪"
    pair=escape(str(r.get("pair") or "—"))
    state=escape(str(r.get("state") or "—"))
    movement=escape(str(r.get("movement") or "N/D"))
    news=escape(str(r.get("news") or "—"))
    return f"""<div class="aq-home-card {tone}">
      <div class="aq-home-top"><strong>{pair}</strong><span>{icon} {escape(action)}</span></div>
      <div class="aq-home-score">{_safe(r.get('priority',0)):.0f}<small>/100 prioridade</small></div>
      <div class="aq-home-grid">
        <span>Dados <b>{_safe(r.get('data_score',0)):.0f}</b></span>
        <span>Qualidade <b>{_safe(r.get('quality',0)):.0f}</b></span>
        <span>{movement}</span>
        <span>Notícias <b>{news}</b></span>
      </div>
      <div class="aq-home-state">{state} · {escape(str(r.get('session_label') or 'Sessão não informada'))}</div>
    </div>"""


HOME_CSS="""
<style>
.aq-home-hero{border:1px solid rgba(137,170,210,.18);border-radius:18px;padding:18px 20px;margin:3px 0 14px;background:linear-gradient(120deg,rgba(18,47,79,.94),rgba(8,25,43,.94) 62%,rgba(12,52,55,.78))}
.aq-home-hero small{color:#6de2c5;font-weight:850;letter-spacing:.12em}.aq-home-hero h2{color:#edf4ff;margin:.25rem 0 .3rem;font-size:1.55rem}.aq-home-hero p{color:#9fb0c6;margin:0;max-width:820px}
.aq-home-card{border:1px solid rgba(137,170,210,.18);border-radius:15px;padding:14px 15px;min-height:184px;background:linear-gradient(180deg,rgba(17,34,57,.9),rgba(10,24,41,.84));margin-bottom:7px}
.aq-home-card.buy{border-top:3px solid #42d392}.aq-home-card.sell{border-top:3px solid #ff6b7a}.aq-home-card.wait{border-top:3px solid #9fb0c6}
.aq-home-top{display:flex;justify-content:space-between;gap:8px;align-items:center}.aq-home-top strong{font-size:1.04rem;color:#edf4ff}.aq-home-top span{font-size:.74rem;font-weight:850;color:#dceaff}
.aq-home-score{font-size:1.9rem;font-weight:850;color:#edf4ff;margin-top:10px}.aq-home-score small{font-size:.68rem;color:#9fb0c6;margin-left:4px}
.aq-home-grid{display:grid;grid-template-columns:1fr 1fr;gap:5px 9px;margin-top:10px}.aq-home-grid span{color:#9fb0c6;font-size:.69rem}.aq-home-grid b{color:#edf4ff}
.aq-home-state{border-top:1px solid rgba(137,170,210,.14);margin-top:10px;padding-top:9px;color:#c6d5e8;font-size:.7rem}
.aq-home-detail{border:1px solid rgba(137,170,210,.18);border-radius:15px;padding:14px 16px;background:rgba(10,26,44,.68);margin-top:8px}
@media(max-width:760px){.aq-home-hero{padding:14px 15px}.aq-home-hero h2{font-size:1.3rem}.aq-home-card{min-height:165px}.aq-home-grid{grid-template-columns:1fr}.aq-home-top{align-items:flex-start}}
</style>
"""


def render_browser_voice(script:str, *, key:str)->None:
    """Compatibility wrapper for the fixed AtlasQuant neural voice."""
    render_neural_voice_player(
        script,
        button_label="🔊 Ouvir análise com a voz AtlasQuant",
        key=f"home_{key}",
    )


def render_home_radar(
    packs:Sequence[Mapping[str,Any]]|None,
    *,
    experience_mode:str="Iniciante",
    macro_context:Mapping[str,Any]|None=None,
)->dict[str,Any]:
    rows=home_rows_from_packs(packs)
    mode="Avançado" if str(experience_mode).casefold().startswith("avan") else "Iniciante"
    st.markdown(HOME_CSS,unsafe_allow_html=True)
    st.markdown(
        """<div class="aq-home-hero"><small>TELA PRINCIPAL</small>
        <h2>🎯 Radar de Oportunidades</h2>
        <p>Bata o olho, veja onde há contexto e abra o ativo para entender o porquê. 
        Compra/Venda é viés de análise; dados insuficientes ou gates bloqueados viram NÃO OPERAR.</p></div>""",
        unsafe_allow_html=True,
    )
    if not rows:
        st.warning("Radar aguardando a Matriz dos pares e dados persistidos.")
        return {"schema":SCHEMA,"rows":0,"mode":mode,"real_orders_enabled":False}

    st.markdown("### 🕒 Meu horário disponível")
    profile_options=list(SESSION_PROFILES)
    stored_profile=st.session_state.get("aq_session_profile","Todos os horários")
    if stored_profile not in profile_options:
        stored_profile="Todos os horários"
    profile=st.radio(
        "Priorizar o Radar para",
        profile_options,
        index=profile_options.index(stored_profile),
        horizontal=True,
        key="aq_session_profile",
        help=(
            "Isto reorganiza onde olhar primeiro conforme seu horário. "
            "Não muda viés, score, Gate ou execução."
        ),
    )
    rows=prioritize_rows_for_session(rows,profile)
    session_summary=session_profile_summary(rows,profile)
    summary=home_summary(rows)
    if profile!="Todos os horários":
        if session_summary["matching"]>0:
            st.success(
                f"{session_summary['matching']} leitura(s) estão na janela escolhida agora. "
                "As demais continuam visíveis para comparação."
            )
        elif session_summary["unknown"]>0:
            st.info(
                "A sessão de algumas leituras ainda não está identificada. "
                "O AtlasQuant não vai escondê-las nem fingir compatibilidade."
            )
        else:
            st.warning(
                "O mercado está fora da sua janela escolhida neste snapshot. "
                "O Radar mantém o contexto visível, mas não força oportunidade fora do seu horário."
            )
    st.caption(session_summary["interpretation"])

    a,b,c,d=st.columns(4)
    a.metric("Pares avaliados",summary["total"])
    b.metric("Com contexto",summary["actionable"])
    c.metric("Não operar",summary["blocked"])
    d.metric("Melhor leitura",summary["best_pair"])

    top_n=3 if mode=="Iniciante" else min(5,len(rows))
    top=rows[:top_n]
    st.markdown("### Agora")
    cols=st.columns(min(3,len(top)))
    for idx,row in enumerate(top):
        with cols[idx%len(cols)]:
            st.markdown(_card_html(row),unsafe_allow_html=True)
            if st.button(f"Ver por que · {row['pair']}",key=f"aq_home_open_{row['pair'].replace('/','_')}",width="stretch"):
                st.session_state["aq_home_pair"]=row["pair"]

    options=[r["pair"] for r in rows]
    stored=st.session_state.get("aq_home_pair")
    if stored not in options:
        st.session_state["aq_home_pair"]=options[0]
    selected=st.selectbox("Ativo para análise detalhada",options,key="aq_home_pair")
    row=next(r for r in rows if r["pair"]==selected)

    st.markdown("### Por que está assim?")
    st.markdown('<div class="aq-home-detail">',unsafe_allow_html=True)
    x1,x2,x3,x4=st.columns(4)
    x1.metric("Viés",row["bias"])
    x2.metric("Ação agora",row["action"])
    x3.metric("Prioridade",f"{row['priority']:.0f}/100")
    x4.metric("Dados",f"{row['data_score']:.0f}/100")
    st.markdown(f"**Resumo:** {row['reason']}")
    st.markdown(f"**Próximo passo:** {row['next_action']}")
    st.caption(
        f"Força relativa Δ {row['strength_diff']:+.1f} pts · H4 {row['h4']} · "
        f"H1 {row['h1']} · M15 {row['m15']} · Gate {row['gate']} · {row['movement']}"
    )
    st.markdown('</div>',unsafe_allow_html=True)

    render_contextual_voice_assistant(
        row,
        mode=mode,
        macro_context=macro_context,
        key_prefix="aq_home_voice",
    )

    if mode=="Avançado":
        st.markdown("### Diagnóstico avançado")
        adv=pd.DataFrame([{
            "Par":r["pair"],"Sessão":r.get("session_label","Sessão não informada"),
            "Compatível com perfil":r.get("session_match","UNKNOWN"),
            "Ação":r["action"],"Viés":r["bias"],"Prioridade":round(r["priority"],1),
            "Qualidade":round(r["quality"],1),"Dados":round(r["data_score"],1),"H4":r["h4"],"H1":r["h1"],
            "M15":r["m15"],"Gate":r["gate"],"Movimento":r["movement"],"Notícias":r["news"],"Evento":r["event"],
        } for r in rows])
        st.dataframe(adv,width="stretch",hide_index=True)
        if row["blockers"]:
            st.warning("Bloqueios/atenções: "+" · ".join(row["blockers"][:6]))

    st.info("O Radar organiza onde olhar primeiro. Ele não envia ordens e não transforma prioridade em probabilidade de lucro.")
    return {
        "schema":SCHEMA,
        "rows":len(rows),
        "mode":mode,
        "selected_pair":row["pair"],
        "selected_action":row["action"],
        "session_profile":profile,
        "session_summary":session_summary,
        "real_orders_enabled":False,
        "automatic_execution":False,
    }


__all__=[
    "SCHEMA","home_rows_from_packs","home_summary","voice_script_for_row",
    "render_browser_voice","render_home_radar",
]