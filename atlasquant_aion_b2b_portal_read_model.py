"""AION B2B customer-portal read model.

Pure/offline presentation contract. It converts already-reviewed managed-service
evidence into a bounded, tenant-scoped read model for the Negócios cockpit.
It never grants authority, mutates customer data, bills, renews, changes quotas,
changes roles, calls providers, or deploys.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Any, Mapping
import json
import math

SCHEMA = "ATLASQUANT_AION_B2B_PORTAL_READ_MODEL_V1"


def _text(value: Any, limit: int = 320) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.replace("\x00", "").split())[:limit]


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _pct(value: Any) -> float | None:
    out = _number(value)
    if out is None or out < 0 or out > 100:
        return None
    return round(out, 2)


def _nonnegative_int(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


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


def build_customer_portal_read_model(
    *,
    trusted_scope: Mapping[str, Any],
    contract_result: Mapping[str, Any],
    cycle_result: Mapping[str, Any],
    usage_evidence: Mapping[str, Any],
    support_evidence: Mapping[str, Any],
    generated_at: str,
    evidence_refs: list[str] | tuple[str, ...],
) -> dict[str, Any]:
    """Return a safe customer-facing/admin-facing presentation snapshot.

    Inputs must already be produced by the controlled B2B pipeline. This function
    validates identity/scope/evidence and intentionally exposes no mutation affordance.
    """
    trusted = _scope(trusted_scope)
    blockers: list[str] = []
    if not all(trusted.values()):
        blockers.append("TRUSTED_SCOPE_INVALID")

    contract_result = dict(contract_result) if isinstance(contract_result, Mapping) else {}
    cycle_result = dict(cycle_result) if isinstance(cycle_result, Mapping) else {}
    usage = dict(usage_evidence) if isinstance(usage_evidence, Mapping) else {}
    support = dict(support_evidence) if isinstance(support_evidence, Mapping) else {}

    if contract_result.get("state") != "DRAFT_FOR_OWNER_ACTIVATION":
        blockers.append("SERVICE_CONTRACT_NOT_REVIEWABLE")
    if contract_result.get("activation_state") != "BLOCKED_UNTIL_OWNER_ACTIVATION":
        blockers.append("SERVICE_CONTRACT_BOUNDARY_INVALID")
    if contract_result.get("blockers"):
        blockers.append("SERVICE_CONTRACT_HAS_BLOCKERS")
    if not _text(contract_result.get("contract_digest"), 180):
        blockers.append("SERVICE_CONTRACT_DIGEST_REQUIRED")

    contract = contract_result.get("contract")
    contract = dict(contract) if isinstance(contract, Mapping) else {}
    if _scope(contract) != trusted:
        blockers.append("SERVICE_CONTRACT_SCOPE_MISMATCH")

    customer_id = _text(contract.get("customer_id"), 120)
    package = _text(contract.get("package"), 40).upper()
    if not customer_id:
        blockers.append("CUSTOMER_ID_REQUIRED")
    if not package:
        blockers.append("PACKAGE_REQUIRED")

    allowed_cycle_states = {"HEALTHY", "REMEDIATION", "CAPACITY_HOLD", "INCIDENT_REVIEW"}
    allowed_decisions = {
        "RENEWAL_REVIEW_CANDIDATE",
        "REMEDIATE_REVIEW",
        "CAPACITY_REVIEW",
        "INCIDENT_REVIEW",
    }
    if _scope(cycle_result) != trusted:
        blockers.append("SERVICE_CYCLE_SCOPE_MISMATCH")
    if cycle_result.get("state") not in allowed_cycle_states:
        blockers.append("SERVICE_CYCLE_STATE_NOT_PRESENTABLE")
    if cycle_result.get("decision") not in allowed_decisions:
        blockers.append("SERVICE_CYCLE_DECISION_NOT_PRESENTABLE")
    if cycle_result.get("blockers"):
        blockers.append("SERVICE_CYCLE_HAS_BLOCKERS")
    if cycle_result.get("customer_id") != customer_id:
        blockers.append("SERVICE_CYCLE_CUSTOMER_MISMATCH")
    if _text(cycle_result.get("package"), 40).upper() != package:
        blockers.append("SERVICE_CYCLE_PACKAGE_MISMATCH")
    if not _text(cycle_result.get("evidence_digest"), 180):
        blockers.append("SERVICE_CYCLE_EVIDENCE_DIGEST_REQUIRED")

    if _scope(usage) != trusted:
        blockers.append("USAGE_SCOPE_MISMATCH")
    if _text(usage.get("customer_id"), 120) not in {"", customer_id}:
        blockers.append("USAGE_CUSTOMER_MISMATCH")
    if _scope(support) != trusted:
        blockers.append("SUPPORT_SCOPE_MISMATCH")
    if _text(support.get("customer_id"), 120) not in {"", customer_id}:
        blockers.append("SUPPORT_CUSTOMER_MISMATCH")

    used_capacity = _nonnegative_int(usage.get("used_capacity_units"))
    calls = _nonnegative_int(usage.get("calls"))
    tokens = _nonnegative_int(usage.get("tokens"))
    tickets = _nonnegative_int(usage.get("support_tickets"))
    for key, value in (
        ("USED_CAPACITY_UNITS", used_capacity),
        ("CALLS", calls),
        ("TOKENS", tokens),
        ("SUPPORT_TICKETS", tickets),
    ):
        if value is None:
            blockers.append(f"{key}_INVALID")

    first_response = _number(support.get("avg_first_response_hours"))
    resolution = _number(support.get("avg_resolution_hours"))
    critical_open = _nonnegative_int(support.get("critical_open_tickets"))
    if first_response is None or first_response < 0:
        blockers.append("SUPPORT_FIRST_RESPONSE_INVALID")
    if resolution is None or resolution < 0:
        blockers.append("SUPPORT_RESOLUTION_INVALID")
    if critical_open is None:
        blockers.append("SUPPORT_CRITICAL_OPEN_INVALID")

    health_score = _pct(cycle_result.get("health_score"))
    roi_pct = _number(cycle_result.get("observed_roi_pct"))
    actual_cost = _number(cycle_result.get("actual_service_cost_brl"))
    if health_score is None:
        blockers.append("HEALTH_SCORE_INVALID")
    if roi_pct is None:
        blockers.append("ROI_INVALID")
    if actual_cost is None or actual_cost < 0:
        blockers.append("ACTUAL_SERVICE_COST_INVALID")

    generated = _text(generated_at, 96)
    if not generated:
        blockers.append("GENERATED_AT_REQUIRED")

    refs = _refs(evidence_refs)
    if len(refs) < 4:
        blockers.append("PORTAL_EVIDENCE_INSUFFICIENT")

    limits = {
        "capacity_units": _nonnegative_int(contract.get("max_capacity_units")),
        "calls": _nonnegative_int(contract.get("max_calls_per_cycle")),
        "tokens": _nonnegative_int(contract.get("max_tokens_per_cycle")),
        "support_tickets": _nonnegative_int(contract.get("max_support_tickets_per_cycle")),
    }
    if any(value is None or value <= 0 for value in limits.values()):
        blockers.append("CONTRACT_LIMITS_INVALID")

    sla = {
        "first_response_hours": _number(contract.get("sla_first_response_hours")),
        "resolution_hours": _number(contract.get("sla_resolution_hours")),
    }
    if (
        sla["first_response_hours"] is None
        or sla["first_response_hours"] <= 0
        or sla["resolution_hours"] is None
        or sla["resolution_hours"] <= 0
    ):
        blockers.append("CONTRACT_SLA_INVALID")

    def utilization(used: int | None, limit: int | None) -> float | None:
        if used is None or limit is None or limit <= 0:
            return None
        return round(used / limit * 100.0, 2)

    usage_view = {
        "capacity": {
            "used": used_capacity,
            "limit": limits["capacity_units"],
            "utilization_pct": utilization(used_capacity, limits["capacity_units"]),
        },
        "calls": {
            "used": calls,
            "limit": limits["calls"],
            "utilization_pct": utilization(calls, limits["calls"]),
        },
        "tokens": {
            "used": tokens,
            "limit": limits["tokens"],
            "utilization_pct": utilization(tokens, limits["tokens"]),
        },
        "support_tickets": {
            "used": tickets,
            "limit": limits["support_tickets"],
            "utilization_pct": utilization(tickets, limits["support_tickets"]),
        },
    }

    first_sla_met = (
        first_response is not None
        and sla["first_response_hours"] is not None
        and first_response <= sla["first_response_hours"]
    )
    resolution_sla_met = (
        resolution is not None
        and sla["resolution_hours"] is not None
        and resolution <= sla["resolution_hours"]
    )

    health_label = {
        "HEALTHY": "SAUDÁVEL",
        "REMEDIATION": "ATENÇÃO",
        "CAPACITY_HOLD": "CAPACIDADE",
        "INCIDENT_REVIEW": "INCIDENTE",
    }.get(str(cycle_result.get("state")), "INDISPONÍVEL")

    evidence = {
        "scope": trusted,
        "customer_id": customer_id,
        "package": package,
        "contract_digest": _text(contract_result.get("contract_digest"), 180),
        "cycle_digest": _text(cycle_result.get("evidence_digest"), 180),
        "generated_at": generated,
        "health_score": health_score,
        "roi_pct": roi_pct,
        "actual_service_cost_brl": actual_cost,
        "usage": usage_view,
        "support": {
            "avg_first_response_hours": first_response,
            "avg_resolution_hours": resolution,
            "critical_open_tickets": critical_open,
            "first_response_sla_met": first_sla_met,
            "resolution_sla_met": resolution_sla_met,
        },
        "evidence_refs": refs,
    }

    return {
        "schema": SCHEMA,
        "state": "READY" if not blockers else "BLOCKED",
        "scope": dict(trusted),
        "customer_id": customer_id,
        "package": package,
        "service_state": cycle_result.get("state"),
        "service_decision": cycle_result.get("decision"),
        "health_label": health_label,
        "health_score": health_score,
        "observed_roi_pct": roi_pct,
        "actual_service_cost_brl": actual_cost,
        "usage": usage_view,
        "support": evidence["support"],
        "review_reasons": list(cycle_result.get("review_reasons") or [])[:20],
        "incident_reasons": list(cycle_result.get("incident_reasons") or [])[:20],
        "generated_at": generated,
        "evidence_refs": refs,
        "evidence_digest": _digest(evidence),
        "blockers": list(dict.fromkeys(blockers)),
        "read_only": True,
        "grants_authority": False,
        "automatic_renewal": False,
        "automatic_billing": False,
        "automatic_quota_change": False,
        "automatic_role_change": False,
        "automatic_customer_contact": False,
        "automatic_deploy": False,
        "production_mutation": False,
        "executes_action": False,
    }


__all__ = ["SCHEMA", "build_customer_portal_read_model"]
