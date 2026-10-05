"""AION B2B bridge from value-bound managed service to recurring cycle review.

Pure/offline governance adapter. It accepts only the value-bound managed-service
draft, preserves customer/pilot/scope lineage, delegates evidence evaluation to
the existing recurring managed-service cycle, and never renews, expands, bills,
contacts, provisions, deploys, or mutates production.
"""
from __future__ import annotations

from hashlib import sha256
import json
from typing import Any, Mapping

from atlasquant_aion_b2b_managed_service_control import (
    evaluate_managed_service_cycle,
)

SCHEMA = "ATLASQUANT_AION_B2B_VALUE_BOUND_SERVICE_CYCLE_V1"
SOURCE_SCHEMA = "ATLASQUANT_AION_B2B_VALUE_BOUND_MANAGED_SERVICE_HANDOFF_V1"

UNSAFE_SOURCE_FIELDS = (
    "automatic_activation",
    "automatic_contract_signature",
    "automatic_billing",
    "automatic_provisioning",
    "automatic_integration_enablement",
    "automatic_role_grant",
    "automatic_customer_contact",
    "automatic_renewal",
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


def _optional_identity_mismatch(
    raw: Mapping[str, Any] | None,
    *,
    customer_id: str,
    pilot_id: str,
    prefix: str,
) -> list[str]:
    data = dict(raw) if isinstance(raw, Mapping) else {}
    blockers: list[str] = []
    evidence_customer = _text(data.get("customer_id"), 120)
    evidence_pilot = _text(data.get("pilot_id"), 120)
    if evidence_customer and evidence_customer != customer_id:
        blockers.append(prefix + "_CUSTOMER_MISMATCH")
    if evidence_pilot and evidence_pilot != pilot_id:
        blockers.append(prefix + "_PILOT_MISMATCH")
    return blockers


def evaluate_value_bound_service_cycle(
    *,
    trusted_scope: Mapping[str, Any],
    value_bound_service: Mapping[str, Any],
    owner_activation_attestation: Mapping[str, Any],
    tenant_evidence: Mapping[str, Any],
    finops_evidence: Mapping[str, Any],
    quota_evidence: Mapping[str, Any],
    support_evidence: Mapping[str, Any],
    customer_health_evidence: Mapping[str, Any],
) -> dict[str, Any]:
    trusted = _scope(trusted_scope)
    source = (
        dict(value_bound_service)
        if isinstance(value_bound_service, Mapping)
        else {}
    )
    blockers: list[str] = []

    if not all(trusted.values()):
        blockers.append("TRUSTED_SCOPE_INVALID")
    if source.get("schema") != SOURCE_SCHEMA:
        blockers.append("VALUE_BOUND_SERVICE_SCHEMA_INVALID")
    if source.get("state") != "DRAFT_FOR_OWNER_ACTIVATION":
        blockers.append("VALUE_BOUND_SERVICE_NOT_DRAFT")
    if source.get("activation_state") != "BLOCKED_UNTIL_OWNER_ACTIVATION":
        blockers.append("VALUE_BOUND_SERVICE_ACTIVATION_BOUNDARY_INVALID")
    if source.get("blockers"):
        blockers.append("VALUE_BOUND_SERVICE_HAS_BLOCKERS")
    if source.get("owner_activation_required") is not True:
        blockers.append("VALUE_BOUND_OWNER_ACTIVATION_BOUNDARY_MISSING")

    for key in UNSAFE_SOURCE_FIELDS:
        if source.get(key) is not False:
            blockers.append("VALUE_BOUND_UNSAFE_FIELD:" + key)

    contract = source.get("contract")
    contract = dict(contract) if isinstance(contract, Mapping) else {}
    if _scope(contract) != trusted:
        blockers.append("VALUE_BOUND_SERVICE_SCOPE_MISMATCH")

    customer_id = _text(source.get("customer_id"), 120)
    contract_customer_id = _text(contract.get("customer_id"), 120)
    if not customer_id:
        blockers.append("VALUE_BOUND_CUSTOMER_ID_REQUIRED")
    if customer_id != contract_customer_id:
        blockers.append("VALUE_BOUND_CUSTOMER_CONTRACT_MISMATCH")

    pilot_id = _text(source.get("pilot_id"), 120)
    if not pilot_id:
        blockers.append("VALUE_BOUND_PILOT_ID_REQUIRED")

    package = _text(source.get("package"), 40).upper()
    contract_package = _text(contract.get("package"), 40).upper()
    if not package:
        blockers.append("VALUE_BOUND_PACKAGE_REQUIRED")
    if package != contract_package:
        blockers.append("VALUE_BOUND_PACKAGE_CONTRACT_MISMATCH")

    contract_digest = _text(source.get("contract_digest"), 180)
    conversion_digest = _text(
        source.get("value_bound_conversion_digest"),
        180,
    )
    if not contract_digest:
        blockers.append("VALUE_BOUND_CONTRACT_DIGEST_REQUIRED")
    if not conversion_digest:
        blockers.append("VALUE_BOUND_CONVERSION_DIGEST_REQUIRED")

    evidence_inputs = (
        ("OWNER_ACTIVATION", owner_activation_attestation),
        ("TENANT_EVIDENCE", tenant_evidence),
        ("FINOPS_EVIDENCE", finops_evidence),
        ("QUOTA_EVIDENCE", quota_evidence),
        ("SUPPORT_EVIDENCE", support_evidence),
        ("CUSTOMER_HEALTH_EVIDENCE", customer_health_evidence),
    )
    for prefix, raw in evidence_inputs:
        blockers.extend(
            _optional_identity_mismatch(
                raw,
                customer_id=customer_id,
                pilot_id=pilot_id,
                prefix=prefix,
            )
        )

    base_cycle = evaluate_managed_service_cycle(
        source,
        owner_activation_attestation=owner_activation_attestation,
        tenant_evidence=tenant_evidence,
        finops_evidence=finops_evidence,
        quota_evidence=quota_evidence,
        support_evidence=support_evidence,
        customer_health_evidence=customer_health_evidence,
    )

    cycle = dict(base_cycle) if isinstance(base_cycle, Mapping) else {}
    if _scope(cycle) != trusted:
        blockers.append("SERVICE_CYCLE_SCOPE_MISMATCH")
    if _text(cycle.get("customer_id"), 120) != customer_id:
        blockers.append("SERVICE_CYCLE_CUSTOMER_MISMATCH")
    if _text(cycle.get("package"), 40).upper() != package:
        blockers.append("SERVICE_CYCLE_PACKAGE_MISMATCH")
    if cycle.get("blockers"):
        blockers.extend(
            "SERVICE_CYCLE:" + _text(item, 180)
            for item in list(cycle.get("blockers") or [])[:40]
            if _text(item, 180)
        )
    if not _text(cycle.get("evidence_digest"), 180):
        blockers.append("SERVICE_CYCLE_EVIDENCE_DIGEST_REQUIRED")

    if blockers:
        state = "BLOCKED"
        decision = "BLOCKED"
    else:
        state = cycle.get("state")
        decision = cycle.get("decision")

    evidence = {
        "scope": trusted,
        "customer_id": customer_id,
        "pilot_id": pilot_id,
        "package": package,
        "contract_digest": contract_digest,
        "value_bound_conversion_digest": conversion_digest,
        "source_cycle_digest": _text(cycle.get("evidence_digest"), 180),
        "state": state,
        "decision": decision,
    }

    return {
        "schema": SCHEMA,
        "state": state,
        "decision": decision,
        "scope": dict(trusted),
        "owner_id": trusted["owner_id"],
        "tenant_id": trusted["tenant_id"],
        "workspace_id": trusted["workspace_id"],
        "customer_id": customer_id,
        "pilot_id": pilot_id,
        "package": package,
        "health_score": cycle.get("health_score"),
        "observed_roi_pct": cycle.get("observed_roi_pct"),
        "actual_service_cost_brl": cycle.get("actual_service_cost_brl"),
        "review_reasons": list(cycle.get("review_reasons") or [])[:40],
        "incident_reasons": list(cycle.get("incident_reasons") or [])[:40],
        "blockers": list(dict.fromkeys(blockers)),
        "contract_digest": contract_digest,
        "value_bound_conversion_digest": conversion_digest,
        "source_cycle_evidence_digest": _text(
            cycle.get("evidence_digest"),
            180,
        ),
        "evidence_digest": _digest(evidence),
        "owner_review_required": True,
        "customer_visible": False,
        "contains_internal_finops": True,
        "requires_customer_safe_projection": True,
        "automatic_renewal": False,
        "automatic_expansion": False,
        "automatic_package_change": False,
        "automatic_pause": False,
        "automatic_termination": False,
        "automatic_billing": False,
        "automatic_quota_increase": False,
        "automatic_role_change": False,
        "automatic_integration_change": False,
        "automatic_customer_contact": False,
        "automatic_provisioning": False,
        "automatic_deploy": False,
        "provider_called": False,
        "production_mutation": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "SOURCE_SCHEMA",
    "UNSAFE_SOURCE_FIELDS",
    "evaluate_value_bound_service_cycle",
]
