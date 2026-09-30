"""Local executor for the AION Tool Hub.

The Tool Hub preflight is the authorization source. This module only runs a
handler after that preflight is READY_FOR_EXECUTOR and the tool is local,
LOCAL_READY, and READ, SEARCH or DRAFT. The handler table is a closed dict of
callables defined here. It does not evaluate code, import caller modules, open
a socket or start a process.

Arguments are sanitized before the handler. Results are sanitized again.
A successful call does not promote truth to CONFIRMED.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Callable, Mapping

from atlasquant_aion_approval_inbox import collect_approval_inbox
from atlasquant_aion_continuity import ACTIVE_STATUSES, MISSION_STATUSES, normalize_missions
from atlasquant_aion_durable_tasks import durable_tasks_summary
from atlasquant_aion_memory import checkpoint_integrity_report, search_canonical_memory
from atlasquant_aion_memory_layers import recall
from atlasquant_aion_observability import is_secret_key, observability_summary, redact_text, sanitize_metadata
from atlasquant_aion_operations import queue_summary
from atlasquant_aion_portable import default_portable_core
from atlasquant_aion_secretary import executive_briefing
from atlasquant_aion_specialist_session import read_loaded_specialist_snapshot
from atlasquant_aion_status_board import build_master_status_board
from atlasquant_aion_tool_hub import default_tool_hub, plan_tool_call
from atlasquant_aion_local_traceability import local_contract_fingerprint

SCHEMA = "ATLASQUANT_AION_LOCAL_TOOL_RESULT_V1"
ALLOWED_KINDS = frozenset({"READ", "SEARCH", "DRAFT"})
FORBIDDEN_KINDS = frozenset({"WRITE", "PUBLISH", "PRODUCTION", "SECRETS", "FINANCIAL"})
_MAX_DEPTH = 6
_MAX_ITEMS = 24
_MAX_TEXT = 500
_PRESERVE = frozenset({
    "truth_state", "freshness", "observed_at", "valid_until", "origin",
    "status", "state", "input_state", "answer_truth",
})
_Handler = Callable[[Mapping[str, Any], Mapping[str, Any]], Any]


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _rows(value: Any) -> list[Any]:
    if isinstance(value, (list, tuple)):
        return list(value)
    return []


def _now(value: Any) -> datetime | None:
    return value if isinstance(value, datetime) else None


def _checkpoint(runtime: Mapping[str, Any]) -> dict[str, Any]:
    return _mapping(runtime.get("checkpoint"))


def _operating(runtime: Mapping[str, Any]) -> dict[str, Any]:
    return _mapping(_checkpoint(runtime).get("operating"))


def _events(runtime: Mapping[str, Any]) -> list[Any]:
    if runtime.get("events") is not None:
        return _rows(runtime.get("events"))
    return _rows(_operating(runtime).get("events"))


def sanitize_local_arguments(value: Any, depth: int = 0) -> Any:
    """Redact secret-like input without stringifying datetimes."""
    if isinstance(value, datetime):
        return value
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if depth >= _MAX_DEPTH:
        return "[TRUNCATED]"
    if isinstance(value, str):
        return redact_text(value)[:_MAX_TEXT]
    if isinstance(value, Mapping):
        out: dict[str, Any] = {}
        for key, item in list(value.items())[:_MAX_ITEMS]:
            if is_secret_key(key):
                continue
            out[redact_text(key)[:80]] = sanitize_local_arguments(item, depth + 1)
        return out
    if isinstance(value, (list, tuple)):
        return [sanitize_local_arguments(item, depth + 1) for item in list(value)[:_MAX_ITEMS]]
    return redact_text(value)[:_MAX_TEXT]


def _bound(value: Any, depth: int = 0) -> tuple[Any, bool]:
    if isinstance(value, datetime):
        return value.isoformat(), False
    if depth >= _MAX_DEPTH:
        return "[TRUNCATED]", True
    if isinstance(value, Mapping):
        preserved = [(key, item) for key, item in value.items() if str(key) in _PRESERVE]
        rest = [(key, item) for key, item in value.items() if str(key) not in _PRESERVE]
        chosen = preserved + rest[: max(0, _MAX_ITEMS - len(preserved))]
        truncated = len(preserved) + len(rest) > len(chosen)
        out: dict[str, Any] = {}
        for key, item in chosen:
            bounded, child = _bound(item, depth + 1)
            out[str(key)[:80]] = bounded
            truncated = truncated or child
        return out, truncated
    if isinstance(value, (list, tuple)):
        truncated = len(value) > _MAX_ITEMS
        rows = []
        for item in list(value)[:_MAX_ITEMS]:
            bounded, child = _bound(item, depth + 1)
            rows.append(bounded)
            truncated = truncated or child
        return rows, truncated
    if isinstance(value, str):
        return (value[:_MAX_TEXT], len(value) > _MAX_TEXT)
    if value is None or isinstance(value, (bool, int, float)):
        return value, False
    text = redact_text(value)
    return (text[:_MAX_TEXT], len(text) > _MAX_TEXT)


def _truth_view(result: Any) -> dict[str, Any]:
    status = "UNKNOWN"
    freshness = "UNVERIFIED"
    if isinstance(result, Mapping):
        declared = str(result.get("truth_state") or "").strip().upper()
        if declared:
            status = declared
        declared_freshness = str(result.get("freshness") or "").strip().upper()
        if declared_freshness:
            freshness = declared_freshness
    return {"status": status, "freshness": freshness, "issues": []}


def _envelope(
    *,
    request_id: str,
    tool_id: str,
    workspace_id: str,
    kind: str,
    state: str,
    result: Any,
    truncated: bool,
    preflight_state: str,
    blockers: list[str],
    source_function: str,
    contract_fingerprint: str,
    error_type: str = "",
    message: str = "",
) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "request_id": redact_text(request_id)[:80],
        "tool_id": tool_id,
        "workspace_id": workspace_id,
        "kind": kind,
        "contract_fingerprint": contract_fingerprint,
        "state": state,
        "result": result,
        "truncated": truncated,
        "error_type": redact_text(error_type)[:80],
        "message": redact_text(message)[:180],
        "preflight": {"state": preflight_state, "blockers": blockers},
        "provenance": {
            "source_module": "atlasquant_aion_local_executor",
            "source_function": source_function,
            "input_scope": "local",
            "local_only": True,
        },
        "truth": _truth_view(result),
        "security": {
            "sanitized": True,
            "network_called": False,
            "connector_called": False,
            "external_side_effects": False,
            "permissions_expanded": False,
            "secrets_included": False,
        },
        "executes_action": False,
        "external_action_executed": False,
        "real_orders_enabled": False,
        "tool_output_is_authority": False,
    }


def _memory_search(arguments: Mapping[str, Any], runtime: Mapping[str, Any]) -> dict[str, Any]:
    query = str(arguments.get("query") or runtime.get("query") or "")
    canonical = search_canonical_memory(query, limit=5) if query.strip() else []
    return {"canonical": canonical, "canonical_count": len(canonical)}


def _memory_recall(arguments: Mapping[str, Any], runtime: Mapping[str, Any]) -> dict[str, Any]:
    layers = arguments.get("memory_layers")
    if not isinstance(layers, Mapping):
        layers = runtime.get("memory_layers") if isinstance(runtime.get("memory_layers"), Mapping) else None
    moment = _now(arguments.get("now")) or _now(runtime.get("now"))
    layered = recall(
        layers,
        persona=arguments.get("persona") or runtime.get("persona") or "",
        domain=arguments.get("domain") or runtime.get("domain") or "",
        accessor_profile=arguments.get("accessor_profile") or runtime.get("accessor_profile") or "",
        explicit_domains=_rows(arguments.get("explicit_domains") or runtime.get("explicit_domains")),
        tags=_rows(arguments.get("tags")),
        include_expired=bool(arguments.get("include_expired", False)),
        include_superseded=bool(arguments.get("include_superseded", False)),
        limit=8,
        now=moment,
    ) if layers is not None else []
    return {"layered": layered, "layered_count": len(layered)}


def _safe_digests(checkpoint: Mapping[str, Any]) -> dict[str, str]:
    found: dict[str, str] = {}
    operating = _mapping(checkpoint.get("operating"))
    continuity = _mapping(checkpoint.get("continuity"))
    durable = _mapping(checkpoint.get("durable_tasks"))
    for key, value in (
        ("task_digest", operating.get("task_digest")),
        ("event_digest", operating.get("event_digest")),
        ("continuity_digest", continuity.get("digest")),
        ("durable_digest", durable.get("digest")),
    ):
        text = str(value or "")
        if text and len(text) <= 80:
            found[key] = text
    return found


def _checkpoint_inspect(arguments: Mapping[str, Any], runtime: Mapping[str, Any]) -> dict[str, Any]:
    del arguments
    checkpoint = _checkpoint(runtime)
    report = checkpoint_integrity_report(checkpoint)
    aion = _mapping(checkpoint.get("aion"))
    operating = _mapping(checkpoint.get("operating"))
    continuity = _mapping(checkpoint.get("continuity"))
    durable = _mapping(checkpoint.get("durable_tasks"))
    areas_raw = checkpoint.get("areas") if isinstance(checkpoint.get("areas"), Mapping) else {}
    areas = {}
    for key, value in list(areas_raw.items())[:_MAX_ITEMS]:
        if isinstance(value, Mapping):
            areas[str(key)[:40]] = str(value.get("state") or value.get("status") or "")[:40]
        else:
            areas[str(key)[:40]] = str(value)[:40]
    inbox = collect_approval_inbox(checkpoint)
    return {
        "checkpoint_version": checkpoint.get("checkpoint_version"),
        "project": checkpoint.get("project"),
        "updated_at": checkpoint.get("updated_at"),
        "aion": {
            "priority": aion.get("priority"),
            "truth_policy": aion.get("truth_policy"),
            "cost_mode": aion.get("cost_mode"),
            "real_trading": False if aion.get("real_trading") is not True else True,
        },
        "areas": areas,
        "counts": {
            "pending": len(_rows(checkpoint.get("pending"))),
            "tasks": len(_rows(operating.get("tasks"))),
            "events": len(_rows(operating.get("events"))),
            "missions": len(_rows(continuity.get("missions"))),
            "durable_tasks": len(_rows(durable.get("records"))),
            "approvals": int(inbox.get("total") or 0),
        },
        "integrity": {
            "state": report.get("state"),
            "mismatches": report.get("mismatches") or [],
            "migration_items": report.get("migration_items") or [],
        },
        "digests": _safe_digests(checkpoint),
        "saved": False,
        "write_safe": False,
    }


def _status_read(arguments: Mapping[str, Any], runtime: Mapping[str, Any]) -> dict[str, Any]:
    del arguments
    return build_master_status_board(
        checkpoint=_checkpoint(runtime),
        runtime_result=_mapping(runtime.get("runtime_result")),
        provider=_mapping(runtime.get("provider")),
        feature_flags=_mapping(runtime.get("feature_flags")),
        system_context=_mapping(runtime.get("system_context")),
        market_context=_mapping(runtime.get("market_context")),
        account_entitlement_audit=_mapping(runtime.get("account_entitlement_audit")),
        working_dirty=bool(runtime.get("working_dirty", False)),
    )


def _tasks(arguments: Mapping[str, Any], runtime: Mapping[str, Any]) -> dict[str, Any]:
    rows = arguments.get("tasks")
    if rows is None:
        rows = runtime.get("tasks")
    if rows is None:
        rows = _operating(runtime).get("tasks")
    summary = queue_summary(_rows(rows))
    summary["executes_action"] = False
    return summary


def _missions(arguments: Mapping[str, Any], runtime: Mapping[str, Any]) -> dict[str, Any]:
    rows = arguments.get("missions")
    if rows is None:
        rows = runtime.get("missions")
    if rows is None:
        rows = _mapping(_checkpoint(runtime).get("continuity")).get("missions")
    missions = normalize_missions(_rows(rows))
    by_status = {status: 0 for status in MISSION_STATUSES}
    for item in missions:
        by_status[str(item.get("status") or "")] += 1
    return {
        "total": len(missions),
        "active": sum(by_status[status] for status in ACTIVE_STATUSES),
        "by_status": by_status,
        "executes_action": False,
    }


def _durable(arguments: Mapping[str, Any], runtime: Mapping[str, Any]) -> dict[str, Any]:
    raw = arguments.get("durable_tasks")
    if raw is None:
        raw = runtime.get("durable_tasks")
    if raw is None:
        raw = _checkpoint(runtime).get("durable_tasks")
    if isinstance(raw, Mapping):
        rows = raw.get("records") if isinstance(raw.get("records"), (list, tuple)) else raw.get("tasks")
    else:
        rows = raw
    summary = durable_tasks_summary(_rows(rows))
    summary["automatic_resume_executes"] = False
    return summary


def _approvals(arguments: Mapping[str, Any], runtime: Mapping[str, Any]) -> dict[str, Any]:
    del arguments
    inbox = collect_approval_inbox(_checkpoint(runtime))
    inbox["automatic_approval"] = False
    inbox["executes_action"] = False
    return inbox


def _events_summary(arguments: Mapping[str, Any], runtime: Mapping[str, Any]) -> dict[str, Any]:
    del arguments
    summary = observability_summary(_events(runtime))
    summary["remote_logging"] = False
    return summary


def _specialists(arguments: Mapping[str, Any], runtime: Mapping[str, Any]) -> dict[str, Any]:
    session = runtime.get("session") if isinstance(runtime.get("session"), Mapping) else None
    reading = read_loaded_specialist_snapshot(
        arguments.get("specialist") or runtime.get("specialist"),
        session,
        now=_now(arguments.get("now")) or _now(runtime.get("now")),
    )
    reading["network_called"] = False
    reading["provider_called"] = False
    return reading


def _secretary(arguments: Mapping[str, Any], runtime: Mapping[str, Any]) -> dict[str, Any]:
    del arguments
    checkpoint = _checkpoint(runtime)
    operating = _operating(runtime)
    brief = executive_briefing(
        tasks=_rows(runtime.get("tasks") if runtime.get("tasks") is not None else operating.get("tasks")),
        events=_events(runtime),
        system_context=_mapping(runtime.get("system_context")),
        market_context=_mapping(runtime.get("market_context")),
        clients_context=_mapping(runtime.get("clients_context")),
        content_context=_mapping(runtime.get("content_context")),
    )
    brief["draft_only"] = True
    brief["published"] = False
    brief["real_orders_enabled"] = False
    brief["checkpoint_used"] = bool(checkpoint)
    return brief


_HANDLERS: dict[str, _Handler] = {
    "aion.memory.search": _memory_search,
    "aion.memory.recall": _memory_recall,
    "aion.checkpoint.inspect": _checkpoint_inspect,
    "aion.status.read": _status_read,
    "aion.tasks.summary": _tasks,
    "aion.missions.summary": _missions,
    "aion.durable.summary": _durable,
    "aion.approvals.summary": _approvals,
    "aion.events.summary": _events_summary,
    "aion.specialists.snapshot": _specialists,
    "aion.secretary.draft_brief": _secretary,
}

_LABELS = {
    "aion.memory.search": "Busca da memória canônica",
    "aion.memory.recall": "Recall da memória local em camadas",
    "aion.checkpoint.inspect": "Inspecionar Checkpoint Mestre",
    "aion.status.read": "Ler quadro de status",
    "aion.tasks.summary": "Resumo de tarefas",
    "aion.missions.summary": "Resumo de missões",
    "aion.durable.summary": "Resumo de tarefas duráveis",
    "aion.approvals.summary": "Resumo da caixa de aprovações",
    "aion.events.summary": "Resumo de eventos locais",
    "aion.specialists.snapshot": "Snapshot local de especialista",
    "aion.secretary.draft_brief": "Rascunho do briefing da secretaria",
}


def local_allowlist() -> tuple[dict[str, str], ...]:
    """Closed handler catalog. Callables stay inside this module."""
    from atlasquant_aion_tool_hub import default_tool_hub as _hub
    kinds = {item["tool_id"]: item["kind"] for item in _hub().get("tools", [])}
    return tuple(
        {"tool_id": tool_id, "kind": str(kinds.get(tool_id, "")), "label": label}
        for tool_id, label in _LABELS.items()
    )


def execute_local_tool(
    tool_id: object,
    context: Mapping[str, Any] | None = None,
    *,
    arguments: Mapping[str, Any] | None = None,
    runtime_context: Mapping[str, Any] | None = None,
    hub: Mapping[str, Any] | None = None,
    portable_core: Mapping[str, Any] | None = None,
    access: Mapping[str, Any] | None = None,
    feature_flags: Mapping[str, Any] | None = None,
    source_kind: object = "ADMIN",
    authenticated_admin: bool = False,
    approved: bool = False,
    request_id: object = "",
) -> dict[str, Any]:
    """Run one local tool only after the Tool Hub preflight allows it."""
    key = str(tool_id or "").strip()
    runtime = _mapping(runtime_context if runtime_context is not None else context)
    clean_arguments = sanitize_local_arguments(_mapping(arguments))
    clean_runtime = sanitize_local_arguments(runtime)
    if not isinstance(clean_arguments, Mapping):
        clean_arguments = {}
    if not isinstance(clean_runtime, Mapping):
        clean_runtime = {}
    effective_hub = hub if hub is not None else default_tool_hub()
    contract_fingerprint = local_contract_fingerprint(effective_hub)
    plan = plan_tool_call(
        key,
        hub=effective_hub,
        portable_core=portable_core if portable_core is not None else default_portable_core(),
        access=access,
        source_kind=source_kind,
        authenticated_admin=bool(authenticated_admin),
        approved=bool(approved),
        feature_flags=feature_flags,
        scope="Consulta local allowlisted do Tool Hub.",
        uncertainty_pct=0,
        impact="LOW",
        reversible=True,
    )
    tool = _mapping(plan.get("tool"))
    blockers = [str(item) for item in list(plan.get("blockers") or [])]
    if plan.get("state") == "BLOCK" and not blockers and plan.get("reason"):
        blockers = [str(plan.get("reason"))]
    preflight_state = str(plan.get("state") or "BLOCK")
    workspace_id = str(tool.get("workspace_id") or "")
    kind = str(tool.get("kind") or "")
    base = {
        "request_id": str(request_id or ""),
        "tool_id": key,
        "workspace_id": workspace_id,
        "kind": kind,
        "contract_fingerprint": contract_fingerprint,
        "preflight_state": preflight_state,
        "blockers": blockers,
    }
    if preflight_state == "BLOCK":
        return _envelope(state="BLOCKED", result=None, truncated=False, source_function="", **base)
    if preflight_state != "READY_FOR_EXECUTOR":
        return _envelope(state="DEGRADED", result=None, truncated=False, source_function="", **base)
    if tool.get("connector_id") or tool.get("state") != "LOCAL_READY" or kind not in ALLOWED_KINDS or kind in FORBIDDEN_KINDS:
        base["blockers"] = blockers + ["LOCAL_EXECUTOR_DENIED"]
        return _envelope(state="BLOCKED", result=None, truncated=False, source_function="", **base)
    handler = _HANDLERS.get(key)
    if handler is None:
        base["blockers"] = blockers + ["HANDLER_NOT_ALLOWLISTED"]
        return _envelope(state="BLOCKED", result=None, truncated=False, source_function="", **base)
    try:
        raw = handler(clean_arguments, clean_runtime)
    except Exception as exc:
        return _envelope(
            state="ERROR",
            result=None,
            truncated=False,
            source_function="",
            error_type=type(exc).__name__,
            message="A ferramenta local falhou de forma fechada.",
            **base,
        )
    bounded, truncated = _bound(sanitize_metadata(raw))
    return _envelope(
        state="SUCCESS",
        result=bounded,
        truncated=truncated,
        source_function=handler.__name__,
        **base,
    )


__all__ = [
    "ALLOWED_KINDS",
    "FORBIDDEN_KINDS",
    "SCHEMA",
    "execute_local_tool",
    "local_allowlist",
    "sanitize_local_arguments",
]
