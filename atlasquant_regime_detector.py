"""AtlasQuant Regime Change Detector V1.

Detects material changes in the already-computed institutional context across
successive snapshots. It does not predict markets, create direction or change
scores. A detected regime shift may only add caution to the Safety Core.
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


def regime_snapshot(pack: Mapping[str, Any] | None) -> dict[str, Any]:
    p=dict(pack or {})
    dr=dict(p.get("data_ready", {}) or {})
    return {
        "pair":str(p.get("pair","—")),
        "side":str(p.get("side","NEUTRAL") or "NEUTRAL").upper(),
        "direction":str(p.get("direction","⚪ AGUARDAR")),
        "state":str(p.get("state","⚪ AGUARDAR")),
        "macro_diff":_num(p.get("macro_diff")),
        "priority":_num(p.get("priority")),
        "score":_num(p.get("score")),
        "quality":_num(p.get("quality")),
        "data_score":_num(dr.get("score")),
        "data_sufficient":bool(dr.get("sufficient",False)),
        "executable":bool(p.get("executable",False)),
        "gate":str(p.get("gate","—")),
        "m15":str(p.get("m15","—")),
        "event":str(p.get("event","—")),
        "hard_blocks":tuple(str(x) for x in (p.get("hard_blocks",[]) or [])),
    }


def detect_regime_change(
    current_pack: Mapping[str, Any] | None,
    previous_snapshot: Mapping[str, Any] | None,
    *,
    macro_delta_threshold: float = 8.0,
    priority_delta_threshold: float = 15.0,
    quality_delta_threshold: float = 15.0,
) -> dict[str, Any]:
    cur=regime_snapshot(current_pack)
    if not previous_snapshot:
        return {
            "status":"BASELINE",
            "label":"BASELINE INICIAL",
            "supported":None,
            "drivers":["Primeira leitura: ainda não há snapshot anterior comparável."],
            "severity":0,
            "snapshot":cur,
        }

    prev=dict(previous_snapshot)
    drivers=[]
    severity=0

    if cur["pair"] != str(prev.get("pair","—")):
        drivers.append(f"Melhor contexto mudou de {prev.get('pair','—')} para {cur['pair']}.")
        severity=max(severity,1)

    prev_side=str(prev.get("side","NEUTRAL") or "NEUTRAL").upper()
    if cur["side"] in ("BUY","SELL") and prev_side in ("BUY","SELL") and cur["side"] != prev_side:
        drivers.append(f"Direcional virou de {prev_side} para {cur['side']}.")
        severity=max(severity,3)
    elif cur["side"] != prev_side:
        drivers.append(f"Lado mudou de {prev_side} para {cur['side']}.")
        severity=max(severity,1)

    cur_macro,prev_macro=cur["macro_diff"],_num(prev.get("macro_diff"))
    if cur_macro is not None and prev_macro is not None:
        delta=cur_macro-prev_macro
        if abs(delta) >= float(macro_delta_threshold):
            drivers.append(f"Diferencial macro mudou {delta:+.1f} pts.")
            severity=max(severity,2)
        if cur_macro*prev_macro < 0 and abs(cur_macro)>=6 and abs(prev_macro)>=6:
            drivers.append("Diferencial macro cruzou de um lado para o outro.")
            severity=max(severity,3)

    cur_pri,prev_pri=cur["priority"],_num(prev.get("priority"))
    if cur_pri is not None and prev_pri is not None and abs(cur_pri-prev_pri)>=float(priority_delta_threshold):
        drivers.append(f"Prioridade mudou {cur_pri-prev_pri:+.1f} pts.")
        severity=max(severity,2)

    cur_q,prev_q=cur["quality"],_num(prev.get("quality"))
    if cur_q is not None and prev_q is not None and abs(cur_q-prev_q)>=float(quality_delta_threshold):
        drivers.append(f"Qualidade mudou {cur_q-prev_q:+.1f} pts.")
        severity=max(severity,2)

    cur_ds,prev_ds=cur["data_score"],_num(prev.get("data_score"))
    if cur_ds is not None and prev_ds is not None and abs(cur_ds-prev_ds)>=float(quality_delta_threshold):
        drivers.append(f"Data Score mudou {cur_ds-prev_ds:+.1f} pts.")
        severity=max(severity,2)

    if cur["executable"] != bool(prev.get("executable",False)):
        drivers.append(
            "Execução foi liberada." if cur["executable"] else "Execução deixou de estar liberada."
        )
        severity=max(severity,2)

    if cur["gate"] != str(prev.get("gate","—")):
        drivers.append(f"Gate mudou: {prev.get('gate','—')} → {cur['gate']}.")
        severity=max(severity,1)

    if cur["m15"] != str(prev.get("m15","—")):
        drivers.append(f"M15 mudou: {prev.get('m15','—')} → {cur['m15']}.")
        severity=max(severity,1)

    if cur["event"] != str(prev.get("event","—")):
        drivers.append(f"Risco de evento mudou: {prev.get('event','—')} → {cur['event']}.")
        severity=max(severity,1)

    new_hard=[x for x in cur["hard_blocks"] if x not in tuple(prev.get("hard_blocks",()) or ())]
    if new_hard:
        drivers.append("Novo hard block: " + "; ".join(new_hard[:2]) + ".")
        severity=max(severity,3)

    if not cur["data_sufficient"]:
        drivers.append("Dados atuais não estão suficientes para confirmar regime.")
        severity=max(severity,2)

    if severity >= 3:
        status="SHIFT"; label="MUDANÇA DE REGIME / CONTEXTO"; supported=False
    elif severity == 2:
        status="TRANSITION"; label="TRANSIÇÃO — REDOBRAR CONFIRMAÇÃO"; supported=False
    elif severity == 1:
        status="WATCH"; label="MUDANÇA LEVE — OBSERVAR"; supported=True
    else:
        status="STABLE"; label="CONTEXTO ESTÁVEL"; supported=True
        drivers=["Sem mudança material entre os snapshots comparáveis."]

    return {
        "status":status,
        "label":label,
        "supported":supported,
        "drivers":drivers[:8],
        "severity":severity,
        "snapshot":cur,
    }


def capture_regime_detector(pack: Mapping[str, Any] | None) -> dict[str, Any]:
    key="atlasquant_regime_previous_snapshot"
    previous=st.session_state.get(key)
    result=detect_regime_change(pack,previous)
    st.session_state[key]=result["snapshot"]
    return result


def render_regime_detector(
    pack: Mapping[str, Any] | None,
    *,
    capture_result: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    result=dict(capture_result or capture_regime_detector(pack))

    icon={"BASELINE":"⚪","STABLE":"🟢","WATCH":"🟡","TRANSITION":"🟠","SHIFT":"🔴"}.get(result["status"],"⚪")
    st.markdown("### 🌡️ Regime Change Detector")
    st.caption(
        "Compara o contexto atual com o snapshot anterior da sessão. Detecta mudança; não prevê o próximo movimento."
    )
    c1,c2=st.columns([1,2])
    c1.metric("Estado",f"{icon} {result['label']}")
    with c2:
        for item in result["drivers"][:4]:
            st.caption("• " + item)

    if result["status"] in ("SHIFT","TRANSITION"):
        st.warning("Regime/contexto em transição: exigir nova confirmação antes de confiar no estado anterior.")
    return result
