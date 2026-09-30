"""AION BUSINESS Privacy, LGPD & Audit Governance V1.

Offline/demo-only governance layer for purpose limitation, consent evidence,
retention, export/deletion requests, role-based access and immutable audit
records. It does not contain real personal data and does not execute deletion,
export, publication, billing, messaging or runtime actions.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
from typing import Any, Mapping, Sequence
import json

SCHEMA = "ATLASQUANT_AION_BUSINESS_PRIVACY_AUDIT_GOVERNANCE_V1"
VERSION = "1"

DATA_CATEGORIES = (
    "CONTACT",
    "LEAD",
    "APPOINTMENT",
    "COMMERCIAL",
    "SUPPORT",
    "USAGE_METRICS",
)

ROLES = (
    "CLIENT_ADMIN",
    "CLIENT_OPERATOR",
    "AION_SUPPORT",
    "AION_ADMIN",
    "AUDITOR",
)

REQUEST_TYPES = (
    "EXPORT",
    "DELETE",
    "CORRECT",
    "RESTRICT",
)

REQUEST_STATES = (
    "DRAFT",
    "REVIEW_REQUIRED",
    "APPROVED_FOR_FUTURE_EXECUTION",
    "BLOCKED",
)

AUDIT_ACTIONS = (
    "VIEW",
    "DRAFT",
    "APPROVAL",
    "CONFIG_CHANGE",
    "VERSION_CHANGE",
    "ROLLBACK_PREPARED",
)


def _clean(value: Any, limit: int = 500) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _seq(value: Any, limit: int = 50) -> list[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return list(value)[:limit]


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


def _digest(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return sha256(raw.encode("utf-8")).hexdigest()


def privacy_profile(
    *,
    client_name: Any,
    purposes: Sequence[str] | None,
    data_categories: Sequence[str] | None,
    legal_basis_label: Any,
    retention_days: Any,
    controller_contact: Any = "",
) -> dict[str, Any]:
    client = _clean(client_name, 120)
    purpose_rows = [_clean(x, 240) for x in _seq(purposes, 20)]
    purpose_rows = [x for x in purpose_rows if x]
    categories = [_clean(x, 80).upper() for x in _seq(data_categories, 20)]
    categories = [x for x in categories if x in DATA_CATEGORIES]
    basis = _clean(legal_basis_label, 160)
    contact = _clean(controller_contact, 180)
    try:
        days = int(retention_days)
    except Exception:
        days = 0
    valid = bool(client and purpose_rows and categories and basis and days > 0)
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "PROFILE_READY" if valid else "INCOMPLETE",
        "client_name": client,
        "purposes": purpose_rows,
        "data_categories": categories,
        "legal_basis_label": basis,
        "retention_days": days if days > 0 else None,
        "controller_contact": contact,
        "real_personal_data_present": False,
        "legal_conclusion": False,
        "executes_action": False,
    }


def consent_record(
    *,
    subject_reference: Any,
    purpose: Any,
    granted: Any,
    recorded_at: Any,
    source: Any,
) -> dict[str, Any]:
    subject = _clean(subject_reference, 120)
    purpose_text = _clean(purpose, 240)
    source_text = _clean(source, 160)
    when = _parse_time(recorded_at)
    exact = granted if type(granted) is bool else None
    complete = bool(subject and purpose_text and source_text and when is not None and exact is not None)
    state = "GRANTED" if complete and exact is True else "DENIED" if complete else "INCOMPLETE"
    record = {
        "schema": SCHEMA,
        "version": VERSION,
        "state": state,
        "subject_reference": subject,
        "purpose": purpose_text,
        "granted": exact,
        "recorded_at": when.isoformat() if when else "",
        "source": source_text,
        "real_subject_verified": False,
        "executes_action": False,
    }
    record["consent_digest"] = _digest(record)
    return record


def role_access_matrix(profile: Mapping[str, Any] | None) -> dict[str, Any]:
    row = _mapping(profile)
    categories = row.get("data_categories") if isinstance(row.get("data_categories"), Sequence) else []
    matrix: dict[str, dict[str, str]] = {}
    for role in ROLES:
        matrix[role] = {}
        for category in categories:
            cat = _clean(category, 80).upper()
            if role == "CLIENT_ADMIN":
                state = "READ_WRITE_REVIEW"
            elif role == "CLIENT_OPERATOR":
                state = "READ_LIMITED"
            elif role == "AION_SUPPORT":
                state = "READ_MINIMUM"
            elif role == "AION_ADMIN":
                state = "READ_METADATA"
            else:
                state = "AUDIT_ONLY"
            if cat == "COMMERCIAL" and role in {"AION_SUPPORT", "CLIENT_OPERATOR"}:
                state = "READ_LIMITED"
            matrix[role][cat] = state
    return {
        "schema": SCHEMA,
        "state": "READY" if row.get("state") == "PROFILE_READY" else "BLOCKED",
        "matrix": matrix,
        "default_deny": True,
        "least_privilege": True,
        "executes_action": False,
    }


def access_decision(
    matrix: Mapping[str, Any] | None,
    *,
    role: Any,
    category: Any,
    requested_action: Any,
) -> dict[str, Any]:
    row = _mapping(matrix)
    role_token = _clean(role, 80).upper()
    category_token = _clean(category, 80).upper()
    action = _clean(requested_action, 80).upper()
    role_map = _mapping(_mapping(row.get("matrix")).get(role_token))
    permission = _clean(role_map.get(category_token), 80).upper()

    if row.get("default_deny") is not True or not permission:
        allowed = False
        reason = "DEFAULT_DENY"
    elif action == "READ":
        allowed = permission in {"READ_WRITE_REVIEW", "READ_LIMITED", "READ_MINIMUM", "READ_METADATA", "AUDIT_ONLY"}
        reason = "ROLE_SCOPE" if allowed else "DENIED"
    elif action == "WRITE":
        allowed = permission == "READ_WRITE_REVIEW"
        reason = "ROLE_SCOPE" if allowed else "WRITE_NOT_ALLOWED"
    else:
        allowed = False
        reason = "UNKNOWN_ACTION"

    return {
        "schema": SCHEMA,
        "state": "ALLOW_DEMO" if allowed else "DENY",
        "role": role_token,
        "category": category_token,
        "requested_action": action,
        "permission": permission,
        "allowed": allowed,
        "external_write_executed": False,
        "executes_action": False,
        "reason": reason,
    }


def retention_review(
    profile: Mapping[str, Any] | None,
    *,
    created_at: Any,
    now: datetime | None = None,
) -> dict[str, Any]:
    row = _mapping(profile)
    created = _parse_time(created_at)
    current = now.astimezone(timezone.utc) if isinstance(now, datetime) else datetime.now(timezone.utc)
    days = row.get("retention_days")
    if not isinstance(days, int) or days <= 0 or created is None:
        return {
            "schema": SCHEMA,
            "state": "BLOCKED",
            "retention_due_at": "",
            "deletion_executed": False,
            "executes_action": False,
        }
    due = created + timedelta(days=days)
    due_now = current >= due
    return {
        "schema": SCHEMA,
        "state": "RETENTION_REVIEW_DUE" if due_now else "WITHIN_RETENTION",
        "created_at": created.isoformat(),
        "retention_days": days,
        "retention_due_at": due.isoformat(),
        "days_remaining": max(0, (due - current).days),
        "deletion_review_required": due_now,
        "deletion_executed": False,
        "executes_action": False,
    }


def data_subject_request(
    *,
    request_type: Any,
    subject_reference: Any,
    requested_at: Any,
    reason: Any = "",
) -> dict[str, Any]:
    kind = _clean(request_type, 40).upper()
    subject = _clean(subject_reference, 120)
    when = _parse_time(requested_at)
    reason_text = _clean(reason, 500)
    valid = kind in REQUEST_TYPES and bool(subject and when)
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "REVIEW_REQUIRED" if valid else "BLOCKED",
        "request_type": kind if kind in REQUEST_TYPES else "",
        "subject_reference": subject if valid else "",
        "requested_at": when.isoformat() if valid else "",
        "reason": reason_text if valid else "",
        "identity_verified": False,
        "human_approval_recorded": False,
        "export_executed": False,
        "deletion_executed": False,
        "correction_executed": False,
        "restriction_executed": False,
        "executes_action": False,
    }


def audit_event(
    *,
    actor: Any,
    action: Any,
    target: Any,
    approval_reference: Any = "",
    before: Any = None,
    after: Any = None,
    timestamp: Any = "",
) -> dict[str, Any]:
    actor_text = _clean(actor, 120)
    action_token = _clean(action, 80).upper()
    target_text = _clean(target, 200)
    approval = _clean(approval_reference, 160)
    when = _parse_time(timestamp) or datetime.now(timezone.utc)
    valid = bool(actor_text and action_token in AUDIT_ACTIONS and target_text)

    core = {
        "actor": actor_text,
        "action": action_token,
        "target": target_text,
        "approval_reference": approval,
        "before_digest": _digest(before) if before is not None else "",
        "after_digest": _digest(after) if after is not None else "",
        "timestamp": when.isoformat(),
    }
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "RECORDED_DEMO" if valid else "BLOCKED",
        **core,
        "event_digest": _digest(core) if valid else "",
        "immutable_demo_record": valid,
        "authorizes_action": False,
        "external_write": False,
        "executes_action": False,
    }


def automation_version(
    *,
    automation_name: Any,
    version: Any,
    config: Mapping[str, Any] | None,
    approved_by: Any = "",
) -> dict[str, Any]:
    name = _clean(automation_name, 160)
    version_text = _clean(version, 80)
    cfg = _mapping(config)
    approved = _clean(approved_by, 120)
    valid = bool(name and version_text and cfg)
    record = {
        "automation_name": name,
        "version": version_text,
        "config_digest": _digest(cfg) if cfg else "",
        "approved_by": approved,
    }
    return {
        "schema": SCHEMA,
        "state": "VERSION_RECORDED_DEMO" if valid else "BLOCKED",
        **record,
        "version_digest": _digest(record) if valid else "",
        "production_deployed": False,
        "executes_action": False,
    }


def rollback_plan(
    current_version: Mapping[str, Any] | None,
    previous_version: Mapping[str, Any] | None,
) -> dict[str, Any]:
    current = _mapping(current_version)
    previous = _mapping(previous_version)
    valid = bool(
        current.get("state") == "VERSION_RECORDED_DEMO"
        and previous.get("state") == "VERSION_RECORDED_DEMO"
        and current.get("automation_name") == previous.get("automation_name")
        and current.get("version_digest")
        and previous.get("version_digest")
    )
    return {
        "schema": SCHEMA,
        "state": "ROLLBACK_READY_DEMO" if valid else "BLOCKED",
        "automation_name": current.get("automation_name") if valid else "",
        "from_version": current.get("version") if valid else "",
        "to_version": previous.get("version") if valid else "",
        "from_digest": current.get("version_digest") if valid else "",
        "to_digest": previous.get("version_digest") if valid else "",
        "human_approval_required": True,
        "rollback_executed": False,
        "production_write": False,
        "executes_action": False,
    }


def governance_snapshot(
    profile: Mapping[str, Any] | None,
    audit_events: Sequence[Mapping[str, Any]] | None,
) -> dict[str, Any]:
    p = _mapping(profile)
    events = [dict(x) for x in _seq(audit_events, 100) if isinstance(x, Mapping)]
    valid_events = [x for x in events if x.get("state") == "RECORDED_DEMO"]
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "DEMO_READY" if p.get("state") == "PROFILE_READY" else "ATTENTION",
        "privacy_profile_ready": p.get("state") == "PROFILE_READY",
        "audit_event_count": len(valid_events),
        "real_personal_data_present": False,
        "exports_executed": 0,
        "deletions_executed": 0,
        "production_rollbacks_executed": 0,
        "runtime_activated": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "VERSION",
    "DATA_CATEGORIES",
    "ROLES",
    "REQUEST_TYPES",
    "REQUEST_STATES",
    "AUDIT_ACTIONS",
    "privacy_profile",
    "consent_record",
    "role_access_matrix",
    "access_decision",
    "retention_review",
    "data_subject_request",
    "audit_event",
    "automation_version",
    "rollback_plan",
    "governance_snapshot",
]
