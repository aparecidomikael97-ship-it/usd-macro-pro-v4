"""AtlasQuant Central Brief — fail-closed executive summary for the Central tab.

Consumes already-computed institutional packs. It never creates a new signal,
changes a score, or bypasses execution gates.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence
import streamlit as st


def _score(v: Any) -> float:
    try:
        return float(v)
    except Exception:
        return 0.0


def build_central_brief(
    packs: Sequence[Mapping[str, Any]] | None,
    autopilot: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    rows = [dict(p or {}) for p in (packs or [])]
    auto = dict(autopilot or {})

    executable = [
        p for p in rows
        if bool(p.get("executable", False))
        and bool((p.get("data_ready", {}) or {}).get("sufficient", False))
    ]
    ready = [p for p in rows if bool((p.get("data_ready", {}) or {}).get("sufficient", False))]
    blocked = [p for p in rows if str(p.get("state", "")).startswith("🔴")]
    waiting = [p for p in rows if p not in executable and p not in blocked]

    process_ok = bool(auto.get("app_headless_ok", False))
    source_blocked = bool(auto.get("twelve_daily_blocked", False))

    if executable and process_ok and not source_blocked:
        state = "PROCURAR ENTRADA"
        light = "GREEN"
        headline = "Há setup executável confirmado pelo motor e processo saudável"
        candidates = executable
    elif executable and (not process_ok or source_blocked):
        state = "NÃO OPERAR"
        light = "RED"
        headline = "Setup aparente bloqueado por saúde de processo/fonte"
        candidates = executable
    elif not rows or not ready or len(blocked) == len(rows):
        state = "NÃO OPERAR"
        light = "RED"
        headline = "Nenhum setup está operacionalmente liberado"
        candidates = ready or rows
    else:
        state = "AGUARDAR CONFIRMAÇÃO"
        light = "YELLOW"
        headline = "Há direção/contexto, mas os gates ainda não liberaram execução"
        candidates = ready

    best = max(candidates, key=lambda p: _score(p.get("priority", 0)), default=None)

    return {
        "state": state,
        "traffic_light": light,
        "headline": headline,
        "best_pair": str((best or {}).get("pair", "—")),
        "best_priority": _score((best or {}).get("priority", 0)),
        "total": len(rows),
        "executable": len(executable),
        "ready": len(ready),
        "blocked": len(blocked),
        "waiting": len(waiting),
        "process_ok": process_ok,
        "source_blocked": source_blocked,
    }


def render_central_brief(
    packs: Sequence[Mapping[str, Any]] | None,
    autopilot: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    brief = build_central_brief(packs, autopilot)
    icon = {"GREEN": "🟢", "YELLOW": "🟡", "RED": "🔴"}.get(brief["traffic_light"], "⚪")
    css_class = brief["traffic_light"].lower()

    st.markdown(
        """
<style>
.aq-brief{border:1px solid rgba(137,170,210,.18);border-radius:16px;padding:17px 19px;
background:linear-gradient(110deg,rgba(14,31,52,.92),rgba(10,24,41,.86));margin:4px 0 14px}
.aq-brief.green{border-left:4px solid #42d392}.aq-brief.yellow{border-left:4px solid #f2c14e}
.aq-brief.red{border-left:4px solid #ff6b7a}
.aq-brief-title{font-size:.75rem;text-transform:uppercase;letter-spacing:.1em;color:#9fb0c6;font-weight:800}
.aq-brief-state{font-size:1.35rem;font-weight:850;margin-top:4px;color:#edf4ff}
.aq-brief-text{font-size:.82rem;color:#b7c6d9;margin-top:5px}
</style>
""",
        unsafe_allow_html=True,
    )
    st.markdown(
        f"""
<div class="aq-brief {css_class}">
  <div class="aq-brief-title">Resumo operacional</div>
  <div class="aq-brief-state">{icon} {brief['state']}</div>
  <div class="aq-brief-text">{brief['headline']}</div>
</div>
""",
        unsafe_allow_html=True,
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Melhor contexto", brief["best_pair"])
    c2.metric("Prioridade", f"{brief['best_priority']:.0f}/100")
    c3.metric("Executáveis", f"{brief['executable']}/{brief['total']}")
    c4.metric("Dados suficientes", f"{brief['ready']}/{brief['total']}")

    notes = []
    if not brief["process_ok"]:
        notes.append("Autopilot/headless sem confirmação saudável")
    if brief["source_blocked"]:
        notes.append("Twelve Data com bloqueio/orçamento registrado")
    if notes:
        st.warning(" · ".join(notes))
    return brief
