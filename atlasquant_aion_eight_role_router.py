"""Deterministic router for the eight logical roles inside one AION nucleus.

This is orchestration metadata only. It does not create eight independent AIs,
call a model/provider, execute a tool, widen permissions, write memory, spend
money, deploy, publish or trade.

The domain router answers "where?" (Trader, Business, Investments, Core).
This router answers "which internal AION role(s) should review this task?".
"""
from __future__ import annotations

from typing import Any, Mapping
import re
import unicodedata

SCHEMA = "ATLASQUANT_AION_EIGHT_ROLE_ROUTER_V1"
VERSION = "1"
MAX_ACTIVE_ROLES = 4

ROLE_IDS = (
    "orchestrator",
    "architect",
    "guardian",
    "executor",
    "memory",
    "finops",
    "reliability",
    "customer_success",
)

ROLE_ACTIONS = {
    "orchestrator": ("coordinate", "read", "route"),
    "architect": ("analyze", "propose", "draft_design"),
    "guardian": ("review", "audit", "block"),
    "executor": ("prepare_execution_plan",),
    "memory": ("read_checkpoint", "propose_memory_update"),
    "finops": ("analyze_cost", "analyze_margin", "budget_guard"),
    "reliability": ("health_review", "incident_review", "recovery_plan"),
    "customer_success": ("analyze_client", "draft_onboarding", "draft_support"),
}

_ROLE_MARKERS = {
    "architect": (
        "arquitet", "architecture", "melhor", "upgrade", "atualiza",
        "integracao", "integração", "desenvolv", "codigo", "código",
        "refator", "projeto", "sistema", "interface",
    ),
    "guardian": (
        "segur", "risco", "lgpd", "privacy", "privacidade", "permiss",
        "audit", "compliance", "rollback", "aprova", "autoriz",
    ),
    "executor": (
        "execut", "aplica", "implementar", "implemente", "cria", "crie",
        "envia", "envie", "publica", "publique", "deploy", "merge",
        "ativar", "ative", "alterar", "altere",
    ),
    "memory": (
        "checkpoint", "memoria", "memória", "histor", "decisao", "decisão",
        "lembra", "contexto", "document", "continuidade",
    ),
    "finops": (
        "custo", "budget", "orcamento", "orçamento", "margem", "receita",
        "lucro", "finops", "api", "capital", "tesouraria", "mensalidade",
        "rentabilidade",
    ),
    "reliability": (
        "backup", "incidente", "falha", "erro", "health", "saude", "saúde",
        "latencia", "latência", "recuper", "observabilidade", "monitor",
        "degrad", "disponibilidade",
    ),
    "customer_success": (
        "cliente", "customer", "onboarding", "suporte", "sla", "churn",
        "retenc", "retenç", "satisfacao", "satisfação", "venda", "comercial",
        "lead", "renovacao", "renovação",
    ),
}

_CRITICAL_MARKERS = (
    "deploy", "merge", "pagamento", "payment", "charge", "cobranca", "cobrança",
    "publica", "publish", "trade real", "real trade", "corretora", "broker",
    "segredo", "secret", "delete", "delet", "excluir", "runtime", "transfer",
)

_PRIORITY = {
    "guardian": 100,
    "executor": 90,
    "finops": 70,
    "reliability": 70,
    "memory": 65,
    "customer_success": 60,
    "architect": 55,
}


def _fold(value: Any) -> str:
    raw = str(value or "").replace("\x00", " ").strip()
    normalized = unicodedata.normalize("NFKD", raw).casefold()
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def _bounded_intent(value: Any) -> str:
    text = _fold(value)
    if not text or len(text) > 8000:
        return ""
    return " ".join(text.split())


def _checkpoint_roles(snapshot: Mapping[str, Any] | None) -> tuple[str, ...]:
    if not isinstance(snapshot, Mapping):
        return ()
    if snapshot.get("state") != "MASTER_CHECKPOINT_LOADED":
        return ()
    if snapshot.get("evidence_ready") is not True:
        return ()
    raw = snapshot.get("multiagent_roles")
    if not isinstance(raw, list):
        return ()
    return tuple(
        str(item.get("id") or "")
        for item in raw
        if isinstance(item, Mapping)
    )


def role_registry(checkpoint_snapshot: Mapping[str, Any] | None) -> dict[str, Any]:
    checkpoint_roles = _checkpoint_roles(checkpoint_snapshot)
    valid = checkpoint_roles == ROLE_IDS
    rows = []
    if valid:
        for role_id in ROLE_IDS:
            rows.append({
                "role_id": role_id,
                "allowed_actions": list(ROLE_ACTIONS[role_id]),
                "independent_ai": False,
                "shares_infrastructure": True,
                "physical_execution_authorized": False,
                "permission_escalation_allowed": False,
            })
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "EIGHT_ROLE_REGISTRY_VALID" if valid else "EIGHT_ROLE_REGISTRY_BLOCKED",
        "roles": rows,
        "role_count": len(rows),
        "one_aion_nucleus": True,
        "independent_ai_count": 0,
        "model_invocation_authorized": False,
        "physical_execution_authorized": False,
        "executes_action": False,
    }


def route_logical_roles(
    intent: Any,
    checkpoint_snapshot: Mapping[str, Any] | None,
) -> dict[str, Any]:
    registry = role_registry(checkpoint_snapshot)
    text = _bounded_intent(intent)
    if registry.get("state") != "EIGHT_ROLE_REGISTRY_VALID" or not text:
        return {
            "schema": SCHEMA,
            "version": VERSION,
            "state": "LOGICAL_ROLE_ROUTE_BLOCKED",
            "reason": (
                "CHECKPOINT_ROLE_REGISTRY_INVALID"
                if registry.get("state") != "EIGHT_ROLE_REGISTRY_VALID"
                else "INTENT_INVALID"
            ),
            "selected_roles": [],
            "primary_role": "",
            "reasoning_tier": "NONE",
            "separate_gate_required": False,
            "model_invocation_authorized": False,
            "physical_execution_authorized": False,
            "permission_escalation_allowed": False,
            "executes_action": False,
        }

    scores: dict[str, int] = {}
    for role_id, markers in _ROLE_MARKERS.items():
        score = sum(1 for marker in markers if marker in text)
        if score:
            scores[role_id] = score

    critical = any(marker in text for marker in _CRITICAL_MARKERS)
    if critical:
        scores["guardian"] = max(scores.get("guardian", 0), 3)
        scores["executor"] = max(scores.get("executor", 0), 2)

    ranked = sorted(
        scores,
        key=lambda role_id: (
            -scores[role_id],
            -_PRIORITY.get(role_id, 0),
            role_id,
        ),
    )
    selected = ["orchestrator"]
    for role_id in ranked:
        if role_id not in selected:
            selected.append(role_id)
        if len(selected) >= MAX_ACTIVE_ROLES:
            break

    specialist_count = len(selected) - 1
    if critical:
        tier = "STRONG_REVIEW"
    elif specialist_count >= 2:
        tier = "SHARED_STANDARD"
    else:
        tier = "LOCAL_LIGHT"

    primary = selected[1] if len(selected) > 1 else "orchestrator"
    role_rows = {
        row["role_id"]: row
        for row in registry["roles"]
    }

    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "LOGICAL_ROLE_ROUTE_READY",
        "reason": "DETERMINISTIC_ROLE_ROUTING",
        "primary_role": primary,
        "selected_roles": selected,
        "selected_role_contracts": [
            role_rows[role_id] for role_id in selected
        ],
        "scores": {key: scores[key] for key in sorted(scores)},
        "reasoning_tier": tier,
        "separate_gate_required": critical,
        "one_aion_nucleus": True,
        "independent_ais_created": 0,
        "model_invocation_authorized": False,
        "automatic_paid_model_upgrade": False,
        "physical_execution_authorized": False,
        "permission_escalation_allowed": False,
        "memory_write_authorized": False,
        "budget_increase_authorized": False,
        "trade_authorized": False,
        "deploy_authorized": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "VERSION",
    "MAX_ACTIVE_ROLES",
    "ROLE_IDS",
    "ROLE_ACTIONS",
    "role_registry",
    "route_logical_roles",
]
