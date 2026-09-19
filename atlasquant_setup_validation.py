"""AtlasQuant private setup-validation registry.

Research-only framework for the 30–60 day private validation phase. It evaluates
whether a setup has enough *evidence for human review*. It never recommends a
setup, promotes it to Beginner mode, changes gates/weights, connects a broker,
or enables real orders.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
import math
from typing import Any, Mapping, Sequence

import pandas as pd
import streamlit as st

SCHEMA="ATLASQUANT_SETUP_VALIDATION_V1"

VALID_STATES=(
    "PESQUISA",
    "BACKTEST",
    "FORWARD/PAPER",
    "CANDIDATO",
    "APROVADO PARA REVISÃO",
    "REJEITADO/REVER",
)

SETUP_CATALOG=(
    {
        "id":"fvg",
        "name":"FVG / desequilíbrio",
        "family":"ICT/SMC",
        "complexity":"INICIANTE_CANDIDATO",
        "status":"BACKTEST",
        "notes":"Já possui replay/backtest; precisa acumular evidência privada comparável.",
    },
    {
        "id":"ote",
        "name":"OTE / Fibonacci",
        "family":"ICT/SMC",
        "complexity":"INICIANTE_CANDIDATO",
        "status":"BACKTEST",
        "notes":"Validar regras objetivas e estabilidade; níveis não devem ser escolhidos por resultado posterior.",
    },
    {
        "id":"crt",
        "name":"CRT",
        "family":"ICT/SMC",
        "complexity":"AVANÇADO",
        "status":"BACKTEST",
        "notes":"Manter separação por sessão/regime e sem promoção automática.",
    },
    {
        "id":"amd-po3",
        "name":"AMD / PO3",
        "family":"ICT/SMC",
        "complexity":"AVANÇADO",
        "status":"BACKTEST",
        "notes":"Avaliar estabilidade temporal e sensibilidade à definição de sessão.",
    },
    {
        "id":"session-liquidity-mss",
        "name":"Liquidez de sessão + MSS",
        "family":"Sessões",
        "complexity":"INICIANTE_CANDIDATO",
        "status":"PESQUISA",
        "notes":"Candidato simples: varredura de liquidez + mudança estrutural + confirmação.",
    },
    {
        "id":"opening-range",
        "name":"Opening Range",
        "family":"Sessões",
        "complexity":"INICIANTE_CANDIDATO",
        "status":"PESQUISA",
        "notes":"Definir janela/fuso antes de backtest; não otimizar horário olhando o resultado.",
    },
    {
        "id":"volume-profile",
        "name":"Volume Profile",
        "family":"Volume",
        "complexity":"AVANÇADO",
        "status":"PESQUISA",
        "notes":"Bloqueado para promoção até documentar fonte/metodologia; spot FX não tem volume centralizado.",
    },
)


@dataclass(frozen=True)
class ReviewThresholds:
    min_backtest_samples:int=100
    min_forward_samples:int=30
    min_regimes:int=2
    min_sessions:int=2
    min_expectancy_r:float=0.0
    min_profit_factor:float=1.0
    max_drawdown_r:float=12.0
    max_backtest_forward_gap_r:float=0.20
    min_positive_fold_pct:float=66.0
    min_oos_positive_pct:float=60.0
    min_friction_positive_pct:float=60.0
    min_parameter_positive_pct:float=60.0


def setup_catalog()->list[dict[str,Any]]:
    return [dict(x) for x in SETUP_CATALOG]


def _finite(value:Any)->float|None:
    try:
        x=float(value)
        return x if math.isfinite(x) else None
    except Exception:
        return None


def _nonnegative_int(value:Any)->int|None:
    if isinstance(value,bool):
        return None
    x=_finite(value)
    if x is None or x<0 or not float(x).is_integer():
        return None
    return int(x)


def _pct(value:Any)->float|None:
    x=_finite(value)
    if x is None or x<0 or x>100:
        return None
    return x


def normalize_evidence(evidence:Mapping[str,Any]|None)->dict[str,Any]:
    e=dict(evidence or {})
    regimes=e.get("regimes",[])
    sessions=e.get("sessions",[])
    if not isinstance(regimes,(list,tuple,set)):
        regimes=[]
    if not isinstance(sessions,(list,tuple,set)):
        sessions=[]
    return {
        "backtest_samples":_nonnegative_int(e.get("backtest_samples",e.get("trades"))),
        "forward_samples":_nonnegative_int(e.get("forward_samples")),
        "expectancy_r":_finite(e.get("expectancy_r")),
        "forward_expectancy_r":_finite(e.get("forward_expectancy_r")),
        "profit_factor":_finite(e.get("profit_factor")),
        "max_drawdown_r":_finite(e.get("max_drawdown_r")),
        "positive_fold_pct":_pct(e.get("positive_fold_pct")),
        "oos_positive_pct":_pct(e.get("oos_positive_pct")),
        "friction_positive_pct":_pct(e.get("friction_positive_pct")),
        "parameter_positive_pct":_pct(e.get("parameter_positive_pct")),
        "regimes":sorted({str(x).strip() for x in regimes if str(x).strip()}),
        "sessions":sorted({str(x).strip() for x in sessions if str(x).strip()}),
        "source_methodology_verified":bool(e.get("source_methodology_verified",False)),
        "rules_frozen_before_evaluation":bool(e.get("rules_frozen_before_evaluation",False)),
    }


def evaluate_setup_for_review(
    setup_id:object,
    evidence:Mapping[str,Any]|None,
    *,
    thresholds:ReviewThresholds|None=None,
)->dict[str,Any]:
    key=str(setup_id or "").strip().casefold()
    setup=next((dict(x) for x in SETUP_CATALOG if x["id"].casefold()==key),None)
    t=thresholds or ReviewThresholds()
    ev=normalize_evidence(evidence)

    blockers=[]
    pending=[]
    if setup is None:
        blockers.append("Setup não cadastrado")
        status="REJEITADO/REVER"
    else:
        status=str(setup["status"])

    numeric_required=(
        "backtest_samples","forward_samples","expectancy_r","forward_expectancy_r",
        "profit_factor","max_drawdown_r","positive_fold_pct","oos_positive_pct",
        "friction_positive_pct","parameter_positive_pct",
    )
    invalid=[k for k in numeric_required if ev.get(k) is None]
    if invalid:
        pending.append("Evidência numérica incompleta: "+", ".join(invalid))

    if not ev["rules_frozen_before_evaluation"]:
        blockers.append("Regras do setup não estavam congeladas antes da avaliação")

    if setup and setup["id"]=="volume-profile" and not ev["source_methodology_verified"]:
        blockers.append("Volume Profile exige fonte/metodologia de volume documentada")

    bt=ev["backtest_samples"]
    fw=ev["forward_samples"]
    if bt is not None and bt<t.min_backtest_samples:
        pending.append(f"Backtest: {bt}/{t.min_backtest_samples} amostras")
    if fw is not None and fw<t.min_forward_samples:
        pending.append(f"Forward/Paper: {fw}/{t.min_forward_samples} amostras")
    if len(ev["regimes"])<t.min_regimes:
        pending.append(f"Regimes: {len(ev['regimes'])}/{t.min_regimes}")
    if len(ev["sessions"])<t.min_sessions:
        pending.append(f"Sessões: {len(ev['sessions'])}/{t.min_sessions}")

    exp=ev["expectancy_r"]
    fexp=ev["forward_expectancy_r"]
    pf=ev["profit_factor"]
    dd=ev["max_drawdown_r"]
    if exp is not None and exp<=t.min_expectancy_r:
        blockers.append("Expectativa observada do backtest não é positiva")
    if fexp is not None and fexp<=t.min_expectancy_r:
        blockers.append("Expectativa observada no Forward/Paper não é positiva")
    if pf is not None and pf<t.min_profit_factor:
        blockers.append("Profit factor observado abaixo do mínimo de revisão")
    if dd is not None and (dd<0 or dd>t.max_drawdown_r):
        blockers.append("Drawdown observado fora do limite de revisão")
    if exp is not None and fexp is not None and abs(exp-fexp)>t.max_backtest_forward_gap_r:
        blockers.append("Diferença Backtest × Forward/Paper acima do limite de revisão")

    pct_checks=(
        ("positive_fold_pct",t.min_positive_fold_pct,"Estabilidade temporal"),
        ("oos_positive_pct",t.min_oos_positive_pct,"Walk-forward OOS"),
        ("friction_positive_pct",t.min_friction_positive_pct,"Robustez a custos/fricção"),
        ("parameter_positive_pct",t.min_parameter_positive_pct,"Robustez de parâmetros"),
    )
    for key_pct,minimum,label in pct_checks:
        value=ev[key_pct]
        if value is not None and value<minimum:
            blockers.append(f"{label} abaixo do mínimo de revisão")

    enough_numeric=not invalid
    enough_samples=bool(
        bt is not None and fw is not None
        and bt>=t.min_backtest_samples and fw>=t.min_forward_samples
        and len(ev["regimes"])>=t.min_regimes
        and len(ev["sessions"])>=t.min_sessions
    )
    beginner_candidate=bool(setup and setup["complexity"]=="INICIANTE_CANDIDATO")
    review_ready=bool(setup and enough_numeric and enough_samples and not blockers and not pending)
    beginner_review_ready=bool(review_ready and beginner_candidate)

    return {
        "schema":SCHEMA,
        "setup_id":key,
        "setup_name":str((setup or {}).get("name") or key or "N/D"),
        "catalog_status":status,
        "complexity":str((setup or {}).get("complexity") or "N/D"),
        "evidence":ev,
        "thresholds":asdict(t),
        "blockers":blockers,
        "pending":pending,
        "review_ready":review_ready,
        "beginner_review_ready":beginner_review_ready,
        "win_rate_alone_can_qualify":False,
        "manual_review_required":True,
        "automatic_beginner_promotion":False,
        "automatic_gate_change":False,
        "automatic_weight_change":False,
        "real_orders_enabled":False,
    }


def evaluate_catalog(
    evidence_by_setup:Mapping[str,Mapping[str,Any]]|None=None,
    *,
    thresholds:ReviewThresholds|None=None,
)->list[dict[str,Any]]:
    source=dict(evidence_by_setup or {})
    return [
        evaluate_setup_for_review(item["id"],source.get(item["id"],{}),thresholds=thresholds)
        for item in SETUP_CATALOG
    ]


def validation_frame(results:Sequence[Mapping[str,Any]]|None)->pd.DataFrame:
    rows=[]
    for raw in list(results or []):
        r=dict(raw or {})
        e=dict(r.get("evidence",{}) or {})
        rows.append({
            "Setup":r.get("setup_name"),
            "Estado catálogo":r.get("catalog_status"),
            "Perfil":r.get("complexity"),
            "Backtest":e.get("backtest_samples"),
            "Forward/Paper":e.get("forward_samples"),
            "Expectativa BT R":e.get("expectancy_r"),
            "Expectativa FW R":e.get("forward_expectancy_r"),
            "Profit Factor":e.get("profit_factor"),
            "Drawdown R":e.get("max_drawdown_r"),
            "Regimes":len(e.get("regimes",[]) or []),
            "Sessões":len(e.get("sessions",[]) or []),
            "Pronto p/ revisão":"SIM" if r.get("review_ready") else "NÃO",
            "Candidato iniciante":"SIM" if r.get("beginner_review_ready") else "NÃO",
        })
    return pd.DataFrame(rows)


def render_private_validation_center(
    evidence_by_setup:Mapping[str,Mapping[str,Any]]|None=None,
)->dict[str,Any]:
    results=evaluate_catalog(evidence_by_setup)
    ready=sum(1 for r in results if r["review_ready"])
    beginner=sum(1 for r in results if r["beginner_review_ready"])

    st.markdown("### 🧪 Validação Privada de Setups")
    st.caption(
        "Fase privada de 30–60 dias. O objetivo é acumular evidência suficiente para revisão humana, "
        "não procurar o setup com maior win rate e promovê-lo automaticamente."
    )
    c1,c2,c3,c4=st.columns(4)
    c1.metric("Setups no catálogo",len(results))
    c2.metric("Prontos p/ revisão",ready)
    c3.metric("Iniciante candidatos",beginner)
    c4.metric("Trading real","DESATIVADO")

    st.dataframe(validation_frame(results),width="stretch",hide_index=True)
    selected=st.selectbox(
        "Ver critérios de um setup",
        [r["setup_id"] for r in results],
        format_func=lambda x:next(r["setup_name"] for r in results if r["setup_id"]==x),
        key="aq_private_validation_setup",
    )
    result=next(r for r in results if r["setup_id"]==selected)
    if result["blockers"]:
        st.error("Bloqueios: "+" · ".join(result["blockers"]))
    if result["pending"]:
        st.warning("Pendências: "+" · ".join(result["pending"]))
    if not result["blockers"] and not result["pending"]:
        st.success("Critérios mínimos atingidos para REVISÃO HUMANA. Nenhuma promoção é automática.")

    st.info(
        "Taxa de acerto isolada nunca aprova um setup. A revisão considera amostra, expectativa, "
        "drawdown, estabilidade temporal, OOS, fricção, parâmetros, regimes e Forward/Paper."
    )
    return {
        "schema":SCHEMA,
        "setups":len(results),
        "review_ready":ready,
        "beginner_review_ready":beginner,
        "manual_review_required":True,
        "automatic_promotion":False,
        "real_orders_enabled":False,
    }


__all__=[
    "SCHEMA","VALID_STATES","SETUP_CATALOG","ReviewThresholds","setup_catalog",
    "normalize_evidence","evaluate_setup_for_review","evaluate_catalog",
    "validation_frame","render_private_validation_center",
]
