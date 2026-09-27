"""Local operational executor for the AION Tool Hub.

The allowlist is static. A call can only reach the handlers declared in this
module, and only for READ, SEARCH or DRAFT. Nothing here starts a process,
evaluates code, imports a caller-supplied module, opens a socket, writes the
checkpoint, publishes, deploys, reads a secret store or sends an order.

Results are sanitized with the central observability redactor and then bounded.
Truth and freshness fields produced by the underlying readers are copied
through; this module does not promote UNKNOWN or expired evidence to CONFIRMED.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Callable, Mapping

from atlasquant_aion_approval_inbox import collect_approval_inbox
from atlasquant_aion_continuity import ACTIVE_STATUSES, MISSION_STATUSES, normalize_missions
from atlasquant_aion_durable_tasks import durable_tasks_summary
from atlasquant_aion_memory import checkpoint_integrity_report, search_canonical_memory
from atlasquant_aion_memory_layers import recall
from atlasquant_aion_observability import observability_summary, sanitize_metadata
from atlasquant_aion_operations import queue_summary
from atlasquant_aion_secretary import executive_briefing
from atlasquant_aion_specialist_session import read_loaded_specialist_snapshot
from atlasquant_aion_status_board import build_master_status_board

SCHEMA = "ATLASQUANT_AION_LOCAL_EXECUTOR_V1"
ALLOWED_KINDS = frozenset({"READ", "SEARCH", "DRAFT"})
FORBIDDEN_KINDS = frozenset({"WRITE", "PUBLISH", "PRODUCTION", "SECRETS", "FINANCIAL"})
_MAX_DEPTH = 6
_MAX_ITEMS = 24
_MAX_TEXT = 500
_PRESERVE = frozenset({
    "truth_state",
    "freshness",
    "observed_at",
    "valid_until",
    "origin",
    "status",
    "state",
    "input_state",
    "answer_truth",
})

_Handler = Callable[[Mapping[str, Any]], Any]


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _rows(value: Any) -> list[Any]:
    if isinstance(value, (list, tuple)):
        return list(value)
    return []


def _now(context: Mapping[str, Any]) -> datetime | None:
    value = context.get("now")
    return value if isinstance(value, datetime) else None


def _checkpoint(context: Mapping[str, Any]) -> dict[str, Any]:
    return _mapping(context.get("checkpoint"))


def _bound(value: Any, depth: int = 0) -> tuple[Any, bool]:
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
        out_list: list[Any] = []
        truncated = len(value) > _MAX_ITEMS
        for item in list(value)[:_MAX_ITEMS]:
            bounded, child = _bound(item, depth + 1)
            out_list.append(bounded)
            truncated = truncated or child
        return out_list, truncated
    if isinstance(value, str):
        if len(value) > _MAX_TEXT:
            return value[:_MAX_TEXT], True
        return value, False
    if value is None or isinstance(value, (bool, int, float)):
        return value, False
    text = str(value)
    if len(text) > _MAX_TEXT:
        return text[:_MAX_TEXT], True
    return text, False


def _memory_search(context: Mapping[str, Any]) -> dict[str, Any]:
    query = str(context.get("query") or "")
    memory = context.get("memory") if isinstance(context.get("memory"), Mapping) else None
    layered = recall(
        memory,
        persona=context.get("persona") or "",
        tags=_rows(context.get("tags")),
        include_expired=bool(context.get("include_expired", False)),
        limit=8,
        now=_now(context),
    ) if memory is not None else []
    canonical = search_canonical_memory(query, limit=5) if query.strip() else []
    return {
        "layered": layered,
        "canonical": canonical,
        "layered_count": len(layered),
        "canonical_count": len(canonical),
    }


def _checkpoint_inspect(context: Mapping[str, Any]) -> dict[str, Any]:
    report = checkpoint_integrity_report(_checkpoint(context))
    return {
        "schema": report.get("schema"),
        "state": report.get("state"),
        "checkpoint_version": report.get("checkpoint_version"),
        "mismatches": report.get("mismatches") or [],
        "migration_items": report.get("migration_items") or [],
        "total": report.get("total"),
        "write_safe": False,
        "saved": False,
    }


def _status_board(context: Mapping[str, Any]) -> dict[str, Any]:
    return build_master_status_board(
        checkpoint=_checkpoint(context),
        runtime_result=_mapping(context.get("runtime_result")),
        provider=_mapping(context.get("provider")),
        feature_flags=_mapping(context.get("feature_flags")),
        system_context=_mapping(context.get("system_context")),
        market_context=_mapping(context.get("market_context")),
        account_entitlement_audit=_mapping(context.get("account_entitlement_audit")),
        working_dirty=bool(context.get("working_dirty", False)),
    )


def _tasks(context: Mapping[str, Any]) -> dict[str, Any]:
    rows = context.get("tasks")
    if rows is None:
        operating = _mapping(_checkpoint(context).get("operating"))
        rows = operating.get("tasks")
    summary = queue_summary(_rows(rows))
    summary["executes_action"] = False
    return summary


def _missions(context: Mapping[str, Any]) -> dict[str, Any]:
    rows = context.get("missions")
    if rows is None:
        continuity = _mapping(_checkpoint(context).get("continuity"))
        rows = continuity.get("missions")
    missions = normalize_missions(_rows(rows))
    by_status = {status: 0 for status in MISSION_STATUSES}
    for item in missions:
        by_status[str(item.get("status") or "")] += 1
    return {
        "total": len(missions),
        "active": sum(by_status[status] for status in ACTIVE_STATUSES),
        "by_status": by_status,
        "next": [
            {
                "mission_id": item.get("mission_id"),
                "title": item.get("title"),
                "status": item.get("status"),
                "next_action": item.get("next_action"),
            }
            for item in missions[:8]
        ],
        "executes_action": False,
    }


def _task_rows(value: Any) -> list[Any]:
    if isinstance(value, Mapping):
        records = value.get("records")
        if isinstance(records, (list, tuple)):
            return list(records)
        tasks = value.get("tasks")
        if isinstance(tasks, (list, tuple)):
            return list(tasks)
        return []
    return _rows(value)


def _durable_tasks(context: Mapping[str, Any]) -> dict[str, Any]:
    raw = context.get("durable_tasks")
    if raw is None:
        raw = _checkpoint(context).get("durable_tasks")
    summary = durable_tasks_summary(_task_rows(raw))
    summary["automatic_resume_executes"] = False
    return summary


def _approval_inbox(context: Mapping[str, Any]) -> dict[str, Any]:
    inbox = collect_approval_inbox(_checkpoint(context))
    inbox["automatic_approval"] = False
    inbox["executes_action"] = False
    return inbox


def _observability(context: Mapping[str, Any]) -> dict[str, Any]:
    events = context.get("events")
    if events is None:
        events = _checkpoint(context).get("events")
    summary = observability_summary(_rows(events))
    summary["remote_logging"] = False
    return summary


def _specialist_snapshot(context: Mapping[str, Any]) -> dict[str, Any]:
    session = context.get("session") if isinstance(context.get("session"), Mapping) else None
    reading = read_loaded_specialist_snapshot(
        context.get("specialist"),
        session,
        now=_now(context),
    )
    reading["network_called"] = False
    reading["provider_called"] = False
    return reading


def _secretary_brief(context: Mapping[str, Any]) -> dict[str, Any]:
    checkpoint = _checkpoint(context)
    operating = _mapping(checkpoint.get("operating"))
    brief = executive_briefing(
        tasks=_rows(context.get("tasks") if context.get("tasks") is not None else operating.get("tasks")),
        events=_rows(context.get("events") if context.get("events") is not None else checkpoint.get("events")),
        system_context=_mapping(context.get("system_context")),
        market_context=_mapping(context.get("market_context")),
        clients_context=_mapping(context.get("clients_context")),
        content_context=_mapping(context.get("content_context")),
    )
    brief["draft_only"] = True
    brief["published"] = False
    brief["real_orders_enabled"] = False
    return brief


_ALLOWLIST: tuple[dict[str, Any], ...] = (
    {"tool_id": "aion.memory.search", "kind": "SEARCH", "label": "Busca da memória local", "handler": _memory_search},
    {"tool_id": "aion.checkpoint.inspect", "kind": "READ", "label": "Inspeção segura do checkpoint", "handler": _checkpoint_inspect},
    {"tool_id": "aion.status.board", "kind": "READ", "label": "Quadro de status", "handler": _status_board},
    {"tool_id": "aion.tasks.summary", "kind": "READ", "label": "Resumo de tarefas", "handler": _tasks},
    {"tool_id": "aion.missions.summary", "kind": "READ", "label": "Resumo de missões", "handler": _missions},
    {"tool_id": "aion.durable_tasks.summary", "kind": "READ", "label": "Resumo de tarefas duráveis", "handler": _durable_tasks},
    {"tool_id": "aion.approval.inbox", "kind": "READ", "label": "Caixa de aprovações", "handler": _approval_inbox},
    {"tool_id": "aion.observability.summary", "kind": "READ", "label": "Resumo de observabilidade", "handler": _observability},
    {"tool_id": "aion.specialist.snapshot", "kind": "READ", "label": "Snapshot do especialista", "handler": _specialist_snapshot},
    {"tool_id": "aion.secretary.brief", "kind": "DRAFT", "label": "Rascunho do briefing da secretaria", "handler": _secretary_brief},
)

_BY_ID = {str(item["tool_id"]): item for item in _ALLOWLIST}


def local_allowlist() -> tuple[dict[str, str], ...]:
    """Public catalog. Handlers stay inside this module."""
    return tuple(
        {"tool_id": str(item["tool_id"]), "kind": str(item["kind"]), "label": str(item["label"])}
        for item in _ALLOWLIST
    )


def _blocked(tool_id: str, reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "tool_id": tool_id,
        "kind": "",
        "state": "BLOCK",
        "blockers": [reason],
        "result": None,
        "truncated": False,
        "executes_external_action": False,
        "network_called": False,
        "subprocess_called": False,
        "real_trading_enabled": False,
        "tool_output_is_authority": False,
        "writes_checkpoint": False,
        "publishes": False,
    }


def execute_local_tool(tool_id: object, context: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Run one allowlisted local tool. Unknown ids fail closed."""
    key = str(tool_id or "").strip()
    spec = _BY_ID.get(key)
    if spec is None or spec["kind"] not in ALLOWED_KINDS or spec["kind"] in FORBIDDEN_KINDS:
        return _blocked(key, "TOOL_NOT_ALLOWLISTED")
    payload = _mapping(context)
    raw = spec["handler"](payload)
    sanitized = sanitize_metadata(raw)
    bounded, truncated = _bound(sanitized)
    return {
        "schema": SCHEMA,
        "tool_id": key,
        "kind": spec["kind"],
        "state": "READY",
        "blockers": [],
        "result": bounded,
        "truncated": truncated,
        "executes_external_action": False,
        "network_called": False,
        "subprocess_called": False,
        "real_trading_enabled": False,
        "tool_output_is_authority": False,
        "writes_checkpoint": False,
        "publishes": False,
    }


__all__ = [
    "ALLOWED_KINDS",
    "FORBIDDEN_KINDS",
    "SCHEMA",
    "execute_local_tool",
    "local_allowlist",
]
