"""AION BUSINESS Integration Hub Readiness V1.

Readiness-only, secret-free integration registry for BUSINESS. It models which
external systems a future client may connect, the minimum scopes needed and the
health/readiness state. This module never performs OAuth, stores credentials,
sends messages, publishes content, charges money or activates runtime.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Mapping, Sequence
import json

SCHEMA = "ATLASQUANT_AION_BUSINESS_INTEGRATION_HUB_READINESS_V1"
VERSION = "1"

INTEGRATIONS = (
    "WHATSAPP_BUSINESS",
    "EMAIL",
    "FORMS",
    "CALENDAR",
    "CRM",
    "PAYMENTS",
    "SOCIAL_MEDIA",
    "ANALYTICS",
)

STATES = (
    "NOT_CONFIGURED",
    "CONFIGURED_DEMO",
    "READY_FOR_AUTH_REVIEW",
    "HEALTHY_READ_ONLY_DEMO",
    "DEGRADED_DEMO",
    "BLOCKED",
)

SCOPE_STATES = (
    "NOT_NEEDED",
    "READ_ONLY",
    "DRAFT_ONLY",
    "FUTURE_APPROVAL_REQUIRED",
    "PROHIBITED_IN_DEMO",
)

DANGEROUS_CAPABILITIES = (
    "SEND_EXTERNAL_MESSAGE",
    "PUBLISH_CONTENT",
    "CHARGE_PAYMENT",
    "REFUND_PAYMENT",
    "SIGN_CONTRACT",
    "DELETE_EXTERNAL_DATA",
    "ADMINISTER_ACCOUNT",
)


def _clean(value: Any, limit: int = 500) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _parse_time(value: Any) -> datetime | None:
    token = _clean(value, 80)
    if not token:
        return None
    try:
        row = datetime.fromisoformat(token.replace("Z", "+00:00"))
    except Exception:
        return None
    if row.tzinfo is None:
        row = row.replace(tzinfo=timezone.utc)
    return row.astimezone(timezone.utc)


def _digest(value: Mapping[str, Any]) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return sha256(raw.encode("utf-8")).hexdigest()


def integration_record(
    *,
    integration: Any,
    display_name: Any,
    purpose: Any,
    account_reference: Any = "",
    config_complete: Any = False,
    auth_review_complete: Any = False,
    read_probe_ok: Any = None,
    last_check_at: Any = "",
) -> dict[str, Any]:
    token = _clean(integration, 80).upper()
    if token not in INTEGRATIONS:
        return {
            "schema": SCHEMA,
            "state": "BLOCKED",
            "integration": "",
            "reason": "UNKNOWN_INTEGRATION",
            "stores_secret": False,
            "connects_external_system": False,
            "executes_action": False,
        }

    name = _clean(display_name, 160) or token
    purpose_text = _clean(purpose, 500)
    account = _clean(account_reference, 180)
    config = config_complete is True
    auth = auth_review_complete is True
    probe = read_probe_ok if type(read_probe_ok) is bool else None
    checked = _parse_time(last_check_at)

    if not config:
        state = "NOT_CONFIGURED"
    elif config and not auth:
        state = "CONFIGURED_DEMO"
    elif auth and probe is None:
        state = "READY_FOR_AUTH_REVIEW"
    elif auth and probe is True:
        state = "HEALTHY_READ_ONLY_DEMO"
    else:
        state = "DEGRADED_DEMO"

    record = {
        "schema": SCHEMA,
        "version": VERSION,
        "integration": token,
        "display_name": name,
        "purpose": purpose_text,
        "account_reference": account,
        "state": state,
        "config_complete": config,
        "auth_review_complete": auth,
        "read_probe_ok": probe,
        "last_check_at": checked.isoformat() if checked else "",
        "credential_value": None,
        "secret_present": False,
        "stores_secret": False,
        "connects_external_system": False,
        "write_scope_granted": False,
        "runtime_activated": False,
        "executes_action": False,
    }
    record["record_digest"] = _digest({
        "integration": token,
        "display_name": name,
        "purpose": purpose_text,
        "account_reference": account,
        "state": state,
        "config_complete": config,
        "auth_review_complete": auth,
        "read_probe_ok": probe,
        "last_check_at": record["last_check_at"],
    })
    return record


def minimum_scope_plan(integration: Any, *, use_case: Any = "") -> dict[str, Any]:
    token = _clean(integration, 80).upper()
    case = _clean(use_case, 240)
    if token not in INTEGRATIONS:
        return {
            "schema": SCHEMA,
            "state": "BLOCKED",
            "integration": "",
            "scopes": {},
            "executes_action": False,
        }

    scopes: dict[str, str] = {}
    if token == "WHATSAPP_BUSINESS":
        scopes = {
            "read_inbound": "READ_ONLY",
            "draft_reply": "DRAFT_ONLY",
            "send_reply": "FUTURE_APPROVAL_REQUIRED",
            "manage_templates": "FUTURE_APPROVAL_REQUIRED",
        }
    elif token == "EMAIL":
        scopes = {
            "read_selected_mailbox": "READ_ONLY",
            "draft_email": "DRAFT_ONLY",
            "send_email": "FUTURE_APPROVAL_REQUIRED",
            "delete_email": "PROHIBITED_IN_DEMO",
        }
    elif token == "FORMS":
        scopes = {
            "read_submissions": "READ_ONLY",
            "write_form": "FUTURE_APPROVAL_REQUIRED",
        }
    elif token == "CALENDAR":
        scopes = {
            "read_availability": "READ_ONLY",
            "draft_event": "DRAFT_ONLY",
            "create_event": "FUTURE_APPROVAL_REQUIRED",
            "cancel_event": "FUTURE_APPROVAL_REQUIRED",
        }
    elif token == "CRM":
        scopes = {
            "read_contacts": "READ_ONLY",
            "read_pipeline": "READ_ONLY",
            "draft_update": "DRAFT_ONLY",
            "write_contact": "FUTURE_APPROVAL_REQUIRED",
            "delete_contact": "PROHIBITED_IN_DEMO",
        }
    elif token == "PAYMENTS":
        scopes = {
            "read_invoice_status": "READ_ONLY",
            "draft_invoice": "DRAFT_ONLY",
            "issue_invoice": "FUTURE_APPROVAL_REQUIRED",
            "charge_payment": "PROHIBITED_IN_DEMO",
            "refund_payment": "PROHIBITED_IN_DEMO",
        }
    elif token == "SOCIAL_MEDIA":
        scopes = {
            "read_metrics": "READ_ONLY",
            "draft_content": "DRAFT_ONLY",
            "publish_content": "FUTURE_APPROVAL_REQUIRED",
            "delete_content": "PROHIBITED_IN_DEMO",
        }
    else:
        scopes = {
            "read_metrics": "READ_ONLY",
            "write_tracking_config": "FUTURE_APPROVAL_REQUIRED",
        }

    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "PLAN_READY",
        "integration": token,
        "use_case": case,
        "principle": "LEAST_PRIVILEGE",
        "scopes": scopes,
        "dangerous_capabilities_granted": [],
        "stores_secret": False,
        "executes_action": False,
    }


def connection_review_packet(
    record: Mapping[str, Any] | None,
    scope_plan: Mapping[str, Any] | None,
    *,
    requested_by: Any,
) -> dict[str, Any]:
    row = _mapping(record)
    scopes = _mapping(scope_plan)
    requester = _clean(requested_by, 120)
    valid = bool(
        row.get("schema") == SCHEMA
        and row.get("integration") in INTEGRATIONS
        and scopes.get("schema") == SCHEMA
        and scopes.get("integration") == row.get("integration")
        and requester
        and row.get("config_complete") is True
        and row.get("stores_secret") is False
    )
    return {
        "schema": "ATLASQUANT_AION_BUSINESS_INTEGRATION_CONNECTION_REVIEW_V1",
        "state": "AUTH_REVIEW_REQUIRED" if valid else "BLOCKED",
        "integration": row.get("integration") if valid else "",
        "requested_by": requester if valid else "",
        "scope_plan_digest": _digest(scopes) if valid else "",
        "approval_scope": "CONNECTION_AUTH_ONLY",
        "human_approval_recorded": False,
        "oauth_executed": False,
        "credential_stored": False,
        "write_scope_granted": False,
        "runtime_activated": False,
        "executes_action": False,
    }


def integration_health(
    record: Mapping[str, Any] | None,
    *,
    now: datetime | None = None,
    max_age_hours: int = 24,
) -> dict[str, Any]:
    row = _mapping(record)
    current = now.astimezone(timezone.utc) if isinstance(now, datetime) else datetime.now(timezone.utc)
    checked = _parse_time(row.get("last_check_at"))
    age_hours = None
    if checked is not None:
        age_hours = max(0.0, (current - checked).total_seconds() / 3600)

    if row.get("integration") not in INTEGRATIONS:
        state = "BLOCKED"
    elif row.get("state") == "HEALTHY_READ_ONLY_DEMO" and age_hours is not None and age_hours <= max_age_hours:
        state = "HEALTHY_READ_ONLY_DEMO"
    elif row.get("config_complete") is True and row.get("auth_review_complete") is True:
        state = "DEGRADED_DEMO"
    else:
        state = row.get("state") or "NOT_CONFIGURED"

    return {
        "schema": SCHEMA,
        "integration": row.get("integration") or "",
        "state": state,
        "last_check_age_hours": None if age_hours is None else round(age_hours, 2),
        "fresh": bool(age_hours is not None and age_hours <= max_age_hours),
        "read_only": True,
        "write_enabled": False,
        "external_action_enabled": False,
        "runtime_activated": False,
        "executes_action": False,
    }


def hub_snapshot(records: Sequence[Mapping[str, Any]] | None) -> dict[str, Any]:
    rows = [dict(x) for x in (list(records)[:50] if isinstance(records, Sequence) and not isinstance(records, (str, bytes, bytearray)) else []) if isinstance(x, Mapping)]
    states = {state: 0 for state in STATES}
    known = set()
    for row in rows:
        token = _clean(row.get("integration"), 80).upper()
        state = _clean(row.get("state"), 80).upper()
        if token in INTEGRATIONS:
            known.add(token)
        if state in states:
            states[state] += 1
    missing = [x for x in INTEGRATIONS if x not in known]
    healthy = states["HEALTHY_READ_ONLY_DEMO"]
    degraded = states["DEGRADED_DEMO"]
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "ATTENTION" if degraded else "DEMO_READY" if healthy else "NOT_CONNECTED",
        "configured_count": len(known),
        "healthy_read_only_count": healthy,
        "degraded_count": degraded,
        "missing_integrations": missing,
        "states": states,
        "real_connections_active": 0,
        "write_integrations_active": 0,
        "payment_execution_active": False,
        "publication_execution_active": False,
        "runtime_activated": False,
        "executes_action": False,
    }


def secret_handling_policy() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "policy": "NO_RAW_SECRETS_IN_DEMO",
        "raw_secret_input_allowed": False,
        "secret_logging_allowed": False,
        "secret_in_checkpoint_allowed": False,
        "secret_in_ui_state_allowed": False,
        "future_secret_storage": "DEDICATED_SECRET_STORE_REQUIRED",
        "rotation_required": True,
        "least_privilege_required": True,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "VERSION",
    "INTEGRATIONS",
    "STATES",
    "SCOPE_STATES",
    "DANGEROUS_CAPABILITIES",
    "integration_record",
    "minimum_scope_plan",
    "connection_review_packet",
    "integration_health",
    "hub_snapshot",
    "secret_handling_policy",
]
