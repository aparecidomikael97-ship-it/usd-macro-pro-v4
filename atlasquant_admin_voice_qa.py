"""Deterministic Admin Voice question router.

Answers only from supplied AtlasQuant evidence. It never invents market state,
authorizes an order, or changes any operational gate.
"""
from __future__ import annotations
from typing import Any,Mapping,Sequence

def _norm(v:Any)->str:
    return " ".join(str(v or "").strip().lower().split())

def _join(values:Sequence[Any]|None,limit:int=4)->str:
    out=[]
    for x in values or []:
        s=" ".join(str(x or "").strip().split())
        if s and s not in out:out.append(s)
        if len(out)>=limit:break
    return "; ".join(out)

def answer_admin_question(question:str,*,admin_state:Mapping[str,Any]|None=None,
                          changes:Sequence[Any]|None=None,macro_summary:Sequence[Any]|None=None,
                          opportunities:Sequence[Mapping[str,Any]]|None=None,
                          paper_summary:Mapping[str,Any]|None=None)->dict[str,Any]:
    q=_norm(question);state=dict(admin_state or {});paper=dict(paper_summary or {})
    system=str(state.get("system_state","UNKNOWN")).upper()
    release=str(state.get("release_state","NOT_READY")).upper()
    reasons=_join(state.get("health_reasons"),3) or "nenhum motivo consolidado disponível"
    intent="HELP";answer=(
        "Posso te atualizar sobre o estado do sistema, o que mudou, macro, Radar, Paper e release."
    )
    if any(k in q for k in ("sistema","health","protegido","protecao","proteção","bloqueado","erro")):
        intent="SYSTEM"
        allowed=state.get("new_entries_allowed") is True
        answer=f"O sistema está {system}. Motivo: {reasons}. "
        answer+=("Novas entradas estão permitidas pelos controles atuais." if allowed else "Novas entradas não estão autorizadas pelos controles atuais.")
    elif any(k in q for k in ("mudou","mudanca","mudança","desde ontem","desde meu ultimo","desde meu último")):
        intent="CHANGES";items=_join(changes,6)
        answer="Desde o último acesso registrado: "+items+"." if items else "Ainda não há um histórico confiável de mudanças desde o seu último acesso."
    elif any(k in q for k in ("macro","fed","dolar","dólar","euro","moeda")):
        intent="MACRO";items=_join(macro_summary,5)
        answer="Resumo macro disponível: "+items+"." if items else "Ainda não há resumo macro consolidado disponível para eu narrar."
    elif any(k in q for k in ("radar","oportunidade","oportunidades","sinal","sinais")):
        intent="RADAR";rows=[]
        for x in opportunities or []:
            r=dict(x or {});pair=str(r.get("pair","")).strip()
            if not pair:continue
            status=str(r.get("operational_status",r.get("status","OBSERVANDO")))
            rows.append(f"{pair}: {status}")
            if len(rows)>=5:break
        answer="Radar: "+"; ".join(rows)+"." if rows else "O Radar ainda não forneceu oportunidades consolidadas para esta conversa."
    elif "paper" in q or "simulado" in q:
        intent="PAPER"
        if paper:
            state_p=str(paper.get("state","UNKNOWN")).upper()
            active=paper.get("active_count",paper.get("paper_trades","N/D"))
            answer=f"O Paper está {state_p}. Registros ativos ou acompanhados: {active}."
            if paper.get("management_mode"):answer+=f" Modo de gerenciamento: {paper.get('management_mode')}."
        else:
            answer="Ainda não há resumo Paper autoritativo disponível para esta conversa."
    elif any(k in q for k in ("release","versao","versão","rc","publicar","producao","produção")):
        intent="RELEASE"
        answer=f"O estado de release é {release.replace('_',' ')}. A voz do administrador não promove produção e não habilita ordens reais."
    return {"intent":intent,"answer":answer,"system_state":system,"release_state":release,
            "voice_can_authorize_orders":False,"real_orders_enabled":False,"source_of_truth":"ADMIN_CONTEXT_ONLY"}
