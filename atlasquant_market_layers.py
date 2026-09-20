"""AtlasQuant four-layer market context.

Research/presentation layer only:
- Macro
- Geopolitics
- Micro/Fundamentals
- Technical/Flow

It consumes state already computed by AtlasQuant. It never fetches providers,
changes Score Mestre, changes gates/weights, promotes setups, or sends orders.
Missing evidence is shown as UNAVAILABLE instead of being silently converted to
neutral confidence.
"""
from __future__ import annotations

from html import escape
import math
import re
import unicodedata
from typing import Any, Mapping, Sequence

import streamlit as st

from atlasquant_layer_consensus import build_layer_consensus
from atlasquant_macro_engine import build_structured_macro
from atlasquant_geopolitical_engine import build_geopolitical_context

SCHEMA="ATLASQUANT_MARKET_LAYERS_V1"
LAYER_ORDER=("macro","geopolitics","micro","technical_flow")
RESEARCH_WEIGHTS={
    "macro":0.35,
    "geopolitics":0.15,
    "micro":0.20,
    "technical_flow":0.30,
}


def _finite(value:Any,default:float=0.0)->float:
    try:
        x=float(value)
        return x if math.isfinite(x) else float(default)
    except Exception:
        return float(default)


def _clip(value:Any,lo:float=-100.0,hi:float=100.0)->float:
    return max(lo,min(hi,_finite(value)))


def _norm(value:object)->str:
    raw=unicodedata.normalize("NFKD",str(value or ""))
    return "".join(ch for ch in raw if not unicodedata.combining(ch)).casefold()


def _pair(value:object)->tuple[str,str]:
    raw=str(value or "").upper().replace("-","/").strip()
    if "/" not in raw:
        return "",""
    base,quote=raw.split("/",1)
    return base.strip(),quote.strip()


def _direction(balance:float,deadband:float=12.0)->str:
    x=_finite(balance)
    if x>=deadband:
        return "COMPRA"
    if x<=-deadband:
        return "VENDA"
    return "NEUTRO"


def _layer(
    layer_id:str,
    label:str,
    *,
    available:bool,
    balance:float=0.0,
    quality:float=0.0,
    reasons:Sequence[object]|None=None,
    risks:Sequence[object]|None=None,
    detail:str="",
)->dict[str,Any]:
    ok=bool(available)
    bal=_clip(balance) if ok else 0.0
    qual=max(0.0,min(100.0,_finite(quality))) if ok else 0.0
    return {
        "id":layer_id,
        "label":label,
        "available":ok,
        "balance":round(bal,1),
        "direction":_direction(bal) if ok else "INDISPONÍVEL",
        "quality":round(qual,1),
        "reasons":[str(x) for x in list(reasons or []) if str(x).strip()][:8],
        "risks":[str(x) for x in list(risks or []) if str(x).strip()][:8],
        "detail":str(detail or ""),
        "probability":False,
        "decision_effect":False,
    }


def macro_layer(
    pack:Mapping[str,Any]|None,
    *,
    macro_context:Mapping[str,Any]|None=None,
)->dict[str,Any]:
    p=dict(pack or {})
    m=dict(macro_context or {})
    pair=str(p.get("pair") or "—")
    base,quote=_pair(pair)
    if not base or not quote:
        return _layer("macro","Macro",available=False,detail="Par inválido ou ausente.")

    diff=_finite(p.get("macro_diff",p.get("strength_diff",0)))
    data=p.get("data_ready")
    data_score=_finite((data or {}).get("score",0)) if isinstance(data,Mapping) else _finite(p.get("data_score",0))
    pair_quality=max(_finite(p.get("quality",0)),data_score,_finite(m.get("usd_quality",0)))

    engine=build_structured_macro(
        pair,
        m,
        legacy_balance=_clip(diff*4.0),
        legacy_quality=pair_quality,
    )
    reasons=list(engine.get("reasons",[]) or [])
    risks=list(engine.get("risks",[]) or [])

    if not reasons:
        if abs(diff)>0.01:
            stronger=base if diff>0 else quote
            weaker=quote if diff>0 else base
            reasons.append(f"{stronger} está {abs(diff):.1f} pts acima de {weaker} na força macro relativa.")
        else:
            reasons.append("Diferença macro relativa sem vantagem clara no estado atual.")

    fed=dict(m.get("fed",{}) or {})
    fed_tone=str(fed.get("tom",m.get("fed_tone","")) or "").strip()
    fed_strength=_finite(fed.get("forca",m.get("fed_strength",0)))
    if "USD" in {base,quote} and fed_tone and not any("fed" in _norm(x) for x in reasons):
        reasons.append(f"Fed: {fed_tone} · intensidade {fed_strength:+.2f}.")

    event=m.get("event")
    if isinstance(event,Mapping) and event.get("disponivel") and not any("proximo evento" in _norm(x) for x in risks):
        name=str(event.get("evento") or "evento macro")
        impact=str(event.get("impacto") or "")
        risks.append(f"Próximo evento: {name}{' · '+impact if impact else ''}.")

    out=_layer(
        "macro","Macro",
        available=bool(engine.get("available",False)),
        balance=_finite(engine.get("balance",0)),
        quality=_finite(engine.get("quality",0)),
        reasons=reasons,
        risks=risks,
        detail=(
            f"Motor macro {engine.get('mode','insufficient')} · cobertura "
            f"{_finite(engine.get('coverage',0)):.0f}% · juros, inflação, emprego, "
            "crescimento/atividade, expectativas/surpresas e bancos centrais. Não é probabilidade."
        ),
    )
    out["engine_mode"]=str(engine.get("mode") or "insufficient")
    out["coverage"]=round(_finite(engine.get("coverage",0)),1)
    out["macro_conflict"]=bool(engine.get("macro_conflict",False))
    out["groups"]=list(engine.get("groups",[]) or [])
    return out

def geopolitical_layer(
    pair:object,
    news_state:Mapping[str,Any]|None,
)->dict[str,Any]:
    engine=build_geopolitical_context(pair,news_state)
    out=_layer(
        "geopolitics","Geopolítica",
        available=bool(engine.get("available",False)),
        balance=_finite(engine.get("balance",0)),
        quality=_finite(engine.get("quality",0)),
        reasons=list(engine.get("reasons",[]) or []),
        risks=list(engine.get("risks",[]) or []),
        detail=(
            f"Motor geopolítico estruturado · {int(engine.get('independent_stories',0) or 0)} história(s) independente(s) · "
            f"regime {engine.get('risk_regime','INDISPONÍVEL')} · severidade {engine.get('severity','N/D')} · "
            f"cobertura {_finite(engine.get('coverage',0)):.0f}%. Não é previsão política nem probabilidade."
        ),
    )
    out["coverage"]=round(_finite(engine.get("coverage",0)),1)
    out["event_count"]=int(engine.get("event_count",0) or 0)
    out["independent_stories"]=int(engine.get("independent_stories",0) or 0)
    out["source_count"]=int(engine.get("source_count",0) or 0)
    out["risk_regime"]=str(engine.get("risk_regime") or "INDISPONÍVEL")
    out["severity"]=str(engine.get("severity") or "N/D")
    out["geo_conflict"]=bool(engine.get("geo_conflict",False))
    out["channels"]=list(engine.get("channels",[]) or [])
    out["regions"]=list(engine.get("regions",[]) or [])
    out["countries"]=list(engine.get("countries",[]) or [])
    out["commodities"]=list(engine.get("commodities",[]) or [])
    out["events"]=list(engine.get("events",[]) or [])
    return out

def micro_fundamentals_layer(
    pair:object,
    micro_state:Mapping[str,Any]|None,
)->dict[str,Any]:
    """Aggregate explicit constituent/sector/company evidence.

    For Forex, missing company/sector inputs are deliberately unavailable. Future
    WIN/indices engines can feed real constituent contributions here.
    """
    p=str(pair or "").upper()
    state=dict(micro_state or {})
    raw=state.get(p)
    if raw is None:
        raw=state.get("default")
    if not isinstance(raw,Mapping):
        return _layer(
            "micro","Micro / Fundamentos",
            available=False,
            detail="Sem dados micro/empresas específicos para este ativo. O AtlasQuant não inventa uma camada micro para Forex.",
        )

    components=[dict(x) for x in list(raw.get("components",[]) or []) if isinstance(x,Mapping)]
    if not components and "balance" not in raw:
        return _layer(
            "micro","Micro / Fundamentos",
            available=False,
            detail="Contrato micro presente, mas sem componentes válidos.",
        )

    weighted=0.0
    denom=0.0
    reasons=[]
    risks=[]
    for item in components:
        impact=_clip(item.get("impact",0))
        quality=max(0.0,min(100.0,_finite(item.get("quality",50),50)))
        weight=max(0.0,_finite(item.get("weight",1.0),1.0))
        if weight<=0:
            continue
        effective=weight*(0.35+0.65*quality/100.0)
        weighted+=impact*effective
        denom+=effective
        name=str(item.get("name") or "Componente")
        reason=str(item.get("reason") or "").strip()
        reasons.append(f"{name}: {impact:+.0f}{' · '+reason if reason else ''}.")
    if denom>0:
        balance=weighted/denom
    else:
        balance=_clip(raw.get("balance",0))
    if components:
        quality=sum(max(0.0,min(100.0,_finite(x.get("quality",50),50))) for x in components)/len(components)
    else:
        quality=max(0.0,min(100.0,_finite(raw.get("quality",0))))
    for risk in list(raw.get("risks",[]) or []):
        if str(risk).strip():
            risks.append(str(risk))
    return _layer(
        "micro","Micro / Fundamentos",
        available=True,
        balance=balance,
        quality=quality,
        reasons=reasons,
        risks=risks,
        detail=str(raw.get("detail") or "Contribuições explícitas de empresas/setores/componentes do ativo."),
    )


def _status_vote(value:object)->float:
    t=_norm(value)
    if not t or t in {"n/d","—","nao disponivel"}:
        return 0.0
    buy=("compra","bull","altista","higher high","confirma buy")
    sell=("venda","bear","baixista","lower low","confirma sell")
    b=any(x in t for x in buy)
    s=any(x in t for x in sell)
    if b and not s:
        return 1.0
    if s and not b:
        return -1.0
    return 0.0


def technical_flow_layer(pack:Mapping[str,Any]|None)->dict[str,Any]:
    p=dict(pack or {})
    if not p:
        return _layer("technical_flow","Técnico / Fluxo",available=False,detail="Pack técnico ausente.")

    raw_ready=p.get("data_ready")
    if isinstance(raw_ready,Mapping):
        sufficient=bool(raw_ready.get("sufficient",False))
        data_score=_finite(raw_ready.get("score",0))
    else:
        sufficient=bool(raw_ready)
        data_score=_finite(p.get("data_score",0))

    tfs=(("H4",p.get("h4")),("H1",p.get("h1")),("M15",p.get("m15")))
    votes=[_status_vote(v) for _,v in tfs]
    known=sum(1 for _,v in tfs if _norm(v) not in {"","—","n/d","nao disponivel"})
    reasons=[f"{tf}: {str(value or 'N/D')}." for tf,value in tfs]
    risks=[str(x) for x in list(p.get("hard_blocks",[]) or []) if str(x).strip()]
    risks.extend(str(x) for x in list(p.get("soft_blocks",[]) or []) if str(x).strip())
    gate=str(p.get("gate") or "—")

    if not sufficient or data_score<=0 or known==0:
        if not sufficient:
            risks.insert(0,"Dados técnicos insuficientes/stale; camada não pode confirmar direção.")
        return _layer(
            "technical_flow","Técnico / Fluxo",
            available=False,
            reasons=reasons,
            risks=risks,
            detail="Dados insuficientes falham fechado; não são convertidos em neutralidade confiável.",
        )

    vote_balance=(sum(votes)/max(1,len(votes)))*65.0
    side=str(p.get("side") or "").upper()
    directional=1.0 if side=="BUY" else -1.0 if side=="SELL" else 0.0
    ict=_finite(p.get("ict_read",0))
    inst=_finite(p.get("inst_read",0))
    readiness_support=((ict+inst)/200.0)*23.0*directional

    quarterly=dict(p.get("quarterly",{}) or {})
    q_support=0.0
    if quarterly.get("available"):
        qdir=str(quarterly.get("direction") or "NEUTRO")
        qvote=1.0 if qdir=="COMPRA" else -1.0 if qdir=="VENDA" else 0.0
        qquality=max(0.0,min(100.0,_finite(quarterly.get("quality",0))))
        q_support=12.0*qvote*(qquality/100.0)
        reasons.append(
            f"Quarterly {quarterly.get('quarter_label','—')}: "
            f"{quarterly.get('event','SEM EVENTO')} · {qdir}."
        )
        if str(quarterly.get("side_alignment"))=="CONTRÁRIO":
            risks.append("Quarterly atual está contrário ao lado macro; observação de pesquisa, sem veto operacional.")
        if quarterly.get("phase_hint"):
            reasons.append(
                f"Fase temporal: {quarterly.get('phase_hint')} (rótulo educacional, não preditivo)."
            )
    else:
        reasons.append("Quarterly: sem evidência temporal suficiente.")

    intermarket=dict(p.get("intermarket",{}) or {})
    im_support=0.0
    if intermarket.get("available"):
        im_balance=_finite(intermarket.get("balance",0))
        im_quality=max(0.0,min(100.0,_finite(intermarket.get("quality",0))))
        im_support=0.15*im_balance*(im_quality/100.0)
        for reason in list(intermarket.get("reasons",[]) or [])[:3]:
            reasons.append("Intermarket: "+str(reason))
        if str(intermarket.get("direction")) not in {"NEUTRO","INDISPONÍVEL"}:
            expected="COMPRA" if side=="BUY" else "VENDA" if side=="SELL" else "NEUTRO"
            if expected!="NEUTRO" and str(intermarket.get("direction"))!=expected:
                risks.append("Intermarket diverge do lado macro; não altera o Gate nesta fase de pesquisa.")
    else:
        reasons.append("Intermarket: aguardando pelo menos dois grupos independentes atuais.")

    inst_map=dict(p.get("inst",{}) or {})
    for key,label in (
        ("structure","BOS/CHOCH"),("order_block","Order Block"),
        ("liquidity","Draw on Liquidity"),("session","Sessão/Judas"),
        ("displacement","Displacement"),("mss","MSS"),("smt","SMT"),
        ("dealing_range","Premium/Discount"),("pd_array","Breaker/Mitigation"),
    ):
        comp=dict(inst_map.get(key,{}) or {})
        status=str(comp.get("status") or "").strip()
        if status:
            reasons.append(f"{label}: {status}.")

    balance=_clip(vote_balance+readiness_support+q_support+im_support)

    if ict>0:
        reasons.append(f"ICT readiness {ict:.0f}/100.")
    if inst>0:
        reasons.append(f"Fluxo institucional {inst:.0f}/100.")
    reasons.append(f"Gate {gate}.")
    quality=min(100.0,0.65*data_score+0.35*_finite(p.get("quality",data_score),data_score))
    if risks:
        quality*=0.80
    return _layer(
        "technical_flow","Técnico / Fluxo",
        available=True,
        balance=balance,
        quality=quality,
        reasons=reasons,
        risks=risks,
        detail=(
            "Top-down + ICT/SMC + estrutura/liquidez/sessão + Quarterly e "
            "intermarket quando houver evidência independente. Camada observacional."
        ),
    )

def build_market_layers(
    pack:Mapping[str,Any]|None,
    *,
    news_state:Mapping[str,Any]|None=None,
    macro_context:Mapping[str,Any]|None=None,
    micro_state:Mapping[str,Any]|None=None,
)->dict[str,Any]:
    p=dict(pack or {})
    pair=str(p.get("pair") or "—")
    layers=[
        macro_layer(p,macro_context=macro_context),
        geopolitical_layer(pair,news_state),
        micro_fundamentals_layer(pair,micro_state),
        technical_flow_layer(p),
    ]
    available=[x for x in layers if x["available"]]
    weighted=0.0
    denom=0.0
    for layer in available:
        w=RESEARCH_WEIGHTS.get(layer["id"],0.0)
        effective=w*(0.25+0.75*layer["quality"]/100.0)
        weighted+=layer["balance"]*effective
        denom+=effective
    balance=weighted/denom if denom>0 else 0.0
    min_quality=min((x["quality"] for x in available),default=0.0)
    output={
        "schema":SCHEMA,
        "pair":pair,
        "layers":layers,
        "available_layers":len(available),
        "missing_layers":[x["id"] for x in layers if not x["available"]],
        "research_balance":round(_clip(balance),1),
        "research_direction":_direction(balance) if available else "INDISPONÍVEL",
        "evidence_floor":round(min_quality,1),
        "weights":dict(RESEARCH_WEIGHTS),
        "probability":False,
        "changes_score_mestre":False,
        "changes_gate":False,
        "changes_weights":False,
        "real_orders_enabled":False,
        "automatic_execution":False,
    }
    output["consensus"]=build_layer_consensus(output)
    return output

def beginner_layer_summary(result:Mapping[str,Any]|None)->str:
    r=dict(result or {})
    layers=list(r.get("layers",[]) or [])
    available=[x for x in layers if x.get("available")]
    if not available:
        return "Camadas adicionais ainda sem evidência suficiente."
    positive=[x["label"] for x in available if x.get("direction")=="COMPRA"]
    negative=[x["label"] for x in available if x.get("direction")=="VENDA"]
    if positive and not negative:
        return "As camadas disponíveis estão majoritariamente favoráveis à alta."
    if negative and not positive:
        return "As camadas disponíveis estão majoritariamente favoráveis à baixa."
    if positive and negative:
        return "As camadas estão divididas; há fatores a favor e contra."
    return "As camadas disponíveis não mostram vantagem adicional clara."


def render_market_layers_panel(
    pack:Mapping[str,Any],
    *,
    news_state:Mapping[str,Any]|None=None,
    macro_context:Mapping[str,Any]|None=None,
    micro_state:Mapping[str,Any]|None=None,
)->dict[str,Any]:
    result=build_market_layers(
        pack,
        news_state=news_state,
        macro_context=macro_context,
        micro_state=micro_state,
    )
    st.markdown("### 🧩 Quatro camadas do contexto")
    st.caption(
        "Macro · Geopolítica · Micro/Fundamentos · Técnico/Fluxo. "
        "Saldo de pesquisa, não probabilidade e não altera o motor operacional."
    )
    cols=st.columns(4)
    for col,layer in zip(cols,result["layers"]):
        with col:
            if layer["available"]:
                icon="🟢" if layer["direction"]=="COMPRA" else "🔴" if layer["direction"]=="VENDA" else "⚪"
                st.metric(layer["label"],f"{icon} {layer['direction']}",f"{layer['balance']:+.0f} saldo")
                st.caption(f"Qualidade da evidência {layer['quality']:.0f}/100")
            else:
                st.metric(layer["label"],"SEM EVIDÊNCIA")
                st.caption(layer["detail"])
    with st.expander("Ver por dentro das quatro camadas",expanded=False):
        for layer in result["layers"]:
            st.markdown(f"**{layer['label']} — {layer['direction']}**")
            if layer["reasons"]:
                for reason in layer["reasons"][:5]:
                    st.write("• "+reason)
            if layer["risks"]:
                st.caption("Riscos/limitações: "+" · ".join(layer["risks"][:4]))
            if layer["detail"]:
                st.caption(layer["detail"])
            st.divider()
    consensus=dict(result.get("consensus",{}) or {})
    state=str(consensus.get("research_state","AGUARDAR"))
    blockers=list(consensus.get("blockers",[]) or [])
    st.info(
        f"Consenso de pesquisa: {state} · saldo {result['research_balance']:+.1f} · "
        f"{result['available_layers']}/4 camadas disponíveis · "
        f"concordância {_finite(consensus.get('agreement_pct',0)):.0f}%. "
        "Não entra no Score Mestre enquanto não for validado."
    )
    if blockers:
        st.warning("Bloqueios do consenso: "+" · ".join(str(x) for x in blockers[:3]))
    return result


__all__=[
    "SCHEMA","LAYER_ORDER","RESEARCH_WEIGHTS","macro_layer","geopolitical_layer",
    "micro_fundamentals_layer","technical_flow_layer","build_market_layers",
    "beginner_layer_summary","render_market_layers_panel",
]