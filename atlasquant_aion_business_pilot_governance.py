"""AION BUSINESS Pilot Governance V1.

Readiness-only governance for a future first real BUSINESS pilot. The module
creates a bounded pilot charter, validates mandatory gates, defines success and
stop criteria, and prepares an approval packet. It never authorizes, activates,
contacts, publishes, charges, deploys, stores credentials or changes production.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Any, Mapping, Sequence
import json

SCHEMA = "ATLASQUANT_AION_BUSINESS_PILOT_GOVERNANCE_V1"
VERSION = "1"

MAX_PILOT_DAYS = 30
MAX_CLIENTS = 1
MAX_WORKFLOWS = 1
MAX_CHANNELS = 2
MAX_HUMAN_OPERATORS = 2

MANDATORY_GATES = (
    "business_specialist_certified",
    "master_readiness_demo_complete",
    "scope_confirmed",
    "privacy_profile_ready",
    "sla_defined",
    "margin_reviewed",
    "capacity_reviewed",
    "integration_readiness_reviewed",
    "rollback_ready",
    "human_operator_assigned",
    "support_owner_assigned",
    "pilot_success_criteria_defined",
    "pilot_stop_conditions_defined",
)

PILOT_STATES = (
    "INCOMPLETE",
    "DRAFT_CHARTER",
    "PILOT_REVIEW_REQUIRED",
    "BLOCKED",
)

STOP_REASONS = (
    "PRIVACY_OR_PERMISSION_RISK",
    "CRITICAL_INCIDENT",
    "SLA_BREACH_PATTERN",
    "UNEXPECTED_EXTERNAL_ACTION",
    "MARGIN_OR_CAPACITY_BREACH",
    "DATA_QUALITY_FAILURE",
    "OPERATOR_UNAVAILABLE",
    "CLIENT_REQUEST",
)


def _clean(value: Any, limit: int = 500) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _exact_bool(value: Any) -> bool | None:
    return value if type(value) is bool else None


def _seq(value: Any, limit: int) -> list[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return list(value)[:limit]


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _digest(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return sha256(raw.encode("utf-8")).hexdigest()


def build_pilot_charter(
    *,
    client_reference: Any,
    segment: Any,
    package_label: Any,
    workflow_name: Any,
    channels: Sequence[str] | None,
    duration_days: Any,
    human_operators: Sequence[str] | None,
    support_owner: Any,
    daily_external_action_cap: Any = 0,
    allow_external_messages: Any = False,
    allow_publication: Any = False,
    allow_payments: Any = False,
) -> dict[str, Any]:
    client = _clean(client_reference, 120)
    segment_text = _clean(segment, 120)
    package = _clean(package_label, 160)
    workflow = _clean(workflow_name, 180)
    channel_rows = [_clean(x, 80) for x in _seq(channels, MAX_CHANNELS)]
    channel_rows = [x for x in channel_rows if x]
    operators = [_clean(x, 120) for x in _seq(human_operators, MAX_HUMAN_OPERATORS)]
    operators = [x for x in operators if x]
    owner = _clean(support_owner, 120)

    try:
        days = int(duration_days)
    except Exception:
        days = 0
    try:
        external_cap = int(daily_external_action_cap)
    except Exception:
        external_cap = -1

    external_messages = _exact_bool(allow_external_messages)
    publication = _exact_bool(allow_publication)
    payments = _exact_bool(allow_payments)

    required_missing = [
        name for name, value in (
            ("client_reference", client),
            ("segment", segment_text),
            ("package_label", package),
            ("workflow_name", workflow),
            ("channels", channel_rows),
            ("human_operators", operators),
            ("support_owner", owner),
        )
        if not value
    ]

    bounds_valid = bool(
        1 <= days <= MAX_PILOT_DAYS
        and 1 <= len(channel_rows) <= MAX_CHANNELS
        and 1 <= len(operators) <= MAX_HUMAN_OPERATORS
        and external_cap >= 0
    )
    flags_valid = all(x is not None for x in (external_messages, publication, payments))

    # This V1 is planning-only: all external execution capabilities must remain off.
    external_capabilities_off = bool(
        external_messages is False
        and publication is False
        and payments is False
        and external_cap == 0
    )

    if required_missing or not bounds_valid or not flags_valid:
        state = "INCOMPLETE"
    elif not external_capabilities_off:
        state = "BLOCKED"
    else:
        state = "DRAFT_CHARTER"

    charter = {
        "client_reference": client,
        "segment": segment_text,
        "package_label": package,
        "client_count": 1 if client else 0,
        "workflow_name": workflow,
        "workflow_count": 1 if workflow else 0,
        "channels": channel_rows,
        "duration_days": days if days > 0 else None,
        "human_operators": operators,
        "support_owner": owner,
        "daily_external_action_cap": external_cap if external_cap >= 0 else None,
        "allow_external_messages": external_messages,
        "allow_publication": publication,
        "allow_payments": payments,
        "runtime_state": "OFF",
        "real_credentials_present": False,
        "production_write_enabled": False,
    }
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": state,
        "charter": charter,
        "required_missing": required_missing,
        "bounds_valid": bounds_valid,
        "external_capabilities_off": external_capabilities_off,
        "charter_digest": _digest(charter) if state == "DRAFT_CHARTER" else "",
        "pilot_authorized": False,
        "runtime_activated": False,
        "executes_action": False,
    }


def define_success_criteria(
    *,
    metric_names: Sequence[str] | None,
    minimum_sample_size: Any,
    review_cadence_days: Any,
) -> dict[str, Any]:
    metrics = [_clean(x, 120) for x in _seq(metric_names, 10)]
    metrics = [x for x in metrics if x]
    try:
        sample = int(minimum_sample_size)
    except Exception:
        sample = 0
    try:
        cadence = int(review_cadence_days)
    except Exception:
        cadence = 0
    valid = bool(metrics and sample >= 20 and 1 <= cadence <= 14)
    return {
        "schema": SCHEMA,
        "state": "DEFINED" if valid else "INCOMPLETE",
        "metrics": metrics,
        "minimum_sample_size": sample if sample > 0 else None,
        "review_cadence_days": cadence if cadence > 0 else None,
        "financial_guarantee": False,
        "automatic_success_claim": False,
        "executes_action": False,
    }


def define_stop_conditions(
    *,
    reasons: Sequence[str] | None,
    immediate_stop_on_unexpected_external_action: Any = True,
) -> dict[str, Any]:
    rows = [_clean(x, 100).upper() for x in _seq(reasons, len(STOP_REASONS))]
    selected = [x for x in rows if x in STOP_REASONS]
    immediate = _exact_bool(immediate_stop_on_unexpected_external_action)
    required = {
        "PRIVACY_OR_PERMISSION_RISK",
        "CRITICAL_INCIDENT",
        "UNEXPECTED_EXTERNAL_ACTION",
    }
    valid = bool(required.issubset(set(selected)) and immediate is True)
    return {
        "schema": SCHEMA,
        "state": "DEFINED" if valid else "INCOMPLETE",
        "reasons": selected,
        "immediate_stop_on_unexpected_external_action": immediate,
        "automatic_runtime_shutdown_available_now": False,
        "human_escalation_required": True,
        "executes_action": False,
    }


def pilot_gate_review(
    charter: Mapping[str, Any] | None,
    gates: Mapping[str, Any] | None,
    success_criteria: Mapping[str, Any] | None,
    stop_conditions: Mapping[str, Any] | None,
) -> dict[str, Any]:
    c = _mapping(charter)
    g = _mapping(gates)
    success = _mapping(success_criteria)
    stop = _mapping(stop_conditions)

    gate_states = {}
    for gate in MANDATORY_GATES:
        if gate == "pilot_success_criteria_defined":
            value = success.get("state") == "DEFINED"
        elif gate == "pilot_stop_conditions_defined":
            value = stop.get("state") == "DEFINED"
        else:
            value = g.get(gate) is True
        gate_states[gate] = value

    failed = [name for name, ok in gate_states.items() if not ok]
    charter_ready = c.get("state") == "DRAFT_CHARTER"
    all_ready = bool(charter_ready and not failed)

    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "PILOT_REVIEW_REQUIRED" if all_ready else "BLOCKED",
        "charter_ready": charter_ready,
        "gates": gate_states,
        "failed_gates": failed,
        "all_mandatory_gates_pass": all_ready,
        "pilot_authorized": False,
        "pilot_started": False,
        "runtime_activated": False,
        "external_actions_authorized": False,
        "payment_authorized": False,
        "publication_authorized": False,
        "executes_action": False,
    }


def pilot_review_packet(
    charter: Mapping[str, Any] | None,
    gate_review: Mapping[str, Any] | None,
    *,
    requested_by: Any,
) -> dict[str, Any]:
    c = _mapping(charter)
    review = _mapping(gate_review)
    requester = _clean(requested_by, 120)
    eligible = bool(
        c.get("state") == "DRAFT_CHARTER"
        and c.get("charter_digest")
        and review.get("state") == "PILOT_REVIEW_REQUIRED"
        and review.get("all_mandatory_gates_pass") is True
        and requester
    )
    return {
        "schema": "ATLASQUANT_AION_BUSINESS_PILOT_REVIEW_PACKET_V1",
        "state": "HUMAN_PILOT_APPROVAL_REQUIRED" if eligible else "BLOCKED",
        "requested_by": requester if eligible else "",
        "charter_digest": c.get("charter_digest") if eligible else "",
        "approval_scope": "BUSINESS_BOUNDED_PILOT_ONLY",
        "approval_must_name_client": True,
        "approval_must_name_workflow": True,
        "approval_must_name_duration": True,
        "human_approval_recorded": False,
        "pilot_authorized": False,
        "runtime_activation_approved": False,
        "external_actions_authorized": False,
        "executes_action": False,
    }


def pilot_posture(
    charter: Mapping[str, Any] | None,
    gate_review: Mapping[str, Any] | None,
    review_packet: Mapping[str, Any] | None,
) -> dict[str, Any]:
    c = _mapping(charter)
    g = _mapping(gate_review)
    p = _mapping(review_packet)
    return {
        "schema": SCHEMA,
        "state": (
            "AWAITING_EXPLICIT_HUMAN_APPROVAL"
            if p.get("state") == "HUMAN_PILOT_APPROVAL_REQUIRED"
            else "NOT_READY_FOR_PILOT"
        ),
        "demo_complete_is_not_pilot_approval": True,
        "pilot_review_is_not_pilot_approval": True,
        "charter_state": c.get("state") or "UNKNOWN",
        "gate_review_state": g.get("state") or "UNKNOWN",
        "review_packet_state": p.get("state") or "UNKNOWN",
        "client_limit": MAX_CLIENTS,
        "workflow_limit": MAX_WORKFLOWS,
        "channel_limit": MAX_CHANNELS,
        "duration_limit_days": MAX_PILOT_DAYS,
        "runtime_state": "OFF",
        "pilot_authorized": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "VERSION",
    "MAX_PILOT_DAYS",
    "MAX_CLIENTS",
    "MAX_WORKFLOWS",
    "MAX_CHANNELS",
    "MAX_HUMAN_OPERATORS",
    "MANDATORY_GATES",
    "PILOT_STATES",
    "STOP_REASONS",
    "build_pilot_charter",
    "define_success_criteria",
    "define_stop_conditions",
    "pilot_gate_review",
    "pilot_review_packet",
    "pilot_posture",
]
