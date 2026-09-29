"""AION Central personas, per-workspace scopes and the developer trust policy.

Pure functions only: nothing here executes an action, reads secrets or talks to
the network. A workspace scope can only narrow what the Guardian already allows;
it never grants anything the Guardian denies.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping

from atlasquant_aion_clock import greeting_period
from atlasquant_aion_core import guardian_decision, is_admin
from atlasquant_aion_ecosystem import persona_capability_map, persona_catalog

SCHEMA = "ATLASQUANT_AION_WORKSPACES_V1"

# Projected from the canonical ecosystem registry. Public keys stay id, title,
# workspace, domain, purpose and actions.
AION_PERSONAS: tuple[dict[str, Any], ...] = persona_catalog()
PERSONA_CAPABILITIES: dict[str, tuple[str, ...]] = persona_capability_map()

# Actions no workspace may request, whatever the Guardian flags say.
NEVER_FROM_WORKSPACE = frozenset({
    "real_trade",
    "deploy_production",
    "merge_main",
    "read_secret",
    "write_secret",
})


def persona(persona_id: object) -> dict[str, Any] | None:
    key = str(persona_id or "").strip().casefold()
    for item in AION_PERSONAS:
        if item["id"] == key:
            return dict(item)
    return None


def persona_for_workspace(workspace: object) -> dict[str, Any] | None:
    label = str(workspace or "")
    for item in AION_PERSONAS:
        if item["workspace"] == label:
            return dict(item)
    return None


def workspace_context_key(persona_id: object, key: object) -> str:
    """Session-state key isolated per persona, so contexts never leak across workspaces."""
    item = persona(persona_id)
    if item is None:
        raise KeyError(f"unknown AION persona: {persona_id!r}")
    clean = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in str(key or "").strip())
    if not clean:
        raise ValueError("empty context key")
    return f"aion_ctx::{item['id']}::{clean}"


def authorize_workspace_action(
    persona_id: object,
    action: object,
    access: Mapping[str, Any] | None,
    *,
    approved: bool = False,
    feature_flags: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Scope check first, then the Guardian. Both must allow; neither can widen the other."""
    action_key = str(action or "").strip().lower()
    item = persona(persona_id)
    base = {"schema": SCHEMA, "persona": item["id"] if item else "", "action": action_key, "executes_action": False}
    if item is None:
        return {**base, "allowed": False, "reason": "Persona AION desconhecida; falha fechado.", "layer": "scope"}
    if action_key in NEVER_FROM_WORKSPACE:
        return {**base, "allowed": False, "reason": "Ação proibida a partir de qualquer workspace AION.", "layer": "scope"}
    if action_key not in item["actions"]:
        return {**base, "allowed": False, "reason": f"Ação fora do escopo de {item['title']}.", "layer": "scope"}
    decision = guardian_decision(action_key, access, approved=approved, feature_flags=feature_flags)
    return {
        **base,
        "allowed": bool(decision.get("allowed")),
        "reason": str(decision.get("reason") or ""),
        "layer": "guardian",
        "risk": decision.get("risk"),
        "requires_explicit_approval": bool(decision.get("requires_explicit_approval", True)),
    }


def capability_snapshot(
    persona_id: object,
    availability: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Declare connected/absent capabilities from explicit runtime evidence."""
    item = persona(persona_id)
    if item is None:
        return {
            "schema": SCHEMA, "persona": "", "state": "BLOCKED",
            "capabilities": [], "executes_action": False,
        }
    supplied = dict(availability or {})
    rows = []
    for capability in PERSONA_CAPABILITIES[item["id"]]:
        raw = supplied.get(capability)
        if isinstance(raw, Mapping):
            confirmed = str(raw.get("truth_state") or "").upper() == "CONFIRMED"
            source = str(raw.get("source") or "")
        else:
            confirmed = raw is True
            source = ""
        rows.append({
            "capability": capability,
            "state": "CONNECTED" if confirmed else "UNAVAILABLE",
            "source": source,
        })
    return {
        "schema": SCHEMA,
        "persona": item["id"],
        "state": "CONNECTED" if any(row["state"] == "CONNECTED" for row in rows) else "UNAVAILABLE",
        "capabilities": rows,
        "connected": sum(row["state"] == "CONNECTED" for row in rows),
        "total": len(rows),
        "executes_action": False,
        "real_orders_enabled": False,
    }


def greeting_for(now: datetime | None = None, *, timezone_name: str | None = None) -> str:
    """Same period as the Central Principal. The hour rule lives in one clock."""
    return greeting_period(now, timezone_name=timezone_name)


def admin_greeting(
    access: Mapping[str, Any] | None,
    display_name: object,
    now: datetime | None = None,
    *,
    timezone_name: str | None = None,
) -> str:
    if not is_admin(access):
        return ""
    name = str(display_name or "").strip()[:64] or "Administrador"
    return f"{greeting_for(now, timezone_name=timezone_name)}, {name}."


def _count(snapshot: Mapping[str, Any], key: str) -> int | None:
    raw = snapshot.get(key)
    if isinstance(raw, bool) or raw is None:
        return None
    try:
        return max(0, int(raw))
    except (TypeError, ValueError):
        return None


def admin_brief_lines(executive_snapshot: Mapping[str, Any] | None) -> list[str]:
    """Short daily summary built only from values present in the executive pulse."""
    snap = dict(executive_snapshot or {})
    lines: list[str] = []
    runtime = str(snap.get("runtime_status") or "").strip()
    lines.append(f"Runtime: {runtime}." if runtime and runtime != "UNKNOWN" else "Runtime: não confirmado.")
    for key, label in (
        ("approval_count", "aprovação(ões) pendente(s)"),
        ("incident_count", "incidente(s) aberto(s)"),
        ("critical_incidents", "incidente(s) crítico(s)"),
        ("active_missions", "missão(ões) ativa(s)"),
        ("blocked_missions", "missão(ões) bloqueada(s)"),
    ):
        value = _count(snap, key)
        lines.append(f"{value} {label}." if value is not None else f"{label.capitalize()}: não confirmado.")
    primary = snap.get("primary") if isinstance(snap.get("primary"), Mapping) else {}
    action = str(primary.get("next_action") or "").strip()
    if action:
        lines.append(f"Próxima ação sugerida: {action}")
    lines.append("Ordens reais: bloqueadas.")
    return lines


DEVELOPER_TRUST_LEVELS: tuple[dict[str, Any], ...] = (
    {"level": 0, "name": "Leitura", "may": "Ler código, logs e checkpoints; resumir.", "human_gate": "nenhum"},
    {"level": 1, "name": "Rascunho", "may": "Propor plano e patch em texto; nada é gravado.", "human_gate": "nenhum"},
    {"level": 2, "name": "Branch isolada", "may": "Commits em branch cursor/* ou Sandbox, com testes.", "human_gate": "revisão do diff"},
    {"level": 3, "name": "PR em rascunho", "may": "Abrir ou atualizar Draft PR com checks verdes.", "human_gate": "aprovação explícita de Mikael"},
)

DEVELOPER_FORBIDDEN = (
    "Merge automático em main.",
    "Deploy automático ou alteração do Render em produção.",
    "Alterar secrets, senhas, chaves ou autenticação ADMIN.",
    "Habilitar ordens reais ou execução automática.",
    "Remover ou enfraquecer o Safety Core.",
    "Force push, reescrita de histórico ou apagar dados persistentes.",
)

DEVELOPER_ROLLBACK_STEPS = (
    "Toda mudança nasce em branch própria a partir de um commit conhecido.",
    "Commits pequenos, um por mudança lógica, para reverter com git revert <sha>.",
    "Antes de promover: Quality Tests, UI Smoke, Mobile DOM e Release Readiness verdes.",
    "Se algo falhar depois do merge humano: git revert do merge, nunca reset/force push.",
    "Checkpoint AION salvo antes de mudanças de estado; restauração exige aprovação.",
)


def developer_trust_policy() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "levels": [dict(x) for x in DEVELOPER_TRUST_LEVELS],
        "max_autonomous_level": 1,
        "forbidden": list(DEVELOPER_FORBIDDEN),
        "rollback": list(DEVELOPER_ROLLBACK_STEPS),
        "auto_merge": False,
        "auto_deploy": False,
        "self_escalation": False,
    }


def developer_step_allowed(level: object, *, human_approved: bool = False) -> bool:
    # bool is a subclass of int. True/False must not become levels 1/0.
    if isinstance(level, bool) or not isinstance(level, int):
        return False
    if level < 0 or level > DEVELOPER_TRUST_LEVELS[-1]["level"]:
        return False
    if level <= 1:
        return True
    return human_approved is True


__all__ = [
    "AION_PERSONAS",
    "DEVELOPER_FORBIDDEN",
    "DEVELOPER_ROLLBACK_STEPS",
    "DEVELOPER_TRUST_LEVELS",
    "NEVER_FROM_WORKSPACE",
    "SCHEMA",
    "admin_brief_lines",
    "admin_greeting",
    "authorize_workspace_action",
    "capability_snapshot",
    "developer_step_allowed",
    "developer_trust_policy",
    "greeting_for",
    "persona",
    "persona_for_workspace",
    "PERSONA_CAPABILITIES",
    "workspace_context_key",
]
