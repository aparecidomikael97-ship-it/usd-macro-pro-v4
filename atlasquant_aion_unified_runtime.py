"""Thin unified facade for the existing AION Core.

This module intentionally does not create another orchestrator. It composes the
existing orchestration, cognitive routing, truth, authorization, model routing
and action-receipt contracts behind one request/response envelope.

It performs no provider call, no external action, no real-money trading, no
automatic memory promotion and no automatic Checkpoint Mestre persistence.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence
import unicodedata
from uuid import uuid4

from aion_chat.authorization import classify_action
from aion_chat.contracts import CheckpointMasterAdapter
from aion_chat.models import ActionClass, Scope
from atlasquant_aion_action_receipt import seal_action_receipt
from atlasquant_aion_cognitive_orchestrator import route_specialists
from atlasquant_aion_internal_roles import internal_roles_snapshot
from atlasquant_aion_model_router import route_intelligence
from atlasquant_aion_orchestrator import orchestrate
from atlasquant_aion_truth import assess_truth

SCHEMA = "ATLASQUANT_AION_UNIFIED_RUNTIME_V1"

OFFICIAL_ROLES = (
    ("orchestrator", "Orquestrador / Núcleo"),
    ("architect", "Arquiteto / Estrategista"),
    ("guardian", "Guardião / Auditor"),
    ("prime", "Prime / Execução"),
    ("shadow", "Shadow / Pesquisa e Triagem"),
    ("sentinel", "Sentinel / Monitoramento"),
    ("commercial", "Comercial / Leads e CRM"),
    ("educator", "Educador / Treinamento"),
)

# Existing role IDs stay readable for backward compatibility. They are
# capabilities/responsibilities inside one shared Core, never independent AIs.
LEGACY_ROLE_COMPATIBILITY = {
    "orchestrator": ("orchestrator",),
    "architect": ("architect",),
    "guardian": ("guardian",),
    "prime": ("executor",),
    "shadow": ("memory",),
    "sentinel": ("observability",),
    "commercial": ("customer_success",),
    "educator": (),
}

_ORCHESTRATOR_ACTION = {
    "query": "read",
    "explain": "read",
    "verify": "read",
    "analyze": "read",
    "draft": "draft",
    "report": "draft",
    "create_task": "draft",
    "publish": "publish",
    "email": "publish",
    "merge": "merge_main",
    "deploy": "deploy_production",
    "spend": "charge_customer",
    "credentials": "read_secret",
    "open_trader": "real_trade",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(value: Any, limit: int = 4000) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _norm(value: Any) -> str:
    raw = unicodedata.normalize("NFKD", str(value or ""))
    return "".join(ch for ch in raw if not unicodedata.combining(ch)).casefold()


@dataclass(frozen=True)
class AionRequest:
    conversation_id: str
    owner_id: str
    tenant_id: str
    workspace_id: str
    user_message: str
    request_id: str = field(default_factory=lambda: uuid4().hex)
    sector: str = "central"
    attachments: tuple[str, ...] = ()
    requested_action: str = "query"
    current_mode: str = "BEGINNER"
    source_context: Mapping[str, Any] = field(default_factory=dict)
    authorization_context: Mapping[str, Any] = field(default_factory=dict)
    evidence: tuple[Mapping[str, Any], ...] = ()

    def __post_init__(self) -> None:
        required = (
            self.request_id,
            self.conversation_id,
            self.owner_id,
            self.tenant_id,
            self.workspace_id,
            self.user_message,
        )
        if any(not isinstance(v, str) or not v.strip() for v in required):
            raise ValueError("request, conversation, owner, tenant, workspace and user_message are required")

    @property
    def scope(self) -> Scope:
        return Scope(self.owner_id, self.tenant_id, self.workspace_id)


@dataclass(frozen=True)
class AionResponse:
    request_id: str
    conversation_id: str
    answer: str
    selected_role: str
    supporting_roles: tuple[str, ...]
    truth_state: str
    evidence: tuple[Mapping[str, Any], ...]
    sources: tuple[Mapping[str, Any], ...]
    memory_updates: tuple[Mapping[str, Any], ...]
    pending_approvals: tuple[Mapping[str, Any], ...]
    task_events: tuple[Mapping[str, Any], ...]
    warnings: tuple[str, ...]
    execution_receipts: tuple[Mapping[str, Any], ...]
    checkpoint_reference: str
    authorization_class: str
    provider_state: str
    model_lane: str
    orchestration: Mapping[str, Any]
    specialist_routing: Mapping[str, Any]
    external_action_executed: bool = False
    real_orders_enabled: bool = False
    schema: str = SCHEMA

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def official_roles_snapshot() -> dict[str, Any]:
    legacy = internal_roles_snapshot()
    rows = [
        {
            "role_id": role_id,
            "label": label,
            "legacy_role_ids": list(LEGACY_ROLE_COMPATIBILITY[role_id]),
            "shared_core": True,
            "independent_ai": False,
            "external_action_authority": False,
        }
        for role_id, label in OFFICIAL_ROLES
    ]
    return {
        "schema": SCHEMA,
        "count": len(rows),
        "roles": rows,
        "single_shared_aion_core": True,
        "legacy_registry_schema": legacy.get("schema"),
        "legacy_registry_preserved": True,
        "execution_authority": False,
    }


def _validate_source_scope(request: AionRequest) -> None:
    source = dict(request.source_context or {})
    for key, expected in (
        ("owner_id", request.owner_id),
        ("tenant_id", request.tenant_id),
        ("workspace_id", request.workspace_id),
    ):
        supplied = str(source.get(key) or "").strip()
        if supplied and supplied != expected:
            raise ValueError(f"source_context {key} crosses request scope")


def select_official_role(request: AionRequest) -> tuple[str, tuple[str, ...]]:
    text = _norm(f"{request.sector} {request.requested_action} {request.user_message}")
    action = str(request.requested_action or "query").casefold()
    if action in {"publish", "email", "merge", "deploy", "spend", "credentials", "open_trader"}:
        selected = "prime"
    elif any(k in text for k in ("auditoria", "auditar", "risco", "seguranca", "guardiao", "approval", "aprovacao")):
        selected = "guardian"
    elif any(k in text for k in ("arquitet", "estrateg", "refator", "design", "estrutura")):
        selected = "architect"
    elif any(k in text for k in ("pesquisa", "pesquisar", "fonte", "verificar", "triagem", "research")):
        selected = "shadow"
    elif any(k in text for k in ("monitor", "alerta", "incidente", "saude", "observabilidade", "sentinel")):
        selected = "sentinel"
    elif any(k in text for k in ("lead", "crm", "cliente", "proposta", "venda", "comercial", "follow-up")):
        selected = "commercial"
    elif any(k in text for k in ("ensinar", "explique", "explicar", "treinamento", "educar", "academia")):
        selected = "educator"
    else:
        selected = "orchestrator"

    supporting = ["orchestrator"]
    if selected != "guardian" and action not in {"query", "explain", "verify", "analyze"}:
        supporting.append("guardian")
    if selected in {"architect", "guardian"} and "shadow" not in supporting:
        supporting.append("shadow")
    supporting = [x for x in supporting if x != selected]
    return selected, tuple(dict.fromkeys(supporting))


def _proposed_memory_updates(request: AionRequest) -> tuple[Mapping[str, Any], ...]:
    raw = request.source_context.get("memory_events") if isinstance(request.source_context, Mapping) else None
    rows = []
    for event in list(raw or [])[:50]:
        if not isinstance(event, Mapping):
            continue
        rows.append({
            "state": "PROPOSED_ONLY",
            "automatic_promotion": False,
            "requires_truth_validation": True,
            "requires_checkpoint_policy": True,
            "event": dict(event),
        })
    return tuple(rows)


def prepare_checkpoint_export(
    request: AionRequest,
    conversation_checkpoint: Mapping[str, Any],
    adapter: CheckpointMasterAdapter,
) -> dict[str, Any]:
    """Prepare a scoped export only. This function never persists it."""
    _validate_source_scope(request)
    export = adapter.prepare_export(request.scope, dict(conversation_checkpoint or {}))
    return {
        "state": "PREPARED_NOT_SAVED",
        "scope": {
            "owner_id": request.owner_id,
            "tenant_id": request.tenant_id,
            "workspace_id": request.workspace_id,
        },
        "export": export,
        "requires_explicit_human_confirmation": True,
        "automatic_checkpoint_write": False,
    }


def save_approved_checkpoint(
    request: AionRequest,
    export: Mapping[str, Any],
    adapter: CheckpointMasterAdapter,
    *,
    approval_receipt: str,
    explicit_approval: bool,
) -> dict[str, Any]:
    """Persist only through an injected adapter and an explicit approval receipt."""
    _validate_source_scope(request)
    if explicit_approval is not True or not str(approval_receipt or "").strip():
        raise PermissionError("explicit approval receipt required")
    return adapter.save_approved(request.scope, dict(export or {}), str(approval_receipt))


def process_aion_request(
    request: AionRequest,
    *,
    approved: bool = False,
    external_feature_enabled: bool = False,
    provider_state: str = "ZERO_COST_LOCAL",
    budget: Mapping[str, Any] | None = None,
) -> AionResponse:
    """Plan one request through the existing Core without executing side effects."""
    if not isinstance(request, AionRequest):
        raise TypeError("AionRequest required")
    _validate_source_scope(request)

    action_class = classify_action(str(request.requested_action or "query")).value
    selected_role, supporting_roles = select_official_role(request)
    cognitive = route_specialists(request.user_message, domain_hint=request.sector)
    truth = assess_truth(request.evidence)

    role = str(request.authorization_context.get("role") or "USER").upper()
    if role not in {"USER", "SALES", "ADMIN"}:
        role = "USER"
    mode = str(request.current_mode or "BEGINNER").upper()
    if mode not in {"BEGINNER", "ADVANCED"}:
        mode = "BEGINNER"

    core_action = _ORCHESTRATOR_ACTION.get(str(request.requested_action or "").casefold(), "read")
    core = orchestrate(
        request.user_message,
        context={
            "role": role,
            "persona": "core",
            "experience_mode": mode,
            "session_id": request.conversation_id,
            "request_id": request.request_id,
            "domain_hint": request.sector,
        },
        evidence=request.evidence,
        requested_action=core_action,
        approved=approved,
    )

    model_route = route_intelligence(
        request.user_message,
        provider_state=str(provider_state or "ZERO_COST_LOCAL"),
        external_feature_enabled=external_feature_enabled,
        budget=budget,
        estimated_request_cost_usd=0.0,
        request_approved=approved,
        force_private=False,
    )

    pending = []
    warnings = []
    if action_class == ActionClass.REQUIRES_APPROVAL.value and not approved:
        pending.append({
            "kind": "EXPLICIT_APPROVAL_REQUIRED",
            "action": request.requested_action,
            "request_id": request.request_id,
        })
    if action_class == ActionClass.BLOCKED.value:
        warnings.append("ACTION_BLOCKED")
    if truth.get("conflict_state") == "CONFLICT":
        warnings.append("EVIDENCE_CONFLICT")
    if truth.get("status") == "UNKNOWN":
        warnings.append("TRUTH_UNVERIFIED")
    if external_feature_enabled and str(provider_state or "").upper() != "EXTERNAL_READY":
        warnings.append("PROVIDER_UNAVAILABLE")
    warnings.append("NO_MODEL_RESPONSE_GENERATED")

    source_refs = tuple(
        dict(x) for x in list(truth.get("source_references") or []) if isinstance(x, Mapping)
    )
    evidence_refs = [
        str(x.get("source_ref") or x.get("source") or "")
        for x in source_refs
        if str(x.get("source_ref") or x.get("source") or "").strip()
    ]
    state = "BLOCKED" if action_class == ActionClass.BLOCKED.value else (
        "WAITING_APPROVAL" if pending else str((core.get("decision") or {}).get("state") or "PLANNED")
    )
    receipt = seal_action_receipt(
        {
            "task_id": (core.get("task") or {}).get("task_id"),
            "reviewers": {
                "PRIME": "aion-role:prime",
                "SHADOW": "aion-role:shadow",
                "SENTINEL": "aion-role:sentinel",
            },
            "blast_radius": "NONE",
            "policy_ref": SCHEMA,
            "guardian": core.get("guardian") or {},
            "evidence_refs": evidence_refs,
            "approval_refs": [request.request_id] if approved else [],
            "capability": (core.get("selected_capability") or {}).get("capability_id") or "UNRESOLVED",
            "tool_id": "aion-unified-runtime",
            "state": state,
            "result": "Preflight unificado concluído; nenhuma ação externa executada.",
            "issued_at": _now(),
            "correlation_id": request.request_id,
        },
        trusted_context={
            "requester_id": request.owner_id,
            "tenant_id": request.tenant_id,
            "workspace_id": request.workspace_id,
            "prime_id": "aion-role:prime",
            "shadow_id": "aion-role:shadow",
            "sentinel_id": "aion-role:sentinel",
        },
    )

    checkpoint_reference = _clean(
        request.source_context.get("checkpoint_id") if isinstance(request.source_context, Mapping) else "",
        160,
    )
    task_events = ({
        "request_id": request.request_id,
        "state": state,
        "selected_role": selected_role,
        "authorization_class": action_class,
        "external_action_executed": False,
    },)

    return AionResponse(
        request_id=request.request_id,
        conversation_id=request.conversation_id,
        answer="",
        selected_role=selected_role,
        supporting_roles=supporting_roles,
        truth_state=str(truth.get("status") or "UNKNOWN"),
        evidence=tuple(dict(x) for x in list(truth.get("records") or []) if isinstance(x, Mapping)),
        sources=source_refs,
        memory_updates=_proposed_memory_updates(request),
        pending_approvals=tuple(pending),
        task_events=task_events,
        warnings=tuple(dict.fromkeys(warnings)),
        execution_receipts=(receipt,),
        checkpoint_reference=checkpoint_reference,
        authorization_class=action_class,
        provider_state=str(provider_state or "ZERO_COST_LOCAL").upper(),
        model_lane=str(model_route.get("lane") or "LOCAL_DETERMINISTIC"),
        orchestration=core,
        specialist_routing=cognitive,
        external_action_executed=False,
        real_orders_enabled=False,
    )


__all__ = [
    "SCHEMA",
    "OFFICIAL_ROLES",
    "LEGACY_ROLE_COMPATIBILITY",
    "AionRequest",
    "AionResponse",
    "official_roles_snapshot",
    "select_official_role",
    "prepare_checkpoint_export",
    "save_approved_checkpoint",
    "process_aion_request",
]
