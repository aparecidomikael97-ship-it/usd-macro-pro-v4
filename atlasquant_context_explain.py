"""AtlasQuant Context Explain V1.

Explains changes, validity and contradictions using outputs already produced by
the institutional engine. It is presentation-only and fail-closed: it never
creates a direction, boosts a score or marks a setup executable.
"""
from __future__ import annotations

from typing import Any, Mapping
import math
import streamlit as st


def _num(value: Any, default: float = 0.0) -> float:
    try:
        out=float(value)
        return out if math.isfinite(out) else default
    except Exception:
        return default


def pack_snapshot(pack: Mapping[str, Any] | None) -> dict[str, Any]:
    p=dict(pack or {})
    dr=dict(p.get("data_ready", {}) or {})
    return {
        "pair": str(p.get("pair", "—")),
        "direction": str(p.get("direction", "⚪ AGUARDAR")),
        "state": str(p.get("state", "⚪ AGUARDAR")),
        "priority": _num(p.get("priority", 0)),
        "quality": _num(p.get("quality", 0)),
        "data_score": _num(dr.get("score", 0)),
        "data_sufficient": bool(dr.get("sufficient", False)),
        "executable": bool(p.get("executable", False)),
        "gate": str(p.get("gate", "—")),
        "m15": str(p.get("m15", "—")),
        "event": str(p.get("event", "—")),
        "technical_age": p.get("technical_age"),
        "hard_blocks": tuple(str(x) for x in (p.get("hard_blocks", []) or [])),
        "soft_blocks": tuple(str(x) for x in (p.get("soft_blocks", []) or [])),
        "next_action": str(p.get("next_action", "—")),
        "reason": str(p.get("reason", "—")),
        "side": str(p.get("side", "NEUTRAL")),
        "up": tuple(str(x) for x in (p.get("up", []) or [])),
        "down": tuple(str(x) for x in (p.get("down", []) or [])),
    }


def explain_change(
    current: Mapping[str, Any] | None,
    previous: Mapping[str, Any] | None,
) -> list[str]:
    cur=pack_snapshot(current)
    if not previous:
        return ["Primeira leitura desta sessão; ainda não há estado anterior para comparar."]
    prev=pack_snapshot(previous)
    reasons=[]
    if cur["pair"] != prev["pair"]:
        reasons.append(f"Melhor contexto mudou de {prev['pair']} para {cur['pair']}.")
    if cur["direction"] != prev["direction"]:
        reasons.append(f"Direção mudou: {prev['direction']} → {cur['direction']}.")
    if cur["state"] != prev["state"]:
        reasons.append(f"Estado operacional mudou: {prev['state']} → {cur['state']}.")
    dp=cur["priority"]-prev["priority"]
    if abs(dp) >= 3:
        reasons.append(f"Prioridade {'subiu' if dp>0 else 'caiu'} {abs(dp):.1f} pontos.")
    dq=cur["quality"]-prev["quality"]
    if abs(dq) >= 5:
        reasons.append(f"Qualidade {'subiu' if dq>0 else 'caiu'} {abs(dq):.1f} pontos.")
    dd=cur["data_score"]-prev["data_score"]
    if abs(dd) >= 5:
        reasons.append(f"Data Score {'subiu' if dd>0 else 'caiu'} {abs(dd):.1f} pontos.")
    if cur["gate"] != prev["gate"]:
        reasons.append(f"Gate mudou: {prev['gate']} → {cur['gate']}.")
    if cur["m15"] != prev["m15"]:
        reasons.append(f"M15 mudou: {prev['m15']} → {cur['m15']}.")
    if cur["event"] != prev["event"]:
        reasons.append(f"Risco de evento mudou: {prev['event']} → {cur['event']}.")
    new_hard=[x for x in cur["hard_blocks"] if x not in prev["hard_blocks"]]
    if new_hard:
        reasons.append("Novo hard block: " + "; ".join(new_hard[:3]) + ".")
    cleared=[x for x in prev["hard_blocks"] if x not in cur["hard_blocks"]]
    if cleared:
        reasons.append("Hard block removido: " + "; ".join(cleared[:3]) + ".")
    if not reasons:
        reasons.append("Sem mudança material nos principais gates, direção ou qualidade.")
    return reasons


def context_validity(pack: Mapping[str, Any] | None) -> dict[str, Any]:
    snap=pack_snapshot(pack)
    hard=list(snap["hard_blocks"])
    soft=list(snap["soft_blocks"])
    if hard or not snap["data_sufficient"]:
        status="BLOCKED"
        label="NÃO OPERAR"
        explanation="Contexto inválido para execução enquanto houver hard block ou dados insuficientes."
    elif soft:
        status="WAIT"
        label="AGUARDAR CONFIRMAÇÃO"
        explanation="Há alerta(s) soft pendente(s); o contexto não deve ser tratado como liberado."
    elif snap["executable"]:
        status="ACTIVE"
        label="MOTOR LIBEROU CONTEXTO"
        explanation="O motor liberou o contexto; Safety Core, plano e risco ainda precisam permanecer válidos."
    else:
        status="WAIT"
        label="AGUARDAR CONFIRMAÇÃO"
        explanation="O contexto existe, mas os gates de execução ainda não foram satisfeitos."

    opposite = list(snap["down"] if snap["side"]=="BUY" else snap["up"] if snap["side"]=="SELL" else ())
    contradictions=[]
    contradictions.extend(hard)
    contradictions.extend(soft)
    contradictions.extend(opposite[:3])

    seen=set()
    contradictions=[x for x in contradictions if not (x in seen or seen.add(x))]
    return {
        "status": status,
        "label": label,
        "explanation": explanation,
        "next_action": snap["next_action"],
        "reason": snap["reason"],
        "contradictions": contradictions[:6],
        "hard_blocks": hard,
        "soft_blocks": soft,
        "data_score": snap["data_score"],
        "quality": snap["quality"],
        "technical_age": snap["technical_age"],
        "gate": snap["gate"],
        "m15": snap["m15"],
        "event": snap["event"],
    }


def render_context_explain(best_pack: Mapping[str, Any] | None) -> dict[str, Any]:
    current=pack_snapshot(best_pack)
    previous=st.session_state.get("atlasquant_previous_best_snapshot")
    changes=explain_change(current, previous)
    validity=context_validity(current)

    st.markdown("### 🧠 Por que mudou? · validade · riscos")
    left,right=st.columns([1.25,1.0])
    with left:
        st.markdown("**Por que o contexto está assim agora**")
        st.write(f"Motivo dominante: {validity['reason']}")
        for item in changes[:5]:
            st.caption("• " + item)
    with right:
        badge={"ACTIVE":"🟢","WAIT":"🟡","BLOCKED":"🔴"}.get(validity["status"],"⚪")
        st.markdown(f"**Validade do contexto:** {badge} {validity['label']}")
        st.caption(validity["explanation"])
        st.caption(f"Gate {validity['gate']} · M15 {validity['m15']} · Evento {validity['event']}")
        st.caption(f"Próximo passo: {validity['next_action']}")

    if validity["contradictions"]:
        with st.expander("⚠️ Riscos e contradições"):
            for item in validity["contradictions"]:
                st.write("•", item)
    else:
        st.success("Nenhuma contradição registrada pelo motor neste contexto.")

    st.session_state["atlasquant_previous_best_snapshot"]=current
    return {"changes":changes,"validity":validity,"snapshot":current}
