"""AtlasQuant adaptive coverage execution gate.

Research-only permission layer for the future 28-pair architecture. Background
pairs can never become execution-grade. Active pairs still need fresh M15,
complete derived H1/H4, sufficient data, and no existing hard block.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence
import math


VERSION="AtlasQuant Adaptive Execution Gate V1"


def _finite(value: Any) -> float | None:
    try:
        out=float(value)
        return out if math.isfinite(out) else None
    except Exception:
        return None


def adaptive_pair_permission(
    pair: str,
    *,
    active_pairs: Sequence[str],
    m15_age_minutes: float | None,
    derived_health: Mapping[str,Any] | None,
    data_sufficient: bool,
    hard_blocks: Sequence[str] | None = None,
    max_active_m15_age_min: float = 60.0,
) -> dict[str,Any]:
    p=str(pair or "").upper().strip()
    active={str(x).upper().strip() for x in active_pairs}
    tier="ACTIVE" if p in active else "BACKGROUND"
    blockers=[]

    if tier!="ACTIVE":
        blockers.append("Par fora do conjunto ativo; cobertura apenas de contexto")

    age=_finite(m15_age_minutes)
    if age is None:
        blockers.append("Frescor M15 indisponível")
    elif age < 0:
        blockers.append("Timestamp M15 futuro/inválido")
    elif age > float(max_active_m15_age_min):
        blockers.append(f"M15 acima do limite ativo ({age:.1f} min)")

    health=dict(derived_health or {})
    if not bool(health.get("h1_ready",False)):
        blockers.append("H1 derivado ainda não possui histórico completo suficiente")
    if not bool(health.get("h4_ready",False)):
        blockers.append("H4 derivado ainda não possui histórico completo suficiente")
    if not bool(health.get("strict_complete_groups",False)):
        blockers.append("Derivação de timeframe sem confirmação de grupos completos")
    if not bool(data_sufficient):
        blockers.append("Dados operacionais insuficientes")

    blockers.extend(str(x) for x in (hard_blocks or []) if str(x).strip())
    executable=not blockers and tier=="ACTIVE"

    return {
        "pair":p,
        "tier":tier,
        "executable":bool(executable),
        "state":"SEARCH_ENTRY_ELIGIBLE" if executable else "NO_EXECUTION",
        "blockers":blockers,
        "m15_age_minutes":age,
        "max_active_m15_age_min":float(max_active_m15_age_min),
        "version":VERSION,
        "automatic_live_wiring_allowed":False,
    }


def active_set_integrity(
    permissions: Sequence[Mapping[str,Any]] | None,
    *,
    expected_active_pairs: Sequence[str],
) -> dict[str,Any]:
    rows=[dict(x) for x in (permissions or [])]
    expected={str(x).upper().strip() for x in expected_active_pairs}
    active_rows=[x for x in rows if str(x.get("tier","")).upper()=="ACTIVE"]
    actual={str(x.get("pair","")).upper().strip() for x in active_rows}
    background_executable=[
        str(x.get("pair",""))
        for x in rows
        if str(x.get("tier","")).upper()=="BACKGROUND" and bool(x.get("executable",False))
    ]
    return {
        "active_set_matches":actual==expected,
        "expected_active_count":len(expected),
        "actual_active_count":len(actual),
        "background_executable_pairs":background_executable,
        "background_execution_violation":bool(background_executable),
        "integrity_ok":bool(actual==expected and not background_executable),
        "automatic_live_wiring_allowed":False,
    }
