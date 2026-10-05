"""AION B2B customer portal access and presentation contract.

Pure/offline boundary for a future customer-facing portal. It binds an authenticated
USER session to one confirmed B2B customer/service tenant and exposes a filtered
read-only view of an already-validated managed-service read model.

It never provisions accounts, mutates roles, bills, renews, changes quotas,
contacts customers, calls providers, deploys, or mutates production.
"""
from __future__ import annotations

from html import escape
from typing import Any, Mapping, Sequence
import re

from atlasquant_aion_tenant import tenant_namespace

SCHEMA = "ATLASQUANT_AION_B2B_CUSTOMER_PORTAL_V1"
PORTAL_SCOPE = "B2B_CUSTOMER_PORTAL"
ALLOWED_VIEWER_ROLE = "USER"
READ_MODEL_SCHEMA = "ATLASQUANT_AION_B2B_PORTAL_READ_MODEL_V1"
PILOT_VALUE_BINDING_SCHEMA = "ATLASQUANT_AION_B2B_PILOT_CUSTOMER_VALUE_BINDING_V1"
RECURRING_PROJECTION_SCHEMA = "ATLASQUANT_AION_B2B_RECURRING_CUSTOMER_PROJECTION_V1"
SAFE_SECTIONS = ("overview", "value", "usage", "support", "integrations", "crm", "documents", "billing", "automations", "tickets")
_SAFE_TENANT_ID = re.compile(r"^[a-f0-9]{32}$")


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


def _allowed_sections(value: Any) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        return SAFE_SECTIONS
    out: list[str] = []
    for raw in value[:12]:
        item = _text(raw, 60).casefold()
        if item in SAFE_SECTIONS and item not in out:
            out.append(item)
    return tuple(out) if out else SAFE_SECTIONS


def normalize_customer_portal_binding(raw: Mapping[str, Any] | None) -> dict[str, Any]:
    """Normalize a trusted admin-created customer portal binding."""
    data = dict(raw) if isinstance(raw, Mapping) else {}
    return {
        "schema": SCHEMA,
        "state": _text(data.get("state"), 40).upper(),
        "enabled": data.get("enabled") is True,
        "portal_scope": _text(data.get("portal_scope"), 80).upper(),
        "subject_tenant_id": _text(data.get("subject_tenant_id"), 64).lower(),
        "service_tenant_id": _text(data.get("service_tenant_id"), 120),
        "workspace_id": _text(data.get("workspace_id"), 120),
        "customer_id": _text(data.get("customer_id"), 120),
        "package": _text(data.get("package"), 40).upper(),
        "binding_ref": _text(data.get("binding_ref"), 320),
        "allowed_sections": _allowed_sections(data.get("allowed_sections")),
    }


def customer_portal_access(
    access: Mapping[str, Any] | None,
    binding: Mapping[str, Any] | None,
    read_model: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Validate customer identity + binding + service read model fail-closed."""
    blockers: list[str] = []
    ns = tenant_namespace(access)
    role = _text(ns.get("role"), 40).upper()

    if ns.get("ready") is not True:
        blockers.append("AUTHENTICATED_CUSTOMER_SESSION_REQUIRED")
    if role != ALLOWED_VIEWER_ROLE:
        blockers.append("CUSTOMER_USER_ROLE_REQUIRED")

    normalized = normalize_customer_portal_binding(binding)
    if normalized["state"] != "CONFIRMED":
        blockers.append("CUSTOMER_PORTAL_BINDING_NOT_CONFIRMED")
    if normalized["enabled"] is not True:
        blockers.append("CUSTOMER_PORTAL_BINDING_DISABLED")
    if normalized["portal_scope"] != PORTAL_SCOPE:
        blockers.append("CUSTOMER_PORTAL_SCOPE_INVALID")
    if not _SAFE_TENANT_ID.fullmatch(normalized["subject_tenant_id"]):
        blockers.append("CUSTOMER_SUBJECT_TENANT_ID_INVALID")
    if normalized["subject_tenant_id"] != _text(ns.get("tenant_id"), 64).lower():
        blockers.append("CUSTOMER_SUBJECT_TENANT_MISMATCH")
    if not normalized["service_tenant_id"]:
        blockers.append("SERVICE_TENANT_ID_REQUIRED")
    if not normalized["workspace_id"]:
        blockers.append("SERVICE_WORKSPACE_ID_REQUIRED")
    if not normalized["customer_id"]:
        blockers.append("CUSTOMER_ID_REQUIRED")
    if not normalized["package"]:
        blockers.append("PACKAGE_REQUIRED")
    if not normalized["binding_ref"]:
        blockers.append("CUSTOMER_PORTAL_BINDING_REF_REQUIRED")

    model = dict(read_model) if isinstance(read_model, Mapping) else {}
    if model.get("schema") != READ_MODEL_SCHEMA:
        blockers.append("CUSTOMER_READ_MODEL_SCHEMA_INVALID")
    if model.get("state") != "READY":
        blockers.append("CUSTOMER_READ_MODEL_NOT_READY")
    if model.get("read_only") is not True:
        blockers.append("CUSTOMER_READ_MODEL_NOT_READ_ONLY")
    if model.get("grants_authority") is not False:
        blockers.append("CUSTOMER_READ_MODEL_AUTHORITY_UNSAFE")
    if model.get("executes_action") is not False:
        blockers.append("CUSTOMER_READ_MODEL_EXECUTION_UNSAFE")
    if not _text(model.get("evidence_digest"), 180):
        blockers.append("CUSTOMER_READ_MODEL_EVIDENCE_REQUIRED")

    model_scope = _scope(model.get("scope") if isinstance(model.get("scope"), Mapping) else {})
    if model_scope["tenant_id"] != normalized["service_tenant_id"]:
        blockers.append("CUSTOMER_SERVICE_TENANT_MISMATCH")
    if model_scope["workspace_id"] != normalized["workspace_id"]:
        blockers.append("CUSTOMER_SERVICE_WORKSPACE_MISMATCH")
    if _text(model.get("customer_id"), 120) != normalized["customer_id"]:
        blockers.append("CUSTOMER_READ_MODEL_CUSTOMER_MISMATCH")
    if _text(model.get("package"), 40).upper() != normalized["package"]:
        blockers.append("CUSTOMER_READ_MODEL_PACKAGE_MISMATCH")

    return {
        "schema": SCHEMA,
        "allowed": not blockers,
        "state": "ALLOW" if not blockers else "BLOCKED",
        "customer_id": normalized["customer_id"],
        "package": normalized["package"],
        "viewer_tenant_id": _text(ns.get("tenant_id"), 64),
        "service_tenant_id": normalized["service_tenant_id"],
        "workspace_id": normalized["workspace_id"],
        "allowed_sections": list(normalized["allowed_sections"]),
        "binding_ref": normalized["binding_ref"],
        "blockers": list(dict.fromkeys(blockers)),
        "read_only": True,
        "admin_memory_access": False,
        "other_tenant_access": False,
        "grants_authority": False,
        "automatic_billing": False,
        "automatic_renewal": False,
        "automatic_quota_change": False,
        "automatic_role_change": False,
        "automatic_customer_contact": False,
        "automatic_deploy": False,
        "production_mutation": False,
        "executes_action": False,
    }


def _copy_usage(raw: Any) -> dict[str, dict[str, Any]]:
    source = raw if isinstance(raw, Mapping) else {}
    out: dict[str, dict[str, Any]] = {}
    for key in ("capacity", "calls", "tokens", "support_tickets"):
        row = source.get(key) if isinstance(source.get(key), Mapping) else {}
        out[key] = {
            "used": row.get("used"),
            "limit": row.get("limit"),
            "utilization_pct": row.get("utilization_pct"),
        }
    return out


def customer_portal_view_model(
    access: Mapping[str, Any] | None,
    binding: Mapping[str, Any] | None,
    read_model: Mapping[str, Any] | None,
    records: Mapping[str, Any] | None = None,
    operations: Mapping[str, Any] | None = None,
    pilot_value_binding: Mapping[str, Any] | None = None,
    recurring_projection: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Filter internal service evidence into a customer-safe presentation model."""
    decision = customer_portal_access(access, binding, read_model)
    if decision["allowed"] is not True:
        return {
            "schema": SCHEMA,
            "state": "BLOCKED",
            "allowed": False,
            "blockers": list(decision["blockers"]),
            "read_only": True,
            "grants_authority": False,
            "executes_action": False,
        }

    model = dict(read_model or {})
    support = model.get("support") if isinstance(model.get("support"), Mapping) else {}

    safe_records = None
    if records is not None:
        candidate = dict(records) if isinstance(records, Mapping) else {}
        record_blockers: list[str] = []
        if candidate.get("schema") != "ATLASQUANT_AION_B2B_CUSTOMER_PORTAL_RECORDS_V1":
            record_blockers.append("CUSTOMER_PORTAL_RECORDS_SCHEMA_INVALID")
        if candidate.get("state") != "READY":
            record_blockers.append("CUSTOMER_PORTAL_RECORDS_NOT_READY")
        if candidate.get("read_only") is not True:
            record_blockers.append("CUSTOMER_PORTAL_RECORDS_NOT_READ_ONLY")
        if candidate.get("secret_material_exposed") is not False:
            record_blockers.append("CUSTOMER_PORTAL_RECORDS_SECRET_BOUNDARY_UNSAFE")
        if candidate.get("executes_action") is not False:
            record_blockers.append("CUSTOMER_PORTAL_RECORDS_EXECUTION_UNSAFE")
        if not _text(candidate.get("evidence_digest"), 180):
            record_blockers.append("CUSTOMER_PORTAL_RECORDS_EVIDENCE_REQUIRED")
        candidate_scope = _scope(candidate.get("scope") if isinstance(candidate.get("scope"), Mapping) else {})
        if candidate_scope["tenant_id"] != decision["service_tenant_id"]:
            record_blockers.append("CUSTOMER_PORTAL_RECORDS_TENANT_MISMATCH")
        if candidate_scope["workspace_id"] != decision["workspace_id"]:
            record_blockers.append("CUSTOMER_PORTAL_RECORDS_WORKSPACE_MISMATCH")
        if _text(candidate.get("customer_id"), 120) != decision["customer_id"]:
            record_blockers.append("CUSTOMER_PORTAL_RECORDS_CUSTOMER_MISMATCH")
        if _text(candidate.get("package"), 40).upper() != decision["package"]:
            record_blockers.append("CUSTOMER_PORTAL_RECORDS_PACKAGE_MISMATCH")
        if record_blockers:
            return {
                "schema": SCHEMA,
                "state": "BLOCKED",
                "allowed": False,
                "blockers": list(dict.fromkeys(record_blockers)),
                "read_only": True,
                "grants_authority": False,
                "executes_action": False,
            }
        safe_records = candidate

    safe_operations = None
    if operations is not None:
        candidate = dict(operations) if isinstance(operations, Mapping) else {}
        operation_blockers: list[str] = []
        if candidate.get("schema") != "ATLASQUANT_AION_B2B_CUSTOMER_PORTAL_OPERATIONS_V1":
            operation_blockers.append("CUSTOMER_PORTAL_OPERATIONS_SCHEMA_INVALID")
        if candidate.get("state") != "READY":
            operation_blockers.append("CUSTOMER_PORTAL_OPERATIONS_NOT_READY")
        if candidate.get("read_only") is not True:
            operation_blockers.append("CUSTOMER_PORTAL_OPERATIONS_NOT_READ_ONLY")
        if candidate.get("automation_control_exposed") is not False:
            operation_blockers.append("CUSTOMER_PORTAL_AUTOMATION_CONTROL_UNSAFE")
        if candidate.get("ticket_write_exposed") is not False:
            operation_blockers.append("CUSTOMER_PORTAL_TICKET_WRITE_UNSAFE")
        if candidate.get("message_content_exposed") is not False:
            operation_blockers.append("CUSTOMER_PORTAL_TICKET_CONTENT_UNSAFE")
        if candidate.get("executes_action") is not False:
            operation_blockers.append("CUSTOMER_PORTAL_OPERATIONS_EXECUTION_UNSAFE")
        if not _text(candidate.get("evidence_digest"), 180):
            operation_blockers.append("CUSTOMER_PORTAL_OPERATIONS_EVIDENCE_REQUIRED")
        candidate_scope = _scope(candidate.get("scope") if isinstance(candidate.get("scope"), Mapping) else {})
        if candidate_scope["tenant_id"] != decision["service_tenant_id"]:
            operation_blockers.append("CUSTOMER_PORTAL_OPERATIONS_TENANT_MISMATCH")
        if candidate_scope["workspace_id"] != decision["workspace_id"]:
            operation_blockers.append("CUSTOMER_PORTAL_OPERATIONS_WORKSPACE_MISMATCH")
        if _text(candidate.get("customer_id"), 120) != decision["customer_id"]:
            operation_blockers.append("CUSTOMER_PORTAL_OPERATIONS_CUSTOMER_MISMATCH")
        if _text(candidate.get("package"), 40).upper() != decision["package"]:
            operation_blockers.append("CUSTOMER_PORTAL_OPERATIONS_PACKAGE_MISMATCH")
        if operation_blockers:
            return {
                "schema": SCHEMA,
                "state": "BLOCKED",
                "allowed": False,
                "blockers": list(dict.fromkeys(operation_blockers)),
                "read_only": True,
                "grants_authority": False,
                "executes_action": False,
            }
        safe_operations = candidate

    safe_pilot_value = None
    if pilot_value_binding is not None:
        candidate = (
            dict(pilot_value_binding)
            if isinstance(pilot_value_binding, Mapping)
            else {}
        )
        pilot_blockers: list[str] = []
        if candidate.get("schema") != PILOT_VALUE_BINDING_SCHEMA:
            pilot_blockers.append("PILOT_VALUE_BINDING_SCHEMA_INVALID")
        if candidate.get("state") != "READY":
            pilot_blockers.append("PILOT_VALUE_BINDING_NOT_READY")
        if candidate.get("allowed") is not True:
            pilot_blockers.append("PILOT_VALUE_BINDING_NOT_ALLOWED")
        if candidate.get("read_only") is not True:
            pilot_blockers.append("PILOT_VALUE_BINDING_NOT_READ_ONLY")
        if candidate.get("customer_safe") is not True:
            pilot_blockers.append("PILOT_VALUE_BINDING_NOT_CUSTOMER_SAFE")
        if candidate.get("internal_economics_exposed") is not False:
            pilot_blockers.append("PILOT_VALUE_BINDING_INTERNAL_ECONOMICS_UNSAFE")
        if candidate.get("retention_risk_exposed") is not False:
            pilot_blockers.append("PILOT_VALUE_BINDING_RETENTION_RISK_UNSAFE")
        if candidate.get("internal_recommendation_exposed") is not False:
            pilot_blockers.append("PILOT_VALUE_BINDING_RECOMMENDATION_UNSAFE")
        if candidate.get("other_tenant_access") is not False:
            pilot_blockers.append("PILOT_VALUE_BINDING_CROSS_TENANT_UNSAFE")
        if candidate.get("admin_memory_access") is not False:
            pilot_blockers.append("PILOT_VALUE_BINDING_ADMIN_MEMORY_UNSAFE")
        if candidate.get("grants_authority") is not False:
            pilot_blockers.append("PILOT_VALUE_BINDING_AUTHORITY_UNSAFE")
        if candidate.get("executes_action") is not False:
            pilot_blockers.append("PILOT_VALUE_BINDING_EXECUTION_UNSAFE")
        if _text(candidate.get("customer_id"), 120) != decision["customer_id"]:
            pilot_blockers.append("PILOT_VALUE_BINDING_CUSTOMER_MISMATCH")
        if _text(candidate.get("service_tenant_id"), 120) != decision["service_tenant_id"]:
            pilot_blockers.append("PILOT_VALUE_BINDING_TENANT_MISMATCH")
        if _text(candidate.get("workspace_id"), 120) != decision["workspace_id"]:
            pilot_blockers.append("PILOT_VALUE_BINDING_WORKSPACE_MISMATCH")
        if not _text(candidate.get("pilot_id"), 120):
            pilot_blockers.append("PILOT_VALUE_BINDING_PILOT_ID_REQUIRED")
        if not _text(candidate.get("evidence_digest"), 180):
            pilot_blockers.append("PILOT_VALUE_BINDING_EVIDENCE_REQUIRED")

        raw_value = (
            dict(candidate.get("pilot_value"))
            if isinstance(candidate.get("pilot_value"), Mapping)
            else {}
        )
        forbidden = (
            "provider_delivery_cost_brl",
            "provider_gross_margin_brl",
            "provider_gross_margin_pct",
            "retention_risk",
            "retention_risk_score",
            "recommendation",
            "review_reasons",
            "low_value_reasons",
            "evidence_refs",
        )
        for key in forbidden:
            if key in raw_value:
                pilot_blockers.append(
                    "PILOT_VALUE_BINDING_FORBIDDEN_FIELD:" + key
                )

        if pilot_blockers:
            return {
                "schema": SCHEMA,
                "state": "BLOCKED",
                "allowed": False,
                "blockers": list(dict.fromkeys(pilot_blockers)),
                "read_only": True,
                "grants_authority": False,
                "executes_action": False,
            }

        quick_wins: list[dict[str, Any]] = []
        for raw in list(raw_value.get("quick_wins") or [])[:5]:
            if not isinstance(raw, Mapping):
                continue
            quick_wins.append(
                {
                    "quick_win": _text(raw.get("quick_win"), 240),
                    "state": _text(raw.get("state"), 40),
                    "achieved": raw.get("achieved") is True,
                }
            )
        safe_pilot_value = {
            "pilot_id": _text(candidate.get("pilot_id"), 120),
            "value_state": _text(raw_value.get("value_state"), 80),
            "health_score": raw_value.get("health_score"),
            "value_trend": _text(raw_value.get("value_trend"), 40),
            "quick_win_completion_pct": raw_value.get("quick_win_completion_pct"),
            "quick_win_achieved_pct": raw_value.get("quick_win_achieved_pct"),
            "quick_wins": quick_wins,
            "observed_savings_brl": raw_value.get("observed_savings_brl"),
            "observed_roi_pct": raw_value.get("observed_roi_pct"),
            "customer_fee_brl": raw_value.get("customer_fee_brl"),
            "customer_value_to_fee_ratio": raw_value.get(
                "customer_value_to_fee_ratio"
            ),
            "customer_net_value_brl": raw_value.get(
                "customer_net_value_brl"
            ),
            "customer_payback_covered": (
                raw_value.get("customer_payback_covered") is True
            ),
            "evidence_digest": _text(
                raw_value.get("evidence_digest"),
                180,
            ),
        }

    safe_recurring = None
    if recurring_projection is not None:
        candidate = (
            dict(recurring_projection)
            if isinstance(recurring_projection, Mapping)
            else {}
        )
        recurring_blockers: list[str] = []
        if candidate.get("schema") != RECURRING_PROJECTION_SCHEMA:
            recurring_blockers.append("RECURRING_PROJECTION_SCHEMA_INVALID")
        if candidate.get("state") != "READY":
            recurring_blockers.append("RECURRING_PROJECTION_NOT_READY")
        if candidate.get("allowed") is not True:
            recurring_blockers.append("RECURRING_PROJECTION_NOT_ALLOWED")
        if candidate.get("read_only") is not True:
            recurring_blockers.append("RECURRING_PROJECTION_NOT_READ_ONLY")
        if candidate.get("customer_safe") is not True:
            recurring_blockers.append("RECURRING_PROJECTION_NOT_CUSTOMER_SAFE")
        for key in (
            "internal_service_cost_exposed",
            "provider_margin_exposed",
            "retention_risk_exposed",
            "internal_recommendation_exposed",
            "internal_review_reasons_exposed",
            "other_tenant_access",
            "admin_memory_access",
            "grants_authority",
            "automatic_billing",
            "automatic_renewal",
            "automatic_expansion",
            "automatic_customer_contact",
            "automatic_deploy",
            "production_mutation",
            "executes_action",
        ):
            if candidate.get(key) is not False:
                recurring_blockers.append(
                    "RECURRING_PROJECTION_UNSAFE_FIELD:" + key
                )
        if _text(candidate.get("customer_id"), 120) != decision["customer_id"]:
            recurring_blockers.append("RECURRING_PROJECTION_CUSTOMER_MISMATCH")
        if (
            _text(candidate.get("service_tenant_id"), 120)
            != decision["service_tenant_id"]
        ):
            recurring_blockers.append("RECURRING_PROJECTION_TENANT_MISMATCH")
        if _text(candidate.get("workspace_id"), 120) != decision["workspace_id"]:
            recurring_blockers.append("RECURRING_PROJECTION_WORKSPACE_MISMATCH")
        if _text(candidate.get("package"), 40).upper() != decision["package"]:
            recurring_blockers.append("RECURRING_PROJECTION_PACKAGE_MISMATCH")
        if not _text(candidate.get("pilot_id"), 120):
            recurring_blockers.append("RECURRING_PROJECTION_PILOT_ID_REQUIRED")
        if not _text(candidate.get("evidence_digest"), 180):
            recurring_blockers.append("RECURRING_PROJECTION_EVIDENCE_REQUIRED")

        forbidden = (
            "actual_service_cost_brl",
            "provider_delivery_cost_brl",
            "provider_gross_margin_brl",
            "provider_gross_margin_pct",
            "retention_risk",
            "retention_risk_score",
            "recommendation",
            "service_decision",
            "review_reasons",
            "incident_reasons",
            "allowed_owner_choices",
            "source_value_decision",
            "source_conversion_decision",
        )
        for key in forbidden:
            if key in candidate:
                recurring_blockers.append(
                    "RECURRING_PROJECTION_FORBIDDEN_FIELD:" + key
                )

        if recurring_blockers:
            return {
                "schema": SCHEMA,
                "state": "BLOCKED",
                "allowed": False,
                "blockers": list(dict.fromkeys(recurring_blockers)),
                "read_only": True,
                "grants_authority": False,
                "executes_action": False,
            }
        safe_recurring = candidate

    effective_support = (
        safe_recurring.get("support")
        if safe_recurring and isinstance(safe_recurring.get("support"), Mapping)
        else support
    )
    effective_usage = (
        safe_recurring.get("usage")
        if safe_recurring and isinstance(safe_recurring.get("usage"), Mapping)
        else model.get("usage")
    )
    effective_service_state = _text(
        safe_recurring.get("service_status")
        if safe_recurring
        else model.get("service_state"),
        80,
    )
    effective_health_label = _text(
        safe_recurring.get("health_label")
        if safe_recurring
        else model.get("health_label"),
        80,
    )
    effective_health_score = (
        safe_recurring.get("health_score")
        if safe_recurring
        else model.get("health_score")
    )
    effective_roi = (
        safe_recurring.get("observed_roi_pct")
        if safe_recurring
        else model.get("observed_roi_pct")
    )
    effective_generated_at = _text(
        safe_recurring.get("generated_at")
        if safe_recurring
        else model.get("generated_at"),
        96,
    )
    effective_evidence_digest = _text(
        safe_recurring.get("evidence_digest")
        if safe_recurring
        else model.get("evidence_digest"),
        180,
    )

    view = {
        "schema": SCHEMA,
        "state": "READY",
        "allowed": True,
        "customer_id": decision["customer_id"],
        "package": decision["package"],
        "service_state": effective_service_state,
        "service_decision": (
            "" if safe_recurring else _text(model.get("service_decision"), 120)
        ),
        "health_label": effective_health_label,
        "health_score": effective_health_score,
        "observed_roi_pct": effective_roi,
        "usage": _copy_usage(effective_usage),
        "support": {
            "avg_first_response_hours": effective_support.get("avg_first_response_hours"),
            "avg_resolution_hours": effective_support.get("avg_resolution_hours"),
            "critical_open_tickets": effective_support.get("critical_open_tickets"),
            "first_response_sla_met": effective_support.get("first_response_sla_met") is True,
            "resolution_sla_met": effective_support.get("resolution_sla_met") is True,
        },
        "review_reasons": (
            [] if safe_recurring
            else [str(x)[:180] for x in list(model.get("review_reasons") or [])[:8]]
        ),
        "incident_reasons": (
            [] if safe_recurring
            else [str(x)[:180] for x in list(model.get("incident_reasons") or [])[:8]]
        ),
        "generated_at": effective_generated_at,
        "evidence_digest": effective_evidence_digest,
        "allowed_sections": list(decision["allowed_sections"]),
        "integrations": list(safe_records.get("integrations") or [])[:20] if safe_records else [],
        "crm": dict(safe_records.get("crm") or {}) if safe_records else {"enabled": False},
        "documents": list(safe_records.get("documents") or [])[:50] if safe_records else [],
        "billing": dict(safe_records.get("billing") or {}) if safe_records else {},
        "records_evidence_digest": _text(safe_records.get("evidence_digest"), 180) if safe_records else "",
        "automations": list(safe_operations.get("automations") or [])[:50] if safe_operations else [],
        "tickets": list(safe_operations.get("tickets") or [])[:100] if safe_operations else [],
        "operation_counts": dict(safe_operations.get("counts") or {}) if safe_operations else {},
        "operations_evidence_digest": _text(safe_operations.get("evidence_digest"), 180) if safe_operations else "",
        "pilot_value": safe_pilot_value or {},
        "pilot_value_evidence_digest": (
            _text(pilot_value_binding.get("evidence_digest"), 180)
            if safe_pilot_value and isinstance(pilot_value_binding, Mapping)
            else ""
        ),
        "pilot_value_internal_economics_exposed": False,
        "pilot_value_retention_risk_exposed": False,
        "pilot_value_internal_recommendation_exposed": False,
        "recurring_projection": dict(safe_recurring) if safe_recurring else {},
        "recurring_projection_evidence_digest": (
            _text(safe_recurring.get("evidence_digest"), 180)
            if safe_recurring
            else ""
        ),
        "recurring_internal_service_cost_exposed": False,
        "recurring_provider_margin_exposed": False,
        "recurring_retention_risk_exposed": False,
        "recurring_internal_recommendation_exposed": False,
        "recurring_internal_review_reasons_exposed": False,
        "read_only": True,
        "admin_memory_access": False,
        "other_tenant_access": False,
        "internal_service_cost_exposed": False,
        "owner_scope_exposed": False,
        "grants_authority": False,
        "automatic_billing": False,
        "automatic_renewal": False,
        "automatic_quota_change": False,
        "automatic_role_change": False,
        "automatic_customer_contact": False,
        "automatic_deploy": False,
        "production_mutation": False,
        "executes_action": False,
    }
    return view


def _fmt(value: Any, suffix: str = "") -> str:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return "—"
    if isinstance(value, float):
        text = f"{value:.2f}".rstrip("0").rstrip(".")
    else:
        text = str(value)
    return text + suffix


def customer_portal_html(view: Mapping[str, Any] | None) -> str:
    """Render customer-safe HTML. Never renders internal cost or action controls."""
    data = dict(view) if isinstance(view, Mapping) else {}
    if data.get("state") != "READY" or data.get("allowed") is not True:
        return (
            '<section class="aq-customer-portal aq-customer-portal-blocked">'
            '<h2>Portal do Cliente</h2>'
            '<p>Dados do cliente indisponíveis até a validação do acesso e das evidências.</p>'
            '</section>'
        )

    allowed = set(data.get("allowed_sections") or [])
    cards: list[str] = []
    if "overview" in allowed:
        cards.extend([
            f'<article><small>PACOTE</small><strong>{escape(str(data.get("package") or "—"))}</strong></article>',
            f'<article><small>SAÚDE</small><strong>{escape(_fmt(data.get("health_score"), "%"))}</strong>'
            f'<span>{escape(str(data.get("health_label") or "—"))}</span></article>',
            f'<article><small>ESTADO DO SERVIÇO</small><strong>{escape(str(data.get("service_state") or "—"))}</strong></article>',
        ])
    if "value" in allowed:
        cards.append(
            f'<article><small>ROI OBSERVADO</small><strong>{escape(_fmt(data.get("observed_roi_pct"), "%"))}</strong>'
            '<span>Baseado em evidência validada do serviço</span></article>'
        )
        pilot_value = (
            data.get("pilot_value")
            if isinstance(data.get("pilot_value"), Mapping)
            else {}
        )
        if pilot_value:
            cards.extend([
                f'<article><small>VALOR DO PILOTO</small><strong>{escape(str(pilot_value.get("value_state") or "—"))}</strong>'
                f'<span>{escape(str(pilot_value.get("value_trend") or "—"))}</span></article>',
                f'<article><small>ROI DO PILOTO</small><strong>{escape(_fmt(pilot_value.get("observed_roi_pct"), "%"))}</strong>'
                '<span>Evidência vinculada ao piloto deste cliente</span></article>',
                f'<article><small>ECONOMIA OBSERVADA</small><strong>R$ {escape(_fmt(pilot_value.get("observed_savings_brl")))}</strong>'
                '<span>Valor observado; não é promessa futura</span></article>',
                f'<article><small>QUICK WINS</small><strong>{escape(_fmt(pilot_value.get("quick_win_achieved_pct"), "%"))}</strong>'
                '<span>Entregas rápidas comprovadas</span></article>',
                f'<article><small>PAYBACK</small><strong>{"COBERTO" if pilot_value.get("customer_payback_covered") is True else "EM REVISÃO"}</strong>'
                '<span>Comparação entre valor observado e fee</span></article>',
            ])
    if "usage" in allowed:
        usage = data.get("usage") if isinstance(data.get("usage"), Mapping) else {}
        for key, label in (
            ("capacity", "CAPACIDADE"),
            ("calls", "CHAMADAS"),
            ("tokens", "TOKENS"),
            ("support_tickets", "SUPORTE"),
        ):
            row = usage.get(key) if isinstance(usage.get(key), Mapping) else {}
            cards.append(
                f'<article><small>{escape(label)}</small>'
                f'<strong>{escape(_fmt(row.get("utilization_pct"), "%"))}</strong>'
                f'<span>{escape(_fmt(row.get("used")))} / {escape(_fmt(row.get("limit")))}</span></article>'
            )
    if "support" in allowed:
        support = data.get("support") if isinstance(data.get("support"), Mapping) else {}
        cards.extend([
            f'<article><small>1ª RESPOSTA</small><strong>{escape(_fmt(support.get("avg_first_response_hours"), "h"))}</strong>'
            f'<span>{"SLA cumprido" if support.get("first_response_sla_met") is True else "SLA em revisão"}</span></article>',
            f'<article><small>RESOLUÇÃO</small><strong>{escape(_fmt(support.get("avg_resolution_hours"), "h"))}</strong>'
            f'<span>{"SLA cumprido" if support.get("resolution_sla_met") is True else "SLA em revisão"}</span></article>',
        ])
    if "integrations" in allowed:
        for row in list(data.get("integrations") or [])[:20]:
            if not isinstance(row, Mapping):
                continue
            cards.append(
                '<article><small>INTEGRAÇÃO</small>'
                f'<strong>{escape(str(row.get("name") or "—"))}</strong>'
                f'<span>{escape(str(row.get("state") or "—"))}</span></article>'
            )
    if "crm" in allowed:
        crm = data.get("crm") if isinstance(data.get("crm"), Mapping) else {}
        if crm.get("enabled") is True:
            cards.extend([
                f'<article><small>CRM · CONTATOS</small><strong>{escape(_fmt(crm.get("contacts")))}</strong></article>',
                f'<article><small>CRM · OPORTUNIDADES</small><strong>{escape(_fmt(crm.get("open_opportunities")))}</strong></article>',
                f'<article><small>CRM · TAREFAS</small><strong>{escape(_fmt(crm.get("open_tasks")))}</strong></article>',
            ])
    if "billing" in allowed:
        billing = data.get("billing") if isinstance(data.get("billing"), Mapping) else {}
        if billing:
            amount = billing.get("amount_due_brl")
            cards.extend([
                f'<article><small>ASSINATURA</small><strong>{escape(str(billing.get("subscription_state") or "—"))}</strong></article>',
                f'<article><small>PAGAMENTO</small><strong>{escape(str(billing.get("payment_state") or "—"))}</strong>'
                f'<span>R$ {escape(_fmt(amount))}</span></article>',
            ])
    if "automations" in allowed:
        for row in list(data.get("automations") or [])[:50]:
            if not isinstance(row, Mapping):
                continue
            cards.append(
                '<article><small>AUTOMAÇÃO</small>'
                f'<strong>{escape(str(row.get("name") or "—"))}</strong>'
                f'<span>{escape(str(row.get("state") or "—"))} · '
                f'{escape(str(row.get("last_result") or "—"))}</span></article>'
            )
    tickets_html = ""
    if "tickets" in allowed and data.get("tickets"):
        rows = []
        for row in list(data.get("tickets") or [])[:100]:
            if not isinstance(row, Mapping):
                continue
            rows.append(
                '<li><strong>' + escape(str(row.get("title") or "—")) + '</strong> · '
                + escape(str(row.get("priority") or "—")) + ' · '
                + escape(str(row.get("state") or "—")) + ' · SLA '
                + escape(str(row.get("sla_state") or "—")) + '</li>'
            )
        if rows:
            tickets_html = '<section class="aq-customer-portal-tickets"><h3>Chamados</h3><ul>' + "".join(rows) + '</ul></section>'

    documents_html = ""
    if "documents" in allowed and data.get("documents"):
        rows = []
        for row in list(data.get("documents") or [])[:50]:
            if not isinstance(row, Mapping):
                continue
            rows.append(
                '<li><strong>' + escape(str(row.get("title") or "—")) + '</strong> · '
                + escape(str(row.get("type") or "—")) + ' · '
                + escape(str(row.get("state") or "—")) + '</li>'
            )
        if rows:
            documents_html = '<section class="aq-customer-portal-docs"><h3>Documentos</h3><ul>' + "".join(rows) + '</ul></section>'

    notices: list[str] = []
    for item in list(data.get("review_reasons") or [])[:5]:
        notices.append(f"<li>{escape(str(item))}</li>")
    for item in list(data.get("incident_reasons") or [])[:5]:
        notices.append(f"<li>{escape(str(item))}</li>")
    notices_html = (
        '<aside class="aq-customer-portal-review"><strong>Itens em revisão</strong><ul>'
        + "".join(notices)
        + "</ul></aside>"
        if notices else ""
    )

    return (
        '<section class="aq-customer-portal" data-customer-portal="read-only">'
        '<header><div><small>ATLASQUANT · CLIENTE</small><h2>Portal do Cliente</h2>'
        f'<p>{escape(str(data.get("customer_id") or "—"))}</p></div>'
        '<span>SOMENTE LEITURA</span></header>'
        '<div class="aq-customer-portal-grid">'
        + "".join(cards)
        + "</div>"
        + documents_html
        + tickets_html
        + notices_html
        + f'<footer>Atualização: {escape(str(data.get("generated_at") or "—"))} · '
        'Nenhuma cobrança, renovação ou alteração operacional pode ser executada por esta tela.</footer>'
        "</section>"
    )


def render_customer_portal(
    st: Any,
    *,
    access: Mapping[str, Any] | None,
    binding: Mapping[str, Any] | None,
    read_model: Mapping[str, Any] | None,
    records: Mapping[str, Any] | None = None,
    operations: Mapping[str, Any] | None = None,
    pilot_value_binding: Mapping[str, Any] | None = None,
    recurring_projection: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Optional Streamlit host adapter. Rendering only; no mutation path."""
    view = customer_portal_view_model(
        access,
        binding,
        read_model,
        records,
        operations,
        pilot_value_binding,
        recurring_projection,
    )
    st.markdown(customer_portal_html(view), unsafe_allow_html=True)
    return view


__all__ = [
    "SCHEMA",
    "PORTAL_SCOPE",
    "SAFE_SECTIONS",
    "normalize_customer_portal_binding",
    "customer_portal_access",
    "customer_portal_view_model",
    "customer_portal_html",
    "render_customer_portal",
]
