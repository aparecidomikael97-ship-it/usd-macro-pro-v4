"""AtlasQuant adaptive 28-pair coverage planner.

Research/planning only. It estimates a quota-safe architecture where all G8
pairs keep background technical context, while only a small active set receives
fresh execution-grade M15 updates. H1/H4 are intended to be derived from a
validated M15 cache before this policy can ever be wired into live collection.
"""
from __future__ import annotations

from math import ceil
import math
from typing import Any
import streamlit as st


DEFAULT_POLICY={
    "pair_count":28,
    "active_pairs":3,
    "market_minutes":1440,
    "active_m15_min":55,
    "background_m15_min":180,
    "daily_context_calls_per_pair":1,
    "daily_cap":480,
    "reserved_calls":80,
    "required_m15_history_bars":1000,
}


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        x=float(value)
        if not math.isfinite(x):
            return default
        return int(x)
    except Exception:
        return default


def _calls(cadence_min: int, market_minutes: int) -> int:
    cadence=_safe_int(cadence_min,0)
    minutes=_safe_int(market_minutes,0)
    if cadence <= 0 or minutes < 0:
        return 0
    return 0 if minutes==0 else int(ceil(minutes/cadence))


def adaptive_coverage_plan(
    *,
    pair_count: int = DEFAULT_POLICY["pair_count"],
    active_pairs: int = DEFAULT_POLICY["active_pairs"],
    market_minutes: int = DEFAULT_POLICY["market_minutes"],
    active_m15_min: int = DEFAULT_POLICY["active_m15_min"],
    background_m15_min: int = DEFAULT_POLICY["background_m15_min"],
    daily_context_calls_per_pair: int = DEFAULT_POLICY["daily_context_calls_per_pair"],
    daily_cap: int = DEFAULT_POLICY["daily_cap"],
    reserved_calls: int = DEFAULT_POLICY["reserved_calls"],
    required_m15_history_bars: int = DEFAULT_POLICY["required_m15_history_bars"],
) -> dict[str,Any]:
    raw_values=(pair_count,active_pairs,market_minutes,active_m15_min,background_m15_min,daily_context_calls_per_pair,daily_cap,reserved_calls,required_m15_history_bars)
    inputs_valid=True
    for value in raw_values:
        try:
            x=float(value)
            if not math.isfinite(x):
                inputs_valid=False
        except Exception:
            inputs_valid=False
    pairs=max(0,_safe_int(pair_count,0))
    active=max(0,min(_safe_int(active_pairs,0),pairs))
    background=pairs-active
    cap=max(1,_safe_int(daily_cap,1))
    reserve=max(0,min(_safe_int(reserved_calls,0),cap))
    usable=cap-reserve

    active_per_pair=_calls(active_m15_min,market_minutes)
    background_per_pair=_calls(background_m15_min,market_minutes)
    daily_context=max(0,_safe_int(daily_context_calls_per_pair,0))

    m15_calls=active*active_per_pair+background*background_per_pair
    context_calls=pairs*daily_context
    total=m15_calls+context_calls
    within_usable=bool(inputs_valid and _safe_int(active_m15_min,0)>0 and _safe_int(background_m15_min,0)>0 and _safe_int(market_minutes,0)>=0 and total<=usable)

    return {
        "pair_count":pairs,
        "active_pairs":active,
        "background_pairs":background,
        "inputs_valid":bool(inputs_valid),
        "active_m15_min":_safe_int(active_m15_min,0),
        "background_m15_min":_safe_int(background_m15_min,0),
        "active_m15_calls_per_pair":active_per_pair,
        "background_m15_calls_per_pair":background_per_pair,
        "m15_calls":m15_calls,
        "daily_context_calls":context_calls,
        "estimated_daily_calls":total,
        "daily_cap":cap,
        "reserved_calls":reserve,
        "usable_cap":usable,
        "headroom_calls":max(0,usable-total),
        "excess_calls":max(0,total-usable),
        "within_usable_cap":within_usable,
        "required_m15_history_bars":max(0,_safe_int(required_m15_history_bars,0)),
        "derive_h1_h4_from_m15_required":True,
        "execution_grade_only_for_active_set":True,
        "background_pairs_must_not_be_executable_when_stale":True,
        "live_change_allowed":False,
        "automatic_expansion_allowed":False,
        "manual_validation_required":True,
    }


def adaptive_readiness(
    plan: dict[str,Any],
    *,
    m15_resampling_validated: bool = False,
    freshness_gate_validated: bool = False,
    quota_shadow_validated: bool = False,
) -> dict[str,Any]:
    blockers=[]
    if not plan.get("within_usable_cap",False):
        blockers.append("Plano excede o orçamento utilizável")
    if not m15_resampling_validated:
        blockers.append("Resampling M15→H1/H4 ainda não validado")
    if not freshness_gate_validated:
        blockers.append("Gate de frescor do conjunto ativo ainda não validado")
    if not quota_shadow_validated:
        blockers.append("Consumo real ainda não validado em Shadow Mode")
    return {
        "status":"REVIEWABLE" if not blockers else "BUILDING",
        "blockers":blockers,
        "manual_validation_required":True,
        "automatic_expansion_allowed":False,
    }


def render_adaptive_coverage_plan() -> dict[str,Any]:
    plan=adaptive_coverage_plan()
    readiness=adaptive_readiness(plan)

    st.markdown("### 🌐 Plano adaptativo — caminho 7 → 28 pares")
    st.caption(
        "Arquitetura de pesquisa para ampliar cobertura sem liberar 28 pares como executáveis "
        "ao mesmo tempo. Não altera PAIR_ORDER nem a coleta ao vivo."
    )
    c1,c2,c3,c4=st.columns(4)
    c1.metric("Universo",f"{plan['pair_count']} pares")
    c2.metric("Conjunto ativo",f"{plan['active_pairs']} pares")
    c3.metric("Teto estimado",f"{plan['estimated_daily_calls']} chamadas/dia")
    c4.metric("Cap utilizável",f"{plan['usable_cap']} chamadas/dia")

    if plan["within_usable_cap"]:
        st.success(
            f"Cenário teórico cabe no orçamento com {plan['headroom_calls']} chamadas de folga, "
            "desde que H1/H4 sejam derivados de M15 validado."
        )
    else:
        st.warning(
            f"Cenário ainda excede o orçamento utilizável em {plan['excess_calls']} chamadas/dia."
        )

    st.caption(
        f"Ativos: M15 ~{plan['active_m15_min']} min. Fundo: M15 ~{plan['background_m15_min']} min. "
        "Pares de fundo permanecem não executáveis quando o frescor não atender ao Safety Core."
    )
    with st.expander("Validações obrigatórias antes de qualquer mudança ao vivo"):
        for item in readiness["blockers"]:
            st.write("•",item)
    st.caption("Expansão automática: DESATIVADA. Alteração ao vivo exige validação manual.")
    return {"plan":plan,"readiness":readiness}
