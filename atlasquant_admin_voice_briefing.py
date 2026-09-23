"""AtlasQuant Admin voice briefing composer.

Builds a PT-BR spoken briefing from authoritative AtlasQuant evidence. The
voice can explain and alert, but never authorizes orders or bypasses gates.
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any,Mapping,Sequence
from atlasquant_admin_voice_profile import admin_voice_profile

SAFE_STATES={"NORMAL","CAUTION","PROTECTED","HALTED","UNKNOWN"}

def _greeting(hour:int)->str:
    if 5<=hour<12:return "Bom dia"
    if 12<=hour<18:return "Boa tarde"
    return "Boa noite"

def _clean_name(value:Any)->str:
    name=" ".join(str(value or "Administrador").strip().split())
    return name[:40] or "Administrador"

def _items(values:Sequence[Any]|None,limit:int)->list[str]:
    out=[]
    for x in values or []:
        s=" ".join(str(x or "").strip().split())
        if s and s not in out:out.append(s[:180])
        if len(out)>=limit:break
    return out

def _opportunity_sentence(rows:Sequence[Mapping[str,Any]]|None)->str|None:
    ready=[]
    preparing=[]
    for row in rows or []:
        r=dict(row or {});pair=str(r.get("pair","")).strip();status=str(r.get("operational_status",r.get("status",""))).upper()
        if not pair:continue
        if r.get("executable") is True and status.startswith("LIBERADO"):ready.append(pair)
        elif status in {"PREPARANDO","AGUARDANDO GATILHO"} or r.get("executable") is False:preparing.append(pair)
    if ready:return f"Há {len(ready)} oportunidade{'s' if len(ready)!=1 else ''} liberada{'s' if len(ready)!=1 else ''} pelo modelo: {', '.join(ready[:3])}."
    if preparing:return f"Não há entrada liberada agora. Estou acompanhando {', '.join(preparing[:3])} em preparação."
    return None

def build_admin_voice_briefing(admin_state:Mapping[str,Any],*,user_name:str="Mikael",now:datetime|None=None,
                               changes_since_last_login:Sequence[Any]|None=None,
                               macro_summary:Sequence[Any]|None=None,
                               opportunities:Sequence[Mapping[str,Any]]|None=None,
                               important_alerts:Sequence[Any]|None=None,
                               max_changes:int=4,max_macro:int=3)->dict[str,Any]:
    state=dict(admin_state or {});current=now or datetime.now(timezone.utc)
    if current.tzinfo is None:current=current.replace(tzinfo=timezone.utc)
    system=str(state.get("system_state","UNKNOWN")).upper()
    if system not in SAFE_STATES:system="UNKNOWN"
    name=_clean_name(user_name);parts=[f"{_greeting(current.hour)}, {name}. Vou te atualizar sobre o AtlasQuant."]
    banner=str(state.get("banner","")).strip()
    release=str(state.get("release_state","NOT_READY")).upper()
    if system=="NORMAL":
        parts.append("O estado geral do sistema está normal.")
    elif system=="CAUTION":
        parts.append("O sistema está em atenção. Novas entradas continuam sob validação.")
    elif system=="PROTECTED":
        parts.append("O sistema está protegido. Novas entradas estão bloqueadas até a condição ser normalizada.")
    elif system=="HALTED":
        parts.append("O sistema está interrompido em modo seguro. Novas entradas estão bloqueadas.")
    else:
        parts.append("Ainda não tenho evidência suficiente para declarar o sistema normal. Vou manter a operação em modo seguro.")
    reasons=_items(state.get("health_reasons"),3)
    if reasons:parts.append("Motivo principal: "+", ".join(reasons)+".")
    if banner and banner.upper() not in " ".join(parts).upper():parts.append(banner.rstrip(".")+".")
    parts.append(f"Estado de release: {release.replace('_',' ').lower()}.")

    changes=_items(changes_since_last_login,max_changes)
    if changes:parts.append("Desde o seu último acesso: "+"; ".join(changes)+".")
    alerts=_items(important_alerts,3)
    if alerts:parts.append("Pontos que precisam da sua atenção: "+"; ".join(alerts)+".")
    macro=_items(macro_summary,max_macro)
    if macro:parts.append("Resumo de mercado: "+"; ".join(macro)+".")
    opp=_opportunity_sentence(opportunities)
    if opp:parts.append(opp)

    if state.get("new_entries_allowed") is not True:
        parts.append("Neste momento, o assistente não considera novas entradas autorizadas.")
    parts.append("Eu posso explicar qualquer um desses pontos em mais detalhes.")
    spoken=" ".join(parts)
    priority="IMPORTANT_ALERT" if system in {"PROTECTED","HALTED","UNKNOWN"} or alerts else "SYSTEM_UPDATE"
    return {
        "profile":admin_voice_profile(),
        "language":"pt-BR",
        "mode":priority,
        "system_state":system,
        "release_state":release,
        "spoken_text":spoken,
        "segments":parts,
        "auto_play_on_admin_open":True,
        "voice_can_authorize_orders":False,
        "real_orders_enabled":False,
        "source_of_truth":"ADMIN_MISSION_CONTROL",
    }
