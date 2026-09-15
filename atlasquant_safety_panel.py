"""AtlasQuant Safety Panel V1.

Adapter between the live institutional pack and the independent Safety Core.
This layer can only preserve/worsen operational permission; it never creates
direction, raises score, or converts a blocked setup into an executable one.
"""
from __future__ import annotations

from typing import Any, Mapping
import math
import streamlit as st

from atlasquant_safety_core import SafetyInput, evaluate_safety


def _finite(value: Any) -> float | None:
    try:
        out=float(value)
        return out if math.isfinite(out) else None
    except Exception:
        return None


def build_safety_input(
    pack: Mapping[str, Any] | None,
    autopilot: Mapping[str, Any] | None = None,
    *,
    regime_supported_override: bool | None = None,
) -> SafetyInput:
    p=dict(pack or {})
    auto=dict(autopilot or {})
    dr=dict(p.get("data_ready", {}) or {})

    data_score=_finite(dr.get("score"))
    sufficient=bool(dr.get("sufficient", False))
    stale=bool(p.get("stale_technical", False))
    source_blocked=bool(auto.get("twelve_daily_blocked", False))
    process_ok=bool(auto.get("app_headless_ok", False))

    essential_ok = sufficient and not source_blocked
    data_fresh = sufficient and not stale

    hard=tuple(str(x) for x in (p.get("hard_blocks", []) or []) if str(x).strip())
    model_conflict=bool(p.get("model_conflict", False))
    lookahead_risk=bool(p.get("lookahead_risk", False))
    regime_supported=(
        regime_supported_override
        if regime_supported_override is not None
        else p.get("regime_supported", True)
    )
    technical_ready=bool(p.get("executable", False))

    return SafetyInput(
        data_quality=data_score,
        data_fresh=data_fresh,
        essential_sources_ok=essential_ok,
        source_conflict=bool(p.get("source_conflict", False)),
        major_event_minutes=_finite(p.get("major_event_minutes")),
        update_health_ok=process_ok,
        regime_supported=regime_supported,
        model_conflict=model_conflict,
        technical_ready=technical_ready,
        lookahead_risk=lookahead_risk,
        extra_hard_blocks=hard,
    )


def evaluate_live_safety(
    pack: Mapping[str, Any] | None,
    autopilot: Mapping[str, Any] | None = None,
    *,
    regime_supported_override: bool | None = None,
) -> dict[str, object]:
    return evaluate_safety(
        build_safety_input(
            pack,
            autopilot,
            regime_supported_override=regime_supported_override,
        )
    )


def render_safety_core(
    pack: Mapping[str, Any] | None,
    autopilot: Mapping[str, Any] | None = None,
    *,
    regime_supported_override: bool | None = None,
) -> dict[str, object]:
    result=evaluate_live_safety(
        pack,
        autopilot,
        regime_supported_override=regime_supported_override,
    )
    icon={"GREEN":"🟢","YELLOW":"🟡","RED":"🔴"}.get(str(result["traffic_light"]),"⚪")

    st.markdown("### 🛡️ Safety Core")
    st.caption(
        "Veto independente. Pode bloquear ou mandar aguardar, mas nunca aumenta score nem cria direção."
    )
    c1,c2,c3=st.columns(3)
    c1.metric("Semáforo", f"{icon} {result['action']}")
    c2.metric("Hard blocks", len(result["hard_blocks"]))
    c3.metric("Alertas", len(result["warnings"]))

    if result["hard_blocks"]:
        st.error("Execução bloqueada pelo Safety Core.")
        with st.expander("Motivos do bloqueio"):
            for item in result["hard_blocks"]:
                st.write("•", item)
    elif result["warnings"]:
        st.warning("Contexto permitido apenas em modo de espera/confirmação.")
        with st.expander("Alertas do Safety Core"):
            for item in result["warnings"]:
                st.write("•", item)
    else:
        st.success("Nenhum veto adicional do Safety Core neste instante.")

    return result
