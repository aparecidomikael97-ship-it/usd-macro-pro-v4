"""AION BUSINESS Client Portal Demo V1.

Read-only, fixture-first client experience. It converts an already-generated
demo diagnostic/proposal into a simple portal view. No live client connection,
billing, publication, contract execution, external messaging, deploy or runtime
activation exists in this module.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

SCHEMA = "ATLASQUANT_AION_BUSINESS_CLIENT_PORTAL_DEMO_V1"
VERSION = "1"

SECTIONS = (
    "VISÃO GERAL",
    "RADAR",
    "PLANO DE AÇÃO",
    "RESULTADOS",
    "SUPORTE",
    "HISTÓRICO",
)

STATUS_ORDER = ("CRITICAL", "ATTENTION", "WATCH", "STABLE", "UNKNOWN")


def _clean(value: Any, limit: int = 500) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _seq(value: Any, limit: int = 20) -> list[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return list(value)[:limit]


def _score_state(score: Any) -> str:
    if isinstance(score, bool):
        return "UNKNOWN"
    try:
        value = float(score)
    except Exception:
        return "UNKNOWN"
    if value < 35:
        return "CRITICAL"
    if value < 60:
        return "ATTENTION"
    if value < 80:
        return "WATCH"
    return "STABLE"


def _severity_rank(value: Any) -> int:
    token = _clean(value, 30).upper() or "UNKNOWN"
    try:
        return STATUS_ORDER.index(token)
    except ValueError:
        return STATUS_ORDER.index("UNKNOWN")


def build_client_portal_demo(
    diagnostic: Mapping[str, Any] | None,
    radar: Mapping[str, Any] | None,
    package_fit: Mapping[str, Any] | None,
    proposal_draft: Mapping[str, Any] | None,
) -> dict[str, Any]:
    diag = _mapping(diagnostic)
    radar_row = _mapping(radar)
    fit = _mapping(package_fit)
    proposal_row = _mapping(proposal_draft)
    proposal = _mapping(proposal_row.get("proposal"))
    intake = _mapping(diag.get("intake"))

    company = _clean(intake.get("company_name"), 120) or "Empresa Demo"
    segment = _clean(intake.get("segment"), 120) or "Segmento Demo"

    radar_cards = []
    for item in _seq(radar_row.get("cards"), 4):
        row = _mapping(item)
        score = row.get("health_score")
        radar_cards.append({
            "label": _clean(row.get("label"), 80) or "Área",
            "health_score": int(score) if isinstance(score, (int, float)) and not isinstance(score, bool) else 0,
            "state": _clean(row.get("state"), 40) or _score_state(score),
        })

    actions = []
    for item in _seq(radar_row.get("next_actions"), 8):
        row = _mapping(item)
        actions.append({
            "title": _clean(row.get("title"), 180),
            "severity": _clean(row.get("severity"), 40) or "UNKNOWN",
            "recommendation": _clean(row.get("recommendation"), 400),
            "status": "PENDING_REVIEW",
        })
    actions.sort(key=lambda x: (_severity_rank(x["severity"]), x["title"]))

    deliverables = [_clean(x, 300) for x in _seq(fit.get("deliverables"), 12)]
    deliverables = [x for x in deliverables if x]
    monthly = [_clean(x, 300) for x in _seq(proposal.get("monthly_maintenance"), 12)]
    monthly = [x for x in monthly if x]

    portal = {
        "schema": SCHEMA,
        "version": VERSION,
        "mode": "DEMO_ONLY",
        "company": company,
        "segment": segment,
        "headline": "Veja rapidamente o que está acontecendo e o próximo passo.",
        "tagline": "Poderoso por dentro. Simples por fora.",
        "sections": list(SECTIONS),
        "package": {
            "id": _clean(fit.get("package_id"), 80),
            "label": _clean(fit.get("package_label"), 160) or "A DEFINIR",
            "deliverables": deliverables,
            "price_state": _clean(fit.get("price_state"), 80) or "TO_DEFINE_AFTER_SCOPE",
        },
        "radar": {
            "headline": _clean(radar_row.get("headline"), 240),
            "cards": radar_cards,
            "source": "DEMO_USER_INPUT",
        },
        "action_plan": actions,
        "results": {
            "state": "NO_REAL_RESULTS",
            "message": (
                "Resultados reais só aparecem depois de implantação, fonte confiável e período de medição. "
                "Esta demonstração não inventa desempenho."
            ),
            "metrics": [],
        },
        "support": {
            "state": "DEMO",
            "sla_state": "TO_DEFINE_IN_SCOPE",
            "open_tickets": 0,
            "critical_incidents": 0,
            "contact_channel": "A DEFINIR NO ONBOARDING",
        },
        "history": [
            {
                "event": "DEMO_CREATED",
                "label": "Portal de demonstração criado",
                "timestamp": "DEMO",
            }
        ],
        "maintenance": {
            "enabled_in_model": bool(monthly),
            "items": monthly,
            "billing_state": "NOT_CONFIGURED",
        },
        "proposal": {
            "state": _clean(proposal_row.get("state"), 60) or "NOT_AVAILABLE",
            "sent": bool(proposal.get("sent")) if type(proposal.get("sent")) is bool else False,
            "signed": bool(proposal.get("signed")) if type(proposal.get("signed")) is bool else False,
        },
        "data_state": {
            "real_client_connected": False,
            "real_client_verified": False,
            "demo_fixture_only": True,
        },
        "runtime_state": "OFF",
        "external_actions_state": "OFF",
        "payment_state": "OFF",
        "publication_state": "OFF",
        "executes_action": False,
    }
    return portal


def portal_attention_summary(portal: Mapping[str, Any] | None) -> dict[str, Any]:
    row = _mapping(portal)
    actions = [_mapping(x) for x in _seq(row.get("action_plan"), 20)]
    critical = [x for x in actions if _clean(x.get("severity"), 40).upper() == "CRITICAL"]
    high = [x for x in actions if _clean(x.get("severity"), 40).upper() == "HIGH"]
    medium = [x for x in actions if _clean(x.get("severity"), 40).upper() in {"MEDIUM", "ATTENTION"}]
    if critical:
        state = "CRITICAL"
    elif high:
        state = "ATTENTION"
    elif medium:
        state = "WATCH"
    elif actions:
        state = "WATCH"
    else:
        state = "STABLE"
    return {
        "schema": SCHEMA,
        "state": state,
        "critical_count": len(critical),
        "high_count": len(high),
        "attention_count": len(medium),
        "pending_actions": len(actions),
        "headline": {
            "CRITICAL": "Há itens críticos para revisão.",
            "ATTENTION": "Há prioridades importantes para revisar.",
            "WATCH": "Existem pontos para acompanhar.",
            "STABLE": "Nenhuma prioridade básica apareceu neste demo.",
        }[state],
        "executes_action": False,
    }


def portal_section(portal: Mapping[str, Any] | None, section: Any) -> dict[str, Any]:
    row = _mapping(portal)
    token = _clean(section, 80).upper()
    if token not in SECTIONS:
        return {
            "schema": SCHEMA,
            "state": "UNKNOWN_SECTION",
            "section": "",
            "payload": {},
            "executes_action": False,
        }

    mapping = {
        "VISÃO GERAL": {
            "company": row.get("company"),
            "segment": row.get("segment"),
            "headline": row.get("headline"),
            "package": row.get("package"),
            "attention": portal_attention_summary(row),
        },
        "RADAR": row.get("radar"),
        "PLANO DE AÇÃO": row.get("action_plan"),
        "RESULTADOS": row.get("results"),
        "SUPORTE": row.get("support"),
        "HISTÓRICO": row.get("history"),
    }
    return {
        "schema": SCHEMA,
        "state": "DEMO",
        "section": token,
        "payload": mapping[token],
        "runtime_state": "OFF",
        "external_actions_state": "OFF",
        "executes_action": False,
    }


def append_demo_history(
    portal: Mapping[str, Any] | None,
    *,
    event: Any,
    label: Any,
) -> dict[str, Any]:
    """Session-copy helper; does not persist externally."""
    row = _mapping(portal)
    history = [dict(x) for x in _seq(row.get("history"), 50) if isinstance(x, Mapping)]
    event_token = _clean(event, 80).upper()
    label_text = _clean(label, 240)
    if not event_token or not label_text:
        return row
    history.append({
        "event": event_token,
        "label": label_text,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    out = dict(row)
    out["history"] = history[-50:]
    out["executes_action"] = False
    out["runtime_state"] = "OFF"
    out["external_actions_state"] = "OFF"
    return out


__all__ = [
    "SCHEMA",
    "VERSION",
    "SECTIONS",
    "build_client_portal_demo",
    "portal_attention_summary",
    "portal_section",
    "append_demo_history",
]
