"""AtlasQuant Data Confidence Center V1.

Presentation-only health summary built from already-computed institutional
readiness and Autopilot status. It does not create signals or relax any gate.
"""
from __future__ import annotations

from statistics import mean
from typing import Any, Mapping, Sequence
import math
import streamlit as st


def _finite(value: Any) -> float | None:
    try:
        out=float(value)
        return out if math.isfinite(out) else None
    except Exception:
        return None


def build_data_confidence(
    packs: Sequence[Mapping[str, Any]] | None,
    autopilot: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    rows=[dict(p or {}) for p in (packs or [])]
    auto=dict(autopilot or {})

    data_scores=[]
    model_quality=[]
    ages=[]
    ready=0
    stale=0
    missing_age=0
    event_risk=0

    for p in rows:
        dr=dict(p.get("data_ready", {}) or {})
        if bool(dr.get("sufficient", False)):
            ready += 1
        ds=_finite(dr.get("score"))
        if ds is not None:
            data_scores.append(ds)
        q=_finite(p.get("quality"))
        if q is not None:
            model_quality.append(q)
        age=_finite(p.get("technical_age"))
        if age is None:
            missing_age += 1
        else:
            ages.append(age)
        if bool(p.get("stale_technical", False)):
            stale += 1
        event=str(p.get("event", "") or "").upper()
        if any(x in event for x in ("ALTO", "MÁX", "MAX", "HIGH", "FOMC", "CPI", "NFP")):
            event_risk += 1

    total=len(rows)
    avg_data=mean(data_scores) if data_scores else 0.0
    avg_quality=mean(model_quality) if model_quality else 0.0
    ready_ratio=(ready/total) if total else 0.0
    process_ok=bool(auto.get("app_headless_ok", False))
    source_blocked=bool(auto.get("twelve_daily_blocked", False))

    if total == 0 or ready == 0:
        status="RED"; label="DADOS INSUFICIENTES"
    elif ready_ratio >= .80 and avg_data >= 85 and process_ok and not source_blocked and stale == 0:
        status="GREEN"; label="DADOS OPERACIONAIS"
    else:
        status="YELLOW"; label="DADOS PARCIAIS / ATENÇÃO"

    return {
        "status": status,
        "label": label,
        "total_pairs": total,
        "ready_pairs": ready,
        "ready_ratio": round(ready_ratio*100, 1),
        "average_data_score": round(avg_data, 1),
        "average_model_quality": round(avg_quality, 1),
        "freshest_age_min": round(min(ages), 1) if ages else None,
        "oldest_age_min": round(max(ages), 1) if ages else None,
        "missing_age_pairs": missing_age,
        "stale_pairs": stale,
        "event_risk_pairs": event_risk,
        "process_ok": process_ok,
        "source_blocked": source_blocked,
        "source_block_type": str(auto.get("twelve_block_type", "") or ""),
        "budget": dict(auto.get("twelve_budget", {}) or {}),
    }



def data_confidence_visual_state(summary: Mapping[str,Any] | None)->dict[str,str]:
    s=dict(summary or {})
    status=str(s.get("status","") or "").upper()
    if status=="GREEN":
        return {"label":"DADOS OPERACIONAIS","detail":"Cobertura e frescor mínimos atendidos; ainda não é autorização de trade"}
    if status=="YELLOW":
        return {"label":"ATENÇÃO NOS DADOS","detail":"Há cobertura parcial, stale, processo ou orçamento exigindo revisão"}
    if status=="RED":
        return {"label":"DADOS INSUFICIENTES","detail":"Leitura operacional deve permanecer bloqueada"}
    return {"label":"REVISAR","detail":"Estado de dados inválido ou indisponível"}


def render_data_confidence(
    packs: Sequence[Mapping[str, Any]] | None,
    autopilot: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    s=build_data_confidence(packs, autopilot)
    icon={"GREEN":"🟢","YELLOW":"🟡","RED":"🔴"}.get(s["status"],"⚪")

    st.markdown("### 🛡️ Data Confidence Center")
    visual=data_confidence_visual_state(s)
    st.markdown(
        f"""<div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap;padding:11px 13px;
        border:1px solid rgba(137,170,210,.18);border-radius:12px;margin:4px 0 13px;background:rgba(11,27,47,.52)">
        <strong>{visual['label']}</strong><span style="opacity:.74;font-size:.78rem">{visual['detail']}</span>
        <span style="margin-left:auto;opacity:.68;font-size:.72rem">Saúde dos dados ≠ direção</span></div>""",
        unsafe_allow_html=True,
    )
    st.caption(
        "Saúde dos dados separada do direcional. Este painel não aumenta score e não libera operação."
    )
    c1,c2,c3,c4=st.columns(4)
    c1.metric("Estado dos dados", f"{icon} {s['label']}")
    c2.metric("Pares prontos", f"{s['ready_pairs']}/{s['total_pairs']}")
    c3.metric("Data Score médio", f"{s['average_data_score']:.0f}/100")
    c4.metric("Qualidade média", f"{s['average_model_quality']:.0f}/100")

    details=[]
    if s["oldest_age_min"] is not None:
        details.append(f"maior idade técnica {s['oldest_age_min']:.0f} min")
    if s["stale_pairs"]:
        details.append(f"{s['stale_pairs']} par(es) stale")
    if s["missing_age_pairs"]:
        details.append(f"{s['missing_age_pairs']} sem idade técnica")
    if s["event_risk_pairs"]:
        details.append(f"{s['event_risk_pairs']} com risco de evento relevante")
    if details:
        st.caption(" · ".join(details))

    p1,p2=st.columns(2)
    p1.write("**Autopilot:** " + ("🟢 saudável" if s["process_ok"] else "🔴 sem confirmação saudável"))
    if s["source_blocked"]:
        p2.write("**Twelve Data:** 🟠 bloqueio/orçamento registrado")
    else:
        p2.write("**Twelve Data:** 🟢 sem bloqueio registrado")

    budget=s["budget"]
    if budget and not budget.get("error"):
        used=int(budget.get("used",0) or 0)
        limit=int(budget.get("limit",480) or 480)
        remaining=int(budget.get("remaining",max(0,limit-used)) or 0)
        st.caption(f"Orçamento técnico: {used}/{limit} créditos contabilizados · saldo protegido {remaining}.")
    return s
