"""AtlasQuant Operational Plan V1.

Builds a conservative operational checklist from the institutional engine's
already-computed outputs. It never invents an entry, stop, target or direction.
"""
from __future__ import annotations

from typing import Any, Mapping
import math
import streamlit as st


def _num(value: Any) -> float | None:
    try:
        out=float(value)
        return out if math.isfinite(out) else None
    except Exception:
        return None


def build_operational_plan(pack: Mapping[str, Any] | None) -> dict[str, Any]:
    p=dict(pack or {})
    dr=dict(p.get("data_ready", {}) or {})
    hard=[str(x) for x in (p.get("hard_blocks", []) or [])]
    soft=[str(x) for x in (p.get("soft_blocks", []) or [])]
    sufficient=bool(dr.get("sufficient", False))
    executable=bool(p.get("executable", False))
    side=str(p.get("side", "NEUTRAL") or "NEUTRAL").upper()
    direction=str(p.get("direction", "⚪ AGUARDAR"))
    pair=str(p.get("pair", "—"))
    gate=str(p.get("gate", "—"))
    m15=str(p.get("m15", "—"))
    next_action=str(p.get("next_action", "—"))
    target=str(p.get("target", "—"))
    event=str(p.get("event", "DESCONHECIDO") or "DESCONHECIDO")
    price=_num(p.get("price"))

    if hard or not sufficient:
        status="NO_TRADE"
        label="NÃO OPERAR"
        instruction="Preservar capital; aguardar os bloqueios/dados serem resolvidos."
    elif soft:
        status="WAIT"
        label="AGUARDAR CONFIRMAÇÃO"
        instruction="Há alerta(s) operacional(is) pendente(s); não procurar entrada até a confirmação."
    elif executable and side in ("BUY","SELL"):
        status="SEARCH_ENTRY"
        label="PROCURAR ENTRADA"
        instruction=f"Procurar somente {'compras' if side=='BUY' else 'vendas'} enquanto o contexto continuar válido."
    else:
        status="WAIT"
        label="AGUARDAR CONFIRMAÇÃO"
        instruction=next_action if next_action and next_action!="—" else "Aguardar confirmação dos gates."

    requirements=[]
    if not sufficient:
        requirements.append("Dados precisam voltar a ficar suficientes e frescos.")
    if gate not in ("—","READY","OK","🟢","A"):
        requirements.append(f"Gate atual: {gate}.")
    if m15 not in ("—","CONFIRMADO","🟢 CONFIRMADO","OK"):
        requirements.append(f"M15 atual: {m15}.")
    if next_action and next_action!="—":
        requirements.append(next_action)
    requirements=list(dict.fromkeys(requirements))

    invalidation=[]
    invalidation.extend(hard)
    invalidation.extend(soft)
    if sufficient:
        invalidation.append("Dados técnicos perderem frescor/suficiência.")
    if side in ("BUY","SELL"):
        invalidation.append("Direcional macro/institucional mudar de lado.")
    if executable:
        invalidation.append("Gate final ou confirmação M15 deixar de estar válida.")
    if event.upper() not in ("NORMAL","—","DESCONHECIDO",""):
        invalidation.append(f"Risco de evento: {event}.")
    invalidation=list(dict.fromkeys(invalidation))

    return {
        "pair": pair,
        "direction": direction,
        "side": side,
        "status": status,
        "label": label,
        "instruction": instruction,
        "requirements": requirements[:6],
        "invalidation": invalidation[:8],
        "reference_price": price,
        "target": target,
        "event": event,
        "gate": gate,
        "m15": m15,
        "next_action": next_action,
        "data_sufficient": sufficient,
        "executable": executable,
        "hard_blocks": hard,
        "soft_blocks": soft,
    }


def render_operational_plan(pack: Mapping[str, Any] | None) -> dict[str, Any]:
    plan=build_operational_plan(pack)
    icon={"SEARCH_ENTRY":"🟢","WAIT":"🟡","NO_TRADE":"🔴"}.get(plan["status"],"⚪")

    st.markdown("### 📋 Plano Operacional Automático")
    st.caption(
        "Checklist derivado do motor atual. Não cria entrada, stop ou alvo novo; alertas soft mantêm o plano em espera."
    )

    c1,c2,c3,c4=st.columns(4)
    c1.metric("Estado", f"{icon} {plan['label']}")
    c2.metric("Par", plan["pair"])
    c3.metric("Gate", plan["gate"])
    c4.metric("M15", plan["m15"])

    st.info(plan["instruction"])

    left,right=st.columns(2)
    with left:
        st.markdown("**O que precisa acontecer**")
        if plan["requirements"]:
            for item in plan["requirements"]:
                st.write("•", item)
        else:
            st.write("• Nenhum requisito adicional registrado pelo motor.")
        if plan["reference_price"] is not None:
            st.caption(f"Preço de referência do contexto: {plan['reference_price']}")
        st.caption(f"Alvo/contexto de liquidez: {plan['target']}")

    with right:
        st.markdown("**O que invalida / faz esperar**")
        if plan["invalidation"]:
            for item in plan["invalidation"]:
                st.write("•", item)
        else:
            st.write("• Nenhuma invalidação adicional registrada.")
        st.caption(f"Risco de evento: {plan['event']}")

    if plan["status"]=="NO_TRADE":
        st.error("Plano bloqueado: NÃO OPERAR enquanto o motivo acima permanecer.")
    elif plan["status"]=="WAIT":
        st.warning("Plano em espera: não antecipar a confirmação.")
    else:
        st.success("Contexto liberado pelo motor para procurar entrada no lado indicado; revalidar gates antes de executar.")

    return plan
