"""AtlasQuant Technical Coverage Budget Planner V1.

Estimates an upper-bound daily Twelve Data call demand from the existing
Autopilot cadences. It is a planning tool only: it does not make API calls,
change cadence, expand PAIR_ORDER, or alter production behavior.
"""
from __future__ import annotations

from math import ceil
import math
from typing import Any
import streamlit as st


DEFAULTS={
    "market_minutes":1440,
    "priority_m15_min":25,
    "priority_h1_min":55,
    "normal_m15_min":55,
    "normal_h1_min":115,
    "h4_min":235,
    "d1_calls_per_pair":1,
    "daily_cap":480,
}


def _safe_int(value: Any, default: int = 0) -> tuple[int,bool]:
    if isinstance(value,bool): return default,False
    try:
        x=float(value)
        if not math.isfinite(x) or not x.is_integer(): return default,False
        return int(x),True
    except Exception: return default,False

def _calls_per_day(cadence_min: int, market_minutes: int) -> int:
    cadence,ok1=_safe_int(cadence_min)
    minutes,ok2=_safe_int(market_minutes)
    if not ok1 or not ok2 or cadence<=0 or minutes<0: return 0
    return 0 if minutes==0 else int(ceil(minutes/cadence))


def estimate_daily_calls(
    *,
    pair_count: int,
    priority_count: int = 3,
    market_minutes: int = DEFAULTS["market_minutes"],
    priority_m15_min: int = DEFAULTS["priority_m15_min"],
    priority_h1_min: int = DEFAULTS["priority_h1_min"],
    normal_m15_min: int = DEFAULTS["normal_m15_min"],
    normal_h1_min: int = DEFAULTS["normal_h1_min"],
    h4_min: int = DEFAULTS["h4_min"],
    d1_calls_per_pair: int = DEFAULTS["d1_calls_per_pair"],
    daily_cap: int = DEFAULTS["daily_cap"],
) -> dict[str, Any]:
    raw=(pair_count,priority_count,market_minutes,priority_m15_min,priority_h1_min,normal_m15_min,normal_h1_min,h4_min,d1_calls_per_pair,daily_cap)
    parsed=[_safe_int(x) for x in raw]
    inputs_valid=all(ok for _,ok in parsed)
    pairs=max(0,parsed[0][0]); priority=max(0,min(parsed[1][0],pairs))
    normal=pairs-priority

    priority_per_pair=(
        _calls_per_day(priority_m15_min,market_minutes)
        +_calls_per_day(priority_h1_min,market_minutes)
        +_calls_per_day(h4_min,market_minutes)
        +max(0,parsed[8][0])
    )
    normal_per_pair=(
        _calls_per_day(normal_m15_min,market_minutes)
        +_calls_per_day(normal_h1_min,market_minutes)
        +_calls_per_day(h4_min,market_minutes)
        +max(0,parsed[8][0])
    )
    total=priority*priority_per_pair+normal*normal_per_pair
    cap=max(1,parsed[9][0])
    ratio=total/cap
    return {
        "inputs_valid":bool(inputs_valid and pairs>=0 and parsed[1][0]>=0 and parsed[2][0]>=0 and all(v>0 for v in (parsed[3][0],parsed[4][0],parsed[5][0],parsed[6][0],parsed[7][0])) and parsed[8][0]>=0 and parsed[9][0]>0),
        "pair_count":pairs,
        "priority_count":priority,
        "normal_count":normal,
        "priority_calls_per_pair":priority_per_pair,
        "normal_calls_per_pair":normal_per_pair,
        "estimated_daily_calls":total,
        "daily_cap":cap,
        "cap_usage_pct":round(ratio*100.0,1),
        "within_cap":bool(inputs_valid and pairs>=0 and parsed[1][0]>=0 and parsed[2][0]>=0 and all(v>0 for v in (parsed[3][0],parsed[4][0],parsed[5][0],parsed[6][0],parsed[7][0])) and parsed[8][0]>=0 and parsed[9][0]>0 and total<=cap),
        "excess_calls":max(0,total-cap),
        "headroom_calls":max(0,cap-total),
    }


def max_supported_pairs(
    *,
    priority_count: int = 3,
    daily_cap: int = DEFAULTS["daily_cap"],
    **kwargs,
) -> int:
    cap=max(1,int(daily_cap))
    # Search is intentionally bounded well above the 28-pair G8 universe.
    last=0
    for pairs in range(0,101):
        est=estimate_daily_calls(
            pair_count=pairs,
            priority_count=min(priority_count,pairs),
            daily_cap=cap,
            **kwargs,
        )
        if est["within_cap"]:
            last=pairs
        else:
            break
    return last


def expansion_plan(
    current_pairs: int = 7,
    target_pairs: int = 28,
    *,
    priority_count: int = 3,
    daily_cap: int = DEFAULTS["daily_cap"],
) -> dict[str, Any]:
    current=estimate_daily_calls(
        pair_count=current_pairs,priority_count=priority_count,daily_cap=daily_cap
    )
    target=estimate_daily_calls(
        pair_count=target_pairs,priority_count=priority_count,daily_cap=daily_cap
    )
    max_pairs=max_supported_pairs(priority_count=priority_count,daily_cap=daily_cap)
    return {
        "current":current,
        "target":target,
        "max_pairs_same_cadence":max_pairs,
        "target_requires_change":not target["within_cap"],
        "estimated_multiplier":round(
            target["estimated_daily_calls"]/max(1,current["estimated_daily_calls"]),2
        ),
    }


def render_expansion_budget_planner(
    current_pairs: int = 7,
    target_pairs: int = 28,
    *,
    daily_cap: int = DEFAULTS["daily_cap"],
) -> dict[str, Any]:
    plan=expansion_plan(
        current_pairs=current_pairs,target_pairs=target_pairs,daily_cap=daily_cap
    )
    cur=plan["current"]; tgt=plan["target"]

    st.markdown("### 🧮 Planejador de expansão técnica — Twelve Data")
    st.caption(
        "Estimativa de teto por cadência, sem fazer chamadas reais. Serve para evitar "
        "expandir o pipeline técnico além do orçamento diário."
    )
    c1,c2,c3,c4=st.columns(4)
    c1.metric("Pipeline atual",f"{cur['pair_count']} pares")
    c2.metric("Teto estimado atual",f"{cur['estimated_daily_calls']} chamadas/dia")
    c3.metric("Meta técnica",f"{tgt['pair_count']} pares")
    c4.metric("Teto estimado da meta",f"{tgt['estimated_daily_calls']} chamadas/dia")

    if plan["target_requires_change"]:
        st.warning(
            f"Com as cadências atuais, {target_pairs} pares excederiam o cap de {daily_cap}/dia "
            f"em aproximadamente {tgt['excess_calls']} chamadas no teto teórico. "
            "A expansão deve mudar cadência, fonte, cache, orçamento ou cobertura técnica."
        )
    else:
        st.success("A meta cabe no orçamento teórico atual.")

    st.caption(
        f"Máximo teórico com a mesma cadência e cap: {plan['max_pairs_same_cadence']} pares. "
        "O consumo real pode ser menor por cache, mercado fechado e agendamento; este cálculo é conservador."
    )
    st.caption("Este painel não altera PAIR_ORDER, cadências, quota nem comportamento do Autopilot.")
    return plan
