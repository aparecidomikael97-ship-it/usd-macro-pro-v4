"""AtlasQuant Confluence Map V1.

Visualizes the state of already-computed engine layers. It is descriptive only:
no score is increased, no direction is invented, and no execution gate is bypassed.
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


def _layer(name: str, status: str, label: str, detail: str) -> dict[str, str]:
    return {"name": name, "status": status, "label": label, "detail": detail}


def build_confluence_map(pack: Mapping[str, Any] | None) -> list[dict[str, str]]:
    p=dict(pack or {})
    dr=dict(p.get("data_ready", {}) or {})
    ict_fresh=dict(p.get("ict_fresh", {}) or {})
    hard=list(p.get("hard_blocks", []) or [])
    side=str(p.get("side", "NEUTRAL") or "NEUTRAL").upper()
    macro_diff=abs(_num(p.get("macro_diff", 0)))
    data_score=_num(dr.get("score", 0))
    quality=_num(p.get("quality", 0))
    ict_read=_num(p.get("ict_read", 0))
    inst_read=_num(p.get("inst_read", 0))
    event=str(p.get("event", "DESCONHECIDO") or "DESCONHECIDO")
    stale=[str(x).upper() for x in (p.get("stale_technical", []) or [])]
    executable=bool(p.get("executable", False))

    layers=[]

    if side in ("BUY","SELL") and macro_diff >= 6:
        layers.append(_layer("Macro", "GREEN", "ALINHADO", f"Δ força {macro_diff:.1f} pts"))
    elif side in ("BUY","SELL"):
        layers.append(_layer("Macro", "YELLOW", "FRACO", f"Δ força {macro_diff:.1f} pts"))
    else:
        layers.append(_layer("Macro", "YELLOW", "NEUTRO", "sem lado definido"))

    if bool(dr.get("sufficient", False)) and data_score >= 85:
        layers.append(_layer("Dados", "GREEN", "SUFICIENTES", f"Data Score {data_score:.0f}/100"))
    elif data_score >= 55:
        layers.append(_layer("Dados", "YELLOW", "PARCIAIS", f"Data Score {data_score:.0f}/100"))
    else:
        layers.append(_layer("Dados", "RED", "INSUFICIENTES", f"Data Score {data_score:.0f}/100"))

    h4=str(p.get("h4","—"))
    h1=str(p.get("h1","—"))
    h4_stale=any(x.startswith("H4:") for x in stale)
    h1_stale=any(x.startswith("H1:") for x in stale)
    if h4_stale or h1_stale:
        layers.append(_layer("Top-down", "RED", "STALE", f"H4 {h4} · H1 {h1}"))
    elif bool(dr.get("sufficient", False)):
        layers.append(_layer("Top-down", "GREEN", "ATUAL", f"H4 {h4} · H1 {h1}"))
    else:
        layers.append(_layer("Top-down", "YELLOW", "INCOMPLETO", f"H4 {h4} · H1 {h1}"))

    if bool(ict_fresh.get("ready", False)) and ict_read >= 70:
        layers.append(_layer("ICT/SMC", "GREEN", "FORTE", f"{ict_read:.0f}/100"))
    elif bool(ict_fresh.get("ready", False)):
        layers.append(_layer("ICT/SMC", "YELLOW", "PARCIAL", f"{ict_read:.0f}/100"))
    else:
        layers.append(_layer("ICT/SMC", "RED", "NÃO PRONTO", str(ict_fresh.get("label","sem frescor"))))

    inst_ready=bool(dr.get("institutional_data_ready", False))
    if inst_ready and inst_read >= 70:
        layers.append(_layer("Institucional", "GREEN", "FORTE", f"{inst_read:.0f}/100"))
    elif inst_ready:
        layers.append(_layer("Institucional", "YELLOW", "PARCIAL", f"{inst_read:.0f}/100"))
    else:
        layers.append(_layer("Institucional", "RED", "SEM DADOS", f"{inst_read:.0f}/100"))

    event_up=event.upper()
    if any(x in event_up for x in ("MÁX", "MAX", "ALTO", "HIGH", "FOMC", "CPI", "NFP")):
        layers.append(_layer("Evento", "RED", "RISCO RELEVANTE", event))
    elif event_up in ("DESCONHECIDO","—",""):
        layers.append(_layer("Evento", "YELLOW", "DESCONHECIDO", event or "—"))
    else:
        layers.append(_layer("Evento", "GREEN", "SEM BLOQUEIO", event))

    if executable and bool(dr.get("sufficient", False)) and not hard:
        layers.append(_layer("Gate final", "GREEN", "LIBERADO", str(p.get("gate","—"))))
    elif hard:
        layers.append(_layer("Gate final", "RED", "BLOQUEADO", "; ".join(str(x) for x in hard[:2])))
    else:
        layers.append(_layer("Gate final", "YELLOW", "AGUARDAR", str(p.get("gate","—"))))

    return layers


def confluence_summary(layers: list[Mapping[str, str]] | None) -> dict[str, int]:
    items=list(layers or [])
    return {
        "green": sum(1 for x in items if x.get("status")=="GREEN"),
        "yellow": sum(1 for x in items if x.get("status")=="YELLOW"),
        "red": sum(1 for x in items if x.get("status")=="RED"),
        "total": len(items),
    }


def render_confluence_map(pack: Mapping[str, Any] | None) -> list[dict[str, str]]:
    layers=build_confluence_map(pack)
    summary=confluence_summary(layers)
    st.markdown("### 🧩 Confluence Map")
    st.caption("Mapa descritivo das camadas do motor. Não é nota de probabilidade e não substitui o Gate final.")

    cols=st.columns(len(layers))
    icon={"GREEN":"🟢","YELLOW":"🟡","RED":"🔴"}
    for col, item in zip(cols, layers):
        with col:
            st.markdown(f"**{icon.get(item['status'],'⚪')} {item['name']}**")
            st.caption(item["label"])
            st.caption(item["detail"])

    st.caption(
        f"Camadas: {summary['green']} prontas · {summary['yellow']} em atenção · "
        f"{summary['red']} bloqueadas/insuficientes."
    )
    return layers
