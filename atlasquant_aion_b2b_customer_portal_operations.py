"""Read-only automation and support-ticket records for the B2B customer portal.

This module exposes bounded operational status only. It never starts/stops
automations, changes schedules, writes tickets, sends messages, changes SLA,
contacts customers, calls providers, deploys, bills, or mutates production.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Any, Mapping
import json

SCHEMA = "ATLASQUANT_AION_B2B_CUSTOMER_PORTAL_OPERATIONS_V1"

AUTOMATION_STATES = {"ACTIVE", "PAUSED", "DEGRADED", "PENDING", "DISABLED"}
AUTOMATION_RESULTS = {"SUCCESS", "FAILED", "PARTIAL", "UNKNOWN"}
TICKET_STATES = {"OPEN", "IN_PROGRESS", "WAITING_CUSTOMER", "RESOLVED", "CLOSED"}
TICKET_PRIORITIES = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
SLA_STATES = {"ON_TRACK", "AT_RISK", "BREACHED", "NOT_APPLICABLE"}
FORBIDDEN_KEY_PARTS = (
    "password", "secret", "token", "api_key", "credential", "authorization",
    "message_body", "raw_payload",
)


def _text(value: Any, limit: int = 320) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.replace("\x00", "").split())[:limit]


def _scope(raw: Mapping[str, Any] | None) -> dict[str, str]:
    data = dict(raw) if isinstance(raw, Mapping) else {}
    return {
        "owner_id": _text(data.get("owner_id"), 120),
        "tenant_id": _text(data.get("tenant_id"), 120),
        "workspace_id": _text(data.get("workspace_id"), 120),
    }


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _digest(value: Any) -> str:
    return "sha256:" + sha256(_canonical(value).encode("utf-8")).hexdigest()


def _refs(value: Any, limit: int = 50) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    out: list[str] = []
    for raw in value[:limit]:
        item = _text(raw, 320)
        if item and item not in out:
            out.append(item)
    return out


def _contains_forbidden_key(value: Any, depth: int = 0) -> bool:
    if depth > 8:
        return True
    if isinstance(value, Mapping):
        for key, item in value.items():
            normalized = str(key or "").strip().casefold()
            if any(part in normalized for part in FORBIDDEN_KEY_PARTS):
                return True
            if _contains_forbidden_key(item, depth + 1):
                return True
        return False
    if isinstance(value, (list, tuple)):
        return any(_contains_forbidden_key(item, depth + 1) for item in value[:100])
    return False


def build_customer_portal_operations(
    *,
    trusted_scope: Mapping[str, Any],
    customer_id: str,
    package: str,
    raw: Mapping[str, Any] | None,
) -> dict[str, Any]:
    data = dict(raw) if isinstance(raw, Mapping) else {}
    trusted = _scope(trusted_scope)
    blockers: list[str] = []

    expected_customer = _text(customer_id, 120)
    expected_package = _text(package, 40).upper()

    if not all(trusted.values()):
        blockers.append("TRUSTED_SCOPE_INVALID")
    if _scope(data) != trusted:
        blockers.append("PORTAL_OPERATIONS_SCOPE_MISMATCH")
    if _text(data.get("customer_id"), 120) != expected_customer:
        blockers.append("PORTAL_OPERATIONS_CUSTOMER_MISMATCH")
    if _text(data.get("package"), 40).upper() != expected_package:
        blockers.append("PORTAL_OPERATIONS_PACKAGE_MISMATCH")
    if _contains_forbidden_key(data):
        blockers.append("PORTAL_OPERATIONS_SECRET_OR_CONTENT_FIELD_REJECTED")

    evidence_refs = _refs(data.get("evidence_refs"))
    if len(evidence_refs) < 3:
        blockers.append("PORTAL_OPERATIONS_EVIDENCE_INSUFFICIENT")

    automations: list[dict[str, Any]] = []
    seen_automations: set[str] = set()
    raw_automations = data.get("automations")
    if raw_automations is not None and not isinstance(raw_automations, (list, tuple)):
        blockers.append("AUTOMATIONS_INVALID")
    for raw_item in list(raw_automations or [])[:50]:
        if not isinstance(raw_item, Mapping):
            blockers.append("AUTOMATION_ITEM_INVALID")
            continue
        automation_id = _text(raw_item.get("automation_id"), 120)
        name = _text(raw_item.get("name"), 160)
        state = _text(raw_item.get("state"), 40).upper()
        last_result = _text(raw_item.get("last_result"), 40).upper()
        last_run_at = _text(raw_item.get("last_run_at"), 96)
        next_review_at = _text(raw_item.get("next_review_at"), 96)
        if (
            not automation_id
            or automation_id in seen_automations
            or not name
            or state not in AUTOMATION_STATES
            or last_result not in AUTOMATION_RESULTS
            or not last_run_at
        ):
            blockers.append("AUTOMATION_ITEM_INVALID")
            continue
        seen_automations.add(automation_id)
        automations.append({
            "automation_id": automation_id,
            "name": name,
            "state": state,
            "last_result": last_result,
            "last_run_at": last_run_at,
            "next_review_at": next_review_at,
        })

    tickets: list[dict[str, Any]] = []
    seen_tickets: set[str] = set()
    raw_tickets = data.get("tickets")
    if raw_tickets is not None and not isinstance(raw_tickets, (list, tuple)):
        blockers.append("TICKETS_INVALID")
    for raw_item in list(raw_tickets or [])[:100]:
        if not isinstance(raw_item, Mapping):
            blockers.append("TICKET_ITEM_INVALID")
            continue
        ticket_id = _text(raw_item.get("ticket_id"), 120)
        title = _text(raw_item.get("title"), 180)
        state = _text(raw_item.get("state"), 40).upper()
        priority = _text(raw_item.get("priority"), 40).upper()
        sla_state = _text(raw_item.get("sla_state"), 40).upper()
        created_at = _text(raw_item.get("created_at"), 96)
        updated_at = _text(raw_item.get("updated_at"), 96)
        if (
            not ticket_id
            or ticket_id in seen_tickets
            or not title
            or state not in TICKET_STATES
            or priority not in TICKET_PRIORITIES
            or sla_state not in SLA_STATES
            or not created_at
            or not updated_at
        ):
            blockers.append("TICKET_ITEM_INVALID")
            continue
        seen_tickets.add(ticket_id)
        tickets.append({
            "ticket_id": ticket_id,
            "title": title,
            "state": state,
            "priority": priority,
            "sla_state": sla_state,
            "created_at": created_at,
            "updated_at": updated_at,
        })

    counts = {
        "automation_total": len(automations),
        "automation_degraded": sum(1 for x in automations if x["state"] == "DEGRADED"),
        "ticket_open": sum(1 for x in tickets if x["state"] in {"OPEN", "IN_PROGRESS", "WAITING_CUSTOMER"}),
        "ticket_sla_breached": sum(1 for x in tickets if x["sla_state"] == "BREACHED"),
        "critical_open": sum(
            1 for x in tickets
            if x["priority"] == "CRITICAL" and x["state"] not in {"RESOLVED", "CLOSED"}
        ),
    }

    core = {
        "scope": trusted,
        "customer_id": expected_customer,
        "package": expected_package,
        "automations": automations,
        "tickets": tickets,
        "counts": counts,
        "evidence_refs": evidence_refs,
    }

    return {
        "schema": SCHEMA,
        "state": "READY" if not blockers else "BLOCKED",
        **core,
        "blockers": list(dict.fromkeys(blockers)),
        "evidence_digest": _digest(core),
        "read_only": True,
        "automation_control_exposed": False,
        "ticket_write_exposed": False,
        "message_content_exposed": False,
        "automatic_automation_change": False,
        "automatic_ticket_change": False,
        "automatic_customer_contact": False,
        "provider_called": False,
        "production_mutation": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "AUTOMATION_STATES",
    "AUTOMATION_RESULTS",
    "TICKET_STATES",
    "TICKET_PRIORITIES",
    "SLA_STATES",
    "build_customer_portal_operations",
]
