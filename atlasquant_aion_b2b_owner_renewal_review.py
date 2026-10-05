"""AION B2B owner-only renewal and continuation review packet.

Pure/offline governance layer. It consumes the value-bound recurring service cycle
and turns it into an owner review packet. It never renews, expands, pauses,
terminates, bills, reprices, changes package/quotas/roles/integrations, contacts a
customer, calls providers, deploys, or mutates production.
"""
from __future__ import annotations

from hashlib import sha256
import json
from typing import Any, Mapping

from atlasquant_aion_b2b_value_bound_service_cycle import (
    SCHEMA as SERVICE_CYCLE_SCHEMA,
)

SCHEMA = "ATLASQUANT_AION_B2B_OWNER_RENEWAL_REVIEW_V1"

STATE_DECISION = {
    ("HEALTHY", "RENEWAL_REVIEW_CANDIDATE"): "RENEWAL_REVIEW",
    ("REMEDIATION", "REMEDIATE_REVIEW"): "REMEDIATION_REVIEW",
    ("CAPACITY_HOLD", "CAPACITY_REVIEW"): "CAPACITY_REVIEW",
    ("INCIDENT_REVIEW", "INCIDENT_REVIEW"): "INCIDENT_REVIEW",
}

CHOICES = {
    "RENEWAL_REVIEW": (
        "RENEW_AS_IS_REVIEW",
        "RENEW_WITH_CHANGES_REVIEW",
        "NON_RENEWAL_REVIEW",
    ),
    "REMEDIATION_REVIEW": (
        "REMEDIATION_PLAN_REVIEW",
        "RENEW_WITH_CHANGES_REVIEW",
        "NON_RENEWAL_REVIEW",
    ),
    "CAPACITY_REVIEW": (
        "RESCOPE_CAPACITY_REVIEW",
        "REPRICE_REVIEW",
        "NON_RENEWAL_REVIEW",
    ),
    "INCIDENT_REVIEW": (
        "INCIDENT_REMEDIATION_REVIEW",
        "PAUSE_SERVICE_REVIEW",
        "TERMINATION_REVIEW",
    ),
}

UNSAFE_FIELDS = (
    "automatic_renewal",
    "automatic_expansion",
    "automatic_package_change",
    "automatic_pause",
    "automatic_termination",
    "automatic_billing",
    "automatic_quota_increase",
    "automatic_role_change",
    "automatic_integration_change",
    "automatic_customer_contact",
    "automatic_provisioning",
    "automatic_deploy",
    "provider_called",
    "production_mutation",
    "executes_action",
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
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def _digest(value: Any) -> str:
    return "sha256:" + sha256(_canonical(value).encode("utf-8")).hexdigest()


def build_owner_renewal_review_packet(
    *,
    trusted_scope: Mapping[str, Any],
    service_cycle: Mapping[str, Any],
) -> dict[str, Any]:
    trusted = _scope(trusted_scope)
    cycle = dict(service_cycle) if isinstance(service_cycle, Mapping) else {}
    blockers: list[str] = []

    if not all(trusted.values()):
        blockers.append("TRUSTED_SCOPE_INVALID")
    if cycle.get("schema") != SERVICE_CYCLE_SCHEMA:
        blockers.append("SERVICE_CYCLE_SCHEMA_INVALID")
    if _scope(cycle.get("scope")) != trusted or _scope(cycle) != trusted:
        blockers.append("SERVICE_CYCLE_SCOPE_MISMATCH")
    if cycle.get("blockers"):
        blockers.append("SERVICE_CYCLE_HAS_BLOCKERS")
    if cycle.get("owner_review_required") is not True:
        blockers.append("OWNER_REVIEW_BOUNDARY_MISSING")
    if cycle.get("customer_visible") is not False:
        blockers.append("INTERNAL_CYCLE_VISIBILITY_BOUNDARY_INVALID")
    if cycle.get("contains_internal_finops") is not True:
        blockers.append("INTERNAL_FINOPS_MARKER_REQUIRED")
    if cycle.get("requires_customer_safe_projection") is not True:
        blockers.append("CUSTOMER_SAFE_PROJECTION_BOUNDARY_MISSING")

    customer_id = _text(cycle.get("customer_id"), 120)
    pilot_id = _text(cycle.get("pilot_id"), 120)
    package = _text(cycle.get("package"), 40).upper()
    if not customer_id:
        blockers.append("CUSTOMER_ID_REQUIRED")
    if not pilot_id:
        blockers.append("PILOT_ID_REQUIRED")
    if not package:
        blockers.append("PACKAGE_REQUIRED")

    pair = (cycle.get("state"), cycle.get("decision"))
    review_type = STATE_DECISION.get(pair, "")
    if not review_type:
        blockers.append("SERVICE_CYCLE_STATE_DECISION_INVALID")

    for field in (
        "evidence_digest",
        "contract_digest",
        "value_bound_conversion_digest",
        "source_cycle_evidence_digest",
    ):
        if not _text(cycle.get(field), 180):
            blockers.append(field.upper() + "_REQUIRED")

    for key in UNSAFE_FIELDS:
        if cycle.get(key) is not False:
            blockers.append("SERVICE_CYCLE_UNSAFE_FIELD:" + key)

    source_conversion_decision = _text(
        cycle.get("source_conversion_decision"),
        120,
    )
    source_value_decision = _text(
        cycle.get("source_value_decision"),
        120,
    )

    expansion_review_candidate = (
        source_conversion_decision
        == "EXPANSION_COMMERCIAL_REVIEW_CANDIDATE"
    )
    continuation_review_candidate = (
        source_conversion_decision
        == "CONTINUE_COMMERCIAL_REVIEW_CANDIDATE"
    )
    if source_conversion_decision and not (
        expansion_review_candidate or continuation_review_candidate
    ):
        blockers.append("SOURCE_CONVERSION_DECISION_INVALID")

    state = "REVIEWABLE" if not blockers else "BLOCKED"
    decision = "OWNER_REVIEW_REQUIRED" if not blockers else "BLOCKED"
    choices = list(CHOICES.get(review_type, ())) if not blockers else []

    evidence = {
        "scope": trusted,
        "customer_id": customer_id,
        "pilot_id": pilot_id,
        "package": package,
        "review_type": review_type,
        "choices": choices,
        "cycle_digest": _text(cycle.get("evidence_digest"), 180),
        "contract_digest": _text(cycle.get("contract_digest"), 180),
        "value_bound_conversion_digest": _text(
            cycle.get("value_bound_conversion_digest"),
            180,
        ),
        "source_conversion_decision": source_conversion_decision,
        "source_value_decision": source_value_decision,
    }

    return {
        "schema": SCHEMA,
        "state": state,
        "decision": decision,
        "review_type": review_type,
        "scope": dict(trusted),
        "owner_id": trusted["owner_id"],
        "tenant_id": trusted["tenant_id"],
        "workspace_id": trusted["workspace_id"],
        "customer_id": customer_id,
        "pilot_id": pilot_id,
        "package": package,
        "service_state": cycle.get("state"),
        "service_decision": cycle.get("decision"),
        "health_score": cycle.get("health_score"),
        "observed_roi_pct": cycle.get("observed_roi_pct"),
        "actual_service_cost_brl": cycle.get("actual_service_cost_brl"),
        "review_reasons": list(cycle.get("review_reasons") or [])[:40],
        "incident_reasons": list(cycle.get("incident_reasons") or [])[:40],
        "allowed_owner_choices": choices,
        "source_value_decision": source_value_decision,
        "source_conversion_decision": source_conversion_decision,
        "expansion_review_candidate": expansion_review_candidate,
        "continuation_review_candidate": continuation_review_candidate,
        "cycle_evidence_digest": _text(cycle.get("evidence_digest"), 180),
        "contract_digest": _text(cycle.get("contract_digest"), 180),
        "value_bound_conversion_digest": _text(
            cycle.get("value_bound_conversion_digest"),
            180,
        ),
        "evidence_digest": _digest(evidence),
        "blockers": list(dict.fromkeys(blockers)),
        "owner_decision_required": True,
        "owner_only": True,
        "customer_visible": False,
        "automatic_owner_choice": False,
        "automatic_renewal": False,
        "automatic_expansion": False,
        "automatic_package_change": False,
        "automatic_pause": False,
        "automatic_termination": False,
        "automatic_billing": False,
        "automatic_pricing_change": False,
        "automatic_quota_increase": False,
        "automatic_role_change": False,
        "automatic_integration_change": False,
        "automatic_customer_contact": False,
        "automatic_provisioning": False,
        "automatic_deploy": False,
        "provider_called": False,
        "crm_write": False,
        "production_mutation": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "STATE_DECISION",
    "CHOICES",
    "build_owner_renewal_review_packet",
]
