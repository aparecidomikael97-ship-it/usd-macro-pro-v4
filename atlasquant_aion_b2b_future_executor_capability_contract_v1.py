"""AION B2B future executor capability/readiness contract V1.

Design-only specification. It describes the proofs and abstract capabilities a
future executor would have to satisfy before implementation could even be
reviewed. It never selects a provider, endpoint, credential, HTTP method,
payload, token, command or production target.

A positive result is NOT execution authority and is NOT permission to implement
a real executor.
"""
from __future__ import annotations

from typing import Any, Mapping

import atlasquant_aion_b2b_future_executor_boundary_v2 as boundary

SCHEMA = "ATLASQUANT_AION_B2B_FUTURE_EXECUTOR_CAPABILITY_CONTRACT_V1"
READY = "READY_FOR_FUTURE_EXECUTOR_CAPABILITY_DESIGN_REVIEW"
NEXT_ALLOWED_STEP = "DESIGN_REAL_RECEIPT_AUTHENTICATOR_CONTRACT_ONLY"

ACTION_OPERATION_KIND = {
    "RENEWAL": "CONTRACT_CONTINUITY",
    "RENEWAL_WITH_CHANGES": "CONTRACT_CHANGE",
    "NON_RENEWAL": "SERVICE_OFFBOARDING",
    "REMEDIATION": "SERVICE_REMEDIATION",
    "CAPACITY_RESCOPE": "CAPACITY_CHANGE",
    "REPRICING": "COMMERCIAL_PRICING_CHANGE",
    "INCIDENT_REMEDIATION": "INCIDENT_REMEDIATION",
    "SERVICE_PAUSE": "SERVICE_PAUSE",
    "SERVICE_TERMINATION": "SERVICE_TERMINATION",
}

REQUIRED_FUTURE_PROOFS = (
    "AUTHENTICATED_REAL_RECEIPT_CONTRACT",
    "PERSISTENT_IDEMPOTENCY_AND_REPLAY_GUARD",
    "PRODUCTION_ROLLBACK_OR_COMPENSATION_PROOF",
    "FRESH_OWNER_EXECUTION_AUTHORIZATION",
    "FINOPS_RUNTIME_BUDGET_GUARD",
    "TENANT_SCOPE_BINDING",
    "PROVIDER_ADAPTER_ATTESTATION",
    "OBSERVABILITY_AND_AUDIT_RECEIPT",
)

FORBIDDEN_IMPLEMENTATION_MATERIAL = (
    "provider_selection",
    "provider_endpoint",
    "credential",
    "secret",
    "token",
    "http_method",
    "headers",
    "payload",
    "shell_command",
    "executable_command",
    "production_target",
)

FALSE_FIELDS = (
    "executor_created",
    "executor_selected",
    "executor_implementation_allowed",
    "provider_selection_allowed",
    "provider_selected",
    "provider_bound",
    "provider_called",
    "network_called",
    "credential_material_included",
    "secret_material_included",
    "provider_endpoint_included",
    "http_method_included",
    "headers_included",
    "executable_payload_included",
    "execution_token_issued",
    "shell_command_generated",
    "execution_command_generated",
    "execution_command_executed",
    "business_action_authorized",
    "billing_authorized",
    "customer_contact_authorized",
    "crm_write_authorized",
    "provisioning_authorized",
    "deploy_authorized",
    "production_mutation_authorized",
    "production_mutation_performed",
    "external_action_executed",
    "executes_action",
)


def _result(state: str, blockers=(), **fields) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": state,
        "blockers": sorted(set(blockers)),
        **fields,
        **{key: False for key in FALSE_FIELDS},
    }


def build_future_executor_capability_contract(
    *,
    boundary_review: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Build a provider-neutral design contract from an approved design boundary."""
    row = dict(boundary_review) if isinstance(boundary_review, Mapping) else {}
    blockers: list[str] = []

    if row.get("schema") != boundary.SCHEMA:
        blockers.append("BOUNDARY_V2_SCHEMA_REQUIRED")
    if row.get("state") != boundary.READY:
        blockers.append("BOUNDARY_V2_DESIGN_REVIEW_REQUIRED")
    if row.get("design_review_eligible") is not True:
        blockers.append("BOUNDARY_V2_NOT_DESIGN_ELIGIBLE")
    if row.get("executor_contract_design_only") is not True:
        blockers.append("BOUNDARY_V2_NOT_DESIGN_ONLY")
    if row.get("next_allowed_step") != boundary.NEXT_ALLOWED_STEP:
        blockers.append("BOUNDARY_V2_NEXT_STEP_INVALID")

    for key in boundary.FALSE_FIELDS:
        if row.get(key) is not False:
            blockers.append("BOUNDARY_V2_UNSAFE_FIELD:" + key)

    if blockers:
        return _result(
            "BLOCKED",
            blockers,
            capability_design_only=True,
            fresh_owner_authorization_required=True,
            authorization_reuse_allowed=False,
            independent_dynamic_audit_pending=True,
        )

    return _result(
        READY,
        [],
        capability_design_only=True,
        provider_neutral=True,
        fresh_owner_authorization_required=True,
        authorization_reuse_allowed=False,
        real_receipt_authenticator_required=True,
        persistent_idempotency_required=True,
        replay_protection_required=True,
        production_rollback_or_compensation_required=True,
        runtime_finops_guard_required=True,
        tenant_scope_binding_required=True,
        provider_adapter_attestation_required=True,
        observability_audit_receipt_required=True,
        independent_dynamic_audit_pending=bool(
            row.get("independent_dynamic_audit_pending", True)
        ),
        supported_action_families=tuple(ACTION_OPERATION_KIND),
        operation_contracts=dict(ACTION_OPERATION_KIND),
        required_future_proofs=REQUIRED_FUTURE_PROOFS,
        forbidden_implementation_material=FORBIDDEN_IMPLEMENTATION_MATERIAL,
        next_allowed_step=NEXT_ALLOWED_STEP,
    )


__all__ = [
    "SCHEMA",
    "READY",
    "NEXT_ALLOWED_STEP",
    "ACTION_OPERATION_KIND",
    "REQUIRED_FUTURE_PROOFS",
    "FORBIDDEN_IMPLEMENTATION_MATERIAL",
    "FALSE_FIELDS",
    "build_future_executor_capability_contract",
]
