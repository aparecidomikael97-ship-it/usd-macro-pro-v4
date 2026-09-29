"""AION Admin Copilot V1.

Read-only synthesis for the AtlasQuant administrator.

The Copilot consumes already-computed reports (Master Status Board, System
Health Center, Cost Center, staged-release matrix, Incident Center, Executive
Pulse and optional Reliability evidence) and produces a compact, traceable
briefing of priorities, blockers and safe next actions.

It does not fetch providers, modify checkpoints, approve requests, change
feature flags, promote trading setups, deploy, publish, bill or enable trading.
Missing evidence remains UNKNOWN and never becomes a positive claim.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence
import re


SCHEMA = "ATLASQUANT_AION_ADMIN_COPILOT_V1"

PRIORITIES = ("P0", "P1", "P2", "P3")
TRUTH_STATES = ("CONFIRMED", "BLOCKED", "UNKNOWN")
_PRIORITY_RANK = {name: idx for idx, name in enumerate(PRIORITIES)}

_SECRET_PATTERNS = (
    re.compile(r"(?i)\b(api[_-]?key|token|password|secret|credential)\s*[:=]\s*[^\s,;]+"),
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]+"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{8,}\b"),
)


def _text(value: Any, limit: int = 500) -> str:
    if not isinstance(value, str):
        return ""
    cleaned = " ".join(value.replace("\x00", "").split())
    for pattern in _SECRET_PATTERNS:
        cleaned = pattern.sub("[REDACTED]", cleaned)
    return cleaned[:limit]


def _priority(value: Any, default: str = "P3") -> str:
    raw = _text(value, 16).upper()
    return raw if raw in PRIORITIES else default


def _truth(value: Any) -> str:
    raw = _text(value, 32).upper()
    if raw in {"CONFIRMED", "HEALTHY", "CONTROLLED", "ELIGIBLE"}:
        return "CONFIRMED"
    if raw in {
        "BLOCKED",
        "CRITICAL",
        "FAIL_CLOSED",
        "BLOCKED_LIMIT",
        "UNAVAILABLE",
    }:
        return "BLOCKED"
    return "UNKNOWN"


def _recommendation(
    *,
    recommendation_id: str,
    priority: str,
    title: Any,
    detail: Any,
    next_action: Any,
    source: Any,
    truth_state: str,
    area: Any = "central",
) -> dict[str, Any]:
    truth = _truth(truth_state)
    return {
        "id": _text(recommendation_id, 100),
        "priority": _priority(priority),
        "title": _text(title, 180),
        "detail": _text(detail, 700),
        "next_action": _text(next_action, 700),
        "source": _text(source, 240),
        "area": _text(area, 100) or "central",
        "truth_state": truth,
        "executes_action": False,
        "automatic_approval": False,
        "automatic_feature_change": False,
        "automatic_setup_promotion": False,
        "real_trading_enabled": False,
    }


def _status_board_recommendations(
    board: Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    data = dict(board or {})
    out: list[dict[str, Any]] = []
    attention = [
        dict(item) for item in list(data.get("attention") or [])
        if isinstance(item, Mapping)
    ]
    for item in attention[:20]:
        state = _text(item.get("state"), 40).upper()
        if state == "BLOCKED":
            priority = "P1"
            truth = "BLOCKED"
        elif state == "EXTERNAL_DEPENDENCY":
            priority = "P2"
            truth = "UNKNOWN"
        else:
            priority = "P3"
            truth = "UNKNOWN"
        out.append(_recommendation(
            recommendation_id=f"status:{_text(item.get('id'),80)}",
            priority=priority,
            title=item.get("label") or "Item do Status Board",
            detail=item.get("detail") or "Há um item pendente no Status Board.",
            next_action=item.get("next_action") or "Revisar a evidência antes de avançar.",
            source=item.get("source") or "master_status_board",
            truth_state=truth,
            area=item.get("area") or "system",
        ))
    return out


def _incident_recommendations(
    incidents: Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    data = dict(incidents or {})
    out: list[dict[str, Any]] = []
    for item in list(data.get("incidents") or [])[:20]:
        if not isinstance(item, Mapping):
            continue
        severity = _text(item.get("severity"), 40).upper()
        priority = (
            "P0" if severity == "CRITICAL"
            else "P1" if severity == "HIGH"
            else "P2" if severity in {"MEDIUM", "LOW"}
            else "P3"
        )
        evidence = _text(item.get("evidence_state"), 40).upper()
        truth = "CONFIRMED" if evidence == "CONFIRMED" else "UNKNOWN"
        out.append(_recommendation(
            recommendation_id=f"incident:{_text(item.get('incident_id'),80)}",
            priority=priority,
            title=item.get("title") or "Incidente",
            detail=item.get("detail") or "Incidente consolidado pelo Incident Center.",
            next_action=(
                "Abrir o Incident Center e revisar a resposta humana recomendada; "
                "o Copiloto não executa contenção."
            ),
            source=item.get("source") or "incident_center",
            truth_state=truth,
            area="development",
        ))
    return out


def _health_recommendations(
    health: Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    data = dict(health or {})
    out: list[dict[str, Any]] = []
    for item in list(data.get("items") or [])[:12]:
        if not isinstance(item, Mapping):
            continue
        state = _text(item.get("state"), 40).upper()
        if state == "HEALTHY":
            continue
        priority = "P1" if state == "BLOCKED" else "P2"
        truth = "BLOCKED" if state == "BLOCKED" else "UNKNOWN"
        out.append(_recommendation(
            recommendation_id=f"health:{_text(item.get('id'),80)}",
            priority=priority,
            title=f"Saúde: {_text(item.get('label'),120) or _text(item.get('id'),80)}",
            detail=item.get("detail") or f"Domínio de saúde está {state or 'UNKNOWN'}.",
            next_action="Revisar a evidência desse domínio; não executar reparo automático.",
            source="system_health_center",
            truth_state=truth,
            area="system",
        ))
    return out


def _cost_recommendations(
    cost: Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    data = dict(cost or {})
    if not data:
        return []
    state = _text(data.get("state"), 40).upper()
    if state == "CONFIRMED":
        return []
    return [_recommendation(
        recommendation_id="cost:evidence",
        priority="P2",
        title="Custos ainda não estão totalmente confirmados",
        detail=(
            f"Estado do Cost Center: {state or 'UNKNOWN'} · "
            f"confirmado US$ {float(data.get('confirmed_monthly_usd') or 0):.2f}/mês · "
            f"estimado US$ {float(data.get('estimated_monthly_usd') or 0):.2f}/mês."
        ),
        next_action=(
            "Adicionar ou revisar evidência de custo. Estimativa não deve ser tratada "
            "como cobrança ou gasto confirmado."
        ),
        source="cost_center",
        truth_state="UNKNOWN",
        area="system",
    )]


def _release_recommendations(
    matrix: Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    data = dict(matrix or {})
    out: list[dict[str, Any]] = []
    for item in list(data.get("items") or [])[:30]:
        if not isinstance(item, Mapping):
            continue
        state = _text(item.get("state"), 40).upper()
        if state == "ELIGIBLE":
            continue
        feature = _text(item.get("feature"), 80) or "feature"
        if state == "BLOCKED":
            priority = "P1"
            truth = "BLOCKED"
        elif state == "HUMAN_REVIEW_READY":
            priority = "P2"
            truth = "CONFIRMED"
        else:
            priority = "P2"
            truth = "UNKNOWN"
        missing = ", ".join(
            _text(x, 80) for x in list(item.get("missing_evidence") or [])[:8]
        )
        out.append(_recommendation(
            recommendation_id=f"release:{feature}",
            priority=priority,
            title=f"Liberação em camadas: {feature}",
            detail=(
                f"Camada solicitada {_text(item.get('requested_layer'),40) or 'UNKNOWN'} · "
                f"estado {state or 'UNKNOWN'}"
                + (f" · evidência faltante: {missing}" if missing else "")
                + "."
            ),
            next_action=(
                "Revisar evidências/aprovação manual. O Copiloto não altera a feature flag."
            ),
            source="release_layers",
            truth_state=truth,
            area="development",
        ))
    return out


def _executive_recommendation(
    executive: Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    data = dict(executive or {})
    primary = data.get("primary") if isinstance(data.get("primary"), Mapping) else {}
    if not primary:
        return []
    title = _text(primary.get("title"), 180)
    if not title:
        return []
    return [_recommendation(
        recommendation_id="executive:primary",
        priority=primary.get("priority") or "P2",
        title=title,
        detail=primary.get("detail"),
        next_action=primary.get("next_action"),
        source=primary.get("source") or "executive_pulse",
        truth_state=(
            "BLOCKED"
            if _text(data.get("posture"),40).upper() == "CRITICAL"
            else "CONFIRMED"
            if _text(data.get("posture"),40).upper() in {"ATTENTION","REVIEW","CONTROLLED"}
            else "UNKNOWN"
        ),
        area=primary.get("area") or data.get("recommended_workspace") or "central",
    )]


def build_admin_copilot(
    *,
    status_board: Mapping[str, Any] | None = None,
    system_health_center: Mapping[str, Any] | None = None,
    cost_center: Mapping[str, Any] | None = None,
    release_matrix: Mapping[str, Any] | None = None,
    incident_snapshot: Mapping[str, Any] | None = None,
    executive_snapshot: Mapping[str, Any] | None = None,
    reliability_snapshot: Mapping[str, Any] | None = None,
    max_items: Any = 8,
) -> dict[str, Any]:
    """Build a compact admin briefing from existing evidence only."""
    try:
        limit = int(max_items)
    except (TypeError, ValueError):
        limit = 8
    if isinstance(max_items, bool):
        limit = 8
    limit = min(12, max(1, limit))

    rows: list[dict[str, Any]] = []
    rows.extend(_executive_recommendation(executive_snapshot))
    rows.extend(_incident_recommendations(incident_snapshot))
    rows.extend(_health_recommendations(system_health_center))
    rows.extend(_release_recommendations(release_matrix))
    rows.extend(_cost_recommendations(cost_center))
    rows.extend(_status_board_recommendations(status_board))

    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for row in rows:
        key = (row["title"].casefold(), row["source"].casefold())
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)

    deduped.sort(
        key=lambda row: (
            _PRIORITY_RANK.get(row["priority"], 9),
            0 if row["truth_state"] == "BLOCKED" else 1,
            row["title"].casefold(),
        )
    )
    selected = deduped[:limit]

    reliability = dict(reliability_snapshot or {})
    reliability_posture = _text(reliability.get("posture"), 40).upper() or "UNKNOWN"

    if any(row["priority"] == "P0" for row in selected):
        state = "CRITICAL"
    elif any(row["priority"] == "P1" for row in selected):
        state = "ATTENTION"
    elif selected:
        state = "REVIEW"
    elif reliability_posture == "CONTROLLED":
        state = "CONTROLLED"
    else:
        state = "UNKNOWN"

    return {
        "schema": SCHEMA,
        "state": state,
        "items": selected,
        "items_total_before_limit": len(deduped),
        "attention_count": len(selected),
        "primary": selected[0] if selected else None,
        "reliability_posture": reliability_posture,
        "evidence_only": True,
        "promotes_setup": False,
        "automatic_setup_promotion": False,
        "automatic_approval": False,
        "automatic_feature_change": False,
        "automatic_repair": False,
        "automatic_deploy": False,
        "automatic_publish": False,
        "automatic_charge": False,
        "real_trading_enabled": False,
        "executes_action": False,
        "interpretation": (
            "O Copiloto Admin prioriza relatórios já calculados. Ele não cria "
            "evidência, não amplia permissões e não executa a próxima ação."
        ),
    }


def compact_admin_copilot_rows(
    copilot: Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    """Presentation-only compact rows."""
    out = []
    for item in list((copilot or {}).get("items") or []):
        if not isinstance(item, Mapping):
            continue
        out.append({
            "Prioridade": _priority(item.get("priority")),
            "Área": _text(item.get("area"), 100),
            "Item": _text(item.get("title"), 180),
            "Evidência": _truth(item.get("truth_state")),
            "Próxima ação": _text(item.get("next_action"), 400),
        })
    return out


__all__ = [
    "SCHEMA",
    "PRIORITIES",
    "TRUTH_STATES",
    "build_admin_copilot",
    "compact_admin_copilot_rows",
]
