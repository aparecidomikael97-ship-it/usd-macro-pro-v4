"""AION B2B handoff from value-bound conversion to managed-service draft.

Pure/offline compatibility bridge. It accepts only a reviewable value-bound
conversion result, preserves the pilot/customer/scope binding, and delegates to
the existing managed-service contract builder. The output remains blocked until
separate owner activation and never performs external actions.
"""
from __future__ import annotations

from typing import Any, Mapping

from atlasquant_aion_b2b_managed_service_control import (
    build_managed_service_contract,
)

SCHEMA = "ATLASQUANT_AION_B2B_VALUE_BOUND_MANAGED_SERVICE_HANDOFF_V1"
VALUE_BOUND_CONVERSION_SCHEMA = "ATLASQUANT_AION_B2B_VALUE_BOUND_CONVERSION_V1"

ELIGIBLE_DECISIONS = {
    "EXPANSION_COMMERCIAL_REVIEW_CANDIDATE",
    "CONTINUE_COMMERCIAL_REVIEW_CANDIDATE",
}

UNSAFE_FIELDS = (
    "automatic_conversion",
    "automatic_expansion",
    "automatic_package_change",
    "automatic_pricing_change",
    "automatic_contract",
    "automatic_billing",
    "automatic_provisioning",
    "automatic_customer_contact",
    "automatic_renewal",
    "automatic_deploy",
    "crm_write",
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


def build_value_bound_managed_service_contract(
    *,
    trusted_scope: Mapping[str, Any],
    value_bound_conversion: Mapping[str, Any],
    owner_commercial_approval: Mapping[str, Any],
    spec: Mapping[str, Any],
) -> dict[str, Any]:
    trusted = _scope(trusted_scope)
    gate = (
        dict(value_bound_conversion)
        if isinstance(value_bound_conversion, Mapping)
        else {}
    )
    blockers: list[str] = []

    if not all(trusted.values()):
        blockers.append("TRUSTED_SCOPE_INVALID")
    if gate.get("schema") != VALUE_BOUND_CONVERSION_SCHEMA:
        blockers.append("VALUE_BOUND_CONVERSION_SCHEMA_INVALID")
    if gate.get("state") != "REVIEWABLE":
        blockers.append("VALUE_BOUND_CONVERSION_NOT_REVIEWABLE")
    if gate.get("decision") not in ELIGIBLE_DECISIONS:
        blockers.append("VALUE_BOUND_CONVERSION_DECISION_INVALID")
    if _scope(gate.get("scope")) != trusted:
        blockers.append("VALUE_BOUND_CONVERSION_SCOPE_MISMATCH")
    if gate.get("blockers"):
        blockers.append("VALUE_BOUND_CONVERSION_HAS_BLOCKERS")
    if gate.get("owner_commercial_approval_required") is not True:
        blockers.append("VALUE_BOUND_OWNER_APPROVAL_BOUNDARY_MISSING")
    if gate.get("owner_review_required") is not True:
        blockers.append("VALUE_BOUND_OWNER_REVIEW_BOUNDARY_MISSING")
    if not _text(gate.get("evidence_digest"), 180):
        blockers.append("VALUE_BOUND_CONVERSION_EVIDENCE_DIGEST_REQUIRED")

    customer_id = _text(gate.get("customer_id"), 120)
    pilot_id = _text(gate.get("pilot_id"), 120)
    package = _text(gate.get("recommended_package"), 40).upper()
    if not customer_id:
        blockers.append("VALUE_BOUND_CUSTOMER_ID_REQUIRED")
    if not pilot_id:
        blockers.append("VALUE_BOUND_PILOT_ID_REQUIRED")
    if package not in {"ESSENCIAL", "PROFISSIONAL", "COMPLETO"}:
        blockers.append("VALUE_BOUND_PACKAGE_INVALID")

    for key in UNSAFE_FIELDS:
        if gate.get(key) is not False:
            blockers.append("VALUE_BOUND_UNSAFE_FIELD:" + key)

    if blockers:
        return {
            "schema": SCHEMA,
            "state": "BLOCKED",
            "activation_state": "BLOCKED_UNTIL_OWNER_ACTIVATION",
            "customer_id": customer_id,
            "pilot_id": pilot_id,
            "package": package,
            "contract": {},
            "blockers": list(dict.fromkeys(blockers)),
            "owner_activation_required": True,
            "automatic_activation": False,
            "automatic_contract_signature": False,
            "automatic_billing": False,
            "automatic_provisioning": False,
            "automatic_integration_enablement": False,
            "automatic_role_grant": False,
            "automatic_customer_contact": False,
            "automatic_renewal": False,
            "automatic_deploy": False,
            "provider_called": False,
            "production_mutation": False,
            "executes_action": False,
        }

    compatibility_conversion = {
        "state": "REVIEWABLE",
        "decision": "COMMERCIAL_REVIEW_CANDIDATE",
        "customer_id": customer_id,
        "recommended_package": package,
        "review_reasons": [],
        "blockers": [],
        "owner_commercial_approval_required": True,
        "evidence_digest": _text(gate.get("evidence_digest"), 180),
    }

    result = build_managed_service_contract(
        trusted_scope=trusted_scope,
        conversion=compatibility_conversion,
        owner_commercial_approval=owner_commercial_approval,
        spec=spec,
    )

    output = dict(result)
    output["schema"] = SCHEMA
    output["source_contract_schema"] = result.get("schema")
    output["customer_id"] = customer_id
    output["pilot_id"] = pilot_id
    output["package"] = package
    output["value_bound_conversion_digest"] = _text(
        gate.get("evidence_digest"),
        180,
    )
    output["source_value_decision"] = gate.get("value_recommendation")
    output["source_conversion_decision"] = gate.get("decision")
    output["owner_review_required"] = True
    output["automatic_customer_contact"] = False
    output["automatic_renewal"] = False
    output["provider_called"] = False
    output["production_mutation"] = False
    output["executes_action"] = False
    return output


__all__ = [
    "SCHEMA",
    "VALUE_BOUND_CONVERSION_SCHEMA",
    "ELIGIBLE_DECISIONS",
    "build_value_bound_managed_service_contract",
]
