"""AION Business brain for the five approved revenue engines.

Pure/offline contracts. The brain can rank, deduplicate and prepare work in
parallel, but it never sends a message, spends money, publishes, contracts or
collects payment by itself. External actions are only eligible for a connector
after the explicit approval gate succeeds.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping, Sequence
import hashlib

from atlasquant_aion_core import is_admin

SCHEMA = "ATLASQUANT_AION_BUSINESS_BRAIN_V1"
MAX_OPPORTUNITIES = 500
TRUTH_STATES = ("CONFIRMED", "INFERENCE", "HYPOTHESIS", "UNKNOWN")
OPPORTUNITY_STATUSES = ("NEW", "RESEARCH", "READY", "WAITING_CUSTOMER", "WON", "LOST", "ARCHIVED")

BUSINESS_ENGINES = (
    {
        "rank": 1,
        "id": "automation_b2b",
        "title": "Automação B2B + Agentes de IA",
        "model": "Implantação + mensalidade recorrente",
        "aion_role": "Mapear processo, preparar proposta, desenhar automação e acompanhar o cliente.",
    },
    {
        "rank": 2,
        "id": "micro_saas",
        "title": "Micro-SaaS / Software próprio",
        "model": "Assinatura de solução repetível",
        "aion_role": "Detectar padrões repetidos nos clientes e propor produto padronizado.",
    },
    {
        "rank": 3,
        "id": "international_ai",
        "title": "Serviços de IA internacionais",
        "model": "Projetos e recorrência em moeda forte",
        "aion_role": "Preparar prospecção, proposta e atendimento multilíngue com contexto preservado.",
    },
    {
        "rank": 4,
        "id": "revenue_ops",
        "title": "Captação + Revenue Operations com IA",
        "model": "CRM, qualificação, follow-up e operação comercial",
        "aion_role": "Organizar leads, priorizar contatos, preparar follow-ups e medir conversão.",
    },
    {
        "rank": 5,
        "id": "digital_products",
        "title": "Produtos digitais próprios",
        "model": "Templates, guias, cursos e ativos digitais",
        "aion_role": "Transformar conhecimento validado das outras frentes em ativos vendáveis.",
    },
)

ENGINE_IDS = tuple(item["id"] for item in BUSINESS_ENGINES)
DEPRECATED_PRIMARY_FRONTS = (
    "dropshipping",
    "afiliados",
    "tiktok_shop",
    "mercado_livre",
    "ecommerce_generico",
    "assistente_virtual_basico",
    "white_label_generico",
)
EXTERNAL_ACTIONS = (
    "send_customer_message",
    "publish_offer",
    "spend_money",
    "sign_contract",
    "collect_payment",
)
ALWAYS_HUMAN_APPROVAL = frozenset(EXTERNAL_ACTIONS)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _text(value: Any, limit: int) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _bounded_score(value: Any) -> int:
    try:
        return max(0, min(100, int(round(float(value)))))
    except Exception:
        return 0


def _truth(value: Any) -> str:
    state = str(value or "UNKNOWN").strip().upper()
    return state if state in TRUTH_STATES else "UNKNOWN"


def business_engine_catalog() -> tuple[dict[str, Any], ...]:
    return tuple(dict(item) for item in BUSINESS_ENGINES)


def parallel_brain_contract() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "mode": "PARALLEL",
        "engines": ENGINE_IDS,
        "unified_inbox": True,
        "deduplicate": True,
        "cross_sell": True,
        "shared_customer_context": True,
        "daily_executive_brief": True,
        "per_engine_metrics": True,
        "prepares_internal_work": True,
        "external_actions_require_gate": True,
        "deprecated_primary_fronts": DEPRECATED_PRIMARY_FRONTS,
    }


def _opportunity_id(engine_id: str, title: str, source: str) -> str:
    raw = f"{engine_id}|{title.casefold()}|{source.casefold()}".encode("utf-8")
    return "OPP-" + hashlib.sha256(raw).hexdigest()[:12].upper()


def normalize_opportunity(raw: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise ValueError("invalid opportunity")
    engine_id = _text(raw.get("engine_id"), 80)
    if engine_id not in ENGINE_IDS:
        raise ValueError("unknown business engine")
    title = _text(raw.get("title"), 220)
    if not title:
        raise ValueError("opportunity title required")
    source = _text(raw.get("source"), 220)
    status = str(raw.get("status") or "NEW").strip().upper()
    if status not in OPPORTUNITY_STATUSES:
        status = "NEW"
    opportunity_id = _text(raw.get("opportunity_id"), 64) or _opportunity_id(engine_id, title, source)
    return {
        "schema": SCHEMA,
        "opportunity_id": opportunity_id,
        "engine_id": engine_id,
        "title": title,
        "summary": _text(raw.get("summary"), 1400),
        "source": source,
        "truth_state": _truth(raw.get("truth_state")),
        "status": status,
        "revenue_score": _bounded_score(raw.get("revenue_score")),
        "recurrence_score": _bounded_score(raw.get("recurrence_score")),
        "readiness_score": _bounded_score(raw.get("readiness_score")),
        "urgency_score": _bounded_score(raw.get("urgency_score")),
        "next_action": _text(raw.get("next_action"), 500),
        "customer_ref": _text(raw.get("customer_ref"), 220),
        "external_action": _text(raw.get("external_action"), 80),
        "updated_at": _text(raw.get("updated_at"), 80) or _now(),
    }


def opportunity_priority(raw: Mapping[str, Any]) -> int:
    item = normalize_opportunity(raw)
    weighted = (
        item["revenue_score"] * 0.35
        + item["recurrence_score"] * 0.30
        + item["readiness_score"] * 0.20
        + item["urgency_score"] * 0.15
    )
    return int(round(weighted))


def normalize_opportunities(rows: Sequence[Mapping[str, Any]] | None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in list(rows or [])[: MAX_OPPORTUNITIES * 2]:
        try:
            item = normalize_opportunity(raw)
        except Exception:
            continue
        dedupe_key = item["opportunity_id"]
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        item["priority_score"] = opportunity_priority(item)
        out.append(item)
        if len(out) >= MAX_OPPORTUNITIES:
            break
    out.sort(key=lambda x: (-int(x["priority_score"]), str(x["opportunity_id"])))
    return out


def unified_business_queue(rows: Sequence[Mapping[str, Any]] | None) -> dict[str, Any]:
    items = normalize_opportunities(rows)
    by_engine = {engine_id: 0 for engine_id in ENGINE_IDS}
    waiting_customer = 0
    external_pending = 0
    for item in items:
        by_engine[item["engine_id"]] += 1
        if item["status"] == "WAITING_CUSTOMER":
            waiting_customer += 1
        if item["external_action"] in EXTERNAL_ACTIONS:
            external_pending += 1
    return {
        "schema": SCHEMA,
        "total": len(items),
        "items": items,
        "by_engine": by_engine,
        "waiting_customer": waiting_customer,
        "external_pending": external_pending,
        "top": items[:10],
    }


def cross_sell_suggestions(rows: Sequence[Mapping[str, Any]] | None) -> list[dict[str, Any]]:
    items = normalize_opportunities(rows)
    customer_engines: dict[str, set[str]] = {}
    for item in items:
        customer = item["customer_ref"]
        if customer:
            customer_engines.setdefault(customer, set()).add(item["engine_id"])
    suggestions: list[dict[str, Any]] = []
    for customer, engines in sorted(customer_engines.items()):
        if "automation_b2b" in engines and "revenue_ops" not in engines:
            suggestions.append({
                "customer_ref": customer,
                "from_engine": "automation_b2b",
                "suggest_engine": "revenue_ops",
                "reason": "Cliente de automação pode se beneficiar de CRM, qualificação e follow-up.",
            })
        if "automation_b2b" in engines and "micro_saas" not in engines:
            suggestions.append({
                "customer_ref": customer,
                "from_engine": "automation_b2b",
                "suggest_engine": "micro_saas",
                "reason": "Fluxo repetível pode revelar uma oportunidade de produto padronizado.",
            })
    return suggestions[:100]


def external_action_preflight(
    action: Any,
    access: Mapping[str, Any] | None,
    *,
    approved: bool = False,
    connector_ready: bool = False,
) -> dict[str, Any]:
    action_id = _text(action, 80)
    known = action_id in EXTERNAL_ACTIONS
    admin = bool(is_admin(access))
    allowed = bool(known and admin and approved and connector_ready)
    if not known:
        reason = "Ação externa desconhecida."
    elif not admin:
        reason = "ADMIN obrigatório."
    elif not approved:
        reason = "Aprovação humana explícita obrigatória."
    elif not connector_ready:
        reason = "Conector externo não confirmado."
    else:
        reason = "Elegível para o conector autorizado."
    return {
        "schema": SCHEMA,
        "action": action_id,
        "allowed": allowed,
        "requires_human_approval": action_id in ALWAYS_HUMAN_APPROVAL,
        "connector_ready": bool(connector_ready),
        "reason": reason,
        "executes_action": False,
    }


def brain_snapshot(rows: Sequence[Mapping[str, Any]] | None) -> dict[str, Any]:
    queue = unified_business_queue(rows)
    return {
        "schema": SCHEMA,
        "contract": parallel_brain_contract(),
        "queue": queue,
        "cross_sell": cross_sell_suggestions(rows),
        "active_engines": len(ENGINE_IDS),
        "external_execution": False,
    }


__all__ = [
    "SCHEMA",
    "BUSINESS_ENGINES",
    "ENGINE_IDS",
    "DEPRECATED_PRIMARY_FRONTS",
    "EXTERNAL_ACTIONS",
    "business_engine_catalog",
    "parallel_brain_contract",
    "normalize_opportunity",
    "normalize_opportunities",
    "opportunity_priority",
    "unified_business_queue",
    "cross_sell_suggestions",
    "external_action_preflight",
    "brain_snapshot",
]
