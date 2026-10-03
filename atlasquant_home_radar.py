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
from atlasquant_signal_lifecycle import derive_signal_view, format_signal_time
from atlasquant_operational_state import (
    OPERATIONAL_SPINE_CSS,
    operational_presentation,
    operational_strip_html,
)
from atlasquant_session_profiles import (
    SESSION_FILTER_OPTIONS,
    SESSION_LABELS,
    extract_session_bucket,
    filter_label_for_profile,
    prioritize_rows_for_session,
    profile_for_filter,
    session_profile_summary,
)
from atlasquant_radar_board import (
    compose_fx_board,
    crypto_ranking,
    highlight_top_fx,
    index_ranking,
)
from atlasquant_premium_shell import PREMIUM_CSS, cockpit_header_html

SCHEMA="ATLASQUANT_HOME_RADAR_V1"
RADAR_VISIBLE_LIMIT=10


def _safe(value:Any, default:float=0.0)->float:
    try:
        x=float(value)
        return x if math.isfinite(x) else float(default)
    except Exception:
        return float(default)


def _mapping(value:Any)->dict[str,Any]:
    """Normalize persisted/runtime payloads without crashing the Radar."""
    return dict(value) if isinstance(value,Mapping) else {}


def _bias(direction:object)->str:
    raw=str(direction or "").upper()
    if "COMPRA" in raw or "BUY" in raw:
        return "COMPRA"
    if "VENDA" in raw or "SELL" in raw:
        return "VENDA"
    return "NEUTRO"


def _blocked(pack:Mapping[str,Any])->bool:
    data=_mapping(pack.get("data_ready"))
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
        if not isinstance(raw,Mapping):
            continue
        p=dict(raw)
        pair=str(p.get("pair") or "—").strip() or "—"
        bias=_bias(p.get("direction",p.get("side")))
        blocked=_blocked(p)
        action="NÃO OPERAR" if blocked or bias=="NEUTRO" else bias
        data=_mapping(p.get("data_ready"))
        strength=_mapping(p.get("strength"))
        blockers=[str(x) for x in list(p.get("blockers",[]) or []) if str(x).strip()]
        session_bucket=extract_session_bucket(p)
        signal=_mapping(p.get("signal_lifecycle"))
        if not signal:
            signal=derive_signal_view(p,timezone="UTC")
        signal_code=str(signal.get("status_code") or "UNVERIFIED")
        signal_side=str(signal.get("side") or ("BUY" if bias=="COMPRA" else "SELL" if bias=="VENDA" else "WAIT"))
        signal_action="COMPRA" if signal_side=="BUY" else "VENDA" if signal_side=="SELL" else "AGUARDAR"
        signal_headline={
            "CONFIRMED":f"{signal_action} CONFIRMADA",
            "POSSIBLE":f"POSSÍVEL {signal_action}",
            "EXPIRED":f"{signal_action} EXPIRADA",
            "BLOCKED":f"{signal_action} BLOQUEADA",
            "UNVERIFIED":f"{signal_action} SEM HORÁRIO — NÃO ENTRAR",
            "NO_SIGNAL":"AGUARDAR",
        }.get(signal_code,str(signal.get("status_label") or "AGUARDAR"))
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
            "signal":signal,
            "signal_status_code":signal_code,
            "signal_status_label":str(signal.get("status_label") or "SEM STATUS"),
            "signal_headline":signal_headline,
            "signal_reference_at":str(signal.get("reference_at") or ""),
            "signal_reference_display":str(signal.get("reference_display") or "horário não comprovado"),
            "signal_confirmed_at":str(signal.get("confirmed_at") or ""),
            "signal_observed_at":str(signal.get("observed_at") or ""),
            "signal_valid_until":str(signal.get("valid_until") or ""),
            "signal_age_minutes":signal.get("age_minutes"),
            "signal_remaining_minutes":signal.get("remaining_minutes"),
            "signal_timezone":str(signal.get("timezone") or "UTC"),
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
            "evidence_source":str(
                p.get("evidence_source")
                or p.get("source")
                or p.get("runtime_source")
                or "Radar / pack institucional"
            ),
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


def radar_operational_model(row:Mapping[str,Any]|None)->dict[str,Any]:
    r=dict(row or {})
    signal_code=str(r.get("signal_status_code") or "UNVERIFIED").upper()
    reference=str(r.get("signal_reference_display") or "")
    age=r.get("signal_age_minutes")
    if signal_code=="EXPIRED":
        temporal_code="EXPIRED"
    elif signal_code in {"UNVERIFIED","BLOCKED","NO_SIGNAL"} or not reference or age is None:
        temporal_code="UNVERIFIED"
    elif signal_code in {"CONFIRMED","POSSIBLE"}:
        temporal_code="CURRENT"
    else:
        temporal_code="UNKNOWN"
    state=(
        "NÃO OPERAR"
        if str(r.get("action") or "")=="NÃO OPERAR"
        else str(r.get("state") or "OBSERVAÇÃO")
    )
    return operational_presentation(
        pair=r.get("pair"),
        bias=r.get("bias"),
        state=state,
        quality=r.get("quality"),
        data_score=r.get("data_score"),
        temporal_code=temporal_code,
        temporal_label=r.get("signal_status_label"),
        reference_display=reference,
        authorized=False,
        evidence_source=r.get("evidence_source") or "Radar / pack institucional",
        next_action=r.get("next_action") or "Aguardar confirmação válida.",
    )


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
    signal_headline=str(r.get("signal_headline") or "sem status de sinal")
    signal_reference=str(r.get("signal_reference_display") or "horário não comprovado")
    signal_age=r.get("signal_age_minutes")
    signal_age_text=(" idade da leitura não comprovada." if signal_age is None else f" leitura com {float(signal_age):.0f} minutos.")
    return (
        f"Análise do {pair}. "
        f"O viés atual é {bias}. A orientação da tela é {action}. "
        f"Status temporal: {signal_headline}, referência {signal_reference};{signal_age_text} "
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
    signal_headline=escape(str(r.get("signal_headline") or "AGUARDAR"))
    signal_reference=escape(str(r.get("signal_reference_display") or "horário não comprovado"))
    signal_age=r.get("signal_age_minutes")
    signal_remaining=r.get("signal_remaining_minutes")
    age_text="idade N/D" if signal_age is None else f"há {float(signal_age):.0f} min"
    validity_text=(
        "revalidar agora"
        if str(r.get("signal_status_code")) in {"EXPIRED","UNVERIFIED","BLOCKED"}
        else ("validade técnica ≤ "+f"{float(signal_remaining):.0f} min" if signal_remaining is not None else "validade N/D")
    )
    confidence=escape(str(r.get("confidence") or "NÃO CONFIRMADA"))
    risk="BLOQUEADO" if action=="NÃO OPERAR" else escape(str(r.get("event") or "NÃO CONFIRMADO"))
    return f"""<div class="aq-home-card {tone}">
      <div class="aq-home-top"><strong>{pair}</strong><span>{icon} {escape(action)}</span></div>
      <div class="aq-home-signal">{signal_headline}</div>
      <div class="aq-home-time">{signal_reference} · {escape(age_text)} · {escape(validity_text)}</div>
      <div class="aq-home-score">{_safe(r.get('priority',0)):.0f}<small>/100 prioridade</small></div>
      <div class="aq-home-grid">
        <span>Confiança <b>{confidence}</b></span>
        <span>Risco <b>{risk}</b></span>
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
.aq-home-hero small{color:#7bf0d3;font-weight:900;letter-spacing:.12em}.aq-home-hero h2{color:#ffffff;margin:.25rem 0 .3rem;font-size:1.55rem}.aq-home-hero p{color:#edf3fb;margin:0;max-width:820px;font-weight:650}
.aq-home-card{border:1px solid rgba(137,170,210,.18);border-radius:15px;padding:14px 15px;min-height:184px;background:linear-gradient(180deg,rgba(17,34,57,.9),rgba(10,24,41,.84));margin-bottom:7px}
.aq-home-card.buy{border-top:3px solid #42d392}.aq-home-card.sell{border-top:3px solid #ff6b7a}.aq-home-card.wait{border-top:3px solid #9fb0c6}
.aq-home-top{display:flex;justify-content:space-between;gap:8px;align-items:center}.aq-home-top strong{font-size:1.04rem;color:#ffffff}.aq-home-top span{font-size:.74rem;font-weight:900;color:#f1f6fd}
.aq-home-score{font-size:1.9rem;font-weight:900;color:#ffffff;margin-top:10px}.aq-home-score small{font-size:.72rem;color:#eef4fb;font-weight:800;margin-left:4px}
.aq-home-grid{display:grid;grid-template-columns:1fr 1fr;gap:5px 9px;margin-top:10px}.aq-home-grid span{color:#eef4fb;font-size:.73rem;font-weight:700}.aq-home-grid b{color:#ffffff;font-weight:850}
.aq-home-state{border-top:1px solid rgba(137,170,210,.24);margin-top:10px;padding-top:9px;color:#f4f8fd;font-size:.74rem;font-weight:750;line-height:1.35}
.aq-home-signal{margin-top:9px;color:#ffffff;font-size:.82rem;font-weight:900;letter-spacing:.025em}
.aq-home-time{margin-top:3px;color:#eef4fb;font-size:.70rem;font-weight:700;line-height:1.35}
.aq-home-detail{border:1px solid rgba(137,170,210,.18);border-radius:15px;padding:14px 16px;background:rgba(10,26,44,.68);margin-top:8px}
.aq-rank-board{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:8px;margin:8px 0 14px}
.aq-rank-card{border:1px solid rgba(163,190,222,.34);border-radius:12px;padding:11px 12px;background:#10233a;color:#f7fbff !important;min-height:108px}
.aq-rank-card strong{display:block;color:#ffffff !important;font-size:.98rem}
.aq-rank-card em{display:block;margin-top:2px;color:#e7eef8 !important;font-style:normal;font-size:.78rem;font-weight:750}
.aq-rank-card span{display:block;margin-top:6px;color:#f4f8fd !important;font-size:.8rem;font-weight:750;line-height:1.4}
.aq-home-hero h2,.aq-home-hero p{color:#f7fbff !important}
.aq-home-card{transition:border-color .2s ease, transform .2s ease}
.aq-home-card:hover{border-color:rgba(215,181,109,.55)}
.aq-radar-live{display:flex;align-items:center;gap:8px;margin-top:10px;color:#d7e4f2;font-size:.75rem;font-weight:800}
.aq-radar-freshness{display:grid;grid-template-columns:1.15fr 1.6fr .75fr 1.5fr 1fr;gap:7px;margin:0 0 13px}
.aq-radar-freshness>div{border:1px solid rgba(163,190,222,.26);border-radius:11px;padding:8px 10px;background:rgba(10,26,44,.72);min-width:0}
.aq-radar-freshness small{display:block;color:#dce8f5;font-size:.61rem;font-weight:900;letter-spacing:.065em;text-transform:uppercase}
.aq-radar-freshness strong{display:block;color:#ffffff;font-size:.74rem;line-height:1.3;margin-top:3px;overflow-wrap:anywhere}
.aq-radar-freshness[data-tone="good"]>div:first-child{border-color:rgba(66,211,146,.48)}
.aq-radar-freshness[data-tone="warn"]>div:first-child{border-color:rgba(242,193,78,.5)}
.aq-radar-freshness[data-tone="bad"]>div:first-child{border-color:rgba(255,107,122,.52)}
.aq-radar-dot{width:8px;height:8px;border-radius:50%;background:#8fd0c4;animation:aq-ping 2.8s ease-out infinite}
@keyframes aq-ping{0%{box-shadow:0 0 0 0 rgba(143,208,196,.55)}100%{box-shadow:0 0 0 10px rgba(143,208,196,0)}}
@media(max-width:760px){.aq-home-hero{padding:14px 15px}.aq-home-hero h2{font-size:1.3rem}.aq-home-card{min-height:0}.aq-home-grid{grid-template-columns:1fr}.aq-home-top{align-items:flex-start}.aq-rank-board{grid-template-columns:1fr}.aq-home-card:hover{transform:none}.aq-radar-freshness{grid-template-columns:1fr 1fr}.aq-radar-freshness>div:first-child{grid-column:1/-1}}
@media (prefers-reduced-motion:reduce){.aq-radar-dot,.aq-home-card{animation:none !important}}
</style>
"""


def radar_freshness_html(freshness:Mapping[str,Any]|None)->str:
    """One truthful freshness strip shared by Beginner and Advanced Radar."""
    item=dict(freshness or {})
    state=str(item.get("state") or "").strip().upper()
    refresh=" ".join(str(item.get("refresh_status") or "").split())[:140]
    retained=refresh.casefold().startswith("pacote anterior")
    if retained:
        status="PACOTE ANTERIOR MANTIDO"
        tone="warn"
    elif state=="LIVE_REFRESH":
        status="ATUALIZAÇÃO AO VIVO CONCLUÍDA"
        tone="good"
    elif state in {"CACHED_SNAPSHOT","VALIDATED_SNAPSHOT"}:
        status="SNAPSHOT VALIDADO"
        tone="good"
    elif state=="STALE_REJECTED":
        status="SNAPSHOT REJEITADO · CAMINHO AO VIVO"
        tone="warn"
    elif state=="LIVE_REQUIRED":
        status="CAMINHO AO VIVO · FRESCOR GLOBAL NÃO COMPROVADO"
        tone="warn"
    else:
        status="FRESCOR NÃO COMPROVADO"
        tone="bad"

    generated=str(
        item.get("runtime_generated_at")
        or item.get("generated_at")
        or ""
    ).strip() or "horário não comprovado"
    age=item.get("age_minutes")
    age_text="N/D"
    if isinstance(age,(int,float)) and math.isfinite(float(age)) and float(age)>=0:
        age_text=f"{float(age):.0f} min"
    source=" ".join(str(item.get("source") or "").split())[:100] or "origem não informada"
    refresh_text=refresh or "estado de atualização não informado"
    state_attr=escape(state or "UNKNOWN")
    return (
        f'<section class="aq-radar-freshness" data-tone="{tone}" data-freshness-state="{state_attr}" '
        'role="status" aria-label="Frescor e atualização do Radar">'
        f'<div><small>Estado</small><strong>{escape(status)}</strong></div>'
        f'<div><small>Última evidência</small><strong>{escape(generated)}</strong></div>'
        f'<div><small>Idade</small><strong>{escape(age_text)}</strong></div>'
        f'<div><small>Atualização</small><strong>{escape(refresh_text)}</strong></div>'
        f'<div><small>Origem</small><strong>{escape(source)}</strong></div>'
        '</section>'
    )


def render_browser_voice(script:str, *, key:str)->None:
    """Compatibility wrapper for the fixed AtlasQuant neural voice."""
    render_neural_voice_player(
        script,
        button_label="🔊 Ouvir análise com a voz AtlasQuant",
        key=f"home_{key}",
    )


def _separate_board_html(title:str, rows:Sequence[Mapping[str,Any]])->str:
    cards=[]
    for row in list(rows or []):
        score=row.get("score")
        score_text="sem score ao vivo" if score is None else f"{float(score):.0f}/100 observação"
        cards.append(
            '<div class="aq-rank-card">'
            f'<strong>{escape(str(row.get("rank") or "—"))}. {escape(str(row.get("symbol") or "—"))}</strong>'
            f'<em>{escape(str(row.get("name") or ""))}</em>'
            f'<span>{escape(str(row.get("action") or "NÃO OPERAR"))} · {escape(str(row.get("state") or ""))}</span>'
            f'<span>{escape(score_text)}</span>'
            '</div>'
        )
    return (
        f'<h3 style="color:#ffffff;margin:8px 0 4px">{escape(title)}</h3>'
        '<div class="aq-rank-board">' + "".join(cards) + "</div>"
    )


def render_home_radar(
    packs:Sequence[Mapping[str,Any]]|None,
    *,
    experience_mode:str="Iniciante",
    macro_context:Mapping[str,Any]|None=None,
    ranking:Any=None,
    separate_observations:Mapping[str,Any]|None=None,
    freshness:Mapping[str,Any]|None=None,
)->dict[str,Any]:
    pack_rows=home_rows_from_packs(packs)
    board=compose_fx_board(pack_rows, ranking)
    rows=list(board["rows"])
    observations=dict(separate_observations or {})
    indices=index_ranking(observations.get("indices"))
    cryptos=crypto_ranking(observations.get("cryptos"))
    mode="Avançado" if str(experience_mode).casefold().startswith("avan") else "Iniciante"
    st.markdown(PREMIUM_CSS,unsafe_allow_html=True)
    st.markdown(HOME_CSS,unsafe_allow_html=True)
    st.markdown(OPERATIONAL_SPINE_CSS,unsafe_allow_html=True)
    st.markdown(
        cockpit_header_html(
            "Radar de Oportunidades",
            "Os 28 cruzamentos G8 passam pelo mesmo pipeline. Compra/Venda é viés de análise; "
            "fonte insuficiente vira NÃO CONFIRMADO ou BLOQUEADO.",
            eyebrow="FOREX RADAR · G8 UNIVERSE",
            telemetry={
                "MONITORADOS": f"{board['monitored']}/28",
                "TÉCNICA": board["institutional"],
                "MACRO": board["macro_only"],
                "ORDENS": "BLOQUEADAS",
            },
        ),
        unsafe_allow_html=True,
    )
    st.markdown(radar_freshness_html(freshness),unsafe_allow_html=True)
    if not rows:
        st.warning("Radar aguardando a Matriz dos pares e dados persistidos.")
        return {"schema":SCHEMA,"rows":0,"mode":mode,"real_orders_enabled":False}

    options=[r["pair"] for r in rows]
    pending=st.session_state.pop("aq_home_pair_pending", None)
    if pending in options:
        st.session_state["aq_home_pair"]=pending
    stored=st.session_state.get("aq_home_pair")
    if stored not in options:
        st.session_state["aq_home_pair"]=options[0]
    selected=st.selectbox("Ativo para análise detalhada",options,key="aq_home_pair")
    row=next(r for r in rows if r["pair"]==selected)
    st.caption("A voz do ativo fica aqui no topo. O ranking continua abaixo, sem esconder alertas.")
    render_contextual_voice_assistant(
        row,
        mode=mode,
        macro_context=macro_context,
        key_prefix="aq_home_voice",
    )

    st.markdown("### 🕒 Meu horário disponível")
    profile_options=list(SESSION_FILTER_OPTIONS)
    stored_profile=filter_label_for_profile(st.session_state.get("aq_session_profile","Ambos"))
    if stored_profile not in profile_options:
        stored_profile="Ambos"
    if st.session_state.get("aq_session_profile")!=stored_profile:
        st.session_state["aq_session_profile"]=stored_profile
    profile_label=st.radio(
        "Priorizar o Radar para",
        profile_options,
        index=profile_options.index(stored_profile),
        horizontal=True,
        key="aq_session_profile",
        help=(
            "Ambos mostra o dia inteiro. Noite prioriza Ásia e Londres. "
            "Dia prioriza Nova York e a continuidade. "
            "O filtro só reorganiza a atenção: não muda viés, score, Gate ou execução."
        ),
    )
    profile=profile_for_filter(profile_label)
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
    a.metric("Forex monitorados",f"{board['monitored']}/28")
    b.metric("Com contexto",summary["actionable"])
    c.metric("Não operar",summary["blocked"])
    d.metric("Melhor leitura",summary["best_pair"])
    st.caption(
        f"{board['monitored']} pares Forex monitorados · "
        f"leitura institucional {board['institutional']} · radar macro {board['macro_only']} · "
        f"sem leitura {board['missing']}. O pipeline avalia os 28 sem exigir seleção individual; "
        "pares sem técnica/proveniência ficam bloqueados. Índices e criptos ficam em rankings separados."
    )

    # Share only this already-computed resident presentation with the cockpit.
    # No provider call, persistence, score calculation or authorization change.
    st.session_state["atlasquant_reference_fx_population"] = {"rows": rows, "freshness": dict(freshness or {})}
    from atlasquant_interface_final import eligible_fx_population
    eligible = eligible_fx_population(st.session_state["atlasquant_reference_fx_population"])["ranked"]
    top_n=min(RADAR_VISIBLE_LIMIT,len(eligible))
    top=highlight_top_fx(eligible, top_n)
    if mode=="Iniciante" and top:
        try:
            from atlasquant_premium_shell import beginner_attention_html
            st.markdown(PREMIUM_CSS, unsafe_allow_html=True)
            st.markdown(beginner_attention_html(top[0]), unsafe_allow_html=True)
        except Exception:
            pass
    st.markdown("### Top 10 · ranking validado" if top else "### Ranking aguardando dados validados")
    st.caption(
        "O Radar mostra até 10 ativos Forex que merecem atenção no snapshot atual. "
        "O destaque é dinâmico e não significa entrada autorizada."
    )
    cols=st.columns(min(3,len(top))) if top else []
    for idx,row in enumerate(top):
        with cols[idx%len(cols)]:
            st.markdown(_card_html(row),unsafe_allow_html=True)
            if st.button(f"Ver por que · {row['pair']}",key=f"aq_home_open_{row['pair'].replace('/','_')}",width="stretch"):
                st.session_state["aq_home_pair_pending"]=row["pair"]
                st.rerun()
    row=next(item for item in rows if item["pair"]==selected)

    st.markdown("### Rankings separados")
    st.caption(
        "Índices e criptos não entram no TOP 10 Forex e não herdam pesos do universo de moedas. "
        "Sem motor próprio validado, a ação permanece NÃO OPERAR."
    )
    st.markdown(_separate_board_html("Ranking de índices", indices), unsafe_allow_html=True)
    st.markdown(_separate_board_html("Ranking de criptos", cryptos), unsafe_allow_html=True)
    if mode=="Avançado":
        st.dataframe(
            pd.DataFrame([{
                "Classe":"Índice",
                "Ativo":row["symbol"],
                "Nome":row["name"],
                "Rank":row["rank"],
                "Ação":row["action"],
                "Estado":row["state"],
                "Score":row["score"],
            } for row in indices] + [{
                "Classe":"Cripto",
                "Ativo":row["symbol"],
                "Nome":row["name"],
                "Rank":row["rank"],
                "Ação":row["action"],
                "Estado":row["state"],
                "Score":row["score"],
            } for row in cryptos]),
            width="stretch",
            hide_index=True,
        )

    _operational_model=radar_operational_model(row)
    st.markdown(
        operational_strip_html(_operational_model),
        unsafe_allow_html=True,
    )
    st.caption(
        "No Radar, compra/venda é viés de análise. A faixa compartilhada permanece "
        "NÃO AUTORIZADA porque esta tela não é o gate final de entrada."
    )

    st.markdown("### Por que está assim?")
    st.markdown('<div class="aq-home-detail">',unsafe_allow_html=True)
    x1,x2,x3,x4=st.columns(4)
    x1.metric("Viés",row["bias"])
    x2.metric("Ação agora",row["action"])
    x3.metric("Prioridade",f"{row['priority']:.0f}/100")
    x4.metric("Dados",f"{row['data_score']:.0f}/100")
    st.markdown(f"**Status temporal:** {row['signal_headline']}")
    _signal_detail = row["signal_reference_display"]
    if row.get("signal_age_minutes") is not None:
        _signal_detail += f" · há {float(row['signal_age_minutes']):.0f} min"
    if row.get("signal_confirmed_at"):
        _signal_detail += " · confirmação registrada em " + format_signal_time(row["signal_confirmed_at"],row["signal_timezone"])
    if row.get("signal_valid_until"):
        _signal_detail += " · limite técnico de frescor até " + format_signal_time(row["signal_valid_until"],row["signal_timezone"])
    st.caption(_signal_detail)
    if row["signal_status_code"] in {"EXPIRED","UNVERIFIED","BLOCKED"}:
        st.warning("Esta leitura não deve ser tratada como entrada atual. É obrigatória nova validação.")
    st.markdown(f"**Resumo:** {row['reason']}")
    st.markdown(f"**Próximo passo:** {row['next_action']}")
    st.caption(
        f"Força relativa Δ {row['strength_diff']:+.1f} pts · H4 {row['h4']} · "
        f"H1 {row['h1']} · M15 {row['m15']} · Gate {row['gate']} · {row['movement']}"
    )
    st.markdown('</div>',unsafe_allow_html=True)

    if mode=="Avançado":
        st.markdown("### Diagnóstico avançado")
        adv=pd.DataFrame([{
            **({
                "Técnico":(r.get("score_components") or {}).get("technical"),
                "Macro":(r.get("score_components") or {}).get("macro"),
                "Componente sessão":(r.get("score_components") or {}).get("session"),
                "Componente qualidade":(r.get("score_components") or {}).get("quality"),
            } if isinstance(r.get("score_components"),Mapping) else {}),
            "Par":r["pair"],"Sessão":r.get("session_label","Sessão não informada"),
            "Compatível com perfil":r.get("session_match","UNKNOWN"),
            "Ação":r["action"],"Viés":r["bias"],"Prioridade":round(r["priority"],1),
            "Confiança":r.get("confidence","NÃO CONFIRMADA"),
            "Proveniência":r.get("provenance_state","NÃO CONFIRMADA"),
            "Qualidade":round(r["quality"],1),"Dados":round(r["data_score"],1),"H4":r["h4"],"H1":r["h1"],
            "M15":r["m15"],"Gate":r["gate"],"Status temporal":r["signal_headline"],
            "Hora leitura":r["signal_reference_display"],"Idade min":r["signal_age_minutes"],
            "Movimento":r["movement"],"Notícias":r["news"],"Evento":r["event"],
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
        "session_filter":profile_label,
        "session_summary":session_summary,
        "fx_monitored":board["monitored"],
        "fx_top":[row["pair"] for row in top],
        "indices":[row["symbol"] for row in indices],
        "cryptos":[row["symbol"] for row in cryptos],
        "real_orders_enabled":False,
        "automatic_execution":False,
    }


__all__=[
    "SCHEMA","home_rows_from_packs","home_summary","voice_script_for_row",
    "render_browser_voice","radar_freshness_html","render_home_radar",
]
